"""Download real CME index futures bars (NQ/ES continuous) from Yahoo Finance.

Saves CSVs in data/ as  <SYM>_<interval>.csv  with columns: time(unix sec, UTC),open,high,low,close,volume
Yahoo limits: 1m -> last ~30 days (7-day chunks), 5m/15m -> 60 days, 1h -> 730 days.
"""
import os
import sys
import time
import datetime as dt

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
SYMBOLS = {"NQ": "NQ=F", "ES": "ES=F"}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert("UTC")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    out = df.reset_index(drop=True)
    secs = (df.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
    out.insert(0, "time", pd.Series(secs, dtype="int64").values)
    return out


def fetch(sym: str, interval: str, period: str | None = None, chunks_days: int | None = None, total_days: int | None = None):
    tkr = SYMBOLS[sym]
    if chunks_days:
        frames = []
        end = dt.datetime.now(dt.timezone.utc)
        start_limit = end - dt.timedelta(days=total_days)
        while end > start_limit:
            start = max(start_limit, end - dt.timedelta(days=chunks_days))
            df = yf.download(tkr, start=start, end=end, interval=interval, progress=False, auto_adjust=False, prepost=True)
            frames.append(_clean(df))
            end = start
            time.sleep(0.5)
        out = pd.concat(frames).drop_duplicates("time").sort_values("time")
    else:
        df = yf.download(tkr, period=period, interval=interval, progress=False, auto_adjust=False, prepost=True)
        out = _clean(df)
    path = os.path.join(HERE, f"{sym}_{interval}.csv")
    # merge with existing file so history accumulates over repeated runs
    if os.path.exists(path):
        old = pd.read_csv(path)
        out = pd.concat([old, out]).drop_duplicates("time", keep="last").sort_values("time")
    out = out[out["volume"] >= 0]
    out.to_csv(path, index=False)
    print(f"{sym} {interval}: {len(out)} bars  "
          f"{dt.datetime.fromtimestamp(out.time.iloc[0], dt.timezone.utc):%Y-%m-%d} -> "
          f"{dt.datetime.fromtimestamp(out.time.iloc[-1], dt.timezone.utc):%Y-%m-%d %H:%M} UTC")
    return out


def main():
    syms = sys.argv[1:] or list(SYMBOLS)
    for s in syms:
        fetch(s, "1m", chunks_days=7, total_days=29)
        fetch(s, "5m", period="60d")
        fetch(s, "15m", period="60d")
        fetch(s, "1h", period="730d")
        fetch(s, "1d", period="10y")


if __name__ == "__main__":
    main()
