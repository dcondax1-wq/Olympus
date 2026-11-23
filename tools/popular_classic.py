"""Popular classic NQ / ES day-trading + quant strategies, as their common textbook rules state (2026-11-23, day-pop-classic).
Paper research only: edits no engine / model / live_model*.json / UI file, arms nothing. Write-up:
research/writeups/popular-classic-2026-11-23.md. Numbers: research/lab/popular_classic.json (+ _detail).

ONE fixed version per strategy, written here BEFORE the first run; no parameter was changed after a look (16 tests).
Bars: CME NQ1! 5m (data/NQ_5m.csv, TradingView back-adjusted, 2021-10 -> 2026-11), RTH 09:30-15:55 ET. ES1! 5m
(data/ES_5m.csv) only exists from 2025-04, so ES is a 2026 robustness column (same rules, MES), not a 2021-25 span.

Execution (all strategies): signal on a 5m bar close -> market entry at the next bar's open + 1 tick slippage; stop-entry
orders fill at the level + 1 tick (or the open if it gaps through); a stop touched in a bar fills at the stop (or the open
through it) - 1 tick; a target is a limit needing a trade-through; stop + target in one bar = stop; rule exits on a bar
close fill at the next open - 1 tick; everything flat at the 15:55 bar's open (MFFU flat by 16:10). $1.90 round turn per
micro. MFFU micro sizing: $400 risk a trade, micros = floor(400 / (stop pts x PV + 1.90)), 1-40 (MNQ $2/pt, MES $5/pt);
a trade whose 1 micro costs more than $400 is skipped. Stops under 8 NQ pts (2 ES pts) widened. One position at a time.
Strategies with no stop in the textbook get a disaster stop for sizing and prop rules (written per strategy below).

 1 orb30     Opening range breakout, 30 min: OR = 09:30-10:00 high/low. First 5m close beyond it 10:00-12:00 -> with it.
             Stop = OR midpoint, target 2R, else 15:55. One a day.
 2 vwaprev   VWAP reversion: RTH VWAP from 09:30 (typical price x volume), volume-weighted SD bands. A 5m close beyond
             +/-2 SD (10:00-15:00) -> fade back to VWAP (target = VWAP at entry), stop 1 tick beyond the 3 SD band. Max 2/day.
 3 vwaptrend VWAP trend pullback: from 10:00-14:30, close above VWAP and VWAP rising (vs 6 bars ago) = up-trend; a bar whose
             low touches VWAP and closes back above it -> long (mirror short). Stop 1 tick beyond the bar, target 2R. Max 2/day.
 4 rsi2_5m   Connors RSI(2): close > SMA200 and RSI(2) < 10 -> long; close < SMA200 and RSI(2) > 90 -> short; exit on a close
             back through SMA5 (long: close > SMA5). Disaster stop 2 x ATR(14). Entries 09:45-15:00 RTH. 5m bars.
 5 rsi2_15m  Same on 15m bars (built from 5m, clock aligned); exit / signal only on 15m closes.
 6 donchian  Donchian 20/10: close above the prior 20 bars' high -> long, exit on a close below the prior 10 bars' low
             (mirror short); initial stop = the 10-bar channel at entry. 5m bars (24h series), entries 10:00-15:00.
 7 nr7id     Crabel NR7 inside day: yesterday's RTH range is the narrowest of 7 AND inside the day before. Today buy stop
             1 tick above yesterday's high / sell stop below its low (first touched, 09:30-15:00), stop = yesterday's
             midpoint, out 15:55.
 8 bbsqueeze Bollinger squeeze: BB(20, 2) inside Keltner(EMA20, 1.5 x ATR20) for >= 6 bars, then the first close outside
             BB -> with it. Stop = SMA20 (BB middle) at entry, target 2R. 10:00-15:00, one a day.
 9 gapfill   Opening gap fill: gap = 09:30 open vs prior 15:55-bar close, 0.1% <= |gap| <= 0.5%. Fade at the 09:30 open,
             target = prior close, stop = 1 x the gap beyond the open (1:1), out 15:55.
10 ib_break  Initial Balance breakout: IB = 09:30-10:30. First 5m close beyond it 10:30-14:00 -> with it. Stop = IB
             midpoint, target = 1 IB width beyond the broken edge (1x extension). One a day.
11 ib_fade   Initial Balance fade: price trades beyond the IB and a 5m close is back inside (within 3 bars), 10:30-14:00 ->
             fade. Stop 1 tick beyond the probe extreme, target = IB midpoint. One a day.
12 ema921    9/21 EMA pullback: EMA9 > EMA21 and close > EMA21 = up-trend; a bar whose low touches EMA9 and closes above it
             -> long (mirror). Stop 1 tick below min(bar low, EMA21), target 2R. 09:45-15:00, max 3/day.
13 keltner   Keltner breakout: close above EMA20 + 2 x ATR10 -> long (mirror); exit on a close back through EMA20; initial
             stop = EMA20 at entry. 10:00-15:00.
14 crabel    Crabel stretch: stretch = 10-day mean of min(H-O, O-L) of RTH days. Buy stop at open + stretch, sell stop at
             open - stretch (first hit), stop = the opposite level, out 15:55.
15 eodmom    End-of-day momentum (Gao et al.): sign of the 09:30 -> 15:25 return; enter at the 15:30 open with it, out at the
             15:55 open. Disaster stop 2 x ATR(14) 5m.
16 tuesday   Turnaround Tuesday: Monday RTH close < Friday RTH close -> long Tuesday 09:30 open -> 15:55. Disaster stop =
             0.5 x ATR(14) of daily RTH ranges.

Spans: 2026 Jan-Jun (H1), 2026 Jul-Oct (H2), 2021-25. Report: trades/week, win %, PF, $/month, max DD; daily correlation
with LIT (research/lab/backtest_live.json) and ATLAS (research/runs/atlas_base.json) + overlap (share of its trade days
LIT / ATLAS also trade); add-on value in a Rapid EOD 25K ($1,500 target, $1,000 EOD trail, add-on $200 a trade, LIT+ATLAS
book x0.5) and 50K ($3,000 / $2,000, add-on $400, book x1) started every session (pass / fail within 40, $/month).
Multiple testing: p-value of mean daily $ (t) on 2021-25, Holm over the 16; "passes" = Holm p < 0.05 AND net > 0 with
PF >= 1.1 in both 2026 halves (any span fails -> rejected).

    python -X utf8 tools/popular_classic.py
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "popular_classic.json")
OUTD = os.path.join(ROOT, "research", "lab", "popular_classic_detail.json")
TICK, COMM, RISK, MAXQ = 0.25, 1.90, 400.0, 40
SYM = {"NQ": {"pv": 2.0, "minstop": 8.0}, "ES": {"pv": 5.0, "minstop": 2.0}}
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-31"), "2021-25": ("2021-01-01", "2025-12-31")}

NAMES = {"orb30": "Opening Range Breakout 30 min", "vwaprev": "VWAP reversion (2 SD -> VWAP)", "vwaptrend": "VWAP trend pullback",
         "rsi2_5m": "Connors RSI(2) 5m", "rsi2_15m": "Connors RSI(2) 15m", "donchian": "Donchian 20/10 breakout",
         "nr7id": "NR7 inside-day breakout", "bbsqueeze": "Bollinger squeeze breakout", "gapfill": "Opening gap fill",
         "ib_break": "Initial Balance breakout", "ib_fade": "Initial Balance fade", "ema921": "9/21 EMA pullback in trend",
         "keltner": "Keltner channel breakout", "crabel": "Crabel stretch", "eodmom": "End-of-day momentum (last 30 min)",
         "tuesday": "Turnaround Tuesday"}
FAMILY = {"orb30": "breakout", "vwaprev": "mean_reversion", "vwaptrend": "trend_pullback", "rsi2_5m": "mean_reversion",
          "rsi2_15m": "mean_reversion", "donchian": "breakout", "nr7id": "volatility_breakout", "bbsqueeze": "volatility_breakout",
          "gapfill": "mean_reversion", "ib_break": "breakout", "ib_fade": "mean_reversion", "ema921": "trend_pullback",
          "keltner": "breakout", "crabel": "volatility_breakout", "eodmom": "momentum", "tuesday": "seasonality"}
# Already in docs/TESTED_AND_REJECTED.md (same or near-identical rule) - read before the run.
PRIOR = {"orb30": "partly: ORB 2nd side after a failed break (E2 2026-11-13), OR high/low roots (strategy tree), allday",
         "vwaprev": "yes: VWAP reversion on low-VIX days (E2 2026-11-13), VWAP/band fades (scalp-mean-reversion)",
         "vwaptrend": "yes: VWAP pullback with trend (ATLAS new members 2026-11-18)",
         "rsi2_5m": "yes: Connors RSI(2) (famous published 2026-11-17; daily) + RSI fades (scalp-mean-reversion)",
         "rsi2_15m": "yes: Connors RSI(2) (famous published 2026-11-17)",
         "donchian": "no (only turtle-soup fades were tested)", "nr7id": "yes: Crabel NR7 / NR4 / NR7-ID (famous published 2026-11-17)",
         "bbsqueeze": "partly: 15m Keltner squeeze (ATLAS members), lunch-box squeeze (new-strategy hunt)",
         "gapfill": "yes: plain gap fade loses (E2 2026-11-13; G1 gap fade paper lead only)",
         "ib_break": "no (IB only as a scalp-mean-reversion level)", "ib_fade": "partly: IB as a scalp-mean-reversion fade level",
         "ema921": "partly: ATLAS's own EMA member is an EMA trend strategy (overlap expected)",
         "keltner": "partly: 15m Keltner squeeze (ATLAS members)", "crabel": "partly: ATR-stretch fades (scalp-mean-reversion)",
         "eodmom": "yes: Gao intraday momentum (famous published 2026-11-17), last-half-hour (E2)",
         "tuesday": "partly: weekday as a strategy-tree condition"}


# ===================================================================================================== data + indicators
def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def wilder(x, n):
    return pd.Series(x).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


def rsi(c, n):
    d = np.diff(c, prepend=c[0])
    up, dn = wilder(np.maximum(d, 0), n), wilder(np.maximum(-d, 0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn == 0, 100.0, 100.0 - 100.0 / (1.0 + up / dn))


class Bars:
    def __init__(self, sym):
        d = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_5m.csv")).drop_duplicates("time").sort_values("time")
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        self.sym, self.pv, self.minstop = sym, SYM[sym]["pv"], SYM[sym]["minstop"]
        self.O, self.H, self.L, self.C, self.V = (d[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
        self.hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        self.cal = et.dt.date.astype(str).to_numpy()
        self.wd = et.dt.weekday.to_numpy()
        n = len(d)
        self.rth = {}
        starts = np.r_[0, np.flatnonzero(self.cal[1:] != self.cal[:-1]) + 1, n]
        for a, b in zip(starts[:-1], starts[1:]):
            hh = self.hm[a:b]
            r0, r1 = np.flatnonzero(hh == 570), np.flatnonzero(hh == 955)
            if len(r0) and len(r1) and r1[0] - r0[0] == 77:
                self.rth[self.cal[a]] = (a + r0[0], a + r1[0])
        self.days = sorted(self.rth)
        C, H, L = self.C, self.H, self.L
        tr = np.maximum(H - L, np.maximum(abs(H - np.r_[C[0], C[:-1]]), abs(L - np.r_[C[0], C[:-1]])))
        self.atr14, self.atr10, self.atr20 = wilder(tr, 14), wilder(tr, 10), wilder(tr, 20)
        self.ema9, self.ema20, self.ema21 = ema(C, 9), ema(C, 20), ema(C, 21)
        s = pd.Series(C)
        self.sma20, self.sd20 = s.rolling(20).mean().to_numpy(), s.rolling(20).std(ddof=0).to_numpy()
        self.sma200, self.sma5 = s.rolling(200).mean().to_numpy(), s.rolling(5).mean().to_numpy()
        self.rsi2 = rsi(C, 2)
        self.hh20 = pd.Series(H).shift(1).rolling(20).max().to_numpy()
        self.ll20 = pd.Series(L).shift(1).rolling(20).min().to_numpy()
        self.hh10 = pd.Series(H).shift(1).rolling(10).max().to_numpy()
        self.ll10 = pd.Series(L).shift(1).rolling(10).min().to_numpy()
        # 15m series (clock aligned): values at the 5m bar that closes each 15m bar, NaN elsewhere
        key = d.time.to_numpy(np.int64) // 900
        ends = np.r_[np.flatnonzero(key[1:] != key[:-1]), n - 1]
        c15 = C[ends]
        f = lambda arr: self._spread(ends, arr, n)  # noqa: E731
        self.c15 = f(c15)
        self.rsi2_15, self.sma200_15, self.sma5_15 = f(rsi(c15, 2)), f(pd.Series(c15).rolling(200).mean().to_numpy()), \
            f(pd.Series(c15).rolling(5).mean().to_numpy())
        h15 = np.maximum.reduceat(H, np.r_[0, ends[:-1] + 1])
        l15 = np.minimum.reduceat(L, np.r_[0, ends[:-1] + 1])
        tr15 = np.maximum(h15 - l15, np.maximum(abs(h15 - np.r_[c15[0], c15[:-1]]), abs(l15 - np.r_[c15[0], c15[:-1]])))
        self.atr14_15 = f(wilder(tr15, 14))
        # daily RTH bars
        self.dH, self.dL, self.dO, self.dC = {}, {}, {}, {}
        for dd, (i0, i1) in self.rth.items():
            self.dH[dd], self.dL[dd] = float(H[i0:i1].max()), float(L[i0:i1].min())
            self.dO[dd], self.dC[dd] = float(self.O[i0]), float(C[i1 - 1])     # 15:50 bar close = last RTH close we hold to

    @staticmethod
    def _spread(ends, arr, n):
        out = np.full(n, np.nan)
        out[ends] = arr
        return out


# ===================================================================================================== trade engine
def sim(b, e, d, entry, stop, tgt, xi, exit_fn=None, same_bar=True):
    """Entry at bar e at price `entry` (already slipped). same_bar=False for stop-entries (stop/target from bar e+1).
    exit_fn(j) on bar j's close -> out at O[j+1] - 1 tick. Returns (pnl-ready dict, exit index)."""
    if (entry - stop) * d < b.minstop:
        stop = entry - d * b.minstop
    risk = (entry - stop) * d
    q = min(MAXQ, int(RISK // (risk * b.pv + COMM)))
    if q < 1 or e >= xi:
        return None, e
    if tgt is not None and (tgt - entry) * d <= 0:
        return None, e
    mae, px, j = 0.0, None, None
    for jj in range(e if same_bar else e + 1, xi):
        lo, hi, op = b.L[jj], b.H[jj], b.O[jj]
        if d == 1 and lo <= stop:
            px, j = min(op, stop) - TICK, jj
            break
        if d == -1 and hi >= stop:
            px, j = max(op, stop) + TICK, jj
            break
        mae = min(mae, (lo - entry) if d == 1 else (entry - hi))
        if tgt is not None and ((d == 1 and hi > tgt) or (d == -1 and lo < tgt)):
            px, j = tgt, jj
            break
        if exit_fn is not None and jj + 1 < xi and exit_fn(jj, d):
            px, j = b.O[jj + 1] - d * TICK, jj + 1
            break
    if px is None:
        px, j = b.O[xi] - d * TICK, xi
    pts = (px - entry) * d
    pnl = q * (pts * b.pv - COMM)
    low = min(pnl, q * (mae * b.pv - COMM))
    return {"pnl": round(pnl, 2), "low": round(low, 2), "q": q, "risk": round(risk, 2), "dir": d}, j


def mkt(b, i):
    return i + 1


# ===================================================================================================== strategies
def s_orb30(b, dd, i0, i1):
    hi, lo = b.H[i0:i0 + 6].max(), b.L[i0:i0 + 6].min()
    mid = (hi + lo) / 2
    for j in range(i0 + 6, i0 + 30):                         # closes 10:00 .. 11:55
        d = 1 if b.C[j] > hi else -1 if b.C[j] < lo else 0
        if d:
            en = b.O[j + 1] + d * TICK
            r = (en - mid) * d
            t, _ = sim(b, j + 1, d, en, mid, en + d * 2 * max(r, b.minstop), i1)
            return [t] if t else []
    return []


def vwap_arrays(b, i0, i1):
    tp = (b.H[i0:i1] + b.L[i0:i1] + b.C[i0:i1]) / 3
    v = np.maximum(b.V[i0:i1], 1.0)
    cv = np.cumsum(v)
    vw = np.cumsum(tp * v) / cv
    var = np.maximum(np.cumsum(v * tp * tp) / cv - vw * vw, 0.0)
    return vw, np.sqrt(var)


def s_vwaprev(b, dd, i0, i1):
    vw, sd = vwap_arrays(b, i0, i1)
    out, j = [], i0 + 6
    while j <= i0 + 65 and len(out) < 2:                     # closes 10:00 .. 15:00
        k = j - i0
        d = -1 if b.C[j] > vw[k] + 2 * sd[k] else 1 if b.C[j] < vw[k] - 2 * sd[k] else 0
        if d and sd[k] > 0:
            en = b.O[j + 1] + d * TICK
            stop = vw[k] - d * 3 * sd[k] - d * TICK
            t, x = sim(b, j + 1, d, en, stop, vw[k], i1)
            if t:
                out.append(t)
                j = x
                continue
        j += 1
    return out


def s_vwaptrend(b, dd, i0, i1):
    vw, _ = vwap_arrays(b, i0, i1)
    out, j = [], i0 + 6
    while j <= i0 + 59 and len(out) < 2:                     # 10:00 .. 14:30
        k = j - i0
        up = b.C[j] > vw[k] and vw[k] > vw[k - 6] and b.L[j] <= vw[k]
        dn = b.C[j] < vw[k] and vw[k] < vw[k - 6] and b.H[j] >= vw[k]
        d = 1 if up else -1 if dn else 0
        if d:
            en = b.O[j + 1] + d * TICK
            stop = (b.L[j] if d == 1 else b.H[j]) - d * TICK
            r = max((en - stop) * d, b.minstop)
            t, x = sim(b, j + 1, d, en, stop, en + d * 2 * r, i1)
            if t:
                out.append(t)
                j = x
                continue
        j += 1
    return out


def _rsi2(b, i0, i1, rs, sma200, sma5, close, atr):
    out, j = [], i0 + 3
    ex = lambda jj, d: np.isfinite(sma5[jj]) and ((d == 1 and close[jj] > sma5[jj]) or (d == -1 and close[jj] < sma5[jj]))  # noqa: E731
    while j <= i0 + 65:                                      # 09:45 .. 15:00
        if np.isfinite(rs[j]) and np.isfinite(sma200[j]):
            d = 1 if (close[j] > sma200[j] and rs[j] < 10) else -1 if (close[j] < sma200[j] and rs[j] > 90) else 0
            if d:
                en = b.O[j + 1] + d * TICK
                t, x = sim(b, j + 1, d, en, en - d * 2 * atr[j], None, i1, exit_fn=ex)
                if t:
                    out.append(t)
                    j = x
                    continue
        j += 1
    return out


def s_rsi2_5m(b, dd, i0, i1):
    return _rsi2(b, i0, i1, b.rsi2, b.sma200, b.sma5, b.C, b.atr14)


def s_rsi2_15m(b, dd, i0, i1):
    return _rsi2(b, i0, i1, b.rsi2_15, b.sma200_15, b.sma5_15, b.c15, b.atr14_15)


def s_donchian(b, dd, i0, i1):
    out, j = [], i0 + 6
    ex = lambda jj, d: (d == 1 and b.C[jj] < b.ll10[jj]) or (d == -1 and b.C[jj] > b.hh10[jj])  # noqa: E731
    while j <= i0 + 65:
        d = 1 if b.C[j] > b.hh20[j] else -1 if b.C[j] < b.ll20[j] else 0
        if d:
            en = b.O[j + 1] + d * TICK
            stop = (b.ll10[j] if d == 1 else b.hh10[j]) - d * TICK
            t, x = sim(b, j + 1, d, en, stop, None, i1, exit_fn=ex)
            if t:
                out.append(t)
                j = x
                continue
        j += 1
    return out


def _prev_days(b, dd, k):
    ix = b.days.index(dd)
    return b.days[max(0, ix - k):ix] if ix >= k else None


def _stop_entry(b, i0, last, hi, lo):
    """First bar (i0..last) trading through hi (+1) or lo (-1): (bar, dir, fill)."""
    for j in range(i0, last + 1):
        up, dn = b.H[j] > hi, b.L[j] < lo
        if up and dn:
            return None                                       # both in one bar: ambiguous, skip
        if up:
            return j, 1, max(b.O[j], hi + TICK) + TICK
        if dn:
            return j, -1, min(b.O[j], lo - TICK) - TICK
    return None


def s_nr7id(b, dd, i0, i1):
    pv = _prev_days(b, dd, 7)
    if not pv:
        return []
    rg = [b.dH[x] - b.dL[x] for x in pv]
    y, y2 = pv[-1], pv[-2]
    if not (rg[-1] <= min(rg) and b.dH[y] <= b.dH[y2] and b.dL[y] >= b.dL[y2]):
        return []
    hit = _stop_entry(b, i0, i0 + 65, b.dH[y], b.dL[y])
    if not hit:
        return []
    j, d, en = hit
    t, _ = sim(b, j, d, en, (b.dH[y] + b.dL[y]) / 2, None, i1, same_bar=False)
    return [t] if t else []


def s_bbsqueeze(b, dd, i0, i1):
    run = 0
    for j in range(i0 - 30, i0 + 66):
        ub, lb = b.sma20[j] + 2 * b.sd20[j], b.sma20[j] - 2 * b.sd20[j]
        ku, kl = b.ema20[j] + 1.5 * b.atr20[j], b.ema20[j] - 1.5 * b.atr20[j]
        if j >= i0 + 6 and run >= 6:
            d = 1 if b.C[j] > ub else -1 if b.C[j] < lb else 0
            if d:
                en = b.O[j + 1] + d * TICK
                stop = b.sma20[j]
                r = max((en - stop) * d, b.minstop)
                t, _ = sim(b, j + 1, d, en, stop, en + d * 2 * r, i1)
                return [t] if t else []
        run = run + 1 if (ub < ku and lb > kl) else 0
    return []


def s_gapfill(b, dd, i0, i1):
    pv = _prev_days(b, dd, 1)
    if not pv:
        return []
    pc = b.dC[pv[-1]]
    o = b.O[i0]
    g = (o - pc) / pc
    if not (0.001 <= abs(g) <= 0.005):
        return []
    d = -1 if g > 0 else 1
    en = o + d * TICK
    t, _ = sim(b, i0, d, en, o - d * abs(o - pc), pc, i1)
    return [t] if t else []


def s_ib_break(b, dd, i0, i1):
    hi, lo = b.H[i0:i0 + 12].max(), b.L[i0:i0 + 12].min()
    w, mid = hi - lo, (hi + lo) / 2
    for j in range(i0 + 12, i0 + 54):                        # closes 10:30 .. 13:55
        d = 1 if b.C[j] > hi else -1 if b.C[j] < lo else 0
        if d:
            en = b.O[j + 1] + d * TICK
            t, _ = sim(b, j + 1, d, en, mid, (hi + w) if d == 1 else (lo - w), i1)
            return [t] if t else []
    return []


def s_ib_fade(b, dd, i0, i1):
    hi, lo = b.H[i0:i0 + 12].max(), b.L[i0:i0 + 12].min()
    mid = (hi + lo) / 2
    st = {1: None, -1: None}                                  # side probed: +1 above hi (fade short)
    for j in range(i0 + 12, i0 + 54):
        for s, lvl in ((1, hi), (-1, lo)):
            if st[s] == "done":
                continue
            beyond = b.H[j] > lvl if s == 1 else b.L[j] < lvl
            if st[s] is None:
                if not beyond:
                    continue
                st[s] = [j, b.H[j] if s == 1 else b.L[j]]
            else:
                st[s][1] = max(st[s][1], b.H[j]) if s == 1 else min(st[s][1], b.L[j])
            back = b.C[j] < lvl if s == 1 else b.C[j] > lvl
            if not back:
                if j - st[s][0] >= 2:
                    st[s] = "done"
                continue
            d = -s
            en = b.O[j + 1] + d * TICK
            t, _ = sim(b, j + 1, d, en, st[s][1] + s * TICK, mid, i1)
            return [t] if t else []
    return []


def s_ema921(b, dd, i0, i1):
    out, j = [], i0 + 3
    while j <= i0 + 65 and len(out) < 3:
        up = b.ema9[j] > b.ema21[j] and b.C[j] > b.ema21[j] and b.L[j] <= b.ema9[j] and b.C[j] > b.ema9[j]
        dn = b.ema9[j] < b.ema21[j] and b.C[j] < b.ema21[j] and b.H[j] >= b.ema9[j] and b.C[j] < b.ema9[j]
        d = 1 if up else -1 if dn else 0
        if d:
            en = b.O[j + 1] + d * TICK
            stop = (min(b.L[j], b.ema21[j]) if d == 1 else max(b.H[j], b.ema21[j])) - d * TICK
            r = max((en - stop) * d, b.minstop)
            t, x = sim(b, j + 1, d, en, stop, en + d * 2 * r, i1)
            if t:
                out.append(t)
                j = x
                continue
        j += 1
    return out


def s_keltner(b, dd, i0, i1):
    out, j = [], i0 + 6
    ex = lambda jj, d: (d == 1 and b.C[jj] < b.ema20[jj]) or (d == -1 and b.C[jj] > b.ema20[jj])  # noqa: E731
    while j <= i0 + 65:
        d = 1 if b.C[j] > b.ema20[j] + 2 * b.atr10[j] else -1 if b.C[j] < b.ema20[j] - 2 * b.atr10[j] else 0
        if d:
            en = b.O[j + 1] + d * TICK
            t, x = sim(b, j + 1, d, en, b.ema20[j], None, i1, exit_fn=ex)
            if t:
                out.append(t)
                j = x
                continue
        j += 1
    return out


def s_crabel(b, dd, i0, i1):
    pv = _prev_days(b, dd, 10)
    if not pv:
        return []
    st = float(np.mean([min(b.dH[x] - b.dO[x], b.dO[x] - b.dL[x]) for x in pv]))
    o = b.O[i0]
    if st <= 0:
        return []
    hit = _stop_entry(b, i0, i0 + 65, o + st, o - st)
    if not hit:
        return []
    j, d, en = hit
    t, _ = sim(b, j, d, en, o - d * st, None, i1, same_bar=False)
    return [t] if t else []


def s_eodmom(b, dd, i0, i1):
    j = i0 + 71                                               # 15:25 bar
    r = b.C[j] - b.O[i0]
    if r == 0:
        return []
    d = 1 if r > 0 else -1
    en = b.O[j + 1] + d * TICK
    t, _ = sim(b, j + 1, d, en, en - d * 2 * b.atr14[j], None, i1)
    return [t] if t else []


def s_tuesday(b, dd, i0, i1):
    if b.wd[i0] != 1:
        return []
    pv = _prev_days(b, dd, 15)
    if not pv:
        return []
    mon, fri = pv[-1], pv[-2]
    if dt.date.fromisoformat(mon).weekday() != 0 or dt.date.fromisoformat(fri).weekday() != 4:
        return []
    if not b.dC[mon] < b.dC[fri]:
        return []
    atr = float(np.mean([b.dH[x] - b.dL[x] for x in pv[-14:]]))
    en = b.O[i0] + TICK
    t, _ = sim(b, i0, 1, en, en - 0.5 * atr, None, i1)
    return [t] if t else []


STRATS = {k: globals()[f"s_{k}"] for k in NAMES}


def run(b, key):
    T = []
    fn = STRATS[key]
    for dd in b.days:
        i0, i1 = b.rth[dd]
        if i0 < 300:
            continue
        for t in fn(b, dd, i0, i1):
            t["day"] = dd
            T.append(t)
    return T


# ===================================================================================================== scoring
def span_days(b, sp):
    a, z = SPANS[sp]
    return [x for x in b.days if a <= x <= z]


def stats(b, T, sp):
    days = span_days(b, sp)
    if not days:
        return None
    ds = set(days)
    X = [t for t in T if t["day"] in ds]
    weeks = {dt.date.fromisoformat(x).isocalendar()[:2] for x in days}
    mo = len(days) / 21.0
    if not X:
        return {"n": 0, "tpw": 0.0, "win": None, "pf": None, "usd_mo": 0, "maxdd": 0, "net": 0, "p": 1.0}
    p = np.array([t["pnl"] for t in X])
    gl = -p[p < 0].sum()
    by = collections.defaultdict(float)
    for t in X:
        by[t["day"]] += t["pnl"]
    y = np.array([by.get(x, 0.0) for x in days])
    eq = np.cumsum(y)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    tstat = float(y.mean() / (y.std(ddof=1) / math.sqrt(len(y)))) if y.std() > 0 else 0.0
    pval = 0.5 * math.erfc(tstat / math.sqrt(2))              # one-sided: mean daily $ > 0
    return {"n": len(X), "tpw": round(len(X) / len(weeks), 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "usd_mo": round(float(p.sum()) / mo),
            "maxdd": round(dd), "net": round(float(p.sum())), "t": round(tstat, 2), "p": round(pval, 4),
            "stop_med": round(float(np.median([t["risk"] for t in X])), 1), "q_med": float(np.median([t["q"] for t in X]))}


def lit_atlas():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    lit = {x["date"]: (float(x["pnl"]), float(x.get("low") or 0.0), int(x.get("trades") or 0)) for x in d["days"]}
    a = json.load(open(os.path.join(ROOT, "research", "runs", "atlas_base.json"), encoding="utf-8"))
    atl = {x[0]: (float(x[1]), float(x[2]), int(x[3])) for x in a["days"]}
    return lit, atl


def corr_view(b, T, sp, lit, atl):
    days = [x for x in span_days(b, sp) if x <= "2026-10-16"]            # LIT / ATLAS backtests end 2026-10-16
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
    y = np.array([by.get(x, 0.0) for x in days])
    tdays = {t["day"] for t in T if t["day"] in set(days)}
    o = {}
    for nm, ref in (("lit", lit), ("atlas", atl)):
        x = np.array([ref.get(z, (0, 0, 0))[0] for z in days])
        o[f"corr_{nm}"] = round(float(np.corrcoef(x, y)[0, 1]), 3) if x.std() > 0 and y.std() > 0 else None
        o[f"overlap_{nm}"] = round(sum(1 for z in tdays if ref.get(z, (0, 0, 0))[2] > 0) / len(tdays), 2) if tdays else None
    return o


def eval_mc(b, sp, daily, low, target, trail, H=40):
    days = span_days(b, sp)
    res, meds = [], []
    for i in range(len(days)):
        bal, hi, out = 0.0, 0.0, None
        for nn, x in enumerate(days[i:i + H], 1):
            floor = min(hi - trail, 100.0)
            if bal + low.get(x, 0.0) <= floor:
                out = ("F", nn)
                break
            bal += daily.get(x, 0.0)
            if bal >= target:
                out = ("P", nn)
                break
            hi = max(hi, bal)
        if out is not None:
            res.append(out[0])
            if out[0] == "P":
                meds.append(out[1])
        elif i + H <= len(days):
            res.append("O")
    n = max(1, len(res))
    return {"pass40": round(100.0 * res.count("P") / n, 1), "fail40": round(100.0 * res.count("F") / n, 1),
            "med_days": int(np.median(meds)) if meds else None}


RAPID = {"25K": {"target": 1500.0, "trail": 1000.0, "book_x": 0.5, "addon_usd": 200.0},
         "50K": {"target": 3000.0, "trail": 2000.0, "book_x": 1.0, "addon_usd": 400.0}}


def rapid_view(b, T, lit, atl):
    out = {}
    for acct, R in RAPID.items():
        f = R["addon_usd"] / RISK
        base, blow = collections.defaultdict(float), collections.defaultdict(float)
        bt = collections.defaultdict(int)
        for ref in (lit, atl):
            for z, (p, lo, n) in ref.items():
                base[z] += p * R["book_x"]
                blow[z] += lo * R["book_x"]
                bt[z] += n
        add, alow = dict(base), dict(blow)
        at = collections.defaultdict(int)
        for t in T:
            add[t["day"]] = add.get(t["day"], 0.0) + t["pnl"] * f
            alow[t["day"]] = alow.get(t["day"], 0.0) + t["low"] * f
            at[t["day"]] += 1
        o = {}
        for sp in SPANS:
            days = [x for x in span_days(b, sp) if x <= "2026-10-16"]
            mo = len(days) / 21.0
            wk = len({dt.date.fromisoformat(x).isocalendar()[:2] for x in days}) or 1
            e0 = eval_mc(b, sp, base, blow, R["target"], R["trail"])
            e1 = eval_mc(b, sp, add, alow, R["target"], R["trail"])
            o[sp] = {"book_usd_mo": round(sum(base.get(x, 0) for x in days) / mo),
                     "with_usd_mo": round(sum(add.get(x, 0) for x in days) / mo),
                     "book_tpw": round(sum(bt.get(x, 0) for x in days) / wk, 2),
                     "with_tpw": round(sum(bt.get(x, 0) + at.get(x, 0) for x in days) / wk, 2),
                     "book_eval": e0, "with_eval": e1}
        out[acct] = o
    return out


def holm(ps):
    order = sorted(ps, key=lambda k: ps[k])
    m, adj, run_max = len(ps), {}, 0.0
    for r, k in enumerate(order):
        run_max = max(run_max, min(1.0, (m - r) * ps[k]))
        adj[k] = round(run_max, 4)
    return adj


def main():
    nq, es = Bars("NQ"), Bars("ES")
    lit, atl = lit_atlas()
    rows, detail = [], {}
    for k in NAMES:
        T = run(nq, k)
        S = {sp: stats(nq, T, sp) for sp in SPANS}
        Te = run(es, k)
        SE = {sp: stats(es, Te, sp) for sp in ("H1", "H2")}
        C = {sp: corr_view(nq, T, sp, lit, atl) for sp in SPANS}
        RV = rapid_view(nq, T, lit, atl)
        detail[k] = {"S": S, "ES": SE, "corr": C, "rapid": RV}
        rows.append(k)
        print(f"{k:10s} " + " | ".join(f"{sp} n{S[sp]['n']} {S[sp]['tpw']}/wk w{S[sp]['win']} PF {S[sp]['pf']} ${S[sp]['usd_mo']}/mo dd {S[sp]['maxdd']}"
                                       for sp in SPANS), flush=True)
    adj = holm({k: detail[k]["S"]["2021-25"]["p"] for k in rows})
    out = []
    for k in rows:
        S = detail[k]["S"]
        ok26 = all(S[sp]["n"] >= 5 and S[sp]["net"] > 0 and (S[sp]["pf"] or 0) >= 1.1 for sp in ("H1", "H2"))
        ok5 = S["2021-25"]["net"] > 0 and (S["2021-25"]["pf"] or 0) >= 1.1
        passed = ok26 and ok5 and adj[k] < 0.05
        r25, r50 = detail[k]["rapid"]["25K"], detail[k]["rapid"]["50K"]
        why = []
        for sp in SPANS:
            if not (S[sp]["net"] > 0 and (S[sp]["pf"] or 0) >= 1.1):
                why.append(f"{sp} PF {S[sp]['pf']} ${S[sp]['usd_mo']}/mo")
        if adj[k] >= 0.05:
            why.append(f"Holm p {adj[k]}")
        out.append({"id": f"popc_{k}", "name": NAMES[k], "family": FAMILY[k], "symbol": "NQ (MNQ)",
                    "spans": {sp: {f: S[sp][f] for f in ("tpw", "win", "pf", "usd_mo", "maxdd")} | {"n": S[sp]["n"]} for sp in SPANS},
                    "es_2026": {sp: {f: (detail[k]["ES"][sp] or {}).get(f) for f in ("n", "tpw", "pf", "usd_mo")} for sp in ("H1", "H2")},
                    "p_2021_25": S["2021-25"]["p"], "p_holm": adj[k],
                    "corr": {sp: detail[k]["corr"][sp] for sp in SPANS},
                    "rapid_addon": {a: {sp: {"usd_mo_delta": v[sp]["with_usd_mo"] - v[sp]["book_usd_mo"],
                                             "tpw": v[sp]["with_tpw"], "book_tpw": v[sp]["book_tpw"],
                                             "pass40": v[sp]["with_eval"]["pass40"], "book_pass40": v[sp]["book_eval"]["pass40"],
                                             "fail40": v[sp]["with_eval"]["fail40"], "book_fail40": v[sp]["book_eval"]["fail40"]}
                                        for sp in SPANS} for a, v in (("25K", r25), ("50K", r50))},
                    "already_tested": PRIOR[k],
                    "verdict": "passes" if passed else "rejected",
                    "why": "; ".join(why) if why else "holds all 3 spans + Holm"})
    meta = {"built": "2026-11-23", "tool": "tools/popular_classic.py", "data": "CME NQ1! 5m (TradingView) + ES1! 5m 2025-04+",
            "sizing": f"${RISK:.0f} risk a trade, MNQ $2/pt, 1-40 micros, ${COMM} RT, 1 tick slippage in/out",
            "spans": SPANS, "tests": len(rows), "correction": "Holm over 16 one-sided t-tests of mean daily $ (2021-25)",
            "pass_rule": "net > 0 and PF >= 1.1 in H1, H2 and 2021-25 (n >= 5 per 2026 half) and Holm p < 0.05",
            "rapid": RAPID, "paper_only": True}
    json.dump({"meta": meta, "rows": out}, open(OUT, "w", encoding="utf-8"), indent=1)
    json.dump(detail, open(OUTD, "w", encoding="utf-8"), indent=1, default=str)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
