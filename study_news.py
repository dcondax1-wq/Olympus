"""News & volatility filters across every period we have (NQ futures 2026, Nasdaq CFD Q4 2023 / Q4 2025)."""
from multiprocessing import Pool

import numpy as np

from engine import backtest

FREE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0}
V = [
    ("current (no news filter)", {}),
    ("blackout 15m before / 30m after + FOMC pm off", {"news_filter": True}),
    ("blackout 30 / 60", {"news_filter": True, "news_before_min": 30, "news_after_min": 60}),
    ("blackout + flatten 5m before", {"news_filter": True, "news_flatten_min": 5}),
    ("skip CPI / NFP / FOMC days", {"news_day_skip": "CPI,Payrolls,FOMC"}),
    ("trade ONLY when VIX <= 20", {"vix_max": 20}),
    ("trade ONLY when VIX <= 25", {"vix_max": 25}),
    ("trade ONLY when VIX >= 15", {"vix_min": 15}),
    ("stop when day range >= 1.0x ADR", {"day_range_max": 1.0}),
    ("stop when day range >= 1.3x ADR", {"day_range_max": 1.3}),
    ("stop when day range >= 1.6x ADR", {"day_range_max": 1.6}),
]
SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]


def seg(tr):
    if not tr:
        return "  0t        "
    r = np.array([t["pnl_r"] for t in tr])
    return f"{len(tr):3d}t {r.mean():+.2f}R"


def run(job):
    name, p = job
    out = []
    for label, sym, a, z in SEGS:
        tr = backtest.run(sym, "5m", {**FREE, **p}, light=True)["trades"]
        tr = [t for t in tr if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        out.append(seg(tr))
    return name, out


if __name__ == "__main__":
    # what kind of days were the trades on?
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", {**FREE, "max_trades_day": 9, "stop_after_win": False, "min_score": -99})
        sh = [s for s in r["shadows"] if (not a or s["day"] >= a) and (not z or s["day"] <= z)]
        def avg(xs): return f"{np.mean(xs):+.2f}R (n={len(xs)})" if xs else "  -  "
        print(f"{label:12s} candidates {len(sh):3d} | news-window {avg([s['r'] for s in sh if s['f']['news_win']])} "
              f"| news-day {avg([s['r'] for s in sh if s['f']['news_day']])} | quiet-day {avg([s['r'] for s in sh if not s['f']['news_day']])} "
              f"| VIX>=20 {avg([s['r'] for s in sh if s['f']['vix_hi']])} | VIX<20 {avg([s['r'] for s in sh if s['f']['vix_prev'] and not s['f']['vix_hi']])} "
              f"| avg VIX {np.mean([s['f']['vix_prev'] for s in sh if s['f']['vix_prev']]):.1f}")
    with Pool(8) as pool:
        out = pool.map(run, V)
    print(f"\n{'variant':46s} | " + " | ".join(f"{l:14s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:46s} | " + " | ".join(f"{x:14s}" for x in o))
