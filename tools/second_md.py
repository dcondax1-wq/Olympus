"""Second strategy next to LIT: MACD divergence at a liquidity sweep, and supply/demand zone retests, made LIT-like.
Owner's order 2026-10-22 (overnight): find 1-2 strategies to trade ALONGSIDE LIT and tune them on 2026 the way LIT was.

    python -X utf8 tools/second_md.py run        # every variant of both families (in R), pick on 2026 H1, check on H2
    python -X utf8 tools/second_md.py picks      # print the H1 picks + chance comparison
    python -X utf8 tools/second_md.py save       # store the picks (rl.save md2_*), research/second/md_best.json, combos
    python -X utf8 tools/second_md.py check      # no look-ahead: rebuild the chosen version on data cut at each signal

Method (no look-ahead, costs in):
- Data: TradingView CME NQ1! 5m (data/NQ_5m.csv) via engine.lit.Market (the LIT levels: session boxes, PDH/PDL, PWH/PWL,
  PMH/PML, NWOG/NDOG, build-ups = equal highs/lows; VIX one-day move from CBOE's file); true 1m bars for 2026
  (data/NQ_1m.csv via engine.lit.bars_1m) for the trade path; 5m elsewhere. 15m / 1h / 4h are built from 5m and a value is
  used only once its last 5m bar has closed (the forming HTF bar's MACD is computed from the 5m close known at that time).
- Signals at a 5m close. Market entry at the next 5m open + 1 tick; limit entry at the CISD level (fills only when price
  trades 1 tick through it, within 30 min, cancelled if the stop trades first; no target on the fill bar).
- Stops 1 tick beyond the sweep extreme / the zone's distal edge (structural, never a fixed distance), 6-80 pts. Stop exits
  at the stop (or a worse open) - 1 tick; 15-min-check cuts, flat 15:55 at market - 1 tick; targets at the limit.
  Stop and target in one bar = stop. $1.90 per micro round trip (MFFU).
- Picked on 2026 H1 (Jan 2 - Jun 30) only; 2026 H2 (Jul 1 - Oct 16) untouched; 2025 and 2021-11..2024 are references.
"""
from __future__ import annotations

import collections
import itertools
import json
import math
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "second")
TICK, PV, COMM, SLIP = 0.25, 2.0, 1.90, 0.25
MIN_STOP, MAX_STOP = 6.0, 80.0
PERIODS = (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"), ("2025", "2025-01-01", "2025-12-31"),
           ("2124", "2021-11-01", "2024-12-31"))
KZ = {"all": ((120, 930),), "lon_ny": ((120, 300), (570, 660)), "ny": ((570, 660),), "lon": ((120, 300),),
      "ny_ext": ((570, 720),)}
LV = {"pd": {"pd", "pw"}, "sess": {"pd", "pw", "asia", "london", "ny", "pre"},
      "all": {"pd", "pw", "pm", "asia", "london", "ny", "pre", "buildup", "gap"}, "eq": {"buildup", "pd"}}

G = {}


