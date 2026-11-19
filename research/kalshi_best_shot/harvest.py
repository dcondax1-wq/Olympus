#!/usr/bin/env python3
"""Rewards-maker backtest data (public, GET only, <= 1 request a second, never an order): for each series, every liquidity
program that overlaps the window (pool, target, discount factor, start / end), and for each market with one (all of them, or a
seeded sample of --markets): its result and close time, hourly (or 1-minute) candles (yes bid / ask closes) over the program span and the
public trade tape over the same span. -> /home/user/kalshi_cache/krew/bt/<series>.json.gz (gitignored cache, resumable:
http responses are cached too).
    python research/kalshi_best_shot/harvest.py KXPANAMAWEEKLY,KXBABELMANDEBWEEKLY [--start 2026-10-18] [--end 2026-11-19] [--markets 0]"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kget  # noqa: E402

OUT = os.environ.get("KREW_BT", "/home/user/kalshi_cache/krew/bt")      # hourly candles; bt_1m for 1-minute
ET5 = 5 * 3600            # midnight ET (EST) = 05:00 UTC


def day_ts(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() + ET5


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def programs(s, t0, t1):
    out = kget.paged("/incentive_programs", {"series_ticker": s, "type": "liquidity", "limit": 10000}, "incentive_programs", cache=False)
    seen, keep = set(), []
    for x in out:
        if x.get("series_ticker") != s or x.get("incentive_type") != "liquidity" or x["id"] in seen:
            continue
        seen.add(x["id"])
        if T(x["end_date"]) > t0 and T(x["start_date"]) < t1:
            keep.append({"m": x["market_ticker"], "start": T(x["start_date"]), "end": T(x["end_date"]), "usd": x["period_reward"] / 1e4,
                         "target": float(x.get("target_size_fp") or 1000), "df": (x.get("discount_factor_bps") or 5000) / 1e4,
                         "paid": bool(x.get("paid_out"))})
    return keep


INTERVAL = 60          # minutes per candle: 1-minute candles take ~16 s a request (3 days), hourly ones cover a month at once


def candles(s, m, a, b, cache):
    out = []
    x, b = int(a), int(b) + 1
    step = 3 * 86400 if INTERVAL == 1 else 30 * 86400
    while x < b:
        y = int(min(b, x + step))
        d = kget.get("/series/%s/markets/%s/candlesticks" % (s, m), {"start_ts": x, "end_ts": y, "period_interval": INTERVAL}, cache=cache) or {}
        for c in d.get("candlesticks") or []:
            yb, ya = c.get("yes_bid") or {}, c.get("yes_ask") or {}
            out.append([c["end_period_ts"], yb.get("close_dollars"), ya.get("close_dollars"), c.get("volume_fp")])
        x = y
    out.sort()
    return out


def trades(m, a, b, cache):
    out, cur = [], None
    for _ in range(300):
        q = {"ticker": m, "limit": 1000, "min_ts": int(a), "max_ts": int(b)}
        if cur:
            q["cursor"] = cur
        d = kget.get("/markets/trades", q, cache=cache) or {}
        tr = d.get("trades") or []
        out += [[T(x["created_time"]), x["taker_side"], float(x["yes_price_dollars"]), float(x["count_fp"])] for x in tr]
        cur = d.get("cursor")
        if not cur or not tr:
            break
    out.sort()
    return out


def one_market(s, m, ps, t1):
    a = min(p["start"] for p in ps)
    b = min(max(p["end"] for p in ps), t1)
    mk = (kget.get("/markets/" + m, cache=False) or {}).get("market") or {}
    info = {k: mk.get(k) for k in ("result", "status", "close_time", "last_price_dollars", "yes_bid_dollars", "yes_ask_dollars",
                                   "settlement_ts", "expiration_value", "open_time", "event_ticker")}
    settled = info.get("result") in ("yes", "no")
    old = b < time.time() - 2 * 86400            # a closed span never changes: keep the http cache for it
    return {"info": info, "programs": ps, "candles": candles(s, m, a - 3600, b, cache=old or settled),
            "trades": trades(m, a - 3600, b + 3 * 86400, cache=settled)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("--start", default="2026-10-18")
    ap.add_argument("--end", default="2026-11-19", help="exclusive (midnight ET)")
    ap.add_argument("--markets", type=int, default=0, help="0 = every market with a program, else a seeded sample")
    ap.add_argument("--interval", type=int, default=60, choices=(1, 60), help="candle minutes (1 is ~50x slower to fetch)")
    a = ap.parse_args()
    global INTERVAL, OUT
    INTERVAL = a.interval
    OUT = OUT + ("" if INTERVAL == 60 else "_1m")
    t0, t1 = day_ts(a.start), day_ts(a.end)
    os.makedirs(OUT, exist_ok=True)
    for s in a.series.split(","):
        fn = os.path.join(OUT, s + ".json.gz")
        if os.path.exists(fn):
            print(s, "cached", flush=True)
            continue
        ps = programs(s, t0, t1)
        sr = (kget.get("/series/" + s, cache=False) or {}).get("series") or {}
        by = {}
        for p in ps:
            by.setdefault(p["m"], []).append(p)
        ms = sorted(by)
        if a.markets and len(ms) > a.markets:
            random.Random(17).shuffle(ms)
            ms = sorted(ms[:a.markets])
        print(s, "programs", len(ps), "markets", len(by), "taking", len(ms), "fee", sr.get("fee_type"), flush=True)
        out = {}
        # 3 requests in flight at most; kget still starts at most ONE request a second across all of this team's processes
        with cf.ThreadPoolExecutor(3) as ex:
            for i, (m, d) in enumerate(zip(ms, ex.map(lambda m: one_market(s, m, by[m], t1), ms))):
                out[m] = d
                if i % 10 == 9:
                    print("  ", s, i + 1, "/", len(ms), kget.STATS, flush=True)
        with gzip.open(fn + ".tmp", "wt") as f:
            json.dump({"series": s, "fee_type": sr.get("fee_type"), "t0": t0, "t1": t1, "n_programs": len(ps), "n_markets": len(by),
                       "settlement_sources": sr.get("settlement_sources"), "markets": out}, f)
        os.replace(fn + ".tmp", fn)
        print(s, "done", sum(len(v["trades"]) for v in out.values()), "trades", sum(len(v["candles"]) for v in out.values()),
              "candles", kget.STATS, flush=True)


if __name__ == "__main__":
    main()
