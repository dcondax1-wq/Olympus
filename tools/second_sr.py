"""Second strategy next to LIT, family SUPPORT / RESISTANCE (owner's order 2026-10-22: "find 1-2 strategies to trade
alongside LIT and make them profitable, the way LIT went from not profitable to PF 4 by tuning on 2026").

    python -X utf8 tools/second_sr.py grid          # stage 1, every variant in R -> research/second/sr_grid.json.gz (4 processes)
    python -X utf8 tools/second_sr.py pick          # pick on 2026 H1 (plateau), report H2 / 2025 / 2021-24, chance check
    python -X utf8 tools/second_sr.py stage2        # filters on the picks (VIX regime, weekday, news blackout), same rule
    python -X utf8 tools/second_sr.py refine        # refinement grid around the stage-1 NY reclaim pick, same rule
    python -X utf8 tools/second_sr.py final         # $ / eval / LIT combination, rl.save sr2_*, research/second/sr_best.json
    python -X utf8 tools/second_sr.py lookahead     # every final trade re-derived from data cut at its entry bar

Starting point: tools/retail_standalone.py (13,320 retail versions; best S/R: PD/ON bounce, PD/ON break-and-limit). What is
borrowed from LIT (engine/lit.py) and tuned here:
- levels: prior-day RTH high/low (pd), overnight high/low (on, from 09:30), Asia box 20:00-24:00 (from 00:00), London box
  02:00-05:00 (from 05:00), prior-week high/low (pw), opening range 09:30-10:00 (or, from 10:00); each level's first touch only.
- setup "reclaim" (sweep and reclaim = a failed break): a 5m bar trades through the level (>= depth x ATR), and within W bars
  a 5m bar closes back on the other side (confirmation "close") or closes beyond the CISD level (the open of the last run of
  against-candles into the extreme, LIT's _cisd_level, confirmation "cisd"); optional displacement body >= disp x ATR;
  optional inducement first (a 5m fractal between the level and 1 ATR from it, taken by the sweep, formed in the last 36 bars).
  Entry at the next 5m open + 1 tick (mkt) or a limit at the reclaimed level for 6 bars (lim). Stop 1 tick beyond the sweep
  extreme (the protected low/high), never a fixed distance.
- setup "break" (break and retest): a 5m close through the level with a body >= disp x ATR; then a limit at the broken level
  for N bars (lim), or the first bar within N that wicks back to the level and closes on the break side -> next open (ret).
  Stop 1 tick beyond the 6-bar swing before/at the break (swing) or beyond the break / retest candle (candle).
- targets: the next level the other way at >= 1.5R (lvl), LIT's VIX band (18:00 open +/- 1 VIX one-day move, >= 1.5R), or a
  fixed 2R / 3R; banked at bank x R; breakeven at 1R (be1) or 1R + 1.25 pts (LIT's BE + costs, be1c) or none; LIT's 15-minute
  check (t15: 15 minutes after the fill, never +0.5R and the close more than 0.3R against -> out at the next open); flat 15:55.
- windows: all 02:00-15:30, lon 02:00-05:00, ny 09:30-11:30, nyx 09:30-15:30, am 08:00-12:00; max 1 or 2 a day; stop 6..60/100.
- costs: $1.90 a micro round trip + 1 tick slippage on market entries, stop / time / flat exits. Stop and target in one bar =
  stop. A limit fills only when price trades 1 tick through it; no target on a limit's fill bar.
- selection (the owner's LIT rule): parameters picked on 2026 H1 (Jan 2 - Jun 30) only, >= 1 trade a week, plateau (every
  one-step neighbour also positive on H1); 2026 H2 (Jul 1 - Oct 16) untouched; 2025 and 2021-24 are reference lines.
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
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
from tools import retail_standalone as rs  # noqa: E402

OUT = os.path.join(ROOT, "research", "second")
TICK, PV, COMM = 0.25, 2.0, 1.90
PERIODS = (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"), ("2026", "2026-01-01", "2026-12-31"),
           ("2025", "2025-01-01", "2025-12-31"), ("2021-24", "2021-11-01", "2024-12-31"))
LV_SETS = {"pdon": ("pd", "on"), "pdon_al": ("pd", "on", "asia", "lon"), "all": ("pd", "on", "asia", "lon", "pw"),
           "all_or": ("pd", "on", "asia", "lon", "pw", "or")}
WINDOWS = {"all": (120, 930), "lon": (120, 300), "ny": (570, 690), "nyx": (570, 930), "am": (480, 720)}

D = {}
ONLY_S = None            # a set of session ids: generators skip every other session (look-ahead check)
PENDING = False          # True: generators also return unfilled limit orders cut off by the data end (look-ahead check)


# ------------------------------------------------------------------------------------------------ data + context
def data(cut=None):
    """rs.load() arrays (+ ATR, session starts, VIX move). cut = keep only bars [0, cut) (look-ahead check)."""
    if cut is None and D:
        return D
    d0 = rs.load()
    n = d0["n"] if cut is None else int(cut)
    d = {k: (v[:n] if isinstance(v, np.ndarray) and len(v) == d0["n"] else v) for k, v in d0.items()}
    d["n"] = n
    d["days"] = d0["days"]
    h, l, c = d["h"], d["l"], d["c"]
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    d["atr"] = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    d["rel"] = (d["mod"] - 1080) % 1440                        # minutes since 18:00 ET
    sid = d["sid"]
    st = np.r_[0, np.nonzero(np.diff(sid))[0] + 1]
    en = np.r_[st[1:], n]
    d["sess"] = [(int(sid[a]), int(a), int(b)) for a, b in zip(st, en)]
    # flat index per session computed on the (possibly cut) arrays: last bar <= 15:50
    flat = np.full(len(d["days"]), -1, np.int64)
    m = d["mod"]
    ok = np.nonzero((m <= 950) & (m < 1080))[0]
    flat[sid[ok]] = ok
    d["flat"] = flat
    vix = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
    vd, vc = list(vix["date"].astype(str)), vix["close"].values.astype(float)
    vm, vv = {}, {}
    for s, a, b in d["sess"]:
        day = d["days"][s]
        j = bisect.bisect_left(vd, day) - 1            # the VIX close of the day before the trading day (LIT's rule)
        if j >= 0:
            vv[s] = float(vc[j]); vm[s] = float(vc[j]) / 100.0 / math.sqrt(252.0) * float(d["o"][a])
    d["vixmove"], d["vix"] = vm, vv
    d["open18"] = {s: float(d["o"][a]) for s, a, b in d["sess"]}
    # 5m fractals (k=2): fractal at bar i confirmed at the close of bar i+2
    k = 2
    lw = pd.Series(l).rolling(2 * k + 1, center=True).min().values
    hw = pd.Series(h).rolling(2 * k + 1, center=True).max().values
    d["fl"] = np.nonzero(l == lw)[0]
    d["fh"] = np.nonzero(h == hw)[0]
    if cut is None:
        D.update(d)
    return d


def levels(d, kinds):
    """dict sid -> list of (price, name, known_rel_minute). Everything is from bars that closed before the known time."""
    key = ("lv", kinds)
    if d is D and key in D:
        return D[key]
    h, l, rel, m = d["h"], d["l"], d["rel"], d["mod"]
    out = collections.defaultdict(list)
    S = d["sess"]
    rth_hl = {}
    for s, a, b in S:
        mm = m[a:b]
        r = np.nonzero((mm >= 570) & (mm < 960))[0]
        if len(r):
            rth_hl[s] = (h[a + r].max(), l[a + r].min())
    # prior ISO week high / low
    wk = {}
    for s, a, b in S:
        y, w, _ = dt.date.fromisoformat(d["days"][s]).isocalendar()
        wk.setdefault((y, w), [-np.inf, np.inf])
        x = wk[(y, w)]; x[0] = max(x[0], h[a:b].max()); x[1] = min(x[1], l[a:b].min())
    wkeys = sorted(wk)
    prev = None
    for s, a, b in S:
        rr = rel[a:b]
        L = []
        if "pd" in kinds and prev is not None and prev in rth_hl:
            L += [(rth_hl[prev][0], "pdh", 0), (rth_hl[prev][1], "pdl", 0)]
        def box(lo_rel, hi_rel, nm):
            ii = np.nonzero((rr >= lo_rel) & (rr < hi_rel))[0]
            if len(ii) >= 2:
                L.extend([(h[a + ii].max(), nm + "h", hi_rel), (l[a + ii].min(), nm + "l", hi_rel)])
        if "on" in kinds:
            box(0, 930, "on")
        if "asia" in kinds:
            box(120, 360, "as")
        if "lon" in kinds:
            box(480, 660, "lo")
        if "or" in kinds:
            box(930, 960, "or")
        if "pw" in kinds:
            y, w, _ = dt.date.fromisoformat(d["days"][s]).isocalendar()
            i = wkeys.index((y, w))
            if i > 0:
                x = wk[wkeys[i - 1]]
                L += [(x[0], "pwh", 0), (x[1], "pwl", 0)]
        out[s] = L
        prev = s
    if d is D:
        D[key] = out
    return out


# ------------------------------------------------------------------------------------------------ candidates
# candidate tuple: (sig_bar, fill_bar_or_-1(market next open), dir, kind 0 mkt / 1 lim, entry_raw, stop, sid, levels_known(tuple), tag)
def _known_prices(L, relj, s_rel_ok=True):
    return tuple(sorted(p for p, nm, fr in L if relj >= fr))


def _cisd(cd, od, a, e, back=3):
    """LIT's CISD (direction space): open of the first bar of the last run of against-candles into the extreme at e."""
    j = e
    while j > e - back and j > a and not (cd[j] < od[j]):
        j -= 1
    if not (cd[j] < od[j]):
        return None
    st = j
    while st - 1 >= a and cd[st - 1] < od[st - 1] and st > e - 30:
        st -= 1
    return float(od[st])


