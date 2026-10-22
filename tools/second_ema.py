"""Second strategy next to LIT, EMA family (owner 2026-10-22: "find 1-2 strategies to trade ALONGSIDE LIT and make them
profitable, the way LIT went from not profitable to PF 4 by tuning on 2026").

Idea: borrow what makes LIT work and put it on an EMA trend trade.
  trend     higher-timeframe EMA trend (15m / 1h / 4h EMA 21 over EMA 50, closed bars only) or the 5m 8/21 (opening hour)
  pullback  a run of counter-trend 5m candles that reaches the 5m EMA 21 (or 50)
  sweep     optional: the pullback low takes a confirmed 5m swing low first (stop hunt, then go)
  trigger   5m CISD back in the trend: a close beyond the open of the first candle of that counter-trend run
            (displacement: the trigger candle's body >= k x ATR(14) 5m)
  entry     next 5m open + 1 tick (market)
  stop      1 tick beyond the pullback extreme (the sweep wick), never a fixed distance; size follows the stop
  exits     fixed R / the VIX-band objective (18:00 open +/- k VIX one-day moves, >= 1.5R, banked at 8R) / ride with a 15m
            close through the 15m EMA 21; BE + costs at 1R; a 15-minute check like LIT's t_check; flat 15:55
Regime filters: VXN level, day of week, first-hour range vs daily ATR, gap, ADX / EMA slope (chop), VWAP side, high-impact
news (data/news/events.csv), opening range.

No look-ahead: a 5m signal is known at its close; HTF values come from bars that CLOSED at or before it; swing lows are
used only once confirmed (k=2) before the pullback started; daily values are from earlier sessions. `lookahead` recomputes
every feature of sampled trades on data cut at the entry bar.
Costs: $1.90 a micro round trip (0.95 pt) + 1 tick on market entries and on stop / signal / time / flat exits; a target
fills at the limit. Stop and target in one bar = stop.
Selection (the LIT way): parameters picked on 2026 H1 (Jan 2 - Jun 30), checked untouched on 2026 H2 (Jul 1 - Oct 16);
2025 and 2021-24 reference. Plateau over spike. Futures data only (data/NQ_5m.csv). Paper research; no engine / live file
touched.

    python -X utf8 tools/second_ema.py grid        # every variant in R (H1/H2/2025/2021-24) -> research/runs/_cache/ema2_grid_*
    python -X utf8 tools/second_ema.py pick        # H1 picks (best + plateau) + chance -> research/second/ema_picks_<mode>.json
    python -X utf8 tools/second_ema.py lookahead   # 30 trades of the pick: features on data cut at the signal == full data
    python -X utf8 tools/second_ema.py save        # money, evals, LIT combo; rl.save ema2_*; research/second/ema_best.json
    EMA2_ENTRY=lim ...                             # the same with a limit entry back at the CISD level (30 min)
"""
from __future__ import annotations

import bisect
import collections
import itertools
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import retail_standalone as RS  # noqa: E402

OUT = os.path.join(ROOT, "research", "second")
TICK, PV, COMM = 0.25, 2.0, 1.90
CPTS = COMM / PV                      # commission in points per micro (0.95)
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "2026": ("2026-01-01", "2026-10-16"),
        "2025": ("2025-01-01", "2025-12-31"), "2021-24": ("2021-11-01", "2024-12-31"), "all": ("2021-11-01", "2026-10-16")}
MIN_STOP, MAX_STOP = 6.0, 80.0
WINS = {"all": (120, 930), "lonny": (180, 690), "ny": (570, 930), "am": (570, 690), "oh": (575, 630), "pre": (120, 570),
        "ny_noon": (570, 720), "lon": (180, 570)}

D = RS.D


# ================================================================================================ data + indicators
def load():
    d = RS.load()
    if "e21" in d:
        return d
    c = d["c"]
    for p in (8, 21, 50):
        d[f"e{p}"] = RS.ema(c, p)
    d["atr"] = RS.atr({"h": d["h"], "l": d["l"], "c": c})
    for tf in (15, 60, 240):
        H = RS.htf(tf)
        e21, e50 = RS.ema(H["c"], 21), RS.ema(H["c"], 50)
        a = RS.atr(H)
        d[f"t{tf}"] = np.nan_to_num(RS.to5(H, np.sign(e21 - e50)))
        d[f"c{tf}"] = np.nan_to_num(RS.to5(H, np.sign(H["c"] - e21)))
        d[f"e21_{tf}"] = RS.to5(H, e21)
        d[f"atr{tf}"] = RS.to5(H, a)
        d[f"slope{tf}"] = RS.to5(H, (e21 - np.r_[np.full(3, np.nan), e21[:-3]]) / a)
        if tf == 15:
            d["adx15"] = RS.to5(H, adx(H))
            E = [RS.ema(H["c"], n) for n in (8, 13, 21, 34, 55)]
            d["rib15"] = RS.to5(H, np.where(np.all([E[i] > E[i + 1] for i in range(4)], axis=0), 1,
                                             np.where(np.all([E[i] < E[i + 1] for i in range(4)], axis=0), -1, 0)).astype(float))
            d["rib15"] = np.nan_to_num(d["rib15"])
    # 15m close-through-EMA21 flags (the ride exit), known at the 15m close
    H = RS.htf(15)
    e21 = RS.ema(H["c"], 21)
    xl = np.zeros(d["n"], bool); xs = xl.copy()
    xl[H["last"][H["c"] < e21]] = True; xs[H["last"][H["c"] > e21]] = True
    d["x15"] = (xl, xs)
    d["x5"] = (c < d["e21"], c > d["e21"])
    day_ctx(d)
    return d


def adx(H, n=14):
    h, l, c = H["h"], H["l"], H["c"]
    up = np.r_[0, h[1:] - h[:-1]]; dn = np.r_[0, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0); ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    w = lambda x: pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().values
    atr_ = w(tr)
    pdi, ndi = 100 * w(pdm) / atr_, 100 * w(ndm) / atr_
    dx = 100 * abs(pdi - ndi) / np.maximum(pdi + ndi, 1e-9)
    return w(dx)


def _vol(name):
    df = pd.read_csv(os.path.join(ROOT, "data", f"{name}_1d.csv"))
    return list(df["date"].astype(str)), df["close"].values.astype(float)


def day_ctx(d):
    """Per session (all from earlier sessions or from bars already closed): open18, RTH open index, prior RTH close,
    daily ATR (14 prior RTH ranges), VIX / VXN prior close, VIX one-day move, gap at 09:30, news minutes."""
    ns = len(d["days"])
    sid, mod = d["sid"], d["mod"]
    first = np.r_[0, np.flatnonzero(np.diff(sid)) + 1]
    open18 = d["o"][first]
    rth = (mod >= 570) & (mod < 960)
    rh = pd.Series(np.where(rth, d["h"], -np.inf)).groupby(sid).max().reindex(range(ns)).values
    rl = pd.Series(np.where(rth, d["l"], np.inf)).groupby(sid).min().reindex(range(ns)).values
    idx = np.arange(d["n"])
    rc = pd.Series(np.where(rth, d["c"], np.nan)).groupby(sid).last().reindex(range(ns)).values
    ro = pd.Series(np.where(rth, idx, np.nan)).groupby(sid).min().reindex(range(ns)).values
    rng = np.where(np.isfinite(rh) & np.isfinite(rl), rh - rl, np.nan)
    atr_d = pd.Series(rng).shift(1).rolling(14, min_periods=5).mean().values
    vd, vc = _vol("VIX"); xd, xc = _vol("VXN")
    vix = np.full(ns, np.nan); vxn = np.full(ns, np.nan)
    for s, day in enumerate(d["days"]):
        j = bisect.bisect_left(vd, day) - 1
        if j >= 0:
            vix[s] = vc[j]
        j = bisect.bisect_left(xd, day) - 1
        if j >= 0:
            vxn[s] = xc[j]
    pclose = np.r_[np.nan, rc[:-1]]
    gap = np.full(ns, np.nan)
    ok = np.isfinite(ro)
    gap[ok] = (d["o"][ro[ok].astype(int)] - pclose[ok]) / atr_d[ok]
    ev = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
    ev = ev[ev["impact"] == "high"]
    news = collections.defaultdict(list)
    for a, b in zip(ev["date"], ev["time_et"]):
        hh, mm = str(b).split(":")
        news[str(a)].append(int(hh) * 60 + int(mm))
    d.update(open18=open18, rth_open=ro, atr_d=atr_d, vix=vix, vxn=vxn, vmove=vix / 100 / math.sqrt(252) * open18,
             gap=gap, pclose=pclose, news=news, sfirst=first)


