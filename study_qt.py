"""Quarterly Theory / AMD / gamma: feature edges on every candidate across all three market periods."""
import numpy as np

from engine import backtest

WIDE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0, "max_trades_day": 9, "stop_after_win": False, "min_score": -99}
SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
FEATS = ["qt_q2_sweep", "qt_q2q3", "qt_entry_q3", "qt_micro_23", "amd_day_open", "qt_session_open", "qt_90_open",
         "qt_week_open", "gex_low", "gex_high", "gex_neg"]

if __name__ == "__main__":
    pools = {}
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", WIDE)
        pools[label] = [s for s in r["shadows"] if (not a or s["day"] >= a) and (not z or s["day"] <= z)]
        print(label, "candidates", len(pools[label]), "avg R", round(float(np.mean([s["r"] for s in pools[label]])), 3))
    print(f"\n{'feature':16s} | " + " | ".join(f"{l:24s}" for l, *_ in SEGS) + " | verdict")
    for k in FEATS:
        cells, edges = [], []
        for label in pools:
            sh = pools[label]
            on = [s["r"] for s in sh if (s["f"].get(k) or 0) > 0]
            off = [s["r"] for s in sh if (s["f"].get(k) or 0) <= 0]
            if len(on) >= 3 and len(off) >= 3:
                e = np.mean(on) - np.mean(off)
                edges.append(e)
                cells.append(f"n={len(on):3d} {np.mean(on):+.2f} vs {np.mean(off):+.2f}")
            else:
                cells.append(f"n={len(on):3d}   (too few)      ")
        v = ""
        if len(edges) == 3 and (all(e > 0.15 for e in edges) or all(e < -0.15 for e in edges)):
            v = "STABLE +" if edges[0] > 0 else "STABLE -"
        print(f"{k:16s} | " + " | ".join(f"{c:24s}" for c in cells) + f" | {v}")
    # entry quarter profile
    print("\nAvg R by 90-min quarter of ENTRY (AM: Q3=09:00-10:30, Q4=10:30-12:00; PM: Q2=13:30-15:00, Q3=15:00-16:30)")
    for label in pools:
        sh = pools[label]
        row = []
        for q in (2, 3, 4):
            rs = [s["r"] for s in sh if s["f"]["q90_entry"] == q]
            row.append(f"Q{q}: {np.mean(rs):+.2f} (n={len(rs)})" if rs else f"Q{q}: -")
        print(f"  {label:12s} " + " | ".join(row))
    print("\nAvg R by GEX percentile bucket (prior day, S&P dealer gamma)")
    for label in pools:
        sh = [s for s in pools[label] if s["f"].get("gex_pct") is not None]
        row = []
        for a, z in ((0, 33), (33, 66), (66, 101)):
            rs = [s["r"] for s in sh if a <= s["f"]["gex_pct"] < z]
            row.append(f"{a}-{min(z, 100)}%: {np.mean(rs):+.2f} (n={len(rs)})" if rs else f"{a}-{z}%: -")
        print(f"  {label:12s} " + " | ".join(row))
