"""BLITZ research library (owner 2026-10-28: turn the noise-area (NA) momentum scalp into something that pays on MFFU).

Research only. Nothing here is imported by the engine. Builds on tools/scalp_mo_lib.py (bars, costs, MFFU rules) and
tools/scalp_mo.py (_noise: the time-of-day noise band from the 09:30 open, 14 prior sessions).

  signals(B, vm, every, win, stopk)  every NA candidate (bar close beyond the band at a check bar) + its features, all
                                     known at the signal bar's close (VIX/VXN = the prior session's close; first hour =
                                     09:30-10:30, complete at the first 10:30 check; ES 5m bar closing at the same time;
                                     LIT = trades / armed setups that started before the signal; news = the day's calendar)
  run(B, p, mask)                    numba executor (same fills as scalp_mo_lib._sim: market next open + 1 tick, stop - 1
                                     tick or the gapped open, limits only when traded through by 1 tick, same-bar tie =
                                     loss, time / 15:55 exit at the close - 1 tick) with a 2-leg option: leg A = part_f of
                                     the micros with a limit at +part_r R, leg B = the runner (trail / BE / time); "ext" =
                                     at the time limit a check bar still beyond the band keeps the trade until the next
                                     check (Zarattini-style hold), max ext_max extensions.
  eval_score / funded_score          MFFU Builder 25K / 50K (scalp_mo_lib.PLANS / FUNDED): size rules frac (f x room, $
                                     cap), need (what is still needed to pass / k, capped), fixed $; a daily $ target stop
                                     (no new trade once the day made +$X); the soft daily loss; intraday floor breach on
                                     the trade's worst open loss; p10/f10, dec10, p15/f15, pass_med, slow_pass, the
                                     back-to-back eval path $ and the funded $ / month to the owner (80%).
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
from numba import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import scalp_mo_lib as L  # noqa: E402
from tools import scalp_mo as SM  # noqa: E402

ET = ZoneInfo("America/New_York")
TICK, PV, COMM = L.TICK, L.PV, L.COMM
SPANS = L.SPANS
PLANS = L.PLANS
FUNDED = L.FUNDED
LEDGER = os.path.join(ROOT, "research", "handoff", "2026-10-25", "COMPLETE_TRADE_LEDGER.csv")

# the scalp_mo pick "na_scalp" (research/writeups/scalp-momentum.md)
BASE = {"vm": 1.0, "every": 30, "stopk": 1.5, "win": (630, 930), "hold": 30, "trail": 1.5, "tstart": 1.0, "be": None,
        "be_off": 0.25, "part_r": None, "part_f": 0.5, "part_be": False, "ext": 0, "maxday": 6, "day_stop": 3.0, "day_tp": 99.0}


# ================================================================================================ day-level context
_M = {}


def _daily(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                out[str(r["date"])[:10]] = float(r["close"])
            except (ValueError, KeyError):
                pass
    ks = sorted(out)
    return ks, [out[k] for k in ks]


def prev_close(name, day):
    """The prior session's close (VIX / VXN), known before the day opens."""
    if name not in _M:
        _M[name] = _daily(os.path.join(ROOT, "data", f"{name}_1d.csv"))
    ks, vs = _M[name]
    k = bisect.bisect_left(ks, day) - 1
    return vs[k] if k >= 0 else np.nan


def prev_rel(name, day, n=20):
    """Prior close / mean of the n closes before it (vol regime vs its own recent level)."""
    if name not in _M:
        _M[name] = _daily(os.path.join(ROOT, "data", f"{name}_1d.csv"))
    ks, vs = _M[name]
    k = bisect.bisect_left(ks, day) - 1
    if k < n:
        return np.nan
    return vs[k] / float(np.mean(vs[k - n:k]))


def news_days():
    """day -> set of high-impact releases (CPI, NFP, FOMC, PCE/GDP; tools/hq_habits calendar rules, in memory)."""
    if "news" in _M:
        return _M["news"]
    from tools import hq_habits as HQ
    by = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")):
        if r["event"] in HQ.KEEP:
            by[r["date"]].add("FOMC" if "FOMC" in r["event"] else r["event"].split(" ")[0])
    for d, tm, ev in HQ.BEA_2026:
        by[d].add("PCE")
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "ff_archive.csv"), encoding="utf-8")):
        if r["event"] == "CPI m/m":
            by[r["date"]].add("CPI")
    for y in range(2021, 2024):
        for m in range(1, 13):
            d = HQ.nfp_rule(y, m)
            if d < dt.date(2023, 10, 1):
                by[d.isoformat()].add("Non-Farm")
    _M["news"] = by
    return by


