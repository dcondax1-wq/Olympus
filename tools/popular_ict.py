"""Popular ICT / SMC NQ strategies, run exactly as pre-registered in
research/writeups/specs/popular-ict-2026-11-23.md (no tuning). Paper research only.

    python -X utf8 tools/popular_ict.py          -> research/lab/popular_ict.json (+ research/lab/popular_ict_full.json)
"""
import json
import math
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.25
FEE = 1.90          # $ a micro round trip
PTV = 2.0           # MNQ $ a point
SPANS = {"2026H1": ("2026-01-01", "2026-06-30"), "2026H2": ("2026-07-01", "2026-10-31"),
         "2021-25": ("2021-11-08", "2025-12-31")}


def T(hh, mm):
    """ET clock -> session minutes (18:00 = 0)."""
    return ((hh * 60 + mm) - 1080) % 1440


# ------------------------------------------------------------------------------------------------ data
def load():
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
    hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    d = et.dt.date.to_numpy()
    sd = np.array([x + timedelta(days=1) if m >= 1080 else x for x, m in zip(d, hm)])
    # a Sunday-evening bar belongs to Monday; Saturday sessions do not exist
    sd = np.array([x + timedelta(days=2) if x.weekday() == 5 else (x + timedelta(days=1) if x.weekday() == 6 else x)
                   for x in sd])
    B = {"t": df["time"].to_numpy(), "o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float),
         "l": df["low"].to_numpy(float), "c": df["close"].to_numpy(float),
         "sm": (hm - 1080) % 1440, "sd": np.array([x.isoformat() for x in sd])}
    n = len(df)
    h, l = B["h"], B["l"]
    ph = np.zeros(n, bool)
    pl = np.zeros(n, bool)
    for j in range(2, n - 2):
        if h[j] > h[j - 1] and h[j] > h[j - 2] and h[j] >= h[j + 1] and h[j] >= h[j + 2]:
            ph[j] = True
        if l[j] < l[j - 1] and l[j] < l[j - 2] and l[j] <= l[j + 1] and l[j] <= l[j + 2]:
            pl[j] = True
    B["ph"], B["pl"] = ph, pl
    sess = []
    s0 = 0
    for i in range(1, n + 1):
        if i == n or B["sd"][i] != B["sd"][s0]:
            sess.append((B["sd"][s0], s0, i))
            s0 = i
    B["sess"] = [x for x in sess if x[2] - x[1] > 100]          # skip stub / holiday half sessions
    return B


# ------------------------------------------------------------------------------------------------ execution
def risk_usd(stop):
    return 800.0 if stop <= 20 else 800.0 * 20.0 / stop


def qty(stop, scale=1.0, cap=40):
    if stop <= 0:
        return 0
    return int(min(cap, math.floor(risk_usd(stop) * scale / (stop * PTV))))


def execute(B, a, b, o):
    """o = dict(kind market|limit|stop, side +1/-1, px, stop, i0, i1 (last bar the order may fill)). Returns trade or None."""
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
        if o["kind"] == "limit":
            # cancel if the stop trades before the fill (cannot happen through the limit, kept for gaps)
            if (side > 0 and l[i] <= o["px"]) or (side < 0 and h[i] >= o["px"]):
                fill, ent = i, o["px"]
                if side > 0 and op[i] < o["px"]:
                    ent = op[i]
                if side < 0 and op[i] > o["px"]:
                    ent = op[i]
                break
        if o["kind"] == "stop":
            if (side > 0 and h[i] >= o["px"]) or (side < 0 and l[i] <= o["px"]):
                ent = (max(o["px"], op[i]) if side > 0 else min(o["px"], op[i])) + side * TICK
                fill = i
                break
    if fill is None:
        return None
    risk = side * (ent - stp)
    if risk < 1.0:                       # degenerate (gap through the stop / < 4 ticks)
        return None
    tgt = ent + side * 2.0 * risk
    for i in range(fill, b):
        if side > 0 and l[i] <= stp:
            x, why = min(stp, op[i]) - TICK if i > fill else stp - TICK, "STOP"
            break
        if side < 0 and h[i] >= stp:
            x, why = max(stp, op[i]) + TICK if i > fill else stp + TICK, "STOP"
            break
        if i > fill and ((side > 0 and h[i] >= tgt) or (side < 0 and l[i] <= tgt)):
            x, why = tgt, "TARGET"
            break
        if sm[i] >= flat:
            x, why = c[i] - side * TICK, "EOD"
            break
    else:
        x, why = c[b - 1] - side * TICK, "EOD"
    return {"date": B["sd"][a], "side": side, "i_in": int(fill), "i_out": int(i), "t_in": int(B["t"][fill]),
            "t_out": int(B["t"][i]) + 300, "entry": float(ent), "stop": float(stp), "stop_pts": float(risk),
            "pts": float(side * (x - ent)), "exit": why}