def gen_reclaim(d, lv, depth, W, conf, disp, idm, entry, lim_bars=6):
    o, h, l, c, atr, rel = d["o"], d["h"], d["l"], d["c"], d["atr"], d["rel"]
    n = d["n"]
    LV = levels(d, LV_SETS[lv]) if d is D else levels(d, LV_SETS[lv])
    fl, fh = d["fl"], d["fh"]
    out = []
    for s, a, b in d["sess"]:
        if ONLY_S is not None and s not in ONLY_S:
            continue
        L = LV.get(s)
        if not L:
            continue
        b2 = min(b, n)
        for p, nm, fr in L:
            # first bar after the level is known where price trades through it from the other side
            j0 = a + int(np.searchsorted(rel[a:b2], fr + 5)) if fr > 0 else a + 1
            j0 = max(j0, a + 1)
            jj = None
            for j in range(j0, b2):
                if rel[j] >= 1315:               # 15:55
                    break
                if c[j - 1] > p and l[j] < p:
                    jj, dr = j, 1; break
                if c[j - 1] < p and h[j] > p:
                    jj, dr = j, -1; break
            if jj is None:
                continue
            j = jj
            A = atr[j - 1]
            # direction space: long = sweep of a low level
            if dr > 0:
                cd, od, ld, hd, pp = c, o, l, h, p
            else:
                cd, od, ld, hd, pp = -c, -o, -h, -l, -p
            ext = ld[j]; r = None; cis = None
            for q in range(j, min(j + W, b2)):
                if rel[q] >= 1315:
                    break
                ext = min(ext, ld[q])
                if conf == "close":
                    if cd[q] > pp:
                        r = q; break
                else:
                    if cis is None or ld[q] <= ext:
                        cis = _cisd(cd, od, a, q)
                    if cis is not None and cd[q] > max(cis, pp) and cd[q] > od[q]:
                        r = q; break
            if r is None:
                continue
            if pp - ext < depth * A:
                continue
            if disp > 0 and (cd[r] - od[r]) < disp * A:
                continue
            if idm:
                F = fl if dr > 0 else fh
                lo_i = bisect.bisect_left(F, j - 36); hi_i = bisect.bisect_left(F, j - 2)
                ok = False
                for f in F[lo_i:hi_i]:
                    fp = l[f] if dr > 0 else -h[f]
                    if pp < fp <= pp + A and f >= a:
                        ok = True; break
                if not ok:
                    continue
            stop_d = ext - TICK
            known = _known_prices(L, rel[r])
            if entry == "mkt":
                out.append((r, -1, dr, 0, np.nan, dr * stop_d, s, known, nm))
            else:
                k1, k2 = r + 1, min(r + lim_bars, b2 - 1)
                fill = None
                for k in range(k1, k2 + 1):
                    if rel[k] >= 1315:
                        break
                    if ld[k] <= pp - TICK:
                        fill = k; break
                if fill is None:
                    if PENDING and r + lim_bars > n - 1:      # look-ahead check: the order as placed at the signal close
                        out.append((r, -2, dr, 1, dr * pp, dr * stop_d, s, known, nm))
                    continue
                epx = min(od[fill], pp)
                out.append((r, fill, dr, 1, dr * epx, dr * stop_d, s, known, nm))
    return out


def gen_break(d, lv, disp, N, stopk, entry):
    o, h, l, c, atr, rel = d["o"], d["h"], d["l"], d["c"], d["atr"], d["rel"]
    n = d["n"]
    LV = levels(d, LV_SETS[lv])
    out = []
    for s, a, b in d["sess"]:
        if ONLY_S is not None and s not in ONLY_S:
            continue
        L = LV.get(s)
        if not L:
            continue
        b2 = min(b, n)
        for p, nm, fr in L:
            j0 = a + int(np.searchsorted(rel[a:b2], fr + 5)) if fr > 0 else a + 1
            j0 = max(j0, a + 1)
            jj = None
            for j in range(j0, b2):
                if rel[j] >= 1315:
                    break
                if c[j] > p >= c[j - 1]:
                    jj, dr = j, 1; break
                if c[j] < p <= c[j - 1]:
                    jj, dr = j, -1; break
            if jj is None:
                continue
            j = jj
            A = atr[j - 1]
            if dr > 0:
                cd, od, ld, hd, pp = c, o, l, h, p
            else:
                cd, od, ld, hd, pp = -c, -o, -h, -l, -p
            if (cd[j] - od[j]) < disp * A:
                continue
            sw = ld[max(a, j - 5):j + 1].min()
            known = _known_prices(L, rel[j])
            if entry == "lim":
                fill = None
                for k in range(j + 1, min(j + N, b2 - 1) + 1):
                    if rel[k] >= 1315:
                        break
                    if ld[k] <= pp - TICK:
                        fill = k; break
                stop_d = (sw if stopk == "swing" else ld[j]) - TICK
                if fill is None:
                    if PENDING and j + N > n - 1:
                        out.append((j, -2, dr, 1, dr * pp, dr * stop_d, s, known, nm))
                    continue
                epx = min(od[fill], pp)
                out.append((j, fill, dr, 1, dr * epx, dr * stop_d, s, known, nm))
            else:
                r = None
                for k in range(j + 1, min(j + N, b2 - 1) + 1):
                    if rel[k] >= 1315:
                        break
                    if cd[k] < pp:       # closed back through: failed break, no retest trade
                        break
                    if ld[k] <= pp and cd[k] > pp and cd[k] > od[k]:
                        r = k; break
                if r is None:
                    continue
                stop_d = (sw if stopk == "swing" else ld[j:r + 1].min()) - TICK
                out.append((r, -1, dr, 0, np.nan, dr * stop_d, s, known, nm))
    return out


