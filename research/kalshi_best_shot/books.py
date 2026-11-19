#!/usr/bin/env python3
"""Snapshot today's public order books of the rewarded markets of some series (GET only, <= 1 request a second, never an
order) and append them to /home/user/kalshi_cache/krew/books/<day>.jsonl.gz (top 40 levels a side). One line per market:
{"t", "m", "s", "yes": [[p, size]..], "no": [..], "prog": {usd_day, target, df, start, end}, "mk": {close, bid, ask, last, vol}}.
    python research/kalshi_best_shot/books.py KXPANAMAWEEKLY,KXBABELMANDEBWEEKLY [--passes 1] [--gap 0] [--max 60]"""
from __future__ import annotations

import argparse
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

OUT = os.environ.get("KREW_BOOKS", "/home/user/kalshi_cache/krew/books")


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def F(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def programs(series):
    ps = kget.paged("/incentive_programs", {"status": "active", "type": "liquidity", "limit": 10000, "series_ticker": series},
                    "incentive_programs", cache=False)
    now = time.time()
    out = {}
    for p in ps:
        if p.get("series_ticker") != series or p.get("incentive_type") != "liquidity":
            continue
        a, b = T(p["start_date"]), T(p["end_date"])
        if not (a <= now < b):
            continue
        out[p["market_ticker"]] = {"usd_day": p["period_reward"] / 1e4 / max((b - a) / 86400, 1e-9), "usd": p["period_reward"] / 1e4,
                                   "target": F(p.get("target_size_fp"), 1000.0), "df": (p.get("discount_factor_bps") or 5000) / 1e4,
                                   "start": a, "end": b}
    return out


def markets(series):
    ms = kget.paged("/markets", {"series_ticker": series, "status": "open", "limit": 1000}, "markets", cache=False)
    return {m["ticker"]: {"close": m.get("close_time"), "bid": F(m.get("yes_bid_dollars")), "ask": F(m.get("yes_ask_dollars")),
                          "last": F(m.get("last_price_dollars")), "vol": F(m.get("volume_fp")), "vol24": F(m.get("volume_24h_fp")),
                          "oi": F(m.get("open_interest_fp")), "event": m.get("event_ticker"), "sub": m.get("yes_sub_title") or m.get("subtitle")}
            for m in ms}


def levels(ob, key):
    o = (ob or {}).get("orderbook_fp") or {}
    lv = sorted([(F(a), F(b)) for a, b in (o.get(key) or []) if F(a) is not None and F(b)], reverse=True)
    return [[round(p, 4), round(s, 2)] for p, s in lv[:40]]


def snap(series_list, max_per=60, seed=None):
    os.makedirs(OUT, exist_ok=True)
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    fn = os.path.join(OUT, day + ".jsonl.gz")
    n = 0
    with gzip.open(fn, "at") as f:
        for s in series_list:
            pr = programs(s)
            mk = markets(s)
            ts = sorted(t for t in pr if t in mk)
            if seed is not None and len(ts) > max_per:
                random.Random(seed).shuffle(ts)
            for t in ts[:max_per]:
                ob = kget.get("/markets/%s/orderbook" % t, cache=False)
                if ob is None:
                    continue
                f.write(json.dumps({"t": round(time.time(), 1), "m": t, "s": s, "yes": levels(ob, "yes_dollars"),
                                    "no": levels(ob, "no_dollars"), "prog": pr[t], "mk": mk[t]}) + "\n")
                n += 1
            f.flush()
    return n, fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--gap", type=float, default=0.0, help="seconds between the starts of passes")
    ap.add_argument("--max", type=int, default=60, help="markets per series per pass")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    for k in range(a.passes):
        t0 = time.time()
        n, fn = snap(a.series.split(","), a.max, a.seed)
        print(dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S"), "pass", k + 1, "books", n, "->", fn, kget.STATS, flush=True)
        if k < a.passes - 1:
            time.sleep(max(0.0, a.gap - (time.time() - t0)))


if __name__ == "__main__":
    main()