def first_fill(B, a, b, orders):
    best = None
    for o in orders:
        tr = execute(B, a, b, o)
        if tr and (best is None or tr["i_in"] < best["i_in"]):
            best = tr
    return best


def idx_at(B, a, b, m0, m1):
    """bar indices of session [a,b) whose open (session minutes) is in [m0, m1)."""
    sm = B["sm"]
    return [i for i in range(a, b) if m0 <= sm[i] < m1]


def rng(B, a, b, m0, m1):
    ii = idx_at(B, a, b, m0, m1)
    if not ii:
        return None
    return max(B["h"][i] for i in ii), min(B["l"][i] for i in ii), ii


# ------------------------------------------------------------------------------------------------ the ten
def fvg_first(B, a, b, m0, m1, expire_m):
    h, l, sm = B["h"], B["l"], B["sm"]
    for i in range(a + 2, b):
        if not (m0 <= sm[i] < m1):
            continue
        last = max([j for j in range(i, b) if sm[j] < expire_m], default=i)
        if l[i] > h[i - 2]:
            return [{"kind": "limit", "side": 1, "px": l[i], "stop": min(l[i - 2:i + 1]) - TICK, "i0": i + 1, "i1": last}]
        if h[i] < l[i - 2]:
            return [{"kind": "limit", "side": -1, "px": h[i], "stop": max(h[i - 2:i + 1]) + TICK, "i0": i + 1, "i1": last}]
    return []


def s_silver_bullet(B, a, b, ctx):
    return fvg_first(B, a, b, T(9, 55), T(10, 55) + 1, T(11, 0))


def s_ny_open_fvg(B, a, b, ctx):
    return fvg_first(B, a, b, T(9, 30), T(9, 55), T(11, 0))


def asia(B, a, b):
    r = rng(B, a, b, T(20, 0), T(0, 0))
    return r


def midnight_open(B, a, b):
    ii = idx_at(B, a, b, T(0, 0), T(0, 5))
    return B["o"][ii[0]] if ii else None


def s_judas(B, a, b, ctx):
    r, M = asia(B, a, b), midnight_open(B, a, b)
    if r is None or M is None:
        return []
    AH, AL, _ = r
    h, l, c, sm = B["h"], B["l"], B["c"], B["sm"]
    took_h = took_l = False
    for i in range(a, b):
        if sm[i] < T(2, 0):
            continue
        if sm[i] >= T(5, 0):
            break
        if h[i] > max(AH, M):
            took_h = True
        if l[i] < min(AL, M):
            took_l = True
        hi0 = max(h[j] for j in range(a, i + 1) if sm[j] >= T(0, 0))
        lo0 = min(l[j] for j in range(a, i + 1) if sm[j] >= T(0, 0))
        if took_h and c[i] < M:
            return [{"kind": "market", "side": -1, "px": None, "stop": hi0 + TICK, "i0": i + 1, "i1": i + 1}]
        if took_l and c[i] > M:
            return [{"kind": "market", "side": 1, "px": None, "stop": lo0 - TICK, "i0": i + 1, "i1": i + 1}]
    return []


