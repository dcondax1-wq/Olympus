#!/usr/bin/env python3
"""K4 idea 3: 15-minute crypto slices not in teams A/B: coin x hour of day (ET) x minutes to expiry x role, strict
multiple-testing control.

Unit: one Kalshi 15-minute market, at the first minute of the bucket (most minutes left) with spread <= 4c, buy one
side at the ask (fee 0.07 p(1-p) rounded up on a $10 order). Roles (by the price paid):
  fav_hi 80-97c, fav_lo 50-80c, dog_hi 20-50c, dog_lo 3-20c.
Buckets: m1-3, m4-7, m8-13 minutes to expiry. Hour = ET hour of the market's close.
Train = closes before SPLIT, test after (read once). Cluster = settle time. A cell (n_train >= 40) is carried only if
its train cluster t beats the one-sided Bonferroni bar over ALL eligible cells; a cell also needs the same sign on test
with a 95% range above zero to survive.
    python research/kalshi_edge_K4/crypto_slices.py   -> results_crypto_slices.json
"""
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from crypto_xvenue import load, quotes
from lib import pnl_per_dollar, summary

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
BUCKETS = {"m1-3": (3, 2, 1), "m4-7": (7, 6, 5, 4), "m8-13": tuple(range(13, 7, -1))}
ROLES = (("fav_hi", 0.80, 0.97), ("fav_lo", 0.50, 0.80), ("dog_hi", 0.20, 0.50), ("dog_lo", 0.03, 0.20))


def et_hour(ts):
    d = datetime.fromtimestamp(ts, timezone.utc)
    # US Eastern: EDT (UTC-4) until the first Sunday of November 2026 (Nov 1, 06:00 UTC), EST (UTC-5) after
    off = 4 if d < datetime(2026, 11, 1, 6, tzinfo=timezone.utc) else 5
    return (d - timedelta(hours=off)).hour


def zbar(k, alpha=0.05):
    a = alpha / max(k, 1)
    lo, hi = 0.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if 0.5 * math.erfc(mid / 2 ** 0.5) > a else (lo, mid)
    return hi


def main():
    cells = defaultdict(list)
    span = [1e18, 0]
    for coin in ("BTC", "ETH", "SOL", "XRP"):
        for r in load(coin):
            q = quotes(r)
            yes_won = r["res"] == "yes"
            h = et_hour(r["close"])
            span = [min(span[0], r["close"]), max(span[1], r["close"])]
            for b, ms in BUCKETS.items():
                for m in ms:
                    if m in q and q[m][1] - q[m][0] <= 0.04:
                        bid, ask = q[m]
                        for side, p, won in (("yes", ask, yes_won), ("no", 1 - bid, not yes_won)):
                            for role, lo, hi in ROLES:
                                if lo <= p < hi:
                                    cells[(coin, h, b, role)].append({"r": pnl_per_dollar(p, won), "won": won,
                                                                       "cl": int(r["close"]), "ts": r["close"], "p": p})
                        break
    dtr = (SPLIT - span[0]) / 86400
    dte = (span[1] - SPLIT) / 86400
    elig = {}
    for k, v in cells.items():
        a = [u for u in v if u["ts"] < SPLIT]
        if len(a) >= 40:
            elig[k] = summary(a, dtr)
    z = zbar(len(elig))
    ranked = sorted(elig.items(), key=lambda kv: -kv[1]["t"])
    # how many cells pass a naive t > 1.96 on train (the false positives a loose search would keep)
    naive = [k for k, s in elig.items() if s["t"] > 1.96]
    naive_test = []
    for k in naive:
        b = [u for u in cells[k] if u["ts"] >= SPLIT]
        s = summary(b, dte)
        naive_test.append({"cell": "|".join(map(str, k)), "train_edge": elig[k]["edge"], "test": s})
    pos_test = sum(1 for x in naive_test if x["test"]["n"] and x["test"]["edge"] > 0)
    pooled_naive = [u for k in naive for u in cells[k] if u["ts"] >= SPLIT]
    out = {"cells_total": len(cells), "eligible": len(elig), "z_bar": z, "train_days": dtr, "test_days": dte,
           "naive_t196": {"count": len(naive), "expected_by_luck": round(0.025 * len(elig), 1),
                          "positive_on_test": pos_test, "pooled_test": summary(pooled_naive, dte)},
           "top": [{"cell": "|".join(map(str, k)), "train": s} for k, s in ranked[:15]], "carried": []}
    for k, s in ranked:
        if s["t"] >= z:
            b = [u for u in cells[k] if u["ts"] >= SPLIT]
            out["carried"].append({"cell": "|".join(map(str, k)), "train": s, "test": summary(b, dte)})
    with open(os.path.join(HERE, "results_crypto_slices.json"), "w") as f:
        json.dump(out, f, indent=1)
    fmt = lambda s: "n %5d edge %+6.2f%% [%+6.2f, %+6.2f] t %+5.2f" % (
        s["n"], 100 * s["edge"], 100 * s["lo"], 100 * s["hi"], s["t"]) if s["n"] else "n 0"
    print("cells", len(cells), "eligible", len(elig), "z bar %.2f" % z, "train days %.1f test %.1f" % (dtr, dte))
    print("naive t>1.96:", len(naive), "expected by luck", out["naive_t196"]["expected_by_luck"], "positive on test", pos_test,
          "pooled test", fmt(out["naive_t196"]["pooled_test"]))
    for c in out["top"]:
        print("  top", c["cell"], fmt(c["train"]))
    for c in out["carried"]:
        print("  CARRIED", c["cell"], fmt(c["train"]), "| TE", fmt(c["test"]))


if __name__ == "__main__":
    main()
