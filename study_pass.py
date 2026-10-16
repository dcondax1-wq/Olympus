"""Pass-speed study for the MFFU Builder 50K evaluation ($3k target, $2k EOD trailing MLL, no consistency rule).
Scores each variant on: rolling-start eval pass rate / avg days / failures, bootstrap Monte Carlo pass odds, and profitability.
"""
from multiprocessing import Pool

import numpy as np

from engine import analytics, backtest

SPLIT = "2026-09-22"
PLAN = analytics.PLANS["builder_50k"]
V = [
    ("current", {}),
    ("no stop-after-win", {"stop_after_win": False}),
    ("no SAW + 3/day", {"stop_after_win": False, "max_trades_day": 3}),
    ("+ London killzone", {"entry_windows": [[180, 300], [570, 690], [810, 930]]}),
    ("risk $450", {"risk_usd": 450}),
    ("risk $500 (cush .30)", {"risk_usd": 500, "cushion_frac": 0.30}),
    ("risk $600 (cush .30)", {"risk_usd": 600, "cushion_frac": 0.30}),
    ("no SAW + $450", {"stop_after_win": False, "risk_usd": 450}),
    ("no SAW + $500 (cush .30)", {"stop_after_win": False, "risk_usd": 500, "cushion_frac": 0.30}),
    ("no SAW + 3/day + $450", {"stop_after_win": False, "max_trades_day": 3, "risk_usd": 450}),
    ("daily stop $900 + no SAW + $450", {"stop_after_win": False, "risk_usd": 450, "daily_max_loss": 900}),
]


def run(job):
    name, p = job
    r = backtest.run("NQ", "5m", p)
    s = r["stats"]
    tr = r["trades"]
    roll = r["rolling"]
    mc = analytics.monte_carlo([d["pnl"] for d in r["days"]], PLAN, runs=3000, horizon=60)
    ins = [t["pnl_r"] for t in tr if t["day"] < SPLIT]
    oos = [t["pnl_r"] for t in tr if t["day"] >= SPLIT]
    return (name, s["trades"], s["trades_per_week"], s["profit_factor"], s["net"], s["max_dd"], s["worst_day"],
            roll["pass"], roll["fail"], roll["avg_days_to_pass"], mc["pass_prob"], mc["fail_prob"], mc["median_days_to_pass"],
            float(np.mean(ins)) if ins else 0, float(np.mean(oos)) if oos else 0, s["best_day_pct"])


if __name__ == "__main__":
    with Pool(10) as pool:
        out = pool.map(run, V)
    print(f"{'variant':32s} {'trd':>4s} {'t/wk':>5s} {'PF':>5s} {'net':>7s} {'maxDD':>7s} {'worstD':>7s} | {'roll P/F':>8s} {'days':>5s} | {'MC pass':>7s} {'fail':>5s} {'med d':>5s} | {'IS R':>5s} {'OOS R':>5s} {'best%':>5s}")
    for o in out:
        n, t, tw, pf, net, dd, wd, rp, rf, rd, mp, mf, md, ir, orr, bd = o
        print(f"{n:32s} {t:4d} {tw:5.1f} {pf:5.2f} {net:+7.0f} {dd:7.0f} {wd:7.0f} | {rp:3d}/{rf:<4d} {rd or 0:5.1f} | {mp:6.1f}% {mf:4.1f}% {md or 0:5.0f} | {ir:+.2f} {orr:+.2f} {bd or 0:5.1f}")
