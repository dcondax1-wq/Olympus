"""Automatic confluence discovery.

Every valid setup the engine sees becomes a shadow trade with ~150 recorded features. This scans ALL of them:
for each feature, how much better (in R per trade) do candidates do when it is present vs absent - separately in
four independent slices (NQ futures in-sample, NQ futures out-of-sample, CFD Q4 2023, CFD Q4 2025).

A confluence only counts as real when the sign of its lift agrees in every slice. Anything that flips is noise,
however good it looks in one period.
"""
from __future__ import annotations

import json
import os
import time
from multiprocessing import Pool

import numpy as np

from .data import DATA_DIR

SPLIT = "2026-09-22"
CACHE = os.path.join(DATA_DIR, "discovery.json")
WIDE = {"max_trades_day": 9, "stop_after_win": False, "min_score": -99, "daily_max_loss": 1e9, "dd_aware": False}
# real CME futures only (owner's rule: no CFD data): NQ in three walk-forward month blocks + ES as a cross-instrument check
# 2026-10-16: data/NQ_5m.csv now holds 5 years of NQ1! (2021-10 .. 2026-10) -> one slice per calendar year
# (late-2021 joins 2022); ES futures (2026-08+ only) stays as a cross-instrument check.
SLICES = [("NQ 2022", "NQ", None, "2022-12-31"), ("NQ 2023", "NQ", "2023-01-01", "2023-12-31"),
          ("NQ 2024", "NQ", "2024-01-01", "2024-12-31"), ("NQ 2025", "NQ", "2025-01-01", "2025-12-31"),
          ("NQ 2026", "NQ", "2026-01-01", None), ("ES futures", "ES", None, None)]
SKIP = {"gex_bn", "gex_pct", "dix", "pd_pos", "vix_prev", "q90_entry", "q90_sweep", "micro_entry"}

