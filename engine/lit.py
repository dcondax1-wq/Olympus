"""LIT (Liquidity Inducement Theorem) research strategy, built from CME NQ1! 5m OHLCV (data/NQ_5m.csv) + VIX/VXN daily.

Research only: the live Liquidity Engine (engine/model.py, live_model.json) is not touched or imported for trading.
Every value below is known at the close of the bar it is attached to (no look-ahead):
  * session boxes are levels only after the box's last bar closed;
  * fractal swings (k=2) count only 2 bars after the swing bar;
  * PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG, VIX move are known at the start of the trading day (18:00 ET);
  * HTF opens (1H/4H/18:00/00:00/08:30/09:30/10:00/weekly) exist only from their own bar on.

Components (all times America/New_York, trading day = 18:00 -> 17:00):
  SESSIONS            Asia / London / NY trap boxes and premarket, several common definitions (see SESSIONS)
  day_context()       PDH/PDL, PWH/PWL, PMH/PML, NWOG, NDOG, VIX/VXN implied one-day move, day/week opens, weekday
  opens()             HTF opens per bar (PO3 reference: 1H, 4H from 18:00, daily 18:00, midnight, 08:30, 09:30, 10:00, weekly)
  vectors()           PVSRA vector candles: climax (vol >= 2x avg10 or vol*range >= max of prior 10), above average (>= 1.5x)
  fractals()          k=2 swing highs/lows
  buildups()          build-up liquidity: equal-ish highs/lows (2 fractals within tol, untouched between them)
  in_how_window()     high/low-of-week window: Tuesday 03:00 (London) -> Wednesday 11:30 (AM close)
  candidates()        LIT setups: inducement taken -> sweep of liquidity -> displacement -> structure shift, with every
                      confluence recorded as a feature so variants can be filtered after the fact
  simulate()          executor: entry next bar open + 1 tick, stop beyond the protected low/high + buffer, size $800 up to a
                      20-pt stop then 800*20/stop, MNQ $2/pt, max 40 micros, $1.40 per micro round trip, BE / time stop options
  run()               first qualifying candidate per day (max trades/day option), returns trade dicts in runlib format
"""
from __future__ import annotations

import bisect
import collections
import math
import os

import numpy as np
import pandas as pd

from engine.data import DATA_DIR, load

TICK, PV, COMM, SLIP, MAX_MICROS = 0.25, 2.0, 1.40, 0.25, 40

# name: (start ET minute, end ET minute exclusive). end <= start means "until midnight" (inside the 18:00 trading day).
SESSIONS = {
    "asia20": (1200, 1440),     # 20:00-00:00 (common LIT / TTrades Asia range)
    "asia18": (1080, 1440),     # 18:00-00:00 (futures Globex open to midnight)
    "asia19": (1140, 1440),     # 19:00-00:00 (Tokyo open)
    "lon25": (120, 300),        # London killzone 02:00-05:00
    "lon34": (180, 240),        # London-open 1-hour inducement window 03:00-04:00 (Reimfx "LIT - Timing" style)
    "lon23": (120, 180),        # Frankfurt hour 02:00-03:00
    "ny89": (480, 540),         # NY-open 1-hour inducement window 08:00-09:00 (forex NY open)
    "ny830": (510, 570),        # 08:30-09:30 (data hour -> cash open "trap")
    "ny930": (570, 600),        # 09:30-10:00 opening-range trap
    "ny9301030": (570, 630),    # 09:30-10:30 first RTH hour
    "pre": (240, 570),          # premarket 04:00-09:30
}
SESSION_CLASS = {k: ("asia" if k.startswith("asia") else "london" if k.startswith("lon") else "pre" if k == "pre" else "ny") for k in SESSIONS}
# Opt-in extra boxes (Market(extra_boxes=[...])): their own class, so lit_A (no extras) is unchanged.
EXTRA_BOXES = {
    "ny8_830": (480, 510, "x_ny"),   # NY open range 08:00-08:30 (ICT), the LIT sessions study's pick
}
DAILY = ("pd", "pw", "pm")      # previous day / week / month


# ------------------------------------------------------------------------------------------------ bar components
def atr(h, l, c, n=14):
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    out = np.empty_like(tr)
    out[0] = tr[0]
    a = 1.0 / n
    for i in range(1, len(tr)):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def vectors(o, h, l, c, v, n=10):
    """PVSRA: climax = vol >= 200% of the prior-10 average OR vol*spread >= the highest vol*spread of the prior 10;
    above = vol >= 150% of the average. Returns (climax bool, above bool, bull bool)."""
    s = pd.Series(v)
    avg = s.shift(1).rolling(n, min_periods=n).mean().values
    vs = pd.Series(v * (h - l))
    mx = vs.shift(1).rolling(n, min_periods=n).max().values
    with np.errstate(invalid="ignore"):
        climax = (v >= 2.0 * avg) | (v * (h - l) >= mx)
        above = (v >= 1.5 * avg) & ~climax
    return np.nan_to_num(climax).astype(bool), np.nan_to_num(above).astype(bool), c > o


def fractals(h, l, k=2):
    """Swing high at j: h[j] > the k highs before and >= the k after (confirmed at j+k). Same for lows."""
    n = len(h)
    fh = np.zeros(n, bool); fl = np.zeros(n, bool)
    for j in range(k, n - k):
        if h[j] > h[j - k:j].max() and h[j] >= h[j + 1:j + k + 1].max():
            fh[j] = True
        if l[j] < l[j - k:j].min() and l[j] <= l[j + 1:j + k + 1].min():
            fl[j] = True
    return np.flatnonzero(fh), np.flatnonzero(fl)


def buildups(h, l, fh, fl, at, tol_atr=0.15, tol_min=1.5, lookback=288, k=2):
    """Build-up liquidity: two fractal lows within tol of each other (tol = max(tol_min, tol_atr*ATR)), at least 3 bars
    apart, with every bar between them above the lower one (price came back to the same level and held). Level = the lower
    low (sell-side resting liquidity); known when the second fractal confirms (j+k). Mirror for highs.
    Returns list of (side, price, known_index)."""
    out = []
    for side, idx, arr in (("low", fl, l), ("high", fh, h)):
        recent = collections.deque()
        for j in idx:
            while recent and j - recent[0] > lookback:
                recent.popleft()
            tol = max(tol_min, tol_atr * at[j])
            for kk in reversed(recent):
                if j - kk < 3 or abs(arr[j] - arr[kk]) > tol:
                    continue
                if side == "low":
                    lev = min(arr[j], arr[kk])
                    if l[kk + 1:j].min() > lev:
                        out.append(("low", float(lev), int(j + k))); break
                else:
                    lev = max(arr[j], arr[kk])
                    if h[kk + 1:j].max() < lev:
                        out.append(("high", float(lev), int(j + k))); break
            recent.append(j)
    out.sort(key=lambda x: x[2])
    return out


def in_how_window(dow, mod):
    """High/low-of-the-week window: Tuesday 03:00 ET (London) -> Wednesday 11:30 ET (AM close). dow = trading-day weekday
    (the Wednesday trading day starts Tuesday 18:00)."""
    return ((dow == 1) & (mod >= 180) & (mod < 1080)) | ((dow == 2) & ((mod >= 1080) | (mod <= 690)))


