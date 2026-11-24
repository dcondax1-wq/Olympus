"""Futures bars for the structure study (data/NQ_5m.csv = TradingView NQ1! exports + the PC's NinjaTrader bars; never Yahoo/CFD).
PAPER RESEARCH ONLY. Session = the CME day 18:00 ET -> 17:00 ET, stamped with the date it closes."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_C = {}


def load(sym: str = "NQ", tf: str = "5m") -> pd.DataFrame:
    k = (sym, tf)
    if k not in _C:
        df = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_{tf}.csv"))
        df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
        et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
        df["et"] = et
        df["mins"] = et.dt.hour * 60 + et.dt.minute                     # ET minute of the bar open
        df["day"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")  # 18:00 ET -> next date
        df["dow"] = (et + pd.Timedelta(hours=6)).dt.dayofweek
        df = df[df["dow"] < 5].reset_index(drop=True)                    # no Saturday-dated stubs
        _C[k] = df
    return _C[k]


def span_of(day: str) -> str:
    return "H1" if "2026-01-01" <= day <= "2026-06-30" else "H2" if day >= "2026-07-01" else "2021-25"


def daily(df: pd.DataFrame) -> pd.DataFrame:
    """One row per CME session from the 5m bars + prior-day facts (all known before the session opens) and the ON / RTH split."""
    g = df.groupby("day", sort=True)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                      "n": g.size()})
    rth = df[(df["mins"] >= 570) & (df["mins"] < 960)]
    on = df[(df["mins"] >= 1080) | (df["mins"] < 570)]
    gr, go = rth.groupby("day"), on.groupby("day")
    d["rth_open"] = gr["open"].first()
    d["rth_high"], d["rth_low"], d["rth_close"] = gr["high"].max(), gr["low"].min(), gr["close"].last()
    d["on_high"], d["on_low"] = go["high"].max(), go["low"].min()
    d = d[d["n"] >= 150].copy()                                           # full sessions only (no half / broken days)
    d["rng"] = d["high"] - d["low"]
    d["atr"] = d["rng"].rolling(14).mean().shift(1)                       # prior 14 sessions
    d["ratio"] = d["rng"] / d["atr"]
    d["on_rng"] = (d["on_high"] - d["on_low"]) / d["atr"]
    d["inside"] = (d["high"].shift(1) <= d["high"].shift(2)) & (d["low"].shift(1) >= d["low"].shift(2))
    r = d["rng"]
    d["nr4"] = r.shift(1) <= r.shift(1).rolling(4).min()
    d["nr7"] = r.shift(1) <= r.shift(1).rolling(7).min()
    d["prior_ratio"] = d["ratio"].shift(1)
    d["span"] = [span_of(x) for x in d.index]
    return d.dropna(subset=["atr"])


def zigzag(h: np.ndarray, l: np.ndarray, thr: np.ndarray):
    """Swing pivots on bars: a pivot is fixed once price moves thr[i] points back from it.
    Returns a list of (pivot_bar, price, kind +1 high / -1 low, confirm_bar). Causal: the pivot is known only at confirm_bar."""
    piv = []
    d = 0
    ext_i, ext_p = 0, h[0]
    lo_i, lo_p = 0, l[0]
    hi_i, hi_p = 0, h[0]
    for i in range(1, len(h)):
        t = thr[i]
        if d == 0:
            if h[i] > hi_p:
                hi_i, hi_p = i, h[i]
            if l[i] < lo_p:
                lo_i, lo_p = i, l[i]
            if hi_p - l[i] >= t and hi_i < i:
                piv.append((hi_i, hi_p, 1, i)); d = -1; ext_i, ext_p = i, l[i]
            elif h[i] - lo_p >= t and lo_i < i:
                piv.append((lo_i, lo_p, -1, i)); d = 1; ext_i, ext_p = i, h[i]
            continue
        if d == 1:                       # rising from a low: track the high
            if h[i] > ext_p:
                ext_i, ext_p = i, h[i]
            elif ext_p - l[i] >= t:
                piv.append((ext_i, ext_p, 1, i)); d = -1; ext_i, ext_p = i, l[i]
        else:
            if l[i] < ext_p:
                ext_i, ext_p = i, l[i]
            elif h[i] - ext_p >= t:
                piv.append((ext_i, ext_p, -1, i)); d = 1; ext_i, ext_p = i, h[i]
    return piv