def sweep_back(B, a, b, H, L, m0, m1):
    h, l, c, sm = B["h"], B["l"], B["c"], B["sm"]
    for k in range(a, b):
        if not (m0 <= sm[k] < m1):
            continue
        up, dn = h[k] > H, l[k] < L
        if up and dn:
            return []
        if not (up or dn):
            continue
        for m in range(k, min(b, k + 13)):
            if up and c[m] < H:
                return [{"kind": "market", "side": -1, "px": None, "stop": max(h[k:m + 1]) + TICK, "i0": m + 1, "i1": m + 1}]
            if dn and c[m] > L:
                return [{"kind": "market", "side": 1, "px": None, "stop": min(l[k:m + 1]) - TICK, "i0": m + 1, "i1": m + 1}]
        return []
    return []


def s_asia_sweep(B, a, b, ctx):
    r = asia(B, a, b)
    if r is None:
        return []
    return sweep_back(B, a, b, r[0], r[1], T(0, 0), T(11, 0))


def s_pdhl(B, a, b, ctx):
    if ctx.get("prev") is None:
        return []
    PH, PL = ctx["prev"]
    return sweep_back(B, a, b, PH, PL, T(9, 30), T(15, 0))


def s_london_bo(B, a, b, ctx):
    r = rng(B, a, b, T(19, 0), T(2, 0))
    if r is None:
        return []
    BH, BL, _ = r
    ii = idx_at(B, a, b, T(2, 0), T(5, 0))
    if not ii:
        return []
    for i in ii:          # both sides inside one bar = ambiguous -> no trade
        if B["h"][i] >= BH + TICK and B["l"][i] <= BL - TICK:
            return []
        if B["h"][i] >= BH + TICK or B["l"][i] <= BL - TICK:
            break
    return [{"kind": "stop", "side": 1, "px": BH + TICK, "stop": BL - TICK, "i0": ii[0], "i1": ii[-1]},
            {"kind": "stop", "side": -1, "px": BL - TICK, "stop": BH + TICK, "i0": ii[0], "i1": ii[-1]}]


def s_po3(B, a, b, ctx):
    r, M = asia(B, a, b), midnight_open(B, a, b)
    m = rng(B, a, b, T(0, 0), T(9, 30))
    o930 = idx_at(B, a, b, T(9, 30), T(9, 35))
    if r is None or M is None or m is None or not o930:
        return []
    AH, AL, _ = r
    MH, ML, _ = m
    i = o930[0]
    up, dn = MH > AH, ML < AL
    if dn and not up and B["o"][i] > M:
        return [{"kind": "market", "side": 1, "px": None, "stop": ML - TICK, "i0": i, "i1": i}]
    if up and not dn and B["o"][i] < M:
        return [{"kind": "market", "side": -1, "px": None, "stop": MH + TICK, "i0": i, "i1": i}]
    return []


def last_pivot(B, flag, k, a_min):
    """latest pivot index j with j + 2 < k (confirmed before bar k)."""
    for j in range(k - 3, a_min - 1, -1):
        if flag[j]:
            return j
    return None