_VIX_CACHE: dict = {}


def _vix(name="VIX"):
    """(dates, closes) of data/<name>_1d.csv, cached by file time. The live bot rewrites the file while it runs
    (engine/news.volatility); a read that catches it half-written falls back to the last good copy (or retries)."""
    path = os.path.join(DATA_DIR, f"{name}_1d.csv")
    for attempt in range(3):
        try:
            mt = os.path.getmtime(path)
            hit = _VIX_CACHE.get(name)
            if hit and hit[0] == mt:
                return hit[1]
            df = pd.read_csv(path)
            out = (list(df["date"].astype(str)), df["close"].values.astype(float))
            if not len(out[0]):
                raise ValueError("empty")
            _VIX_CACHE[name] = (mt, out)
            return out
        except Exception:
            if name in _VIX_CACHE:
                return _VIX_CACHE[name][1]
            import time as _t
            _t.sleep(0.5)
    df = pd.read_csv(path)
    return list(df["date"].astype(str)), df["close"].values.astype(float)


# ------------------------------------------------------------------------------------------------ market (all components)
class Market:
    """All LIT components for the whole NQ 5m history, computed once."""

    def __init__(self, tol_atr=0.15, extra_boxes=None, bars=None):
        """bars: an engine.data.Bars 5m window (the live loop, engine/lit_live.py); None = the whole data/NQ_5m.csv."""
        self.extra = {nm: EXTRA_BOXES[nm] for nm in (extra_boxes or ())}
        b = bars if bars is not None else load("NQ", "5m")
        self.b = b
        self.t, self.o, self.h, self.l, self.c, self.v = b.t, b.o, b.h, b.l, b.c, b.v
        self.mod, self.dow = b.mod, b.dow
        self.dates = np.array(b.date_str)
        n = len(b)
        self.n = n
        self.atr = atr(self.h, self.l, self.c)
        self.climax, self.above, self.bull = vectors(self.o, self.h, self.l, self.c, self.v)
        self.fh, self.fl = fractals(self.h, self.l)
        self.bu = buildups(self.h, self.l, self.fh, self.fl, self.atr, tol_atr=tol_atr)
        self._bu_known = [z[2] for z in self.bu]
        self.how = in_how_window(self.dow, self.mod)
        # trading days
        td = b.tday
        starts = np.r_[0, np.flatnonzero(np.diff(td)) + 1]
        ends = np.r_[starts[1:], n]
        self.days = [(self.dates[s], int(s), int(e)) for s, e in zip(starts, ends)]
        self.day_of = np.repeat(np.arange(len(starts)), ends - starts)
        self._opens()
        self._context()

    # ---- HTF opens per bar (PO3 reference)
    def _opens(self):
        n, mod, o = self.n, self.mod, self.o
        di = self.day_of
        # 1H: clock hour bucket (ET offsets are whole hours, so UTC hour buckets = ET hour buckets)
        hb = self.t // 3600
        self.open_1h = _ffill_group(o, hb)
        # 4H aligned to 18:00 ET: 18,22,02,06,10,14
        rel = (mod - 1080) % 1440
        b4 = di.astype(np.int64) * 10 + rel // 240
        self.open_4h = _ffill_group(o, b4)
        self.open_d = _ffill_group(o, di)
        # intraday anchored opens: value from that bar on within the day, nan before
        self.open_00 = _anchor(o, di, mod, 0)
        self.open_830 = _anchor(o, di, mod, 510)
        self.open_930 = _anchor(o, di, mod, 570)
        self.open_1000 = _anchor(o, di, mod, 600)
        self.open_22 = _anchor(o, di, mod, 1320)
        # weekly open: first bar of the trading week (ISO week of the trading date)
        dts = pd.to_datetime(self.dates)
        iso = dts.isocalendar()
        self.week_id = (iso["year"].values.astype(np.int64) * 100 + iso["week"].values.astype(np.int64))
        self.open_wk = _ffill_group(o, self.week_id)
        self.month_id = (dts.year.values * 100 + dts.month.values).astype(np.int64)

    # ---- per-day context
    def _context(self):
        h, l, o, c, mod = self.h, self.l, self.o, self.c, self.mod
        vd, vc = _vix("VIX")
        xd, xc = _vix("VXN")
        ctx = []
        prev = None
        wk_hl, mo_hl = {}, {}
        for d, s, e in self.days:
            wk_hl.setdefault(int(self.week_id[s]), [np.inf, -np.inf, s, e])
            w = wk_hl[int(self.week_id[s])]; w[0] = min(w[0], l[s:e].min()); w[1] = max(w[1], h[s:e].max()); w[3] = e
            mo_hl.setdefault(int(self.month_id[s]), [np.inf, -np.inf])
            m = mo_hl[int(self.month_id[s])]; m[0] = min(m[0], l[s:e].min()); m[1] = max(m[1], h[s:e].max())
        wks = sorted(wk_hl); mos = sorted(mo_hl)
        for k, (d, s, e) in enumerate(self.days):
            x = {"date": d, "s": s, "e": e, "dow": int(self.dow[s]), "open18": float(o[s])}
            if prev is not None:
                ps, pe = prev
                x["pdh"], x["pdl"] = float(h[ps:pe].max()), float(l[ps:pe].min())
                g = sorted([float(c[pe - 1]), float(o[s])])
                x["ndog"] = g if g[1] - g[0] >= TICK else None
            wid = int(self.week_id[s]); wi = wks.index(wid)
            if wi > 0:
                pw = wk_hl[wks[wi - 1]]
                x["pwh"], x["pwl"] = float(pw[1]), float(pw[0])
                first_of_week = s == wk_hl[wid][2]
                g = sorted([float(c[pw[3] - 1]), float(o[wk_hl[wid][2]])])
                x["nwog"] = g if g[1] - g[0] >= TICK else None
                x["first_of_week"] = first_of_week
            mid = int(self.month_id[s]); mi = mos.index(mid)
            if mi > 0:
                pm = mo_hl[mos[mi - 1]]
                x["pmh"], x["pml"] = float(pm[1]), float(pm[0])
            for nm, (dd, cc) in (("vix", (vd, vc)), ("vxn", (xd, xc))):
                j = bisect.bisect_left(dd, d) - 1
                if j >= 0:
                    x[nm] = float(cc[j])
                    x[nm + "_move"] = float(cc[j]) / 100.0 / math.sqrt(252.0) * float(o[s])
            # session boxes
            md = mod[s:e]
            for nm, (a, z) in list(SESSIONS.items()) + [(k, v[:2]) for k, v in self.extra.items()]:
                ii = np.flatnonzero((md >= a) & (md < z)) if a < z else np.flatnonzero(md >= a)
                if a >= 1080:   # evening box: only bars before midnight inside this trading day
                    ii = ii[md[ii] >= 1080]
                else:
                    ii = ii[md[ii] < 1080]
                if len(ii) >= 2:
                    x[nm] = (float(h[s + ii].max()), float(l[s + ii].min()), int(s + ii[-1]))
            ctx.append(x)
            prev = (s, e)
        self.ctx = ctx

    # ---- levels of one day (side, price, known_index, name, cls)
    def levels(self, k):
        x = self.ctx[k]; s, e = x["s"], x["e"]
        L = []
        for nm in SESSIONS:
            if nm in x:
                hi, lo, ki = x[nm]
                L.append(("high", hi, ki, nm + "_h", SESSION_CLASS[nm])); L.append(("low", lo, ki, nm + "_l", SESSION_CLASS[nm]))
        for nm, (_a, _z, cls) in self.extra.items():
            if nm in x:
                hi, lo, ki = x[nm]
                L.append(("high", hi, ki, nm + "_h", cls)); L.append(("low", lo, ki, nm + "_l", cls))
        for p in DAILY:
            if p + "h" in x:
                L.append(("high", x[p + "h"], s - 1, p + "h", p)); L.append(("low", x[p + "l"], s - 1, p + "l", p))
        for g in ("nwog", "ndog"):
            if x.get(g):
                for px in x[g]:
                    L.append(("high" if px > self.o[s] else "low", float(px), s - 1, g, "gap"))
        lo_i = bisect.bisect_left(self._bu_known, s - 576)
        hi_i = bisect.bisect_left(self._bu_known, e)
        for side, px, ki in self.bu[lo_i:hi_i]:
            L.append((side, px, ki, "bu_" + side[0], "buildup"))
        return L


