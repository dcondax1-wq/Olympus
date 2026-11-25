"""ICT lab 2026-11-25: popular ICT / time-price concepts as taught, every test view side by side.
Rules: research/ictlab/DESIGN.md (pre-registered, committed before this file ran). Paper research only, futures data only.

    python -X utf8 research/ictlab/ict_lab.py      -> research/ictlab/results.json (+ printed tables)
"""
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import popular_ict as P  # noqa: E402

T, TICK, FEE, PTV = P.T, P.TICK, P.FEE, P.PTV
RNG = np.random.default_rng(20261125)
NDRAW = 500
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
FULL_YEARS = [2022, 2023, 2024, 2025, 2026]
LIT_END, ATLAS_END = "2026-10-16", "2026-10-13"

MACROS = [((2, 33), (3, 0)), ((4, 3), (4, 30)), ((8, 50), (9, 10)), ((9, 50), (10, 10)), ((10, 50), (11, 10)),
          ((11, 50), (12, 10)), ((13, 10), (13, 40)), ((15, 15), (15, 45))]
MAC_RTH = [m for m in MACROS if m[0][0] in (8, 9, 10, 11, 13, 15)]
MAC_LDN = [m for m in MACROS if m[0][0] in (2, 4)]
SB_H = [3, 10, 14]
KZ = [((2, 0), (5, 0)), ((8, 30), (11, 0))]


def clk(hm):
    return hm[0] * 60 + hm[1]


def in_win(cm, wins):
    """cm = ET clock minutes."""
    return any(clk(s) <= cm < clk(e) for s, e in wins)


# ================================================================================================ data + session context
def load():
    B = P.load()
    n = len(B["t"])
    es = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
    em = dict(zip(es["time"].to_numpy(), zip(es["high"].to_numpy(float), es["low"].to_numpy(float))))
    B["esh"] = np.array([em.get(t, (np.nan, np.nan))[0] for t in B["t"]])
    B["esl"] = np.array([em.get(t, (np.nan, np.nan))[1] for t in B["t"]])
    B["es_from"] = int(es["time"].iloc[0])
    B["n"] = n
    return B


def first_at(B, a, b, m):
    """first bar index of the session with session-minute >= m (None if none)."""
    j = a + int(np.searchsorted(B["sm"][a:b], m, "left"))
    return j if j < b else None


def build_ctx(B):
    """per-session levels known at (or before) each moment; keyed by session date."""
    h, l, c, o, sm = B["h"], B["l"], B["c"], B["o"], B["sm"]
    S = B["sess"]
    C = {}
    daily = []          # (H, L, C) of past sessions
    cbdr_hist, asia_hist = [], []
    week = None
    prev = None
    for k, (sd, a, b) in enumerate(S):
        x = {"a": a, "b": b, "gopen": o[a]}
        j0 = first_at(B, a, b, T(0, 0))
        x["tdo"] = o[j0] if j0 is not None and sm[j0] == T(0, 0) else None
        x["j0"] = j0
        for nm, hm in (("tso_asia", (19, 30)), ("tso_ldn", (1, 30)), ("tso_ny", (7, 30)), ("tso_pm", (13, 30))):
            j = first_at(B, a, b, T(*hm))
            x[nm] = o[j] if j is not None and sm[j] == T(*hm) else None
        # IPDA ranges from the prior N sessions
        for N in (20, 40, 60):
            if len(daily) >= N:
                H = max(d[0] for d in daily[-N:])
                L = min(d[1] for d in daily[-N:])
                x[f"ipda{N}"] = (H + L) / 2
            else:
                x[f"ipda{N}"] = None
        # previous day / draw on liquidity
        if prev:
            PH, PL, PC = prev
            x["pdh"], x["pdl"] = PH, PL
            x["dol"] = 1 if PC > (PH + PL) / 2 else -1
        else:
            x["pdh"] = x["pdl"] = x["dol"] = None
        # NDOG / NWOG
        if k > 0:
            pa, pb = S[k - 1][1], S[k - 1][2]
            pc = c[pb - 1]
            g = o[a] - pc
            x["ndog_ce"] = (o[a] + pc) / 2 if abs(g) >= 4 else None
            import datetime as _dt
            wk = _dt.date.fromisoformat(str(sd)).isocalendar()[:2]
            monday = week is None or week['wk'] != wk
            if monday:
                week = {"sd": sd, "wk": wk, "ce": (o[a] + pc) / 2 if abs(g) >= 4 else None, "touched": False}
        else:
            x["ndog_ce"] = None
        x["nwog_ce"] = week["ce"] if week else None
        # was the NWOG CE touched before 09:30 today (incl. earlier days of the week)?
        j930 = first_at(B, a, b, T(9, 30))
        x["j930"] = j930 if j930 is not None and sm[j930] == T(9, 30) else None
        if week and week["ce"] is not None:
            jj = x["j930"] if x["j930"] is not None else b
            x["nwog_touched_930"] = week["touched"] or bool(np.any((l[a:jj] <= week["ce"]) & (h[a:jj] >= week["ce"])))
            if np.any((l[a:b] <= week["ce"]) & (h[a:b] >= week["ce"])):
                week["touched"] = True
        else:
            x["nwog_touched_930"] = True
        # CBDR 14:00-20:00 (prev session 14:00-17:00 + this 18:00-20:00) and Asia 20:00-00:00
        hi_, lo_ = [], []
        if k > 0:
            pa, pb = S[k - 1][1], S[k - 1][2]
            q = [i for i in range(pa, pb) if sm[i] >= T(14, 0)]
            hi_ += [h[i] for i in q]
            lo_ += [l[i] for i in q]
        q = [i for i in range(a, b) if sm[i] < T(20, 0)]
        hi_ += [h[i] for i in q]
        lo_ += [l[i] for i in q]
        x["cbdr"] = (max(hi_), min(lo_)) if hi_ else None
        q = [i for i in range(a, b) if T(20, 0) <= sm[i] < T(0, 0)]
        x["asia"] = (max(h[i] for i in q), min(l[i] for i in q)) if q else None
        for nm, hist in (("cbdr", cbdr_hist), ("asia", asia_hist)):
            r = x[nm]
            x[nm + "_small"] = bool(r and len(hist) >= 20 and (r[0] - r[1]) <= np.median(hist[-60:]))
            if r:
                hist.append(r[0] - r[1])
        C[sd] = x
        H, L = float(h[a:b].max()), float(l[a:b].min())
        prev = (H, L, float(c[b - 1]))
        daily.append(prev)
    return C


