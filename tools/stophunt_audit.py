"""STOP-HUNT AUDIT (2026-10-23): an adversarial check of the two stop-hunt leads in research/writeups/stophunt.md
(sh_asia_resweep, sh_trend_idm5) before the owner trusts them. Research / paper only.

INDEPENDENT re-implementation: this file does NOT import engine/stophunt.py or tools/stophunt.py for the strategy itself.
It rebuilds pools, hunts, signals, fills and the trade walk from the plain-language rules in research/stophunt/sh_*.json
(plus the hidden details the plain rules leave out, listed in HIDDEN and in the write-up) on the raw data/NQ_5m.csv and
data/NQ_1m.csv. The researcher's code is only used where the check is ABOUT that code (the selection re-run in check 5, the
eval executors in check 7).

    python -X utf8 tools/stophunt_audit.py replicate   # check 1: my trades vs the stored picks
    python -X utf8 tools/stophunt_audit.py all         # every check -> research/stophunt/audit.json
    python -X utf8 tools/stophunt_audit.py <check>     # replicate | lookahead | costs | robust | oos | multi | evals

Write-up: research/writeups/stophunt-audit.md.
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

try:
    from numba import njit
except Exception:                                     # pragma: no cover
    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT =os.path.join(ROOT, "research", "stophunt")
TICK, PV, COMM = 0.25, 2.0, 1.90
RISK_USD, MAXQ = 500.0, 50
M1_FROM = 1767308400                                  # 2026-01-01 18:00 ET: the first full 1m session
SPANS = (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"), ("2025", "2025-01-01", "2025-12-31"),
         ("2021-24", "2021-11-01", "2024-12-31"))

# Details the plain-language rules do not state, read from the researcher's docstrings (needed to compare like for like).
HIDDEN = [
    "Pool lifetimes: 15m swings 576 5m bars (2 days), 1h swings 1440 (5 days), 15m equal highs/lows 576, Asia/London/prior NY 432, "
    "overnight 288, prior day 576, prior week 1500, 5m swings 288. A pool not taken within its life is dropped.",
    "Swing highs/lows are fractals with N = 2, 3, 4 and 5 bars each side (all four count; strictly above the left N, >= the right N).",
    "Equal highs/lows: two 15m N=2 swings within max(1 pt, 0.1 ATR) and 2 days, nothing between them beyond the pair by more than that.",
    "The ATR for every threshold is ATR(14, Wilder) of the 5m bar BEFORE the hunt bar, fixed for the whole setup.",
    "'Within 3 hours' = 36 5m bars counted from the hunt bar itself; the setup also ends at the session end or 15:30.",
    "Resweep (Asia): either a bar trading under the pool after an earlier close back inside it, or a new extreme after a 0.5 ATR "
    "bounce at least 2 bars after the previous extreme; it must happen on a bar before the trigger bar.",
    "Market structure shift: the close beats the LATEST 5m swing (N=2) the other way that is confirmed before the trigger bar "
    "and formed no earlier than 48 bars before the hunt; older swings do not count.",
    "Inducement (trend): a 5m N=2 swing on the pool's side, between the pool and 1 ATR beyond it, formed in the 36 bars before the "
    "hunt and confirmed before it.",
    "When two hunts give a signal on the same bar and side, the most obvious pool's hunt is used (score), then the latest hunt.",
    "1h trend = sign(close of the last CLOSED clock-hour bar - EMA 50 of 1h closes); 1h bars are cut at the 18:00 session start.",
    "2026 trades are filled and walked on 1m bars from the 5m signal close; before 2026 on 5m bars (no 1m data).",
    "Limit at mid-candle: floor to the tick in trade direction; filled only when price trades 1 tick through within 30 minutes "
    "(30 1m bars / 6 5m bars), at the limit or a better open; no target and no BE on the fill bar.",
    "Stops 6-80 pts; size floor(500 / (stop x $2)), max 50 micros; the 'max 1 / 2 a session' counts filled trades; a signal while "
    "a trade is open is skipped; sessions are 18:00-17:00 ET and a trade is flat at the 15:55 close.",
    "Windows are judged on the 5m signal bar's open time (Asia = signal bar opening 18:00-01:55 ET).",
]


# ================================================================================================ data
def _et_parts(t):
    et = pd.to_datetime(t, unit="s", utc=True).tz_convert("America/New_York")
    mod = (et.hour * 60 + et.minute).values.astype(np.int64)
    naive = et.tz_localize(None)
    sday = (naive.normalize() + pd.to_timedelta((mod >= 1080).astype(int), unit="D")).strftime("%Y-%m-%d").values
    loc = naive.values.astype("datetime64[s]").astype(np.int64)
    return mod, sday, loc


_D = {}


def data():
    """5m and 1m bars with ET minute, session day (18:00 ET start), session id, minutes since 18:00, ATR(14)."""
    if _D:
        return _D
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    t = d5["time"].values.astype(np.int64)
    mod, sday, loc = _et_parts(t)
    days, sid = np.unique(sday, return_inverse=True)
    o, h, l, c = (d5[k].values.astype(float) for k in ("open", "high", "low", "close"))
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - prev), np.abs(l - prev)])
    atr = np.empty(len(tr)); a = tr[0]
    for i, x in enumerate(tr):                       # Wilder: a += (x - a) / 14
        a = x if i == 0 else a + (x - a) / 14.0
        atr[i] = a
    rel = (mod - 1080) % 1440
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    t1 = d1["time"].values.astype(np.int64)
    mod1, sday1, _ = _et_parts(t1)
    dix = {x: i for i, x in enumerate(days)}
    sid1 = np.array([dix.get(x, -1) for x in sday1], np.int64)
    _D.update(t=t, o=o, h=h, l=l, c=c, mod=mod, rel=rel.astype(np.int64), sid=sid.astype(np.int64), days=days, loc=loc, atr=atr,
              n=len(t), t1=t1, o1=d1["open"].values.astype(float), h1=d1["high"].values.astype(float),
              l1=d1["low"].values.astype(float), c1=d1["close"].values.astype(float), rel1=((mod1 - 1080) % 1440).astype(np.int64),
              sid1=sid1, m1_to=int(t1[-1]))
    _D["flat5"] = _flat(_D["sid"], _D["rel"], 1310)        # the 5m bar 15:50-15:55
    _D["flat1"] = _flat(sid1, _D["rel1"], 1314)            # the 1m bar 15:54-15:55
    return _D


def _flat(sid, rel, fr):
    """Per bar: the last bar of its session that closes by 15:55 (or -1 if the bar is after it)."""
    n = len(sid); out = np.full(n, -1, np.int64)
    s_end = np.r_[np.nonzero(np.diff(sid))[0], n - 1]
    s_beg = np.r_[0, s_end[:-1] + 1]
    for a, b in zip(s_beg, s_end):
        ok = np.nonzero(rel[a:b + 1] <= fr)[0]
        if len(ok):
            last = a + ok[-1]
            out[a:last + 1] = last
    return out


def resample(D, minutes):
    """Clock-aligned bars of `minutes` inside each session; returns high, low, close, and the 5m index of each bar's last bar."""
    key = D["loc"] // (minutes * 60)
    new = np.r_[True, (key[1:] != key[:-1]) | (D["sid"][1:] != D["sid"][:-1])]
    first = np.nonzero(new)[0]
    last = np.r_[first[1:] - 1, D["n"] - 1]
    return dict(h=np.maximum.reduceat(D["h"], first), l=np.minimum.reduceat(D["l"], first), c=D["c"][last], last=last)


def fractal_idx(h, l, N):
    """Swing highs / lows with N bars each side (strictly above the N before, at least as high as the N after)."""
    m = len(h)
    hi, lo = [], []
    if m < 2 * N + 1:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    from numpy.lib.stride_tricks import sliding_window_view as win
    H = win(h, 2 * N + 1); L = win(l, 2 * N + 1)
    cH, cL = H[:, N], L[:, N]
    okH = (cH > H[:, :N].max(1)) & (cH >= H[:, N + 1:].max(1))
    okL = (cL < L[:, :N].min(1)) & (cL <= L[:, N + 1:].min(1))
    return np.nonzero(okH)[0] + N, np.nonzero(okL)[0] + N


# ================================================================================================ pools
SCORE = {"f5": 1.0, "f15": 2.0, "f60": 3.0, "eq15": 3.0, "asia": 3.0, "lon": 3.0, "ny": 3.5, "on": 3.5, "pd": 3.5, "pw": 4.0}
LIFE = {"f5": 288, "f15": 576, "f60": 1440, "eq15": 576, "asia": 432, "lon": 432, "ny": 432, "on": 288, "pd": 576, "pw": 1500}


@njit(cache=True)
def _eq(fb, fp, fk, side, h, l, atr, look):
    m = len(fb)
    px = np.empty(m); kn = np.empty(m, np.int64); tc = np.empty(m, np.int64); k = 0
    for i in range(m):
        b = fb[i]; tol = max(1.0, 0.1 * atr[b]); touches = 1; outer = fp[i]
        j = i - 1
        while j >= 0 and fb[j] >= b - look:
            if abs(fp[j] - fp[i]) <= tol:
                ref = max(fp[j], fp[i]) if side > 0 else min(fp[j], fp[i])
                broke = False
                for q in range(fb[j] + 1, b):
                    if side > 0 and h[q] > ref + tol:
                        broke = True; break
                    if side < 0 and l[q] < ref - tol:
                        broke = True; break
                if not broke:
                    touches += 1
                    outer = max(outer, fp[j]) if side > 0 else min(outer, fp[j])
            j -= 1
        if touches >= 2:
            px[k] = outer; kn[k] = fk[i]; tc[k] = touches; k += 1
    return px[:k], kn[:k], tc[:k]