def _ffill_group(o, g):
    g = np.asarray(g)
    first = np.r_[True, g[1:] != g[:-1]]
    idx = np.where(first, np.arange(len(o)), 0)
    np.maximum.accumulate(idx, out=idx)
    return o[idx]


def _anchor(o, di, mod, at):
    """Open of the first bar at/after ET minute `at` inside each trading day (evening anchors >= 1080), nan before."""
    n = len(o)
    out = np.full(n, np.nan)
    evening = at >= 1080
    cond = (mod >= at) if evening else ((mod >= at) & (mod < 1080))
    cur_day, val = -1, np.nan
    for i in range(n):
        if di[i] != cur_day:
            cur_day, val = di[i], np.nan
        if np.isnan(val) and cond[i]:
            val = o[i]
        out[i] = val
    return out


# ------------------------------------------------------------------------------------------------ setup detector
def _first_breach(lo_d, start, end, lev):
    """First index in (start, end) where the direction-space low trades below lev; end if none."""
    if start + 1 >= end:
        return end
    seg = lo_d[start + 1:end] < lev
    j = int(np.argmax(seg))
    return start + 1 + j if seg[j] else end


def _cisd_level(c_d, o_d, ee, back=3):
    """CISD (TTrades): open of the first bar of the last unbroken run of down-close bars into the extreme (direction space).
    Returns (level, first_bar) or None. (From tools/lit_entry.py.)"""
    j = ee
    while j > ee - back and not (c_d[j] < o_d[j]):
        j -= 1
    if not (c_d[j] < o_d[j]):
        return None
    st = j
    while st - 1 >= 0 and c_d[st - 1] < o_d[st - 1] and st > ee - 30:
        st -= 1
    return float(o_d[st]), st