# ------------------------------------------------------------------------------------------------ data
class Ctx:
    """Bars + LIT levels + the execution stream (1m where clean 1m exists, else 5m) for one Market."""

    def __init__(self, M, B1=None):
        from engine import lit
        self.M = M
        self.t, self.o, self.h, self.l, self.c = M.t, M.o, M.h, M.l, M.c
        self.mod = M.mod.astype(np.int64)
        self.n = M.n
        self.day = M.day_of.astype(np.int64)
        self.atr = M.atr
        self.dates = [str(d) for d, s, e in M.days]
        # execution stream
        if B1 is None:
            B1 = lit.bars_1m(M)
        elif B1 == "none":                     # signals only (the look-ahead check): no 1m execution stream
            e = np.zeros(0)
            B1 = type("B", (), {"t": e.astype(np.int64), "o": e, "h": e, "l": e, "c": e})()
        t5 = B1.t // 300 * 300
        j5 = np.searchsorted(M.t, t5)
        j5c = np.minimum(j5, M.n - 1)
        ok = (j5 < M.n) & (M.t[j5c] == t5)
        cnt = np.bincount(j5c[ok], minlength=M.n)
        full = cnt == 5
        first1 = np.full(M.n, -1, np.int64)
        idx = np.flatnonzero(ok)
        # first 1m index of each 5m bar (1m sorted by time)
        for i in idx[::-1]:
            first1[j5c[i]] = i
        X = {k: [] for k in ("t", "o", "h", "l", "c", "mod", "end", "k5")}
        x_of5 = np.zeros(M.n + 1, np.int64)
        pos = 0
        # build with numpy: lengths per 5m bar
        lens = np.where(full, 5, 1)
        x_of5[:-1] = np.r_[0, np.cumsum(lens)[:-1]]
        x_of5[-1] = int(lens.sum())
        N = int(lens.sum())
        Xt = np.zeros(N, np.int64); Xo = np.zeros(N); Xh = np.zeros(N); Xl = np.zeros(N); Xc = np.zeros(N)
        Xe = np.zeros(N, np.int64); Xk = np.zeros(N, np.int64); Xm = np.zeros(N, np.int64)
        one = ~full
        p1 = x_of5[:-1][one]
        Xt[p1] = M.t[one]; Xo[p1] = M.o[one]; Xh[p1] = M.h[one]; Xl[p1] = M.l[one]; Xc[p1] = M.c[one]
        Xe[p1] = M.t[one] + 300; Xk[p1] = np.flatnonzero(one); Xm[p1] = self.mod[one]
        fk = np.flatnonzero(full)
        for q in range(5):
            p = x_of5[:-1][fk] + q
            s = first1[fk] + q
            Xt[p] = B1.t[s]; Xo[p] = B1.o[s]; Xh[p] = B1.h[s]; Xl[p] = B1.l[s]; Xc[p] = B1.c[s]
            Xe[p] = B1.t[s] + 60; Xk[p] = fk; Xm[p] = self.mod[fk] + q
        self.Xt, self.Xo, self.Xh, self.Xl, self.Xc, self.Xe, self.Xk, self.Xm = Xt, Xo, Xh, Xl, Xc, Xe, Xk, Xm
        self.Xday = self.day[Xk]
        self.x_of5 = x_of5
        self.full5 = full
        self._h = {}

    # ---- higher timeframes from 5m (clock aligned; 4h from 18:00 ET), within one trading day
    def htf(self, tf):
        if tf in self._h:
            return self._h[tf]
        n = self.n
        if tf == 5:
            H = dict(o=self.o, h=self.h, l=self.l, c=self.c, last=np.arange(n), first=np.arange(n), of5=np.arange(n))
        else:
            if tf == 240:
                b = self.day * 10 + ((self.mod - 1080) % 1440) // 240
            else:
                b = self.t // (tf * 60)
            g = np.r_[True, (b[1:] != b[:-1]) | (self.day[1:] != self.day[:-1])]
            first = np.flatnonzero(g)
            last = np.r_[first[1:] - 1, n - 1]
            H = dict(o=self.o[first], c=self.c[last], h=np.maximum.reduceat(self.h, first), l=np.minimum.reduceat(self.l, first),
                     last=last, first=first, of5=np.cumsum(g) - 1)
        # index of the latest HTF bar CLOSED at or before each 5m bar
        cl = np.full(n, -1, np.int64)
        cl[H["last"]] = np.arange(len(H["last"]))
        if tf != 5 and n:
            # the data's last HTF bar counts as closed only if its last 5m bar ends on the clock boundary
            # (data cut in the middle of an hour = that hour is still forming)
            end = int(self.t[n - 1]) + 300
            done = (((self.mod[n - 1] + 5 - 1080) % 1440) % 240 == 0) if tf == 240 else end % (tf * 60) == 0
            if not done:
                cl[n - 1] = -1
        H["closed"] = pd.Series(np.where(cl >= 0, cl, np.nan)).ffill().fillna(-1).values.astype(np.int64)
        H["atr"] = atr_w(H["h"], H["l"], H["c"])
        self._h[tf] = H
        return H

    def to5(self, H, vals):
        """value of the latest CLOSED HTF bar at each 5m bar (nan before the first)."""
        q = H["closed"]
        out = np.full(self.n, np.nan)
        ok = q >= 0
        out[ok] = np.asarray(vals, float)[q[ok]]
        return out


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def atr_w(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def macd_state(c):
    e12, e26 = ema(c, 12), ema(c, 26)
    line = e12 - e26
    sg = ema(line, 9)
    return e12, e26, line, sg, line - sg


def pivots(h, l, k=2):
    hw = pd.Series(h).rolling(2 * k + 1, center=True).max().values
    lw = pd.Series(l).rolling(2 * k + 1, center=True).min().values
    return h == hw, l == lw


def ctx_full():
    if "X" not in G:
        from engine import lit
        G["X"] = Ctx(lit.Market())
    return G["X"]


def sessions():
    if "sess" not in G:
        r = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        G["sess"] = [d[0] for d in r["days"]]
    return G["sess"]


def cisd_level(c, o, x, d, back=3):
    """LIT/TTrades CISD level for direction d (+1 long after a low sweep): open of the first bar of the last run of
    against-direction candles into the extreme bar x (for a long: down-close candles)."""
    against = (lambda q: c[q] < o[q]) if d > 0 else (lambda q: c[q] > o[q])
    j = x
    while j > x - back and not against(j):
        j -= 1
    if not against(j):
        return None
    st = j
    while st - 1 >= 0 and against(st - 1) and st > x - 30:
        st -= 1
    return float(o[st])


# ------------------------------------------------------------------------------------------------ sweep events
def sweep_events(X, classes, from_mod=0):
    """First breach of each LIT level of the given classes in its trading day, after the level is known.
    Returns list of (i, dir, level_price) sorted by i; dir = trade direction (+1 after a low is taken)."""
    M = X.M
    ev = {}
    for k, (d, s, e) in enumerate(M.days):
        L = M.levels(k)
        for side, px, ki, nm, cls in L:
            if cls not in classes:
                continue
            a = max(int(ki) + 1, s)
            if a >= e:
                continue
            seg = (X.h[a:e] > px) if side == "high" else (X.l[a:e] < px)
            if not seg.any():
                continue
            i = a + int(np.argmax(seg))
            dr = -1 if side == "high" else 1
            key = (i, dr)
            # keep the most extreme level taken on that bar (the deepest pool)
            if key not in ev or (px - ev[key]) * (-dr) > 0:
                ev[key] = px
    out = sorted((i, dr, px) for (i, dr), px in ev.items())
    return out


# ------------------------------------------------------------------------------------------------ MACD divergence
def md_cands(X, tf, osc, lv, W=24, LB=None):
    """MACD divergence at a liquidity sweep, confirmed by a 5m CISD.
    A LIT level (lv set) is taken (first breach of the day). Within W 5m bars price closes back through the CISD level of
    the run into the sweep extreme. At that close the tf-chart MACD (line or histogram) at the sweep-extreme bar must be
    weaker than at the highest prior swing high (lowest swing low) of the last LB tf bars = regular divergence.
    Stop 1 tick beyond the sweep extreme. 'lvl' target = the opposite end of the divergence leg."""
    H = X.htf(tf)
    LB = LB or (48 if tf == 5 else 32)
    e12, e26, line, sg, hist = macd_state(H["c"])
    a12, a26, a9 = 2 / 13, 2 / 27, 2 / 10
    ph, pl = pivots(H["h"], H["l"])
    h1 = X.htf(60)
    _, _, l1, _, hs1 = macd_state(h1["c"])
    _, _, _, _, hs15 = macd_state(X.htf(15)["c"])
    R_h1h, R_h1l, R_m15h = np.sign(X.to5(h1, hs1)), np.sign(X.to5(h1, l1)), np.sign(X.to5(X.htf(15), hs15))
    o, h, l, c, A = X.o, X.h, X.l, X.c, X.atr
    of5, closed = H["of5"], H["closed"]
    out = []
    for (i, dr, px) in sweep_events(X, LV[lv]):
        dday = X.day[i]
        ext, x = (l[i], i) if dr > 0 else (h[i], i)
        for j in range(i, min(i + W, X.n)):
            if X.day[j] != dday or X.mod[j] >= 930 and X.mod[j] < 1080:
                break
            if (dr > 0 and l[j] < ext) or (dr < 0 and h[j] > ext):
                ext, x = (l[j], j) if dr > 0 else (h[j], j)
            if j == x:
                continue
            lev = cisd_level(c, o, x, dr)
            if lev is None or not ((c[j] - lev) * dr > 0):
                continue
            # divergence at the extreme, tf chart, known at j
            qx = of5[x]
            if closed[j] >= qx:
                ox = (line if osc == "line" else hist)[qx]
                hx = H["l"][qx] if dr > 0 else H["h"][qx]
            else:   # the tf bar holding the extreme is still forming: its MACD with the close known at j
                cl = c[j]
                n12 = e12[qx - 1] + a12 * (cl - e12[qx - 1]); n26 = e26[qx - 1] + a26 * (cl - e26[qx - 1])
                ln = n12 - n26; sgn = sg[qx - 1] + a9 * (ln - sg[qx - 1])
                ox = ln if osc == "line" else ln - sgn
                hx = ext
            a_, b_ = max(0, qx - LB), qx - 3
            if b_ <= a_:
                break
            cand = np.flatnonzero((pl if dr > 0 else ph)[a_:b_ + 1]) + a_
            cand = cand[cand + 2 <= max(closed[j], 0)]
            if not len(cand):
                break
            P = cand[np.argmin(H["l"][cand])] if dr > 0 else cand[np.argmax(H["h"][cand])]
            pP = H["l"][P] if dr > 0 else H["h"][P]
            oP = (line if osc == "line" else hist)[P]
            if (ext - pP) * dr > 0:          # the sweep extreme must beyond the prior swing (a higher high / lower low)
                break
            if not ((ox - oP) * dr > 0):     # long: MACD higher at the lower low = bullish divergence
                break
            leg = H["h"][P:qx + 1].max() if dr > 0 else H["l"][P:qx + 1].min()
            out.append({"j": int(j), "dir": int(dr), "ext": float(ext), "stops": {"ext": float(ext - dr * TICK)}, "cisd": lev,
                        "lvl": float(leg), "f": {"depth": float((px - ext) * dr / A[i]) if A[i] > 0 else 0.0,
                                                 "h1h": float(R_h1h[j] * dr), "h1l": float(R_h1l[j] * dr), "m15h": float(R_m15h[j] * dr)}})
            break
    out.sort(key=lambda z: z["j"])
    ded, seen = [], set()
    for z in out:
        if (z["j"], z["dir"]) not in seen:
            seen.add((z["j"], z["dir"])); ded.append(z)
    return ded


# ------------------------------------------------------------------------------------------------ supply / demand
def sd_cands(X, tf, imp, bos, sw, W=24, max_age=10):
    """Fresh supply/demand zones on tf: 1-3 base candles then a displacement candle (body >= imp x ATR(tf)) closing beyond
    the base (bos: and beyond the last confirmed swing high/low = break of structure). Demand zone: distal = lowest low of
    base + impulse, proximal = highest base body. First retest only (first 5m touch of the proximal, up to max_age
    sessions). In the retest, optionally a sweep (sw): the low wicks through a 5m swing low formed after the zone, or a LIT
    level, lying between the distal and proximal + 1 ATR. Then a 5m CISD out of the zone within W bars (a 5m close
    beyond the distal first kills the zone). Stops: 'zone' 1 tick beyond the farther of the distal and the retest extreme,
    'ext' 1 tick beyond the retest extreme. 'lvl' target = the proximal of the nearest fresh opposite zone."""
    H = X.htf(tf)
    o, h, l, c, last = H["o"], H["h"], H["l"], H["c"], H["last"]
    AH = H["atr"]
    body = abs(c - o); rng = h - l
    small = rng <= 1.0 * AH
    ph, pl = pivots(h, l)
    Z = []   # created5, dir, prox, dist, height/atr
    lastph, lastpl = np.nan, np.nan
    for j in range(20, len(c)):
        p = j - 3          # pivots confirmed by bar j-1 (2 bars after the pivot)
        if p >= 0:
            if ph[p]:
                lastph = h[p]
            if pl[p]:
                lastpl = l[p]
        if body[j] < imp * AH[j - 1]:
            continue
        nb = 0
        while nb < 3 and small[j - 1 - nb]:
            nb += 1
        nb = max(nb, 1)
        bs = slice(j - nb, j)
        bh, bl = h[bs].max(), l[bs].min()
        if c[j] > o[j] and c[j] > bh and (not bos or (not np.isnan(lastph) and c[j] > lastph)):
            prox = float(np.maximum(o[bs], c[bs]).max()); dist = float(min(bl, l[j]))
            Z.append((int(last[j]), 1, prox, dist, (prox - dist) / AH[j]))
        elif c[j] < o[j] and c[j] < bl and (not bos or (not np.isnan(lastpl) and c[j] < lastpl)):
            prox = float(np.minimum(o[bs], c[bs]).min()); dist = float(max(bh, h[j]))
            Z.append((int(last[j]), -1, prox, dist, (dist - prox) / AH[j]))
    O5, H5, L5, C5, A5 = X.o, X.h, X.l, X.c, X.atr
    p5h, p5l = pivots(H5, L5)
    PH5, PL5 = np.flatnonzero(p5h), np.flatnonzero(p5l)
    h1, h4 = X.htf(60), X.htf(240)
    tr1 = np.sign(X.to5(h1, h1["c"] - ema(h1["c"], 200)))
    tr4 = np.sign(X.to5(h4, h4["c"] - ema(h4["c"], 50)))
    M = X.M
    lit_lv = {}
    if sw:
        for k in range(len(M.days)):
            lit_lv[k] = [(1 if side == "low" else -1, px, ki) for side, px, ki, nm, cls in M.levels(k)
                         if cls in LV["all"]]
    day_end = np.array([e for d, s, e in M.days])
    touched = []
    raw = []
    for zi, (k0, dd, prox, dist, zh) in enumerate(Z):
        a = k0 + 1
        if a >= X.n:
            touched.append(X.n); continue
        dlim = min(X.day[k0] + max_age, len(M.days) - 1)
        kend = int(day_end[dlim])
        seg = (L5[a:kend] <= prox) if dd > 0 else (H5[a:kend] >= prox)
        if not seg.any():
            touched.append(kend); continue
        k = a + int(np.argmax(seg))
        touched.append(k)
        raw.append((zi, k))
    Zc = np.array([z[0] for z in Z]); Zd = np.array([z[1] for z in Z]); Zp = np.array([z[2] for z in Z]); Tt = np.array(touched)
    out = []
    for zi, k in raw:
        k0, dd, prox, dist, zh = Z[zi]
        dday = X.day[k]
        ext, x = (L5[k], k) if dd > 0 else (H5[k], k)
        # liquidity between the distal and proximal + 1 ATR, formed after the zone
        band_lo, band_hi = (dist, prox + A5[k]) if dd > 0 else (prox - A5[k], dist)
        piv = PL5 if dd > 0 else PH5
        pv = piv[(piv > k0) & (piv <= k + W)]
        liq = [((L5 if dd > 0 else H5)[p], p + 2) for p in pv if band_lo <= (L5 if dd > 0 else H5)[p] <= band_hi]
        if sw:
            liq += [(px, ki + 1) for sd_, px, ki in lit_lv.get(int(dday), []) if sd_ == dd and band_lo <= px <= band_hi]
        swept = False
        for j in range(k, min(k + W, X.n)):
            if X.day[j] != dday or (930 <= X.mod[j] < 1080):
                break
            if (dd > 0 and L5[j] < ext) or (dd < 0 and H5[j] > ext):
                ext, x = (L5[j], j) if dd > 0 else (H5[j], j)
            if (C5[j] - dist) * dd < 0:
                break                                  # closed beyond the distal: zone broken
            if sw and not swept:
                swept = any((ext - px) * dd < 0 and kn <= j for px, kn in liq)
                if not swept:
                    continue
            if j == x:
                continue
            lev = cisd_level(C5, O5, x, dd)
            if lev is None or not ((C5[j] - lev) * dd > 0):
                continue
            alive = (Zc < j) & (Tt > j) & (Zd == -dd)
            cand = Zp[alive]
            cand = cand[(cand > C5[j]) if dd > 0 else (cand < C5[j])]
            tg = float((cand.min() if dd > 0 else cand.max())) if len(cand) else np.nan
            far = min(dist, ext) if dd > 0 else max(dist, ext)
            out.append({"j": int(j), "dir": int(dd), "ext": float(ext), "cisd": lev, "lvl": tg,
                        "stops": {"zone": float(far - dd * TICK), "ext": float(ext - dd * TICK)},
                        "f": {"age": int(X.day[k] - X.day[k0]), "zh": float(zh), "tr1": float(tr1[j] * dd), "tr4": float(tr4[j] * dd)}})
            break
    out.sort(key=lambda z: z["j"])
    ded, seen = [], set()
    for z in out:
        if (z["j"], z["dir"]) not in seen:
            seen.add((z["j"], z["dir"])); ded.append(z)
    return ded


# ------------------------------------------------------------------------------------------------ executor
def sim_one(X, z, ent, tgt, be, tc, stop_key, force_t=None, live=False):
    """One trade per micro. Returns dict (x0 fill exec index, x1 exit exec index, entry, exit, risk, pts, worst, kind,
    target) or None (no fill / stop out of range / target too close). live=True (engine/second.py): when the bars end
    inside the trade, kind "OPEN" (x1 = the last bar, ex = its close, stop_now = the stop now, cut = a 15-minute cut
    decided at the last close, it exits at the next open); live=False never does this (the research result is unchanged)."""
    j, dr = z["j"], z["dir"]
    stop = z["stops"][stop_key]
    if j + 1 >= X.n or X.day[j + 1] != X.day[j]:
        return None
    Xo, Xh, Xl, Xc, Xt, Xe, Xm, Xd = X.Xo, X.Xh, X.Xl, X.Xc, X.Xt, X.Xe, X.Xm, X.Xday
    x = int(X.x_of5[j + 1])
    dday = X.day[j]
    lim = ent == "lim"
    if not lim:
        x0 = x
        e = Xo[x] + dr * SLIP
    else:
        L = z["cisd"]
        tend = X.t[j + 1] + 1800
        x0 = None
        while x < len(Xo) and Xt[x] < tend and Xd[x] == dday and Xm[x] < 930:
            if (dr > 0 and Xl[x] <= stop) or (dr < 0 and Xh[x] >= stop):
                if (dr > 0 and Xl[x] <= L - TICK) or (dr < 0 and Xh[x] >= L + TICK):
                    x0 = x                            # filled and stopped in the same bar (conservative)
                    e = min(Xo[x], L) if dr > 0 else max(Xo[x], L)
                break
            if (dr > 0 and Xl[x] <= L - TICK) or (dr < 0 and Xh[x] >= L + TICK):
                x0 = x
                e = min(Xo[x], L) if dr > 0 else max(Xo[x], L)
                break
            x += 1
        if x0 is None:
            return None
    risk = (e - stop) * dr
    if risk < MIN_STOP or risk > MAX_STOP:
        return None
    M = X.M
    if tgt == "vix":
        cx = M.ctx[int(dday)]
        vm = cx.get("vix_move")
        if not vm:
            return None
        dist = (cx["open18"] + dr * vm - e) * dr
        if dist < 1.5 * risk:
            return None
        tp = e + dr * min(dist, 8.0 * risk)
    elif tgt == "lvl":
        Lv = z.get("lvl")
        if Lv is None or not np.isfinite(Lv):
            return None
        dist = (Lv - e) * dr
        if dist < 1.5 * risk:
            return None
        tp = e + dr * min(dist, 8.0 * risk)
    else:
        tp = e + dr * float(tgt) * risk
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    fill_t = Xt[x0]
    tc_done, cut = not tc, False
    k = x0
    N = len(Xo)
    ex = kind = None
    while k < N:
        if Xd[k] != dday or Xm[k] >= 955:
            k -= 1; ex, kind = Xc[k] - dr * SLIP, "flat"; break
        if cut:
            ex, kind = Xo[k] - dr * SLIP, "cut"; break
        if force_t is not None and Xt[k] >= force_t:
            ex, kind = Xo[k] - dr * SLIP, "lit"; break
        hi, lo = (Xh[k], Xl[k]) if dr > 0 else (-Xl[k], -Xh[k])
        op = Xo[k] * dr
        if lo <= cur * dr:
            ex = (min(op, cur * dr) if not (lim and k == x0) else cur * dr) * dr - dr * SLIP
            kind = "be" if be_done else "stop"
            worst = min(worst, (ex - e) * dr)
            break
        worst = min(worst, lo - e * dr)
        if not (lim and k == x0) and hi >= tp * dr:
            ex = (max(op, tp * dr) if k > x0 else tp * dr) * dr
            kind = "target"; break
        mfe = max(mfe, (hi - e * dr) / risk)
        if be is not None and not be_done and hi - e * dr >= risk:
            cur, be_done = e + dr * be, True
        if not tc_done and Xe[k] >= fill_t + 900:
            tc_done = True
            if not be_done and mfe < 0.5 and (Xc[k] - e) * dr < -0.3 * risk:
                cut = True
        k += 1
    if ex is None:
        if not live or k <= x0:
            return None
        cl = float(Xc[N - 1])
        pts = (cl - e) * dr
        return {"x0": int(x0), "x1": int(N - 1), "e": float(e), "ex": cl, "risk": float(risk), "pts": float(pts),
                "worst": float(min(worst, pts)), "kind": "OPEN", "tp": float(tp), "stop": float(stop), "stop_now": float(cur),
                "be_done": bool(be_done), "cut": bool(cut)}
    pts = (ex - e) * dr
    return {"x0": int(x0), "x1": int(k), "e": float(e), "ex": float(ex), "risk": float(risk), "pts": float(pts),
            "worst": float(min(worst, pts)), "kind": kind, "tp": float(tp), "stop": float(stop)}


def in_kz(m, kz):
    return any(a <= m < b for a, b in KZ[kz])


def greedy(X, cands, outs, kz, maxpd, filt):
    """Apply time window / filters / 1 position at a time / max per day. outs[i] = sim result of cands[i]."""
    busy = -1
    cnt = collections.Counter()
    res = []
    for z, r in zip(cands, outs):
        if r is None or r["x0"] <= busy:
            continue
        if not filt(z["f"]):
            continue
        if not in_kz(int(X.Xm[r["x0"]]), kz):
            continue
        d = int(X.Xday[r["x0"]])
        if cnt[d] >= maxpd:
            continue
        cnt[d] += 1
        busy = r["x1"]
        res.append((z, r))
    return res


def r_of(r):
    return (r["pts"] * PV - COMM) / (r["risk"] * PV)


def pstats(X, T):
    """R stats per period for a list of (z, r)."""
    S = sessions()
    out = {}
    dates = X.dates
    for nm, a, b in PERIODS:
        R = np.array([r_of(r) for z, r in T if a <= dates[X.Xday[r["x0"]]] <= b])
        nw = sum(1 for s in S if a <= s <= b) / 5
        if len(R) == 0:
            out[nm] = (0, 0.0, 0.0, 0.0, 0.0, 0.0); continue
        gl = -R[R < 0].sum()
        t = float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))) if len(R) > 2 and R.std() > 0 else 0.0
        out[nm] = (int(len(R)), round(float(R.sum()), 2), round(len(R) / nw, 2), round(float(R[R > 0].sum() / gl), 2) if gl else 9.99,
                   round(t, 2), round(100 * float((R > 0).mean()), 1))
    return out


