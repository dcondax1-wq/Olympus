"""IDEA MILL grammar: every idea = trigger x direction x window x filter x stop x exit (research/ideamill/DESIGN.md).
PAPER RESEARCH ONLY. Futures data only (data/NQ_5m.csv = TradingView NQ1! + the PC's NinjaTrader bars; VIX / GEX daily; ES_5m).
Each trigger is a small pure function of the bar context -> (signal +1 / -1 / 0 per bar, the structural stop price per bar).
"""
from __future__ import annotations

import itertools
import os

import numpy as np
import pandas as pd

try:
    from numba import njit
except ImportError:  # pragma: no cover - the walker still runs, slowly
    def njit(*a, **k):
        def w(f):
            return f
        return w if not (a and callable(a[0])) else a[0]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TICK = 0.25
COST_PTS = 1.45            # 1 tick in + 1 tick out + $1.90 a micro round trip (0.95 pt)
MIN_STOP = 4.0
FLAT = 955                 # 15:55 ET

WINDOWS = {"asia": (1080, 1440, 0, 120), "london": (120, 480, -1, -1), "nyam": (480, 690, -1, -1),
           "nypm": (690, 930, -1, -1), "all": (120, 930, -1, -1)}
FILTERS = ("none", "trend_with", "trend_against", "vix_lo", "vix_hi", "gex_hi", "gex_lo", "no_mon", "no_fri")
TFS = ("5m", "15m", "1h")
STOPS = ("struct", "atr")
EXITS = ("R1", "R2", "R3", "T12")
DIRS = ("with", "fade")


