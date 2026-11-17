#!/usr/bin/env python3
"""K4 harvest: settled Kalshi sports winner markets + hourly yes bid/ask from 24 h before the scheduled start to 6 h after.
PUBLIC GET only, no key, no order.

    python research/kalshi_edge_K4/harvest_sports.py live            closes since the historical cutoff (batch candles)
    python research/kalshi_edge_K4/harvest_sports.py hist 2026-03-01 closes from that date to the cutoff (per-market candles)
Scheduled start = expiration_time - 48 h (Kalshi's 'not started within 48 hours' rule); checked against the volume jump.
Writes data/sports_<live|hist>.json.gz: [{t, e, s, start, close, res, vol, c:[[end_ts,bid,ask,last,vol],..]}]
"""
import datetime as dt
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import KAL, get  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = ["KXNBAGAME", "KXNFLGAME", "KXNHLGAME", "KXMLBGAME", "KXNCAAFGAME", "KXNCAAMBGAME", "KXWNBAGAME",
          "KXEPLGAME", "KXUCLGAME", "KXMLSGAME", "KXLALIGAGAME", "KXSERIEAGAME", "KXBUNDESLIGAGAME", "KXLIGUE1GAME",
          "KXUFCFIGHT"]  # tennis left out: its scheduled start is not in the market data (order of play)
GRACE = {"KXMLBGAME": 72}  # hours between the scheduled start and expiration_time (default 48)
PRE, POST = 24, 6
SOCCER = {"KXEPLGAME", "KXUCLGAME", "KXMLSGAME", "KXLALIGAGAME", "KXSERIEAGAME", "KXBUNDESLIGAGAME", "KXLIGUE1GAME"}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def listing(series, hist, lo, hi):
    ms, cur = [], None
    for _ in range(300):
        p = {"series_ticker": series, "limit": 1000, "min_close_ts": int(lo), "max_close_ts": int(hi)}
        if not hist:
            p["status"] = "settled"
        if cur:
            p["cursor"] = cur
        d = get(KAL + ("/historical" if hist else "") + "/markets", p)
        if not d or not d.get("markets"):
            break
        ms += d["markets"]
        cur = d.get("cursor")
        if not cur:
            break
    out = []
    for m in ms:
        if m.get("result") not in ("yes", "no") or not m.get("expiration_time"):
            continue
        if not lo <= ts(m["close_time"]) < hi:  # /historical ignores min/max_close_ts
            continue
        out.append({"t": m["ticker"], "e": m["event_ticker"], "s": series, "start": ts(m["expiration_time"]) - GRACE.get(series, 48) * 3600,
                    "close": ts(m["close_time"]), "res": m["result"], "vol": f(m.get("volume_fp") or m.get("volume"))})
    return out


def cand(c):  # live candles say close_dollars, /historical ones say close
    g = lambda d: f((d or {}).get("close_dollars", (d or {}).get("close")))
    return [c["end_period_ts"], g(c.get("yes_bid")), g(c.get("yes_ask")), g(c.get("price")),
            f(c.get("volume_fp") or c.get("volume"))]


def fill_live(rows):
    rows.sort(key=lambda r: r["start"])
    chunks, cur = [], []
    for r in rows:
        trial = cur + [r]
        span = (trial[-1]["start"] - trial[0]["start"]) / 3600 + PRE + POST + 2
        if cur and (len(trial) * span > 9000 or len(trial) > 100):
            chunks.append(cur)
            cur = [r]
        else:
            cur = trial
    if cur:
        chunks.append(cur)
    for i, ch in enumerate(chunks):
        a = min(r["start"] for r in ch) - PRE * 3600 - 3600
        b = max(r["start"] for r in ch) + POST * 3600
        d = get(KAL + "/markets/candlesticks", {"market_tickers": ",".join(r["t"] for r in ch), "start_ts": int(a),
                                                 "end_ts": int(b), "period_interval": 60})
        by = {m["market_ticker"]: m["candlesticks"] for m in (d or {}).get("markets", [])}
        for r in ch:
            r["c"] = [cand(c) for c in by.get(r["t"], [])
                      if r["start"] - PRE * 3600 - 3600 <= c["end_period_ts"] <= r["start"] + POST * 3600]
        if i % 50 == 0:
            print("chunk", i, len(chunks), flush=True)


def fill_hist(rows):
    for i, r in enumerate(rows):
        d = get(KAL + "/historical/markets/%s/candlesticks" % r["t"],
                {"start_ts": int(r["start"] - PRE * 3600 - 3600), "end_ts": int(r["start"] + POST * 3600), "period_interval": 60})
        r["c"] = [cand(c) for c in (d or {}).get("candlesticks", [])]
        if i % 500 == 0:
            print("hist", i, len(rows), flush=True)


def main():
    mode = sys.argv[1]
    cut = ts(get(KAL + "/historical/cutoff", cache=False)["market_settled_ts"])
    if mode == "live":
        lo, hi, hist = cut, dt.datetime.now(dt.timezone.utc).timestamp(), False
    else:
        lo, hi, hist = ts(sys.argv[2] + "T00:00:00Z"), cut, True
    series = sys.argv[3].split(",") if len(sys.argv) > 3 else SERIES  # (live: argv[2] is a placeholder)
    rows = []
    for s in series:
        x = listing(s, hist, lo, hi)
        print(s, len(x), flush=True)
        rows += x
    if hist:  # one market per two-way event (the other side is its mirror); soccer keeps home / away / tie
        seen, keep = set(), []
        for r in rows:
            if r["s"] in SOCCER or r["e"] not in seen:
                keep.append(r)
                seen.add(r["e"])
        rows = keep
        print("hist markets after one-per-event", len(rows), flush=True)
        fill_hist(rows)
    else:
        fill_live(rows)
    with gzip.open(os.path.join(HERE, "data", "sports_%s%s.json.gz" % (mode, "_" + sys.argv[3] if len(sys.argv) > 3 else "")), "wt") as fo:
        json.dump(rows, fo)
    print("saved", len(rows), flush=True)


if __name__ == "__main__":
    main()
