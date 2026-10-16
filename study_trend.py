"""Trend-day playbook: does a with-trend FVG-retest continuation add edge in the regimes where sweep reversals fail?"""
from multiprocessing import Pool

import numpy as np

from engine import backtest

SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
T = {"trend_model": True}
V = [("current (sweep only)", {}),
     ("+ trend (trending days)", T),
     ("+ trend, dir5 agree", {**T, "trend_require_dir5": True}),
     ("+ trend, any regime", {**T, "trend_require_regime": False}),
     ("+ trend, lookback 60", {**T, "trend_fvg_lookback_min": 60}),
     ("+ trend, lookback 150", {**T, "trend_fvg_lookback_min": 150}),
     ("+ trend, gap x1.5", {**T, "trend_fvg_mult": 1.5}),
     ("+ trend, threshold 0.40", {**T, "regime_er10_max": 0.40}),
     ("+ trend, skip reversals on trend days", {**T, "regime_mode": "skip"}),
     ("+ trend, target fixed 2R", {**T, "target_mode": "fixed", "fallback_rr": 2.0})]


def stat(tr):
    if not tr:
        return "   -"
    pnl = sum(t["pnl"] for t in tr)
    g = sum(t["pnl"] for t in tr if t["pnl"] > 0); l = -sum(t["pnl"] for t in tr if t["pnl"] < 0)
    return f"{len(tr):3d}t {np.mean([t['pnl_r'] for t in tr]):+.2f}R ${pnl:+6.0f} pf{(g / l if l else 99):4.1f}"


def run(job):
    name, p = job
    out = []
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", {**p, "dd_aware": False, "daily_max_loss": 1e9}, light=True)
        tr = [t for t in r["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        nd = len([d for d in r["days"] if (not a or d["date"] >= a) and (not z or d["date"] <= z)])
        if not tr:
            out.append("-"); continue
        cont = [t for t in tr if t["trigger"] == "CONT"]
        out.append(f"{len(tr) / max(nd / 5, 1e-9):.1f}/wk all {stat(tr)} | cont {stat(cont)}")
    return name, out


if __name__ == "__main__":
    with Pool(10) as pool:
        out = pool.map(run, V)
    print(f"{'variant':38s} | " + " | ".join(f"{l:66s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:38s} | " + " | ".join(f"{x:66s}" for x in o))
