"""The root rules: plain level trades on NQ 5-minute bars, one trade a day at most per root.

A root = a level x a mode x a target x a horizon.
  fade   price sweeps the level (trades through it), then a bar CLOSES back on the near side within 30 minutes: enter at
         that close against the sweep. Stop 1 tick beyond the sweep extreme (the high/low made since the sweep began).
  break  a bar CLOSES through the level: enter at that close with the break. Stop 1 tick beyond that bar's other end.
Target = entry +/- target_r x the stop distance. Out at the target, the stop, after `horizon` minutes, or at the 15:55
flat, whichever comes first (a bar that touches both the stop and the target counts as the stop). Entries close between
09:50 and 15:00 ET, and the level must sit on the far side of price when the window opens (09:45).

Money: $2 a point per MNQ micro, $1.90 a round trip in costs.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tools.strategytree.sessions import Market

TICK = 0.25
POINT_USD = 2.0                      # MNQ
COST_RT = 1.90                       # commission + fees per micro, round trip
MIN_RISK, MAX_RISK = 3.0, 100.0      # points; outside this the root takes no trade that day
RECLAIM_BARS = 6                     # the fade's reclaim must close within 30 minutes of the sweep
FIRST_ENTRY_MOD = 585                # the 09:45 bar (closes 09:50): the opening range is complete
LAST_ENTRY_MOD = 895                 # the 14:55 bar (closes 15:00)
FLAT_MOD = 950                       # the 15:50 bar: out at its close (15:55)
BAR_SECONDS = 300                    # entries and exits happen at a bar's close

# key: (day-table column, +1 a high / -1 a low, plain name)
LEVELS = {
    "PDH": ("pdh", +1, "prior-day high"), "PDL": ("pdl", -1, "prior-day low"),
    "ONH": ("onh", +1, "overnight high"), "ONL": ("onl", -1, "overnight low"),
    "AH": ("ah", +1, "Asia high"), "AL": ("al", -1, "Asia low"),
    "LH": ("lh", +1, "London high"), "LL": ("ll", -1, "London low"),
    "ORH": ("orh", +1, "opening-range high"), "ORL": ("orl", -1, "opening-range low"),
}
MODES = ("fade", "break")
TARGETS_R = (1.0, 2.0)
HORIZONS = (60, 120)

# entry_t / exit_t: unix seconds of the fill (the bar's close); entry_i / exit_i: bar indices into Market.bars
TRADE_COLS = ["root", "day_row", "date", "entry_i", "entry_t", "dir", "entry", "stop", "risk_pts", "exit_i", "exit_t",
              "exit", "reason", "r", "pnl", "mae_r", "mfe_r", "bars_held"]


@dataclass(frozen=True)
class Root:
    level: str
    mode: str
    target_r: float
    horizon: int

    @property
    def side(self) -> int:
        return LEVELS[self.level][1]

    @property
    def dir(self) -> int:
        """-1 short / +1 long: a fade goes against the level's side, a break with it."""
        return -self.side if self.mode == "fade" else self.side

    @property
    def id(self) -> str:
        return f"{self.level.lower()}_{self.mode}_{self.target_r:g}r_{self.horizon}m"

    @property
    def key(self) -> str:
        """Short label for the seed trees, e.g. ORH·SHORT (the direction names the mode for a given level)."""
        return f"{self.level}·{'LONG' if self.dir > 0 else 'SHORT'}"

    @property
    def text(self) -> str:
        name = LEVELS[self.level][2]
        side = "high" if self.side > 0 else "low"
        how = (f"after a sweep and reclaim, stop 1 tick beyond the sweep {side}" if self.mode == "fade"
               else f"on a 5-minute close through it, stop 1 tick beyond the break bar")
        return (f"{'Long' if self.dir > 0 else 'Short'} at the {name} {how}, target {self.target_r:g}R, "
                f"out after {self.horizon} min")


def all_roots() -> list[Root]:
    """The 80 roots: 10 levels x 2 modes x 2 targets x 2 horizons."""
    return [Root(lv, m, tr, hz) for lv in LEVELS for m in MODES for tr in TARGETS_R for hz in HORIZONS]