# ================================================================================================ candidates (CISD after a pullback)
FEATS = ("dir", "sig", "ei", "e", "stop", "risk", "mod", "dow", "t15", "c15", "t60", "t240", "s5", "e8x21", "touch21",
         "touch50", "swept", "sdepth", "disp", "nrun", "depth", "slope15", "slope60", "adx15", "rib15", "vix", "vxn", "gap",
         "fhr", "vwap", "orb", "odrive", "news", "pdir", "lvl")


def candidates():
    """Every 5m CISD that ends a counter-trend run (both directions), with its features, all known at the signal close."""
    if "cand" in D:
        return D["cand"]
    d = load()
    n = d["n"]
    sid, mod = d["sid"], d["mod"]
    rows = []
    # VWAP (RTH) and opening range (09:30-10:00) per bar, causal
    rthm = (mod >= 570) & (mod < 960)
    tp = (d["h"] + d["l"] + d["c"]) / 3
    pv = pd.Series(tp * d["v"] * rthm).groupby(sid).cumsum().values
    vv = pd.Series(d["v"] * rthm).groupby(sid).cumsum().values
    vwap = np.where(vv > 0, pv / np.maximum(vv, 1e-9), np.nan)
    orm = (mod >= 570) & (mod < 600)
    orh = pd.Series(np.where(orm, d["h"], -np.inf)).groupby(sid).cummax().values
    orl = pd.Series(np.where(orm, d["l"], np.inf)).groupby(sid).cummin().values
    rh = pd.Series(np.where(rthm, d["h"], -np.inf)).groupby(sid).cummax().values
    rl = pd.Series(np.where(rthm, d["l"], np.inf)).groupby(sid).cummin().values
    fh, fl = fractal_masks(d["h"], d["l"])
    for dr in (1, -1):
        if dr > 0:
            O, H, L, C = d["o"], d["h"], d["l"], d["c"]
            FL = fl
        else:
            O, H, L, C = -d["o"], -d["l"], -d["h"], -d["c"]
            FL = fh
        e8, e21, e50 = dr * d["e8"], dr * d["e21"], dr * d["e50"]
        atr = d["atr"]
        bear = C < O
        start, lvl, low, active, last_s, prev_bear = -1, 0.0, 0.0, False, -1, -9
        swl = collections.deque(maxlen=20)      # confirmed swing lows (index, price) in this direction's space
        for i in range(n):
            s = sid[i]
            if s != last_s:
                active = False; last_s = s
            q = i - 2                              # fractal at q is confirmed at the close of q+2 = i
            if q >= 0 and FL[q]:
                swl.append((q, L[q]))
            if bear[i]:
                if not active:
                    start, lvl, low, active = i, O[i], L[i], True
                elif i != prev_bear + 1 and L[i] < low:
                    lvl = O[i]                       # a new down series that extends the pullback: its open is the level
                prev_bear = i
                low = min(low, L[i])
                continue
            if not active:
                continue
            low = min(low, L[i])
            if i - start > 24:
                active = False
                continue
            if C[i] > lvl:
                active = False
                if i + 1 >= n or sid[i + 1] != s:
                    continue
                m = mod[i]
                if not (110 <= m < 935):
                    continue
                ei = i + 1
                e = O[ei] + TICK
                stop = low - TICK
                risk = e - stop
                if not (MIN_STOP <= risk <= MAX_STOP):
                    continue
                a = atr[i]
                # sweep: a swing low confirmed before the run started, inside the last 48 bars, taken by the pullback low
                sw = [p for (qq, p) in swl if qq + 2 < start and qq >= i - 48 and p > low and p - low < 1.5 * a]
                lowbar = start + int(np.argmin(L[start:i + 1]))
                hi12 = H[max(0, start - 12):start + 1].max()
                sdx = d["sfirst"][s]
                ro = d["rth_open"][s]
                ad = d["atr_d"][s]
                fhr = np.nan
                if np.isfinite(ro) and m >= 630 and np.isfinite(ad):
                    fhr = _range(d, int(ro), i, 630) / ad
                orb = 0
                if m >= 600 and np.isfinite(orh[i]):
                    hi_, lo_ = (orh[i], orl[i]) if dr > 0 else (-orl[i], -orh[i])
                    orb = 1 if C[i] > hi_ else (-1 if C[i] < lo_ else 0)
                od = 0
                if np.isfinite(ro) and m >= 570:
                    od = int(np.sign(C[i] - O[int(ro)]))
                vw = int(np.sign(C[i] - dr * vwap[i])) if np.isfinite(vwap[i]) else 0
                day = d["days"][s]
                nm = d["news"].get(day, [])
                emod = mod[ei]
                news = int(any(-10 <= x - emod <= 30 for x in nm))
                pdir = 0
                if s > 0 and np.isfinite(d["pclose"][s]) and np.isfinite(d["rth_open"][s - 1]):
                    pdir = int(np.sign(dr * (d["pclose"][s] - d["o"][int(d["rth_open"][s - 1])])))
                rows.append((dr, i, ei, e, stop, risk, m, d["dow"][i],
                             dr * d["t15"][i], dr * d["c15"][i], dr * d["t60"][i], dr * d["t240"][i],
                             int(e8[i] > e21[i] > e50[i]), int(e8[i] > e21[i]),
                             int(low <= e21[lowbar] + 0.1 * a), int(low <= e50[lowbar] + 0.1 * a),
                             int(bool(sw)), (max(sw) - low) / a if sw else 0.0, (C[i] - O[i]) / a, i - start,
                             (hi12 - low) / a, dr * d["slope15"][i], dr * d["slope60"][i], d["adx15"][i], dr * d["rib15"][i],
                             d["vix"][s], d["vxn"][s], dr * d["gap"][s] if np.isfinite(d["gap"][s]) and m >= 570 else np.nan,
                             fhr, vw, orb, od, news, pdir, lvl))
        # end dir
    df = pd.DataFrame(rows, columns=FEATS).sort_values(["ei", "dir"]).reset_index(drop=True)
    df["day"] = d["days"][d["sid"][df["sig"].values]]
    df["lim"] = 0
    D["cand"] = df
    if ENTRY_MODE == "lim":
        df = to_limit(df, d)
    D["cand"] = df
    return df


ENTRY_MODE = os.environ.get("EMA2_ENTRY", "mkt")      # mkt: next 5m open | lim: limit back at the CISD level for 30 min


