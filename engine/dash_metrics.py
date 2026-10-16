"""Pure performance metrics over a normalized dataset (engine/dash_data.py): slim trades + per-session days.

Every function takes plain lists and returns JSON-ready dicts. Nothing here reads files or the clock, so the same code
serves the backtest, paper and five-year sources. R values are the engine's pnl_r (`r` in slim trades).
"""
from __future__ import annotations

import datetime as dt
import math
from collections import OrderedDict, defaultdict
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BAND = (2, 4)                                   # owner's hard rule: 2-4 trades per week
POOL_FAMILY = {"PWH": "PW", "PWL": "PW", "PDH": "PD", "PDL": "PD", "ONH": "ON", "ONL": "ON", "ASH": "ASIA", "ASL": "ASIA",
               "LOH": "LON", "LOL": "LON", "H1H": "H1", "H1L": "H1", "ITH": "M15", "ITL": "M15", "EQH": "EQ", "EQL": "EQ"}
POOL_ORDER = ["PW", "PD", "ON", "ASIA", "LON", "H1", "EQ", "M15"]


def _r(v, nd=2):
    if v is None:
        return None
    v = float(v)
    if v != v or math.isinf(v):
        return None
    return round(v, nd)


def entry_et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t["entry_t"]), ET)


def killzone(t) -> str:
    x = entry_et(t)
    m = x.hour * 60 + x.minute
    if 570 <= m < 690:
        return "NY AM"
    if 810 <= m < 930:
        return "NY PM"
    if 120 <= m < 300:
        return "London"
    return "Other"


def pool_family(t) -> str:
    fams = set()
    for lab in t.get("pools") or []:
        for k in str(lab).split("·")[-1].split("/"):
            fams.add(POOL_FAMILY.get(k.strip(), k.strip()))
    for f in POOL_ORDER:
        if f in fams:
            return f
    return sorted(fams)[0] if fams else "?"


def target_family(t) -> str:
    lab = str(t.get("target_label") or "").split(" ")[0].split("/")[0]
    lab = "".join(ch for ch in lab if not ch.isdigit())
    return POOL_FAMILY.get(lab, lab or "R")


def agg(ts: list) -> dict:
    n = len(ts)
    pnl = [float(t.get("pnl") or 0) for t in ts]
    rs = [float(t.get("r") or 0) for t in ts]
    wins = [x for x in pnl if x > 0]
    gp, gl = sum(wins), -sum(x for x in pnl if x <= 0)
    return {"n": n, "wins": len(wins), "wr": _r(len(wins) / n * 100, 1) if n else None,
            "avg_r": _r(sum(rs) / n, 3) if n else None, "total_r": _r(sum(rs), 2), "pnl": _r(sum(pnl), 2),
            "pf": (_r(gp / gl, 2) if gl > 0 else (None if gp == 0 else 999.0)) if n else None,
            "expectancy": _r(sum(pnl) / n, 2) if n else None}


# ------------------------------------------------------------------ equity + drawdown
def equity(trades, days, start=50000.0):
    eq, peak, rows = start, start, []
    for t in trades:
        eq += float(t.get("pnl") or 0)
        peak = max(peak, eq)
        rows.append({"t": t.get("exit_t") or t["entry_t"], "eq": _r(eq), "dd": _r(eq - peak), "pnl": t.get("pnl"), "r": t.get("r")})
    eq, peak, drows, uw, max_uw, max_dd, max_dd_date = start, start, [], 0, 0, 0.0, None
    for d in days:
        eq += float(d.get("pnl") or 0)
        peak = max(peak, eq)
        dd = eq - peak
        uw = uw + 1 if dd < 0 else 0
        max_uw = max(max_uw, uw)
        if dd < max_dd:
            max_dd, max_dd_date = dd, d["date"]
        drows.append({"date": d["date"], "eq": _r(eq), "dd": _r(dd), "pnl": d.get("pnl"), "trades": d.get("trades", 0)})
    net = eq - start
    return {"trades": rows, "days": drows,
            "summary": {"start": start, "net": _r(net), "end": _r(eq), "peak": _r(peak), "max_dd": _r(max_dd),
                        "max_dd_date": max_dd_date, "current_dd": _r(eq - peak), "longest_underwater_days": max_uw,
                        "recovery_factor": _r(net / -max_dd, 2) if max_dd < 0 else None}}


