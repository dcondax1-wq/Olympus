"""Momentum / breakout / continuation scalp families (owner 2026-10-28, third strategy on its own MFFU account).

Each family turns CME NQ1! bars into candidate orders (tools/scalp_mo_lib.cands) using only what is known at the signal bar's
close; tools/scalp_mo_lib.simulate executes them (one position, max trades a day, daily stop in R, flat 15:55, costs and
slippage in). Families:

  orb     opening-range breakout (London 03:00 / NY 09:30, 5/15/30-min range): resting stop orders 1 tick beyond the
          range; stop = other side / middle of the range / k ATR; target rr or trail; first break each side
  orbc    the same, entry on the first bar CLOSE beyond the range (market at the next open)
  disp    displacement candle (body > k ATR, close in its outer quarter) -> limit at 50% of the body (or the FVG edge), stop
          1 tick beyond the candle, rr target, optional higher-timeframe trend filter
  cisd    CISD continuation: a close beyond the open of the last opposite run (2+ candles) that made an N-bar swing, in the
          direction of the 15m / 1h trend; stop beyond the run's extreme
  emapb   EMA pullback: 9 > 21 > 50 on the bar timeframe (+ 15m trend up), the bar touched the 21 EMA and closes back above the
          9 EMA; stop beyond the pullback low (last m bars)
  nbar    close beyond the prior N bars' high / low in the 1h trend (A09 style), stop beyond the last m bars
  news    08:30 / 10:00 bar: body > k ATR -> continuation at the next open (or 50% limit); stop beyond the bar
  tday    trend day: 09:30-10:30 range >= k x its 20-day average and the 10:30 close in the outer quarter -> only that side;
          add-on scalps (n-bar breakouts or EMA pullbacks) 10:30-15:30
  na      noise-area momentum (Zarattini 2024) as a scalp: close outside the time-of-day noise band from the 09:30 open,
          checked every bar; stop k ATR / VWAP, rr target or trail, re-entries allowed
  esl     ES leads NQ (5m, 2025-04 on): ES closes at a new RTH high (low) while NQ does not -> NQ in ES's direction

    python -X utf8 tools/scalp_mo.py grid [family ...]    # grid on 1m 2026 + 5m 2021-26 -> research/scalp/mo_grid_<fam>.json
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import time

import warnings

import numpy as np

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import scalp_mo_lib as L  # noqa: E402

OUT = os.path.join(ROOT, "research", "scalp")
T_ = L.TICK
NAN = np.nan


def _tf_bars(B, minutes):
    return max(1, int(round(minutes / B["tf"])))


def _trend(B, i, mode):
    """+1 / -1 / 0 trend known at bar i's close."""
    if mode == "none":
        return 0
    if mode == "h1":
        s = B["h1_sl20"][i]
    elif mode == "m15":
        s = B["m15_sl20"][i]
    elif mode == "h1c":
        s = B["c"][i] - B["h1_ema50"][i]
    elif mode == "vwap":
        s = B["c"][i] - B["vwap"][i]
    else:
        raise ValueError(mode)
    if np.isnan(s):
        return 0
    return 1 if s > 0 else (-1 if s < 0 else 0)


def _ok_trend(B, i, D, mode):
    return mode == "none" or _trend(B, i, mode) == D


def _days(B):
    """(day id, first index, flat index) of every tradable day."""
    d = B["day"]
    starts = np.r_[0, np.where(np.diff(d) != 0)[0] + 1]
    out = []
    for s in starts:
        di = d[s]
        f = B["flat_of_day"][di]
        if f >= 0:
            out.append((di, s, f))
    return out


def _stack(rows):
    if not rows:
        return L.cands({"sig": [], "dir": []})
    keys = set().union(*[r.keys() for r in rows])
    return L.cands({k: [r.get(k, NAN if k not in ("prio",) else 0) for r in rows] for k in keys})