def to_limit(df, d, wait=6):
    """LIT-style entry: a limit at the CISD level (the open of the counter-trend run) for `wait` 5m bars after the signal;
    filled when price trades 1 tick through it (at the limit or a better open). The stop stays beyond the pullback extreme."""
    rows = []
    for j, row in enumerate(df.itertuples(index=False)):
        dr = row.dir
        L = d["l"] if dr > 0 else -d["h"]
        O = d["o"] * dr
        s = d["sid"][row.sig]
        for k in range(row.sig + 1, min(row.sig + 1 + wait, d["n"])):
            if d["sid"][k] != s or d["mod"][k] >= 930:
                break
            if L[k] <= row.lvl - TICK:      # stop < level: a bar that reaches the stop fills first, then stops (sim)
                e = min(O[k], row.lvl)
                risk = e - row.stop
                if MIN_STOP <= risk <= MAX_STOP:
                    rows.append((j, k, e, risk))
                break
    idx = [r[0] for r in rows]
    out = df.iloc[idx].copy().reset_index(drop=True)
    out["ei"] = [r[1] for r in rows]; out["e"] = [r[2] for r in rows]; out["risk"] = [r[3] for r in rows]
    out["lim"] = 1
    return out.sort_values(["ei", "dir"]).reset_index(drop=True)


def _range(d, a, i, upto_mod):
    """RTH high - low from bar a up to the bar that ends at upto_mod (first hour), using only bars <= i."""
    mod = d["mod"]
    j = a
    hi, lo = -np.inf, np.inf
    while j <= i and mod[j] < upto_mod:
        hi = max(hi, d["h"][j]); lo = min(lo, d["l"][j]); j += 1
    return hi - lo


def fractal_masks(h, l, k=2):
    n = len(h)
    fh = np.zeros(n, bool); fl = np.zeros(n, bool)
    hp = pd.Series(h)
    lp = pd.Series(l)
    prev_hmax = hp.shift(1).rolling(k).max().values
    next_hmax = hp[::-1].shift(1).rolling(k).max().values[::-1]
    prev_lmin = lp.shift(1).rolling(k).min().values
    next_lmin = lp[::-1].shift(1).rolling(k).min().values[::-1]
    fh = (h > prev_hmax) & (h >= next_hmax)
    fl = (l < prev_lmin) & (l <= next_lmin)
    return np.nan_to_num(fh).astype(bool), np.nan_to_num(fl).astype(bool)


# ================================================================================================ exits
def simulate(row, X, d=None):
    """One trade from candidate `row` under exit config X. All in direction space (long-positive).
    X: tgt (R float | "vix" | None), vk (VIX moves), bank (R cap for vix), be (None | R trigger), beo (pts beyond entry),
       tchk (None | (bars, x, mfe)), ride (None | "15" | "5"), part (None | (R, frac)).
    Candidate e / stop are in direction space (short prices negated). Returns (r, exit_i, kind, exit_px_dirspace,
    worst_pts, target_px_dirspace) per micro, costs in."""
    d = d or load()
    dr = int(row["dir"])
    O = d["o"] * dr
    if dr > 0:
        Hh, Ll, Cc = d["h"], d["l"], d["c"]
    else:
        Hh, Ll, Cc = -d["l"], -d["h"], -d["c"]
    ei, e, stop, risk = int(row["ei"]), float(row["e"]), float(row["stop"]), float(row["risk"])
    lim = bool(row.get("lim", 0))
    s = d["sid"][ei]
    kf = d["flat_idx"][s]
    live = d.get("open_sid") is not None and s == d["open_sid"]   # live (engine/second.py): today's 15:55 flat not reached yet
    if live:
        kf = d["n"] - 1
    if kf < ei:
        return None
    tg = X.get("tgt")
    if tg == "vix":
        vm = d["vmove"][s]
        if not np.isfinite(vm):
            return None
        lvl = dr * d["open18"][s] + X.get("vk", 1.0) * vm
        rr = (lvl - e) / risk
        if rr < X.get("min_rr", 1.5):
            return None
        tgt = e + min(rr, X.get("bank", 8.0)) * risk
    elif tg is None:
        tgt = None
    else:
        tgt = e + float(tg) * risk
    be = X.get("be"); beo = X.get("beo", 0.0)
    tc = X.get("tchk")
    ride = X.get("ride")
    xf = None
    if ride:
        xf = d["x15"] if ride == "15" else d["x5"]
        xf = xf[0] if dr > 0 else xf[1]
    part = X.get("part")
    sp = stop
    mfe = 0.0
    worst = 0.0
    legs = []          # (fraction, pts)
    rem = 1.0
    k = ei
    kind = None
    ex = None
    while k <= kf:
        op, hi, lo, cl = O[k], Hh[k], Ll[k], Cc[k]
        if lo <= sp:
            ex = min(op, sp) - TICK if k > ei else sp - TICK
            kind = "STOP" if sp == stop else "BE"
            worst = min(worst, ex - e)
            break
        worst = min(worst, lo - e)
        if part and rem == 1.0 and hi >= e + part[0] * risk:
            legs.append((part[1], part[0] * risk)); rem = 1.0 - part[1]
        if tgt is not None and hi >= tgt and not (lim and k == ei):
            ex = max(op, tgt) if k > ei else tgt
            kind = "TARGET"
            break
        mfe = max(mfe, hi - e)
        if k == kf:
            if live:                   # the bars end inside the trade: still open (stop after this bar's breakeven check)
                if be is not None and sp < e and hi >= e + be * risk and not (lim and k == ei):
                    sp = e + beo
                return ((cl - e - CPTS) / risk, k, "OPEN_BE" if sp != stop else "OPEN", cl, min(worst, cl - e), tgt)
            ex = cl - TICK; kind = "FLAT"; break
        if tc and k - ei + 1 == tc[0] and mfe < tc[2] * risk and sp == stop and cl < e - tc[1] * risk:
            ex = O[k + 1] - TICK; kind = "CUT"; k += 1; worst = min(worst, ex - e); break
        if xf is not None and xf[k]:
            ex = O[k + 1] - TICK; kind = "RIDE"; k += 1; worst = min(worst, ex - e); break
        if be is not None and sp < e and hi >= e + be * risk and not (lim and k == ei):
            sp = e + beo
        k += 1
    if ex is None:
        return None
    pts = sum(f * p for f, p in legs) + rem * (ex - e) - CPTS
    return (pts / risk, min(k, kf), kind, ex, min(worst, ex - e), tgt)


# ================================================================================================ variants
ENTRY = {
    "win": ("all", "lonny", "ny", "am", "oh", "lon"),
    "trend": ("t15", "t60", "t15_60", "t60_240", "all3", "s5"),
    "pull": ("e21", "e50", "any"),
    "sweep": (0, 1),
    "disp": (0.0, 0.5, 0.8),
}
EXITS = {
    "tgt": (2.0, 3.0, 4.0, "vix", None),
    "be": (None, 1.0),
    "tchk": (None, (3, 0.3, 0.5)),
    "ride": (None, "15"),
}
REGIME = ("none", "adx20", "slope", "vxn_lo", "vxn_hi", "nonews", "fhr_hi", "vwap", "nomon", "orb")


def exit_list():
    out = []
    for tg, be, tc, ride in itertools.product(*EXITS.values()):
        if tg is None and ride is None:
            continue
        out.append({"tgt": tg, "be": be, "beo": 1.25 if be else 0.0, "tchk": tc, "ride": ride})
    return out


def xname(X):
    t = X["tgt"]
    s = ("vix" if t == "vix" else ("ride" if t is None else f"{t:g}R"))
    if X.get("ride") and t is not None:
        s += "+ride15"
    if X.get("be"):
        s += "+BE"
    if X.get("tchk"):
        s += "+t15"
    return s


