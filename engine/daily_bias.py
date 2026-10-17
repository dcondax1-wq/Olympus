"""Daily bias for NQ futures: mechanical, causal versions of the bias methods discretionary ICT/SMC traders use.

STABLE API (for tools/trader_layer.py and engine/narrative.py; signatures and return keys will not change)
------------------------------------------------------------------------------------------------------------
    from engine.daily_bias import bias, bias_all, BiasContext, METHODS, DEFAULT_METHOD

    res = bias(bars5, t, method=DEFAULT_METHOD)
        bars5   pandas DataFrame of 5m bars with columns time (unix seconds, bar OPEN), open, high, low, close.
                The et/day/mod columns that tools.strategy_lab.bars() adds are reused when present. Give it at least
                ~45 trading days of history (weekly range, daily swings, ADR20); fewer days just mean more neutrals.
        t       unix seconds, the decision time. Only bars with time + 300 <= t are used (closed bars). Daily, weekly
                and 4H bars are used only once closed. For a trade, pass the entry (fill) bar's open time.
        method  one of METHODS
        -> {"dir": +1 | -1 | 0, "draw": float | None, "draw_label": str, "confidence": float in [0, 1],
            "why": str, "method": str, "state": str}
           dir = where price is expected to be DRAWN (not a forecast of the close), draw = the target level.

    ctx = BiasContext(bars5)      # build once, then query many times: ctx.bias(t, method), ctx.all(t)
    bias() keeps the last context (keyed by the frame's id, length and last bar time), so repeated calls on one frame
    are cheap; a live loop that appends a bar rebuilds it (well under a second for a 60-day frame).

METHODS (rules pre-registered in research/lab/BIAS_RULES.md, measured in research/lab/BIAS_REPORT.md)
    ttrades        A   TTrades candle closure, yesterday (Y) vs the day before (P). Inside / outside-inside = 0
    ttrades_carry  A2  as A, but an inside day carries the previous day's bias
    htf_draw       B   ICT HTF draw: best untaken HTF pool (PWH/PWL, daily and 4H swings, PDH/PDL, EQH/EQL) by
                       weight minus distance in ADR20; neutral when both sides score within 0.5
    structure      C   daily BOS trend + 4H BOS trend + 4-week premium/discount, majority vote
    open_amd       D   a sweep of a pool below (above) the midnight or 09:30 open, then a close back through it
    composite      E   vote of A, B, C: >= 2 agree and none opposes, else 0
    samd_cont      F1  owner's session AMD at 09:25 (Asia range, London 02:00-05:00); London still manipulating ->
                       NY continues that way
    samd_rev       F2  same; London still manipulating -> NY completes the reversal
    samd_rev_only  F0  same; only completed London manipulations count
    composite2     E2  vote of A, B, C, D, F0
    h1_trend       reference only (not a daily bias): the 1H BOS trend, the CONFLUENCE_RESULTS benchmark

    bias_all(bars5, t) -> {method: result} for every method (dashboard / narrative logging).

WHAT THE DATA SAYS (research/lab/BIAS_REPORT.md, NQ1! 2022-2026, model trades 2025-04..2026-10)
    No method predicts the NY RTH direction or, distance-matched, which side's liquidity NY takes. The TTrades "next
    day takes Y.H 80%" is distance: a level the same distance on the other side of the 18:00 open is taken 78%.
    On model trades only open_amd (D) separated winners: +0.56R aligned minus counter, pooled over 6 models (positive
    in all 6), nominal p 0.011, NOT significant after correcting for 11 methods. As a hard "aligned only" filter it
    keeps 0.1-0.9 trades/week per model. So: use any of these as context, a draw/target label or a soft grade, never
    as a veto. DEFAULT_METHOD is open_amd because it is the best measured, not because it is proven.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
TICK = 0.25
FULL_DAY_BARS = 150
METHODS = ("ttrades", "ttrades_carry", "htf_draw", "structure", "open_amd", "composite",
           "samd_cont", "samd_rev", "samd_rev_only", "composite2", "h1_trend")
DEFAULT_METHOD = "open_amd"
W_PW, W_DSW, W_PD, W_4SW, EQ_BONUS = 2.0, 1.5, 1.0, 0.5, 1.0
B_MAX_D, B_MARGIN, EQ_TOL_ADR = 1.5, 0.5, 0.05
DAILY_SWING_DAYS, H4_SWING_DAYS = 60, 30


def _out(method, d=0, draw=None, label="", conf=0.0, why="", state=""):
    return {"dir": int(d), "draw": None if draw is None else float(draw), "draw_label": label,
            "confidence": float(round(max(0.0, min(1.0, conf)), 3)), "why": why, "method": method, "state": state}


def _trend(H, L, C):
    """3-candle swings (strict) and BOS trend on one timeframe. trend[m] is known at the close of bar m.
    Returns trend, swing-high positions, their confirming positions, swing-low positions, confirming positions."""
    n = len(H)
    tr_arr = np.zeros(n, np.int8)
    hp, hc, lp, lc = [], [], [], []
    sh = sl = None
    shb = slb = True
    tr = 0
    for m in range(n):
        if m >= 2:
            if H[m - 1] > H[m - 2] and H[m - 1] > H[m]:
                sh, shb = H[m - 1], False
                hp.append(m - 1)
                hc.append(m)
            if L[m - 1] < L[m - 2] and L[m - 1] < L[m]:
                sl, slb = L[m - 1], False
                lp.append(m - 1)
                lc.append(m)
        if sh is not None and not shb and C[m] > sh:
            tr, shb = 1, True
        if sl is not None and not slb and C[m] < sl:
            tr, slb = -1, True
        tr_arr[m] = tr
    a = lambda x: np.asarray(x, np.int64)
    return tr_arr, a(hp), a(hc), a(lp), a(lc)


def _segments(key):
    brk = np.flatnonzero(key[1:] != key[:-1]) + 1
    return np.r_[0, brk].astype(np.int64), np.r_[brk, len(key)].astype(np.int64)


class BiasContext:
    """Everything precomputed once per bars frame; every query is causal in t."""

    def __init__(self, bars5):
        b = bars5
        t = b["time"].to_numpy(np.int64)
        if len(t) > 1 and (np.diff(t) < 0).any():
            b = b.sort_values("time").reset_index(drop=True)
            t = b["time"].to_numpy(np.int64)
        self.t = t
        self.o, self.h = b["open"].to_numpy(float), b["high"].to_numpy(float)
        self.l, self.c = b["low"].to_numpy(float), b["close"].to_numpy(float)
        if "mod" in b.columns and "day" in b.columns:
            mod, day = b["mod"].to_numpy(np.int64), b["day"].to_numpy().astype(str)
        else:
            et = pd.to_datetime(b["time"], unit="s", utc=True).dt.tz_convert(ET)
            mod = (et.dt.hour * 60 + et.dt.minute).to_numpy(np.int64)
            day = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d").to_numpy().astype(str)
        self.mod = mod
        self.n = n = len(t)
        self.ds, self.de = _segments(day)
        self.days = [str(day[i]) for i in self.ds]
        self.day_ix = {d: k for k, d in enumerate(self.days)}
        nd = self.nd = len(self.ds)
        self.di = np.repeat(np.arange(nd), self.de - self.ds)
        h, l, c, o = self.h, self.l, self.c, self.o
        self.dO, self.dC = o[self.ds], c[self.de - 1]
        self.dH, self.dL = np.maximum.reduceat(h, self.ds), np.minimum.reduceat(l, self.ds)
        self.nb = self.de - self.ds
        self.full = self.nb >= FULL_DAY_BARS
        dates = [dt.date.fromisoformat(d) for d in self.days]
        self.dates = dates
        self.end_t = np.array([int(dt.datetime(x.year, x.month, x.day, 17, 0, tzinfo=ET).timestamp()) for x in dates], np.int64)
        self.start_t = np.array([int(dt.datetime(*(x - dt.timedelta(days=1)).timetuple()[:3], 18, 0, tzinfo=ET).timestamp())
                                 for x in dates], np.int64)
        # ---- full days, ADR20, ATR14d
        F = self.F = np.flatnonzero(self.full)
        self.fpos = np.searchsorted(F, np.arange(nd), side="left")      # number of full days before day k
        fr = self.dH[F] - self.dL[F]
        cs = np.r_[0.0, np.cumsum(fr)]
        pc = np.r_[self.dC[F][0], self.dC[F][:-1]] if len(F) else np.zeros(0)
        ftr = np.maximum(self.dH[F], pc) - np.minimum(self.dL[F], pc) if len(F) else np.zeros(0)
        ct = np.r_[0.0, np.cumsum(ftr)]
        self.adr = np.full(nd, np.nan)
        self.atr = np.full(nd, np.nan)
        for k in range(nd):
            p = self.fpos[k]
            if p >= 5:
                a = max(0, p - 20)
                self.adr[k] = (cs[p] - cs[a]) / (p - a)
                a = max(0, p - 14)
                self.atr[k] = (ct[p] - ct[a]) / (p - a)
        # ---- intraday prefix/suffix extremes for fast "taken" checks
        # ---- weeks (completed, >= 2 full days)
        wkey = np.array([x.isocalendar()[0] * 100 + x.isocalendar()[1] for x in dates], np.int64)
        self.wkey = wkey
        wk_list, wk_hi, wk_lo, wk_last = [], [], [], []
        for k in F:
            if not wk_list or wk_list[-1] != wkey[k]:
                wk_list.append(wkey[k]); wk_hi.append(self.dH[k]); wk_lo.append(self.dL[k]); wk_last.append([k])
            else:
                wk_hi[-1] = max(wk_hi[-1], self.dH[k]); wk_lo[-1] = min(wk_lo[-1], self.dL[k]); wk_last[-1].append(k)
        keep = [i for i, ks in enumerate(wk_last) if len(ks) >= 2]
        self.wk_key = np.array([wk_list[i] for i in keep], np.int64)
        self.wk_hi = np.array([wk_hi[i] for i in keep], float)
        self.wk_lo = np.array([wk_lo[i] for i in keep], float)
        self.wk_end_idx = np.array([self.de[wk_last[i][-1]] for i in keep], np.int64)   # first bar after the week
        self.prev_wk = np.searchsorted(self.wk_key, wkey, side="left") - 1          # last completed week before day k
        self.pwh_taken = np.array([self._first_take(self.wk_hi[w], 1, self.wk_end_idx[w]) for w in range(len(self.wk_key))], np.int64)
        self.pwl_taken = np.array([self._first_take(self.wk_lo[w], -1, self.wk_end_idx[w]) for w in range(len(self.wk_key))], np.int64)
        # ---- PDH / PDL per day (Y = last full day before k)
        self.Y = np.where(self.fpos >= 1, F[np.maximum(self.fpos - 1, 0)] if len(F) else -1, -1)
        self.P = np.where(self.fpos >= 2, F[np.maximum(self.fpos - 2, 0)] if len(F) else -1, -1)
        self.pdh_taken = np.full(nd, n, np.int64)
        self.pdl_taken = np.full(nd, n, np.int64)
        for k in range(nd):
            y = self.Y[k]
            if y >= 0:
                self.pdh_taken[k] = self._first_take(self.dH[y], 1, self.de[y])
                self.pdl_taken[k] = self._first_take(self.dL[y], -1, self.de[y])
        # ---- daily structure (full days)
        if len(F) >= 3:
            self.trD, hp, hc, lp, lc = _trend(self.dH[F], self.dL[F], self.dC[F])
        else:
            self.trD, hp, hc, lp, lc = np.zeros(len(F), np.int8), *(np.zeros(0, np.int64),) * 4
        self.dsw = self._swing_table(hp, hc, lp, lc, lvl_h=self.dH[F], lvl_l=self.dL[F],
                                     avail=lambda q: self.end_t[F[q]], form=lambda q: self.de[F[q]],
                                     dayof=lambda q: q, w=W_DSW, kind="D")
        # ---- 4H (18:00-aligned) structure
        b4 = ((mod - 1080) % 1440) // 240
        key4 = self.di * 6 + b4
        s4, e4 = _segments(key4)
        self.s4, self.e4 = s4, e4
        H4, L4 = np.maximum.reduceat(h, s4), np.minimum.reduceat(l, s4)
        C4 = c[e4 - 1]
        d4 = self.di[s4]
        self.end4 = np.minimum(self.start_t[d4] + (b4[s4] + 1) * 14400, self.end_t[d4])
        self.tr4, hp, hc, lp, lc = _trend(H4, L4, C4)
        self.h4sw = self._swing_table(hp, hc, lp, lc, lvl_h=H4, lvl_l=L4, avail=lambda q: self.end4[q],
                                      form=lambda q: e4[q], dayof=lambda q: d4[q], w=W_4SW, kind="4H")
        # ---- 1H clock bars (reference method)
        key1 = t // 3600
        s1, e1 = _segments(key1)
        self.end1 = (key1[s1] + 1) * 3600
        self.tr1, *_ = _trend(np.maximum.reduceat(h, s1), np.minimum.reduceat(l, s1), c[e1 - 1])
        # ---- TTrades per day
        self._ttrades()
        self._sess_cache, self._amd_cache = {}, {}

    # ------------------------------------------------------------------------------------------------ helpers
    def _first_take(self, level, side, f):
        """First 5m bar index >= f that takes the level by 1 tick (n if never)."""
        n = self.n
        if f >= n:
            return n
        k = self.di[f]
        z = self.de[k]
        if side > 0:
            thr = level + TICK
            seg = self.h[f:z] >= thr
            if seg.any():
                return int(f + np.argmax(seg))
            rest = self.dH[k + 1:] >= thr
        else:
            thr = level - TICK
            seg = self.l[f:z] <= thr
            if seg.any():
                return int(f + np.argmax(seg))
            rest = self.dL[k + 1:] <= thr
        if not rest.any():
            return n
        k2 = k + 1 + int(np.argmax(rest))
        a, z = self.ds[k2], self.de[k2]
        seg = (self.h[a:z] >= thr) if side > 0 else (self.l[a:z] <= thr)
        return int(a + np.argmax(seg))

    def _swing_table(self, hp, hc, lp, lc, lvl_h, lvl_l, avail, form, dayof, w, kind):
        lv = np.r_[lvl_h[hp], lvl_l[lp]] if len(hp) + len(lp) else np.zeros(0)
        side = np.r_[np.ones(len(hp), np.int8), -np.ones(len(lp), np.int8)]
        pos = np.r_[hp, lp]
        conf = np.r_[hc, lc]
        av = np.array([avail(q) for q in conf], np.int64) if len(conf) else np.zeros(0, np.int64)
        fm = np.array([form(q) for q in pos], np.int64) if len(pos) else np.zeros(0, np.int64)
        dy = np.array([dayof(q) for q in pos], np.int64) if len(pos) else np.zeros(0, np.int64)
        tk = np.array([self._first_take(lv[i], side[i], fm[i]) for i in range(len(lv))], np.int64)
        return {"lv": lv, "side": side, "avail": av, "taken": tk, "day": dy, "w": w, "kind": kind}

    def _locate(self, t):
        """(j, m): last closed bar index at t and the index of t's trading day (nd = a day with no bars yet)."""
        j = int(np.searchsorted(self.t, int(t) - 300, side="right")) - 1
        lab = (dt.datetime.fromtimestamp(int(t), ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")
        m = self.day_ix.get(lab)
        if m is None:
            m = int(np.searchsorted(np.array(self.days), lab, side="left"))
        return j, m

    def _pools(self, t, j, m):
        """Untaken HTF pools at t: list of [level, side, weight, label]; merged within 1 tick."""
        P = []
        y = self.Y[m] if m < self.nd else (self.F[-1] if len(self.F) else -1)
        if m < self.nd and y >= 0:
            if self.pdh_taken[m] > j:
                P.append([self.dH[y], 1, W_PD, "PDH"])
            if self.pdl_taken[m] > j:
                P.append([self.dL[y], -1, W_PD, "PDL"])
        w = self.prev_wk[m] if m < self.nd else len(self.wk_key) - 1
        if w >= 0:
            if self.pwh_taken[w] > j:
                P.append([self.wk_hi[w], 1, W_PW, "PWH"])
            if self.pwl_taken[w] > j:
                P.append([self.wk_lo[w], -1, W_PW, "PWL"])
        fp = self.fpos[m] if m < self.nd else len(self.F)
        for tb, lim in ((self.dsw, fp - DAILY_SWING_DAYS), (self.h4sw, m - H4_SWING_DAYS)):
            if not len(tb["lv"]):
                continue
            mk = (tb["avail"] <= t) & (tb["taken"] > j) & (tb["day"] >= lim)
            for i in np.flatnonzero(mk):
                P.append([tb["lv"][i], int(tb["side"][i]), tb["w"], f"{tb['kind']} swing {'H' if tb['side'][i] > 0 else 'L'}"])
        if not P:
            return []
        P.sort(key=lambda x: (x[1], x[0]))
        M = [P[0]]
        for q in P[1:]:
            if q[1] == M[-1][1] and abs(q[0] - M[-1][0]) <= TICK:
                if q[2] > M[-1][2]:
                    M[-1] = q
            else:
                M.append(q)
        return M

    def _nearest(self, pools, p, d):
        best = None
        for lv, sd, w, lab in pools:
            if sd != d:
                continue
            dist = (lv - p) * d
            if best is None or dist < best[0]:
                best = (dist, lv, lab)
        return (None, "none untaken") if best is None else (best[1], best[2])

    # ------------------------------------------------------------------------------------------------ A: TTrades
    def _ttrades(self):
        nd = self.nd
        self.a_dir = np.zeros(nd, np.int8)
        self.a_state = ["NA"] * nd
        self.a2_dir = np.zeros(nd, np.int8)
        self.a2_src = ["NA"] * nd
        dH, dL, dC = self.dH, self.dL, self.dC
        a2_by_full = {}
        for k in range(nd):
            y, p = self.Y[k], self.P[k]
            if y < 0 or p < 0:
                continue
            if dC[y] > dH[p]:
                s, d = "CONT_UP", 1
            elif dC[y] < dL[p]:
                s, d = "CONT_DN", -1
            elif dH[y] > dH[p] and dL[y] < dL[p]:
                s, d = "OUTSIDE_IN", 0
            elif dH[y] > dH[p]:
                s, d = "REV_DN", -1
            elif dL[y] < dL[p]:
                s, d = "REV_UP", 1
            else:
                s, d = "INSIDE", 0
            self.a_dir[k], self.a_state[k] = d, s
            if s == "INSIDE":
                d2, src = a2_by_full.get(y, (0, "NA"))
                self.a2_dir[k], self.a2_src[k] = d2, f"carry({src})"
            else:
                self.a2_dir[k], self.a2_src[k] = d, s
            if self.full[k]:
                a2_by_full[k] = (int(self.a2_dir[k]), self.a2_src[k].replace("carry(", "").replace(")", ""))

    def _a(self, t, j, m, carry=False, method="ttrades"):
        if m >= self.nd:
            return _out(method, why="no bars for this trading day yet")
        d = int(self.a2_dir[m] if carry else self.a_dir[m])
        st = self.a2_src[m] if carry else self.a_state[m]
        y = self.Y[m]
        if y < 0:
            return _out(method, why="not enough daily history")
        if d == 0:
            return _out(method, 0, None, "", 0.0, f"{st}: no bias (Y {self.dates[y]})", st)
        tgt = self.dH[y] if d > 0 else self.dL[y]
        taken = (self.pdh_taken[m] if d > 0 else self.pdl_taken[m]) <= j
        conf = (0.8 if "CONT" in st else 0.6) * (0.5 if "carry" in st else 1.0) * (0.5 if taken else 1.0)
        p = self.c[j] if j >= 0 else tgt
        if taken:
            lv, lab = self._nearest(self._pools(t, j, m), p, d)
            lab = f"{lab} (Y.{'H' if d > 0 else 'L'} {tgt:.2f} already taken)"
        else:
            lv, lab = tgt, f"Y.{'H' if d > 0 else 'L'} (PD{'H' if d > 0 else 'L'})"
        return _out(method, d, lv, lab, conf, f"{st}: Y {self.dates[y]} vs P {self.dates[self.P[m]]}", st)

    # ------------------------------------------------------------------------------------------------ B: HTF draw
    def _b(self, t, j, m, method="htf_draw"):
        if j < 0 or m >= self.nd or np.isnan(self.adr[m]):
            return _out(method, why="not enough history")
        p, adr = self.c[j], self.adr[m]
        pools = self._pools(t, j, m)
        tol = EQ_TOL_ADR * adr
        best = {1: None, -1: None}
        npl = len(pools)
        for i, (lv, sd, w, lab) in enumerate(pools):
            dist = max(0.0, (lv - p) * sd) / adr
            if dist > B_MAX_D:
                continue
            # pools are sorted by (side, level): the nearest same-side neighbour is adjacent
            eq = any(0 <= k < npl and pools[k][1] == sd and abs(pools[k][0] - lv) <= tol for k in (i - 1, i + 1))
            sc = w + (EQ_BONUS if eq else 0.0) - dist
            if best[sd] is None or sc > best[sd][0]:
                best[sd] = (sc, lv, lab + (" +EQ" if eq else ""), dist)
        su = best[1][0] if best[1] else -np.inf
        sdn = best[-1][0] if best[-1] else -np.inf
        if su == -np.inf and sdn == -np.inf:
            return _out(method, 0, None, "", 0.0, "no untaken HTF pool within 1.5 ADR", "NONE")
        diff = su - sdn
        why = (f"above {best[1][2]} {best[1][1]:.2f} score {su:.2f}" if best[1] else "above: none") + " | " + \
              (f"below {best[-1][2]} {best[-1][1]:.2f} score {sdn:.2f}" if best[-1] else "below: none")
        if diff >= B_MARGIN:
            return _out(method, 1, best[1][1], best[1][2], min(1.0, diff / 2) if np.isfinite(diff) else 1.0, why, "UP")
        if -diff >= B_MARGIN:
            return _out(method, -1, best[-1][1], best[-1][2], min(1.0, -diff / 2) if np.isfinite(diff) else 1.0, why, "DN")
        return _out(method, 0, None, "", 0.0, "two-sided: " + why, "TWO_SIDED")

    # ------------------------------------------------------------------------------------------------ C: structure
    def _c(self, t, j, m, method="structure"):
        if j < 0 or m >= self.nd:
            return _out(method, why="not enough history")
        fp = self.fpos[m]
        d_tr = int(self.trD[fp - 1]) if fp >= 1 and len(self.trD) >= fp else 0
        q4 = int(np.searchsorted(self.end4, t, side="right")) - 1
        h4 = int(self.tr4[q4]) if q4 >= 0 else 0
        w = self.prev_wk[m]
        p = self.c[j]
        pd_ = 0
        pos = None
        if w >= 3:
            hi, lo = self.wk_hi[w - 3:w + 1].max(), self.wk_lo[w - 3:w + 1].min()
            if hi > lo:
                pos = (p - lo) / (hi - lo)
                pd_ = 1 if pos < 0.5 else (-1 if pos > 0.5 else 0)
        s = d_tr + h4 + pd_
        d = int(np.sign(s))
        why = f"daily BOS {d_tr:+d}, 4H BOS {h4:+d}, 4-week range pos {('%.2f' % pos) if pos is not None else 'n/a'} ({'discount' if pd_ > 0 else 'premium' if pd_ < 0 else 'n/a'})"
        if d == 0:
            return _out(method, 0, None, "", 0.0, why, "MIXED")
        lv, lab = self._nearest(self._pools(t, j, m), p, d)
        return _out(method, d, lv, lab, abs(s) / 3, why, f"S{s:+d}")

    # ------------------------------------------------------------------------------------------------ sessions
    def _sess(self, m):
        if m in self._sess_cache:
            return self._sess_cache[m]
        a, z = self.ds[m], self.de[m]
        mm = self.mod[a:z]
        h, l, o, c = self.h[a:z], self.l[a:z], self.o[a:z], self.c[a:z]
        st = self.start_t[m]
        S = {"a": a, "z": z}

        def win(mask):
            ii = np.flatnonzero(mask)
            if not len(ii):
                return None
            return {"hi": float(h[ii].max()), "lo": float(l[ii].min()), "i0": int(a + ii[0]), "i1": int(a + ii[-1]),
                    "open": float(o[ii[0]])}
        S["asia"] = win((mm >= 1200) & (mm < 1440))
        S["lon"] = win((mm >= 120) & (mm < 300))
        S["ext"] = win((mm >= 120) & (mm < 565))
        S["on"] = win((mm >= 1080) | (mm < 570))
        post = np.flatnonzero(mm < 1080)
        S["i_mo"] = int(a + post[0]) if len(post) else None
        S["mo"] = float(o[post[0]]) if len(post) else None
        i930 = np.flatnonzero((mm >= 570) & (mm < 1080))
        S["i930"] = int(a + i930[0]) if len(i930) and mm[i930[0]] < 600 else None
        S["o930"] = float(o[i930[0]]) if S["i930"] is not None else None
        pre = np.flatnonzero(mm < 565)
        S["i920"] = int(a + pre[-1]) if len(pre) else None
        S["c925"] = float(c[pre[-1]]) if len(pre) else None
        S["t_mid"], S["t0500"], S["t0925"], S["t0930"], S["t1100"] = st + 6 * 3600, st + 11 * 3600, st + 15 * 3600 + 1500, \
            st + 15 * 3600 + 1800, st + 17 * 3600
        self._sess_cache[m] = S
        return S

    # ------------------------------------------------------------------------------------------------ D: open AMD
    def _amd_events(self, m):
        if m in self._amd_cache:
            return self._amd_cache[m]
        S = self._sess(m)
        ev = []
        y = self.Y[m]
        if S["i_mo"] is None or y < 0:
            self._amd_cache[m] = ev
            return ev
        h, l, c, t = self.h, self.l, self.c, self.t
        # candidate pools: (level, side, label, usable-from time, first bar index to check takes from)
        pools = [(self.dH[y], 1, "PDH", 0, self.de[y]), (self.dL[y], -1, "PDL", 0, self.de[y])]
        if S["asia"]:
            pools += [(S["asia"]["hi"], 1, "Asia H", S["t_mid"], S["asia"]["i1"] + 1), (S["asia"]["lo"], -1, "Asia L", S["t_mid"], S["asia"]["i1"] + 1)]
        if S["lon"]:
            pools += [(S["lon"]["hi"], 1, "London H", S["t0500"], S["lon"]["i1"] + 1), (S["lon"]["lo"], -1, "London L", S["t0500"], S["lon"]["i1"] + 1)]
        if S["on"]:
            pools += [(S["on"]["hi"], 1, "ON H", S["t0930"], S["on"]["i1"] + 1), (S["on"]["lo"], -1, "ON L", S["t0930"], S["on"]["i1"] + 1)]
        tk = [(lv, sd, lab, av, self._first_take(lv, sd, fi)) for lv, sd, lab, av, fi in pools]
        z = self.de[m]
        for lv, sd, lab, av, k in tk:
            if k >= z or k < S["i_mo"] or t[k] < av or t[k] >= S["t1100"]:
                continue
            ref, refn = (S["o930"], "O930") if (S["i930"] is not None and k >= S["i930"]) else (S["mo"], "MO")
            if ref is None:
                continue
            if sd < 0 and not (l[k] < ref):
                continue
            if sd > 0 and not (h[k] > ref):
                continue
            # reclaim: first close back through the open at or after the sweep bar
            seg = (c[k:z] > ref) if sd < 0 else (c[k:z] < ref)
            if not seg.any():
                continue
            r = k + int(np.argmax(seg))
            ext = float(l[k:r + 1].min()) if sd < 0 else float(h[k:r + 1].max())
            # invalidation: first later close beyond the sweep extreme
            inv = (c[r + 1:z] < ext) if sd < 0 else (c[r + 1:z] > ext)
            inv_i = r + 1 + int(np.argmax(inv)) if inv.any() else None
            ev.append({"dir": -sd, "r": r, "t_on": int(t[r]) + 300, "ext": ext, "pool": lab, "ref": refn, "refpx": ref,
                       "t_off": (int(t[inv_i]) + 300) if inv_i is not None else None})
        ev.sort(key=lambda e: e["t_on"])
        self._amd_cache[m] = ev
        return ev

    def _d(self, t, j, m, method="open_amd"):
        if j < 0 or m >= self.nd:
            return _out(method, why="no bars for this trading day yet")
        ev = [e for e in self._amd_events(m) if e["t_on"] <= t]
        if not ev:
            return _out(method, 0, None, "", 0.0, "no sweep-and-reclaim of the midnight/09:30 open yet", "NONE")
        e = ev[-1]
        if e["t_off"] is not None and e["t_off"] <= t:
            return _out(method, 0, None, "", 0.0, f"{e['pool']} sweep reclaim of {e['ref']} failed (close beyond {e['ext']:.2f})", "FAILED")
        d = e["dir"]
        lv, lab = self._nearest(self._session_and_htf_pools(t, j, m), self.c[j], d)
        return _out(method, d, lv, lab, 0.6, f"swept {e['pool']} {'below' if d > 0 else 'above'} {e['ref']} {e['refpx']:.2f}, closed back "
                    f"{'above' if d > 0 else 'below'} it", "RECLAIM_UP" if d > 0 else "RECLAIM_DN")

    def _session_and_htf_pools(self, t, j, m):
        P = list(self._pools(t, j, m))
        S = self._sess(m)
        for key, av_key, nm in (("asia", "t_mid", "Asia"), ("lon", "t0500", "London"), ("on", "t0930", "ON")):
            w = S[key]
            if w and S[av_key] <= t:
                for lv, sd in ((w["hi"], 1), (w["lo"], -1)):
                    if self._first_take(lv, sd, w["i1"] + 1) > j:
                        P.append([lv, sd, 1.0, f"{nm} {'H' if sd > 0 else 'L'}"])
        return P

    # ------------------------------------------------------------------------------------------------ F: session AMD
    def samd_state(self, m, window="lon", ref="asia"):
        """Owner's session AMD state at 09:25 for day m: (state, details). window 'lon' (02:00-04:55) or 'ext'
        (02:00-09:20); ref 'asia' (back above the Asia low) or 'lo' (back above the London open)."""
        S = self._sess(m)
        A, Wn = S["asia"], S[window]
        if A is None or Wn is None or S["c925"] is None:
            return "NA", {}
        tl = Wn["lo"] <= A["lo"] - TICK
        th = Wn["hi"] >= A["hi"] + TICK
        c925 = S["c925"]
        lo_open = S["lon"]["open"] if S["lon"] else None
        if tl and th:
            st = "BOTH"
        elif not tl and not th:
            st = "NONE"
        elif tl:
            bound = A["lo"] if ref == "asia" or lo_open is None else lo_open
            st = "REV_UP" if c925 > bound else "INPROC_DN"
        else:
            bound = A["hi"] if ref == "asia" or lo_open is None else lo_open
            st = "REV_DN" if c925 < bound else "INPROC_UP"
        return st, {"asia_hi": A["hi"], "asia_lo": A["lo"], "lon_hi": S["lon"]["hi"] if S["lon"] else None,
                    "lon_lo": S["lon"]["lo"] if S["lon"] else None, "c925": c925, "lon_open": lo_open}

    def _f(self, t, j, m, reading, method):
        if m >= self.nd:
            return _out(method, why="no bars for this trading day yet")
        S = self._sess(m)
        if t < S["t0925"]:
            return _out(method, 0, None, "", 0.0, "session AMD is decided at 09:25 ET", "PENDING")
        st, info = self.samd_state(m)
        d = {"REV_UP": 1, "REV_DN": -1}.get(st, 0)
        if st in ("INPROC_DN", "INPROC_UP") and reading != "rev_only":
            base = -1 if st == "INPROC_DN" else 1
            d = base if reading == "cont" else -base
        if d == 0:
            return _out(method, 0, None, "", 0.0, f"{st}: no session-AMD bias", st)
        p = self.c[j]
        cand = []
        y = self.Y[m]
        names = (("lon_hi", "London H"), ("asia_hi", "Asia H")) if d > 0 else (("lon_lo", "London L"), ("asia_lo", "Asia L"))
        for key, nm in names:
            if info.get(key) is not None:
                cand.append([info[key], d, 1.0, nm])
        if y >= 0:
            cand.append([self.dH[y] if d > 0 else self.dL[y], d, 1.0, "PDH" if d > 0 else "PDL"])
        # keep only untaken (from the window end to now) and on the right side of price
        live = []
        for lv, sd, w, nm in cand:
            fi = (S["lon"]["i1"] + 1) if nm.startswith("London") and S["lon"] else ((S["asia"]["i1"] + 1) if nm.startswith("Asia") else self.de[y])
            if self._first_take(lv, sd, fi) > j and (lv - p) * sd > 0:
                live.append([lv, sd, w, nm])
        lv, lab = self._nearest(live, p, d) if live else self._nearest(self._pools(t, j, m), p, d)
        conf = 0.6 if st.startswith("REV") else 0.4
        return _out(method, d, lv, lab, conf, f"{st} at 09:25 (Asia {info['asia_lo']:.2f}-{info['asia_hi']:.2f}, 09:20 close {info['c925']:.2f})", st)

    # ------------------------------------------------------------------------------------------------ public
    def bias(self, t, method=DEFAULT_METHOD):
        t = int(t)
        j, m = self._locate(t)
        if method == "ttrades":
            return self._a(t, j, m, False, method)
        if method == "ttrades_carry":
            return self._a(t, j, m, True, method)
        if method == "htf_draw":
            return self._b(t, j, m, method)
        if method == "structure":
            return self._c(t, j, m, method)
        if method == "open_amd":
            return self._d(t, j, m, method)
        if method == "samd_cont":
            return self._f(t, j, m, "cont", method)
        if method == "samd_rev":
            return self._f(t, j, m, "rev", method)
        if method == "samd_rev_only":
            return self._f(t, j, m, "rev_only", method)
        if method in ("composite", "composite2"):
            parts = ["ttrades", "htf_draw", "structure"] + (["open_amd", "samd_rev_only"] if method == "composite2" else [])
            R = [self.bias(t, p) for p in parts]
            ups = sum(r["dir"] > 0 for r in R)
            dns = sum(r["dir"] < 0 for r in R)
            votes = ", ".join(f"{p}:{r['dir']:+d}" for p, r in zip(parts, R))
            if ups >= 2 and dns == 0:
                d = 1
            elif dns >= 2 and ups == 0:
                d = -1
            else:
                return _out(method, 0, None, "", 0.0, "no agreement: " + votes, "NO_AGREE")
            src = next(r for r in R if r["dir"] == d and r["draw"] is not None) if any(r["dir"] == d and r["draw"] is not None for r in R) else None
            return _out(method, d, src["draw"] if src else None, (src["draw_label"] if src else ""), max(ups, dns) / len(parts),
                        votes, f"{max(ups, dns)}of{len(parts)}")
        if method == "h1_trend":
            q = int(np.searchsorted(self.end1, t, side="right")) - 1
            d = int(self.tr1[q]) if q >= 0 else 0
            return _out(method, d, None, "", 0.5 if d else 0.0, f"last 1H BOS {d:+d}", "H1")
        raise ValueError(f"unknown bias method {method!r}; use one of {METHODS}")

    def all(self, t):
        return {mth: self.bias(t, mth) for mth in METHODS}


_CACHE = {"key": None, "ctx": None}


def _context(bars5):
    key = (id(bars5), len(bars5), int(bars5["time"].iloc[-1]) if len(bars5) else 0)
    if _CACHE["key"] != key:
        _CACHE["ctx"], _CACHE["key"] = BiasContext(bars5), key
    return _CACHE["ctx"]


def bias(bars5, t, method=DEFAULT_METHOD):
    """Causal daily bias at time t (unix s) from 5m bars. See the module docstring for the contract."""
    return _context(bars5).bias(t, method)


def bias_all(bars5, t):
    """Every method at time t: {method: result}."""
    return _context(bars5).all(t)
