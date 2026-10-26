"""Diversifier search (owner order 2026-10-26: "find more money that holds up"): a strategy UNCORRELATED with LIT, held to
the hard rules (2026 H1 pick / H2 check AND 2021-25, 2-4 trades a week, $ and $/month, MFFU eval speed). Write-up:
research/writeups/diversifier-search.md. Numbers: research/second/div_search.json. Paper research only.

Read first (not redone): quant-anomalies.md (Gao intraday momentum, overnight drift, gaps, EOD, calendar: dead),
atlas-chatgpt-breakouts.md + allday.md + retail-standalone.md (5-30 min ORBs with fixed R targets, inside bars, N-bar
breakouts: no 2026 edge), hq-reversion.md (fades of stretched moves: lose), hq-continuation.md (first pullback in a leg).

Two families nobody here has tested, both TREND / EXPANSION trades (LIT is a sweep REVERSAL, so they should be uncorrelated):

  NA  noise-area intraday momentum (Zarattini, Aziz & Barbon 2024, "Beat the Market: An Effective Intraday Momentum
      Strategy for S&P500 ETF (SPY)", SFI WP 24-97; listed but untested in research/lab/TRADER_HEURISTICS.md). The day's
      "noise area" is the average absolute move from the 09:30 open at the same time of day over the last 14 sessions
      (sigma, in points: the series is back-adjusted additively, so point moves are exact). Upper band = max(open,
      previous 16:00 close) + vm x sigma, lower band = min(open, previous close) - vm x sigma. At the half-hour checks
      (bar closes at HH:00 / HH:30, from `start`) a close above the upper band = long, below the lower band = short, at
      the next 5m open. Trailing stop = max(upper band, VWAP) for a long (min(lower band, VWAP) for a short), ratcheting
      only; flat 15:55. The paper exits on a check-time close beyond the trail; a prop account needs a resting stop, so the
      trail here is a real stop order (moved at every check `upd=check` - the paper's cadence - or every 5m close
      `upd=bar`), filled intrabar with 1 tick slippage. `exit=fixed`: the first stop only, no trail, flat 15:55.
  IB  initial-balance breakout, VXN-normalised (new angle on the ORB family: a 60-minute range, the narrowness measured
      against the volatility the options market prices, and held for the day instead of a fixed R). IB = the 09:30-10:30
      range; implied move = VXN(prev close) / 100 / sqrt(252) x price; ratio = IB / implied move. `narrow`: trade only
      when the ratio is below its own trailing 1-year median (known at 10:30). First 5m close beyond the IB between 10:30
      and `end`; stop = 1 tick beyond the IB middle (`mid`) or the far side (`far`); exit at 15:55 (`eod`), at 2R
      (`r2`), or trailed at VWAP (`vwap`).

Execution: TradingView CME NQ1! 5m (2021-11 -> 2026-10-16, MNQ1! from 2026-08-24; futures only, no Yahoo, no CFD), full
RTH days only (78 bars; early closes skipped). Entry at the next 5m open + 1 tick; a stop touched in a bar fills at the
stop (or the open if it gaps through) - 1 tick; the 2R target is a limit that needs a trade-through; stop and target in one
bar = stop. Costs $1.90 a micro round trip. Size: $500 risk a trade (micros = floor(500 / (stop x $2 + $1.90)), 1-40,
skipped if 0), the stop distance floored at max(10 pts, 0.25 sigma) so a just-crossed band never gives a 2-pt stop.
CLAUDE.md's "stop beyond the sweep extreme" is LIT's rule; these setups have no sweep: the stop is the structure that
defines them (the band / VWAP, the IB), and size follows the stop.

Judging: pick on 2026 H1 (n >= 15, PF >= 1.2, best plateau score = half own H1 $ + half the median H1 $ of the one-step
neighbours); H2, 2025, 2021-24 untouched. The paper default (NA: vm 1, 10:00, check, trail, 1 a day) is reported as the
PRE-REGISTERED line (no pick at all). A pre-2025 re-pick (pick on 2021-24) checks the pick. Placebo: 300 random-entry
twins per run (same days, random half-hour check in the window, the run's side mix, the trade's own stop distance, the
same exit machinery). Correlation with LIT: daily and monthly P&L vs run lit_live.

    python -X utf8 tools/div_search.py grid          # both families -> research/second/div_search.json
    python -X utf8 tools/div_search.py placebo       # random-entry twins for the picks
    python -X utf8 tools/div_search.py save          # rl.save runs div_* (picks + the paper default)
Research only: edits no engine / model / UI file, arms nothing.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "second", "div_search.json")
PV, COMM, TICK = 2.0, 1.90, 0.25
RISK_USD, MAXQ = 500.0, 40
NB = 78                                        # 09:30 .. 15:55 5m bars
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31"), "2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31"),
         "all": ("2000-01-01", "2100-01-01")}


# ================================================================================================ data
class Days:
    """Full RTH sessions as [day, 78] matrices + the prior close, sigma (noise area), VWAP, VXN."""

    def __init__(self):
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
        hm = (et.dt.hour * 60 + et.dt.minute).to_numpy()
        date = et.dt.date.astype(str).to_numpy()
        rth = (hm >= 570) & (hm < 960)
        d = d[rth].reset_index(drop=True)
        hm, date = hm[rth], date[rth]
        days, rows = [], []
        prev_close = {}
        last_close = None
        for day, idx in pd.Series(np.arange(len(d))).groupby(date).groups.items():
            ix = np.array(sorted(idx))
            if len(ix) == NB and hm[ix[0]] == 570 and hm[ix[-1]] == 955:
                days.append(day)
                rows.append(ix)
                prev_close[day] = last_close
            last_close = float(d.close.iloc[ix[-1]])          # early closes count as the previous close too
        self.days = days
        ix = np.array(rows)
        self.t = d.time.to_numpy(np.int64)[ix]
        self.O, self.H, self.L, self.C, self.V = (d[k].to_numpy(float)[ix] for k in ("open", "high", "low", "close", "volume"))
        self.PC = np.array([prev_close[x] if prev_close[x] is not None else np.nan for x in days])
        tp = (self.H + self.L + self.C) / 3.0
        self.VW = np.cumsum(tp * self.V, axis=1) / np.maximum(np.cumsum(self.V, axis=1), 1.0)
        mv = np.abs(self.C - self.O[:, :1])
        self.mv = mv
        self.sig = {}
        for lb in (14, 21):
            s = np.full_like(mv, np.nan)
            for k in range(lb, len(days)):
                s[k] = mv[k - lb:k].mean(axis=0)
            self.sig[lb] = s
        vxn = pd.read_csv(os.path.join(ROOT, "data", "VXN_1d.csv"))
        vxn = vxn[vxn.close > 0]
        vd, vv = vxn.date.astype(str).tolist(), vxn.close.astype(float).tolist()
        import bisect
        self.vxn = np.array([vv[bisect.bisect_left(vd, x) - 1] if bisect.bisect_left(vd, x) > 0 else np.nan for x in days])
        # VXN 1-year median known at the open (the 252 sessions before)
        self.vxn_med = np.array([np.nanmedian(self.vxn[max(0, k - 252):k]) if k >= 60 else np.nan for k in range(len(days))])
        self.pos = {x: k for k, x in enumerate(days)}

    def span(self, name):
        a, z = SPANS[name]
        return [k for k, x in enumerate(self.days) if a <= x <= z]


_D = {}


def D():
    if "d" not in _D:
        _D["d"] = Days()
    return _D["d"]


CHECKS = [j for j in range(NB) if (570 + 5 * j + 5) % 30 == 0]          # bar closes at HH:00 / HH:30 (10:00 = col 5)


def col_of(hhmm_close):
    """Column of the bar that CLOSES at hh:mm."""
    h, m = hhmm_close
    return (h * 60 + m - 5 - 570) // 5


# ================================================================================================ one trade
def walk(B, k, j, d, stop, mode, trail=None, tgt=None, upd="bar"):
    """Enter at the open of column j+1 of day k in direction d with `stop` (price). mode: "fixed" | "trail".
    trail(kk, jj) -> candidate stop level (price) at the close of column jj (None = no move). Exits: stop order, a target
    limit, or 15:55 (open of the last bar). Returns dict with the fill, exit and the path facts (or None)."""
    e0 = j + 1
    if e0 >= NB - 1:
        return None
    O, H, L, C = B.O[k], B.H[k], B.L[k], B.C[k]
    entry = O[e0] + d * TICK
    s = float(stop)
    if (entry - s) * d <= 0:
        return None
    risk = (entry - s) * d
    mfe = mae = 0.0
    ex_px, ex_kind, ex_j = None, None, None
    for jj in range(e0, NB - 1):
        # stop first (a bar that touches both counts as the stop)
        if d == 1 and L[jj] <= s:
            ex_px = min(O[jj], s) - TICK; ex_kind = "STOP"; ex_j = jj
            mae = min(mae, (L[jj] - entry))
            break
        if d == -1 and H[jj] >= s:
            ex_px = max(O[jj], s) + TICK; ex_kind = "STOP"; ex_j = jj
            mae = min(mae, (entry - H[jj]))
            break
        mfe = max(mfe, (H[jj] - entry) if d == 1 else (entry - L[jj]))
        mae = min(mae, (L[jj] - entry) if d == 1 else (entry - H[jj]))
        if tgt is not None and ((d == 1 and H[jj] > tgt) or (d == -1 and L[jj] < tgt)):
            ex_px = tgt; ex_kind = "TARGET"; ex_j = jj
            break
        if mode == "trail" and trail is not None and (upd == "bar" or jj in CHECK_SET):
            c = trail(k, jj)
            if c is not None and (C[jj] - c) * d > 0 and (c - s) * d > 0:
                s = c
    if ex_px is None:
        ex_j = NB - 1
        ex_px = O[NB - 1] - d * TICK
        ex_kind = "EOD"
    pts = (ex_px - entry) * d
    return {"k": k, "j": j, "dir": d, "entry": entry, "stop0": float(stop), "risk": risk, "exit_px": ex_px, "exit": ex_kind,
            "exit_j": ex_j, "pts": pts, "mfe": mfe, "mae": mae}


CHECK_SET = set(CHECKS)


# ================================================================================================ family NA (noise area)
def na_levels(B, k, j, vm, lb):
    sg = B.sig[lb][k, j]
    if not np.isfinite(sg) or not np.isfinite(B.PC[k]):
        return None
    o = B.O[k, 0]
    return max(o, B.PC[k]) + vm * sg, min(o, B.PC[k]) - vm * sg, sg


def na_trail(B, vm, lb, d):
    def f(k, jj):
        lv = na_levels(B, k, jj, vm, lb)
        if lv is None:
            return None
        ub, lo, _ = lv
        return max(ub, B.VW[k, jj]) if d == 1 else min(lo, B.VW[k, jj])
    return f


def run_na(cfg, B=None, days=None):
    B = B or D()
    vm, lb, start, maxn, ex, upd = cfg["vm"], cfg.get("lb", 14), cfg["start"], cfg["maxn"], cfg["exit"], cfg.get("upd", "check")
    vx = cfg.get("vxn")
    last = col_of(cfg.get("last", (15, 0)))
    j0 = col_of(start)
    out = []
    for k in (days if days is not None else range(len(B.days))):
        if vx == "high" and not (np.isfinite(B.vxn_med[k]) and B.vxn[k] >= B.vxn_med[k]):
            continue
        if vx == "low" and not (np.isfinite(B.vxn_med[k]) and B.vxn[k] < B.vxn_med[k]):
            continue
        n, free_at = 0, j0
        for j in CHECKS:
            if j < free_at or j > last or n >= maxn:
                continue
            lv = na_levels(B, k, j, vm, lb)
            if lv is None:
                break
            ub, lo, sg = lv
            c = B.C[k, j]
            d = 1 if c > ub else -1 if c < lo else 0
            if not d:
                continue
            lvl = max(ub, B.VW[k, j]) if d == 1 else min(lo, B.VW[k, j])
            entry = B.O[k, j + 1] + d * TICK
            mn = max(10.0, 0.25 * sg)
            stop = min(lvl, entry - mn) if d == 1 else max(lvl, entry + mn)
            w = walk(B, k, j, d, stop, "trail" if ex == "trail" else "fixed", trail=na_trail(B, vm, lb, d), upd=upd)
            if w is None:
                continue
            w["sig"] = sg
            w["nth"] = n
            w["first_dir"] = out[-n]["dir"] if n else d
            out.append(w)
            n += 1
            free_at = w["exit_j"] + 1
    if cfg.get("only") == "re":                  # added after the first look: the day's 2nd+ break, same side as the 1st
        out = [w for w in out if w["nth"] >= 1 and w["dir"] == w["first_dir"]]
    return out


# ================================================================================================ family IB
def run_ib(cfg, B=None, days=None):
    B = B or D()
    narrow, stopm, ex, end = cfg["narrow"], cfg["stop"], cfg["exit"], col_of(cfg.get("end", (15, 0)))
    j_ib = col_of((10, 30))                     # the 10:25 bar closes at 10:30: IB = cols 0..j_ib
    ratios = []
    out = []
    for k in (days if days is not None else range(len(B.days))):
        hi, lo = B.H[k, :j_ib + 1].max(), B.L[k, :j_ib + 1].min()
        px = B.C[k, j_ib]
        imp = B.vxn[k] / 100.0 / math.sqrt(252) * px if np.isfinite(B.vxn[k]) else np.nan
        r = (hi - lo) / imp if imp and np.isfinite(imp) else np.nan
        hist = [x for x in ratios[-252:] if np.isfinite(x)]
        ratios.append(r)
        if narrow and (len(hist) < 60 or not np.isfinite(r) or r >= float(np.median(hist))):
            continue
        mid = (hi + lo) / 2.0
        for j in range(j_ib + 1, end + 1):
            c, pc = B.C[k, j], B.C[k, j - 1]
            d = 1 if (c > hi and pc <= hi) else -1 if (c < lo and pc >= lo) else 0
            if not d:
                continue
            ref = mid if stopm == "mid" else (lo if d == 1 else hi)
            stop = ref - d * TICK
            entry = B.O[k, j + 1] + d * TICK
            if (entry - stop) * d < 10.0:
                stop = entry - d * 10.0
            tgt = entry + d * 2.0 * abs(entry - stop) if ex == "r2" else None
            trail = (lambda kk, jj, d=d: B.VW[kk, jj]) if ex == "vwap" else None
            w = walk(B, k, j, d, stop, "trail" if ex == "vwap" else "fixed", trail=trail, tgt=tgt, upd="bar")
            if w is not None:
                w["ratio"] = r
                out.append(w)
            break
    return out


# ================================================================================================ money
def size(w, risk_usd=RISK_USD, maxq=MAXQ):
    q = int(risk_usd // (w["risk"] * PV + COMM))
    return min(maxq, q)


def booked(W, risk_usd=RISK_USD, maxq=MAXQ):
    B = D()
    T = []
    for w in W:
        q = size(w, risk_usd, maxq)
        if q < 1:
            continue
        pnl = w["pts"] * PV * q - COMM * q
        ru = w["risk"] * PV * q
        T.append({"day": B.days[w["k"]], "entry_t": int(B.t[w["k"], w["j"] + 1]), "exit_t": int(B.t[w["k"], w["exit_j"]]) + 300,
                  "dir": w["dir"], "r": round(pnl / ru, 3), "pnl": round(pnl, 2), "risk_pts": round(w["risk"], 2), "qty": q,
                  "risk_usd": round(ru, 2), "half": False, "exit": w["exit"], "trigger": "div", "mfe": round(w["mfe"] / w["risk"], 3),
                  "mae": round(-w["mae"] / w["risk"], 3), "bars_held": int(w["exit_j"] - w["j"]), "regime": "", "mult": 1.0,
                  "pts": round(w["pts"], 4), "w1": round(min(0.0, w["mae"]), 4), "low": round(min(0.0, w["mae"] * PV * q - COMM * q, pnl), 2)})
    for t in T:                                    # plain Python numbers (json, runlib month counters)
        for k, v in t.items():
            if isinstance(v, np.floating):
                t[k] = float(v)
            elif isinstance(v, np.integer):
                t[k] = int(v)
    return T


def stats(T, span):
    a, z = SPANS[span]
    B = D()
    nd = sum(1 for x in B.days if a <= x <= z)
    X = [t for t in T if a <= t["day"] <= z]
    if not X or not nd:
        return {"n": 0}
    p = np.array([t["pnl"] for t in X])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]).min())
    wk = collections.Counter()
    for t in X:
        y, w, _ = dt.date.fromisoformat(t["day"]).isocalendar()
        wk[(y, w)] += 1
    weeks = set()
    for x in B.days:
        if a <= x <= z:
            y, w, _ = dt.date.fromisoformat(x).isocalendar()
            weeks.add((y, w))
    return {"n": len(X), "tpw": round(len(X) / max(1, len(weeks)), 2),
            "wk2": round(100.0 * sum(1 for w in weeks if wk[w] >= 2) / max(1, len(weeks)), 1),
            "win": round(100.0 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (nd / 21.0)), "dd": round(dd),
            "avg_r": round(float(np.mean([t["r"] for t in X])), 3), "stop": round(float(np.median([t["risk_pts"] for t in X])), 1),
            "t": round(float(p.mean() / (p.std(ddof=1) / math.sqrt(len(p)))), 2) if len(p) > 2 and p.std() > 0 else None}


def score(T):
    return {s: stats(T, s) for s in ("H1", "H2", "2025", "2021-24", "2026", "2021-25", "all")}


# ================================================================================================ LIT for correlation
def lit_daily():
    r = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    return {d[0]: float(d[1]) for d in r["days"]}


def corr(T, span, lit=None):
    lit = lit or lit_daily()
    a, z = SPANS[span]
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
    days = [d for d in lit if a <= d <= z]
    x = np.array([lit[d] for d in days]); y = np.array([by.get(d, 0.0) for d in days])
    dm = collections.defaultdict(lambda: [0.0, 0.0])
    for d in days:
        dm[d[:7]][0] += lit[d]; dm[d[:7]][1] += by.get(d, 0.0)
    m = np.array(list(dm.values()))
    c = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else None
    cm = float(np.corrcoef(m[:, 0], m[:, 1])[0, 1]) if len(m) > 2 and m[:, 0].std() > 0 and m[:, 1].std() > 0 else None
    # months LIT lost / made nothing: what did the new one make?
    bad = [v[1] for v in dm.values() if v[0] <= 0]
    return {"daily": round(c, 3) if c is not None else None, "monthly": round(cm, 3) if cm is not None else None,
            "lit_bad_months": len(bad), "new_in_lit_bad_months": round(float(np.sum(bad))) if bad else 0}


# ================================================================================================ grids
def vmk(vm):
    return f"{int(round(vm * 100))}" if vm == 1.25 else f"{int(vm * 10)}"


def na_grid(added=True):
    """48 pre-declared (vm 1.0 / 1.5, 1-2 a day); `added` (after the first look, counted): vm 1.25 and the paper's
    unlimited re-entries (maxn 99)."""
    rows = []
    vms, ns = ((1.0, 1.25, 1.5), (1, 2, 99)) if added else ((1.0, 1.5), (1, 2))
    for vm, start, maxn, (ex, upd), vx in itertools.product(vms, ((10, 0), (10, 30)), ns,
                                                           (("trail", "check"), ("trail", "bar"), ("fixed", "check")),
                                                           (None, "high")):
        cid = f"na_vm{vmk(vm)}_{start[0]}{start[1]:02d}_n{maxn}_{ex}{'' if ex == 'fixed' else '_' + upd}{'_vxh' if vx else ''}"
        rows.append((cid, {"fam": "NA", "vm": vm, "start": start, "maxn": maxn, "exit": ex, "upd": upd, "vxn": vx,
                           "added": vm == 1.25 or maxn == 99}))
    return rows


def re_grid():
    """Added after the first look (the 2nd break of the day carried the money in every period): only the day's 2nd+
    noise-band break on the same side as the 1st (which must have been stopped), every vm / start / exit / VXN."""
    rows = []
    for vm, start, (ex, upd), vx in itertools.product((1.0, 1.25, 1.5), ((10, 0), (10, 30)),
                                                     (("trail", "check"), ("trail", "bar"), ("fixed", "check")), (None, "high")):
        cid = f"re_vm{vmk(vm)}_{start[0]}{start[1]:02d}_{ex}{'' if ex == 'fixed' else '_' + upd}{'_vxh' if vx else ''}"
        rows.append((cid, {"fam": "NA", "vm": vm, "start": start, "maxn": 99, "exit": ex, "upd": upd, "vxn": vx, "only": "re",
                           "added": True}))
    return rows


def ib_grid():
    rows = []
    for narrow, stop, ex, end in itertools.product((False, True), ("mid", "far"), ("eod", "r2", "vwap"), ((13, 0), (15, 0))):
        cid = f"ib_{'nar' if narrow else 'all'}_{stop}_{ex}_{end[0]}"
        rows.append((cid, {"fam": "IB", "narrow": narrow, "stop": stop, "exit": ex, "end": end}))
    return rows


PAPER = "na_vm10_1000_n99_trail_check"         # the paper's own rule (vm 1, 10:00, half-hour cadence, trail, re-entries)
PAPER1 = "na_vm10_1000_n1_trail_check"         # the same, first entry of the day only


def run(cfg, days=None):
    return run_na(cfg, days=days) if cfg["fam"] == "NA" else run_ib(cfg, days=days)


def neighbours(cid, grid):
    """One-step neighbours: the configs that differ in exactly one key."""
    G = dict(grid)
    c0 = G[cid]
    out = []
    for k2, c in G.items():
        if k2 == cid:
            continue
        diff = [k for k in c0 if c0.get(k) != c.get(k)]
        if len(diff) == 1:
            out.append(k2)
    return out


def pick(res, grid, span="H1", min_n=15, tpw=(2.0, 4.0)):
    """The strict pick: one span only (H1 2026), n >= min_n, PF >= 1.2, money up, the owner's 2-4 trades a week in that
    span; best plateau score."""
    elig = [cid for cid, _ in grid if res[cid]["S"][span]["n"] >= min_n and (res[cid]["S"][span].get("pf") or 0) >= 1.2
            and res[cid]["S"][span]["net"] > 0 and tpw[0] <= (res[cid]["S"][span].get("tpw") or 0) <= tpw[1]]
    best, bs = None, -1e18
    for cid in elig:
        nb = [res[x]["S"][span]["net"] for x in neighbours(cid, grid)]
        sc = 0.5 * res[cid]["S"][span]["net"] + 0.5 * (float(np.median(nb)) if nb else 0.0)
        if sc > bs:
            best, bs = cid, sc
    return best, len(elig)


def pick2(res, grid, tpw=(2.0, 4.0)):
    """The joint in-sample pick (defined after the first look, counted): in sample = 2026 H1 AND 2021-24, both money up,
    PF >= 1.2 / 1.1, 2-4 trades a week in both; score = plateau (half own, half the neighbours' median) of the smaller of
    the two $/month. Out of sample for this pick: 2026 H2 and 2025."""
    def ok(cid):
        a, b = res[cid]["S"]["H1"], res[cid]["S"]["2021-24"]
        return (a["n"] >= 15 and (a.get("pf") or 0) >= 1.2 and a["net"] > 0 and b["n"] >= 100 and (b.get("pf") or 0) >= 1.1
                and b["net"] > 0 and all(tpw[0] <= (x.get("tpw") or 0) <= tpw[1] for x in (a, b)))

    def m(cid):
        return min(res[cid]["S"]["H1"]["per_month"], res[cid]["S"]["2021-24"]["per_month"])
    elig = [cid for cid, _ in grid if ok(cid)]
    best, bs = None, -1e18
    for cid in elig:
        nb = [m(x) for x in neighbours(cid, grid)]
        sc = 0.5 * m(cid) + 0.5 * (float(np.median(nb)) if nb else 0.0)
        if sc > bs:
            best, bs = cid, sc
    return best, len(elig)


def grid_main():
    lit = lit_daily()
    out = {"built": dt.date.today().isoformat(), "families": {}}
    for fam, grid in (("NA", na_grid()), ("RE", re_grid()), ("IB", ib_grid())):
        res = {}
        for cid, cfg in grid:
            W = run(cfg)
            T = booked(W)
            S = score(T)
            res[cid] = {"cfg": cfg, "S": S, "corr": {sp: corr(T, sp, lit) for sp in ("2026", "2021-25")},
                        "years": {y: round(sum(t["pnl"] for t in T if t["day"][:4] == y)) for y in ("2021", "2022", "2023", "2024", "2025", "2026")}}
            s = S
            print(f"{cid:40s} H1 {s['H1']['n']:>3} {s['H1'].get('tpw')}/wk PF {s['H1'].get('pf')} ${s['H1'].get('net'):>7} | "
                  f"H2 PF {s['H2'].get('pf')} ${s['H2'].get('net'):>7} | 2025 PF {s['2025'].get('pf')} ${s['2025'].get('net'):>7} | "
                  f"21-24 PF {s['2021-24'].get('pf')} ${s['2021-24'].get('net'):>7} | corr {res[cid]['corr']['2026']['daily']}", flush=True)
        p_h1, n_h1 = pick(res, grid, "H1")
        p_pre, n_pre = pick(res, grid, "2021-24", min_n=100)
        p_j, n_j = pick2(res, grid)
        allpos = [cid for cid in res if all((res[cid]["S"][sp].get("net") or 0) > 0 for sp in ("H1", "H2", "2025", "2021-24"))]
        out["families"][fam] = {"res": res, "pick_h1": p_h1, "eligible_h1": n_h1, "pick_pre2025": p_pre, "eligible_pre": n_pre,
                                "pick_joint": p_j, "eligible_joint": n_j, "positive_all4": allpos, "count": len(grid),
                                "pre_declared": sum(1 for _, c in grid if not c.get("added"))}
        print(fam, "pick H1:", p_h1, f"({n_h1} eligible)", "| pre-2025 re-pick:", p_pre, f"({n_pre})", "| joint pick:", p_j,
              f"({n_j})", "| positive in all 4:", len(allpos), "of", len(grid))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)
    return out


# ================================================================================================ placebo
def twins(cfg, W, n=300, seed=11):
    """Random-entry twins: the same days as the real trades, a random half-hour check in the run's window (one per real
    trade), the run's long/short mix, the real trade's stop distance, the same exit machinery (trail for NA, fixed / 2R /
    VWAP for IB). -> list of n totals ($500 risk, costs in) per span."""
    B = D()
    rng = np.random.default_rng(seed)
    if cfg["fam"] == "NA":
        j0, j1 = col_of(cfg["start"]), col_of(cfg.get("last", (15, 0)))
    else:
        j0, j1 = col_of((10, 30)) + 1, col_of(cfg.get("end", (15, 0)))
    win = [j for j in range(NB) if j0 <= j <= j1]
    if cfg["fam"] == "NA":
        win = [j for j in win if j in CHECK_SET]
    pl = np.mean([w["dir"] == 1 for w in W]) if W else 0.5
    out = {sp: [] for sp in ("H1", "H2", "2025", "2021-24", "2026", "all")}
    for _ in range(n):
        tot = collections.defaultdict(float)
        for w in W:
            k = w["k"]
            j = int(rng.choice(win))
            d = 1 if rng.random() < pl else -1
            entry = B.O[k, j + 1] + d * TICK
            stop = entry - d * w["risk"]
            if cfg["fam"] == "NA":
                tr = na_trail(B, cfg["vm"], cfg.get("lb", 14), d) if cfg["exit"] == "trail" else None
                ww = walk(B, k, j, d, stop, "trail" if tr else "fixed", trail=tr, upd=cfg.get("upd", "check"))
            else:
                tgt = entry + d * 2.0 * w["risk"] if cfg["exit"] == "r2" else None
                tr = (lambda kk, jj: B.VW[kk, jj]) if cfg["exit"] == "vwap" else None
                ww = walk(B, k, j, d, stop, "trail" if tr else "fixed", trail=tr, tgt=tgt, upd="bar")
            if ww is None:
                continue
            q = size(ww)
            if q < 1:
                continue
            p = ww["pts"] * PV * q - COMM * q
            day = B.days[k]
            for sp in out:
                a, z = SPANS[sp]
                if a <= day <= z:
                    tot[sp] += p
        for sp in out:
            out[sp].append(tot[sp])
    return out


def placebo_main(ids=None):
    res = json.load(open(OUT, encoding="utf-8"))
    ids = ids or []
    if not ids:
        for fam in ("NA", "RE", "IB"):
            F = res["families"][fam]
            ids += [x for x in (F["pick_h1"], F["pick_pre2025"], F.get("pick_joint")) if x]
        ids += [PAPER, PAPER1]
    ids = list(dict.fromkeys(ids))
    res.setdefault("placebo", {})
    for cid in ids:
        fam = {"na": "NA", "re": "RE", "ib": "IB"}[cid[:2]]
        cfg = res["families"][fam]["res"][cid]["cfg"]
        cfg["start"] = tuple(cfg["start"]) if "start" in cfg else None
        if "end" in cfg:
            cfg["end"] = tuple(cfg["end"])
        W = run(cfg)
        T = booked(W)
        real = {sp: sum(t["pnl"] for t in T if SPANS[sp][0] <= t["day"] <= SPANS[sp][1]) for sp in ("H1", "H2", "2025", "2021-24", "2026", "all")}
        P = twins(cfg, W)
        row = {sp: {"real": round(real[sp]), "placebo_med": round(float(np.median(P[sp]))),
                    "p": round(float(np.mean([x >= real[sp] for x in P[sp]])), 3)} for sp in real}
        res["placebo"][cid] = row
        print(cid, " | ".join(f"{sp} real {v['real']:+,} plac {v['placebo_med']:+,} p {v['p']}" for sp, v in row.items()), flush=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)


# ================================================================================================ look-ahead + save
def lookahead(cid, n=300, seed=5):
    """Every signal of `cid` re-derived with the day's bars AFTER the signal bar scrambled (prices, volume) and the later
    days dropped from sigma: the side, the entry and the first stop must not change."""
    B = D()
    G = {**dict(na_grid()), **dict(re_grid())}
    cfg = G[cid]
    W = run(cfg)
    rng = np.random.default_rng(seed)
    pick_ = rng.choice(len(W), size=min(n, len(W)), replace=False)
    bad = 0
    for i in pick_:
        w = W[i]
        k, j = w["k"], w["j"]
        keep = {a: getattr(B, a)[k].copy() for a in ("O", "H", "L", "C", "V", "VW")}
        sg = {lb: B.sig[lb][k].copy() for lb in B.sig}
        try:
            for a in ("O", "H", "L", "C"):
                arr = getattr(B, a)[k]
                arr[j + 1:] = arr[j + 1:] + rng.normal(0, 50, NB - j - 1)
            B.V[k, j + 1:] = rng.integers(1, 10000, NB - j - 1)
            tp = (B.H[k] + B.L[k] + B.C[k]) / 3.0
            B.VW[k] = np.cumsum(tp * B.V[k]) / np.maximum(np.cumsum(B.V[k]), 1.0)
            for lb in B.sig:                       # sigma from the lb days before k only (recomputed from mv)
                B.sig[lb][k] = B.mv[k - lb:k].mean(axis=0) if k >= lb else np.nan
            lv = na_levels(B, k, j, cfg["vm"], cfg.get("lb", 14))
            ub, lo, sg2 = lv
            c = B.C[k, j]
            d = 1 if c > ub else -1 if c < lo else 0
            lvl = max(ub, B.VW[k, j]) if d == 1 else min(lo, B.VW[k, j])
            entry_ok = abs((B.O[k, j + 1] + d * TICK) - w["entry"]) < 1e-9 or True     # the entry bar's open is the fill (future by design)
            mn = max(10.0, 0.25 * sg2)
            e0 = w["entry"]
            stop = min(lvl, e0 - mn) if d == 1 else max(lvl, e0 + mn)
            if d != w["dir"] or abs(stop - w["stop0"]) > 1e-6:
                bad += 1
        finally:
            for a, v in keep.items():
                getattr(B, a)[k] = v
            for lb in B.sig:
                B.sig[lb][k] = sg[lb]
    return {"checked": int(len(pick_)), "differ": bad}


SAVE = [  # (run id, cid, title, status)
    ("div_na_joint", "na_vm125_1000_n99_fixed", "Noise-area momentum (Zarattini 2024) - joint pick H1 + 2021-24: band 1.25 sigma, 10:00, re-entries, fixed stop", "promising"),
    ("div_na_paper", "na_vm10_1000_n99_trail_check", "Noise-area momentum - the paper's own rule (band 1 sigma, 10:00, half-hour trail, re-entries)", "promising"),
    ("div_na_paper_1aday", "na_vm10_1000_n1_trail_check", "Noise-area momentum - the paper's rule, first entry of the day only", "rejected"),
    ("div_na_h1pick", "na_vm125_1030_n99_trail_check_vxh", "Noise-area momentum - strict 2026 H1 pick (VXN-high filter): fails 2025", "rejected"),
    ("div_na_plateau_1030", "na_vm125_1030_n2_fixed", "Noise-area momentum - 10:30 start, 2 a day (the 10:30 plateau)", "promising"),
    ("div_ib_h1pick", "ib_nar_mid_r2_15", "Initial-balance breakout, VXN-normalised narrow IB - H1 pick (fails H2, 2025)", "rejected"),
]


def save_main():
    from tools import runlib as rl
    res = json.load(open(OUT, encoding="utf-8"))
    B = D()
    G = {**dict(na_grid()), **dict(re_grid()), **dict(ib_grid())}
    for rid, cid, title, status in SAVE:
        T = booked(run(G[cid]))
        S = rl.score(T, B.days)
        fam = {"na": "NA", "re": "RE", "ib": "IB"}[cid[:2]]
        sc = res["families"][fam]["res"][cid]["S"]
        pl = res.get("placebo", {}).get(cid, {})
        v = (f"$500 risk a trade, costs in. H1 {sc['H1']['net']:+,} (PF {sc['H1']['pf']}), H2 {sc['H2']['net']:+,} (PF {sc['H2']['pf']}), "
             f"2025 {sc['2025']['net']:+,} (PF {sc['2025']['pf']}), 2021-24 {sc['2021-24']['net']:+,} (PF {sc['2021-24']['pf']}); "
             f"{sc['2026']['tpw']} / {sc['2021-25']['tpw']} trades a week (2026 / 2021-25). "
             + (f"Random-entry placebo p: 2026 {pl['2026']['p']}, 2021-24 {pl['2021-24']['p']}, all {pl['all']['p']}. " if pl else "")
             + "On MFFU accounts alone it cannot pass an eval in 2 weeks and the 50% best-day rule holds its payouts "
               "(research/writeups/diversifier-search.md).")
        rl.save(rid, title, "other", "Owner 2026-10-26: a strategy uncorrelated with LIT that holds in 2026 AND 2021-25?",
                params={"cfg": G[cid], "risk_usd": RISK_USD, "data": "CME NQ1! 5m RTH", "tool": "tools/div_search.py"},
                sizing={"mode": "fixed_risk", "risk_usd": RISK_USD, "max_micros": MAXQ}, trades=T, scored=S, status=status,
                verdict=v, notes="tools/div_search.py (research/second/div_search.json); entries at the next 5m open + 1 tick, stop "
                                 "fills -1 tick, $1.90 a micro; the run-library eval columns are at $500 a trade (not an eval sizing).",
                writeup="diversifier-search", tags=["second", "diversifier", fam.lower()])
        print("saved", rid, rl.line(S, "2026"), "|", rl.line(S, "2021-25"), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid_main()
    elif cmd == "placebo":
        placebo_main(sys.argv[2:])
    elif cmd == "lookahead":
        for cid in (sys.argv[2:] or ["na_vm125_1000_n99_fixed", "na_vm10_1000_n99_trail_check"]):
            print(cid, lookahead(cid))
    elif cmd == "save":
        save_main()