def s_ict2022(B, a, b, ctx):
    h, l, c, sm, ph, pl = B["h"], B["l"], B["c"], B["sm"], B["ph"], B["pl"]
    wins = [(T(2, 0), T(5, 0)), (T(8, 30), T(11, 0))]
    orders = []
    lo_scan = max(0, a - 60)
    used = set()
    for k in range(a, b):
        if not any(w0 <= sm[k] < w1 for w0, w1 in wins):
            continue
        for side in (-1, 1):
            flag_s, flag_o = (ph, pl) if side < 0 else (pl, ph)
            js = last_pivot(B, flag_s, k, lo_scan)
            if js is None or (side, js) in used:
                continue
            lvl = h[js] if side < 0 else l[js]
            if not ((side < 0 and h[k] > lvl) or (side > 0 and l[k] < lvl)):
                continue
            # first bar to take this swing only
            if any((side < 0 and h[q] > lvl) or (side > 0 and l[q] < lvl) for q in range(js + 1, k)):
                used.add((side, js))
                continue
            used.add((side, js))
            jo = last_pivot(B, flag_o, k, lo_scan)
            if jo is None:
                continue
            olvl = l[jo] if side < 0 else h[jo]
            for m in range(k, min(b, k + 13)):
                if (side < 0 and c[m] < olvl) or (side > 0 and c[m] > olvl):
                    fv = None
                    for i in range(k + 2, m + 1):            # most recent FVG of the leg, candle 1 >= sweep bar
                        if side < 0 and h[i] < l[i - 2]:
                            fv = h[i]
                        if side > 0 and l[i] > h[i - 2]:
                            fv = l[i]
                    if fv is not None:
                        ext = max(h[k:m + 1]) + TICK if side < 0 else min(l[k:m + 1]) - TICK
                        orders.append({"kind": "limit", "side": side, "px": fv,
                                       "stop": ext, "i0": m + 1, "i1": min(b - 1, m + 12)})
                    break
    return orders                        # side -1 = a high sweep that sells, +1 = a low sweep that buys


def s_turtle(B, a, b, ctx):
    D = ctx.get("daily")
    if D is None or len(D) < 21:
        return []
    h, l, sm = B["h"], B["l"], B["sm"]
    prior = D[-21:-1]                    # 20 prior sessions (high, low)
    lows = [x[1] for x in prior]
    highs = [x[0] for x in prior]
    jl, jh = int(np.argmin(lows)), int(np.argmax(highs))
    L20, H20 = lows[jl], highs[jh]
    okL, okH = (19 - jl) >= 3, (19 - jh) >= 3     # made >= 4 sessions before today (index 19 = yesterday)
    orders = []
    ii = idx_at(B, a, b, T(9, 30), T(15, 0))
    if not ii:
        return []
    for k in ii:
        if okL and l[k] < L20:
            # buy stop at the old low from the next bar; stop under today's low so far (updated at entry: use the
            # low up to the fill bar, approximated by the low through the break bar and re-checked below)
            orders.append(("L", k))
            break
    for k in ii:
        if okH and h[k] > H20:
            orders.append(("H", k))
            break
    out = []
    for tag, k in orders:
        # walk forward bar by bar so the stop is today's extreme at the moment of entry
        for i in range(k + 1, ii[-1] + 1):
            if tag == "L" and h[i] >= L20 + 0:
                stp = min(l[a:i + 1]) - TICK
                out.append({"kind": "stop", "side": 1, "px": L20, "stop": stp, "i0": i, "i1": i})
                break
            if tag == "H" and l[i] <= H20:
                stp = max(h[a:i + 1]) + TICK
                out.append({"kind": "stop", "side": -1, "px": H20, "stop": stp, "i0": i, "i1": i})
                break
    return out


