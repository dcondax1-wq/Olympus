"""Quant anomalies on CME NQ (owner 2026-10-23: "What about quant, could you learn that?").

The documented, published index-futures anomalies, textbook version first, then a small PRE-DECLARED set of variants (no
grids), on the TradingView CME NQ1! / MNQ1! 5-minute bars (data/NQ_5m.csv, back-adjusted additively: point moves exact; %
returns use the unadjusted price = adjusted - later roll gaps, data/NQ_rolls.json). VIX / VIX3M / VXN from CBOE's files.
Futures only, never Yahoo (ES cross-check stops at 2026-08-21, where data/ES_5m.csv switches to Yahoo).

  family  variant          idea (paper)                                                        trade
  IM      im_textbook      Gao, Han, Li, Zhou 2018 (JFE) "Market intraday momentum": the first   sign(prev 16:00 -> 10:00) ->
                           half hour (incl. the overnight) predicts the last half hour           15:30 -> 16:00
          im_60            same, first hour / last hour                                          sign(prev 16:00 -> 10:30) -> 15:00 -> 16:00
          im_rth30         same, RTH-only first half hour (no overnight)                         sign(09:30 -> 10:00) -> 15:30 -> 16:00
          im_mag           textbook, only big first-half-hour moves (|r| >= median of the       (magnitude instead of sign only)
                           previous 60 sessions)
          im_vix           textbook, only when yesterday's VIX >= its 1-year median (GHLZ:       (VIX filter)
                           stronger in high-volatility times)
  ON      on_1600          overnight drift (Cliff, Cooper, Gulen 2008; Kelly & Clark 2011;      long 16:00 -> 09:30 next day
                           Lou, Polk, Skouras 2019): the index earns its return overnight
          on_1800          same, from the 18:00 Globex reopen                                   long 18:00 -> 09:30
          id_rth           the other half: the regular session                                   long 09:30 -> 16:00
          on_after_down    overnight after a down day (close < previous close)                   long 16:00 -> 09:30
          on_mon..on_fri   overnight by the weekday of the morning it ends                        long 16:00 -> 09:30
  CAL     tom              turn of the month (Ariel 1987; Lakonishok & Smidt 1988; McConnell &    long 16:00 day -2 -> 16:00 day +3
                           Xu 2008): last trading day + first 3
          tom_1            last day + first day only                                              long 16:00 day -2 -> 16:00 day +1
          pre_fomc         pre-FOMC drift (Lucca & Moench 2015, JF): the 24 h before the          long 14:00 day before -> 13:55
                           14:00 ET statement
          pre_fomc_rth     the FOMC morning only                                                  long 09:30 -> 13:55
          pre_holiday      pre-holiday effect (Ariel 1990; Lakonishok & Smidt 1988)              long the last session before a holiday
  DAY     rev1/rev2/rev5   short-term reversal at the daily horizon (Lehmann 1990; Jegadeesh     -sign(last k close-to-close returns),
                           1990; index version: daily autocorrelation). Negative = momentum.    hold 16:00 -> 16:00
          gap_fill         gap fill at the 09:30 open: fade gaps >= 0.1 ATR, target the         fade at 09:30, target prev close,
                           previous 16:00 close                                                   flat 16:00
          gap_go           gap-and-go: the same gaps, with the gap                                with the gap 09:30 -> 16:00
          gap_fill_small   fade only small gaps (0.1-0.3 ATR)                                     as gap_fill
  VIX     bh_cc            buy and hold NQ (reference, day by day)                                long 16:00 -> 16:00
          vreg_level       VIX level regime (Whaley 2000 and the long/flat vol-regime papers):   long when yesterday's VIX < its 1-year
                                                                                                  median, else flat
          vreg_ts          VIX term structure (Simon & Campasano 2014; contango = calm):         long when VIX/VIX3M < 1 (VIX/20-day
                                                                                                  mean where VIX3M is missing)
          vreg_ts20        the proxy only: VIX below its 20-day mean                             long, else flat
  EOD     eod_textbook     Baltussen, Da, Lammers, Martens 2021 (JFE) "Hedging demand and        sign(prev 16:00 -> 15:30) ->
                           market intraday momentum": the day's move predicts the last 30 min   15:30 -> 16:00
          eod_hour         last-hour momentum from the RTH open                                   sign(09:30 -> 15:00) -> 15:00 -> 16:00
          eod_big          textbook, only big moves (|r| >= 60-session median)
  VT      vt_rv/vt_vxn/    volatility-targeted size (Moreira & Muir 2017, "Volatility-managed     size multiplier on LIT's and ATLAS's
          vt_rv_down/vt_ts portfolios"; Harvey et al. 2018): size ~ target vol / recent vol        own trades (sizing change only)

Execution (quant overlays, NOT LIT setups): MNQ micros ($2 a point), entry and exit at 5m bar OPENS, $1.90 a micro round
turn + 1 tick slippage each side. Two P&L views:
  unlevered   1 micro per signal, no stop (the clean test of the effect; t-stats and placebos use this, costs in)
  $500 risk   a volatility stop: max(10, 1.5 x ATR20 x sqrt(hold hours / 23)) points (ATR20 = mean 18:00-17:00 range of the
              20 sessions before), micros = $500 / (stop x $2), 1-40. This is a fixed-rule, non-structural stop: CLAUDE.md's
              "stop beyond the sweep extreme" rule is for LIT setups; these trades have no sweep, so the stop is a
              volatility stop (hit on 0-1% of the calendar trades, ~5% of the overnight / daily holds, 11-18% of
              the intraday windows). Holds of a day or more get the 1-micro minimum (their stop is $800+ a micro).
LIT / ATLAS overlays (sizing only, no rule change): vol-target multipliers vt_* and pre-declared bias tilts tilt_on /
tilt_vix / tilt_fomc on run lit_live (LIT size rule), on the live two_week eval path (units of lit_adopt_t15_be_off_eval,
tools/lit_big_ideas.run_eval_x; base = 57.1/5.9, 52.2/0.0) and on ATLAS's Builder 25K need path
(tools/second_account_b.py; base = H1 68.9, H2 43.5); plus a separate quant slot (fixed $250 risk on the 50K, $125 on
the 25K) for the in-sample leads (placebo p < 0.05) and on_1800.
Spans: 2021-24 (in sample, where the papers say it should exist; data start 2021-11), 2025, 2026 H1, 2026 H2 (out of
sample), every year. Placebos (1000 draws, in sample and all): random direction (signal anomalies), random dates from the
same window (calendar anomalies), random start time of the same length (every-day windows), circular shift of the regime
(VIX). Family-wise: Holm over every counted variant's in-sample placebo p.

    python -X utf8 tools/quant_anoms.py          # all -> research/quant/quant_anoms.json (+ a table)
    python -X utf8 tools/quant_anoms.py save     # + rl.save runs q_* (one per anomaly variant + the vol-target runs)
Research only: edits no engine / model / UI file, arms nothing.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import pickle
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, "research", "quant")
OUT = os.path.join(OUT_DIR, "quant_anoms.json")
PV, COMM, SLIP = 2.0, 1.90, 0.25            # MNQ $ a point, $ a micro round turn, 1 tick each side
RISK_USD, MAXQ = 500.0, 40
NPLAC = 1000
SPANS = {"2021-24": ("2021-01-01", "2024-12-31"), "2025": ("2025-01-01", "2025-12-31"), "2026H1": ("2026-01-01", "2026-06-30"),
         "2026H2": ("2026-07-01", "2026-12-31"), "OOS": ("2025-01-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31"),
         "2021-25": ("2021-01-01", "2025-12-31"), "all": ("2000-01-01", "2100-01-01")}

# FOMC statement days 2021-2026 (all 14:00 ET; written from memory, checked against data/news/events.csv below)
FOMC = ["2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
        "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
        "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
        "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
# NYSE full-day holidays in the data window (from memory; checked against the bars: no 15:55 bar on these sessions)
HOLIDAYS = ["2021-11-25", "2021-12-24", "2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20", "2022-07-04",
            "2022-09-05", "2022-11-24", "2022-12-26", "2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29",
            "2023-06-19", "2023-07-04", "2023-09-04", "2023-11-23", "2023-12-25", "2024-01-01", "2024-01-15", "2024-02-19",
            "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25", "2025-01-01",
            "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
            "2025-11-27", "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
            "2026-07-03", "2026-09-07"]


# ------------------------------------------------------------------------------------------------ data
class Bars:
    def __init__(self, sym="NQ", until=None):
        d = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_5m.csv"))
        if until:
            d = d[d.time < until].reset_index(drop=True)
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        self.t = d.time.to_numpy(np.int64)
        self.o, self.h, self.l, self.c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        cal = et.dt.date
        sess = np.where(hm >= 18 * 60, (et + pd.Timedelta(days=1)).dt.date, cal)
        self.hm = hm
        self.sess = np.array([str(x) for x in sess])
        rolls = json.load(open(os.path.join(ROOT, "data", f"{sym}_rolls.json"), encoding="utf-8"))["rolls"]
        adj = np.zeros(len(self.t))
        for r in rolls:
            adj += np.where(self.t < int(r["switch_t"]), float(r["gap"]), 0.0)
        self.unadj = self.c - adj                     # adjusted - the gaps of the rolls after the bar
        self.ix = {(s, int(m)): i for i, (s, m) in enumerate(zip(self.sess, hm))}
        order = list(dict.fromkeys(self.sess))
        self.all_sess = order
        self.pos = {s: k for k, s in enumerate(order)}
        # full sessions: 09:30 and the 16:00 bar exist (early closes and holidays drop out of 16:00-based trades)
        self.full = [s for s in order if (s, 570) in self.ix and (s, 960) in self.ix and (s, 955) in self.ix]
        # session range for ATR (18:00 -> 17:00)
        first = {}
        last = {}
        for i, s in enumerate(self.sess):
            first.setdefault(s, i); last[s] = i
        self.first, self.last = first, last
        rng = {s: float(self.h[first[s]:last[s] + 1].max() - self.l[first[s]:last[s] + 1].min()) for s in order}
        self.atr = {}
        R = [rng[s] for s in order]
        for k, s in enumerate(order):
            w = [x for x in R[max(0, k - 20):k]]
            self.atr[s] = float(np.mean(w)) if len(w) >= 10 else None

    def i(self, s, hm):
        return self.ix.get((s, hm))

    def px(self, s, hm):
        k = self.ix.get((s, hm))
        return None if k is None else float(self.o[k])

    def upx(self, s, hm):
        """Unadjusted open price (for % returns)."""
        k = self.ix.get((s, hm))
        return None if k is None else float(self.o[k] - (self.c[k] - self.unadj[k]))


def load_vol():
    def rd(name, col="close"):
        d = pd.read_csv(os.path.join(ROOT, "data", name))
        d = d[d[col] > 0]
        return dict(zip(d["date"].astype(str), d[col].astype(float)))
    vix, vxn = rd("VIX_1d.csv"), rd("VXN_1d.csv")
    cb = pd.read_csv(os.path.join(ROOT, "data", "CBOE_vol_1d.csv"))
    cb = cb[cb["vix3m"] > 0]
    v3 = dict(zip(cb["date"].astype(str), cb["vix3m"].astype(float)))
    return vix, vxn, v3


def prev_val(series, day, dates_sorted):
    """The last value strictly before `day` (known at that session's open)."""
    import bisect
    k = bisect.bisect_left(dates_sorted, day) - 1
    return (dates_sorted[k], series[dates_sorted[k]]) if k >= 0 else (None, None)


# ------------------------------------------------------------------------------------------------ execution
def stop_pts(B, s, hold_h):
    a = B.atr.get(s)
    if a is None:
        return None
    return max(10.0, round(4 * 1.5 * a * math.sqrt(hold_h / 23.0)) / 4)


def execute(B, i0, i1, d, stop=None, tgt=None):
    """Enter at the open of bar i0, exit at the open of bar i1 (time exit), unless the stop / target is touched in bars
    i0..i1-1 (stop first when both are in one bar; a bar that opens beyond the level fills at its open).
    Returns (gross pts, exit kind, exit bar, worst open pts)."""
    e = B.o[i0]
    sp = None if stop is None else e - d * stop
    tp = None if tgt is None else tgt
    if sp is None and tp is None:
        seg_l, seg_h = B.l[i0:i1], B.h[i0:i1]
        worst = (seg_l.min() - e) if d == 1 else (e - seg_h.max())
        return d * (B.o[i1] - e), "TIME", i1, min(0.0, float(worst))
    worst = 0.0
    for k in range(i0, i1):
        o, h, l = B.o[k], B.h[k], B.l[k]
        if sp is not None:
            if (d == 1 and o <= sp) or (d == -1 and o >= sp):
                return d * (o - e), "STOP", k, min(worst, d * (o - e))
            if (d == 1 and l <= sp) or (d == -1 and h >= sp):
                return d * (sp - e), "STOP", k, min(worst, d * (sp - e))
        if tp is not None:
            if (d == 1 and o >= tp) or (d == -1 and o <= tp):
                return d * (o - e), "TGT", k, worst
            if (d == 1 and h >= tp) or (d == -1 and l <= tp):
                return d * (tp - e), "TGT", k, min(worst, (l - e) if d == 1 else (e - h))
        worst = min(worst, (l - e) if d == 1 else (e - h))
    return d * (B.o[i1] - e), "TIME", i1, worst


def make_trade(B, var, s_entry, hm0, s_exit, hm1, d, hold_h, tgt=None, extra=None):
    i0, i1 = B.i(s_entry, hm0), B.i(s_exit, hm1)
    if i0 is None or i1 is None or i1 <= i0 or d == 0:
        return None
    st = stop_pts(B, s_entry, hold_h)
    if st is None:
        return None
    g_un, _, _, _ = execute(B, i0, i1, d, None, tgt)          # unlevered: no stop
    g_mi, _, _, _ = execute(B, i0, i1, -d, None, None if tgt is None else 2 * B.o[i0] - tgt)  # mirror (placebo)
    g, kind, kx, worst = execute(B, i0, i1, d, st, tgt)
    q = int(max(1, min(MAXQ, RISK_USD // (st * PV))))
    net_pts = g - 2 * SLIP
    pnl = float(q * (net_pts * PV - COMM))
    low = float(min(0.0, q * ((worst - SLIP) * PV - COMM), pnl))
    t = {"var": var, "day": s_exit, "entry_t": int(B.t[i0]), "exit_t": int(B.t[kx]) if kind != "TIME" else int(B.t[i1]),
         "dir": int(d), "g_un": float(g_un), "g_mirror": float(g_mi), "un_usd": round((g_un - 2 * SLIP) * PV - COMM, 2),
         "pnl": round(pnl, 2), "low": round(low, 2), "qty": q, "risk_pts": st, "risk_usd": round(st * PV * q, 2),
         "exit": kind, "hold_h": hold_h, "r": round(pnl / (st * PV * q), 3)}
    if extra:
        t.update(extra)
    return t


# ------------------------------------------------------------------------------------------------ the anomalies
def day_table(B):
    """Per full session: the prices the rules need (adjusted opens; % from unadjusted)."""
    F = B.full
    rows = []
    for k, s in enumerate(F):
        r = {"s": s, "prev": F[k - 1] if k else None, "next": F[k + 1] if k + 1 < len(F) else None}
        for hm in (570, 600, 630, 900, 930, 960):
            r[hm] = B.px(s, hm)
            r["u%d" % hm] = B.upx(s, hm)
        rows.append(r)
    by = {r["s"]: r for r in rows}
    for r in rows:
        p = by.get(r["prev"]) if r["prev"] else None
        # the previous full session must be the calendar-previous session (else the "previous close" is stale)
        r["pc"] = p[960] if p else None
        r["upc"] = p["u960"] if p else None
    return rows, by


def rolling_median_prev(vals, n):
    out = []
    for k in range(len(vals)):
        w = [abs(x) for x in vals[max(0, k - n):k] if x is not None]
        out.append(float(np.median(w)) if len(w) >= n // 2 else None)
    return out


def build(B, vol):
    vix, vxn, v3 = vol
    vd = sorted(vix)
    rows, by = day_table(B)
    T = collections.defaultdict(list)
    pool = collections.defaultdict(list)     # placebo pools (random-date / random-subset)
    sgn = lambda x: 0 if x is None or x == 0 else (1 if x > 0 else -1)

    def add(var, t, pl=None):
        if t is not None:
            T[var].append(t)

    # VIX 1-year median (prior days) for im_vix / vreg_level
    vix_med = {}
    vv = [vix[d] for d in vd]
    for k, d in enumerate(vd):
        w = vv[max(0, k - 252):k]
        vix_med[d] = float(np.median(w)) if len(w) >= 120 else None
    vix_m20 = {d: (float(np.mean(vv[max(0, k - 20):k])) if k >= 20 else None) for k, d in enumerate(vd)}

    # ---- IM + EOD (signals)
    r1 = [((r["u600"] / r["upc"] - 1) if r["upc"] and r["u600"] else None) for r in rows]
    med1 = rolling_median_prev(r1, 60)
    re = [((r["u930"] / r["upc"] - 1) if r["upc"] and r["u930"] else None) for r in rows]
    mede = rolling_median_prev(re, 60)
    for k, r in enumerate(rows):
        s = r["s"]
        if r["pc"] is None:
            continue
        d1 = sgn(r1[k])
        _, vprev = prev_val(vix, s, vd)
        dprev, _ = prev_val(vix, s, vd)
        add("im_textbook", make_trade(B, "im_textbook", s, 930, s, 960, d1, 0.5))
        if r["u630"]:
            add("im_60", make_trade(B, "im_60", s, 900, s, 960, sgn(r["u630"] / r["upc"] - 1), 1.0))
        if r["u570"] and r["u600"]:
            add("im_rth30", make_trade(B, "im_rth30", s, 930, s, 960, sgn(r["u600"] / r["u570"] - 1), 0.5))
        if med1[k] is not None and r1[k] is not None and abs(r1[k]) >= med1[k]:
            add("im_mag", make_trade(B, "im_mag", s, 930, s, 960, d1, 0.5))
        if dprev and vix_med.get(dprev) and vprev >= vix_med[dprev]:
            add("im_vix", make_trade(B, "im_vix", s, 930, s, 960, d1, 0.5))
        add("eod_textbook", make_trade(B, "eod_textbook", s, 930, s, 960, sgn(re[k]), 0.5))
        if r["u570"] and r["u900"]:
            add("eod_hour", make_trade(B, "eod_hour", s, 900, s, 960, sgn(r["u900"] / r["u570"] - 1), 1.0))
        if mede[k] is not None and re[k] is not None and abs(re[k]) >= mede[k]:
            add("eod_big", make_trade(B, "eod_big", s, 930, s, 960, sgn(re[k]), 0.5))

    # ---- ON (always long windows)
    WD = ["on_mon", "on_tue", "on_wed", "on_thu", "on_fri"]
    for r in rows:
        s, n = r["s"], r["next"]
        if n is None:
            continue
        # the next full session must be the next Globex session (holiday / early close in between -> skip the night)
        if B.pos.get(n) != B.pos.get(s) + 1:
            continue
        t = make_trade(B, "on_1600", s, 960, n, 570, 1, 17.5)
        add("on_1600", t)
        if t is not None:
            w = dt.date.fromisoformat(n).weekday()
            if w < 5:
                T[WD[w]].append({**t, "var": WD[w]})
            if r["pc"] is not None and r[960] < r["pc"]:
                T["on_after_down"].append({**t, "var": "on_after_down"})
        add("on_1800", make_trade(B, "on_1800", n, 1080, n, 570, 1, 15.5))
    for r in rows:
        add("id_rth", make_trade(B, "id_rth", r["s"], 570, r["s"], 960, 1, 6.5))

    # ---- CAL
    F = B.full
    months = collections.defaultdict(list)
    for s in F:
        months[s[:7]].append(s)
    mk = sorted(months)
    tom_starts = []
    for a, b in zip(mk, mk[1:]):
        A, Bm = months[a], months[b]
        if len(A) < 2 or len(Bm) < 3:
            continue
        tom_starts.append((A[-2], Bm[2], Bm[0]))
        add("tom", make_trade(B, "tom", A[-2], 960, Bm[2], 960, 1, 4 * 23.0))
        add("tom_1", make_trade(B, "tom_1", A[-2], 960, Bm[0], 960, 1, 2 * 23.0))
    fset = set(FOMC)
    for s in F:
        if s in fset:
            k = B.pos.get(s)
            p = B.all_sess[k - 1] if k else None
            if p:
                add("pre_fomc", make_trade(B, "pre_fomc", p, 840, s, 835, 1, 23.9))
            add("pre_fomc_rth", make_trade(B, "pre_fomc_rth", s, 570, s, 835, 1, 4.4))
    hol = sorted(HOLIDAYS)
    import bisect
    for h in hol:
        k = bisect.bisect_left(F, h) - 1
        if k < 1:
            continue
        pre, pp = F[k], F[k - 1]
        if (dt.date.fromisoformat(h) - dt.date.fromisoformat(pre)).days > 4:
            continue
        add("pre_holiday", make_trade(B, "pre_holiday", pp, 960, pre, 960, 1, 23.0))

    # ---- DAY: reversal + gaps
    cc = [((r["u960"] / r["upc"] - 1) if r["upc"] and r["u960"] else None) for r in rows]
    for k, r in enumerate(rows):
        s, n = r["s"], r["next"]
        if n is None or B.pos.get(n) != B.pos.get(s) + 1:
            continue
        for K in (1, 2, 5):
            w = cc[max(0, k - K + 1):k + 1]
            if len(w) < K or any(x is None for x in w):
                continue
            add(f"rev{K}", make_trade(B, f"rev{K}", s, 960, n, 960, -sgn(sum(w)), 23.0))
    for r in rows:
        s = r["s"]
        a = B.atr.get(s)
        if r["pc"] is None or a is None or r[570] is None:
            continue
        gap = r[570] - r["pc"]
        g = abs(gap) / a
        if g < 0.1:
            continue
        d = -sgn(gap)
        add("gap_fill", make_trade(B, "gap_fill", s, 570, s, 960, d, 6.5, tgt=r["pc"]))
        add("gap_go", make_trade(B, "gap_go", s, 570, s, 960, -d, 6.5))
        if g < 0.3:
            add("gap_fill_small", make_trade(B, "gap_fill_small", s, 570, s, 960, d, 6.5, tgt=r["pc"]))

    # ---- VIX regimes on the day-by-day hold (16:00 -> next 16:00); the signal is the VIX close of the day BEFORE the
    # entry day (VIX settles 16:15, after the 16:00 entry)
    v3d = sorted(v3)
    for r in rows:
        s, n = r["s"], r["next"]
        if n is None or B.pos.get(n) != B.pos.get(s) + 1:
            continue
        t = make_trade(B, "bh_cc", s, 960, n, 960, 1, 23.0)
        if t is None:
            continue
        dprev, vp = prev_val(vix, s, vd)
        if dprev is None:
            continue
        T["bh_cc"].append(t)
        lv = vix_med.get(dprev)
        m20 = vix_m20.get(dprev)
        t3 = v3.get(dprev)
        ts = (vp / t3) if t3 else ((vp / m20) if m20 else None)
        flags = {"vreg_level": lv is not None and vp < lv, "vreg_ts": ts is not None and ts < 1.0,
                 "vreg_ts20": m20 is not None and vp < m20}
        t["_reg"] = flags
        for v, on in flags.items():
            if on:
                T[v].append({**t, "var": v})
    return T, rows, tom_starts


FAMILY = {"IM": ["im_textbook", "im_60", "im_rth30", "im_mag", "im_vix"],
          "ON": ["on_1600", "on_1800", "id_rth", "on_after_down", "on_mon", "on_tue", "on_wed", "on_thu", "on_fri"],
          "CAL": ["tom", "tom_1", "pre_fomc", "pre_fomc_rth", "pre_holiday"],
          "DAY": ["rev1", "rev2", "rev5", "gap_fill", "gap_go", "gap_fill_small"],
          "VIX": ["bh_cc", "vreg_level", "vreg_ts", "vreg_ts20"],
          "EOD": ["eod_textbook", "eod_hour", "eod_big"]}
PLACEBO = {**{v: "sign" for v in FAMILY["IM"] + FAMILY["EOD"] + ["rev1", "rev2", "rev5", "gap_fill", "gap_go", "gap_fill_small"]},
           "on_1600": "start", "on_1800": "start", "id_rth": "start", "bh_cc": "start",
           **{v: "subset:on_1600" for v in ["on_after_down", "on_mon", "on_tue", "on_wed", "on_thu", "on_fri"]},
           "tom": "dates", "tom_1": "dates", "pre_fomc": "dates", "pre_fomc_rth": "dates", "pre_holiday": "dates",
           "vreg_level": "shift", "vreg_ts": "shift", "vreg_ts20": "shift"}
TEXTBOOK = {"im_textbook", "on_1600", "tom", "pre_fomc", "pre_holiday", "rev1", "gap_fill", "vreg_ts", "eod_textbook"}


# ------------------------------------------------------------------------------------------------ scoring
def in_span(day, span):
    a, z = SPANS[span]
    return a <= day <= z


def stats(TT, sess):
    n = len(TT)
    nw = max(len(sess) / 5.0, 1e-9)
    if not n:
        return {"n": 0, "tpw": 0.0}
    un = np.array([t["g_un"] - 2 * SLIP - COMM / PV for t in TT])       # net points a micro, unlevered
    p = np.array([t["pnl"] for t in TT])
    sd = float(un.std(ddof=1)) if n > 1 else 0.0
    tstat = float(un.mean() / sd * math.sqrt(n)) if sd else 0.0
    daily = collections.defaultdict(float)
    for t in TT:
        daily[t["day"]] += t["pnl"]
    dser = np.array([daily.get(s, 0.0) for s in sess])
    sh = float(dser.mean() / dser.std(ddof=1) * math.sqrt(252)) if dser.std() > 0 else 0.0
    eq = np.cumsum(dser)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(eq) else 0.0
    gl = -p[p < 0].sum()
    return {"n": n, "tpw": round(n / nw, 2), "avg_pts": round(float(un.mean()), 2), "t": round(tstat, 2),
            "win": round(100.0 * float((un > 0).mean()), 1), "un_net": round(float(un.sum() * PV)),
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(sess) / 21.0)), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "sharpe": round(sh, 2), "dd": round(dd), "stops": sum(1 for t in TT if t["exit"] == "STOP"),
            "med_qty": float(np.median([t["qty"] for t in TT])), "med_stop": float(np.median([t["risk_pts"] for t in TT]))}


def placebo(var, T, B, rng, span, kind):
    """One-sided placebo p (share of placebo means >= the real mean, gross points a micro) on the span."""
    TT = [t for t in T[var] if in_span(t["day"], span)]
    if len(TT) < 5:
        return None
    real = float(np.mean([t["g_un"] for t in TT]))
    if kind == "sign":
        g = np.array([t["g_un"] for t in TT]); m = np.array([t["g_mirror"] for t in TT])
        d = np.array([t["dir"] for t in TT])
        n = len(TT); nl = int((d == 1).sum())
        # pairs: outcome if long / if short for each trade
        gl_ = np.where(d == 1, g, m); gs_ = np.where(d == 1, m, g)
        res = np.empty(NPLAC)
        for k in range(NPLAC):
            pick = np.zeros(n, bool); pick[rng.choice(n, nl, replace=False)] = True
            res[k] = np.where(pick, gl_, gs_).mean()
    elif kind.startswith("subset:"):
        P = np.array([t["g_un"] for t in T[kind[7:]] if in_span(t["day"], span)])
        res = np.array([rng.choice(P, len(TT), replace=False).mean() for _ in range(NPLAC)])
    elif kind == "dates":
        P = date_pool(var, B, span)
        res = np.array([rng.choice(P, len(TT), replace=len(P) < len(TT)).mean() for _ in range(NPLAC)])
    elif kind == "start":
        nb = int(np.median([(t["exit_t"] - t["entry_t"]) for t in TT]) // 300)
        a, z = SPANS[span]
        ok = np.where((B.sess >= a) & (B.sess <= z))[0]
        ok = ok[ok + nb < len(B.o)]
        # a window of nb bars (5m) starting at a random bar: the same clock length, any time of day
        res = np.empty(NPLAC)
        for k in range(NPLAC):
            j = rng.choice(ok, len(TT))
            res[k] = (B.o[j + nb] - B.o[j]).mean()
    elif kind == "shift":
        base = [t for t in T["bh_cc"] if in_span(t["day"], span)]
        g = np.array([t["g_un"] for t in base]); mask = np.array([t["_reg"][var] for t in base])
        L = len(base)
        res = np.array([g[np.roll(mask, int(rng.integers(20, L - 20)))].mean() for _ in range(NPLAC)])
        real = float(g[mask].mean())
    else:
        return None
    return round(float((res >= real).mean()), 4)


_POOL = {}


def date_pool(var, B, span):
    """Every session's outcome of the same clock window (the random-date placebo for calendar anomalies)."""
    key = (var, span)
    if key in _POOL:
        return _POOL[key]
    F = [s for s in B.full if in_span(s, span)]
    out = []
    for k, s in enumerate(F):
        if var == "tom" and k + 4 < len(F):
            a, b = B.i(s, 960), B.i(F[k + 4], 960)
        elif var == "tom_1" and k + 2 < len(F):
            a, b = B.i(s, 960), B.i(F[k + 2], 960)
        elif var == "pre_fomc":
            j = B.pos.get(s)
            a, b = (B.i(B.all_sess[j - 1], 840) if j else None), B.i(s, 835)
        elif var == "pre_fomc_rth":
            a, b = B.i(s, 570), B.i(s, 835)
        elif var == "pre_holiday" and k:
            a, b = B.i(F[k - 1], 960), B.i(s, 960)
        else:
            continue
        if a is not None and b is not None and b > a:
            out.append(float(B.o[b] - B.o[a]))
    _POOL[key] = np.array(out)
    return _POOL[key]


def holm(pvals, alpha=0.05):
    items = sorted((p, v) for v, p in pvals.items() if p is not None)
    m = len(items)
    surv = {}
    stop = False
    for k, (p, v) in enumerate(items):
        thr = alpha / (m - k)
        if not stop and p <= thr:
            surv[v] = True
        else:
            stop = True
            surv[v] = False
    return surv, m


def verdict(o):
    a, b = o["spans"]["2021-24"], o["spans"]["OOS"]
    p = o["placebo"].get("2021-24")
    is_ok = a.get("n", 0) >= 5 and p is not None and p < 0.05 and a["avg_pts"] > 0
    oos_ok = b.get("n", 0) >= 5 and b["avg_pts"] > 0 and b["t"] >= 1.0
    if is_ok and oos_ok:
        return "exists"
    if is_ok or oos_ok or (p is not None and p < 0.10 and a["avg_pts"] > 0):
        return "weak"
    return "dead"


# ------------------------------------------------------------------------------------------------ overlays: LIT / ATLAS
def lit_daily():
    from tools import runlib as rl
    r = rl.load("lit_live")
    return {d[0]: d[1] for d in r["days"]}


def corr_with_lit(T, var, litd, span):
    days = [d for d in sorted(litd) if in_span(d, span)]
    q = collections.defaultdict(float)
    for t in T[var]:
        q[t["day"]] += t["pnl"]
    x = np.array([litd[d] for d in days]); y = np.array([q.get(d, 0.0) for d in days])
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)


def vt_mults(B, vol, rows):
    """Size multipliers by session (known before the session): pre-declared, no tuning.
      vt_rv       clip(1-year median of rv20 / rv20, 0.5, 1.5); rv20 = stdev of the last 20 close-to-close % returns
      vt_vxn      clip(1-year median VXN / yesterday's VXN, 0.5, 1.5)
      vt_rv_down  vt_rv capped at 1.0 (only ever smaller)
      vt_ts       0.5 when VIX/VIX3M >= 1 (backwardation; VIX/20-day mean where VIX3M is missing), else 1.0"""
    vix, vxn, v3 = vol
    vd, nd = sorted(vix), sorted(vxn)
    cc = {}
    for r in rows:
        if r["upc"] and r["u960"]:
            cc[r["s"]] = r["u960"] / r["upc"] - 1
    sess = B.all_sess
    ccs = [cc.get(s) for s in sess]
    rv = {}
    for k, s in enumerate(sess):
        w = [x for x in ccs[max(0, k - 30):k] if x is not None][-20:]
        rv[s] = float(np.std(w, ddof=1)) if len(w) >= 15 else None
    rvl = [rv[s] for s in sess]
    vxl = {d: k for k, d in enumerate(nd)}
    nv = [vxn[d] for d in nd]
    vv = [vix[d] for d in vd]
    M = {}
    for k, s in enumerate(sess):
        w = [x for x in rvl[max(0, k - 252):k] if x is not None]
        m_rv = (float(np.clip(np.median(w) / rv[s], 0.5, 1.5)) if rv[s] and len(w) >= 120 else 1.0)
        dp, vp = prev_val(vxn, s, nd)
        if dp is not None:
            j = vxl[dp]; ww = nv[max(0, j - 252):j]
            m_vx = float(np.clip(np.median(ww) / vp, 0.5, 1.5)) if len(ww) >= 120 else 1.0
        else:
            m_vx = 1.0
        dv, xv = prev_val(vix, s, vd)
        ts = None
        if dv is not None:
            j = vd.index(dv)
            t3 = v3.get(dv)
            m20 = float(np.mean(vv[max(0, j - 20):j])) if j >= 20 else None
            ts = (xv / t3) if t3 else ((xv / m20) if m20 else None)
        M[s] = {"vt_rv": m_rv, "vt_vxn": m_vx, "vt_rv_down": min(1.0, m_rv), "vt_ts": 0.5 if (ts is not None and ts >= 1.0) else 1.0}
    return M


def lit_size_rule(mf):
    """run lit_live (the LIT size rule) with a per-trade multiplier mf(t) (None = 1): micros x m (rounded, 1-40), P&L linear
    in micros."""
    from tools import runlib as rl
    r = rl.load("lit_live")
    C = r["trade_cols"]
    T = []
    for row in r["trades"]:
        t = dict(zip(C, row))
        m = mf(t) if mf else 1.0
        q0 = int(t["qty"]) or 1
        q = int(max(1, min(MAXQ, round(q0 * m))))
        f = q / q0
        t.update(pnl=round(t["pnl"] * f, 2), qty=q, risk_usd=round(t["risk_usd"] * f, 2), mult=round(m, 3), low=round(min(0.0, t["pnl"] * f), 2))
        T.append(t)
    sess = [d[0] for d in r["days"]]
    return T, sess


def lit_units():
    """LIT live (t_check + be_off) 2026 trades as eval units (tools/lit_adopt_combo.units), cached."""
    p = os.path.join(ROOT, "research", "runs", "_cache", "quant_lit_units.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    from tools import lit_adopt_combo as LC
    from tools import lit_final as LF
    U = LC.units(LF.run({**LC.LIVE, **LC.V["t15_be_off"]}))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    pickle.dump(U, open(p, "wb"))
    return U


def _run_eval_slot(seq, by, horizon=20, keep=None, cfg=None):
    """tools/lit_big_ideas.run_eval_x + overlay units with a fixed size t['fq'] (a separate quant slot on the same eval:
    same soft daily loss, same trailing floor; the LIT trade keeps its live two_week size). Identical to run_eval_x
    without overlay units."""
    from tools import lit_big_ideas as BI
    from tools import lit_adv_manage as A
    from engine import lit
    from engine import sizing as SZ
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            if t.get("fq"):
                q = qfull = int(t["fq"])
                if st["room"] <= 0:
                    continue
            else:
                m0 = lit.qty_for(t["risk"])
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                               learning=None)["qty"] if m0 else 0
                if q <= 0:
                    continue
                qfull = q
                m = float(t.get("m", 1.0))
                if m < 1.0 - 1e-9:
                    q = max(1, int(q * m + 1e-9))
                elif m > 1.0 + 1e-9:
                    q = max(q, min(int(q * m + 1e-9), BI._cap(t, st)))
            pnl, low, tot = BI.trade_pnl(t, q, qfull, st)
            if cum + low <= -dll:
                pnl = -dll - cum - BI.SLIP * BI.PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * BI.PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


SLOT_USD = 250.0          # the quant slot's risk on the 50K eval (half the $500 study size); the 25K gets half of that


def overlay_units(T, var, src="Q"):
    """An overlay's trades as eval units at a fixed $250-risk size (1-40 micros); pts net of 2 ticks a micro."""
    out = []
    for t in T.get(var, []):
        pts = (t["pnl"] / t["qty"] + COMM) / PV
        fq = int(max(1, min(MAXQ, SLOT_USD // (t["risk_pts"] * PV))))
        w1 = min(0.0, (t["low"] / t["qty"] + COMM) / PV)
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "exit": t["exit"],
                    "risk": float(t["risk_pts"]), "tgt": float(t["risk_pts"]), "pts": round(pts, 4), "w1": round(w1, 4),
                    "legs": [(1.0, round(pts, 4))], "on1": False, "fq": fq, "src": src})
    return out


def lit_eval_path(mf=None, extra=None):
    """The live two_week eval path (run lit_adopt_t15_be_off_eval: 57.1/5.9, 52.2/0.0) with the size multiplier mf(t)
    (cut int(q x m) min 1; up capped by the live caps) and optional overlay units `extra` (fixed size, own slot)."""
    from tools import lit_big_ideas as BI
    from tools import lit_adv_manage as A
    U = [{**u, "m": (mf(u) if mf else 1.0)} for u in lit_units()]
    if extra:
        S = set(A.S26)
        U += [u for u in extra if u["day"] in S]
    old = A.run_eval
    A.run_eval = _run_eval_slot
    try:
        o = BI.short(BI.score(U))
    finally:
        A.run_eval = old
    return {s: {k: o[s].get(k) for k in ("n", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "mc_p10", "mc_f10")} for s in o}


def atlas_path(mf=None, extra=None):
    """ATLAS on its own Builder 25K (tools/second_account_b.py, need size) with the multiplier mf(t) on each
    second-strategy trade (m < 1 -> int(q x m) min 1; m > 1 -> up to the plan's max micros and the soft-daily-loss cap) and
    optional overlay units `extra` (src Q, fixed size = half the 50K slot; they share ATLAS's one-position / 2-a-day rule)."""
    from tools import second_account_b as AB
    from tools import second_mix as SM
    U = SM.acct_units(AB.NAMES, nohedge=True)
    U = [{**u, "m": (mf(u) if mf else 1.0)} for u in U]
    if extra:
        U = U + [{**u, "fq": max(1, u["fq"] // 2)} for u in extra]
    out = {}
    with AB.Plan("builder25k") as pl:
        base_q = SM.second_q

        def tilted(t, st, r):
            if t.get("fq"):
                return int(t["fq"]) if st["room"] > 0 else 0
            q = base_q(t, st, r)
            m = float(t.get("m", 1.0))
            if q <= 0 or abs(m - 1.0) < 1e-9:
                return q
            if m < 1.0:
                return max(1, int(q * m + 1e-9))
            return max(q, min(int(q * m + 1e-9), pl.maxq, SM.dll_cap(t, st)))
        SM.second_q = tilted
        try:
            for s in ("H1", "H2", "2025", "2021-24"):
                o, _ = AB.score(U, "acctb_need", s, pl.safe_rule)
                out[s] = {k: o.get(k) for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "dead10", "p20", "f20", "pass_med")}
        finally:
            SM.second_q = base_q
    return out


def tilt_funcs(T, vol):
    """Pre-declared size tilts from the leads (LIT / ATLAS trade direction x the overlay's bias, known at entry):
      tilt_on    overnight drift: entries before 09:30 ET, longs x1.25, shorts x0.75
      tilt_vix   VIX level regime: yesterday's VIX < its 1-year median -> longs x1.25, shorts x0.75; else x1
      tilt_fomc  pre-FOMC drift: from 14:00 the day before to 13:55 on FOMC day, longs x1.5, shorts x0.5"""
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    vix = vol[0]
    vd = sorted(vix)
    vv = [vix[d] for d in vd]
    med = {}
    for k, d in enumerate(vd):
        w = vv[max(0, k - 252):k]
        med[d] = float(np.median(w)) if len(w) >= 120 else None
    calm = {}

    def is_calm(day):
        if day not in calm:
            dp, vp = prev_val(vix, day, vd)
            calm[day] = bool(dp and med.get(dp) and vp < med[dp])
        return calm[day]
    win = [(t["entry_t"], t["exit_t"]) for t in T.get("pre_fomc", [])]

    def hm(t):
        x = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
        return x.hour * 60 + x.minute
    up = lambda t, a, b: a if int(t["dir"]) == 1 else b
    return {"tilt_on": lambda t: up(t, 1.25, 0.75) if hm(t) < 570 else 1.0,
            "tilt_vix": lambda t: up(t, 1.25, 0.75) if is_calm(t["day"]) else 1.0,
            "tilt_fomc": lambda t: up(t, 1.5, 0.5) if any(a <= int(t["entry_t"]) < b for a, b in win) else 1.0}


def lit_view(T, sess):
    from tools import runlib as rl
    S = rl.score(T, sess)
    o = {}
    H = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31")}
    for k, (a, z) in H.items():
        TT = [t for t in T if a <= t["day"] <= z]
        p = np.array([t["pnl"] for t in TT]); gl = -p[p < 0].sum()
        o[k] = {"n": len(TT), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None}
    for k in ("2026", "2021-25"):
        s = S["spans"][k]
        o[k] = {x: s.get(x) for x in ("n", "net", "per_month", "pf", "dd", "p10", "f10", "p20", "f20")}
    return o, S


# ------------------------------------------------------------------------------------------------ main
def es_check():
    """Textbook IM / ON / EOD / TOM on CME ES (TradingView ES1! 2025-04 -> 2026-08-21; the file is Yahoo after that)."""
    cut = int(dt.datetime(2026, 8, 22, tzinfo=dt.timezone.utc).timestamp())
    E = Bars("ES", until=cut)
    T, _, _ = build(E, load_vol())
    out = {}
    for v in ("im_textbook", "on_1600", "id_rth", "eod_textbook", "tom", "rev1"):
        TT = T.get(v, [])
        g = np.array([t["g_un"] for t in TT])
        out[v] = {"n": len(TT), "avg_pts_gross": round(float(g.mean()), 2) if len(g) else None,
                  "t_gross": round(float(g.mean() / g.std(ddof=1) * math.sqrt(len(g))), 2) if len(g) > 2 else None}
    return out


def main(save=False):
    B = Bars("NQ")
    vol = load_vol()
    # checks: FOMC list vs data/news/events.csv, holidays vs the bars
    ev = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
    ev_f = sorted(set(ev[ev.event.str.contains("FOMC rate decision", case=False)].date.astype(str)))
    fomc_check = {"missing_in_events": [d for d in FOMC if d <= "2026-10-16" and d not in ev_f],
                  "extra_in_events": [d for d in ev_f if "2021-01-01" <= d <= "2026-10-16" and d not in FOMC]}
    hol_check = [h for h in HOLIDAYS if "2021-10-18" <= h <= "2026-10-16" and (h, 955) in B.ix]
    print("FOMC check", fomc_check, "| holidays with a 15:55 bar (should be none):", hol_check, flush=True)
    T, rows, _ = build(B, vol)
    rng = np.random.default_rng(20261023)
    sess_of = {sp: [s for s in B.full if in_span(s, sp)] for sp in SPANS}
    litd = lit_daily()
    res = {}
    for fam, vs in FAMILY.items():
        for v in vs:
            TT = sorted(T.get(v, []), key=lambda t: t["entry_t"])
            o = {"family": fam, "textbook": v in TEXTBOOK, "spans": {}, "years": {}, "placebo": {}}
            for sp in SPANS:
                o["spans"][sp] = stats([t for t in TT if in_span(t["day"], sp)], sess_of[sp])
            for y in sorted({t["day"][:4] for t in TT}):
                ys = [s for s in B.full if s[:4] == y]
                o["years"][y] = {k: o2 for k, o2 in stats([t for t in TT if t["day"][:4] == y], ys).items()
                                 if k in ("n", "avg_pts", "t", "net", "pf", "sharpe")}
            for sp in ("2021-24", "OOS", "all"):
                o["placebo"][sp] = placebo(v, T, B, rng, sp, PLACEBO[v])
            o["corr_lit"] = {k: corr_with_lit(T, v, litd, sp) for k, sp in (("2026", "2026"), ("2021-25", "2021-25"))}
            o["verdict"] = verdict(o)
            res[v] = o
            a, b = o["spans"]["2021-24"], o["spans"]["OOS"]
            print(f"{v:15s} IS n={a['n']:4d} {a.get('avg_pts', 0):+7.2f}pt t={a.get('t', 0):+5.2f} p={o['placebo']['2021-24']} "
                  f"${a.get('net', 0):+8,} | OOS n={b['n']:4d} {b.get('avg_pts', 0):+7.2f}pt t={b.get('t', 0):+5.2f} "
                  f"${b.get('net', 0):+8,} ({b.get('per_month', 0):+,}/mo) | {o['verdict']}", flush=True)
    counted = [v for v in res if v != "bh_cc"]
    surv, m = holm({v: res[v]["placebo"]["2021-24"] for v in counted})
    for v in counted:
        res[v]["holm_is"] = surv.get(v, False)
    fw = {"variants_counted": m, "expected_false_positives_at_5pct": round(0.05 * m, 2),
          "is_p_below_5pct": sorted(v for v in counted if (res[v]["placebo"]["2021-24"] or 1) < 0.05),
          "holm_survivors_is": sorted(v for v in counted if surv.get(v)),
          "exists": sorted(v for v in counted if res[v]["verdict"] == "exists"),
          "weak": sorted(v for v in counted if res[v]["verdict"] == "weak")}
    print("family-wise", fw, flush=True)

    # vol targeting on LIT / ATLAS (sizing only)
    M = vt_mults(B, vol, rows)
    vt = {}
    funcs = {None: None, **{r: (lambda t, r=r: M.get(t["day"], {}).get(r, 1.0)) for r in ("vt_rv", "vt_vxn", "vt_rv_down", "vt_ts")},
             **tilt_funcs(T, vol)}

    def show(k, lv, e, a):
        lr = (f"LIT rule H1 {lv['H1']['net']:+,} PF {lv['H1']['pf']} H2 {lv['H2']['net']:+,} PF {lv['H2']['pf']} 21-25 {lv['2021-25']['net']:+,} | "
              if lv else "")
        print(f"{k:16s} {lr}LIT eval H1 {e['H1']['p10']}/{e['H1']['f10']} {e['H1']['net']:+,} H2 {e['H2']['p10']}/{e['H2']['f10']} {e['H2']['net']:+,} | "
              f"ATLAS25K H1 {a['H1']['p10']}/{a['H1']['dead10']} {a['H1']['net']:+,} H2 {a['H2']['p10']}/{a['H2']['dead10']} {a['H2']['net']:+,} "
              f"2025 {a['2025']['p10']}/{a['2025']['dead10']} 21-24 {a['2021-24']['p10']}/{a['2021-24']['dead10']}", flush=True)
    for rule, mf in funcs.items():
        k = rule or "base"
        T2, sess2 = lit_size_rule(mf)
        lv, S2 = lit_view(T2, sess2)
        vt[k] = {"lit_rule": lv, "lit_eval": lit_eval_path(mf), "atlas_25k": atlas_path(mf)}
        show(k, lv, vt[k]["lit_eval"], vt[k]["atlas_25k"])
        if save and rule:
            vt[k]["_trades"] = (T2, sess2)
    # separate quant slot (fixed $250 risk on the 50K eval, $125 on the 25K) for the in-sample leads (placebo p < 0.05)
    # and the strongest out-of-sample one (on_1800)
    slots = {}
    for v in sorted(set(fw["is_p_below_5pct"]) | {"on_1800"}):
        X = overlay_units(T, v)
        slots[v] = {"lit_eval": lit_eval_path(None, X), "atlas_25k": atlas_path(None, X)}
        show("slot_" + v, None, slots[v]["lit_eval"], slots[v]["atlas_25k"])
    mstats = {r: {"mean": round(float(np.mean([M[s][r] for s in M if s >= "2021-11"])), 3),
                  "2026_mean": round(float(np.mean([M[s][r] for s in M if s >= "2026"])), 3)} for r in ("vt_rv", "vt_vxn", "vt_rv_down", "vt_ts")}
    es = es_check()
    print("ES check", es, flush=True)
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "data": "TradingView CME NQ1!/MNQ1! 5m (data/NQ_5m.csv, back-adjusted)",
           "costs": {"comm_per_micro_rt": COMM, "slip_ticks_each_side": 1, "pv": PV}, "sizing": {"risk_usd": RISK_USD, "stop": "max(10, 1.5 x ATR20 x sqrt(hold_h/23))"},
           "fomc_dates": FOMC, "fomc_check": fomc_check, "holidays": HOLIDAYS, "holiday_check": hol_check,
           "spans": SPANS, "placebo_draws": NPLAC, "family": FAMILY, "placebo_kind": PLACEBO, "anoms": res, "family_wise": fw,
           "vol_target": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in vt.items()},
           "vt_mult_stats": mstats, "slots": slots, "slot_usd": SLOT_USD, "es_check": es}
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    if save:
        store(T, res, vt, B)
    return out


TITLES = {"im_textbook": "Intraday momentum (Gao et al. 2018): first 30 min incl. overnight -> last 30 min",
          "im_60": "Intraday momentum: first hour -> last hour", "im_rth30": "Intraday momentum: RTH first 30 min -> last 30 min",
          "im_mag": "Intraday momentum: big first-30-min moves only", "im_vix": "Intraday momentum: high-VIX days only",
          "on_1600": "Overnight drift: long 16:00 -> 09:30", "on_1800": "Overnight drift: long 18:00 -> 09:30",
          "id_rth": "Regular session: long 09:30 -> 16:00", "on_after_down": "Overnight drift after a down day",
          "on_mon": "Overnight into Monday", "on_tue": "Overnight into Tuesday", "on_wed": "Overnight into Wednesday",
          "on_thu": "Overnight into Thursday", "on_fri": "Overnight into Friday",
          "tom": "Turn of the month: last day + first 3 days", "tom_1": "Turn of the month: last day + first day",
          "pre_fomc": "Pre-FOMC drift (Lucca-Moench 2015): 24 h before the 14:00 statement", "pre_fomc_rth": "Pre-FOMC drift: FOMC morning 09:30 -> 13:55",
          "pre_holiday": "Pre-holiday effect: the session before an exchange holiday",
          "rev1": "Daily reversal (1 day)", "rev2": "Daily reversal (2 days)", "rev5": "Daily reversal (5 days)",
          "gap_fill": "Gap fill at the 09:30 open (target previous close)", "gap_go": "Gap and go at the 09:30 open",
          "gap_fill_small": "Gap fill, small gaps only (0.1-0.3 ATR)", "bh_cc": "Buy and hold NQ, day by day (reference)",
          "vreg_level": "VIX level regime: long when VIX < 1-year median", "vreg_ts": "VIX term structure: long in contango (VIX/VIX3M < 1)",
          "vreg_ts20": "VIX below its 20-day mean: long, else flat",
          "eod_textbook": "End-of-day momentum (Baltussen et al. 2021): day's move -> last 30 min", "eod_hour": "Last-hour momentum from the RTH open",
          "eod_big": "End-of-day momentum, big days only"}


def store(T, res, vt, B):
    from tools import runlib as rl
    real_index = rl.index
    rl.index = lambda: None                        # one index rebuild at the end (each save would re-read ~1,700 runs)
    Q = "Owner 2026-10-23: do the published index-futures anomalies (quant) exist on CME NQ in 2021-26?"
    sess = [s for s in B.full]
    try:
        for v, o in res.items():
            TT = sorted(T.get(v, []), key=lambda t: t["entry_t"])
            rows = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": t["r"], "pnl": t["pnl"],
                     "risk_pts": t["risk_pts"], "qty": t["qty"], "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": v,
                     "mfe": None, "mae": None, "bars_held": int((t["exit_t"] - t["entry_t"]) // 300), "regime": "", "mult": None,
                     "low": t["low"]} for t in TT]
            a, b = o["spans"]["2021-24"], o["spans"]["OOS"]
            f = lambda s, nm: (f"{nm}: n={s['n']} ({s['tpw']}/wk) avg {s.get('avg_pts', 0):+.2f} pts a micro net, t {s.get('t', 0):+.2f}, "
                               f"$500-risk net {s.get('net', 0):+,} (${s.get('per_month', 0):,}/mo), PF {s.get('pf')}, Sharpe {s.get('sharpe')}, DD {s.get('dd', 0):,}")
            status = "promising" if o["verdict"] == "exists" else ("info" if o["verdict"] == "weak" or v == "bh_cc" else "rejected")
            rl.save("q_" + v, "Quant: " + TITLES.get(v, v), "timing" if o["family"] in ("CAL", "ON") else "other", Q,
                    params={"anomaly": v, "family": o["family"], "textbook": o["textbook"]},
                    sizing={"risk_usd": RISK_USD, "stop": "max(10, 1.5 x ATR20 x sqrt(hold_h/23)) pts (volatility catastrophe stop, not structural)",
                            "costs": "$1.90 a micro + 1 tick each side"},
                    trades=rows, scored=rl.score(rows, sess), status=status,
                    verdict=f"{o['verdict'].upper()}. {f(a, '2021-24 (in sample)')}; placebo p {o['placebo']['2021-24']}. {f(b, '2025-26 (out of sample)')}. "
                            f"Holm survivor in sample: {o.get('holm_is')}.",
                    notes="tools/quant_anoms.py: CME NQ 5m bars, entries/exits at bar opens, MNQ micros. Quant overlay, not a LIT setup.",
                    writeup="quant-anomalies", tags=["quant", o["family"]])
        for k, v in vt.items():
            if k == "base" or "_trades" not in v:
                continue
            T2, sess2 = v["_trades"]
            e = v["lit_eval"]
            rl.save("q_" + k + "_lit", ("Quant: LIT with a quant size tilt (" if k.startswith("tilt") else "Quant: LIT with volatility-targeted size (") + k + ")", "risk",
                    "Owner 2026-10-23: does volatility targeting (Moreira-Muir 2017) or a quant bias tilt improve LIT and ATLAS $ and eval odds (sizing only)?",
                    params={"rule": k}, sizing={"base": "run lit_live (LIT size rule)", "mult": k}, trades=T2, scored=rl.score(T2, sess2),
                    status="rejected" if not _vt_better(vt, k) else "promising",
                    verdict=f"LIT size rule H1 {v['lit_rule']['H1']['net']:+,} (PF {v['lit_rule']['H1']['pf']}) / H2 {v['lit_rule']['H2']['net']:+,} "
                            f"(PF {v['lit_rule']['H2']['pf']}) vs lit_live {vt['base']['lit_rule']['H1']['net']:+,} / {vt['base']['lit_rule']['H2']['net']:+,}; "
                            f"eval path two_week 2-week pass/fail H1 {e['H1']['p10']}/{e['H1']['f10']} H2 {e['H2']['p10']}/{e['H2']['f10']} "
                            f"(live 57.1/5.9, 52.2/0.0); ATLAS 25K 2-week pass/dead H1 {v['atlas_25k']['H1']['p10']}/{v['atlas_25k']['H1']['dead10']} "
                            f"H2 {v['atlas_25k']['H2']['p10']}/{v['atlas_25k']['H2']['dead10']}.",
                    notes="tools/quant_anoms.py vt_mults: multiplier known before the session; micros x m, 1-40.",
                    writeup="quant-anomalies", tags=["quant", "VT", "lit"])
    finally:
        rl.index = real_index
    rl.index()


def _vt_better(vt, k):
    b, v = vt["base"], vt[k]
    ok_rule = all((v["lit_rule"][h]["net"] or 0) > (b["lit_rule"][h]["net"] or 0) for h in ("H1", "H2"))
    ok_eval = all(v["lit_eval"][h]["p10"] >= b["lit_eval"][h]["p10"] and v["lit_eval"][h]["f10"] <= b["lit_eval"][h]["f10"] for h in ("H1", "H2"))
    return ok_rule and ok_eval


if __name__ == "__main__":
    main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
