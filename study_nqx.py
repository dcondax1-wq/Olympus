"""Out-of-period diagnosis on NQX (Dukascopy Nasdaq-100 CFD): 2023-Q4 and 2025-Q4 segments.
Sizing pressure removed (dd_aware off, flat risk) so every period is traded and judged in R."""
from multiprocessing import Pool

import numpy as np

from engine import backtest

FREE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0}
V1 = {"w_amt": 1, "w_pd": 0, "w_protected": 1, "w_smt": 1, "w_quality": 1, "w_m15": 0, "target_mode": "dol",
      "amt_targets": True, "be_at_r": 0, "time_stop_min": 0}
HALF = {"spec": {"min_fvg": 1.5, "min_stop": 5, "max_stop": 30, "stop_buffer": 1.0, "eq_tol": 3}}   # NQ ~15k in 2023
V = [
    ("current", {}),
    ("current, scaled specs", HALF),
    ("v1 (original)", V1),
    ("v1, scaled specs", {**V1, **HALF}),
    ("current, nearest DOL", {"target_mode": "dol"}),
]


def seg(trs):
    if not trs:
        return "  0t"
    r = np.array([t["pnl_r"] for t in trs]); m = np.array([t["mfe"] for t in trs])
    return f"{len(trs):3d}t win {np.mean(r > 0) * 100:4.0f}% avgR {r.mean():+.2f} MFE {m.mean():.2f} hit1R {np.mean(m >= 1) * 100:3.0f}%"


def run(job):
    name, p = job
    tr = backtest.run("NQX", "5m", {**FREE, **p}, light=True)["trades"]
    a = [t for t in tr if t["day"] < "2024-01-01"]; b = [t for t in tr if t["day"] >= "2025-01-01"]
    return name, seg(a), seg(b), seg(tr)


if __name__ == "__main__":
    nq = backtest.run("NQ", "5m", FREE, light=True)["trades"]
    print("reference NQ futures 2026  :", seg(nq))
    with Pool(5) as pool:
        out = pool.map(run, V)
    for n, a, b, c in out:
        print(f"{n:24s} | 2023Q4 {a} | 2025Q4 {b} | ALL {c}")