@njit(cache=True)
def _first_take(px, side, known, life, h, l):
    """First 5m bar after the pool is known (within its life) that trades 1 tick through it; -1 if none."""
    m = len(px); n = len(h); out = np.full(m, -1, np.int64)
    for i in range(m):
        k1 = min(known[i] + life[i], n - 1)
        for k in range(known[i] + 1, k1 + 1):
            if (side[i] > 0 and h[k] >= px[i] + 0.25) or (side[i] < 0 and l[k] <= px[i] - 0.25):
                out[i] = k
                break
    return out


def pools(D, types, life_mult=1.0, Ns=(2, 3, 4, 5)):
    """Every pool of the given types: price, side (+1 highs = buy stops above, -1 lows), bar it is known at, life, score, type."""
    rows = collections.defaultdict(list)

    def add(px, side, kn, typ, sc):
        px = np.atleast_1d(np.asarray(px, float)); kn = np.atleast_1d(np.asarray(kn, np.int64))
        rows["px"].append(px); rows["side"].append(np.full(len(px), side)); rows["kn"].append(kn)
        rows["life"].append(np.full(len(px), int(round(LIFE[typ] * life_mult)))); rows["sc"].append(np.broadcast_to(np.asarray(sc, float), px.shape).copy())
        rows["typ"].append(np.full(len(px), typ, dtype=object))

    h, l, n = D["h"], D["l"], D["n"]
    for typ, mins in (("f5", 5), ("f15", 15), ("f60", 60)):
        if typ not in types and not (typ == "f15" and "eq15" in types):
            continue
        R = resample(D, mins) if mins > 5 else dict(h=h, l=l, last=np.arange(n))
        for N in Ns:
            fh, fl = fractal_idx(R["h"], R["l"], N)
            for side, ff, arr in ((1, fh, R["h"]), (-1, fl, R["l"])):
                ff = ff[ff + N < len(R["last"])]
                kn = R["last"][ff + N]
                if typ in types:
                    add(arr[ff], side, kn, typ, SCORE[typ] + 0.25 * (N - 2))
                if typ == "f15" and N == 2 and "eq15" in types:
                    fb = R["last"][ff]
                    o = np.argsort(fb, kind="stable")
                    ep, ek, et = _eq(fb[o].astype(np.int64), arr[ff][o].astype(float), kn[o].astype(np.int64), side, h, l, D["atr"], 576)
                    add(ep, side, ek, "eq15", SCORE["eq15"] + 0.5 * (et - 2))
    sess_types = [x for x in ("asia", "lon", "ny", "on", "pd", "pw") if x in types]
    if sess_types:
        sid, rel, mod = D["sid"], D["rel"], D["mod"]
        ends = np.r_[np.nonzero(np.diff(sid))[0], n - 1]; begs = np.r_[0, ends[:-1] + 1]
        week = {}
        for a, b in zip(begs, ends + 1):
            rr, mm = rel[a:b], mod[a:b]
            parts = {"asia": rr < 480, "lon": (rr >= 480) & (rr < 840), "ny": (mm >= 570) & (mm < 960) & (rr < 1320), "on": rr < 930}
            for nm, msk in parts.items():
                if nm not in types:
                    continue
                ii = a + np.nonzero(msk)[0]
                if len(ii) < 6:
                    continue
                add(h[ii].max(), 1, ii[-1], nm, SCORE[nm]); add(l[ii].min(), -1, ii[-1], nm, SCORE[nm])
            if "pd" in types:
                add(h[a:b].max(), 1, b - 1, "pd", SCORE["pd"]); add(l[a:b].min(), -1, b - 1, "pd", SCORE["pd"])
            y, w, _ = dt.date.fromisoformat(str(D["days"][sid[a]])).isocalendar()
            W = week.setdefault((y, w), [-1e18, 1e18, 0])
            W[0] = max(W[0], h[a:b].max()); W[1] = min(W[1], l[a:b].min()); W[2] = b - 1
        if "pw" in types:
            for (y, w), (hi, lo, kn) in week.items():
                add(hi, 1, kn, "pw", SCORE["pw"]); add(lo, -1, kn, "pw", SCORE["pw"])
    P = {k: np.concatenate(v) for k, v in rows.items()}
    P["take"] = _first_take(P["px"], P["side"].astype(np.int64), P["kn"], P["life"].astype(np.int64), h, l)
    return P


def hunts(P):
    """Hunt events: per (bar, side) the pools of the set taken by that bar; p = the outermost one, score = the most obvious."""
    ok = P["take"] >= 0
    df = pd.DataFrame({"j": P["take"][ok], "side": P["side"][ok], "px": P["px"][ok], "sc": P["sc"][ok]})
    g = df.groupby(["j", "side"])
    hi = g.agg(pmax=("px", "max"), pmin=("px", "min"), sc=("sc", "max")).reset_index()
    p = np.where(hi["side"].values > 0, hi["pmax"].values, hi["pmin"].values)
    return dict(j=hi["j"].values.astype(np.int64), side=hi["side"].values.astype(np.int64), p=p, sc=hi["sc"].values)


# ================================================================================================ signals
@njit(cache=True)
def _setups(ej, es, ep, esc, o, h, l, c, atr, rel, sid, swh, swl, W, mode, kb, depth, bounce_k, mss_look, pre_look, pre_atr,
            cut_rel, atr_at_trigger):
    """mode 0 = no extra condition, 1 = resweep first (pool re-run after a close back inside, or a new extreme after a bounce),
    2 = inducement before the hunt (a 5m swing between the pool and pre_atr x ATR beyond it, formed in the pre_look bars before)."""
    m = len(ej); n = len(o)
    S = np.empty(m, np.int64); DR = np.empty(m, np.int64); X = np.empty(m); PP = np.empty(m); MID = np.empty(m)
    SC = np.empty(m); JJ = np.empty(m, np.int64); k = 0
    for e in range(m):
        j = ej[e]
        if j < 2 or j >= n:
            continue
        d = -es[e]                                     # highs taken -> short (-1); lows taken -> long (+1)
        s = sid[j]
        A0 = atr[j - 1]
        p = d * ep[e]
        if mode == 2:
            sw = swl if d > 0 else swh
            found = False
            for f in sw:
                if f < j - pre_look:
                    continue
                if f + 2 > j - 1:
                    break
                fp = l[f] if d > 0 else -h[f]
                if p < fp and fp <= p + pre_atr * A0:
                    found = True
                    break
            if not found:
                continue
        ext = 1e18; arg = j; bnc = -1e18; back_inside = False; rs = -1
        for q in range(j, min(j + W + 1, n)):
            if sid[q] != s or rel[q] > cut_rel:
                break
            if d > 0:
                oq = o[q]; hq = h[q]; lq = l[q]; cq = c[q]
            else:
                oq = -o[q]; hq = -l[q]; lq = -h[q]; cq = -c[q]
            A = atr[q - 1] if atr_at_trigger else A0
            if q > j and rs < 0:
                if back_inside and lq < p:
                    rs = q
                elif lq < ext and bnc - ext >= bounce_k * A0 and q - arg >= 2:
                    rs = q
            if lq < ext:
                ext = lq; arg = q; bnc = hq
            else:
                bnc = max(bnc, hq)
            gate = True
            if mode == 1:
                gate = rs >= 0 and rs < q
            body = cq - oq
            if gate and cq > p and body > 0 and body >= kb * A and (p - ext) >= depth * A0:
                # market structure shift: beyond the latest swing the other way confirmed before this bar
                G = swh if d > 0 else swl
                z = np.searchsorted(G, q - 2) - 1
                if z >= 0 and G[z] >= j - mss_look:
                    lvl = h[G[z]] if d > 0 else -l[G[z]]
                    if cq > lvl:
                        S[k] = q; DR[k] = d; X[k] = ext; PP[k] = p
                        MID[k] = math.floor((oq + 0.5 * body) / 0.25) * 0.25
                        SC[k] = esc[e]; JJ[k] = j; k += 1
                        break
            if cq > p:
                back_inside = True
    return S[:k], DR[:k], X[:k], PP[:k], MID[:k], SC[:k], JJ[:k]


def signals(D, ev, cfg):
    swh, swl = D["sw2"]
    S, DR, X, PP, MID, SC, JJ = _setups(ev["j"], ev["side"], ev["p"], ev["sc"], D["o"], D["h"], D["l"], D["c"], D["atr"], D["rel"],
                                        D["sid"], swh, swl, cfg["W"], cfg["mode"], cfg["body"], cfg["depth"], cfg["bounce"],
                                        cfg["mss_look"], cfg["pre_look"], cfg["pre_atr"], 1290, cfg.get("atr_trig", False))
    df = pd.DataFrame({"sig": S, "dr": DR, "ext": X, "p": PP, "mid": MID, "sc": SC, "j": JJ})
    df = df.sort_values(["sig", "dr", "sc", "j"], ascending=[True, True, False, False]).drop_duplicates(["sig", "dr"])
    return df.sort_values("sig", kind="stable").reset_index(drop=True)