# ------------------------------------------------------------------------------------------------ grids
MD_GEN = {"tf": [5, 15], "osc": ["line", "hist"], "lv": ["pd", "sess", "all", "eq"]}
MD_SIM = {"ent": ["mkt", "lim"], "tgt": ["vix", 2.0, 3.0, "lvl"], "be": [None, 1.25], "tc": [False, True]}
MD_FLT = {"depth": [0.0, 0.25, 0.5], "reg": ["none", "h1h+", "h1h-", "h1l+", "h1l-", "m15h+"], "kz": ["all", "lon_ny", "ny", "lon"],
          "maxpd": [1, 2]}
SD_GEN = {"tf": [15, 60, 240], "imp": [1.0, 1.5], "bos": [False, True], "sw": [False, True]}
SD_SIM = {"stop": ["zone", "ext"], "ent": ["mkt", "lim"], "tgt": ["vix", 2.0, 3.0, "lvl"], "be": [None, 1.25], "tc": [False, True]}
SD_FLT = {"age": [1, 3, 10], "zh": [1.0, 99.0], "trend": ["none", "tr1+", "tr4+", "tr1-"], "kz": ["all", "lon_ny", "ny", "lon"],
          "maxpd": [1]}


def md_filter(F):
    dep = F["depth"]; rg = F["reg"]
    if rg == "none":
        return lambda f: f["depth"] >= dep
    key, sgn = rg[:-1], (1 if rg[-1] == "+" else -1)
    return lambda f: f["depth"] >= dep and f[key] * sgn > 0


