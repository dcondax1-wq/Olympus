"""Retail strategies as STANDALONE NQ strategies (separate from LIT): EMA, MACD, support/resistance (incl. ORB) and
supply/demand. Owner's ask 2026-10-22: "Could those strategies on their own, separate to LIT, make money?"

    python -X utf8 tools/retail_standalone.py run       # every variant (in R), pick on 2021-11..2024-12, check 2025 / 2026
    python -X utf8 tools/retail_standalone.py save      # store the picked versions (rl.save, ids retail_sa_*) + JSON

Method (no look-ahead, costs in):
- Data: TradingView CME NQ1! 5m (data/NQ_5m.csv, back-adjusted); 15m / 1h / 4h are built from it, an HTF value is only used
  from the 5m bar on which that HTF bar CLOSED. Round numbers use the unadjusted price (data/NQ_rolls.json).
- A signal is known at a bar close; a market entry fills at the next 5m open + 1 tick. Limit entries (zone / level
  retests) fill only when price trades 1 tick through the limit, at the limit or a better open; no target on the fill bar.
- Stop exits fill at the stop (or a worse open) - 1 tick; signal / trailing / 15:55 flat exits at the next open - 1 tick;
  targets at the limit. Stop and target in one bar = stop. Commission $1.40 per MNQ micro round trip.
- Stops are structural (owner): the setup candle low/high, the swing low/high, the zone edge, the broken level, the
  opposite side of the opening range: never a fixed distance. Every variant is scored in R first, then sized.
- Sizings: lit ($800 up to a 20-pt stop, then 800x20/stop, max 40, 0 micros = skip), fixed 2/5/10 micros, risk $300 / $500,
  and the MFFU 50K eval path (lit micros capped at 0.6 x room to the trailing max loss / (stop x $2)).
- Entries 02:00-15:30 ET (or RTH 09:30-15:30), flat 15:55, max 1 trade a day (ORB: 1).
- Parameters are picked on 2021-11..2024-12 only; 2025 and 2026 (H1 Jan-Jun, H2 Jul-Oct 16) are untouched checks.
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
OUT = os.path.join(ROOT, "research", "retail")
TICK, PV, COMM = 0.25, 2.0, 1.40
IS_END, START = "2024-12-31", "2021-11-01"
PERIODS = (("2021-24", START, IS_END), ("2025", "2025-01-01", "2025-12-31"), ("2026", "2026-01-01", "2026-12-31"),
           ("2026H1", "2026-01-01", "2026-06-30"), ("2026H2", "2026-07-01", "2026-12-31"))

# ------------------------------------------------------------------------------------------------ data
D = {}


def load():
    if D:
        return D
    return load_frame(pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")))


def load_frame(df, live_cut=False):
    """Fill D from a 5m frame (time, open, high, low, close, volume). load() = the research file. live_cut=True (the live
    second strategies, engine/second.py): the data ends NOW, so a higher-timeframe bar whose clock period has not ended yet
    is still forming and never counts as closed (htf / to5); the research file (live_cut False) is unchanged."""
    D.clear()
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    et = pd.to_datetime(df["time"].values, unit="s", utc=True).tz_convert("America/New_York")
    mod = (et.hour * 60 + et.minute).values.astype(np.int64)
    sdate = (et.tz_localize(None).normalize() + pd.to_timedelta((mod >= 18 * 60).astype(int), unit="D"))
    days = sdate.strftime("%Y-%m-%d").values
    uniq, sidx = np.unique(days, return_inverse=True)
    loc = (df["time"].values + et.tz_localize(None).values.astype("datetime64[s]").astype(np.int64) - df["time"].values)
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))["rolls"]
    adj = np.zeros(len(df))
    for r in rolls:                       # unadjusted = adjusted - sum(gaps of rolls after the bar)
        adj[df["time"].values < r["switch_t"]] += r["gap"]
    D.update(t=df["time"].values.astype(np.int64), o=df["open"].values.astype(float), h=df["high"].values.astype(float),
             l=df["low"].values.astype(float), c=df["close"].values.astype(float), v=df["volume"].values.astype(float),
             mod=mod, sid=sidx.astype(np.int64), days=uniq, loc=loc.astype(np.int64), adj=adj, dow=et.dayofweek.values)
    n = len(df)
    # last bar index of each session at or before 15:50 (that bar closes 15:55 -> flat exit at its close)
    last = np.full(len(uniq), -1, np.int64)
    ok = mod <= 15 * 60 + 50
    ok &= mod >= 0
    for i in np.nonzero(ok & (mod < 18 * 60))[0]:
        last[sidx[i]] = i
    D["flat_idx"] = last
    D["n"] = n
    D["live_cut"] = bool(live_cut)
    return D


def htf(tf):
    """Clock-aligned higher-timeframe bars (tf minutes) built from 5m, within one session. Returns dict with o,h,l,c,v,
    last (5m index of the bar's last 5m bar = when it is known) and first."""
    key = f"htf{tf}"
    if key in D:
        return D[key]
    d = load()
    if tf == 5:
        H = dict(o=d["o"], h=d["h"], l=d["l"], c=d["c"], v=d["v"], last=np.arange(d["n"]), first=np.arange(d["n"]), sid=d["sid"])
        D[key] = H
        return H
    sec = tf * 60
    shift = 18 * 3600 if tf >= 240 else 0          # 4h buckets start at 18:00 ET
    b = (d["loc"] - shift) // sec
    g = np.r_[True, (b[1:] != b[:-1]) | (d["sid"][1:] != d["sid"][:-1])]
    first = np.nonzero(g)[0]
    last = np.r_[first[1:] - 1, d["n"] - 1]
    H = dict(o=d["o"][first], c=d["c"][last], h=np.maximum.reduceat(d["h"], first), l=np.minimum.reduceat(d["l"], first),
             v=np.add.reduceat(d["v"], first), last=last, first=first, sid=d["sid"][first])
    # an incomplete HTF bar (the 5m data has a gap) still closes at its last 5m bar: known only then
    if D.get("live_cut") and len(last) and (int(d["loc"][d["n"] - 1]) + 300 - shift) % sec != 0:
        H["open_last"] = True        # live: the data's last HTF bar is still forming (its period has not ended)
    D[key] = H
    return H


def to5(H, vals, fill=np.nan):
    """Map an HTF series to 5m bars: the value of the latest HTF bar CLOSED at or before each 5m bar."""
    d = load()
    out = np.full(d["n"], fill, dtype=float)
    if H.get("open_last"):           # live cut: the forming HTF bar is not closed yet
        out[H["last"][:-1]] = np.asarray(vals, dtype=float)[:-1]
    else:
        out[H["last"]] = vals
    s = pd.Series(out).ffill().values
    return s


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def atr(H, n=14):
    pc = np.r_[H["c"][0], H["c"][:-1]]
    tr = np.maximum(H["h"] - H["l"], np.maximum(abs(H["h"] - pc), abs(H["l"] - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def cached(key, fn):
    if key not in D:
        D[key] = fn()
    return D[key]


def pivots(H, k):
    """Pivot lows/highs (k bars each side). Returns pl (price or nan at pivot bar), ph, both known k bars later."""
    def f():
        l, h = H["l"], H["h"]
        n = len(l)
        pl = np.full(n, np.nan); ph = np.full(n, np.nan)
        lw = pd.Series(l).rolling(2 * k + 1, center=True).min().values
        hw = pd.Series(h).rolling(2 * k + 1, center=True).max().values
        pl[(l == lw)] = l[(l == lw)]; ph[(h == hw)] = h[(h == hw)]
        return pl, ph
    return cached(("piv", id(H), k), f)


def swing_stops(tf, k=3, back=12):
    """Per HTF bar: the most recent confirmed pivot low below the bar close (long stop) and pivot high above it
    (short stop); fallback = the lowest low / highest high of the last `back` bars. Known at the bar close."""
    def f():
        H = htf(tf)
        pl, ph = pivots(H, k)
        n = len(H["c"])
        sl = np.full(n, np.nan); sh = np.full(n, np.nan)
        lows, highs = collections.deque(maxlen=12), collections.deque(maxlen=12)
        c = H["c"]
        rl = pd.Series(H["l"]).rolling(back, min_periods=1).min().values
        rh = pd.Series(H["h"]).rolling(back, min_periods=1).max().values
        for j in range(n):
            p = j - k
            if p >= 0:
                if not np.isnan(pl[p]):
                    lows.append(pl[p])
                if not np.isnan(ph[p]):
                    highs.append(ph[p])
            v = next((x for x in reversed(lows) if x < c[j]), None)
            sl[j] = v if v is not None else rl[j]
            w = next((x for x in reversed(highs) if x > c[j]), None)
            sh[j] = w if w is not None else rh[j]
        return sl, sh
    return cached(("swst", tf, k, back), f)


def trend_filter(name):
    """+1 long allowed / -1 short allowed / 0 both, per 5m bar (closed HTF bars only)."""
    def f():
        d = load()
        if name == "none":
            return np.zeros(d["n"])
        tf, n = {"h1_200": (60, 200), "h4_50": (240, 50), "m15_200": (15, 200), "m5_200": (5, 200)}[name]
        H = htf(tf)
        e = ema(H["c"], n)
        return to5(H, np.sign(H["c"] - e), 0.0)
    return cached(("tf", name), f)


def vwap_side():
    def f():
        d = load()
        rth = (d["mod"] >= 570) & (d["mod"] < 960)
        tp = (d["h"] + d["l"] + d["c"]) / 3 * d["v"] * rth
        vv = d["v"] * rth
        key = d["sid"]
        cpv = pd.Series(tp).groupby(key).cumsum().values
        cv = pd.Series(vv).groupby(key).cumsum().values
        vw = np.where(cv > 0, cpv / np.maximum(cv, 1e-9), np.nan)
        return np.sign(d["c"] - vw) * rth
    return cached("vwap", f)


# ------------------------------------------------------------------------------------------------ candidates
def C(ei, epx, dr, kind, stops, tgt=None, sig=None):
    """Candidate list. ei 5m entry bar index, epx raw entry price, dr +1/-1, kind 0 market / 1 limit, stops dict
    name -> stop price, tgt optional level-target price, sig optional 5m index of the signal bar (for sorting)."""
    ei = np.asarray(ei, np.int64)
    return {"ei": ei, "epx": np.asarray(epx, float), "dir": np.asarray(dr, np.int64), "kind": np.asarray(kind, np.int64) * np.ones(len(ei), np.int64),
            "stops": {k: np.asarray(v, float) for k, v in stops.items()},
            "tgt": np.asarray(tgt, float) if tgt is not None else np.full(len(ei), np.nan)}


def mkt(sig5, dr, stops, tgt=None):
    """Market entries at the next 5m open after the signal bar close (same session only)."""
    d = load()
    sig5 = np.asarray(sig5, np.int64)
    ok = sig5 + 1 < d["n"]
    sig5, dr = sig5[ok], np.asarray(dr)[ok]
    stops = {k: np.asarray(v)[ok] for k, v in stops.items()}
    tgt = None if tgt is None else np.asarray(tgt)[ok]
    same = d["sid"][sig5 + 1] == d["sid"][sig5]
    ei = sig5 + 1
    return C(ei[same], d["o"][ei[same]], dr[same], 0, {k: v[same] for k, v in stops.items()},
             None if tgt is None else tgt[same])


# ------------------------------------------------------------------------------------------------ simulator
WIN = {"all": (120, 930), "rth": (570, 930), "am": (570, 690)}


def simulate(cd, P, xflag=None):
    """Run one variant. P: stop (name in cd['stops']), tgt (float R | 'lvl' | 'sig' | 'trail'), be (bool), sess, maxpd,
    min_stop, max_stop, trail (n bars for 'trail'), lvl_min (min R of a level target). xflag: (exit_long, exit_short)
    boolean 5m arrays (signal exits at the next open). Returns per-micro trades."""
    d = load()
    O, Hh, Ll, Cc, sid, mod, flat = d["o"], d["h"], d["l"], d["c"], d["sid"], d["mod"], d["flat_idx"]
    a, z = WIN[P.get("sess", "all")]
    st = cd["stops"][P["stop"]]
    order = np.argsort(cd["ei"], kind="stable")
    tg = P["tgt"]
    be = P.get("be", False)
    maxpd = P.get("maxpd", 1)
    mn, mx = P.get("min_stop", 4.0), P.get("max_stop", 1e9)
    tn = P.get("trail", 6)
    lvl_min = P.get("lvl_min", 1.5)
    busy = -1
    cnt = collections.Counter()
    out = []
    for q in order:
        k0 = cd["ei"][q]
        if k0 <= busy:
            continue
        s = sid[k0]
        if cnt[s] >= maxpd or not (a <= mod[k0] < z):
            continue
        dr = cd["dir"][q]
        stop = st[q]
        if np.isnan(stop):
            continue
        lim = cd["kind"][q] == 1
        e = cd["epx"][q] + (0 if lim else dr * TICK)
        risk = (e - stop) * dr
        if risk < mn or risk > mx:
            continue
        if tg == "lvl":
            L = cd["tgt"][q]
            if np.isnan(L) or (L - e) * dr < lvl_min * risk:
                continue
            tgt = L
        elif isinstance(tg, (int, float)):
            tgt = e + dr * tg * risk
        else:
            tgt = None
        kf = flat[s]
        if kf < k0:
            continue
        sp = stop
        worst = 0.0
        ex = None
        reason = "flat"
        k = k0
        while k <= kf:
            ho, lo = (Hh[k], Ll[k]) if dr > 0 else (-Ll[k], -Hh[k])
            op = O[k] * dr
            spd = sp * dr
            if lo <= spd:                                  # stop first (conservative)
                ex = min(op, spd) - TICK if k > k0 or not lim else spd - TICK
                worst = min(worst, ex - e * dr if False else (ex - e * dr))
                reason = "stop" if sp == stop else ("be" if abs(sp - e) < 1e-9 else "trail")
                break
            worst = min(worst, lo - e * dr)
            if tgt is not None and not (lim and k == k0) and ho >= tgt * dr:
                ex = max(op, tgt * dr) if k > k0 else tgt * dr
                reason = "target"
                break
            # end of bar updates (known at the close)
            if xflag is not None and k < kf and (xflag[0][k] if dr > 0 else xflag[1][k]):
                ex = O[k + 1] * dr - TICK
                reason = "signal"
                k += 1
                worst = min(worst, ex - e * dr)
                break
            if be and sp * dr < e * dr and ho >= e * dr + risk:
                sp = e
            if tg == "trail" and k - tn + 1 >= k0 - 0:
                lo_n = (Ll[k - tn + 1:k + 1].min() - TICK) if dr > 0 else (Hh[k - tn + 1:k + 1].max() + TICK)
                if (lo_n - sp) * dr > 0 and (Cc[k] - lo_n) * dr > 0:
                    sp = lo_n
            if k == kf:
                ex = Cc[k] * dr - TICK
                reason = "flat"
                break
            k += 1
        if ex is None:
            continue
        pts = ex - e * dr
        out.append((s, k0, min(k, kf), int(dr), float(risk), float(pts), float(min(worst, pts)), reason))
        busy = min(k, kf)
        cnt[s] += 1
    return out


# ------------------------------------------------------------------------------------------------ scoring
def r_of(t):
    return (t[5] * PV - COMM) / (t[4] * PV)


def r_stats(T, lo, hi):
    d = load()
    R = np.array([r_of(t) for t in T if lo <= d["days"][t[0]] <= hi])
    nd = n_sessions(lo, hi)
    if len(R) == 0:
        return {"n": 0, "tpw": 0, "R": 0.0, "exp": 0.0, "pf": None, "t": 0.0, "win": None, "R_x5": 0.0}
    gl = -R[R < 0].sum()
    return {"n": int(len(R)), "tpw": round(len(R) / max(nd / 5, 1e-9), 2), "R": round(float(R.sum()), 1),
            "exp": round(float(R.mean()), 3), "pf": round(float(R[R > 0].sum() / gl), 2) if gl else None,
            "t": round(float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))) if len(R) > 2 and R.std() > 0 else 0.0, 2),
            "win": round(100 * float((R > 0).mean()), 1), "R_x5": round(float(np.sort(R)[:-5].sum()), 1)}


def sessions():
    d = load()
    def f():
        rth = (d["mod"] >= 570) & (d["mod"] < 960)
        s = np.unique(d["sid"][rth])
        ds = d["days"][s]
        return [x for x in ds if START <= x <= "2026-10-16"]
    return cached("sessions", f)


def n_sessions(lo, hi):
    return sum(1 for x in sessions() if lo <= x <= hi)


def qty(rule, rp):
    if rule == "lit":
        r = 800.0 if rp <= 20 else 800.0 * 20 / rp
        return max(0, min(40, int(r / (rp * PV))))
    if rule.startswith("fix"):
        return int(rule[3:])
    if rule.startswith("usd"):
        return max(0, min(40, int(float(rule[3:]) / (rp * PV))))
    raise ValueError(rule)


SIZINGS = ("lit", "usd500", "usd300", "fix2", "fix5", "fix10")


def sized(T, rule):
    """Per-micro trades -> runlib-style trades at a sizing rule."""
    d = load()
    out = []
    for t in T:
        q = qty(rule, t[4])
        if q <= 0:
            continue
        pnl = q * (t[5] * PV - COMM)
        out.append({"day": d["days"][t[0]], "entry_t": int(d["t"][t[1]]), "exit_t": int(d["t"][t[2]] + 300), "dir": t[3],
                    "r": round(r_of(t), 3), "pnl": round(pnl, 2), "risk_pts": round(t[4], 2), "qty": q,
                    "risk_usd": round(q * t[4] * PV, 2), "half": False, "exit": t[7], "trigger": "", "mfe": None,
                    "mae": round(-t[6] / t[4], 3), "bars_held": int(t[2] - t[1] + 1), "regime": "", "mult": 1.0,
                    "low": round(min(q * (t[6] * PV - COMM), pnl), 2)})
    return out


def eval_path(T, horizon=60):
    """MFFU Builder 50K eval with path sizing: lit micros capped at 0.6 x room / (stop x $2), fresh eval every session.
    Returns p10/f10/p20/f20 (% of starts) and the median sessions to pass."""
    from engine.analytics import PLANS
    plan = PLANS["builder_50k"]
    d = load()
    S = sessions()
    by = collections.defaultdict(list)
    for t in T:
        by[d["days"][t[0]]].append(t)
    res = []
    for i in range(len(S)):
        bal, peak = plan["start"], plan["start"]
        mll = bal - plan["mll"]; lock = plan["start"] + plan["lock_above"]
        r = ("OPEN", horizon)
        for k, day in enumerate(S[i:i + horizon]):
            dp, low = 0.0, 0.0
            for t in by.get(day, []):
                room = bal + dp - mll
                if room <= 0:
                    break
                q = min(qty("lit", t[4]), int(0.6 * room / (t[4] * PV)))
                if q <= 0:
                    continue
                low = min(low, dp + q * (t[6] * PV - COMM)); dp += q * (t[5] * PV - COMM); low = min(low, dp)
            if bal + low <= mll or bal + dp <= mll:
                r = ("FAIL", k + 1); break
            bal += dp
            peak = max(peak, bal); mll = min(max(mll, peak - plan["mll"]), lock)
            if bal - plan["start"] >= plan["target"]:
                r = ("PASS", k + 1); break
        res.append((S[i], r))
    return res


def eval_summary(res, lo, hi):
    rr = [r for day, r in res if lo <= day <= hi]
    n = len(rr) or 1
    f = lambda kind, H: round(100 * sum(1 for x in rr if x[0] == kind and x[1] <= H) / n, 1)
    ps = [x[1] for x in rr if x[0] == "PASS"]
    return {"p10": f("PASS", 10), "f10": f("FAIL", 10), "p20": f("PASS", 20), "f20": f("FAIL", 20),
            "pass_med": float(np.median(ps)) if ps else None}


def money(T, rule, lo, hi):
    from tools import runlib as rl
    S = [x for x in sessions() if lo <= x <= hi]
    TT = [t for t in sized(T, rule) if lo <= t["day"] <= hi]
    days = rl.days_of(TT, S)
    return rl._compact(TT, days) if TT else {"n": 0, "net": 0, "per_month": 0}, days


def lit_daily():
    def f():
        r = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
        return {x[0]: x[1] for x in r["days"]}
    return cached("litd", f)


def corr_lit(days, lo, hi):
    L = lit_daily()
    a = [(x["pnl"], L[x["date"]]) for x in days if lo <= x["date"] <= hi and x["date"] in L]
    if len(a) < 20:
        return None
    x, y = np.array(a).T
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 2)