def _find_entry(h: np.ndarray, l: np.ndarray, c: np.ndarray, i0: int, i1: int, level: float, mode: str):
    """Entry on a level ABOVE price (a high). Callers mirror lows by negating prices. Returns (bar, entry, stop) or None.
    Only bars i0..i1 are read for the decision, and each decision uses bars up to the entry bar only."""
    if mode == "break":
        for i in range(i0, i1 + 1):
            if c[i] > level:
                return i, c[i], l[i] - TICK
        return None
    for i in range(i0, i1 + 1):
        if h[i] > level:                                   # the first sweep of the level
            extreme = h[i]
            for j in range(i, min(i + RECLAIM_BARS, i1 + 1)):
                extreme = max(extreme, h[j])
                if c[j] < level:
                    return j, c[j], extreme + TICK
            return None                                     # swept and held: the fade is off for the day
    return None


def find_signal(m: Market, row: dict, level_key: str, mode: str):
    """The day's entry for one level and mode: (entry bar index, entry, stop, dir) in real prices, or None."""
    col, side, _ = LEVELS[level_key]
    level = row[col]
    if not np.isfinite(level):
        return None
    b = m.bars
    a, z = int(row["a"]), int(row["z"])
    mod = b.mod[a:z]
    window = np.flatnonzero((mod >= FIRST_ENTRY_MOD) & (mod <= LAST_ENTRY_MOD))
    if not len(window) or window[0] == 0:
        return None
    i0, i1 = window[0], window[-1]                          # day-relative bar numbers
    s = float(side)
    h, l, c = b.h[a:z], b.l[a:z], b.c[a:z]
    if side < 0:                                           # mirror a low into a high
        h, l, c = -l, -h, -c
    lv = s * level
    if not c[i0 - 1] < lv:                                 # price must be on the near side when the window opens
        return None
    hit = _find_entry(h, l, c, i0, i1, lv, mode)
    if hit is None:
        return None
    j, entry, stop = hit
    j, entry, stop = a + j, s * entry, s * stop
    d = -side if mode == "fade" else side
    risk = (entry - stop) * d
    if not MIN_RISK <= risk <= MAX_RISK:
        return None
    return int(j), float(entry), float(stop), int(d)


def simulate_exit(m: Market, row: dict, j: int, entry: float, stop: float, d: int, target_r: float, horizon: int):
    """Walk the bars after the entry bar. Returns (exit bar, exit price, reason, mae_r, mfe_r) or None when the entry
    bar is already at the flat."""
    b = m.bars
    a, z = int(row["a"]), int(row["z"])
    flat = np.flatnonzero(b.mod[a:z] <= FLAT_MOD)
    i_flat = a + flat[-1] if len(flat) else j
    end = min(j + horizon // 5, i_flat)
    if end <= j:
        return None
    risk = (entry - stop) * d
    target = entry + d * target_r * risk
    mae = mfe = 0.0
    for k in range(j + 1, end + 1):
        hi, lo = b.h[k], b.l[k]
        adverse, favour = ((entry - lo), (hi - entry)) if d > 0 else ((hi - entry), (entry - lo))
        mae, mfe = max(mae, adverse / risk), max(mfe, favour / risk)
        if (d > 0 and lo <= stop) or (d < 0 and hi >= stop):
            return k, stop, "stop", min(mae, 1.0), mfe
        if (d > 0 and hi >= target) or (d < 0 and lo <= target):
            return k, target, "target", mae, min(mfe, target_r)
    return end, float(b.c[end]), "time" if end < i_flat else "flat", mae, mfe


def root_trades(m: Market, root: Root, signals: dict | None = None) -> pd.DataFrame:
    """Every trade of one root. `signals` caches find_signal per (level, mode, day row) across the roots that share them."""
    out = []
    b = m.bars
    for k, row in enumerate(m.days.to_dict("records")):
        ck = (root.level, root.mode, k)
        if signals is not None and ck in signals:
            sig = signals[ck]
        else:
            sig = find_signal(m, row, root.level, root.mode)
            if signals is not None:
                signals[ck] = sig
        if sig is None:
            continue
        j, entry, stop, d = sig
        ex = simulate_exit(m, row, j, entry, stop, d, root.target_r, root.horizon)
        if ex is None:
            continue
        xi, xp, reason, mae, mfe = ex
        risk = (entry - stop) * d
        pts = (xp - entry) * d
        out.append([root.id, k, row["date"], j, int(b.t[j]) + BAR_SECONDS, d, entry, stop, risk, xi,
                    int(b.t[xi]) + BAR_SECONDS, xp, reason, pts / risk, pts * POINT_USD - COST_RT, mae, mfe, xi - j])
    return pd.DataFrame(out, columns=TRADE_COLS)