def entry_mask(df, E):
    m = np.ones(len(df), bool)
    a, z = WINS[E["win"]]
    m &= (df["mod"].values + 5 >= a) & (df["mod"].values + 5 < z)   # entry bar = signal + 5 min
    tr = E["trend"]
    if tr == "t15":
        m &= (df["t15"].values > 0) & (df["c15"].values > 0)
    elif tr == "t60":
        m &= df["t60"].values > 0
    elif tr == "t15_60":
        m &= (df["t15"].values > 0) & (df["t60"].values > 0)
    elif tr == "t60_240":
        m &= (df["t60"].values > 0) & (df["t240"].values > 0)
    elif tr == "all3":
        m &= (df["t15"].values > 0) & (df["t60"].values > 0) & (df["t240"].values > 0)
    elif tr == "s5":
        m &= df["s5"].values > 0
    elif tr == "e8x21":
        m &= df["e8x21"].values > 0
    pu = E["pull"]
    if pu == "e21":
        m &= df["touch21"].values > 0
    elif pu == "e50":
        m &= df["touch50"].values > 0
    if E["sweep"]:
        m &= df["swept"].values > 0
    m &= df["disp"].values >= E["disp"]
    rg = E.get("reg", "none")
    v = df["vxn"].values
    if rg == "adx20":
        m &= df["adx15"].values >= 20
    elif rg == "slope":
        m &= df["slope15"].values > 0.1
    elif rg == "vxn_lo":
        m &= v < 24
    elif rg == "vxn_hi":
        m &= v >= 20
    elif rg == "nonews":
        m &= df["news"].values == 0
    elif rg == "fhr_hi":
        m &= ~(df["fhr"].values < 0.6)
    elif rg == "vwap":
        m &= df["vwap"].values >= 0
    elif rg == "nomon":
        m &= df["dow"].values != 0
    elif rg == "orb":
        m &= df["orb"].values >= 0
    return m


def pick_first(df, m, R, ok):
    """Max 1 trade a day: the first candidate of the day that passes the mask and has a valid exit."""
    idx = np.flatnonzero(m & ok)
    if not len(idx):
        return idx
    days = df["day"].values[idx]
    _, first = np.unique(days, return_index=True)
    return idx[first]


def rstats(R, n_sess):
    if len(R) == 0:
        return {"n": 0, "tpw": 0.0, "R": 0.0, "exp": 0.0, "pf": 0.0, "win": 0.0, "t": 0.0}
    gl = -R[R < 0].sum()
    sd = R.std(ddof=1) if len(R) > 2 else 0
    return {"n": int(len(R)), "tpw": round(len(R) / (n_sess / 5), 2), "R": round(float(R.sum()), 2),
            "exp": round(float(R.mean()), 3), "pf": round(float(R[R > 0].sum() / gl), 2) if gl > 0 else 99.0,
            "win": round(100 * float((R > 0).mean()), 1), "t": round(float(R.mean() / (sd / math.sqrt(len(R)))) if sd > 0 else 0.0, 2)}


def n_sess(span):
    a, z = SPAN[span]
    return RS.n_sessions(a, z)


# ---- per-exit outcome arrays (worker)
_G = {}


def _sim_exit(args):
    xi, X, rows = args
    d = load()
    R = np.full(len(rows), np.nan)
    for j, row in enumerate(rows):
        r = simulate(row, X, d)
        if r is not None:
            R[j] = r[0]
    return xi, R


def outcome_table(df, procs=4):
    """R per candidate for every exit config (NaN = no trade)."""
    from multiprocessing import Pool
    XL = exit_list()
    rows = df[["dir", "ei", "e", "stop", "risk", "lim"]].to_dict("records")
    with Pool(procs, initializer=load) as pool:
        res = pool.map(_sim_exit, [(i, X, rows) for i, X in enumerate(XL)])
    R = np.vstack([r for _, r in sorted(res, key=lambda x: x[0])])
    return XL, R


CACHE = os.path.join(ROOT, "research", "runs", "_cache")
SP4 = ("H1", "H2", "2025", "2021-24")
COLS = ("n", "tpw", "R", "exp", "pf", "win", "t")


def outcomes(procs=4, force=False):
    """R per candidate (all years) for every exit config, cached."""
    p = os.path.join(CACHE, f"ema2_outcomes_{ENTRY_MODE}.npz")
    df = candidates()
    XL = exit_list()
    if os.path.exists(p) and not force:
        z = np.load(p)
        if z["R"].shape == (len(XL), len(df)):
            return df, XL, z["R"]
    _, R = outcome_table(df, procs)
    os.makedirs(CACHE, exist_ok=True)
    np.savez_compressed(p, R=R)
    return df, XL, R


def span_masks(df):
    dy = df["day"].values
    return {s: (dy >= SPAN[s][0]) & (dy <= SPAN[s][1]) for s in SP4}


def entries():
    keys = list(ENTRY.keys())
    for combo in itertools.product(*ENTRY.values()):
        for reg in REGIME:
            E = dict(zip(keys, combo)); E["reg"] = reg
            yield E


def grid(procs=4):
    """Every variant (entry x regime x exit), max 1 trade a day, scored in R on H1 / H2 / 2025 / 2021-24."""
    t0 = time.time()
    df, XL, R = outcomes(procs)
    print(f"candidates {len(df)}, outcomes {R.shape} ({time.time() - t0:.0f}s)", flush=True)
    SM = span_masks(df)
    NS = {s: n_sess(s) for s in SP4}
    h1 = SM["H1"]
    E_list, X_idx, stats = [], [], []
    for E in entries():
        m = entry_mask(df, E)
        if (m & h1).sum() < 15:
            continue
        for xi in range(len(XL)):
            ok = np.isfinite(R[xi])
            sel = pick_first(df, m, R[xi], ok)
            if (h1[sel]).sum() < 15:
                continue
            r = R[xi][sel]
            row = []
            for sp in SP4:
                st = rstats(r[SM[sp][sel]], NS[sp])
                row += [st[c] for c in COLS]
            E_list.append(E); X_idx.append(xi); stats.append(row)
    S = np.array(stats, float)
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"E": E_list, "xi": X_idx}, open(os.path.join(CACHE, f"ema2_grid_keys_{ENTRY_MODE}.json"), "w"))
    np.save(os.path.join(CACHE, f"ema2_grid_stats_{ENTRY_MODE}.npy"), S)
    print(f"variants {len(E_list)} ({time.time() - t0:.0f}s)", flush=True)
    return E_list, X_idx, S


def load_grid():
    k = json.load(open(os.path.join(CACHE, f"ema2_grid_keys_{ENTRY_MODE}.json")))
    return k["E"], k["xi"], np.load(os.path.join(CACHE, f"ema2_grid_stats_{ENTRY_MODE}.npy"))


def col(sp, c):
    return SP4.index(sp) * len(COLS) + COLS.index(c)


# ================================================================================================ picks
TGT_NB = {2.0: [3.0], 3.0: [2.0, 4.0, "vix"], 4.0: [3.0, "vix"], "vix": [3.0, 4.0], None: []}
WIN_NB = {"lon": ["lonny"], "lonny": ["lon", "all", "am"], "all": ["lonny", "ny"], "ny": ["all", "am"], "am": ["ny", "lonny", "oh"],
          "oh": ["am"]}
TR_NB = {"t15": ["t15_60", "s5"], "t60": ["t15_60", "t60_240"], "t15_60": ["t15", "t60", "all3"], "t60_240": ["t60", "all3"],
         "all3": ["t15_60", "t60_240"], "s5": ["t15"]}
PU_NB = {"e21": ["any"], "e50": ["any"], "any": ["e21", "e50"]}
DISP_NB = {0.0: [0.5], 0.5: [0.0, 0.8], 0.8: [0.5]}


def vkey(E, X):
    return (E["win"], E["trend"], E["pull"], int(E["sweep"]), float(E["disp"]), E["reg"], X["tgt"], bool(X["be"]),
            bool(X["tchk"]), bool(X["ride"]))