def s_unicorn(B, a, b, ctx):
    h, l, c, o, sm, ph, pl = B["h"], B["l"], B["c"], B["o"], B["sm"], B["ph"], B["pl"]
    lo_scan = max(0, a - 60)
    orders = []
    done = set()
    for m in range(a, b):
        if not (T(2, 0) <= sm[m] < T(15, 0)):
            continue
        for side in (1, -1):
            # bullish: A low, B high, C lower low, close above B
            fB, fC = (ph, pl) if side > 0 else (pl, ph)
            jc = last_pivot(B, fC, m + 1, lo_scan)          # C confirmed by bar m
            if jc is None:
                continue
            jb = next((j for j in range(jc - 1, lo_scan - 1, -1) if fB[j]), None)
            if jb is None:
                continue
            ja = next((j for j in range(jb - 1, lo_scan - 1, -1) if fC[j]), None)
            if ja is None:
                continue
            if side > 0 and not (l[jc] < l[ja]):
                continue
            if side < 0 and not (h[jc] > h[ja]):
                continue
            Bl = h[jb] if side > 0 else l[jb]
            if (side, jb, jc) in done:
                continue
            if not ((side > 0 and c[m] > Bl) or (side < 0 and c[m] < Bl)):
                continue
            if any((side > 0 and c[q] > Bl) or (side < 0 and c[q] < Bl) for q in range(jc + 1, m)):
                done.add((side, jb, jc))
                continue
            done.add((side, jb, jc))
            # breaker = last up-close (bull) / down-close (bear) candle between B and C
            cand = [j for j in range(jb, jc + 1) if (c[j] > o[j] if side > 0 else c[j] < o[j])]
            if not cand:
                continue
            jbk = cand[-1]
            bl, bh = l[jbk], h[jbk]
            px = None
            for i in range(jc + 2, m + 1):
                if side > 0 and l[i] > h[i - 2]:
                    lo_, hi_ = max(h[i - 2], bl), min(l[i], bh)
                    if lo_ < hi_:
                        px = hi_
                if side < 0 and h[i] < l[i - 2]:
                    lo_, hi_ = max(h[i], bl), min(l[i - 2], bh)
                    if lo_ < hi_:
                        px = lo_
            if px is None:
                continue
            stp = l[jc] - TICK if side > 0 else h[jc] + TICK
            orders.append({"kind": "limit", "side": side, "px": px, "stop": stp, "i0": m + 1, "i1": min(b - 1, m + 12)})
    return orders


STRATS = [
    ("silver_bullet", "Silver Bullet (10-11 ET FVG)", "FVG / time window", s_silver_bullet),
    ("judas_swing", "Judas Swing (London, midnight open)", "false move / reversal", s_judas),
    ("asia_sweep", "Asian range sweep and reversal", "liquidity sweep / reversal", s_asia_sweep),
    ("london_breakout", "London breakout (19:00-02:00 box)", "breakout", s_london_bo),
    ("pdhl_sweep", "Previous-day high/low sweep and reversal", "liquidity sweep / reversal", s_pdhl),
    ("ny_open_fvg", "NY open FVG retrace (09:30-10:00)", "FVG / time window", s_ny_open_fvg),
    ("po3_amd", "Power of 3 / AMD", "false move / reversal", s_po3),
    ("ict2022", "2022 ICT model (sweep + MSS + FVG)", "sweep + MSS + FVG", s_ict2022),
    ("turtle_soup", "Turtle Soup (20-day false breakout)", "false breakout", s_turtle),
    ("unicorn", "Unicorn (breaker + FVG)", "sweep + MSS + FVG", s_unicorn),
]


PRIOR = {   # what docs/TESTED_AND_REJECTED.md and research/writeups already had (checked 2026-11-23, before the run)
    "silver_bullet": "yes - 'Published models as taught' (TESTED_AND_REJECTED): 0.2-1.5 trades/wk, PF ~1",
    "ict2022": "yes - 'Published models as taught' (TESTED_AND_REJECTED): PF ~1",
    "po3_amd": "partly - ICT_REPORT 2026-10-16 as a LIT filter / gate / size (noise, slightly negative); never standalone",
    "turtle_soup": "partly - ICT_REPORT 2026-10-16 as a LIT trap feature (-0.17R shadows); never standalone",
    "pdhl_sweep": "partly - E2 2026-11-13 (PDH/PDL sweep + climax volume) and the DAPHNE tree roots (fade 09:50-15:00)",
    "asia_sweep": "partly - DAPHNE tree roots (Asia fade, RTH entries only); not the 00:00-11:00 version",
    "london_breakout": "partly - DAPHNE tree London 02:00-05:00 break roots (RTH entries); not the 02:00 OCO box",
    "ny_open_fvg": "partly - Mech/IFVG and the opening-drive tests; not the first-FVG 09:30-10:00 rule",
    "judas_swing": "no - only named as a concept in the LIT report coverage notes",
    "unicorn": "no - only named as a concept in the LIT report coverage notes",
}


