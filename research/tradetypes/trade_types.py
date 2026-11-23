"""New trade types (2026-11-23): four lanes that are NOT intraday directional NQ setups.

  python -X utf8 research/tradetypes/trade_types.py      # -> research/lab/trade_types.json (about 1 minute)

Research only, paper, nothing armed. Futures data only (data/NQ_5m.csv, data/ES_5m.csv: TradingView NQ1!/ES1! exports,
additive back-adjusted, so point differences are real). All rules were written into VARIANTS below before the first run.

Lanes
 1. ES/NQ relative value: z-score mean reversion of ln(NQ/ES), intraday (5m) and 1-3 sessions (daily z, legs closed at
    15:55 and re-opened at 18:00 each session, because every firm forces flat; the continuous hold is shown as BANNED).
 2. Holds: overnight drift (18:00 -> 09:30 inside one MFFU day), turn of month, pre-holiday, post-FOMC drift; plus the
    textbook close -> open hold for reference (BANNED: crosses the 16:10 flat).
 3. Event days: monthly OPEX Friday, quad witching / index rebalance days (3rd Fri of Mar/Jun/Sep/Dec), CPI / NFP
    straddle breakout of the 08:30-08:35 bar.
 4. Regime switch: rotate LIT <-> ATLAS on the strategies' RELATIVE trailing record (new; the drift switch only paused a
    strategy to paper on its own record, round 3 used market weather).

Costs: $1.90 a micro round trip + 1 tick per side on market fills and stops (MNQ $0.50, MES $1.25 a tick).
Size: $250 risk a trade (ATLAS's fixed size), at most 20 micros (Builder 25K), quantity = floor(risk / per-micro risk),
at least 1 micro (a full-session NQ hold with a 1-ATR stop risks ~$600-1,000 on ONE micro: reported as risk_1micro).
Stats per span: 2026 H1 (Jan-Jun), 2026 H2 (Jul-Oct), REF (2021-10-18 .. 2025-12-31; ES lanes only 2025-04-14 on).
p-values: calendar / event long-or-directional holds -> placebo (the same hold on random non-event sessions of the span,
4,000 draws); spread and straddle -> one-sided bootstrap of mean $ > 0; regime -> random switches with the same share of
LIT-off trades. A variant's p = the worst of its 3 spans (it must hold in all), then Holm across the whole family.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "research", "lab", "trade_types.json")
RNG = np.random.default_rng(20261123)
NDRAW = 4000

PV = {"NQ": 2.0, "ES": 5.0}           # micro $ per point
TICK = 0.25
COMM = 1.90
RISK = 250.0
MAXQ = 20
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-31"), "REF": ("2021-10-18", "2025-12-31")}
LIT_END = "2026-10-16"                # LIT / ATLAS stored trades end here

# minutes since the 18:00 ET session open
def m(hhmm):
    h, mi = map(int, hhmm.split(":"))
    return ((h * 60 + mi) - 1080) % 1440


# ------------------------------------------------------------------------------------------------ data
def load(sym):
    d = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_5m.csv"))
    et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    d["sess"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    d["tm"] = ((et.dt.hour * 60 + et.dt.minute) - 1080) % 1440
    d = d[d.tm < m("17:00")]           # 16:55 is the last bar
    return d.reset_index(drop=True)


def sessions(d):
    out = {}
    for s, g in d.groupby("sess", sort=True):
        if len(g) < 30:                # Sunday stubs / broken days
            continue
        out[s] = {"tm": g.tm.to_numpy(), "o": g.open.to_numpy(), "h": g.high.to_numpy(), "l": g.low.to_numpy(),
                  "c": g.close.to_numpy(), "t": g.time.to_numpy()}
    return out


def span_of(day):
    for k, (a, z) in SPANS.items():
        if a <= day <= z:
            return k
    return None


# ------------------------------------------------------------------------------------------------ calendar
def us_holidays(y0=2021, y1=2027):
    from pandas.tseries.holiday import (USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay, USLaborDay,
                                        USThanksgivingDay, Holiday, nearest_workday)
    rules = [Holiday("NY", month=1, day=1, observance=nearest_workday), USMartinLutherKingJr, USPresidentsDay, GoodFriday,
             USMemorialDay, Holiday("J19", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
             Holiday("J4", month=7, day=4, observance=nearest_workday), USLaborDay, USThanksgivingDay,
             Holiday("XM", month=12, day=25, observance=nearest_workday)]
    a, z = f"{y0}-01-01", f"{y1}-12-31"
    hol = set()
    for r in rules:
        for x in r.dates(a, z):
            hol.add(x.strftime("%Y-%m-%d"))
    return hol


def third_fridays(days):
    out = set()
    for d in days:
        x = dt.date.fromisoformat(d)
        if x.weekday() == 4 and 15 <= x.day <= 21:
            out.add(d)
    return out


def events():
    e = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
    ev = collections.defaultdict(set)
    for _, r in e.iterrows():
        n = str(r.event)
        if n.startswith("FOMC rate decision"):
            ev["fomc"].add(r.date)
        elif n.startswith("CPI"):
            ev["cpi"].add(r.date)
        elif n.startswith("Non-Farm Payrolls"):
            ev["nfp"].add(r.date)
    return ev


# ------------------------------------------------------------------------------------------------ one-leg trade engine
def hold(S, day, t_in, t_out, side, stop_pts, tp_pts=None):
    """market in at the open of the first bar >= t_in, out at the open of the first bar >= t_out (or the session's last
    close), protective stop stop_pts away (1-tick slip). Returns (net $, qty) at $250 risk or None."""
    s = S.get(day)
    if s is None or stop_pts is None or not np.isfinite(stop_pts) or stop_pts <= 0:
        return None
    tm = s["tm"]
    i = np.searchsorted(tm, t_in)
    if i >= len(tm) or tm[i] - t_in > 15:
        return None
    j = np.searchsorted(tm, t_out)
    px = s["o"][i] + side * TICK
    stop = px - side * stop_pts
    tp = px + side * tp_pts if tp_pts else None
    exit_px = None
    for k in range(i, min(j, len(tm))):
        lo, hi = s["l"][k], s["h"][k]
        if (side > 0 and lo <= stop) or (side < 0 and hi >= stop):
            exit_px = stop - side * TICK
            break
        if tp is not None and ((side > 0 and hi >= tp) or (side < 0 and lo <= tp)):
            exit_px = tp
            break
    if exit_px is None:
        exit_px = (s["o"][j] if j < len(tm) else s["c"][-1]) - side * TICK
    per = (stop_pts + 2 * TICK) * PV["NQ"] + COMM
    q = max(1, min(MAXQ, int(RISK // per)))     # a hold needs at least 1 micro even when 1 micro risks > $250
    return q * (side * (exit_px - px) * PV["NQ"] - COMM), q


# ------------------------------------------------------------------------------------------------ stats
def stats(tr, days_in_span):
    """tr = list of (day, $)."""
    out = {}
    for k, (a, z) in SPANS.items():
        x = [(d, v) for d, v in tr if a <= d <= z]
        nd = days_in_span[k]
        if nd == 0:
            out[k] = None
            continue
        p = np.array([v for _, v in x], float)
        by = collections.defaultdict(float)
        for d, v in x:
            by[d] += v
        eq = np.cumsum([by[d] for d in sorted(by)]) if by else np.array([0.0])
        dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(eq) else 0.0
        gl = -p[p < 0].sum()
        out[k] = {"n": int(len(p)), "per_week": round(len(p) / (nd / 5), 2), "win_pct": round(100 * float((p > 0).mean()), 1) if len(p) else None,
                  "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else (None if not len(p) else 99.0),
                  "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (nd / 21)), "max_dd": round(min(dd, 0.0)),
                  "avg": round(float(p.mean()), 1) if len(p) else None}
    return out


def boot_p(vals):
    v = np.asarray(vals, float)
    if len(v) < 5:
        return 1.0
    mu = v.mean()
    b = RNG.choice(v - mu, size=(NDRAW, len(v)), replace=True).mean(1)
    return float((b >= mu).mean())


def placebo_p(ev_vals, pool_vals):
    ev, pool = np.asarray(ev_vals, float), np.asarray(pool_vals, float)
    if len(ev) < 3 or len(pool) < len(ev) + 5:
        return 1.0
    obs = ev.mean()
    draws = np.array([RNG.choice(pool, size=len(ev), replace=False).mean() for _ in range(NDRAW)])
    return float((draws >= obs).mean())


def holm(ps):
    names = sorted(ps, key=lambda k: ps[k])
    n, out, run = len(names), {}, 0.0
    for i, k in enumerate(names):
        run = max(run, min(1.0, (n - i) * ps[k]))
        out[k] = run
    return out


def bh(ps):
    names = sorted(ps, key=lambda k: ps[k])
    n, out, run = len(names), {}, 1.0
    for i in range(n - 1, -1, -1):
        k = names[i]
        run = min(run, ps[k] * n / (i + 1))
        out[k] = min(1.0, run)
    return out


# ------------------------------------------------------------------------------------------------ lane 2/3: holds and events
def atr_map(S):
    days = sorted(S)
    rng = np.array([S[d]["h"].max() - S[d]["l"].min() for d in days])
    out = {}
    for i, d in enumerate(days):
        if i >= 20:
            out[d] = float(np.mean(rng[i - 20:i]))
    return out


def run_holds(S, ATR, ev, hol):
    days = sorted(S)
    idx = {d: i for i, d in enumerate(days)}
    # trading days that precede a holiday (the last session before a closed weekday)
    pre_hol = set()
    for h in hol:
        x = dt.date.fromisoformat(h) - dt.timedelta(days=1)
        while x.weekday() >= 5:
            x -= dt.timedelta(days=1)
        if x.isoformat() in S:
            pre_hol.add(x.isoformat())
    thanks = {d for d in pre_hol if dt.date.fromisoformat(d).month == 11}
    # turn of month: last 1 + first 3 sessions of each month
    tom = set()
    bym = collections.defaultdict(list)
    for d in days:
        bym[d[:7]].append(d)
    for mo, ds in bym.items():
        tom.update(ds[:3])
        tom.add(ds[-1])
    fomc = {d for d in ev["fomc"] if d in S}
    post_fomc_next = {days[idx[d] + 1] for d in fomc if idx[d] + 1 < len(days)}
    tf = third_fridays(days)
    quad = {d for d in tf if dt.date.fromisoformat(d).month in (3, 6, 9, 12)}
    opex = tf - quad
    full = lambda d: ATR.get(d)
    V = {}
    # -- lane 2
    V["H1 overnight drift 18:00->09:30 long"] = dict(lane=2, days=set(days), f=lambda d: hold(S, d, m("18:00"), m("09:30"), 1, 0.6 * full(d) if full(d) else None), placebo=False)
    V["H2 turn of month 18:00->15:55 long"] = dict(lane=2, days=tom, f=lambda d: hold(S, d, m("18:00"), m("15:55"), 1, full(d)), placebo=True)
    V["H3 pre-holiday 18:00->close long"] = dict(lane=2, days=pre_hol, f=lambda d: hold(S, d, m("18:00"), m("15:55"), 1, full(d)), placebo=True)
    V["H4 Thanksgiving Wed+Fri long"] = dict(lane=2, days=thanks | {days[idx[d] + 1] for d in thanks if idx[d] + 1 < len(days)},
                                            f=lambda d: hold(S, d, m("18:00"), m("15:55"), 1, full(d)), placebo=True)

    def post_fomc(d):           # direction of 14:00 -> 14:30, ride it 14:30 -> 15:55, stop = 14:00-14:30 range
        s = S.get(d)
        if s is None:
            return None
        a, b = np.searchsorted(s["tm"], m("14:00")), np.searchsorted(s["tm"], m("14:30"))
        if b >= len(s["tm"]) or b - a < 5:
            return None
        mv = s["o"][b] - s["o"][a]
        rg = s["h"][a:b].max() - s["l"][a:b].min()
        return hold(S, d, m("14:30"), m("15:55"), 1 if mv > 0 else -1, rg) if mv != 0 else None

    def fomc_next(d):           # next session 18:00 -> 15:55 in the direction of the FOMC day's 14:00 -> 15:55 move
        i = idx[d] - 1
        p = S.get(days[i])
        if p is None:
            return None
        a, b = np.searchsorted(p["tm"], m("14:00")), np.searchsorted(p["tm"], m("15:55"))
        if b >= len(p["tm"]):
            return None
        mv = p["o"][b] - p["o"][a]
        return hold(S, d, m("18:00"), m("15:55"), 1 if mv > 0 else -1, full(d)) if mv != 0 else None

    V["H5 post-FOMC 14:30->15:55 with the first 30 min"] = dict(lane=2, days=fomc, f=post_fomc, placebo="dir")
    V["H6 post-FOMC next session with the FOMC move"] = dict(lane=2, days=post_fomc_next, f=fomc_next, placebo="dir")
    # BANNED reference: buy the RTH close, sell the next RTH open (16:00 -> 09:30, crosses the 16:10 flat)
    V["X1 close->open long (BANNED, reference)"] = dict(lane=2, days=set(days), f=None, placebo=False, banned=True)

    # -- lane 3
    V["E1 monthly OPEX Fri long 18:00->15:55"] = dict(lane=3, days=opex, f=lambda d: hold(S, d, m("18:00"), m("15:55"), 1, full(d)), placebo=True)
    V["E2 quad witching / rebalance Fri long"] = dict(lane=3, days=quad, f=lambda d: hold(S, d, m("18:00"), m("15:55"), 1, full(d)), placebo=True)

    def last_hour_fade(d):      # rebalance-day MOC flows: fade 09:30 -> 15:00 move from 15:00 to 15:55, stop 0.25 ATR
        s = S.get(d)
        if s is None or not full(d):
            return None
        a, b = np.searchsorted(s["tm"], m("09:30")), np.searchsorted(s["tm"], m("15:00"))
        if b >= len(s["tm"]):
            return None
        mv = s["o"][b] - s["o"][a]
        return hold(S, d, m("15:00"), m("15:55"), -1 if mv > 0 else 1, 0.25 * full(d)) if mv != 0 else None

    V["E3 quad witching last-hour fade"] = dict(lane=3, days=quad, f=last_hour_fade, placebo="dir")

    def straddle(d):            # OCO stops 1 tick outside the 08:30-08:35 bar, 08:35-09:30, stop = other side, 2R or 11:00
        s = S.get(d)
        if s is None:
            return None
        tm = s["tm"]
        k = np.searchsorted(tm, m("08:30"))
        if k >= len(tm) or tm[k] != m("08:30"):
            return None
        hi, lo = s["h"][k] + TICK, s["l"][k] - TICK
        rng = hi - lo
        e = np.searchsorted(tm, m("09:30"))
        x = np.searchsorted(tm, m("11:00"))
        for i in range(k + 1, min(e, len(tm))):
            up, dn = s["h"][i] >= hi, s["l"][i] <= lo
            if not (up or dn):
                continue
            if up and dn:       # both in one 5m bar: assume the worse (a stop-out at the other side)
                q = max(1, min(MAXQ, int(RISK // ((rng + 2 * TICK) * PV["NQ"] + COMM))))
                return q * (-(rng + 2 * TICK) * PV["NQ"] - COMM), q
            side = 1 if up else -1
            px = (hi if up else lo) + side * TICK
            stop = lo if up else hi
            risk = abs(px - stop)
            tp = px + side * 2 * risk
            q = max(1, min(MAXQ, int(RISK // ((risk + 2 * TICK) * PV["NQ"] + COMM))))
            out = None
            for j in range(i + 1, min(x, len(tm))):
                if (side > 0 and s["l"][j] <= stop) or (side < 0 and s["h"][j] >= stop):
                    out = stop - side * TICK
                    break
                if (side > 0 and s["h"][j] >= tp) or (side < 0 and s["l"][j] <= tp):
                    out = tp
                    break
            if out is None:
                out = (s["o"][x] if x < len(tm) else s["c"][-1]) - side * TICK
            return q * (side * (out - px) * PV["NQ"] - COMM), q
        return None

    cpinfp = {d for d in ev["cpi"] | ev["nfp"] if d in S}
    V["E4 CPI/NFP straddle of the 08:30 bar"] = dict(lane=3, days=cpinfp, f=straddle, placebo=False)
    return V, days


def textbook_close_open(S, ATR, days):
    out = []
    for i in range(1, len(days)):
        p, d = S[days[i - 1]], S[days[i]]
        a = np.searchsorted(p["tm"], m("16:00"))
        b = np.searchsorted(d["tm"], m("09:30"))
        if a >= len(p["tm"]) or b >= len(d["tm"]) or not ATR.get(days[i]):
            continue
        st = 0.6 * ATR[days[i]]
        per = (st + 2 * TICK) * PV["NQ"] + COMM
        q = max(1, min(MAXQ, int(RISK // per)))
        px = p["o"][a] + TICK
        lo = min(p["l"][a:].min(), d["l"][:b].min())
        ex = (px - st - TICK) if lo <= px - st else d["o"][b] - TICK
        out.append((days[i], q * ((ex - px) * PV["NQ"] - COMM)))
    return out


# ------------------------------------------------------------------------------------------------ lane 1: ES/NQ spread
def spread_lane(NQ, ES):
    a = NQ[["time", "sess", "tm", "close"]].merge(ES[["time", "close"]], on="time", suffixes=("_nq", "_es"))
    a["x"] = np.log(a.close_nq / a.close_es)
    V = {}
    unit_nq, unit_es = 2, 3               # 2 MNQ ($2) vs 3 MES ($5): close to dollar-neutral at 2025-26 prices
    cost_unit = (unit_nq + unit_es) * COMM + 2 * (unit_nq * TICK * PV["NQ"] + unit_es * TICK * PV["ES"])

    def unit_pnl(r0, r1):
        """$ of one unit long the spread (long 2 MNQ, short 3 MES) from row r0 to r1, before costs."""
        return unit_nq * PV["NQ"] * (r1.close_nq - r0.close_nq) - unit_es * PV["ES"] * (r1.close_es - r0.close_es)

    # intraday: z over the last 48 bars (4 h), entries 09:45-15:15, exit z through 0 / |z| 4 stop / 15:55
    for name, ze, zs in (("S1 NQ/ES intraday z 2.0", 2.0, 4.0), ("S2 NQ/ES intraday z 2.5", 2.5, 4.5)):
        tr = []
        for sess, g in a.groupby("sess", sort=True):
            g = g.reset_index(drop=True)
            if len(g) < 100:
                continue
            mu = g.x.rolling(48).mean()
            sd = g.x.rolling(48).std()
            z = (g.x - mu) / sd
            pos, r0, ent_sd, side = 0, None, None, 0
            for i in range(48, len(g)):
                if pos == 0:
                    if m("09:45") <= g.tm[i] <= m("15:15") and abs(z[i]) >= ze and sd[i] > 0:
                        side = -1 if z[i] > 0 else 1        # z high -> NQ rich -> short the spread
                        pos, r0, ent_sd, z0 = 1, g.iloc[i], sd[i], z[i]
                        # risk per unit to the stop (|z| to zs) in $
                        risk_u = (zs - abs(z0)) * ent_sd * (unit_nq * PV["NQ"] * g.close_nq[i]) + cost_unit
                        q = max(1, min(MAXQ // (unit_nq + unit_es), int(RISK // risk_u)))
                    continue
                done = (side < 0 and z[i] <= 0) or (side > 0 and z[i] >= 0) or abs(z[i]) >= zs or g.tm[i] >= m("15:55") or i == len(g) - 1
                if done:
                    pnl = side * unit_pnl(r0, g.iloc[i]) * q - q * cost_unit
                    tr.append((sess, float(pnl)))
                    pos = 0
                    if g.tm[i] >= m("15:55"):
                        break
        V[name] = dict(lane=1, trades=tr, ptype="boot", es=True)

    # 1-3 sessions: daily z of the 15:55 ratio vs the 20 prior sessions; enter next 18:00, flat 15:55, re-enter each
    # session while |z| > 0.5 and under 3 sessions (firm-legal chain); BANNED continuous version for reference
    rows = []
    for sess, g in a.groupby("sess", sort=True):
        g = g.reset_index(drop=True)
        k = np.searchsorted(g.tm.to_numpy(), m("15:55"))
        if len(g) < 100 or k >= len(g):
            continue
        rows.append((sess, g.iloc[0], g.iloc[k], float(g.x[k])))
    xs = np.array([r[3] for r in rows])
    for name, ze, chain in (("S3 NQ/ES 1-3 day z 1.5 (daily legs)", 1.5, True), ("S4 NQ/ES 1-3 day z 2.0 (daily legs)", 2.0, True),
                            ("X2 NQ/ES 1-3 day z 1.5 continuous (BANNED)", 1.5, False)):
        tr, i = [], 20
        while i < len(rows) - 1:
            mu, sd = xs[i - 20:i].mean(), xs[i - 20:i].std(ddof=1)
            z = (xs[i] - mu) / sd if sd > 0 else 0
            if abs(z) < ze:
                i += 1
                continue
            side = -1 if z > 0 else 1
            notional = unit_nq * PV["NQ"] * rows[i][2].close_nq
            q = max(1, min(MAXQ // (unit_nq + unit_es), int(RISK // (1.5 * sd * notional + cost_unit))))
            held, pnl, j = 0, 0.0, i + 1
            start = rows[j][1]
            while j < len(rows) and held < 3:
                o, c = rows[j][1], rows[j][2]
                if chain:
                    pnl += side * unit_pnl(o, c) * q - q * cost_unit
                held += 1
                zj = (xs[j] - mu) / sd
                if (side < 0 and zj <= 0.5 * 0) or (side > 0 and zj >= 0) or abs(zj) >= ze + 1.5:
                    break
                j += 1
            j = min(j, len(rows) - 1)
            if not chain:
                pnl = side * unit_pnl(start, rows[j][2]) * q - q * cost_unit
            tr.append((rows[j][0], float(pnl)))
            i = j + 1
        V[name] = dict(lane=1, trades=tr, ptype="boot", es=True, banned=not chain)
    return V


# ------------------------------------------------------------------------------------------------ lane 4: regime rotation
def regime_lane():
    sys.path[:0] = [ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")]
    logging.disable(logging.ERROR)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        import account4_sim as A4
        import atlas_health as AH
        S, BY = A4.load()
        lit = [dict(t, strat="LIT") for ts in BY for t in ts]
        atl = [dict(t, strat="ATLAS") for t in AH.stream()]
    usd = {"LIT": 350.0, "ATLAS": 250.0}

    def tusd(t):
        q = int(usd[t["strat"]] // ((t["risk"] + TICK) * PV["NQ"] + COMM))
        return q * (t["pts"] * PV["NQ"] - COMM) if q > 0 else 0.0

    allt = sorted(lit + atl, key=lambda t: (t["entry_t"], t["strat"]))
    for t in allt:
        t["usd"] = tusd(t)
        t["R"] = t["usd"] / usd[t["strat"]]
    daily = collections.defaultdict(float)
    for t in allt:
        daily[t["day"]] += t["usd"]

    def rotate(N, mode):
        """mode 'sub': LIT while its last N closed trades sum > 0, else ATLAS takes LIT's slot (ATLAS always on);
        'rot': only the strategy with the better last-N sum trades, flat if both <= 0; record keeps every trade (paper)."""
        hist = {"LIT": [], "ATLAS": []}
        pend = []                                   # trades not closed yet at this entry
        kept, off = [], 0
        for t in allt:
            done = [p for p in pend if p["exit_t"] <= t["entry_t"]]
            for p in done:
                hist[p["strat"]].append(p["R"])
                pend.remove(p)
            sL = sum(hist["LIT"][-N:]) if len(hist["LIT"]) >= N else 1.0
            sA = sum(hist["ATLAS"][-N:]) if len(hist["ATLAS"]) >= N else 1.0
            if mode == "sub":
                on = t["strat"] == "ATLAS" or sL > 0
            else:
                best = "LIT" if sL >= sA else "ATLAS"
                on = t["strat"] == best and max(sL, sA) > 0
            if on:
                kept.append((t["day"], t["usd"]))
            else:
                off += 1
            pend.append(t)
        return kept, off

    V = {}
    base = [(t["day"], t["usd"]) for t in allt]
    lit_only = [(t["day"], t["usd"]) for t in allt if t["strat"] == "LIT"]
    for name, N, mode in (("R1 LIT if its last 40 > 0, ATLAS always", 40, "sub"), ("R2 rotate to the better of last 40", 40, "rot"),
                          ("R3 rotate to the better of last 20", 20, "rot"), ("R4 rotate to the better of last 60", 60, "rot")):
        kept, off = rotate(N, mode)
        V[name] = dict(lane=4, trades=kept, ptype="regime", n_off=off)
    return V, base, lit_only, allt, daily, sorted(S)


def regime_placebo(allt, kept_trades, n_off, span):
    """share of random switch-offs (same count of trades off, inside the span) that beat the real switch's net."""
    a, z = SPANS[span]
    T = [t for t in allt if a <= t["day"] <= z]
    if not T:
        return 1.0
    ids = set()
    real = sum(v for d, v in kept_trades if a <= d <= z)
    frac = 1 - sum(1 for d, v in kept_trades if a <= d <= z) / len(T)
    k = int(round(frac * len(T)))
    if k == 0:
        return 1.0
    usd = np.array([t["usd"] for t in T])
    tot = usd.sum()
    draws = np.array([tot - usd[RNG.choice(len(T), k, replace=False)].sum() for _ in range(NDRAW)])
    return float((draws >= real).mean())