# ------------------------------------------------------------------------------------------------ families
def ema_cross(tf, fast, slow, trend):
    H = htf(tf)
    f, s = ema(H["c"], fast), ema(H["c"], slow)
    up = (f > s) & (np.r_[False, f[:-1] <= s[:-1]])
    dn = (f < s) & (np.r_[False, f[:-1] >= s[:-1]])
    j = np.nonzero(up | dn)[0]
    j = j[j > 250]
    dr = np.where(up[j], 1, -1)
    i5 = H["last"][j]
    if trend == "tf200":
        e2 = ema(H["c"], 200); ok = np.sign(H["c"][j] - e2[j]) == dr
    else:
        ok = (trend_filter(trend)[i5] == dr) | (trend == "none")
    j, dr, i5 = j[ok], dr[ok], i5[ok]
    sl, sh = swing_stops(tf)
    lo3 = pd.Series(H["l"]).rolling(3, min_periods=1).min().values
    hi3 = pd.Series(H["h"]).rolling(3, min_periods=1).max().values
    stops = {"tight": np.where(dr > 0, lo3[j] - TICK, hi3[j] + TICK), "swing": np.where(dr > 0, sl[j] - TICK, sh[j] + TICK)}
    cd = mkt(i5, dr, stops)
    xl = np.zeros(load()["n"], bool); xs = xl.copy()
    xl[H["last"][dn]] = True; xs[H["last"][up]] = True
    return cd, (xl, xs)