def neighbours(k):
    w, tr, pu, sw, ds, rg, tg, be, tc, ri = k
    out = [(x, tr, pu, sw, ds, rg, tg, be, tc, ri) for x in WIN_NB[w]]
    out += [(w, x, pu, sw, ds, rg, tg, be, tc, ri) for x in TR_NB[tr]]
    out += [(w, tr, x, sw, ds, rg, tg, be, tc, ri) for x in PU_NB[pu]]
    out += [(w, tr, pu, 1 - sw, ds, rg, tg, be, tc, ri)]
    out += [(w, tr, pu, sw, x, rg, tg, be, tc, ri) for x in DISP_NB[ds]]
    out += [(w, tr, pu, sw, ds, x, tg, be, tc, ri) for x in (REGIME[1:] if rg == "none" else ["none"])]
    out += [(w, tr, pu, sw, ds, rg, x, be, tc, ri) for x in TGT_NB[tg]]
    out += [(w, tr, pu, sw, ds, rg, tg, not be, tc, ri), (w, tr, pu, sw, ds, rg, tg, be, not tc, ri)]
    if tg is not None:
        out += [(w, tr, pu, sw, ds, rg, tg, be, tc, not ri)]
    return out


def pick(min_tpw=1.0, max_tpw=5.0, top=15):
    """Best (highest H1 t) and plateau (every one-step neighbour positive on H1, highest median H1 t of itself + neighbours).
    H2 / 2025 / 2021-24 are only read after the pick. Also: survival of the H1 leaders vs all variants (chance)."""
    E_list, X_idx, S = load_grid()
    XL = exit_list()
    keys = [vkey(E, XL[x]) for E, x in zip(E_list, X_idx)]
    pos = {k: i for i, k in enumerate(keys)}
    t1, R1, tpw1 = S[:, col("H1", "t")], S[:, col("H1", "R")], S[:, col("H1", "tpw")]
    okf = (tpw1 >= min_tpw) & (tpw1 <= max_tpw)
    plat = np.full(len(keys), -9.0)
    nbn = np.zeros(len(keys), int)
    for i in np.flatnonzero(okf & (R1 > 0)):
        nb = [pos[k] for k in neighbours(keys[i]) if k in pos]
        if len(nb) < 6 or (R1[nb] <= 0).any():
            continue
        plat[i] = float(np.median(np.r_[t1[i], t1[nb]])); nbn[i] = len(nb)
    def row(i, how):
        o = {"how": how, "E": E_list[i], "X": XL[X_idx[i]], "name": label(E_list[i], XL[X_idx[i]]), "plateau_t": round(plat[i], 2),
             "n_nb": int(nbn[i])}
        for sp in SP4:
            o[sp] = {c: float(S[i, col(sp, c)]) for c in COLS}
        return o
    best = [row(i, "best") for i in np.argsort(-np.where(okf, t1, -9))[:top]]
    plats = [row(i, "plateau") for i in np.argsort(-plat)[:top] if plat[i] > -9]
    # chance: how often a variant positive on H1 stays positive on H2, for all / the top 10% / 1% by H1 t / plateau
    R2 = S[:, col("H2", "R")]
    allv = okf
    ch = {"variants": int(len(keys)), "in_freq": int(allv.sum()), "h1_pos": round(100 * float((R1[allv] > 0).mean()), 1),
          "h2_pos_all": round(100 * float((R2[allv] > 0).mean()), 1), "h2_meanR_all": round(float(R2[allv].mean()), 2)}
    for q in (0.9, 0.99, 0.999):
        th = np.quantile(t1[allv], q)
        m = allv & (t1 >= th)
        ch[f"top{round(100 * (1 - q), 1)}"] = {"n": int(m.sum()), "h2_pos": round(100 * float((R2[m] > 0).mean()), 1),
                                                "h2_meanR": round(float(R2[m].mean()), 2)}
    pm = plat > -9
    th = np.quantile(plat[pm], 0.9)
    m = pm & (plat >= th)
    ch["plateau_top10"] = {"n": int(m.sum()), "h2_pos": round(100 * float((R2[m] > 0).mean()), 1), "h2_meanR": round(float(R2[m].mean()), 2)}
    for sp in ("2025", "2021-24"):
        Rx = S[:, col(sp, "R")]
        ch[f"{sp}_pos_all"] = round(100 * float((Rx[allv] > 0).mean()), 1)
        ch[f"{sp}_pos_plateau_top10"] = round(100 * float((Rx[m] > 0).mean()), 1)
    out = {"best": best, "plateau": plats, "chance": ch}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, f"ema_picks_{ENTRY_MODE}.json"), "w"), indent=1, default=str)
    return out


def label(E, X):
    reg = "" if E["reg"] == "none" else f" {E['reg']}"
    return (f"win={E['win']} trend={E['trend']} pull={E['pull']} sweep={E['sweep']} disp={E['disp']}{reg} | {xname(X)}")


# ================================================================================================ trades, money, evals
def trades_of(E, X, span=("2021-11-01", "2026-10-16")):
    """The variant's trades (max 1 a day, first qualifying CISD), per micro, with real prices."""
    d = load()
    df = candidates()
    m = entry_mask(df, E) & (df["day"].values >= span[0]) & (df["day"].values <= span[1])
    out, seen = [], set()
    for j in np.flatnonzero(m):
        row = df.iloc[j]
        if row["day"] in seen:
            continue
        r = simulate(row, X, d)
        if r is None:
            continue
        seen.add(row["day"])
        dr = int(row["dir"])
        rr, xi, kind, ex, worst, tgt = r
        out.append({"day": row["day"], "entry_t": int(d["t"][int(row["ei"])]), "exit_t": int(d["t"][xi]) + 300, "dir": dr,
                    "entry": round(dr * float(row["e"]), 2), "stop": round(dr * float(row["stop"]), 2),
                    "target": round(dr * float(tgt), 2) if tgt is not None else None, "exit": round(dr * float(ex), 2),
                    "exit_kind": kind, "r": round(float(rr), 4), "risk_pts": float(row["risk"]), "worst_pts": float(worst),
                    "sig_i": int(row["sig"]), "ei": int(row["ei"]), "exit_i": int(xi),
                    "setup": f"EMA trend pullback {'long' if dr > 0 else 'short'}: {'sweep + ' if row['swept'] else ''}5m CISD"})
    return out


def qty(rule, rp):
    if rule == "lit":
        r = 800.0 if rp <= 20 else 800.0 * 20 / rp
        return max(0, min(40, int(r / (rp * PV))))
    if rule.startswith("usd"):
        return max(1, min(40, int(float(rule[3:]) / (rp * PV))))
    if rule.startswith("fix"):
        return int(rule[3:])
    raise ValueError(rule)


def sized(U, rule):
    """Per-micro trades -> runlib trades at a sizing rule ($: q x (r x risk x $2); low = worst open $)."""
    out = []
    for u in U:
        q = qty(rule, u["risk_pts"])
        if q <= 0:
            continue
        pnl = q * PV * u["r"] * u["risk_pts"]
        low = min(q * (PV * u["worst_pts"] - COMM), pnl)
        out.append({**u, "qty": q, "pnl": round(pnl, 2), "pnl_usd": round(pnl, 2), "risk_usd": round(q * u["risk_pts"] * PV, 2),
                    "half": False, "trigger": "EMA2", "mfe": None,
                    "mae": round(-u["worst_pts"] / u["risk_pts"], 3), "bars_held": u["exit_i"] - u["ei"] + 1, "regime": "",
                    "mult": 1.0, "low": round(low, 2)})
    return out


def sessions(lo="2021-11-01", hi="2026-10-16"):
    return [x for x in RS.sessions() if lo <= x <= hi]


def span_stats(T, sp):
    from tools import runlib as rl
    a, z = SPAN[sp]
    S = sessions(a, z)
    TT = [t for t in T if a <= t["day"] <= z]
    D_ = rl.days_of(TT, S)
    if not TT:
        return {"n": 0, "net": 0, "per_month": 0}
    o = rl._compact(TT, D_)
    o["corr_lit"] = corr_lit(D_)
    return o