def sd_filter(F):
    age, zh, tr = F["age"], F["zh"], F["trend"]
    if tr == "none":
        return lambda f: f["age"] <= age and f["zh"] <= zh
    key, sgn = tr[:-1], (1 if tr[-1] == "+" else -1)
    return lambda f: f["age"] <= age and f["zh"] <= zh and f[key] * sgn > 0


def combos(grid):
    ks = list(grid)
    return [dict(zip(ks, v)) for v in itertools.product(*[grid[k] for k in ks])]


def run_gen(job):
    fam, gp = job
    X = ctx_full()
    t0 = time.time()
    if fam == "md":
        cands = md_cands(X, **gp)
        SIM, FLT, mk = MD_SIM, MD_FLT, md_filter
    else:
        cands = sd_cands(X, **gp)
        SIM, FLT, mk = SD_SIM, SD_FLT, sd_filter
    rows = []
    for sp in combos(SIM):
        outs = [sim_x(X, z, sp) for z in cands]
        for fp in combos(FLT):
            T = greedy(X, cands, outs, fp["kz"], fp["maxpd"], mk(fp))
            rows.append({"fam": fam, "gen": gp, "sim": {k: v for k, v in sp.items()}, "flt": fp, "st": pstats(X, T),
                         "sig": hash(tuple(r["x0"] for z, r in T))})
    print(f"  {fam} {gp}: {len(cands)} cands, {len(rows)} variants, {time.time() - t0:.0f}s", flush=True)
    return rows


