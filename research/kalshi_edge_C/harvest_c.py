#!/usr/bin/env python3
"""Team C harvest: settled Kalshi markets + HOURLY yes bid/ask (batch candlestick endpoint) from the PUBLIC read-only API. No key, no orders.
Writes data/snap_<series>.jsonl.gz: one row per settled market
  {t, e, ct, ot, res, ev (settlement value, e.g. the temperature), fs, cs, st, vol, q:{"<hours before close>":[bid_c, ask_c, vol_in_hour]}}
Listing = live `/markets?status=settled` + `/historical/markets` (older than the live cutoff). Polite: one request at a time (kc.py).

    python research/kalshi_edge_C/harvest_c.py [--since 2025-11-01] [--series KXHIGHNY,KXINX] [--group weather_main]
"""
import argparse, gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kc

GROUPS = {
    "weather_main": ["KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS", "KXHIGHLAX", "KXHIGHDEN", "KXHIGHPHIL"],
    "weather_rep": ["KXHIGHTSFO", "KXHIGHTPHX", "KXHIGHTATL", "KXHIGHTSEA", "KXHIGHTBOS", "KXHIGHTDAL", "KXHIGHTDC", "KXHIGHTLV",
                    "KXHIGHTHOU", "KXHIGHTMIN", "KXHIGHTOKC", "KXHIGHTNOLA", "KXHIGHTSATX"],
    "weather_low": ["KXLOWTNYC", "KXLOWTAUS", "KXLOWTDEN", "KXLOWTMIA", "KXLOWTCHI", "KXLOWTLAX", "KXLOWTPHIL"],
    "index": ["KXINX", "KXNASDAQ100"],
    "econ": ["KXFEDDECISION", "KXFED", "KXCPI", "KXCPIYOY", "KXCPICORE", "KXPAYROLLS", "KXU3", "KXGDP", "KXJOBLESSCLAIMS"],
    "other": ["KXAAAGASD", "KXAAAGASW", "KXAAAGASM", "KXTNOTED", "KXTNOTEW", "KXUSDJPY", "KXEURUSD", "KXSPOTIFYD", "KXTSAW", "KXRAINNYC",
              "KXDIESELD", "KXNETFLIXRANKSHOW", "KXRT"],
}
OFFS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 21, 24, 27, 29, 33, 36, 48]
WIN_H = 50
FAILED = []


def g(m, *names):
    for n in names:
        if m.get(n) is not None:
            return m[n]
    return None