def lit_trades():
    """The live LIT trades (2026: run lit_live, true 1m fills; 2021-25: the 5m REF rows) from the 2026-10-25 ledger:
    day -> [(entry epoch, exit epoch, dir)]."""
    if "lit" in _M:
        return _M["lit"]
    by = collections.defaultdict(list)
    for r in csv.DictReader(open(LEDGER, encoding="utf-8")):
        if not r["trade_id"].startswith(("T-2026", "REF-")):
            continue
        e = int(dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp())
        x = int(dt.datetime.fromisoformat(r["exit_time"][:25]).timestamp())
        by[r["entry_fill_at"][:10]].append((e, x, 1 if r["direction"] == "long" else -1))
    _M["lit"] = by
    return by


def lit_armed():
    if "arm" not in _M:
        from tools import atlas_lit_armed as ARM
        _M["arm"] = ARM.by_day()
    return _M["arm"]


# ================================================================================================ ES 5m noise band
def es_band():
    """ES 5m (2025-04-14 on): bar END epoch -> (close, 09:30 open, sigma at that slot) for the ES noise band."""
    if "es" in _M:
        return _M["es"]
    import pandas as pd
    e = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
    et = pd.to_datetime(e.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    e["date"] = et.dt.strftime("%Y-%m-%d")
    e["mod"] = et.dt.hour * 60 + et.dt.minute
    out = {}
    hist = []
    slots = np.arange(570, 960, 5)
    for d, g in e.groupby("date", sort=True):
        r = g[(g["mod"] >= 570) & (g["mod"] < 960)]
        if len(r) < 10:
            continue
        o0 = float(r.open.iloc[0])
        mv = np.full(len(slots), np.nan)
        pos = ((r["mod"].to_numpy() - 570) // 5).astype(int)
        mv[pos] = np.abs(r.close.to_numpy() / o0 - 1)
        if len(hist) >= 14:
            sg = np.nanmean(np.array(hist[-14:]), axis=0)
            for tt, cc, p in zip(r.time.to_numpy(), r.close.to_numpy(), pos):
                out[int(tt) + 300] = (float(cc), o0, float(sg[p]))
        hist.append(mv)
    _M["es"] = out
    return out


# ================================================================================================ signals + features
_SIG = {}


def _noise(B):
    k = ("noise", B["tf"], len(B["t"]))
    if k not in _SIG:
        _SIG[k] = SM._noise(B)
    return _SIG[k]


def _day_ctx(B):
    """per day id: 09:30 open, prior RTH close/high/low, 14-day mean RTH range, Asia box (prior date 18:00-24:00), first
    hour (ratio to the 20-day mean, close position), first-hour end index."""
    k = ("ctx", B["tf"], len(B["t"]))
    if k in _SIG:
        return _SIG[k]
    m, o, h, l, c = B["mod"], B["o"], B["h"], B["l"], B["c"]
    nd = len(B["dates"])
    X = {nm: np.full(nd, np.nan) for nm in ("o930", "pc", "ph", "pl", "rng14", "ah", "al", "fh_ratio", "fh_pos", "fh_end",
                                             "prng_ratio")}
    starts = np.r_[0, np.where(np.diff(B["day"]) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(B["day"])]
    rngs, fhr = [], []
    last = None          # (rth close, high, low) of the previous date with RTH bars
    asia = None          # (high, low) of the previous date's 18:00-24:00 bars
    for s, e in zip(starts, ends):
        di = int(B["day"][s])
        mm = m[s:e]
        rth = np.where((mm >= 570) & (mm < 960))[0] + s
        if last is not None:
            X["pc"][di], X["ph"][di], X["pl"][di] = last
        if asia is not None:
            X["ah"][di], X["al"][di] = asia
        if len(rngs) >= 10:
            X["rng14"][di] = float(np.mean(rngs[-14:]))
        ev = np.where(mm >= 1080)[0] + s
        asia = (float(h[ev].max()), float(l[ev].min())) if len(ev) else None
        if len(rth) < 5:
            continue
        X["o930"][di] = o[rth[0]]
        fh = rth[m[rth] < 630]
        if len(fh) >= 3:
            hi, lo = h[fh].max(), l[fh].min()
            rg = hi - lo
            if len(fhr) >= 10:
                X["fh_ratio"][di] = rg / float(np.mean(fhr[-20:]))
            X["fh_pos"][di] = (c[fh[-1]] - lo) / rg if rg > 0 else 0.5
            X["fh_end"][di] = fh[-1]
            fhr.append(rg)
        hi, lo = float(h[rth].max()), float(l[rth].min())
        if len(rngs) >= 10:
            X["prng_ratio"][di] = (last[1] - last[2]) / float(np.mean(rngs[-14:])) if last is not None else np.nan
        rngs.append(hi - lo)
        last = (float(c[rth[-1]]), hi, lo)
    _SIG[k] = X
    return X


def signals(B, vm=1.0, every=30, win=(630, 930), stopk=1.5, first_only=False):
    """NA candidates (scalp_mo.fam_na with stop 'a5x<stopk>') + features. Returns dict of arrays (one row per candidate,
    in bar order; long before short on the same bar - only one side can be true)."""
    key = ("sig", B["tf"], len(B["t"]), vm, every, tuple(win), stopk)
    if key in _SIG:
        return _SIG[key]
    sg, op = _noise(B)
    c, m = B["c"], B["mod"]
    ev = max(1, int(round(every / B["tf"])))
    up = op * (1 + vm * sg)
    lo = op * (1 - vm * sg)
    w0, w1 = win
    I = np.where((m >= w0) & (m < w1) & ~np.isnan(sg))[0]
    I = I[((m[I] + B["tf"] - 570) // B["tf"]) % ev == 0]
    rows_i, rows_d = [], []
    for i in I:
        if c[i] > up[i]:
            rows_i.append(i); rows_d.append(1)
        elif c[i] < lo[i]:
            rows_i.append(i); rows_d.append(-1)
    I = np.array(rows_i, np.int64)
    D = np.array(rows_d, np.float64)
    a5 = B["atr5"][I]
    F = {"sig": I, "dir": D, "stop": c[I] - D * stopk * a5, "risk_pts": stopk * a5, "mod": m[I] + B["tf"],
         "day": B["day"][I]}
    X = _day_ctx(B)
    dd = F["day"]
    dates = B["dates"][dd]
    F["date"] = dates
    F["dow"] = B["dow"][I]
    F["vix"] = np.array([prev_close("VIX", d) for d in dates])
    F["vxn"] = np.array([prev_close("VXN", d) for d in dates])
    F["vxn_rel"] = np.array([prev_rel("VXN", d) for d in dates])
    F["vix_rel"] = np.array([prev_rel("VIX", d) for d in dates])
    o930 = X["o930"][dd]
    F["gap"] = (o930 - X["pc"][dd]) / X["rng14"][dd]            # gap in units of the 14-day mean RTH range
    F["gap_with"] = np.sign(o930 - X["pc"][dd]) * D               # +1 the gap is on the trade's side
    F["fh_ratio"] = X["fh_ratio"][dd]
    fp = X["fh_pos"][dd]
    F["fh_with"] = np.where(D > 0, fp, 1 - fp)                    # 1 = the first hour closed at the trade's extreme
    F["prng_ratio"] = X["prng_ratio"][dd]
    F["exc"] = D * (c[I] - op[I]) / (op[I] * sg[I])               # move from the open in sigmas (>= vm)
    F["band_atr"] = op[I] * sg[I] / a5                            # band half-width vs the 5m ATR
    F["vwap_with"] = np.sign(c[I] - B["vwap"][I]) * D
    F["h1_with"] = np.sign(B["h1_sl20"][I]) * D
    F["m15_with"] = np.sign(B["m15_sl20"][I]) * D
    # nth signal of the day in this direction / any (1 = first)
    nth = np.zeros(len(I)); seen = collections.Counter()
    for q in range(len(I)):
        seen[(dd[q], D[q])] += 1
        nth[q] = seen[(dd[q], D[q])]
    F["nth"] = nth
    # draw_pd: nearer untaken prior RTH high / low on the trade's side (+1), the other side (-1); amd: Asia box taken
    dpd = np.zeros(len(I)); amd = np.zeros(len(I))
    starts = {}
    for q, i in enumerate(I):
        di = int(dd[q])
        if di not in starts:
            starts[di] = int(np.searchsorted(B["day"], di))
        s = starts[di]
        hi, lw = float(B["h"][s:i + 1].max()), float(B["l"][s:i + 1].min())
        ph, pl = X["ph"][di], X["pl"][di]
        if ph == ph:
            upd = abs(ph - c[i]) if not hi > ph else np.inf
            dnd = abs(c[i] - pl) if not lw < pl else np.inf
            if np.isfinite(upd) or np.isfinite(dnd):
                dpd[q] = (1 if upd < dnd else -1) * D[q]
        ah, al = X["ah"][di], X["al"][di]
        if ah == ah:
            th, tl = hi > ah, lw < al
            if th != tl:
                amd[q] = D[q] if tl else -D[q]
    F["draw_with"] = dpd
    F["amd_with"] = amd
    # news
    N = news_days()
    F["news"] = np.array([1.0 if N.get(d) else 0.0 for d in dates])
    F["fomc"] = np.array([1.0 if "FOMC" in N.get(d, ()) else 0.0 for d in dates])
    # ES at the same bar close (5m ES bar ending at the NQ bar's end)
    E = es_band()
    tend = B["t"][I] + 60 * B["tf"]
    esl, ess, esr = np.full(len(I), np.nan), np.full(len(I), np.nan), np.full(len(I), np.nan)
    for q in range(len(I)):
        x = E.get(int(tend[q]))
        if x is None:
            continue
        cc, o0, s_ = x
        mv = (cc / o0 - 1) / s_ if s_ > 0 else 0.0
        esl[q] = np.sign(cc - o0) * D[q]
        ess[q] = 1.0 if D[q] * mv > vm else 0.0
        esr[q] = F["exc"][q] - D[q] * mv                       # NQ's move in sigmas minus ES's (+ = NQ leads)
    F["es_with"], F["es_out"], F["es_rel"] = esl, ess, esr
    # LIT (live trades + armed setups) known at the signal close
    LT, AW = lit_trades(), lit_armed()
    lit_dir = np.zeros(len(I)); lit_open = np.zeros(len(I)); lit_arm = np.zeros(len(I)); lit_any = np.zeros(len(I))
    for q in range(len(I)):
        d, T0 = dates[q], int(tend[q])
        ts = LT.get(d, ())
        lit_any[q] = 1.0 if ts else 0.0
        before = [x for x in ts if x[0] <= T0]
        if before:
            lit_dir[q] = before[-1][2] * D[q]
        lit_open[q] = 1.0 if any(e <= T0 < x for e, x, _ in ts) else 0.0
        lit_arm[q] = 1.0 if any(a <= T0 < z for _, a, z in AW.get(d, ())) else 0.0
    F["lit_with"], F["lit_open"], F["lit_arm"], F["lit_day"] = lit_dir, lit_open, lit_arm, lit_any
    # band arrays for the "ext" exit
    F["_up"], F["_lo"] = up, lo
    _SIG[key] = F
    return F


# ================================================================================================ executor
@njit(cache=True)
def _sim(o, h, l, c, flat, day, mod, isck, up, lo, sig, dr, stop0, hold, trail_r, trail_st, be_r, be_off, part_r, part_be,
         ext_max, maxday, day_stop_r, day_tp_r, last_mod, tick):
    n = len(sig)
    out = np.zeros((n, 20))
    k = 0
    busy = -1
    cur = -1
    dn = 0
    dR = 0.0
    for q in range(n):
        s = sig[q]
        d = day[s]
        if d != cur:
            cur = d; dn = 0; dR = 0.0
        if s < busy:
            continue
        if dn >= maxday or dR <= -day_stop_r or dR >= day_tp_r:
            continue
        fe = flat[s]
        if s + 1 > fe or mod[s] > last_mod:
            continue
        D = dr[q]
        st = stop0[q]
        j = s + 1
        fill = o[j] + D * tick
        risk = D * (fill - st)
        if risk < tick:
            busy = j
            continue
        tgA = fill + D * part_r * risk if part_r == part_r else np.nan
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
        nx = 0
        dl = j + hold
        for i in range(j, fe + 1):
            first = i == j
            # gap through the stop at the open
            if not first and ((D > 0 and o[i] <= stp) or (D < 0 and o[i] >= stp)):
                xp = o[i] - D * tick; xk = i; xkind = 1
                mae = max(mae, D * (fill - xp))
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 1; maeA = mae
                break
            if xA < 0 and tgA == tgA and not first and ((D > 0 and o[i] >= tgA + tick) or (D < 0 and o[i] <= tgA - tick)):
                xA = i; pA = D * (o[i] - fill); kA = 2; maeA = mae
                if part_be and D * (fill + D * be_off - stp) > 0:
                    stp = fill + D * be_off
            adv = (fill - l[i]) if D > 0 else (h[i] - fill)
            hit = (l[i] <= stp) if D > 0 else (h[i] >= stp)
            if hit:
                xp = stp - D * tick; xk = i; xkind = 1
                mae = max(mae, D * (fill - xp))
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 1; maeA = mae
                break
            mae = max(mae, adv)
            if xA < 0 and tgA == tgA and ((D > 0 and h[i] >= tgA + tick) or (D < 0 and l[i] <= tgA - tick)):
                xA = i; pA = D * (tgA - fill); kA = 2; maeA = mae
                if part_be and D * (fill + D * be_off - stp) > 0:
                    stp = fill + D * be_off
            if i >= fe:
                xp = c[i] - D * tick; xk = i; xkind = 4
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 4; maeA = mae
                break
            if i - j >= hold - 1 and ext_max > 0 and isck[i] and i < dl:
                # a check bar at the time limit: still beyond the band -> hold to the next check
                if nx < ext_max and ((D > 0 and c[i] > up[i]) or (D < 0 and c[i] < lo[i])):
                    nx += 1
                    dl = i + hold
                else:
                    xp = c[i] - D * tick; xk = i; xkind = 3
                    if xA < 0:
                        xA = i; pA = D * (xp - fill); kA = 3; maeA = mae
                    break
            if i >= dl:
                xp = c[i] - D * tick; xk = i; xkind = 3
                if xA < 0:
                    xA = i; pA = D * (xp - fill); kA = 3; maeA = mae
                break
            if D > 0:
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
        pts = D * (xp - fill)
        if xA < 0:
            xA = xk; pA = pts; kA = xkind; maeA = mae
        out[k, 0] = s; out[k, 1] = j; out[k, 2] = xk; out[k, 3] = D; out[k, 4] = fill; out[k, 5] = st
        out[k, 6] = xp; out[k, 7] = xkind; out[k, 8] = pts; out[k, 9] = risk; out[k, 10] = mae; out[k, 11] = q
        out[k, 12] = xA; out[k, 13] = pA; out[k, 14] = kA; out[k, 15] = maeA; out[k, 16] = nx
        out[k, 17] = D * (ext - fill)
        k += 1
        busy = max(xk, xA)
        dn += 1
        r = (pts * 2.0 - 1.9) / ((risk + tick) * 2.0 + 1.9)
        if part_r == part_r:
            rA = (pA * 2.0 - 1.9) / ((risk + tick) * 2.0 + 1.9)
            r = 0.5 * (r + rA)
        dR += r
    return out[:k]


XK = {1: "stop", 2: "target", 3: "time", 4: "flat"}


def check_bars(B, every):
    ev = max(1, int(round(every / B["tf"])))
    return (((B["mod"] + B["tf"] - 570) // B["tf"]) % ev == 0).astype(np.bool_)


def run(B, p=None, mask=None, F=None, placebo=None):
    """BLITZ trades for parameters p (BASE + overrides) and a candidate mask (None = all). placebo=seed: the same
    candidate bars with a random direction (stop mirrored at the same distance) - does the direction carry the edge?"""
    P = {**BASE, **(p or {})}
    F = F if F is not None else signals(B, P["vm"], P["every"], tuple(P["win"]), P["stopk"])
    if placebo is not None:
        rng = np.random.default_rng(placebo)
        nd = rng.choice([-1.0, 1.0], len(F["sig"]))
        ref = B["c"][F["sig"]]
        F = {**F, "dir": nd, "stop": ref - nd * np.abs(ref - F["stop"])}
    sel = np.ones(len(F["sig"]), bool) if mask is None else np.asarray(mask, bool)
    idx = np.where(sel)[0]
    hold = max(1, int(round(P["hold"] / B["tf"])))
    nan = np.nan
    X = _sim(B["o"], B["h"], B["l"], B["c"], B["flat"], B["day"], B["mod"], check_bars(B, P["every"]), F["_up"], F["_lo"],
             F["sig"][idx], F["dir"][idx], F["stop"][idx], hold, P["trail"] if P["trail"] else nan, float(P["tstart"]),
             P["be"] if P["be"] else nan, float(P["be_off"]), P["part_r"] if P["part_r"] else nan, bool(P["part_be"]),
             int(P["ext"]), int(P["maxday"]), float(P["day_stop"]), float(P["day_tp"]), 930, TICK)
    T = []
    pf = float(P["part_f"]) if P["part_r"] else 0.0
    for r in X:
        s, j, xk = int(r[0]), int(r[1]), int(r[2])
        q = int(idx[int(r[11])])
        pts, risk, mae = float(r[8]), float(r[9]), float(r[10])
        ptsA, maeA = float(r[13]), float(r[15])
        t = {"day": B["dates"][B["day"][j]], "sig_t": int(B["t"][s]), "entry_t": int(B["t"][j]),
             "exit_t": int(B["t"][max(xk, int(r[12]))]) + 60 * B["tf"], "dir": int(r[3]), "entry": float(r[4]), "stop": float(r[5]),
             "exit": float(r[6]), "exit_kind": XK.get(int(r[7]), "?"), "pts": round(pts, 2), "risk_pts": round(risk, 2),
             "mae_pts": round(mae, 2), "mfe_pts": round(float(r[17]), 2), "bars": xk - j + 1, "ext": int(r[16]), "q": q,
             "pnl_pm": pts * PV - COMM, "risk_pm": (risk + TICK) * PV + COMM, "mae_pm": -mae * PV - COMM, "kind": 0}
        if pf:
            t.update(ptsA=round(ptsA, 2), pnlA_pm=ptsA * PV - COMM, maeA_pm=-maeA * PV - COMM, part_f=pf, kindA=XK.get(int(r[14]), "?"))
            t["pnl_pm"] = pf * t["pnlA_pm"] + (1 - pf) * t["pnl_pm"]     # per-micro blend (exact for even splits)
        T.append(t)
    return T


# ================================================================================================ fixed-$ stats
def stats(T, S, risk_usd=150.0, maxq=20):
    """scalp_mo_lib.stats (fixed $ risk a trade) with 2-leg trades priced at the integer split."""
    Ts = [t for t in T if S and S[0] <= t["day"] <= S[-1]]
    if not Ts:
        return {"n": 0, "tpw": 0.0, "pf": 0.0, "net": 0, "per_month": 0, "avg_r": 0.0, "dd": 0, "t_r": 0.0, "win": 0.0}
    pnl = np.array([trade_pnl(t, max(1, min(maxq, int(risk_usd / t["risk_pm"]))))[0] for t in Ts])
    q = np.array([max(1, min(maxq, int(risk_usd / t["risk_pm"]))) for t in Ts])
    R = pnl / (q * np.array([t["risk_pm"] for t in Ts]))
    gl = -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    nS = len(S)
    weeks = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in Ts)
    allw = {dt.date.fromisoformat(d).isocalendar()[:2] for d in S}
    return {"n": len(Ts), "tpw": round(len(Ts) / (nS / 5), 2), "wk5": round(100 * sum(1 for w in allw if weeks.get(w, 0) >= 5) / len(allw), 1),
            "win": round(100 * float((pnl > 0).mean()), 1), "avg_r": round(float(R.mean()), 3),
            "pf": round(float(pnl[pnl > 0].sum() / gl), 2) if gl else 99.0, "net": round(float(pnl.sum())),
            "per_month": round(float(pnl.sum()) / (nS / 21)), "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
            "t_r": round(float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))) if len(R) > 2 and R.std() > 0 else 0.0, 2),
            "med_stop": round(float(np.median([t["risk_pts"] for t in Ts])), 1)}


def trade_pnl(t, q):
    """($ pnl, $ worst open) of a trade at q micros (2-leg: int(q x part_f) micros on leg A, at least 1 on the runner)."""
    if q <= 0:
        return 0.0, 0.0
    pf = t.get("part_f", 0.0)
    qa = int(q * pf) if pf and q >= 2 else 0
    qb = q - qa
    if qa:
        base_b = (t["pnl_pm"] - pf * t["pnlA_pm"]) / (1 - pf)           # runner per micro
        pnl = qa * t["pnlA_pm"] + qb * base_b
        low = qa * t["maeA_pm"] + qb * t["mae_pm"]
    else:
        pnl = q * (t["pnl_pm"] if not pf else (t["pnl_pm"] - pf * t["pnlA_pm"]) / (1 - pf))
        low = q * t["mae_pm"]
    return pnl, low


def r_of(t):
    return t["pnl_pm"] / t["risk_pm"]


# ================================================================================================ sizing on MFFU
def qty(t, room, cum, bal, P, sz):
    """Micros for one trade. sz: {"mode": "frac" | "need" | "fixed", "f", "cap", "k", "usd", "min1"}.
      frac   min(cap, f x room)
      need   min(cap, f x room, (target - balance incl. today) / k)   (pass maximizer: risk what still has to be made / k)
      fixed  usd
    always <= 0.9 x the soft daily loss left; min 1 micro while it fits half the room and the soft daily loss (min1)."""
    dll_left = P["dll"] + cum
    mode = sz.get("mode", "frac")
    if mode == "fixed":
        b = float(sz["usd"])
    else:
        b = min(float(sz["cap"]), float(sz["f"]) * room)
        if mode == "need":
            need = P.get("target", 1e9) - (bal + cum)
            b = min(b, max(need, 0.0) / float(sz["k"]))
    b = min(b, 0.9 * dll_left)
    if b <= 0:
        return 0
    q = int(min(P["maxq"], b // t["risk_pm"]))
    if q == 0 and sz.get("min1", True) and t["risk_pm"] <= min(0.5 * room, 0.9 * dll_left):
        q = 1
    return q


def run_eval(days, by, P, sz, horizon=20, keep=None, stuck=60.0):
    bal = peak = 0.0
    floor = -P["mll"]
    day_tp = sz.get("day_tp")
    for kk, d in enumerate(days[:horizon]):
        dp = 0.0
        for t in by.get(d, ()):
            if day_tp is not None and dp >= day_tp:
                break
            room = bal + dp - floor
            q = qty(t, room, dp, bal, P, sz)
            if q <= 0:
                continue
            pnl, low = trade_pnl(t, q)
            if bal + dp + low <= floor:
                if keep is not None:
                    keep.append({**t, "qty": q, "pnl": round(floor - bal - dp, 2)})
                return "FAIL", kk + 1
            dp += pnl
            if keep is not None:
                keep.append({**t, "qty": q, "pnl": round(pnl, 2)})
            if bal + dp >= P["target"]:
                return "PASS", kk + 1
            if dp <= -P["dll"]:
                break
        bal += dp
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - P["mll"]), P["lock"])
        if bal - floor < stuck:
            return "STUCK", kk + 1
    return "OPEN", min(len(days), horizon)


def eval_score(T, S, plan="25k", sz=None, paths=True):
    P = PLANS[plan]
    sz = sz or {"mode": "frac", "f": 0.3, "cap": 600.0}
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    stuck = 2.0 * float(np.median([t["risk_pm"] for t in T])) if T else 60.0
    res = [(run_eval(S[i:i + 20], by, P, sz, stuck=stuck), len(S) - i) for i in range(len(S))]
    o = {}
    for H in (10, 15, 20):
        R = [r for r, av in res if av >= H]
        N = len(R) or 1
        o[f"p{H}"] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= H) / N, 1)
        o[f"f{H}"] = round(100.0 * sum(1 for r in R if r[0] in ("FAIL", "STUCK") and r[1] <= H) / N, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    if not paths:
        return o
    k, K, n = 0, [], collections.Counter()
    while k < len(S):
        r, used = run_eval(S[k:], by, P, sz, len(S) - k, keep=K, stuck=stuck)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([x["pnl"] for x in K]) if K else np.zeros(1)
    eq = np.cumsum(p)
    bought = n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0)
    o.update(path_net=round(float(p.sum())), path_pm=round(float(p.sum()) / (len(S) / 21)),
             path_dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
             b2b=f"{n['PASS']}/{n['FAIL'] + n['STUCK']}", evals_bought=bought, passes_pm=round(n["PASS"] / (len(S) / 21), 2),
             fees=round(bought * P["price"], 2), med_qty=float(np.median([x["qty"] for x in K])) if K else 0)
    return o


def run_funded(days, by, plan, sz, stuck):
    F = FUNDED[plan]
    P = {"dll": F["dll"], "maxq": F["maxq"]}
    bal = peak = 0.0
    floor = -F["mll"]
    paid, n_pay, last_bal, cyc = 0.0, 0, 0.0, []
    day_tp = sz.get("day_tp")
    for k, d in enumerate(days):
        dp = 0.0
        traded = False
        for t in by.get(d, ()):
            if day_tp is not None and dp >= day_tp:
                break
            room = bal + dp - floor
            q = qty(t, room, dp, bal, P, {**sz, "mode": "frac" if sz.get("mode") == "need" else sz.get("mode", "frac")})
            if q <= 0:
                continue
            pnl, low = trade_pnl(t, q)
            if bal + dp + low <= floor:
                return {"paid": paid, "n": n_pay, "lost": k + 1}
            dp += pnl; traded = True
            if dp <= -F["dll"]:
                break
        bal += dp
        if bal <= floor:
            return {"paid": paid, "n": n_pay, "lost": k + 1}
        peak = max(peak, bal)
        floor = min(max(floor, peak - F["mll"]), F["lock"])
        if bal - floor < stuck:
            return {"paid": paid, "n": n_pay, "lost": None, "stuck": k + 1}
        if traded:
            cyc.append(dp)
        if k + 1 < F["first_wait"] or len(cyc) < F["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or max(cyc) > F["cons"] * prof:
            continue
        amt = min(bal - F["buffer"], F["pay_max"])
        if amt < F["pay_min"]:
            continue
        paid += amt * F["split"]; n_pay += 1; bal -= amt; last_bal, cyc = bal, []
        if n_pay >= F["max_payouts"]:
            break
    return {"paid": paid, "n": n_pay, "lost": None}


def funded_score(T, S, plan="25k", sz=None, horizon=63, step=3):
    """scalp_mo_lib.funded_score with this module's sizing: $ / month to the owner over 3-month funded accounts started
    every 3rd session (2026 halves: every start runs to the end of the half)."""
    sz = sz or {"mode": "frac", "f": 0.3, "cap": 300.0}
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    stuck = 2.0 * float(np.median([t["risk_pm"] for t in T])) if T else 60.0
    starts = [i for i in range(0, len(S), step) if i + horizon <= len(S)]
    if not starts:
        starts = list(range(0, max(1, len(S) - 21), step))
    R = [(run_funded(S[i:i + horizon], by, plan, sz, stuck), min(horizon, len(S) - i)) for i in starts]
    if not R:
        return {}
    pm = [r["paid"] / (n / 21.0) for r, n in R]
    return {"fund_pm": round(float(np.mean(pm))), "fund_pay_pm": round(float(np.mean([r["n"] / (n / 21.0) for r, n in R])), 2),
            "fund_lost": round(100.0 * sum(1 for r, _ in R if r["lost"]) / len(R), 1),
            "fund_stuck": round(100.0 * sum(1 for r, _ in R if r.get("stuck")) / len(R), 1), "fund_starts": len(R)}


# ================================================================================================ helpers
_B = {}


def bars(tf):
    if tf not in _B:
        _B[tf] = L.bars(tf)
    return _B[tf]


def sessions(B, span):
    return L.sessions(B, span)


def span_trades(T, S):
    return [t for t in T if S and S[0] <= t["day"] <= S[-1]]


def lines(p=None, mask_fn=None, spans=(("H1", 1), ("H2", 1), ("R", 5)), risk_usd=150.0):
    """Fixed-$ stats of a variant on the judging spans: 2026 halves on 1m, 2021-25 on 5m (the same rule)."""
    P = {**BASE, **(p or {})}
    out, TT = {}, {}
    for sp, tf in spans:
        B = bars(tf)
        if tf not in TT:
            F = signals(B, P["vm"], P["every"], tuple(P["win"]), P["stopk"])
            TT[tf] = run(B, P, mask_fn(F) if mask_fn else None, F)
        out[sp] = stats(TT[tf], sessions(B, sp), risk_usd, 20)
    return out, TT


# ================================================================================================ account slot (eval -> funded -> payouts)
class Eval:
    """One MFFU Builder eval, a session at a time (= run_eval above, checked in tools/scalp_na.py selfcheck)."""

    def __init__(self, plan, sz, stuck):
        self.P, self.sz, self.stuck = PLANS[plan], sz, stuck
        self.bal = self.peak = 0.0
        self.floor = -self.P["mll"]
        self.s = 0

    def step(self, ts):
        P, sz = self.P, self.sz
        self.s += 1
        dp = 0.0
        tp = sz.get("day_tp")
        for t in ts:
            if tp is not None and dp >= tp:
                break
            q = qty(t, self.bal + dp - self.floor, dp, self.bal, P, sz)
            if q <= 0:
                continue
            pnl, low = trade_pnl(t, q)
            if self.bal + dp + low <= self.floor:
                return "fail"
            dp += pnl
            if self.bal + dp >= P["target"]:
                return "pass"
            if dp <= -P["dll"]:
                break
        self.bal += dp
        if self.bal <= self.floor:
            return "fail"
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - P["mll"]), P["lock"])
        if self.bal - self.floor < self.stuck:
            return "stuck"
        return None