def sim_x(X, z, sp, force_t=None, live=False):
    """sp: ent, tgt, be (None = off, else breakeven at +1R with the stop to entry + be pts), tc, stop."""
    return sim_one(X, z, sp["ent"], sp["tgt"], sp["be"], sp["tc"], sp.get("stop", "ext"), force_t, live)


# ------------------------------------------------------------------------------------------------ run + pick
VAR_PATH = os.path.join(OUT, "md_variants.json.gz")
ST_KEYS = ("n", "R", "tpw", "pf", "t", "win")


def all_jobs():
    return [("md", g) for g in combos(MD_GEN)] + [("sd", g) for g in combos(SD_GEN)]


def run_all(procs=4):
    import gzip
    ctx_full()
    t0 = time.time()
    with Pool(procs) as pool:
        parts = pool.map(run_gen, all_jobs(), chunksize=1)
    rows = [r for p in parts for r in p]
    os.makedirs(OUT, exist_ok=True)
    comp = [{"fam": r["fam"], "gen": r["gen"], "sim": r["sim"], "flt": r["flt"], "sig": r["sig"],
             "st": {p: list(v) for p, v in r["st"].items()}} for r in rows]
    with gzip.open(VAR_PATH, "wt", encoding="utf-8") as fh:
        json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "grids": {"md": [MD_GEN, MD_SIM, MD_FLT], "sd": [SD_GEN, SD_SIM, SD_FLT]},
                   "st_keys": ST_KEYS, "rows": comp}, fh, separators=(",", ":"))
    print(f"{len(rows)} variants in {time.time() - t0:.0f}s -> {VAR_PATH}")


def load_rows():
    import gzip
    if "rows" in G:
        return G["rows"]
    with gzip.open(VAR_PATH, "rt", encoding="utf-8") as fh:
        d = json.load(fh)
    for r in d["rows"]:
        r["S"] = {p: dict(zip(ST_KEYS, v)) for p, v in r["st"].items()}
    G["rows"] = d["rows"]
    return d["rows"]


def vkey(r):
    return json.dumps([r["fam"], r["gen"], r["sim"], r["flt"]], sort_keys=True)


def grid_of(fam):
    return {"md": (MD_GEN, MD_SIM, MD_FLT), "sd": (SD_GEN, SD_SIM, SD_FLT)}[fam]


def neighbours(r, by):
    out = []
    for part, grid in zip(("gen", "sim", "flt"), grid_of(r["fam"])):
        for k, vals in grid.items():
            for v in vals:
                if v == r[part][k]:
                    continue
                q = {**r, part: {**r[part], k: v}}
                x = by.get(vkey(q))
                if x is not None:
                    out.append(x)
    return out


def eligible(r, min_n=25, max_tpw=4.5):
    h = r["S"]["H1"]
    return h["n"] >= min_n and h["tpw"] <= max_tpw


def pick(rows, fam, ref_ok=True):
    """H1 picks of one family: 'best' (top H1 t-stat), 'plateau' (top median H1 t of itself + every one-parameter
    neighbour), each optionally only among versions not negative in 2025 and 2021-24 (the reference years)."""
    R = [r for r in rows if r["fam"] == fam]
    by = {vkey(r): r for r in R}
    E = [r for r in R if eligible(r) and r["S"]["H1"]["R"] > 0]
    if ref_ok:
        E = [r for r in E if r["S"]["2025"]["R"] >= 0 and r["S"]["2124"]["R"] >= 0]
    best = max(E, key=lambda r: r["S"]["H1"]["t"]) if E else None
    top = sorted(E, key=lambda r: -r["S"]["H1"]["t"])[:400]
    for r in top:
        nb = neighbours(r, by)
        ts = [r["S"]["H1"]["t"]] + [x["S"]["H1"]["t"] for x in nb]
        r["plat"] = float(np.median(ts)); r["plat_pos"] = round(float(np.mean([x["S"]["H1"]["R"] > 0 for x in nb])), 2) if nb else 0
    plat = max(top, key=lambda r: r["plat"]) if top else None
    return best, plat


