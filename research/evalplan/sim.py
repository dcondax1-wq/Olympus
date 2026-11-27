"""Order flow lane A on the owner's 4 MFFU accounts: rollout sim (2026-11-27). PAPER RESEARCH ONLY.
Design (committed before the run): research/evalplan/DESIGN.md.

    python -X utf8 research/evalplan/sim.py [--n 1000]   -> research/evalplan/results.json (+ printed table)
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
sys.path.insert(0, os.path.join(ROOT, "research", "alloc"))
try:                                              # numba-free fallback (cloud without numba): njit = plain Python (slower BLITZ load)
    import numba  # noqa: F401
except ImportError:
    import types
    _nb = types.ModuleType("numba")
    _nb.njit = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
    _nb.jit = _nb.njit
    _nb.prange = range
    sys.modules["numba"] = _nb
import alloc as AL  # noqa: E402  (book.py + rank.py engines, today's account state)

BK, R, U, SOA = AL.BK, AL.R, AL.U, AL.SOA
RL = R.RL
SPANS = ("H1", "H2", "REF")
LEN, H_EVAL = 126, 60
VERDICT = os.path.join(ROOT, "research", "orderflow", "real_verdict.json")
SCEN = {"REAL": 0.50, "Q25": None, "ZERO": 1.0 / 3.0, "BAD": 0.24}
SIZES = {"SMALL": (100.0, 200.0), "FULL": (250.0, 500.0)}


def pool():
    d = json.load(open(VERDICT, encoding="utf-8"))
    rows = d["rows"]
    tk = [r for r in rows if r["taken"]]
    days = sorted({r["day"] for r in rows})
    stops = [abs(r["usd_1"] / r["R"]) / 2.0 for r in tk if r["R"]]
    mean_r = float(np.mean([r["R"] for r in tk]))
    return {"n": len(tk), "days": len(days), "rate": len(tk) / len(days), "stops": stops, "mean_R": mean_r,
            "win": sum(1 for r in tk if r["R"] > 0) / len(tk)}


def p_of(scen, P):
    if scen == "Q25":
        return (1.0 + 0.25 * P["mean_R"]) / 3.0
    return SCEN[scen]


def of_draws(P, p_win, n_paths, n_steps, seed):
    """(n_paths, n_steps) arrays: has a trade, stop pts, win?"""
    g = np.random.default_rng(seed)
    has = g.random((n_paths, n_steps)) < P["rate"]
    stop = np.array(P["stops"])[g.integers(0, len(P["stops"]), (n_paths, n_steps))]
    win = g.random((n_paths, n_steps)) < p_win
    return has, stop, win


def of_trade(stop, win):
    pts = 2.0 * stop if win else -stop
    return {"day": "of", "risk": float(stop), "tgt": 2.0 * float(stop), "pts": float(pts),
            "w1": float(-0.5 * stop if win else -stop), "entry_t": 2_000_000_000, "exit_t": 2_000_000_001, "dir": 1,
            "strat": "OFA", "tf": 1}


def day(base, i, k, D, mode):
    if D is None or not D[0][i, k]:
        return base
    if mode == "quiet" and base:
        return base
    return list(base) + [of_trade(D[1][i, k], D[2][i, k])]


def run_eval(sp, A, paths, D, mode):
    res = []
    for i, seq in enumerate(paths):
        e = AL.set_eval(sp["ev"](), A)
        out, used = "open", H_EVAL
        for k, si in enumerate(seq[:H_EVAL]):
            r, _ = e.step(day(sp["BYe"][si], i, k, D, mode))
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used))
    n = len(res)
    pas = [u for o, u in res if o == "pass"]
    return {"pass": round(100.0 * len(pas) / n, 1), "fail": round(100.0 * sum(1 for o, _ in res if o == "fail") / n, 1),
            "med_days": float(np.median(pas)) if pas else None}


def run_slot(sp, A, paths, D, mode):
    """alloc.slot_from with the OF lane injected (same re-buy logic)."""
    net, lost_n, pays_n = [], [], []
    for i, seq in enumerate(paths):
        cost, owner, lost, pays = 0.0, 0.0, 0, 0
        if A["stage"] == "eval":
            e, f, wait = AL.set_eval(sp["ev"](), A), None, 0
        else:
            e, f, wait = None, AL.set_funded(sp["fund"](), A), 0
        for k, si in enumerate(seq[:LEN]):
            if e is not None:
                r, _ = e.step(day(sp["BYe"][si], i, k, D, mode))
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
            ev, x, _ = f.step(day(sp["BYf"][si], i, k, D, mode))
            if ev in ("paid", "grad"):
                owner += x
                pays += 1
            if ev in ("lost", "grad"):
                lost += ev == "lost"
                f = None
                e = sp["ev"]()
                cost += sp["price"]
        net.append(owner - cost)
        lost_n.append(lost)
        pays_n.append(pays)
    net = np.array(net)
    return {"net": round(float(net.mean())), "per_month": round(float(net.mean()) / 6.0), "p10": round(float(np.percentile(net, 10))),
            "lost": round(100.0 * sum(1 for x in lost_n if x) / len(net), 1),
            "no_pay": round(100.0 * sum(1 for p in pays_n if not p) / len(net), 1)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    t0 = time.time()
    P = pool()
    print(f"lane A pool: {P['n']} trades on {P['days']} days (rate {P['rate']:.2f}/day), won {P['win']:.0%}, mean {P['mean_R']:+.2f}R, "
          f"stop median {np.median(P['stops']):.0f} pts (max {max(P['stops']):.0f})", flush=True)
    S = SOA.data()["S"]
    PF = {s: U.mc_paths(S, s, a.n, length=LEN, seed=23) for s in SPANS}
    PE = {s: U.mc_paths(S, s, a.n, length=H_EVAL, seed=7) for s in SPANS}
    out = {"n": a.n, "pool": {k: v for k, v in P.items() if k != "stops"}, "stops_pts": sorted(round(x, 1) for x in P["stops"]),
           "scen_p": {s: round(p_of(s, P), 3) for s in SCEN}, "cells": {}}
    settings = [("none", None, None, "after")]
    for sz in SIZES:
        for sc in SCEN:
            settings.append((f"{sz}|{sc}", sz, sc, "after"))
    for sc in ("REAL", "ZERO"):
        settings.append((f"SMALL|{sc}|quiet", "SMALL", sc, "quiet"))
    for aid, A in AL.ACCTS.items():
        big = "50k" in A["plan"]
        for lab, sz, sc, mode in settings:
            sp = BK.build(A["plan"], A["today"])
            if sz:
                sp["z"]["OFA"] = {"usd": SIZES[sz][1 if big else 0], "f": 0.3}
            BK.CFG.clear()
            BK.CFG.update(sp["knobs"])
            row = {}
            for s in SPANS:
                if sz:
                    pw = p_of(sc, P)
                    DE = of_draws(P, pw, a.n, H_EVAL, 101)
                    DF = of_draws(P, pw, a.n, LEN, 202)
                else:
                    DE = DF = None
                row[s] = {"eval": run_eval(sp, A, PE[s], DE, mode) if A["stage"] == "eval" else None,
                          "slot": run_slot(sp, A, PF[s], DF, mode)}
            BK.CFG.clear()
            out["cells"][f"{aid}|{lab}"] = row
            ev = lambda s: (f"pass {row[s]['eval']['pass']:>5}% ~{row[s]['eval']['med_days']}d fail {row[s]['eval']['fail']:>5}% "
                            if row[s]["eval"] else "")
            print(f"{aid} {lab:18s} " + " | ".join(f"{s} {ev(s)}6m ${row[s]['slot']['net']:>6} p10 {row[s]['slot']['p10']:>6} "
                                                   f"lost {row[s]['slot']['lost']:>5}%" for s in SPANS)
                  + f" [{time.time() - t0:.0f}s]", flush=True)
    # the pre-registered rule
    verdict = {}
    for aid, A in AL.ACCTS.items():
        base = out["cells"][f"{aid}|none"]
        price = R.PLANS[A["plan"]]
        v = {}
        for sz in SIZES:
            c = lambda sc, s: out["cells"][f"{aid}|{sz}|{sc}"][s]["slot"]["net"]
            better = all(c(sc, s) > base[s]["slot"]["net"] for sc in ("REAL", "Q25") for s in ("H1", "H2"))
            zero_cost = base["H2"]["slot"]["net"] - c("ZERO", "H2")
            v[sz] = {"real_q25_beat_both_halves": better, "zero_cost_H2": zero_cost, "price": price,
                     "worth_forward_plan": bool(better and zero_cost <= price)}
        verdict[aid] = v
    out["verdict"] = verdict
    json.dump(out, open(os.path.join(HERE, "results.json"), "w", encoding="utf-8"), indent=1, default=float)
    print("VERDICT", json.dumps(verdict))


if __name__ == "__main__":
    main()