def trend_1h(D, span=50):
    if ("trend", span) in D:
        return D[("trend", span)]
    R = resample(D, 60)
    c = R["c"]; a = 2.0 / (span + 1); ema = np.empty(len(c)); e = c[0]
    for i, x in enumerate(c):
        e = x if i == 0 else a * x + (1 - a) * e
        ema[i] = e
    v = np.full(D["n"], np.nan); v[R["last"]] = np.sign(c - ema)
    tr = pd.Series(v).ffill().fillna(0.0).values
    D[("trend", span)] = tr
    return tr


# ================================================================================================ fills + walk
@njit(cache=True)
def _fill_one(o, h, l, rel, sid, k0, s, d, kind, lim, maxbars, cut_rel, thru):
    n = len(o)
    if k0 >= n or sid[k0] != s or rel[k0] > cut_rel:
        return -1, 0.0
    if kind == 0:
        return k0, (o[k0] if d > 0 else -o[k0]) + 0.25
    for k in range(k0, min(k0 + maxbars, n)):
        if sid[k] != s or rel[k] > cut_rel:
            return -1, 0.0
        od = o[k] if d > 0 else -o[k]
        ld = l[k] if d > 0 else -h[k]
        if ld <= lim - thru:
            return k, min(od, lim)
    return -1, 0.0


@njit(cache=True)
def _walk_one(o, h, l, c, k0, kf, d, e, sp, risk, T, be_at, be_off, is_lim, slip_x, tgt_thru, be_pess):
    """Stop first when stop and target share a bar; no target / BE on a limit's fill bar; stop / flat exits pay 1 tick + slip_x.
    be_pess: on the bar that moves the stop to BE, assume the low came after the high (exit at BE if the bar went back there)."""
    cur = sp; moved = False
    for k in range(k0, kf + 1):
        if d > 0:
            ok_ = o[k]; hk = h[k]; lk = l[k]
        else:
            ok_ = -o[k]; hk = -l[k]; lk = -h[k]
        if lk <= cur:
            px = (min(ok_, cur) if (k > k0 or not is_lim) else cur) - 0.25 - slip_x
            return px - e, k, (1 if moved else 0)
        if is_lim and k == k0:
            continue
        if hk >= T + tgt_thru:
            px = max(ok_, T) if k > k0 else T
            return px - e, k, 2
        if be_at > 0 and not moved and hk >= e + be_at * risk:
            cur = e + be_off; moved = True
            if be_pess and lk <= cur:
                return cur - 0.25 - slip_x - e, k, 1
    ck = c[kf] if d > 0 else -c[kf]
    return ck - 0.25 - slip_x - e, kf, 3


EXITS = ("STOP", "BE", "TARGET", "FLAT")


def trades(D, sg, cfg, cost=None):
    """Fill and walk every signal, then apply the one-position / max-per-session / hours rules. Returns rows like the stored
    picks (day, entry_t, exit_t, dir, entry, stop, target, exit, exit_kind, qty, pnl_usd, risk_pts, ...)."""
    cost = cost or {}
    xslip = cost.get("slip_ticks", 0) * 0.25
    night = cost.get("night_ticks", 0) * 0.25
    thru = 0.25 + cost.get("limit_thru_extra", 0) * 0.25
    tthru = cost.get("tgt_thru", 0) * 0.25
    bep = bool(cost.get("be_pess", False))
    force5 = bool(cost.get("force_5m", False))
    late = int(cost.get("late_min", 0))              # the order goes in this many minutes after the signal close
    trend = trend_1h(D, cfg.get("ema", 50)) if cfg.get("trend") else None
    kind = 0 if cfg["entry"] == "mkt" else 1
    rows = []
    for r in sg.itertuples(index=False):
        s5 = int(r.sig); d = int(r.dr); s = int(D["sid"][s5])
        if trend is not None and not (trend[s5] * d > 0):
            continue
        b = int(np.searchsorted(np.array(cfg["win_edges"]), D["rel"][s5], side="right"))
        if not cfg["win_ok"][b]:
            continue
        tsig = int(D["t"][s5]) + 300
        lim = 0.0
        if kind == 1 and cfg.get("mid_frac", 0.5) != 0.5:
            o_, c_ = (D["o"][s5], D["c"][s5]) if d > 0 else (-D["o"][s5], -D["c"][s5])
            lim = math.floor((o_ + cfg["mid_frac"] * (c_ - o_)) / 0.25) * 0.25
        elif kind == 1:
            lim = r.mid
        stop_d = r.ext - 0.25
        if (not force5) and M1_FROM <= tsig < D["m1_to"]:
            k1 = int(np.searchsorted(D["t1"], tsig))
            if k1 >= len(D["t1"]):
                continue
            k0, e = _fill_one(D["o1"], D["h1"], D["l1"], D["rel1"], D["sid1"], k1 + late, s, d, kind, lim, cfg["lim_bars1"] - late, 1290, thru)
            path = 1
        else:
            k0, e = _fill_one(D["o"], D["h"], D["l"], D["rel"], D["sid"], s5 + 1 + late // 5, s, d, kind, lim, cfg["lim_bars5"] - late // 5, 1290, thru)
            path = 0
        if k0 < 0:
            continue
        if path == 1:
            o, h, l, c, t, fl, rl, secs = D["o1"], D["h1"], D["l1"], D["c1"], D["t1"], D["flat1"], D["rel1"], 60
        else:
            o, h, l, c, t, fl, rl, secs = D["o"], D["h"], D["l"], D["c"], D["t"], D["flat5"], D["rel"], 300
        # extra entry slippage: the order was planned (risk, size, target) at the expected fill; the worse fill only costs points
        e_slip = (xslip + (night if rl[k0] < 480 else 0.0)) if kind == 0 else 0.0
        risk = e - stop_d
        kf = int(fl[k0])
        if risk < cfg["min_stop"] or risk > cfg["max_stop"] or kf < 0:
            continue
        T = e + cfg["rr"] * risk
        be_at, be_off = cfg["be"]
        pts, kx, ek = _walk_one(o, h, l, c, k0, kf, d, e, stop_d, risk, T, be_at, be_off, kind == 1, xslip, tthru, bep)
        if night and rl[kx] < 480 and ek != 2:
            pts -= night
        pts -= e_slip
        qty = int(min(MAXQ, math.floor(RISK_USD / (risk * PV))))
        rows.append({"day": str(D["days"][s]), "sid": s, "entry_t": int(t[k0]), "exit_t": int(t[kx]) + secs, "dir": d,
                     "entry": round(d * e, 2), "stop": round(d * stop_d, 2), "target": round(d * T, 2),
                     "exit": round(d * (e + pts), 2), "exit_kind": EXITS[ek], "qty": qty, "pnl_usd": round(qty * (pts * PV - COMM), 2),
                     "r": qty * (pts * PV - COMM) / (risk * PV * qty), "risk_pts": round(risk, 2), "signal_t": tsig,
                     "hunt_t": int(D["t"][r.j]), "pool_px": round(d * r.p, 2), "path": "1m" if path else "5m",
                     "rel_sig": int(D["rel"][s5])})
    rows.sort(key=lambda x: x["entry_t"])
    out, busy, cnt = [], -1, collections.Counter()
    for x in rows:
        if x["entry_t"] < busy or cnt[x["sid"]] >= cfg["mp"]:
            continue
        cnt[x["sid"]] += 1; busy = x["exit_t"]
        out.append(x)
    return [x for x in out if x["day"] >= "2021-11-01"]


# ================================================================================================ the two leads
ASIA = dict(name="sh_asia_resweep", types=("f15", "f60", "eq15", "asia", "lon", "ny", "on", "pd", "pw"), mode=1, W=36, body=1.2,
            depth=0.5, bounce=0.5, mss_look=48, pre_look=36, pre_atr=1.0, entry="mkt", min_stop=6.0, max_stop=80.0,
            rr=2.0, be=(1.0, 1.25), mp=1, trend=False, win_edges=[240, 480, 840, 1080], win_ok=[1, 1, 0, 0, 0],
            lim_bars1=30, lim_bars5=6, life=1.0, Ns=(2, 3, 4, 5))
TREND = dict(name="sh_trend_idm5", types=("f5",), mode=2, W=6, body=1.2, depth=0.25, bounce=0.5, mss_look=48, pre_look=36,
             pre_atr=1.0, entry="mid", min_stop=6.0, max_stop=80.0, rr=2.0, be=(1.0, 1.25), mp=2, trend=True, ema=50,
             win_edges=[240, 480, 840, 1080], win_ok=[1, 1, 1, 1, 1], lim_bars1=30, lim_bars5=6, life=1.0, Ns=(2, 3, 4, 5))
LEADS = {"asia": ASIA, "trend": TREND}
_EV = {}


def run(cfg, cost=None, D=None):
    D = D or data()
    if "sw2" not in D:
        D["sw2"] = tuple(x.astype(np.int64) for x in fractal_idx(D["h"], D["l"], 2))
    key = (tuple(cfg["types"]), cfg["life"], tuple(cfg["Ns"]), id(D))
    if key not in _EV:
        _EV[key] = hunts(pools(D, cfg["types"], cfg["life"], cfg["Ns"]))
    sg = signals(D, _EV[key], cfg)
    return trades(D, sg, cfg, cost)


# ================================================================================================ scoring
def span_of(day):
    for nm, a, z in SPANS:
        if a <= day <= z:
            return nm
    return None


def nsess(D):
    return {nm: int(((D["days"] >= a) & (D["days"] <= z)).sum()) for nm, a, z in SPANS}


def score(rows, D=None, by=SPANS):
    D = D or data()
    ns = nsess(D)
    out = {}
    for nm, a, z in by:
        p = np.array([r["pnl_usd"] for r in rows if a <= r["day"] <= z])
        R = np.array([r["r"] for r in rows if a <= r["day"] <= z])
        if not len(p):
            out[nm] = {"n": 0, "net": 0}
            continue
        eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
        gl = -p[p <= 0].sum()
        sess = ns.get(nm) or max(1, int(((D["days"] >= a) & (D["days"] <= z)).sum()))
        out[nm] = {"n": int(len(p)), "tpw": round(len(p) / (sess / 5), 2), "win": round(100 * float((p > 0).mean()), 1),
                   "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else None, "net": int(round(p.sum())),
                   "per_month": int(round(p.sum() / (sess / 21))), "dd": int(round(dd)),
                   "t": round(float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))), 2) if len(R) > 2 and R.std() > 0 else None}
    return out


