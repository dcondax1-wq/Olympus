#!/usr/bin/env python3
"""K4 harvest: Kalshi 15-minute crypto up/down markets (1-minute yes bid/ask for the whole window) and the SAME 15-minute
window on Polymarket (Up token price history, ~1 per minute). PUBLIC GET only, no key, no order.

    python research/kalshi_edge_K4/harvest_crypto.py 2026-10-12 2026-11-17     (closes in [from, to))
Writes data/crypto_<COIN>.json.gz: [{t, close, k, ev, res, c:[[ts,bid,ask,last,vol],..], pm:[[ts,p],..], pm_res}]
"""
import datetime as dt
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import CLOB, GAMMA, KAL, get  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COINS = {"BTC": "btc", "ETH": "eth", "SOL": "sol", "XRP": "xrp"}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def kalshi(series, lo, hi):
    ms, cur = [], None
    while True:
        p = {"series_ticker": series, "status": "settled", "limit": 1000, "min_close_ts": int(lo), "max_close_ts": int(hi)}
        if cur:
            p["cursor"] = cur
        d = get(KAL + "/markets", p)
        if not d or not d.get("markets"):
            break
        ms += d["markets"]
        cur = d.get("cursor")
        if not cur:
            break
    rows = [{"t": m["ticker"], "close": ts(m["close_time"]), "k": f(m.get("floor_strike")), "ev": f(m.get("expiration_value")),
             "res": m["result"]} for m in ms if m.get("result") in ("yes", "no")]
    rows.sort(key=lambda r: r["close"])
    for i in range(0, len(rows), 9):  # 9 tickers x ~1000 min windows < 10000 cap
        ch = rows[i:i + 9]
        a, b = ch[0]["close"] - 17 * 60, ch[-1]["close"] + 60
        d = get(KAL + "/markets/candlesticks", {"market_tickers": ",".join(r["t"] for r in ch), "start_ts": int(a),
                                                 "end_ts": int(b), "period_interval": 1})
        by = {m["market_ticker"]: m["candlesticks"] for m in (d or {}).get("markets", [])}
        for r in ch:
            r["c"] = [[c["end_period_ts"], f(c["yes_bid"].get("close_dollars")), f(c["yes_ask"].get("close_dollars")),
                       f((c.get("price") or {}).get("close_dollars")), f(c.get("volume_fp"))]
                      for c in by.get(r["t"], []) if r["close"] - 16 * 60 <= c["end_period_ts"] <= r["close"] + 60]
        if i % 450 == 0:
            print(series, "candles", i, len(rows), flush=True)
    return rows


def poly(coin, r):
    op = int(r["close"]) - 900
    e = get(GAMMA + "/events", {"slug": "%s-updown-15m-%d" % (coin, op)}, gap=0.07)
    if not e:
        return
    m = e[0]["markets"][0]
    try:
        tok = json.loads(m["clobTokenIds"])[0]
        out = json.loads(m.get("outcomePrices") or "[]")
        r["pm_res"] = "yes" if out and float(out[0]) > 0.5 else ("no" if out else None)
        r["pm_vol"] = f(m.get("volume"))
    except Exception:
        return
    h = get(CLOB + "/prices-history", {"market": tok, "startTs": op - 120, "endTs": op + 960, "fidelity": 1}, gap=0.07)
    r["pm"] = [[x["t"], x["p"]] for x in (h or {}).get("history", [])]


def main():
    lo, hi = ts(sys.argv[1] + "T00:00:00Z"), ts(sys.argv[2] + "T00:00:00Z")
    coins = sys.argv[3].split(",") if len(sys.argv) > 3 else list(COINS)
    for C in coins:
        fn = os.path.join(HERE, "data", "crypto_%s.json.gz" % C)
        rows = kalshi("KX%s15M" % C, lo, hi)
        print(C, "kalshi markets", len(rows), flush=True)
        with ThreadPoolExecutor(6) as ex:
            for i, _ in enumerate(ex.map(lambda r: poly(COINS[C], r), rows)):
                if i % 500 == 0:
                    print(C, "poly", i, flush=True)
        with gzip.open(fn, "wt") as fo:
            json.dump(rows, fo)
        print(C, "saved", len(rows), sum(1 for r in rows if r.get("pm")), flush=True)


if __name__ == "__main__":
    main()
