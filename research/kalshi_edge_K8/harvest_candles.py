#!/usr/bin/env python3
"""1-minute Kalshi quotes (yes bid / yes ask / trade price / volume) for every 15-minute commodity market.

Markets settled after Kalshi's historical cutoff come in batches of 24 markets per request (/markets/candlesticks);
older ones one by one from /historical/markets/<ticker>/candlesticks (optionally only some windows, --windows).
Output: /home/user/kalshi_cache/kmetal/cd_<SERIES>.jsonl, one row per market:
  {"t": ticker, "hhmm": ET close time, "day": ET date, "o": open_ts, "c": close_ts, "fs": reference price,
   "ev": settlement price, "res": "yes"/"no", "vol": volume, "k": [[end_ts, bid_c, ask_c, bid_h, bid_l, ask_h, ask_l,
   px_o, px_h, px_l, px_c, vol, oi], ...]}
Resumable (skips markets already saved).  Public GET only, <=1 request/second.

    python research/kalshi_edge_K8/harvest_candles.py KXGOLD15M --live
    python research/kalshi_edge_K8/harvest_candles.py KXGOLD15M --hist --windows 0530,1700
"""
import argparse, json, os, sys
import kk8

OUT = "/home/user/kalshi_cache/kmetal"


def f(x):
    try:
        return None if x is None else round(float(x), 4)
    except Exception:
        return None


def pick(d, *names):
    for n in names:
        if d is not None and n in d:
            return d[n]
    return None


def compact_candles(cs):
    out = []
    for k in cs:
        b, a, p = k.get("yes_bid") or {}, k.get("yes_ask") or {}, k.get("price") or {}
        out.append([k["end_period_ts"],
                    f(pick(b, "close_dollars", "close")), f(pick(a, "close_dollars", "close")),
                    f(pick(b, "high_dollars", "high")), f(pick(b, "low_dollars", "low")),
                    f(pick(a, "high_dollars", "high")), f(pick(a, "low_dollars", "low")),
                    f(pick(p, "open_dollars", "open")), f(pick(p, "high_dollars", "high")),
                    f(pick(p, "low_dollars", "low")), f(pick(p, "close_dollars", "close")),
                    f(pick(k, "volume_fp", "volume")), f(pick(k, "open_interest_fp", "open_interest"))])
    return out


def meta(r):
    ev = r["event_ticker"].split("-")[1]          # e.g. 26NOV120530 -> ET date + ET close time
    return {"t": r["ticker"], "hhmm": ev[-4:], "day": ev[:7], "o": kk8.ts(r["open_time"]), "c": kk8.ts(r["close_time"]),
            "fs": f(r.get("floor_strike")), "ev": f(r.get("expiration_value")), "res": r.get("result"),
            "vol": f(r.get("volume_fp"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--hist", action="store_true")
    ap.add_argument("--windows", default="")
    ap.add_argument("--from_day", default="2026-08-01")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(OUT, "mk_%s.jsonl" % a.series))]
    rows = [r for r in rows if r.get("result") in ("yes", "no") and r["close_time"][:10] >= a.from_day]
    cut = kk8.get("/historical/cutoff", cache=False) or {}
    cutoff = kk8.ts(cut.get("market_settled_ts", "2026-09-19T00:00:00Z"))
    fn = os.path.join(OUT, "cd_%s.jsonl" % a.series)
    done = set()
    if os.path.exists(fn):
        for l in open(fn):
            try:
                done.add(json.loads(l)["t"])
            except Exception:
                pass
    wins = set(w for w in a.windows.split(",") if w)
    todo = [r for r in rows if r["ticker"] not in done and float(r.get("volume_fp") or 0) > 0]
    live = [r for r in todo if kk8.ts(r["settlement_ts"] or r["close_time"]) >= cutoff + 3600]
    hist = [r for r in todo if r not in live]
    if wins:
        hist = [r for r in hist if meta(r)["hhmm"] in wins]
        live = [r for r in live if meta(r)["hhmm"] in wins] if not a.live else live
    print(a.series, "todo live", len(live), "hist", len(hist), flush=True)
    with open(fn, "a") as out:
        if a.live:
            live.sort(key=lambda r: r["close_time"])
            i = 0
            while i < len(live):
                chunk = [live[i]]
                j = i + 1
                # up to 24 markets whose span (first open .. last close) keeps markets x minutes <= 10000
                while j < len(live) and len(chunk) < 40:
                    s0 = kk8.ts(chunk[0]["open_time"]) - 60
                    e1 = kk8.ts(live[j]["close_time"]) + 60
                    if (len(chunk) + 1) * ((e1 - s0) // 60 + 1) > 9800:
                        break
                    chunk.append(live[j])
                    j += 1
                s0 = kk8.ts(chunk[0]["open_time"]) - 60
                e1 = kk8.ts(chunk[-1]["close_time"]) + 60
                d = kk8.get("/markets/candlesticks", {"market_tickers": ",".join(r["ticker"] for r in chunk),
                                                     "start_ts": s0, "end_ts": e1, "period_interval": 1}, cache=False)
                got = {m["market_ticker"]: m["candlesticks"] for m in (d or {}).get("markets", [])}
                for r in chunk:
                    if r["ticker"] in got:
                        row = meta(r)
                        row["k"] = compact_candles(got[r["ticker"]])
                        out.write(json.dumps(row) + "\n")
                out.flush()
                i = j
                if (i // 24) % 20 == 0:
                    print(a.series, "live", i, "/", len(live), kk8.STATS, flush=True)
        if a.hist:
            for n, r in enumerate(hist):
                o, c = kk8.ts(r["open_time"]), kk8.ts(r["close_time"])
                d = kk8.get("/historical/markets/%s/candlesticks" % r["ticker"],
                            {"start_ts": o - 60, "end_ts": c + 60, "period_interval": 1}, cache=False)
                if d is None or not d.get("candlesticks"):
                    d = kk8.get("/series/%s/markets/%s/candlesticks" % (a.series, r["ticker"]),
                                {"start_ts": o - 60, "end_ts": c + 60, "period_interval": 1}, cache=False)
                if d is None:
                    continue
                row = meta(r)
                row["k"] = compact_candles(d.get("candlesticks") or [])
                out.write(json.dumps(row) + "\n")
                if n % 50 == 0:
                    out.flush()
                    print(a.series, "hist", n, "/", len(hist), kk8.STATS, flush=True)
    print(a.series, "done", kk8.STATS, flush=True)


if __name__ == "__main__":
    main()
