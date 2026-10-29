"""BLITZ on its own MFFU Builder 25K ("account C"): research library (owner 2026-10-28/29: trade "like a person, not a fixed
rr", learn market structure). Research only; nothing here is imported by the engine. research/writeups/blitz-25k.md.

Builds on tools/scalp_na_lib.py (BLITZ's signals: the noise band, the prior-day range filter, the fills, the MFFU eval /
funded / whole-slot simulators) and adds:

  structure(B)          swing pivots known at each bar's close: 1m pivots (strength 3) and 5m pivots (strength 2, from 5m
                        bars built out of the 1m bars, or the native 5m file), the price and the START time of the pivot bar
  cands(B, v)           BLITZ's candidates (today's signal bars + the day filter) with a STOP and TARGETS from variant v:
                          stop  "atr"   signal close -/+ k x ATR(14) of 5m bars (today: k 1.5)
                                "sw1" / "sw5" 1 tick beyond the last confirmed 1m / 5m swing low (long) / high (short)
                                "lowN"  1 tick beyond the lowest low / highest high of the last N minutes (the move's origin)
                                min / max distance in 5m-ATR units: under the min -> widened to the min, over the max -> skipped
                          target "liq"  the nearest untaken opposing liquidity at least r_min R away and at most r_max R:
                                prior RTH high / low, overnight (18:00-09:30) high / low, the prior week's high / low, today's
                                RTH high / low so far, untaken 5m swing highs / lows of the last 3 sessions ("eq" only the
                                levels where two untaken 5m swings sit within 3 points = equal highs / lows, plus PDH / PDL,
                                ONH / ONL, PWH / PWL); the limit sits 1 tick in front of the level (fills when the level trades)
                                a partial ("part") at the first level >= p_min R and the runner to the next level
  run(B, v, C)          numba executor = scalp_na_lib._sim fills (market next open + 1 tick, stop - 1 tick or the gapped open,
                        limits only when traded through, same-bar tie = loss, time / 15:55 exits at the close - 1 tick, $1.90 a
                        micro) plus: a fixed target for the runner, a swing trail (the stop follows each new confirmed 1m / 5m
                        swing low that formed after the entry, once +x R), a change-of-character exit (a close beyond the last
                        swing formed after the entry), no time limit (hold 0), and ACCOUNT C (C = blocking arrays): no entry
                        opposite a position LIT (account A) or ATLAS (account B) holds; a BLITZ trade is closed at the open of
                        the first bar at / after an opposite LIT / ATLAS entry (they go first, MFFU anti-hedge across one
                        person's accounts); option "armed": also never opposite a LIT setup that is armed (limit working /
                        waiting for its 1m CISD), closed when one is armed.
  account_c(B, mode)    the blocking arrays from the research LIT trades (2026 run lit_live 1m fills, 2021-25 the 5m REF rows,
                        research/handoff/2026-10-25 ledger), the ATLAS account-B trades (tools/atlas.account_units, as
                        tools/scalp_na_combo.atlas_by_day) and the LIT armed windows (tools/atlas_lit_armed).

Trade rows are scalp_na_lib.run rows (+ "rew_pm" = the target's $ a micro when there is one), so scalp_na_lib.stats /
eval_score / funded_score / life score them unchanged. qty() adds the sizing "tneed": micros so that the trade's TARGET pays
what the eval still needs (one winner passes), capped by f x room and the $ cap.
"""
from __future__ import annotations

import collections
import datetime as dt
import os
import sys

import numpy as np
from numba import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import scalp_na_lib as N  # noqa: E402

_NQTY = N.qty                     # scalp_na_lib's own sizing (install_qty may route N.qty through qty() below)

TICK, PV, COMM = N.TICK, N.PV, N.COMM
NAN = np.nan
TODAY = {"stop": "atr", "k": 1.5, "tgt": None, "part": None, "hold": 30, "trail": 1.5, "tstart": 1.0, "be": None, "be_off": 0.25,
         "sw_trail": 0, "sw_start": 1.0, "choch": 0, "maxday": 6, "day_stop": 3.0, "dmin": 0.0, "dmax": 99.0, "r_min": 1.0,
         "r_max": 99.0, "p_min": 0.5, "part_f": 0.5, "part_be": False, "liq": "all", "filter": "prng>=0.8", "late": 0,
         "wins": ("rth",), "last_mod": 930, "lim": None, "lim_w": 10}


# ================================================================================================ swing structure
@njit(cache=True)
def _pivots(h, l, n):
    """pivot high at k: h[k] > h[k-1..k-n] and h[k] >= h[k+1..k+n] (lows mirrored); confirmed at the close of bar k+n.
    Returns per bar i the last CONFIRMED pivot (price, pivot index) as of i's close, for highs and lows."""
    m = len(h)
    hp = np.full(m, np.nan); hk = np.full(m, -1, np.int64)
    lp = np.full(m, np.nan); lk = np.full(m, -1, np.int64)
    ch, ck, cl, clk = np.nan, -1, np.nan, -1
    for i in range(m):
        k = i - n
        if k >= n:
            okh = True
            okl = True
            for j in range(1, n + 1):
                if not (h[k] > h[k - j]) or not (h[k] >= h[k + j]):
                    okh = False
                if not (l[k] < l[k - j]) or not (l[k] <= l[k + j]):
                    okl = False
            if okh:
                ch, ck = h[k], k
            if okl:
                cl, clk = l[k], k
        hp[i], hk[i], lp[i], lk[i] = ch, ck, cl, clk
    return hp, hk, lp, lk


