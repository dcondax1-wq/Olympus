"""Loss anatomy across every period: exit reasons, MFE of losers, MAE of winners, synthetic stop/BE levels,
with-trend vs counter-trend inside trending regimes, time-of-day and grade buckets."""
from collections import defaultdict
from multiprocessing import Pool

import numpy as np

from engine import backtest

WIDE = {"max_trades_day": 9, "stop_after_win": False, "min_score": -99, "daily_max_loss": 1e9, "dd_aware": False,
        "regime_er10_max": 0, "news_filter": False}
SEGS = [("NQ 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]


def _run(sym):
    r = backtest.run(sym, "5m", WIDE)
    return sym, r["trades"], r["shadows"]


def seg_rows(rows, a, z, key="day"):
    return [x for x in rows if (not a or x[key] >= a) and (not z or x[key] <= z)]


def avg(xs):
    return float(np.mean(xs)) if xs else float("nan")


if __name__ == "__main__":
    with Pool(2) as pool:
        res = dict((s, (t, sh)) for s, t, sh in pool.map(_run, ["NQ", "NQX"]))
    per = []
    for name, sym, a, z in SEGS:
        tr = seg_rows(res[sym][0], a, z)
        sh = [s for s in seg_rows(res[sym][1], a, z) if s["r"] is not None]
        for t in tr:
            t["r"] = t["pnl_r"]
        if tr:
            per.append((name, tr, sh))
    print("=== A. exit reasons (taken trades, wide config) ===")
    for name, tr, sh in per:
        by = defaultdict(list)
        for t in tr:
            by[t["exit_reason"]].append(t["r"])
        print(f"{name:12s} n={len(tr):3d} avg {avg([t['r'] for t in tr]):+.2f}R | " +
              "  ".join(f"{k}:{len(v)} ({avg(v):+.2f}R)" for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))))

    print("\n=== B. how far losers went in our favour first (MFE) / how deep winners dipped (MAE) ===")
    for name, tr, sh in per:
        L = [t for t in tr if t["r"] <= 0]; W = [t for t in tr if t["r"] > 0]
        mfe = np.array([t["mfe"] for t in L]) if L else np.array([])
        mae = np.array([t["mae"] for t in W]) if W else np.array([])
        print(f"{name:12s} losers {len(L):3d}: MFE>=0.3R {np.mean(mfe >= 0.3) if len(mfe) else 0:.0%}  >=0.5R {np.mean(mfe >= 0.5) if len(mfe) else 0:.0%}  "
              f">=0.75R {np.mean(mfe >= 0.75) if len(mfe) else 0:.0%}  >=1R {np.mean(mfe >= 1.0) if len(mfe) else 0:.0%} | "
              f"winners {len(W):3d}: MAE median {np.median(mae) if len(mae) else 0:.2f}R  p75 {np.percentile(mae, 75) if len(mae) else 0:.2f}R  "
              f">0.5R {np.mean(mae > 0.5) if len(mae) else 0:.0%}  >0.7R {np.mean(mae > 0.7) if len(mae) else 0:.0%}")

    print("\n=== C. synthetic tighter stop at X x planned risk (R re-based to the new risk; BE ignored) ===")
    print(f"{'stop X':8s} | " + " | ".join(f"{n:>22s}" for n, *_ in per))
    for X in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        cells = []
        for name, tr, sh in per:
            rs = []
            for t in tr:
                if t["mae"] >= X:
                    rs.append(-1.0 - 0.05)
                else:
                    rs.append(t["r"] / X)
            rs = np.array(rs)
            g = rs[rs > 0].sum(); l = -rs[rs <= 0].sum()
            cells.append(f"{rs.mean():+.2f}R pf{(g / l if l else 99):5.2f} wr{np.mean(rs > 0):4.0%}")
        print(f"{X:8.1f} | " + " | ".join(f"{c:>22s}" for c in cells))

    print("\n=== D. synthetic break-even trigger at Y R (loser becomes ~0 if MFE reached Y) ===")
    print(f"{'BE at':8s} | " + " | ".join(f"{n:>16s}" for n, *_ in per))
    for Y in (None, 0.5, 0.75, 1.0, 1.5):
        cells = []
        for name, tr, sh in per:
            rs = np.array([(0.0 if (Y and t["r"] < 0 and t["mfe"] >= Y) else t["r"]) for t in tr])
            cells.append(f"{rs.mean():+.2f}R wr{np.mean(rs > 0):4.0%}")
        print(f"{str(Y):8s} | " + " | ".join(f"{c:>16s}" for c in cells))

    print("\n=== E. trending regime (er10 > 0.45): with-trend vs counter-trend (shadows) ===")
    for name, tr, sh in per:
        T = [s for s in sh if (s["f"].get("rg_er10") or 0) > 0.45]
        R = [s for s in sh if (s["f"].get("rg_er10") or 0) <= 0.45 and s["f"].get("rg_er10") is not None]
        def split(S, key, pos_is_with):
            w = [s["r"] for s in S if (s["f"].get(key, 0) > 0) == pos_is_with]
            c = [s["r"] for s in S if (s["f"].get(key, 0) > 0) != pos_is_with]
            return f"with {len(w):2d} {avg(w):+.2f}R / counter {len(c):2d} {avg(c):+.2f}R"
        print(f"{name:12s} TRENDING n={len(T):3d}: 5-day dir -> {split(T, 'rg_counter_5d', False)} | 1H structure -> {split(T, 'htf_trend', True)} | today's dir -> {split(T, 'rg_fade_today', False)}")
        print(f"{'':12s} ROTATING n={len(R):3d}: 5-day dir -> {split(R, 'rg_counter_5d', False)} | 1H structure -> {split(R, 'htf_trend', True)} | today's dir -> {split(R, 'rg_fade_today', False)}")

    print("\n=== F. entry time buckets (shadows, avg R / n) ===")
    import datetime as dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    buckets = ["09:30", "10:00", "10:30", "11:00", "13:30", "14:00", "14:30", "15:00"]
    print(f"{'period':12s} | " + " | ".join(f"{b:>11s}" for b in buckets))
    for name, tr, sh in per:
        by = defaultdict(list)
        for s in sh:
            m = dt.datetime.fromtimestamp(s["t"], et)
            key = f"{m.hour:02d}:{'30' if m.minute >= 30 else '00'}"
            by[key].append(s["r"])
        print(f"{name:12s} | " + " | ".join(f"{avg(by[b]):+.2f}R/{len(by[b]):2d}" if by[b] else f"{'-':>11s}" for b in buckets))

    print("\n=== G. grade buckets (shadows, avg R / n) ===")
    for name, tr, sh in per:
        by = defaultdict(list)
        for s in sh:
            by[s.get("grade", "?")].append(s["r"])
        print(f"{name:12s} | " + "  ".join(f"{g}: {avg(by[g]):+.2f}R/{len(by[g])}" for g in ("A+", "A", "B", "C", "D") if by[g]))

    print("\n=== H. planned R:R buckets (shadows) ===")
    for name, tr, sh in per:
        by = defaultdict(list)
        for s in sh:
            rr = s["f"].get("rr_plan", 0)
            by["<2R" if rr < 2 else "2-3R" if rr < 3 else "3-4R" if rr < 4 else "4R+"].append(s["r"])
        print(f"{name:12s} | " + "  ".join(f"{g}: {avg(by[g]):+.2f}R/{len(by[g])} hit {np.mean(np.array(by[g]) >= 1.5):.0%}" for g in ("<2R", "2-3R", "3-4R", "4R+") if by[g]))
