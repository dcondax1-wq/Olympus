#!/usr/bin/env python3
"""K3 angle 2 harvest: every settled Kalshi market on the big US releases (CPI m/m, core CPI, CPI y/y, payrolls, unemployment,
initial jobless claims, Fed rate / decision), old series names and new KX ones, from the PUBLIC read-only API.
Hourly yes bid/ask closes over the last 8 days before each market's close.

Writes data/econ_<series>.jsonl.gz, one row per market:
  {t, e, ct, res, ev, fs, cs, st, vol, q:{"<hours before close>": [bid, ask, vol]}}

    python research/kalshi_edge_K3/harvest_econ.py [--count] [--series CPI,KXCPI]
"""
import argparse, collections, gzip, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

SERIES = ["CPI", "KXCPI", "CPICORE", "KXCPICORE", "CPIYOY", "KXCPIYOY", "PAYROLLS", "KXPAYROLLS", "U3", "KXU3",
          "JOBLESS", "KXJOBLESS", "KXJOBLESSCLAIMS", "FED", "KXFED", "FEDDECISION", "KXFEDDECISION"]
OFFS = [1, 2, 3, 4, 6, 12, 24, 48, 72, 120, 168]
WIN_H = 170
CUTOFF = kk.ts("2026-09-13T00:00:00")


def list_all(series):
    allm = {}
    for hist in (True, False):
        cur, pages = "", 0
        while True:
            p = {"series_ticker": series, "limit": 1000}
            if not hist:
                p["status"] = "settled"
            if cur:
                p["cursor"] = cur
            d = kk.get(("/historical" if hist else "") + "/markets", p)
            if not d or not d.get("markets"):
                break
            for m in d["markets"]:
                if m.get("result") in ("yes", "no"):
                    allm[m["ticker"]] = m
            pages += 1
            cur = d.get("cursor") or ""
            if not cur or pages > 40:
                break
    return list(allm.values())


def parse(cs):
    out = {}
    for k in cs or []:
        a = kk.c((k.get("yes_ask") or {}).get("close_dollars") or (k.get("yes_ask") or {}).get("close"))
        b = kk.c((k.get("yes_bid") or {}).get("close_dollars") or (k.get("yes_bid") or {}).get("close"))
        if a is None or b is None:
            continue
        out[k["end_period_ts"]] = [b, a, round(kk.fl(k.get("volume_fp") or k.get("volume")) or 0)]
    return out


def pick(c, ct):
    q = {}
    base = (ct // 3600) * 3600
    for off in OFFS:
        for back in (0, 1, 2):
            k = c.get(base - (off + back) * 3600)
            if k:
                q[str(off)] = k
                break
    return q


def harvest(series):
    fn = os.path.join(kk.DATA, f"econ_{series}.jsonl.gz")
    if os.path.exists(fn):
        print(series, "cached")
        return
    ms = list_all(series)
    rows = []
    old = [m for m in ms if kk.ts(m["close_time"]) < CUTOFF]
    new = [m for m in ms if kk.ts(m["close_time"]) >= CUTOFF]
    for m in old:
        ct = kk.ts(m["close_time"])
        d = kk.get(f"/historical/markets/{m['ticker']}/candlesticks", {"start_ts": ct - WIN_H * 3600, "end_ts": ct, "period_interval": 60})
        rows.append((m, pick(parse((d or {}).get("candlesticks")), ct)))
    byev = {}
    for m in new:
        byev.setdefault(m["event_ticker"], []).append(m)
    chunks = [v[i:i + 25] for v in byev.values() for i in range(0, len(v), 25)]   # one event per call: the window stays short
    for ch in chunks:
        lo = min(kk.ts(m["close_time"]) for m in ch) - WIN_H * 3600
        hi = max(kk.ts(m["close_time"]) for m in ch)
        d = kk.get("/markets/candlesticks", {"market_tickers": ",".join(m["ticker"] for m in ch), "start_ts": lo, "end_ts": hi, "period_interval": 60})
        got = {(x.get("market_ticker") or x.get("ticker")): parse(x.get("candlesticks")) for x in (d or {}).get("markets", [])}
        for m in ch:
            rows.append((m, pick(got.get(m["ticker"], {}), kk.ts(m["close_time"]))))
    with gzip.open(fn, "wt") as fh:
        for m, q in sorted(rows, key=lambda r: r[0]["close_time"]):
            fh.write(json.dumps({"t": m["ticker"], "e": m.get("event_ticker"), "ct": kk.ts(m["close_time"]), "res": m["result"],
                                 "ev": kk.fl(m.get("expiration_value")), "fs": m.get("floor_strike"), "cs": m.get("cap_strike"),
                                 "st": m.get("strike_type"), "vol": kk.fl(m.get("volume_fp") or m.get("volume")),
                                 "title": (m.get("title") or "")[:120], "q": q}, separators=(",", ":")) + "\n")
    nq = sum(1 for _, q in rows if q)
    print(series, "markets", len(rows), "with quotes", nq, "events", len({m["event_ticker"] for m, _ in rows}), kk.STATS, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--series", default="")
    a = ap.parse_args()
    ser = a.series.split(",") if a.series else SERIES
    for s in ser:
        if a.count:
            ms = list_all(s)
            cts = sorted(m["close_time"] for m in ms)
            print(s, len(ms), "events", len({m["event_ticker"] for m in ms}), cts[0][:10] if cts else "", cts[-1][:10] if cts else "",
                  collections.Counter(m.get("strike_type") for m in ms).most_common(3), flush=True)
        else:
            harvest(s)


if __name__ == "__main__":
    main()