_S = {}


def _agg5(B):
    """5m bars from 1m bars (groups t // 300): per group high / low / start time and the 1m index of the group's last bar."""
    t = B["t"]
    g = t // 300
    last = np.r_[g[1:] != g[:-1], True]
    first = np.r_[True, g[1:] != g[:-1]]
    gid = np.cumsum(first) - 1
    ng = int(gid[-1]) + 1
    H = np.full(ng, -np.inf); Lo = np.full(ng, np.inf)
    np.maximum.at(H, gid, B["h"]); np.minimum.at(Lo, gid, B["l"])
    T0 = t[first]
    return H, Lo, T0, gid, np.where(last)[0]


def _parr(rows):
    return {"t": np.array([r[0] for r in rows], np.int64), "p": np.array([r[1] for r in rows]), "ci": np.array([r[2] for r in rows], np.int64)}


def structure(B):
    """dict of per-bar arrays: sw1 / sw5 x (hp, ht, lp, lt) = last confirmed swing high / low price and its pivot bar's START
    time as of the bar's close. On 5m bars "sw1" = 5m pivots of strength 1 (the closest proxy; flagged in the write-up)."""
    k = ("st", B["tf"], len(B["t"]))
    if k in _S:
        return _S[k]
    out = {}
    t = B["t"]
    if B["tf"] == 1:
        hp, hk, lp, lk = _pivots(B["h"], B["l"], 3)
        out["sw1"] = (hp, np.where(hk >= 0, t[np.clip(hk, 0, None)], -1), lp, np.where(lk >= 0, t[np.clip(lk, 0, None)], -1))
        H, Lo, T0, gid, lastix = _agg5(B)
        hp5, hk5, lp5, lk5 = _pivots(H, Lo, 2)
        # 1m bar i: the 5m group's value is known at the close of the group's last 1m bar; before that, the previous group's
        pos = np.where(np.r_[gid[1:] != gid[:-1], True], gid, gid - 1)
        ok = pos >= 0
        pc = np.clip(pos, 0, None)
        out["sw5"] = (np.where(ok, hp5[pc], np.nan), np.where(ok & (hk5[pc] >= 0), T0[np.clip(hk5[pc], 0, None)], -1),
                      np.where(ok, lp5[pc], np.nan), np.where(ok & (lk5[pc] >= 0), T0[np.clip(lk5[pc], 0, None)], -1))
    else:
        for nm, n in (("sw1", 1), ("sw5", 2)):
            hp, hk, lp, lk = _pivots(B["h"], B["l"], n)
            out[nm] = (hp, np.where(hk >= 0, t[np.clip(hk, 0, None)], -1), lp, np.where(lk >= 0, t[np.clip(lk, 0, None)], -1))
    # 5m pivot LISTS for targets (untaken swing highs / lows): (start time, price, confirm 1m/5m index)
    if B["tf"] == 1:
        H, Lo, T0, gid, lastix = _agg5(B)
        hp5, hk5, lp5, lk5 = _pivots(H, Lo, 2)
        ph = sorted({int(x) for x in hk5 if x >= 0})
        pl = sorted({int(x) for x in lk5 if x >= 0})
        conf = lambda kk: int(lastix[min(kk + 2, len(lastix) - 1)])
        out["piv_hi"] = _parr([(int(T0[kk]), float(H[kk]), conf(kk)) for kk in ph])
        out["piv_lo"] = _parr([(int(T0[kk]), float(Lo[kk]), conf(kk)) for kk in pl])
    else:
        hp, hk, lp, lk = _pivots(B["h"], B["l"], 2)
        out["piv_hi"] = _parr([(int(t[kk]), float(B["h"][kk]), kk + 2) for kk in sorted({int(x) for x in hk if x >= 0})])
        out["piv_lo"] = _parr([(int(t[kk]), float(B["l"][kk]), kk + 2) for kk in sorted({int(x) for x in lk if x >= 0})])
    _S[k] = out
    return out


@njit(cache=True)
def _bos_state(c, hp, lp, gl):
    """market-structure state per higher-timeframe bar: +1 after a close above the last confirmed swing high (bullish break of
    structure), -1 after a close below the last confirmed swing low; the swing values are the ones known BEFORE this bar."""
    m = len(c)
    st = np.zeros(m)
    cur = 0.0
    for i in range(1, m):
        if hp[i - 1] == hp[i - 1] and c[i] > hp[i - 1]:
            cur = 1.0
        elif lp[i - 1] == lp[i - 1] and c[i] < lp[i - 1]:
            cur = -1.0
        st[i] = cur
    return st


def htf_state(B, minutes, n=2):
    """per base bar: the market-structure state of `minutes` bars (built from the base bars, pivots of strength n) as of the
    last COMPLETED higher bar at the base bar's close."""
    k = ("htf", minutes, n, B["tf"], len(B["t"]))
    if k in _S:
        return _S[k]
    t = B["t"]
    g = t // (60 * minutes)
    last = np.r_[g[1:] != g[:-1], True]
    first = np.r_[True, g[1:] != g[:-1]]
    gid = np.cumsum(first) - 1
    ng = int(gid[-1]) + 1
    H = np.full(ng, -np.inf); Lo = np.full(ng, np.inf)
    np.maximum.at(H, gid, B["h"]); np.minimum.at(Lo, gid, B["l"])
    C = B["c"][last]
    hp, hk, lp, lk = _pivots(H, Lo, n)
    st = _bos_state(C, hp, lp, 0)
    pos = np.where(last, gid, gid - 1)
    out = np.where(pos >= 0, st[np.clip(pos, 0, None)], 0.0)
    _S[k] = out
    return out