def ema_pullback(tf, pe, trend):
    H = htf(tf)
    c, o, h, l = H["c"], H["o"], H["h"], H["l"]
    e8, e21, e50, e200 = ema(c, 8), ema(c, 21), ema(c, 50), ema(c, 200)
    ep = e21 if pe == 21 else e50
    stack_up = (e8 > e21) & (e21 > e50)
    stack_dn = (e8 < e21) & (e21 < e50)
    if trend == "200":
        stack_up &= c > e200; stack_dn &= c < e200
    rng = np.maximum(h - l, TICK)
    up = stack_up & (l <= ep) & (c > ep) & (c > o) & ((c - l) / rng >= 0.5)
    dn = stack_dn & (h >= ep) & (c < ep) & (c < o) & ((h - c) / rng >= 0.5)
    prev_above = np.r_[False, c[:-1] > ep[:-1]]
    prev_below = np.r_[False, c[:-1] < ep[:-1]]
    up &= prev_above; dn &= prev_below
    j = np.nonzero(up | dn)[0]; j = j[j > 250]
    dr = np.where(up[j], 1, -1)
    lo5 = pd.Series(l).rolling(5, min_periods=1).min().values
    hi5 = pd.Series(h).rolling(5, min_periods=1).max().values
    stops = {"candle": np.where(dr > 0, l[j] - TICK, h[j] + TICK), "pull": np.where(dr > 0, lo5[j] - TICK, hi5[j] + TICK)}
    cd = mkt(H["last"][j], dr, stops)
    xl = np.zeros(load()["n"], bool); xs = xl.copy()
    xl[H["last"][c < e50]] = True; xs[H["last"][c > e50]] = True
    return cd, (xl, xs)


def ema_ribbon(tf, trend, xema):
    H = htf(tf)
    c = H["c"]
    E = [ema(c, n) for n in (8, 13, 21, 34, 55)]
    up = np.all([E[i] > E[i + 1] for i in range(4)], axis=0) & (c > E[0])
    dn = np.all([E[i] < E[i + 1] for i in range(4)], axis=0) & (c < E[0])
    su = up & ~np.r_[False, up[:-1]]
    sd = dn & ~np.r_[False, dn[:-1]]
    j = np.nonzero(su | sd)[0]; j = j[j > 250]
    dr = np.where(su[j], 1, -1)
    i5 = H["last"][j]
    tr = trend_filter(trend)
    ok = (tr[i5] == dr) | (trend == "none")
    j, dr, i5 = j[ok], dr[ok], i5[ok]
    sl, sh = swing_stops(tf)
    lo3 = pd.Series(H["l"]).rolling(3, min_periods=1).min().values
    hi3 = pd.Series(H["h"]).rolling(3, min_periods=1).max().values
    stops = {"tight": np.where(dr > 0, lo3[j] - TICK, hi3[j] + TICK), "swing": np.where(dr > 0, sl[j] - TICK, sh[j] + TICK)}
    cd = mkt(i5, dr, stops)
    ex = E[2] if xema == 21 else E[3]
    xl = np.zeros(load()["n"], bool); xs = xl.copy()
    xl[H["last"][c < ex]] = True; xs[H["last"][c > ex]] = True
    return cd, (xl, xs)


def ema_openhour(trig, filt):
    """8/21 EMA momentum in the first RTH hour on 5m (09:35-10:30)."""
    d = load()
    c, o = d["c"], d["o"]
    e8, e21 = ema(c, 8), ema(c, 21)
    m = d["mod"]
    win = (m >= 575) & (m < 630)
    if trig == "cross":
        up = (e8 > e21) & np.r_[False, e8[:-1] <= e21[:-1]]
        dn = (e8 < e21) & np.r_[False, e8[:-1] >= e21[:-1]]
    else:   # state: 8 over 21 and a candle closing with it, first such bar of the hour
        up = (e8 > e21) & (c > e8) & (c > o)
        dn = (e8 < e21) & (c < e8) & (c < o)
    up &= win; dn &= win
    if filt == "vwap":
        vs = vwap_side(); up &= vs > 0; dn &= vs < 0
    elif filt != "none":
        tr = trend_filter(filt); up &= tr > 0; dn &= tr < 0
    j = np.nonzero(up | dn)[0]; j = j[j > 250]
    dr = np.where(up[j], 1, -1)
    sl, sh = swing_stops(5)
    lo3 = pd.Series(d["l"]).rolling(3, min_periods=1).min().values
    hi3 = pd.Series(d["h"]).rolling(3, min_periods=1).max().values
    stops = {"tight": np.where(dr > 0, lo3[j] - TICK, hi3[j] + TICK), "swing": np.where(dr > 0, sl[j] - TICK, sh[j] + TICK)}
    cd = mkt(j, dr, stops)
    xl = (e8 < e21); xs = (e8 > e21)
    return cd, (xl, xs)