# ================================================================================================ execution (P.execute + own target)
def execute(B, a, b, o):
    h, l, c, op, sm = B["h"], B["l"], B["c"], B["o"], B["sm"]
    side, stp = o["side"], o["stop"]
    flat = T(15, 50)
    fill = None
    for i in range(o["i0"], min(o["i1"], b - 1) + 1):
        if sm[i] > flat:
            return None
        if o["kind"] == "market":
            fill, ent = i, op[i] + side * TICK
            break
        if (side > 0 and l[i] <= o["px"]) or (side < 0 and h[i] >= o["px"]):
            fill, ent = i, o["px"]
            if side > 0 and op[i] < o["px"]:
                ent = op[i]
            if side < 0 and op[i] > o["px"]:
                ent = op[i]
            break
    if fill is None:
        return None
    risk = side * (ent - stp)
    if risk < 1.0 or risk > o.get("max_stop", 1e9):
        return None
    tgt = o.get("tgt")
    if tgt is None:
        tgt = ent + side * 2.0 * risk
    elif side * (tgt - ent) < o.get("min_rr", 0.0) * risk:
        return None
    for i in range(fill, b):
        if side > 0 and l[i] <= stp:
            x, why = (min(stp, op[i]) - TICK if i > fill else stp - TICK), "STOP"
            break
        if side < 0 and h[i] >= stp:
            x, why = (max(stp, op[i]) + TICK if i > fill else stp + TICK), "STOP"
            break
        if i > fill and ((side > 0 and h[i] >= tgt) or (side < 0 and l[i] <= tgt)):
            x, why = tgt, "TARGET"
            break
        if sm[i] >= flat:
            x, why = c[i] - side * TICK, "EOD"
            break
    else:
        x, why = c[b - 1] - side * TICK, "EOD"
    return {"date": B["sd"][a], "side": side, "i_in": int(fill), "t_in": int(B["t"][fill]), "entry": float(ent),
            "stop": float(stp), "stop_pts": float(risk), "pts": float(side * (x - ent)), "exit": why}


def first_fill(B, a, b, orders):
    best = None
    for o in orders:
        tr = execute(B, a, b, o)
        if tr and (best is None or tr["i_in"] < best["i_in"]):
            best = tr
    return best


# ================================================================================================ standalone rules
def amdx(B, a, b, open_m, manip_end, dist_end, lvl=None):
    """generic Quarterly-Theory AMDX: level = open of bar open_m (or lvl); manipulation open_m..manip_end; first close back
    through the level in manip_end..dist_end, the side the manipulation did NOT go -> enter next bar."""
    h, l, c, o, sm = B["h"], B["l"], B["c"], B["o"], B["sm"]
    j = first_at(B, a, b, open_m)
    if j is None or sm[j] != open_m:
        return []
    L0 = o[j] if lvl is None else lvl
    if L0 is None:
        return []
    went_dn = went_up = False
    for i in range(j, b):
        if sm[i] >= manip_end:
            break
        went_dn |= l[i] < L0
        went_up |= h[i] > L0
    for i in range(j + 1, b):
        if sm[i] < manip_end:
            continue
        if sm[i] >= dist_end:
            break
        if went_dn and c[i - 1] <= L0 < c[i]:
            return [{"kind": "market", "side": 1, "stop": float(l[j:i + 1].min()) - TICK, "i0": i + 1, "i1": i + 1}]
        if went_up and c[i - 1] >= L0 > c[i]:
            return [{"kind": "market", "side": -1, "stop": float(h[j:i + 1].max()) + TICK, "i0": i + 1, "i1": i + 1}]
    return []


def s_qt_tdo(B, a, b, x):
    return amdx(B, a, b, T(0, 0), T(6, 0), T(12, 0))


def s_qt_tso(B, a, b, x):
    return amdx(B, a, b, T(7, 30), T(9, 0), T(10, 30))


def s_qt_225(B, a, b, x):
    return amdx(B, a, b, T(9, 20), T(9, 45), T(10, 10))


