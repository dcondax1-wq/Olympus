"""Trader brain: an explicit, causal discretion layer that reasons like an ICT/SMC futures trader.

Rules, weights and thresholds: research/lab/NARRATIVE_RULES.md (pre-registered; v1 = sections 1-4, v2 = section 7).
Model-agnostic: works on setups from any model (engine, ATM, Silver Bullet, Mech/IFVG, ICT2022, Continuation, ...).

PUBLIC API (plain dicts and pandas frames only; nothing engine-internal is required)
  bars5 / es5: DataFrames with columns time (unix open, s), open, high, low, close[, volume][, day, mod] - e.g.
      tools.strategy_lab.bars("NQ", "5m", ...) / bars("ES", "5m", ...). Give the brain some history before the first
      setup (about 60 trading days for the daily structure). es5 is optional (SMT / relative strength become 0).

  narrative(bars5, t, es5=None) -> dict
      t = decision time (unix s). Only bars with open + 300 <= t are read. Keys: bias ('long'|'short'|'neutral'),
      bias_dir (+1/-1/0), conviction (0..1), draw ({price, label, nice, side, dist_pts, within_reach} or None),
      day_type ('expansion'|'normal'|'consolidation'), po3, htf, overnight, news, adr10, story (pre-market story +
      intraday update), premarket_story, update, bias_failed, draw_hit, today_range, remaining, reach_now.

  assess(setup, nar=None, bars5=None, es5=None, version="v1", trust=None, cuts=None) -> dict
      setup (plain dict): entry_t (decision time, unix s: the signal close or the fill-bar open), dir (+1 long /
          -1 short), entry, stop; optional: sweep_level, sweep_label (or label; pool ids like 'PDL', 'ASIA-L',
          'ATM-H', see NICE), sweep_t (unix open of the raid-extreme bar), trigger_tf ('5m', '15m', ...), targets
          (list of prices, last = final), ifvg_pts, bars_to_v, model (free text, logged only).
          Missing targets -> the nearest untaken Tier-A pool >= 1R in the trade direction, else entry + 2R.
          Missing sweep_t -> the most extreme bar of the last 36 closed bars.
      nar: the narrative() dict at setup['entry_t'] (computed if None).
      Returns decision ('TAKE'|'SKIP'), grade ('A'|'B'|'C'|'SKIP'), score, size_tier, risk_usd (A $700 max 1 NQ,
      B $350, C $175), target_plan {plan: 'partial_runner'|'first_draw', tp1, final, text}, manage_mode
      ('hold'|'normal'|'quick'), veto, elements {id: {score, why}}, facts, thoughts (2-4 sentences).
      version: 'v1' (default) or 'v2' (call enable_v2() first). trust: {element id: multiplier} (experience layer).

  manage(position, bars_since_entry, nar=None) -> {"action": 'hold'|'exit'|'stop', "stop": price, "reason": str}
      position: dir, entry, stop; optional risk (default |entry - stop|), tp1, final, partial_done, be_done,
          mode ('hold'|'normal'|'quick', from assess), atr (ATR5 at entry; default 1/40 of the price... pass it).
      bars_since_entry: dict or DataFrame with open/high/low/close/mod of the bars from the fill bar to the last
          closed bar. Call once per closed bar; apply 'stop' (move the stop) or 'exit' (exit at that close).

  simulate(bars5, setup, verdict, nar, fill_t=None, entry_fill=None) -> {legs, log, r, mfe_r}
      Replays manage() bar by bar from the fill bar (research and thought logs).
  infer_setup(bars5, entry_t, dir, risk_pts, rr_plan=None, trigger="") -> setup dict for an engine trade.
  register(eid, fn, versions, label) -> plug in a new judgment element; enable_v2() registers the v2 heuristics.

Causal by construction: at decision time t only 5m bars whose close (open + 300 s) is <= t are read; HTF bars (1H clock,
4H anchored 18:00 ET, CME day, ISO week) are built from those closed 5m bars and used only once their last 5m bar has
closed. Judgment elements live in the ELEMENTS registry so new heuristics plug in as new entries (VERSIONS lists which
elements each version uses) and the experience layer can re-weigh each one (`trust`).
"""
from __future__ import annotations

import collections
import datetime as dt
import math
import os

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
TICK = 0.25
BAR = 300

# ------------------------------------------------------------------------------------------------ fixed parameters (v1)
BIAS_W = {"daily": 1.0, "h4": 0.75, "h1": 0.5, "candle": 1.0, "clv": 0.5, "raid": 0.5, "weekly": 0.25}
BIAS_CUT = 1.0
CONV_DIV = 3.0
GRADE_CUT = {"A": 3.0, "B": 0.5, "C": -2.0}          # S >= A -> A; >= B -> B; >= C -> C; below -> SKIP
# per-version default cutoffs: v2's were set by the outcome-blind calibration rule on the 2026 dev bed (P70 / P25 / P5)
VERSION_CUTS = {"v1": GRADE_CUT, "v2": {"A": 0.05, "B": -2.5, "C": -4.0}}
TIER_RISK = {"A": 700.0, "B": 350.0, "C": 175.0, "SKIP": 0.0}
TIER_A_MAX_QTY = 10                                  # 1 NQ = 10 MNQ
SIG = {"PWH": 5, "PWL": 5, "PDH": 4, "PDL": 4, "RTH-H": 3.5, "RTH-L": 3.5, "D1SW-H": 3.5, "D1SW-L": 3.5,
       "LON-H": 3, "LON-L": 3, "ASIA-H": 3, "ASIA-L": 3, "ATM-H": 2.5, "ATM-L": 2.5, "ON-H": 2.5, "ON-L": 2.5,
       "H4SW-H": 2.5, "H4SW-L": 2.5, "EQH": 2.2, "EQL": 2.2, "H1SW-H": 2, "H1SW-L": 2, "M5SW-H": 1, "M5SW-L": 1}
NICE = {"PWH": "prior-week high", "PWL": "prior-week low", "PDH": "prior-day high", "PDL": "prior-day low",
        "RTH-H": "prior RTH high", "RTH-L": "prior RTH low", "D1SW-H": "daily swing high", "D1SW-L": "daily swing low",
        "LON-H": "London high", "LON-L": "London low", "ASIA-H": "Asia high", "ASIA-L": "Asia low",
        "ATM-H": "ATM high (07:00-09:25)", "ATM-L": "ATM low (07:00-09:25)", "ON-H": "overnight high", "ON-L": "overnight low",
        "H4SW-H": "4H swing high", "H4SW-L": "4H swing low", "EQH": "1H equal highs", "EQL": "1H equal lows",
        "H1SW-H": "1H swing high", "H1SW-L": "1H swing low", "M5SW-H": "5m swing high", "M5SW-L": "5m swing low"}
TIER_A = {"PWH", "PWL", "PDH", "PDL", "RTH-H", "RTH-L", "D1SW-H", "D1SW-L", "LON-H", "LON-L", "ASIA-H", "ASIA-L",
          "ATM-H", "ATM-L", "ON-H", "ON-L", "H4SW-H", "H4SW-L"}