# ------------------------------------------------------------------------------------------------ outcomes
TGTS = ("lvl", "vix", 2.0, 3.0)
BANKS = (2.0, 3.0, 4.0, 5.0, 8.0)
BES = (None, 1.25)
TCS = (False, True)


def outcomes(d, cands, max_stop=120.0, min_stop=6.0, min_rr=1.5):
    """For every candidate and every management combo (target x bank x be x t15): (R per micro after costs, exit bar,
    exit kind, worst pts). Returns list of dicts per candidate with base info and an outcome table."""
    o, h, l, c, rel = d["o"], d["h"], d["l"], d["c"], d["rel"]
    flat = d["flat"]
    n = d["n"]
    res = []
    for (sig, fill, dr, kind, epx, stop, s, known, nm) in cands:
        k0 = sig + 1 if fill < 0 else fill
        if k0 >= n or d["sid"][k0] != s:
            continue
        kf = flat[s]
        live = d.get("open_sid") is not None and s == d["open_sid"]   # live (engine/second.py): 15:55 flat not reached yet
        if live:
            kf = n - 1
        if kf < k0:
            continue
        if dr > 0:
            od, hd, ld, cd = o, h, l, c
        else:
            od, hd, ld, cd = -o, -l, -h, -c
        e = (od[k0] + TICK) if kind == 0 else dr * epx
        sp = dr * stop
        risk = e - sp
        if risk < min_stop or risk > max_stop:
            continue
        lim = kind == 1
        # targets in direction space
        kn = [dr * x for x in known]
        lv = sorted(x for x in kn if x >= e + min_rr * risk)
        vm = d["vixmove"].get(s)
        tv = (d["open18"][s] * dr + vm) if vm else None
        tlist = {}
        for tg in TGTS:
            if tg == "lvl":
                base = lv[0] if lv else None
            elif tg == "vix":
                base = tv if (tv is not None and tv >= e + min_rr * risk) else None
            else:
                base = e + tg * risk
            tlist[tg] = base
        seg_h, seg_l, seg_o, seg_c = hd[k0:kf + 1], ld[k0:kf + 1], od[k0:kf + 1], cd[k0:kf + 1]
        tab = {}
        for tg in TGTS:
            base = tlist[tg]
            if base is None:
                continue
            for bk in (BANKS if tg in ("lvl", "vix") else (None,)):
                T = min(base, e + bk * risk) if bk else base
                for be in BES:
                    for tc in TCS:
                        tab[(tg, bk, be, tc)] = _walk(seg_o, seg_h, seg_l, seg_c, e, sp, risk, T, be, tc, lim, live)
        if not tab:
            continue
        res.append({"sig": sig, "k0": k0, "dir": dr, "kind": kind, "e": e, "stop": sp, "risk": risk, "s": s, "nm": nm,
                    "mod": int(d["mod"][k0]), "tab": tab, "tl": tlist})
    return res


def _walk(O, H, L, C, e, sp, risk, T, be, tc, lim, live=False):
    """One trade in direction space. Returns (pts, exit_offset, kind, worst_pts, mfe_R). live=True (engine/second.py): the
    bars end inside the trade -> kind "OPEN" at the last close (the research default live=False is unchanged)."""
    cur = sp; moved = False; worst = 0.0; mfe = 0.0
    nb = len(O)
    cut = False
    for k in range(nb):
        if cut:
            px = O[k] - TICK
            return (px - e, k, "T15", min(worst, px - e), mfe)
        if L[k] <= cur:
            px = (min(O[k], cur) if (k > 0 or not lim) else cur) - TICK
            return (px - e, k, "BE" if moved else "STOP", min(worst, px - e), mfe)
        worst = min(worst, L[k] - e)
        if not (lim and k == 0):
            mfe = max(mfe, (H[k] - e) / risk)
            if H[k] >= T:
                px = max(O[k], T) if k > 0 else T
                return (px - e, k, "TARGET", worst, mfe)
            if be is not None and not moved and H[k] >= e + risk:
                cur = e + be; moved = True
        if tc and k == 2 and not moved and mfe < 0.5 and C[k] < e - 0.3 * risk and (k + 1 < nb or live):
            cut = True
        if k == nb - 1:
            if live:
                # live (engine/second.py): a 15-minute cut decided on this last close exits at the next open: "OPEN_CUT"
                return (C[k] - e, k, "OPEN_CUT" if cut else "OPEN_BE" if moved else "OPEN", min(worst, C[k] - e), mfe)
            px = C[k] - TICK
            return (px - e, k, "FLAT", min(worst, px - e), mfe)
    px = C[-1] - TICK
    return (px - e, nb - 1, "FLAT", min(worst, px - e), mfe)


def select(d, oc, combo, win, maxpd, max_stop, skip=None):
    """Sequential selection: entries in time order, one position at a time, max maxpd a day, window, stop cap.
    skip(x) -> True drops a candidate before it is taken (stage-2 filters, LIT priority on one account)."""
    a, z = WINDOWS[win]
    busy = -1
    cnt = collections.Counter()
    T = []
    for x in oc:
        if x["k0"] <= busy or x["risk"] > max_stop:
            continue
        if not (a <= x["mod"] < z):
            continue
        if skip is not None and skip(x):
            continue
        r = x["tab"].get(combo)
        if r is None:
            continue
        if cnt[x["s"]] >= maxpd:
            continue
        pts, off, kind, worst, mfe = r
        T.append((x, r))
        busy = x["k0"] + off
        cnt[x["s"]] += 1
    return T


def r_of(x, r):
    return (r[0] * PV - COMM) / (x["risk"] * PV)


def rstats(d, T, lo, hi):
    days = d["days"]
    R = np.array([r_of(x, r) for x, r in T if lo <= days[x["s"]] <= hi])
    nd = rs.n_sessions(lo, min(hi, "2026-10-16"))
    if len(R) == 0:
        return {"n": 0, "tpw": 0.0, "R": 0.0, "exp": 0.0, "pf": 0.0, "t": 0.0, "win": 0.0}
    gl = -R[R < 0].sum()
    return {"n": int(len(R)), "tpw": round(len(R) / (nd / 5), 2), "R": round(float(R.sum()), 2), "exp": round(float(R.mean()), 3),
            "pf": round(float(R[R > 0].sum() / gl), 2) if gl > 0 else 99.0,
            "t": round(float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))), 2) if len(R) > 2 and R.std() > 0 else 0.0,
            "win": round(100 * float((R > 0).mean()), 1)}


