"""Part 2: the cheapest ATLAS entry (research/atlasfill/DESIGN.md, pre-registered 9e574345). PAPER RESEARCH ONLY.
    python -X utf8 research/atlasfill/entries.py build        # variants + fixed $250 table -> entries.json, trades.json.gz
    python -X utf8 research/atlasfill/entries.py engines X3   # one variant through the real engines (own process)
    python -X utf8 research/atlasfill/entries.py all          # everything (subprocesses) + the gate
"""
from __future__ import annotations

import gzip
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "atlas2"))
import atlas2 as A2  # noqa: E402  (fixed scoring, tables, the real-engine runner)

OUT = os.path.join(HERE, "entries.json")
TRADES = os.path.join(HERE, "trades.json.gz")
FOR = os.path.join(HERE, "forensics.json")
TICK = 0.25
FAST = math.sqrt(1.5 / 4.0)
VARIANTS = {
    "X0": {"what": "market today (give-away s x first-minute run)", "k": 1.0},
    "X1": {"what": "fast send (fast_entry ON + pre-built order): s x sqrt(1.5/4)", "k": FAST},
    "X1b": {"what": "fast send, bad case: s x 0.8", "k": 0.8, "scenario_only": True},
    "X2": {"what": "marketable limit cap 4 ticks, rest 5 min", "k": 1.0, "cap": 4, "timeout": 5},
    "X3": {"what": "marketable limit cap 8 ticks, rest 5 min", "k": 1.0, "cap": 8, "timeout": 5},
    "X4": {"what": "marketable limit cap 8 ticks, rest 15 min", "k": 1.0, "cap": 8, "timeout": 15},
    "X5": {"what": "marketable limit cap 12 ticks, rest 15 min", "k": 1.0, "cap": 12, "timeout": 15},
    "X6": {"what": "fast send + cap 8 ticks, rest 15 min", "k": FAST, "cap": 8, "timeout": 15},
    "F12": {"what": "reference: flat 12 ticks (atlas2 base)", "flat": 12, "reference": True},
    "F14": {"what": "reference: flat 14 ticks (the 4 real fills' mean)", "flat": 14, "reference": True},
}


def calib():
    """s from the real ATLAS fills (part 1); r = mean fav1 / mean fav5 over the 2026 ATLAS signals."""
    F = json.load(open(FOR, encoding="utf-8"))
    s = float(F["atlas"]["share_of_fav1_mean"])
    AF = A2._AF()
    B5, B1 = AF._bars()
    f1, f5 = [], []
    for u in AF.units():
        d, et_ = int(u["dir"]), int(u["entry_t"])
        k5, o = AF._open5(u)
        j = int(np.searchsorted(B1.t, et_))
        if j < len(B1.t) and int(B1.t[j]) == et_:
            f1.append((B1.h[j] - B1.o[j]) if d == 1 else (B1.o[j] - B1.l[j]))
            f5.append((B5.h[k5] - o) if d == 1 else (o - B5.l[k5]))
    return s, float(np.mean(f1)) / float(np.mean(f5)), len(f1)


def giveaway(u, s, r):
    """(give-away ticks for a market order arriving ~4 s after the open, which bars were used)."""
    AF = A2._AF()
    B5, B1 = AF._bars()
    d, et_ = int(u["dir"]), int(u["entry_t"])
    j = int(np.searchsorted(B1.t, et_))
    if j < len(B1.t) and int(B1.t[j]) == et_:
        fav = (B1.h[j] - B1.o[j]) if d == 1 else (B1.o[j] - B1.l[j])
        return max(1.0, round(s * fav / TICK)), "1m"
    k5, o = AF._open5(u)
    fav5 = (B5.h[k5] - o) if d == 1 else (o - B5.l[k5])
    return max(1.0, round(s * r * fav5 / TICK)), "5m"