def lit_days():
    load()                                   # RS.load() returns D as soon as it holds anything: load the bars first
    if "litd" not in D:
        r = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        D["litd"] = {x[0]: x[1] for x in r["days"]}
        D["lit_trades"] = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    return D["litd"]


def corr_lit(days):
    L = lit_days()
    a = [(x["pnl"], L[x["date"]]) for x in days if x["date"] in L]
    if len(a) < 20:
        return None
    x, y = np.array(a).T
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 2)


# ---- MFFU 50K eval paths (fresh eval every session of a span; only starts with the full horizon counted, as
#      tools/lit_adv_manage.evals; LIT two_week sizing via engine/sizing.lit_qty; EMA micros capped at 0.6 x room and the
#      $1,000 soft daily loss)
A50 = {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0}


def ema_eval_qty(u, st, base="lit"):
    q = qty(base, u["risk_pts"])
    q = min(q, int(0.6 * max(0.0, st["room"]) / (u["risk_pts"] * PV)))
    q = min(q, int(max(0.0, A50["dll"] + st["cum"]) / ((u["risk_pts"] + TICK) * PV + COMM)))
    return max(0, q)


def run_eval_mix(seq, byL, byE, horizon=20, keep=None, base="lit"):
    from engine import lit
    from engine import sizing as SZ
    from tools import lit_adv_manage as A
    tgt, mll, dll, lockv = A50["target"], A50["mll"], A50["dll"], A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        ev = sorted([(t["entry_t"], 0, t) for t in byL[si]] + [(u["entry_t"], 1, u) for u in byE[si]], key=lambda x: (x[0], x[1]))
        for _, kind, t in ev:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            if kind == 0:
                m0 = lit.qty_for(t["risk"])
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, A.CFG, room=st["room"], state=st,
                               learning=None)["qty"] if m0 else 0
                if q <= 0:
                    continue
                pnl = A.leg_pnl(t, q)
                low = min(0.0, t["w1"] * PV * q - A.ECOMM * q, pnl)
            else:
                q = ema_eval_qty(t, st, base)
                if q <= 0:
                    continue
                pnl = q * PV * t["r"] * t["risk_pts"]
                low = min(0.0, q * (PV * t["worst_pts"] - COMM), pnl)
            if cum + low <= -dll:
                pnl = -dll - cum - TICK * PV * q
                low = pnl
            if keep is not None:
                keep.append({"day": t["day"], "entry_t": t["entry_t"], "src": "LIT" if kind == 0 else "EMA", "qty": q,
                             "pnl": round(pnl, 2), "low": round(low, 2)})
            if bal + cum + low <= floor:
                return "FAIL", kk + 1
            cum += pnl
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


_LU = {}


def lit_units():
    """The live LIT trades (lit_live: t_check + be_off) as eval units (tools/lit_adopt_combo.units)."""
    if "U" not in _LU:
        from tools import lit_adopt_combo as AC
        from tools import lit_retail_conf as LC
        _LU["T"] = LC.live_trades()
        _LU["U"] = AC.units(_LU["T"])
    return _LU["U"]


def _eval_res(byL, byE, a, z, base):
    res = [(run_eval_mix(list(range(i, min(z, i + 20))), byL, byE, base=base), z - i) for i in range(a, z)]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    k, T, n = a, [], collections.Counter()
    while k < z:
        r, used = run_eval_mix(list(range(k, z)), byL, byE, z - k, keep=T, base=base)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    eq = np.cumsum(p)
    gl = -p[p < 0].sum()
    o.update(b2b=f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}", net=round(float(p.sum())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), n=len(T),
             n_ema=sum(1 for t in T if t["src"] == "EMA"), net_ema=round(sum(t["pnl"] for t in T if t["src"] == "EMA")))
    return o


def eval_mix(EU, span, with_lit=True, base="lit"):
    """LIT (two_week, run lit_adopt_t15_be_off_eval) + EMA on one eval: fresh evals on every session of H1 / H2 (2-week,
    1-month pass / fail) + the back-to-back path ($, PF, DD)."""
    from tools import lit_adv_manage as A
    S26 = A.S26
    a, z = SPAN[span]
    ix = [i for i, x in enumerate(S26) if a <= x <= z]
    pos = {x: i for i, x in enumerate(S26)}
    byL = collections.defaultdict(list); byE = collections.defaultdict(list)
    if with_lit:
        for t in lit_units():
            if t["day"] in pos:
                byL[pos[t["day"]]].append(t)
    for u in EU:
        if u["day"] in pos:
            byE[pos[u["day"]]].append(u)
    return _eval_res(byL, byE, ix[0], ix[-1] + 1, base)


def eval_alone(EU, span, base="usd500"):
    """EMA alone on its own eval (micros = base rule capped at 0.6 x room and the soft daily loss), any span."""
    S = sessions(*SPAN[span])
    pos = {x: i for i, x in enumerate(S)}
    byE = collections.defaultdict(list)
    for u in EU:
        if u["day"] in pos:
            byE[pos[u["day"]]].append(u)
    return _eval_res(collections.defaultdict(list), byE, 0, len(S), base)


# ---- the same account as LIT, LIT first (LIT-rule $, run lit_live)
def combine(TE, maxday=2):
    """LIT trades (run lit_live) + EMA trades on one account. LIT always trades. maxday 2: an EMA trade is skipped while a
    LIT trade is open (1 LIT + 1 EMA a day at most). maxday 1: an EMA trade is skipped once LIT has traded that day, and a
    LIT trade that comes after an EMA entry on the same day is lost (the day's one trade is taken). -> (trades, lost LIT)."""
    lit_days()
    L = D["lit_trades"]
    byL = collections.defaultdict(list)
    for t in L:
        byL[t["day"]].append(t)
    out, lost, first_ema = [], [], {}
    for u in TE:
        ls = byL.get(u["day"], [])
        if any(t["entry_t"] <= u["entry_t"] < t["exit_t"] for t in ls):
            continue
        if maxday == 1 and any(t["entry_t"] <= u["entry_t"] for t in ls):
            continue
        out.append({**u, "src": "EMA"})
        first_ema.setdefault(u["day"], u["entry_t"])
    for t in L:
        x = {**t, "src": "LIT", "low": -min(float(t.get("mae") or 0), max(1.0, -float(t["r"]))) * float(t["risk_pts"]) * 2.0 * int(t["qty"])}
        if maxday == 1 and t["day"] in first_ema and first_ema[t["day"]] < t["entry_t"]:
            lost.append(x)
            continue
        out.append(x)
    out.sort(key=lambda t: t["entry_t"])
    return out, lost


# ================================================================================================ the picked versions
# Picked on 2026 H1 only (+ the 2025 / 2021-24 reference preference): among the 25 best H1 plateau variants (every one-step
# neighbour profitable on H1), keep those not negative in 2025 and 2021-24, take the highest H1 R (`select`).
VERSIONS = {
    "ema2_lon_vix": ("London EMA trend pullback, VIX-band target",
                     {"win": "lon", "trend": "t15_60", "pull": "e50", "sweep": 1, "disp": 0.0, "reg": "nomon"},
                     {"tgt": "vix", "be": 1.0, "beo": 1.25, "tchk": None, "ride": None}),
    "ema2_lon_3r": ("London EMA trend pullback, 3R (no sweep needed)",
                    {"win": "lon", "trend": "t15_60", "pull": "e50", "sweep": 0, "disp": 0.0, "reg": "nomon"},
                    {"tgt": 3.0, "be": 1.0, "beo": 1.25, "tchk": None, "ride": None}),
}
MAIN = "ema2_lon_vix"
SIZE = "usd500"
RULES = [
    "Market: NQ / MNQ futures, 5-minute chart. Entries 03:00-09:30 ET, not on Mondays, max 1 trade a day, flat 15:55.",
    "Trend: on the 15-minute AND the 1-hour chart the EMA 21 is above the EMA 50 (longs; below for shorts). Only closed bars.",
    "Pullback: a run of down candles (for a long) that reaches the 5-minute EMA 50 (low within 0.1 ATR of it).",
    "Sweep (VIX version): the pullback low takes out an earlier confirmed 5-minute swing low (stop hunt), by less than 1.5 ATR.",
    "Trigger: a 5-minute candle closes above the open of the first candle of that down run (CISD, as LIT). "
    "Enter at the next 5-minute open.",
    "Stop: 1 tick beyond the pullback low (the sweep wick). Stops under 6 or over 80 points: no trade. Size follows the stop.",
    "Target (VIX version): the 18:00 open + 1 VIX one-day move (VIX prior close / 100 / sqrt(252) x open), at least 1.5R "
    "(else no trade), banked at 8R. 3R version: 3 x the stop distance.",
    "Breakeven: at +1R the stop moves to entry + 1.25 points (covers costs). No other management.",
    "Size: $500 risk a trade (micros = 500 / (stop x $2), 1-40). Eval: the same capped at 60% of the room to the trailing "
    "max loss and the $1,000 soft daily loss. On the LIT account: LIT first, no EMA entry while a LIT trade is open.",
]