def macd(H, a=12, b=26, s=9):
    m = ema(H["c"], a) - ema(H["c"], b)
    sg = ema(m, s)
    return m, sg, m - sg


def macd_sig(tf, mode, trend, zone="any", nfall=3):
    """mode: cross (signal-line cross), zero (zero-line cross), hist (histogram turns after nfall bars)."""
    H = htf(tf)
    m, sg, hs = macd(H)
    c = H["c"]
    if mode == "cross":
        up = (m > sg) & np.r_[False, m[:-1] <= sg[:-1]]
        dn = (m < sg) & np.r_[False, m[:-1] >= sg[:-1]]
        if zone == "zero":
            up &= m < 0; dn &= m > 0
        xl, xs = dn, up
    elif mode == "zero":
        up = (m > 0) & np.r_[False, m[:-1] <= 0]
        dn = (m < 0) & np.r_[False, m[:-1] >= 0]
        xl, xs = dn, up
    else:
        shf = lambda x, k: np.r_[np.full(k, np.nan), x[:-k]]
        fall = np.all([shf(hs, k) < shf(hs, k + 1) for k in range(1, nfall + 1)], axis=0)
        rise = np.all([shf(hs, k) > shf(hs, k + 1) for k in range(1, nfall + 1)], axis=0)
        up = (hs > np.r_[0, hs[:-1]]) & (hs < 0) & fall
        dn = (hs < np.r_[0, hs[:-1]]) & (hs > 0) & rise
        xl = hs < np.r_[0, hs[:-1]]
        xs = hs > np.r_[0, hs[:-1]]
    j = np.nonzero(up | dn)[0]; j = j[j > 250]
    dr = np.where(up[j], 1, -1)
    i5 = H["last"][j]
    if trend == "tf200":
        e2 = ema(c, 200); ok = np.sign(c[j] - e2[j]) == dr
    elif trend == "none":
        ok = np.ones(len(j), bool)
    else:
        ok = trend_filter(trend)[i5] == dr
    j, dr, i5 = j[ok], dr[ok], i5[ok]
    sl, sh = swing_stops(tf)
    lo3 = pd.Series(H["l"]).rolling(3, min_periods=1).min().values
    hi3 = pd.Series(H["h"]).rolling(3, min_periods=1).max().values
    stops = {"tight": np.where(dr > 0, lo3[j] - TICK, hi3[j] + TICK), "swing": np.where(dr > 0, sl[j] - TICK, sh[j] + TICK)}
    cd = mkt(i5, dr, stops)
    n = load()["n"]
    XL = np.zeros(n, bool); XS = XL.copy()
    XL[H["last"][xl]] = True; XS[H["last"][xs]] = True
    return cd, (XL, XS)


def macd_div(tf, k, osc, trend):
    """Regular divergence: a new pivot low below the previous pivot low (within 40 bars) while the MACD line (or the
    histogram) is higher; entry when the pivot is confirmed (k bars later) and that bar closes up. Stop beyond the
    divergence low; level target = the swing high between the two lows."""
    H = htf(tf)
    m, sg, hs = macd(H)
    x = m if osc == "macd" else hs
    pl, ph = pivots(H, k)
    c, o, h, l = H["c"], H["o"], H["h"], H["l"]
    sig, dr, stp, tgt = [], [], [], []
    PL = np.nonzero(~np.isnan(pl))[0]; PH = np.nonzero(~np.isnan(ph))[0]
    for arr, d_, src, opp in ((PL, 1, l, h), (PH, -1, h, l)):
        for a_, b_ in zip(arr[:-1], arr[1:]):
            if b_ - a_ > 40 or b_ - a_ < 3:
                continue
            q = b_ + k
            if q >= len(c):
                continue
            if d_ > 0 and src[b_] < src[a_] and x[b_] > x[a_] and x[b_] < 0 and c[q] > o[q]:
                sig.append(q); dr.append(1); stp.append(l[b_:q + 1].min() - TICK); tgt.append(h[a_:b_ + 1].max())
            if d_ < 0 and src[b_] > src[a_] and x[b_] < x[a_] and x[b_] > 0 and c[q] < o[q]:
                sig.append(q); dr.append(-1); stp.append(h[b_:q + 1].max() + TICK); tgt.append(l[a_:b_ + 1].min())
    sig = np.array(sig, np.int64); dr = np.array(dr); stp = np.array(stp); tgt = np.array(tgt)
    srt = np.argsort(sig); sig, dr, stp, tgt = sig[srt], dr[srt], stp[srt], tgt[srt]
    keep = sig > 250
    sig, dr, stp, tgt = sig[keep], dr[keep], stp[keep], tgt[keep]
    i5 = H["last"][sig]
    if trend != "none":
        ok = trend_filter(trend)[i5] == dr
        sig, dr, stp, tgt, i5 = sig[ok], dr[ok], stp[ok], tgt[ok], i5[ok]
    sl, sh = swing_stops(tf)
    wide = np.where(dr > 0, np.minimum(stp, sl[sig] - TICK), np.maximum(stp, sh[sig] + TICK))
    cd = mkt(i5, dr, {"div": stp, "swing": wide}, tgt)
    n = load()["n"]
    XL = np.zeros(n, bool); XS = XL.copy()
    xl = (m < sg) & np.r_[False, m[:-1] >= sg[:-1]]; xs = (m > sg) & np.r_[False, m[:-1] <= sg[:-1]]
    XL[H["last"][xl]] = True; XS[H["last"][xs]] = True
    return cd, (XL, XS)


# ---- support / resistance levels per session
def day_levels(src):
    """dict sid -> list of (price, name, active_from_mod). Known before they are used."""
    def f():
        d = load()
        n_s = len(d["days"])
        out = collections.defaultdict(list)
        sid, m, h, l = d["sid"], d["mod"], d["h"], d["l"]
        rth = (m >= 570) & (m < 960)
        on = (m >= 18 * 60) | (m < 570)
        rh = pd.Series(np.where(rth, h, -np.inf)).groupby(sid).max().reindex(range(n_s)).values
        rl = pd.Series(np.where(rth, l, np.inf)).groupby(sid).min().reindex(range(n_s)).values
        oh = pd.Series(np.where(on, h, -np.inf)).groupby(sid).max().reindex(range(n_s)).values
        ol = pd.Series(np.where(on, l, np.inf)).groupby(sid).min().reindex(range(n_s)).values
        for s in range(1, n_s):
            if "pd" in src and np.isfinite(rh[s - 1]) and np.isfinite(rl[s - 1]):
                out[s] += [(rh[s - 1], "pdh", 0), (rl[s - 1], "pdl", 0)]
            if "on" in src and np.isfinite(oh[s]):
                out[s] += [(oh[s], "onh", 930), (ol[s], "onl", 930)]   # minutes since 18:00 ET (= 09:30)
        if "sw" in src:     # swing clusters: 1h pivots (k=3) of the last 10 sessions, 2+ within 0.08% of price
            H = htf(60)
            pl, ph = pivots(H, 3)
            by = collections.defaultdict(list)
            nH = len(H["c"])
            for arr in (pl, ph):
                for j in np.nonzero(~np.isnan(arr))[0]:
                    if j + 3 < nH:
                        by[H["sid"][j + 3]].append(arr[j])     # known when the pivot is confirmed (3 bars later)
            for s in range(10, n_s):
                vals = sorted(v for q in range(s - 10, s) for v in by.get(q, []))
                if not vals:
                    continue
                tol = vals[-1] * 0.0008
                cl, grp = [], [vals[0]]
                for v in vals[1:]:
                    if v - grp[-1] <= tol:
                        grp.append(v)
                    else:
                        cl.append(grp); grp = [v]
                cl.append(grp)
                for g in cl:
                    if len(g) >= 2:
                        out[s].append((float(np.mean(g)), "sw", 0))
        if "rn" in src:     # round numbers (unadjusted 100s) near the prior close, mapped to adjusted prices
            first = np.r_[0, np.nonzero(np.diff(sid))[0] + 1]
            for s_i, i in enumerate(first):
                s = sid[i]
                ua = d["c"][i] - d["adj"][i]
                base = math.floor(ua / 100) * 100
                for k in range(-3, 5):
                    out[s].append((base + 100 * k + d["adj"][i], "rn", 0))
        return out
    return cached(("lv", src), f)


