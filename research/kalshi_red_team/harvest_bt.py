#!/usr/bin/env python3
"""Red team: re-harvest the rewards backtest's raw tape (research/kalshi_rewards_bt/harvest.py, same sample, same format) at
<= 1 request a second, into /home/user/kalshi_cache/kred/bt/ (outside the repo). GET only, public data, never an order.
  window 'bt'  : the backtest's own 30 days (END = 2026-11-17 05:00 UTC), the same seeded sample of 40 markets per series
  window 'oos' : END .. --until (default: now, whole minutes): days the backtest never saw (all program markets)
    python research/kalshi_red_team/harvest_bt.py KXPANAMAWEEKLY,KXBABELMANDEBWEEKLY [--window bt|oos] [--markets 40]"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402

OUT = os.path.join(fetch.CACHE, "bt")
END = 1794891600.0             # 2026-11-17 05:00 UTC = research/kalshi_rewards_bt/harvest.py END
DAYS = 30


def T(s):
    import datetime as dt
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def programs(s, t0, t1):
    rows = fetch.paged("/incentive_programs", {"series_ticker": s, "type": "liquidity", "limit": 1000}, "incentive_programs",
                       cursor_key="next_cursor", cache=False)
    seen, keep = set(), []
    for x in rows:
        if x.get("series_ticker") != s or x.get("incentive_type") != "liquidity" or x["id"] in seen:
            continue
        seen.add(x["id"])
        if T(x["end_date"]) > t0 and T(x["start_date"]) < t1:
            keep.append({"m": x["market_ticker"], "start": T(x["start_date"]), "end": T(x["end_date"]), "usd": x["period_reward"] / 1e4,
                         "target": float(x["target_size_fp"]), "df": x["discount_factor_bps"] / 1e4, "paid": bool(x.get("paid_out"))})
    return keep


def candles(s, m, a, b, cache):
    out, x, b = [], int(a), int(b) + 1
    while x < b:
        y = int(min(b, x + 3 * 86400))
        d = fetch.get("/series/%s/markets/%s/candlesticks" % (s, m), {"start_ts": x, "end_ts": y, "period_interval": 1}, cache=cache) or {}
        for c in d.get("candlesticks") or []:
            yb, ya = c.get("yes_bid") or {}, c.get("yes_ask") or {}
            out.append([c["end_period_ts"], yb.get("close_dollars"), ya.get("close_dollars"), c.get("volume_fp")])
        x = y
    out.sort()
    return out


def trades(m, a, b, cache):
    rows = fetch.paged("/markets/trades", {"ticker": m, "limit": 1000, "min_ts": int(a), "max_ts": int(b)}, "trades", cache=cache, max_pages=400)
    out = [[T(x["created_time"]), x["taker_side"], float(x["yes_price_dollars"]), float(x["count_fp"])] for x in rows]
    out.sort()
    return out


def one_market(s, m, ps, t1, cache):
    a = min(p["start"] for p in ps)
    b = min(max(p["end"] for p in ps), t1)
    mk = (fetch.get("/markets/" + m, cache=False) or {}).get("market") or {}
    info = {k: mk.get(k) for k in ("result", "status", "close_time", "last_price_dollars", "yes_bid_dollars", "yes_ask_dollars",
                                   "settlement_ts", "expiration_value")}
    info["fetched"] = time.time()
    return {"info": info, "programs": ps, "candles": candles(s, m, a - 3600, b, cache), "trades": trades(m, a - 3600, min(b + 3 * 86400, t1 + 3 * 86400), cache)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("--window", default="bt", choices=("bt", "oos"))
    ap.add_argument("--markets", type=int, default=40)
    ap.add_argument("--until", type=float, default=None)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.window == "bt":
        t0, t1 = END - DAYS * 86400, END
    else:
        t0, t1 = END, float(int((a.until or time.time()) // 60 * 60))
    for s in a.series.split(","):
        fn = os.path.join(OUT, "%s_%s.json.gz" % (s, a.window))
        if os.path.exists(fn):
            print(s, a.window, "cached", flush=True)
            continue
        ps = programs(s, t0, t1)
        sr = (fetch.get("/series/" + s, cache=False) or {}).get("series") or {}
        by = {}
        for p in ps:
            by.setdefault(p["m"], []).append(p)
        ms = sorted(by)
        if a.window == "bt":                       # the backtest's own seeded sample
            random.Random(17).shuffle(ms)
            ms = ms[:a.markets]
        print(s, a.window, "programs", len(ps), "markets", len(by), "taking", len(ms), "fee", sr.get("fee_type"), flush=True)
        out = {}
        import concurrent.futures as cf       # 3 threads share the 1-request-a-second lock (they only overlap the waiting)
        with cf.ThreadPoolExecutor(3) as ex:
            for i, (m, dd) in enumerate(ex.map(lambda m: (m, one_market(s, m, by[m], t1, cache=(a.window == "bt"))), ms)):
                out[m] = dd
                if i % 10 == 9:
                    print("  ", s, i + 1, "/", len(ms), "requests so far", fetch.COUNT[0], flush=True)
        with gzip.open(fn, "wt") as f:
            json.dump({"series": s, "window": a.window, "fee_type": sr.get("fee_type"), "fee_multiplier": sr.get("fee_multiplier"),
                       "t0": t0, "t1": t1, "n_programs": len(ps), "n_markets": len(by),
                       "pool_usd_window": sum(p["usd"] * max(0, min(p["end"], t1) - max(p["start"], t0)) / max(p["end"] - p["start"], 1) for p in ps),
                       "markets": out}, f)
        print(s, a.window, "done", sum(len(v["trades"]) for v in out.values()), "trades", sum(len(v["candles"]) for v in out.values()),
              "candles; requests", fetch.COUNT[0], flush=True)


if __name__ == "__main__":
    main()
