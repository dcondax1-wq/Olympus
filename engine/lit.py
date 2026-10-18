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


def _vix(name="VIX"):
    df = pd.read_csv(os.path.join(DATA_DIR, f"{name}_1d.csv"))
    return list(df["date"].astype(str)), df["close"].values.astype(float)


# ------------------------------------------------------------------------------------------------ market (all components)
class Market:
    """All LIT components for the whole NQ 5m history, computed once."""

    def __init__(self, tol_atr=0.15):
        b = load("NQ", "5m")
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
            for nm, (a, z) in SESSIONS.items():
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


def candidates(M: Market, leg=24, sweep_win=24, ref_back=36, ind_back=36, t_from=60, t_to=955):
    """Every LIT setup on every day, both directions. Long (mirror for shorts):
      1. sweep:      a known low-side liquidity level (session box, PDL/PWL/PML, gap edge, build-up lows) is breached for the
                     first time within `sweep_win` bars before the leg's extreme (the lowest low of the last `leg` bars)
      2. inducement: minor fractal lows ABOVE the swept level, formed in the `ind_back` bars before the sweep and taken out
                     before/at the sweep bar (early buyers trapped) -> feature ind_n (count)
      3. displacement + structure shift: the trigger bar closes above the last confirmed fractal high before the extreme
                     (the protected low = the extreme), first close above it -> feature disp (max body / ATR between
                     extreme and trigger), vec (a climax vector candle in the trade's direction), vec_any (climax or above)
      4. entry next bar open; stop beyond the protected low; targets = unbroken levels beyond the entry, per class.
    Trigger bars between ET minute t_from and t_to (entry-window filters are applied later)."""
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
                jj = bisect.bisect_left(swing_hi, ee) - 1
                if jj < 0 or swing_hi[jj] < ee - ref_back:
                    continue
                j = int(swing_hi[jj]); ref = float(hi_d[j])
                if not (c_d[i] > ref and c_d[ee:i].max() <= ref):
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
                wk_lo = lo_d[max(s - 1440, 0):ee + 1]
                ws = int(np.searchsorted(M.week_id[:ee + 1], M.week_id[ee]))
                out.append({
                    "day": str(date), "k": k, "dir": d, "i": int(i), "ext_i": int(ee), "ref_i": j, "entry_i": ei, "sweep_i": int(sb),
                    "entry_t": int(M.t[ei]), "entry_d": entry_d, "ext_d": ext, "ref_d": ref, "trig_c": float(c_d[i]), "mod": int(mod[ei]),
                    "swept": sorted({z[0][2] for z in swept}), "swept_cls": sorted({z[0][3] for z in swept}),
                    "depth_atr": round((lev_near - ext) / max(at[ee], 1e-9), 3), "ind_n": ind_n,
                    "disp": round(float(body[1:].max()) if len(body) > 1 else 0.0, 3), "vec": vec, "vec_any": vec_any,
                    "vec_sweep": bool(M.climax[ee]), "bars": int(i - ee), "atr": round(float(at[i]), 2),
                    "targets": dict(T), "po3": po3,
                    "vix_ext": round((op - ext) / vm, 3) if vm else None, "vxn_ext": round((op - ext) / xm, 3) if xm else None,
                    "vix_room": round((op + vm - entry_d), 2) if vm else None,
                    "how": bool(M.how[ee]), "wk_ext": bool(lo_d[ee] <= lo_d[ws:ee + 1].min()), "dow": x["dow"],
                })
    out.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    return out


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