# human names for the leaderboard (anything missing falls back to the key)
NAMES = {
    "htf_trend": "1H structure with trade", "pd": "Discount/premium of 1H range", "vwap_disc": "Value side of session VWAP",
    "vol_climax": "Volume climax on raid", "lrl": "Low-resistance path (LRL)", "hrl": "High-resistance path (HRL)",
    "m15_trend": "15m already aligned", "dol_align": "Toward nearest major liquidity", "tgt_major": "Target is a major pool",
    "midnight": "Raid beyond midnight open", "keylevel": "Sweep into HTF key level", "smt": "SMT divergence",
    "protected": "Protected high/low intact", "amt": "AMT value context", "quality": "Quality pool swept",
    "shallow_raid": "Shallow raid (<0.5 ATR)", "deep_raid": "Deep raid (>1.5 ATR)", "disp_strong": "Strong displacement candle",
    "fast_reclaim": "Fast reclaim (<=3 bars)", "first_hour": "First hour of RTH", "multi_sweep": "Stacked liquidity raid",
    "major_swept": "Major pool raided", "cisd": "CISD trigger (no IFVG)", "trig_15m": "15m IFVG trigger", "pm": "PM session",
    "news_day": "High-impact news day", "fomc_day": "FOMC day", "vix_hi": "VIX >= 20",
    "qt_q2_sweep": "QT: sweep in Q2", "qt_q2q3": "QT: Q2 raid -> Q3 entry", "qt_entry_q3": "QT: entry in Q3",
    "qt_micro_23": "QT: micro quarter 2/3", "amd_day_open": "PO3: raid beyond daily open", "qt_session_open": "Raid beyond session true open",
    "qt_90_open": "Raid beyond 90m true open", "qt_week_open": "Raid beyond weekly open", "gex_low": "Low gamma regime",
    "gex_high": "High gamma regime", "gex_neg": "Negative dealer gamma",
    "x_swept_pd": "Swept prior-day H/L", "x_swept_on": "Swept overnight H/L", "x_swept_asia": "Swept Asia H/L",
    "x_swept_london": "Swept London H/L", "x_swept_h1": "Swept 1H swing", "x_swept_eq": "Swept equal highs/lows",
    "x_swept_pw": "Swept prior-week H/L", "x_minor_only": "Only minor 15m swing swept", "x_strong_close": "Trigger closes in top 25%",
    "x_weak_close": "Trigger closes weak", "x_trigger_vol_hi": "High volume on trigger", "x_early_session": "First 45m of session",
    "x_late_session": "90m+ into session", "x_monday": "Monday", "x_friday": "Friday", "x_midweek": "Tue-Thu",
    "x_after_loss": "Already lost today", "x_second_trade": "Not first setup of day", "x_tight_stop": "Tight stop (<=1 ATR)",
    "x_wide_stop": "Wide stop (>=2.5 ATR)", "x_big_ifvg": "Large IFVG (>=0.6 ATR)", "x_far_target": "Target >= 0.5 ADR away",
    "x_near_target": "Target <= 0.2 ADR away", "x_vwap_far": "Stretched >= 3 ATR from VWAP", "x_poc_side": "Entry below/above prior POC",
    "x_pd_mid_side": "Entry in discount of prior day", "x_pd_weak_close": "Prior day closed weak (toward raid)",
    "x_inside_day": "Prior day was an inside day", "x_on_wide": "Wide overnight range", "x_on_narrow": "Narrow overnight range",
    "x_with_day": "With the day's direction so far", "x_cisd_trigger": "CISD trigger", "x_long": "Long side", "trend_model": "Trend-day continuation",
    "rg_pd_trend": "Prior day trended (close near extreme)", "rg_pd_trend_day": "Prior day was a trend day", "rg_big_gap": "Big opening gap (>=0.35 ADR)",
    "rg_day_er": "Today's directional efficiency", "rg_dir5": "5-day direction", "rg_counter_5d": "Fading the 5-day direction",
    "rg_fade_today": "Fading today's direction", "rg_trending_5d": "5-day efficiency >= 0.5", "rg_rotational_5d": "5-day efficiency <= 0.25",
    "rg_trend_today": "Today already trending", "rg_vol_expanding": "Volatility expanding", "rg_pd_range_ratio": "Prior day range vs ADR",
    "rg_er5": "5-day efficiency", "rg_er10": "10-day efficiency", "rg_vol_expansion": "5-day range vs 60-day", "rg_gap_adr": "Opening gap (ADR)",
    "rg_day_dir": "Today's direction", "b_1D": "1D FVG order flow", "b_4H": "4H FVG order flow", "b_1H": "1H FVG order flow", "b_15m": "15m FVG order flow",
    "dol_room3": "3R+ room to major liquidity", "news_win": "Inside news window", "mtf_net": "MTF bias net",
    "rr_plan": "Planned R:R", "obstacles": "Obstacles to target", "depth_atr": "Raid depth (ATR)", "disp_atr": "Displacement (ATR)",
    "reclaim_bars": "Bars to reclaim", "dol_room_r": "Room to major liquidity (R)",
}


def _run(sym):
    from . import backtest
    r = backtest.run(sym, "5m", WIDE)
    return sym, [{"day": s["day"], "r": s["r"], "f": s["f"], "taken": s.get("taken", False)} for s in r["shadows"]]


def _split(vals):
    """How to turn a feature into present/absent: binary -> >0, signed -> >0 vs <0, continuous -> top vs bottom half."""
    u = set(np.unique(vals).tolist())
    if u <= {0, 1}:
        return "binary", None
    if u <= {-1, 0, 1}:
        return "signed", None
    return "continuous", float(np.median(vals))