def chance(rows, fam):
    """Does a good H1 predict a good H2? Share of versions positive in H2: all eligible vs the top by H1."""
    E = [r for r in rows if r["fam"] == fam and eligible(r)]
    seen, D = set(), []
    for r in E:
        if r["sig"] in seen:
            continue
        seen.add(r["sig"]); D.append(r)
    pos = lambda L: round(100 * float(np.mean([r["S"]["H2"]["R"] > 0 for r in L])), 1) if L else None
    mean = lambda L: round(float(np.mean([r["S"]["H2"]["R"] for r in L])), 2) if L else None
    D.sort(key=lambda r: -r["S"]["H1"]["t"])
    top50, top1 = D[:50], D[:max(1, len(D) // 100)]
    h1pos = [r for r in D if r["S"]["H1"]["R"] > 0]
    allpos = [r for r in D if r["S"]["H1"]["R"] > 0 and r["S"]["H2"]["R"] > 0 and r["S"]["2025"]["R"] > 0 and r["S"]["2124"]["R"] > 0]
    rk = np.argsort(np.argsort([-r["S"]["H1"]["t"] for r in D]))
    rk2 = np.argsort(np.argsort([-r["S"]["H2"]["t"] for r in D]))
    rho = float(np.corrcoef(rk, rk2)[0, 1]) if len(D) > 2 else None
    return {"versions": sum(1 for r in rows if r["fam"] == fam), "eligible": len(E), "distinct": len(D),
            "h1_pos_pct": round(100 * len(h1pos) / max(len(D), 1), 1), "h2_pos_all_pct": pos(D), "h2_pos_top50_pct": pos(top50),
            "h2_pos_top1pct": pos(top1), "h2_meanR_all": mean(D), "h2_meanR_top50": mean(top50), "h2_meanR_top1pct": mean(top1),
            "h2_pos_given_h1_pos_pct": pos(h1pos), "pos_all_four": len(allpos), "rank_corr_h1_h2": round(rho, 3) if rho is not None else None}


def label(r):
    g, s, f = r["gen"], r["sim"], r["flt"]
    return f"{r['fam']} " + " ".join(f"{k}={v}" for k, v in {**g, **s, **f}.items())


def show(r):
    S = r["S"]
    return " | ".join(f"{p} n={S[p]['n']} R={S[p]['R']:+.1f} pf={S[p]['pf']} t={S[p]['t']} tpw={S[p]['tpw']} win={S[p]['win']}"
                      for p in ("H1", "H2", "2025", "2124"))


def print_picks():
    rows = load_rows()
    for fam in ("md", "sd"):
        print(f"== {fam}", json.dumps(chance(rows, fam)))
        for ref in (False, True):
            b, p = pick(rows, fam, ref)
            for nm, r in (("best", b), ("plateau", p)):
                if r:
                    print(f"  {nm} ref_ok={ref}: {label(r)}\n     {show(r)} plat={r.get('plat')} nb_pos={r.get('plat_pos')}")
        E = sorted([r for r in rows if r["fam"] == fam and eligible(r) and r["S"]["H1"]["R"] > 0], key=lambda r: -r["S"]["H1"]["t"])
        print("  top 15 by H1 t:")
        for r in E[:15]:
            print("   ", label(r), "\n      ", show(r))


# ------------------------------------------------------------------------------------------------ trades, sizing, money
def trades_of(X, v):
    """(z, r) list of one variant dict {fam, gen, sim, flt}."""
    cands = (md_cands if v["fam"] == "md" else sd_cands)(X, **v["gen"])
    outs = [sim_x(X, z, v["sim"]) for z in cands]
    mk = md_filter if v["fam"] == "md" else sd_filter
    return greedy(X, cands, outs, v["flt"]["kz"], v["flt"]["maxpd"], mk(v["flt"]))


def q_usd(usd, risk):
    return max(0, min(40, int(usd / (risk * PV))))


def tr_rec(X, z, r, q, setup):
    """One trade in the common format (+ the runlib columns)."""
    d = X.dates[X.Xday[r["x0"]]]
    ex_t = int(X.Xt[r["x1"]]) if r["kind"] in ("cut", "lit") else int(X.Xe[r["x1"]])
    per = r["pts"] * PV - COMM
    return {"day": d, "entry_t": int(X.Xt[r["x0"]]), "exit_t": ex_t, "dir": int(z["dir"]), "entry": round(r["e"], 2),
            "stop": round(r["stop"], 2), "target": round(r["tp"], 2), "exit": round(r["ex"], 2), "exit_kind": r["kind"],
            "r": round(per / (r["risk"] * PV), 3), "qty": int(q), "pnl_usd": round(q * per, 2), "setup": setup,
            # runlib columns
            "pnl": round(q * per, 2), "risk_pts": round(r["risk"], 2), "risk_usd": round(q * r["risk"] * PV, 2), "half": False,
            "trigger": setup, "mfe": None, "mae": round(-r["worst"] / r["risk"], 3), "bars_held": int(r["x1"] - r["x0"] + 1),
            "regime": "", "mult": 1.0, "low": round(min(q * (r["worst"] * PV - COMM), q * per), 2),
            "_worst": r["worst"], "_pts": r["pts"], "_risk": r["risk"]}


def sized_list(X, T, usd, setup):
    out = []
    for z, r in T:
        q = q_usd(usd, r["risk"])
        if q > 0:
            out.append(tr_rec(X, z, r, q, setup))
    return out


def lit_trades(comm=COMM, run="lit_live"):
    """LIT trades of a stored run at $comm a micro (lit_live is stored at $1.40)."""
    r = json.load(open(os.path.join(ROOT, "research", "runs", run + ".json"), encoding="utf-8"))
    T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    adj = comm - 1.40 if run == "lit_live" else 0.0
    dl = {d[0]: d[2] for d in r["days"]}
    for t in T:
        t["pnl"] = round(float(t["pnl"]) - adj * int(t["qty"]), 2)
        if t.get("mae") is not None:
            t["low"] = -min(float(t["mae"]), max(1.0, -float(t["r"]))) * float(t["risk_pts"]) * PV * int(t["qty"]) - comm * int(t["qty"])
        else:
            t["low"] = dl.get(t["day"], min(0.0, t["pnl"]))
        t["low"] = min(t["low"], t["pnl"])
        t["src"] = "lit"
    return T


def eval_item(t, qb):
    """An eval-path item: per-micro P&L / low, stop, base micros (sized down to 0.6 x room on the path)."""
    q = max(1, int(t["qty"]))
    return {"day": t["day"], "entry_t": t["entry_t"], "pm": t["pnl"] / q, "pl": min(t["low"], t["pnl"]) / q,
            "risk": float(t["risk_pts"]), "qb": int(qb)}


def eval_path(items, starts, horizon=60):
    """MFFU Builder 50K, a fresh eval started on every session in `starts`. items: day -> list of eval items in time
    order; micros = min(base micros, 0.6 x room / (stop x $2)), room = balance + today's P&L - trailing max loss (the
    eval-safe sizing, the same rule for LIT and the second strategy). Returns {start: (result, sessions)}."""
    from engine.analytics import PLANS
    plan = PLANS["builder_50k"]
    S = sessions()
    pos = {d: i for i, d in enumerate(S)}
    res = {}
    for st in starts:
        i0 = pos[st]
        bal = peak = plan["start"]; mll = bal - plan["mll"]; lock = plan["start"] + plan["lock_above"]
        r = ("OPEN", horizon)
        for k, day in enumerate(S[i0:i0 + horizon]):
            dp = low = 0.0
            for t in items.get(day, []):
                room = bal + dp - mll
                if room <= 0:
                    break
                q = min(t["qb"], int(0.6 * room / (t["risk"] * PV)))
                if q <= 0:
                    continue
                low = min(low, dp + q * t["pl"]); dp += q * t["pm"]
                low = min(low, dp)
            if bal + low <= mll or bal + dp <= mll:
                r = ("FAIL", k + 1); break
            bal += dp; peak = max(peak, bal); mll = min(max(mll, peak - plan["mll"]), lock)
            if bal - plan["start"] >= plan["target"]:
                r = ("PASS", k + 1); break
        res[st] = r
    return res


def eval_sum(res, a, b):
    rr = [v for d, v in res.items() if a <= d <= b]
    n = len(rr) or 1
    f = lambda kind, H: round(100 * sum(1 for x in rr if x[0] == kind and x[1] <= H) / n, 1)
    return {"p10": f("PASS", 10), "f10": f("FAIL", 10), "p20": f("PASS", 20), "f20": f("FAIL", 20)}


def period_table(T, eval_items=None, lit_days=None):
    """Per period: trades, tr/wk, win %, PF, net $, $/month, max DD, avg R (+ eval 2 wk / 1 mo pass/fail, corr with LIT)."""
    from tools import runlib as rl
    S = sessions()
    out = {}
    ev = eval_path(items_by_day([eval_item(t, t["qty"]) for t in T]), S) if eval_items else None
    for nm, a, b in PERIODS + (("2026", "2026-01-01", "2026-10-16"), ("all", "2021-11-01", "2026-10-16")):
        SS = [s for s in S if a <= s <= b]
        TT = [t for t in T if a <= t["day"] <= b]
        days = rl.days_of(TT, SS)
        if not TT:
            out[nm] = {"n": 0, "net": 0}
            continue
        c = rl._compact(TT, days)
        row = {k: c[k] for k in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "avg_r")}
        if ev is not None:
            row.update(eval_sum(ev, a, b))
        if lit_days is not None:
            row["corr_lit"] = corr(days, lit_days)
        out[nm] = row
    return out


def corr(days, other):
    a = [(x["pnl"], other.get(x["date"], 0.0)) for x in days]
    if len(a) < 20:
        return None
    x, y = np.array(a).T
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 2)