class Funded:
    """One MFFU Builder sim-funded account, a session at a time (= run_funded above). step -> paid $ (to the owner) today,
    and self.done in (None, "lost", "stuck", "max")."""

    def __init__(self, plan, sz, stuck):
        self.F, self.sz, self.stuck = FUNDED[plan], sz, stuck
        self.P = {"dll": self.F["dll"], "maxq": self.F["maxq"]}
        self.bal = self.peak = 0.0
        self.floor = -self.F["mll"]
        self.k = 0
        self.n_pay, self.last_bal, self.cyc = 0, 0.0, []
        self.done = None

    def step(self, ts):
        F, sz = self.F, self.sz
        self.k += 1
        dp = 0.0
        traded = False
        tp = sz.get("day_tp")
        for t in ts:
            if tp is not None and dp >= tp:
                break
            q = qty(t, self.bal + dp - self.floor, dp, self.bal, self.P, {**sz, "mode": "frac" if sz.get("mode") == "need" else sz.get("mode", "frac")})
            if q <= 0:
                continue
            pnl, low = trade_pnl(t, q)
            if self.bal + dp + low <= self.floor:
                self.done = "lost"
                return 0.0
            dp += pnl; traded = True
            if dp <= -F["dll"]:
                break
        self.bal += dp
        if self.bal <= self.floor:
            self.done = "lost"
            return 0.0
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - F["mll"]), F["lock"])
        if self.bal - self.floor < self.stuck:
            self.done = "stuck"
            return 0.0
        if traded:
            self.cyc.append(dp)
        if self.k < F["first_wait"] or len(self.cyc) < F["cycle_days"]:
            return 0.0
        prof = self.bal - self.last_bal
        if prof <= 0 or max(self.cyc) > F["cons"] * prof:
            return 0.0
        amt = min(self.bal - F["buffer"], F["pay_max"])
        if amt < F["pay_min"]:
            return 0.0
        self.n_pay += 1
        self.bal -= amt
        self.last_bal, self.cyc = self.bal, []
        if self.n_pay >= F["max_payouts"]:
            self.done = "max"
        return amt * F["split"]