# ------------------------------------------------------------------------------------------------ grid
GEN_GRID = []
for lv in LV_SETS:
    for depth in (0.0, 0.25, 0.5):
        for W in (1, 3, 6):
            for conf in ("close", "cisd"):
                for disp in (0.0, 0.5):
                    for idm in (False, True):
                        for entry in ("mkt", "lim"):
                            if conf == "cisd" and W == 1:
                                continue
                            GEN_GRID.append(("reclaim", dict(lv=lv, depth=depth, W=W, conf=conf, disp=disp, idm=idm, entry=entry)))
    for disp in (0.0, 0.5, 0.8):
        for N in (6, 12):
            for stopk in ("swing", "candle"):
                for entry in ("lim", "ret"):
                    GEN_GRID.append(("break", dict(lv=lv, disp=disp, N=N, stopk=stopk, entry=entry)))
SIM_GRID = [dict(win=w, maxpd=m, max_stop=80.0) for w in WINDOWS for m in (1, 2)]
COMBOS = [(tg, bk, be, tc) for tg in TGTS for bk in ((3.0, 5.0, 8.0) if tg in ("lvl", "vix") else (None,)) for be in BES for tc in TCS]


def gen(d, setup, g):
    return gen_reclaim(d, **g) if setup == "reclaim" else gen_break(d, **g)


def _job(i):
    d = data()
    setup, g = GEN_GRID[i]
    cands = gen(d, setup, g)
    oc = outcomes(d, cands)
    oc.sort(key=lambda x: x["k0"])
    rows = []
    for sg in SIM_GRID:
        for cb in COMBOS:
            T = select(d, oc, cb, sg["win"], sg["maxpd"], sg["max_stop"])
            st = {nm: rstats(d, T, lo, hi) for nm, lo, hi in PERIODS}
            rows.append([i, sg["win"], sg["maxpd"], list(cb)] + [[st[nm][k] for k in SK] for nm, _, _ in PERIODS])
    return rows


SK = ("n", "tpw", "R", "exp", "pf", "t", "win")


def _jkey(r):
    g = r["g"]
    return json.dumps([r["setup"], g, r["sim"], r["combo"]], sort_keys=True, default=str)


def cmd_grid(procs=4):
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    data()
    rows = []
    with Pool(procs, initializer=data) as P:
        for k, rr in enumerate(P.imap_unordered(_job, range(len(GEN_GRID)), chunksize=1)):
            rows.extend(rr)
            if k % 20 == 0:
                print(f"{k + 1}/{len(GEN_GRID)} generator configs, {len(rows)} variants, {time.time() - t0:.0f}s", flush=True)
    import gzip
    with gzip.open(os.path.join(OUT, "sr_grid.json.gz"), "wt") as f:
        json.dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "n": len(rows), "gen": GEN_GRID,
                   "row_cols": ["gi", "win", "maxpd", "combo"] + [nm for nm, _, _ in PERIODS], "stat_cols": SK,
                   "rows": rows}, f, separators=(",", ":"), default=str)
    print("done", len(rows), f"{time.time() - t0:.0f}s")


# ------------------------------------------------------------------------------------------------ pick (2026 H1 only)
ORDERED = {"depth": (0.0, 0.25, 0.5), "W": (1, 3, 6), "disp": (0.0, 0.5, 0.8), "N": (6, 12), "bk": (3.0, 5.0, 8.0),
           "maxpd": (1, 2), "be": (None, 1.25), "tc": (False, True)}
P_IX = {nm: k for k, (nm, _, _) in enumerate(PERIODS)}


def load_grid():
    import gzip
    with gzip.open(os.path.join(OUT, "sr_grid.json.gz"), "rt") as f:
        G = json.load(f)
    gens = G["gen"]
    V = []
    for r in G["rows"]:
        gi, win, maxpd, cb = r[0], r[1], r[2], r[3]
        setup, g = gens[gi]
        key = dict(setup=setup, **g, win=win, maxpd=maxpd, tg=cb[0], bk=cb[1], be=cb[2], tc=cb[3])
        V.append((key, {nm: dict(zip(SK, r[4 + k])) for nm, k in P_IX.items()}))
    return V


def _k(key):
    return json.dumps(key, sort_keys=True)


def neighbours(key, idx):
    """One-step neighbours along the ordered / on-off dimensions (levels, setup type, window and target type are the
    strategy itself, not neighbours)."""
    out = []
    for dim, vals in ORDERED.items():
        if dim not in key or key[dim] not in vals:
            continue
        j = vals.index(key[dim])
        for jj in (j - 1, j + 1):
            if 0 <= jj < len(vals):
                k2 = dict(key); k2[dim] = vals[jj]
                x = idx.get(_k(k2))
                if x is not None:
                    out.append(x)
    return out


def pick(V, min_n=25, ref=False, top=10, setup=None, flt=None):
    """Plateau pick on 2026 H1: n >= min_n, H1 R > 0, every one-step neighbour H1 R > 0; score = median H1 t of itself +
    neighbours. ref=True also needs 2025 and 2021-24 R >= 0 (the owner's "prefer versions not negative there")."""
    idx = {_k(k): (k, st) for k, st in V}
    cand = []
    seen = set()
    for k, st in V:
        if setup and k["setup"] != setup:
            continue
        if flt and not flt(k):
            continue
        h1 = st["H1"]
        if h1["n"] < min_n or h1["R"] <= 0:
            continue
        if ref and (st["2025"]["R"] < 0 or st["2021-24"]["R"] < 0):
            continue
        nb = neighbours(k, idx)
        if len(nb) < 2 or any(x[1]["H1"]["R"] <= 0 for x in nb):
            continue
        sig = (round(h1["R"], 2), h1["n"], round(st["2025"]["R"], 2), round(st["2021-24"]["R"], 2))
        if sig in seen:
            continue
        seen.add(sig)
        sc = float(np.median([h1["t"]] + [x[1]["H1"]["t"] for x in nb]))
        cand.append((sc, k, st, len(nb)))
    cand.sort(key=lambda x: -x[0])
    return cand[:top], len(cand)


def chance(V, min_n=25):
    """How often an H1-positive variant is also H2-positive (the base rate a pick has to beat)."""
    a = [st for k, st in V if st["H1"]["n"] >= min_n]
    pos = [st for st in a if st["H1"]["R"] > 0]

    def frac(L, f):
        return round(100 * sum(1 for x in L if f(x)) / max(len(L), 1), 1)
    return {"variants": len(V), "with_n": len(a), "h1_pos": len(pos), "h1_pos_pct": frac(a, lambda x: x["H1"]["R"] > 0),
            "h2_pos_all": frac(a, lambda x: x["H2"]["R"] > 0), "h2_pos_given_h1": frac(pos, lambda x: x["H2"]["R"] > 0),
            "h2_pos_given_h1_t2": frac([x for x in pos if x["H1"]["t"] >= 2], lambda x: x["H2"]["R"] > 0),
            "n_h1_t2": sum(1 for x in pos if x["H1"]["t"] >= 2),
            "all4_pos": frac(a, lambda x: all(x[p]["R"] > 0 for p in ("H1", "H2", "2025", "2021-24")))}


def fmt(k):
    return k["setup"] + " " + " ".join(f"{a}={b}" for a, b in k.items() if a != "setup")


def show(st):
    return " | ".join(f"{p} n={st[p]['n']} R={st[p]['R']:+.1f} pf={st[p]['pf']} t={st[p]['t']}" for p in ("H1", "H2", "2025", "2021-24"))


