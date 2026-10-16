"""Overlap test: Nasdaq-100 CFD (NQX) vs NQ futures on the SAME days. Is the CFD a fair proxy for the strategy?"""
import sys

import numpy as np
import pandas as pd

from engine import backtest
from engine.data import load

A = sys.argv[1] if len(sys.argv) > 1 else "2026-08-06"
Z = sys.argv[2] if len(sys.argv) > 2 else "2026-08-28"
FREE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0, "days_from": A, "days_to": Z}

nq, nqx = load("NQ", "5m"), load("NQX", "5m")
a = pd.DataFrame({"t": nq.t, "c": nq.c, "h": nq.h, "l": nq.l, "d": nq.date_str}).set_index("t")
b = pd.DataFrame({"t": nqx.t, "c": nqx.c, "h": nqx.h, "l": nqx.l}).set_index("t")
j = a.join(b, rsuffix="_x", how="inner")
j = j[(j["d"] >= A) & (j["d"] <= Z)]
ra, rb = j["c"].pct_change(), j["c_x"].pct_change()
rng_a, rng_b = (j["h"] - j["l"]) / j["c"], (j["h_x"] - j["l_x"]) / j["c_x"]
print(f"overlapping 5m bars: {len(j)}  ({A} -> {Z})")
print(f"  5m return correlation        : {ra.corr(rb):.3f}")
print(f"  avg bar range NQ / CFD       : {rng_a.mean() * 1e4:.1f} / {rng_b.mean() * 1e4:.1f} bps")
print(f"  price basis (NQ - CFD)       : {np.median(j['c'] - j['c_x']):.1f} pts")


def stats(sym):
    tr = backtest.run(sym, "5m", FREE, light=True)["trades"]
    if not tr:
        return tr, "0 trades"
    r = np.array([t["pnl_r"] for t in tr]); m = np.array([t["mfe"] for t in tr])
    return tr, f"{len(tr):3d}t win {np.mean(r > 0) * 100:4.0f}% avgR {r.mean():+.2f} MFE {m.mean():.2f} hit1R {np.mean(m >= 1) * 100:3.0f}%"


ta_, sa = stats("NQ")
tb_, sb = stats("NQX")
print(f"\nNQ futures : {sa}")
print(f"NQX CFD    : {sb}")
# same-signal agreement: trades on both within 15 minutes, same direction
match = 0
for t in ta_:
    if any(abs(u["entry_t"] - t["entry_t"]) <= 900 and u["dir"] == t["dir"] for u in tb_):
        match += 1
print(f"signals shared (same side, within 15 min): {match} of {len(ta_)} futures trades")