def daymap(T):
    d = collections.defaultdict(float)
    for t in T:
        d[t["day"]] += t["pnl"]
    return d


def combine(X, T_md, lit, mode, usd=None, eval_sized=False):
    """One account, LIT first. mode 'two': up to 2 trades a day, one position at a time: the second strategy never enters
    while LIT is in a trade, and is closed at market the moment LIT enters. mode 'one': max 1 trade a day total, first
    come first served (a second-strategy trade earlier in the day takes LIT's slot). T_md: (z, r) list. Returns the merged
    trade list (LIT trades as stored; second-strategy trades sized at $usd, or eval items when eval_sized)."""
    by = collections.defaultdict(list)
    for t in lit:
        by[t["day"]].append(t)
    out = []
    md_by = collections.defaultdict(list)
    for z, r in T_md:
        md_by[X.dates[X.Xday[r["x0"]]]].append((z, r))
    days = sorted(set(by) | set(md_by))
    for d in days:
        L = sorted(by.get(d, []), key=lambda t: t["entry_t"])
        Mx = md_by.get(d, [])
        if mode == "one":
            first_lit = L[0]["entry_t"] if L else None
            if Mx and (first_lit is None or X.Xt[Mx[0][1]["x0"]] < first_lit):
                z, r = Mx[0]
                if first_lit is not None and X.Xe[r["x1"]] > first_lit:
                    pass   # LIT's slot is taken: LIT skips the day (max 1 a day), the second trade runs normally
                x = _mk(X, z, r, usd, eval_sized, "second")
                if x:
                    out.append(x)
            else:
                out += L[:1]
            continue
        out += L
        taken = len(L)
        for z, r in Mx:
            if taken >= 2:
                break
            ft = int(X.Xt[r["x0"]])
            if any(t["entry_t"] <= ft < t["exit_t"] for t in L):
                continue
            nxt = [t["entry_t"] for t in L if t["entry_t"] > ft]
            et = int(X.Xt[r["x1"]])
            if nxt and nxt[0] <= et:
                r = sim_x(X, z, G["cur_sim"], force_t=nxt[0])
                if r is None:
                    continue
            x = _mk(X, z, r, usd, eval_sized, "second")
            if x:
                out.append(x)
                taken += 1
    out.sort(key=lambda t: t["entry_t"])
    return out


def _mk(X, z, r, usd, eval_sized, setup):
    if eval_sized:
        t = tr_rec(X, z, r, 1, setup)
        t["usd"] = usd
        return t
    q = q_usd(usd, r["risk"])
    return tr_rec(X, z, r, q, setup) if q > 0 else None


