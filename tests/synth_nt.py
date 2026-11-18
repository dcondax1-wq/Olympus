"""SYNTHETIC NinjaTrader 8 1-minute exports (tests only, never real data): a random walk with a London / NY intraday volume
profile on the CME Globex day (18:00 -> 17:00 ET, the 17:00-18:00 halt), written exactly as "Tools > Historical Data >
Export" writes it: `yyyyMMdd HHmmss;open;high;low;close;volume`, stamped at the bar's CLOSE in a chosen time zone.
Used by tests/test_other_markets.py and `python -X utf8 tools/other_markets.py selftest`.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ET = "America/New_York"


def base_bars(start: str, end: str, price: float, tick: float, vol_year: float = 0.18, seed: int = 7) -> pd.DataFrame:
    """1m bars (open-stamped UTC seconds) for every weekday trading date in [start, end]: 1,380 minutes a session."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    t0 = [pd.Timestamp(f"{(d - pd.Timedelta(days=1)).date()} 18:00").tz_localize(ET) for d in days]   # Monday: Sunday 18:00
    mins = np.arange(1380)
    et_mod = (1080 + mins) % 1440
    prof = np.full(1380, 0.55)
    prof[(et_mod >= 180) & (et_mod < 300)] = 1.6        # London
    prof[(et_mod >= 510) & (et_mod < 690)] = 2.2        # NY open
    prof[(et_mod >= 690) & (et_mod < 960)] = 1.0
    prof /= np.sqrt(np.mean(prof ** 2))
    sig_min = vol_year / np.sqrt(252.0 * 1380.0)
    T, O, H, L, C, V = [], [], [], [], [], []
    px = price
    for d0 in t0:
        ts = (d0 + pd.to_timedelta(mins, unit="m")).tz_convert("UTC")
        r = rng.standard_normal(1380) * sig_min * prof * (0.7 + 0.6 * rng.random())
        r += 0.15 * sig_min * np.sin(np.arange(1380) / 37.0 + rng.random() * 6)   # some swings for sweeps
        c = px * np.exp(np.cumsum(r))
        o = np.r_[px, c[:-1]]
        wig = np.abs(rng.standard_normal((2, 1380))) * sig_min * prof * px * 0.6
        h = np.maximum(o, c) + wig[0]
        l = np.minimum(o, c) - wig[1]
        q = lambda a: np.round(a / tick) * tick
        o, c, h, l = q(o), q(c), q(h), q(l)
        h = np.maximum.reduce([h, o, c]); l = np.minimum.reduce([l, o, c])
        T.append(np.asarray((ts - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1), dtype=np.int64)); O.append(o); H.append(h); L.append(l); C.append(c)
        V.append(rng.poisson(40 * prof).astype(np.int64) + 1)
        px = float(c[-1])
    return pd.DataFrame({"time": np.concatenate(T), "open": np.concatenate(O), "high": np.concatenate(H),
                         "low": np.concatenate(L), "close": np.concatenate(C), "volume": np.concatenate(V)})


def write_nt(df: pd.DataFrame, path: str, tz: str, tick: float):
    """Write bars in NinjaTrader export format: close stamp (open + 60 s) in time zone tz."""
    dec = max(0, len(f"{tick:.10f}".rstrip("0").split(".")[1]))
    loc = pd.to_datetime(df["time"].values + 60, unit="s", utc=True).tz_convert(tz).strftime("%Y%m%d %H%M%S")
    f = lambda a: np.char.mod(f"%.{dec}f", a.values)
    lines = np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(
        np.char.add(loc.values.astype(str), ";"), f(df["open"])), ";"), f(df["high"])), ";"), f(df["low"])), ";"), f(df["close"])), ";"),
        df["volume"].values.astype(str))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(lines.tolist()) + "\n")


def contracts(df: pd.DataFrame, roll_day: str, offset: float, tick: float, overlap_days: int = 8) -> tuple:
    """Two contracts from one base series: old = base up to a few days after roll_day, new = base + offset from
    overlap_days before it. Old trades more volume until roll_day's session, new from roll_day on (so the switch is the
    session AFTER roll_day). Returns (old, new, roll_day's trading date)."""
    et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET) + pd.Timedelta(hours=6)
    td = et.dt.strftime("%Y-%m-%d")
    days = sorted(td.unique())
    i = days.index(roll_day)
    a_end, b_start = days[min(len(days) - 1, i + 3)], days[max(0, i - overlap_days)]
    old = df[td <= a_end].copy()
    new = df[td >= b_start].copy()
    for c in ("open", "high", "low", "close"):
        new[c] = np.round((new[c] + offset) / tick) * tick
    tdo, tdn = td[td <= a_end], td[td >= b_start]
    old.loc[tdo > roll_day, "volume"] = (old.loc[tdo > roll_day, "volume"] // 10).clip(lower=1)
    old.loc[tdo == roll_day, "volume"] = (old.loc[tdo == roll_day, "volume"] // 3).clip(lower=1)
    new.loc[tdn < roll_day, "volume"] = (new.loc[tdn < roll_day, "volume"] // 10).clip(lower=1)
    return old, new, roll_day
