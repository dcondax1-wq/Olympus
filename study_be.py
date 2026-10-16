"""Real-engine test of exit tweaks suggested by the loss anatomy: earlier break-even, IFVG-failure exit, time stop."""
import sys
from multiprocessing import Pool

import numpy as np

from engine import backtest

SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
V = [("current (BE 1.0R)", {}), ("BE 0.5R", {"be_at_r": 0.5}), ("BE 0.75R", {"be_at_r": 0.75}), ("BE off", {"be_at_r": 0}),
     ("BE 0.5R + ts 20m", {"be_at_r": 0.5, "time_stop_min": 20}), ("BE 0.5R + ts 45m", {"be_at_r": 0.5, "time_stop_min": 45}),
     ("IFVG-fail exit", {"ifvg_fail_exit": True}), ("IFVG-fail + BE 0.5R", {"ifvg_fail_exit": True, "be_at_r": 0.5}),
     ("BE 0.5R, lock 0.5R at 2R", {"be_at_r": 0.5, "lock_at_r": 2.0, "lock_r": 0.5}),
     ("BE 0.5R, lock 1R at 2.5R", {"be_at_r": 0.5, "lock_at_r": 2.5, "lock_r": 1.0})]


def run(job):
    name, p = job
    out = []
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", {**p, "dd_aware": False, "daily_max_loss": 1e9}, light=True)
        tr = [t for t in r["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        nd = len([d for d in r["days"] if (not a or d["date"] >= a) and (not z or d["date"] <= z)])
        if not tr:
            out.append("-"); continue
        pnl = sum(t["pnl"] for t in tr)
        g = sum(t["pnl"] for t in tr if t["pnl"] > 0); l = -sum(t["pnl"] for t in tr if t["pnl"] < 0)
        eq = np.cumsum([t["pnl"] for t in tr])
        dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
        avg_r = np.mean([t["pnl_r"] for t in tr])
        out.append(f"{len(tr):3d}t {len(tr) / max(nd / 5, 1e-9):.1f}/wk {avg_r:+.2f}R ${pnl:+6.0f} pf{(g / l if l else 99):5.2f} dd{dd:6.0f}")
    return name, out


if __name__ == "__main__":
    with Pool(8) as pool:
        out = pool.map(run, V)
    print(f"{'variant':26s} | " + " | ".join(f"{l:44s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:26s} | " + " | ".join(f"{x:44s}" for x in o))
