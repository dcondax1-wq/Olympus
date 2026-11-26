"""ICT lab round 2 (2026-11-25): more concepts, every test view. Rules: research/ictlab/DESIGN2.md (pre-registered).

    python -X utf8 research/ictlab/ict_lab2.py      -> research/ictlab/results2.json, trades2.json
"""
import datetime as dt
import itertools
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ict_lab as L1  # noqa: E402

P, T, TICK, FEE, PTV = L1.P, L1.T, L1.TICK, L1.FEE, L1.PTV
first_at, execute, first_fill, bias_trade, overnight = L1.first_at, L1.execute, L1.first_fill, L1.bias_trade, L1.overnight
RNG = np.random.default_rng(20261126)
NDRAW = 500
FULL = L1.FULL_YEARS
INF = 1e12


# ================================================================================================ indicators
def indicators(B):
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    v = df["volume"].to_numpy(float)
    assert len(v) == len(B["t"])
    B["v"] = v
    h, l, c, o = B["h"], B["l"], B["c"], B["o"]
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    B["atr"] = pd.Series(tr).rolling(14, min_periods=1).mean().to_numpy()
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean()
    B["rsi"] = (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).to_numpy()
    e12 = pd.Series(c).ewm(span=12, adjust=False).mean()
    e26 = pd.Series(c).ewm(span=26, adjust=False).mean()
    m = e12 - e26
    B["macdh"] = (m - m.ewm(span=9, adjust=False).mean()).to_numpy()
    B["vavg"] = pd.Series(v).rolling(20, min_periods=1).mean().shift(1).bfill().to_numpy()
    body = abs(c - o)
    B["bmed"] = pd.Series(body).rolling(20, min_periods=5).median().shift(1).bfill().to_numpy()
    # session VWAP / SD from 09:30 (NaN before)
    vw = np.full(len(c), np.nan)
    sd = np.full(len(c), np.nan)
    for sdate, a, b in B["sess"]:
        j = first_at(B, a, b, T(9, 30))
        if j is None:
            continue
        tp = (h[j:b] + l[j:b] + c[j:b]) / 3
        vv = np.maximum(v[j:b], 1.0)
        cv = np.cumsum(vv)
        m1 = np.cumsum(tp * vv) / cv
        m2 = np.cumsum(tp * tp * vv) / cv
        vw[j:b] = m1
        sd[j:b] = np.sqrt(np.maximum(0.0, m2 - m1 * m1))
    B["vwap"], B["vsd"] = vw, sd