def candidates(M: Market, leg=24, sweep_win=24, ref_back=36, ind_back=36, t_from=60, t_to=955, ref="frac"):
    """Every LIT setup on every day, both directions. Long (mirror for shorts):
      1. sweep:      a known low-side liquidity level (session box, PDL/PWL/PML, gap edge, build-up lows) is breached for the
                     first time within `sweep_win` bars before the leg's extreme (the lowest low of the last `leg` bars)
      2. inducement: minor fractal lows ABOVE the swept level, formed in the `ind_back` bars before the sweep and taken out
                     before/at the sweep bar (early buyers trapped) -> feature ind_n (count)
      3. displacement + structure shift: the trigger bar closes above the last confirmed fractal high before the extreme
                     (the protected low = the extreme), first close above it -> feature disp (max body / ATR between
                     extreme and trigger), vec (a climax vector candle in the trade's direction), vec_any (climax or above)
      4. entry next bar open; stop beyond the protected low; targets = unbroken levels beyond the entry, per class.
    Trigger bars between ET minute t_from and t_to (entry-window filters are applied later).
    ref = the structure-shift level: "frac" (last 5m fractal high before the extreme, lit_A) or "cisd" (open of the last run
    of down-close bars into the extreme, TTrades CISD; the LIT entry study's pick).
    Extra features for run_x (ignored by run): sw {level name: price}, atr_ext, idm_a [(dist ATR, age bars)], nwog_side,
    ndog_side, mw_break (see _week_context)."""
    o, h, l, c, mod, at = M.o, M.h, M.l, M.c, M.mod, M.atr
    out = []
    for k, (date, s, e) in enumerate(M.days):
        x = M.ctx[k]
        if "pdh" not in x or e - s < 50:
            continue
        L = M.levels(k)
        for d in (1, -1):
            if d == 1:
                hi_d, lo_d, c_d, o_d = h, l, c, o
                swing_hi, swing_lo = M.fh, M.fl
            else:
                hi_d, lo_d, c_d, o_d = -l, -h, -c, -o
                swing_hi, swing_lo = M.fl, M.fh
            liq = [(px * d, ki, nm, cls) for side, px, ki, nm, cls in L if (side == "low") == (d == 1)]
            tgt = [(px * d, ki, nm, cls) for side, px, ki, nm, cls in L if (side == "high") == (d == 1)]
            seg_end = e
            # first breach of every liquidity level (direction space) and every target level (other side, as a touch)
            fb = [_first_breach(lo_d, max(ki, s - 600), seg_end, p) for p, ki, nm, cls in liq]
            tb = []
            for p, ki, nm, cls in tgt:
                st = max(ki, s - 600)
                seg = hi_d[st + 1:seg_end] >= p
                j = int(np.argmax(seg)) if len(seg) else 0
                tb.append(st + 1 + j if len(seg) and seg[j] else seg_end)
            last_e = -1
            for i in range(s + leg, e - 1):
                if not (t_from <= mod[i] < t_to) or mod[i] >= 1080:
                    continue
                a = i - leg
                ee = a + int(np.argmin(lo_d[a:i + 1]))
                if ee == i or ee == last_e:
                    continue
                if ref == "frac":
                    jj = bisect.bisect_left(swing_hi, ee) - 1
                    if jj < 0 or swing_hi[jj] < ee - ref_back:
                        continue
                    j = int(swing_hi[jj]); rp = float(hi_d[j])
                elif ref == "cisd":
                    cz = _cisd_level(c_d, o_d, ee)
                    if cz is None:
                        continue
                    rp, j = cz
                else:
                    raise ValueError(ref)
                if not (c_d[i] > rp and c_d[ee:i].max() <= rp):
                    continue
                ext = float(lo_d[ee])
                swept = [(liq[q], fb[q]) for q in range(len(liq)) if liq[q][1] < ee and ee - sweep_win <= fb[q] <= ee and ext < liq[q][0]]
                if not swept:
                    continue
                last_e = ee
                sb = min(z[1] for z in swept)
                lev_near = max(z[0][0] for z in swept)          # nearest swept level (direction space)
                # inducement: fractal lows above the swept level taken before the sweep bar
                ind_n = 0
                lo_i = bisect.bisect_left(swing_lo, sb - ind_back)
                for m in swing_lo[lo_i:bisect.bisect_left(swing_lo, sb)]:
                    m = int(m)
                    if m + 2 <= sb and lo_d[m] > lev_near and lo_d[m + 1:sb + 1].min() < lo_d[m]:
                        ind_n += 1
                # I-a inducement (tools/lit_entry.py): fractal lows above the swept level, untouched until the final run (from the
                # leg's swing high to the extreme) takes them -> (distance above the level in ATR, age in bars before the sweep)
                idm_a = []
                leg_top = int(ee - np.argmax(hi_d[max(ee - ref_back, s - 600):ee + 1][::-1])) if ee > s else ee
                lo_i2 = bisect.bisect_left(swing_lo, sb - 72)
                for m in swing_lo[lo_i2:bisect.bisect_left(swing_lo, ee)]:
                    m = int(m)
                    if lo_d[m] <= lev_near:
                        continue
                    sg = lo_d[m + 1:ee + 1] < lo_d[m]
                    if not sg.any():
                        continue
                    tk = m + 1 + int(np.argmax(sg))
                    if tk < max(leg_top, m + 3) or tk > ee:
                        continue
                    idm_a.append((round((lo_d[m] - lev_near) / max(at[sb], 1e-9), 3), int(sb - m)))
                sw = {}
                for zq in swept:
                    p_, nm_ = zq[0][0], zq[0][2]
                    if nm_ not in sw or p_ > sw[nm_]:
                        sw[nm_] = p_
                body = (c_d[ee:i + 1] - o_d[ee:i + 1]) / np.maximum(at[ee:i + 1], 1e-9)
                dir_bull = (c_d[ee + 1:i + 1] > o_d[ee + 1:i + 1])
                vec = bool((M.climax[ee + 1:i + 1] & dir_bull).any())
                vec_any = bool(((M.climax[ee + 1:i + 1] | M.above[ee + 1:i + 1]) & dir_bull).any())
                ei = i + 1
                if ei >= e or mod[ei] >= 955 or mod[ei] >= 1080:
                    continue
                entry_d = float(o_d[ei]) + SLIP
                # targets: levels beyond entry, not touched by the trigger bar's close
                T = collections.defaultdict(list)
                for q, (p, ki, nm, cls) in enumerate(tgt):
                    if ki <= i and tb[q] > i and p > entry_d:
                        T[cls].append(round(p - entry_d, 2))
                for cls in T:
                    T[cls].sort()
                # PO3: extreme beyond / entry beyond each HTF open (direction space)
                po3 = {}
                for nm, arr in (("1h", M.open_1h), ("4h", M.open_4h), ("d", M.open_d), ("00", M.open_00), ("830", M.open_830),
                                ("930", M.open_930), ("wk", M.open_wk), ("22", M.open_22)):
                    ov = arr[i]
                    if np.isnan(ov):
                        po3[nm] = None
                    else:
                        po3[nm] = (int(ext < ov * d), int(entry_d - SLIP < ov * d))   # (manipulation beyond open, entry in discount)
                vm = x.get("vix_move"); xm = x.get("vxn_move")
                op = x["open18"] * d
                gside = {}
                for gk in ("nwog", "ndog"):          # +1 = entry on the premium side of the gap midpoint, -1 discount, 0 no gap
                    gv = x.get(gk)
                    gside[gk] = (1 if (entry_d * d - 0.5 * (gv[0] + gv[1])) * d > 0 else -1) if gv else 0
                ws = int(np.searchsorted(M.week_id[:ee + 1], M.week_id[ee]))
                out.append({
                    "day": str(date), "k": k, "dir": d, "i": int(i), "ext_i": int(ee), "ref_i": j, "entry_i": ei, "sweep_i": int(sb),
                    "entry_t": int(M.t[ei]), "entry_d": entry_d, "ext_d": ext, "ref_d": rp, "trig_c": float(c_d[i]), "mod": int(mod[ei]),
                    "swept": sorted({z[0][2] for z in swept}), "swept_cls": sorted({z[0][3] for z in swept}),
                    "depth_atr": round((lev_near - ext) / max(at[ee], 1e-9), 3), "ind_n": ind_n,
                    "disp": round(float(body[1:].max()) if len(body) > 1 else 0.0, 3), "vec": vec, "vec_any": vec_any,
                    "vec_sweep": bool(M.climax[ee]), "bars": int(i - ee), "atr": round(float(at[i]), 2),
                    "targets": dict(T), "po3": po3,
                    "vix_ext": round((op - ext) / vm, 3) if vm else None, "vxn_ext": round((op - ext) / xm, 3) if xm else None,
                    "vix_room": round((op + vm - entry_d), 2) if vm else None,
                    "how": bool(M.how[ee]), "wk_ext": bool(lo_d[ee] <= lo_d[ws:ee + 1].min()), "dow": x["dow"],
                    "sw": sw, "atr_ext": float(at[ee]), "idm_a": idm_a, "nwog_side": gside["nwog"], "ndog_side": gside["ndog"],
                })
    out.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    _week_context(M, out)
    return out


def _week_context(M: Market, C):
    """mw_break (tools/lit_sessions.py): on Thursday/Friday, the direction of the first break of the Monday-Wednesday range
    seen by the trigger bar (+1 up, -1 down, 0 not yet); None on Monday-Wednesday."""
    h, l = M.h, M.l
    wk_days = collections.defaultdict(list)
    for k, (d, s, e) in enumerate(M.days):
        wk_days[int(M.week_id[s])].append(k)
    mw = {}
    for w, ks in wk_days.items():
        mon_wed = [k for k in ks if M.ctx[k]["dow"] <= 2]
        late = [k for k in ks if M.ctx[k]["dow"] >= 3]
        if len(mon_wed) < 2 or not late:
            continue
        H = max(float(h[M.days[k][1]:M.days[k][2]].max()) for k in mon_wed)
        Lw = min(float(l[M.days[k][1]:M.days[k][2]].min()) for k in mon_wed)
        a = M.days[late[0]][1]; zend = M.days[late[-1]][2]
        up = np.flatnonzero(h[a:zend] > H); dn = np.flatnonzero(l[a:zend] < Lw)
        fu = a + int(up[0]) if len(up) else 10 ** 12
        fd = a + int(dn[0]) if len(dn) else 10 ** 12
        for k in late:
            mw[k] = (fu, fd)
    for z in C:
        if z["k"] in mw:
            fu, fd = mw[z["k"]]
            z["mw_break"] = (1 if fu < fd else -1) if min(fu, fd) <= z["i"] else 0
        else:
            z["mw_break"] = None