# ------------------------------------------------------------------------------------------------ main
def corr_daily(tr, ref_daily, a, z):
    by = collections.defaultdict(float)
    for d, v in tr:
        by[d] += v
    ds = sorted(d for d in ref_daily if a <= d <= z)
    if len(ds) < 30:
        return None
    x = np.array([by.get(d, 0.0) for d in ds])
    y = np.array([ref_daily[d] for d in ds])
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)


def main():
    NQd, ESd = load("NQ"), load("ES")
    S = sessions(NQd)
    ATR = atr_map(S)
    ev = events()
    hol = us_holidays()
    days_all = sorted(S)
    es_days = set(ESd.sess)
    ndays = {k: sum(1 for d in days_all if a <= d <= z) for k, (a, z) in SPANS.items()}
    ndays_es = {k: sum(1 for d in days_all if a <= d <= z and d in es_days and d >= "2025-04-14") for k, (a, z) in SPANS.items()}

    V, _ = run_holds(S, ATR, ev, hol)
    res = {}
    # every-session pools for placebos
    pool_cache = {}

    def pool(key, f, a, z, exclude):
        ck = (key, a)
        if ck not in pool_cache:
            vals = []
            for d in days_all:
                if a <= d <= z and d not in exclude:
                    r = f(d)
                    if r:
                        vals.append(r[0])
            pool_cache[ck] = vals
        return pool_cache[ck]

    for name, v in V.items():
        if v.get("banned") and v["f"] is None:
            tr = textbook_close_open(S, ATR, days_all)
        else:
            tr = []
            for d in sorted(v["days"]):
                r = v["f"](d)
                if r:
                    tr.append((d, float(r[0])))
        ps = {}
        for k, (a, z) in SPANS.items():
            ev_vals = [x for d, x in tr if a <= d <= z]
            if v["placebo"] is True:
                ps[k] = placebo_p(ev_vals, pool(name, v["f"], a, z, v["days"]))
            elif v["placebo"] == "dir":
                # the same directional rule on random non-event sessions
                ps[k] = placebo_p(ev_vals, pool(name, v["f"], a, z, v["days"]))
            else:
                ps[k] = boot_p(ev_vals)
        res[name] = {"lane": v["lane"], "trades": tr, "p": ps, "banned": bool(v.get("banned")), "es": False}

    for name, v in spread_lane(NQd, ESd).items():
        ps = {k: boot_p([x for d, x in v["trades"] if a <= d <= z]) for k, (a, z) in SPANS.items()}
        res[name] = {"lane": 1, "trades": v["trades"], "p": ps, "banned": bool(v.get("banned")), "es": True}

    RV, base, lit_only, allt, daily_ref, s_days = regime_lane()
    for name, v in RV.items():
        ps = {k: regime_placebo(allt, v["trades"], v["n_off"], k) for k in SPANS}
        res[name] = {"lane": 4, "trades": v["trades"], "p": ps, "banned": False, "es": False, "n_off": v["n_off"]}
    reg_days = {k: sum(1 for d in s_days if a <= d <= z) for k, (a, z) in SPANS.items()}

    # stats, correlation, multiple testing
    out = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "script": "research/tradetypes/trade_types.py",
           "writeup": "research/writeups/new-trade-types-2026-11-23.md", "spans": SPANS,
           "costs": "$1.90 a micro round trip + 1 tick a side (MNQ $0.50, MES $1.25); $250 risk a trade, max 20 micros",
           "ref_note": "ES/NQ lanes: REF = 2025-04-14 .. 2025-12-31 only (ES1! history starts 2025-04-14)",
           "baseline": {"LIT+ATLAS": stats(base, reg_days), "LIT only": stats(lit_only, reg_days)}, "variants": {}}
    fam = {}
    for name, r in res.items():
        nd = reg_days if r["lane"] == 4 else (ndays_es if r["es"] else ndays)
        st = stats(r["trades"], nd)
        if r["lane"] == 4:
            cor = None
        else:
            cor = corr_daily(r["trades"], daily_ref, "2021-11-01", LIT_END) if not r["es"] else corr_daily(r["trades"], daily_ref, "2025-04-14", LIT_END)
        pmax = max(r["p"][k] for k in SPANS)
        allpos = all(st[k] and st[k]["net"] > 0 for k in SPANS)
        if r["lane"] == 4:
            bst = out["baseline"]["LIT+ATLAS"]
            allpos = all(st[k]["net"] > bst[k]["net"] for k in SPANS)
        out["variants"][name] = {"lane": r["lane"], "banned_everywhere": r["banned"], "stats": st,
                                 "p_by_span": {k: round(v, 4) for k, v in r["p"].items()}, "p_worst_span": round(pmax, 4),
                                 "positive_all_3": allpos, "corr_daily_vs_lit_atlas": cor,
                                 **({"lit_atlas_trades_switched_off": r["n_off"]} if "n_off" in r else {})}
        if not r["banned"]:
            fam[name] = pmax
    H, B = holm(fam), bh(fam)
    for name in out["variants"]:
        vv = out["variants"][name]
        vv["p_holm"] = round(H[name], 4) if name in H else None
        vv["p_bh"] = round(B[name], 4) if name in B else None
        vv["passes"] = bool(name in H and H[name] < 0.05 and vv["positive_all_3"])
    out["family_size"] = len(fam)
    out["n_pass"] = sum(1 for v in out["variants"].values() if v["passes"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    # plain print
    print(f"family {len(fam)}  pass {out['n_pass']}")
    for b, st in out["baseline"].items():
        print(f"{b:52s}", "  ".join(f"{k}: n{st[k]['n']} ${st[k]['per_month']}/mo pf{st[k]['pf']} dd{st[k]['max_dd']}" for k in SPANS))
    for name, v in out["variants"].items():
        st = v["stats"]
        cells = "  ".join(f"{k}: n{st[k]['n']} {st[k]['per_week']}/wk w{st[k]['win_pct']} pf{st[k]['pf']} ${st[k]['per_month']}/mo dd{st[k]['max_dd']}" if st[k] else f"{k}: -" for k in SPANS)
        print(f"{name:52s} {cells} | p {v['p_worst_span']} holm {v['p_holm']} corr {v['corr_daily_vs_lit_atlas']} {'PASS' if v['passes'] else ''}")


if __name__ == "__main__":
    main()