def _px(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{x:,.2f}"


def _hm(mod):
    return f"{int(mod) // 60:02d}:{int(mod) % 60:02d}"


def _wilder(h, l, c, n=14):
    if len(h) == 0:
        return np.zeros(0)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.empty(len(tr))
    a = tr[0]
    for i, x in enumerate(tr):
        a = x if i == 0 else a + (x - a) / n
        out[i] = a
    return out


# ------------------------------------------------------------------------------------------------ news
_NEWS = None


def news_on(day):
    """[(minute ET, event, impact)] for a trading-day label (data/news/events.csv)."""
    global _NEWS
    if _NEWS is None:
        _NEWS = collections.defaultdict(list)
        p = os.path.join(ROOT, "data", "news", "events.csv")
        if os.path.exists(p):
            for r in pd.read_csv(p).itertuples():
                try:
                    hh, mm = str(r.time_et).split(":")[:2]
                    _NEWS[str(r.date)].append((int(hh) * 60 + int(mm), str(r.event), str(r.impact)))
                except Exception:
                    pass
    return _NEWS.get(day, [])


# ------------------------------------------------------------------------------------------------ HTF series
class _TF:
    """Closed higher-timeframe bars built from 5m groups, plus structure (last BOS) and k=1 swings."""

    def __init__(self, C, gid, period_end=None):
        starts = np.r_[0, np.flatnonzero(np.diff(gid)) + 1]
        ends = np.r_[starts[1:], len(gid)]
        self.first, self.last = starts, ends - 1
        self.O = C.o[starts]
        self.C = C.c[ends - 1]
        self.H = np.maximum.reduceat(C.h, starts)
        self.L = np.minimum.reduceat(C.l, starts)
        # an HTF bar is usable only once its clock period has ended (same rule live, where the frame ends at the last
        # closed 5m bar, and in research on the full history)
        self.close_t = C.t[ends - 1] + BAR
        if period_end is not None:
            self.close_t = np.maximum(self.close_t, np.asarray(period_end(starts), np.int64))
        self.day = C.di[starts]
        self.atr = _wilder(self.H, self.L, self.C)
        n = len(starts)
        self.dir = np.zeros(n, int)
        self.bos_t = np.zeros(n, np.int64)
        sh = sl = None
        shu = slu = True
        d, bt = 0, 0
        H, L, Cc = self.H, self.L, self.C
        for j in range(n):
            if j >= 2 and H[j - 1] > H[j - 2] and H[j - 1] >= H[j]:
                sh, shu = H[j - 1], False
            if j >= 2 and L[j - 1] < L[j - 2] and L[j - 1] <= L[j]:
                sl, slu = L[j - 1], False
            if sh is not None and not shu and Cc[j] > sh:
                d, shu, bt = 1, True, int(self.close_t[j])
            if sl is not None and not slu and Cc[j] < sl:
                d, slu, bt = -1, True, int(self.close_t[j])
            self.dir[j], self.bos_t[j] = d, bt
        self.swh = np.zeros(n, bool)
        self.swl = np.zeros(n, bool)
        if n >= 3:
            self.swh[1:-1] = (H[1:-1] > H[:-2]) & (H[1:-1] >= H[2:])
            self.swl[1:-1] = (L[1:-1] < L[:-2]) & (L[1:-1] <= L[2:])

    def at(self, T):
        """Index of the last bar closed by T (-1 if none)."""
        return int(np.searchsorted(self.close_t, T, side="right")) - 1


class Ctx:
    """Everything precomputed once per bar frame (cached by frame identity)."""

    def __init__(self, df):
        self.t = df["time"].to_numpy(np.int64)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.v = df["volume"].to_numpy(float) if "volume" in df else np.ones(len(self.c))
        if "mod" in df and "day" in df:
            self.mod = df["mod"].to_numpy(int)
            dl = df["day"].to_numpy()
        else:
            et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
            self.mod = (et.dt.hour * 60 + et.dt.minute).to_numpy(int)
            dl = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d").to_numpy()
        days, di = np.unique(dl, return_inverse=True)
        self.days, self.di = [str(x) for x in days], di
        n = len(days)
        idx = np.arange(n)
        self.ds = np.searchsorted(di, idx, "left")
        self.de = np.searchsorted(di, idx, "right")
        self.atr5 = _wilder(self.h, self.l, self.c)
        self.t930 = np.array([int(dt.datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), 9, 30, tzinfo=ET).timestamp())
                              for d in self.days], np.int64)
        tt, mm = self.t, self.mod
        self.D = _TF(self, di, lambda st: self.t930[di[st]] + int(7.5 * 3600))                 # CME day ends 17:00 ET
        self.H1 = _TF(self, self.t // 3600, lambda st: (tt[st] // 3600 + 1) * 3600)
        self.M15 = _TF(self, self.t // 900, lambda st: (tt[st] // 900 + 1) * 900)
        self.H4 = _TF(self, di * 6 + ((self.mod - 1080) % 1440) // 240,
                      lambda st: tt[st] - ((mm[st] - 1080) % 240) * 60 + 4 * 3600)               # 18:00-anchored 4H blocks
        rng = self.D.H - self.D.L
        cs = np.r_[0.0, np.cumsum(rng)]
        self.adr10 = np.array([(cs[k] - cs[max(0, k - 10)]) / max(1, k - max(0, k - 10)) if k > 0 else rng[0]
                               for k in range(n)])
        m = self.mod
        self.sess = {}
        for nm, mask, end_off in (("ASIA", (m >= 1200) & (m < 1440), -9.5 * 3600), ("LON", (m >= 120) & (m < 300), -4.5 * 3600),
                                  ("ATM", (m >= 420) & (m < 570), 0), ("ON", (m >= 1080) | (m < 570), 0),
                                  ("RTH", (m >= 570) & (m < 960), 6.5 * 3600)):
            H = np.full(n, np.nan)
            L = np.full(n, np.nan)
            last = np.full(n, -1)
            ii = np.flatnonzero(mask)
            if len(ii):
                dd = di[ii]
                Hm = np.full(n, -np.inf)
                Lm = np.full(n, np.inf)
                np.maximum.at(Hm, dd, self.h[ii])
                np.minimum.at(Lm, dd, self.l[ii])
                np.maximum.at(last, dd, ii)
                ok = np.isfinite(Hm)
                H[ok], L[ok] = Hm[ok], Lm[ok]
            self.sess[nm] = (H, L, last, (self.t930 + int(end_off)).astype(np.int64))
        # ISO weeks of the day labels
        wk = [dt.date.fromisoformat(d).isocalendar()[:2] for d in self.days]
        wid, cur, prev = np.zeros(n, int), -1, None
        for k, w in enumerate(wk):
            if w != prev:
                cur, prev = cur + 1, w
            wid[k] = cur
        self.wid = wid
        self.wstart = np.searchsorted(wid, np.arange(cur + 1), "left")
        self.WH = np.array([self.D.H[self.wstart[w]:(self.wstart[w + 1] if w + 1 <= cur else n)].max() for w in range(cur + 1)])
        self.WL = np.array([self.D.L[self.wstart[w]:(self.wstart[w + 1] if w + 1 <= cur else n)].min() for w in range(cur + 1)])
        # 5m swings, k=2 (confirmed at i+2)
        h, l = self.h, self.l
        N = len(h)
        self.sh5 = np.zeros(N, bool)
        self.sl5 = np.zeros(N, bool)
        if N > 5:
            self.sh5[2:-2] = (h[2:-2] > np.maximum(h[:-4], h[1:-3])) & (h[2:-2] >= np.maximum(h[3:-1], h[4:]))
            self.sl5[2:-2] = (l[2:-2] < np.minimum(l[:-4], l[1:-3])) & (l[2:-2] <= np.minimum(l[3:-1], l[4:]))
        self.fvg = {"5m": self._fvgs_5m(), "15m": self._fvgs_tf(self.M15), "1h": self._fvgs_tf(self.H1)}
        self._pm = {}

    @staticmethod
    def _pack(i3, ct, d, bot, top):
        o = np.argsort(i3, kind="stable")
        return {"i3": np.asarray(i3, np.int64)[o], "ct": np.asarray(ct, np.int64)[o], "d": np.asarray(d, int)[o],
                "bot": np.asarray(bot, float)[o], "top": np.asarray(top, float)[o]}

    def _fvgs_5m(self):
        h, l, a = self.h, self.l, self.atr5
        mn = np.maximum(TICK, 0.1 * a[2:])
        bear = (l[:-2] - h[2:]) >= mn
        bull = ~bear & ((l[2:] - h[:-2]) >= mn)
        ib, iu = np.flatnonzero(bear) + 2, np.flatnonzero(bull) + 2
        return self._pack(np.r_[ib, iu], np.r_[self.t[ib], self.t[iu]] + BAR, np.r_[-np.ones(len(ib)), np.ones(len(iu))],
                          np.r_[h[ib], h[iu - 2]], np.r_[l[ib - 2], l[iu]])

    def _fvgs_tf(self, T):
        H, L = T.H, T.L
        bear = (L[:-2] - H[2:]) >= TICK
        bull = ~bear & ((L[2:] - H[:-2]) >= TICK)
        jb, ju = np.flatnonzero(bear) + 2, np.flatnonzero(bull) + 2
        return self._pack(np.r_[T.last[jb], T.last[ju]], np.r_[T.close_t[jb], T.close_t[ju]],
                          np.r_[-np.ones(len(jb)), np.ones(len(ju))], np.r_[H[jb], H[ju - 2]], np.r_[L[jb - 2], L[ju]])

    def idx_at(self, t):
        """Last 5m bar whose close is <= t."""
        return int(np.searchsorted(self.t, int(t) - BAR, side="right")) - 1

    def taken(self, side, px, a, i):
        """Was a pool at px (side +1 = buy-side high, -1 = sell-side low) traded through on bars a..i?"""
        if a > i:
            return False
        if side > 0:
            return bool(self.h[a:i + 1].max() >= px + TICK)
        return bool(self.l[a:i + 1].min() <= px - TICK)


_CTX = {}


def ctx(df):
    if df is None:
        return None
    key = (id(df), len(df), int(df["time"].iloc[0]), int(df["time"].iloc[-1]))
    c = _CTX.get(key)
    if c is None:
        if len(_CTX) > 6:
            _CTX.clear()
        c = _CTX[key] = Ctx(df)
    return c


# ------------------------------------------------------------------------------------------------ liquidity inventory
def pools(C, i_now, t_now=None):
    """Every ERL pool known at the close of bar i_now, with taken/untaken status at that close."""
    k = int(C.di[i_now])
    t_now = int(C.t[i_now]) + BAR if t_now is None else int(t_now)
    out = []

    def add(name, side, px, avail, tier="A"):
        if px is None or not np.isfinite(px) or avail is None:
            return
        avail = int(avail)
        if avail > i_now + 1:
            return
        out.append({"name": name, "side": side, "price": float(px), "tier": tier, "avail": avail,
                    "taken": C.taken(side, px, avail, i_now), "sig": SIG.get(name, 1)})

    if k >= 1:
        add("PDH", 1, C.D.H[k - 1], C.ds[k])
        add("PDL", -1, C.D.L[k - 1], C.ds[k])
        rH, rL, rlast, _ = C.sess["RTH"]
        if rlast[k - 1] >= 0:
            add("RTH-H", 1, rH[k - 1], rlast[k - 1] + 1)
            add("RTH-L", -1, rL[k - 1], rlast[k - 1] + 1)
    w = C.wid[k]
    if w >= 1:
        a = C.ds[C.wstart[w]]
        add("PWH", 1, C.WH[w - 1], a)
        add("PWL", -1, C.WL[w - 1], a)
    for nm in ("ASIA", "LON", "ATM", "ON"):
        H, L, last, endt = C.sess[nm]
        if last[k] >= 0 and t_now >= endt[k] and last[k] <= i_now:
            add(nm + "-H", 1, H[k], last[k] + 1)
            add(nm + "-L", -1, L[k], last[k] + 1)
    # 4H swings (last 10 days) and daily swings (last 60 days), k=1
    T = C.H4
    j1 = T.at(t_now)
    for j in range(max(1, j1 - 70), j1):
        if T.day[j] < k - 10:
            continue
        if T.swh[j] and j + 1 <= j1:
            add("H4SW-H", 1, T.H[j], T.last[j + 1] + 1)
        if T.swl[j] and j + 1 <= j1:
            add("H4SW-L", -1, T.L[j], T.last[j + 1] + 1)
    D = C.D
    for j in range(max(1, k - 60), k - 1):
        if D.swh[j]:
            add("D1SW-H", 1, D.H[j], C.de[j + 1])
        if D.swl[j]:
            add("D1SW-L", -1, D.L[j], C.de[j + 1])
    # 1H swings (Tier B) and 1H equal highs/lows (last 5 days)
    T = C.H1
    j1 = T.at(t_now)
    hs, ls = [], []
    for j in range(max(1, j1 - 130), j1):
        if T.day[j] < k - 5:
            continue
        if T.swh[j]:
            hs.append(j)
            add("H1SW-H", 1, T.H[j], T.last[j + 1] + 1, "B")
        if T.swl[j]:
            ls.append(j)
            add("H1SW-L", -1, T.L[j], T.last[j + 1] + 1, "B")
    for lst, side, arr, nm in ((hs, 1, T.H, "EQH"), (ls, -1, T.L, "EQL")):
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                a, b = lst[x], lst[y]
                tol = max(2 * TICK, 0.1 * T.atr[b])
                if b - a >= 3 and abs(arr[a] - arr[b]) <= tol:
                    lvl = max(arr[a], arr[b]) if side > 0 else min(arr[a], arr[b])
                    add(nm, side, lvl, T.last[b + 1] + 1, "B")
    return out


def live_gaps(C, i_now, gdir, kinds=("5m", "15m", "1h"), days_back=None):
    """Live (CE not yet touched) FVGs of direction gdir (-1 bearish = above price, +1 bullish = below) at bar i_now."""
    t_now = int(C.t[i_now]) + BAR
    k = int(C.di[i_now])
    lim = {"5m": 1, "15m": 5, "1h": 10} if days_back is None else days_back
    out = []
    for tf in kinds:
        F = C.fvg[tf]
        a0 = int(np.searchsorted(F["i3"], C.ds[max(0, k - lim[tf])]))
        b0 = int(np.searchsorted(F["i3"], i_now, side="right"))
        for q in range(a0, b0):
            i3, ct, d, bot, top = int(F["i3"][q]), int(F["ct"][q]), int(F["d"][q]), float(F["bot"][q]), float(F["top"][q])
            if d != gdir or ct > t_now:
                continue
            ce = 0.5 * (bot + top)
            a = i3 + 1
            if a <= i_now:
                if gdir < 0 and C.h[a:i_now + 1].max() >= ce:
                    continue
                if gdir > 0 and C.l[a:i_now + 1].min() <= ce:
                    continue
            out.append({"tf": tf, "bottom": float(bot), "top": float(top), "ce": float(ce), "created_t": ct})
    return out


def swings5(C, i_now, side, days=1):
    """Untaken 5m k=2 swing highs (side +1) / lows (-1) confirmed today or in the last `days` days."""
    k = int(C.di[i_now])
    a = C.ds[max(0, k - days)]
    arr = C.sh5 if side > 0 else C.sl5
    out = []
    for j in np.flatnonzero(arr[a:max(a, i_now - 1)]) + a:
        px = C.h[j] if side > 0 else C.l[j]
        if not C.taken(side, px, j + 3, i_now):
            out.append(float(px))
    return out


# ------------------------------------------------------------------------------------------------ narrative
def _candle(C, k):
    """TTrades-style daily candle closure of day k-1 vs day k-2: (score, text)."""
    if k < 2:
        return 0.0, "not enough history", "n/a"
    H, L, Cl, O = C.D.H, C.D.L, C.D.C, C.D.O
    p, pp = k - 1, k - 2
    if H[p] <= H[pp] and L[p] >= L[pp]:
        return 0.0, "an inside day (compression)", "inside"
    if H[p] > H[pp] and L[p] < L[pp]:
        clv = (Cl[p] - L[p]) / max(H[p] - L[p], TICK)
        s = 0.5 if clv >= 0.5 else -0.5
        return s, f"an outside day that closed in its {'upper' if s > 0 else 'lower'} half", "outside"
    if Cl[p] > H[pp]:
        return 1.0, "a bullish close above the day-before high", "bull_close"
    if Cl[p] < L[pp]:
        return -1.0, "a bearish close below the day-before low", "bear_close"
    if L[p] < L[pp] and Cl[p] > L[pp]:
        return 1.0, "a sweep of the day-before low that closed back inside (bullish)", "low_swept_reclaim"
    if H[p] > H[pp] and Cl[p] < H[pp]:
        return -1.0, "a sweep of the day-before high that closed back inside (bearish)", "high_swept_reject"
    return 0.0, "an ordinary day inside the prior range", "plain"


def _premarket(C, k, T0):
    key = (k, T0)
    if key in C._pm:
        return C._pm[key]
    i0 = C.idx_at(T0)
    px = float(C.c[i0])
    adr = float(C.adr10[k])
    day = C.days[k]
    # --- HTF structure
    jd, j4, j1 = C.D.at(T0), C.H4.at(T0), C.H1.at(T0)
    dD = int(C.D.dir[jd]) if jd >= 0 else 0
    d4 = int(C.H4.dir[j4]) if j4 >= 0 else 0
    d1 = int(C.H1.dir[j1]) if j1 >= 0 else 0
    cs, ctext, ctype = _candle(C, k)
    if k >= 1:
        PH, PL, PC = C.D.H[k - 1], C.D.L[k - 1], C.D.C[k - 1]
        clv = float((PC - PL) / max(PH - PL, TICK))
    else:
        PH = PL = PC = np.nan
        clv = 0.5
    clv_s = 0.5 if clv >= 0.75 else (-0.5 if clv <= 0.25 else 0.0)
    # --- overnight raids (Asia / London levels taken by 09:30 and reclaimed)
    on = {}
    for nm in ("ASIA", "LON", "ATM"):
        H, L, last, endt = C.sess[nm]
        if last[k] >= 0 and T0 >= endt[k] and last[k] <= i0:
            on[nm] = {"H": float(H[k]), "L": float(L[k]), "H_taken": C.taken(1, H[k], last[k] + 1, i0),
                      "L_taken": C.taken(-1, L[k], last[k] + 1, i0)}
    lows_raided = [nm for nm in ("ASIA", "LON") if nm in on and on[nm]["L_taken"] and px > on[nm]["L"]]
    highs_raided = [nm for nm in ("ASIA", "LON") if nm in on and on[nm]["H_taken"] and px < on[nm]["H"]]
    any_low = any(on[nm]["L_taken"] for nm in ("ASIA", "LON") if nm in on)
    any_high = any(on[nm]["H_taken"] for nm in ("ASIA", "LON") if nm in on)
    raid = 0.5 if (lows_raided and not any_high) else (-0.5 if (highs_raided and not any_low) else 0.0)
    # --- dealing ranges
    w = C.wid[k]
    a_today = C.ds[k]
    tH = float(C.h[a_today:i0 + 1].max())
    tL = float(C.l[a_today:i0 + 1].min())
    if w >= 1:
        wk_hi = max(C.WH[w - 1], tH, C.D.H[C.wstart[w]:k].max() if k > C.wstart[w] else tH)
        wk_lo = min(C.WL[w - 1], tL, C.D.L[C.wstart[w]:k].min() if k > C.wstart[w] else tL)
        wpos = float((px - wk_lo) / max(wk_hi - wk_lo, TICK))
    else:
        wpos = 0.5
    wk_s = -0.25 if wpos > 0.85 else (0.25 if wpos < 0.15 else 0.0)
    dr_hi = max(PH, tH) if np.isfinite(PH) else tH
    dr_lo = min(PL, tL) if np.isfinite(PL) else tL
    dpos = float((px - dr_lo) / max(dr_hi - dr_lo, TICK))
    comp = {"daily": BIAS_W["daily"] * dD, "h4": BIAS_W["h4"] * d4, "h1": BIAS_W["h1"] * d1,
            "candle": BIAS_W["candle"] * cs, "clv": clv_s, "raid": raid, "weekly": wk_s}
    score = float(sum(comp.values()))
    bias = "long" if score >= BIAS_CUT else ("short" if score <= -BIAS_CUT else "neutral")
    conviction = round(min(1.0, abs(score) / CONV_DIV), 2)
    bdir = 1 if bias == "long" else (-1 if bias == "short" else 0)
    # --- PO3 expectation (18:00 daily open)
    dopen = float(C.o[a_today])
    if bdir == 0:
        po3 = "two-sided: no bias, wait for a raid of one side and a shift"
    else:
        below = (px - dopen) * bdir < 0
        manip_done = ((tL < dopen) if bdir > 0 else (tH > dopen))
        if below:
            po3 = ("manipulation phase: price is " + ("below" if bdir > 0 else "above") + f" the 18:00 open ({_px(dopen)}); "
                   "expect a " + ("low" if bdir > 0 else "high") + " to form first (Judas), then expansion " + ("up" if bdir > 0 else "down"))
        elif manip_done:
            po3 = ("manipulation done: the overnight already traded " + ("under" if bdir > 0 else "over") +
                   f" the open ({_px(dopen)}); expansion phase: " + ("buy dips" if bdir > 0 else "sell rallies"))
        else:
            po3 = (f"no manipulation yet: price is on the bias side of the open ({_px(dopen)}) without a " +
                   ("dip under it" if bdir > 0 else "push over it") + "; watch for one in the first hour")
    # --- pools / draws
    P = pools(C, i0, T0)
    today_rng = tH - tL
    reach = max(0.5 * adr, adr - today_rng)
    draw = None

    def pick(side):
        cand = [p for p in P if p["side"] == side and not p["taken"] and (p["price"] - px) * side >= 0.15 * adr]
        a_ = sorted([p for p in cand if p["name"] in TIER_A], key=lambda p: (p["price"] - px) * side)
        if not a_:
            return None, None
        first = a_[0]
        if (first["price"] - px) * side <= reach:
            return first, None
        inr = sorted([p for p in cand if (p["price"] - px) * side <= reach], key=lambda p: (p["price"] - px) * side)
        return (inr[0] if inr else first), first

    beyond = None
    if bdir != 0:
        draw, beyond = pick(bdir)
    else:
        up, _ = pick(1)
        dn, _ = pick(-1)
        cands = [x for x in (up, dn) if x is not None]
        if cands:
            draw = min(cands, key=lambda p: abs(p["price"] - px))
    dd = None
    if draw is not None:
        dist = abs(draw["price"] - px)
        dd = {"price": draw["price"], "label": draw["name"], "nice": NICE.get(draw["name"], draw["name"]), "side": draw["side"],
              "dist_pts": round(dist, 2), "dist_adr": round(dist / max(adr, TICK), 2), "within_reach": bool(dist <= reach),
              "two_sided": bdir == 0}
    # --- day type
    ev = news_on(day)
    cpi_nfp = any(("CPI" in e or "Non-Farm" in e) and imp == "high" for _, e, imp in ev)
    fomc = any("FOMC" in e and imp == "high" for _, e, imp in ev)
    high_ev = [(m, e) for m, e, imp in ev if imp == "high"]
    inside = ctype == "inside"
    nr4 = k >= 4 and (C.D.H[k - 1] - C.D.L[k - 1]) <= min(C.D.H[k - 4:k - 1] - C.D.L[k - 4:k - 1])
    rthc = None
    rH, rL, rlast, _ = C.sess["RTH"]
    if k >= 1 and rlast[k - 1] >= 0:
        rthc = float(C.c[rlast[k - 1]])
    gap = (px - rthc) if rthc is not None else 0.0
    on_rng = today_rng
    big_prev = k >= 1 and (C.D.H[k - 1] - C.D.L[k - 1]) >= 1.3 * adr
    dts = (1.0 if (inside or nr4) else 0.0) + (1.0 if abs(gap) >= 0.25 * adr else 0.0) + (0.5 if cpi_nfp else 0.0) \
        - (1.0 if on_rng >= 0.6 * adr else 0.0) - (1.0 if fomc else 0.0) - (0.5 if big_prev else 0.0)
    day_type = "expansion" if dts >= 1.0 else ("consolidation" if dts <= -1.0 else "normal")
    ndog = None
    if k >= 1:
        ndog = float(C.o[a_today] - C.c[C.de[k - 1] - 1])
    res = {"day": day, "t": int(T0), "price": px, "adr10": round(adr, 2), "bias": bias, "bias_dir": bdir,
           "conviction": conviction, "bias_score": round(score, 2), "bias_parts": comp, "draw": dd,
           "draw_beyond": ({"price": beyond["price"], "label": beyond["name"]} if beyond else None),
           "day_type": day_type, "day_type_score": dts, "po3": po3, "daily_open": dopen,
           "htf": {"daily_dir": dD, "h4_dir": d4, "h1_dir": d1, "weekly_pos": round(wpos, 2), "daily_pos": round(dpos, 2),
                   "prev_close_loc": round(clv, 2), "prev_candle": ctype, "prev_candle_text": ctext,
                   "daily_bos_t": int(C.D.bos_t[jd]) if jd >= 0 else 0},
           "overnight": {"sessions": on, "lows_raided": lows_raided, "highs_raided": highs_raided, "ndog": ndog,
                         "gap_vs_rth_close": round(gap, 2), "on_range": round(on_rng, 2), "today_hi": tH, "today_lo": tL},
           "news": {"events": high_ev, "cpi_nfp": cpi_nfp, "fomc": fomc}, "inside": inside, "nr4": bool(nr4),
           "reach": round(reach, 2), "pools": P}
    res["bias_why"] = _bias_why(res)
    res["bias_line"] = _bias_line(res)
    res["story"] = _story(res)
    C._pm[key] = res
    return res


_CANDLE_STAT = {"bull_close": "after a close above the prior high NQ takes that high next day ~80% of the time (base 55%)",
                "bear_close": "after a close below the prior low NQ takes that low next day ~67% (base 46%)",
                "low_swept_reclaim": "a swept-and-reclaimed low leads to the prior high ~62% of the time",
                "high_swept_reject": "a swept-and-rejected high leads to the prior low ~58% of the time"}


def _bias_why(n):
    """Bias components as phrases: supporting ones first, then 'despite ...' for the ones that disagree."""
    h, parts = n["htf"], n["bias_parts"]
    sgn = 1 if n["bias_score"] > 0 else (-1 if n["bias_score"] < 0 else 0)
    nice = {"ASIA": "Asia", "LON": "London"}
    items = []
    if parts["daily"]:
        items.append((parts["daily"], f"daily structure {_dirword(h['daily_dir'])}"))
    if parts["h4"]:
        items.append((parts["h4"], f"4H {_dirword(h['h4_dir'])}"))
    if parts["candle"]:
        st = _CANDLE_STAT.get(h["prev_candle"])
        items.append((parts["candle"], f"yesterday printed {h['prev_candle_text']}" + (f" ({st})" if st else "")))
    if parts["clv"]:
        items.append((parts["clv"], f"yesterday closed in the {'top' if parts['clv'] > 0 else 'bottom'} quarter of its range"))
    if parts["raid"]:
        o = n["overnight"]
        nm = o["lows_raided"] if parts["raid"] > 0 else o["highs_raided"]
        items.append((parts["raid"], "overnight raided the " + " and ".join(nice.get(x, x) for x in nm) +
                      (" low" if parts["raid"] > 0 else " high") + " and reclaimed"))
    if parts["h1"]:
        items.append((parts["h1"], f"1H {_dirword(h['h1_dir'])}"))
    if parts["weekly"]:
        items.append((parts["weekly"], f"price at a weekly {'low' if parts['weekly'] > 0 else 'high'} extreme"))
    if sgn == 0:
        return [w for _, w in items]
    pro = [w for v, w in items if v * sgn > 0]
    con = [w for v, w in items if v * sgn < 0]
    return pro + ([f"despite {', '.join(con)}"] if con else [])


def _bias_line(n):
    wp = n["htf"]["weekly_pos"]
    loc = "discount" if wp < 0.45 else ("premium" if wp > 0.55 else "equilibrium")
    why = "; ".join(n.get("bias_why") or []) or "no strong components"
    if n["bias_dir"] == 0:
        return f"Bias neutral (score {n['bias_score']:+.2f}): {why}; both sides are in play."
    side = "longs" if n["bias_dir"] > 0 else "shorts"
    return (f"Bias {'bullish' if n['bias_dir'] > 0 else 'bearish'} (conviction {n['conviction']:.2f}): {why}; price in {loc} "
            f"of the weekly range, so {side} preferred.")


def _dirword(d):
    return "bullish" if d > 0 else ("bearish" if d < 0 else "flat")


def _story(n):
    h, o = n["htf"], n["overnight"]
    s = []
    agree = h["daily_dir"] == h["h4_dir"] and h["daily_dir"] != 0
    s.append(f"Daily structure is {_dirword(h['daily_dir'])}" +
             (f" and the 4H agrees" if agree else f", 4H is {_dirword(h['h4_dir'])}") +
             f"; 1H is {_dirword(h['h1_dir'])}.")
    s.append(f"Yesterday printed {h['prev_candle_text']} and closed at {int(round(100 * h['prev_close_loc']))}% of its range.")
    raids = []
    for nm, lab in (("ASIA", "Asia"), ("LON", "London"), ("ATM", "the 07:00-09:25 range")):
        x = o["sessions"].get(nm)
        if not x:
            continue
        tk = [w for w, f in (("high", x["H_taken"]), ("low", x["L_taken"])) if f]
        if tk and nm != "ATM":
            raids.append(f"the {lab} {' and '.join(tk)} {'were' if len(tk) > 1 else 'was'} taken")
    if raids:
        s.append("Overnight: " + "; ".join(raids) + ".")
    else:
        s.append("Overnight: Asia and London ranges are intact.")
    if o.get("ndog") is not None and abs(o["ndog"]) >= 0.05 * n["adr10"]:
        s.append(f"There is a {abs(o['ndog']):.0f}-pt opening gap (NDOG) {'up' if o['ndog'] > 0 else 'down'} from yesterday's close.")
    wp = h["weekly_pos"]
    s.append(f"Price sits in the {'premium' if wp > 0.55 else ('discount' if wp < 0.45 else 'middle')} of the weekly range "
             f"({int(round(100 * wp))}%).")
    if n["bias"] == "neutral":
        s.append(f"No clear bias (score {n['bias_score']:+.2f}); I want to see which side gets raided first.")
    else:
        s.append(f"Bias: {n['bias'].upper()} with conviction {n['conviction']:.2f} (score {n['bias_score']:+.2f}).")
    d = n["draw"]
    if d:
        if d.get("two_sided"):
            s.append(f"Nearest obvious liquidity: {d['nice']} at {_px(d['price'])} ({d['dist_pts']:.0f} pts).")
        else:
            s.append(f"Primary draw: {d['nice']} at {_px(d['price'])}, {d['dist_pts']:.0f} pts away "
                     f"({'inside' if d['within_reach'] else 'beyond'} the {n['reach']:.0f}-pt range left today).")
        if n.get("draw_beyond"):
            b = n["draw_beyond"]
            s.append(f"The bigger target, the {NICE.get(b['label'], b['label'])} at {_px(b['price'])}, is beyond today's range.")
    else:
        s.append("No obvious untaken pool on the bias side (price discovery); targets will be projections.")
    s.append(f"PO3: {n['po3']}.")
    dt_ = n["day_type"]
    why = []
    if n["inside"] or n["nr4"]:
        why.append("yesterday was compressed")
    if abs(o["gap_vs_rth_close"]) >= 0.25 * n["adr10"]:
        why.append("big gap vs yesterday's RTH close")
    if n["news"]["cpi_nfp"]:
        why.append("CPI/NFP today")
    if n["news"]["fomc"]:
        why.append("FOMC today (expect a slow AM)")
    if o["on_range"] >= 0.6 * n["adr10"]:
        why.append("overnight already used most of the ADR")
    s.append(f"Day type: {dt_}" + (f" ({', '.join(why)})." if why else "."))
    if n["news"]["events"]:
        s.append("Calendar: " + ", ".join(f"{_hm(m)} {e}" for m, e in n["news"]["events"][:3]) + ".")
    return " ".join(s)


def use_daily_bias(method="composite"):
    """Bias source backed by engine/daily_bias.py (another agent's module) when it exists; None otherwise.
    Pass the result as narrative(..., bias_source=...)."""
    try:
        from engine import daily_bias as DB
    except Exception:
        return None

    def src(bars5, t):
        r = DB.bias(bars5, t, method)
        return r if isinstance(r, dict) else None
    return src


def narrative(bars5, t, es5=None, bias_source=None):
    """Pre-market narrative (state at 09:30 ET, from closed bars only) plus the intraday update at t.
    bias_source: optional callable (bars5, t) -> {dir, confidence, draw?, why?} that replaces the brain's own bias."""
    C = ctx(bars5)
    i_now = C.idx_at(t)
    if i_now < 0:
        return {"bias": "neutral", "bias_dir": 0, "conviction": 0.0, "draw": None, "day_type": "normal",
                "story": "no data"}
    k = int(C.di[i_now])

    t930 = int(C.t930[k])
    T0 = min(int(t), t930)
    pm = _premarket(C, k, T0)
    n = {kk: v for kk, v in pm.items() if kk != "pools"}
    n["bias_source"] = "brain"
    if bias_source is not None:
        try:
            ext = bias_source(bars5, min(int(t), t930))
        except Exception:
            ext = None
        if ext and ext.get("dir") is not None:
            bd = int(np.sign(ext["dir"]))
            n["bias_dir"], n["bias"] = bd, ("long" if bd > 0 else ("short" if bd < 0 else "neutral"))
            n["conviction"] = round(float(min(1.0, max(0.0, ext.get("confidence", 0.5)))), 2)
            why = ext.get("why")
            n["bias_why"] = [why] if isinstance(why, str) else list(why or [])
            dr = ext.get("draw")
            if isinstance(dr, dict) and dr.get("price") is not None:
                n["draw"] = {**(n.get("draw") or {}), **dr}
            elif isinstance(dr, (int, float)):
                n["draw"] = {**(n.get("draw") or {}), "price": float(dr), "label": "external", "nice": "external draw",
                             "side": int(np.sign(float(dr) - pm["price"])) or bd}
            n["bias_line"] = _bias_line(n)
            n["bias_source"] = "external"
    n["premarket_story"] = pm["story"]
    n["t_now"] = int(t)
    n["update"] = None
    n["bias_failed"] = False
    n["draw_hit"] = False
    a_today = C.ds[k]
    tH = float(C.h[a_today:i_now + 1].max())
    tL = float(C.l[a_today:i_now + 1].min())
    n["today_hi"], n["today_lo"] = tH, tL
    n["today_range"] = round(tH - tL, 2)
    n["remaining"] = round(pm["adr10"] - (tH - tL), 2)
    n["reach_now"] = round(max(0.5 * pm["adr10"], pm["adr10"] - (tH - tL)), 2)
    n["price_now"] = float(C.c[i_now])
    if int(t) > t930:
        i0 = C.idx_at(T0)
        upd = []
        px0 = pm["price"]
        d = pm["draw"]
        if d is not None and C.taken(d["side"], d["price"], i0 + 1, i_now):
            n["draw_hit"] = True
            upd.append(f"the draw ({d['nice']} {_px(d['price'])}) has been delivered")
        taken_now = [p for p in pm["pools"] if not p["taken"] and p["name"] in TIER_A and C.taken(p["side"], p["price"], max(p["avail"], i0 + 1), i_now)]
        if taken_now:
            upd.append("taken since the open: " + ", ".join(NICE.get(p["name"], p["name"]) for p in taken_now[:4]))
        b = pm["bias_dir"]
        if b != 0:
            opp = [p for p in pm["pools"] if p["side"] == -b and not p["taken"] and p["name"] in TIER_A and (p["price"] - px0) * b < 0]
            if opp:
                ref = max(opp, key=lambda p: p["price"] * b)
                cl = C.c[i0 + 1:i_now + 1]
                beyond = (cl - ref["price"]) * b < 0
                if len(beyond) >= 2 and np.any(beyond[1:] & beyond[:-1]):
                    n["bias_failed"] = True
                    n["bias"], n["bias_dir"], n["conviction"] = "neutral", 0, 0.0
                    upd.append(f"BIAS FAILED: two closes {'below' if b > 0 else 'above'} the {NICE.get(ref['name'], ref['name'])} "
                               f"({_px(ref['price'])}); the {pm['bias']} idea is off, standing aside from bias trades")
        # actual RTH gap once the 09:30 bar has closed
        i930 = int(np.searchsorted(C.t, t930))
        if i930 < len(C.t) and C.t[i930] == t930 and i930 <= i_now:
            rH, rL, rlast, _ = C.sess["RTH"]
            if k >= 1 and rlast[k - 1] >= 0:
                gap = float(C.o[i930] - C.c[rlast[k - 1]])
                n["rth_gap"] = round(gap, 2)
        used = (tH - tL) / max(pm["adr10"], TICK)
        upd.append(f"range so far {tH - tL:.0f} pts = {100 * used:.0f}% of ADR, {max(0.0, n['remaining']):.0f} pts left")
        mod_now = int((C.mod[i_now] + 5) % 1440)
        n["update"] = f"Update {_hm(mod_now)}: " + "; ".join(upd) + "."
        n["story"] = pm["story"] + " " + n["update"]
    return n


# ------------------------------------------------------------------------------------------------ setup judgment
def _extreme(C, setup, i_dec):
    d = setup["dir"]
    if setup.get("sweep_t"):
        j = int(np.searchsorted(C.t, int(setup["sweep_t"]), side="right")) - 1     # the 5m bar containing the raid extreme
        if 0 <= j <= i_dec:
            return j
    a = max(0, i_dec - 35)
    seg = C.l[a:i_dec + 1] if d > 0 else -C.h[a:i_dec + 1]
    return a + int(np.argmin(seg))


def n_res(C, i_now, d, entry, target):
    """DOL-6 path resistance: fresh 5m swings (today+yesterday) + live 15m opposing FVGs in (entry, target), merged."""
    atr = float(C.atr5[i_now])
    tol = max(2 * TICK, 0.1 * atr)
    zones = [px for px in swings5(C, i_now, d, days=1) if (px - entry) * d > 0 and (target - px) * d > tol]
    for g in live_gaps(C, i_now, -d, kinds=("15m",)):
        near = g["bottom"] if d > 0 else g["top"]
        if (near - entry) * d > 0 and (target - near) * d > tol:
            zones.append(near)
    zones = sorted(z * d for z in zones)
    cnt, last = 0, None
    for z in zones:
        if last is None or z - last > tol:
            cnt += 1
        last = z
    return cnt


def _e_align(ctx_):
    s, n = ctx_["setup"], ctx_["nar"]
    b, d = n["bias_dir"], s["dir"]
    m = 2.0 * max(n["conviction"], 0.5)
    if b == 0:
        why = "no bias" + (" (the pre-market bias failed)" if n.get("bias_failed") else "") + ": this is a pure reaction trade"
        return 0.0, why
    if b == d:
        return m, f"with the {n['bias']} bias (conviction {n['conviction']:.2f})"
    return -m, f"against the {n['bias']} bias (conviction {n['conviction']:.2f})"


def _e_manip(ctx_):
    s, n = ctx_["setup"], ctx_["nar"]
    b, d = n["bias_dir"], s["dir"]
    lab = s.get("sweep_label")
    if b == 0:
        return 0.0, "no bias, so no PO3 read on the sweep"
    if n.get("draw_hit"):
        if b == d:
            return -0.5, "the day's draw is already delivered; a with-bias trade now is late"
        return 0.0, "the draw is delivered, so a fade is allowed"
    if b == d:
        if lab:
            return 1.0, f"the sweep of the {NICE.get(lab, lab)} is the manipulation into the draw"
        return 0.5, "with-bias entry after a local raid"
    return -0.5, "fading the narrative while the draw is still open"


def _e_location(ctx_):
    s, n = ctx_["setup"], ctx_["nar"]
    d = s["dir"]
    lo = min(n["today_lo"], ctx_["pdl"]) if ctx_["pdl"] is not None else n["today_lo"]
    hi = max(n["today_hi"], ctx_["pdh"]) if ctx_["pdh"] is not None else n["today_hi"]
    p = (s["entry"] - lo) / max(hi - lo, TICK)
    ctx_["dr_pos"] = p
    good = p < 0.35 if d > 0 else p > 0.65
    bad = p > 0.65 if d > 0 else p < 0.35
    word = "discount" if p < 0.45 else ("premium" if p > 0.55 else "equilibrium")
    if good:
        return 1.0, f"{'buying' if d > 0 else 'selling'} from {word} ({100 * p:.0f}% of the 2-day range)"
    if bad:
        return -1.0, f"{'buying' if d > 0 else 'selling'} from {word} ({100 * p:.0f}% of the 2-day range): poor location"
    return 0.0, f"entry near equilibrium ({100 * p:.0f}% of the 2-day range)"


def _e_timing(ctx_):
    m = ctx_["mod_dec"]
    if m < 570:
        return -0.5, f"pre-open entry ({_hm(m)})"
    if m < 630:
        return 1.0, f"prime time ({_hm(m)}, first RTH hour)"
    if m < 660:
        return 0.0, f"late morning ({_hm(m)})"
    if m < 720:
        return -1.0, f"after 11:00 ({_hm(m)}): the AM move is usually done"
    if m < 810:
        return -1.5, f"lunch ({_hm(m)}): chop risk"
    return -1.0, f"PM session ({_hm(m)}): draws are hit less often"


def _e_quality(ctx_):
    C, s = ctx_["C"], ctx_["setup"]
    d, ie, idc = s["dir"], ctx_["i_ext"], ctx_["i_dec"]
    atr = max(float(C.atr5[idc]), TICK)
    bodies = (C.c[ie:idc + 1] - C.o[ie:idc + 1]) * d
    mb = float(bodies.max()) / atr if len(bodies) else 0.0
    vb = int(idc - ie) if s.get("bars_to_v") is None else int(s["bars_to_v"])
    sc, why = 0.0, []
    if mb >= 1.5:
        sc += 1.0
        why.append(f"strong displacement ({mb:.1f} ATR body)")
    elif mb >= 1.0:
        sc += 0.5
        why.append(f"decent displacement ({mb:.1f} ATR)")
    elif mb < 0.7:
        sc -= 0.5
        why.append(f"weak displacement ({mb:.1f} ATR)")
    if vb <= 3:
        sc += 0.5
        why.append(f"fast V ({vb} bars)")
    elif vb >= 9:
        sc -= 0.5
        why.append(f"slow reclaim ({vb} bars)")
    if s.get("ifvg_pts") is not None and s["ifvg_pts"] >= 0.25 * atr:
        sc += 0.25
        why.append(f"meaningful IFVG ({s['ifvg_pts']:.1f} pts)")
    if str(s.get("trigger_tf", "5m")) in ("15m", "1h", "30m"):
        sc += 0.25
        why.append(f"{s['trigger_tf']} trigger")
    sc = float(min(1.5, max(-1.0, sc)))
    ctx_["disp_atr"], ctx_["v_bars"] = round(mb, 2), vb
    return sc, ", ".join(why) if why else f"ordinary displacement ({mb:.1f} ATR), V in {vb} bars"


def _e_intermarket(ctx_):
    E, C, s = ctx_["E"], ctx_["C"], ctx_["setup"]
    if E is None:
        return 0.0, "no ES data"
    d, ie, idc = s["dir"], ctx_["i_ext"], ctx_["i_dec"]
    t_ext, t_dec = int(C.t[ie]), int(C.t[idc]) + BAR
    a = max(0, ie - 24)
    ref_a, ref_b = int(C.t[a]), int(C.t[max(a, ie - 2)])
    ja, jb = np.searchsorted(E.t, ref_a), np.searchsorted(E.t, ref_b, side="right")
    jx0, jx1 = np.searchsorted(E.t, int(C.t[max(0, ie - 1)])), np.searchsorted(E.t, min(t_ext + 2 * BAR, t_dec - BAR), side="right")
    sc, why = 0.0, []
    if jb - ja >= 3 and jx1 > jx0:
        if d > 0:
            nq_took = C.l[ie] < C.l[a:max(a + 1, ie - 1)].min()
            es_took = E.l[jx0:jx1].min() < E.l[ja:jb].min()
        else:
            nq_took = C.h[ie] > C.h[a:max(a + 1, ie - 1)].max()
            es_took = E.h[jx0:jx1].max() > E.h[ja:jb].max()
        if nq_took != es_took:
            sc += 1.0
            why.append("SMT: " + ("NQ swept, ES held" if nq_took else "ES swept, NQ held"))
            ctx_["smt"] = True
    # relative strength since 09:30 (18:00 before 09:30)
    k = int(C.di[idc])
    t0 = int(C.t930[k]) if t_dec > int(C.t930[k]) + BAR else int(C.t[C.ds[k]])
    i0 = int(np.searchsorted(C.t, t0))
    e0 = int(np.searchsorted(E.t, t0))
    e1 = int(np.searchsorted(E.t, t_dec - BAR, side="right")) - 1
    if i0 <= idc and 0 <= e0 <= e1 < len(E.t) and abs(int(E.t[e0]) - t0) <= 900:
        rn = C.c[idc] / C.o[i0] - 1.0
        re_ = E.c[e1] / E.o[e0] - 1.0
        rs = (rn - re_) * d
        ctx_["rs"] = round(float(rs) * 100, 3)
        if rs > 0.0002:
            sc += 0.5
            why.append(f"NQ {'stronger' if d > 0 else 'weaker'} than ES since the open")
        elif rs < -0.0002:
            sc -= 0.5
            why.append(f"NQ {'weaker' if d > 0 else 'stronger'} than ES since the open (wrong-way strength)")
    return sc, ", ".join(why) if why else "no intermarket signal"


def _e_room(ctx_):
    s, n = ctx_["setup"], ctx_["nar"]
    tg = s["targets"][-1] if s.get("targets") else None
    used = n["today_range"] / max(n["adr10"], TICK)
    sc, why = 0.0, []
    if tg is not None:
        dist = abs(tg - s["entry"])
        if dist <= n["reach_now"]:
            sc += 0.5
            why.append(f"target {dist:.0f} pts away is inside the {n['reach_now']:.0f}-pt range left")
        else:
            sc -= 1.0
            why.append(f"target {dist:.0f} pts away is beyond the {n['reach_now']:.0f}-pt range left")
    if used >= 1.0:
        sc -= 1.0
        why.append(f"the day already ran {100 * used:.0f}% of its ADR")
    return sc, "; ".join(why) if why else "room unknown"


def _e_path(ctx_):
    C, s = ctx_["C"], ctx_["setup"]
    tg = s["targets"][-1] if s.get("targets") else None
    if tg is None:
        return 0.0, "no target to check the path"
    nr = n_res(C, ctx_["i_dec"], s["dir"], s["entry"], tg)
    ctx_["n_res"] = nr
    if nr <= 1:
        return 0.5, f"clean path to the target (LRLR, {nr} obstacle{'s' if nr != 1 else ''})"
    if nr >= 3:
        return -0.5, f"crowded path ({nr} obstacles, HRLR)"
    return 0.0, f"{nr} obstacles on the way"


def _e_news(ctx_):
    n = ctx_["nar"]
    m = ctx_["mod_dec"]
    for em, e in n["news"]["events"]:
        if -10 <= em - m <= 15:
            ctx_["veto"] = f"{e} at {_hm(em)} is too close"
    if n["news"]["fomc"]:
        return -1.0, "FOMC day"
    if n["news"]["cpi_nfp"]:
        return -1.0, "CPI/NFP day"
    return 0.0, "no tier-1 news"


def _e_po3(ctx_):
    s, n = ctx_["setup"], ctx_["nar"]
    b = n["bias_dir"]
    if b != 0 and b == s["dir"] and (s["entry"] - n["daily_open"]) * b < 0:
        return 0.5, f"{'buying below' if b > 0 else 'selling above'} the 18:00 open in a {n['bias']} bias (PO3)"
    return 0.0, "no PO3 location edge"


ELEMENTS = collections.OrderedDict([
    ("E1_align", _e_align), ("E2_manip", _e_manip), ("E3_location", _e_location), ("E4_timing", _e_timing),
    ("E5_quality", _e_quality), ("E6_intermarket", _e_intermarket), ("E7_room", _e_room), ("E8_path", _e_path),
    ("E9_news", _e_news), ("E10_po3", _e_po3),
])
VERSIONS = {"v1": list(ELEMENTS)}
LABEL = {"E1_align": "bias alignment", "E2_manip": "manipulation into the draw", "E3_location": "premium/discount location",
         "E4_timing": "time of day", "E5_quality": "displacement / V quality", "E6_intermarket": "SMT / NQ-vs-ES",
         "E7_room": "room in the day's range", "E8_path": "path resistance", "E9_news": "news", "E10_po3": "PO3 open location"}


def register(eid, fn, versions=("v2",), label=None):
    """Plug in a new judgment element (e.g. a trader heuristic) for the given versions."""
    ELEMENTS[eid] = fn
    LABEL[eid] = label or eid
    for v in versions:
        VERSIONS.setdefault(v, list(VERSIONS["v1"]))
        if eid not in VERSIONS[v]:
            VERSIONS[v].append(eid)


def first_irl(C, i_dec, d, entry, risk, final):
    """First internal draw >= 1R and short of the final target: live opposing FVG near edge or Tier-B/C pool."""
    cands = []
    for g in live_gaps(C, i_dec, -d):
        near = g["bottom"] if d > 0 else g["top"]
        cands.append((near, f"{g['tf']} FVG"))
    for px in swings5(C, i_dec, d, days=1):
        cands.append((px - d * 2 * TICK, "5m swing"))
    lim = abs(final - entry) if final is not None else 1e9
    ok = [(abs(px - entry), px, lab) for px, lab in cands if (px - entry) * d >= risk and abs(px - entry) < lim - TICK]
    if not ok:
        return None
    _, px, lab = min(ok)
    return {"price": float(px), "label": lab, "r": round(abs(px - entry) / max(risk, TICK), 2)}


def assess(setup, nar=None, bars5=None, es5=None, version="v1", trust=None, cuts=None, require_bias_alignment=False):
    """Judge one setup like a trader. setup: entry_t (decision time), dir, entry, stop, targets, optional sweep_level /
    sweep_label / sweep_t / trigger_tf / ifvg_pts / bars_to_v. Returns decision, grade, size_tier, plan and thoughts."""
    if bars5 is None:
        raise ValueError("assess() needs bars5")
    C, E = ctx(bars5), ctx(es5)
    setup = dict(setup)
    setup["dir"] = int(setup["dir"])
    if setup.get("sweep_label") is None and setup.get("label"):
        setup["sweep_label"] = setup["label"]
    t = int(setup["entry_t"])
    if nar is None:
        nar = narrative(bars5, t, es5)
    i_dec = C.idx_at(t)
    k = int(C.di[i_dec])
    if not setup.get("targets"):
        setup["targets"] = [default_target(C, i_dec, setup["dir"], float(setup["entry"]), abs(float(setup["entry"]) - float(setup["stop"])))]
        setup["target_source"] = "default"
    cx = {"C": C, "E": E, "setup": setup, "nar": nar, "i_dec": i_dec, "mod_dec": int((C.mod[i_dec] + 5) % 1440),
          "pdh": float(C.D.H[k - 1]) if k >= 1 else None, "pdl": float(C.D.L[k - 1]) if k >= 1 else None}
    cx["i_ext"] = _extreme(C, setup, i_dec)
    els = {}
    for eid in VERSIONS[version]:
        try:
            sc, why = ELEMENTS[eid](cx)
        except Exception as ex:                      # a broken heuristic must never break the trade decision
            sc, why = 0.0, f"n/a ({type(ex).__name__})"
        els[eid] = (float(sc), why)
    tr = trust or {}
    S = float(sum(tr.get(e, 1.0) * v[0] for e, v in els.items()))
    gc = cuts or VERSION_CUTS.get(version, GRADE_CUT)
    grade = "A" if S >= gc["A"] else ("B" if S >= gc["B"] else ("C" if S >= gc["C"] else "SKIP"))
    veto = cx.get("veto")
    if require_bias_alignment and nar.get("bias_dir", 0) != 0 and nar["bias_dir"] != setup["dir"] and not veto:
        veto = f"counter-bias setup ({nar['bias']} bias) and require_bias_alignment is on"
    if veto:
        grade = "SKIP"
    decision = "SKIP" if grade == "SKIP" else "TAKE"
    risk = abs(setup["entry"] - setup["stop"])
    final = setup["targets"][-1] if setup.get("targets") else (nar["draw"]["price"] if nar.get("draw") and nar["draw"]["side"] == setup["dir"] else None)
    tp1 = first_irl(C, i_dec, setup["dir"], setup["entry"], risk, final)
    hr = cx.get("n_res", 0) >= 3
    if grade in ("A", "B") and nar["day_type"] != "consolidation" and not hr:
        plan = {"plan": "partial_runner", "tp1": tp1, "final": final,
                "text": (f"half at the first IRL ({tp1['label']} {_px(tp1['price'])}, {tp1['r']}R), runner to {_px(final)}" if tp1
                         else f"no IRL in between: all to {_px(final)}")}
    else:
        first = tp1["price"] if tp1 else final
        plan = {"plan": "first_draw", "tp1": tp1, "final": first,
                "text": f"all out at the first draw {_px(first)}" + (f" ({tp1['label']})" if tp1 else "")}
    if grade == "C" or nar["day_type"] == "consolidation" or cx["mod_dec"] >= 810:
        mode = "quick"
    elif grade in ("A", "B") and nar["day_type"] == "expansion":
        mode = "hold"
    else:
        mode = "normal"
    out = {"decision": decision, "grade": grade, "score": round(S, 2), "size_tier": grade,
           "risk_usd": TIER_RISK[grade], "target_plan": plan, "manage_mode": mode, "veto": veto,
           "elements": {e: {"score": v[0], "why": v[1]} for e, v in els.items()},
           "facts": {kk: cx.get(kk) for kk in ("dr_pos", "disp_atr", "v_bars", "n_res", "smt", "rs")}}
    out["thoughts"] = _thoughts(setup, nar, out)
    return out


def _thoughts(setup, nar, v):
    d = "Long" if setup["dir"] > 0 else "Short"
    lab = setup.get("sweep_label")
    els = v["elements"]
    pos = sorted([(s["score"], s["why"]) for s in els.values() if s["score"] > 0], reverse=True)
    neg = sorted([(s["score"], s["why"]) for s in els.values() if s["score"] < 0])
    first = f"{d} after a sweep of the {NICE.get(lab, lab)}" if lab else f"{d} after a local raid"
    first += f" at {_px(setup['entry'])}"
    b = nar.get("bias_dir", 0)
    bl = nar.get("bias_line") or ""
    if nar.get("bias_failed"):
        bl = "The pre-market bias failed intraday, so this is a two-sided tape."
    al = ("This trade is WITH the bias." if b == setup["dir"] else ("This trade is AGAINST the bias." if b else "No bias to align with."))
    parts = [f"{bl} {al}".strip()]
    parts.append(first + (": " + "; ".join(w for _, w in pos[:2]) if pos else "") + ".")
    if neg:
        parts.append("Against it: " + "; ".join(w for _, w in neg[:2]) + ".")
    if v["veto"]:
        parts.append(f"Hard pass: {v['veto']}.")
    elif v["decision"] == "SKIP":
        parts.append(f"Too many strikes (score {v['score']:+.1f}); I pass.")
    else:
        risk = {"A": "full size ($700 risk, up to 1 NQ)", "B": "normal size ($350)", "C": "small size ($175 in micros)"}[v["grade"]]
        parts.append(f"Grade {v['grade']} (score {v['score']:+.1f}) -> {risk}; plan: {v['target_plan']['text']}, "
                     f"{'hold for expansion' if v['manage_mode'] == 'hold' else ('manage it quick' if v['manage_mode'] == 'quick' else 'normal management')}.")
    return " ".join(parts)


# ------------------------------------------------------------------------------------------------ in-trade thinking
def manage(position, bars_since_entry, nar=None):
    """One decision at the close of the latest bar. position: dir, entry, stop, risk, tp1, final, partial_done, be_done,
    mode, atr, mfe_r. bars_since_entry: dict/DataFrame with open/high/low/close/mod for bars from the fill bar on.
    Returns {"action": hold|exit|stop, "stop": price, "reason": str}."""
    b = bars_since_entry
    o, h, l, c = (np.asarray(b[x], float) for x in ("open", "high", "low", "close"))
    mods = np.asarray(b["mod"], int)
    n = len(c)
    d, E = int(position["dir"]), float(position["entry"])
    R = max(float(position.get("risk") or abs(E - float(position["stop"]))), TICK)
    atr = max(float(position.get("atr") or (float(np.mean(np.asarray(b["high"], float)[:1] - np.asarray(b["low"], float)[:1])) or 1.0)), TICK)
    stop = position["stop"]
    mfe = float(((h.max() - E) if d > 0 else (E - l.min())) / R) if n else 0.0
    position["mfe_r"] = mfe
    m_close = int((mods[-1] + 5) % 1440)
    buf = max(2 * TICK, 0.1 * atr)
    if m_close >= 955:
        return {"action": "exit", "stop": stop, "reason": "15:55: flat for the day"}
    if m_close == 720 and (stop - E) * d < 0:
        return {"action": "exit", "stop": stop, "reason": "12:00 and the trade is still unprotected: lunch is no place for open risk"}
    lim = 9 if position.get("mode") == "quick" else 12
    if n >= lim and mfe < 0.5 and not position.get("partial_done"):
        return {"action": "exit", "stop": stop, "reason": f"{5 * n} min in and only +{mfe:.2f}R: no progress, the idea isn't working"}
    # opposing CISD with displacement (series in favor that began after entry)
    body = (c - o) * d
    last = n - 1
    if n >= 3:
        j = last - 1
        while j >= 0 and body[j] > 0:
            j -= 1
        start = j + 1
        if start < last and start >= 0 and body[last] < 0:
            ref = o[start]
            disp = abs(c[last] - o[last]) >= 1.0 * atr and abs(c[last] - o[last]) >= 0.6 * max(h[last] - l[last], TICK)
            if (c[last] - ref) * d < 0 and disp and mfe < 1.0:
                return {"action": "exit", "stop": stop, "reason": "an opposing displacement candle broke my in-favor series (CISD against me): delivery changed state"}
    # IRL rejection
    tp1 = position.get("tp1")
    if tp1 is not None and n >= 1:
        near = ((h[last] if d > 0 else -l[last]) >= (tp1 * d - 0.1 * R))
        rej = (-body[last]) >= 0.8 * atr and ((c[last] - l[last]) / max(h[last] - l[last], TICK) <= 0.3 if d > 0 else
                                               (h[last] - c[last]) / max(h[last] - l[last], TICK) <= 0.3)
        if near and rej:
            return {"action": "exit", "stop": stop, "reason": f"the IRL at {_px(tp1)} rejected with displacement: bank it"}
    # 5m BOS in favor (swing formed after entry)
    bos, pl = False, None
    if n >= 5:
        H_ = h if d > 0 else -l
        L_ = l if d > 0 else -h
        for s_ in range(2, n - 2):
            if H_[s_] > max(H_[s_ - 2], H_[s_ - 1]) and H_[s_] >= max(H_[s_ + 1], H_[s_ + 2]) and s_ + 2 < last:
                if (c[last] * d) > H_[s_] and (c[last - 1] * d) <= H_[s_]:
                    bos = True
                    pl = float(L_[s_:last + 1].min())
    if not position.get("be_done") and (position.get("partial_done") or (bos and mfe >= 0.5)):
        ns = E + d * 2 * TICK
        if (ns - stop) * d > 0:
            why = "partial banked" if position.get("partial_done") else "5m BOS in my favor"
            return {"action": "stop", "stop": ns, "be": True, "reason": f"{why}: stop to break-even"}
    if position.get("be_done") and position.get("mode") == "hold" and bos and pl is not None:
        ns = (pl - buf) if d > 0 else (-pl + buf)
        if (ns - stop) * d > 0:
            return {"action": "stop", "stop": ns, "reason": f"expansion continues (5m BOS): trail under the protected {'low' if d > 0 else 'high'} {_px(ns)}"}
    if n >= 2 and body[-1] > 0.8 * atr and body[-2] > 0.8 * atr:
        return {"action": "hold", "stop": stop, "reason": "consecutive displacement in my favor: let it run"}
    return {"action": "hold", "stop": stop, "reason": f"inside the plan (MFE +{mfe:.2f}R)"}


def simulate(bars5, setup, verdict, nar, fill_t=None, entry_fill=None):
    """Replay manage() bar by bar from the fill bar. Returns legs [(fraction, exit_px, kind, exit_t)], log, r (per
    contract, after 1-tick stop/market slippage and $1.40/micro commission, in R of the planned risk)."""
    C = ctx(bars5)
    d = setup["dir"]
    E = float(entry_fill if entry_fill is not None else setup["entry"])
    S0 = float(setup["stop"])
    R = abs(E - S0)
    i = int(np.searchsorted(C.t, int(fill_t if fill_t is not None else setup["entry_t"])))
    k = int(C.di[min(i, len(C.t) - 1)])
    plan = verdict["target_plan"]
    tp1 = plan["tp1"]["price"] if (plan["plan"] == "partial_runner" and plan.get("tp1")) else None
    final = plan.get("final")
    pos = {"dir": d, "entry": E, "stop": S0, "risk": R, "tp1": tp1, "final": final, "partial_done": False, "be_done": False,
           "mode": verdict["manage_mode"], "atr": float(C.atr5[max(0, i - 1)])}
    legs, log, rem = [], [], 1.0
    i0 = i
    while i < len(C.t) and C.di[i] == k and rem > 1e-9:
        hi, lo = C.h[i], C.l[i]
        tm = int(C.t[i])
        st = pos["stop"]
        if (lo <= st) if d > 0 else (hi >= st):
            legs.append((rem, st, "stop", tm + BAR))
            log.append((tm, f"stopped at {_px(st)}" + (" (break-even)" if pos["be_done"] else "")))
            rem = 0.0
            break
        if tp1 is not None and not pos["partial_done"] and ((hi >= tp1 + TICK) if d > 0 else (lo <= tp1 - TICK)):
            legs.append((0.5 * rem, tp1, "target", tm + BAR))
            rem *= 0.5
            pos["partial_done"] = True
            log.append((tm, f"partial at the IRL {_px(tp1)}"))
        if final is not None and ((hi >= final + TICK) if d > 0 else (lo <= final - TICK)):
            legs.append((rem, final, "target", tm + BAR))
            log.append((tm, f"target {_px(final)} reached: done"))
            rem = 0.0
            break
        b = {"open": C.o[i0:i + 1], "high": C.h[i0:i + 1], "low": C.l[i0:i + 1], "close": C.c[i0:i + 1], "mod": C.mod[i0:i + 1]}
        act = manage(pos, b, nar)
        if act["action"] == "exit":
            legs.append((rem, float(C.c[i]), "market", tm + BAR))
            log.append((tm + BAR, f"exit at {_px(C.c[i])}: {act['reason']}"))
            rem = 0.0
            break
        if act["action"] == "stop":
            pos["stop"] = act["stop"]
            if act.get("be"):
                pos["be_done"] = True
            log.append((tm + BAR, act["reason"]))
        elif act["reason"].startswith("consecutive") and (not log or not log[-1][1].startswith("consecutive")):
            log.append((tm + BAR, act["reason"]))
        i += 1
    if rem > 1e-9:
        j = min(i, len(C.t) - 1)
        legs.append((rem, float(C.c[j - 1] if j > i0 else C.c[j]), "market", int(C.t[j - 1]) + BAR))
        log.append((int(C.t[j - 1]) + BAR, "end of session: flat"))
    r = 0.0
    for frac, px, kind, _ in legs:
        fill = px - d * TICK if kind in ("stop", "market") else px
        r += frac * (((fill - E) * d * 2.0 - 1.40) / (R * 2.0))
    return {"legs": legs, "log": log, "r": round(r, 3), "mfe_r": round(pos.get("mfe_r", 0.0), 2)}


# ------------------------------------------------------------------------------------------------ v2: trader heuristics
# Rules: research/lab/NARRATIVE_RULES.md section 7 (v2-final). Source: research/lab/TRADER_HEURISTICS.md.
def _refs(C, k):
    key = ("refs", k)
    if key in C._pm:
        return C._pm[key]
    a, b = int(C.ds[k]), int(C.de[k])
    mods = C.mod[a:b]

    def first(m):
        j = np.flatnonzero(mods == m)
        return a + int(j[0]) if len(j) else None

    i_mo, i930 = first(0), first(570)
    rH, rL, rlast, _ = C.sess["RTH"]
    prth = (float(rH[k - 1]), float(rL[k - 1]), float(C.c[rlast[k - 1]])) if k >= 1 and rlast[k - 1] >= 0 else None
    r = {"i_mo": i_mo, "mo": float(C.o[i_mo]) if i_mo is not None else None, "i930": i930,
         "o930": float(C.o[i930]) if i930 is not None else None, "prth": prth}
    C._pm[key] = r
    return r


def _cx_refs(cx):
    C, i = cx["C"], cx["i_dec"]
    k = int(C.di[i])
    return C, i, k, _refs(C, k)


def _rvwap(C, i930, i):
    if i930 is None or i < i930:
        return None
    tp = (C.h[i930:i + 1] + C.l[i930:i + 1] + C.c[i930:i + 1]) / 3.0
    v = C.v[i930:i + 1]
    return float((tp * v).sum() / v.sum()) if v.sum() > 0 else float(tp.mean())


def _h_htf(cx):
    C, s = cx["C"], cx["setup"]
    d, t = s["dir"], int(s["entry_t"])
    j1, jd = C.H1.at(t), C.D.at(t)
    h1 = int(C.H1.dir[j1]) if j1 >= 0 else 0
    dd = int(C.D.dir[jd]) if jd >= 0 else 0
    if h1 == d and dd != -d:
        return 1.0, f"with the 1H order flow (last 1H BOS {'up' if d > 0 else 'down'}), daily not against"
    if h1 == -d:
        return -1.0, f"against the 1H order flow (last 1H BOS {'down' if d > 0 else 'up'})"
    return 0.0, "1H structure neutral or daily opposed"


def _b1_state(C, k):
    if k < 2:
        return None
    Y, P = k - 1, k - 2
    H, L, Cl, O = C.D.H, C.D.L, C.D.C, C.D.O
    tol = max(0.05 * float(C.adr10[k]), 4.0)
    if Cl[Y] > H[P] + tol:
        return ("CONT_UP", 1, float(H[Y]), 1.0)
    if Cl[Y] < L[P] - tol:
        return ("CONT_DN", -1, float(L[Y]), 1.0)
    if H[Y] > H[P] and Cl[Y] <= H[P] and L[Y] >= L[P]:
        return ("REV_DN", -1, float(L[Y]), 0.5)
    if L[Y] < L[P] and Cl[Y] >= L[P] and H[Y] <= H[P]:
        return ("REV_UP", 1, float(H[Y]), 0.5)
    if H[Y] <= H[P] and L[Y] >= L[P]:
        return ("INSIDE_UP", 1, float(H[Y]), 0.5) if Cl[Y] > O[Y] else ("INSIDE_DN", -1, float(L[Y]), 0.5)
    return None


def _h_b1(cx):
    C, i, k, _ = _cx_refs(cx)
    s = cx["setup"]
    d = s["dir"]
    st = _b1_state(C, k)
    if st is None:
        return 0.0, "TTrades closure: no state (outside day)"
    name, side, tgt, w = st
    a = int(C.ds[k])
    hh, ll = C.h[a:i + 1], C.l[a:i + 1]
    opp = float(C.D.L[k - 1]) if side > 0 else float(C.D.H[k - 1])
    if side > 0:
        hit = np.flatnonzero(hh >= tgt)
        oppx = np.flatnonzero(ll <= opp - TICK)
    else:
        hit = np.flatnonzero(ll <= tgt)
        oppx = np.flatnonzero(hh >= opp + TICK)
    t_hit = int(hit[0]) if len(hit) else None
    t_opp = int(oppx[0]) if len(oppx) else None
    if t_opp is not None and (t_hit is None or t_opp < t_hit):
        return 0.0, f"TTrades {name} target {_px(tgt)} void (the opposite extreme traded first)"
    if t_hit is None:
        if d == side and (tgt - s["entry"]) * d > 0:
            return w, f"toward the TTrades {name} target {_px(tgt)} (still untaken)"
        return 0.0, f"TTrades {name} points the other way ({_px(tgt)}); not a veto"
    if d == side:
        return -1.0, f"the TTrades {name} target {_px(tgt)} is already hit: continuation needs a new draw"
    return 0.0, f"TTrades {name} target already delivered; reversal allowed"


def _h_oneside(cx):
    C, i, k, r = _cx_refs(cx)
    s = cx["setup"]
    if r["prth"] is None or r["i930"] is None or i < r["i930"]:
        return 0.0, "one-side rule n/a"
    pH, pL, _ = r["prth"]
    a = r["i930"]
    tH = bool(C.h[a:i + 1].max() >= pH + TICK)
    tL = bool(C.l[a:i + 1].min() <= pL - TICK)
    tg = s["targets"][-1] if s.get("targets") else None
    if tg is None or tH == tL:
        return 0.0, "one-side rule: " + ("both prior-RTH sides taken" if tH else "neither prior-RTH side taken yet")
    if tL and s["dir"] > 0 and tg >= pH:
        return -1.0, f"prior-RTH low already taken; targeting the prior-RTH high {_px(pH)} too (both sides only ~10%)"
    if tH and s["dir"] < 0 and tg <= pL:
        return -1.0, f"prior-RTH high already taken; targeting the prior-RTH low {_px(pL)} too (both sides only ~10%)"
    return 0.0, "one-side rule respected"


def _h_sides(cx):
    C, i, k, r = _cx_refs(cx)
    s = cx["setup"]
    d = s["dir"]
    if cx["mod_dec"] < 630 or r["o930"] is None or r["mo"] is None:
        return 0.0, "before 10:30: side-of-open rule not active"
    px = float(C.c[i])
    vw = _rvwap(C, r["i930"], i)
    smo, so, sv = np.sign(px - r["mo"]), np.sign(px - r["o930"]), (np.sign(px - vw) if vw is not None else 0)
    if smo == d and so == d and sv == d:
        return 1.0, "on the trade's side of the midnight open, the 09:30 open and VWAP"
    if smo == -d and so == -d:
        if "disp_atr" not in cx:
            _e_quality(cx)
        if s.get("sweep_label") and (cx.get("disp_atr") or 0) >= 1.0:
            return 0.0, "wrong side of both opens, but it is a named-pool sweep with displacement"
        return -1.0, "wrong side of both the midnight open and the 09:30 open after 10:30"
    return 0.0, "mixed side of the opens"


def _h_time(cx):
    m = cx["mod_dec"]
    if 570 <= m <= 585:
        cx["veto"] = cx.get("veto") or "first 15 minutes after the open (signal closes by 09:45)"
        return 0.0, f"{_hm(m)}: inside the first 15 minutes"
    if m > 930:
        cx["veto"] = cx.get("veto") or "after 15:30"
        return 0.0, f"{_hm(m)}: too late"
    if 590 <= m <= 660 or 810 <= m <= 900:
        return 1.0, f"{_hm(m)}: inside a killzone"
    if 690 < m < 810:
        return -1.0, f"{_hm(m)}: lunch hours"
    return 0.0, f"{_hm(m)}: neutral time"


def _ib(C, r, i):
    a = r["i930"]
    if a is None or i < a + 11 or a + 11 >= len(C.t) or C.di[a + 11] != C.di[a]:
        return None
    hh, ll = C.h[a:a + 12], C.l[a:a + 12]
    return {"H": float(hh.max()), "L": float(ll.min()), "close": float(C.c[a + 11]),
            "low_first": int(np.argmin(ll)) < int(np.argmax(hh)), "end": a + 11}


def _h_lunch(cx):
    C, i, k, r = _cx_refs(cx)
    m = cx["mod_dec"]
    if not (695 <= m <= 810):
        return 0.0, "not lunch"
    ib = _ib(C, r, i)
    ok = False
    if ib is not None:
        b = min(i, ib["end"] + 12)
        if b > ib["end"]:
            rng = ib["H"] - ib["L"]
            up = C.h[ib["end"] + 1:b + 1].max() - ib["H"] >= rng and C.l[ib["end"] + 1:b + 1].min() >= ib["L"]
            dn = ib["L"] - C.l[ib["end"] + 1:b + 1].min() >= rng and C.h[ib["end"] + 1:b + 1].max() <= ib["H"]
            ok = bool(up or dn)
    if ok:
        return 0.0, "lunch, but the IB extended one-sided (trend exception)"
    cx["veto"] = cx.get("veto") or "lunch chop (11:35-13:30)"
    return 0.0, "lunch chop"


def _h_disp(cx):
    C, s = cx["C"], cx["setup"]
    d, ie, idc = s["dir"], cx["i_ext"], cx["i_dec"]
    atr = max(float(C.atr5[idc]), TICK)
    o, h, l, c = C.o[ie:idc + 1], C.h[ie:idc + 1], C.l[ie:idc + 1], C.c[ie:idc + 1]
    body = (c - o) * d
    rng = np.maximum(h - l, TICK)
    a_ = bool(np.any((body > 0) & (body / rng >= 0.6)))
    span = (h.max() - C.l[ie]) if d > 0 else (C.h[ie] - l.min())
    b_ = bool(span >= 1.5 * atr)
    c_ = False
    for j in range(ie + 2, idc + 1):
        g = (C.l[j] - C.h[j - 2]) if d > 0 else (C.l[j - 2] - C.h[j])
        if g >= 0.2 * atr:
            c_ = True
            break
    j = ie
    while j > max(0, ie - 30) and (C.c[j] - C.o[j]) * d < 0:
        j -= 1
    ref = C.o[j + 1] if j < ie else C.o[ie]
    cisd = bool(np.any((C.c[ie + 1:idc + 1] - ref) * d > 0)) if idc > ie else False
    sw = np.flatnonzero((C.sh5 if d > 0 else C.sl5)[max(0, ie - 40):max(0, ie - 2)]) + max(0, ie - 40)
    bos = False
    if len(sw):
        lvl = C.h[sw[-1]] if d > 0 else C.l[sw[-1]]
        bos = bool(np.any((C.c[ie:idc + 1] - lvl) * d > 0))
    d_ = cisd or bos
    n = int(a_) + int(b_) + int(c_) + int(d_)
    sc = 1.0 if n == 4 else (0.0 if n == 3 else -1.0)
    stall = int(np.sum((np.diff(c) * d) <= 0)) if len(c) > 1 else 0
    why = f"displacement checks {n}/4 (body {'ok' if a_ else 'no'}, span {span / atr:.1f} ATR, FVG {'yes' if c_ else 'no'}, CISD/BOS {'yes' if d_ else 'no'})"
    if stall >= 3:
        sc = min(sc, -1.0)
        why += f"; choppy leg ({stall} no-progress closes)"
    return sc, why


def _h_smt(cx):
    if "smt" not in cx and "rs" not in cx:
        _e_intermarket(cx)
    if cx.get("smt") or (cx.get("rs") is not None and cx["rs"] > 0.02):
        return 1.0, ("SMT divergence" if cx.get("smt") else "NQ leading ES in the trade's direction")
    return 0.0, "no SMT / no relative strength (never a penalty)"


def _h_news(cx):
    n = cx["nar"]
    m = cx["mod_dec"]
    day = n.get("day") or cx["C"].days[int(cx["C"].di[cx["i_dec"]])]
    ev = news_on(day)
    for em, e, imp in ev:
        if imp == "high" and -10 <= em - m <= 15:
            cx["veto"] = cx.get("veto") or f"{e} at {_hm(em)} is too close"
    t1_830 = any(em == 510 and imp == "high" for em, e, imp in ev)
    fomc = any("FOMC" in e and "inute" not in e and imp == "high" for em, e, imp in ev)
    minutes = any("inute" in e for em, e, imp in ev)
    ten = any(em == 600 for em, e, imp in ev)
    if t1_830 and m <= 585:
        cx["veto"] = cx.get("veto") or "08:30 release day: no entries before 09:45"
    if fomc and 780 <= m <= 880:
        cx["veto"] = cx.get("veto") or "FOMC window 13:00-14:40"
    if minutes and 835 <= m <= 855:
        cx["veto"] = cx.get("veto") or "FOMC minutes window 13:55-14:15"
    if ten and m == 605:
        cx["veto"] = cx.get("veto") or "the 10:00 release bar is never a signal bar"
    if n["news"]["fomc"] or n["news"]["cpi_nfp"]:
        return -1.0, "FOMC day" if n["news"]["fomc"] else "CPI/NFP day"
    return 0.0, "no tier-1 news"


def _h_room(cx):
    s, n = cx["setup"], cx["nar"]
    tg = s["targets"][-1] if s.get("targets") else None
    if tg is None:
        return 0.0, "no target"
    dist = abs(tg - s["entry"])
    if dist <= n["reach_now"]:
        return 0.5, f"target {dist:.0f} pts away is inside the {n['reach_now']:.0f}-pt range left"
    return -1.0, f"target {dist:.0f} pts away is beyond the {n['reach_now']:.0f}-pt range left"


_B2W = {"PWH": 2, "PWL": 2, "PDH": 1, "PDL": 1, "RTH-H": 1, "RTH-L": 1, "D1SW-H": 1, "D1SW-L": 1, "ASIA-H": 0.5, "ASIA-L": 0.5,
        "LON-H": 0.5, "LON-L": 0.5, "ATM-H": 0.5, "ATM-L": 0.5, "ON-H": 0.5, "ON-L": 0.5, "H4SW-H": 0.5, "H4SW-L": 0.5,
        "EQH": 1.0, "EQL": 1.0}


def _h_draw(cx):
    C, i = cx["C"], cx["i_dec"]
    s = cx["setup"]
    k = int(C.di[i])
    adr = max(float(C.adr10[k]), TICK)
    px = float(C.c[i])
    best = {1: None, -1: None}
    for p in pools(C, i):
        if p["taken"] or p["name"] not in _B2W:
            continue
        dist = (p["price"] - px) * p["side"]
        if not (0.25 * adr <= dist <= 1.5 * adr):
            continue
        sc = _B2W[p["name"]] - dist / adr
        if best[p["side"]] is None or sc > best[p["side"]][0]:
            best[p["side"]] = (sc, p)
    if best[1] is None and best[-1] is None:
        return 0.0, "no draw within 0.25-1.5 ADR"
    if best[1] is not None and best[-1] is not None and abs(best[1][0] - best[-1][0]) < 0.5:
        return -1.0, f"two-sided: {NICE.get(best[1][1]['name'])} vs {NICE.get(best[-1][1]['name'])} pull equally"
    side = 1 if (best[-1] is None or (best[1] is not None and best[1][0] > best[-1][0])) else -1
    p = best[side][1]
    if s["dir"] == side:
        return 1.0, f"toward the primary draw ({NICE.get(p['name'], p['name'])} {_px(p['price'])})"
    return -1.0, f"against the primary draw ({NICE.get(p['name'], p['name'])} {_px(p['price'])})"


def _od(C, r, adr):
    a = r["i930"]
    if a is None or a + 5 >= len(C.t) or C.di[a + 5] != C.di[a]:
        return 0
    O = r["o930"]
    hh, ll, cc = C.h[a:a + 6], C.l[a:a + 6], C.c[a + 5]
    e = 0.05 * adr
    rng = max(hh.max() - ll.min(), TICK)
    xo = bool(np.any((hh[2:] >= O) & (ll[2:] <= O)))
    if O - ll.min() <= e and cc - O >= 0.20 * adr and (cc - ll.min()) / rng >= 0.70 and not xo:
        return 1
    if hh.max() - O <= e and O - cc >= 0.20 * adr and (hh.max() - cc) / rng >= 0.70 and not xo:
        return -1
    return 0


def _h_od(cx):
    C, i, k, r = _cx_refs(cx)
    if cx["mod_dec"] < 600:
        return 0.0, "open type not known before 10:00"
    od = _od(C, r, float(C.adr10[k]))
    if od == 0:
        return 0.0, "no open drive"
    if od == cx["setup"]["dir"]:
        return 1.0, f"with the open drive ({'up' if od > 0 else 'down'})"
    cx["veto"] = cx.get("veto") or f"fading an open-drive day ({'up' if od > 0 else 'down'})"
    return 0.0, "fading an open drive"


def _h_ib(cx):
    C, i, k, r = _cx_refs(cx)
    if cx["mod_dec"] < 630:
        return 0.0, "IB not complete"
    ib = _ib(C, r, i)
    if ib is None:
        return 0.0, "IB n/a"
    mid = 0.5 * (ib["H"] + ib["L"])
    if ib["close"] > mid:
        b, w = 1, (1.0 if ib["low_first"] else 0.5)
    elif ib["close"] < mid:
        b, w = -1, (1.0 if not ib["low_first"] else 0.5)
    else:
        return 0.0, "IB closed at its mid"
    if cx["setup"]["dir"] == b:
        return w, f"with the IB bias ({'up' if b > 0 else 'down'}, {'strong' if w == 1.0 else 'weak'})"
    return 0.0, f"against the IB bias ({'up' if b > 0 else 'down'}); not penalized"


def _h_gap(cx):
    C, i, k, r = _cx_refs(cx)
    s = cx["setup"]
    if r["o930"] is None or r["prth"] is None or r["i930"] is None or i < r["i930"]:
        return 0.0, "gap n/a"
    pH, pL, pC = r["prth"]
    gap = r["o930"] - pC
    if gap == 0:
        return 0.0, "no gap"
    gA = abs(gap) / max(float(C.adr10[k]), TICK)
    fade = s["dir"] == -int(np.sign(gap))
    a = r["i930"]
    filled = bool(C.l[a:i + 1].min() <= pC) if gap > 0 else bool(C.h[a:i + 1].max() >= pC)
    large = gA >= 0.35 or r["o930"] > pH or r["o930"] < pL
    if gA < 0.2 and not large:
        if fade and cx["mod_dec"] < 630 and not filled:
            return 1.0, f"small gap ({gA:.2f} ADR): fading toward yesterday's close {_px(pC)}"
        return 0.0, f"small gap ({gA:.2f} ADR)"
    if large:
        if fade:
            j = np.arange(a, i + 1)
            m30 = ((C.mod[j] + 5) % 30) == 0
            back = bool(np.any((C.c[j][m30] <= pH) & (C.c[j][m30] >= pL)))
            if not back:
                return -1.0, f"fading a large gap ({gA:.2f} ADR) before a 30-min close back inside yesterday's range"
            return 0.0, "large gap, but a 30-min close is back inside yesterday's range"
        return 1.0, f"with the large gap ({gA:.2f} ADR): gap-and-go"
    return 0.0, f"medium gap ({gA:.2f} ADR): wait for acceptance"


def _h_10am(cx):
    C, i, k, r = _cx_refs(cx)
    s = cx["setup"]
    m = cx["mod_dec"]
    a = r["i930"]
    if not (590 <= m <= 630) or a is None or a + 6 >= len(C.t):
        return 0.0, "not a 10 AM reversal window"
    me = int(C.mod[cx["i_ext"]])
    if not (590 <= me <= 620):
        return 0.0, "raid not in 09:50-10:20"
    mv = int(np.sign(C.c[a + 5] - r["o930"]))
    if mv == 0 or s["dir"] != -mv:
        return 0.0, "not a reversal of the opening move"
    hh, ll = C.h[a:a + 6], C.l[a:a + 6]
    took = (C.h[cx["i_ext"]] > hh.max()) if mv > 0 else (C.l[cx["i_ext"]] < ll.min())
    rng = max(hh.max() - ll.min(), TICK)
    cl = (C.c[a + 5] - ll.min()) / rng
    b10 = (C.c[a + 6] - C.o[a + 6]) * mv
    power = ((cl >= 0.9) if mv > 0 else (cl <= 0.1)) and b10 >= 1.0 * C.atr5[a + 6] and abs(C.c[a + 6] - C.o[a + 6]) >= 0.6 * max(C.h[a + 6] - C.l[a + 6], TICK)
    if took and not power:
        return 1.0, "10 AM reversal: swept the opening-range extreme and reclaimed"
    return 0.0, "no 10 AM reversal"


def _h_obst(cx):
    C, s = cx["C"], cx["setup"]
    i, d, E = cx["i_dec"], s["dir"], float(s["entry"])
    R = max(abs(E - float(s["stop"])), TICK)
    atr = float(C.atr5[i])
    tol = max(2 * TICK, 0.1 * atr)
    cand = [px for px in swings5(C, i, d, days=1)]
    cand += [(g["bottom"] if d > 0 else g["top"]) for g in live_gaps(C, i, -d, kinds=("15m",))]
    cand += [p["price"] for p in pools(C, i) if p["side"] == d and not p["taken"]]
    dist = [(px - E) * d for px in cand if (px - E) * d > tol]
    if not dist:
        return 1.0, "open air to the first obstacle"
    room = min(dist) / R
    cx["room_r"] = round(room, 2)
    if room < 1.0:
        return -1.5, f"first obstacle only {room:.1f}R away"
    if room < 2.0:
        return -1.0, f"first obstacle {room:.1f}R away"
    if room >= 3.0:
        return 1.0, f"{room:.1f}R of room to the first obstacle"
    return 0.0, f"{room:.1f}R of room to the first obstacle"


V2_LIST = [("H1_htf", _h_htf, "1H order flow (B6)"), ("H2_b1", _h_b1, "TTrades draw (B1)"),
           ("H3_oneside", _h_oneside, "one-side rule (B3)"), ("H4_sides", _h_sides, "side of the opens (T7)"),
           ("E2_manip", _e_manip, LABEL["E2_manip"]), ("E3_location", _e_location, LABEL["E3_location"]),
           ("H5_time", _h_time, "killzone / first 15 min (G4, N5)"), ("H6_lunch", _h_lunch, "lunch veto (S4)"),
           ("H7_disp", _h_disp, "displacement checks (G2)"), ("H8_smt", _h_smt, "SMT / strength (G3)"),
           ("H9_news", _h_news, "news windows (S6)"), ("H10_room", _h_room, "room in the day's range"),
           ("H11_draw", _h_draw, "primary draw (B2)"), ("H12_od", _h_od, "open drive (T1)"),
           ("H13_ib", _h_ib, "IB side (T3)"), ("H14_gap", _h_gap, "gap fill/go (T6)"),
           ("H15_10am", _h_10am, "10 AM reversal (S1)"), ("H16_obst", _h_obst, "room to first obstacle (N2)"),
           ("E10_po3", _e_po3, LABEL["E10_po3"])]


def enable_v2():
    """Register the v2 trader heuristics (NARRATIVE_RULES.md section 7) as version 'v2'."""
    VERSIONS["v2"] = []
    for eid, fn, lab in V2_LIST:
        ELEMENTS[eid] = fn
        LABEL[eid] = lab
        VERSIONS["v2"].append(eid)
    return VERSIONS["v2"]


# ------------------------------------------------------------------------------------------------ helpers for callers
def infer_setup(bars5, entry_t, d, risk_pts, rr_plan=None, trigger="", fill_bar=True):
    """Rebuild a setup dict from an engine trade (entry_t = fill bar open; fill = open + 1 tick; stop = fill - d*risk)."""
    C = ctx(bars5)
    i_fill = int(np.searchsorted(C.t, int(entry_t)))
    entry = float(C.o[min(i_fill, len(C.o) - 1)] + d * TICK) if fill_bar else None
    stop = entry - d * float(risk_pts)
    i_dec = i_fill - 1
    sw = infer_sweep(C, i_dec, d)
    tg = [entry + d * float(rr_plan) * float(risk_pts)] if rr_plan else []
    return {"entry_t": int(entry_t), "dir": int(d), "entry": entry, "stop": stop, "sweep_level": sw["sweep_level"],
            "sweep_label": sw["sweep_label"], "sweep_t": sw["sweep_t"], "sweep_extreme": sw["sweep_extreme"],
            "trigger_tf": "5m", "trigger": trigger, "targets": tg, "model": "engine"}


def infer_sweep(C, i_dec, d):
    """The raid extreme (last 36 closed bars, today only) and the most significant pool its final leg took."""
    if not isinstance(C, Ctx):
        C = ctx(C)
    a = max(0, i_dec - 35)
    k = int(C.di[i_dec])
    a = max(a, C.ds[max(0, k)] - 0)
    seg = C.l[a:i_dec + 1] if d > 0 else -C.h[a:i_dec + 1]
    ie = a + int(np.argmin(seg))
    ext = float(C.l[ie] if d > 0 else C.h[ie])
    s_ = max(0, ie - 6)
    lab, lvl = None, None
    best = -1
    # pools known just before the extreme bar that were still untaken 30 min before it and were taken by the final leg
    for p in pools(C, max(0, ie - 1), int(C.t[ie])):
        if p["side"] != -d:
            continue
        if p["avail"] <= s_ and C.taken(-d, p["price"], p["avail"], s_):
            continue
        if (ext - p["price"]) * d <= -TICK and C.taken(-d, p["price"], max(p["avail"], s_ + 1), ie):
            sc = p["sig"] - 1e-6 * abs(p["price"] - ext)
            if sc > best:
                best, lab, lvl = sc, p["name"], p["price"]

    return {"sweep_level": lvl, "sweep_label": lab, "sweep_t": int(C.t[ie]), "sweep_extreme": ext}


def default_target(C, i_dec, d, entry, risk):
    """Generic setups without a target: nearest untaken Tier-A pool >= 1R in the trade direction, else entry + 2R."""
    best = None
    for p in pools(C, i_dec):
        if p["side"] == d and not p["taken"] and p["name"] in TIER_A:
            dist = (p["price"] - entry) * d
            if dist >= risk and (best is None or dist < best):
                best = dist
    return float(entry + d * (best if best is not None else 2.0 * risk))