def levels_ctx(B):
    """per day id: prior RTH high / low, overnight high / low (prior date 18:00 -> today 09:30), prior week high / low (RTH,
    ISO week before), and the first index of the day / RTH."""
    k = ("lv", B["tf"], len(B["t"]))
    if k in _S:
        return _S[k]
    m, h, l = B["mod"], B["h"], B["l"]
    nd = len(B["dates"])
    X = {nm: np.full(nd, np.nan) for nm in ("pdh", "pdl", "onh", "onl", "pwh", "pwl", "eveh", "evel", "wkh0", "wkl0")}
    s0 = np.full(nd, -1, np.int64)
    starts = np.r_[0, np.where(np.diff(B["day"]) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(B["day"])]
    last = None
    eve = None
    weeks = collections.OrderedDict()
    for s, e in zip(starts, ends):
        di = int(B["day"][s])
        s0[di] = s
        mm = m[s:e]
        wk = dt.date.fromisoformat(B["dates"][di]).isocalendar()[:2]
        if last is not None:
            X["pdh"][di], X["pdl"][di] = last
        pre = np.where(mm < 570)[0] + s
        hs = [eve[0]] if eve else []
        ls = [eve[1]] if eve else []
        if len(pre):
            hs.append(float(h[pre].max())); ls.append(float(l[pre].min()))
        if hs:
            X["onh"][di], X["onl"][di] = max(hs), min(ls)
        if eve:
            X["eveh"][di], X["evel"][di] = eve
        prev_w = [w for w in weeks if w < wk]
        if prev_w:
            X["pwh"][di], X["pwl"][di] = weeks[prev_w[-1]]
        if wk in weeks:
            X["wkh0"][di], X["wkl0"][di] = weeks[wk]
        ev = np.where(mm >= 1080)[0] + s
        eve = (float(h[ev].max()), float(l[ev].min())) if len(ev) else None
        rth = np.where((mm >= 570) & (mm < 960))[0] + s
        if len(rth) >= 5:
            hi, lo = float(h[rth].max()), float(l[rth].min())
            last = (hi, lo)
            w = weeks.get(wk)
            weeks[wk] = (max(w[0], hi), min(w[1], lo)) if w else (hi, lo)
    X["s0"] = s0
    _S[k] = X
    return X


# ================================================================================================ candidates
WINDOWS = {"rth": (570, (630, 930), 30),        # today's: anchor 09:30 open, checks at the closes 11:00 ... 15:30
           "od": (570, (570, 645), 15),          # opening drive (new): checks at 09:45, 10:00, 10:15, 10:30
           "od30": (570, (570, 630), 30),        # opening drive, checks at 10:00 and 10:30
           "ldn": (180, (225, 510), 30)}         # London continuation (new): anchor 03:00 open, checks 04:00 ... 08:30


def _noise_anchor(B, anchor, end, lookback=14):
    """scalp_mo._noise for any anchor minute: sigma(minute) = mean over the prior `lookback` days of |close / anchor open - 1|
    at that minute; the reference open = the day's first bar at / after the anchor (bars anchor .. end)."""
    c, m, tf = B["c"], B["mod"], B["tf"]
    slots = np.arange(anchor, end, tf)
    hist = []
    sig = np.full(len(c), np.nan)
    op = np.full(len(c), np.nan)
    starts = np.r_[0, np.where(np.diff(B["day"]) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(B["day"])]
    for s, e in zip(starts, ends):
        idx = np.arange(s, e)
        r = idx[(m[idx] >= anchor) & (m[idx] < end)]
        if len(r) == 0:
            continue
        o0 = B["o"][r[0]]
        mv = np.full(len(slots), np.nan)
        pos = ((m[r] - anchor) // tf).astype(int)
        mv[pos] = np.abs(c[r] / o0 - 1)
        if len(hist) >= lookback:
            sg = np.nanmean(np.array(hist[-lookback:]), axis=0)
            sig[r] = sg[pos]
            op[r] = o0
        hist.append(mv)
    return sig, op


def _signals_win(B, wk):
    """candidates of window wk ("rth" = scalp_na_lib.signals; the others from _noise_anchor), with prng_ratio."""
    if wk == "rth":
        return N.signals(B, 1.0, 30, (630, 930), 1.5)
    k = ("sigw", wk, B["tf"], len(B["t"]))
    if k in _S:
        return _S[k]
    anchor, (w0, w1), every = WINDOWS[wk]
    end = 570 if anchor < 570 else 960
    sg, op = _noise_anchor(B, anchor, end)
    c, m = B["c"], B["mod"]
    ev = max(1, int(round(every / B["tf"])))
    up, lo = op * (1 + sg), op * (1 - sg)
    I = np.where((m >= w0) & (m < w1) & ~np.isnan(sg))[0]
    I = I[((m[I] + B["tf"] - anchor) // B["tf"]) % ev == 0]
    D = np.where(c[I] > up[I], 1.0, np.where(c[I] < lo[I], -1.0, 0.0))
    I, D = I[D != 0], D[D != 0]
    X = N._day_ctx(B)
    F = {"sig": I.astype(np.int64), "dir": D, "stop": c[I] - D * 1.5 * B["atr5"][I], "risk_pts": 1.5 * B["atr5"][I], "mod": m[I] + B["tf"],
         "day": B["day"][I], "prng_ratio": X["prng_ratio"][B["day"][I]], "_up": up, "_lo": lo}
    _S[k] = F
    return F


def base(B, filt="prng>=0.8", wins=("rth",)):
    """BLITZ's candidates (today's: window "rth" + the prior-day range filter) as a dict of arrays, bar order."""
    k = ("base", B["tf"], len(B["t"]), filt, tuple(wins))
    if k in _S:
        return _S[k]
    parts = []
    for wk in wins:
        F = _signals_win(B, wk)
        if filt == "prng>=0.8":
            m = F["prng_ratio"] >= 0.8
        elif filt in (None, "none"):
            m = np.ones(len(F["sig"]), bool)
        else:
            raise ValueError(filt)
        parts.append({kk: F[kk][m] for kk in ("sig", "dir")})
    I = np.concatenate([p["sig"] for p in parts]).astype(np.int64)
    D = np.concatenate([p["dir"] for p in parts])
    o = np.argsort(I, kind="stable")
    I, D = I[o], D[o]
    keep = np.r_[True, I[1:] != I[:-1]]            # one candidate per bar (windows do not overlap; safety)
    G = {"sig": I[keep], "dir": D[keep]}
    _S[k] = G
    return G


def _untaken(piv, B, i, t_from, ref, D):
    """untaken 5m pivots (confirmed by bar i, pivot bar started at / after t_from) beyond ref on the trade's side: prices."""
    out = []
    h, l = B["h"], B["l"]
    ts = piv["t"]
    a = int(np.searchsorted(ts, t_from, "left"))
    for z in range(a, len(ts)):
        ci = int(piv["ci"][z])
        if ci > i:
            break
        px = float(piv["p"][z])
        if D > 0 and px > ref:
            if h[ci + 1:i + 1].max(initial=-np.inf) < px:
                out.append(px)
        elif D < 0 and px < ref:
            if l[ci + 1:i + 1].min(initial=np.inf) > px:
                out.append(px)
    return out


def _target_levels(B, i, D, ref, mode, S, LV, cache):
    """sorted (nearest first) opposing liquidity levels beyond ref for a trade in direction D at signal bar i."""
    key = (i, D, mode)
    if key in cache:
        return cache[key]
    di = int(B["day"][i])
    s0 = int(LV["s0"][di])
    h, l, m, t = B["h"], B["l"], B["mod"], B["t"]
    seg = np.arange(s0, i + 1)
    rth = seg[m[seg] >= 570]
    hi_t = float(h[seg].max()) if len(seg) else ref                 # today's bars (from midnight) up to the signal
    lo_t = float(l[seg].min()) if len(seg) else ref
    eh, el = LV["eveh"][di], LV["evel"][di]
    hi_d = max(hi_t, eh) if eh == eh else hi_t                         # since the prior RTH close
    lo_d = min(lo_t, el) if el == el else lo_t
    rh = float(h[rth].max()) if len(rth) else -np.inf
    rl = float(l[rth].min()) if len(rth) else np.inf
    wh, wl = LV["wkh0"][di], LV["wkl0"][di]
    hi_w = max(hi_d, wh) if wh == wh else hi_d                         # this week so far
    lo_w = min(lo_d, wl) if wl == wl else lo_d
    lv = []
    for a, b, hh, ll in (("pdh", "pdl", hi_d, lo_d), ("onh", "onl", rh, rl), ("pwh", "pwl", hi_w, lo_w)):
        x = LV[a][di] if D > 0 else LV[b][di]
        if x == x:
            if D > 0 and x > ref and hh < x:
                lv.append(x)
            if D < 0 and x < ref and ll > x:
                lv.append(x)
    if len(rth):
        if D > 0 and rh > ref + TICK:
            lv.append(rh)
        if D < 0 and rl < ref - TICK:
            lv.append(rl)
    piv = S["piv_hi"] if D > 0 else S["piv_lo"]
    t_from = int(t[max(0, s0 - 1)]) - 3 * 86400
    sw = _untaken(piv, B, i, t_from, ref, D)
    if mode == "all":
        lv += sw
    elif mode == "eq":
        sw = sorted(sw)
        eq = [(min(a, b) if D > 0 else max(a, b)) for a, b in zip(sw[:-1], sw[1:]) if abs(b - a) <= 3.0]
        lv += eq
    elif mode == "major":
        pass
    lv = sorted(set(lv), key=lambda x: D * (x - ref))
    cache[key] = lv
    return lv


_TC = {}


def cands(B, v):
    """candidate arrays for variant v (keys of TODAY): sig, dir, stop, tgtA (partial limit), tgtB (runner limit)."""
    v = {**TODAY, **v}
    F = base(B, v["filter"], tuple(v["wins"]))
    I, D = F["sig"], F["dir"]
    c, h, l, a5 = B["c"], B["h"], B["l"], B["atr5"][F["sig"]]
    ref = c[I]
    st = v["stop"]
    if st == "atr":
        stop = ref - D * v["k"] * a5
    elif st in ("sw1", "sw5"):
        S = structure(B)
        hp, ht, lp, lt = S[st]
        stop = np.where(D > 0, lp[I] - TICK, hp[I] + TICK)
        # a swing on the wrong side of the close (price already back through it) -> the bar's own extreme
        bad = (D * (ref - stop) <= 0) | np.isnan(stop)
        stop = np.where(bad, np.where(D > 0, l[I] - TICK, h[I] + TICK), stop)
    elif st.startswith("low"):
        n = max(1, int(round(int(st[3:]) / B["tf"])))
        lo_n = np.array([l[max(0, i - n + 1):i + 1].min() for i in I])
        hi_n = np.array([h[max(0, i - n + 1):i + 1].max() for i in I])
        stop = np.where(D > 0, lo_n - TICK, hi_n + TICK)
    else:
        raise ValueError(st)
    dist = D * (ref - stop)
    keep = np.ones(len(I), bool)
    lo_d, hi_d = v["dmin"] * a5, v["dmax"] * a5
    stop = np.where(dist < lo_d, ref - D * lo_d, stop)
    dist = D * (ref - stop)
    keep &= dist <= hi_d
    tA = np.full(len(I), NAN)
    tB = np.full(len(I), NAN)
    if v["tgt"] == "liq" or v["part"] == "liq":
        S = structure(B)
        LV = levels_ctx(B)
        cache = _TC.setdefault((B["tf"], len(B["t"])), {})
        for q in range(len(I)):
            if not keep[q]:
                continue
            Lv = _target_levels(B, int(I[q]), D[q], ref[q], v["liq"], S, LV, cache)
            rq = dist[q]
            ds = [D[q] * (x - ref[q]) / rq for x in Lv]
            if v["part"] == "liq":
                a_ = [x for x, d in zip(Lv, ds) if d >= v["p_min"]]
                if a_:
                    tA[q] = a_[0] - D[q] * TICK
                    if v["tgt"] == "liq":
                        b_ = [x for x, d in zip(Lv, ds) if d >= max(v["r_min"], D[q] * (a_[0] - ref[q]) / rq + 0.25) and d <= v["r_max"]]
                        if b_:
                            tB[q] = b_[0] - D[q] * TICK
            elif v["tgt"] == "liq":
                b_ = [x for x, d in zip(Lv, ds) if v["r_min"] <= d <= v["r_max"]]
                if b_:
                    tB[q] = b_[0] - D[q] * TICK
                elif v.get("need_tgt"):
                    keep[q] = False
    elif v["tgt"] is not None and isinstance(v["tgt"], (int, float)):
        tB = ref + D * float(v["tgt"]) * dist
    if v["part"] is not None and isinstance(v["part"], (int, float)):
        tA = ref + D * float(v["part"]) * dist
    lim = np.full(len(I), NAN)
    if v["lim"] is not None:
        if v["lim"] == "band":
            F0 = _signals_win(B, "rth")
            lim = np.where(D > 0, F0["_up"][I], F0["_lo"][I])
        else:
            lim = ref - D * float(v["lim"]) * a5          # a retest of x 5m-ATR from the signal close
    mult = np.ones(len(I))
    if v.get("sfilter"):
        mode, mins = v["sfilter"]                        # ("with" | "not_against" | "size", 15 | 60)
        sv = htf_state(B, mins)[I]
        al = sv * D
        if mode == "with":
            keep &= al > 0
        elif mode == "not_against":
            keep &= al >= 0
        elif mode == "size":                             # prefer a size change over skipping: half size against the structure
            mult = np.where(al < 0, float(v.get("s_mult", 0.5)), 1.0)
    return {"sig": I[keep], "dir": D[keep], "stop": stop[keep], "tgtA": tA[keep], "tgtB": tB[keep], "lim": lim[keep], "q": np.where(keep)[0],
            "mult": mult[keep]}


# ================================================================================================ account C (no hedge across own accounts)
_AC = {}


def _other_trades(mode):
    """day -> [(start epoch, end epoch, dir)] of what BLITZ must never be opposite to. mode: "lit+atlas" (positions),
    "lit" / "atlas" alone, "lit+atlas+armed" (also LIT's armed setups)."""
    if mode in _AC:
        return _AC[mode]
    from tools import scalp_na_combo as C
    by = collections.defaultdict(list)
    if "lit" in mode:
        for d, ts in C.lit_by_day().items():
            by[d] += list(ts)
    if "atlas" in mode:
        for d, ts in C.atlas_by_day().items():
            by[d] += list(ts)
    if "armed" in mode:
        for d, ws in N.lit_armed().items():
            for dr, a, z in ws:
                dd = dr if isinstance(dr, (int, float)) else (1 if str(dr).lower().startswith("l") else -1)
                by[d].append((int(a), int(z), int(np.sign(dd))))
    _AC[mode] = by
    return by


def account_c(B, mode="lit+atlas"):
    """per-bar arrays: hold_long / hold_short (another account holds that side at the bar's open) and cut_long / cut_short
    (an entry of that side at / before this bar's open since the previous bar's open: BLITZ's opposite trade is closed at this
    bar's open). None = BLITZ alone."""
    if not mode or mode == "alone":
        return None
    k = (mode, B["tf"], len(B["t"]))
    if k in _AC:
        return _AC[k]
    t = B["t"]
    n = len(t)
    hl, hs = np.zeros(n, np.bool_), np.zeros(n, np.bool_)
    cl, cs = np.zeros(n, np.bool_), np.zeros(n, np.bool_)
    for d, ts in _other_trades(mode).items():
        for a, z, dr in ts:
            i0 = int(np.searchsorted(t, a, "left"))       # first bar opening at / after the start
            i1 = int(np.searchsorted(t, z, "left"))
            if i0 >= n:
                continue
            if dr > 0:
                cl[i0] = True
                # holds at bar opens a <= t[i] < z  (+ the bar containing a: an entry inside a bar blocks the next open)
                hl[i0:max(i0, i1)] = True
            else:
                cs[i0] = True
                hs[i0:max(i0, i1)] = True
    _AC[k] = (hl, hs, cl, cs)
    return _AC[k]


# ================================================================================================ executor
@njit(cache=True)
def _sim(o, h, l, c, t, flat, day, mod, sig, dr, stop0, tgA, tgB, hold, trail_r, trail_st, be_r, be_off, part_be, sw_mode, sw_start,
         ch_mode, s1hp, s1ht, s1lp, s1lt, s5hp, s5ht, s5lp, s5lt, maxday, day_stop_r, last_mod, tick, use_c, hl, hs, cl, cs, late,
         lim, lim_w):
    n = len(sig)
    out = np.zeros((n, 20))
    k = 0
    busy = -1
    cur = -1
    dn = 0
    dR = 0.0
    for q in range(n):
        s = sig[q] + late
        d = day[sig[q]]
        if d != cur:
            cur = d; dn = 0; dR = 0.0
        if s < busy:
            continue
        if dn >= maxday or dR <= -day_stop_r:
            continue
        fe = flat[sig[q]]
        if s + 1 > fe or mod[sig[q]] > last_mod:
            continue
        D = dr[q]
        j = s + 1
        lm = lim[q]
        limfill = False
        fillp = 0.0
        if lm == lm:
            # retest entry: a limit at lm works lim_w bars; filled when traded through by 1 tick (or gapped through at the open)
            jf = -1
            for jj in range(s + 1, min(s + 1 + lim_w, fe + 1)):
                if (D > 0 and o[jj] <= lm) or (D < 0 and o[jj] >= lm):
                    jf = jj; fillp = o[jj]
                    break
                if (D > 0 and l[jj] <= lm - tick) or (D < 0 and h[jj] >= lm + tick):
                    jf = jj; fillp = lm
                    break
            if jf < 0:
                busy = min(s + lim_w, fe)
                continue
            j = jf
            limfill = True
        if use_c:
            if (D > 0 and hs[j]) or (D < 0 and hl[j]):
                continue                       # another account holds the other side: never opposite
        st = stop0[q]
        fill = fillp if limfill else o[j] + D * tick
        risk = D * (fill - st)
        if risk < tick:
            busy = j
            continue
        ta = tgA[q]
        tb = tgB[q]
        if ta == ta and D * (ta - fill) <= tick:
            ta = np.nan                         # the partial level is already reached at the fill
        if tb == tb and D * (tb - fill) <= tick:
            tb = np.nan
        stp = st
        ext = fill
        mae = 0.0
        maeA = 0.0
        xA = -1
        pA = 0.0
        kA = 0
        xk = -1
        xp = 0.0
        xkind = 0
        tj = t[j]
        dl = j + hold if hold > 0 else fe + 1
        for i in range(j, fe + 1):
            first = i == j
            if not first and use_c and ((D > 0 and cs[i]) or (D < 0 and cl[i])):
                xp = o[i] - D * tick; xk = i; xkind = 5
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 5; maeA = mae
                mae = max(mae, D * (fill - xp))
                break
            if not first and ((D > 0 and o[i] <= stp) or (D < 0 and o[i] >= stp)):
                xp = o[i] - D * tick; xk = i; xkind = 1
                mae = max(mae, D * (fill - xp))
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 1; maeA = mae
                break
            if xA < 0 and ta == ta and not first and ((D > 0 and o[i] >= ta + tick) or (D < 0 and o[i] <= ta - tick)):
                xA = i; pA = D * (o[i] - fill); kA = 2; maeA = mae
                if part_be and D * (fill + D * be_off - stp) > 0:
                    stp = fill + D * be_off
            if tb == tb and not first and ((D > 0 and o[i] >= tb + tick) or (D < 0 and o[i] <= tb - tick)):
                xp = o[i]; xk = i; xkind = 2
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 2; maeA = mae
                break
            adv = (fill - l[i]) if D > 0 else (h[i] - fill)
            hit = (l[i] <= stp) if D > 0 else (h[i] >= stp)
            if hit:
                xp = stp - D * tick; xk = i; xkind = 1
                mae = max(mae, D * (fill - xp))
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 1; maeA = mae
                break
            mae = max(mae, adv)
            if xA < 0 and ta == ta and not (first and limfill) and ((D > 0 and h[i] >= ta + tick) or (D < 0 and l[i] <= ta - tick)):
                xA = i; pA = D * (ta - fill); kA = 2; maeA = mae
                if part_be and D * (fill + D * be_off - stp) > 0:
                    stp = fill + D * be_off
            if tb == tb and not (first and limfill) and ((D > 0 and h[i] >= tb + tick) or (D < 0 and l[i] <= tb - tick)):
                xp = tb; xk = i; xkind = 2
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 2; maeA = mae
                break
            if i >= fe:
                xp = c[i] - D * tick; xk = i; xkind = 4
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 4; maeA = mae
                break
            if hold > 0 and i >= dl:
                xp = c[i] - D * tick; xk = i; xkind = 3
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 3; maeA = mae
                break
            # change of character: a close beyond the last swing that formed after the entry
            if ch_mode > 0:
                if ch_mode == 1:
                    sp_ = s1lp[i] if D > 0 else s1hp[i]
                    stt = s1lt[i] if D > 0 else s1ht[i]
                else:
                    sp_ = s5lp[i] if D > 0 else s5hp[i]
                    stt = s5lt[i] if D > 0 else s5ht[i]
                if stt >= tj and sp_ == sp_ and ((D > 0 and c[i] < sp_) or (D < 0 and c[i] > sp_)):
                    xp = c[i] - D * tick; xk = i; xkind = 6
                    if xA < 0:
                        xA = i; pA = D * (xp - fill); kA = 6; maeA = mae
                    break
            if first and limfill:
                ext = max(ext, c[i]) if D > 0 else min(ext, c[i])     # the bar's extreme may have come before the fill
            elif D > 0:
                ext = max(ext, h[i])
            else:
                ext = min(ext, l[i])
            mfe = D * (ext - fill)
            if be_r == be_r and mfe >= be_r * risk:
                nb = fill + D * be_off
                if D * (nb - stp) > 0:
                    stp = nb
            if trail_r == trail_r and mfe >= trail_st * risk:
                nt = ext - D * trail_r * risk
                if D * (nt - stp) > 0:
                    stp = nt
            if sw_mode > 0 and mfe >= sw_start * risk:
                if sw_mode == 1:
                    sp_ = s1lp[i] if D > 0 else s1hp[i]
                    stt = s1lt[i] if D > 0 else s1ht[i]
                else:
                    sp_ = s5lp[i] if D > 0 else s5hp[i]
                    stt = s5lt[i] if D > 0 else s5ht[i]
                if stt >= tj and sp_ == sp_:
                    ns = sp_ - D * tick
                    if D * (ns - stp) > 0 and D * (c[i] - ns) > 0:
                        stp = ns
        pts = D * (xp - fill)
        if xA < 0:
            xA = xk; pA = pts; kA = xkind; maeA = mae
        out[k, 0] = s; out[k, 1] = j; out[k, 2] = xk; out[k, 3] = D; out[k, 4] = fill; out[k, 5] = st
        out[k, 6] = xp; out[k, 7] = xkind; out[k, 8] = pts; out[k, 9] = risk; out[k, 10] = mae; out[k, 11] = q
        out[k, 12] = xA; out[k, 13] = pA; out[k, 14] = kA; out[k, 15] = maeA; out[k, 16] = 0
        out[k, 17] = D * (ext - fill)
        out[k, 18] = D * (tb - fill) if tb == tb else np.nan
        out[k, 19] = D * (ta - fill) if ta == ta else np.nan
        k += 1
        busy = max(xk, xA)
        dn += 1
        r = (pts * 2.0 - 1.9) / ((risk + tick) * 2.0 + 1.9)
        if ta == ta:
            rA = (pA * 2.0 - 1.9) / ((risk + tick) * 2.0 + 1.9)
            r = 0.5 * (r + rA)
        dR += r
    return out[:k]


XK = {1: "stop", 2: "target", 3: "time", 4: "flat", 5: "hedge", 6: "choch"}


def run(B, v=None, cmode=None, placebo=None):
    """BLITZ trades (scalp_na_lib.run rows) of variant v on bars B; cmode = account_c mode (None = alone); placebo = seed: the
    same candidate bars with a coin-flip side (stop and targets mirrored at the same distances)."""
    v = {**TODAY, **(v or {})}
    K = cands(B, v)
    if placebo is not None:
        rng = np.random.default_rng(placebo)
        nd = rng.choice([-1.0, 1.0], len(K["sig"]))
        ref = B["c"][K["sig"]]
        flip = nd != K["dir"]
        K = {**K, "dir": nd, "stop": np.where(flip, 2 * ref - K["stop"], K["stop"]), "tgtA": np.where(flip, 2 * ref - K["tgtA"], K["tgtA"]),
             "tgtB": np.where(flip, 2 * ref - K["tgtB"], K["tgtB"]), "lim": np.where(flip, 2 * ref - K["lim"], K["lim"])}
    S = structure(B)
    AC = account_c(B, cmode)
    use_c = AC is not None
    z = np.zeros(1, np.bool_)
    hl, hs, cl, cs = AC if use_c else (z, z, z, z)
    hold = int(round(v["hold"] / B["tf"])) if v["hold"] else 0
    pa = v["part"] is not None
    X = _sim(B["o"], B["h"], B["l"], B["c"], B["t"], B["flat"], B["day"], B["mod"], K["sig"].astype(np.int64), K["dir"].astype(np.float64),
             K["stop"].astype(np.float64), K["tgtA"].astype(np.float64), K["tgtB"].astype(np.float64), hold,
             float(v["trail"]) if v["trail"] else NAN, float(v["tstart"]), float(v["be"]) if v["be"] else NAN, float(v["be_off"]),
             bool(v["part_be"]), int(v["sw_trail"]), float(v["sw_start"]), int(v["choch"]), *S["sw1"], *S["sw5"], int(v["maxday"]),
             float(v["day_stop"]), int(v["last_mod"]), TICK, use_c, hl, hs, cl, cs, int(v["late"]), K["lim"].astype(np.float64),
             max(1, int(round(v["lim_w"] / B["tf"]))))
    T = []
    pf = float(v["part_f"]) if pa else 0.0
    for r in X:
        s, j, xk = int(r[0]), int(r[1]), int(r[2])
        pts, risk, mae = float(r[8]), float(r[9]), float(r[10])
        ptsA, maeA = float(r[13]), float(r[15])
        t = {"day": B["dates"][B["day"][j]], "sig_t": int(B["t"][s]), "entry_t": int(B["t"][j]),
             "exit_t": int(B["t"][max(xk, int(r[12]))]) + 60 * B["tf"], "dir": int(r[3]), "entry": float(r[4]), "stop": float(r[5]),
             "exit": float(r[6]), "exit_kind": XK.get(int(r[7]), "?"), "pts": round(pts, 2), "risk_pts": round(risk, 2),
             "mae_pts": round(mae, 2), "mfe_pts": round(float(r[17]), 2), "bars": xk - j + 1, "ext": 0, "q": int(K["q"][int(r[11])]),
             "pnl_pm": pts * PV - COMM, "risk_pm": (risk + TICK) * PV + COMM, "mae_pm": -mae * PV - COMM, "kind": 0,
             "mult": float(K["mult"][int(r[11])])}
        tg = float(r[18])
        t["rew_pm"] = tg * PV - COMM if tg == tg else None
        if pf and r[19] == r[19]:
            t.update(ptsA=round(ptsA, 2), pnlA_pm=ptsA * PV - COMM, maeA_pm=-maeA * PV - COMM, part_f=pf, kindA=XK.get(int(r[14]), "?"))
            t["pnl_pm"] = pf * t["pnlA_pm"] + (1 - pf) * t["pnl_pm"]
        T.append(t)
    return T


# ================================================================================================ sizing ("tneed": one winner passes)
def qty(t, room, cum, bal, P, sz):
    """scalp_na_lib.qty + mode "tneed": micros = what the eval still needs / the target's $ a micro (rounded up), capped by
    f x room / the $ cap / 0.9 x the soft daily loss left; a trade without a target falls back to f x room."""
    mu = t.get("mult", 1.0)
    if mu != 1.0 and sz.get("mode") in ("frac", "need", "tneed"):
        sz = {**sz, "f": float(sz["f"]) * mu, "cap": float(sz["cap"]) * mu}
    if sz.get("mode") != "tneed" or not t.get("rew_pm"):
        z = sz if sz.get("mode") != "tneed" else {**sz, "mode": "frac"}
        return _NQTY(t, room, cum, bal, P, z)
    dll_left = P["dll"] + cum
    b = min(float(sz["cap"]), float(sz["f"]) * room, 0.9 * dll_left)
    if b <= 0:
        return 0
    qmax = int(min(P["maxq"], b // t["risk_pm"]))
    if qmax == 0 and t["risk_pm"] <= min(0.5 * room, 0.9 * dll_left):
        qmax = 1
    need = P.get("target", 1e9) - (bal + cum)
    if need <= 0 or t["rew_pm"] <= 0:
        return min(qmax, 1)
    qn = int(np.ceil(need / t["rew_pm"]))
    return max(1 if qmax else 0, min(qmax, max(qn, int(sz.get("qmin", 1)))))


def install_qty():
    """route scalp_na_lib's simulators (its Funded / eval / life) through qty() above: the "tneed" mode and the per-trade size
    multiplier "mult"; with mult 1 and the old modes it is scalp_na_lib.qty unchanged."""
    if N.qty is not qty:
        N.qty = qty


# ================================================================================================ helpers
SPANS = (("H1", 1), ("H2", 1), ("R", 5))


def trades(v=None, cmode=None, placebo=None):
    """{1: 1m trades (2026), 5: 5m trades (2021-25 used)}"""
    return {tf: run(N.bars(tf), v, cmode, placebo) for tf in (1, 5)}


def span(TT, sp, tf):
    B = N.bars(tf)
    S = N.sessions(B, sp)
    return N.span_trades(TT[tf], S), S


def lines(TT, risk_usd=150.0, spans=SPANS):
    out = {}
    for sp, tf in spans:
        T, S = span(TT, sp, tf)
        if any(t.get("mult", 1.0) != 1.0 for t in T):
            # a size multiplier: the trade risks mult x risk_usd (priced as risk_pm / mult a micro for the integer sizing)
            Tm = [{**t, "pnl_pm": t["pnl_pm"], "risk_pm": t["risk_pm"] / t.get("mult", 1.0)} for t in T]
            o = N.stats(Tm, S, risk_usd, 20)
            R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
            o["avg_r"] = round(float(R.mean()), 3)
            out[sp] = o
        else:
            out[sp] = N.stats(T, S, risk_usd, 20)
        out[sp]["wk2"] = wk2(T, S)
        ks = collections.Counter(t["exit_kind"] for t in T)
        out[sp]["exits"] = {k_: round(100.0 * v_ / max(1, len(T)), 1) for k_, v_ in ks.items()}
    return out


def wk2(T, S):
    """% of weeks with 2+ trades."""
    weeks = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in T)
    allw = {dt.date.fromisoformat(d).isocalendar()[:2] for d in S}
    return round(100.0 * sum(1 for w in allw if weeks.get(w, 0) >= 2) / max(1, len(allw)), 1)
