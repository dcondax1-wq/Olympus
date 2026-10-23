"""STOP-HUNT core (research, owner 2026-10-23): retail stop pools, the hunt through them, the reversal trigger, objective
targets and the trade walk. Research / paper only: no adapter, no NinjaTrader, no order code; nothing in the live bot
imports this module. The research driver is tools/stophunt.py; the write-up is research/writeups/stophunt.md.

Owner's idea: "When all the retail traders get stopped out, it's usually because their stop loss is at a low or high. If we
wait for a resweep, or inducement, then a strong candle move toward our DOL (draw on liquidity), we could find gold."

Everything here is causal (no look-ahead): a pool is used only from the 5m bar AFTER the one at whose close it is known
(a fractal N bars each side is known when the N-th bar to its right has closed; a session high when the session is over;
an HTF bar only when its last 5m bar has closed), a signal is known at a 5m close and is traded from the next bar.
tools/stophunt.py `lookahead` re-derives the final trades from data cut at each signal bar.

Pieces (all prices in points of the back-adjusted TradingView CME NQ1! series):
  load()          5m bars 2021-11 .. 2026-10-16 (+ 1m bars of 2026 for the trade path), sessions from 18:00 ET, ATR(14)
  build_pools()   every retail stop pool, each its own type (see TYPES), with a price (a trendline has a slope), the 5m
                  bar it is known at, its life, an obviousness score, and the first 5m bar that trades through it (= hunt)
  events()        hunts: the 5m bars that trade through one or more pools of a chosen set (grouped per bar and side)
  signals()       the hunt -> (resweep / inducement / immediate reclaim) -> strong candle back toward the draw
  fills(), walk() entry (market, limit at the trigger candle's middle or its FVG, 1m CISD) and the managed trade
  dol_tables()    the nearest unswept opposite pools at every 5m close (the draw on liquidity = target candidates)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import numpy as np
import pandas as pd

try:                                   # numba makes the research grid ~100x faster; without it the code is the same, slower
    from numba import njit
except Exception:                      # pragma: no cover
    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK, PV, COMM = 0.25, 2.0, 1.90

# ------------------------------------------------------------------------------------------------ pool types
TYPES = ["f1", "f5", "f15", "f60", "eq5", "eq15", "range", "tl", "asia", "lon", "ny", "on", "pd", "pw", "r100", "r50"]
TYPE_TXT = {"f1": "1m swing high/low (fractal, N bars each side)", "f5": "5m swing high/low", "f15": "15m swing high/low",
            "f60": "1h swing high/low", "eq5": "equal highs/lows on 5m swings (2+ touches)",
            "eq15": "equal highs/lows on 15m swings (2+ touches)", "range": "edge of a tight 2h/4h consolidation (2+ touches each side)",
            "tl": "3-touch trendline (rising lows / falling highs; stops beyond the line)", "asia": "Asia session high/low (18:00-02:00)",
            "lon": "London session high/low (02:00-08:00)", "ny": "prior NY session (RTH 09:30-16:00) high/low",
            "on": "overnight high/low (18:00-09:30)", "pd": "prior CME day high/low (18:00-17:00)", "pw": "prior week high/low",
            "r100": "round number (x00, unadjusted price)", "r50": "half round number (x50)"}
TI = {t: i for i, t in enumerate(TYPES)}
BASE_SCORE = np.array([0.5, 1.0, 2.0, 3.0, 2.0, 3.0, 2.0, 2.5, 3.0, 3.0, 3.5, 3.5, 3.5, 4.0, 1.5, 1.0])
# retail-visible feature classes (for "how many features coincide"): swing, equal, range, trendline, session/day, week, round
CLASS = np.array([0, 0, 0, 0, 1, 1, 2, 3, 4, 4, 4, 4, 4, 5, 6, 6])
LIFE = {"f1": 96, "f5": 288, "f15": 576, "f60": 1440, "eq5": 288, "eq15": 576, "range": 288, "asia": 432, "lon": 432,
        "ny": 432, "on": 288, "pd": 576, "pw": 1500, "r100": 288, "r50": 288}
# session buckets by minutes since 18:00 ET (rel): Asia 18-02, London 02-08, NY AM 08-12, NY PM 12-16
BUCKETS = ((0, 480), (480, 840), (840, 1080), (1080, 1320))
BUCKET_NAMES = ("Asia", "London", "NY AM", "NY PM")
ENTRY_CUT = 1290                       # no new entry after 15:30 ET (rel 1290); flat 15:55 (MFFU: flat by 16:10)
FLAT_REL5 = 1310                       # the 5m bar 15:50 closes at 15:55
FLAT_REL1 = 1314                       # the 1m bar 15:54 closes at 15:55


# ------------------------------------------------------------------------------------------------ bars
def _frame(df):
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    et = pd.to_datetime(df["time"].values, unit="s", utc=True).tz_convert("America/New_York")
    mod = (et.hour * 60 + et.minute).values.astype(np.int64)
    sdate = (et.tz_localize(None).normalize() + pd.to_timedelta((mod >= 18 * 60).astype(int), unit="D"))
    loc = et.tz_localize(None).values.astype("datetime64[s]").astype(np.int64)
    return df, mod, sdate.strftime("%Y-%m-%d").values, loc, et.dayofweek.values


def load(cut_t=None, with_1m=True):
    """Bars as numpy arrays. cut_t (unix s): keep only the 5m bars that OPEN before cut_t and the 1m bars that open before it
    (look-ahead check: the data as it was at that moment)."""
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")) if with_1m else None
    return bars(df, d1, cut_t=cut_t)


def bars(df, d1=None, cut_t=None, m1_from=None, m1_to=None):
    """load() on given frames (time, open, high, low, close): the research CSVs, or a live window (engine/second.py plugin
    "stop_hunt": LIT's 5m window + its 1m bars). d1 None = no 1m bars (every trade walks on 5m). m1_from / m1_to override the
    1m-path span (default: from the 2026-01-02 session to the last 1m bar, as the research)."""
    df, mod, sdays, loc, dow = _frame(df)
    if cut_t is not None:
        k = int(np.searchsorted(df["time"].values, cut_t))
        df, mod, sdays, loc, dow = df.iloc[:k].reset_index(drop=True), mod[:k], sdays[:k], loc[:k], dow[:k]
    days, sid = np.unique(sdays, return_inverse=True)
    t = df["time"].values.astype(np.int64)
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))["rolls"]
    adj = np.zeros(len(df))
    for r in rolls:                    # unadjusted = adjusted - adj
        adj[t < r["switch_t"]] += r["gap"]
    o, h, l, c = (df[x].values.astype(np.float64) for x in ("open", "high", "low", "close"))
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    rel = (mod - 1080) % 1440
    body = np.abs(c - o)
    mb10 = pd.Series(body).shift(1).rolling(10, min_periods=5).mean().bfill().values   # mean body of the 10 bars before
    B = dict(t=t, o=o, h=h, l=l, c=c, mod=mod, rel=rel.astype(np.int64), sid=sid.astype(np.int64), days=days, loc=loc,
             adj=adj, atr=atr, mb10=mb10, dow=dow, n=len(t))
    st = np.r_[0, np.nonzero(np.diff(B["sid"]))[0] + 1]
    B["sess_start"] = st.astype(np.int64)
    B["sess_end"] = np.r_[st[1:], len(t)].astype(np.int64)
    B["flat5"] = _flat_idx(B["sid"], B["rel"], FLAT_REL5)
    B["sflat5"] = _sess_flat_idx(B["sid"], B["rel"], FLAT_REL5)
    # VIX one-day move (LIT's target band): the VIX close of the day before the trading day x the 18:00 open
    vix = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
    vd, vc = list(vix["date"].astype(str)), vix["close"].values.astype(float)
    import bisect
    nd = len(days)
    B["open18"] = np.full(nd, np.nan); B["vixmove"] = np.full(nd, np.nan)
    for s, a in zip(B["sid"][st], st):
        B["open18"][s] = o[a]
        j = bisect.bisect_left(vd, str(days[s])) - 1
        if j >= 0:
            B["vixmove"][s] = vc[j] / 100.0 / math.sqrt(252.0) * o[a]
    if d1 is not None:
        d1, mod1, sd1, loc1, _ = _frame(d1)
        if cut_t is not None:
            k = int(np.searchsorted(d1["time"].values, cut_t))
            d1, mod1, sd1, loc1 = d1.iloc[:k].reset_index(drop=True), mod1[:k], sd1[:k], loc1[:k]
        dmap = {d: i for i, d in enumerate(days)}
        sid1 = np.array([dmap.get(x, -1) for x in sd1], np.int64)
        rel1 = ((mod1 - 1080) % 1440).astype(np.int64)
        B["m1"] = dict(t=d1["time"].values.astype(np.int64), o=d1["open"].values.astype(float), h=d1["high"].values.astype(float),
                       l=d1["low"].values.astype(float), c=d1["close"].values.astype(float), rel=rel1, sid=sid1, loc=loc1,
                       n=len(d1))
        B["m1"]["flat"] = _flat_idx(sid1, rel1, FLAT_REL1)
        B["m1"]["sflat"] = _sess_flat_idx(sid1, rel1, FLAT_REL1)
        # 1m path only from the first full 1m session (2026-01-02 session start)
        B["m1_from"] = 1767308400 if len(d1) else 1 << 62      # the 2026-01-02 session (2026-01-01 18:00 ET)
        B["m1_to"] = int(B["m1"]["t"][-1]) if len(d1) else 0
    else:
        z = np.zeros(0, np.int64)
        B["m1"] = dict(t=z, o=np.zeros(0), h=np.zeros(0), l=np.zeros(0), c=np.zeros(0), rel=z, sid=z, loc=z, n=0, flat=z, sflat=z)
        B["m1_from"], B["m1_to"] = 1 << 62, 0
    if m1_from is not None:
        B["m1_from"] = int(m1_from)
    if m1_to is not None:
        B["m1_to"] = int(m1_to)
    return B


def _flat_idx(sid, rel, flat_rel):
    """Per bar: index of the last bar of its session with rel <= flat_rel (the 15:55 flat), -1 if none at/after it."""
    n = len(sid)
    out = np.full(n, -1, np.int64)
    last = -1
    for i in range(n - 1, -1, -1):
        if i == n - 1 or sid[i + 1] != sid[i]:
            last = -1
        if rel[i] <= flat_rel and last == -1:
            last = i
        out[i] = last if last >= i else -1
    return out


def _sess_flat_idx(sid, rel, flat_rel):
    """Per bar: index of the last bar of the same session BUCKET (Asia ends 02:00, London 08:00, NY AM 12:00, NY PM 15:55)."""
    n = len(sid)
    out = np.full(n, -1, np.int64)
    bk = np.searchsorted(np.array([480, 840, 1080, 99999]), rel, side="right")
    last = -1
    for i in range(n - 1, -1, -1):
        if i == n - 1 or sid[i + 1] != sid[i] or bk[i + 1] != bk[i]:
            last = -1
        if rel[i] <= flat_rel and last == -1:
            last = i
        out[i] = last if last >= i else -1
    return out


def htf(B, tf):
    """Clock-aligned tf-minute bars from 5m within a session; last = 5m index of the bar's last 5m bar (known at its close).
    On cut data the final HTF bar is dropped if its clock period has not ended (still forming)."""
    sec = tf * 60
    b = B["loc"] // sec
    g = np.r_[True, (b[1:] != b[:-1]) | (B["sid"][1:] != B["sid"][:-1])]
    first = np.nonzero(g)[0]
    last = np.r_[first[1:] - 1, B["n"] - 1]
    H = dict(h=np.maximum.reduceat(B["h"], first), l=np.minimum.reduceat(B["l"], first), first=first, last=last)
    if B.get("cut") and len(last) and (int(B["loc"][-1]) + 300) % sec != 0:
        H = {k: v[:-1] for k, v in H.items()}
    return H


# ------------------------------------------------------------------------------------------------ pools
def _frac(h, l, N):
    """Fractal highs/lows with N bars each side (strictly above the left N, >= the right N). Returns (fh, fl) bar indices."""
    from numpy.lib.stride_tricks import sliding_window_view as sw
    m = len(h)
    if m < 2 * N + 1:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    W = sw(h, 2 * N + 1); V = sw(l, 2 * N + 1)
    ch, cl = W[:, N], V[:, N]
    isH = (ch > W[:, :N].max(1)) & (ch >= W[:, N + 1:].max(1))
    isL = (cl < V[:, :N].min(1)) & (cl <= V[:, N + 1:].min(1))
    return np.nonzero(isH)[0] + N, np.nonzero(isL)[0] + N


class _Acc:
    def __init__(self):
        self.cols = {k: [] for k in ("px", "slope", "t0", "side", "known", "birth", "life", "typ", "strength", "touch")}

    def add(self, px, side, known, birth, life, typ, strength=0, touch=1, slope=0.0, t0=None):
        px = np.atleast_1d(np.asarray(px, float)); m = len(px)
        if m == 0:
            return
        f = lambda v, dt_: np.broadcast_to(np.asarray(v, dt_), (m,)).copy()
        self.cols["px"].append(px); self.cols["slope"].append(f(slope, float))
        self.cols["t0"].append(f(known if t0 is None else t0, np.int64)); self.cols["side"].append(f(side, np.int64))
        self.cols["known"].append(f(known, np.int64)); self.cols["birth"].append(f(birth, np.int64))
        self.cols["life"].append(f(life, np.int64)); self.cols["typ"].append(f(TI[typ], np.int64))
        self.cols["strength"].append(f(strength, np.int64)); self.cols["touch"].append(f(touch, np.int64))

    def done(self):
        return {k: np.concatenate(v) if v else np.zeros(0) for k, v in self.cols.items()}


@njit(cache=True)
def _eq_pools(fb, fpx, fknown, side, h, l, atr, look):
    """Equal highs (side 1) / lows (-1) from fractals (bars fb, prices fpx, known fknown, in bar order). A new fractal within
    max(1 pt, 0.1 ATR) of an earlier one of the last `look` bars that is still intact (no bar between went beyond the pair by
    more than the tolerance) makes an equal-highs pool at the outer price, known when the new fractal is known."""
    m = len(fb)
    opx = np.empty(m); okn = np.empty(m, np.int64); obi = np.empty(m, np.int64); otc = np.empty(m, np.int64)
    k = 0
    for i in range(m):
        b = fb[i]
        tol = max(1.0, 0.1 * atr[b])
        touch = 1
        outer = fpx[i]
        first = b
        for j in range(i - 1, -1, -1):
            if fb[j] < b - look:
                break
            if abs(fpx[j] - fpx[i]) > tol:
                continue
            ref = max(fpx[j], fpx[i]) if side > 0 else min(fpx[j], fpx[i])
            ok = True
            for q in range(fb[j] + 1, b):
                if (side > 0 and h[q] > ref + tol) or (side < 0 and l[q] < ref - tol):
                    ok = False
                    break
            if ok:
                touch += 1
                outer = max(outer, fpx[j]) if side > 0 else min(outer, fpx[j])
                first = min(first, fb[j])
        if touch >= 2:
            opx[k] = outer; okn[k] = fknown[i]; obi[k] = first; otc[k] = touch; k += 1
    return opx[:k], okn[:k], obi[:k], otc[:k]


@njit(cache=True)
def _range_pools(h, l, atr, sid, M, width_k, look_touch):
    """Edges of tight consolidations: at bar i the last M bars (one session) span <= width_k x ATR and each edge was touched
    (within 0.15 ATR) by 2+ separate swings (bars 3+ apart). Registered once per new pair of edges; known at bar i."""
    n = len(h)
    ohi = np.empty(n); olo = np.empty(n); okn = np.empty(n, np.int64); oth = np.empty(n, np.int64); otl = np.empty(n, np.int64)
    k = 0
    last_hi = -1e18; last_lo = 1e18
    for i in range(M, n):
        if sid[i - M + 1] != sid[i]:
            continue
        hi = -1e18; lo = 1e18
        for q in range(i - M + 1, i + 1):
            hi = max(hi, h[q]); lo = min(lo, l[q])
        A = atr[i]
        if hi - lo > width_k * A:
            continue
        if abs(hi - last_hi) <= 0.25 and abs(lo - last_lo) <= 0.25:
            continue
        th = 0; tl = 0; lh = -100; ll = -100
        for q in range(i - M + 1, i + 1):
            if h[q] >= hi - 0.15 * A and q - lh >= look_touch:
                th += 1; lh = q
            if l[q] <= lo + 0.15 * A and q - ll >= look_touch:
                tl += 1; ll = q
        if th >= 2 and tl >= 2:
            ohi[k] = hi; olo[k] = lo; okn[k] = i; oth[k] = th; otl[k] = tl; k += 1
            last_hi = hi; last_lo = lo
    return ohi[:k], olo[:k], okn[:k], oth[:k], otl[:k]


@njit(cache=True)
def _tl_pools(fb, fpx, fknown, side, h, l, atr, look, gap):
    """3-touch trendlines: rising lows (side -1: the stops sit below the line) / falling highs (side 1). For each new
    fractal p3, the longest line p1 -> p3 (p1 < p2 < p3 for lows, within `look` bars, touches `gap`+ bars apart) whose middle
    fractal p2 sits within 0.15 ATR of the line and that no bar between p1 and p3 broke by more than that. Known when p3 is
    known; price(t) = px1 + slope x (t - b1); life = the line's own span after p3 (max 288 bars)."""
    m = len(fb)
    opx = np.empty(m); osl = np.empty(m); ot0 = np.empty(m, np.int64); okn = np.empty(m, np.int64); olf = np.empty(m, np.int64)
    k = 0
    for i3 in range(m):
        b3 = fb[i3]; p3 = fpx[i3]
        tol = 0.15 * atr[b3]
        best = -1; bi2 = -1
        for i1 in range(i3 - 1, -1, -1):
            b1 = fb[i1]
            if b1 < b3 - look:
                break
            p1 = fpx[i1]
            if b3 - b1 < 2 * gap:
                continue
            if (side < 0 and not (p1 < p3)) or (side > 0 and not (p1 > p3)):
                continue
            s = (p3 - p1) / (b3 - b1)
            for i2 in range(i1 + 1, i3):
                b2 = fb[i2]
                if b2 - b1 < gap or b3 - b2 < gap:
                    continue
                v2 = p1 + s * (b2 - b1)
                if abs(fpx[i2] - v2) > tol:
                    continue
                if (side < 0 and not (p1 < fpx[i2] < p3)) or (side > 0 and not (p1 > fpx[i2] > p3)):
                    continue
                ok = True
                for q in range(b1 + 1, b3):
                    v = p1 + s * (q - b1)
                    if (side < 0 and l[q] < v - tol) or (side > 0 and h[q] > v + tol):
                        ok = False
                        break
                if ok:
                    best = i1; bi2 = i2
                    break
        if best >= 0:
            b1 = fb[best]
            opx[k] = fpx[best]; osl[k] = (p3 - fpx[best]) / (b3 - b1); ot0[k] = b1; okn[k] = fknown[i3]
            olf[k] = min(288, b3 - b1); k += 1
    return opx[:k], osl[:k], ot0[:k], okn[:k], olf[:k]


@njit(cache=True)
def _round_pools(c, h, l, adj, grid, quiet):
    """Round numbers (unadjusted multiples of `grid`): the nearest level above and below each close becomes a pool when no
    bar of the last `quiet` bars traded through it and it is not already an active (untraded) pool."""
    n = len(c)
    opx = np.empty(2 * n); osd = np.empty(2 * n, np.int64); okn = np.empty(2 * n, np.int64); olv = np.empty(2 * n, np.int64)
    k = 0
    lastU = np.full(4096, -1, np.int64); lastLv = np.full(4096, -1, np.int64)
    lastD = np.full(4096, -1, np.int64); lastLvD = np.full(4096, -1, np.int64)
    for i in range(quiet, n):
        u = c[i] - adj[i]
        up = math.floor(u / grid) * grid + grid
        dn = math.ceil(u / grid) * grid - grid
        for sd in (1, -1):
            U = up if sd > 0 else dn
            A = U + adj[i]
            ok = True
            for q in range(i - quiet + 1, i + 1):
                if (sd > 0 and h[q] >= A) or (sd < 0 and l[q] <= A):
                    ok = False
                    break
            if not ok:
                continue
            key = int(U / grid) % 4096
            if sd > 0:
                r = lastU[key]; lv = lastLv[key]
            else:
                r = lastD[key]; lv = lastLvD[key]
            if lv == int(U) and r >= 0 and i - r < 288:
                still = True
                for q in range(r + 1, i + 1):
                    if (sd > 0 and h[q] >= A) or (sd < 0 and l[q] <= A):
                        still = False
                        break
                if still:
                    continue
            opx[k] = A; osd[k] = sd; okn[k] = i; olv[k] = int(U); k += 1
            if sd > 0:
                lastU[key] = i; lastLv[key] = int(U)
            else:
                lastD[key] = i; lastLvD[key] = int(U)
    return opx[:k], osd[:k], okn[:k], olv[:k]


@njit(cache=True)
def _sweeps(px, slope, t0, side, known, life, h, l, adj, typ, round_lo):
    """First 5m bar after `known` (within `life` bars) that trades 1+ tick through each pool (-1 = never), and the end of
    its active life (sweep bar, or the last bar it is alive + 1). Round numbers die at a contract roll (adj change)."""
    m = len(px); n = len(h)
    sw = np.full(m, -1, np.int64); end = np.empty(m, np.int64); pxs = np.full(m, np.nan)
    for i in range(m):
        k0 = known[i] + 1
        k1 = min(known[i] + life[i], n - 1)
        e = k1 + 1
        for k in range(k0, k1 + 1):
            if typ[i] >= round_lo and adj[k] != adj[known[i]]:
                e = k
                break
            p = px[i] + slope[i] * (k - t0[i])
            if (side[i] > 0 and h[k] >= p + 0.25) or (side[i] < 0 and l[k] <= p - 0.25):
                sw[i] = k; e = k; pxs[i] = p
                break
        end[i] = e
    return sw, end, pxs


def build_pools(B, use_1m=True, verbose=False, types=None):
    """Every retail stop pool. Returns dict of arrays (one row per pool) incl. sweep bar and score. types: only these pool
    types (names of TYPES; None = all, the research default). The pools of a type do not depend on the others, so a subset
    gives exactly the rows of those types (the live plugin builds only what its pool set hunts)."""
    want = set(TYPES if types is None else types)
    acc = _Acc()
    h, l, atr = B["h"], B["l"], B["atr"]
    n = B["n"]
    frac_store = {}
    for tf, name in ((5, "f5"), (15, "f15"), (60, "f60")):
        H = htf(B, tf) if tf > 5 else dict(h=h, l=l, first=np.arange(n), last=np.arange(n))
        for N in (2, 3, 4, 5):
            fh, fl = _frac(H["h"], H["l"], N)
            for side, ff, arr in ((1, fh, H["h"]), (-1, fl, H["l"])):
                ok = ff + N < len(H["last"])
                ff = ff[ok]
                kn = H["last"][ff + N]; bi = H["last"][ff]
                if name in want:
                    acc.add(arr[ff], side, kn, bi, LIFE[name], name, strength=N)
                if N == 2:
                    frac_store[(tf, side)] = (bi, arr[ff], kn)
                if N == 3 and tf == 5:
                    frac_store[("tl5", side)] = (bi, arr[ff], kn)
    if use_1m and "f1" in want and "m1" in B and B["m1"]["n"]:
        M1 = B["m1"]
        for N in (2, 3, 4, 5):
            fh, fl = _frac(M1["h"], M1["l"], N)
            for side, ff, arr in ((1, fh, M1["h"]), (-1, fl, M1["l"])):
                ff = ff[ff + N < M1["n"]]
                tk = M1["t"][ff + N]
                k5 = np.searchsorted(B["t"], tk, side="right") - 1
                inside = (k5 >= 0) & (tk < B["t"][np.maximum(k5, 0)] + 300)
                k5 = np.where(inside, k5, k5 + 1)
                tb = np.searchsorted(B["t"], M1["t"][ff], side="right") - 1
                ok = (k5 < n) & (k5 >= 0)
                acc.add(arr[ff][ok], side, k5[ok], np.maximum(tb[ok], 0), LIFE["f1"], "f1", strength=N)
    # equal highs / lows
    for tf, name, look in ((5, "eq5", 288), (15, "eq15", 576)):
        if name not in want:
            continue
        for side in (1, -1):
            bi, px, kn = frac_store[(tf, side)]
            o = np.argsort(bi, kind="stable")
            opx, okn, obi, otc = _eq_pools(bi[o].astype(np.int64), px[o].astype(float), kn[o].astype(np.int64), side, h, l, atr, look)
            acc.add(opx, side, okn, obi, LIFE[name], name, touch=otc)
    # range edges (2h within 3.5 ATR, 4h within 5 ATR)
    for M, wk in ((24, 3.5), (48, 5.0)) if "range" in want else ():
        hi, lo, kn, th, tl = _range_pools(h, l, atr, B["sid"], M, wk, 3)
        acc.add(hi, 1, kn, kn - M + 1, LIFE["range"], "range", strength=M, touch=th)
        acc.add(lo, -1, kn, kn - M + 1, LIFE["range"], "range", strength=M, touch=tl)
    # trendlines (5m N=3 swings, 12h; 15m N=2 swings mapped to 5m bars, 2 days)
    for side_line, side_fr in ((-1, -1), (1, 1)) if "tl" in want else ():
        bi, px, kn = frac_store[("tl5", side_fr)]
        o = np.argsort(bi, kind="stable")
        opx, osl, ot0, okn, olf = _tl_pools(bi[o].astype(np.int64), px[o].astype(float), kn[o].astype(np.int64), side_line, h, l, atr, 144, 6)
        for a in range(len(opx)):
            acc.add(opx[a], side_line, okn[a], ot0[a], int(olf[a]), "tl", strength=5, slope=osl[a], t0=ot0[a])
        bi, px, kn = frac_store[(15, side_fr)]
        o = np.argsort(bi, kind="stable")
        opx, osl, ot0, okn, olf = _tl_pools(bi[o].astype(np.int64), px[o].astype(float), kn[o].astype(np.int64), side_line, h, l, atr, 576, 9)
        for a in range(len(opx)):
            acc.add(opx[a], side_line, okn[a], ot0[a], int(olf[a]), "tl", strength=15, slope=osl[a], t0=ot0[a])
    # session / day / week levels
    rel, mod, sid = B["rel"], B["mod"], B["sid"]
    days = B["days"]
    wk_hi, wk_lo, wk_last = {}, {}, {}
    for a, b in zip(B["sess_start"], B["sess_end"]):
        rr, mm = rel[a:b], mod[a:b]
        for nm, msk in (("asia", rr < 480), ("lon", (rr >= 480) & (rr < 840)), ("ny", (mm >= 570) & (mm < 960) & (rr < 1320)),
                        ("on", rr < 930)):
            ii = np.nonzero(msk)[0]
            if len(ii) < 6:
                continue
            ii = a + ii
            kn = int(ii[-1])
            if nm == "on" and B.get("cut") and kn == n - 1 and rel[kn] < 925:
                continue                  # cut data: the overnight is not over yet
            if B.get("cut") and kn == n - 1 and nm in ("asia", "lon", "ny"):
                end_rel = {"asia": 475, "lon": 835, "ny": 1315}[nm]
                if rel[kn] < end_rel:
                    continue
            ih = ii[np.argmax(h[ii])]; il = ii[np.argmin(l[ii])]
            if nm in want:
                acc.add(h[ih], 1, kn, ih, LIFE[nm], nm); acc.add(l[il], -1, kn, il, LIFE[nm], nm)
        if "pd" in want and not (B.get("cut") and b == n and rel[n - 1] < 1375):
            ih = a + int(np.argmax(h[a:b])); il = a + int(np.argmin(l[a:b]))
            acc.add(h[ih], 1, b - 1, ih, LIFE["pd"], "pd"); acc.add(l[il], -1, b - 1, il, LIFE["pd"], "pd")
        y, w, _ = dt.date.fromisoformat(str(days[sid[a]])).isocalendar()
        kk = (y, w)
        ih = a + int(np.argmax(h[a:b])); il = a + int(np.argmin(l[a:b]))
        if kk not in wk_hi or h[ih] > h[wk_hi[kk]]:
            wk_hi[kk] = ih
        if kk not in wk_lo or l[il] < l[wk_lo[kk]]:
            wk_lo[kk] = il
        wk_last[kk] = b - 1
    wkeys = sorted(wk_last)
    for kk in (wkeys[:-1] if (B.get("cut")) else wkeys) if "pw" in want else ():
        kn = wk_last[kk]
        acc.add(h[wk_hi[kk]], 1, kn, wk_hi[kk], LIFE["pw"], "pw"); acc.add(l[wk_lo[kk]], -1, kn, wk_lo[kk], LIFE["pw"], "pw")
    # round numbers
    for grid, nm in ((100.0, "r100"), (50.0, "r50")):
        if nm not in want:
            continue
        opx, osd, okn, olv = _round_pools(B["c"], h, l, B["adj"], grid, 48)
        if nm == "r50":
            keep = (olv % 100) != 0
            opx, osd, okn = opx[keep], osd[keep], okn[keep]
        for sd in (1, -1):
            m = osd == sd
            acc.add(opx[m], sd, okn[m], okn[m], LIFE[nm], nm)
    P = acc.done()
    P["typ"] = P["typ"].astype(np.int64)
    # obviousness score: type base + strength of a swing (N-2) x 0.25 + extra touches of equal highs x 0.5
    sc = BASE_SCORE[P["typ"]].copy()
    isf = np.isin(P["typ"], [TI["f1"], TI["f5"], TI["f15"], TI["f60"]])
    sc[isf] += 0.25 * (P["strength"][isf] - 2)
    ise = np.isin(P["typ"], [TI["eq5"], TI["eq15"]])
    sc[ise] += 0.5 * (P["touch"][ise] - 2)
    P["score"] = sc
    P["cls"] = CLASS[P["typ"]]
    sw, end, pxs = _sweeps(P["px"], P["slope"], P["t0"], P["side"], P["known"], P["life"], h, l, B["adj"], P["typ"], TI["r100"])
    P["sweep"], P["end"], P["px_sw"] = sw, end, pxs
    if verbose:
        for t in TYPES:
            m = P["typ"] == TI[t]
            print(f"  pools {t:6s} {int(m.sum()):8d}  swept {int((sw[m] >= 0).sum()):8d}", flush=True)
    return P


# ------------------------------------------------------------------------------------------------ hunts (events)
@njit(cache=True)
def _events(swb, side, pxs, score, cls, birth, typ, mask, atr):
    m = len(swb)
    ej = np.empty(m, np.int64); es = np.empty(m, np.int64); ep = np.empty(m); esc = np.empty(m); enc = np.empty(m, np.int64)
    eag = np.empty(m, np.int64); etm = np.empty(m, np.int64)
    k = 0
    i = 0
    while i < m:
        j = swb[i]; sd = side[i]
        q = i
        while q < m and swb[q] == j and side[q] == sd:
            q += 1
        found = False
        pref = 0.0; smax = -1.0; age = 0; tm = 0
        for z in range(i, q):
            if mask[z]:
                if not found or (sd > 0 and pxs[z] > pref) or (sd < 0 and pxs[z] < pref):
                    pref = pxs[z]
                found = True
                smax = max(smax, score[z]); age = max(age, j - birth[z]); tm |= (1 << typ[z])
        if found:
            A = atr[j - 1] if j > 0 else atr[0]
            cm = 0
            for z in range(i, q):
                if abs(pxs[z] - pref) <= 0.3 * A:
                    cm |= (1 << cls[z])
            nc = 0
            while cm:
                nc += cm & 1
                cm >>= 1
            ej[k] = j; es[k] = sd; ep[k] = pref; esc[k] = smax; enc[k] = nc; eag[k] = age; etm[k] = tm; k += 1
        i = q
    return ej[:k], es[:k], ep[:k], esc[:k], enc[:k], eag[:k], etm[:k]


def sorted_sweeps(P):
    """Pools that were hunted, sorted by (sweep bar, side): the input of events()."""
    ok = P["sweep"] >= 0
    idx = np.nonzero(ok)[0]
    o = np.lexsort((P["side"][idx], P["sweep"][idx]))
    return idx[o]


def events(P, order, mask, B, min_score=0.0, min_cls=1, min_age=0):
    """Hunt events for the pools in mask (bool per pool): dict of arrays j (hunt bar), side (1 = highs taken = short setup),
    p (outermost pool of the set taken by that bar), score (most obvious pool), ncls (retail feature classes within 0.3 ATR
    of p swept by that bar), age (bars since the oldest pool was born), tmask (types)."""
    o = order
    ej, es, ep, esc, enc, eag, etm = _events(P["sweep"][o], P["side"][o], P["px_sw"][o], P["score"][o], P["cls"][o],
                                            P["birth"][o], P["typ"][o], mask[o], B["atr"])
    k = (esc >= min_score) & (enc >= min_cls) & (eag >= min_age)
    return dict(j=ej[k], side=es[k], p=ep[k], score=esc[k], ncls=enc[k], age=eag[k], tmask=etm[k])


# ------------------------------------------------------------------------------------------------ signals
MODES = ("any", "fast", "rs", "idm", "pre", "rs_idm", "rs_or_idm")


@njit(cache=True)
def _cisd_s(o, c, a, ee, sg):
    """LIT's CISD level in direction space (sg = +1 long, -1 short): the open of the first bar of the last unbroken run of
    against-candles into the extreme bar ee (within 3 bars of it, run at most 30 bars, not before bar a). nan if none."""
    j = ee
    while j > ee - 3 and j > a and not (sg * c[j] < sg * o[j]):
        j -= 1
    if not (sg * c[j] < sg * o[j]):
        return np.nan
    st = j
    while st - 1 >= a and sg * c[st - 1] < sg * o[st - 1] and st > ee - 30:
        st -= 1
    return sg * o[st]


@njit(cache=True)
def _signals(ej, es, ep, esc, o, h, l, c, atr, mb10, rel, sid, sess_start, fhb, flb,
             W, mode, rs_kind, kb, btype, struct, fvg, depth, cut_rel):
    """The state machine per hunt (direction space: a long after sell stops under a low were taken; shorts mirrored).
    Returns arrays: sig (5m bar the signal is known at its close), dr, ext_d (hunt extreme), p_d (pool), mid_d (50% of the
    trigger candle), fvg_d (near edge of its fair value gap or nan), score, flags (1 rs, 2 idm, 4 pre), j."""
    m = len(ej); n = len(o)
    S = np.empty(m, np.int64); D = np.empty(m, np.int64); X = np.empty(m); Pp = np.empty(m); MD = np.empty(m); FV = np.empty(m)
    SC = np.empty(m); FL = np.empty(m, np.int64); J = np.empty(m, np.int64); CZ = np.empty(m)
    k = 0
    for e in range(m):
        j = ej[e]
        if j < 2 or j >= n:
            continue
        dr = -es[e]
        s = sid[j]
        a = sess_start[s] if s < len(sess_start) else 0
        A = atr[j - 1]
        p = dr * ep[e]
        # pre-inducement (LIT style): a 5m swing (2 bars each side) of the pool's side between the pool and 1 ATR beyond it,
        # formed in the 36 bars before the hunt and confirmed before it (it is taken on the way into the pool)
        F = flb if dr > 0 else fhb
        pre = False
        lo_i = np.searchsorted(F, j - 36)
        for z in range(lo_i, len(F)):
            f = F[z]
            if f + 2 > j - 1:
                break
            fp = l[f] if dr > 0 else -h[f]
            if p < fp <= p + A:
                pre = True
                break
        ext = 1e18; arg = j; bounce = -1e18; inside = False; rs_bar = -1; idm_bar = -1; il = np.nan
        cz = np.nan
        found = False
        for q in range(j, min(j + W + 1, n)):
            if sid[q] != s or rel[q] > cut_rel:
                break
            if dr > 0:
                oq, hq, lq, cq = o[q], h[q], l[q], c[q]
            else:
                oq, hq, lq, cq = -o[q], -l[q], -h[q], -c[q]
            if q > j:
                if rs_bar < 0:
                    if (rs_kind == 0 or rs_kind == 2) and inside and lq < p:
                        rs_bar = q
                    elif (rs_kind == 1 or rs_kind == 2) and lq < ext and (bounce - ext) >= 0.5 * A and q - arg >= 2:
                        rs_bar = q
                if idm_bar < 0 and not np.isnan(il) and lq < il:
                    idm_bar = q
            if lq < ext:
                ext = lq; arg = q; bounce = hq
                if struct == 1:
                    cz = _cisd_s(o, c, a, arg, dr)
            else:
                bounce = max(bounce, hq)
            # trigger at q
            mode_ok = True
            if mode == 1:
                mode_ok = q <= j + 1
            elif mode == 2:
                mode_ok = rs_bar >= 0 and rs_bar < q
            elif mode == 3:
                mode_ok = idm_bar >= 0 and idm_bar < q
            elif mode == 4:
                mode_ok = pre
            elif mode == 5:
                mode_ok = rs_bar >= 0 and rs_bar < q and idm_bar >= 0 and idm_bar < q
            elif mode == 6:
                mode_ok = (rs_bar >= 0 and rs_bar < q) or (idm_bar >= 0 and idm_bar < q)
            body = cq - oq
            thr = kb * A if btype == 0 else kb * mb10[q]
            ok = mode_ok and cq > p and body >= thr and body > 0 and (p - ext) >= depth * A
            if ok and struct == 1:
                ok = (not np.isnan(cz)) and cq > cz
            if ok and struct == 2:
                # market structure shift: close beyond the latest confirmed 5m swing high (direction space) of the last
                # 48 bars before the hunt .. now
                G = fhb if dr > 0 else flb
                hi_i = np.searchsorted(G, q - 2) - 1      # swings at bar <= q-3 are confirmed by q-1
                lvl = np.nan
                if hi_i >= 0:
                    f = G[hi_i]
                    if f >= j - 48:
                        lvl = h[f] if dr > 0 else -l[f]
                ok = (not np.isnan(lvl)) and cq > lvl
            if ok:
                sgb = q
                fv = np.nan
                if fvg == 1:
                    q1 = q + 1
                    if q1 >= n or sid[q1] != s or rel[q1] > cut_rel:
                        ok = False
                    else:
                        l1 = l[q1] if dr > 0 else -h[q1]
                        hm = h[q - 1] if dr > 0 else -l[q - 1]
                        if l1 > hm and l1 > ext:
                            fv = l1; sgb = q1
                        else:
                            ok = False
                if ok:
                    S[k] = sgb; D[k] = dr; X[k] = ext; Pp[k] = p; MD[k] = math.floor((oq + 0.5 * body) / 0.25) * 0.25; FV[k] = fv; SC[k] = esc[e]
                    FL[k] = (1 if rs_bar >= 0 and rs_bar < q else 0) + (2 if idm_bar >= 0 and idm_bar < q else 0) + (4 if pre else 0)
                    J[k] = j; CZ[k] = cz; k += 1
                    found = True
                    break
            # register a 1-bar internal swing low at q-1 (confirmed by q's close), above the extreme: early reversal
            # traders' stops (the internal inducement)
            if q - 1 > j and q - 2 >= j:
                if dr > 0:
                    l1, l0, l2 = l[q - 1], l[q - 2], l[q]
                else:
                    l1, l0, l2 = -h[q - 1], -h[q - 2], -h[q]
                if l1 < l0 and l1 < l2 and l1 > ext + 0.25 and q - 1 != arg:
                    il = l1
            if cq > p:
                inside = True
        if not found:
            continue
    return S[:k], D[:k], X[:k], Pp[:k], MD[:k], FV[:k], SC[:k], FL[:k], J[:k], CZ[:k]


def signals(ev, B, F, W=12, mode=0, rs_kind=2, kb=0.8, btype=0, struct=1, fvg=0, depth=0.0):
    """Signals for one setup config; one per (signal bar, direction): the most obvious hunt wins (then the latest)."""
    S, D, X, Pp, MD, FV, SC, FL, J, CZ = _signals(ev["j"], ev["side"], ev["p"], ev["score"], B["o"], B["h"], B["l"], B["c"],
                                                B["atr"], B["mb10"], B["rel"], B["sid"], B["sess_start"], F["fh"], F["fl"],
                                                W, mode, rs_kind, kb, btype, struct, fvg, depth, ENTRY_CUT)
    if not len(S):
        return dict(sig=S, dr=D, ext=X, p=Pp, mid=MD, fvg=FV, score=SC, flags=FL, j=J, cz=CZ)
    o = np.lexsort((J, SC, D, S))[::-1]          # per (sig, dr): highest score, then latest hunt
    key = S[o] * 2 + (D[o] > 0)
    _, first = np.unique(key, return_index=True)
    sel = np.sort(o[first])
    sel = sel[np.argsort(S[sel], kind="stable")]
    return dict(sig=S[sel], dr=D[sel], ext=X[sel], p=Pp[sel], mid=MD[sel], fvg=FV[sel], score=SC[sel], flags=FL[sel], j=J[sel], cz=CZ[sel])


def swing_index(B):
    """5m swings (2 bars each side) as sorted bar indices: fh (highs), fl (lows) (known 2 bars later)."""
    fh, fl = _frac(B["h"], B["l"], 2)
    return dict(fh=fh.astype(np.int64), fl=fl.astype(np.int64))


# ------------------------------------------------------------------------------------------------ draw-on-liquidity tables
DOL_K = 10
DOL_CLS = (0.0, 2.0, 3.0)                     # class thresholds: any pool / score >= 2 (HTF-ish) / score >= 3 (obvious)


@njit(cache=True)
def _dol(n, c, h, l, known, end, side, px, score, flat, K, thr):
    """At every 5m close: the K nearest active (known, not yet taken, not expired) opposite pools per class threshold, in
    direction space ascending. TB[i, 0] = highs above (long targets), TB[i, 1] = -lows below (short targets)."""
    nc = len(thr)
    TB = np.full((n, 2, nc, K), np.nan, np.float32)
    P = len(px)
    act = np.empty(P, np.int64)
    na = 0
    ptr = 0
    for i in range(n):
        while ptr < P and known[ptr] <= i:
            if flat[ptr]:
                act[na] = ptr; na += 1
            ptr += 1
        w = 0
        for a in range(na):
            p = act[a]
            if end[p] > i:
                act[w] = p; w += 1
        na = w
        for a in range(na):
            p = act[a]
            if side[p] > 0:
                v = px[p]
                if v <= h[i]:
                    continue
                d = 0
            else:
                v = -px[p]
                if v <= -l[i]:
                    continue
                d = 1
            for ci in range(nc):
                if score[p] < thr[ci]:
                    continue
                row = TB[i, d, ci]
                # insertion into the sorted K (dedupe within a tick)
                if not np.isnan(row[K - 1]) and v >= row[K - 1]:
                    continue
                dup = False
                pos = K - 1
                for z in range(K):
                    if np.isnan(row[z]) or row[z] > v:
                        pos = z
                        break
                    if abs(row[z] - v) < 0.2:
                        dup = True
                        break
                if dup:
                    continue
                for z in range(K - 1, pos, -1):
                    row[z] = row[z - 1]
                row[pos] = v
    return TB


def dol_tables(P, B):
    o = np.argsort(P["known"], kind="stable")
    flat = (P["slope"][o] == 0.0)
    return _dol(B["n"], B["c"], B["h"], B["l"], P["known"][o], P["end"][o], P["side"][o], P["px"][o], P["score"][o], flat,
                DOL_K, np.array(DOL_CLS))


# ------------------------------------------------------------------------------------------------ fills + walk
@njit(cache=True)
def _fill(t, o, h, l, c, rel, sid, k_start, dr, kind, lim, stop_d, maxbars, s, cut_rel):
    """Entry on a path (5m or 1m bars) from bar k_start. kind 0 market at its open + 1 tick; 1/2 limit at lim (fills when
    price trades 1 tick through it, at the limit or a better open); 3 a 1m CISD (close above the open of the last run of
    down candles into the low since the signal) -> next open + 1 tick. Returns (fill bar, entry, is_limit) or (-1, 0, 0)."""
    n = len(o)
    if k_start >= n or sid[k_start] != s or rel[k_start] > cut_rel:
        return -1, 0.0, 0
    if kind == 0:
        e = (o[k_start] if dr > 0 else -o[k_start]) + 0.25
        if e - stop_d <= 0:
            return -1, 0.0, 0
        return k_start, e, 0
    if kind == 1 or kind == 2:
        if np.isnan(lim):
            return -1, 0.0, 0
        for k in range(k_start, min(k_start + maxbars, n)):
            if sid[k] != s or rel[k] > cut_rel:
                return -1, 0.0, 0
            od = o[k] if dr > 0 else -o[k]
            ld = l[k] if dr > 0 else -h[k]
            if ld <= lim - 0.25:
                return k, min(od, lim), 1
        return -1, 0.0, 0
    # kind 3: 1m CISD
    lowk = k_start; lowv = 1e18
    for k in range(k_start, min(k_start + maxbars, n - 1)):
        if sid[k] != s or rel[k] > cut_rel:
            return -1, 0.0, 0
        ld = l[k] if dr > 0 else -h[k]
        if ld <= stop_d:
            return -1, 0.0, 0
        if ld < lowv:
            lowv = ld; lowk = k
        if k > lowk:
            lvl = _cisd_s(o, c, max(0, k_start - 30), lowk, dr)
            ck = c[k] if dr > 0 else -c[k]
            if not np.isnan(lvl) and ck > lvl and sid[k + 1] == s and rel[k + 1] <= cut_rel:
                e = (o[k + 1] if dr > 0 else -o[k + 1]) + 0.25
                if e - stop_d <= 0:
                    return -1, 0.0, 0
                return k + 1, e, 0
    return -1, 0.0, 0


@njit(cache=True)
def _walk(o, h, l, c, k0, kf, dr, e, sp, risk, T, be_at, be_off, tcb, lim, part_px, part_f):
    """One trade in direction space from fill bar k0 to the flat bar kf. Stop first when stop and target share a bar; no
    target on a limit's fill bar; stop / time / flat exits get 1 tick slippage, targets fill at the limit. BE: at be_at R
    the stop goes to entry + be_off. tcb: the 15-minute check bar count (3 on 5m, 15 on 1m): at its close, never +0.5R and
    more than 0.3R against -> out at the next open. part_px: half (part_f) off at the first pool on the way, then BE.
    Returns (pts per micro, exit bar, kind 0 STOP 1 BE 2 TARGET 3 T15 4 FLAT 5 PSTOP, mfe R, mae R)."""
    cur = sp; moved = False; mfe = 0.0; mae = 0.0; parted = False; bank = 0.0; cut = False
    for k in range(k0, kf + 1):
        if dr > 0:
            ok_, hk, lk, ck = o[k], h[k], l[k], c[k]
        else:
            ok_, hk, lk, ck = -o[k], -l[k], -h[k], -c[k]
        rest = (1.0 - part_f) if parted else 1.0
        if cut:
            px = ok_ - 0.25
            return bank + rest * (px - e), k, 3, mfe, mae
        if lk <= cur:
            px = (min(ok_, cur) if (k > k0 or lim == 0) else cur) - 0.25
            kind = 5 if parted else (1 if moved else 0)
            return bank + rest * (px - e), k, kind, mfe, min(mae, (px - e) / risk)
        mae = min(mae, (lk - e) / risk)
        if not (lim == 1 and k == k0):
            mfe = max(mfe, (hk - e) / risk)
            if part_px > 0 and not parted and hk >= part_px and part_px < T:
                fp = max(ok_, part_px) if k > k0 else part_px
                bank = part_f * (fp - e); parted = True
                if not moved:
                    cur = max(cur, e + be_off); moved = True
                rest = 1.0 - part_f
            if hk >= T:
                px = max(ok_, T) if k > k0 else T
                return bank + rest * (px - e), k, 2, mfe, mae
            if be_at > 0 and not moved and hk >= e + be_at * risk:
                cur = e + be_off; moved = True
        if tcb > 0 and k - k0 == tcb - 1 and not moved and mfe < 0.5 and ck < e - 0.3 * risk and k + 1 <= kf:
            cut = True
    if dr > 0:
        ck = c[kf]
    else:
        ck = -c[kf]
    rest = (1.0 - part_f) if parted else 1.0
    return bank + rest * (ck - 0.25 - e), kf, 4, mfe, mae


EXIT_KINDS = ("STOP", "BE", "TARGET", "T15", "FLAT", "PSTOP")