def items_by_day(T):
    by = collections.defaultdict(list)
    for t in sorted(T, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    return by


def money_line(nm, P):
    r = P.get(nm) or {}
    if not r.get("n"):
        return f"{nm}: no trades"
    s = (f"{nm}: n={r['n']} tpw={r['tpw']} win={r['win']}% PF={r['pf']} net={r['net']:+,} (${r['per_month']:,}/mo) DD={r['dd']:,} "
         f"avgR={r['avg_r']}")
    if "p10" in r:
        s += f" eval2wk {r['p10']}/{r['f10']} 1mo {r['p20']}/{r['f20']}"
    if r.get("corr_lit") is not None:
        s += f" corrLIT {r['corr_lit']}"
    return s


def report_version(v, usd_list=(300, 500, 800), main_usd=500, eval_usd=500):
    """Every number for one variant: own account at $300/$500/$800 risk (+ eval-safe on that base); with LIT (LIT size
    rule, run lit_live) on one account; eval with LIT (both eval-safe on one account)."""
    X = ctx_full()
    G["cur_sim"] = v["sim"]
    T = trades_of(X, v)
    lit = lit_trades()
    litd = daymap(lit)
    setup = "MACD-div" if v["fam"] == "md" else "SD-retest"
    rep = {"own": {}, "combo": {}}
    for usd in usd_list:
        TT = sized_list(X, T, usd, setup)
        rep["own"][f"usd{usd}"] = period_table(TT, True, litd)
    for mode in ("two", "one"):
        C = combine(X, T, lit, mode, usd=main_usd)
        Ls = [t for t in C if t.get("src") == "lit"]
        rep["combo"][mode] = {"merged": period_table(C, True), "lit_kept": len(Ls), "second_kept": len(C) - len(Ls),
                              "corr_daily_all": corr(rl_days(sized_list(X, T, main_usd, setup)), litd)}
        for usd in (300, 500):
            C = combine(X, T, lit, mode, usd=usd)
            ev = eval_path(items_by_day([eval_item(t, t["qty"]) for t in C]), sessions())
            rep["combo"][mode][f"eval_usd{usd}"] = {nm: eval_sum(ev, a, b) for nm, a, b in PERIODS}
    rep["combo"]["lit_only"] = period_table(lit, True)
    return T, rep


def rl_days(T):
    from tools import runlib as rl
    return rl.days_of(T, sessions())


# ------------------------------------------------------------------------------------------------ no look-ahead check
def check(v, n=30, seed=7, days_back=120):
    """Rebuild the version's signals on data CUT at each sampled signal bar (Market from `days_back` days before to the
    signal bar, nothing after) and compare signal time, direction, stop, CISD level, level target and filter features."""
    from engine import lit
    X = ctx_full()
    T = trades_of(X, v)
    rng = np.random.default_rng(seed)
    pick_ = rng.choice(len(T), size=min(n, len(T)), replace=False)
    bad, done = [], 0
    for q in sorted(pick_):
        z, r = T[q]
        j = z["j"]
        a = max(0, X.M.days[max(0, X.day[j] - days_back)][1])
        Mc = lit.Market(bars=X.M.b.slice(a, j + 1))
        Xc = Ctx(Mc, "none")
        cc = (md_cands if v["fam"] == "md" else sd_cands)(Xc, **v["gen"])
        hit = [c for c in cc if Xc.t[c["j"]] == X.t[j] and c["dir"] == z["dir"]]
        ok = bool(hit)
        if ok:
            c = hit[0]
            ok = (abs(c["stops"][v["sim"].get("stop", "ext")] - z["stops"][v["sim"].get("stop", "ext")]) < 1e-6
                  and abs(c["cisd"] - z["cisd"]) < 1e-6
                  and ((np.isnan(c["lvl"]) and np.isnan(z["lvl"])) or abs(c["lvl"] - z["lvl"]) < 1e-6)
                  and all((abs(c["f"][k] - z["f"][k]) < 1e-3) if isinstance(z["f"][k], float) and k in ("depth", "zh")
                          else c["f"][k] == z["f"][k] for k in z["f"]))
        done += 1
        if not ok:
            bad.append({"day": X.dates[X.day[j]], "t": int(X.t[j]), "full": {k: z[k] for k in ("dir", "cisd", "lvl", "f", "stops")},
                        "cut": ({k: hit[0][k] for k in ("dir", "cisd", "lvl", "f", "stops")} if hit else None)})
    return {"checked": done, "differ": len(bad), "examples": bad[:5]}


CHOSEN = {"fam": "md", "gen": {"tf": 5, "osc": "line", "lv": "all"}, "sim": {"ent": "mkt", "tgt": "vix", "be": None, "tc": True},
          "flt": {"depth": 0.5, "reg": "none", "kz": "lon_ny", "maxpd": 1}}
CHOSEN_USD = 500
RULES = [
    "Chart: NQ 5-minute, CME futures. Trade only 02:00-05:00 ET (London) and 09:30-11:00 ET (New York open); 1 trade a day.",
    "Liquidity: any LIT level of the day (Asia / London / NY session highs and lows, premarket box, previous day / week / "
    "month high and low, NWOG / NDOG gaps, build-ups = equal highs / lows). Wait for the first time today that price "
    "trades through one of them.",
    "Depth: the sweep must reach at least 0.5 x ATR(14, 5m) beyond the level.",
    "Confirmation (CISD): within 2 hours of the sweep a 5m candle closes back through the open of the run of candles that "
    "made the sweep extreme (for a short: closes below the open of the last up-candle run into the high).",
    "MACD divergence (12/26/9, MACD line, 5m): at that close the MACD line at the sweep-extreme bar is weaker than at the "
    "highest prior swing high of the last 4 hours (lowest swing low for a long) while price made a higher high (lower low).",
    "Entry: market at the next 5m open. Stop: 1 tick beyond the sweep extreme (6-80 pts, else no trade).",
    "Target: the 18:00 ET open +/- 1 VIX one-day move (VIX/100/sqrt(252) x price), at least 1.5R away (else no trade), "
    "banked at 8R. No breakeven.",
    "15-minute check (as LIT): 15 minutes after the fill, if the trade never reached +0.5R and is more than 0.3R under water, "
    "exit at market.",
    "Flat at 15:55 ET. Size: $500 risk a trade = 500 / (stop pts x $2) micros, max 40 (eval: also capped at 0.6 x room to "
    "the trailing max loss / (stop x $2)).",
]


def common_json(X, T, usd, setup):
    keys = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind", "r", "qty", "pnl_usd", "setup")
    return [{k: t[k] for k in keys} for t in sized_list(X, T, usd, setup)]


def save_all():
    """Store the H1 picks + the chosen version (rl.save md2_*), the chosen version's trades (research/second/md_best.json),
    its combo with LIT and the no-look-ahead check."""
    from tools import runlib as rl
    rows = load_rows()
    X = ctx_full()
    lit = lit_trades()
    summary = {"chance": {f: chance(rows, f) for f in ("md", "sd")}, "picks": [],
               "versions": {f: sum(1 for r in rows if r["fam"] == f) for f in ("md", "sd")}}
    by = {vkey(r): r for r in rows}
    picks = []
    for fam in ("md", "sd"):
        for ref in (False, True):
            b, p = pick(rows, fam, ref)
            for nm, r in (("best", b), ("plateau", p)):
                if r is not None:
                    picks.append((f"{fam}_{nm}{'_ref' if ref else ''}", r))
    picks.append(("best", by[vkey(CHOSEN)]))
    seen = set()
    for pid, r in picks:
        k = vkey(r)
        if k in seen and pid != "best":
            continue
        seen.add(k)
        v = {"fam": r["fam"], "gen": r["gen"], "sim": r["sim"], "flt": r["flt"]}
        T, rep = report_version(v)
        setup = "MACD-div" if r["fam"] == "md" else "SD-retest"
        TT = sized_list(X, T, CHOSEN_USD, setup)
        S = rl.score(TT, sessions())
        rid = "md2_" + pid
        own = rep["own"]["usd500"]
        verdict = (f"H1 {own['H1'].get('net', 0):+,} / H2 {own['H2'].get('net', 0):+,} / 2025 {own['2025'].get('net', 0):+,} / "
                   f"2021-24 {own['2124'].get('net', 0):+,} at $500 risk a trade")
        st = "promising" if r["fam"] == "md" else "rejected"
        rl.save(rid, f"Second strategy: {label(r)}", "other", "A second strategy next to LIT (MACD divergence / supply-demand)",
                params={"variant": v, "report": rep, "label": label(r), "R": r["S"]}, sizing={"rule": f"usd{CHOSEN_USD}"},
                trades=TT, scored=S, status=st, verdict=verdict, writeup="second-md", tags=["second", r["fam"]])
        summary["picks"].append({"id": rid, "pick": pid, "label": label(r), "variant": v, "R": r["S"], "report": rep})
        print(rid, label(r))
        for nm in ("H1", "H2", "2025", "2124"):
            print("   ", money_line(nm, own))
        if pid == "best":
            G["cur_sim"] = v["sim"]
            C = combine(X, T, lit, "two", usd=CHOSEN_USD)
            rl.save("md2_combo_lit", "LIT + MACD divergence at a sweep on one account (LIT first, max 2 a day)", "other",
                    "LIT and the second strategy on one account", params={"variant": v, "mode": "two", "lit_run": "lit_live"},
                    sizing={"lit": "LIT size rule ($1.90/micro)", "second": f"usd{CHOSEN_USD}"}, trades=C,
                    scored=rl.score(C, sessions()), status="promising", writeup="second-md", tags=["second", "combo"],
                    verdict="LIT + second strategy, see second-md.md")
            ck = check(v, n=40)
            summary["check"] = ck
            print("look-ahead check:", ck["checked"], "checked,", ck["differ"], "differ")
            out = {"name": "MACD divergence at a liquidity sweep (London + NY open)", "id": rid, "built": time.strftime("%Y-%m-%d"),
                   "params": {**v, "sizing": f"${CHOSEN_USD} risk a trade (micros = {CHOSEN_USD} / (stop x $2), max 40)",
                              "costs": "$1.90 a micro round trip + 1 tick slippage on market entries, stop and market exits",
                              "data": "CME NQ1! 5m (TradingView), 1m for the 2026 trade path"},
                   "rules": RULES, "trades": common_json(X, T, CHOSEN_USD, setup), "report": rep, "lookahead_check": ck}
            json.dump(out, open(os.path.join(OUT, "md_best.json"), "w"), indent=1, default=float)
    json.dump(summary, open(os.path.join(OUT, "md_summary.json"), "w"), indent=1, default=float)
    return summary


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run_all(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif cmd == "picks":
        print_picks()
    elif cmd == "save":
        save_all()
    elif cmd == "check":
        print(json.dumps(check(CHOSEN, n=int(sys.argv[2]) if len(sys.argv) > 2 else 40), default=str))
