"""Placebo / permutation test.

For each real trade we create a fake trade on the same day: random bar inside the killzones, random direction,
SAME stop distance, SAME planned R target, same management (BE at +1R, 30-min time stop, flat 15:55).
Repeat N times -> distribution of average R a no-skill strategy gets from the same exits in the same market.
Also: real entries with the direction flipped (does the side-picking matter?).
python study_placebo.py [SYM]
"""
import sys

import numpy as np

from engine import backtest
from engine.data import load

SYM = sys.argv[1] if len(sys.argv) > 1 else "NQ"
N = 1000
rng = np.random.default_rng(11)


def sim(b, i0, d, risk, rr, be_r=1.0, tstop=6, slip=0.25):
    """Simulate from bar i0 open. Returns R."""
    entry = b.o[i0] + d * slip
    stop = entry - d * risk
    tgt = entry + d * rr * risk
    mfe = 0.0
    day = b.tday[i0]
    for k in range(i0, min(i0 + 200, len(b.t))):
        if b.tday[k] != day:
            return (b.c[k - 1] - entry) * d / risk
        lo, hi = (b.l[k], b.h[k]) if d == 1 else (-b.h[k], -b.l[k])
        if lo <= stop * d:
            return (min(b.o[k] * d, stop * d) - slip - entry * d) / risk
        if hi >= tgt * d + 0.25:
            return rr
        mfe = max(mfe, (hi - entry * d) / risk)
        if b.mod[k] >= 955:
            return (b.c[k] - entry) * d / risk
        if tstop and (k - i0 + 1) >= tstop and mfe < 0.5:
            return (b.c[k] - entry) * d / risk
        if be_r and mfe >= be_r:
            stop = entry + d * 0.25
    return (b.c[k] - entry) * d / risk


if __name__ == "__main__":
    r = backtest.run(SYM, "5m", {"dd_aware": False, "conviction_step": 0}, light=True)
    tr = r["trades"]
    b = load(SYM, "5m")
    idx_by_day = {}
    for i, (d, m) in enumerate(zip(b.date_str, b.mod)):
        if 570 <= m < 680 or 810 <= m < 920:
            idx_by_day.setdefault(d, []).append(i)
    t_index = {int(t): i for i, t in enumerate(b.t)}
    real = np.mean([t["pnl_r"] for t in tr])
    # same entry, opposite direction
    flipped = []
    for t in tr:
        i0 = t_index.get(int(t["entry_t"]))
        if i0 is not None:
            flipped.append(sim(b, i0, -t["dir"], t["risk_pts"], max(1.5, t["rr"])))
    # random time + random direction, same risk / R
    dist = []
    for _ in range(N):
        rs = []
        for t in tr:
            cands = idx_by_day.get(t["day"])
            if not cands:
                continue
            i0 = int(rng.choice(cands))
            rs.append(sim(b, i0, int(rng.choice([-1, 1])), t["risk_pts"], t["rr"]))
        dist.append(np.mean(rs))
    dist = np.array(dist)
    print(f"{SYM}: {len(tr)} real trades")
    print(f"  real strategy avg R           : {real:+.3f}")
    print(f"  same entries, flipped side    : {np.mean(flipped):+.3f}")
    print(f"  random placebo avg R          : mean {dist.mean():+.3f}  p95 {np.percentile(dist, 95):+.3f}  p99 {np.percentile(dist, 99):+.3f}  max {dist.max():+.3f}")
    print(f"  p-value (placebo >= real)     : {np.mean(dist >= real):.4f}")
