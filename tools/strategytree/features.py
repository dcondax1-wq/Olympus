"""The conditions a branch can add, each one known at the entry bar's close (no look-ahead).

A feature turns every trade into a bucket code (0..K-1, or -1 when the fact is missing that day). A *condition* is one
bucket or, for an ordered feature, a contiguous band of buckets: vol30d[vol q2..vol q5] keeps the trades in the 2nd to
5th volatility quintile. A path through the tree uses each feature at most once.

Day facts (vol30d, gap, pos_pd, trend, vix, or_width, weekday) come from the day table (sessions.py: prior days, the
09:30 open, the opening range that closes at 09:45, before the first entry at 09:50). Intraday facts (hour, dist_open,
vwap, es) read bars from the 09:30 open up to and including the entry bar, never after it.

The quantile cut points (volatility quintiles, opening-range terciles) come from TRAIN days only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tools.strategytree.sessions import Market, TRAIN_END


@dataclass(frozen=True)
class Feature:
    name: str
    labels: tuple
    ordinal: bool
    text: str                                    # what the fact is, in plain words


@dataclass(frozen=True)
class Condition:
    feature: int                                 # index into FEATURES
    lo: int
    hi: int
    label: str                                   # tree label, e.g. vol30d[vol q2..vol q5]
    text: str                                    # plain words, e.g. "30-day volatility is in quintile 2 to 5"


FEATURES = (
    Feature("vol30d", ("vol q1", "vol q2", "vol q3", "vol q4", "vol q5"), True, "30-day realized volatility quintile"),
    Feature("gap", ("gap down", "no gap", "gap up"), True, "the 09:30 open vs yesterday's close (0.25% bands)"),
    Feature("pos_pd", ("below pd low", "low half", "high half", "above pd high"), True,
            "where the 09:30 open sits in yesterday's range"),
    Feature("dist_open", ("near open", "mid", "far"), True, "entry distance from the 09:30 open (0.15 / 0.4 ATR)"),
    Feature("hour", ("9-10", "10-11", "11-12", "12-13", "13-14", "14-15"), True, "the hour of the entry (ET)"),
    Feature("weekday", ("Mon", "Tue", "Wed", "Thu", "Fri"), False, "the day of the week"),
    Feature("vwap", ("above vwap", "below vwap"), False, "entry price vs the session VWAP since 09:30"),
    Feature("trend", ("uptrend", "downtrend"), False, "yesterday's close vs its 20-day EMA"),
    Feature("vix", ("vix<15", "vix15-20", "vix20-25", "vix25+"), True, "yesterday's VIX close"),
    Feature("or_width", ("narrow OR", "mid OR", "wide OR"), True, "opening-range width vs the 14-day ATR (terciles)"),
    Feature("es", ("ES agrees", "ES splits"), False, "ES's move since 09:30 has the same sign as NQ's"),
)
F = {f.name: i for i, f in enumerate(FEATURES)}


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_POS = {(0, 0): "below yesterday's low", (1, 1): "in the low half of yesterday's range",
        (2, 2): "in the high half of yesterday's range", (3, 3): "above yesterday's high",
        (0, 1): "below the middle of yesterday's range", (1, 2): "inside yesterday's range",
        (2, 3): "above the middle of yesterday's range", (0, 2): "below yesterday's high", (1, 3): "above yesterday's low"}
_DIST = {(0, 0): "near the 09:30 open (under 0.15 ATR)", (1, 1): "0.15-0.4 ATR from the 09:30 open",
         (2, 2): "far from the 09:30 open (over 0.4 ATR)", (0, 1): "within 0.4 ATR of the 09:30 open",
         (1, 2): "at least 0.15 ATR from the 09:30 open"}
_OR = {(0, 0): "narrow", (1, 1): "mid-sized", (2, 2): "wide", (0, 1): "not wide", (1, 2): "not narrow"}
_VIX = (None, 15, 20, 25, None)


def _vix_words(a: int, b: int) -> str:
    lo, hi = _VIX[a], _VIX[b + 1]
    return f"below {hi}" if lo is None else f"{lo} or more" if hi is None else f"{lo}-{hi}"


# plain words for a band lo..hi of each feature (the rule cards and the write-up read these)
PHRASES = {
    "vol30d": lambda a, b: f"30-day volatility is in quintile {a + 1}" + ("" if a == b else f" to {b + 1}"),
    "gap": lambda a, b: {(0, 0): "the open gapped down", (1, 1): "the open did not gap", (2, 2): "the open gapped up",
                         (0, 1): "the open did not gap up", (1, 2): "the open did not gap down"}[(a, b)],
    "pos_pd": lambda a, b: "the 09:30 open is " + _POS[(a, b)],
    "dist_open": lambda a, b: "the entry is " + _DIST[(a, b)],
    "hour": lambda a, b: f"the entry is between {'9:50' if a == 0 else f'{a + 9}:00'} and {b + 10}:00 ET",
    "weekday": lambda a, b: f"it is a {_WEEKDAYS[a]}",
    "vwap": lambda a, b: "price is above the session VWAP" if a == 0 else "price is below the session VWAP",
    "trend": lambda a, b: ("the daily trend is up" if a == 0 else "the daily trend is down") +
                          " (yesterday's close vs its 20-day EMA)",
    "vix": lambda a, b: f"yesterday's VIX closed {_vix_words(a, b)}",
    "or_width": lambda a, b: "the opening range is " + _OR[(a, b)],
    "es": lambda a, b: "ES moved the same way as NQ since 09:30" if a == 0 else "ES moved the other way since 09:30",
}


def describe(f: Feature, a: int, b: int) -> str:
    """Plain words for the band a..b of feature f (a generic sentence for a feature without a phrase)."""
    if f.name in PHRASES:
        return PHRASES[f.name](a, b)
    return f"{f.text}: " + (f.labels[a] if a == b else f"{f.labels[a]} to {f.labels[b]}")


def conditions(features=FEATURES) -> list[Condition]:
    """Every condition: each bucket of a feature, plus every contiguous band (not the full range) of an ordered one."""
    out = []
    for fi, f in enumerate(features):
        k = len(f.labels)
        bands = [(a, b) for a in range(k) for b in range(a, k) if (a, b) != (0, k - 1)] if f.ordinal and k > 2 \
            else [(a, a) for a in range(k)]
        for a, b in bands:
            label = f"{f.name}={f.labels[a]}" if a == b else f"{f.name}[{f.labels[a]}..{f.labels[b]}]"
            out.append(Condition(fi, a, b, label, describe(f, a, b)))
    return out


def _bucket(x: np.ndarray, edges) -> np.ndarray:
    """Bucket codes by ascending edges; NaN -> -1."""
    codes = np.searchsorted(np.asarray(edges, dtype=float), x, side="right").astype(int)
    return np.where(np.isfinite(x), codes, -1)


def train_edges(days: pd.DataFrame) -> dict:
    """Quantile cut points from train days only (a fixed rule, so test days never shape their own buckets)."""
    tr = days[days["date"] <= TRAIN_END]
    return {"vol30d": np.quantile(tr["vol30"], [0.2, 0.4, 0.6, 0.8]).round(4).tolist(),
            "or_width": np.quantile(tr["or_width"].dropna(), [1 / 3, 2 / 3]).round(4).tolist()}


def _vwap_at(m: Market, i_open: int, j: int) -> float:
    """Volume-weighted typical price of the bars from the 09:30 bar to the entry bar j (inclusive)."""
    b = m.bars
    sl = slice(i_open, j + 1)
    tp = (b.h[sl] + b.l[sl] + b.c[sl]) / 3
    v = b.v[sl]
    return float((tp * v).sum() / v.sum()) if v.sum() > 0 else float(tp.mean())


def _es_code(m: Market, row: dict, j: int, nq_entry: float) -> int:
    """0 ES agrees / 1 ES splits on the sign of the move since 09:30 at the entry bar's close, -1 without ES data."""
    es_now = m.es_close.get(int(m.bars.t[j]))
    es_open = m.es_open.get(row["date"])
    if es_now is None or es_open is None:
        return -1
    nq_move, es_move = nq_entry - row["rth_open"], es_now - es_open
    if nq_move == 0 or es_move == 0:
        return -1
    return 0 if (nq_move > 0) == (es_move > 0) else 1