def value_area(B, a, b):
    """RTH 09:30-16:00 volume profile in 5-pt bins -> (VAL, VAH, POC) or None."""
    j0 = first_at(B, a, b, T(9, 30))
    if j0 is None:
        return None
    h, l, v, sm = B["h"], B["l"], B["v"], B["sm"]
    ii = [i for i in range(j0, b) if sm[i] < T(16, 0)]
    if len(ii) < 20:
        return None
    lo = math.floor(min(l[i] for i in ii) / 5) * 5
    hi = math.ceil(max(h[i] for i in ii) / 5) * 5
    nb = int((hi - lo) / 5) + 1
    prof = np.zeros(nb)
    for i in ii:
        b0, b1 = int((l[i] - lo) // 5), int((h[i] - lo) // 5)
        prof[b0:b1 + 1] += v[i] / (b1 - b0 + 1)
    poc = int(np.argmax(prof))
    tot, acc = prof.sum(), prof[poc]
    lo_i = hi_i = poc
    while acc < 0.7 * tot and (lo_i > 0 or hi_i < nb - 1):
        dn = prof[lo_i - 1] if lo_i > 0 else -1
        upv = prof[hi_i + 1] if hi_i < nb - 1 else -1
        if upv >= dn:
            hi_i += 1
            acc += prof[hi_i]
        else:
            lo_i -= 1
            acc += prof[lo_i]
    return lo + lo_i * 5, lo + hi_i * 5 + 5, lo + poc * 5 + 2.5


def build_ctx2(B, C):
    """adds weekly levels, value areas, 20-day range, the prior 3 days' box to round 1's per-session context."""
    S = B["sess"]
    h, l, c, o = B["h"], B["l"], B["c"], B["o"]
    weeks = []                                   # list of dicts per week
    cur = None
    prev_va = None
    daily = []
    for k, (sd, a, b) in enumerate(S):
        x = C[sd]
        wk = dt.date.fromisoformat(str(sd)).isocalendar()[:2]
        if cur is None or cur["wk"] != wk:
            if cur is not None:
                weeks.append(cur)
            cur = {"wk": wk, "open": o[a], "days": []}
        dow = len(cur["days"])                   # 0 = first session of the week (Mon)
        pw = weeks[-1] if weeks else None
        if pw and pw["days"]:
            PH = max(d[0] for d in pw["days"])
            PL = min(d[1] for d in pw["days"])
            PC = pw["days"][-1][2]
            x.update({"pwh": PH, "pwl": PL, "wbias": 1 if PC > (PH + PL) / 2 else -1, "pw_range": PH - PL})
        else:
            x.update({"pwh": None, "pwl": None, "wbias": None, "pw_range": None})
        x["wopen"] = cur["open"]
        x["dow_w"] = dow
        x["wk_days"] = list(cur["days"])          # (H, L, C, O) of this week's earlier sessions
        x["wday"] = dt.date.fromisoformat(str(sd)).weekday()
        x["va"] = prev_va
        x["d20"] = (max(d[0] for d in daily[-20:]), min(d[1] for d in daily[-20:])) if len(daily) >= 20 else None
        x["box3"] = (max(d[0] for d in daily[-3:]), min(d[1] for d in daily[-3:])) if len(daily) >= 3 else None
        H, L = float(h[a:b].max()), float(l[a:b].min())
        cur["days"].append((H, L, float(c[b - 1]), float(o[a])))
        daily.append((H, L))
        prev_va = value_area(B, a, b)
    return C


# ================================================================================================ structure helpers
def pivots_known(B, i, lo):
    """confirmed pivot highs / lows with index in [lo, i-2] (a pivot needs 2 bars after it)."""
    hi = i - 2
    if hi < lo:
        return [], []
    r = np.arange(lo, hi + 1)
    return list(r[B["ph"][lo:hi + 1]]), list(r[B["pl"][lo:hi + 1]])


def breaker_events(B, a, b, m0, m1, sweep=True):
    """(m, side, zone_lo, zone_hi, stop) for each MSS bar m in [m0, m1) (session minutes): breaker (sweep) / mitigation."""
    h, l, c, o, sm = B["h"], B["l"], B["c"], B["o"], B["sm"]
    out, done = [], set()
    for m in range(a + 20, b):
        if not (m0 <= sm[m] < m1):
            continue
        PH, PL = pivots_known(B, m, max(a - 60, 0))
        for side in (1, -1):
            A_ = PH if side > 0 else PL
            C_ = PL if side > 0 else PH
            if not A_:
                continue
            ja = A_[-1]
            cs = [j for j in C_ if j > ja]
            if not cs:
                continue
            jc = cs[-1]
            if (side, ja) in done:
                continue
            ref = l[max(0, ja - 12):ja + 1].min() if side > 0 else h[max(0, ja - 12):ja + 1].max()
            swept = (l[jc] < ref) if side > 0 else (h[jc] > ref)
            if swept != sweep:
                continue
            lvl = h[ja] if side > 0 else l[ja]
            if not ((side > 0 and c[m] > lvl) or (side < 0 and c[m] < lvl)):
                continue
            done.add((side, ja))
            cand = [j for j in range(max(0, ja - 2), ja + 1) if (c[j] > o[j] if side > 0 else c[j] < o[j])]
            if not cand:
                continue
            jz = cand[-1]
            stp = l[jc] - TICK if side > 0 else h[jc] + TICK
            out.append((m, side, float(l[jz]), float(h[jz]), float(stp)))
    return out


def ob_events(B, a, b, m0, m1):
    """strict order blocks: (k_ready, side, ob_lo, ob_hi) with the displacement candle k, ready at k+1's close."""
    h, l, c, o, sm, bm = B["h"], B["l"], B["c"], B["o"], B["sm"], B["bmed"]
    out = []
    for k in range(a + 6, b - 1):
        if not (m0 <= sm[k] < m1):
            continue
        body = c[k] - o[k]
        if abs(body) < 2 * bm[k] or bm[k] <= 0:
            continue
        side = 1 if body > 0 else -1
        if side > 0 and not (l[k + 1] > h[k - 1]):
            continue
        if side < 0 and not (h[k + 1] < l[k - 1]):
            continue
        PH, PL = pivots_known(B, k, max(a - 60, 0))
        piv = PH if side > 0 else PL
        if not piv:
            continue
        lvl = h[piv[-1]] if side > 0 else l[piv[-1]]
        if not ((side > 0 and c[k] > lvl) or (side < 0 and c[k] < lvl)):
            continue
        cand = [j for j in range(k - 5, k) if (c[j] < o[j] if side > 0 else c[j] > o[j])]
        if not cand:
            continue
        j = cand[-1]
        out.append((k + 1, side, float(l[j]), float(h[j])))
    return out


def fvg_list(B, lo, hi):
    """(i, side, gap_lo, gap_hi) for FVGs completed at bar i in [lo, hi]."""
    h, l = B["h"], B["l"]
    out = []
    for i in range(max(lo, 2), hi + 1):
        if l[i] > h[i - 2]:
            out.append((i, 1, float(h[i - 2]), float(l[i])))
        elif h[i] < l[i - 2]:
            out.append((i, -1, float(h[i]), float(l[i - 2])))
    return out


# ================================================================================================ standalone rules
def s_mmbm(B, a, b, x):
    if x["pdh"] is None or x["j0"] is None:
        return []
    h, l, c, sm = B["h"], B["l"], B["c"], B["sm"]
    j83 = first_at(B, a, b, T(8, 30))
    j12 = first_at(B, a, b, T(12, 0)) or b
    if j83 is None or j83 <= x["j0"]:
        return []
    CH, CL = float(h[x["j0"]:j83].max()), float(l[x["j0"]:j83].min())
    ext = {1: None, -1: None}
    for i in range(j83, j12):
        if l[i] < x["pdl"] and (ext[1] is None or l[i] < l[ext[1]]):
            ext[1] = i
        if h[i] > x["pdh"] and (ext[-1] is None or h[i] > h[ext[-1]]):
            ext[-1] = i
        for side in (1, -1):
            e = ext[side]
            if e is None or i <= e:
                continue
            if side > 0:
                mss = float(h[max(a, e - 6):e].max()) if e > a else None
                if mss is not None and c[i] > mss:
                    return [{"kind": "market", "side": 1, "stop": float(l[e]) - TICK, "i0": i + 1, "i1": i + 1, "tgt": CH,
                             "min_rr": 1.0, "max_stop": 80.0}]
            else:
                mss = float(l[max(a, e - 6):e].min()) if e > a else None
                if mss is not None and c[i] < mss:
                    return [{"kind": "market", "side": -1, "stop": float(h[e]) + TICK, "i0": i + 1, "i1": i + 1, "tgt": CL,
                             "min_rr": 1.0, "max_stop": 80.0}]
    return []


def _brk(sweep):
    def f(B, a, b, x):
        ev = breaker_events(B, a, b, T(9, 30), T(12, 0), sweep)
        out = []
        for m, side, zl, zh, stp in ev[:1]:
            px = zh if side > 0 else zl
            out.append({"kind": "limit", "side": side, "px": px, "stop": stp, "i0": m + 1, "i1": min(b - 1, m + 12)})
        return out
    return f


def s_ob(B, a, b, x):
    for k1, side, ol, oh in ob_events(B, a, b, T(9, 30), T(12, 0))[:1]:
        px = oh if side > 0 else ol
        stp = ol - TICK if side > 0 else oh + TICK
        return [{"kind": "limit", "side": side, "px": px, "stop": stp, "i0": k1 + 1, "i1": min(b - 1, k1 + 12)}]
    return []


def s_ifvg(B, a, b, x):
    h, l, c, sm = B["h"], B["l"], B["c"], B["sm"]
    j9 = first_at(B, a, b, T(9, 30))
    j12 = first_at(B, a, b, T(12, 0)) or b
    if j9 is None:
        return []
    for i, side, gl, gh in fvg_list(B, j9, j12 - 1):
        for m in range(i + 1, min(b, i + 25)):
            if side < 0 and c[m] > gh:              # bearish gap closed through its top -> bullish IFVG
                return [{"kind": "limit", "side": 1, "px": gh, "stop": float(l[i - 2:m + 1].min()) - TICK, "i0": m + 1,
                         "i1": min(b - 1, m + 12)}]
            if side > 0 and c[m] < gl:
                return [{"kind": "limit", "side": -1, "px": gl, "stop": float(h[i - 2:m + 1].max()) + TICK, "i0": m + 1,
                         "i1": min(b - 1, m + 12)}]
    return []


def s_bpr(B, a, b, x):
    h, l = B["h"], B["l"]
    j9 = first_at(B, a, b, T(9, 30))
    j12 = first_at(B, a, b, T(12, 0)) or b
    if j9 is None:
        return []
    F = fvg_list(B, j9, j12 - 1)
    for p, (i1, s1, l1, h1) in enumerate(F):
        for i2, s2, l2, h2 in F[p + 1:]:
            if i2 - i1 > 12:
                break
            if s2 == s1:
                continue
            lo, hi = max(l1, l2), min(h1, h2)
            if lo >= hi:
                continue
            if s2 > 0:
                return [{"kind": "limit", "side": 1, "px": hi, "stop": float(l[i1 - 2:i2 + 1].min()) - TICK, "i0": i2 + 1,
                         "i1": min(b - 1, i2 + 12)}]
            return [{"kind": "limit", "side": -1, "px": lo, "stop": float(h[i1 - 2:i2 + 1].max()) + TICK, "i0": i2 + 1,
                     "i1": min(b - 1, i2 + 12)}]
    return []


def s_void(B, a, b, x):
    h, l, c, o, atr = B["h"], B["l"], B["c"], B["o"], B["atr"]
    j9 = first_at(B, a, b, T(9, 30))
    j12 = first_at(B, a, b, T(12, 0)) or b
    if j9 is None:
        return []
    for k in range(j9 + 2, j12):
        w = range(k - 2, k + 1)
        if all(c[j] > o[j] for j in w) and all(l[j] > l[j - 1] for j in w):
            if h[k] - l[k - 2] >= 2 * atr[k - 3]:
                return [{"kind": "market", "side": -1, "stop": float(h[k]) + TICK, "i0": k + 1, "i1": k + 1,
                         "tgt": (h[k] + l[k - 2]) / 2, "min_rr": 1.0}]
        if all(c[j] < o[j] for j in w) and all(h[j] < h[j - 1] for j in w):
            if h[k - 2] - l[k] >= 2 * atr[k - 3]:
                return [{"kind": "market", "side": 1, "stop": float(l[k]) - TICK, "i0": k + 1, "i1": k + 1,
                         "tgt": (h[k - 2] + l[k]) / 2, "min_rr": 1.0}]
    return []


def _sweep_side(B, a, b, H, L, m0, m1):
    return P.sweep_back(B, a, b, H, L, m0, m1)


def s_w_tue(B, a, b, x):
    if x["dow_w"] != 1 or not x["wk_days"] or x["wbias"] is None:
        return []
    MH, ML = x["wk_days"][0][0], x["wk_days"][0][1]
    H, L = (INF, ML) if x["wbias"] > 0 else (MH, -INF)
    return _sweep_side(B, a, b, H, L, T(2, 0), T(12, 0))


def s_w_wed(B, a, b, x):
    if x["dow_w"] != 2 or len(x["wk_days"]) < 2 or x["wbias"] is None:
        return []
    mon, tue = x["wk_days"][0], x["wk_days"][1]
    H2, L2 = max(mon[0], tue[0]), min(mon[1], tue[1])
    if x["wbias"] > 0 and tue[2] < mon[3]:
        return _sweep_side(B, a, b, INF, L2, T(2, 0), T(12, 0))
    if x["wbias"] < 0 and tue[2] > mon[3]:
        return _sweep_side(B, a, b, H2, -INF, T(2, 0), T(12, 0))
    return []


def s_w_thu(B, a, b, x):
    if x["dow_w"] != 3 or len(x["wk_days"]) < 3 or not x["pw_range"]:
        return []
    H3 = max(d[0] for d in x["wk_days"][:3])
    L3 = min(d[1] for d in x["wk_days"][:3])
    if H3 - L3 > 0.6 * x["pw_range"]:
        return []
    return _sweep_side(B, a, b, H3, L3, T(2, 0), T(12, 0))


def s_dor(B, a, b, x):
    if x["dol"] is None or x["tdo"] is None or x["j0"] is None:
        return []
    j83 = first_at(B, a, b, T(8, 30))
    j11 = first_at(B, a, b, T(11, 0)) or b
    if j83 is None or j83 <= x["j0"]:
        return []
    px = B["o"][j83]
    td = x["tdo"]
    if x["dol"] > 0 and px > td:
        stp = float(B["l"][x["j0"]:j83].min()) - TICK
        if stp >= td - 1:
            return []
        return [{"kind": "limit", "side": 1, "px": td, "stop": stp, "i0": j83, "i1": j11 - 1, "max_stop": 60.0}]
    if x["dol"] < 0 and px < td:
        stp = float(B["h"][x["j0"]:j83].max()) + TICK
        if stp <= td + 1:
            return []
        return [{"kind": "limit", "side": -1, "px": td, "stop": stp, "i0": j83, "i1": j11 - 1, "max_stop": 60.0}]
    return []


def s_wpo3(B, a, b, x):
    if x["dow_w"] not in (1, 2, 3) or x["wbias"] is None:
        return []
    h, l, c = B["h"], B["l"], B["c"]
    WO = x["wopen"]
    j9 = first_at(B, a, b, T(9, 30))
    j12 = first_at(B, a, b, T(12, 0)) or b
    if j9 is None:
        return []
    wl = min([d[1] for d in x["wk_days"]] + [float(l[a:j9].min())])
    wh = max([d[0] for d in x["wk_days"]] + [float(h[a:j9].max())])
    for i in range(j9, j12):
        wl, wh = min(wl, l[i]), max(wh, h[i])
        if x["wbias"] > 0 and wl < WO and c[i - 1] <= WO < c[i]:
            return [{"kind": "market", "side": 1, "stop": wl - TICK, "i0": i + 1, "i1": i + 1, "max_stop": 150.0}]
        if x["wbias"] < 0 and wh > WO and c[i - 1] >= WO > c[i]:
            return [{"kind": "market", "side": -1, "stop": wh + TICK, "i0": i + 1, "i1": i + 1, "max_stop": 150.0}]
    return []


def s_wyckoff(B, a, b, x):
    if not x["box3"]:
        return []
    BH, BL = x["box3"]
    h, l, c, v, va = B["h"], B["l"], B["c"], B["v"], B["vavg"]
    j9 = first_at(B, a, b, T(9, 30))
    j15 = first_at(B, a, b, T(15, 0)) or b
    if j9 is None:
        return []
    for k in range(j9, j15):
        if l[k] < BL:
            if v[k] > va[k]:
                return []
            for m in range(k, min(j15, k + 3)):
                if c[m] > BL:
                    return [{"kind": "market", "side": 1, "stop": float(l[k:m + 1].min()) - TICK, "i0": m + 1, "i1": m + 1}]
            return []
        if h[k] > BH:
            if v[k] > va[k]:
                return []
            for m in range(k, min(j15, k + 3)):
                if c[m] < BH:
                    return [{"kind": "market", "side": -1, "stop": float(h[k:m + 1].max()) + TICK, "i0": m + 1, "i1": m + 1}]
            return []
    return []


def s_mp80(B, a, b, x):
    if not x["va"]:
        return []
    VAL, VAH, POC = x["va"]
    h, l, c, o = B["h"], B["l"], B["c"], B["o"]
    j9 = first_at(B, a, b, T(9, 30))
    j13 = first_at(B, a, b, T(13, 0)) or b
    if j9 is None:
        return []
    op = o[j9]
    if VAL <= op <= VAH:
        return []
    run = 0
    for br in range(0, 7):
        e = j9 + 6 * br + 5
        if e >= j13:
            break
        inside = VAL < c[e] < VAH
        run = run + 1 if inside else 0
        if run >= 2:
            if op > VAH:
                return [{"kind": "market", "side": -1, "stop": float(h[j9:e + 1].max()) + TICK, "i0": e + 1, "i1": e + 1,
                         "tgt": VAL, "min_rr": 1.0}]
            return [{"kind": "market", "side": 1, "stop": float(l[j9:e + 1].min()) - TICK, "i0": e + 1, "i1": e + 1,
                     "tgt": VAH, "min_rr": 1.0}]
    return []


def s_vafade(B, a, b, x):
    if not x["va"]:
        return []
    VAL, VAH, POC = x["va"]
    j9 = first_at(B, a, b, T(9, 35))
    j15 = first_at(B, a, b, T(15, 0)) or b
    if j9 is None or not (VAL < B["o"][j9 - 1] < VAH):
        return []
    w = 0.25 * (VAH - VAL)
    return [{"kind": "limit", "side": -1, "px": VAH, "stop": VAH + w + TICK, "i0": j9, "i1": j15 - 1, "tgt": POC},
            {"kind": "limit", "side": 1, "px": VAL, "stop": VAL - w - TICK, "i0": j9, "i1": j15 - 1, "tgt": POC}]


def s_vwapsd(B, a, b, x):
    c, h, l, vw, sd = B["c"], B["h"], B["l"], B["vwap"], B["vsd"]
    j10 = first_at(B, a, b, T(10, 0))
    j15 = first_at(B, a, b, T(15, 0)) or b
    if j10 is None:
        return []
    for k in range(j10, j15 - 1):
        if np.isnan(vw[k]) or sd[k] <= 0:
            continue
        if c[k] > vw[k] + 2 * sd[k] and c[k + 1] < vw[k + 1] + 2 * sd[k + 1]:
            return [{"kind": "market", "side": -1, "stop": float(max(h[k], h[k + 1])) + TICK, "i0": k + 2, "i1": k + 2,
                     "tgt": float(vw[k + 1]), "min_rr": 1.0}]
        if c[k] < vw[k] - 2 * sd[k] and c[k + 1] > vw[k + 1] - 2 * sd[k + 1]:
            return [{"kind": "market", "side": 1, "stop": float(min(l[k], l[k + 1])) - TICK, "i0": k + 2, "i1": k + 2,
                     "tgt": float(vw[k + 1]), "min_rr": 1.0}]
    return []


def s_orbv(B, a, b, x):
    j9 = x["j930"]
    if j9 is None or j9 + 6 >= b:
        return []
    h, l, c, v = B["h"], B["l"], B["c"], B["v"]
    OH, OL = float(h[j9:j9 + 6].max()), float(l[j9:j9 + 6].min())
    mv = float(v[j9:j9 + 6].mean())
    mid = (OH + OL) / 2
    j12 = first_at(B, a, b, T(12, 0)) or b
    for k in range(j9 + 6, j12):
        if c[k] > OH:
            return [{"kind": "market", "side": 1, "stop": mid - TICK, "i0": k + 1, "i1": k + 1}] if v[k] >= 1.5 * mv else []
        if c[k] < OL:
            return [{"kind": "market", "side": -1, "stop": mid + TICK, "i0": k + 1, "i1": k + 1}] if v[k] >= 1.5 * mv else []
    return []


def _div(ind):
    def f(B, a, b, x):
        if x["pdh"] is None:
            return []
        on = overnight(B, a, b, x)
        if on is None:
            return []
        h, l, c, I = B["h"], B["l"], B["c"], B[ind]
        j9 = x["j930"]
        j12 = first_at(B, a, b, T(12, 0)) or b
        ups = [x["pdh"], on[0]]
        dns = [x["pdl"], on[1]]
        for k in range(j9, j12):
            if k < 40:
                continue
            ph = int(np.argmax(h[k - 36:k - 5])) + k - 36
            pl = int(np.argmin(l[k - 36:k - 5])) + k - 36
            for lv in ups:
                if h[k] > lv and h[k] > h[ph] and I[k] < I[ph]:
                    for m in range(k, min(j12, k + 6)):
                        if c[m] < lv:
                            return [{"kind": "market", "side": -1, "stop": float(h[k:m + 1].max()) + TICK, "i0": m + 1, "i1": m + 1}]
            for lv in dns:
                if l[k] < lv and l[k] < l[pl] and I[k] > I[pl]:
                    for m in range(k, min(j12, k + 6)):
                        if c[m] > lv:
                            return [{"kind": "market", "side": 1, "stop": float(l[k:m + 1].min()) - TICK, "i0": m + 1, "i1": m + 1}]
        return []
    return f


def s_round(B, a, b, x):
    j9 = x["j930"]
    on = overnight(B, a, b, x)
    if j9 is None or on is None:
        return []
    op = B["o"][j9]
    R = round(op / 100.0) * 100.0
    dist = abs(R - op)
    if not (15 <= dist <= 60) or (on[1] <= R <= on[0]):
        return []
    return bias_trade(B, a, b, x, 1 if R > op else -1, R, 1.0)


def s_pwfade(B, a, b, x):
    if x["pwh"] is None:
        return []
    return P.sweep_back(B, a, b, x["pwh"], x["pwl"], T(9, 30), T(15, 0))


def s_pwbrk(B, a, b, x):
    if x["pwh"] is None:
        return []
    h, l, c = B["h"], B["l"], B["c"]
    j9 = x["j930"]
    j14 = first_at(B, a, b, T(14, 0)) or b
    if j9 is None:
        return []
    for k in range(j9 + 1, j14):
        if c[k] > x["pwh"] and c[k - 1] > x["pwh"]:
            return [{"kind": "market", "side": 1, "stop": float(min(l[k], l[k - 1])) - TICK, "i0": k + 1, "i1": k + 1}]
        if c[k] < x["pwl"] and c[k - 1] < x["pwl"]:
            return [{"kind": "market", "side": -1, "stop": float(max(h[k], h[k - 1])) + TICK, "i0": k + 1, "i1": k + 1}]
    return []


STAND = [
    ("S_MMBM", "MMXM", "Market Maker Buy/Sell Model, target the consolidation", s_mmbm, "L1"),
    ("S_TURTLE", "TURTLE", "Turtle Soup (20-day false break)", None, "P_turtle"),
    ("S_BREAKER", "BRK", "Breaker block (sweep + MSS, retest)", _brk(True), "L1"),
    ("S_MITIG", "BRK", "Mitigation block (failure swing + MSS, retest)", _brk(False), "L1"),
    ("S_OB", "OB", "Strict order block retest", s_ob, "L1"),
    ("S_UNICORN", "OB", "Unicorn (breaker + FVG)", None, "P_unicorn"),
    ("S_IFVG", "FVG", "Inversion FVG retest", s_ifvg, "L1"),
    ("S_BPR", "FVG", "Balanced Price Range", s_bpr, "L1"),
    ("S_VOID", "FVG", "Liquidity void fade to its 50%", s_void, "L1"),
    ("S_W_TUE", "WEEK", "Weekly profile: Tuesday low/high of week", s_w_tue, "L1"),
    ("S_W_WED", "WEEK", "Weekly profile: Wednesday reversal", s_w_wed, "L1"),
    ("S_W_THU", "WEEK", "Weekly profile: consolidation Thursday reversal", s_w_thu, "L1"),
    ("S_DOR", "DOR", "Daily (midnight) open retracement", s_dor, "L1"),
    ("S_WPO3", "WEEK", "Weekly Power of 3 (weekly open)", s_wpo3, "L1"),
    ("S_WYCKOFF", "WYK", "Wyckoff spring / upthrust (3-day box, low volume)", s_wyckoff, "L1"),
    ("S_MP80", "MP", "Market Profile 80% rule", s_mp80, "L1"),
    ("S_VAFADE", "MP", "VAH / VAL fade to the POC", s_vafade, "L1"),
    ("S_VWAPSD", "VWAP", "VWAP 2-SD reversion to VWAP", s_vwapsd, "L1"),
    ("S_ORBV", "ORB", "Opening range breakout with volume", s_orbv, "L1"),
    ("S_DIVRSI", "DIV", "RSI divergence at PDH/PDL / overnight levels", _div("rsi"), "L1"),
    ("S_DIVMACD", "DIV", "MACD divergence at levels", _div("macdh"), "L1"),
    ("S_ROUND", "ROUND", "Round-number (100) magnet at 09:30", s_round, "L1"),
    ("S_PWFADE", "PW", "Prior-week high/low sweep fade", s_pwfade, "L1"),
    ("S_PWBRK", "PW", "Prior-week high/low break (2 closes)", s_pwbrk, "L1"),
]


def run_standalone(B, C):
    out = {k: [] for k, *_ in STAND}
    daily = []
    prev = None
    for sd, a, b in B["sess"]:
        x = C[sd]
        pctx = {"prev": prev, "daily": daily}
        for k, _, _, fn, eng in STAND:
            if eng == "P_turtle":
                tr = P.first_fill(B, a, b, P.s_turtle(B, a, b, pctx))
            elif eng == "P_unicorn":
                tr = P.first_fill(B, a, b, P.s_unicorn(B, a, b, pctx))
            else:
                tr = first_fill(B, a, b, fn(B, a, b, x))
            if tr:
                out[k].append(tr)
        H, L = float(B["h"][a:b].max()), float(B["l"][a:b].min())
        prev = (H, L)
        daily.append((H, L))
    return out


# ================================================================================================ confluence features
FEATS = ["F_OB", "F_BRK", "F_FVG", "F_IFVG", "F_WEEK", "F_WPO3", "F_DOR", "F_VA", "F_POC", "F_VWAP", "F_DIV", "F_ROUND",
         "F_PW", "F_WYK", "F_ORB", "F_TURTLE"]
FCON = {"F_OB": "OB", "F_BRK": "BRK", "F_FVG": "FVG", "F_IFVG": "FVG", "F_WEEK": "WEEK", "F_WPO3": "WEEK", "F_DOR": "DOR",
        "F_VA": "MP", "F_POC": "MP", "F_VWAP": "VWAP", "F_DIV": "DIV", "F_ROUND": "ROUND", "F_PW": "PW", "F_WYK": "WYK",
        "F_ORB": "ORB", "F_TURTLE": "TURTLE"}


def features2(B, C, i, side, price, ext):
    sd = B["sd"][i]
    x = C[sd]
    a = x["a"]
    h, l, c, o = B["h"], B["l"], B["c"], B["o"]
    f = {}
    lo = max(0, i - 36)
    # OB zones (ready before i)
    ob = False
    for k1, s, ol, oh in ob_events(B, max(a, lo), i, 0, 1440):
        if k1 < i and s == side and ol <= price <= oh:
            ob = True
    f["F_OB"] = ob
    brk = False
    for m, s, zl, zh, stp in breaker_events(B, max(a, lo), i, 0, 1440, True):
        if m < i and s == side and zl <= price <= zh:
            brk = True
    f["F_BRK"] = brk
    fv = iv = False
    for j, s, gl, gh in fvg_list(B, max(0, i - 24), i - 1):
        filled = (l[j + 1:i].min() <= gl) if s > 0 and j + 1 < i else (h[j + 1:i].max() >= gh if s < 0 and j + 1 < i else False)
        if s == side and not filled and gl <= price <= gh:
            fv = True
    for j, s, gl, gh in fvg_list(B, lo, i - 1):
        if s == -side:
            seg = c[j + 1:i]
            inv = bool(len(seg)) and ((side > 0 and seg.max() > gh) or (side < 0 and seg.min() < gl))
            if inv and gl <= price <= gh:
                iv = True
    f["F_FVG"], f["F_IFVG"] = fv, iv
    f["F_WEEK"] = x["wbias"] is not None and side == x["wbias"]
    f["F_WPO3"] = (side > 0 and price < x["wopen"]) or (side < 0 and price > x["wopen"])
    td = x["tdo"] if x["j0"] is not None and i >= x["j0"] else None
    f["F_DOR"] = bool(td is not None and x["dol"] == side and ((side > 0 and price <= td + 10) or (side < 0 and price >= td - 10)))
    va = x["va"]
    f["F_VA"] = bool(va and ((side > 0 and price < va[0]) or (side < 0 and price > va[1])))
    f["F_POC"] = bool(va and ((side > 0 and price < va[2]) or (side < 0 and price > va[2])))
    vw, sdv = B["vwap"][i], B["vsd"][i]
    f["F_VWAP"] = None if np.isnan(vw) else bool((side > 0 and price < vw - sdv) or (side < 0 and price > vw + sdv))
    dv = False
    if i > 40:
        r = B["rsi"]
        if side > 0:
            k = int(np.argmin(l[i - 12:i])) + i - 12
            p = int(np.argmin(l[i - 36:i - 12])) + i - 36
            dv = l[k] < l[p] and r[k] > r[p]
        else:
            k = int(np.argmax(h[i - 12:i])) + i - 12
            p = int(np.argmax(h[i - 36:i - 12])) + i - 36
            dv = h[k] > h[p] and r[k] < r[p]
    f["F_DIV"] = bool(dv)
    nxt = (math.floor(price / 100) + 1) * 100 if side > 0 else (math.ceil(price / 100) - 1) * 100
    f["F_ROUND"] = abs(nxt - price) <= 40
    f["F_PW"] = bool(x["pwh"] is not None and ((side > 0 and ext < x["pwl"]) or (side < 0 and ext > x["pwh"])))
    k = (int(np.argmin(l[i - 12:i])) + i - 12) if side > 0 else (int(np.argmax(h[i - 12:i])) + i - 12)
    f["F_WYK"] = bool(B["v"][k] <= B["vavg"][k])
    j9 = x["j930"]
    if j9 is not None and i >= j9 + 6:
        OH, OL = float(h[j9:j9 + 6].max()), float(l[j9:j9 + 6].min())
        f["F_ORB"] = bool((side > 0 and price > OH) or (side < 0 and price < OL))
    else:
        f["F_ORB"] = None
    d20 = x["d20"]
    f["F_TURTLE"] = bool(d20 and ((side > 0 and ext < d20[1]) or (side < 0 and ext > d20[0])))
    return f


# ================================================================================================ scoring (round 1's views)
def placebo_half(base_u, base_m, out_mask, mi, mode):
    """HALF: a random set of the same size as the 'without' set gets x0.5; ONLY: a random set of that size is dropped."""
    n = len(base_u)
    k = int(out_mask.sum())
    mpos = {m: j for j, m in enumerate(mi)}
    col = np.array([mpos.get(m, -1) for m in base_m])
    ok = col >= 0
    M = np.zeros((NDRAW, len(mi)))
    for d in range(NDRAW):
        sel = np.zeros(n, bool)
        sel[RNG.choice(n, k, replace=False)] = True
        ch = np.where(sel, (-0.5 if mode == "HALF" else -1.0) * base_u, 0.0)
        M[d] = np.bincount(col[ok], weights=ch[ok], minlength=len(mi))
    return M


def pstand(trs, mi):
    if not trs:
        return np.zeros((NDRAW, len(mi)))
    return L1.placebo_matrix_stand(trs, mi)


def main():
    B = L1.load()
    indicators(B)
    C = L1.build_ctx(B)
    build_ctx2(B, C)
    S_all = [s for s, _, _ in B["sess"]]
    print("sessions", len(S_all), flush=True)
    stand = run_standalone(B, C)
    print("standalone", {k: len(v) for k, v in stand.items()}, flush=True)
    LT, AT = L1.lit_trades(B), L1.atlas_trades(B)
    for t in LT + AT:
        t["f"] = features2(B, C, t["i"], t["side"], t["price"], t["ext"])
    for k, v in stand.items():
        for t in v:
            t["usd"], t["q"] = L1.stand_usd(t)
            t["f1"] = L1.features(B, C, t["i_in"], t["side"], t["entry"], t["entry"])
    print("features done", flush=True)
    SPANS = {"LIT": [s for s in S_all if "2021-11-08" <= s <= L1.LIT_END], "ATLAS": [s for s in S_all if "2021-11-01" <= s <= L1.ATLAS_END],
             "STAND": [s for s in S_all if s >= "2021-11-01"]}
    EV = {"LIT": (3000.0, 2000.0), "ATLAS": (1500.0, 1000.0), "STAND": (3000.0, 2000.0)}
    res = {}

    def add(name, concept, kind, desc, rows, base_rows, S, Mp, group):
        mi = L1.months_between(S[0][:7], S[-1][:7])
        r = L1.score_variant(rows, base_rows, S, mi, kind, EV[kind])
        vec = r["_months"]
        real_total = float(vec.sum())
        if Mp is not None and kind != "STAND":
            mean = Mp.mean(0)
            cols = [[k for k, m in enumerate(mi) if m.startswith(str(y))] for y in FULL]
            r["years_better"] = int(L1.card_metrics(np.array([vec]), mi, mean)[0][0])
            r["years_vs_random"] = {y: round(float(sum(vec[k] - mean[k] for k in c))) for y, c in zip(FULL, cols)}
        if Mp is not None:
            b_, wf_, _ = L1.card_metrics(Mp, mi, Mp.mean(0) if kind != "STAND" else None)
            tot = Mp.sum(1)
            r["p"] = round(float((tot >= real_total).mean()), 3)
            pd_ = np.array([(tot >= z).mean() for z in tot])
            h1c = [j for j, m in enumerate(mi) if "2026-01" <= m <= "2026-06"]
            h2c = [j for j, m in enumerate(mi) if m >= "2026-07"]
            oc = [j for j, m in enumerate(mi) if m < "2026-01"]
            hr = (Mp[:, h1c].sum(1) > 0) & (Mp[:, h2c].sum(1) > 0)
            if kind != "LIT":
                hr &= Mp[:, oc].sum(1) > 0
            r["placebo_card_rate"] = round(float(((b_ >= 4) & (wf_ > 0) & (pd_ < 0.05) & hr).mean()), 4)
        else:
            r["p"], r["placebo_card_rate"] = None, None
        r.update({"name": name, "concept": concept, "kind": kind, "desc": desc, "group": group})
        r["verdict"] = L1.verdict(r)
        bk = res.get(f"{kind}_BASE") if kind != "STAND" else None
        r["d_h1_2026"] = r["h1_2026"]["net"] - (bk["h1_2026"]["net"] if bk else 0)
        r["d_h2_2026"] = r["h2_2026"]["net"] - (bk["h2_2026"]["net"] if bk else 0)
        r["d_2021_25"] = sum(r["years_delta"][y] for y in (2021, 2022, 2023, 2024, 2025))
        r["house_rule"] = bool(r["d_h1_2026"] > 0 and r["d_h2_2026"] > 0 and (kind == "LIT" or r["d_2021_25"] > 0))
        tpw_ok = (2 <= r["tpw"] <= 4) if kind == "STAND" else True
        r["card"] = bool(r["years_better"] >= 4 and r["wf"] > 0 and r["p"] is not None and r["p"] < 0.05 and tpw_ok and r["house_rule"])
        r["months"] = {m: round(float(v)) for m, v in zip(mi, r.pop("_months"))}
        res[name] = r
        if group != "pair":
            print(f"{name:26s} {r['verdict']:30s} yrs+{r['years_better']} wf {r['wf']:>7} p {r['p']} tot {round(real_total):>8}", flush=True)

    for kind, BT, S in (("LIT", LT, SPANS["LIT"]), ("ATLAS", AT, SPANS["ATLAS"])):
        L1.WF = L1.wf_blocks(last=S[-1][:7])
        Sset = set(S)
        BT = [t for t in BT if t["sd"] in Sset]
        base_rows = [(t["sd"], t["usd"]) for t in BT]
        mi = L1.months_between(S[0][:7], S[-1][:7])
        add(f"{kind}_BASE", "BASE", kind, f"{kind} as it is", base_rows, [], S, None, "base")
        bu = np.array([t["usd"] for t in BT])
        bm = [L1.month_key(t["sd"]) for t in BT]
        sets = [(f, [f], FCON[f], "single") for f in FEATS] + \
               [(f"{a}+{b}", [a, b], "PAIR", "pair") for a, b in itertools.combinations(FEATS, 2)]
        for fid, keys, concept, group in sets:
            mask = np.array([L1.has(t["f"], keys) for t in BT])
            modes = ("HALF", "ONLY") if group == "single" else ("HALF",)
            for mode in modes:
                mult = 0.5 if mode == "HALF" else 0.0
                rows = ([(t["sd"], t["usd"] * (1.0 if m else mult)) for t, m in zip(BT, mask)] if mode == "HALF"
                        else [(t["sd"], t["usd"]) for t, m in zip(BT, mask) if m])
                Mp = placebo_half(bu, bm, ~mask, mi, mode)
                add(f"{kind}_{fid}_{mode}", concept, kind, f"{kind} {mode} {'+'.join(keys)} (has it {int(mask.sum())}/{len(mask)})",
                    rows, base_rows, S, Mp, group)
        print(kind, "filters done", flush=True)
    S = SPANS["STAND"]
    L1.WF = L1.wf_blocks(last=S[-1][:7])
    mi = L1.months_between(S[0][:7], S[-1][:7])
    for k, concept, desc, _, _ in STAND:
        trs = [t for t in stand[k] if t["q"]]
        add(k, concept, "STAND", desc, [(t["date"], t["usd"]) for t in trs], [], S, pstand(trs, mi), "stand")
        for gk in ("F_TDO", "F_DOL"):
            g = [t for t in trs if t["f1"][gk]]
            add(f"{k}|{gk}", "GATE", "STAND", f"{k} only if {gk}", [(t["date"], t["usd"]) for t in g], [], S,
                pstand(g, mi), "gate")
        # weekly-bias gate (round-2 feature)
        g = [t for t in trs if C[t["date"]]["wbias"] == t["side"]]
        add(f"{k}|F_WEEK", "GATE", "STAND", f"{k} only with the weekly bias", [(t["date"], t["usd"]) for t in g], [], S,
            pstand(g, mi), "gate")
    tested = [r for r in res.values() if r["placebo_card_rate"] is not None]
    luck = {"variants": len(tested), "cards_real": sum(r["card"] for r in tested),
            "cards_expected_by_luck": round(sum(r["placebo_card_rate"] for r in tested), 1),
            "p05_real": sum(1 for r in tested if r["p"] < 0.05), "p05_expected": round(0.05 * len(tested), 1),
            "by_group": {g: {"n": sum(1 for r in tested if r["group"] == g), "cards": sum(r["card"] for r in tested if r["group"] == g),
                             "luck": round(sum(r["placebo_card_rate"] for r in tested if r["group"] == g), 1)}
                         for g in ("single", "pair", "stand", "gate")}}
    print(json.dumps(luck), flush=True)
    for r in sorted([r for r in res.values() if r["card"]], key=lambda r: -r["wf"]):
        print("CARD", r["name"], r["years_delta"], "wf", r["wf"], "p", r["p"], "h1", r["d_h1_2026"], "h2", r["d_h2_2026"], r["eval_all"], r["eval_2026"])
    json.dump({"meta": {"design": "research/ictlab/DESIGN2.md", "draws": NDRAW}, "luck": luck, "variants": res},
              open(os.path.join(HERE, "results2.json"), "w"), default=float)
    tr = {"LIT": [{"sd": t["sd"], "t": int(t["t"]), "side": t["side"], "usd": round(t["usd"], 2), "f": t["f"]} for t in LT],
          "ATLAS": [{"sd": t["sd"], "t": int(t["t"]), "side": t["side"], "usd": round(t["usd"], 2), "src": t["src"], "f": t["f"]} for t in AT],
          "STAND": {k: [{"sd": t["date"], "t": t["t_in"], "side": t["side"], "usd": round(t["usd"], 2), "exit": t["exit"]}
                        for t in v if t["q"]] for k, v in stand.items()}}
    json.dump(tr, open(os.path.join(HERE, "trades2.json"), "w"),
              default=lambda z: bool(z) if isinstance(z, np.bool_) else (None if z is None else float(z)))


if __name__ == "__main__":
    main()