def cmd_pick():
    V = load_grid()
    ch = chance(V)
    print("chance:", ch)
    res = {"chance": ch}
    for setup in ("reclaim", "break"):
        for ref in (False, True):
            top, ncand = pick(V, ref=ref, setup=setup)
            print(f"\n== {setup} ref={ref}: {ncand} plateau candidates")
            for sc, k, st, nn in top:
                print(f"{sc:5.2f} nb={nn} {fmt(k)}\n      {show(st)}")
            res[f"{setup}_{'ref' if ref else 'h1'}"] = {"n_plateau": ncand,
                                                         "top": [{"score": sc, "key": k, "st": st, "nb": nn} for sc, k, st, nn in top]}
    json.dump(res, open(os.path.join(OUT, "sr_picks.json"), "w"), indent=1, default=str)


# ------------------------------------------------------------------------------------------------ refinement round
# A second, smaller grid around the stage-1 reference pick (reclaim, inducement first, displacement close, market entry,
# NY hours): reclaim window, displacement size, sweep depth, level set, NY window, stop cap, min R of the level target,
# bank, BE, 15-minute check. Picked the same way (2026 H1 plateau; 2025 / 2021-24 not negative).
WINDOWS.update({"ny12": (570, 720), "ny10": (600, 930), "ny11": (570, 660)})      # ny11: ATLAS (tools/atlas.py, atlas.md)
REF_GEN = [dict(lv=lv, depth=dp, W=w, conf="close", disp=ds, idm=True, entry="mkt")
           for lv in ("all_or", "all") for dp in (0.0, 0.25) for w in (2, 3, 4, 6) for ds in (0.3, 0.5, 0.7)]
REF_SIM = [dict(win=w, maxpd=1, max_stop=ms) for w in ("nyx", "ny12", "ny10") for ms in (60.0, 80.0, 120.0)]
REF_COMBOS = [(tg, bk, be, tc) for tg in ("lvl", 2.0) for bk in ((2.0, 3.0, 5.0) if tg == "lvl" else (None,))
              for be in BES for tc in TCS]
REF_ORDERED = {"depth": (0.0, 0.25), "W": (2, 3, 4, 6), "disp": (0.3, 0.5, 0.7), "max_stop": (60.0, 80.0, 120.0),
               "min_rr": (1.0, 1.5, 2.0), "bk": (2.0, 3.0, 5.0), "be": (None, 1.25), "tc": (False, True)}


def _ref_job(i):
    d = data()
    g = REF_GEN[i]
    cands = gen_reclaim(d, **g)
    rows = []
    for mr in (1.0, 1.5, 2.0):
        oc = outcomes(d, cands, min_rr=mr)
        oc.sort(key=lambda x: x["k0"])
        for sg in REF_SIM:
            for cb in REF_COMBOS:
                if cb[0] != "lvl" and mr != 1.5:
                    continue
                T = select(d, oc, cb, sg["win"], sg["maxpd"], sg["max_stop"])
                st = {nm: rstats(d, T, lo, hi) for nm, lo, hi in PERIODS}
                key = dict(setup="reclaim", **g, win=sg["win"], maxpd=1, max_stop=sg["max_stop"], min_rr=mr,
                           tg=cb[0], bk=cb[1], be=cb[2], tc=cb[3])
                rows.append((key, st))
    return rows


def cmd_refine(procs=4):
    global ORDERED
    t0 = time.time()
    V = []
    with Pool(procs, initializer=data) as P:
        for rr in P.imap_unordered(_ref_job, range(len(REF_GEN))):
            V.extend(rr)
    print(len(V), "refinement variants", f"{time.time() - t0:.0f}s")
    import gzip
    with gzip.open(os.path.join(OUT, "sr_refine.json.gz"), "wt") as f:
        json.dump({"n": len(V), "rows": V}, f, separators=(",", ":"), default=str)
    ORDERED = REF_ORDERED
    ch = chance(V)
    print("chance:", ch)
    out = {"chance": ch}
    for ref in (False, True):
        top, nc = pick(V, ref=ref, top=12)
        print(f"\n== refine ref={ref}: {nc} plateau candidates")
        for sc, k, st, nn in top:
            print(f"{sc:5.2f} nb={nn} {fmt(k)}\n      {show(st)}")
        out["ref" if ref else "h1"] = {"n_plateau": nc, "top": [{"score": sc, "key": k, "st": st, "nb": nn} for sc, k, st, nn in top]}
    json.dump(out, open(os.path.join(OUT, "sr_refine_picks.json"), "w"), indent=1, default=str)


# ------------------------------------------------------------------------------------------------ one version end to end
GEN_KEYS = {"reclaim": ("lv", "depth", "W", "conf", "disp", "idm", "entry"), "break": ("lv", "disp", "N", "stopk", "entry")}
_OC = {}


def oc_of(key, d=None):
    d = d or data()
    g = {k: key[k] for k in GEN_KEYS[key["setup"]]}
    mr = key.get("min_rr", 1.5)
    ck = _k(dict(setup=key["setup"], min_rr=mr, **g))
    if d is D and ck in _OC:
        return _OC[ck]
    oc = outcomes(d, gen(d, key["setup"], g), min_rr=mr)
    oc.sort(key=lambda x: x["k0"])
    if d is D:
        _OC[ck] = oc
    return oc


def run_key(key, skip=None, d=None):
    d = d or data()
    cb = (key["tg"], key["bk"], key["be"], key["tc"])
    return select(d, oc_of(key, d), cb, key["win"], key["maxpd"], key.get("max_stop", 80.0), skip=skip)


def news_times():
    """High-impact releases (data/news/events.csv: FOMC, CPI, NFP, PPI ...) as unix seconds (ET clock)."""
    def f():
        ev = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
        ev = ev[ev["impact"].astype(str).str.lower() == "high"]
        ts = pd.to_datetime(ev["date"].astype(str) + " " + ev["time_et"].astype(str)).dt.tz_localize("America/New_York")
        ep = pd.Timestamp("1970-01-01", tz="UTC")
        return np.sort(((ts - ep).dt.total_seconds()).values.astype(np.int64))
    return rs.cached("sr_news", f)


def stage2_filters():
    """Stage-2 filters (each its own variant): VIX regime, weekday, news blackout. Return name -> skip(x)."""
    d = data()
    vix = d["vix"]
    nt = news_times()

    def near_news(x, before=30 * 60, after=30 * 60):
        t = int(d["t"][x["k0"]])
        i = bisect.bisect_left(nt, t - after)
        return i < len(nt) and nt[i] <= t + before
    F = {"none": None}
    for lo, hi in ((0, 20), (0, 25), (15, 99), (18, 99), (20, 99), (15, 30)):
        F[f"vix{lo}-{hi}"] = (lambda lo, hi: lambda x: not (lo <= vix.get(x["s"], 20) < hi))(lo, hi)
    for wd in range(5):
        F[f"no_dow{wd}"] = (lambda wd: lambda x: int(d["dow"][x["k0"]]) == wd)(wd)
    F["news30"] = near_news
    nd = {dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-4))).strftime("%Y-%m-%d") for t in nt}
    F["news_day"] = lambda x: d["days"][x["s"]] in nd
    return F


def stats_T(T):
    return {nm: rstats(data(), T, lo, hi) for nm, lo, hi in PERIODS}