def list_markets(series, lo, hi):
    seen = {}
    for m in kc.settled_markets(series, lo, hi):
        seen[m["ticker"]] = m
    # historical: newest first, the time filter is ignored there, so page until we are past `lo`
    cur, pages = "", 0
    while True:
        p = {"series_ticker": series, "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = kc.get("/historical/markets", p)
        if not d or not d.get("markets"):
            break
        pages += 1
        old = 0
        for m in d["markets"]:
            ct = kc.ts(m["close_time"])
            if ct < lo:
                old += 1
                continue
            if ct <= hi and m.get("result") in ("yes", "no"):
                seen.setdefault(m["ticker"], m)
        cur = d.get("cursor") or ""
        if not cur or old == len(d["markets"]) or pages > 80:
            break
    return list(seen.values())


def cents(x):
    v = kc.fl(x)
    return None if v is None else int(round(v * 100))


def candles(series, chunk):
    lo = min(kc.ts(m["close_time"]) for m in chunk) - WIN_H * 3600
    hi = max(kc.ts(m["close_time"]) for m in chunk)
    d = kc.get("/markets/candlesticks", {"market_tickers": ",".join(m["ticker"] for m in chunk), "start_ts": lo, "end_ts": hi, "period_interval": 60}, cache=False)
    out = {}
    if not d:
        if len(chunk) > 1:   # too many candles for one call, or a transient failure: split
            h = len(chunk) // 2
            out.update(candles(series, chunk[:h])); out.update(candles(series, chunk[h:]))
        else:
            FAILED.append(chunk[0]["ticker"])
        return out
    for mk in d.get("markets", []):
        tk = g(mk, "market_ticker", "ticker")
        cs = {}
        for k in mk.get("candlesticks", []):
            a = cents(g(k["yes_ask"], "close_dollars", "close"))
            b = cents(g(k["yes_bid"], "close_dollars", "close"))
            if a is None or b is None:
                continue
            cs[k["end_period_ts"]] = [b, a, int(round(kc.fl(g(k, "volume_fp", "volume")) or 0))]
        out[tk] = cs
    return out


def harvest(series, lo, hi):
    out = os.path.join(kc.DATA, f"snap_{series}.jsonl.gz")
    if os.path.exists(out):
        print(series, "cached", flush=True)
        return
    t0 = time.time()
    ms = list_markets(series, lo, hi)
    ms.sort(key=lambda m: m["close_time"])
    if ms:
        print(series, "rule:", (ms[-1].get("rules_primary") or "")[:230].replace("\n", " "), flush=True)
    rows, chunk = [], []

    def flush():
        if not chunk:
            return
        cs = candles(series, chunk)
        for m in chunk:
            ct = kc.ts(m["close_time"])
            c = cs.get(m["ticker"]) or {}
            q = {}
            for off in OFFS:
                tgt = (ct // 3600) * 3600 - off * 3600 if ct % 3600 == 0 else (ct // 3600) * 3600 - (off - 1) * 3600
                for back in (0, 1):
                    k = c.get(tgt - 3600 * back)
                    if k:
                        q[str(off)] = k + [back]
                        break
            rows.append({"t": m["ticker"], "e": m.get("event_ticker"), "ct": ct, "ot": kc.ts(m["open_time"]) if m.get("open_time") else None,
                         "res": m["result"], "ev": kc.fl(m.get("expiration_value")), "fs": m.get("floor_strike"), "cs": m.get("cap_strike"),
                         "st": m.get("strike_type"), "vol": kc.fl(g(m, "volume_fp", "volume")), "q": q})
        chunk.clear()

    for m in ms:
        ct = kc.ts(m["close_time"])
        if chunk and (len(chunk) >= 100 or (len(chunk) + 1) * (WIN_H + 2 + (ct - kc.ts(chunk[0]["close_time"])) / 3600) > 9500):
            flush()
        chunk.append(m)
    flush()
    with gzip.open(out, "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    nq = sum(1 for r in rows if r["q"])
    print(f"{series}: markets {len(rows)}, with quotes {nq}, failed {len(FAILED)}, {time.time() - t0:.0f}s, {kc.STATS}", flush=True)


def pick(c, ct):
    q = {}
    for off in OFFS:
        tgt = (ct // 3600) * 3600 - off * 3600 if ct % 3600 == 0 else (ct // 3600) * 3600 - (off - 1) * 3600
        for back in (0, 1):
            k = c.get(tgt - 3600 * back)
            if k:
                q[str(off)] = k + [back]
                break
    return q


def backfill(series, since):
    """the batch endpoint does not serve markets older than the live cutoff: fetch those one by one from /historical (slow)."""
    import concurrent.futures as cf
    fn = os.path.join(kc.DATA, f"snap_{series}.jsonl.gz")
    rows = [json.loads(l) for l in gzip.open(fn, "rt")]
    todo = [r for r in rows if not r["q"] and r["ct"] >= since and not r.get("bf")]
    t0 = time.time()

    def one(r):
        d = kc.get(f"/historical/markets/{r['t']}/candlesticks", {"start_ts": r["ct"] - WIN_H * 3600, "end_ts": r["ct"], "period_interval": 60}, cache=False)
        cs = {}
        for k in (d or {}).get("candlesticks", []):
            a = cents(g(k["yes_ask"], "close_dollars", "close")); b = cents(g(k["yes_bid"], "close_dollars", "close"))
            if a is None or b is None:
                continue
            cs[k["end_period_ts"]] = [b, a, int(round(kc.fl(g(k, "volume_fp", "volume")) or 0))]
        r["q"] = pick(cs, r["ct"])
        r["bf"] = 1 if d is not None else 0
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(one, todo))
    with gzip.open(fn, "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"{series}: backfilled {sum(1 for r in todo if r['q'])} of {len(todo)}, {time.time() - t0:.0f}s, {kc.STATS}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-11-01")
    ap.add_argument("--series", default="")
    ap.add_argument("--group", default="")
    ap.add_argument("--backfill-since", default="", help="fetch hourly quotes of pre-cutoff markets one by one from /historical, back to this date")
    a = ap.parse_args()
    os.makedirs(kc.DATA, exist_ok=True)
    lo = kc.ts(a.since + "T00:00:00")
    hi = int(time.time()) - 6 * 3600
    ser = a.series.split(",") if a.series else [s for k, v in GROUPS.items() if (not a.group or k in a.group.split(",")) for s in v]
    for s in ser:
        try:
            harvest(s, lo, hi)
            if a.backfill_since:
                backfill(s, kc.ts(a.backfill_since + "T00:00:00"))
        except Exception as e:  # keep going: one bad series must not stop the night
            print(s, "FAILED", repr(e), flush=True)


if __name__ == "__main__":
    main()
