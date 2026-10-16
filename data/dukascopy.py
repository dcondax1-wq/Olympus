"""Long-history proxy data: Dukascopy Nasdaq-100 (USATECHIDXUSD) and S&P 500 (USA500IDXUSD) CFD 1-minute candles.

The CFDs track the cash indices that NQ/ES are priced off, so they give multi-year intraday history for
validating the model beyond Yahoo's 60-day intraday limit. Saved as NQX_5m/NQX_1h and ESX_5m/ESX_1h.
python dukascopy.py [years=3]
"""
import datetime as dt
import lzma
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "duka_cache")
FEEDS = {"NQX": "USATECHIDXUSD", "ESX": "USA500IDXUSD"}


def fetch_day(inst: str, day: dt.date):
    path = os.path.join(CACHE, inst, f"{day:%Y%m%d}.bi5")
    if os.path.exists(path):
        raw = open(path, "rb").read()
    else:
        url = f"https://datafeed.dukascopy.com/datafeed/{inst}/{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
        raw = None
        for attempt in range(6):
            try:
                raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
                time.sleep(1.0)
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raw = b""
                    break
                time.sleep(8 * (attempt + 1))
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        if raw is None:
            return []
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(raw)
    if not raw:
        return []
    d = lzma.decompress(raw)
    base = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp())
    out = []
    for k in range(len(d) // 24):
        ts, o, c, lo, hi, v = struct.unpack(">5if", d[k * 24:(k + 1) * 24])
        if v <= 0 and o == c == lo == hi:
            continue
        out.append((base + ts, o / 1000, hi / 1000, lo / 1000, c / 1000, round(v * 1e4, 2)))
    return out


def build(sym: str, years: float):
    inst = FEEDS[sym]
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=int(365 * years))
    days = [start + dt.timedelta(days=k) for k in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() != 5]  # Saturdays are closed
    rows = []
    with ThreadPoolExecutor(1) as ex:
        for k, recs in enumerate(ex.map(lambda d: fetch_day(inst, d), days)):
            rows.extend(recs)
            if k % 100 == 0:
                print(f"  {sym} {k}/{len(days)}", flush=True)
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).sort_values("time")
    for tf, secs in (("5m", 300), ("1h", 3600)):
        g = df.assign(b=df["time"] // secs * secs).groupby("b")
        out = pd.DataFrame({"time": g["b"].first(), "open": g["open"].first(), "high": g["high"].max(),
                            "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()})
        out.to_csv(os.path.join(HERE, f"{sym}_{tf}.csv"), index=False)
        print(f"{sym} {tf}: {len(out)} bars")


def build_from_cache(sym: str):
    """Build NQX/ESX CSVs from whatever day files are already cached (no network)."""
    inst = FEEDS[sym]
    folder = os.path.join(CACHE, inst)
    rows = []
    for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        day = dt.date(int(fn[:4]), int(fn[4:6]), int(fn[6:8]))
        rows.extend(fetch_day(inst, day))
    if not rows:
        print(f"{sym}: nothing cached")
        return
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).sort_values("time")
    for tf, secs in (("5m", 300), ("1h", 3600)):
        g = df.assign(b=df["time"] // secs * secs).groupby("b")
        out = pd.DataFrame({"time": g["b"].first(), "open": g["open"].first(), "high": g["high"].max(),
                            "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()})
        out.to_csv(os.path.join(HERE, f"{sym}_{tf}.csv"), index=False)
        print(f"{sym} {tf}: {len(out)} bars from cache")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--range":
        # python dukascopy.py --range 2026-08-05 2026-10-15 NQX   (download a window, then rebuild from cache)
        a, z = dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
        syms = sys.argv[4].split(",") if len(sys.argv) > 4 else list(FEEDS)
        for s in syms:
            d = a
            while d <= z:
                if d.weekday() != 5:
                    fetch_day(FEEDS[s], d)
                    print(f"  {s} {d}", flush=True)
                d += dt.timedelta(days=1)
            build_from_cache(s)
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--cache-only":
        for s in (sys.argv[2].split(",") if len(sys.argv) > 2 else FEEDS):
            build_from_cache(s)
        sys.exit(0)
    yrs = float(sys.argv[1]) if len(sys.argv) > 1 else 3
    for s in (sys.argv[2].split(",") if len(sys.argv) > 2 else FEEDS):
        build(s, yrs)