# ------------------------------------------------------------------------------------------------ executor
def qty_for(risk_pts, risk_usd=800.0, ref_stop=20.0, max_micros=MAX_MICROS):
    r = risk_usd if risk_pts <= ref_stop else risk_usd * ref_stop / risk_pts
    return max(0, min(max_micros, int(r / (risk_pts * PV))))


def entry_price(cand, mode="market", stop_buf=2.0):
    """Direction-space entry price: "market" = next bar open + 1 tick; limit modes (filled later, no slippage):
    "ref" = the broken swing high (breaker / structure level), "fib50" / "fib62" = 50% / 62% retrace of the leg from the
    protected low to the trigger close."""
    if mode == "market":
        return cand["entry_d"]
    ext, ref, cl = cand["ext_d"], cand["ref_d"], cand["trig_c"]
    if mode == "ref":
        return ref
    f = {"fib50": 0.5, "fib62": 0.618, "fib70": 0.705}[mode]
    return cl - f * (cl - ext)


def simulate(M: Market, cand, target_pts, stop_buf=2.0, be_r=None, time_bars=None, time_min_r=0.0, flat_mod=955,
             entry_mode="market", wait=12):
    """Walk one trade bar by bar (5m; stop checked before target inside a bar = conservative). Limit entries wait up to
    `wait` bars, are cancelled if the target level trades first, and are stopped on the fill bar if that bar also reaches
    the stop. Returns a trade dict or None (no fill / no size)."""
    d = cand["dir"]
    if d == 1:
        hi_d, lo_d, c_d, o_d = M.h, M.l, M.c, M.o
    else:
        hi_d, lo_d, c_d, o_d = -M.l, -M.h, -M.c, -M.o
    ei = cand["entry_i"]
    stop = cand["ext_d"] - stop_buf
    s_day = M.day_of[ei]
    entry = entry_price(cand, entry_mode, stop_buf)
    if entry_mode != "market":
        tgt_px = entry + target_pts
        fill = None
        for k in range(ei, min(ei + wait, M.n)):
            if M.day_of[k] != s_day or M.mod[k] >= flat_mod or M.mod[k] >= 1080:
                break
            if lo_d[k] <= entry:
                fill = k
                entry = min(entry, float(o_d[k]))
                break
            if hi_d[k] >= tgt_px:
                break
        if fill is None:
            return None
        ei = fill
    risk = entry - stop
    if risk <= 0:
        return None
    q = qty_for(risk)
    if q < 1:
        return None
    tgt = entry + target_pts
    cur = stop
    be_done = False
    mfe = mae = 0.0
    worst = 0.0
    k = ei
    exit_px, kind = None, None
    while k < M.n:
        if M.day_of[k] != s_day or M.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == ei and entry_mode != "market"):     # a limit fill bar: no target credit on the same bar
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tgt:
                exit_px, kind = tgt, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry, True
        if time_bars and k - ei + 1 >= time_bars and not be_done and (c_d[k] - entry) / risk < time_min_r:
            exit_px, kind = float(c_d[k]) - SLIP, "TIME"; break
        if M.mod[k] >= flat_mod:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    pts = exit_px - entry
    pnl = pts * PV * q - COMM * q
    low = min(0.0, worst * PV * q - COMM * q, pnl)
    return {"day": cand["day"], "entry_t": int(M.t[ei]), "exit_t": int(M.t[k]) + 300, "exit_i": int(k), "dir": d,
            "r": round(pnl / (risk * PV * q), 3), "pnl": round(pnl, 2), "risk_pts": round(risk, 2), "qty": q,
            "risk_usd": round(risk * PV * q, 2), "half": False, "exit": kind, "trigger": "LIT-" + entry_mode, "mfe": round(mfe, 3),
            "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - ei + 1), "regime": "", "mult": 1.0, "low": round(low, 2),
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "target_px": round(tgt * d, 2), "swept": cand["swept"],
            "ind_n": cand["ind_n"], "vec": cand["vec"], "i": cand["i"], "ext_i": cand["ext_i"], "ref_i": cand["ref_i"],
            "sweep_i": cand["sweep_i"], "entry_i": int(ei)}


def pick_target(cand, risk, classes, min_rr=1.5, max_rr=5.0, fixed_rr=None, fallback_rr=None):
    """Target in points: fixed R, or the nearest unbroken level of the given classes >= min_rr R away (capped / banked at
    max_rr). None = no trade."""
    if fixed_rr:
        return fixed_rr * risk
    best = None
    for cls in classes:
        for dist in cand["targets"].get(cls, []):
            if dist >= min_rr * risk:
                best = dist if best is None else min(best, dist)
                break
    if best is None:
        return fallback_rr * risk if fallback_rr else None
    return min(best, max_rr * risk) if max_rr else best


def run(M: Market, cands, cfg, sessions=None):
    """Trades for one variant. cfg keys: filt(cand)->bool, classes, min_rr, max_rr, fixed_rr, fallback_rr, stop_buf,
    min_stop, max_stop, be_r, time_bars, time_min_r, max_per_day."""
    filt = cfg.get("filt") or (lambda z: True)
    sset = set(sessions) if sessions else None
    out, busy, per_day = [], -1, collections.Counter()
    buf = cfg.get("stop_buf", 2.0)
    for z in cands:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= cfg.get("max_per_day", 1):
            continue
        if not filt(z):
            continue
        mode = cfg.get("entry", "market")
        ep = entry_price(z, mode, buf)
        risk = ep - (z["ext_d"] - buf)
        if not (cfg.get("min_stop", 8.0) <= risk <= cfg.get("max_stop", 60.0)):
            continue
        zz = z
        if mode != "market":   # target distances are measured from the market entry; shift them to the limit price
            sh = z["entry_d"] - ep
            zz = {**z, "targets": {k: [x + sh for x in v] for k, v in z["targets"].items()}}
        tp = pick_target(zz, risk, cfg.get("classes", ("buildup", "asia", "london", "ny", "pre", "pd", "pw", "pm", "gap")),
                         cfg.get("min_rr", 1.5), cfg.get("max_rr", 5.0), cfg.get("fixed_rr"), cfg.get("fallback_rr"))
        if tp is None:
            continue
        t = simulate(M, z, tp, buf, cfg.get("be_r"), cfg.get("time_bars"), cfg.get("time_min_r", 0.0), entry_mode=mode,
                     wait=cfg.get("wait", 12))
        if t is None:
            continue
        out.append(t); busy = t["exit_i"]; per_day[z["day"]] += 1
    return out


def cold_size(trades, lookback=15, thr=0.0, size=0.25):
    """The live cold-streak filter applied to LIT's own signals (sum of the last 15 finished trades' R <= 0 -> quarter size)."""
    out = []
    srt = sorted(trades, key=lambda t: t["entry_t"])
    for t in srt:
        fin = [x for x in srt if x["exit_t"] < t["entry_t"]][-lookback:]
        on = len(fin) < lookback or sum(x["r"] for x in fin) > thr
        if on:
            out.append(t); continue
        q0 = t["qty"]; q = max(1, int(q0 * size))
        f = q / q0
        x = dict(t)
        per = (t["pnl"] + COMM * q0) / q0
        x.update(qty=q, pnl=round(per * q - COMM * q, 2), risk_usd=round(t["risk_usd"] * f, 2), half=True, mult=round(f, 3),
                 low=round(t["low"] * f, 2))
        out.append(x)
    return out


