#!/usr/bin/env python3
"""K4 idea 1b (crypto, honest timing): does a Polymarket MOVE that Kalshi has not followed yet pay on Kalshi?
The live check (live_analyze.py) found Polymarket's 30 s moves correlate with Kalshi's next 30 s (BTC 0.30, ETH 0.09);
the venues' levels differ (different start prices), so this uses changes, not levels.
At minute m before close: dP = Polymarket print (stamped <= t) minus the print 60 s earlier; dK = Kalshi mid now minus
Kalshi mid 1 minute earlier. If dP - dK > thr: buy Kalshi YES at the ask of the SAME minute (t); if < -thr: buy NO at
1 - bid. Only prints stamped at or before t are used (live check: a stamp shows a price seen about 10 s BEFORE it, so
nothing here is from the future). One trade per market (earliest firing minute 13..2). Train before 2026-10-29, test after.
    python research/kalshi_edge_K4/crypto_move.py   -> results_crypto_move.json
"""
import json
import os
from datetime import datetime, timezone

from crypto_xvenue import load, pm_at, quotes
from lib import pnl_per_dollar, summary

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()


def main():
    out = {}
    span = [1e18, 0]
    res = {}
    for thr in (0.03, 0.05, 0.08):
        for coin in ("BTC", "ETH", "SOL", "XRP", "ALL"):
            res[(coin, thr)] = []
    for coin in ("BTC", "ETH", "SOL", "XRP"):
        for r in load(coin):
            pm = sorted(r.get("pm") or [])
            if not pm:
                continue
            span = [min(span[0], r["close"]), max(span[1], r["close"])]
            q = quotes(r)
            yes_won = r["res"] == "yes"
            for thr in (0.03, 0.05, 0.08):
                for m in range(13, 1, -1):
                    t = r["close"] - m * 60
                    p1, p0 = pm_at(pm, t), pm_at(pm, t - 60)
                    if p1 is None or p0 is None or m not in q or (m + 1) not in q:
                        continue
                    bid, ask = q[m]
                    if ask - bid > 0.04:
                        continue
                    dK = (bid + ask) / 2 - sum(q[m + 1]) / 2
                    d = (p1 - p0) - dK
                    side = None
                    if d > thr:
                        side, p, won = "yes", ask, yes_won
                    elif d < -thr:
                        side, p, won = "no", 1 - bid, not yes_won
                    if side and 0.03 <= p <= 0.97:
                        u = {"r": pnl_per_dollar(p, won), "won": won, "cl": int(r["close"]), "ts": r["close"], "p": p}
                        res[(coin, thr)].append(u)
                        res[("ALL", thr)].append(u)
                        break
    dtr, dte = (SPLIT - span[0]) / 86400, (span[1] - SPLIT) / 86400
    fmt = lambda s: "n %5d edge %+6.2f%% [%+6.2f, %+6.2f] t %+5.2f" % (
        s["n"], 100 * s["edge"], 100 * s["lo"], 100 * s["hi"], s["t"]) if s["n"] else "n 0"
    for k, v in res.items():
        a = summary([u for u in v if u["ts"] < SPLIT], dtr)
        b = summary([u for u in v if u["ts"] >= SPLIT], dte)
        out["%s|%.2f" % k] = {"train": a, "test": b}
        print("%-4s thr %.2f  TR %s | TE %s" % (k[0], k[1], fmt(a), fmt(b)))
    with open(os.path.join(HERE, "results_crypto_move.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