def fvg_win(B, a, b, wins, live_after=30):
    out = []
    for s, e in wins:
        m0 = -(-(clk(s) - 5) // 5) * 5          # 3rd candle closes inside the window (close >= start, <= end)
        m1 = clk(e) - 5 + 1
        ex = clk(e) + live_after
        f = P.fvg_first(B, a, b, T(m0 // 60, m0 % 60), T(m1 // 60, m1 % 60), T((ex // 60) % 24, ex % 60))
        out += f
    return out


def s_mac_all(B, a, b, x):
    return fvg_win(B, a, b, MACROS)


def s_mac_rth(B, a, b, x):
    return fvg_win(B, a, b, MAC_RTH)


def s_mac_ldn(B, a, b, x):
    return fvg_win(B, a, b, MAC_LDN)


def sb(B, a, b, H):
    return P.fvg_first(B, a, b, T(H - 1, 55), T(H, 55) + 1, T(H + 1, 0))


def s_sb03(B, a, b, x):
    return sb(B, a, b, 3)


def s_sb10(B, a, b, x):
    return sb(B, a, b, 10)


def s_sb14(B, a, b, x):
    return sb(B, a, b, 14)


def s_sball(B, a, b, x):
    return sb(B, a, b, 3) + sb(B, a, b, 10) + sb(B, a, b, 14)


def s_judas(B, a, b, x):
    return P.s_judas(B, a, b, {})


def s_po3(B, a, b, x):
    return P.s_po3(B, a, b, {"prev": None, "daily": []})


def overnight(B, a, b, x):
    """00:00-09:25 high / low."""
    j0, j9 = x["j0"], x["j930"]
    if j0 is None or j9 is None or j9 <= j0:
        return None
    return float(B["h"][j0:j9].max()), float(B["l"][j0:j9].min())


def bias_trade(B, a, b, x, side, tgt=None, min_rr=0.0):
    on = overnight(B, a, b, x)
    if on is None or not side:
        return []
    stp = on[1] - TICK if side > 0 else on[0] + TICK
    o = {"kind": "market", "side": side, "stop": stp, "i0": x["j930"], "i1": x["j930"], "max_stop": 80.0}
    if tgt is not None:
        o["tgt"], o["min_rr"] = tgt, min_rr
    return [o]


def s_ipda(N):
    def f(B, a, b, x):
        m = x[f"ipda{N}"]
        if m is None or x["j930"] is None:
            return []
        return bias_trade(B, a, b, x, 1 if B["o"][x["j930"]] < m else -1)
    return f


def s_dol(B, a, b, x):
    if x["dol"] is None or x["j930"] is None:
        return []
    on = overnight(B, a, b, x)
    if on is None:
        return []
    hh, ll = float(B["h"][a:x["j930"]].max()), float(B["l"][a:x["j930"]].min())
    if x["dol"] > 0 and hh < x["pdh"]:
        return bias_trade(B, a, b, x, 1, x["pdh"], 1.0)
    if x["dol"] < 0 and ll > x["pdl"]:
        return bias_trade(B, a, b, x, -1, x["pdl"], 1.0)
    return []


def s_gap(kind):
    def f(B, a, b, x):
        ce = x[kind + "_ce"]
        if ce is None or x["j930"] is None:
            return []
        if kind == "nwog":
            if x["nwog_touched_930"]:
                return []
        else:
            j = x["j930"]
            if np.any((B["l"][a:j] <= ce) & (B["h"][a:j] >= ce)):
                return []
        side = -1 if B["o"][x["j930"]] > ce else 1
        return bias_trade(B, a, b, x, side, ce, 1.0)
    return f


def s_ote(B, a, b, x):
    j9 = x["j930"]
    if j9 is None or j9 + 6 >= b:
        return []
    hi, lo = float(B["h"][j9:j9 + 6].max()), float(B["l"][j9:j9 + 6].min())
    rg = hi - lo
    if rg <= 0:
        return []
    cl = B["c"][j9 + 5]
    j12 = first_at(B, a, b, T(12, 0)) or b
    if cl >= lo + 2 * rg / 3:
        return [{"kind": "limit", "side": 1, "px": hi - 0.705 * rg, "stop": lo - TICK, "i0": j9 + 6, "i1": j12 - 1,
                 "tgt": hi + 0.27 * rg}]
    if cl <= hi - 2 * rg / 3:
        return [{"kind": "limit", "side": -1, "px": lo + 0.705 * rg, "stop": hi + TICK, "i0": j9 + 6, "i1": j12 - 1,
                 "tgt": lo - 0.27 * rg}]
    return []


def s_kz(B, a, b, x):
    r = P.rng(B, a, b, T(2, 0), T(5, 0))
    if r is None:
        return []
    return P.sweep_back(B, a, b, r[0], r[1], T(8, 30), T(11, 0))


def s_sd(kind):
    def f(B, a, b, x):
        r = x[kind]
        if not r or not x[kind + "_small"]:
            return []
        H, L = r
        R = H - L
        if R <= 0:
            return []
        j2 = first_at(B, a, b, T(2, 0))
        j11 = first_at(B, a, b, T(11, 0)) or b
        if j2 is None:
            return []
        return [{"kind": "limit", "side": -1, "px": H + 2 * R, "stop": H + 4 * R + TICK, "i0": j2, "i1": j11 - 1, "tgt": H},
                {"kind": "limit", "side": 1, "px": L - 2 * R, "stop": L - 4 * R - TICK, "i0": j2, "i1": j11 - 1, "tgt": L}]
    return f


def s_smt(B, a, b, x):
    h, l, c, sm, eh, el = B["h"], B["l"], B["c"], B["sm"], B["esh"], B["esl"]
    j0, j9 = x["j0"], x["j930"]
    if j0 is None or j9 is None or B["t"][a] < B["es_from"]:
        return []
    if np.isnan(eh[j0:j9]).all():
        return []
    NH, NL = float(h[j0:j9].max()), float(l[j0:j9].min())
    EH, EL = float(np.nanmax(eh[j0:j9])), float(np.nanmin(el[j0:j9]))
    j12 = first_at(B, a, b, T(12, 0)) or b
    for i in range(j9, j12):
        if np.isnan(eh[i]):
            continue
        bear = h[i] > NH and eh[i] < EH
        bull = l[i] < NL and el[i] > EL
        if not (bear or bull):
            if h[i] > NH or l[i] < NL:
                return []          # NQ took it and ES did too: no SMT, day done
            continue
        for m in range(i, min(j12, i + 12)):
            if bear and c[m] < NH:
                return [{"kind": "market", "side": -1, "stop": float(h[i:m + 1].max()) + TICK, "i0": m + 1, "i1": m + 1}]
            if bull and c[m] > NL:
                return [{"kind": "market", "side": 1, "stop": float(l[i:m + 1].min()) - TICK, "i0": m + 1, "i1": m + 1}]
        return []
    return []


STAND = [
    ("S_QT_TDO", "QT", "Quarterly Theory: daily AMDX vs True Day Open 00:00", s_qt_tdo),
    ("S_QT_TSO", "QT", "Quarterly Theory: NY 90-min AMDX vs True Session Open 07:30", s_qt_tso),
    ("S_QT_225", "QT", "Quarterly Theory: 22.5-min AMDX 09:20-10:10", s_qt_225),
    ("S_MAC_ALL", "MAC", "Macros: first FVG in any of the 8 macros", s_mac_all),
    ("S_MAC_RTH", "MAC", "Macros: first FVG in an NY macro", s_mac_rth),
    ("S_MAC_LDN", "MAC", "Macros: first FVG in a London macro", s_mac_ldn),
    ("S_SB_03", "SB", "Silver Bullet 03-04", s_sb03),
    ("S_SB_10", "SB", "Silver Bullet 10-11", s_sb10),
    ("S_SB_14", "SB", "Silver Bullet 14-15", s_sb14),
    ("S_SB_ALL", "SB", "Silver Bullet: first of the 3 hours", s_sball),
    ("S_JUD", "JUD", "Judas swing (London)", s_judas),
    ("S_PO3", "PO3", "Power of 3 / AMD", s_po3),
    ("S_SMT", "SMT", "SMT NQ vs ES at the overnight high/low (2025-04+)", s_smt),
    ("S_IPDA20", "IPDA", "IPDA 20-day premium/discount bias, 09:30", s_ipda(20)),
    ("S_IPDA40", "IPDA", "IPDA 40-day bias, 09:30", s_ipda(40)),
    ("S_IPDA60", "IPDA", "IPDA 60-day bias, 09:30", s_ipda(60)),
    ("S_DOL", "DOL", "PDH/PDL draw on liquidity, target the draw", s_dol),
    ("S_NWOG", "GAP", "NWOG: trade to the gap's 50%", s_gap("nwog")),
    ("S_NDOG", "GAP", "NDOG: trade to the gap's 50%", s_gap("ndog")),
    ("S_OTE", "OTE", "OTE 70.5% of the 09:30-10:00 leg, target -27%", s_ote),
    ("S_KZ", "KZ", "NY killzone sweep of the London killzone range", s_kz),
    ("S_CBDR", "CBDR", "CBDR 2 SD fade, target the range edge", s_sd("cbdr")),
    ("S_ASIA", "CBDR", "Asia range 2 SD fade, target the range edge", s_sd("asia")),
]


def run_standalone(B, C):
    out = {k: [] for k, *_ in STAND}
    for sd, a, b in B["sess"]:
        x = C[sd]
        for k, _, _, fn in STAND:
            tr = first_fill(B, a, b, fn(B, a, b, x))
            if tr:
                out[k].append(tr)
    return out


# ================================================================================================ features at a trade's entry
def features(B, C, i, side, price, ext):
    sd = B["sd"][i]
    x = C[sd]
    a = x["a"]
    cm = (int(B["sm"][i]) + 1080) % 1440
    f = {}
    f["F_MAC"] = in_win(cm, MACROS)
    f["F_SB"] = any(H * 60 <= cm < H * 60 + 60 for H in SB_H)
    f["F_KZ"] = in_win(cm, KZ)
    pos = int(B["sm"][i]) % 360
    f["F_QT90"] = (pos // 90) in (1, 2)
    p90 = pos % 90
    f["F_QT225"] = 22.5 <= p90 < 67.5

    def al(lvl):
        return lvl is not None and ((side > 0 and price < lvl) or (side < 0 and price > lvl))
    f["F_TDO"] = al(x["tdo"]) if x["j0"] is not None and i >= x["j0"] else False
    sm = int(B["sm"][i])
    tso = None
    for nm, hm in (("tso_asia", (19, 30)), ("tso_ldn", (1, 30)), ("tso_ny", (7, 30)), ("tso_pm", (13, 30))):
        if sm >= T(*hm) and x[nm] is not None:
            tso = x[nm]
    f["F_TSO"] = al(tso)
    f["F_PO3"] = al(x["gopen"])
    for N in (20, 40, 60):
        f[f"F_IPDA{N}"] = al(x[f"ipda{N}"])
    f["F_DOL"] = x["dol"] is not None and side == x["dol"]
    f["F_NWOG"] = al(x["nwog_ce"])
    s0 = x["j0"] if x["j0"] is not None and i > x["j0"] else a
    if i > s0:
        hi, lo = float(B["h"][s0:i].max()), float(B["l"][s0:i].min())
        rg = hi - lo
        d = ((hi - price) / rg if side > 0 else (price - lo) / rg) if rg > 0 else 0
        f["F_OTE"] = 0.62 <= d <= 0.79
    else:
        f["F_OTE"] = False
    band = False
    for nm in ("cbdr", "asia"):
        r = x[nm]
        if not r or (nm == "asia" and sm < T(0, 0)):
            continue
        H, L = r
        R = H - L
        if R > 0 and (H + 2 * R <= ext <= H + 4 * R or L - 4 * R <= ext <= L - 2 * R):
            band = True
    f["F_CBDR"] = band
    # SMT: NQ took the 00:00(or session)-to-30-min-ago extreme in the last 30 min, ES did not
    if B["t"][i] < B["es_from"] or i - 6 <= s0:
        f["F_SMT"] = None
    else:
        r0, r1 = s0, i - 6
        eh, el = B["esh"], B["esl"]
        if np.isnan(eh[r0:i]).all():
            f["F_SMT"] = None
        elif side > 0:
            nq = B["l"][r1:i].min() < B["l"][r0:r1].min()
            es = np.nanmin(el[r1:i]) < np.nanmin(el[r0:r1]) if not np.isnan(el[r1:i]).all() else True
            f["F_SMT"] = bool(nq and not es)
        else:
            nq = B["h"][r1:i].max() > B["h"][r0:r1].max()
            es = np.nanmax(eh[r1:i]) > np.nanmax(eh[r0:r1]) if not np.isnan(eh[r1:i]).all() else True
            f["F_SMT"] = bool(nq and not es)
    return f


FILTERS = ["F_MAC", "F_SB", "F_KZ", "F_QT90", "F_QT225", "F_TDO", "F_TSO", "F_PO3", "F_IPDA20", "F_IPDA40", "F_IPDA60",
           "F_DOL", "F_NWOG", "F_OTE", "F_CBDR", "F_SMT"]
FCONCEPT = {"F_MAC": "MAC", "F_SB": "SB", "F_KZ": "KZ", "F_QT90": "QT", "F_QT225": "QT", "F_TDO": "QT", "F_TSO": "QT",
            "F_PO3": "PO3", "F_IPDA20": "IPDA", "F_IPDA40": "IPDA", "F_IPDA60": "IPDA", "F_DOL": "DOL", "F_NWOG": "GAP",
            "F_OTE": "OTE", "F_CBDR": "CBDR", "F_SMT": "SMT"}
COMBOS = {"C1": ["F_MAC", "F_TDO"], "C2": ["F_SB", "F_IPDA20"], "C3": ["F_KZ", "F_DOL"], "C4": ["F_TDO", "F_IPDA20", "F_DOL"],
          "C5": ["F_QT90", "F_TSO"], "C6": ["F_MAC", "F_OTE"], "C7": ["F_CBDR", "F_KZ"], "C8": ["F_SMT", "F_KZ"],
          "C9": ["F_TDO", "F_NWOG"], "C10": ["F_SB", "F_TDO", "F_DOL"]}
GATES = {"G1": ("S_SB_10", ["F_TDO"]), "G2": ("S_MAC_RTH", ["F_IPDA20"]), "G3": ("S_OTE", ["F_DOL"]),
         "G4": ("S_KZ", ["F_TDO", "F_IPDA20"]), "G5": ("S_QT_TSO", ["F_DOL"]), "G6": ("S_CBDR", ["F_KZ"])}


def has(f, keys):
    """None (SMT before ES data) = no filter -> counts as True."""
    return all(f[k] is None or bool(f[k]) for k in keys)


# ================================================================================================ base strategies
def lit_trades(B):
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    out = []
    for t in d["trades"]:
        i = int(np.searchsorted(B["t"], t["entry_t"], "right")) - 1
        side = 1 if t["side"] == "LONG" else -1
        out.append({"i": i, "t": t["entry_t"], "sd": B["sd"][i], "side": side, "price": float(t["entry"]),
                    "ext": float(t.get("sweep_ext") or t["entry"]), "usd": float(t["pnl"])})
    return out


def atlas_trades(B):
    import atlas_health as AH
    out = []
    for t in AH.stream():
        i = int(np.searchsorted(B["t"], t["entry_t"], "right")) - 1
        loss1 = (t["risk"] + AH.SLIP) * AH.PV + AH.COMM
        q = int(250.0 // loss1)
        if q <= 0:
            continue
        px = float(B["o"][i])
        out.append({"i": i, "t": t["entry_t"], "sd": B["sd"][i], "side": int(t["dir"]), "price": px, "ext": px,
                    "usd": q * (t["pts"] * AH.PV - AH.COMM), "src": t["src"]})
    return out


def stand_usd(tr):
    q = P.qty(tr["stop_pts"])
    return q * (tr["pts"] * PTV - FEE), q


# ================================================================================================ the views
def month_key(sd):
    return sd[:7]


def months_between(a, z):
    out = []
    y, m = int(a[:4]), int(a[5:7])
    while f"{y:04d}-{m:02d}" <= z:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def quarter(sd):
    return f"{sd[:4]}Q{(int(sd[5:7]) - 1) // 3 + 1}"


def series_stats(D, Dlow, S):
    eq = pk = dd = 0.0
    for s in S:
        eq += D.get(s, 0.0)
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    net = sum(D.get(s, 0.0) for s in S)
    return {"net": round(net), "usd_mo": round(net / max(1e-9, len(S) / 21)), "maxdd": round(dd)}


def eval40(D, Dlow, S, starts, target, mll, n=40):
    res = []
    idx = {s: k for k, s in enumerate(S)}
    for s0 in starts:
        k0 = idx[s0]
        if k0 + n > len(S):
            continue
        bal = hi = 0.0
        out = None
        for j in range(k0, k0 + n):
            s = S[j]
            floor = min(hi - mll, 100.0)
            if bal + Dlow.get(s, 0.0) <= floor:
                out = ("F", j - k0 + 1)
                break
            bal += D.get(s, 0.0)
            if bal <= floor:
                out = ("F", j - k0 + 1)
                break
            if bal >= target:
                out = ("P", j - k0 + 1)
                break
            hi = max(hi, bal)
        res.append(out)
    m = len(res)
    if not m:
        return {"pass": None, "fail": None, "days": None, "n": 0}
    Pd = [x[1] for x in res if x and x[0] == "P"]
    F = [x for x in res if x and x[0] == "F"]
    return {"pass": round(100 * len(Pd) / m), "fail": round(100 * len(F) / m),
            "days": int(np.median(Pd)) if Pd else None, "n": m}


def wf_blocks(first="2022-05", last="2026-10"):
    """3-month OOS blocks with the 6 months before each as the look-back."""
    ms = months_between("2021-11", last)
    out = []
    k = ms.index(first)
    while k < len(ms):
        out.append((ms[k - 6:k], ms[k:k + 3]))
        k += 3
    return out


WF = None


def card_metrics(M, mi, mean=None):
    """M: draws x months matrix of the $ CHANGE vs the baseline (standalone: $). -> years better count, WF $ (per draw).
    mean (filters): the placebo mean per month; a year is better only if the change is > 0 AND beats random filters
    of the same size (change - placebo mean > 0)."""
    global WF
    cols = [[k for k, m in enumerate(mi) if m.startswith(str(y))] for y in FULL_YEARS]
    yrs = np.stack([M[:, c].sum(1) for c in cols], 1)
    if mean is not None:
        ym = np.array([mean[c].sum() for c in cols])
        better = ((yrs > 0) & (yrs - ym > 0)).sum(1)
    else:
        better = (yrs > 0).sum(1)
    wf = np.zeros(M.shape[0])
    pos = {m: k for k, m in enumerate(mi)}
    for lb, oos in WF:
        lbk = [pos[m] for m in lb if m in pos]
        ok = [pos[m] for m in oos if m in pos]
        if not ok:
            continue
        on = M[:, lbk].sum(1) > 0
        wf += np.where(on, M[:, ok].sum(1), 0.0)
    return better, wf, yrs


def score_variant(rows, base_rows, S, mi, kind, ev):
    """rows / base_rows: lists of (sd, $) per trade (variant / baseline; standalone baseline = empty).
    -> dict of every view."""
    D, Dl = defaultdict(float), defaultdict(float)
    run = defaultdict(float)
    for sd, u in rows:
        D[sd] += u
        run[sd] += u
        Dl[sd] = min(Dl[sd], run[sd])
    Db = defaultdict(float)
    for sd, u in base_rows:
        Db[sd] += u
    Sset = set(S)
    dm = defaultdict(float)
    for s in S:
        dm[month_key(s)] += D.get(s, 0.0) - Db.get(s, 0.0)
    vec = np.array([[dm[m] for m in mi]])
    better, wf, yrs = card_metrics(vec, mi)
    yd = {y: round(sum(D.get(s, 0) - Db.get(s, 0) for s in S if s.startswith(str(y)))) for y in YEARS}
    qd = defaultdict(float)
    for s in S:
        qd[quarter(s)] += D.get(s, 0.0) - Db.get(s, 0.0)
    S26 = [s for s in S if s >= "2026-01-01"]
    S26a = [s for s in S26 if s <= "2026-06-30"]
    S26b = [s for s in S26 if s >= "2026-07-01"]
    n = len([1 for sd, _ in rows if sd in Sset])
    n26 = len([1 for sd, _ in rows if sd >= "2026-01-01" and sd in Sset])
    wins = [u for sd, u in rows if sd in Sset and u > 0]
    losses = [u for sd, u in rows if sd in Sset and u <= 0]
    return {"years_delta": yd, "quarters_delta": {k: round(v) for k, v in sorted(qd.items())},
            "years_better": int(better[0]), "wf": round(float(wf[0])),
            "all": series_stats(D, Dl, S), "y2026": series_stats(D, Dl, S26),
            "h1_2026": series_stats(D, Dl, S26a), "h2_2026": series_stats(D, Dl, S26b),
            "tpw": round(n / (len(S) / 5), 2), "tpw26": round(n26 / max(1, len(S26) / 5), 2), "trades": n,
            "pf": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
            "eval_all": eval40(D, Dl, S, S, *ev), "eval_2026": eval40(D, Dl, S, S26, *ev),
            "_months": vec[0]}


def placebo_matrix_filter(base_u, base_m, keep_mask, mode, mi):
    """random keep-sets (ONLY) / random x1.5 sets (UP) of the same size -> draws x months of the $ change."""
    n = len(base_u)
    k = int(keep_mask.sum())
    mpos = {m: j for j, m in enumerate(mi)}
    col = np.array([mpos.get(m, -1) for m in base_m])
    ok = col >= 0
    M = np.zeros((NDRAW, len(mi)))
    for d in range(NDRAW):
        sel = np.zeros(n, bool)
        sel[RNG.choice(n, k, replace=False)] = True
        if mode == "ONLY":
            ch = np.where(sel, 0.0, -base_u)
        else:
            ch = np.where(sel, 0.5 * base_u, 0.0)
        M[d] = np.bincount(col[ok], weights=ch[ok], minlength=len(mi))
    return M


def placebo_matrix_stand(trs, mi):
    mpos = {m: j for j, m in enumerate(mi)}
    q = np.array([P.qty(t["stop_pts"]) for t in trs], float)
    pts = np.array([t["pts"] for t in trs])
    col = np.array([mpos.get(month_key(t["date"]), -1) for t in trs])
    ok = (col >= 0) & (q > 0)
    M = np.zeros((NDRAW, len(mi)))
    for d in range(NDRAW):
        s = RNG.choice([-1.0, 1.0], len(trs))
        u = q * (s * pts * PTV - FEE)
        M[d] = np.bincount(col[ok], weights=u[ok], minlength=len(mi))
    return M


def verdict(r):
    yd = r["years_delta"]
    yr = r.get("years_vs_random")
    pos = [y for y in FULL_YEARS if yd[y] > 0 and (yr is None or yr[y] > 0)]
    neg = [y for y in FULL_YEARS if yd[y] <= 0]
    h1, h2 = r["h1_2026"]["net"], r["h2_2026"]["net"]
    if len(pos) >= 4 and r["wf"] > 0:
        return "works every year" if len(pos) == 5 else "works most years (4 of 5)"
    if len(pos) == 0:
        return "never"
    if pos == [2026]:
        if h1 > 0 and h2 <= 0:
            return "2026 H1 only"
        if h2 > 0 and h1 <= 0:
            return "2026 H2 only"
        return "2026 only"
    if len(neg) >= 4:
        return f"never (only {pos[0]})"
    return "mixed (" + ", ".join(str(y) for y in pos) + " up)"


def main():
    global WF
    B = load()
    C = build_ctx(B)
    S_all = [s for s, _, _ in B["sess"]]
    print("sessions", len(S_all), S_all[0], S_all[-1], flush=True)
    stand = run_standalone(B, C)
    print("standalone done", {k: len(v) for k, v in stand.items()}, flush=True)
    LT, AT = lit_trades(B), atlas_trades(B)
    for t in LT + AT:
        t["f"] = features(B, C, t["i"], t["side"], t["price"], t["ext"])
    for k, v in stand.items():
        for t in v:
            t["usd"], t["q"] = stand_usd(t)
            t["f"] = features(B, C, t["i_in"], t["side"], t["entry"], t["entry"])
    SPANS = {"LIT": [s for s in S_all if s <= LIT_END and s >= "2021-11-08"],
             "ATLAS": [s for s in S_all if s <= ATLAS_END and s >= "2021-11-01"],
             "STAND": [s for s in S_all if s >= "2021-11-01"]}
    EV = {"LIT": (3000.0, 2000.0), "ATLAS": (1500.0, 1000.0), "STAND": (3000.0, 2000.0)}
    res = {}
    luck = []

    def add(name, concept, kind, desc, rows, base_rows, S, Mplacebo):
        mi = months_between(S[0][:7], S[-1][:7])
        r = score_variant(rows, base_rows, S, mi, kind, EV["STAND" if kind == "STAND" else kind])
        real_total = float(r["_months"].sum())
        r["months_raw"] = list(r["_months"])
        if Mplacebo is not None and kind != "STAND":
            mean = Mplacebo.mean(0)
            cols = [[k for k, m in enumerate(mi) if m.startswith(str(y))] for y in FULL_YEARS]
            vec = np.array([[r["months_raw"][k] for k in range(len(mi))]])
            r["years_better"] = int(card_metrics(vec, mi, mean)[0][0])
            r["years_vs_random"] = {y: round(float(sum(r["months_raw"][k] - mean[k] for k in c))) for y, c in zip(FULL_YEARS, cols)}
        if Mplacebo is not None:
            b_, wf_, _ = card_metrics(Mplacebo, mi, Mplacebo.mean(0) if kind != "STAND" else None)
            r["p"] = round(float((Mplacebo.sum(1) >= real_total).mean()), 3)
            tot = Mplacebo.sum(1)
            pd_ = np.array([(tot >= x).mean() for x in tot])
            h1c = [j for j, m in enumerate(mi) if "2026-01" <= m <= "2026-06"]
            h2c = [j for j, m in enumerate(mi) if m >= "2026-07"]
            oc = [j for j, m in enumerate(mi) if m < "2026-01"]
            hr = (Mplacebo[:, h1c].sum(1) > 0) & (Mplacebo[:, h2c].sum(1) > 0)
            if kind != "LIT":
                hr &= Mplacebo[:, oc].sum(1) > 0
            r["placebo_card_rate"] = round(float(((b_ >= 4) & (wf_ > 0) & (pd_ < 0.05) & hr).mean()), 3)
            r["placebo_yrs_wf_rate"] = round(float(((b_ >= 4) & (wf_ > 0)).mean()), 3)
        else:
            r["p"], r["placebo_card_rate"] = None, None
        r.update({"name": name, "concept": concept, "kind": kind, "desc": desc})
        r["verdict"] = verdict(r)
        tpw_ok = (2 <= r["tpw"] <= 4) if kind == "STAND" else True
        bk = res.get(f"{kind}_BASE") if kind != "STAND" else None
        dh1 = r["h1_2026"]["net"] - (bk["h1_2026"]["net"] if bk and name != f"{kind}_BASE" else 0)
        dh2 = r["h2_2026"]["net"] - (bk["h2_2026"]["net"] if bk and name != f"{kind}_BASE" else 0)
        d2125 = sum(r["years_delta"][y] for y in (2021, 2022, 2023, 2024, 2025))
        r["d_h1_2026"], r["d_h2_2026"], r["d_2021_25"] = dh1, dh2, d2125
        r["house_rule"] = bool(dh1 > 0 and dh2 > 0 and (kind == "LIT" or d2125 > 0))
        r["card"] = concept != "ROBUST" and bool(r["years_better"] >= 4 and r["wf"] > 0 and r["p"] is not None and r["p"] < 0.05 and tpw_ok
                         and r["house_rule"])
        r["months"] = {m: round(float(v)) for m, v in zip(mi, r.pop("_months"))}
        r.pop("months_raw")
        res[name] = r
        print(f"{name:22s} {r['verdict']:28s} yrs+{r['years_better']} wf {r['wf']:>7} p {r['p']} tot {round(real_total):>8}", flush=True)

    members = {}
    for kind, BT, S in (("LIT", LT, SPANS["LIT"]), ("ATLAS", AT, SPANS["ATLAS"])):
        WF = wf_blocks(last=S[-1][:7])
        Sset = set(S)
        BT = [t for t in BT if t["sd"] in Sset]
        base_rows = [(t["sd"], t["usd"]) for t in BT]
        mi = months_between(S[0][:7], S[-1][:7])
        # the baseline itself (absolute)
        add(f"{kind}_BASE", "BASE", kind, f"{kind} as it is (baseline)", base_rows, [], S, None)
        bu = np.array([t["usd"] for t in BT])
        bm = [month_key(t["sd"]) for t in BT]
        sets = [(f, [f], FCONCEPT[f], f) for f in FILTERS] + [(c, ks, "COMBO", "+".join(ks)) for c, ks in COMBOS.items()]
        for fid, keys, concept, desc in sets:
            mask = np.array([has(t["f"], keys) for t in BT])
            for mode in ("ONLY", "UP"):
                if mode == "ONLY":
                    rows = [(t["sd"], t["usd"]) for t, m in zip(BT, mask) if m]
                else:
                    rows = [(t["sd"], t["usd"] * (1.5 if m else 1.0)) for t, m in zip(BT, mask)]
                Mp = placebo_matrix_filter(bu, bm, mask, mode, mi)
                if kind == "ATLAS" and mode == "ONLY":
                    mem = {}
                    for src in sorted({t["src"] for t in BT}):
                        ii = [k for k, t in enumerate(BT) if t["src"] == src]
                        mem[src] = round(100 * float(mask[ii].mean()))
                    members[fid] = mem
                add(f"{kind}_{fid}_{mode}", concept, kind, f"{kind} {mode} {desc} (keeps {int(mask.sum())}/{len(mask)})",
                    rows, base_rows, S, Mp)
    # robustness (not counted as tries): shifted windows, other hourly opens instead of the 00:00 True Day Open
    for kind, BT, S in (("LIT", LT, SPANS["LIT"]), ("ATLAS", AT, SPANS["ATLAS"])):
        WF = wf_blocks(last=S[-1][:7])
        Sset = set(S)
        BT = [t for t in BT if t["sd"] in Sset]
        base_rows = [(t["sd"], t["usd"]) for t in BT]
        mi = months_between(S[0][:7], S[-1][:7])
        bu = np.array([t["usd"] for t in BT])
        bm = [month_key(t["sd"]) for t in BT]
        tests = {}
        for sh in (-120, -60, 60, 120):
            for nm, fn in (("SB", lambda cm: any(H * 60 <= cm < H * 60 + 60 for H in SB_H)), ("KZ", lambda cm: in_win(cm, KZ)),
                           ("MAC", lambda cm: in_win(cm, MACROS))):
                tests[f"R_{nm}_shift{sh:+d}"] = np.array([fn(((int(B["sm"][t["i"]]) + 1080 + sh) % 1440)) for t in BT])
        for hh in (21, 22, 23, 1, 2, 3, 6):
            m = []
            for t in BT:
                a, b = C[t["sd"]]["a"], C[t["sd"]]["b"]
                j = first_at(B, a, b, T(hh, 0))
                ok = j is not None and B["sm"][j] == T(hh, 0) and t["i"] >= j
                lvl = B["o"][j] if ok else None
                m.append(bool(ok and ((t["side"] > 0 and t["price"] < lvl) or (t["side"] < 0 and t["price"] > lvl))))
            tests[f"R_OPEN_{hh:02d}00"] = np.array(m)
        for fid, mask in tests.items():
            for mode in ("ONLY", "UP"):
                rows = ([(t["sd"], t["usd"]) for t, mm in zip(BT, mask) if mm] if mode == "ONLY"
                        else [(t["sd"], t["usd"] * (1.5 if mm else 1.0)) for t, mm in zip(BT, mask)])
                add(f"{kind}_{fid}_{mode}", "ROBUST", kind, f"{kind} {mode} {fid} (keeps {int(mask.sum())}/{len(mask)})",
                    rows, base_rows, S, placebo_matrix_filter(bu, bm, mask, mode, mi))
    S = SPANS["STAND"]
    WF = wf_blocks(last=S[-1][:7])
    mi = months_between(S[0][:7], S[-1][:7])
    for k, concept, desc, _ in STAND:
        trs = [t for t in stand[k] if t["q"]]
        add(k, concept, "STAND", desc, [(t["date"], t["usd"]) for t in trs], [], S, placebo_matrix_stand(trs, mi))
    for g, (k, keys) in GATES.items():
        trs = [t for t in stand[k] if t["q"] and has(t["f"], keys)]
        add(f"{g}_{k}", "GATE", "STAND", f"{k} only if {'+'.join(keys)}", [(t["date"], t["usd"]) for t in trs], [], S,
            placebo_matrix_stand(trs, mi))

    # per-concept walk-forward pick (best variant of the concept on the last 6 months, or none)
    pick = {}
    for kind in ("LIT", "ATLAS", "STAND"):
        S = SPANS[kind]
        blocks = wf_blocks(last=S[-1][:7])
        concepts = sorted({r["concept"] for r in res.values() if r["kind"] == kind and r["concept"] not in ("BASE", "ROBUST")})
        for cpt in concepts:
            vs = [r for r in res.values() if r["kind"] == kind and r["concept"] == cpt]
            tot, chosen = 0.0, []
            for lb, oos in blocks:
                sc = [(sum(v["months"].get(m, 0) for m in lb), v) for v in vs]
                best = max(sc, key=lambda z: z[0])
                if best[0] > 0:
                    tot += sum(best[1]["months"].get(m, 0) for m in oos)
                    chosen.append(best[1]["name"])
                else:
                    chosen.append(None)
            pick[f"{kind}:{cpt}"] = {"wf_pick": round(tot), "n_variants": len(vs),
                                     "blocks_on": sum(1 for c in chosen if c), "blocks": len(chosen),
                                     "last_pick": chosen[-1]}
    tested = [r for r in res.values() if r["placebo_card_rate"] is not None and r["concept"] != "ROBUST"]
    luck = {"variants": len(tested), "cards_real": sum(r["card"] for r in tested),
            "cards_expected_by_luck": round(sum(r["placebo_card_rate"] for r in tested), 1),
            "years4_wf_real": sum(1 for r in tested if r["years_better"] >= 4 and r["wf"] > 0),
            "years4_wf_expected": round(sum(r["placebo_yrs_wf_rate"] for r in tested), 1),
            "p05_real": sum(1 for r in tested if r["p"] < 0.05), "p05_expected": round(0.05 * len(tested), 1)}
    print(json.dumps(luck), flush=True)
    out = {"meta": {"design": "research/ictlab/DESIGN.md", "data": "data/NQ_5m.csv, data/ES_5m.csv (ES 2025-04+)",
                    "lit_span": [SPANS["LIT"][0], SPANS["LIT"][-1]], "atlas_span": [SPANS["ATLAS"][0], SPANS["ATLAS"][-1]],
                    "stand_span": [SPANS["STAND"][0], SPANS["STAND"][-1]], "draws": NDRAW},
           "luck": luck, "pick": pick, "atlas_member_keep_pct": members, "variants": res}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
    tr = {"LIT": [{"sd": t["sd"], "t": int(t["t"]), "side": t["side"], "usd": round(t["usd"], 2), "f": t["f"]} for t in LT],
          "ATLAS": [{"sd": t["sd"], "t": int(t["t"]), "side": t["side"], "usd": round(t["usd"], 2), "src": t["src"], "f": t["f"]}
                    for t in AT],
          "STAND": {k: [{"sd": t["date"], "t": t["t_in"], "side": t["side"], "usd": round(t["usd"], 2), "exit": t["exit"],
                         "stop_pts": t["stop_pts"]} for t in v if t["q"]] for k, v in stand.items()}}
    json.dump(tr, open(os.path.join(HERE, "trades.json"), "w"), default=lambda x: bool(x) if isinstance(x, np.bool_) else float(x))


if __name__ == "__main__":
    main()