def nets(rows):
    return {k: v["net"] for k, v in score(rows).items()}


def stored(name):
    return json.load(open(os.path.join(OUT, name + ".json"), encoding="utf-8"))


# ================================================================================================ check 1: replicate
def _key(r):
    return (r["entry_t"], r["dir"])


def compare(mine, ref):
    """Trade-by-trade comparison on (entry time, side); then entry / stop / exit / exit kind / pnl of the matched ones."""
    A = {_key(r): r for r in mine}; B = {_key(r): r for r in ref}
    both = sorted(set(A) & set(B))
    only_m = sorted(set(A) - set(B)); only_r = sorted(set(B) - set(A))
    diff = collections.Counter(); ex = []
    for k in both:
        a, b = A[k], B[k]
        for f in ("entry", "stop", "target", "exit", "exit_kind", "qty", "pnl_usd"):
            same = (a[f] == b[f]) if isinstance(a[f], str) else abs(float(a[f]) - float(b[f])) < 0.011
            if not same:
                diff[f] += 1
                if len(ex) < 8:
                    ex.append({"day": a["day"], "field": f, "mine": a[f], "stored": b[f]})
    return {"mine": len(mine), "stored": len(ref), "matched": len(both), "only_mine": len(only_m), "only_stored": len(only_r),
            "field_diffs": dict(diff), "examples": ex, "only_mine_ex": [A[k]["day"] for k in only_m[:10]],
            "only_stored_ex": [B[k]["day"] for k in only_r[:10]],
            "identical_all_fields": sum(1 for k in both if all(
                (A[k][f] == B[k][f]) if isinstance(A[k][f], str) else abs(float(A[k][f]) - float(B[k][f])) < 0.011
                for f in ("entry", "stop", "target", "exit", "exit_kind", "qty", "pnl_usd")))}


def cmd_replicate():
    res = {}
    for nm, cfg in LEADS.items():
        t0 = time.time()
        mine = run(cfg)
        ref = stored(cfg["name"])["trades"]
        c = compare(mine, ref)
        c["nets_mine"] = nets(mine); c["nets_stored"] = nets(ref)
        c["secs"] = round(time.time() - t0, 1)
        res[nm] = c
        print(nm, json.dumps(c, default=str)[:1500], flush=True)
    return res


# ================================================================================================ check 2: look-ahead
def cut_data(t_cut):
    """The data as it was at t_cut: only the 5m / 1m bars that OPENED before t_cut (the signal bar closes at t_cut)."""
    D = data()
    k = int(np.searchsorted(D["t"], t_cut)); k1 = int(np.searchsorted(D["t1"], t_cut))
    C = {x: D[x][:k] for x in ("t", "o", "h", "l", "c", "mod", "rel", "sid", "loc")}
    C.update({x: D[x][:k1] for x in ("t1", "o1", "h1", "l1", "c1", "rel1", "sid1")})
    # ATR recomputed from the cut bars only
    h, l, c = C["h"], C["l"], C["c"]
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - prev), np.abs(l - prev)])
    C["atr"] = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    C["days"] = D["days"]; C["n"] = k; C["m1_to"] = int(C["t1"][-1]) if k1 else 0
    C["flat5"] = _flat(C["sid"], C["rel"], 1310); C["flat1"] = _flat(C["sid1"], C["rel1"], 1314)
    C["sw2"] = tuple(x.astype(np.int64) for x in fractal_idx(C["h"], C["l"], 2))
    return C


def _trend_cut(C, span=50):
    """1h trend at the last cut bar from complete 1h bars only."""
    R = resample(C, 60)
    c = R["c"]
    if (int(C["loc"][-1]) + 300) % 3600 != 0:          # the last 1h bar is still forming: drop it
        c = c[:-1]
    a = 2.0 / (span + 1); e = c[0]
    for x in c[1:]:
        e = a * x + (1 - a) * e
    return float(np.sign(c[-1] - e))


def cmd_lookahead(n=30, seed=17):
    """Sampled trades re-derived on data cut at the signal close: the same signal (bar, side, hunt extreme = stop, pool), and
    for the trend lead the same 1h trend from complete 1h bars; entries never before the signal close."""
    rng = np.random.default_rng(seed)
    D = data()
    res = {}
    for nm, cfg in LEADS.items():
        rows = run(cfg)
        idx = sorted(rng.choice(len(rows), size=min(n, len(rows)), replace=False))
        ok, bad = 0, []
        for i in idx:
            r = rows[i]
            C = cut_data(r["signal_t"])
            ev = hunts(pools(C, cfg["types"], cfg["life"], cfg["Ns"]))
            sg = signals(C, ev, cfg)
            ks = C["n"] - 1
            hit = sg[(sg["sig"] == ks) & (sg["dr"] == r["dir"])]
            good = len(hit) == 1
            if good:
                h_ = hit.iloc[0]
                good = abs(r["dir"] * (h_["ext"] - 0.25) - r["stop"]) < 1e-6 and abs(r["dir"] * h_["p"] - r["pool_px"]) < 0.011
            if good and cfg.get("trend"):
                good = _trend_cut(C, cfg.get("ema", 50)) * r["dir"] > 0
            ok += int(good)
            if not good:
                bad.append({"day": r["day"], "entry_t": r["entry_t"]})
        after = all(r["entry_t"] >= r["signal_t"] for r in rows)
        res[nm] = {"checked": len(idx), "identical": ok, "diffs": bad[:5], "entries_after_signal": bool(after)}
        print(nm, res[nm], flush=True)
    res["walk_order"] = walk_order_stats()
    print(res["walk_order"])
    return res


def walk_order_stats():
    """How often a trade bar touched both stop and target (always scored as a stop), and how many trades had a bar that
    reached +1R and also traded back to the BE level (the same-bar BE ambiguity, tested in check 3)."""
    D = data(); out = {}
    for nm, cfg in LEADS.items():
        rows = run(cfg)
        both = be_amb = 0
        for r in rows:
            p1 = r["path"] == "1m"
            t, h, l = (D["t1"], D["h1"], D["l1"]) if p1 else (D["t"], D["h"], D["l"])
            secs = 60 if p1 else 300
            k0 = int(np.searchsorted(t, r["entry_t"])); kx = int(np.searchsorted(t, r["exit_t"] - secs))
            d = r["dir"]; E = d * r["entry"]; risk = r["risk_pts"]
            hi = h[k0:kx + 1] if d > 0 else -l[k0:kx + 1]
            lo = l[k0:kx + 1] if d > 0 else -h[k0:kx + 1]
            both += int(np.any((hi >= E + 2 * risk) & (lo <= E - risk)))
            be_amb += int(np.any((hi >= E + risk) & (lo <= E + 1.25)))
        out[nm] = {"trades": len(rows), "trades_with_a_bar_touching_stop_and_target": both,
                   "trades_with_a_bar_hitting_1R_and_back_to_BE": be_amb}
    return out


# ================================================================================================ check 3: costs and fills
COSTS = {
    "base (researcher's costs)": {},
    "+1 tick slippage (entries and stop / BE / flat exits)": {"slip_ticks": 1},
    "+2 ticks slippage": {"slip_ticks": 2},
    "limits need 2 ticks through, targets 1 tick through": {"limit_thru_extra": 1, "tgt_thru": 1},
    "night +1 tick (fills 18:00-02:00 ET)": {"night_ticks": 1},
    "+1 tick + night +1 tick": {"slip_ticks": 1, "night_ticks": 1},
    "BE same-bar pessimistic": {"be_pess": True},
    "2026 walked on 5m bars (no 1m)": {"force_5m": True},
    "order 5 minutes late (one 5m bar)": {"late_min": 5},
    "worst case (+2 ticks, night +1, trade-through, BE pessimistic)": {"slip_ticks": 2, "night_ticks": 1, "limit_thru_extra": 1,
                                                                        "tgt_thru": 1, "be_pess": True},
}


