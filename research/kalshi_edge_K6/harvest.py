#!/usr/bin/env python3
"""K6 harvest: settled Kalshi rates markets + their HOURLY yes bid/ask over the market's life (public API, GET only,
no key, never an order; <= 1 request a second; cached in /home/user/kalshi_cache/knew1, resumable).

Strike selection uses only what was known BEFORE the market opened (the last official yield published before the open
day), never the settlement value, so the sample is not conditioned on the outcome.

Writes data/q_<SERIES>.jsonl.gz, one row per market:
  {t, e, ot, ct, res, fs, cs, st, ev, c: [[end_ts, bid_c, ask_c, vol], ...]}

    python research/kalshi_edge_K6/harvest.py SERIES[,SERIES...] [--near 0.20] [--every 1] [--days 40]
"""
import argparse, bisect, gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk6

YIELD_OF = {"KXTNOTED": "DGS10", "KXTNOTEW": "DGS10", "KXUST10A": "DGS10", "KXUST2A": "DGS2", "KXUST5A": "DGS5",
            "KXUST30A": "DGS30", "KX10YRDIRHW": "DGS10", "KX10YRDIRLW": "DGS10", "KX10YRDIRHM": "DGS10",
            "KX10YRDIRLM": "DGS10", "KX2YRDIRHM": "DGS2", "KX2YRDIRLM": "DGS2", "KX5YRDIRHM": "DGS5",
            "KX30YRDIRHM": "DGS30", "KXSOFRD": "SOFR", "KX5YRDIRLM": "DGS5", "KX30YRDIRLM": "DGS30",
            "KX7YRDIRHM": "DGS7", "KX7YRDIRLM": "DGS7"}


def prior_value(fred, series, day):
    ds = sorted(fred[series])
    i = bisect.bisect_left(ds, day) - 1
    return fred[series][ds[i]] if i >= 0 else None


def parse_candles(lst):
    out = []
    for k in lst or []:
        a = kk6.cents(kk6.g(k.get("yes_ask") or {}, "close_dollars", "close"))
        b = kk6.cents(kk6.g(k.get("yes_bid") or {}, "close_dollars", "close"))
        if a is None or b is None:
            continue
        out.append([k["end_period_ts"], b, a, int(round(kk6.fl(kk6.g(k, "volume_fp", "volume")) or 0))])
    return out


def window(m, days):
    ot, ct = kk6.ts(m["open_time"]), kk6.ts(m["close_time"])
    return int(max(ot, ct - days * 86400)) - 3600, ct


def fetch_batch(chunk, days):
    lo = min(window(m, days)[0] for m in chunk)
    hi = max(window(m, days)[1] for m in chunk)
    d = kk6.get("/markets/candlesticks", {"market_tickers": ",".join(m["ticker"] for m in chunk), "start_ts": lo,
                                          "end_ts": hi, "period_interval": 60}, retry400=False)
    if not d:
        if len(chunk) > 1:
            h = len(chunk) // 2
            r = fetch_batch(chunk[:h], days)
            r.update(fetch_batch(chunk[h:], days))
            return r
        return {chunk[0]["ticker"]: fetch_one(chunk[0], days, hist=False)}
    return {kk6.g(mk, "market_ticker", "ticker"): parse_candles(mk.get("candlesticks")) for mk in d.get("markets", [])}


def fetch_one(m, days, hist=True):
    lo, hi = window(m, days)
    path = ("/historical" if hist else "") + f"/markets/{m['ticker']}/candlesticks"
    if not hist:
        path = f"/series/{m.get('_series')}/markets/{m['ticker']}/candlesticks"
    d = kk6.get(path, {"start_ts": lo, "end_ts": hi, "period_interval": 60})
    return parse_candles((d or {}).get("candlesticks"))