def encode(m: Market, trades: pd.DataFrame, edges: dict) -> np.ndarray:
    """Bucket codes, one row per trade and one column per FEATURES entry (int8, -1 = missing)."""
    days = m.days
    if trades.empty:
        return np.zeros((0, len(FEATURES)), dtype=np.int8)
    rows = days.iloc[trades["day_row"].values].reset_index(drop=True)
    entry = trades["entry"].values.astype(float)
    codes = np.full((len(trades), len(FEATURES)), -1, dtype=np.int8)
    codes[:, F["vol30d"]] = _bucket(rows["vol30"].values, edges["vol30d"])
    codes[:, F["gap"]] = _bucket(rows["gap_pct"].values, [-0.25, 0.25])
    rng = (rows["pdh"] - rows["pdl"]).values
    pos = np.where(rng > 0, (rows["rth_open"].values - rows["pdl"].values) / np.where(rng > 0, rng, 1), np.nan)
    codes[:, F["pos_pd"]] = _bucket(pos, [0.0, 0.5, 1.0])
    codes[:, F["dist_open"]] = _bucket(np.abs(entry - rows["rth_open"].values) / rows["atr14"].values, [0.15, 0.4])
    close_min = m.bars.mod[trades["entry_i"].values] + 5            # the entry bar's close, ET minutes
    codes[:, F["hour"]] = np.clip(close_min // 60, 9, 14) - 9
    codes[:, F["weekday"]] = rows["weekday"].values
    vwap = np.array([_vwap_at(m, int(io), int(j)) for io, j in zip(rows["i_open"], trades["entry_i"])])
    codes[:, F["vwap"]] = np.where(entry >= vwap, 0, 1)
    codes[:, F["trend"]] = np.where(rows["pdc"].values >= rows["ema20"].values, 0, 1)
    codes[:, F["vix"]] = _bucket(rows["vix_prev"].values, [15, 20, 25])
    codes[:, F["or_width"]] = _bucket(rows["or_width"].values, edges["or_width"])
    day_rows = days.to_dict("records")
    codes[:, F["es"]] = [_es_code(m, day_rows[k], int(j), e) for k, j, e in
                         zip(trades["day_row"], trades["entry_i"], entry)]
    return codes


def condition_masks(codes: np.ndarray, conds: list[Condition]) -> np.ndarray:
    """(n_conditions x n_trades) bool: which trades each condition keeps (a missing fact never passes)."""
    if not len(conds):
        return np.zeros((0, len(codes)), dtype=bool)
    fi = np.array([c.feature for c in conds])
    lo = np.array([c.lo for c in conds])[:, None]
    hi = np.array([c.hi for c in conds])[:, None]
    x = codes[:, fi].T
    return (x >= lo) & (x <= hi)
