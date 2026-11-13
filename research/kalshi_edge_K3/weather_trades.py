#!/usr/bin/env python3
"""K3 angle 3, trade tape: after a temperature bucket's outcome is known from the METARs, who still trades it and at what price?

For each crossing in data/weather_minute_rows.jsonl.gz (market whose outcome became known at t_obs, margin 0 or 1 degree F),
pull the PUBLIC trade tape (GET /markets/trades) from t_obs - 10 min to the market's close and count, from t_obs + 5 min on:
  taker   = contracts a taker bought on the KNOWN side at <= 98c (an offer was there to lift: a taker bot would have got them)
  maker   = contracts someone bought on the WRONG side at >= 2c (a resting order on the known side at <= 98c would have been filled)
  maker99 = the same at exactly 1c / 99c (the 'last cent', where the fee rounding eats most of it)
with the profit per contract 100 - price - fee (taker 0.07 p(1-p); maker 0.0175 p(1-p), both rounded up per order of 100).
Upper bounds: queue position and competing resting orders are not modelled.

    python research/kalshi_edge_K3/weather_trades.py
Writes data/weather_trades.json.
"""
import gzip, json, os, random, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk


def trades(ticker, lo, hi):
    out, cur, pages = [], "", 0
    while True:
        p = {"ticker": ticker, "min_ts": lo, "max_ts": hi, "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = kk.get("/markets/trades", p)
        if not d:
            break
        for t in d.get("trades", []):
            out.append((kk.ts(t["created_time"]), kk.c(t["yes_price_dollars"]), t["taker_side"], kk.fl(t["count_fp"]) or 0.0))
        cur = d.get("cursor") or ""
        pages += 1
        if not cur or pages > 20 or not d.get("trades"):
            break
    return out


def fee(p, rate):
    return kk.fee_c(p, 100, rate) / 100


def main():
    rows = [json.loads(l) for l in gzip.open(os.path.join(kk.DATA, "weather_minute_rows.jsonl.gz"), "rt")]
    first = {}
    for r in rows:
        k = r["t"]
        first[k] = min(first.get(k, 1e18), r["t_obs"])
    close = {}
    for r in rows:
        close[r["t"]] = r["t_obs"] + r["hrs_left"] * 3600
    tape = {}
    t0 = time.time()
    for i, (tk, t) in enumerate(sorted(first.items())):
        tape[tk] = trades(tk, int(t - 600), int(close[tk]))
        if i % 200 == 0:
            print(i, len(first), round(time.time() - t0), kk.STATS, flush=True)
    windows = [("5-15m", 300, 900), ("15-60m", 900, 3600), ("1-6h", 3600, 21600), ("6h+", 21600, 10 ** 9)]
    out = {"n_markets": len(first), "cells": {}}
    for kind in ("high", "low"):
        for mg in (0, 1):
            rs = [r for r in rows if r["kind"] == kind and r["margin"] == mg]
            days = sorted({r["e"].split("-")[1] for r in rs})
            cell = {"crossings": len(rs), "lost": sum(not r["won"] for r in rs), "days": len(days), "w": {}}
            for wn, a, b in windows:
                agg = defaultdict(float)
                for r in rs:
                    for ts_, yp, side, n in tape.get(r["t"], []):
                        dt = ts_ - r["t_obs"]
                        if not (a <= dt < b) or yp is None:
                            continue
                        kp = (100 - yp) if r["side"] == "no" else yp       # price of the KNOWN side in this print
                        taker_known = (side == "no") if r["side"] == "no" else (side == "yes")
                        won = r["won"]
                        if kp <= 98:
                            if taker_known:
                                agg["taker_n"] += n
                                agg["taker_pnl_usd"] += n * ((100 if won else 0) - kp - fee(kp, 0.07)) / 100
                            else:
                                agg["maker_n"] += n
                                agg["maker_pnl_usd"] += n * ((100 if won else 0) - kp - fee(kp, 0.0175)) / 100
                        elif kp == 99 and not taker_known:
                            agg["maker99_n"] += n
                            agg["maker99_pnl_usd"] += n * ((100 if won else 0) - kp - fee(kp, 0.0175)) / 100
                cell["w"][wn] = {k: round(v, 2) for k, v in agg.items()}
                for k in ("taker_pnl_usd", "maker_pnl_usd", "maker99_pnl_usd"):
                    cell["w"][wn][k.replace("_usd", "_per_day")] = round(agg[k] / max(1, len(days)), 2)
            # day-level bootstrap of the maker (<=98c) P&L from t+5 min to close, per day
            perday = defaultdict(float)
            for r in rs:
                for ts_, yp, side, n in tape.get(r["t"], []):
                    if ts_ - r["t_obs"] < 300 or yp is None:
                        continue
                    kp = (100 - yp) if r["side"] == "no" else yp
                    taker_known = (side == "no") if r["side"] == "no" else (side == "yes")
                    if kp <= 98 and not taker_known:
                        perday[r["e"].split("-")[1]] += n * ((100 if r["won"] else 0) - kp - fee(kp, 0.0175)) / 100
            vals = [perday.get(d, 0.0) for d in days]
            rnd = random.Random(5)
            bs = sorted(sum(rnd.choice(vals) for _ in vals) / len(vals) for _ in range(2000)) if vals else [0]
            cell["maker_usd_per_day_after_5m"] = {"mean": round(sum(vals) / max(1, len(vals)), 2), "lo": round(bs[50], 2), "hi": round(bs[1949], 2),
                                                  "worst_day": round(min(vals), 2) if vals else None}
            out["cells"][f"{kind}_m{mg}"] = cell
            print(kind, mg, json.dumps(cell))
    json.dump(out, open(os.path.join(kk.DATA, "weather_trades.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