def cmd_stage2(n_each=3):
    """Stage 2 on the stage-1 picks: each filter scored on 2026 H1 only; adopted only if H1 R and t improve."""
    P = json.load(open(os.path.join(OUT, "sr_picks.json")))
    F = stage2_filters()
    out = {}
    tried = 0
    for grp in ("reclaim_h1", "reclaim_ref", "break_h1", "break_ref"):
        for it in P[grp]["top"][:n_each]:
            key = it["key"]
            base = stats_T(run_key(key))
            rows = []
            for nm, f in F.items():
                st = stats_T(run_key(key, skip=f)); tried += 1
                rows.append({"filter": nm, "st": st})
            rows.sort(key=lambda r: -r["st"]["H1"]["t"])
            out[_k(key)] = {"key": key, "grp": grp, "base": base, "rows": rows}
            print(f"\n{grp} {fmt(key)}\n   base   {show(base)}")
            for r in rows[:6]:
                print(f"   {r['filter']:<10} {show(r['st'])}")
    out["_tried"] = tried
    json.dump(out, open(os.path.join(OUT, "sr_stage2.json"), "w"), indent=1, default=str)


# ---- trades in the common format + $ sizing
def qty_rule(rule, risk):
    if rule.startswith("usd"):
        return max(0, min(40, int(float(rule[3:]) / (risk * PV))))
    if rule == "lit":
        r = 800.0 if risk <= 20 else 800.0 * 20 / risk
        return max(0, min(40, int(r / (risk * PV))))
    raise ValueError(rule)


def trades_of(T, rule="usd500", setup="sr"):
    d = data()
    out = []
    for x, r in T:
        pts, off, kind, worst, mfe = r
        q = qty_rule(rule, x["risk"])
        if q <= 0:
            continue
        dr = x["dir"]
        k_ex = x["k0"] + off
        ex_d = x["e"] + pts
        tl = x["tl"]
        key_t = None
        out.append({"day": d["days"][x["s"]], "entry_t": int(d["t"][x["k0"]]),
                    "exit_t": int(d["t"][k_ex]) + (0 if kind == "T15" else 300), "dir": int(dr),
                    "entry": round(dr * x["e"], 2), "stop": round(dr * x["stop"], 2), "target": None,
                    "exit": round(dr * ex_d, 2), "exit_kind": kind, "r": round(r_of(x, r), 3), "qty": q,
                    "pnl_usd": round(q * (pts * PV - COMM), 2), "setup": setup,
                    # runlib columns
                    "pnl": round(q * (pts * PV - COMM), 2), "risk_pts": round(x["risk"], 2), "risk_usd": round(q * x["risk"] * PV, 2),
                    "half": False, "trigger": x["nm"], "mfe": round(mfe, 3), "mae": round(-worst / x["risk"], 3),
                    "bars_held": int(off + 1), "regime": "", "mult": 1.0, "low": round(min(q * (worst * PV - COMM), q * (pts * PV - COMM)), 2),
                    "_x": x, "_r": r})
    return out


def set_targets(TT, key):
    for t in TT:
        x = t["_x"]
        base = x["tl"].get(key["tg"])
        if base is None:
            continue
        T = min(base, x["e"] + key["bk"] * x["risk"]) if key["bk"] else base
        t["target"] = round(x["dir"] * T, 2)
    return TT


def sessions_in(lo, hi):
    return [s for s in rs.sessions() if lo <= s <= hi]


def money(TT, lo, hi):
    from tools import runlib as rl
    S = sessions_in(lo, hi)
    T = [t for t in TT if lo <= t["day"] <= hi]
    days = rl.days_of(T, S)
    return (rl._compact(T, days) if T else {"n": 0, "net": 0, "per_month": 0}), days


def eval_path(T, base_rule="usd500", lit_days=None, lit_trades=None, horizon=60, cap=0.6):
    """MFFU Builder 50K, a fresh eval started on every session: SR micros = min(base_rule micros, cap x room / (stop x $2)),
    room = balance (incl. today's closed P&L) - trailing max loss. lit_days: {date: (pnl, low)} of LIT on the same
    account (LIT's own eval-path run, its P&L taken as stored and booked at its exit time)."""
    from engine.analytics import PLANS
    plan = PLANS["builder_50k"]
    d = data()
    S = rs.sessions()
    ev = collections.defaultdict(list)
    for x, r in T:
        ev[d["days"][x["s"]]].append((int(d["t"][x["k0"]]), "sr", x, r))
    if lit_trades:
        for t in lit_trades:
            ev[t["day"]].append((int(t["exit_t"]), "lit", t, None))
    for k in ev:
        ev[k].sort(key=lambda e: e[0])
    res = []
    for i in range(len(S)):
        bal = peak = plan["start"]
        mll = bal - plan["mll"]; lock = plan["start"] + plan["lock_above"]
        out = ("OPEN", horizon)
        for k, day in enumerate(S[i:i + horizon]):
            dp, low = 0.0, 0.0
            if lit_days and day in lit_days:
                low = min(low, lit_days[day][1])
            for t0, kind, x, r in ev.get(day, []):
                if kind == "lit":
                    dp += x["pnl"]; low = min(low, dp)
                    continue
                room = bal + dp - mll
                if room <= 0:
                    break
                q = min(qty_rule(base_rule, x["risk"]), int(cap * room / (x["risk"] * PV)))
                if q <= 0:
                    continue
                pts, off, kk, worst, mfe = r
                low = min(low, dp + q * (worst * PV - COMM)); dp += q * (pts * PV - COMM); low = min(low, dp)
            if bal + low <= mll or bal + dp <= mll:
                out = ("FAIL", k + 1); break
            bal += dp
            peak = max(peak, bal); mll = min(max(mll, peak - plan["mll"]), lock)
            if bal - plan["start"] >= plan["target"]:
                out = ("PASS", k + 1); break
        res.append((S[i], out))
    return res


def eval_sum(res, lo, hi):
    rr = [r for day, r in res if lo <= day <= hi]
    n = len(rr) or 1
    f = lambda kind, H: round(100 * sum(1 for x in rr if x[0] == kind and x[1] <= H) / n, 1)
    ps = [x[1] for x in rr if x[0] == "PASS"]
    return {"p10": f("PASS", 10), "f10": f("FAIL", 10), "p20": f("PASS", 20), "f20": f("FAIL", 20),
            "pass_med": float(np.median(ps)) if ps else None}


def lit_run(rid):
    from tools import runlib as rl
    r = rl.load(rid)
    cols = r["trade_cols"]
    T = [dict(zip(cols, x)) for x in r["trades"]]
    days = {x[0]: (x[1], x[2]) for x in r["days"]}
    return T, days


def lit_skip(lit_T, mode):
    """LIT priority on one account. max2: SR is skipped while a LIT position is open (both may trade the same day).
    max1: SR is skipped once LIT has entered that day (or is open); a LIT entry later the same day after an SR trade is
    dropped (reported as LIT trades lost)."""
    d = data()
    by = collections.defaultdict(list)
    for t in lit_T:
        by[t["day"]].append((int(t["entry_t"]), int(t["exit_t"])))

    def f(x):
        t = int(d["t"][x["k0"]])
        for a, b in by.get(d["days"][x["s"]], []):
            if a <= t < b:
                return True
            if mode == "max1" and a <= t:
                return True
        return False
    return f


def combine(lit_T, sr_TT, mode):
    """Day P&L of LIT + SR on one account; max1 drops LIT trades entered after an SR trade the same day."""
    sr_by = collections.defaultdict(list)
    for t in sr_TT:
        sr_by[t["day"]].append(t)
    L, lost = [], []
    for t in lit_T:
        if mode == "max1" and any(s["entry_t"] <= t["entry_t"] for s in sr_by.get(t["day"], [])):
            lost.append(t); continue
        L.append(t)
    return L, lost