# ================================================================================================ LIT v2 (combined executor)
# One parameter dict drives every option the four 2026 studies found (tools/lit_entry.py, lit_sessions.py, lit_risk.py,
# lit_filters.py). DEFAULTS reproduce lit_A trade for trade on 5m bars (tools/lit_final.py check). The final variant lives in
# research/lit/lit_final.json.
DEFAULTS = {
    # detector (candidates): structure-shift level and extra boxes
    "ref": "frac",               # "frac" (lit_A) | "cisd"
    "extra_boxes": [],           # e.g. ["ny8_830"]
    # setup filters
    "window": [[120, 930]],      # entry-bar ET minute windows (02:00-15:30)
    "sweep_names": None,         # None = every level counts as swept liquidity; else a list of level names (e.g. "asia20_l", "pdh")
    "disp": 1.0,                 # biggest displacement body / ATR between the extreme and the trigger
    "depth": 0.5,                # sweep depth beyond the nearest swept level (of the sweep set), in ATR
    "idm_a": None,               # [max_dist_atr, max_age_bars, min_count] pre-sweep inducement gate
    "nwog_discount": False,      # longs only below the NWOG midpoint, shorts only above (weeks without a gap trade normally)
    "mw_filter": False,          # Thu/Fri: only in the direction that broke the Mon-Wed range (no break yet = allowed)
    # entry
    "wait": 12,                  # 5m bars the limit (at the broken structure level) stays valid
    "tf": "5m",                  # "1m" = 2026 days with full 1m coverage are filled and managed on true 1m bars
    "cisd1m": None,              # n 1m bars after the tap to see a 1m CISD, then enter at the next open + 1 tick (5m before 2026: n//5)
    # stop
    "stop_buf": 2.0, "min_stop": 8.0, "max_stop": 80.0,
    # target
    "classes": ["pd", "pw", "pm"],   # target classes; "vix" = the 18:00 open +/- vix_k VIX one-day moves
    "vix_k": 1.0,
    "min_rr": 1.5, "max_rr": 5.0,    # nearest target >= min_rr R away, banked at max_rr (None = no bank)
    "fallback_rr": None,             # fixed R target when no level clears min_rr (None = no trade)
    # management
    "be_r": 1.0, "flat_mod": 955, "max_per_day": 1,
    # size (micros = $800 up to a 20-pt stop, then 800*20/stop, max 40; then these multipliers, floor 1 micro)
    "how_out": 1.0,              # multiplier when the sweep extreme is outside the high/low-of-week window (Tue 03:00-Wed 11:30)
    # loss rules (research/writeups/lit-losses.md, run lit_loss_pack; both off by default so lit_final stays reproducible)
    "monday": False,             # Monday rule: once Monday's session took Friday's high (PDH) only shorts, once it took Friday's
                                 # low (PDL) only longs (both taken / neither: no rule); a skipped setup leaves the day free
    "wk_stop": None,             # weekly stop [n, mult]: after n STOP exits in the calendar week (ISO week of the trading day,
                                 # Mon-Fri) the rest of that week trades at mult x size (one rounding with how_out, floor 1 micro)
    # execution (research only; research/writeups/lit-live-fills.md): None = the plain backtest fills above
    "fills": None,               # realistic fill model {} / {...}: engine/lit_fills.py FILL_DEFAULTS (live bot latency, market
                                 # entry at the price when the order reaches CME, stop slippage by hour and bar range, target
                                 # limit needs a trade-through, breakeven lag, MFFU commission). Ignored by the live loop.
}


class XBars:
    """Executor bars (5m from the Market, or true 1m) with direction-space views. day = Market day index (-1 = none)."""

    def __init__(self, t, o, h, l, c, mod, day, secs, full=None):
        self.t, self.o, self.h, self.l, self.c, self.mod, self.day, self.secs = t, o, h, l, c, mod, np.asarray(day), secs
        self.n = len(t)
        self.full = full                  # Market day indices with full coverage (1m only)
        self._d = {1: (h, l, c, o), -1: (-l, -h, -c, -o)}

    def dirs(self, d):
        return self._d[d]


def bars_5m(M: Market):
    return XBars(M.t, M.o, M.h, M.l, M.c, M.mod, M.day_of, 300)


def bars_1m(M: Market, cover=0.97, src=None, tol=None, tail=False):
    """True 1m NQ bars (data/NQ_1m.csv, cleaned by engine.data.load_ltf). Only days with >= cover of their 5m minutes in
    clean 1m bars are used for execution; other days fall back to 5m.
    Live loop (engine/lit_live.py): src = 1m Bars from the feed instead of the file; tol = also keep a window whose 1m bars
    rebuild the 5m bar within tol points (feeds round differently; no shift then); tail = keep the 1m bars after the last
    closed 5m bar (the 5m bar still forming). The defaults (src None, tol None, tail False) are the research rule."""
    if src is None:
        from engine.data import load_ltf
        b, _ = load_ltf("NQ", M.b)
    else:
        b = src
    # Keep only 5-minute windows whose five 1m bars rebuild the 5m bar (O, H, L, C). On 12 days of 2026 (Jan 14-15,
    # Aug 31 - Sep 14) the 1m RTH bars sit on another contract's price basis (a constant +765.75 / +295.75 pts vs the
    # back-adjusted 5m file); those windows are shifted onto the 5m basis (back-adjusted) when all four prices differ by the
    # same constant, and dropped otherwise. Mixing bases would fake fills against 5m stops.
    t5 = b.t // 300 * 300
    j5 = np.searchsorted(M.t, t5)
    j5c = np.minimum(j5, M.n - 1)
    ok = (j5 < M.n) & (M.t[j5c] == t5)
    starts = np.r_[0, np.flatnonzero(np.diff(t5)) + 1]
    ends = np.r_[starts[1:], len(t5)]
    keep = np.zeros(len(t5), bool)
    shift = np.zeros(len(t5))
    last5 = int(M.t[-1]) if M.n else -1
    for a, z in zip(starts, ends):
        j = j5c[a]
        if tail and t5[a] > last5:
            keep[a:z] = True        # the forming 5m bar: nothing to check against yet
            continue
        if z - a != 5 or not ok[a]:
            continue
        dd = np.array([b.o[a] - M.o[j], b.c[z - 1] - M.c[j], b.h[a:z].max() - M.h[j], b.l[a:z].min() - M.l[j]])
        if np.abs(dd - dd[0]).max() < 0.01:
            keep[a:z] = True
            shift[a:z] = dd[0] if abs(dd[0]) >= 0.01 else 0.0
        elif tol is not None and np.abs(dd).max() <= tol:
            keep[a:z] = True
    if tail and len(ix_tail := np.flatnonzero(keep & (t5 > last5))):
        shift[ix_tail] = shift[np.flatnonzero(keep & (t5 <= last5))[-1]] if (keep & (t5 <= last5)).any() else 0.0
    ix = np.flatnonzero(keep)
    sh = shift[ix]
    dmap = {d: k for k, (d, s, e) in enumerate(M.days)}
    day = np.array([dmap.get(x, -1) for x in np.asarray(b.date_str)[ix]])
    cnt = np.bincount(day[day >= 0], minlength=len(M.days))
    full = {k for k, (d, s, e) in enumerate(M.days) if cnt[k] >= cover * 5 * (e - s)}
    return XBars(b.t[ix], b.o[ix] - sh, b.h[ix] - sh, b.l[ix] - sh, b.c[ix] - sh, b.mod[ix], day, 60, full)


