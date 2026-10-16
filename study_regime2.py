"""Trending-regime switch: stand aside or half size when the 10-day efficiency says the market is trending."""
from multiprocessing import Pool

import numpy as np

from engine import backtest

SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
V = [("off (current)", {}), ("skip if er10 > 0.40", {"regime_er10_max": 0.40, "regime_mode": "skip"}),
     ("skip if er10 > 0.45", {"regime_er10_max": 0.45, "regime_mode": "skip"}), ("skip if er10 > 0.50", {"regime_er10_max": 0.50, "regime_mode": "skip"}),
     ("half size if er10 > 0.40", {"regime_er10_max": 0.40, "regime_mode": "half"}), ("half size if er10 > 0.45", {"regime_er10_max": 0.45, "regime_mode": "half"})]


def run(job):
    name, p = job
    out = []
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", {**p, "dd_aware": False, "daily_max_loss": 1e9}, light=True)
        tr = [t for t in r["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        nd = len([d for d in r["days"] if (not a or d["date"] >= a) and (not z or d["date"] <= z)])
        pnl = sum(t["pnl"] for t in tr)
        out.append(f"{len(tr):3d}t {len(tr) / max(nd / 5, 1e-9):.1f}/wk ${pnl:+7.0f}")
    return name, out


if __name__ == "__main__":
    with Pool(6) as pool:
        out = pool.map(run, V)
    print(f"{'trending-regime rule':26s} | " + " | ".join(f"{l:24s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:26s} | " + " | ".join(f"{x:24s}" for x in o))