def select(top=25):
    E_list, X_idx, G = load_grid()
    XL = exit_list()
    keys = [vkey(E, XL[x]) for E, x in zip(E_list, X_idx)]
    pos = {k: i for i, k in enumerate(keys)}
    t1, R1, tp = G[:, col("H1", "t")], G[:, col("H1", "R")], G[:, col("H1", "tpw")]
    plat = np.full(len(keys), -9.0)
    for i in np.flatnonzero((tp >= 1) & (tp <= 5) & (R1 > 0)):
        nb = [pos[k] for k in neighbours(keys[i]) if k in pos]
        if len(nb) >= 6 and not (R1[nb] <= 0).any():
            plat[i] = float(np.median(np.r_[t1[i], t1[nb]]))
    order = [i for i in np.argsort(-plat)[:top] if plat[i] > -9]
    keep = [i for i in order if G[i, col("2025", "R")] >= 0 and G[i, col("2021-24", "R")] >= 0]
    best = max(keep, key=lambda i: R1[i])
    return {"top": [(label(E_list[i], XL[X_idx[i]]), round(plat[i], 2)) for i in order],
            "kept": [label(E_list[i], XL[X_idx[i]]) for i in keep], "pick": label(E_list[best], XL[X_idx[best]]),
            "neighbours": [{"name": label(E_list[j], XL[X_idx[j]]), **{sp: {c: float(G[j, col(sp, c)]) for c in ("n", "R", "pf")} for sp in SP4}}
                           for j in [pos[k] for k in neighbours(keys[best]) if k in pos]]}


def chance_draws(E, X, n_draw=500, seed=11):
    """Chance baseline for the H2 check: the same exit on random CISD candidates (same window, any trend / pullback /
    sweep, both directions), as many trades as the pick took, 1 a day. Returns the share of draws beating the pick."""
    df, XL, R = outcomes()
    xi = next(i for i, x in enumerate(XL) if xname(x) == xname(X))
    base = entry_mask(df, {"win": E["win"], "trend": "none", "pull": "any", "sweep": 0, "disp": 0.0, "reg": E["reg"]})
    m = entry_mask(df, E)
    out = {}
    rng = np.random.default_rng(seed)
    for sp in ("H1", "H2", "2025", "2021-24"):
        sm = span_masks(df)[sp]
        ok = np.isfinite(R[xi])
        sel = pick_first(df, m & sm, R[xi], ok)
        pick_r = float(R[xi][sel].sum())
        pool = np.flatnonzero(base & sm & ok)
        days = df["day"].values[pool]
        ud = np.unique(days)
        k = len(sel)
        sums = []
        for _ in range(n_draw):
            dd = set(rng.choice(ud, size=min(k, len(ud)), replace=False))
            cand = [p for p in pool if df["day"].values[p] in dd]
            cand = rng.permutation(cand)
            seen, tot = set(), 0.0
            for p in cand:
                dy = df["day"].values[p]
                if dy in seen:
                    continue
                seen.add(dy); tot += R[xi][p]
            sums.append(tot)
        sums = np.array(sums)
        out[sp] = {"pick_R": round(pick_r, 1), "random_mean_R": round(float(sums.mean()), 1),
                   "random_p95_R": round(float(np.quantile(sums, 0.95)), 1), "share_random_better": round(float((sums >= pick_r).mean()), 3)}
    return out


def slip_test(U, extra_ticks=1):
    """Every market fill 1 tick worse again (entry, and stop / BE / flat exits); targets are limits."""
    out = []
    for u in U:
        x = extra_ticks * TICK * (1 + (u["exit_kind"] != "TARGET"))
        out.append({**u, "r": u["r"] - x / u["risk_pts"]})
    return out


def lit_only(maxday=2):
    lit_days()
    return [{**t, "low": -min(float(t.get("mae") or 0), max(1.0, -float(t["r"]))) * float(t["risk_pts"]) * 2.0 * int(t["qty"])}
            for t in D["lit_trades"]]


SP_REP = ("H1", "H2", "2026", "2025", "2021-24")


def report_version(vid, quiet=False):
    title, E, X = VERSIONS[vid]
    U = trades_of(E, X)
    o = {"id": vid, "title": title, "E": E, "X": {**X, "tchk": list(X["tchk"]) if X["tchk"] else None}, "name": label(E, X)}
    o["R"] = {sp: rstats(np.array([u["r"] for u in U if SPAN[sp][0] <= u["day"] <= SPAN[sp][1]]), n_sess(sp))
              for sp in SP_REP}
    o["money"] = {}
    for rule in ("usd300", "usd500", "usd800", "lit"):
        T = sized(U, rule)
        o["money"][rule] = {sp: span_stats(T, sp) for sp in SP_REP}
    o["eval_safe_alone"] = {sp: eval_alone(U, sp, base=SIZE) for sp in ("H1", "H2", "2025", "2021-24")}
    T = sized(U, SIZE)
    for md in (2, 1):
        C_, lost = combine(T, md)
        o[f"with_lit_max{md}"] = {sp: span_stats(C_, sp) for sp in SP_REP}
        o[f"with_lit_max{md}"]["ema_trades_kept_2026"] = sum(1 for t in C_ if t["src"] == "EMA" and t["day"] >= "2026")
        o[f"with_lit_max{md}"]["lit_trades_lost_2026"] = sum(1 for t in lost if t["day"] >= "2026")
    C2, _ = combine(T, 2)
    keep_ids = {(t["day"], t["entry_t"]) for t in C2 if t["src"] == "EMA"}
    UK = [u for u in U if (u["day"], u["entry_t"]) in keep_ids]
    o["eval_with_lit"] = {sp: eval_mix(UK, sp, base=SIZE) for sp in ("H1", "H2")}
    o["slip_plus1"] = {sp: rstats(np.array([u["r"] for u in slip_test(U) if SPAN[sp][0] <= u["day"] <= SPAN[sp][1]]), n_sess(sp))
                       for sp in SP_REP}
    o["chance"] = chance_draws(E, X, 300)
    o["months_2026"] = {}
    for t in T:
        if t["day"] >= "2026":
            m = o["months_2026"].setdefault(t["day"][:7], {"n": 0, "net": 0.0})
            m["n"] += 1; m["net"] = round(m["net"] + t["pnl"], 2)
    o["exits_2026"] = dict(collections.Counter(u["exit_kind"] for u in U if u["day"] >= "2026"))
    o["hours_2026"] = dict(sorted(collections.Counter(f"{int(load()['mod'][u['ei']] // 60):02d}" for u in U if u["day"] >= "2026").items()))
    o["dirs_2026"] = dict(collections.Counter("long" if u["dir"] > 0 else "short" for u in U if u["day"] >= "2026"))
    o["median_stop"] = {sp: float(np.median([u["risk_pts"] for u in U if SPAN[sp][0] <= u["day"] <= SPAN[sp][1]])) for sp in SP_REP}
    lit_same_day = {t["day"] for t in D["lit_trades"]}
    o["days_with_lit_2026"] = sum(1 for u in U if u["day"] >= "2026" and u["day"] in lit_same_day)
    return o, U, T


