"""Stress tests: execution costs, outlier removal, walk-forward folds, parameter neighbourhood."""
from __future__ import annotations

import numpy as np

from . import backtest
from .instruments import INSTRUMENTS


def _summ(trades):
    if not trades:
        return {"n": 0, "net": 0, "pf": 0, "wr": 0, "avg_r": 0}
    pnl = np.array([t["pnl"] for t in trades])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    return {"n": int(len(pnl)), "net": round(float(pnl.sum()), 2), "pf": round(float(gp / gl), 2) if gl else 9.99,
            "wr": round(float((pnl > 0).mean() * 100), 1), "avg_r": round(float(np.mean([t["pnl_r"] for t in trades])), 3)}


def stress(sym="NQ", tf="5m", params=None):
    params = dict(params or {})
    base = backtest.run(sym, tf, params, light=True)
    out = {"baseline": _summ(base["trades"])}
    out["slippage_2t"] = _summ(backtest.run(sym, tf, {**params, "slippage_ticks": 2}, light=True)["trades"])
    out["slippage_3t"] = _summ(backtest.run(sym, tf, {**params, "slippage_ticks": 3}, light=True)["trades"])
    spec = INSTRUMENTS[sym]
    dbl = [dict(t, pnl=t["pnl"] - t["comm"]) for t in base["trades"]]
    out["commission_x2"] = _summ(dbl)
    srt = sorted(base["trades"], key=lambda t: t["pnl"], reverse=True)
    out["minus_best_3"] = _summ(srt[3:])
    out["minus_best_5"] = _summ(srt[5:])
    # walk-forward style folds (contiguous blocks of trading days)
    days = [d["date"] for d in base["days"]]
    folds = []
    k = 4
    size = max(1, len(days) // k)
    for f in range(k):
        a = days[f * size]
        z = days[min(len(days) - 1, (f + 1) * size - 1)] if f < k - 1 else days[-1]
        tr = [t for t in base["trades"] if a <= t["day"] <= z]
        folds.append({"from": a, "to": z, **_summ(tr)})
    out["folds"] = folds
    return out


EXIT_GROUPS = {
    "Target": [("Current", {}), ("Nearest DOL", {"target_mode": "dol"}), ("Next DOL", {"target_mode": "dol_next"}),
               ("Fixed 1.5R", {"target_mode": "fixed", "fallback_rr": 1.5}), ("Fixed 2R", {"target_mode": "fixed", "fallback_rr": 2.0}),
               ("Fixed 3R", {"target_mode": "fixed", "fallback_rr": 3.0}), ("Cap 3R", {"max_rr": 3.0}), ("Cap 4R", {"max_rr": 4.0}), ("Cap 6R", {"max_rr": 6.0})],
    "Stop": [("Current", {}), ("Buffer ×0.5", {"stop_buffer_mult": 0.5}), ("Buffer ×2", {"stop_buffer_mult": 2.0}),
             ("Beyond IFVG", {"stop_mode": "ifvg"}), ("Max stop 40", {"spec": {"max_stop": 40}}), ("Max stop 80", {"spec": {"max_stop": 80}})],
    "Partials": [("Current", {}), ("50% @1R + BE", {"partial_pct": 0.5, "partial_r": 1.0, "be_after_partial": True}),
                 ("50% @1R", {"partial_pct": 0.5, "partial_r": 1.0, "be_after_partial": False}),
                 ("33% @1R", {"partial_pct": 0.34, "partial_r": 1.0, "be_after_partial": False}),
                 ("50% @2R", {"partial_pct": 0.5, "partial_r": 2.0, "be_after_partial": False}),
                 ("50% @first pool", {"partial_pct": 0.5, "partial_at": "pool", "be_after_partial": False})],
    "Management": [("Current", {}), ("No BE", {"be_at_r": 0.0}), ("BE @1.5R", {"be_at_r": 1.5}), ("BE @2R", {"be_at_r": 2.0}),
                   ("R-trail 1R from 2R", {"trail_mode": "r", "trail_start_r": 2.0, "trail_r": 1.0}),
                   ("Swing trail from 1R", {"trail_mode": "swing", "trail_start_r": 1.0}),
                   ("No time stop", {"time_stop_min": 0}), ("Time stop 20m", {"time_stop_min": 20}), ("Time stop 60m", {"time_stop_min": 60})],
}


def exit_study(sym="NQ", tf="5m", params=None, split="2026-09-22"):
    params = dict(params or {})
    out = {"split": split, "groups": {}}
    for g, variants in EXIT_GROUPS.items():
        rows = []
        for name, over in variants:
            p = {**params, **over}
            if "spec" in over:
                p["spec"] = {**(params.get("spec") or {}), **over["spec"]}
            tr = backtest.run(sym, tf, p, light=True)["trades"]
            rows.append({"name": name, "is": _summ([t for t in tr if t["day"] < split]),
                         "oos": _summ([t for t in tr if t["day"] >= split]), "all": _summ(tr)})
        out["groups"][g] = rows
    base = backtest.run(sym, tf, params, light=True)["trades"]
    mfe = np.array([t["mfe"] for t in base]) if base else np.zeros(0)
    mae = np.array([t["mae"] for t in base]) if base else np.zeros(0)
    pr = np.array([t["pnl_r"] for t in base]) if base else np.zeros(0)
    lv = [0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5]
    out["anatomy"] = {
        "levels": lv,
        "reach_all": [round(float(np.mean(mfe >= x) * 100), 1) for x in lv] if len(mfe) else [],
        "reach_losers": [round(float(np.mean(mfe[pr <= 0] >= x) * 100), 1) for x in lv] if (pr <= 0).any() else [],
        "winners_mae": [round(float(np.mean(mae[pr > 0] >= x) * 100), 1) for x in lv] if (pr > 0).any() else [],
    }
    return out


def placebo(sym="NQ", tf="5m", params=None, n=500, seed=11):
    """Random-entry placebo with identical risk, targets and management. Returns real vs placebo distribution."""
    from .data import load
    params = {**(params or {}), "dd_aware": False, "conviction_step": 0}
    tr = backtest.run(sym, tf, params, light=True)["trades"]
    if not tr:
        return {"n_trades": 0}
    b = load(sym, tf)
    p = backtest.merge_params(params)
    rng = np.random.default_rng(seed)
    by_day = {}
    for i, (d, m) in enumerate(zip(b.date_str, b.mod)):
        if any(a <= m < z - 10 for a, z in p["entry_windows"]):
            by_day.setdefault(d, []).append(i)
    secs = {"1m": 60, "5m": 300}.get(tf, 300)
    tstop = int(p["time_stop_min"] * 60 // secs) if p["time_stop_min"] else 0

    def sim(i0, d, risk, rr):
        entry = b.o[i0] + d * 0.25
        stop, tgt, mfe, day = entry - d * risk, entry + d * rr * risk, 0.0, b.tday[i0]
        k = i0
        for k in range(i0, min(i0 + 300, len(b.t))):
            if b.tday[k] != day:
                return (b.c[k - 1] - entry) * d / risk
            lo, hi = (b.l[k], b.h[k]) if d == 1 else (-b.h[k], -b.l[k])
            if lo <= stop * d:
                return (min(b.o[k] * d, stop * d) - 0.25 - entry * d) / risk
            if hi >= tgt * d + 0.25:
                return rr
            mfe = max(mfe, (hi - entry * d) / risk)
            if b.mod[k] >= p["flat_mod"] or (tstop and k - i0 + 1 >= tstop and mfe < 0.5):
                return (b.c[k] - entry) * d / risk
            if p["be_at_r"] and mfe >= p["be_at_r"]:
                stop = entry + d * 0.25
        return (b.c[k] - entry) * d / risk

    tix = {int(t): i for i, t in enumerate(b.t)}
    real = float(np.mean([t["pnl_r"] for t in tr]))
    flipped = [sim(tix[int(t["entry_t"])], -t["dir"], t["risk_pts"], max(1.5, t["rr"])) for t in tr if int(t["entry_t"]) in tix]
    dist = []
    for _ in range(n):
        rs = [sim(int(rng.choice(by_day[t["day"]])), int(rng.choice([-1, 1])), t["risk_pts"], t["rr"]) for t in tr if t["day"] in by_day]
        dist.append(float(np.mean(rs)))
    dist = np.array(dist)
    # bootstrap CI of the real average R
    rr_ = np.array([t["pnl_r"] for t in tr])
    boots = np.array([rng.choice(rr_, len(rr_)).mean() for _ in range(2000)])
    hist, edges = np.histogram(dist, bins=30)
    return {"n_trades": len(tr), "real": round(real, 3), "flipped": round(float(np.mean(flipped)), 3) if flipped else None,
            "placebo_mean": round(float(dist.mean()), 3), "placebo_p95": round(float(np.percentile(dist, 95)), 3),
            "placebo_p99": round(float(np.percentile(dist, 99)), 3), "p_value": round(float(np.mean(dist >= real)), 4),
            "ci90": [round(float(np.percentile(boots, 5)), 3), round(float(np.percentile(boots, 95)), 3)],
            "p_avg_r_le_0": round(float(np.mean(boots <= 0)), 4),
            "hist": hist.tolist(), "edges": [round(float(e), 3) for e in edges]}


def neighbourhood(sym="NQ", tf="5m", params=None, x=("min_rr", [1.0, 1.5, 2.0, 2.5]), y=("max_rr", [2.0, 3.0, 4.0, 5.0, 6.0])):
    params = dict(params or {})
    grid = []
    for yv in y[1]:
        row = []
        for xv in x[1]:
            r = backtest.run(sym, tf, {**params, x[0]: xv, y[0]: yv}, light=True)
            s = _summ(r["trades"])
            row.append({"x": xv, "y": yv, **s})
        grid.append(row)
    return {"x": x[0], "y": y[0], "xs": x[1], "ys": y[1], "grid": grid}