def _exit_kw(p):
    kw = {"tgt_r": p.get("rr", 1.0), "hold": _tf_hold(p)}
    if p.get("be"):
        kw["be_r"] = p["be"]
    if p.get("trail"):
        kw["trail_r"] = p["trail"]; kw["trail_start"] = p.get("trail_start", 1.0); kw["tgt_r"] = p.get("rr", 20.0)
    return kw


def _tf_hold(p):
    return p.get("_hold_bars", 10 ** 6)


# ================================================================================================ families
def fam_orb(B, p):
    s0, rng, smode = p["start"], p["range"], p["stop"]
    end_mod = p.get("until", s0 + 120)
    close_entry = p.get("close", False)
    rows = []
    m = B["mod"]
    h, l, c, a = B["h"], B["l"], B["c"], B["atr"]
    for di, s, f in _days(B):
        idx = np.arange(s, f + 1)
        rmask = (m[idx] >= s0) & (m[idx] < s0 + rng)
        if rmask.sum() < max(1, rng // B["tf"] - 1):
            continue
        ri = idx[rmask]
        e = ri[-1]
        hi, lo = h[ri].max(), l[ri].min()
        width = hi - lo
        if width <= 0 or (p.get("maxw_atr") and width > p["maxw_atr"] * a[e] * np.sqrt(rng / B["tf"])):
            continue
        mid = (hi + lo) / 2
        w = idx[(idx > e) & (m[idx] < end_mod)]
        if len(w) == 0:
            continue
        for D in (1, -1):
            if p.get("side") and D != p["side"]:
                continue
            lv = hi + T_ if D > 0 else lo - T_
            if close_entry:
                hit = np.where(c[w] > hi if D > 0 else c[w] < lo)[0]
            else:
                hit = np.where(h[w] >= lv if D > 0 else l[w] <= lv)[0]
            if len(hit) == 0:
                continue
            j = w[hit[0]]
            sig = j if close_entry else j - 1
            if not _ok_trend(B, sig, D, p.get("trend", "none")):
                continue
            if smode == "opp":
                st = lo - T_ if D > 0 else hi + T_
            elif smode == "mid":
                st = mid - T_ if D > 0 else mid + T_
            else:
                ref = c[j] if close_entry else lv
                st = ref - D * float(smode[3:]) * a[sig]
            row = {"sig": sig, "dir": D, "stop": st, **_exit_kw(p), "prio": 0 if D > 0 else 1}
            if not close_entry:
                row.update(kind=1, level=lv, expiry=1)
            rows.append(row)
    return _stack(rows)


def fam_disp(B, p):
    k, q = p["k"], p.get("q", 0.25)
    w0, w1 = p["win"]
    o, h, l, c, a, m = B["o"], B["h"], B["l"], B["c"], B["atr"], B["mod"]
    body = c - o
    rngb = h - l
    pa = np.r_[a[0], a[:-1]]
    big = np.abs(body) > k * pa
    pos = np.where(rngb > 0, (c - l) / np.where(rngb > 0, rngb, 1), 0.5)
    rows = []
    exp = p.get("expiry", 6)
    for i in np.where(big & (m >= w0) & (m < w1))[0]:
        if i < 2 or i >= len(c) - 2:
            continue
        D = 1 if body[i] > 0 else -1
        if (D > 0 and pos[i] < 1 - q) or (D < 0 and pos[i] > q):
            continue
        if not _ok_trend(B, i, D, p.get("trend", "none")):
            continue
        ent = p.get("entry", "half")
        if ent == "fvg":
            # FVG needs bar i+1: gap between bar i-1 and bar i+1
            j = i + 1
            if D > 0 and l[j] > h[i - 1]:
                lv = l[j]
            elif D < 0 and h[j] < l[i - 1]:
                lv = h[j]
            else:
                continue
            sig = j
        elif ent == "mkt":
            sig, lv = i, NAN
        else:
            sig, lv = i, (o[i] + c[i]) / 2
        st = (l[i] - T_) if D > 0 else (h[i] + T_)
        if p.get("stop") == "half_ext":     # tighter: beyond 50% by the same distance as entry to close
            st = lv - D * (abs(c[i] - lv)) if not np.isnan(lv) else st
        row = {"sig": sig, "dir": D, "stop": st, **_exit_kw(p)}
        if ent != "mkt":
            row.update(kind=2, level=lv, expiry=exp)
        rows.append(row)
    return _stack(rows)


def fam_cisd(B, p):
    o, h, l, c, m = B["o"], B["h"], B["l"], B["c"], B["mod"]
    w0, w1 = p["win"]
    N = p.get("swing", 10)
    minrun = p.get("run", 2)
    rows = []
    n = len(c)
    up = c > o
    dn = c < o
    # for every bar the start of the latest run of down (up) candles that ended at i-1 or earlier within 'age' bars
    age = p.get("age", 3)
    for i in np.where((m >= w0) & (m < w1))[0]:
        if i < N + 5:
            continue
        for D in (1, -1):
            opp = dn if D > 0 else up
            # find the last opposite run ending within age bars before i
            j = i - 1
            while j > i - 1 - age and not opp[j]:
                j -= 1
            if j <= i - 1 - age or not opp[j]:
                continue
            e = j
            while j - 1 >= 0 and opp[j - 1]:
                j -= 1
            if e - j + 1 < minrun:
                continue
            ref = o[j]
            if D > 0:
                if not (c[i] > ref and c[i - 1] <= ref):
                    continue
                ext = l[j:i + 1].min()
                if ext > l[i - N:i + 1].min():
                    continue
                st = ext - T_
            else:
                if not (c[i] < ref and c[i - 1] >= ref):
                    continue
                ext = h[j:i + 1].max()
                if ext < h[i - N:i + 1].max():
                    continue
                st = ext + T_
            if not _ok_trend(B, i, D, p.get("trend", "m15")):
                continue
            if p.get("max_stop_atr") and abs(c[i] - st) > p["max_stop_atr"] * B["atr"][i]:
                continue
            rows.append({"sig": i, "dir": D, "stop": st, **_exit_kw(p)})
    return _stack(rows)


def fam_emapb(B, p):
    o, h, l, c, m = B["o"], B["h"], B["l"], B["c"], B["mod"]
    e9, e21, e50 = B["ema9"], B["ema21"], B["ema50"]
    w0, w1 = p["win"]
    lb = p.get("lb", 3)
    rows = []
    for i in np.where((m >= w0) & (m < w1))[0]:
        if i < lb + 2:
            continue
        for D in (1, -1):
            if D > 0:
                if not (e9[i] > e21[i] > e50[i]):
                    continue
                if not (l[i - lb + 1:i + 1].min() <= e21[i]) or not (c[i] > e9[i] and c[i] > o[i]):
                    continue
                if c[i - 1] > e9[i - 1] and l[i] > e21[i]:
                    continue   # the touch must be part of this pullback, the close back above the 9 must be new
                st = l[i - lb + 1:i + 1].min() - T_
            else:
                if not (e9[i] < e21[i] < e50[i]):
                    continue
                if not (h[i - lb + 1:i + 1].max() >= e21[i]) or not (c[i] < e9[i] and c[i] < o[i]):
                    continue
                if c[i - 1] < e9[i - 1] and h[i] < e21[i]:
                    continue
                st = h[i - lb + 1:i + 1].max() + T_
            if not _ok_trend(B, i, D, p.get("trend", "m15")):
                continue
            if p.get("max_stop_atr") and abs(c[i] - st) > p["max_stop_atr"] * B["atr"][i]:
                continue
            rows.append({"sig": i, "dir": D, "stop": st, **_exit_kw(p)})
    return _stack(rows)


def fam_nbar(B, p):
    h, l, c, m = B["h"], B["l"], B["c"], B["mod"]
    N, sb = p["n"], p.get("sb", 3)
    w0, w1 = p["win"]
    rows = []
    from numpy.lib.stride_tricks import sliding_window_view as swv
    hh = np.r_[np.full(N, np.inf), swv(h, N).max(axis=1)[:-1]]
    ll = np.r_[np.full(N, -np.inf), swv(l, N).min(axis=1)[:-1]]
    for i in np.where((m >= w0) & (m < w1))[0]:
        if i < N + sb:
            continue
        for D in (1, -1):
            if D > 0 and not (c[i] > hh[i] and c[i - 1] <= hh[i - 1]):
                continue
            if D < 0 and not (c[i] < ll[i] and c[i - 1] >= ll[i - 1]):
                continue
            if not _ok_trend(B, i, D, p.get("trend", "h1")):
                continue
            st = (l[i - sb + 1:i + 1].min() - T_) if D > 0 else (h[i - sb + 1:i + 1].max() + T_)
            if p.get("stop_atr"):
                st = c[i] - D * p["stop_atr"] * B["atr"][i]
            if p.get("max_stop_atr") and abs(c[i] - st) > p["max_stop_atr"] * B["atr"][i]:
                continue
            rows.append({"sig": i, "dir": D, "stop": st, **_exit_kw(p)})
    return _stack(rows)


def fam_news(B, p):
    o, h, l, c, a, m = B["o"], B["h"], B["l"], B["c"], B["atr"], B["mod"]
    rows = []
    span = p.get("bar_min", 5)            # the release candle = the first span minutes after the release
    nb = _tf_bars(B, span)
    for t0 in p["times"]:
        for di, s, f in _days(B):
            idx = np.arange(s, f + 1)
            r = idx[(m[idx] >= t0) & (m[idx] < t0 + span)]
            if len(r) < nb:
                continue
            i0, i1 = r[0], r[-1]
            bo, bc, bh, bl = o[i0], c[i1], h[r].max(), l[r].min()
            ref = a[i0 - 1] * np.sqrt(nb)
            if abs(bc - bo) < p["k"] * ref:
                continue
            D = 1 if bc > bo else -1
            if not _ok_trend(B, i1, D, p.get("trend", "none")):
                continue
            st = (bl - T_) if D > 0 else (bh + T_)
            if p.get("entry") == "half":
                lv = (bo + bc) / 2
                rows.append({"sig": i1, "dir": D, "kind": 2, "level": lv, "expiry": p.get("expiry", 6), "stop": st, **_exit_kw(p)})
            else:
                rows.append({"sig": i1, "dir": D, "stop": st, **_exit_kw(p)})
    return _stack(rows)


def _first_hour(B):
    """per day: (dir, ok) of a trend day from 09:30-10:30, using the prior 20 days' first-hour range."""
    h, l, c, m = B["h"], B["l"], B["c"], B["mod"]
    rngs, out = [], {}
    for di, s, f in _days(B):
        idx = np.arange(s, f + 1)
        r = idx[(m[idx] >= 570) & (m[idx] < 630)]
        if len(r) < 3:
            continue
        hi, lo, cl = h[r].max(), l[r].min(), c[r[-1]]
        rg = hi - lo
        avg = np.mean(rngs[-20:]) if len(rngs) >= 10 else np.nan
        rngs.append(rg)
        pos = (cl - lo) / rg if rg > 0 else 0.5
        out[di] = (rg / avg if avg == avg else np.nan, pos, r[-1])
    return out


def fam_tday(B, p):
    FH = _first_hour(B)
    sub = p["sub"]
    base = fam_nbar(B, {**p, **sub, "win": (630, 930), "trend": "none"}) if sub["kind"] == "nbar" else \
        fam_emapb(B, {**p, **sub, "win": (630, 930), "trend": "none"})
    keep = np.zeros(len(base["sig"]), bool)
    for q in range(len(base["sig"])):
        i = int(base["sig"][q])
        x = FH.get(int(B["day"][i]))
        if not x or not (x[0] >= p["k"]):
            continue
        D = 1 if x[1] >= 1 - p.get("q", 0.25) else (-1 if x[1] <= p.get("q", 0.25) else 0)
        keep[q] = D != 0 and base["dir"][q] == D and i > x[2]
    return {k: v[keep] for k, v in base.items()}


def _noise(B, lookback=14):
    """sigma(mod) per day: mean over the prior `lookback` days of |close / open_0930 - 1| at that minute of day."""
    c, m = B["c"], B["mod"]
    D = _days(B)
    tf = B["tf"]
    slots = np.arange(570, 960, tf)
    hist = []
    sig = np.full(len(c), np.nan)
    op = np.full(len(c), np.nan)
    prevc = np.nan
    for di, s, f in D:
        idx = np.arange(s, f + 1)
        r = idx[m[idx] >= 570]
        if len(r) == 0:
            continue
        o0 = B["o"][r[0]]
        mv = np.full(len(slots), np.nan)
        pos = ((m[r] - 570) // tf).astype(int)
        ok = pos < len(slots)
        mv[pos[ok]] = np.abs(c[r[ok]] / o0 - 1)
        if len(hist) >= lookback:
            sg = np.nanmean(np.array(hist[-lookback:]), axis=0)
            sig[r[ok]] = sg[pos[ok]]
            op[r] = o0 if np.isnan(prevc) else o0  # reference open
        hist.append(mv)
        prevc = c[f]
    return sig, op


def fam_na(B, p):
    sig, op = _noise(B)
    c, m, a, vw = B["c"], B["mod"], B["atr"], B["vwap"]
    vm = p.get("vm", 1.0)
    w0, w1 = p["win"]
    every = _tf_bars(B, p.get("every", 5))
    rows = []
    up = op * (1 + vm * sig)
    lo = op * (1 - vm * sig)
    for i in np.where((m >= w0) & (m < w1) & ~np.isnan(sig))[0]:
        if ((m[i] + B["tf"] - 570) // B["tf"]) % every:
            continue
        for D in (1, -1):
            if D > 0 and not (c[i] > up[i]):
                continue
            if D < 0 and not (c[i] < lo[i]):
                continue
            if p.get("fresh") and ((D > 0 and c[i - 1] > up[i - 1]) or (D < 0 and c[i - 1] < lo[i - 1])):
                continue
            if p["stop"] == "band":
                st = (max(up[i], vw[i]) if D > 0 else min(lo[i], vw[i])) if not np.isnan(vw[i]) else (up[i] if D > 0 else lo[i])
                if D * (c[i] - st) < 2 * T_:
                    st = c[i] - D * 0.5 * a[i]
            else:
                st = c[i] - D * float(p["stop"][3:]) * a[i]
            rows.append({"sig": i, "dir": D, "stop": st, **_exit_kw(p)})
    return _stack(rows)


_ES = {}


def _es(B):
    if B["tf"] != 5:
        return None
    if "x" not in _ES:
        import pandas as pd
        e = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
        _ES["x"] = dict(zip(e.time.to_numpy(np.int64), zip(e.high.to_numpy(), e.low.to_numpy(), e.close.to_numpy())))
    return _ES["x"]


def fam_esl(B, p):
    E = _es(B)
    if E is None:
        return _stack([])
    h, l, c, m, t, a = B["h"], B["l"], B["c"], B["mod"], B["t"], B["atr"]
    w0, w1 = p["win"]
    rows = []
    for di, s, f in _days(B):
        if B["dates"][di] < "2025-04-14":
            continue
        idx = np.arange(s, f + 1)
        r = idx[m[idx] >= p.get("from", 570)]
        eh = el = None
        nh = nl = None
        for i in r:
            x = E.get(int(t[i]))
            if x is None:
                continue
            if eh is None:
                eh, el, nh, nl = x[0], x[1], h[i], l[i]
                continue
            if w0 <= m[i] < w1:
                for D in (1, -1):
                    if D > 0 and x[2] > eh and c[i] < nh:
                        st = c[i] - p.get("satr", 1.0) * a[i]
                        if _ok_trend(B, i, D, p.get("trend", "none")):
                            rows.append({"sig": i, "dir": 1, "stop": st, **_exit_kw(p)})
                    if D < 0 and x[2] < el and c[i] > nl:
                        st = c[i] + p.get("satr", 1.0) * a[i]
                        if _ok_trend(B, i, D, p.get("trend", "none")):
                            rows.append({"sig": i, "dir": -1, "stop": st, **_exit_kw(p)})
            eh, el = max(eh, x[0]), min(el, x[1])
            nh, nl = max(nh, h[i]), min(nl, l[i])
    return _stack(rows)


FAMS = {"orb": fam_orb, "disp": fam_disp, "cisd": fam_cisd, "emapb": fam_emapb, "nbar": fam_nbar, "news": fam_news,
        "tday": fam_tday, "na": fam_na, "esl": fam_esl}


# ================================================================================================ run one config
def run(B, fam, p, maxday=3, day_stop=2.0, max_loss=99):
    pp = dict(p)
    if p.get("hold_min"):
        pp["_hold_bars"] = _tf_bars(B, p["hold_min"])
    C = FAMS[fam](B, pp)
    X = L.simulate(B, C, maxday=maxday, day_stop_r=day_stop, max_loss=max_loss, last_mod=p.get("last_mod", 930))
    return L.to_trades(B, X)


def quick(T, B, span):
    S = L.sessions(B, span)
    return L.stats(T, S, 100.0, 40) if S else {"n": 0}


# ================================================================================================ grids
WIN = {"lon": (180, 360), "ny": (570, 690), "nyall": (570, 930), "am": (480, 690), "all": (120, 930)}


def grid_specs(fam):
    G = []
    ex_rr = [{"rr": r} for r in (1.0, 1.5, 2.0)] + [{"rr": 1.0, "be": 0.6}, {"trail": 1.0, "trail_start": 1.0}]
    hold = [None, 30]
    if fam in ("orb", "orbc"):
        for s0, rng, st, ex, tr, h in itertools.product((180, 570), (5, 15, 30), ("opp", "mid", "atr1.5"), ex_rr, ("none", "h1"), hold):
            G.append(("orb", {"start": s0, "range": rng, "stop": st, **ex, "trend": tr, "hold_min": h, "close": fam == "orbc",
                              "until": s0 + 150}))
    elif fam == "disp":
        for k, ent, w, ex, tr in itertools.product((1.5, 2.0, 3.0), ("half", "fvg", "mkt"), ("lon", "ny", "nyall"), ex_rr, ("none", "h1", "m15")):
            G.append(("disp", {"k": k, "entry": ent, "win": WIN[w], **ex, "trend": tr, "hold_min": 60}))
    elif fam == "cisd":
        for sw, w, ex, tr, ms in itertools.product((10, 20), ("lon", "ny", "nyall"), ex_rr, ("m15", "h1", "h1c"), (None, 3.0)):
            G.append(("cisd", {"swing": sw, "win": WIN[w], **ex, "trend": tr, "max_stop_atr": ms, "hold_min": 60}))
    elif fam == "emapb":
        for lb, w, ex, tr, ms in itertools.product((3, 5), ("lon", "ny", "nyall"), ex_rr, ("m15", "h1", "none"), (None, 3.0)):
            G.append(("emapb", {"lb": lb, "win": WIN[w], **ex, "trend": tr, "max_stop_atr": ms, "hold_min": 60}))
    elif fam == "nbar":
        for n, sb, w, ex, tr in itertools.product((6, 12, 24), (3, 6), ("lon", "ny", "nyall"), ex_rr, ("h1", "m15", "vwap")):
            G.append(("nbar", {"n_min": n, "sb_min": sb, "win": WIN[w], **ex, "trend": tr, "hold_min": 60, "max_stop_atr": 4.0}))
    elif fam == "news":
        for tm, k, ent, ex, bm in itertools.product(((510,), (600,), (510, 600)), (1.0, 1.5, 2.5), ("mkt", "half"), ex_rr, (1, 5)):
            G.append(("news", {"times": tm, "k": k, "entry": ent, **ex, "bar_min": bm, "hold_min": 30}))
    elif fam == "tday":
        for k, sub, ex in itertools.product((1.0, 1.3, 1.6), ({"kind": "nbar", "n_min": 12, "sb_min": 3}, {"kind": "nbar", "n_min": 30, "sb_min": 6},
                                                            {"kind": "emapb", "lb": 3}, {"kind": "emapb", "lb": 5}), ex_rr):
            G.append(("tday", {"k": k, "sub": sub, **ex, "hold_min": 60}))
    elif fam == "na":
        for vm, ev, st, ex, w, fr in itertools.product((0.75, 1.0, 1.25), (5, 15, 30), ("band", "atr1.5", "atr3"), ex_rr, ("ny", "nyall"), (True, False)):
            G.append(("na", {"vm": vm, "every": ev, "stop": st, **ex, "win": (600, WIN[w][1]), "fresh": fr}))
    elif fam == "esl":
        for satr, w, ex, tr in itertools.product((1.0, 2.0, 3.0), ("ny", "nyall"), ex_rr, ("none", "h1")):
            G.append(("esl", {"satr": satr, "win": WIN[w], **ex, "trend": tr, "hold_min": 30}))
    return G


def _resolve(B, fam, p):
    """minute parameters -> bars of this timeframe."""
    q = dict(p)
    if "n_min" in q:
        q["n"] = max(2, _tf_bars(B, q.pop("n_min")))
    if "sb_min" in q:
        q["sb"] = max(1, _tf_bars(B, q.pop("sb_min")))
    if "sub" in q:
        q["sub"] = _resolve(B, fam, q["sub"])
    return q


def _job(args):
    fam, p, tfs, md, ds = args
    out = {"fam": fam, "p": p, "maxday": md, "day_stop": ds}
    for tf in tfs:
        B = L.bars(tf)
        T = run(B, fam, _resolve(B, fam, p), maxday=md, day_stop=ds)
        for sp in (("H1", "H2") if tf == 1 else ("H1", "H2", "R")):
            out[f"{tf}m_{sp}"] = quick(T, B, sp)
    return out


def grid(fams, procs=4):
    from multiprocessing import Pool
    os.makedirs(OUT, exist_ok=True)
    L.bars(1); L.bars(5)
    for fam in fams:
        t0 = time.time()
        specs = grid_specs(fam)
        tfs = (5,) if fam == "esl" else (1, 5)
        jobs = [(f, p, tfs, md, ds) for f, p in specs for md, ds in ((3, 2.0), (6, 3.0))]
        with Pool(procs) as P:
            R = P.map(_job, jobs, chunksize=4)
        json.dump(R, open(os.path.join(OUT, f"mo_grid_{fam}.json"), "w"), default=float)
        print(fam, len(R), f"{time.time() - t0:.0f}s", flush=True)
        show(R)


def show(R, tf="1m", top=8, min_tpw=5.0):
    """H1-picked top: by H1 avg R t-stat among configs with >= min_tpw, then H2 (and the 5m reference)."""
    ok = [r for r in R if r.get(f"{tf}_H1", {}).get("tpw", 0) >= min_tpw]
    ok.sort(key=lambda r: -r[f"{tf}_H1"].get("t_r", -9))
    pos2 = sum(1 for r in ok[:20] if r.get(f"{tf}_H2", {}).get("net", -1) > 0)
    print(f"  {tf}: {len(ok)} configs >= {min_tpw}/wk; of the top 20 by H1, {pos2} positive in H2")
    for r in ok[:top]:
        a, b = r[f"{tf}_H1"], r.get(f"{tf}_H2", {})
        c = r.get("5m_R", {})
        print(f"   H1 n{a['n']} {a['tpw']}/wk pf{a['pf']} R{a['avg_r']} t{a['t_r']} ${a['net']} | H2 {b.get('tpw')}/wk pf{b.get('pf')} "
              f"R{b.get('avg_r')} ${b.get('net')} | 5mR pf{c.get('pf')} R{c.get('avg_r')} ${c.get('net')} | md{r['maxday']} {r['fam']} {json.dumps(r['p'])}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "grid":
        grid(a[1:] or list(FAMS))