def lit_reference():
    L = lit_only()
    o = {sp: span_stats(L, sp) for sp in SP_REP}
    o["eval_path"] = {sp: eval_mix([], sp) for sp in ("H1", "H2")}
    return o


def save_all():
    from tools import runlib as rl
    os.makedirs(OUT, exist_ok=True)
    rep = {"select": select(), "lit": lit_reference(), "versions": {}}
    for vid in VERSIONS:
        o, U, T = report_version(vid)
        rep["versions"][vid] = o
        title, E, X = VERSIONS[vid]
        S_ = rl.score(T, sessions())
        h1, h2 = o["money"][SIZE]["H1"], o["money"][SIZE]["H2"]
        verdict = (f"$500 risk: 2026 H1 (pick) n={h1['n']} PF {h1.get('pf')} net {h1['net']:+,} (${h1['per_month']:,}/mo); "
                   f"H2 (check) n={h2['n']} PF {h2.get('pf')} net {h2['net']:+,} (${h2['per_month']:,}/mo); "
                   f"2025 {o['money'][SIZE]['2025']['net']:+,}; 2021-24 {o['money'][SIZE]['2021-24']['net']:+,}. "
                   f"Corr with LIT 2026 {o['money'][SIZE]['2026'].get('corr_lit')}.")
        rl.save(vid, title + " (second strategy next to LIT)", "other",
                "Owner 2026-10-22: an EMA strategy to trade alongside LIT, tuned on 2026 H1, checked on H2.",
                params={"entry": E, "exit": o["X"], "sizing": SIZE, "tool": "tools/second_ema.py"}, sizing={"rule": SIZE},
                trades=T, scored=S_, status="promising", verdict=verdict,
                notes="5m signals, market entry next open + 1 tick, $1.90/micro + 1 tick slippage on market fills. "
                      "Picked on 2026 H1 (plateau) + 2025/2021-24 not negative; H2 untouched.",
                writeup="second-ema", tags=["second-strategy", "ema"])
        C_, _ = combine(T, 2)
        S2 = rl.score(C_, sessions())
        rl.save(vid + "_with_lit", title + " + LIT on one account (LIT first, max 2 a day)", "other",
                "LIT (run lit_live) and the EMA version on one account; no EMA entry while a LIT trade is open.",
                params={"entry": E, "exit": o["X"], "sizing": SIZE, "lit_run": "lit_live", "max_per_day": 2}, sizing={"rule": SIZE},
                trades=C_, scored=S2, status="info",
                verdict=f"Combined 2026 H1 {o['with_lit_max2']['H1']['net']:+,} / H2 {o['with_lit_max2']['H2']['net']:+,} "
                        f"(LIT alone {rep['lit']['H1']['net']:+,} / {rep['lit']['H2']['net']:+,}).",
                writeup="second-ema", tags=["second-strategy", "ema", "combo"])
        if vid == MAIN:
            common = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "entry": t["entry"],
                       "stop": t["stop"], "target": t["target"], "exit": t["exit"], "exit_kind": t["exit_kind"], "r": t["r"],
                       "qty": t["qty"], "pnl_usd": t["pnl"], "setup": t["setup"]} for t in T]
            json.dump({"strategy": title, "id": vid, "params": {"entry": E, "exit": o["X"], "sizing": SIZE,
                                                                "min_stop": MIN_STOP, "max_stop": MAX_STOP,
                                                                "costs": "$1.90 a micro round trip + 1 tick on market fills"},
                       "rules": RULES, "trades": common},
                      open(os.path.join(OUT, "ema_best.json"), "w"), indent=1)
    json.dump(rep, open(os.path.join(OUT, "ema_report.json"), "w"), indent=1, default=str)
    return rep


# ================================================================================================ look-ahead check
def lookahead(n=30, seed=5, pool=None):
    """Recompute the candidates with every bar after the signal bar blanked (NaN; the entry bar keeps only its open) and
    compare each sampled candidate's features, stop and CISD level with the full-data ones. pool: candidate rows to sample
    from (default: all 2026 + 2021-25)."""
    import random
    full = candidates().copy()
    raw = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    tvals = load()["t"]
    pool = full if pool is None else pool
    rng = random.Random(seed)
    pick_ix = rng.sample(range(len(pool)), min(n, len(pool)))
    real_read = pd.read_csv
    bad = []
    num = [c for c in FEATS if c not in ("ei",)]
    for j in pick_ix:
        row = pool.iloc[j]
        i = int(row["sig"])
        t_sig = int(tvals[i])
        cut = raw.copy()
        after = cut["time"].values > t_sig
        for c_ in ("high", "low", "close", "volume"):
            cut.loc[after, c_] = np.nan
        nxt = np.flatnonzero(after)
        keep_open = nxt[0] if len(nxt) else None
        cut.loc[after, "open"] = np.nan
        if keep_open is not None:
            cut.loc[keep_open, "open"] = raw.loc[keep_open, "open"]

        def fake(path, *a, **k):
            if str(path).endswith("NQ_5m.csv"):
                return cut.copy()
            return real_read(path, *a, **k)
        RS.pd.read_csv = fake
        try:
            D.clear()
            c2 = candidates()
        finally:
            RS.pd.read_csv = real_read
        m = c2[(c2["sig"] == i) & (c2["dir"] == row["dir"])]
        if not len(m):
            bad.append({"sig": i, "day": row["day"], "why": "missing on cut data"})
            continue
        r2 = m.iloc[0]
        diff = [c_ for c_ in num if not (pd.isna(row[c_]) and pd.isna(r2[c_])) and
                not (abs(float(row[c_]) - float(r2[c_])) < 1e-6 if not pd.isna(row[c_]) and not pd.isna(r2[c_]) else False)]
        if diff:
            bad.append({"sig": i, "day": row["day"], "why": {c_: (float(row[c_]), float(r2[c_])) for c_ in diff}})
    D.clear()
    return {"checked": len(pick_ix), "flagged": len(bad), "bad": bad[:10]}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid()
    elif cmd == "pick":
        o = pick()
        print(json.dumps(o["chance"], indent=1))
        for r in o["plateau"] + o["best"]:
            print(r["how"], r["name"], r["plateau_t"], "|", " | ".join(f"{sp} n{r[sp]['n']:.0f} {r[sp]['tpw']}/wk R{r[sp]['R']:+.1f} pf{r[sp]['pf']}" for sp in SP4))
    elif cmd == "save":
        rep = save_all()
        print(json.dumps(rep["select"]["pick"]))
    elif cmd == "lookahead":
        _, E_, X_ = VERSIONS[MAIN]
        sig = {u["sig_i"] for u in trades_of(E_, X_)}
        cd = candidates()
        pool_ = cd[cd["sig"].isin(sig)].reset_index(drop=True)
        o = lookahead(int(sys.argv[2]) if len(sys.argv) > 2 else 30, pool=pool_)
        o["pool"] = f"trades of {MAIN}"
        print(json.dumps(o, indent=1, default=str))
        os.makedirs(OUT, exist_ok=True)
        json.dump(o, open(os.path.join(OUT, "ema_lookahead.json"), "w"), indent=1, default=str)
    elif cmd == "cand":
        t0 = time.time()
        df = candidates()
        print(len(df), time.time() - t0)
        print(df.describe().T.to_string())
