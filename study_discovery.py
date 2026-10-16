"""Promote discovery-scan confluences into the grade (sizing only) and check every period with real sizing."""
from multiprocessing import Pool

import numpy as np

from engine import backtest

SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q1 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
V = [("current grade", {}),
     ("+ 1H-swing raid -1", {"g_h1sweep": 1}), ("+ first 45m -1", {"g_early": 1}), ("+ stacked raid -1", {"g_stacked": 1}),
     ("+ Q3 entry -1", {"g_q3": 1}),
     ("+ 1H-swing & first 45m", {"g_h1sweep": 1, "g_early": 1}),
     ("+ all four", {"g_h1sweep": 1, "g_early": 1, "g_stacked": 1, "g_q3": 1}),
     ("+ first 45m & Q3", {"g_early": 1, "g_q3": 1}), ("+ first 45m x2 & Q3", {"g_early": 2, "g_q3": 1}),
     ("+ all four x2", {"g_h1sweep": 2, "g_early": 2, "g_stacked": 2, "g_q3": 2})]


def run(job):
    name, p = job
    out = []
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", {**p, "dd_aware": False, "daily_max_loss": 1e9}, light=True)
        tr = [t for t in r["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        nd = len([d for d in r["days"] if (not a or d["date"] >= a) and (not z or d["date"] <= z)])
        pnl = sum(t["pnl"] for t in tr)
        g = sum(t["pnl"] for t in tr if t["pnl"] > 0); l = -sum(t["pnl"] for t in tr if t["pnl"] < 0)
        eq = np.cumsum([t["pnl"] for t in tr]) if tr else np.array([0])
        dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if tr else 0
        out.append(f"{len(tr):3d}t {len(tr) / max(nd / 5, 1e-9):.1f}/wk ${pnl:+7.0f} pf{(g / l if l else 99):5.2f} dd{dd:6.0f}")
    return name, out


if __name__ == "__main__":
    with Pool(8) as pool:
        out = pool.map(run, V)
    print(f"{'variant':24s} | " + " | ".join(f"{l:38s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:24s} | " + " | ".join(f"{x:38s}" for x in o))