# ------------------------------------------------------------------ calendar heatmap
def calendar(trades, days):
    rsum = defaultdict(float)
    for t in trades:
        rsum[t["day"]] += float(t.get("r") or 0)
    out, months = [], OrderedDict()
    for d in days:
        p = float(d.get("pnl") or 0)
        out.append({"date": d["date"], "dow": d.get("dow"), "pnl": _r(p), "trades": d.get("trades", 0),
                    "r": _r(rsum.get(d["date"], 0.0), 2) if d.get("trades") else None, "regime": d.get("regime")})
        m = months.setdefault(d["date"][:7], {"month": d["date"][:7], "pnl": 0.0, "trades": 0, "green_days": 0, "red_days": 0,
                                              "flat_days": 0, "sessions": 0})
        m["pnl"] += p
        m["trades"] += d.get("trades", 0)
        m["sessions"] += 1
        m["green_days" if p > 0 else "red_days" if p < 0 else "flat_days"] += 1
    for m in months.values():
        m["pnl"] = _r(m["pnl"])
    return {"days": out, "months": list(months.values()),
            "max_abs_pnl": _r(max((abs(x["pnl"] or 0) for x in out), default=0.0))}


# ------------------------------------------------------------------ hour x weekday
def heatmap(trades, metric="avg_r"):
    cells = defaultdict(list)
    for t in trades:
        x = entry_et(t)
        cells[(x.hour, x.weekday())].append(t)
    hours = sorted({h for h, _ in cells} | {9, 10, 11, 13, 14, 15})
    rows = []
    for h in hours:
        for w in range(5):
            a = agg(cells.get((h, w), []))
            rows.append({"hour": h, "dow": w, "n": a["n"], "pnl": a["pnl"], "avg_r": a["avg_r"], "wr": a["wr"]})
    by_hour = [{"hour": h, **agg([t for (hh, _), v in cells.items() if hh == h for t in v])} for h in hours]
    by_dow = [{"dow": w, "name": DOW[w], **agg([t for (_, ww), v in cells.items() if ww == w for t in v])} for w in range(5)]
    return {"metric": metric, "hours": hours, "weekdays": DOW[:5], "cells": rows, "by_hour": by_hour, "by_dow": by_dow}