def corr(days_a, days_b, lo, hi):
    A = {x["date"]: x["pnl"] for x in days_a}
    a = [(A[x["date"]], x["pnl"]) for x in days_b if lo <= x["date"] <= hi and x["date"] in A]
    if len(a) < 20:
        return None
    u, v = np.array(a).T
    if u.std() == 0 or v.std() == 0:
        return None
    return round(float(np.corrcoef(u, v)[0, 1]), 2)


def report(key, skip=None, name="sr", rules="", verbose=True):
    """Every number the owner asked for, for one version."""
    from tools import runlib as rl
    d = data()
    T = run_key(key, skip=skip)
    lit_T, lit_days = lit_run("lit_live")
    lite_T, lite_days = lit_run("lit_adopt_t15_be_off_eval")
    rep = {"key": key, "periods": {}, "sizing": {}, "eval": {}, "combo": {}}
    TTs = {}
    for rule in ("usd300", "usd500", "usd800", "lit"):
        TTs[rule] = set_targets(trades_of(T, rule, name), key)
    for nm, lo, hi in PERIODS:
        m, days = money(TTs["usd500"], lo, hi)
        st = rstats(d, T, lo, hi)
        ldays = rl.days_of([t for t in lit_T if lo <= t["day"] <= hi], sessions_in(lo, hi))
        rep["periods"][nm] = {"R": st, "usd500": m, "corr_lit": corr(ldays, days, lo, hi)}
        rep["sizing"][nm] = {}
        for rule in ("usd300", "usd800", "lit"):
            mm, _ = money(TTs[rule], lo, hi)
            rep["sizing"][nm][rule] = {k: mm.get(k) for k in ("n", "net", "per_month", "pf", "dd", "p10", "f10", "p20", "f20")}
    # eval-safe sizing alone + with LIT
    ev_alone = eval_path(T, "usd500")
    ev_alone8 = eval_path(T, "usd800")
    lit_eval_days = {x: v for x, v in lite_days.items()}
    ev_l = eval_path([], lit_days=lit_eval_days, lit_trades=lite_T)
    rep["eval"]["lit_alone"] = {"H1": eval_sum(ev_l, "2026-01-01", "2026-06-30"), "H2": eval_sum(ev_l, "2026-07-01", "2026-12-31"),
                                "2026": eval_sum(ev_l, "2026-01-01", "2026-12-31")}
    for mode in ("max2", "max1"):
        sk = lit_skip(lite_T, mode)
        f2 = (lambda sk, skip: (lambda x: sk(x) or (skip is not None and skip(x))))(sk, skip)
        T2 = run_key(key, skip=f2)
        Lk, lost = combine(lite_T, set_targets(trades_of(T2, "usd500", name), key), mode)
        kept = {t["day"] for t in Lk}
        ev_c = eval_path(T2, "usd500", lit_days={k: v for k, v in lit_eval_days.items() if k in kept}, lit_trades=Lk)
        rep["eval"]["with_lit_" + mode] = {"H1": eval_sum(ev_c, "2026-01-01", "2026-06-30"), "H2": eval_sum(ev_c, "2026-07-01", "2026-12-31"),
                                           "2026": eval_sum(ev_c, "2026-01-01", "2026-12-31"), "lit_lost": len(lost)}
        # $ on one account: LIT size rule (lit_live) + SR at $500 risk
        sk2 = lit_skip(lit_T, mode)
        f3 = (lambda sk, skip: (lambda x: sk(x) or (skip is not None and skip(x))))(sk2, skip)
        T3 = set_targets(trades_of(run_key(key, skip=f3), "usd500", name), key)
        L3, lost3 = combine(lit_T, T3, mode)
        rep["combo"][mode] = {}
        for nm, lo, hi in PERIODS:
            S = sessions_in(lo, hi)
            ld = rl.days_of([t for t in L3 if lo <= t["day"] <= hi], S)
            sd = rl.days_of([t for t in T3 if lo <= t["day"] <= hi], S)
            both = [{"date": a["date"], "pnl": a["pnl"] + b["pnl"], "low": min(a["low"], a["pnl"] + b["low"]), "trades": a["trades"] + b["trades"]}
                    for a, b in zip(ld, sd)]
            eq = np.cumsum([x["pnl"] for x in both]); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(eq) else 0.0
            lit_only = sum(t["pnl"] for t in lit_T if lo <= t["day"] <= hi)
            lit_only_eq = np.cumsum([x["pnl"] for x in rl.days_of([t for t in lit_T if lo <= t["day"] <= hi], S)])
            lit_dd = float((lit_only_eq - np.maximum.accumulate(np.r_[0, lit_only_eq])[1:]).min()) if len(lit_only_eq) else 0.0
            ee = rl.eval_speed(both) if nm in ("H1", "H2", "2026") else {}
            rep["combo"][mode][nm] = {"sr_n": sum(1 for t in T3 if lo <= t["day"] <= hi), "sr_net": round(sum(t["pnl"] for t in T3 if lo <= t["day"] <= hi)),
                                      "lit_net_kept": round(sum(t["pnl"] for t in L3 if lo <= t["day"] <= hi)), "lit_net_alone": round(lit_only),
                                      "lit_dd_alone": round(lit_dd), "lit_lost": sum(1 for t in lost3 if lo <= t["day"] <= hi),
                                      "net": round(float(eq[-1])) if len(eq) else 0, "dd": round(dd),
                                      "per_month": round(float(eq[-1]) / max(len(S) / 21, 1e-9)) if len(eq) else 0,
                                      **{k: ee.get(k) for k in ("p10", "f10", "p20", "f20")}}
    for nm, lo, hi in PERIODS:
        rep["eval"].setdefault("alone_usd500_cap", {})[nm] = eval_sum(ev_alone, lo, hi)
        rep["eval"].setdefault("alone_usd800_cap", {})[nm] = eval_sum(ev_alone8, lo, hi)
    rep["trades"] = TTs
    return rep


def print_report(rep):
    print(fmt(rep["key"]))
    for nm, v in rep["periods"].items():
        m, R = v["usd500"], v["R"]
        print(f"  {nm:<8} n={R['n']:<4} tpw={R['tpw']:<5} R={R['R']:+7.1f} avgR={R['exp']:+.3f} PF(R)={R['pf']} win={R['win']}% | $500: "
              f"net={m.get('net', 0):+,} /mo={m.get('per_month', 0):+,} pf={m.get('pf')} dd={m.get('dd')} ev2w={m.get('p10')}/{m.get('f10')} "
              f"1mo={m.get('p20')}/{m.get('f20')} corrLIT={v['corr_lit']}")
    for nm, v in rep["sizing"].items():
        print(f"  {nm:<8} " + "  ".join(f"{k}: {x['net']:+,} dd={x.get('dd')}" for k, x in v.items()))
    for k, v in rep["eval"].items():
        print("  eval", k, {a: (b["p10"], b["f10"], b["p20"], b["f20"]) for a, b in v.items() if isinstance(b, dict)}, v.get("lit_lost", ""))
    for mode, v in rep["combo"].items():
        for nm, x in v.items():
            print(f"  combo {mode} {nm:<8} {x}")