def simulate_x(M: Market, B: XBars, cand, entry_px, tgt, stop, P, live=False):
    """Walk one trade on B (5m or 1m). Stop beyond the 5m sweep extreme. Conservative intrabar rule: stop before target;
    a limit fill bar gets no target / breakeven credit. tgt = ("pts", distance from the fill) or ("lvl", direction-space price,
    is_fallback) for the 1m-CISD entry, where the target must still be >= min_rr R from the real fill (a fallback target is
    re-measured from the fill). Ported from tools/lit_entry.py sim() (identical to simulate() on 5m bars).
    Returns a trade dict (runlib columns) or None. live=True (engine/lit_live.py): when the bars end before the setup is
    decided, returns {"pending": True, ...} (limit still working / tapped and waiting for the 1m CISD), and when they end
    inside the trade, the trade with exit "OPEN" (stop_now = the stop after a breakeven move). live=False never does."""
    if P.get("fills") is not None and not live:
        from engine import lit_fills
        return lit_fills.simulate(M, B, cand, entry_px, tgt, stop, P)
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    d_ = cand["dir"]

    def _pending(tapped_k):
        return {"pending": True, "day": cand["day"], "dir": d_, "limit_px": round(entry_px * d_, 2), "stop_px": round(stop * d_, 2),
                "t0": t0, "expires_t": t0 + P["wait"] * 300, "tapped_t": int(B.t[tapped_k]) if tapped_k is not None else None,
                "cisd_bars": P.get("cisd1m"), "tf": B.secs // 60}
    if k0 >= B.n:
        return _pending(None) if live else None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop:              # extreme broken before a fill / a confirmation: dead (a plain limit fills and stops)
            if tapped is None and lo_d[k] <= entry_px and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_cancel:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = _cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False; break
        k += 1
    else:
        if live and fill is None:           # the data ended before the setup was decided
            return _pending(tapped)
    if fill is None:
        return None
    risk = entry - stop
    if risk <= 0:
        return None
    if tgt[0] == "pts":
        tg = entry + tgt[1]
    else:
        if tgt[2]:                          # fallback target: fixed R from the real fill
            tg = entry + P["fallback_rr"] * risk
        else:
            dist = tgt[1] - entry
            if dist < P["min_rr"] * risk:
                return None
            tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    q = qty_for(risk)
    if q < 1:
        return None
    be_r = P["be_r"]
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry, True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        if not live:
            return None
        k = B.n - 1                          # still in the trade at the last bar: an open position
        kind = "OPEN"
        exit_px = float(c_d[k])
    pnl = (exit_px - entry) * PV * q - COMM * q
    low = min(0.0, worst * PV * q - COMM * q, pnl)
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    ei5 = int(np.searchsorted(M.t, B.t[fill], side="right") - 1)
    out = {"day": cand["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "r": round(pnl / (risk * PV * q), 3), "pnl": round(pnl, 2), "risk_pts": round(risk, 2), "qty": q,
            "risk_usd": round(risk * PV * q, 2), "half": False, "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "mult": 1.0, "low": round(low, 2), "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2),
            "target_px": round(tg * d, 2), "swept": cand["swept"], "ind_n": cand["ind_n"], "vec": cand["vec"], "i": cand["i"],
            "ext_i": cand["ext_i"], "ref_i": cand["ref_i"], "sweep_i": cand["sweep_i"], "entry_i": ei5, "tf": B.secs // 60,
            **({"exit_px": round(exit_px * d, 2), "stop_now": round(cur * d, 2), "be_done": be_done,
                "limit_fill": limit_fill, "last_t": int(B.t[k])} if live else {})}
    if kind == "OPEN":
        out.update(exit_t=None, exit_i=10 ** 12)
    return out


def scale_trade(t, m):
    """Size multiplier on a finished trade (exact: P&L, commission and slippage are linear in micros); floor 1 micro."""
    q0 = t["qty"]
    if not q0:                           # a realistic-fill skip (engine/lit_fills.py): nothing to scale
        return dict(t)
    q = max(1, int(q0 * m + 1e-9)) if m < 1 else min(MAX_MICROS, int(q0 * m + 1e-9))
    f = q / q0
    cm = t.get("comm_rt", COMM)
    per = (t["pnl"] + cm * q0) / q0
    x = dict(t)
    x.update(qty=q, pnl=round(per * q - cm * q, 2), risk_usd=round(t["risk_usd"] * f, 2), half=f < 1, mult=round(f, 3),
             low=round(t["low"] * f, 2))
    if "pnl_model" in t:                 # realistic-fill trades: the model's own P&L at the same size ($1.40 commission)
        x["pnl_model"] = round((t["pnl_model"] + COMM * q0) / q0 * q - COMM * q, 2)
    return x


def setup_ok(z, P, names=None):
    """The setup filters of P (window, sweep set + depth, displacement, inducement, NWOG side, Mon-Wed rule)."""
    if not any(a <= z["mod"] < b for a, b in P["window"]):
        return False
    if names is None:
        if z["depth_atr"] < P["depth"]:
            return False
    else:
        sw = [p for nm, p in z["sw"].items() if nm in names]
        if not sw or (max(sw) - z["ext_d"]) / max(z["atr_ext"], 1e-9) < P["depth"]:
            return False
    if z["disp"] < P["disp"]:
        return False
    if P.get("idm_a"):
        dm, age, cnt = P["idm_a"]
        if sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age) < cnt:
            return False
    if P.get("nwog_discount") and z["nwog_side"] == 1:
        return False
    if P.get("mw_filter") and z.get("mw_break") and z["mw_break"] != z["dir"]:
        return False
    return True


def monday_block(M: Market, z):
    """Monday rule (lit_loss_pack): on a Monday trading day, True when the session (from 18:00 Sunday to the trigger bar) has
    taken Friday's high but not its low and the setup is a long, or taken Friday's low but not its high and it is a short."""
    x = M.ctx[z["k"]]
    if x["dow"] != 0 or "pdh" not in x:
        return False
    s, i = x["s"], z["i"]
    took_hi = bool(M.h[s:i + 1].max() > x["pdh"])
    took_lo = bool(M.l[s:i + 1].min() < x["pdl"])
    if took_hi == took_lo:
        return False
    return (took_hi and z["dir"] == 1) or (took_lo and z["dir"] == -1)


