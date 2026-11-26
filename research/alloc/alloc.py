"""Multi-account allocation optimizer (2026-11-26). Design: research/alloc/DESIGN.md (pre-registered). Paper research only.

    python -X utf8 research/alloc/alloc.py [--n 1000]     -> research/alloc/results.json (+ printed tables)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "onebook"))
import logging  # noqa: E402
logging.disable(logging.WARNING)
import book as BK  # noqa: E402  (rank.py real fills + the book sizers)

R, U, SOA = BK.R, BK.U, BK.SOA
U.SPAN["2025"] = ("2025-01-01", "2025-12-31")
SPANS = ("H1", "H2", "REF", "2025")
LEN = 126
# today's state (board 2026-11-26 11:15 ET); bal / peak / floor are vs the start balance (MFFU's funded $0 view for A25)
ACCTS = {
    "Z50": {"plan": "mffu_builder_50k", "stage": "eval", "bal": -822.0, "room": 1009.0, "s": 27, "dtr": 14, "today": "B01 LIT only",
            "name": "Zlarior Builder 50K eval"},
    "Z25": {"plan": "mffu_builder_25k", "stage": "eval", "bal": 19.0, "room": 996.0, "s": 4, "dtr": 1, "today": "B01 LIT only",
            "name": "Zlarior 25K #2 eval"},
    "R25": {"plan": "mffu_rapid_eod_25k", "stage": "eval", "bal": -5.0, "room": 995.0, "s": 4, "dtr": 1,
            "today": "B03 LIT + ATLAS first-come", "name": "Rapid EOD 25K eval"},
    "A25": {"plan": "mffu_builder_25k", "stage": "funded", "bal": 401.0, "room": 1000.0, "s": 7, "dtr": 6, "today": "B02 ATLAS only",
            "name": "ATLAS Builder 25K funded"},
}


def set_eval(e, a):
    e.bal = a["bal"]
    e.floor = a["bal"] - a["room"]
    e.peak = e.floor + e.E["mll"]
    e.s, e.dtr = a["s"], a["dtr"]
    return e


def set_funded(f, a):
    f.bal = a["bal"]
    f.floor = a["bal"] - a["room"]
    f.peak = max(f.bal, f.floor + f.R["mll"])
    f.cyc_start = 0.0
    f.cyc = [round(a["bal"] / max(1, a["dtr"]), 2)] * a["dtr"] if a["bal"] > 0 else []
    return f


def slot_from(sp, paths, a):
    """rank.slot_run from today's state: (net per path, owner per path, payouts, lost, first pay)."""
    net, own, pays_n, lost_n, firsts = [], [], [], [], []
    for seq in paths:
        cost, owner, lost, pays, first = 0.0, 0.0, 0, 0, None
        if a["stage"] == "eval":
            e, f, wait = set_eval(sp["ev"](), a), None, 0
        else:
            e, f, wait = None, set_funded(sp["fund"](), a), 0
        for k, si in enumerate(seq[:LEN]):
            if e is not None:
                r, _ = e.step(sp["BYe"][si])
                if r == "pass":
                    e, wait = None, R.GAP
                elif r in ("fail", "stuck"):
                    e = sp["ev"]()
                    cost += sp["price"]
                continue
            if f is None:
                wait -= 1
                if wait <= 0:
                    f = sp["fund"]()
                continue
            ev, x, _ = f.step(sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x
                pays += 1
                first = first or k + 1
            if ev in ("lost", "grad"):
                lost += ev == "lost"
                f = None
                e = sp["ev"]()
                cost += sp["price"]
        net.append(owner - cost)
        own.append(owner)
        pays_n.append(pays)
        lost_n.append(lost)
        firsts.append(first)
    net = np.array(net)
    fp = [x for x in firsts if x]
    return net, {"mean": round(float(net.mean())), "p10": round(float(np.percentile(net, 10))), "p50": round(float(np.median(net))),
                 "owner": round(float(np.mean(own))), "fees": round(float(np.mean(own) - net.mean())),
                 "no_pay": round(100.0 * sum(1 for p in pays_n if not p) / len(net), 1),
                 "lost": round(100.0 * sum(1 for x in lost_n if x) / len(net), 1),
                 "first_pay": float(np.median(fp)) if fp else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    t0 = time.time()
    S = SOA.data()["S"]
    PF = {s: U.mc_paths(S, s, a.n, length=LEN, seed=23) for s in SPANS}
    books = list(BK.BOOKS)
    cells, nets = {}, {}
    for aid, A in ACCTS.items():
        for bk in books:
            sp = BK.build(A["plan"], bk)
            BK.CFG.clear()
            BK.CFG.update(sp["knobs"])
            row = {}
            for s in SPANS:
                n_, st = slot_from(sp, PF[s], A)
                row[s] = st
                nets[(aid, bk, s)] = n_
            BK.CFG.clear()
            cells[f"{aid}|{bk}"] = row
            print(f"{aid} {bk:56s} " + " | ".join(f"{s} ${row[s]['mean']:>6} p10 {row[s]['p10']:>6} lost {row[s]['lost']:>5}%"
                                                 for s in SPANS) + f" [{time.time() - t0:.0f}s]", flush=True)
    # per-account pick (DESIGN rule); + the same rule without BLITZ (post-hoc constraint: the BLITZ v2 study landed 2026-11-26
    # recommends retiring it) and the routing the already-built switches give (combo lanes ON, x0.5 in the eval: B08)
    def pick_rule(allowed):
        out = {}
        for aid, A in ACCTS.items():
            tb = A["today"]
            base = cells[f"{aid}|{tb}"]
            best, best_v = tb, None
            for bk in allowed:
                c = cells[f"{aid}|{bk}"]
                if bk == tb:
                    continue
                if not (c["H1"]["mean"] > base["H1"]["mean"] and c["H2"]["mean"] > base["H2"]["mean"]
                        and c["REF"]["mean"] >= base["REF"]["mean"] - 100):
                    continue
                v = c["H1"]["mean"] + c["H2"]["mean"]
                if best_v is None or v > best_v:
                    best, best_v = bk, v
            out[aid] = best
        return out
    pick_nb = pick_rule([b for b in books if "BLITZ" not in b])
    switches = {"Z50": "B08 ATLAS x0.5 in the eval, full funded", "Z25": "B08 ATLAS x0.5 in the eval, full funded",
                "R25": ACCTS["R25"]["today"], "A25": ACCTS["A25"]["today"]}
    pick = {}
    for aid, A in ACCTS.items():
        tb = A["today"]
        base = cells[f"{aid}|{tb}"]
        best, best_v = tb, None
        for bk in books:
            c = cells[f"{aid}|{bk}"]
            if bk == tb:
                continue
            if not (c["H1"]["mean"] > base["H1"]["mean"] and c["H2"]["mean"] > base["H2"]["mean"]
                    and c["REF"]["mean"] >= base["REF"]["mean"] - 100):
                continue
            v = c["H1"]["mean"] + c["H2"]["mean"]
            if best_v is None or v > best_v:
                best, best_v = bk, v
        pick[aid] = best
    # joint totals on the same paths: today's routing vs the pick
    joint = {}
    for lab, rt in (("today", {k: v["today"] for k, v in ACCTS.items()}), ("pick", pick), ("pick_no_blitz", pick_nb),
                    ("switches_only", switches)):
        jr = {}
        for s in SPANS:
            tot = sum(nets[(aid, rt[aid], s)] for aid in ACCTS)
            jr[s] = {"mean": round(float(tot.mean())), "p10": round(float(np.percentile(tot, 10))),
                     "p_neg": round(100.0 * float((tot < 0).mean()), 1), "p50": round(float(np.median(tot)))}
        joint[lab] = {"routing": rt, **jr}
    # the best single-account alternative per regime (for the table; not the pick rule)
    top = {aid: {s: max(books, key=lambda bk: cells[f"{aid}|{bk}"][s]["mean"]) for s in SPANS} for aid in ACCTS}
    d = {s: joint["pick"][s]["mean"] - joint["today"][s]["mean"] for s in SPANS}
    dd = {lab: {s: joint[lab][s]["mean"] - joint["today"][s]["mean"] for s in SPANS} for lab in joint}
    card = d["H1"] > 100 and d["H2"] > 100 and joint["pick"]["H1"]["p10"] >= joint["today"]["H1"]["p10"] - 200 \
        and joint["pick"]["H2"]["p10"] >= joint["today"]["H2"]["p10"] - 200
    out = {"n": a.n, "len": LEN, "accounts": ACCTS, "books": books, "cells": cells, "pick": pick, "joint": joint, "delta": d,
           "card": card, "top_by_regime": top, "deltas": dd,
           "note": "pick = the pre-registered rule; pick_no_blitz + switches_only = labelled constraints (BLITZ retire study; no new code)"}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
    print("PICK", pick)
    print("JOINT", json.dumps(joint))
    print("DELTA", d, "CARD", card)
    print("DELTAS", json.dumps(dd))
    print("PICK_NB", pick_nb)


if __name__ == "__main__":
    main()