def sr_signals(src, mode, tf=5, nret=12):
    """mode bounce: a bar trades through a level and closes back on its side with a rejection candle -> market entry
    against the poke. Stops: 'tight' beyond that candle, 'swing' beyond the 6-bar extreme. Level target = the next level
    the other way. mode retest: a close through a level arms it for nret bars; the first bar that comes back to touch it
    and closes on the break side (rejection) -> market entry. Stops: 'tight' beyond the retest candle, 'swing' beyond
    the breakout candle. mode limit: limit at the broken level after the break; stops: 'tight' beyond the breakout
    candle, 'swing' beyond the 6-bar extreme before the break."""
    d = load()
    LV = day_levels(src)
    H = htf(tf)
    o, h, l, c, sidH, last = H["o"], H["h"], H["l"], H["c"], H["sid"], H["last"]
    modH = (d["mod"][H["first"]] - 1080) % 1440          # minutes since 18:00 ET of the bar's start
    lo6 = pd.Series(l).rolling(6, min_periods=1).min().values
    hi6 = pd.Series(h).rolling(6, min_periods=1).max().values
    starts = np.r_[0, np.nonzero(np.diff(sidH))[0] + 1, len(c)]
    sig, dr, st1, st2, tg, kind, epx, ei = [], [], [], [], [], [], [], []
    for a_, b_ in zip(starts[:-1], starts[1:]):
        s = sidH[a_]
        lvls = LV.get(s)
        if not lvls:
            continue
        used = set()
        armed = {}
        prices = sorted(p for p, _, _ in lvls)
        for j in range(a_ + 1, b_):
            mj = modH[j]
            for p, nm, frm in lvls:
                if mj < frm + tf or (p, nm) in used:
                    continue
                if mode == "bounce":
                    if l[j] < p < c[j] and c[j - 1] > p and c[j] > o[j]:
                        nxt = [x for x in prices if x > c[j] + 1]
                        sig.append(j); dr.append(1); st1.append(l[j] - TICK); st2.append(min(lo6[j], l[j]) - TICK)
                        tg.append(nxt[0] if nxt else np.nan); used.add((p, nm))
                    elif h[j] > p > c[j] and c[j - 1] < p and c[j] < o[j]:
                        nxt = [x for x in prices if x < c[j] - 1]
                        sig.append(j); dr.append(-1); st1.append(h[j] + TICK); st2.append(max(hi6[j], h[j]) + TICK)
                        tg.append(nxt[-1] if nxt else np.nan); used.add((p, nm))
                else:
                    key = (p, nm)
                    if key in armed:
                        dd, j0, bl, pre = armed[key]
                        if j - j0 > nret:
                            del armed[key]; used.add(key); continue
                        if mode == "retest":
                            if dd > 0 and l[j] <= p and c[j] > p and c[j] > o[j]:
                                nxt = [x for x in prices if x > c[j] + 1]
                                sig.append(j); dr.append(1); st1.append(l[j] - TICK); st2.append(min(bl, l[j]) - TICK)
                                tg.append(nxt[0] if nxt else np.nan); used.add(key); del armed[key]
                            elif dd < 0 and h[j] >= p and c[j] < p and c[j] < o[j]:
                                nxt = [x for x in prices if x < c[j] - 1]
                                sig.append(j); dr.append(-1); st1.append(h[j] + TICK); st2.append(max(bl, h[j]) + TICK)
                                tg.append(nxt[-1] if nxt else np.nan); used.add(key); del armed[key]
                            elif (dd > 0 and c[j] < p) or (dd < 0 and c[j] > p):
                                del armed[key]; used.add(key)
                        continue
                    if c[j] > p >= c[j - 1]:
                        armed[key] = (1, j, l[j], lo6[j - 1])
                    elif c[j] < p <= c[j - 1]:
                        armed[key] = (-1, j, h[j], hi6[j - 1])
            # limit orders: resolved below on 5m bars
    sig = np.array(sig, np.int64); dr = np.array(dr, np.int64)
    return mkt(last[sig], dr, {"tight": np.array(st1), "swing": np.array(st2)}, np.array(tg)), None


def sr_limit(src, tf=5, nret=12):
    """Break then limit at the broken level (retest fill)."""
    d = load()
    LV = day_levels(src)
    H = htf(tf)
    o, h, l, c, sidH, last = H["o"], H["h"], H["l"], H["c"], H["sid"], H["last"]
    modH = (d["mod"][H["first"]] - 1080) % 1440          # minutes since 18:00 ET of the bar's start
    lo6 = pd.Series(l).rolling(6, min_periods=1).min().values
    hi6 = pd.Series(h).rolling(6, min_periods=1).max().values
    O5, H5, L5, sid5 = d["o"], d["h"], d["l"], d["sid"]
    starts = np.r_[0, np.nonzero(np.diff(sidH))[0] + 1, len(c)]
    E, P_, DR, S1, S2, TG = [], [], [], [], [], []
    for a_, b_ in zip(starts[:-1], starts[1:]):
        s = sidH[a_]
        lvls = LV.get(s)
        if not lvls:
            continue
        prices = sorted(p for p, _, _ in lvls)
        used = set()
        for j in range(a_ + 1, b_):
            for p, nm, frm in lvls:
                if modH[j] < frm + tf or (p, nm) in used:
                    continue
                dd = 1 if c[j] > p >= c[j - 1] else -1 if c[j] < p <= c[j - 1] else 0
                if not dd:
                    continue
                used.add((p, nm))
                k1 = last[j] + 1
                k2 = min(last[min(j + nret, b_ - 1)], last[b_ - 1])
                if k1 > k2:
                    continue
                seg = (L5[k1:k2 + 1] <= p - TICK) if dd > 0 else (H5[k1:k2 + 1] >= p + TICK)
                if not seg.any():
                    continue
                k = k1 + int(np.argmax(seg))
                fill = min(O5[k], p) if dd > 0 else max(O5[k], p)
                nxt = [x for x in prices if x > p + 1] if dd > 0 else [x for x in prices if x < p - 1]
                E.append(k); P_.append(fill); DR.append(dd)
                S1.append(l[j] - TICK if dd > 0 else h[j] + TICK)
                S2.append(min(lo6[j], l[j]) - TICK if dd > 0 else max(hi6[j], h[j]) + TICK)
                TG.append((nxt[0] if dd > 0 else nxt[-1]) if nxt else np.nan)
    return C(E, P_, DR, 1, {"tight": S1, "swing": S2}, TG)


def orb(orm, filt, cutoff):
    """Opening-range breakout: first 5m close beyond the 09:30 + orm range before the cutoff. Stops: 'opp' = the other
    side of the range, 'mid' = the range midpoint. Level target = none (R targets / signal = none / trail)."""
    d = load()
    m, sid, h, l, c = d["mod"], d["sid"], d["h"], d["l"], d["c"]
    sig, dr, s1, s2 = [], [], [], []
    vs = vwap_side()
    tr = trend_filter(filt) if filt not in ("none", "vwap", "gap") else None
    starts = np.r_[0, np.nonzero(np.diff(sid))[0] + 1, d["n"]]
    for a_, b_ in zip(starts[:-1], starts[1:]):
        mm = m[a_:b_]
        rng = np.nonzero((mm >= 570) & (mm < 570 + orm))[0]
        if len(rng) < orm // 5:
            continue
        hi, lo = h[a_ + rng].max(), l[a_ + rng].min()
        after = np.nonzero((mm >= 570 + orm) & (mm < cutoff))[0]
        for q in after:
            i = a_ + q
            dd = 1 if c[i] > hi else -1 if c[i] < lo else 0
            if not dd:
                continue
            if filt == "vwap" and vs[i] != dd:
                break
            if tr is not None and tr[i] != dd:
                break
            sig.append(i); dr.append(dd)
            s1.append(lo - TICK if dd > 0 else hi + TICK); s2.append((hi + lo) / 2 - (TICK if dd > 0 else -TICK))
            break
    return mkt(sig, dr, {"opp": s1, "mid": s2}), None


