"""Nov 16-19 (4 of 12 won): noise or the edge dying? Runs EXACTLY the test pre-registered in PREREG_noise.md (committed first).

    python research/kalshi_k8_day/noise.py    -> research/kalshi_k8_day/noise.json + plain lines
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import kalshi_k8_feed as F  # noqa: E402
from engine import kalshi_clock as KC  # noqa: E402

OUT = os.path.join(HERE, "noise.json")
LIVE3 = ["gold_0530_down", "gold_1700_up", "silver_1700_up"]
BASE = (dt.date(2026, 8, 3), dt.date(2026, 11, 13))
BAD = (dt.date(2026, 11, 16), dt.date(2026, 11, 19))
SEED = 20261120


def slope(xs, ys, ws):
    sw = sum(ws)
    mx, my = sum(w * x for x, w in zip(xs, ws)) / sw, sum(w * y for y, w in zip(ys, ws)) / sw
    num = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    den = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    return num / den if den else 0.0


def perm_p(xs, ys, ws, sign, n=20000, rng=None):
    """One-sided permutation p: share of shuffles of the weeks with a slope at least as extreme (sign -1 = falling, +1 = rising)."""
    rng = rng or random.Random(SEED)
    s0 = slope(xs, ys, ws)
    pairs = list(zip(ys, ws))
    hit = 0
    for _ in range(n):
        rng.shuffle(pairs)
        s = slope(xs, [p[0] for p in pairs], [p[1] for p in pairs])
        hit += (s <= s0 + 1e-15) if sign < 0 else (s >= s0 - 1e-15)
    return s0, (hit + 1) / (n + 1)


def beta_below(won, n, x, draws=200000, rng=None):
    rng = rng or random.Random(SEED + 1)
    return sum(1 for _ in range(draws) if rng.betavariate(won + 1, n - won + 1) < x) / draws


def main() -> int:
    rs = F.bets(legs=LIVE3, last=dt.date(2026, 11, 20))
    base = [r for r in rs if BASE[0] <= r["day"] <= BASE[1]]
    bad = [r for r in rs if BAD[0] <= r["day"] <= BAD[1]]
    after = [r for r in rs if r["day"] > BAD[1]]
    bw, bn = sum(r["won"] for r in bad), len(bad)
    by_day = {}
    for r in base:
        by_day.setdefault(r["day"], []).append(r["won"])
    days = sorted(by_day)
    # 1a. every run of 4 consecutive trading days in the baseline (real order)
    runs = [days[i:i + 4] for i in range(len(days) - 3)]
    run_rates = [(sum(sum(by_day[d]) for d in g), sum(len(by_day[d]) for d in g)) for g in runs]
    as_bad_runs = [g for g, (w, n) in zip(runs, run_rates) if n and w / n <= bw / bn + 1e-9]
    p_runs = len(as_bad_runs) / len(runs) if runs else None
    # 1b. 100,000 draws of 4 random baseline days (each day's bets together)
    rng = random.Random(SEED)
    hit = 0
    N = 100000
    for _ in range(N):
        g = [by_day[rng.choice(days)] for _ in range(4)]
        w, n = sum(sum(x) for x in g), sum(len(x) for x in g)
        hit += n > 0 and w / n <= bw / bn + 1e-9
    p_boot = hit / N
    # 2 + 3. weekly trends Aug 3 - Nov 20
    wk = {}
    for r in rs:
        wk.setdefault(KC.week_of(r["day"]), []).append(r)
    ks = sorted(wk)
    xs = list(range(len(ks)))
    ws = [len(wk[k]) for k in ks]
    win = [sum(r["won"] for r in wk[k]) / len(wk[k]) for k in ks]
    px = [sum(r["price"] for r in wk[k]) / len(wk[k]) for k in ks]
    s_win, p_win = perm_p(xs, win, ws, -1, rng=random.Random(SEED + 2))
    s_px, p_px = perm_p(xs, px, ws, +1, rng=random.Random(SEED + 3))
    # verdict (fixed in PREREG_noise.md)
    p1 = p_boot
    if p1 < 0.0167 and (p_win < 0.0167 or p_px < 0.0167):
        verdict = "edge dying"
    elif p1 < 0.05 or p_win < 0.05 or p_px < 0.05:
        verdict = "warning"
    else:
        verdict = "noise"
    last60 = rs[-60:]
    be60 = sum(r["price"] + r["fee"] / r["n"] for r in last60) / len(last60)
    w60 = sum(r["won"] for r in last60)
    p_below_be = beta_below(w60, len(last60), be60)
    p_below_58 = beta_below(w60, len(last60), 0.58)
    l4 = [r for r in rs if r["day"] >= dt.date(2026, 10, 26)]
    out = {"prereg": "research/kalshi_k8_day/PREREG_noise.md", "through": str(rs[-1]["day"]), "bets": len(rs),
           "baseline": {"from": str(BASE[0]), "to": str(BASE[1]), "n": len(base), "won": sum(r["won"] for r in base),
                        "rate": round(sum(r["won"] for r in base) / len(base), 4), "days": len(days)},
           "bad": {"n": bn, "won": bw, "net": round(sum(r["pnl"] for r in bad), 2)},
           "after": [{"day": str(r["day"]), "leg": r["leg"], "won": r["won"], "pnl": r["pnl"], "price": r["price"]} for r in after],
           "t1a_runs": {"runs": len(runs), "as_bad": len(as_bad_runs), "p": round(p_runs, 4) if p_runs is not None else None,
                        "which": [[str(d) for d in g] for g in as_bad_runs][:10]},
           "p_bad4": round(p_boot, 4),
           "t2_win_trend": {"slope_per_week": round(s_win, 5), "p": round(p_win, 4)},
           "t3_price_trend": {"slope_c_per_week": round(100 * s_px, 3), "p": round(p_px, 4)},
           "p_trend_win": round(p_win, 4), "p_trend_price": round(p_px, 4),
           "weeks": [{"wk": k, "n": len(wk[k]), "won": sum(r["won"] for r in wk[k]), "avg_c": round(100 * px[i], 1),
                      "net": round(sum(r["pnl"] for r in wk[k]), 2)} for i, k in enumerate(ks)],
           "last60": {"n": len(last60), "won": w60, "breakeven": round(be60, 4), "p_true_below_breakeven": round(p_below_be, 4),
                      "p_true_below_58": round(p_below_58, 4)},
           "last4wk": {"n": len(l4), "won": sum(r["won"] for r in l4), "net": round(sum(r["pnl"] for r in l4), 2)},
           "all": {"n": len(rs), "won": sum(r["won"] for r in rs), "net": round(sum(r["pnl"] for r in rs), 2)},
           "verdict": verdict}
    one_in = round(1 / p_boot) if p_boot > 0 else None
    out["plain"] = (f"{verdict.upper()}: in the good months (Aug 3-Nov 13, {out['baseline']['rate'] * 100:.0f}% won) a 4-day stretch as bad as "
                    f"Nov 16-19 ({bw} of {bn}) came up {p_boot * 100:.1f}% of the time (about 1 in {one_in}); "
                    f"{len(as_bad_runs)} of {len(runs)} real 4-day runs were that bad. Win rate trend p {p_win:.2f}, price creep p {p_px:.2f}.")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(out["plain"])
    print(json.dumps({k: out[k] for k in ("baseline", "bad", "t1a_runs", "p_bad4", "t2_win_trend", "t3_price_trend", "last60", "last4wk", "all", "after")}, default=str)[:3000])
    for w in out["weeks"]:
        print(w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