def run_all(B):
    out = {k: [] for k, *_ in STRATS}
    daily = []
    prev = None
    for sd, a, b in B["sess"]:
        ctx = {"prev": prev, "daily": daily}
        for k, _, _, fn in STRATS:
            tr = first_fill(B, a, b, fn(B, a, b, ctx))
            if tr:
                out[k].append(tr)
        H, L = float(B["h"][a:b].max()), float(B["l"][a:b].min())
        prev = (H, L)
        daily.append((H, L))
    return out


# ------------------------------------------------------------------------------------------------ scoring
def in_span(d, sp):
    x, y = SPANS[sp]
    return x <= d <= y


def usd(tr, scale=1.0, cap=40):
    q = qty(tr["stop_pts"], scale, cap)
    return q * (tr["pts"] * PTV - FEE), q


def day_series(T_, scale=1.0, cap=40):
    D = {}
    for t in T_:
        u, q = usd(t, scale, cap)
        if q:
            D[t["date"]] = D.get(t["date"], 0.0) + u
    return D


def stats(T_, sessions, sp):
    ss = [s for s in sessions if in_span(s, sp)]
    TT = [t for t in T_ if in_span(t["date"], sp) and qty(t["stop_pts"])]
    sk = len([t for t in T_ if in_span(t["date"], sp) and not qty(t["stop_pts"])])
    pn = [usd(t)[0] for t in TT]
    rr = [usd(t)[0] / (qty(t["stop_pts"]) * t["stop_pts"] * PTV) for t in TT]
    D = day_series(TT)
    eq = pk = dd = 0.0
    for s in ss:
        eq += D.get(s, 0.0)
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    w = [x for x in pn if x > 0]
    lo = [x for x in pn if x <= 0]
    n = len(TT)
    tt = float(np.mean(rr) / (np.std(rr, ddof=1) / math.sqrt(n))) if n > 2 and np.std(rr) > 0 else 0.0
    return {"trades": n, "skipped_big_stop": sk, "tpw": round(n / (len(ss) / 5), 2),
            "win": round(100 * len(w) / n, 1) if n else None,
            "pf": round(sum(w) / -sum(lo), 2) if lo and sum(lo) < 0 else (99.0 if w else None),
            "net": round(sum(pn)), "usd_mo": round(sum(pn) / (len(ss) / 21)), "maxdd": round(dd),
            "avg_r": round(float(np.mean(rr)), 3) if n else None, "t": round(tt, 2),
            "median_stop": round(float(np.median([t["stop_pts"] for t in TT])), 1) if n else None}, rr


def p_one(rr):
    n = len(rr)
    if n < 3 or np.std(rr) == 0:
        return 1.0
    t = np.mean(rr) / (np.std(rr, ddof=1) / math.sqrt(n))
    return 0.5 * math.erfc(t / math.sqrt(2))


def holm(ps):
    k = sorted(range(len(ps)), key=lambda i: ps[i])
    m = len(ps)
    adj = [0.0] * m
    run = 0.0
    for r, i in enumerate(k):
        run = max(run, min(1.0, (m - r) * ps[i]))
        adj[i] = run
    return adj


def bh(ps):
    m = len(ps)
    k = sorted(range(m), key=lambda i: ps[i], reverse=True)
    adj = [0.0] * m
    run = 1.0
    for r, i in enumerate(k):
        rank = m - r
        run = min(run, ps[i] * m / rank)
        adj[i] = run
    return adj


def lit():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    D50 = {x["date"]: float(x["pnl"]) for x in d["days"]}
    D25 = {}
    for t in d["trades"]:
        q = t.get("qty_total") or t.get("qty") or 1
        f = math.floor(q / 2) / q
        D25[t["day"]] = D25.get(t["day"], 0.0) + t["pnl"] * f
    return D50, D25, d["trades"]