# ================================================================================================ context
def _ema(x, n):
    a = 2.0 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def _daily_csv(name, col="close"):
    p = os.path.join(ROOT, "data", name)
    if not os.path.exists(p):
        return {}
    d = pd.read_csv(p)
    key = "date" if "date" in d.columns else None
    if key is None:
        d["date"] = pd.to_datetime(d["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
    return dict(zip(d["date"].astype(str), d[col].astype(float)))


def context(tf="5m"):
    df = pd.read_csv(os.path.join(ROOT, "data", f"NQ_{tf}.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
    mins = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    day = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d").to_numpy()
    dow = (et + pd.Timedelta(hours=6)).dt.dayofweek.to_numpy()
    keep = dow < 5
    df, mins, day, dow = df[keep].reset_index(drop=True), mins[keep], day[keep], dow[keep]
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    v = df["volume"].to_numpy(float)
    n = len(c)
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).rolling(14).mean().shift(1).bfill().to_numpy()
    # day index + per-day facts (all PRIOR-day values)
    udays, di = np.unique(day, return_inverse=True)
    nd = len(udays)
    dh = np.full(nd, -np.inf); dl = np.full(nd, np.inf); dc = np.zeros(nd)
    rth_o = np.full(nd, np.nan); rth_c = np.full(nd, np.nan)
    np.maximum.at(dh, di, h); np.minimum.at(dl, di, l)
    last = np.zeros(nd, int)
    for i in range(n):
        last[di[i]] = i
        if mins[i] == 570 and np.isnan(rth_o[di[i]]):
            rth_o[di[i]] = o[i]
        if 570 <= mins[i] < 960:
            rth_c[di[i]] = c[i]
    dc = c[last]
    pdh = np.r_[np.nan, dh[:-1]]; pdl = np.r_[np.nan, dl[:-1]]; pdc = np.r_[np.nan, rth_c[:-1]]
    rng = dh - dl
    nr7 = np.r_[False, [(i >= 7 and rng[i - 1] <= rng[i - 7:i].min()) for i in range(1, nd)]]
    # prior week high / low
    wk = pd.to_datetime(pd.Series(udays)).dt.isocalendar()
    wkey = (wk["year"].astype(int) * 100 + wk["week"].astype(int)).to_numpy()
    pwh = np.full(nd, np.nan); pwl = np.full(nd, np.nan)
    wh, wl = {}, {}
    for k in range(nd):
        wh[wkey[k]] = max(wh.get(wkey[k], -np.inf), dh[k]); wl[wkey[k]] = min(wl.get(wkey[k], np.inf), dl[k])
    keys = sorted(wh)
    prev = {keys[i]: keys[i - 1] for i in range(1, len(keys))}
    for k in range(nd):
        p = prev.get(wkey[k])
        if p is not None:
            pwh[k], pwl[k] = wh[p], wl[p]
    trend = np.r_[np.zeros(21), np.sign(dc[20:-1] - dc[:-21])] if nd > 21 else np.zeros(nd)
    trend = trend[:nd]
    vix = _daily_csv("VIX_1d.csv")
    gex = _daily_csv("GEX_1d.csv", "gex")
    gd = sorted(gex)
    gv = np.array([gex[d] for d in gd])
    gmed = {gd[i]: (gv[i] > np.median(gv[max(0, i - 60):i])) if i > 20 else None for i in range(len(gd))}
    vd = sorted(vix)
    def prior(dct_keys, dct, d):
        k = np.searchsorted(dct_keys, d) - 1
        return dct[dct_keys[k]] if k >= 0 else None
    vix_p = np.array([prior(vd, vix, d) or np.nan for d in udays])
    gex_p = np.array([{True: 1, False: -1, None: 0}[prior(gd, gmed, d)] if gd else 0 for d in udays])
    # intraday: overnight high/low (18:00-09:30), opening range 09:30-10:00, session VWAP + sd, EMA, RSI, volume median
    on_h = np.full(n, np.nan); on_l = np.full(n, np.nan); or_h = np.full(n, np.nan); or_l = np.full(n, np.nan)
    vwap = np.zeros(n); vsd = np.zeros(n)
    cur = -1
    for i in range(n):
        if di[i] != cur:
            cur = di[i]; oh, ol, rh, rl = -np.inf, np.inf, -np.inf, np.inf; pv = vv = pv2 = 0.0
        tp = (h[i] + l[i] + c[i]) / 3; w = max(v[i], 1.0)
        pv += tp * w; vv += w; m = pv / vv; pv2 += w * (tp - m) ** 2
        vwap[i] = m; vsd[i] = np.sqrt(pv2 / vv)
        if mins[i] >= 1080 or mins[i] < 570:
            oh, ol = max(oh, h[i]), min(ol, l[i])
        else:
            on_h[i], on_l[i] = oh, ol
        if 570 <= mins[i] < 600:
            rh, rl = max(rh, h[i]), min(rl, l[i])
        if mins[i] >= 600 and mins[i] < 960:
            or_h[i], or_l[i] = rh, rl
    e20, e50 = _ema(c, 20), _ema(c, 50)
    d = np.diff(c, prepend=c[0]); up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / 14).mean().to_numpy()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / 14).mean().to_numpy()
    rsi = 100 - 100 / (1 + up / np.maximum(dn, 1e-9))
    vmed = pd.Series(v).rolling(20).median().shift(1).bfill().to_numpy()
    X = dict(time=df["time"].to_numpy(), o=o, h=h, l=l, c=c, v=v, mins=mins, day=day, di=di, udays=udays, dow=dow, atr=atr, pdh=pdh[di], pdl=pdl[di],
             pdc=pdc[di], rth_o=rth_o[di], pwh=pwh[di], pwl=pwl[di], nr7=nr7[di], trend=trend[di], vix=vix_p[di],
             gex=gex_p[di], on_h=on_h, on_l=on_l, or_h=or_h, or_l=or_l, vwap=vwap, vsd=vsd, e20=e20, e50=e50, rsi=rsi, vmed=vmed,
             n=n)
    X["tf"] = tf
    X["es"] = _es_context(X, tf)
    return X


def _es_context(X, tf="5m"):
    p = os.path.join(ROOT, "data", f"ES_{tf}.csv")
    if not os.path.exists(p):
        return None
    e = pd.read_csv(p).drop_duplicates("time").set_index("time")
    t = X["time"]
    eh = e["high"].reindex(t).to_numpy(); el = e["low"].reindex(t).to_numpy()
    return {"h": eh, "l": el}


def _prev(a):
    return np.r_[a[0], a[:-1]]


# ================================================================================================ triggers (pure)
def trig_level_sweep(X, hi, lo):
    """Wick through a level, close back inside -> reversal (long below the low, short above the high)."""
    h, l, c = X["h"], X["l"], X["c"]
    s = np.zeros(X["n"], np.int8)
    s[(l < lo) & (c > lo)] = 1
    s[(h > hi) & (c < hi)] = -1
    return s


def trig_level_break(X, hi, lo):
    c, pc = X["c"], _prev(X["c"])
    s = np.zeros(X["n"], np.int8)
    s[(c > hi) & (pc <= hi)] = 1
    s[(c < lo) & (pc >= lo)] = -1
    return s


def t_pd_sweep(X): return trig_level_sweep(X, X["pdh"], X["pdl"])
def t_pd_break(X): return trig_level_break(X, X["pdh"], X["pdl"])
def t_pw_sweep(X): return trig_level_sweep(X, X["pwh"], X["pwl"])
def t_pw_break(X): return trig_level_break(X, X["pwh"], X["pwl"])
def t_on_sweep(X): return trig_level_sweep(X, X["on_h"], X["on_l"])
def t_or_break(X): return trig_level_break(X, X["or_h"], X["or_l"])


def t_nr7_or_break(X):
    s = t_or_break(X)
    s[~X["nr7"].astype(bool)] = 0
    return s


def t_gap(X):
    """First RTH bar: gap vs the prior RTH close > 0.3 x the 5m ATR x 10 -> go with the gap."""
    s = np.zeros(X["n"], np.int8)
    m = X["mins"] == 570
    g = X["rth_o"] - X["pdc"]
    big = np.abs(g) > 3.0 * X["atr"]
    s[m & big & (g > 0)] = 1
    s[m & big & (g < 0)] = -1
    return s


def t_vwap_cross(X):
    c, pc, w, pw = X["c"], _prev(X["c"]), X["vwap"], _prev(X["vwap"])
    s = np.zeros(X["n"], np.int8)
    s[(c > w) & (pc <= pw)] = 1
    s[(c < w) & (pc >= pw)] = -1
    return s


def t_vwap_band(X):
    """Close beyond VWAP +- 2 sd -> fade back toward VWAP."""
    c, w, sd = X["c"], X["vwap"], X["vsd"]
    s = np.zeros(X["n"], np.int8)
    s[c > w + 2 * sd] = -1
    s[c < w - 2 * sd] = 1
    s[sd <= 0] = 0
    return s


def t_round(X):
    lvl = np.floor(X["c"] / 100.0) * 100.0
    s = np.zeros(X["n"], np.int8)
    s[(X["l"] < lvl) & (X["c"] > lvl)] = 1
    up = lvl + 100.0
    s[(X["h"] > up) & (X["c"] < up)] = -1
    return s


def t_disp(X):
    o, h, l, c, a = X["o"], X["h"], X["l"], X["c"], X["atr"]
    b = c - o
    r = np.maximum(h - l, TICK)
    s = np.zeros(X["n"], np.int8)
    s[(b >= 1.5 * a) & ((c - l) / r >= 0.75)] = 1
    s[(-b >= 1.5 * a) & ((h - c) / r >= 0.75)] = -1
    return s


def t_fvg_retest(X):
    h, l, c = X["h"], X["l"], X["c"]
    n = X["n"]
    s = np.zeros(n, np.int8)
    bull_top = bull_bot = bear_top = bear_bot = np.nan
    age_b = age_s = 99
    for i in range(3, n):
        if l[i - 1] > h[i - 3]:
            bull_top, bull_bot, age_b = l[i - 1], h[i - 3], 0
        if h[i - 1] < l[i - 3]:
            bear_top, bear_bot, age_s = l[i - 3], h[i - 1], 0
        age_b += 1; age_s += 1
        if age_b <= 12 and l[i] <= bull_top and c[i] > bull_bot:
            s[i] = 1; age_b = 99
        elif age_s <= 12 and h[i] >= bear_bot and c[i] < bear_top:
            s[i] = -1; age_s = 99
    return s


def t_inside_break(X):
    h, l, c = X["h"], X["l"], X["c"]
    ins = np.r_[False, False, (h[1:-1] <= h[:-2]) & (l[1:-1] >= l[:-2])]
    s = np.zeros(X["n"], np.int8)
    ph, pl = _prev(h), _prev(l)
    s[ins & (c > ph)] = 1
    s[ins & (c < pl)] = -1
    return s


def t_vol_spike(X):
    b = X["c"] - X["o"]
    sp = X["v"] >= 3 * np.maximum(X["vmed"], 1)
    s = np.zeros(X["n"], np.int8)
    s[sp & (b > 0)] = 1
    s[sp & (b < 0)] = -1
    return s


def t_ema_cross(X):
    d, pd_ = X["e20"] - X["e50"], _prev(X["e20"] - X["e50"])
    s = np.zeros(X["n"], np.int8)
    s[(d > 0) & (pd_ <= 0)] = 1
    s[(d < 0) & (pd_ >= 0)] = -1
    return s


def t_rsi_rev(X):
    r, pr = X["rsi"], _prev(X["rsi"])
    s = np.zeros(X["n"], np.int8)
    s[(pr < 20) & (r >= 20)] = 1
    s[(pr > 80) & (r <= 80)] = -1
    return s


def t_es_div(X):
    """NQ sweeps its prior-day high (low) on a bar where ES does NOT make a new session high (low) -> reversal: ES lags."""
    E = X.get("es")
    if E is None:
        return np.zeros(X["n"], np.int8)
    s = t_pd_sweep(X).copy()
    eh, el, di = E["h"], E["l"], X["di"]
    run_h = np.full(X["n"], np.nan); run_l = np.full(X["n"], np.nan)
    cur, mh, ml = -1, -np.inf, np.inf
    for i in range(X["n"]):
        if di[i] != cur:
            cur, mh, ml = di[i], -np.inf, np.inf
        run_h[i], run_l[i] = mh, ml                    # the session extreme BEFORE this bar
        if eh[i] == eh[i]:
            mh, ml = max(mh, eh[i]), min(ml, el[i])
    no_es = np.isnan(eh) | np.isinf(run_h)
    s[no_es] = 0
    s[(s == -1) & (eh > run_h)] = 0                    # ES made a new high too: no divergence
    s[(s == 1) & (el < run_l)] = 0
    return s


TRIGGERS = {"pd_sweep": t_pd_sweep, "pd_break": t_pd_break, "pw_sweep": t_pw_sweep, "pw_break": t_pw_break,
            "on_sweep": t_on_sweep, "or_break": t_or_break, "nr7_or_break": t_nr7_or_break, "gap": t_gap,
            "vwap_cross": t_vwap_cross, "vwap_band": t_vwap_band, "round100": t_round, "displacement": t_disp,
            "fvg_retest": t_fvg_retest, "inside_break": t_inside_break, "vol_spike": t_vol_spike, "ema_cross": t_ema_cross,
            "rsi_rev": t_rsi_rev, "es_div": t_es_div}
NEEDS = {"es_div": "ES 5m bars (start 2025-04: not in discovery)"}


def window_mask(X, w):
    a, z, a2, z2 = WINDOWS[w]
    m = X["mins"]
    k = (m >= a) & (m < z)
    if a2 >= 0:
        k |= (m >= a2) & (m < z2)
    return k


def filter_mask(X, f, s):
    n = X["n"]
    if f == "none":
        return np.ones(n, bool)
    if f == "trend_with":
        return np.sign(s) == X["trend"]
    if f == "trend_against":
        return np.sign(s) == -X["trend"]
    if f == "vix_lo":
        return X["vix"] < 20
    if f == "vix_hi":
        return X["vix"] >= 20
    if f == "gex_hi":
        return X["gex"] == 1
    if f == "gex_lo":
        return X["gex"] == -1
    if f == "no_mon":
        return X["dow"] != 0
    if f == "no_fri":
        return X["dow"] != 4
    raise KeyError(f)


def stop_price(X, kind, s):
    if kind == "struct":
        return np.where(s > 0, X["l"] - TICK, X["h"] + TICK)
    return np.where(s > 0, X["c"] - X["atr"], X["c"] + X["atr"])


@njit(cache=True)
def walk(o, h, l, c, mins, di, sig, stop, tgt_r, tmax):
    """One position at a time, max one trade a day; entry at the next bar's open; flat 15:55; stop first on a tie.
    Returns (day index, net R, gross R) per trade."""
    n = len(c)
    out_d = np.empty(n, np.int64); out_r = np.empty(n); out_g = np.empty(n)
    k = 0
    busy = -1
    lastday = -1
    for i in range(n - 1):
        s = sig[i]
        if s == 0 or i <= busy or di[i] == lastday or di[i + 1] != di[i]:
            continue
        e = o[i + 1]
        st = stop[i]
        risk = (e - st) * s
        if risk < 4.0 or risk != risk:
            continue
        tg = e + s * tgt_r * risk if tgt_r > 0 else 0.0
        j = i + 1
        ex = c[i + 1]
        while j < n and di[j] == di[i]:
            if mins[j] >= 955 and mins[j] < 1080:
                ex = o[j]; break
            if (s > 0 and l[j] <= st) or (s < 0 and h[j] >= st):
                ex = st; break
            if tgt_r > 0 and ((s > 0 and h[j] >= tg) or (s < 0 and l[j] <= tg)):
                ex = tg; break
            if tmax > 0 and j - (i + 1) >= tmax:
                ex = c[j]; break
            ex = c[j]
            j += 1
        busy = j
        lastday = di[i]
        g = (ex - e) * s
        out_d[k] = di[i]; out_g[k] = g / risk; out_r[k] = (g - 1.45) / risk
        k += 1
    return out_d[:k], out_r[:k], out_g[:k]


def ideas():
    """Every grammar idea (v2: with the timeframe), in a fixed order (the id is stable)."""
    for tf, t, d, w, f, st, ex in itertools.product(TFS, TRIGGERS, DIRS, WINDOWS, FILTERS, STOPS, EXITS):
        yield {"id": f"{tf}|{t}|{d}|{w}|{f}|{st}|{ex}", "tf": tf, "trigger": t, "dir": d, "window": w, "filter": f, "stop": st,
               "exit": ex}


_SIG = {}


def run_idea(X, I):
    key = (X["tf"], I["trigger"], I["dir"])
    if key not in _SIG:
        s = TRIGGERS[I["trigger"]](X).astype(np.int8)
        _SIG[key] = s if I["dir"] == "with" else (-s).astype(np.int8)
    s = _SIG[key].copy()
    s[~window_mask(X, I["window"])] = 0
    s[~filter_mask(X, I["filter"], s)] = 0
    stp = stop_price(X, I["stop"], s)
    tr = {"R1": 1.0, "R2": 2.0, "R3": 3.0, "T12": 0.0}[I["exit"]]
    tm = 12 if I["exit"] == "T12" else 0
    return walk(X["o"], X["h"], X["l"], X["c"], X["mins"], X["di"], s, stp, tr, tm)
