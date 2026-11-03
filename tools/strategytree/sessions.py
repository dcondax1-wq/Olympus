"""The market as one row per trading day: the levels the roots trade and the day facts the conditions use.

Real CME futures only: data/NQ_5m.csv and data/ES_5m.csv (TradingView NQ1! / ES1! exports, back-adjusted at the rolls)
and CBOE's VIX file data/VIX_1d.csv. A trading day runs 18:00 -> 17:00 ET (engine.data's tagging). Clock times below are
ET minutes after midnight of a bar's OPEN (09:30 bar = 570, it closes at 09:35).

Every "prior" column only uses days before the row's day, so it is known before that day's 09:30 open.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine import data as edata

TRAIN_END = "2024-12-31"           # the search sees only trades up to here
TEST_START = "2025-01-01"
YEAR_START = "2026-01-01"           # "2026 alone"
WARMUP_DAYS = 31                    # 30-day realized vol needs 31 closes

RTH_OPEN, RTH_END = 570, 960        # 09:30, 16:00
OR_END = 585                        # the opening range is the 09:30, 09:35 and 09:40 bars
ASIA = (1200, 1440)                 # 20:00 - 24:00 the evening before
LONDON = (120, 300)                 # 02:00 - 05:00
GLOBEX_OPEN = 1080                  # 18:00


@dataclass
class Market:
    """NQ bars, the day table (one row per usable day, with the bar range of each day) and the ES closes by time."""
    bars: edata.Bars
    days: pd.DataFrame
    es_close: dict                  # bar open time -> ES close (2025-04 onwards only)
    es_open: dict                   # date -> ES 09:30 open


def _window(mod: np.ndarray, lo: int, hi: int) -> np.ndarray:
    return (mod >= lo) & (mod < hi)


def _day_rows(b: edata.Bars) -> list[dict]:
    """One raw row per trading day that has a 09:30 bar: its bar range and the session highs and lows."""
    starts = np.flatnonzero(np.r_[True, b.tday[1:] != b.tday[:-1]])
    ends = np.r_[starts[1:], len(b)]
    rows = []
    for a, z in zip(starts, ends):
        mod = b.mod[a:z]
        opens = np.flatnonzero(mod == RTH_OPEN)
        rth = _window(mod, RTH_OPEN, RTH_END)
        orng = _window(mod, RTH_OPEN, OR_END)
        if not len(opens) or orng.sum() < 3:
            continue
        h, l = b.h[a:z], b.l[a:z]
        on = (mod >= GLOBEX_OPEN) | (mod < RTH_OPEN)
        asia, london = _window(mod, *ASIA), _window(mod, *LONDON)
        nan = float("nan")
        rows.append({
            "date": b.date_str[a], "a": int(a), "z": int(z), "i_open": int(a + opens[0]), "weekday": int(b.dow[a]),
            "rth_open": float(b.o[a + opens[0]]), "rth_close": float(b.c[a + np.flatnonzero(rth)[-1]]),
            "hi": float(h.max()), "lo": float(l.min()),
            "onh": float(h[on].max()) if on.any() else nan, "onl": float(l[on].min()) if on.any() else nan,
            "ah": float(h[asia].max()) if asia.any() else nan, "al": float(l[asia].min()) if asia.any() else nan,
            "lh": float(h[london].max()) if london.any() else nan, "ll": float(l[london].min()) if london.any() else nan,
            "orh": float(h[orng].max()), "orl": float(l[orng].min()),
        })
    return rows


def _prior_vix(dates: pd.Series, vix: pd.DataFrame | None) -> np.ndarray:
    """VIX close of the last CBOE date strictly before each day (yesterday's close, never today's)."""
    if vix is None or vix.empty:
        return np.full(len(dates), np.nan)
    vd = vix["date"].astype(str).values
    k = np.searchsorted(vd, dates.values, side="left") - 1
    out = np.where(k >= 0, vix["close"].values[np.clip(k, 0, None)], np.nan)
    return out.astype(float)


def build_days(b: edata.Bars, vix: pd.DataFrame | None = None) -> pd.DataFrame:
    """The day table: levels + facts known before 09:30 (prior-day range and close, 30-day vol, ATR, EMA trend, VIX).
    The first WARMUP_DAYS rows are dropped (no 30-day vol yet)."""
    d = pd.DataFrame(_day_rows(b))
    d["pdh"], d["pdl"], d["pdc"] = d["hi"].shift(1), d["lo"].shift(1), d["rth_close"].shift(1)
    d["vol30"] = np.log(d["rth_close"]).diff().rolling(30).std().shift(1) * np.sqrt(252) * 100
    d["atr14"] = (d["hi"] - d["lo"]).rolling(14).mean().shift(1)
    d["ema20"] = d["rth_close"].ewm(span=20, adjust=False).mean().shift(1)
    d["vix_prev"] = _prior_vix(d["date"], vix)
    d["gap_pct"] = (d["rth_open"] - d["pdc"]) / d["pdc"] * 100
    d["or_width"] = (d["orh"] - d["orl"]) / d["atr14"]
    d = d.iloc[WARMUP_DAYS:].dropna(subset=["vol30", "atr14", "pdh"]).reset_index(drop=True)
    return d


def _es_maps() -> tuple[dict, dict]:
    """ES closes by bar time and ES 09:30 opens by date (data/ES_5m.csv covers 2025-04 onwards only)."""
    if not os.path.exists(os.path.join(edata.DATA_DIR, "ES_5m.csv")):
        return {}, {}
    es = edata.load("ES", "5m")
    close = dict(zip(es.t.tolist(), es.c.tolist()))
    at_open = np.flatnonzero(es.mod == RTH_OPEN)
    opens = {es.date_str[i]: float(es.o[i]) for i in at_open}
    return close, opens


def load_market() -> Market:
    """The real market: NQ 5m, ES 5m and CBOE VIX from data/."""
    b = edata.load("NQ", "5m")
    vix_path = os.path.join(edata.DATA_DIR, "VIX_1d.csv")
    vix = pd.read_csv(vix_path).sort_values("date") if os.path.exists(vix_path) else None
    es_close, es_open = _es_maps()
    return Market(b, build_days(b, vix), es_close, es_open)


def period_of(dates: np.ndarray | pd.Series) -> dict[str, np.ndarray]:
    """Boolean masks of the three judged spans for an array of yyyy-mm-dd dates."""
    d = np.asarray(dates, dtype=str)
    return {"train": d <= TRAIN_END, "test": d >= TEST_START, "y2026": d >= YEAR_START}