# ------------------------------------------------------------------ R distribution
def rdist(trades, bin_r=0.25):
    rs = np.array([float(t.get("r") or 0) for t in trades])
    if not len(rs):
        return {"bin": bin_r, "bins": [], "stats": {"n": 0}}
    lo = max(-3.0, math.floor(rs.min() / bin_r) * bin_r)
    hi = min(8.0, math.ceil(rs.max() / bin_r) * bin_r + (bin_r if rs.max() % bin_r == 0 else 0))
    edges = np.arange(lo, hi + bin_r / 2, bin_r)
    if len(edges) < 2:
        edges = np.array([lo, lo + bin_r])
    bins = []
    clipped = np.clip(rs, edges[0], edges[-1] - 1e-9)
    idx = np.searchsorted(edges, clipped, side="right") - 1
    for k in range(len(edges) - 1):
        m = idx == k
        bins.append({"lo": _r(edges[k], 2), "hi": _r(edges[k + 1], 2), "n": int(m.sum()), "wins": int((rs[m] > 0).sum())})
    sd = float(rs.std())
    skew = float(((rs - rs.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    pnl = [float(t.get("pnl") or 0) for t in trades]
    return {"bin": bin_r, "bins": bins,
            "stats": {"n": int(len(rs)), "mean": _r(rs.mean(), 3), "median": _r(np.median(rs), 3), "std": _r(sd, 3),
                      "skew": _r(skew, 2), "min": _r(rs.min(), 2), "max": _r(rs.max(), 2),
                      "pct_ge_2r": _r((rs >= 2).mean() * 100, 1), "pct_le_m1r": _r((rs <= -0.99).mean() * 100, 1),
                      "pct_scratch": _r((np.abs(rs) < 0.1).mean() * 100, 1), "expectancy_usd": _r(sum(pnl) / len(pnl), 2)}}


# ------------------------------------------------------------------ streaks
def _runs(seq):
    """seq of +1/-1 -> list of (sign, length)."""
    out = []
    for s in seq:
        if out and out[-1][0] == s:
            out[-1][1] += 1
        else:
            out.append([s, 1])
    return out


def streaks(trades, days):
    seq = [1 if float(t.get("pnl") or 0) > 0 else -1 for t in trades]
    runs = _runs(seq)
    hw, hl = defaultdict(int), defaultdict(int)
    for s, n in runs:
        (hw if s > 0 else hl)[n] += 1
    cur = {"kind": ("win" if runs[-1][0] > 0 else "loss"), "len": runs[-1][1]} if runs else None
    dseq = [1 if d["pnl"] > 0 else -1 for d in days if d.get("trades") and d.get("pnl")]
    druns = _runs(dseq)
    return {"trades": {"current": cur, "max_win": max((n for s, n in runs if s > 0), default=0),
                       "max_loss": max((n for s, n in runs if s < 0), default=0),
                       "hist_win": [{"len": k, "n": v} for k, v in sorted(hw.items())],
                       "hist_loss": [{"len": k, "n": v} for k, v in sorted(hl.items())],
                       "sequence": [{"entry_t": t["entry_t"], "w": 1 if s > 0 else 0, "r": t.get("r")} for t, s in zip(trades, seq)][-200:]},
            "days": {"current": ({"kind": "green" if druns[-1][0] > 0 else "red", "len": druns[-1][1]} if druns else None),
                     "max_green": max((n for s, n in druns if s > 0), default=0),
                     "max_red": max((n for s, n in druns if s < 0), default=0), "note": "days with trades only"}}


# ------------------------------------------------------------------ MAE / MFE
def maemfe(trades):
    pts = [{"entry_t": t["entry_t"], "mae": t.get("mae"), "mfe": t.get("mfe"), "r": t.get("r"), "win": float(t.get("pnl") or 0) > 0,
            "exit": t.get("exit_reason"), "grade": t.get("grade"), "dir": t.get("dir")} for t in trades if t.get("mfe") is not None]
    w = [p for p in pts if p["win"]]
    l = [p for p in pts if not p["win"]]
    cap = [p["r"] / p["mfe"] for p in w if p["mfe"] and p["mfe"] > 0 and p["r"] is not None]
    return {"points": pts,
            "summary": {"n": len(pts), "winners_median_mae": _r(np.median([p["mae"] for p in w]), 3) if w else None,
                        "losers_median_mfe": _r(np.median([p["mfe"] for p in l]), 3) if l else None,
                        "pct_winners_mae_gt_half_r": _r(sum(1 for p in w if (p["mae"] or 0) > 0.5) / len(w) * 100, 1) if w else None,
                        "pct_losers_mfe_ge_1r": _r(sum(1 for p in l if (p["mfe"] or 0) >= 1) / len(l) * 100, 1) if l else None,
                        "avg_capture": _r(np.mean(cap), 3) if cap else None,
                        "left_on_table_r": _r(sum(max(0.0, (p["mfe"] or 0) - (p["r"] or 0)) for p in w), 2) if w else None}}


# ------------------------------------------------------------------ breakdowns
DIMS = {"grade": lambda t: t.get("grade") or "?", "killzone": killzone, "dir": lambda t: "Long" if t.get("dir") == 1 else "Short",
        "pool": pool_family, "trigger": lambda t: t.get("trigger") or "?", "exit": lambda t: t.get("exit_reason") or "?",
        "regime": lambda t: t.get("regime") or "?", "dow": lambda t: DOW[entry_et(t).weekday()], "target": target_family,
        "model": lambda t: t.get("model") or "sweep", "hour": lambda t: f"{entry_et(t).hour:02d}:00"}
DIM_ORDER = {"grade": ["A+", "A", "B", "C", "D", "?"], "dow": DOW, "killzone": ["London", "NY AM", "NY PM", "Other"]}


def breakdown(trades, by=None):
    out = {}
    for dim in (by or [k for k in DIMS if k != "hour"]):
        fn = DIMS.get(dim)
        if fn is None:
            continue
        g = defaultdict(list)
        for t in trades:
            g[fn(t)].append(t)
        order = DIM_ORDER.get(dim)
        keys = sorted(g, key=lambda k: (order.index(k) if order and k in order else 99, str(k)))
        out[dim] = [{"key": k, **agg(g[k])} for k in keys]
    return out


def conditions(trades, min_n=5, top=5):
    """Best / worst buckets across every dimension (min_n trades each), ranked by avg R."""
    rows = []
    for dim, groups in breakdown(trades).items():
        for g in groups:
            if g["n"] >= min_n and g["avg_r"] is not None:
                rows.append({"dim": dim, **g})
    rows.sort(key=lambda x: -x["avg_r"])
    return {"best": rows[:top], "worst": list(reversed(rows[-top:])) if len(rows) > top else [], "min_n": min_n}


# ------------------------------------------------------------------ frequency (2-4 trades / week)
def iso_week(day: str):
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def weeks(trades, days):
    wk = OrderedDict()
    for d in days:
        k = iso_week(d["date"])
        mon = dt.date.fromisoformat(d["date"]) - dt.timedelta(days=dt.date.fromisoformat(d["date"]).weekday())
        w = wk.setdefault(k, {"key": k, "start": mon.isoformat(), "sessions": 0, "n": 0, "pnl": 0.0, "r": 0.0})
        w["sessions"] += 1
        w["pnl"] += float(d.get("pnl") or 0)
    for t in trades:
        k = iso_week(t["day"])
        if k in wk:
            wk[k]["n"] += 1
            wk[k]["r"] += float(t.get("r") or 0)
    return list(wk.values())


def frequency(trades, days, current_week=None):
    rows = weeks(trades, days)
    lo, hi = BAND
    for w in rows:
        w["pnl"], w["r"] = _r(w["pnl"]), _r(w["r"])
        w["zone"] = "zero" if w["n"] == 0 else "below" if w["n"] < lo else "above" if w["n"] > hi else "in"
        w["in_band"] = w["zone"] == "in"
        w["partial"] = w["sessions"] < 4 or w["key"] == current_week
    full = [w for w in rows if not w["partial"]]
    ns = [w["n"] for w in full]
    pct = lambda z: _r(sum(1 for w in full if w["zone"] == z) / len(full) * 100, 1) if full else None
    summ = {"weeks": len(full), "avg": _r(np.mean(ns), 2) if ns else None, "median": _r(np.median(ns), 1) if ns else None,
            "pct_in_band": pct("in"), "pct_below": _r(((pct("below") or 0) + (pct("zero") or 0)), 1) if full else None,
            "pct_above": pct("above"), "pct_zero": pct("zero"), "rolling4": _r(np.mean(ns[-4:]), 2) if ns else None,
            "tpw_overall": _r(len(trades) / max(len(days) / 5.0, 1e-9), 2) if days else None,
            "note": "partial weeks (fewer than 4 sessions, or the current week) are listed but excluded from the percentages"}
    return {"band": list(BAND), "weeks": rows, "summary": summ}


# ------------------------------------------------------------------ periods (5-year history)
def _pkey(day: str, by: str):
    if by == "year":
        return day[:4]
    if by == "month":
        return day[:7]
    return f"{day[:4]}Q{(int(day[5:7]) - 1) // 3 + 1}"


def _max_dd(pnls):
    if not pnls:
        return 0.0
    eq = np.cumsum(pnls)
    return float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())


def period_stats(trades, days):
    a = agg(trades)
    fq = frequency(trades, days)["summary"]
    ers = [d["er10"] for d in days if d.get("er10") is not None]
    reg = defaultdict(int)
    for d in days:
        reg[d.get("regime") or "?"] += 1
    return {"sessions": len(days), "trades": a["n"], "tpw": _r(a["n"] / max(len(days) / 5.0, 1e-9), 2) if days else None,
            "wr": a["wr"], "avg_r": a["avg_r"], "total_r": a["total_r"], "pf": a["pf"], "net": a["pnl"],
            "max_dd": _r(_max_dd([float(t.get("pnl") or 0) for t in trades])), "pct_weeks_in_band": fq["pct_in_band"],
            "pct_zero_weeks": fq["pct_zero"], "avg_er10": _r(np.mean(ers), 3) if ers else None,
            "trending_days": reg.get("trending", 0), "longs": sum(1 for t in trades if t.get("dir") == 1),
            "shorts": sum(1 for t in trades if t.get("dir") == -1)}


def periods(trades, days, by="quarter"):
    g = OrderedDict()
    for d in days:
        g.setdefault(_pkey(d["date"], by), {"days": [], "trades": []})["days"].append(d)
    for t in trades:
        k = _pkey(t["day"], by)
        if k in g:
            g[k]["trades"].append(t)
    rows = [{"key": k, "from": v["days"][0]["date"], "to": v["days"][-1]["date"], **period_stats(v["trades"], v["days"])}
            for k, v in g.items()]
    return {"by": by, "periods": rows, "total": period_stats(trades, days)}


# ------------------------------------------------------------------ rolling edge
def rolling(trades, window=20):
    out = []
    for i in range(window, len(trades) + 1):
        a = agg(trades[i - window:i])
        out.append({"i": i, "entry_t": trades[i - 1]["entry_t"], "day": trades[i - 1]["day"], "wr": a["wr"], "avg_r": a["avg_r"],
                    "pf": a["pf"], "sum_r": a["total_r"]})
    full = agg(trades)
    return {"window": window, "series": out, "latest": out[-1] if out else None,
            "full": {"wr": full["wr"], "avg_r": full["avg_r"], "pf": full["pf"], "n": full["n"]}}


# ------------------------------------------------------------------ exits
def exits(trades, exit_signals=None):
    g = defaultdict(list)
    for t in trades:
        g[t.get("exit_reason") or "?"].append(t)
    n = len(trades)
    reasons = sorted(({"key": k, **agg(v), "share": _r(len(v) / n * 100, 1)} for k, v in g.items()), key=lambda x: -x["n"])
    sigs = []
    for x in exit_signals or []:
        sigs.append({k: (_r(v, 3) if isinstance(v, float) else v) for k, v in x.items()})
    return {"reasons": reasons, "signals": sigs}


# ------------------------------------------------------------------ MFFU eval: tracker + Monte Carlo
def eval_state(days, plan, balance=None, peak_eod=None):
    """Walk the given paper days through the EOD-trailing MLL. Overrides win over the walk."""
    start, mll_amt = float(plan["start"]), float(plan["mll"])
    lock = start + float(plan["lock_above"]) if plan.get("lock_above") is not None else float("inf")
    bal, peak, mll, rows = start, start, start - mll_amt, []
    for d in days:
        bal += float(d.get("pnl") or 0)
        peak = max(peak, bal)
        mll = min(max(mll, peak - mll_amt), lock)
        rows.append({"date": d["date"], "pnl": _r(d.get("pnl")), "balance": _r(bal), "mll": _r(mll), "trades": d.get("trades", 0)})
    if balance is not None:
        bal = float(balance)
    if peak_eod is not None:
        peak = max(float(peak_eod), start)
        mll = min(max(start - mll_amt, peak - mll_amt), lock)
    elif balance is not None:
        peak = max(peak, bal)
        mll = min(max(mll, peak - mll_amt), lock)
    return {"balance": bal, "peak_eod": peak, "mll": mll, "locked": mll >= lock, "lock": lock, "days": rows}


def mc_eval(days, plan, n=3000, horizon=60, start_bal=None, peak_eod=None, seed=7, paths=30):
    """Vectorized bootstrap of (day pnl, intraday low) pairs through the MFFU EOD-trailing rules
    (same semantics as engine.analytics.simulate_eval), optionally from the current eval state."""
    pn = np.array([float(d.get("pnl") or 0) for d in days])
    lo = np.array([float(d.get("low") if d.get("low") is not None else min(0.0, d.get("pnl") or 0)) for d in days])
    if not len(pn):
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pn), (n, horizon))
    P, L = pn[idx], lo[idx]
    start = float(plan["start"])
    mll_amt = float(plan["mll"])
    lock = start + float(plan["lock_above"]) if plan.get("lock_above") is not None else np.inf
    b0 = float(start_bal) if start_bal is not None else start
    p0 = max(float(peak_eod) if peak_eod is not None else b0, b0, start)
    bal = np.full(n, b0)
    peak = np.full(n, p0)
    mll = np.full(n, min(max(start - mll_amt, p0 - mll_amt), lock))
    status = np.zeros(n, dtype=np.int8)
    when = np.zeros(n, dtype=np.int32)
    active = np.zeros(n, dtype=np.int32)
    curve = np.zeros((n, horizon))
    target = start + float(plan["target"])
    min_days = int(plan.get("min_days_eval") or 1)
    for k in range(horizon):
        live = status == 0
        low_intra = bal + L[:, k]
        nb = bal + P[:, k]
        fail = live & ((low_intra <= mll) | (nb <= mll))
        bal = np.where(live, nb, bal)
        status[fail] = -1
        when[fail] = k + 1
        ok = live & ~fail
        peak = np.where(ok, np.maximum(peak, bal), peak)
        mll = np.where(ok, np.minimum(np.maximum(mll, peak - mll_amt), lock), mll)
        active += (ok & (P[:, k] != 0)).astype(np.int32)
        win = ok & (bal >= target) & (active >= min_days)
        status[win] = 1
        when[win] = k + 1
        curve[:, k] = bal - b0
    passed = when[status == 1]
    hist = []
    if len(passed):
        step = 5
        for a in range(0, horizon, step):
            hist.append({"d": a + step, "n": int(((passed > a) & (passed <= a + step)).sum())})
    q = lambda arr, p: _r(np.percentile(arr, p), 1)
    bands = {f"p{p}": [q(curve[:, k], p) for k in range(horizon)] for p in (5, 25, 50, 75, 95)}
    finals = curve[:, -1]
    return {"n": n, "horizon": horizon, "pass_prob": _r((status == 1).mean() * 100, 1), "fail_prob": _r((status == -1).mean() * 100, 1),
            "open_prob": _r((status == 0).mean() * 100, 1),
            "days_to_pass": {"median": _r(np.median(passed), 1) if len(passed) else None,
                             "p25": q(passed, 25) if len(passed) else None, "p75": q(passed, 75) if len(passed) else None,
                             "p90": q(passed, 90) if len(passed) else None, "hist": hist},
            "days_to_fail_median": _r(np.median(when[status == -1]), 1) if (status == -1).any() else None,
            "bands": {"days": list(range(1, horizon + 1)), **bands},
            "final": {"p5": q(finals, 5), "p50": q(finals, 50), "p95": q(finals, 95)},
            "sample_paths": [[_r(x, 1) for x in curve[i]] for i in range(min(paths, n))],
            "start": {"balance": _r(b0), "peak_eod": _r(p0)}, "bootstrap_days": int(len(pn))}
