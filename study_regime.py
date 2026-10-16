"""Regime detector research: which pre-trade regime measures separate winners from losers in EVERY period?"""
import numpy as np

from engine import backtest

WIDE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0, "max_trades_day": 9, "stop_after_win": False,
        "min_score": -99, "grade_sizing": False}
SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
FLAGS = ["rg_trending_5d", "rg_rotational_5d", "rg_counter_5d", "rg_trend_today", "rg_fade_today", "rg_pd_trend_day",
         "rg_vol_expanding", "rg_big_gap"]
NUMS = ["rg_er5", "rg_er10", "rg_day_er", "rg_pd_trend", "rg_pd_range_ratio", "rg_vol_expansion", "rg_gap_adr"]

if __name__ == "__main__":
    pools = {}
    for label, sym, a, z in SEGS:
        sh = [s for s in backtest.run(sym, "5m", WIDE)["shadows"] if (not a or s["day"] >= a) and (not z or s["day"] <= z)]
        pools[label] = sh
        print(f"{label:12s} candidates {len(sh)} avg R {np.mean([s['r'] for s in sh]):+.2f} | "
              + " ".join(f"{k[3:]}={np.nanmean([s['f'][k] if s['f'].get(k) is not None else np.nan for s in sh]):.2f}" for k in NUMS))
    print(f"\n{'regime flag':18s} | " + " | ".join(f"{l:26s}" for l in pools) + " | verdict")
    for k in FLAGS:
        cells, edges = [], []
        for l, sh in pools.items():
            on = [s["r"] for s in sh if s["f"].get(k)]
            off = [s["r"] for s in sh if not s["f"].get(k)]
            if len(on) >= 3 and len(off) >= 3:
                edges.append(np.mean(on) - np.mean(off))
                cells.append(f"n={len(on):2d} {np.mean(on):+.2f} vs {np.mean(off):+.2f}")
            else:
                cells.append(f"n={len(on):2d} (too few)")
        v = "STABLE +" if len(edges) == 3 and all(e > 0.15 for e in edges) else "STABLE -" if len(edges) == 3 and all(e < -0.15 for e in edges) else ""
        print(f"{k[3:]:18s} | " + " | ".join(f"{c:26s}" for c in cells) + f" | {v}")
    print("\nNumeric measures: avg R by tercile (thresholds from all periods pooled)")
    allsh = [s for sh in pools.values() for s in sh]
    for k in NUMS:
        vals = np.array([s["f"][k] for s in allsh if s["f"].get(k) is not None])
        if len(vals) < 20:
            continue
        t1, t2 = np.percentile(vals, [33.3, 66.7])
        row = []
        for l, sh in pools.items():
            b = [[s["r"] for s in sh if s["f"].get(k) is not None and lo <= s["f"][k] < hi] for lo, hi in ((-1e9, t1), (t1, t2), (t2, 1e9))]
            row.append(" / ".join(f"{np.mean(x):+.2f}" if x else "  -  " for x in b))
        print(f"  {k[3:]:16s} cuts {t1:.2f},{t2:.2f} | " + " | ".join(f"{l}: {r}" for l, r in zip(pools, row)))