def mc_paths(S, n=1000, length=126, block=5, seed=23):
    """uprisk-style Monte Carlo: n paths of `length` sessions drawn in 5-session blocks from the span S (indices)."""
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(0, len(S) - block + 1))
            s.extend(range(b, b + block))
        P.append([S[i] for i in s[:length]])
    return P


def life(T, S, plan, ez, fz, n=1000, length=126, gap=2, seed=23):
    """A whole account SLOT for `length` sessions on MC paths of the span: buy the eval (plan price) -> eval sized ez ->
    pass -> `gap` sessions of MFFU paperwork -> funded sized fz -> payouts (80% to the owner) -> lost / stuck / 5 payouts
    -> buy the next eval at once. -> $ / month to the owner net of every eval bought, funded accounts reached, P(slot
    loses money), first payout session (median)."""
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    stuck = 2.0 * float(np.median([t["risk_pm"] for t in T])) if T else 60.0
    price = PLANS[plan]["price"]
    nets, funded_n, first = [], [], []
    for seq in mc_paths(S, n, length, seed=seed):
        cash, nf, wait, acc, fp = -price, 0, 0, Eval(plan, ez, stuck), None
        for k, d in enumerate(seq):
            if wait:
                wait -= 1
                continue
            if isinstance(acc, Eval):
                r = acc.step(by.get(d, ()))
                if r == "pass":
                    acc, wait, nf = Funded(plan, fz, stuck), gap, nf + 1
                elif r in ("fail", "stuck"):
                    cash -= price
                    acc = Eval(plan, ez, stuck)
            else:
                paid = acc.step(by.get(d, ()))
                if paid and fp is None:
                    fp = k + 1
                cash += paid
                if acc.done:
                    cash -= price
                    acc = Eval(plan, ez, stuck)
        nets.append(cash / (length / 21.0))
        funded_n.append(nf)
        if fp:
            first.append(fp)
    a = np.array(nets)
    return {"life_pm": round(float(a.mean())), "life_p10": round(float(np.percentile(a, 10))), "life_lose": round(100.0 * float((a < 0).mean()), 1),
            "funded_per_6m": round(float(np.mean(funded_n)), 2), "first_pay_med": float(np.median(first)) if first else None}
