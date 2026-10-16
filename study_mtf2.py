"""Follow-up MTF study: pooled NQ+ES feature edges, and MTF-based trade management variants."""
import sys
from multiprocessing import Pool

import numpy as np

from engine import backtest, learn
from study_mtf import seg, SPLIT


def run(args):
    name, sym, params = args
    r = backtest.run(sym, "5m", params, light=True)
    tr = r["trades"]
    return name, sym, seg([t for t in tr if t["day"] < SPLIT]), seg([t for t in tr if t["day"] >= SPLIT]), seg(tr)


if __name__ == "__main__":
    pooled = []
    for sym in ("NQ", "ES"):
        r = backtest.run(sym, "5m", {"max_trades_day": 9, "stop_after_win": False, "min_score": -99})
        pooled += r["shadows"]
        print(sym, "shadows", len(r["shadows"]), "avg R", round(float(np.mean([s["r"] for s in r["shadows"]])), 3))
    fs = learn.feature_study(pooled, SPLIT)
    print(f"\nPOOLED NQ+ES ({len(pooled)} candidates)")
    print(f"{'feature':12s} | IS n_on  edge | OOS n_on  edge | consistent?")
    for row in fs:
        e1, e2 = row["is_edge"], row["oos_edge"]
        cons = "YES" if e1 is not None and e2 is not None and e1 * e2 > 0 and min(abs(e1), abs(e2)) > 0.15 else ""
        print(f"{row['feature']:12s} | {row['is_n_on']:6d} {e1 if e1 is not None else 0:+.2f} | {row['oos_n_on']:7d} {e2 if e2 is not None else 0:+.2f} | {cons}")
    V = [("baseline", {}), ("counter cap 2.5R", {"counter_rr_cap": 2.5}), ("counter cap 2R", {"counter_rr_cap": 2.0}),
         ("counter cap 3R", {"counter_rr_cap": 3.0}), ("highest-TF IFVG", {"ifvg_tf": "highest"}),
         ("highest + cap 2.5", {"ifvg_tf": "highest", "counter_rr_cap": 2.5})]
    jobs = [(n, s, p) for n, p in V for s in ("NQ", "ES")]
    with Pool(8) as pool:
        out = pool.map(run, jobs)
    print(f"\n{'variant':20s} sym | {'IN-SAMPLE':28s} | {'OUT-OF-SAMPLE':28s} | ALL")
    for name, sym, a, b, c in out:
        print(f"{name:20s} {sym:3s} | {a:28s} | {b:28s} | {c}")