def capped(u, D, cap, timeout):
    """marketable limit `cap` ticks past the open: (cost ticks | None = no trade, fill time)."""
    if D <= cap:
        return D, int(u["entry_t"])
    AF = A2._AF()
    B5, B1 = AF._bars()
    d, et_ = int(u["dir"]), int(u["entry_t"])
    k5, o = AF._open5(u)
    need = o * d + cap * TICK - TICK                     # dir space: price must trade 1 tick better than the cap
    fill_t = None
    j = int(np.searchsorted(B1.t, et_))
    if j < len(B1.t) and int(B1.t[j]) == et_:
        for m in range(timeout):
            if j + m >= len(B1.t) or int(B1.t[j + m]) >= et_ + 60 * timeout:
                break
            q = float(B1.c[j]) * d if m == 0 else (float(B1.l[j + m]) if d == 1 else -float(B1.h[j + m]))
            if q <= need:
                fill_t = (int(B1.t[j + m]), 60); break
    else:
        for m in range(max(1, timeout // 5)):
            k = k5 + m
            if k >= len(B5.t) or int(B5.t[k]) >= et_ + 60 * max(5, timeout):
                break
            q = float(B5.c[k]) * d if m == 0 else (float(B5.l[k]) if d == 1 else -float(B5.h[k]))
            if q <= need:
                fill_t = (int(B5.t[k]), 300); break
    if fill_t is None:
        return None, None
    t0, ln = fill_t
    if AF.is_target(u) and int(u["exit_t"]) < t0 + ln:
        return None, None
    if not AF.is_target(u) and int(u["exit_t"]) < t0:
        return None, None
    return float(cap), t0


def price(u, ticks_from_open):
    """the stored unit enters 1 tick past the open; price it at `ticks_from_open` on the entry, 2 on a market / stop exit."""
    AF = A2._AF()
    return AF.priced(u, ticks_from_open, A2.X_MKT)


def build(say=print):
    AF = A2._AF()
    s, r, n1 = calib()
    U = AF.units()
    res, dump, cost_seen = {}, {}, {}
    for v, V in VARIANTS.items():
        P, D_all = [], []
        for u in U:
            if V.get("flat"):
                P.append(price(u, V["flat"])); continue
            D, src = giveaway(u, s * V["k"], r)
            if V.get("k") != 1.0:
                D = max(1.0, round(giveaway(u, s, r)[0] * V["k"]))
            if V.get("cap"):
                c, _ = capped(u, D, V["cap"], V["timeout"])
                if c is None:
                    continue
                D = c
            D_all.append((u["day"], D, src))
            P.append(price(u, D))
        T = AF.to_T(P)
        for t in T:
            t["R_c"] = A2.r_cost(t)
        dump[v] = T
        res[v] = {"what": V["what"], "trades": len(T), **A2.table(T)}
        if D_all:
            cost_seen[v] = {sp: round(float(np.mean([d for day, d, _ in D_all if a <= day <= z])), 2) for sp, (a, z) in A2.SPANS.items()}
            res[v]["mean_entry_ticks"] = cost_seen[v]
        x = res[v]
        say(f"{v:4s} {V['what'][:52]:52s} " + " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['net']}" for sp in A2.SPANS)
            + f" | cost {cost_seen.get(v)}", flush=True)
    with gzip.open(TRADES, "wt", encoding="utf-8") as fh:
        json.dump(dump, fh, default=float)
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    old.update({"made": "2026-11-26", "design": "research/atlasfill/DESIGN.md (9e574345)",
                "calibration": {"s_share_of_first_minute_run": round(s, 3), "r_fav1_over_fav5_2026": round(r, 3), "n_2026_signals_1m": n1,
                                "fast_factor": round(FAST, 3)}, "fixed": res})
    json.dump(old, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    return res


def engines(v, n=600):
    A2.TRADES, A2.HERE = TRADES, HERE
    return A2.cmd_engines(v, n)


def gate(res):
    F, E = res["fixed"], res["engines"]
    b, be = F["X0"], E["X0"]
    out = {}
    for v, V in VARIANTS.items():
        if v == "X0" or V.get("reference") or V.get("scenario_only") or v not in E:
            continue
        x, e = F[v], E[v]
        fx = all(x[sp]["net"] > b[sp]["net"] for sp in A2.SPANS)
        fu = all(e["funded_25k"]["funded"][s]["per_month"] >= be["funded_25k"]["funded"][s]["per_month"] for s in ("H1", "H2"))
        bl = all(e["builder"]["mffu_builder_50k"][s]["slot"]["net_6m"] >= be["builder"]["mffu_builder_50k"][s]["slot"]["net_6m"] for s in ("H1", "H2"))
        tpw = all(1.5 <= x[sp]["tpw"] <= 4.1 for sp in A2.SPANS)
        out[v] = {"fixed_all_3_better": fx, "funded_h1_h2_ok": fu, "builder50_h1_h2_ok": bl, "tpw_ok": tpw,
                  "pass": fx and fu and bl and tpw, "proven": not v.startswith(("X1", "X6")),
                  "funded_h2": e["funded_25k"]["funded"]["H2"]["per_month"]}
    P = sorted([v for v in out if out[v]["pass"]], key=lambda v: -out[v]["funded_h2"])
    proven = [v for v in P if out[v]["proven"]]
    verdict = {"winner": P[0] if P else None, "best_proven": proven[0] if proven else None,
               "words": (f"{P[0]} wins" + ("" if out[P[0]]["proven"] else " (as a Sim101 measurement, not proven on bars)")
                         + (f"; best bar-proven: {proven[0]}" if proven and proven[0] != P[0] else "")) if P else
               "no entry beats today's market order on every span and engine"}
    return out, verdict


def all_(say=print):
    build(say)
    eng = {}
    for v, V in VARIANTS.items():
        if V.get("reference") and v != "F14":
            continue
        subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "engines", v], check=True)
        p = os.path.join(HERE, f"_eng_{v}.json")
        eng[v] = json.load(open(p, encoding="utf-8")); os.remove(p)
    res = json.load(open(OUT, encoding="utf-8"))
    res["engines"] = eng
    res["gate"], res["verdict"] = gate(res)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    say(json.dumps(res["gate"], indent=0)); say(res["verdict"])
    return res


if __name__ == "__main__":
    a = sys.argv[1:] or ["build"]
    {"build": lambda: build(), "engines": lambda: engines(a[1]), "all": lambda: all_()}[a[0]]()