def cmd_costs():
    res = {}
    for nm, cfg in LEADS.items():
        res[nm] = {}
        for lab, c in COSTS.items():
            sc = score(run(cfg, c))
            res[nm][lab] = {k: {x: sc[k].get(x) for x in ("n", "net", "pf", "win")} for k in sc}
            print(nm, lab, {k: (v["n"], v["net"], v["pf"]) for k, v in res[nm][lab].items()}, flush=True)
    return res


# ================================================================================================ check 4: robustness
STEPS = {
    "asia": [("W", 24), ("W", 48), ("body", 1.0), ("body", 1.5), ("depth", 0.25), ("depth", 0.75), ("bounce", 0.25),
             ("bounce", 0.75), ("mss_look", 36), ("mss_look", 60), ("rr", 1.5), ("rr", 3.0), ("be", (0.0, 0.0)), ("be", (1.0, 0.0)),
             ("be", (0.75, 1.25)), ("be", (1.5, 1.25)), ("min_stop", 4.0), ("min_stop", 10.0), ("max_stop", 60.0), ("max_stop", 100.0),
             ("mp", 2), ("life", 0.5), ("life", 2.0), ("Ns", (2,)), ("Ns", (3, 4, 5)), ("atr_trig", True),
             ("win_ok", [1, 0, 0, 0, 0]), ("win_ok", [0, 1, 0, 0, 0]), ("win_edges", [240, 540, 840, 1080]),
             ("win_edges", [240, 420, 840, 1080]), ("mode", 0)]
            + [("types", tuple(x for x in ASIA["types"] if x != drop)) for drop in ASIA["types"]],
    "trend": [("W", 4), ("W", 8), ("body", 1.0), ("body", 1.5), ("depth", 0.0), ("depth", 0.5), ("pre_atr", 0.75), ("pre_atr", 1.25),
              ("pre_look", 24), ("pre_look", 48), ("mss_look", 36), ("mss_look", 60), ("ema", 40), ("ema", 60), ("ema", 20),
              ("ema", 100), ("entry", "mkt"), ("mid_frac", 0.4), ("mid_frac", 0.6), ("lim_bars", 20), ("lim_bars", 40), ("rr", 1.5),
              ("rr", 3.0), ("be", (0.0, 0.0)), ("be", (1.0, 0.0)), ("be", (0.75, 1.25)), ("be", (1.5, 1.25)), ("min_stop", 4.0),
              ("min_stop", 10.0), ("max_stop", 60.0), ("max_stop", 100.0), ("mp", 1), ("mp", 3), ("life", 0.5), ("life", 2.0),
              ("Ns", (2,)), ("Ns", (3, 4, 5)), ("atr_trig", True), ("trend", False), ("mode", 0)],
}
LABEL = {"W": "trigger window (bars)", "body": "candle body (x ATR)", "depth": "hunt depth (x ATR)", "bounce": "resweep bounce (x ATR)",
         "mss_look": "swing look-back for the shift (bars)", "rr": "target (R)", "be": "breakeven (at R, offset pts)",
         "min_stop": "min stop (pts)", "max_stop": "max stop (pts)", "mp": "max trades a session", "life": "pool life (x)",
         "Ns": "swing strengths N", "atr_trig": "ATR of the trigger bar instead of the hunt bar", "win_ok": "hours",
         "win_edges": "Asia end / early-late split", "mode": "no resweep / inducement condition", "pre_atr": "inducement distance (x ATR)",
         "pre_look": "inducement look-back (bars)", "ema": "1h EMA length", "entry": "entry", "mid_frac": "limit level in the candle",
         "lim_bars": "limit timeout (min)", "trend": "1h trend filter", "types": "pool types"}


def _variant(cfg, k, v):
    c = dict(cfg)
    if k == "lim_bars":
        c["lim_bars1"] = v; c["lim_bars5"] = max(1, round(v / 5))
    else:
        c[k] = v
    return c


def drop_best(rows, k):
    p = sorted((r["pnl_usd"] for r in rows), reverse=True)
    return int(round(sum(p[k:])))