def sd_zones(tf, imp, age, trend):
    """Supply/demand: a base of 1-3 small candles (range <= 0.8 ATR, body <= half the range) then an impulse candle with a
    body >= imp x ATR closing beyond the base. Demand zone = base low (distal) .. highest base body (proximal). First
    retest (fresh zone): limit at the proximal, filled on 5m once price trades 1 tick through, within `age` sessions.
    Stops: 'edge' 1 tick beyond the distal, 'leg' beyond the lowest low of the 6 bars before the impulse. Level target =
    the proximal of the nearest fresh opposite zone."""
    d = load()
    H = htf(tf)
    o, h, l, c, last, sidH = H["o"], H["h"], H["l"], H["c"], H["last"], H["sid"]
    A = atr(H)
    body = abs(c - o); rng = h - l
    small = (rng <= 0.8 * A) & (body <= 0.5 * np.maximum(rng, TICK))
    Z = []   # (created_5m, dir, prox, dist, leg)
    lo6 = pd.Series(l).rolling(6, min_periods=1).min().values
    hi6 = pd.Series(h).rolling(6, min_periods=1).max().values
    for j in range(20, len(c)):
        if body[j] < imp * A[j - 1]:
            continue
        nb = 0
        while nb < 3 and small[j - 1 - nb] and sidH[j - 1 - nb] == sidH[j]:
            nb += 1
        if nb == 0:
            continue
        bs = slice(j - nb, j)
        bh, bl = h[bs].max(), l[bs].min()
        if c[j] > o[j] and c[j] > bh:
            prox = np.maximum(o[bs], c[bs]).max(); dist = min(bl, l[j])
            Z.append((last[j], 1, prox, dist, min(lo6[j - 1], dist)))
        elif c[j] < o[j] and c[j] < bl:
            prox = np.minimum(o[bs], c[bs]).min(); dist = max(bh, h[j])
            Z.append((last[j], -1, prox, dist, max(hi6[j - 1], dist)))
    O5, H5, L5, sid5 = d["o"], d["h"], d["l"], d["sid"]
    fs = d["flat_idx"]
    n5 = d["n"]
    first_of = np.r_[0, np.nonzero(np.diff(sid5))[0] + 1]
    sess_first = {sid5[i]: i for i in first_of}
    tr = trend_filter(trend)
    E, P_, DR, S1, S2, TG, ZD = [], [], [], [], [], [], []
    touched = []
    for (k0, dd, prox, dist, leg) in Z:
        s_end = min(sid5[k0] + age, sid5[-1])
        kend = sess_first.get(s_end + 1, n5) - 1
        a = k0 + 1
        if a >= n5:
            touched.append(n5); continue
        seg = (L5[a:kend + 1] <= prox - TICK) if dd > 0 else (H5[a:kend + 1] >= prox + TICK)
        if not seg.any():
            touched.append(kend + 1); continue
        k = a + int(np.argmax(seg))
        touched.append(k)
        if trend != "none" and tr[k - 1] != dd:
            continue
        fill = min(O5[k], prox) if dd > 0 else max(O5[k], prox)
        E.append(k); P_.append(fill); DR.append(dd); S1.append(dist - dd * TICK); S2.append(leg - dd * TICK); ZD.append(len(touched) - 1)
    # level target: nearest fresh opposite zone alive at the fill (created before it, not yet touched)
    Zc = np.array([z[0] for z in Z]); Zd = np.array([z[1] for z in Z]); Zp = np.array([z[2] for z in Z]); Tt = np.array(touched)
    for q, k in enumerate(E):
        dd = DR[q]
        alive = (Zc < k) & (Tt > k) & (Zd == -dd)
        cand = Zp[alive]
        cand = cand[(cand > P_[q]) if dd > 0 else (cand < P_[q])]
        TG.append((cand.min() if dd > 0 else cand.max()) if len(cand) else np.nan)
    return C(E, P_, DR, 1, {"edge": S1, "leg": S2}, TG), None


def sd_confirm(tf, imp, age, trend, nconf=12):
    """Supply/demand with a confirmation entry (the other common retail way): the zone (same definition as sd_zones) is
    touched for the first time, then within `nconf` 5m bars a 5m candle closes back out of the zone in the zone's
    direction -> market entry at the next open. A close beyond the distal first kills the zone. Stops: 'edge' beyond the
    distal, 'tight' beyond the low/high made inside the zone. Level target = the nearest fresh opposite zone."""
    d = load()
    H = htf(tf)
    o, h, l, c, last, sidH = H["o"], H["h"], H["l"], H["c"], H["last"], H["sid"]
    A = atr(H)
    body = abs(c - o); rng = h - l
    small = (rng <= 0.8 * A) & (body <= 0.5 * np.maximum(rng, TICK))
    Z = []
    for j in range(20, len(c)):
        if body[j] < imp * A[j - 1]:
            continue
        nb = 0
        while nb < 3 and small[j - 1 - nb] and sidH[j - 1 - nb] == sidH[j]:
            nb += 1
        if nb == 0:
            continue
        bs = slice(j - nb, j)
        bh, bl = h[bs].max(), l[bs].min()
        if c[j] > o[j] and c[j] > bh:
            Z.append((last[j], 1, np.maximum(o[bs], c[bs]).max(), min(bl, l[j])))
        elif c[j] < o[j] and c[j] < bl:
            Z.append((last[j], -1, np.minimum(o[bs], c[bs]).min(), max(bh, h[j])))
    O5, H5, L5, C5, sid5 = d["o"], d["h"], d["l"], d["c"], d["sid"]
    n5 = d["n"]
    first_of = np.r_[0, np.nonzero(np.diff(sid5))[0] + 1]
    sess_first = {sid5[i]: i for i in first_of}
    tr = trend_filter(trend)
    SIG, DR, S1, S2, touched = [], [], [], [], []
    for (k0, dd, prox, dist) in Z:
        s_end = min(sid5[k0] + age, sid5[-1])
        kend = sess_first.get(s_end + 1, n5) - 1
        a = k0 + 1
        if a >= n5:
            touched.append(n5); continue
        seg = (L5[a:kend + 1] <= prox) if dd > 0 else (H5[a:kend + 1] >= prox)
        if not seg.any():
            touched.append(kend + 1); continue
        k = a + int(np.argmax(seg))
        touched.append(k)
        if trend != "none" and tr[k - 1] != dd:
            continue
        ext = L5[k] if dd > 0 else H5[k]
        for q in range(k, min(k + nconf, n5 - 1)):
            if sid5[q] != sid5[k]:
                break
            ext = min(ext, L5[q]) if dd > 0 else max(ext, H5[q])
            if (C5[q] - dist) * dd < 0:
                break
            if (C5[q] - prox) * dd > 0 and (C5[q] - O5[q]) * dd > 0:
                SIG.append(q); DR.append(dd); S1.append(dist - dd * TICK); S2.append(ext - dd * TICK)
                break
    Zc = np.array([z[0] for z in Z]); Zd = np.array([z[1] for z in Z]); Zp = np.array([z[2] for z in Z]); Tt = np.array(touched)
    TG = []
    for q, dd in zip(SIG, DR):
        alive = (Zc < q) & (Tt > q) & (Zd == -dd)
        cand = Zp[alive]
        cand = cand[(cand > C5[q]) if dd > 0 else (cand < C5[q])]
        TG.append((cand.min() if dd > 0 else cand.max()) if len(cand) else np.nan)
    return mkt(SIG, DR, {"edge": S1, "tight": S2}, TG), None