# ------------------------------------------------------------------------------------------------ look-ahead check
def lookahead(key, skip=None, sample=None):
    """Every trade re-derived from data cut right after its signal bar (bars [0, signal + 1)): the same signal bar,
    direction, stop, order price (limits) and the same known levels / VIX band for the target must come out."""
    global ONLY_S, PENDING
    d = data()
    T = run_key(key, skip=skip)
    if sample:
        T = T[-sample:]
    g = {k: key[k] for k in GEN_KEYS[key["setup"]]}
    bad = []
    try:
        PENDING = True
        for x, r in T:
            ONLY_S = {x["s"]}
            dc = data(cut=x["sig"] + 1)
            cc = gen(dc, key["setup"], g)
            m = [c for c in cc if c[0] == x["sig"] and c[2] == x["dir"]]
            ok = False
            for c in m:
                same_stop = abs(c[5] * x["dir"] - x["stop"]) < 1e-6
                kn = sorted(x["dir"] * v for v in c[7])
                lv_ok = True
                if key["tg"] == "lvl":
                    want = x["tl"]["lvl"]
                    got = [v for v in kn if v >= x["e"] + key.get("min_rr", 1.5) * x["risk"]]
                    lv_ok = bool(got) and abs(got[0] - want) < 1e-6
                if key["tg"] == "vix":
                    vm = dc["vixmove"].get(x["s"])
                    lv_ok = vm is not None and abs(dc["open18"][x["s"]] * x["dir"] + vm - x["tl"]["vix"]) < 1e-6
                px_ok = True
                if x["kind"] == 1:
                    px_ok = c[1] == -2
                if same_stop and lv_ok and px_ok:
                    ok = True
            if not ok:
                bad.append((d["days"][x["s"]], int(x["sig"])))
    finally:
        ONLY_S, PENDING = None, False
    return {"checked": len(T), "flagged": len(bad), "bad": bad[:20]}


# ------------------------------------------------------------------------------------------------ final versions
FINAL = {        # name -> {"key": ..., "filter": stage-2 filter name, "rules": plain words}; the refinement round's H1 pick
    "nyreclaim": {
        "title": "NY sweep-and-reclaim of the day's levels (09:30-12:00, 2R)",
        "key": dict(setup="reclaim", lv="all_or", depth=0.0, W=4, conf="close", disp=0.3, idm=True, entry="mkt", win="ny12",
                    maxpd=1, max_stop=80.0, min_rr=1.5, tg=2.0, bk=None, be=None, tc=True),
        "filter": "none", "sizing": "usd500", "status": "promising",
        "verdict": "Picked on 2026 H1 (plateau), positive on the untouched 2026 H2 and on 2025 / 2021-24; thin edge outside 2026",
        "rules": [
            "Levels (each known before it is used): yesterday's RTH high/low (09:30-16:00), the overnight high/low (18:00-09:30, "
            "from 09:30), the Asia box 20:00-24:00 high/low (from 00:00), the London box 02:00-05:00 high/low (from 05:00), last "
            "week's high/low, the opening range 09:30-10:00 high/low (from 10:00).",
            "Only the first time price trades through a level that day counts (a 5m bar whose low goes under a level the bar "
            "before closed above = a sweep of sell-side, long setup; mirror for shorts).",
            "Inducement first: a 5m swing low (2 bars each side) between the level and 1 ATR above it, formed in the 3 hours "
            "before the sweep, was taken on the way down.",
            "Reclaim: within 4 bars (the sweep bar included) a 5m candle closes back above the level, green, with a body of at "
            "least 0.3 x ATR(14, 5m).",
            "Entry: market at the next 5m open (+1 tick slippage), only 09:30-12:00 ET, 1 trade a day, no trade while one is open.",
            "Stop: 1 tick beyond the sweep extreme (the lowest low from the sweep bar to the reclaim bar); stops of 6-80 pts only. "
            "Size follows the stop ($500 / (stop x $2) micros, max 40).",
            "Target: 2R. No breakeven move. LIT's 15-minute check: 15 minutes after the fill, if the trade never reached +0.5R "
            "and the 5m close is more than 0.3R against, exit at the next open. Flat at 15:55.",
        ],
    },
}


def clean(TT):
    out = []
    for t in TT:
        if t["day"] < "2021-11-01":
            continue
        out.append({k: (float(v) if isinstance(v, (np.floating,)) else int(v) if isinstance(v, np.integer) else v)
                    for k, v in t.items() if not k.startswith("_")})
    return out


def cmd_final():
    from tools import runlib as rl
    F = stage2_filters()
    allrep = {}
    for name, spec in FINAL.items():
        key, fl = spec["key"], spec.get("filter", "none")
        skip = F[fl]
        rep = report(key, skip=skip, name=name)
        print_report(rep)
        la = lookahead(key, skip=skip)
        print("  look-ahead:", la)
        rep["lookahead"] = la
        S_all = rs.sessions()
        for rule in ("usd500", "usd300", "lit"):
            TT = clean(rep["trades"][rule])
            rl.save(f"sr2_{name}_{rule}", f"Second strategy (S/R): {spec['title']}, {rule}", "other",
                    "A support/resistance strategy to trade alongside LIT (owner 2026-10-22), picked on 2026 H1, checked on H2",
                    params={"key": key, "filter": fl, "costs": "$1.90/micro + 1 tick"}, sizing={"rule": rule},
                    trades=TT, scored=rl.score(TT, S_all), status=spec.get("status", "promising"), verdict=spec.get("verdict", ""),
                    writeup="second-sr")
        # LIT + SR on one account (LIT priority, max 2 a day), both at their size rules (LIT rule / SR $500)
        lit_T, _ = lit_run("lit_live")
        T3 = clean(set_targets(trades_of(run_key(key, skip=(lambda sk: lambda x: sk(x) or (skip is not None and skip(x)))(
            lit_skip(lit_T, "max2"))), "usd500", name), key))
        both = sorted(lit_T + T3, key=lambda t: t["entry_t"])
        rl.save(f"sr2_{name}_with_lit", f"LIT (lit_live) + second strategy {spec['title']} on one account (max 2 a day)", "other",
                "LIT and the S/R strategy on the same account, LIT priority (SR skipped while LIT is open)",
                params={"key": key, "filter": fl, "lit": "lit_live", "mode": "max2"}, sizing={"lit": "LIT rule", "sr": "usd500"},
                trades=both, scored=rl.score(both, S_all), status="info", writeup="second-sr")
        rep["trades"] = None
        allrep[name] = rep
    json.dump(allrep, open(os.path.join(OUT, "sr_final.json"), "w"), indent=1, default=float)
    # common-format trades of the best version
    best = next(iter(FINAL))
    spec = FINAL[best]
    rep = report(spec["key"], skip=F[spec.get("filter", "none")], name=best)
    TT = clean(rep["trades"][spec.get("sizing", "usd500")])
    cols = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind", "r", "qty", "pnl_usd", "setup")
    json.dump({"name": best, "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "params": {**spec["key"], "filter": spec.get("filter", "none"),
               "sizing": spec.get("sizing", "usd500"), "costs": "$1.90 a micro round trip + 1 tick slippage on market entries and stop / time / flat exits",
               "data": "TradingView CME NQ1! 5m (data/NQ_5m.csv)", "code": "tools/second_sr.py"},
               "rules": spec["rules"], "trades": [{c: t[c] for c in cols} for t in TT]},
              open(os.path.join(OUT, "sr_best.json"), "w"), indent=1)
    print("wrote sr_best.json", len(TT))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        cmd_grid()
    elif cmd == "pick":
        cmd_pick()
    elif cmd == "refine":
        cmd_refine()
    elif cmd == "stage2":
        cmd_stage2()
    elif cmd == "final":
        cmd_final()
    elif cmd == "lookahead":
        for nm, sp in FINAL.items():
            print(nm, lookahead(sp["key"], skip=stage2_filters()[sp.get("filter", "none")]))
