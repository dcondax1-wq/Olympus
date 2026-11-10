#!/usr/bin/env python3
"""Collect settled Kalshi crypto markets + their last-minutes 1-minute quote candles (PUBLIC data, read-only, no key).

    python research/kalshi_edge_B/collect.py 15m KXBTC15M 3000     # up/down 15-minute markets, newest N
    python research/kalshi_edge_B/collect.py hourly KXBTCD 14      # hourly strike ladders, last N days (near-money strikes only)

Writes research/kalshi_edge_B/data/<series>.json.gz = list of markets with compact candles:
  c = [[end_ts, yes_bid_close, yes_ask_close, last_close, volume], ...] (dollars, None when empty)
"""
import sys, os, json, gzip, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kapi import get

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def candles(series, tk, close, lead):
    d = get("/series/%s/markets/%s/candlesticks" % (series, tk),
            {"start_ts": int(close - lead * 60 - 60), "end_ts": int(close + 60), "period_interval": 1})
    if not d:
        return None
    out = []
    for c in d.get("candlesticks", []):
        out.append([c["end_period_ts"], f(c["yes_bid"].get("close_dollars")), f(c["yes_ask"].get("close_dollars")),
                    f(c["price"].get("close_dollars")), f(c.get("volume_fp"))])
    return out


def batch(rows, lead):
    """fill r['c'] for rows using the batch candlestick endpoint (<=60 tickers per call)."""
    rows.sort(key=lambda r: r["close"])
    chunks, cur = [], []
    for r in rows:  # the API caps tickers x window-minutes at 10000
        trial = cur + [r]
        span = (trial[-1]["close"] - trial[0]["close"]) / 60 + lead + 3
        if cur and len(trial) * span > 9000:
            chunks.append(cur); cur = [r]
        else:
            cur = trial
    if cur:
        chunks.append(cur)
    for i, ch in enumerate(chunks):
        lo = min(r["close"] for r in ch) - lead * 60 - 60
        hi = max(r["close"] for r in ch) + 60
        d = get("/markets/candlesticks", {"market_tickers": ",".join(r["t"] for r in ch), "start_ts": int(lo),
                                          "end_ts": int(hi), "period_interval": 1})
        by = {m["market_ticker"]: m["candlesticks"] for m in (d or {}).get("markets", [])}
        for r in ch:
            out = []
            for c in by.get(r["t"], []):
                if c["end_period_ts"] < r["close"] - lead * 60 or c["end_period_ts"] > r["close"] + 60:
                    continue
                out.append([c["end_period_ts"], f(c["yes_bid"].get("close_dollars")), f(c["yes_ask"].get("close_dollars")),
                            f(c["price"].get("close_dollars")), f(c.get("volume_fp"))])
            r["c"] = out
        print("batch", i, len(chunks), flush=True)


def mk(m):
    return {"t": m["ticker"], "e": m["event_ticker"], "k": m.get("floor_strike"), "cap": m.get("cap_strike"),
            "close": ts(m["close_time"]), "open": ts(m["open_time"]), "res": m["result"],
            "ev": f(m.get("expiration_value")), "vol": f(m.get("volume_fp")), "st": m.get("strike_type")}


def main():
    kind, series, arg = sys.argv[1], sys.argv[2], int(sys.argv[3])
    skip = int(sys.argv[4]) if len(sys.argv) > 4 else 0  # skip the newest `skip` markets (already collected): older block only
    rows = []
    if kind == "15m":
        cur, ms = None, []
        while len(ms) < arg:
            p = {"series_ticker": series, "status": "settled", "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = get("/markets", p)
            if not d or not d["markets"]:
                break
            ms += d["markets"]
            cur = d.get("cursor")
            if not cur:
                break
        ms = [m for m in ms[skip:arg] if m["result"] in ("yes", "no")]
        for i, m in enumerate(ms):
            rows.append(mk(m))
        batch(rows, 16)
    else:
        cur, evs = None, []
        cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - arg * 86400
        done = False
        while not done:
            p = {"series_ticker": series, "status": "settled", "limit": 100, "with_nested_markets": "true"}
            if cur:
                p["cursor"] = cur
            d = get("/events", p)
            if not d or not d["events"]:
                break
            for e in d["events"]:
                ms = e.get("markets") or []
                if not ms:
                    continue
                if ts(ms[0]["close_time"]) < cutoff:
                    done = True
                    break
                evs.append(ms)
            cur = d.get("cursor")
            if not cur:
                break
        print("events", len(evs), flush=True)
        for j, ms in enumerate(evs):
            ev = [f(m.get("expiration_value")) for m in ms if m.get("expiration_value")]
            if not ev:
                continue
            S = ev[0]
            for m in ms:
                if m["result"] not in ("yes", "no") or m.get("floor_strike") is None:
                    continue
                if abs(m["floor_strike"] / S - 1) > 0.012:
                    continue
                rows.append(mk(m))
        batch(rows, 30)
    with gzip.open(os.path.join(OUT, series + ("_older" if skip else "") + ".json.gz"), "wt") as fh:
        json.dump(rows, fh)
    print("done", series, len(rows))


main()