def monday_state(M: Market, k, upto):
    """Today's Monday rule for the dashboards: None (not Monday / no Friday levels), "both", "none", "high" (Friday's high
    taken: shorts only) or "low" (Friday's low taken: longs only), seen by bar `upto`."""
    x = M.ctx[k]
    if x["dow"] != 0 or "pdh" not in x:
        return None
    s = x["s"]
    if upto < s:
        return "none"
    hi = bool(M.h[s:upto + 1].max() > x["pdh"]); lo = bool(M.l[s:upto + 1].min() < x["pdl"])
    return "both" if hi and lo else "high" if hi else "low" if lo else "none"


def iso_week(day):
    import datetime as _dt
    return tuple(_dt.date.fromisoformat(str(day)).isocalendar()[:2])


def week_stops(day, entry_t, own, week_hist=None):
    """STOP exits in the ISO week of trading day `day` that finished by entry_t. own = this run's finished trades; week_hist =
    the live ledger's rows ({"day", "exit" or "exit_reason", "exit_t"}): a day the ledger knows is counted from the ledger
    (what was routed), every other day from the run's own trades (one trade a day, so no double count)."""
    wk = iso_week(day)
    ext = [r for r in (week_hist or []) if r.get("day") and iso_week(r["day"]) == wk]
    ext_days = {r["day"] for r in ext}
    n = 0
    for r in ext:
        ex = r.get("exit") or r.get("exit_reason")
        xt = r.get("exit_t")
        done = (int(xt) <= int(entry_t)) if isinstance(xt, (int, float, np.integer)) else (r["day"] < day)
        n += ex == "STOP" and done
    for t in own:
        if t["day"] in ext_days or t.get("exit_t") is None or iso_week(t["day"]) != wk:
            continue
        # the live ledger records the model's exit reason (engine/live.py routes it); realistic-fill trades carry it apart
        n += t.get("exit_model_kind", t["exit"]) == "STOP" and int(t["exit_t"]) <= int(entry_t)
    return n


def targets_x(M: Market, z, P):
    """Target distances from the market entry (direction space) per class, plus the VIX band class."""
    T = {c: z["targets"].get(c, []) for c in P["classes"] if c != "vix"}
    if "vix" in P["classes"]:
        x = M.ctx[z["k"]]
        vm = x.get("vix_move")
        if vm:
            p = x["open18"] * z["dir"] + P["vix_k"] * vm
            if p > z["entry_d"]:
                T["vix"] = [round(p - z["entry_d"], 2)]
    return T


def run_x(M: Market, cands, P=None, sessions=None, B1=None, B5=None):
    """Trades of one LIT variant P (keys: DEFAULTS). First qualifying candidate per day (max_per_day), one trade at a time."""
    return _run_core(M, cands, P, sessions, B1, B5, live=False)["trades"]


def run_live(M: Market, cands, P=None, B1=None, B5=None, week_hist=None):
    """run_x for the live loop (engine/lit_live.py) on a window that ends now. Returns {"trades": finished trades + at most
    one with exit "OPEN", "pending": setups whose limit is still working (or tapped, waiting for the 1m CISD), "signals":
    every setup that passed the filters and was sent to the executor (limit placed), with its plan}. A pending setup does
    not block a later one: whichever fills first is the day's trade (the backtest decides in setup order; the two differ
    only when a later setup fills while an earlier limit is still working and that earlier limit fills afterwards).
    week_hist: the live ledger's finished trades of this week for the weekly stop (see week_stops); None = the run's own."""
    return _run_core(M, cands, P, None, B1, B5, live=True, week_hist=week_hist)


def _run_core(M: Market, cands, P, sessions, B1, B5, live, week_hist=None):
    P = {**DEFAULTS, **(P or {})}
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    B5 = B5 or bars_5m(M)
    if P["tf"] == "1m" and B1 is None and not live:
        B1 = bars_1m(M)
    out, busy, per_day = [], -1, collections.Counter()
    pending, signals = [], []
    buf = P["stop_buf"]
    for z in cands:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not setup_ok(z, P, names):
            continue
        if P.get("monday") and monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop = z["ext_d"] - buf
        risk = ep - stop
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in targets_x(M, z, P).items()}
        best = None
        best_c = None
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk:
                    if best is None or dist < best:
                        best, best_c = dist, c
                    break
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        tgt = ("lvl", ep + tp, fb) if P.get("cisd1m") else ("pts", tp)
        t = simulate_x(M, B, z, ep, tgt, stop, P, live=live)
        if live:
            d = z["dir"]
            signals.append({"t": int(M.t[z["entry_i"]]), "day": z["day"], "dir": d, "limit_px": round(ep * d, 2),
                            "stop_px": round(stop * d, 2), "target_px": round((ep + tp) * d, 2), "risk_pts": round(risk, 2),
                            "rr": round(tp / risk, 2), "target_label": ("fallback " + str(P["fallback_rr"]) + "R") if fb else
                            ("VIX band" if best_c == "vix" else str(best_c)) + (" (banked at " + str(P["max_rr"]) + "R)"
                                                                             if P["max_rr"] and best and best > P["max_rr"] * risk else ""),
                            "swept": z["swept"], "sweep_ext": round(z["ext_d"] * d, 2), "ind": len(z.get("idm_a") or []),
                            "disp": z["disp"], "tf": B.secs // 60, "how": z["how"],
                            "status": "pending" if (t and t.get("pending")) else ("filled" if t else "no fill")})
        if t is None:
            continue
        if t.get("pending"):
            t.update(target_px=round((ep + tp) * z["dir"], 2), swept=z["swept"], sig_t=int(M.t[z["entry_i"]]))
            pending.append(t)
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        m = P["how_out"] if (P["how_out"] != 1.0 and not z["how"]) else 1.0
        why = ["outside the high/low-of-week window x%g" % m] if m != 1.0 else []
        if P.get("wk_stop"):
            n_st, m_st = P["wk_stop"]
            ws = week_stops(z["day"], t["entry_t"], out, week_hist)
            if ws >= n_st:
                m *= float(m_st)
                why.append(f"weekly stop: {ws} stop-outs this week x{float(m_st):g}")
        if m != 1.0:
            t = scale_trade(t, m)
            t["size_mult"] = round(m, 6)
            t["size_why"] = why
        if live:
            t["target_label"] = signals[-1]["target_label"]
            t["sweep_ext"] = signals[-1]["sweep_ext"]
        out.append(t)
    if not live:
        return {"trades": out}
    pending = [x for x in pending if per_day[x["day"]] < P["max_per_day"] and busy < 10 ** 12]
    week = None
    if P.get("wk_stop") and M.n:
        today = M.days[-1][0]
        ws = week_stops(today, 10 ** 12, [t for t in out if t["exit"] != "OPEN"], week_hist)
        week = {"week": "%d-W%02d" % iso_week(today), "stops": int(ws), "after": int(P["wk_stop"][0]),
                "mult": float(P["wk_stop"][1]) if ws >= P["wk_stop"][0] else 1.0, "ledger_days": sorted({r["day"] for r in (week_hist or [])
                                                                                                        if r.get("day") and iso_week(r["day"]) == iso_week(today)})}
    return {"trades": out, "pending": pending, "signals": signals, "week": week}
