"""PANTHEON statistics: percentiles, rolling z-scores, the no-look-ahead alignment and the honest NQ relation table.

No look-ahead: a value observed on date t is only "known" `lag` business days later (FRED daily data posts the next day,
the CFTC report of Tuesday's positions comes out on Friday). A god's reading for session D is the last value known by the
close of the previous session (D - 1 business day), and it is compared with NQ's return of session D (close D / close D-1),
i.e. "the next-day return" of what was known at the close.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NQ_1D = os.path.join(ROOT, "data", "NQ_1d.csv")
BDAY = pd.offsets.BDay(1)
Z_WINDOW, Z_MIN = 1260, 250            # 5 years of observations, at least ~1 year before a z-score counts
PERIODS = (("2021-25", "2021-11-01", "2025-12-31"), ("2026", "2026-01-01", "2026-12-31"))
VOTE_ON = 0.25                         # |vote| from which a day counts as a risk-on / risk-off call in the hit rate
MIN_CORR, MIN_EDGE = 0.05, 2.0         # a "weak signal" needs corr >= 0.05 and +2 points over chance in BOTH periods


def nq_returns(path: str = NQ_1D) -> pd.Series:
    """NQ1! (TradingView CME export, back-adjusted additively: daily point moves are real) session returns, by session date."""
    df = pd.read_csv(path)
    idx = pd.to_datetime(df["time"], unit="s").dt.normalize()
    close = pd.Series(df["close"].to_numpy(dtype=float), index=idx)
    close = close[~close.index.duplicated(keep="last")].sort_index()
    return close.diff().div(close.shift(1)).dropna()


def sessions(start: str = "2021-11-01", end=None) -> pd.DatetimeIndex:
    """Mon-Fri session dates from start to the next business day after `end` (default today)."""
    end = pd.Timestamp(end or pd.Timestamp.today()).normalize()
    return pd.bdate_range(start, end + BDAY)


def known_on(s: pd.Series, days: pd.DatetimeIndex, lag: int = 0) -> pd.Series:
    """For each session D in `days`: the last value of `s` known by the close of D - 1 (observations become known `lag`
    business days after their date). NaN before the first known value."""
    s = s.dropna().sort_index()
    if s.empty:
        return pd.Series(np.nan, index=days)
    known = s.copy()
    known.index = s.index + pd.offsets.BDay(lag) if lag else s.index
    known = known[~known.index.duplicated(keep="last")]
    asof = days - BDAY
    pos = known.index.searchsorted(asof, side="right") - 1
    vals = np.where(pos >= 0, known.to_numpy()[np.clip(pos, 0, None)], np.nan)
    return pd.Series(vals, index=days, dtype=float)


def rolling_z(s: pd.Series, window: int = Z_WINDOW, min_periods: int = Z_MIN) -> pd.Series:
    """z-score of each value against the window that ends on it (past and present only, never the future)."""
    m = s.rolling(window, min_periods=min_periods).mean()
    sd = s.rolling(window, min_periods=min_periods).std()
    return (s - m) / sd.replace(0, np.nan)


def vote(z: pd.Series, direction: int) -> pd.Series:
    """Risk-on (+1) .. risk-off (-1): direction x z / 2, clipped."""
    return (direction * z / 2.0).clip(-1, 1)


def percentile(s: pd.Series, years: float = 5.0) -> tuple[float | None, float]:
    """(percentile 0-100 of the latest value within the last `years` of history, the years actually covered)."""
    s = s.dropna()
    if len(s) < 20:
        return None, 0.0
    last_t = s.index[-1]
    hist = s[s.index > last_t - pd.DateOffset(days=int(365.25 * years))]
    cover = (hist.index[-1] - hist.index[0]).days / 365.25
    return round(100.0 * float((hist <= s.iloc[-1]).mean()), 1), round(cover, 1)


def change(s: pd.Series, n: int, pct: bool = False) -> float | None:
    s = s.dropna()
    if len(s) <= n:
        return None
    a, b = float(s.iloc[-1 - n]), float(s.iloc[-1])
    if pct:
        return None if a == 0 else 100.0 * (b / a - 1.0)
    return b - a


def spark(s: pd.Series, days: int = 365, points: int = 64) -> list:
    """The last `days` of a series, down-sampled to about `points` values (the card's sparkline)."""
    s = s.dropna()
    if s.empty:
        return []
    s = s[s.index > s.index[-1] - pd.Timedelta(days=days)]
    if len(s) > points:
        s = s.iloc[np.linspace(0, len(s) - 1, points).round().astype(int)]
    return [_r(x) for x in s.to_numpy()]


def _r(x, nd=4):
    if x is None or not math.isfinite(float(x)):
        return None
    x = float(x)
    mag = abs(x)
    return round(x, nd if mag < 10 else 2 if mag < 1e4 else 0)


def relation(sig: pd.Series, ret: pd.Series) -> dict:
    """How a session-aligned vote related to NQ's return of the same session (i.e. the next day after it was known).

    Per period (2021-25, 2026): n days, Pearson corr, the hit rate on days with |vote| >= VOTE_ON (risk-on and NQ up, or
    risk-off and NQ down), the hit rate expected by chance (votes independent of NQ), NQ's average return on risk-on and
    risk-off days; plus the honest verdict: "weak signal" only when it holds in both periods, "inverse" when NQ did the
    opposite in both (reported, never flipped: a flip would need its own research run), else "context, not a signal"."""
    df = pd.concat({"v": sig, "r": ret}, axis=1).dropna()
    out = {"periods": [], "verdict": "context, not a signal", "holds": False, "inverse": False}
    good = bad = 0
    for name, a, b in PERIODS:
        d = df[(df.index >= a) & (df.index <= b)]
        row = {"period": name, "n": int(len(d)), "corr": None, "hit": None, "chance": None, "edge": None, "calls": 0,
               "avg_on": None, "avg_off": None, "n_on": 0, "n_off": 0}
        if len(d) >= 30 and d["v"].std() > 0:
            row["corr"] = round(float(d["v"].corr(d["r"])), 3)
            c = d[(d["v"].abs() >= VOTE_ON) & (d["r"] != 0)]
            on, off = d[d["v"] >= VOTE_ON], d[d["v"] <= -VOTE_ON]
            row.update(n_on=int(len(on)), n_off=int(len(off)), calls=int(len(c)),
                       avg_on=None if on.empty else round(100 * float(on["r"].mean()), 3),
                       avg_off=None if off.empty else round(100 * float(off["r"].mean()), 3))
            if len(c) >= 20:
                hit = float(((c["v"] > 0) == (c["r"] > 0)).mean())
                p_on, up = float((c["v"] > 0).mean()), float((c["r"] > 0).mean())
                chance = p_on * up + (1 - p_on) * (1 - up)
                row.update(hit=round(100 * hit, 1), chance=round(100 * chance, 1), edge=round(100 * (hit - chance), 1))
                if row["corr"] >= MIN_CORR and row["edge"] >= MIN_EDGE:
                    good += 1
                if row["corr"] <= -MIN_CORR and row["edge"] <= -MIN_EDGE:
                    bad += 1
        out["periods"].append(row)
    if good == len(PERIODS):
        out.update(verdict="weak signal (holds in 2021-25 and 2026)", holds=True)
    elif bad == len(PERIODS):
        out.update(verdict="inverse (both periods): NQ tended to do the opposite of the textbook reading", inverse=True)
    return out


def abs_move(flag: pd.Series, ret: pd.Series) -> dict:
    """ATHENA: NQ's average absolute move on flagged sessions (event days) vs the others, per period."""
    df = pd.concat({"f": flag.astype(float), "r": ret.abs()}, axis=1).dropna()
    rows = []
    for name, a, b in PERIODS:
        d = df[(df.index >= a) & (df.index <= b)]
        on, off = d[d["f"] > 0], d[d["f"] <= 0]
        rows.append({"period": name, "n_on": int(len(on)), "n_off": int(len(off)),
                     "abs_on": None if on.empty else round(100 * float(on["r"].mean()), 3),
                     "abs_off": None if off.empty else round(100 * float(off["r"].mean()), 3),
                     "ratio": None if on.empty or off.empty or off["r"].mean() == 0 else round(float(on["r"].mean() / off["r"].mean()), 2)})
    bigger = all(r["ratio"] is not None and r["ratio"] >= 1.1 for r in rows)
    return {"periods": rows, "verdict": "bigger moves on event days (both periods)" if bigger else "context, not a signal",
            "holds": bigger}


def intervals(flag: pd.Series) -> list:
    """Run-length ranges of a boolean session series: [["2022-07-05", "2024-09-03"], ...] (inclusive)."""
    f = flag.fillna(False).astype(bool)
    out, start, prev = [], None, None
    for t, v in f.items():
        if v and start is None:
            start = t
        if not v and start is not None:
            out.append([str(start.date()), str(prev.date())])
            start = None
        prev = t
    if start is not None:
        out.append([str(start.date()), str(prev.date())])
    return out