def scan(force=False, max_age_h=24):
    if not force and os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < max_age_h * 3600:
        with open(CACHE) as fh:
            return json.load(fh)
    with Pool(2) as pool:
        sh = dict(pool.map(_run, ["NQ", "ES"]))
    slices = []
    for name, sym, a, z in SLICES:
        rows = [s for s in sh.get(sym, []) if s["r"] is not None and (not a or s["day"] >= a) and (not z or s["day"] <= z)]
        slices.append((name, rows))
    keys = sorted({k for _, rows in slices for s in rows for k, v in s["f"].items()
                   if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in SKIP})
    allrows = [s for _, rows in slices for s in rows]
    out = []
    for k in keys:
        vals = np.array([float(s["f"].get(k) or 0) for s in allrows])
        kind, med = _split(vals)
        if kind == "binary" and vals.sum() < 8:
            continue
        on_ = (lambda v: v > 0) if kind != "continuous" else (lambda v: v > med)
        off_ = (lambda v: v <= 0) if kind == "binary" else ((lambda v: v < 0) if kind == "signed" else (lambda v: v <= med))
        per = []
        for name, rows in slices:
            on = [s["r"] for s in rows if on_(float(s["f"].get(k) or 0))]
            off = [s["r"] for s in rows if off_(float(s["f"].get(k) or 0))]
            if len(on) >= 5 and len(off) >= 5:
                per.append({"slice": name, "lift": round(float(np.mean(on) - np.mean(off)), 3), "n_on": len(on), "n_off": len(off),
                            "r_on": round(float(np.mean(on)), 3)})
            else:
                per.append({"slice": name, "lift": None, "n_on": len(on), "n_off": len(off), "r_on": None})
        lifts = [x["lift"] for x in per if x["lift"] is not None]
        if len(lifts) < 3:
            continue
        on_all = [s["r"] for s in allrows if on_(float(s["f"].get(k) or 0))]
        off_all = [s["r"] for s in allrows if off_(float(s["f"].get(k) or 0))]
        pooled = float(np.mean(on_all) - np.mean(off_all))
        se = float(np.sqrt(np.var(on_all) / max(len(on_all), 1) + np.var(off_all) / max(len(off_all), 1))) or 1e-9
        tk_on = [s["r"] for s in allrows if s["taken"] and on_(float(s["f"].get(k) or 0))]
        tk_off = [s["r"] for s in allrows if s["taken"] and off_(float(s["f"].get(k) or 0))]
        pooled_taken = round(float(np.mean(tk_on) - np.mean(tk_off)), 3) if len(tk_on) >= 5 and len(tk_off) >= 5 else None
        sgn = 1 if pooled > 0 else -1
        agree = sum(1 for x in lifts if x * sgn > 0.05)
        verdict = ("STABLE" if agree == len(lifts) >= 4 else "LEANING" if agree >= len(lifts) - 1 and agree >= 3 else "NOISE")
        out.append({"key": k, "name": NAMES.get(k, k), "kind": kind, "median": med, "pooled": round(pooled, 3), "t": round(pooled / se, 2),
                    "pooled_taken": pooled_taken, "n_taken": len(tk_on),
                    "sign": sgn, "agree": agree, "slices_ok": len(lifts), "verdict": verdict, "per": per,
                    "freq": round(len(on_all) / max(len(allrows), 1), 3), "is_new": k.startswith("x_")})
    order = {"STABLE": 0, "LEANING": 1, "NOISE": 2}
    out.sort(key=lambda x: (order[x["verdict"]], -abs(x["t"])))
    res = {"generated": time.strftime("%Y-%m-%d %H:%M"), "slices": [{"name": n, "n": len(r), "avg_r": round(float(np.mean([s["r"] for s in r])), 3) if r else None}
                                                                    for n, r in slices],
           "features": out, "n_features": len(out),
           "counts": {v: sum(1 for x in out if x["verdict"] == v) for v in order}}
    with open(CACHE, "w") as fh:
        json.dump(res, fh)
    return res


if __name__ == "__main__":
    r = scan(force=True)
    print(f"{r['n_features']} features scanned  {r['counts']}  slices: {r['slices']}")
    for x in r["features"]:
        if x["verdict"] == "NOISE":
            continue
        ls = "  ".join("   -  " if p["lift"] is None else f"{p['lift']:+.2f}" for p in x["per"])
        print(f"{x['verdict']:7s} {'NEW ' if x['is_new'] else '    '}{x['name'][:38]:38s} pooled {x['pooled']:+.2f}R t={x['t']:+.1f} freq {x['freq']:.0%} | {ls}")
