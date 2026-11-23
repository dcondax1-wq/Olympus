"""BLITZ at real fills on the one-account book (2026-11-23). PAPER RESEARCH ONLY. Design: research/blitzfills/DESIGN.md
(committed before this run). Engine = research/onebook/book.py (rank.py real fills, ATLAS 10 ticks), same paths.

    python -X utf8 research/blitzfills/run.py [--n 1000]   -> research/blitzfills/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "onebook"))
import book as BK  # noqa: E402  (patches rank.py: ATLAS at 10 ticks, BLITZ kept)

R, RL, SOA, U = BK.R, BK.RL, BK.SOA, BK.U
TICK = 0.25
OUT = os.path.join(HERE, "results.json")
PLAN = "mffu_rapid_eod_50k"
F_MEAS, F_LOW = 0.39, 0.29
B0 = list(BK._blitz0())                          # the stored BLITZ trades (1 tick a side)


def _reach():
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    ix = {int(t): i for i, t in enumerate(df.time)}
    O, H, L = df.open.values, df.high.values, df.low.values
    out = {}
    for t in B0:
        if t["tf"] != 1:
            continue
        i = ix.get(int(t["entry_t"]))
        if i is not None:
            out[(t["entry_t"], t["dir"])] = float(H[i] - O[i]) if t["dir"] > 0 else float(O[i] - L[i])
    return out


def priced(t, se, sx):
    """tools/atlas_fills.priced for a BLITZ unit: se / sx = total ticks on the entry / every exit (stored = 1 + 1)."""
    pts = float(t["pts"]) - (se - 1) * TICK - (sx - 1) * TICK
    w1 = min(0.0, float(t["w1"]) - (se - 1) * TICK, pts)
    return {**t, "pts": round(pts, 4), "w1": round(w1, 4), "fill_e": se, "fill_x": sx}


def variants():
    RE = _reach()

    def meas(f):
        ticks = {k: 1 + int(f * v / TICK) for k, v in RE.items()}
        med = int(np.median(list(ticks.values())))
        return [priced(t, ticks.get((t["entry_t"], t["dir"]), med) if t["tf"] == 1 else med, 1) for t in B0], med, ticks
    fm, med_m, tk_m = meas(F_MEAS)
    fl, med_l, tk_l = meas(F_LOW)
    V = {"F0 stored (1 tick)": B0, "FM measured (0.39 x reach)": fm, "FL measured-low (0.29 x reach)": fl,
         "T3 (3 ticks a side)": [priced(t, 3, 3) for t in B0], "T6 (6 ticks a side)": [priced(t, 6, 6) for t in B0],
         "T10 (10 ticks a side)": [priced(t, 10, 10) for t in B0]}
    tv = np.array(list(tk_m.values()))
    info = {"reach_pts": {"median": float(np.median(list(RE.values()))), "mean": round(float(np.mean(list(RE.values()))), 2),
                          "n": len(RE)},
            "FM_entry_ticks": {"median": med_m, "mean": round(float(tv.mean()), 1), "p25": float(np.percentile(tv, 25)),
                               "p75": float(np.percentile(tv, 75)), "usd_per_micro_median": round((med_m - 1) * TICK * 2.0, 2)},
            "FL_entry_ticks_median": med_l}
    return V, info


def use(T):
    SOA._blitz = lambda T=T: list(T)
    SOA._D.clear()
    RL._MB.clear()


BK.BOOKS["PB B11 + BLITZ $300"] = (BK.LA + ("BLITZ",), BK.LA + ("BLITZ",), {"lit_e": 0.5}, None, {"BLITZ": 300})


def blitz_alone(S):
    BY = RL.mix_by(("BLITZ",))
    usd = {s: 0.0 for s in RL.PRI}
    usd["BLITZ"] = 300.0
    return {s: SOA.plain_stats(BY, S, s, usd) for s in R.SPANS}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    t0 = time.time()
    V, info = variants()
    print("fills:", json.dumps(info), flush=True)
    use(B0)
    S = SOA.data()["S"]
    PF = {s: U.mc_paths(S, s, a.n, length=R.LEN, seed=23) for s in R.SPANS}
    PE = {s: U.mc_paths(S, s, a.n, length=R.H_EVAL, seed=7) for s in R.SPANS}
    base = {}
    for bk in ("B01 LIT only", "B11 size split: LIT x0.5 in the eval"):
        base[bk] = BK.run(PLAN, bk, PE, PF, S)
        print(BK.line(PLAN, bk, base[bk]), f"[{time.time() - t0:.0f}s]", flush=True)
    rows = {}
    for vn, T in V.items():
        use(T)
        rows[vn] = {"blitz_alone": blitz_alone(S)}
        for bk in ("PB B11 + BLITZ $300", "B12 LIT + ATLAS + BLITZ $300"):
            rows[vn][bk] = BK.run(PLAN, bk, PE, PF, S)
            print(vn, "|", BK.line(PLAN, bk, rows[vn][bk]), f"[{time.time() - t0:.0f}s]", flush=True)
    P, bar = base["B11 size split: LIT x0.5 in the eval"], base["B01 LIT only"]["H1"]["eval"]["fail"] + 2.0
    verdict = {}
    for vn in rows:
        pb = rows[vn]["PB B11 + BLITZ $300"]
        verdict[vn] = {"H1_beats": pb["H1"]["slot"]["net_6m"] > P["H1"]["slot"]["net_6m"],
                       "H2_beats": pb["H2"]["slot"]["net_6m"] > P["H2"]["slot"]["net_6m"],
                       "fail_ok": pb["H1"]["eval"]["fail"] <= bar,
                       "REF_not_worse": pb["REF"]["slot"]["net_6m"] >= P["REF"]["slot"]["net_6m"],
                       "gain_per_month": {s: round((pb[s]["slot"]["net_6m"] - P[s]["slot"]["net_6m"]) / 6.0) for s in R.SPANS}}
        verdict[vn]["joins"] = all(verdict[vn][k] for k in ("H1_beats", "H2_beats", "fail_ok", "REF_not_worse"))
    out = {"n": a.n, "plan": PLAN, "fills": info, "fail_bar_h1": bar, "base": base, "rows": rows, "verdict": verdict,
           "rule": "FM primary (DESIGN.md)", "secs": round(time.time() - t0)}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    for vn, v in verdict.items():
        print("VERDICT", vn, v)


if __name__ == "__main__":
    main()
