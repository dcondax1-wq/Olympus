#!/usr/bin/env python3
"""Pull settled Kalshi markets + 1-minute bid/ask candles from Kalshi's PUBLIC market-data API (no key, no account, read only).
Writes data/snap_<series>.jsonl: one row per settled market with the quoted yes bid/ask at fixed minutes before close.
Never places an order. Polite: 6 threads, retry on 429.

    python research/kalshi_edge_A/harvest.py [--days 59] [--minvol 20] [--series KXBTCD,KXBTC15M]
"""
import argparse, calendar, json, os, sys, time, urllib.request, urllib.error, concurrent.futures as cf

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OFFS = [2, 5, 10, 20, 30, 60, 120, 240]   # minutes before close
SERIES = {
    "crypto15": ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M"],
    "cryptoH": ["KXBTCD", "KXETHD", "KXSOLD", "KXXRPD", "KXDOGED", "KXBTC", "KXETH", "KXSOL", "KXXRP", "KXDOGE"],
    "index": ["KXINXU", "KXNASDAQ100U", "KXINXZ", "KXNASDAQ100Z", "KXINXI", "KXINXAB", "KXINX", "KXNASDAQ100", "KXINX15M"],
    "commod": ["KXGOLDH", "KXGOLDD", "KXGOLD15M", "KXWTIH", "KXWTI", "KXWTI15M", "KXGOLD"],
    "weather": ["KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHLAX", "KXHIGHDEN", "KXHIGHAUS", "KXHIGHPHIL", "KXHIGHTSEA", "KXHIGHTATL", "KXHIGHTDAL", "KXHIGHTPHX", "KXHIGHTBOS", "KXHIGHTLV", "KXHIGHTHOU", "KXHIGHTSFO", "KXHIGHTMIN", "KXHIGHTDC", "KXHIGHTNOLA", "KXHIGHTOKC", "KXHIGHTSATX"],
}


def get(path, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(B + path, headers={"User-Agent": "research-client"})
            return json.load(urllib.request.urlopen(req, timeout=25))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5 * (i + 1)); continue
            if e.code in (400, 404):
                return None
            time.sleep(1 + i)
        except Exception:
            time.sleep(1 + i)
    return None


def ts(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def snap(series, m):
    ct = ts(m["close_time"])
    c = get(f"/series/{series}/markets/{m['ticker']}/candlesticks?start_ts={ct - 4 * 3600 - 120}&end_ts={ct}&period_interval=1")
    if not c or not c.get("candlesticks"):
        return None
    cs = {k["end_period_ts"]: k for k in c["candlesticks"]}
    row = {"t": m["ticker"], "s": series, "ct": ct, "res": m["result"], "vol": f(m["volume_fp"]),
           "oi": None, "strike": m.get("floor_strike"), "type": m.get("strike_type"), "q": {}}
    for off in OFFS:
        target = ct - off * 60
        # last candle at or before the target that has a two-sided quote
        best = None
        for back in range(0, 6):
            k = cs.get(target - 60 * back)
            if not k:
                continue
            a, b = f(k["yes_ask"].get("close_dollars")), f(k["yes_bid"].get("close_dollars"))
            if a is None or b is None:
                continue
            best = (a, b, f(k.get("volume_fp")) or 0.0, f(k.get("open_interest_fp")) or 0.0, back)
            break
        if best:
            row["q"][str(off)] = best
    return row if row["q"] else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=59)
    ap.add_argument("--minvol", type=float, default=20)
    ap.add_argument("--series", default="")
    ap.add_argument("--cap", type=int, default=6000, help="max markets per series (random sample beyond that)")
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    allser = a.series.split(",") if a.series else [s for v in SERIES.values() for s in v]
    now = int(time.time())
    lo = now - a.days * 86400
    import random
    rnd = random.Random(7)
    for s in allser:
        out = os.path.join(DATA, f"snap_{s}.jsonl")
        if os.path.exists(out):
            print(s, "cached"); continue
        ms, cur = [], ""
        while True:
            d = get(f"/markets?status=settled&series_ticker={s}&limit=1000&min_close_ts={lo}&max_close_ts={now - 3600}" + (f"&cursor={cur}" if cur else ""))
            if not d:
                break
            ms += [m for m in d["markets"] if m.get("result") in ("yes", "no") and (f(m.get("volume_fp")) or 0) >= a.minvol]
            cur = d.get("cursor") or ""
            if not cur or not d["markets"]:
                break
        n0 = len(ms)
        if len(ms) > a.cap:
            ms = rnd.sample(ms, a.cap)
        t0 = time.time()
        rows = []
        with cf.ThreadPoolExecutor(int(os.environ.get("THREADS", "6"))) as ex:
            for r in ex.map(lambda m: snap(s, m), ms):
                if r:
                    rows.append(r)
        with open(out, "w") as fh:
            for r in sorted(rows, key=lambda r: r["ct"]):
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        print(f"{s}: eligible {n0}, used {len(ms)}, rows {len(rows)}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