def eval_run(D, sessions, sp, target, dd, horizon=None):
    S = sessions
    res = []
    for i0, s in enumerate(S):
        if not in_span(s, sp):
            continue
        bal = hi = best = 0.0
        out = None
        for j in range(i0, len(S) if horizon is None else min(len(S), i0 + horizon)):
            p = D.get(S[j], 0.0)
            bal += p
            best = max(best, p)
            if bal <= min(hi - dd, 100.0):
                out = ("F", j - i0 + 1)
                break
            hi = max(hi, bal)
            if bal >= target and best <= 0.30 * bal and j - i0 + 1 >= 4:
                out = ("P", j - i0 + 1)
                break
        res.append(out)
    n = len(res)
    P = [x[1] for x in res if x and x[0] == "P"]
    F = [x for x in res if x and x[0] == "F"]
    return {"pass": round(100 * len(P) / n, 1), "fail": round(100 * len(F) / n, 1),
            "median_days": int(np.median(P)) if P else None}


def combo_stats(D, sessions, sp, n_trades):
    ss = [s for s in sessions if in_span(s, sp)]
    net = sum(D.get(s, 0.0) for s in ss)
    eq = pk = dd = 0.0
    for s in ss:
        eq += D.get(s, 0.0)
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    return {"tpw": round(n_trades / (len(ss) / 5), 2), "usd_mo": round(net / (len(ss) / 21)), "maxdd": round(dd)}


