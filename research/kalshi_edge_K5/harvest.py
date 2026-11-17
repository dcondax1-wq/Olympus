#!/usr/bin/env python3
"""K5 harvest: settled markets (live + /historical) for the slow 'public number' series + hourly yes bid/ask candles
over the last H hours before close. PUBLIC GET only, no key, no order.
    python research/kalshi_edge_K5/harvest.py list  SERIES[,SERIES]
    python research/kalshi_edge_K5/harvest.py candles SERIES HOURS
Writes data/raw/<series>_list.json.gz and data/raw/<series>_c.json.gz (raw folder gitignored)."""
import datetime as dt, gzip, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import KAL, get  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw"); os.makedirs(RAW, exist_ok=True)

def ts(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
def f(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None

def listing(series):
    out = {}
    for hist in (False, True):
        cur = None
        for _ in range(500):
            p = {"series_ticker": series, "limit": 1000}
            if not hist: p["status"] = "settled"
            if cur: p["cursor"] = cur
            d = get(KAL + ("/historical" if hist else "") + "/markets", p)
            if not d or not d.get("markets"): break
            for m in d["markets"]:
                if m.get("result") not in ("yes", "no"): continue
                out[m["ticker"]] = {"t": m["ticker"], "e": m["event_ticker"], "s": series, "open": ts(m["open_time"]),
                    "close": ts(m["close_time"]), "res": m["result"], "ev": m.get("expiration_value"),
                    "vol": f(m.get("volume_fp") or m.get("volume")), "st": m.get("strike_type"), "fl": f(m.get("floor_strike")),
                    "cap": f(m.get("cap_strike")), "sub": m.get("yes_sub_title"), "hist": hist,
                    "rules": (m.get("rules_primary") or "")[:400]}
            cur = d.get("cursor")
            if not cur: break
    return sorted(out.values(), key=lambda r: r["close"])

def cand(c):
    g = lambda d: f((d or {}).get("close_dollars", (d or {}).get("close")))
    return [c["end_period_ts"], g(c.get("yes_bid")), g(c.get("yes_ask")), g(c.get("price")), f(c.get("volume_fp") or c.get("volume"))]

def candles(rows, hours, minvol):
    live = [r for r in rows if not r["hist"] and (r["vol"] or 0) >= minvol]
    hist = [r for r in rows if r["hist"] and (r["vol"] or 0) >= minvol]
    by_close = {}
    for r in live: by_close.setdefault(r["close"], []).append(r)
    for i, (cl, grp) in enumerate(sorted(by_close.items())):
        for k in range(0, len(grp), 80):
            ch = grp[k:k + 80]
            a = cl - hours * 3600
            d = get(KAL + "/markets/candlesticks", {"market_tickers": ",".join(r["t"] for r in ch), "start_ts": int(a), "end_ts": int(cl) + 60, "period_interval": 60})
            by = {m["market_ticker"]: m["candlesticks"] for m in (d or {}).get("markets", [])}
            for r in ch: r["c"] = [cand(c) for c in by.get(r["t"], [])]
    def one(r):
        d = get(KAL + "/historical/markets/%s/candlesticks" % r["t"], {"start_ts": int(r["close"] - hours * 3600), "end_ts": int(r["close"]) + 60, "period_interval": 60}, gap=0.15)
        r["c"] = [cand(c) for c in (d or {}).get("candlesticks", [])]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as ex:
        for i, _ in enumerate(ex.map(one, hist)):
            if i % 500 == 0: print("hist", i, len(hist), flush=True)
    return live + hist

if __name__ == "__main__":
    if sys.argv[1] == "list":
        for s in sys.argv[2].split(","):
            rows = listing(s)
            with gzip.open(os.path.join(RAW, s + "_list.json.gz"), "wt") as fo: json.dump(rows, fo)
            v = [r for r in rows if (r["vol"] or 0) > 0]
            print(s, len(rows), "traded", len(v), "events", len({r["e"] for r in rows}),
                  "first", dt.datetime.utcfromtimestamp(rows[0]["close"]).date() if rows else None,
                  "last", dt.datetime.utcfromtimestamp(rows[-1]["close"]).date() if rows else None,
                  "vol", int(sum(r["vol"] or 0 for r in rows)), flush=True)
    else:
        s, h = sys.argv[2], float(sys.argv[3]); mv = float(sys.argv[4]) if len(sys.argv) > 4 else 1
        rows = json.load(gzip.open(os.path.join(RAW, s + "_list.json.gz"), "rt"))
        since = sys.argv[5] if len(sys.argv) > 5 else None  # optional first close date (YYYY-MM-DD) to keep the fetch small
        if since: rows = [r for r in rows if r["close"] >= ts(since + "T00:00:00Z")]
        out = candles(rows, h, mv)
        with gzip.open(os.path.join(RAW, s + "_c.json.gz"), "wt") as fo: json.dump(out, fo)
        print("saved", s, len(out), "with candles", sum(1 for r in out if r.get("c")), flush=True)