def breakdown(rows):
    out = {}
    by = collections.defaultdict(list)
    for r in rows:
        y = r["day"][:4]
        by["year " + ("2021-22" if y in ("2021", "2022") else y)].append(r)
        if r["day"] >= "2026-07-01":
            by["2026 H2 month " + r["day"][:7]].append(r)
        by["side " + ("long" if r["dir"] > 0 else "short")].append(r)
        by["weekday " + "Mon Tue Wed Thu Fri Sat Sun".split()[dt.date.fromisoformat(r["day"]).weekday()]].append(r)
        b = int(np.searchsorted(np.array([480, 840, 1080]), r["rel_sig"], side="right"))
        by["session " + ("Asia", "London", "NY AM", "NY PM")[b]].append(r)
    for k in sorted(by):
        p = np.array([x["pnl_usd"] for x in by[k]])
        gl = -p[p <= 0].sum()
        out[k] = {"n": len(p), "net": int(round(p.sum())), "win": round(100 * float((p > 0).mean()), 1),
                  "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else None}
    return out


def cmd_robust():
    res = {}
    S4 = ("H1", "H2", "2025", "2021-24")
    for nm, cfg in LEADS.items():
        base = run(cfg)
        rows = []
        for k, v in STEPS[nm]:
            sc = score(run(_variant(cfg, k, v)))
            lab = f"{LABEL[k]} = {v}" if k != "types" else "drop pool type " + (set(cfg["types"]) - set(v)).pop()
            rows.append({"change": lab, **{s: sc[s]["net"] for s in S4}, "n_H2": sc["H2"]["n"]})
        pos = {s: round(100 * float(np.mean([r[s] > 0 for r in rows]))) for s in S4}
        allpos = round(100 * float(np.mean([all(r[s] > 0 for s in S4) for r in rows])))
        med = {s: int(np.median([r[s] for r in rows])) for s in S4}
        worst = {s: min(rows, key=lambda r: r[s])["change"] + f" ({min(r[s] for r in rows):+,})" for s in S4}
        spans = {s: [r for r in base if span_of(r["day"]) == s] for s in S4}
        db = {f"drop best {k}": {s: drop_best(spans[s], k) for s in S4} for k in (3, 5, 10)}
        db["drop best 10 of all 5 years"] = drop_best(base, 10)
        res[nm] = {"base": nets(base), "neighbours": rows, "share_positive": pos, "share_all4_positive": allpos, "median": med,
                   "worst": worst, "drop_best": db, "breakdown": breakdown(base)}
        print(nm, "base", nets(base), "pos%", pos, "all4", allpos, "median", med, flush=True)
        print("   worst", worst); print("   drop", db)
        for r in rows:
            print("   ", r)
        for k, v in res[nm]["breakdown"].items():
            print("   ", k, v)
    return res


# ================================================================================================ check 5: true out-of-sample
# The researcher's own search code (tools/stophunt.py) re-run with six periods; the pick uses ONLY 2021-11 .. 2024-12.
OOS_SPANS = (("2021-22", "2021-11-01", "2022-12-31"), ("2023", "2023-01-01", "2023-12-31"), ("2024", "2024-01-01", "2024-12-31"),
             ("2025", "2025-01-01", "2025-12-31"), ("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"))
OOS_NAMES = [s[0] for s in OOS_SPANS]
PICK_SPANS = (2, 1, 0)          # the analogue of the researcher's (H1, 2025, 2021-24): (2024, 2023, 2021-22); 2024 plays H1
_OG = {}


def _oos_base():
    from tools import stophunt as SH
    SH.base()
    g = SH.G                       # base() returns a copy on its first call; the workers read SH.G
    B = g["B"]
    sp = np.full(len(B["days"]), -1, np.int64)
    for i, (nm, a, z) in enumerate(OOS_SPANS):
        sp[(B["days"] >= a) & (B["days"] <= z)] = i
    g["span_of_sid"] = sp
    g["nsess"] = [int(((B["days"] >= a) & (B["days"] <= z)).sum()) for nm, a, z in OOS_SPANS]
    _OG["SH"] = SH
    return SH, g


def _grid(SH, g, S, opt):
    """tools/stophunt.run_grid2 with six periods instead of four (same loops, same primitives)."""
    sg = SH.sigs_of(g, S)
    out = []
    for en in opt["entry"]:
        if en == "fvg" and not S["fvg"]:
            continue
        for ms in opt["max_stop"]:
            X = SH.fills(g, sg, en, max_stop=ms)
            o = np.argsort(X["ft"], kind="stable")
            Xo = {k: v[o] for k, v in X.items()}
            cm = {c: SH.ctx_ok(g, Xo, c) for c in opt["ctx"]}
            for tg in opt["tg"]:
                for mr in opt["min_rr"]:
                    if SH.TARGETS[tg][0] == "R" and mr != opt["min_rr"][0]:
                        continue
                    T = SH.targets(g, Xo, tg, min_rr=mr)
                    for t15 in opt["t15"]:
                        for be in opt["be"]:
                            for part in opt["part"]:
                                for fl in opt["flat"]:
                                    Wk = SH.walk(g, Xo, T, be=be, t15=bool(t15), part=bool(part), flat=fl)
                                    for c in opt["ctx"]:
                                        okc = Wk["ok"] & cm[c]
                                        for wn in opt["win"]:
                                            for mp in opt["mp"]:
                                                st, _ = SH.select_stats(Xo["ft"], Wk["xt"], Xo["sid"], Xo["bucket"], okc, Wk["pnl"], Wk["R"],
                                                                        SH.WINDOWS[wn], mp, g["span_of_sid"], 6, False)
                                                out.append(([opt[k].index(v) for k, v in
                                                             zip(SH.S2_KEYS, (en, ms, tg, mr, t15, be, part, fl, c, wn, mp))], st))
    return out


def _s1_job(ci):
    SH = _OG["SH"]; g = SH.base()
    S = SH.SETUPS[ci]
    sg = SH.sigs_of(g, S)
    codes, sts = [], []
    for ei, en in enumerate(["mkt", "mid", "fvg"]):
        if en == "fvg" and not S["fvg"]:
            continue
        X = SH.fills(g, sg, en)
        o = np.argsort(X["ft"], kind="stable")
        Xo = {k: v[o] for k, v in X.items()}
        for ti, tg in enumerate(SH.G1_TG):
            T = SH.targets(g, Xo, tg)
            for t15 in SH.G1_T15:
                Wk = SH.walk(g, Xo, T, t15=bool(t15))
                for wi, wn in enumerate(SH.G1_WIN):
                    for mi, mp in enumerate(SH.G1_MP):
                        st, _ = SH.select_stats(Xo["ft"], Wk["xt"], Xo["sid"], Xo["bucket"], Wk["ok"], Wk["pnl"], Wk["R"],
                                                SH.WINDOWS[wn], mp, g["span_of_sid"], 6, False)
                        codes.append([ci, ei, ti, t15, wi, mi]); sts.append(st)
    return np.array(codes, np.int32), np.array(sts, np.float32)


def _gen_job(args):
    SH = _OG["SH"]; g = SH.base()
    j, S, opt = args
    R = _grid(SH, g, S, opt)
    return np.array([[j] + c for c, _ in R], np.int32), np.array([st for _, st in R], np.float32)


def _pmap(fn, jobs, procs=4, chunk=8, tag=""):
    from multiprocessing import Pool
    C, S = [], []
    t0 = time.time()
    with Pool(procs) as pool:
        for k, (c, s) in enumerate(pool.imap(fn, jobs, chunksize=chunk)):
            C.append(c); S.append(s)
            if k % 2000 == 0:
                print(f"   {tag} {k}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    return np.concatenate(C), np.concatenate(S)


def _robust_pick(SH, M, K, radix, names, nb, nwk, top=12):
    """The researcher's 'robust' rule (tools/stophunt.s3_pick) with 2024 / 2023 / 2021-22 in place of H1 / 2025 / 2021-24."""
    a, b, c = PICK_SPANS
    ki = SH._kint(K, radix); sorter = np.argsort(ki)
    el = (M["n"][:, a] >= nwk[a]) & (M["net"][:, a] > 0) & (M["pf"][:, a] >= 1.3) & (M["n"][:, b] >= 0.5 * nwk[b]) & \
         (M["n"][:, c] >= 0.5 * nwk[c])
    score_ = np.min(M["t"][:, list(PICK_SPANS)], 1)
    idx = np.nonzero(el)[0]
    o = idx[np.argsort(-score_[idx])]
    picks, seen = [], set()
    for i in o:
        sig = (int(M["n"][i, a]), int(M["net"][i, a]), int(M["n"][i, c]), int(M["net"][i, c]))
        if sig in seen:
            continue
        fr, nn = SH.plateau2(K, radix, names, nb, ki, sorter, i, M["net"], a)
        if nn < 5 or fr < 0.8:
            continue
        fr3, _ = SH.plateau2(K, radix, names, nb, ki, sorter, i, M["net"], c)
        if fr3 < 0.8:
            continue
        seen.add(sig); picks.append(int(i))
        if len(picks) >= top:
            break
    return picks, int(el.sum())


def _row(M, i):
    return {OOS_NAMES[s]: {"n": int(M["n"][i, s]), "net": int(round(float(M["net"][i, s]))), "t": round(float(M["t"][i, s]), 2),
                           "win": round(float(M["win"][i, s]), 1)} for s in range(6)}


def _summ(M, picks, eligible, n_var, base_mask):
    later = (3, 4, 5)
    return {"variants": int(n_var), "eligible": eligible, "top_pick": _row(M, picks[0]) if picks else None,
            "shortlist_positive_share": {OOS_NAMES[s]: round(float(np.mean([M["net"][i, s] > 0 for i in picks])), 2) for s in later} if picks else None,
            "shortlist_mean_net": {OOS_NAMES[s]: int(np.mean([M["net"][i, s] for i in picks])) for s in later} if picks else None,
            "base_positive_share": {OOS_NAMES[s]: round(float((M["net"][base_mask, s] > 0).mean()), 2) for s in later}}


def cmd_oos(procs=4):
    SH, g = _oos_base()
    nwk = [x / 5 for x in g["nsess"]]
    res = {"periods": OOS_NAMES, "pick_on": "worst t of 2024, 2023 and 2021-22 (the researcher's robust rule, shifted back)"}
    # ---- stage 1: the generic grid (defined before any result was seen)
    t0 = time.time()
    C1, S1 = _pmap(_s1_job, list(range(len(SH.SETUPS))), procs, 16, "stage1")
    print("stage 1", len(C1), f"{time.time() - t0:.0f}s", flush=True)
    M1 = SH.metrics(S1)
    dimv = {d: np.array([SH.DIMS[d].index(x[d]) for x in SH.SETUPS]) for d in SH.DIMS}
    K1 = np.zeros((len(C1), len(SH.KEY_DIMS)), np.int64)
    for i, d in enumerate(SH.DIMS):
        K1[:, i] = dimv[d][C1[:, 0]]
    K1[:, len(SH.DIMS):] = C1[:, 1:]
    nb1 = {"W": "ord", "body": "ord", "depth": "any", "t15": "any", "mp": "any", "entry": "any", "struct": "any", "tg": "any",
           "fvg": "any"}
    p1, e1 = _robust_pick(SH, M1, K1, SH.RADIX, SH.KEY_DIMS, nb1, nwk, top=39)
    base1 = M1["n"][:, 2] >= nwk[2]
    res["stage1"] = _summ(M1, p1[:12], e1, len(C1), base1)
    res["stage1"]["top_labels"] = [SH.label(K1, i) for i in p1[:12]]
    print("stage 1 picks", json.dumps(res["stage1"])[:2000], flush=True)
    # ---- stage 2: the management grid (OPT_A) on the 39 best stage-1 setups, robust pick again
    setups, seen = [], set()
    for i in p1:
        lab = SH.label(K1, i).split("|")
        S = dict(pool=lab[0], mode=lab[1], W=int(lab[2]), body=lab[3], struct=lab[4], fvg=int(lab[5]), depth=float(lab[6]))
        k = json.dumps(S, sort_keys=True)
        if k not in seen:
            seen.add(k); setups.append((S, lab[10]))
    jobs = []
    for j, (S, w) in enumerate(setups):
        opt = dict(SH.OPT_A); opt["win"] = sorted({w, "all"})
        jobs.append((j, S, opt))
    del S1, M1
    C2, S2 = _pmap(_gen_job, jobs, procs, 1, "stage2")
    M2 = SH.metrics(S2)
    radix = [len(jobs)] + [max(len(SH.OPT_A[k]) if SH.OPT_A[k] else 2, 2) for k in SH.S2_KEYS]
    names = ["job"] + SH.S2_KEYS
    nb2 = {"entry": "any", "max_stop": "ord", "tg": "any", "min_rr": "any", "t15": "any", "be": "any", "part": "any",
           "flat": "any", "mp": "any"}
    # option index -> value per job (the win list differs per job)
    p2, e2 = _robust_pick(SH, M2, C2.astype(np.int64), radix, names, nb2, nwk)
    res["stage2"] = _summ(M2, p2, e2, len(C2), M2["n"][:, 2] >= nwk[2])
    res["stage2"]["top_specs"] = [{**jobs[C2[i, 0]][1], **{k: jobs[C2[i, 0]][2][k][C2[i, 1 + q]] for q, k in enumerate(SH.S2_KEYS)}}
                                  for i in p2[:12]]
    print("stage 2", json.dumps(res["stage2"], default=str)[:2500], flush=True)
    # ---- stage 3: the researcher's two refinement families (shaped after looking at later data), pick on pre-2025 only
    for fam in ("asia", "trend"):
        sd, opt = SH.FAM3[fam]
        import itertools
        J = [(j, dict(zip(sd, v)), opt) for j, v in enumerate(itertools.product(*sd.values()))]
        C3, S3 = _pmap(_gen_job, J, procs, 4, "stage3 " + fam)
        M3 = SH.metrics(S3)
        Gm = np.array([[sd[d].index(j[1][d]) for d in sd] for j in J])
        K3 = np.c_[Gm[C3[:, 0]], C3[:, 1:]].astype(np.int64)
        radix3 = [len(sd[d]) for d in sd] + [len(opt[k]) for k in SH.S2_KEYS]
        names3 = list(sd) + SH.S2_KEYS
        nb3 = {"W": "ord", "body": "ord", "depth": "ord", "struct": "any", "mode": "any", "fvg": "any", "entry": "any",
               "max_stop": "ord", "tg": "any", "t15": "any", "be": "any", "mp": "any"}
        p3, e3 = _robust_pick(SH, M3, K3, radix3, names3, nb3, nwk)
        spec = lambda i: {**J[C3[i, 0]][1], **{k: opt[k][C3[i, 1 + q]] for q, k in enumerate(SH.S2_KEYS)}}
        r = _summ(M3, p3, e3, len(C3), M3["n"][:, 2] >= nwk[2])
        r["top_specs"] = [spec(i) for i in p3[:12]]
        r["shortlist"] = [_row(M3, i) for i in p3[:12]]
        # where do the researcher's leads rank under the pre-2025 rule?
        lead = {"asia": dict(pool="htf", mode="rs", W=36, body="a1.2", struct="mss", fvg=0, depth=0.5, entry="mkt", max_stop=80.0,
                             tg="r2", min_rr=1.5, t15=0, be="be1c", part=0, flat="1555", ctx="none", win="asia", mp=1),
                "trend": dict(pool="f5", mode="pre", W=6, body="a1.2", struct="mss", fvg=0, depth=0.25, entry="mid", max_stop=80.0,
                              tg="r2", min_rr=1.5, t15=0, be="be1c", part=0, flat="1555", ctx="with", win="all", mp=2)}[fam]
        row = [sd[d].index(lead[d]) for d in sd] + [opt[k].index(lead[k]) for k in SH.S2_KEYS]
        li = int(np.nonzero((K3 == np.array(row)).all(1))[0][0])
        sc_all = np.min(M3["t"][:, list(PICK_SPANS)], 1)
        el = (M3["n"][:, 2] >= nwk[2]) & (M3["net"][:, 2] > 0) & (M3["pf"][:, 2] >= 1.3) & (M3["n"][:, 1] >= 0.5 * nwk[1]) & \
             (M3["n"][:, 0] >= 0.5 * nwk[0])
        r["lead"] = {"row": _row(M3, li), "eligible_pre2025": bool(el[li]), "pre2025_score": round(float(sc_all[li]), 2),
                     "rank_among_eligible": int((sc_all[el] > sc_all[li]).sum()) + 1 if el[li] else None, "eligible": int(el.sum())}
        res["stage3_" + fam] = r
        print("stage 3", fam, json.dumps(r, default=str)[:3000], flush=True)
        del C3, S3, M3, K3
    json.dump(res, open(os.path.join(OUT, "_audit_oos.json"), "w"), indent=1, default=str)
    return res


# ================================================================================================ check 6: multiple testing
RCACHE = os.environ.get("SH_CACHE", os.path.join(ROOT, "research", "runs", "_cache"))
FAM_CACHE = {"asia": "stophunt_s3asia_stats.npy", "trend": "stophunt_s3trend_stats.npy"}
RULE_KEYS = {"asia": ("asia_robust", "asia_robust_win"), "trend": ("trend_robust", "trend_robust_win")}
LEAD_SPEC = {"asia": dict(pool="htf", mode="rs", W=36, body="a1.2", struct="mss", depth=0.5, entry="mkt", max_stop=80.0, tg="r2",
                          t15=0, be="be1c", ctx="none", win="asia", mp=1),
             "trend": dict(pool="f5", mode="pre", W=6, body="a1.2", struct="mss", depth=0.25, entry="mid", max_stop=80.0, tg="r2",
                           t15=0, be="be1c", ctx="with", win="all", mp=2)}


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _phinv(p):
    from statistics import NormalDist
    return NormalDist().inv_cdf(p)


def deflated_sharpe(R, sr_var, N):
    """Bailey & Lopez de Prado: P(true Sharpe > the best-of-N luck level) for per-trade returns R."""
    R = np.asarray(R, float); T = len(R)
    sr = R.mean() / R.std(ddof=1)
    g3 = float(((R - R.mean()) ** 3).mean() / R.std() ** 3); g4 = float(((R - R.mean()) ** 4).mean() / R.std() ** 4)
    gam = 0.5772156649
    sr0 = math.sqrt(sr_var) * ((1 - gam) * _phinv(1 - 1.0 / N) + gam * _phinv(1 - 1.0 / (N * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-9, 1 - g3 * sr + (g4 - 1) / 4 * sr * sr))
    return {"sr_per_trade": round(sr, 3), "luck_level_sr": round(sr0, 3), "T": T, "dsr": round(_phi(z), 3)}


def boot_p(R, n=20000, seed=5):
    """One-sided bootstrap p-value that the mean per-trade R is <= 0."""
    rng = np.random.default_rng(seed)
    R = np.asarray(R, float)
    m = rng.choice(R - R.mean(), size=(n, len(R)), replace=True).mean(1)
    return round(float((m >= R.mean()).mean()), 4)


def cmd_multi():
    picks = json.load(open(os.path.join(OUT, "stage3_picks.json"), encoding="utf-8"))
    summ = json.load(open(os.path.join(OUT, "search_summary.json"), encoding="utf-8"))
    res = {}
    for fam, cfg in LEADS.items():
        rows = run(cfg)
        r = {}
        # (a) was the lead the rule's own pick? rank inside the researcher's shortlists and its H2 against the shortlist's
        for rk in RULE_KEYS[fam]:
            P = picks[rk]["picks"]
            rank = next((i + 1 for i, p in enumerate(P) if all(p["spec"].get(k) == v for k, v in LEAD_SPEC[fam].items())), None)
            h2 = [p["H2_net"] for p in P]
            r[rk] = {"lead_rank": rank, "of": len(P), "rank1_H2_net": round(h2[0]), "shortlist_H2_mean": round(float(np.mean(h2))),
                     "shortlist_H2_median": round(float(np.median(h2))), "shortlist_H2_positive": f"{sum(x > 0 for x in h2)}/{len(h2)}",
                     "lead_H2_net": round(h2[rank - 1]) if rank else None,
                     "lead_H2_rank_in_shortlist": (sorted(h2, reverse=True).index(h2[rank - 1]) + 1) if rank else None}
        # (b) deflated Sharpe on the selection periods (H1 + 2025 + 2021-24) against the family's spread of Sharpe ratios
        fp = os.path.join(RCACHE, FAM_CACHE[fam])
        if os.path.exists(fp):
            S = np.load(fp, mmap_mode="r")
            n = S[:, [0, 2, 3], 0].sum(1); s1 = S[:, [0, 2, 3], 5].sum(1); s2 = S[:, [0, 2, 3], 6].sum(1)
            ok = n >= 100
            mu = s1[ok] / n[ok]; sd = np.sqrt(np.maximum(s2[ok] / n[ok] - mu * mu, 1e-12))
            srs = mu / sd
            V = float(np.var(srs))
            ins = [x["r"] for x in rows if span_of(x["day"]) in ("H1", "2025", "2021-24")]
            dis = summ["stages"]["stage3_" + fam]["distinct"]
            r["deflated_sharpe"] = {"family_variants_with_100_trades": int(ok.sum()), "family_sr_sd": round(math.sqrt(V), 3),
                                    "lead_sr_rank_in_family": f"top {100 * float((srs > np.mean(ins) / np.std(ins, ddof=1)).mean()):.2f}%",
                                    **{f"N={N:,}": deflated_sharpe(ins, V, N) for N in (100, 1000, 10000, 100000)},
                                    f"N={dis:,} (distinct trade sets in the family)": deflated_sharpe(ins, V, dis),
                                    "N=28.7M (whole search)": deflated_sharpe(ins, V, 28703424)}
        # (c) the only clean period: H2 on its own, then adjusted for the choice among the shortlist
        h2 = [x["r"] for x in rows if span_of(x["day"]) == "H2"]
        p = boot_p(h2)
        st = stored(cfg["name"])["placebo"]["H2"]
        k = 12
        r["H2_alone"] = {"n": len(h2), "mean_R": round(float(np.mean(h2)), 3),
                         "t": round(float(np.mean(h2) / (np.std(h2, ddof=1) / math.sqrt(len(h2)))), 2),
                         "bootstrap_p_mean_R_le_0": p, "random_time_placebo_p (researcher)": st["p_rtime"],
                         "flip_placebo_p (researcher)": st["p_flip"],
                         f"bootstrap_p_adjusted_for_best_of_{k}": round(1 - (1 - p) ** k, 3),
                         f"random_time_p_adjusted_for_best_of_{k}": round(1 - (1 - st["p_rtime"]) ** k, 3)}
        r["family_chance"] = {k_: summ["stages"]["stage3_" + fam][k_] for k_ in ("t1_H1_2025_2124_obs", "t1_H1_2025_2124_exp",
                                                                                 "p_H2pos_given_t1_H1_2025_2124", "p_pos")}
        res[fam] = r
        print(fam, json.dumps(r, indent=1, default=str), flush=True)
    return res


# ================================================================================================ check 7: eval paths
SCR = os.environ.get("SH_SCRATCH", os.path.join(ROOT, "research", "runs", "_cache", "stophunt_audit"))


def placebo_rows(cfg, rows, mode, seed):
    """Placebo trades with the lead's own mechanics (entry kind, the real trade's stop points, 2R, BE + 1.25 at 1R, flat 15:55,
    one position, max per session). mode 'rtime': same side, a random 5m signal bar of the same session bucket in a random
    session of the same period (redrawn up to 20 times if a limit does not fill); 'flip': same signal bar, other side."""
    D = data(); rng = np.random.default_rng(seed)
    kind = 0 if cfg["entry"] == "mkt" else 1
    rel = D["rel"]; bk = np.searchsorted(np.array([480, 840, 1080]), rel, side="right")
    sp5 = np.array([span_of(str(d)) or "" for d in D["days"]])[D["sid"]]
    elig = (rel <= 1285) & (D["flat5"] >= 0)
    pools_ = {}
    out = []
    for r in rows:
        s5 = int(np.searchsorted(D["t"], r["signal_t"] - 300))
        d = r["dir"]; risk = r["risk_pts"]
        c_sig = D["c"][s5] * d
        dist = (c_sig - d * r["entry"]) if kind == 1 else 0.0
        key = (span_of(r["day"]), int(bk[s5]))
        if key not in pools_:
            pools_[key] = np.nonzero(elig & (sp5 == key[0]) & (bk == key[1]))[0]
        for attempt in range(20 if mode == "rtime" else 1):
            if mode == "rtime":
                q = int(pools_[key][rng.integers(len(pools_[key]))]); dd_ = d
            else:
                q = s5; dd_ = -d
            s = int(D["sid"][q]); tsig = int(D["t"][q]) + 300
            lim = math.floor((D["c"][q] * dd_ - dist) / 0.25) * 0.25 if kind == 1 else 0.0
            if M1_FROM <= tsig < D["m1_to"]:
                k1 = int(np.searchsorted(D["t1"], tsig))
                if k1 >= len(D["t1"]):
                    continue
                k0, e = _fill_one(D["o1"], D["h1"], D["l1"], D["rel1"], D["sid1"], k1, s, dd_, kind, lim, 30, 1290, 0.25)
                arr = (D["o1"], D["h1"], D["l1"], D["c1"], D["t1"], D["flat1"], 60)
            else:
                k0, e = _fill_one(D["o"], D["h"], D["l"], D["rel"], D["sid"], q + 1, s, dd_, kind, lim, 6, 1290, 0.25)
                arr = (D["o"], D["h"], D["l"], D["c"], D["t"], D["flat5"], 300)
            if k0 < 0 or arr[5][k0] < 0:
                continue
            o, h, l, c, t, fl, secs = arr
            sp = e - risk; T = e + 2.0 * risk
            pts, kx, ek = _walk_one(o, h, l, c, k0, int(fl[k0]), dd_, e, sp, risk, T, 1.0, 1.25, kind == 1, 0.0, 0.0, False)
            qty = int(min(MAXQ, math.floor(RISK_USD / (risk * PV))))
            out.append({"day": str(D["days"][s]), "sid": s, "entry_t": int(t[k0]), "exit_t": int(t[kx]) + secs, "dir": dd_,
                        "entry": round(dd_ * e, 2), "stop": round(dd_ * sp, 2), "target": round(dd_ * T, 2),
                        "exit": round(dd_ * (e + pts), 2), "exit_kind": EXITS[ek], "qty": qty, "r": 0.0,
                        "pnl_usd": round(qty * (pts * PV - COMM), 2), "risk_pts": risk})
            break
    out.sort(key=lambda x: x["entry_t"])
    sel, busy, cnt = [], -1, collections.Counter()
    for x in out:
        if x["entry_t"] < busy or cnt[x["sid"]] >= cfg["mp"]:
            continue
        cnt[x["sid"]] += 1; busy = x["exit_t"]; sel.append(x)
    return sel


def _ev(o):
    return {k: o.get(k) for k in ("p10", "f10", "s10", "dead10", "p20", "dead20", "pass_med", "net", "dd", "b2b")}


def cmd_evals(nseed=10):
    from tools import second_mix as M
    from tools import second_account_b as AB
    os.makedirs(SCR, exist_ok=True)
    U = M.units()
    stored_ev = json.load(open(os.path.join(OUT, "evals.json"), encoding="utf-8"))

    def member(nm, rows):
        fp = os.path.join(SCR, nm + ".json")
        json.dump({"trades": rows}, open(fp, "w"))
        M.SECOND[nm] = fp
        U[nm] = M.second_units(nm)

    def atlas_plus(names):
        with AB.Plan("builder25k") as pl:
            UA = M.acct_units(("EMA", "MD", "SR") + tuple(names), nohedge=True)
            return {s: _ev(AB.score(UA, "acctb_need", s, pl.safe_rule)[0]) for s in AB.SPANS}

    res = {"ATLAS_alone": atlas_plus(())}
    print("ATLAS alone", res["ATLAS_alone"], flush=True)
    real = {nm: run(cfg) for nm, cfg in LEADS.items()}
    for nm, cfg in LEADS.items():
        member("aud_" + nm, real[nm])
        r = {"real": atlas_plus(("aud_" + nm,)),
             "stored (researcher)": {s: _ev(stored_ev[cfg["name"]]["ATLAS_plus_25k"][s]) for s in AB.SPANS}}
        stress = run(cfg, {"slip_ticks": 1, "night_ticks": 1})
        member("aud_" + nm + "_stress", stress)
        r["real, +1 tick + night +1 tick"] = atlas_plus(("aud_" + nm + "_stress",))
        for mode in ("rtime", "flip"):
            runs_ = []
            for sd in range(nseed if mode == "rtime" else 1):
                pr = placebo_rows(cfg, real[nm], mode, 100 + sd)
                member(f"aud_{nm}_{mode}{sd}", pr)
                runs_.append(atlas_plus((f"aud_{nm}_{mode}{sd}",)))
            r[f"placebo {mode}"] = {s: {"p10_mean": round(float(np.mean([x[s]["p10"] for x in runs_])), 1),
                                        "p10_min_max": [min(x[s]["p10"] for x in runs_), max(x[s]["p10"] for x in runs_)],
                                        "dead10_mean": round(float(np.mean([x[s]["dead10"] for x in runs_])), 1),
                                        "net_mean": int(np.mean([x[s]["net"] for x in runs_]))} for s in AB.SPANS}
            r[f"placebo {mode}"]["n_runs"] = len(runs_)
        res[nm] = r
        print(nm, json.dumps(r, default=str), flush=True)
    # both hunts
    res["both_real"] = atlas_plus(("aud_asia", "aud_trend"))
    print("both", res["both_real"], flush=True)
    return res


VERDICT = {
    "sh_asia_resweep": {"verdict": "WEAK", "use": "paper only (ATLAS member on account B at most); no eval, no real money",
                        "checks": {"1_replicate": "pass", "2_lookahead": "pass", "3_costs": "pass (2021-24 loses ~1/5 to a night tick)",
                                   "4_robust": "mixed (plateau and years fine; H2 = its 3 best trades)",
                                   "5_oos": "fail for the variant (rank ~12,000); family picks positive in H2 12/12, weak in 2025/H1",
                                   "6_multiple_testing": "fail (rank 9/12, 2nd-best H2; H2 p 0.21; DSR ~0)",
                                   "7_evals": "numbers reproduce; beats a random-time placebo member; 'no fails' hides 41% stuck in 2025/2021-24"}},
    "sh_trend_idm5": {"verdict": "NOT REAL", "use": "do not route; a control at most",
                      "checks": {"1_replicate": "pass", "2_lookahead": "pass", "3_costs": "pass (5 minutes late halves H2)",
                                 "4_robust": "mixed (plateau fine; 2024 PF 1.11; H2 +$168 without its 5 best)",
                                 "5_oos": "fail (not eligible pre-2025; family picks 0/12 positive in 2025 and H2)",
                                 "6_multiple_testing": "fail (rank 10/12 with the best H2 of 12; best-of-12 p 0.32-0.44; family 0.5x chance)",
                                 "7_evals": "no better than a random member in H1; the flipped twin passes more"}},
}


def cmd_all():
    """Every check except the slow selection re-run (cmd_oos writes research/stophunt/_audit_oos.json, read here)."""
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "leads": {k: v["name"] for k, v in LEADS.items()},
           "code": "tools/stophunt_audit.py (independent of engine/stophunt.py)", "hidden_rule_details": HIDDEN}
    out["1_replicate"] = cmd_replicate()
    out["2_lookahead"] = cmd_lookahead()
    out["3_costs"] = cmd_costs()
    out["4_robust"] = cmd_robust()
    fp = os.path.join(OUT, "_audit_oos.json")
    out["5_oos"] = json.load(open(fp)) if os.path.exists(fp) else None
    out["6_multiple_testing"] = cmd_multi()
    out["7_evals"] = cmd_evals()
    out["verdict"] = VERDICT
    json.dump(out, open(os.path.join(OUT, "audit.json"), "w"), indent=1, default=str)
    print("wrote research/stophunt/audit.json")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "replicate"
    globals()["cmd_" + cmd]()