def main():
    B = load()
    sessions = [s for s, _, _ in B["sess"]]
    trades = run_all(B)
    L50, L25, LT = lit()
    lit_int = {}
    for t in LT:
        lit_int.setdefault(t["day"], []).append((t["entry_t"], t["exit_t"], 1 if t["side"] == "LONG" else -1))
    rows, full = [], {}
    p_all, p_26 = [], []
    for k, name, fam, _ in STRATS:
        T_ = trades[k]
        spans, rr_all, rr_26 = {}, [], []
        for sp in SPANS:
            st, rr = stats(T_, sessions, sp)
            spans[sp] = st
            rr_all += rr
            if sp.startswith("2026"):
                rr_26 += rr
        p_all.append(p_one(rr_all))
        p_26.append(p_one(rr_26))
        # LIT relation
        TT = [t for t in T_ if qty(t["stop_pts"])]
        D = day_series(TT)
        rel = {}
        for sp in SPANS:
            ss = [s for s in sessions if in_span(s, sp) and s in L50]
            x = np.array([D.get(s, 0.0) for s in ss])
            y = np.array([L50[s] for s in ss])
            cr = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else 0.0
            ts = [t for t in TT if in_span(t["date"], sp)]
            same_day = [t for t in ts if t["date"] in lit_int]
            live = [t for t in same_day if any(a0 < t["t_out"] and t["t_in"] < a1 for a0, a1, _ in lit_int[t["date"]])]
            same_dir = [t for t in live if any(a0 < t["t_out"] and t["t_in"] < a1 and sd == t["side"]
                                               for a0, a1, sd in lit_int[t["date"]])]
            rel[sp] = {"corr": round(cr, 2), "same_day_pct": round(100 * len(same_day) / len(ts), 1) if ts else None,
                       "open_together_pct": round(100 * len(live) / len(ts), 1) if ts else None,
                       "same_side_together_pct": round(100 * len(same_dir) / len(ts), 1) if ts else None}
        # add-on to LIT on Rapid EOD 25K / 50K
        addon = {}
        lsess = [s for s in sessions if s in L50]          # LIT replay ends 2026-10-16
        for acct, LD, scale, cap, tgt, ddv in (("rapid50", L50, 1.0, 30, 3000.0, 2000.0),
                                               ("rapid25", L25, 0.5, 20, 1500.0, 1000.0)):
            DA = day_series(TT, scale, cap)
            DC = {s: LD.get(s, 0.0) + DA.get(s, 0.0) for s in lsess}
            addon[acct] = {}
            for sp in SPANS:
                nl = sum(1 for t in LT if in_span(t["day"], sp))
                na = sum(1 for t in TT if in_span(t["date"], sp) and t["date"] <= lsess[-1]
                         and qty(t["stop_pts"], scale, cap))
                addon[acct][sp] = {
                    "lit": {**combo_stats(LD, lsess, sp, nl), **{"eval_1mo": eval_run(LD, lsess, sp, tgt, ddv, 21),
                                                                     "eval_ever": eval_run(LD, lsess, sp, tgt, ddv)}},
                    "lit_plus": {**combo_stats(DC, lsess, sp, nl + na),
                                 **{"eval_1mo": eval_run(DC, lsess, sp, tgt, ddv, 21),
                                    "eval_ever": eval_run(DC, lsess, sp, tgt, ddv)}}}
        full[k] = {"name": name, "family": fam, "spans": spans, "lit": rel, "addon": addon,
                   "exits": {e: sum(1 for t in TT if t["exit"] == e) for e in ("TARGET", "STOP", "EOD")}}
    ha, ba, h26 = holm(p_all), bh(p_all), holm(p_26)
    for i, (k, name, fam, _) in enumerate(STRATS):
        f = full[k]
        f["p_one_sided_all"] = round(p_all[i], 4)
        f["p_holm_all"] = round(ha[i], 4)
        f["p_bh_all"] = round(ba[i], 4)
        f["p_one_sided_2026"] = round(p_26[i], 4)
        f["p_holm_2026"] = round(h26[i], 4)
        sp = f["spans"]
        pos = all((sp[s]["pf"] or 0) > 1.0 for s in SPANS)
        if pos and ha[i] < 0.05:
            v = "keep - passes all 3 spans and Holm"
        elif pos:
            v = "watch - PF > 1 in all 3 spans but not significant after Holm"
        else:
            bad = [s for s in SPANS if (sp[s]["pf"] or 0) <= 1.0]
            v = "reject - loses in " + ", ".join(bad)
        f["verdict"] = v
        rows.append({"id": k, "name": name, "family": fam,
                     "spans": {s: {x: sp[s][x] for x in ("tpw", "win", "pf", "usd_mo", "maxdd")} for s in SPANS},
                     "corr_lit": {s: f["lit"][s]["corr"] for s in SPANS},
                     "p_holm": f["p_holm_all"], "tested_before": PRIOR[k], "verdict": v})
        f["tested_before"] = PRIOR[k]
    rows.sort(key=lambda r: -min(r["spans"][s]["usd_mo"] for s in SPANS))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        full[r["id"]]["rank"] = i
    meta = {"built": "2026-11-23", "spec": "research/writeups/specs/popular-ict-2026-11-23.md",
            "writeup": "research/writeups/popular-ict-2026-11-23.md", "tool": "tools/popular_ict.py",
            "data": "data/NQ_5m.csv (TradingView CME NQ1!, 5m, back-adjusted)", "spans": SPANS, "lit_compare_end": "2026-10-16 (LIT replay end; strategy spans run to the data end 2026-10-31 for H2)",
            "sizing": "LIT rule: $800 up to a 20-pt stop then 800x20/stop, floor micros, max 40, <1 = skip; 2R target",
            "costs": "$1.90/micro RT + 1 tick slip on market/stop entries and stop/EOD exits",
            "paper_only": True}
    os.makedirs(os.path.join(ROOT, "research", "lab"), exist_ok=True)
    json.dump({"meta": meta, "strategies": rows}, open(os.path.join(ROOT, "research", "lab", "popular_ict.json"), "w"),
              indent=1)
    json.dump({"meta": meta, "strategies": full}, open(os.path.join(ROOT, "research", "lab", "popular_ict_full.json"), "w"),
              indent=1)
    for r in rows:
        print(r["id"], {s: (v["tpw"], v["win"], v["pf"], v["usd_mo"], v["maxdd"]) for s, v in r["spans"].items()},
              r["p_holm"], r["verdict"])


if __name__ == "__main__":
    sys.exit(main())