# ------------------------------------------------------------------------------------------------ grids
TG_R = [1.5, 2.0, 3.0]
GRIDS = {
    # family, sub, generator args grid, sim grid
    "ema_cross": ("ema", ema_cross, {"tf": [5, 15, 60], "fs": [(8, 21), (9, 21), (20, 50)], "trend": ["none", "tf200", "h1_200"]},
                  {"stop": ["tight", "swing"], "tgt": TG_R + ["sig"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "ema_pullback": ("ema", ema_pullback, {"tf": [5, 15, 60], "pe": [21, 50], "trend": ["stack", "200"]},
                     {"stop": ["candle", "pull"], "tgt": TG_R + ["sig"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "ema_ribbon": ("ema", ema_ribbon, {"tf": [5, 15], "trend": ["none", "h1_200"], "xema": [21, 34]},
                   {"stop": ["tight", "swing"], "tgt": ["sig", "trail", 3.0], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "ema_openhour": ("ema", ema_openhour, {"trig": ["cross", "state"], "filt": ["none", "vwap", "h1_200"]},
                     {"stop": ["tight", "swing"], "tgt": TG_R + ["sig"], "be": [False, True], "sess": ["rth"], "maxpd": [1, 2]}),
    "macd_cross": ("macd", lambda tf, trend, zone: macd_sig(tf, "cross", trend, zone),
                   {"tf": [5, 15, 60], "trend": ["tf200", "h1_200"], "zone": ["any", "zero"]},
                   {"stop": ["tight", "swing"], "tgt": TG_R + ["sig"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "macd_zero": ("macd", lambda tf, trend: macd_sig(tf, "zero", trend), {"tf": [5, 15], "trend": ["none", "tf200", "h1_200"]},
                  {"stop": ["tight", "swing"], "tgt": TG_R + ["sig"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "macd_hist": ("macd", lambda tf, trend, nfall: macd_sig(tf, "hist", trend, nfall=nfall),
                  {"tf": [5, 15], "trend": ["tf200", "h1_200"], "nfall": [3, 5]},
                  {"stop": ["tight", "swing"], "tgt": TG_R + ["sig"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "macd_div": ("macd", macd_div, {"tf": [5, 15, 60], "k": [2, 3], "osc": ["macd", "hist"], "trend": ["none", "h1_200"]},
                 {"stop": ["div", "swing"], "tgt": TG_R + ["lvl"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "sr_bounce": ("sr", lambda src, tf: sr_signals(src, "bounce", tf), {"src": ["pd", "on", "pdon", "sw", "rn"], "tf": [5, 15]},
                  {"stop": ["tight", "swing"], "tgt": [1.0, 1.5, 2.0, 3.0, "lvl"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "sr_retest": ("sr", lambda src, tf: sr_signals(src, "retest", tf), {"src": ["pd", "on", "pdon", "sw", "rn"], "tf": [5, 15]},
                  {"stop": ["tight", "swing"], "tgt": [1.5, 2.0, 3.0, "lvl"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "sr_limit": ("sr", lambda src, tf: (sr_limit(src, tf), None), {"src": ["pd", "on", "pdon", "sw", "rn"], "tf": [5, 15]},
                 {"stop": ["tight", "swing"], "tgt": [1.5, 2.0, 3.0, "lvl"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "orb": ("sr", orb, {"orm": [5, 15, 30], "filt": ["none", "vwap", "h1_200"], "cutoff": [660, 720]},
            {"stop": ["opp", "mid"], "tgt": [1.0, 1.5, 2.0, 3.0, "trail"], "be": [False, True], "sess": ["rth"]}),
    "sd_confirm": ("sd", sd_confirm, {"tf": [15, 60, 240], "imp": [1.0, 1.5], "age": [5, 20], "trend": ["none", "h1_200", "h4_50"]},
                   {"stop": ["edge", "tight"], "tgt": TG_R + ["lvl"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
    "sd_zone": ("sd", sd_zones, {"tf": [15, 60, 240], "imp": [1.0, 1.5], "age": [5, 20], "trend": ["none", "h1_200", "h4_50"]},
                {"stop": ["edge", "leg"], "tgt": TG_R + ["lvl"], "be": [False, True], "sess": ["all", "rth"], "maxpd": [1, 2]}),
}
FAMILY_NAME = {"ema": "EMA", "macd": "MACD", "sr": "Support / resistance (incl. ORB)", "sd": "Supply / demand"}


def gen_args(sub):
    fam, fn, g, sg = GRIDS[sub]
    keys = list(g)
    for vals in itertools.product(*[g[k] for k in keys]):
        yield dict(zip(keys, vals))


def sim_args(sub):
    fam, fn, g, sg = GRIDS[sub]
    keys = list(sg)
    for vals in itertools.product(*[sg[k] for k in keys]):
        yield dict(zip(keys, vals))


def call_gen(sub, ga):
    fn = GRIDS[sub][1]
    kw = dict(ga)
    if "fs" in kw:
        kw["fast"], kw["slow"] = kw.pop("fs")
    return fn(**kw)


def run_gen(job):
    sub, ga = job
    load()
    cd, xf = call_gen(sub, ga)
    rows = []
    for sa in sim_args(sub):
        P = dict(sa, max_stop=MAX_STOP)
        if sa["tgt"] == "sig" and xf is None:
            continue
        T = simulate(cd, P, xf if sa["tgt"] == "sig" else None)
        st = {name: r_stats(T, lo, hi) for name, lo, hi in PERIODS}
        rows.append({"sub": sub, "fam": GRIDS[sub][0], "gen": ga, "sim": sa, "st": st})
    return rows


MAX_STOP = 120.0   # points: above it a retail trader would not take the trade (the LIT size rule sizes to 0 above ~88)


def all_jobs():
    return [(sub, ga) for sub in GRIDS for ga in gen_args(sub)]


def jkey(r):
    g = dict(r["gen"]); s = dict(r["sim"])
    return json.dumps([r["sub"], g, s], sort_keys=True, default=str)


def neighbours(r, rows_by_sub):
    """Variants of the same sub-strategy that differ in exactly one parameter by one step of its grid."""
    fam, fn, g, sg = GRIDS[r["sub"]]
    out = []
    for space, key in ((g, "gen"), (sg, "sim")):
        for p, vals in space.items():
            cur = r[key][p]
            i = vals.index(tuple(cur) if isinstance(cur, list) else cur)
            for jj in (i - 1, i + 1):
                if 0 <= jj < len(vals):
                    alt = {"gen": dict(r["gen"]), "sim": dict(r["sim"])}
                    alt[key][p] = vals[jj]
                    k = json.dumps([r["sub"], alt["gen"], alt["sim"]], sort_keys=True, default=str)
                    if k in rows_by_sub:
                        out.append(rows_by_sub[k])
    return out


def pick(rows, min_n=165):
    """Per sub-strategy: best in-sample (t-stat of R, 2021-11..2024-12, >= min_n trades = 1 a week) and the plateau version (every
    one-step neighbour also positive in-sample; highest median t of itself + neighbours)."""
    by = {jkey(r): r for r in rows}
    picks = {}
    for sub in GRIDS:
        R = [r for r in rows if r["sub"] == sub and r["st"]["2021-24"]["n"] >= min_n]
        if not R:
            continue
        best = max(R, key=lambda r: r["st"]["2021-24"]["t"])
        plat, ps = None, -1e9
        for r in R:
            nb = neighbours(r, by)
            if len(nb) < 3 or r["st"]["2021-24"]["R"] <= 0 or any(x["st"]["2021-24"]["R"] <= 0 for x in nb):
                continue
            sc = float(np.median([r["st"]["2021-24"]["t"]] + [x["st"]["2021-24"]["t"] for x in nb]))
            if sc > ps:
                plat, ps = r, sc
        picks[sub] = {"best": best, "plateau": plat, "plateau_score": ps if plat else None, "n_variants": sum(1 for r in rows if r["sub"] == sub)}
    return picks


def run_all(procs=4):
    t0 = time.time()
    jobs = all_jobs()
    with Pool(procs, initializer=load) as pool:
        rows = []
        for k, rr in enumerate(pool.imap_unordered(run_gen, jobs, chunksize=1)):
            rows += rr
            if k % 20 == 0:
                print(f"  {k + 1}/{len(jobs)} generators, {len(rows)} variants, {time.time() - t0:.0f}s", flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "periods": PERIODS, "max_stop": MAX_STOP, "rows": rows},
              open(os.path.join(OUT, "variants.json"), "w"), separators=(",", ":"), default=str)
    print(len(rows), "variants in", round(time.time() - t0), "s")
    return rows


def rerun(r):
    load()
    cd, xf = call_gen(r["sub"], r["gen"])
    P = dict(r["sim"], max_stop=MAX_STOP)
    return simulate(cd, P, xf if P["tgt"] == "sig" else None)


def full_report(T):
    """Every sizing in $ for every period + eval path + LIT correlation."""
    rep = {"R": {name: r_stats(T, lo, hi) for name, lo, hi in PERIODS}}
    for rule in SIZINGS:
        rep[rule] = {}
        for name, lo, hi in PERIODS:
            s, days = money(T, rule, lo, hi)
            keep = {k: s.get(k) for k in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "avg_r", "stop", "risk", "p10", "f10", "p20", "f20", "pass_med")}
            keep["corr_lit"] = corr_lit(days, lo, hi)
            rep[rule][name] = keep
    ev = eval_path(T)
    rep["eval_path"] = {name: eval_summary(ev, lo, hi) for name, lo, hi in PERIODS}
    return rep


def hindsight(rows, fam, min_n=165):
    """NOT an in-sample pick: the version of a family that is positive in 2021-24, 2025 and 2026 with the highest lowest
    t-stat over the three. Shown to answer 'which versions DID make money', flagged as chosen with hindsight."""
    R = [r for r in rows if r["fam"] == fam and r["st"]["2021-24"]["n"] >= min_n
         and all(r["st"][k]["R"] > 0 for k in ("2021-24", "2025", "2026"))]
    return max(R, key=lambda r: min(r["st"][k]["t"] for k in ("2021-24", "2025", "2026"))) if R else None


def distinct(rows):
    """Variants that differ in their trades (some grid cells give identical trades, e.g. BE at 1R with a 1R target)."""
    return len({(r["sub"], json.dumps(r["st"], sort_keys=True)) for r in rows})


def family_summary(rows):
    out = {}
    for fam in FAMILY_NAME:
        R = [r for r in rows if r["fam"] == fam]
        Rn = [r for r in R if r["st"]["2021-24"]["n"] >= 165]
        pos = lambda k: round(100 * np.mean([r["st"][k]["R"] > 0 for r in Rn]), 1) if Rn else None
        out[fam] = {"variants": len(R), "distinct": distinct(R), "scored": len(Rn), "pos_is": pos("2021-24"), "pos_2025": pos("2025"),
                    "pos_2026": pos("2026"),
                    "pos_all3": sum(all(r["st"][k]["R"] > 0 for k in ("2021-24", "2025", "2026")) for r in Rn)}
    return out


def label(r):
    g, s = r["gen"], r["sim"]
    return f"{r['sub']} " + " ".join(f"{k}={v}" for k, v in g.items()) + " | " + " ".join(f"{k}={v}" for k, v in s.items())


def save_all():
    from tools import runlib as rl
    V = json.load(open(os.path.join(OUT, "variants.json"), encoding="utf-8"))["rows"]
    P = pick(V)
    chosen = []
    for sub, p in P.items():
        for kind in ("best", "plateau"):
            if p[kind]:
                chosen.append((sub, kind, p[kind]))
    for fam in FAMILY_NAME:
        h = hindsight(V, fam)
        if h:
            chosen.append((h["sub"], "hindsight", h))
    picks = []
    d = load()
    for sub, kind, r in chosen:
        T = rerun(r)
        rep = full_report(T)
        rid = f"retail_sa_{GRIDS[sub][0]}_{sub}_{kind}"
        picks.append({"id": rid, "sub": sub, "fam": GRIDS[sub][0], "kind": kind, "gen": r["gen"], "sim": r["sim"], "label": label(r),
                      "report": rep, "trade_cols": ["day", "entry_t", "exit_t", "dir", "risk_pts", "pts", "mae_pts", "exit", "r"],
                      "trades": [[d["days"][t[0]], int(d["t"][t[1]]), int(d["t"][t[2]] + 300), t[3], round(t[4], 2), round(t[5], 2),
                                  round(t[6], 2), t[7], round(r_of(t), 3)] for t in T]})
        # stored run: LIT size rule ($800 up to 20 pts) so it compares with LIT runs; other sizings in params
        TT = sized(T, "lit")
        S = rl.score(TT, sessions())
        for name, lo, hi in PERIODS:
            TP = [t for t in TT if lo <= t["day"] <= hi]
            DP = [x for x in S["days"] if lo <= x["date"] <= hi]
            S["spans"][name] = rl._compact(TP, DP) if TP else {"n": 0}
        a = rep["R"]
        status = "promising" if all(a[k]["R"] > 0 for k in ("2021-24", "2025", "2026")) else "rejected"
        verdict = (f"{kind} ({'in-sample pick' if kind != 'hindsight' else 'picked with hindsight'}): R 2021-24 {a['2021-24']['R']:+} / "
                   f"2025 {a['2025']['R']:+} / 2026 {a['2026']['R']:+}; $ at the LIT size 2021-24 {rep['lit']['2021-24']['net']:+,} / "
                   f"2025 {rep['lit']['2025']['net']:+,} / 2026 {rep['lit']['2026']['net']:+,}")
        rl.save(rid, f"Retail standalone: {label(r)}", "other", "Does this retail strategy make money on its own on NQ?",
                params={"sub": sub, "gen": r["gen"], "sim": r["sim"], "max_stop": MAX_STOP, "sizings": {k: rep[k] for k in SIZINGS},
                        "eval_path": rep["eval_path"], "R": rep["R"]},
                sizing={"rule": "lit ($800 up to a 20-pt stop, then 800x20/stop, max 40 micros)", "commission": COMM, "slip_ticks": 1},
                trades=TT, scored=S, status=status, verdict=verdict, notes="tools/retail_standalone.py; research/retail/picks.json",
                writeup="retail-standalone", tags=["retail_standalone", GRIDS[sub][0], kind])
        print(rid, verdict, flush=True)
    json.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "families": family_summary(V), "picks": picks},
              open(os.path.join(OUT, "picks.json"), "w"), separators=(",", ":"), default=str)


def cap_sens(pk, caps=(60, 80, 120, 200, 400)):
    """R per period of one stored pick under other max-stop caps (skip above the cap)."""
    load()
    cd, xf = call_gen(pk["sub"], pk["gen"])
    out = {}
    for cap in caps:
        T = simulate(cd, dict(pk["sim"], max_stop=float(cap)), xf if pk["sim"]["tgt"] == "sig" else None)
        out[cap] = {name: r_stats(T, lo, hi) for name, lo, hi in PERIODS}
    return out


def tables():
    """Markdown tables for research/writeups/retail-standalone.md."""
    PK = json.load(open(os.path.join(OUT, "picks.json"), encoding="utf-8"))
    fs = PK["families"]
    f = lambda v: "-" if v is None else (f"{v:+,.0f}" if isinstance(v, (int, float)) else str(v))
    for fam, nm in FAMILY_NAME.items():
        x = fs[fam]
        print(f"\n### {nm}: {x['variants']} variants ({x['distinct']} with different trades); in-sample positive {x['pos_is']}%, "
              f"2025 {x['pos_2025']}%, 2026 {x['pos_2026']}%; positive in all three: {x['pos_all3']}\n")
        print("| version | pick | R 21-24 / 25 / 26 | $ 21-24 | $ 2025 | $ 2026 (H1 / H2) | $/mo 2026 | PF 21-24 / 25 / 26 | tr/wk | max DD | eval 2wk 2026 | corr LIT |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for p in PK["picks"]:
            if p["fam"] != fam:
                continue
            R, U = p["report"]["R"], p["report"]["usd500"]
            dd = min(U[k]["dd"] or 0 for k in ("2021-24", "2025", "2026"))
            print(f"| {p['label'].replace(' | ', '; ')} | {p['kind']} | {R['2021-24']['R']:+.0f} / {R['2025']['R']:+.0f} / {R['2026']['R']:+.0f} | "
                  f"{f(U['2021-24']['net'])} | {f(U['2025']['net'])} | {f(U['2026']['net'])} ({f(U['2026H1']['net'])} / {f(U['2026H2']['net'])}) | "
                  f"{f(U['2026']['per_month'])} | {U['2021-24']['pf']} / {U['2025']['pf']} / {U['2026']['pf']} | {R['2021-24']['tpw']} / {R['2026']['tpw']} | "
                  f"{f(dd)} | {U['2026'].get('p10')}/{U['2026'].get('f10')} | {U['2026']['corr_lit']} |")


def detail(pid):
    """Per-period table (usd500 sizing) and the sizing comparison of one stored pick."""
    PK = json.load(open(os.path.join(OUT, "picks.json"), encoding="utf-8"))
    p = next(x for x in PK["picks"] if x["id"] == pid)
    rep = p["report"]
    f = lambda v: "-" if v is None else f"{v:+,.0f}"
    print(f"\n**{p['label']}** (`{pid}`), sized at $500 risk a trade\n")
    print("| period | trades | tr/wk | win % | PF | net $ | $/month | max DD | avg R | eval 2 wk pass/fail | eval 1 mo pass/fail | corr LIT |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, lo, hi in PERIODS:
        u = rep["usd500"][name]
        print(f"| {name} | {u['n']} | {u['tpw']} | {u['win']} | {u['pf']} | {f(u['net'])} | {f(u['per_month'])} | {f(u['dd'])} | {u['avg_r']} | "
              f"{u.get('p10')}/{u.get('f10')} | {u.get('p20')}/{u.get('f20')} | {u['corr_lit']} |")
    print("\n| sizing | $ 2021-24 | $ 2025 | $ 2026 | max DD 2026 | eval 2 wk 2026 pass/fail | eval 1 mo 2026 pass/fail |")
    print("|---|---|---|---|---|---|---|")
    names = {"lit": "LIT rule ($800 to 20 pts)", "usd500": "$500 risk", "usd300": "$300 risk", "fix2": "2 micros", "fix5": "5 micros", "fix10": "10 micros"}
    for rule in SIZINGS:
        u = rep[rule]
        print(f"| {names[rule]} | {f(u['2021-24']['net'])} | {f(u['2025']['net'])} | {f(u['2026']['net'])} | {f(u['2026']['dd'])} | "
              f"{u['2026'].get('p10')}/{u['2026'].get('f10')} | {u['2026'].get('p20')}/{u['2026'].get('f20')} |")
    e = rep["eval_path"]
    print(f"| eval path (LIT rule, capped at 60% of the room) | - | - | - | - | {e['2026']['p10']}/{e['2026']['f10']} | {e['2026']['p20']}/{e['2026']['f20']} |")
    print(f"\nEval path in 2021-24: {e['2021-24']['p10']}/{e['2021-24']['f10']} in 2 weeks, {e['2021-24']['p20']}/{e['2021-24']['f20']} in a month; "
          f"2025: {e['2025']['p10']}/{e['2025']['f10']}, {e['2025']['p20']}/{e['2025']['f20']}.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        rows = run_all()
        P = pick(rows)
        for sub, p in P.items():
            for kind in ("best", "plateau"):
                r = p[kind]
                if r:
                    print(sub, kind, r["gen"], r["sim"], {k: (v["n"], v["R"], v["pf"], v["t"]) for k, v in r["st"].items()})
    elif cmd == "save":
        save_all()
    elif cmd == "tables":
        tables()
    elif cmd == "detail":
        for pid in sys.argv[2:]:
            detail(pid)
