#!/usr/bin/env python3
"""Kalshi rewards backtest, step 1: public data for the last ~30 days (GET only, no key, no account, never an order).
For each series: every liquidity-incentive program (pool, target, discount factor, start / end) whose period overlaps the
window, then for a seeded sample of those markets: market details (result, close time), 1-minute candles (yes bid / yes ask)
over the program periods, and the full public trade tape over the same span. Cached under cache/ (gitignored, resumable).

    python research/kalshi_rewards_bt/harvest.py [SERIES,..] [--days 30] [--markets 40]
Writes cache/<series>.json.gz (programs + per-market candles + trades)."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import json
import os
import random
import threading
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
K = "https://api.elections.kalshi.com/trade-api/v2"
UA = "rewards-backtest (read-only research)"
SERIES = ["KXRT", "KXPANAMAWEEKLY", "KXBABELMANDEBWEEKLY", "KXART", "KXYTVIEWSW", "KXFEATURE", "KXEOWEEK", "KXDPRESPRIMARY"]
END = dt.datetime(2026, 11, 17, 5, tzinfo=dt.timezone.utc).timestamp()      # midnight ET, the last whole day
_lock, _last = threading.Lock(), [0.0]
GAP = 0.11


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def get(path, params=None, cache=True):
    u = K + path + ("?" + urllib.parse.urlencode(params) if params else "")
    fn = os.path.join(CACHE, "http", hashlib.md5(u.encode()).hexdigest() + ".json.gz")
    if cache and os.path.exists(fn):
        with gzip.open(fn, "rt") as f:
            return json.load(f)
    for k in range(6):
        with _lock:
            now = time.time()
            slot = max(now, _last[0] + GAP)
            _last[0] = slot
        if slot > now:
            time.sleep(slot - now)
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40)
            d = json.load(r)
            if cache:
                os.makedirs(os.path.dirname(fn), exist_ok=True)
                with gzip.open(fn, "wt") as f:
                    json.dump(d, f)
            return d
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) in (400, 404):
                return None
            time.sleep(2.0 * (k + 1))
    return None


def programs(s, t0, t1):
    out, cur = [], None
    for _ in range(200):
        q = {"series_ticker": s, "type": "liquidity", "limit": 1000}
        if cur:
            q["cursor"] = cur
        d = get("/incentive_programs", q, cache=False) or {}
        ps = d.get("incentive_programs") or []
        out += ps
        cur = d.get("next_cursor")
        if not cur or not ps:
            break
    seen, keep = set(), []
    for x in out:
        if x.get("series_ticker") != s or x.get("incentive_type") != "liquidity" or x["id"] in seen:
            continue
        seen.add(x["id"])
        if T(x["end_date"]) > t0 and T(x["start_date"]) < t1:
            keep.append({"m": x["market_ticker"], "start": T(x["start_date"]), "end": T(x["end_date"]), "usd": x["period_reward"] / 1e4,
                         "target": float(x["target_size_fp"]), "df": x["discount_factor_bps"] / 1e4, "paid": bool(x.get("paid_out"))})
    return keep


def candles(s, m, a, b):
    out = []
    step = 3 * 86400
    x, b = int(a), int(b) + 1          # whole seconds (a fractional end looped forever)
    while x < b:
        y = int(min(b, x + step))
        d = get("/series/%s/markets/%s/candlesticks" % (s, m), {"start_ts": x, "end_ts": y, "period_interval": 1}) or {}
        for c in d.get("candlesticks") or []:
            yb, ya = c.get("yes_bid") or {}, c.get("yes_ask") or {}
            out.append([c["end_period_ts"], yb.get("close_dollars"), ya.get("close_dollars"), c.get("volume_fp")])
        x = y
    out.sort()
    return out


def trades(m, a, b):
    out, cur = [], None
    for _ in range(400):
        q = {"ticker": m, "limit": 1000, "min_ts": int(a), "max_ts": int(b)}
        if cur:
            q["cursor"] = cur
        d = get("/markets/trades", q) or {}
        tr = d.get("trades") or []
        out += [[T(x["created_time"]), x["taker_side"], float(x["yes_price_dollars"]), float(x["count_fp"])] for x in tr]
        cur = d.get("cursor")
        if not cur or not tr:
            break
    out.sort()
    return out


def one_market(s, m, ps):
    a = min(p["start"] for p in ps)
    b = min(max(p["end"] for p in ps), END)
    mk = (get("/markets/" + m, cache=False) or {}).get("market") or {}
    info = {k: mk.get(k) for k in ("result", "status", "close_time", "last_price_dollars", "yes_bid_dollars", "yes_ask_dollars",
                                   "settlement_ts", "expiration_value")}
    return m, {"info": info, "programs": ps, "candles": candles(s, m, a - 3600, b), "trades": trades(m, a - 3600, b + 3 * 86400)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series", nargs="?", default=",".join(SERIES))
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--markets", type=int, default=40)
    a = ap.parse_args()
    t0 = END - a.days * 86400
    os.makedirs(CACHE, exist_ok=True)
    for s in a.series.split(","):
        fn = os.path.join(CACHE, s + ".json.gz")
        if os.path.exists(fn):
            print(s, "cached", flush=True)
            continue
        ps = programs(s, t0, END)
        sr = (get("/series/" + s, cache=False) or {}).get("series") or {}
        by = {}
        for p in ps:
            by.setdefault(p["m"], []).append(p)
        ms = sorted(by)
        random.Random(17).shuffle(ms)
        ms = ms[:a.markets]
        print(s, "programs", len(ps), "markets", len(by), "sampled", len(ms), "fee", sr.get("fee_type"), flush=True)
        out = {}
        with cf.ThreadPoolExecutor(4) as ex:
            for m, d in ex.map(lambda m: one_market(s, m, by[m]), ms):
                out[m] = d
        with gzip.open(fn, "wt") as f:
            json.dump({"series": s, "fee_type": sr.get("fee_type"), "t0": t0, "t1": END, "n_programs": len(ps),
                       "n_markets": len(by), "pool_usd_window": sum(p["usd"] * max(0, min(p["end"], END) - max(p["start"], t0)) /
                                                                     max(p["end"] - p["start"], 1) for p in ps),
                       "markets": out}, f)
        print(s, "done", sum(len(v["trades"]) for v in out.values()), "trades", sum(len(v["candles"]) for v in out.values()), "candles", flush=True)


if __name__ == "__main__":
    main()