def harvest(series, near, every, days, fred):
    out = os.path.join(kk6.DATA, f"q_{series}.jsonl.gz")
    live = kk6.markets(series)
    hist = kk6.markets(series, historical=True)
    live_t = {m["ticker"] for m in live}
    ms = [m for m in {m["ticker"]: m for m in hist + live}.values() if m.get("result") in ("yes", "no")]
    for m in ms:
        m["_series"] = series
    ys = YIELD_OF.get(series)
    if ys and near:
        keep = []
        for m in ms:
            y0 = prior_value(fred, ys, m["open_time"][:10])
            lo_k, hi_k = kk6.fl(m.get("floor_strike")), kk6.fl(m.get("cap_strike"))
            ks = [k for k in (lo_k, hi_k) if k is not None]
            if y0 is None or not ks:
                continue
            a, b = (min(ks), max(ks))
            if b >= y0 - near and a <= y0 + near:   # bucket / strike touches [y0 - near, y0 + near]
                keep.append(m)
        ms = keep
    if every > 1:
        evs = sorted({m["event_ticker"] for m in ms})
        pick = set(evs[::every])
        ms = [m for m in ms if m["event_ticker"] in pick]
    ms.sort(key=lambda m: m["close_time"])
    done = {}
    if os.path.exists(out):
        for line in gzip.open(out, "rt"):
            r = json.loads(line)
            if r["c"]:                       # empty = a failed fetch (transient 400/404 under load): try again
                done[r["t"]] = r
    todo = [m for m in ms if m["ticker"] not in done]
    print(f"{series}: {len(ms)} markets selected, {len(done)} done, {len(todo)} to fetch "
          f"({sum(1 for m in todo if m['ticker'] in live_t)} live)", flush=True)
    t0 = time.time()
    rows = list(done.values())

    def row(m, c):
        return {"t": m["ticker"], "e": m.get("event_ticker"), "ot": kk6.ts(m["open_time"]), "ct": kk6.ts(m["close_time"]),
                "res": m["result"], "fs": kk6.fl(m.get("floor_strike")), "cs": kk6.fl(m.get("cap_strike")),
                "st": m.get("strike_type"), "ev": kk6.fl(m.get("expiration_value")),
                "vol": kk6.fl(kk6.g(m, "volume_fp", "volume")), "c": c}

    def save():
        tmp = out + ".tmp"
        with gzip.open(tmp, "wt") as fh:
            for r in sorted(rows, key=lambda r: r["ct"]):
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        os.replace(tmp, out)

    lv = [m for m in todo if m["ticker"] in live_t]
    chunk = []
    for m in lv + [None]:
        if m is not None:
            span = (window(m, days)[1] - window(m, days)[0]) / 3600 + 2
            if not chunk or (len(chunk) < 60 and (len(chunk) + 1) * span < 4500):
                chunk.append(m)
                continue
        if chunk:
            cs = fetch_batch(chunk, days)
            rows.extend(row(x, cs.get(x["ticker"]) or []) for x in chunk)
            save()
        chunk = [m] if m is not None else []
    hs = [m for m in todo if m["ticker"] not in live_t]
    for i, m in enumerate(hs):
        rows.append(row(m, fetch_one(m, days, hist=True)))
        if i % 50 == 49:
            save()
            print(f"  {series} {i + 1}/{len(hs)} {time.time() - t0:.0f}s {kk6.STATS}", flush=True)
    save()
    print(f"{series}: done, {len(rows)} rows, {sum(1 for r in rows if r['c'])} with quotes, {time.time() - t0:.0f}s, {kk6.STATS}",
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("--near", type=float, default=0.0)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--days", type=float, default=40)
    a = ap.parse_args()
    fred = json.load(open(os.path.join(kk6.DATA, "fred.json")))
    for s in a.series.split(","):
        try:
            harvest(s, a.near, a.every, a.days, fred)
        except Exception as e:
            print(s, "FAILED", repr(e), flush=True)


if __name__ == "__main__":
    main()
