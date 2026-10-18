"""Backtest bundle for the dashboard's Results page: everything behind the live strategy in one JSON.

Re-runs the exact live loop (tools/five_year.live_jobs: 20-day window per session, as engine/live.py) with the settings in
live_model.json over every TradingView NQ1! session in data/NQ_5m.csv, applies the cold-streak equity filter exactly as
engine/equity_filter.py does, and writes research/lab/backtest_live.json:

  meta      strategy label, params, filter, data coverage, costs, how it was built
  trades    every trade (entry/stop/target/exit, stop pts, micros, $ risked, R, $, half-size flag, trigger, grade)
  days      daily P&L + intraday low (for equity curve / drawdown / eval sim)
  periods   stats for 2026 YTD, each full year and all years (trades/week, win %, PF, net, max DD, stop sizes)
  months    net $ and trades per month
  stop_buckets  results by stop size (why wide stops are de-risked)
  evals     MFFU 50K: pass/fail within 2 weeks and 1 month (new eval every session) and back-to-back runs
  lessons   learning from wins and losses: each condition's results in 2021-25 vs 2026; only patterns that hold in both count
  trades[].report   strategy, date, time, why it entered, the plan, what happened, lessons from that trade

  python tools/export_backtest.py            # ~1-2 min on 11 processes

When live_model.json says "model": "lit" the bundle is the LIT replay instead (main_lit: one process, ~20 s), same shape
plus the periods "2026 H1 (picked on)", "2026 H2 (check)" and "2021-25 (reference)". The engine's own replay is then
tools/runlib.py baseline (it reads live_model_engine.json).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "backtest_live.json")

from tools import five_year as fy  # noqa: E402

_orig_slim = fy._slim


def _slim(t):
    d = _orig_slim(t)
    d.update({"exit_t": int(t["exit_t"]) if t.get("exit_t") else None, "entry": t.get("entry"),
              "stop": t.get("stop0") or t.get("stop"), "target": t.get("target"), "exit_price": t.get("exit_price")})
    # what the engine saw when it entered (for the per-trade report and the lessons)
    d.update({k: t.get(k) for k in ("pools", "sweep_ext", "zone", "target_label", "conf_tags", "htf_trend", "m15_trend", "pd_pos",
                                    "open_loc", "mfe", "bars_held", "signal_t", "score", "key_level", "trigger_tf")})
    d["checklist"] = [[c.get("label"), c.get("state")] for c in (t.get("checklist") or []) if c.get("weight")]
    f = t.get("features") or {}
    d["smc"] = {k: f.get(k) for k in ("x_resweep", "x_inducement", "x_fbos", "x_rbos", "multi_sweep", "fast_reclaim")}
    return d


POOL_NAMES = {"PDH": "prior day high", "PDL": "prior day low", "PWH": "prior week high", "PWL": "prior week low",
              "ONH": "overnight high", "ONL": "overnight low", "LOH": "London high", "LOL": "London low", "AH": "Asia high",
              "AL": "Asia low", "ASH": "Asia high", "ASL": "Asia low", "H1H": "1H swing high", "H1L": "1H swing low",
              "EQH": "equal highs", "EQL": "equal lows", "ITH": "15m swing high", "ITL": "15m swing low"}


def _et(ts):
    from zoneinfo import ZoneInfo
    return dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def _report(t, strategy):
    """Plain-language report for one trade: what, when, why it entered, what happened, lessons."""
    d = 1 if t["side"] == "LONG" else -1
    pools = ", ".join(POOL_NAMES.get(p, p) for p in (t.get("pools") or [])) or "a liquidity pool"
    why = [f"Swept the {pools} (extreme {t['sweep_ext']:,.2f})" if t.get("sweep_ext") else f"Swept the {pools}",
           f"{t.get('trigger')} trigger on the {t.get('trigger_tf') or '5m'} chart"
           + (f" (zone {t['zone'][0]:,.2f}-{t['zone'][1]:,.2f})" if t.get("zone") else "")]
    ht = (t.get("htf_trend") or 0) * d
    why.append("1H trend with the trade" if ht > 0 else "1H trend against the trade" if ht < 0 else "1H trend flat")
    if t.get("pd_pos") is not None:
        good = (d == 1 and t["pd_pos"] < 0.5) or (d == -1 and t["pd_pos"] > 0.5)
        why.append(f"{'discount' if t['pd_pos'] < 0.5 else 'premium'} of the 1H range ({'good' if good else 'poor'} location)")
    if (t.get("m15_trend") or 0) * d > 0:
        why.append("15m had already turned its way (late)")
    smc = t.get("smc") or {}
    reads = [txt for k, txt in (("x_resweep", "re-sweep (double tap of the liquidity)"), ("x_inducement", "inducement taken before the raid"),
                                ("x_fbos", "FBOS: raid candle closed back inside the pool"), ("x_rbos", "RBOS: structure broken back before entry"),
                                ("multi_sweep", "stacked pools raided")) if smc.get(k)]
    if reads:
        why.append("price action: " + ", ".join(reads))
    if t.get("conf_tags"):
        why.append("confluences: " + ", ".join(str(x) for x in t["conf_tags"][:6]))
    plan = (f"Stop {t['stop']:,.2f} beyond the sweep ({t['risk_pts']:.2f} pts) -> {t['qty']} micros, ${t['risk_usd']:,.0f} at risk"
            + (" (half size: cold streak)" if t["half"] else "") + f"; target {t['target']:,.2f}"
            + (f" ({t['target_label']})" if t.get("target_label") else "")) if t.get("stop") is not None else ""
    mfe = t.get("mfe") or 0.0
    res = (f"{t['exit']} at {_et(t['exit_t']):%H:%M} after {t.get('bars_held') or '?'} bars: {t['r']:+.2f}R, ${t['pnl']:+,.0f}; "
           f"best point +{mfe:.2f}R")
    lessons = []
    if t["r"] < 0:
        if (t.get("bars_held") or 99) <= 2 and t["exit"] == "STOP":
            lessons.append("stopped almost immediately: the sweep extreme did not hold")
        if mfe < 0.3:
            lessons.append("never moved in favour: no follow-through after the trigger")
        elif mfe >= 1.0:
            lessons.append(f"was +{mfe:.1f}R and still lost: profit given back")
        if ht < 0:
            lessons.append("traded against the 1H trend")
        if (t.get("m15_trend") or 0) * d > 0:
            lessons.append("entered late (15m already turned)")
        if t["risk_pts"] >= 45:
            lessons.append("wide stop: correctly sized down")
    else:
        if t["exit"] == "TARGET":
            lessons.append("reached the draw on liquidity")
        if t["risk_pts"] <= 20:
            lessons.append("tight stop beyond the sweep -> full size paid off")
        if ht > 0:
            lessons.append("with the 1H trend")
        if t["exit"] in ("TIME", "TIME STOP") and t["r"] > 0:
            lessons.append("closed on time: target not reached")
    return {"strategy": strategy, "date": t["day"], "time": f"{_et(t['entry_t']):%H:%M} ET", "side": t["side"],
            "why": why, "plan": plan, "result": res, "lessons": lessons}


def _lessons(trades):
    """Learn from wins and losses: which conditions paid and which hurt, checked separately on 2021-25 and 2026."""
    def feats(t):
        d = 1 if t["side"] == "LONG" else -1
        ht = (t.get("htf_trend") or 0) * d
        pd = t.get("pd_pos")
        return {"Session": "AM (before 12:00)" if _et(t["entry_t"]).hour < 12 else "PM",
                "Trigger": t.get("trigger") or "?",
                "Pool swept": "15m swing (minor)" if set(t.get("pools") or []) <= {"ITH", "ITL"} else "major pool",
                "1H trend": "with" if ht > 0 else "against" if ht < 0 else "flat",
                "15m already turned (late)": "yes" if (t.get("m15_trend") or 0) * d > 0 else "no",
                "Location": "?" if pd is None else ("good (discount long / premium short)" if (d == 1 and pd < 0.5) or (d == -1 and pd > 0.5) else "poor"),
                "Stop size": "under 20 pts" if t["risk_pts"] < 20 else "20-30 pts" if t["risk_pts"] < 30 else "30-45 pts" if t["risk_pts"] < 45 else "45-60 pts",
                "Market regime": t.get("regime") or "?",
                "Day": _et(t["entry_t"]).strftime("%A"),
                "Re-sweep": "yes" if (t.get("smc") or {}).get("x_resweep") else "no",
                "Inducement taken first": "yes" if (t.get("smc") or {}).get("x_inducement") else "no",
                "FBOS (raid closed back inside)": "yes" if (t.get("smc") or {}).get("x_fbos") else "no",
                "RBOS before entry": "yes" if (t.get("smc") or {}).get("x_rbos") else "no"}
    old = [t for t in trades if t["day"] < "2026-01-01"]; new = [t for t in trades if t["day"] >= "2026-01-01"]
    base_o = float(np.mean([t["r"] for t in old])) if old else 0.0; base_n = float(np.mean([t["r"] for t in new])) if new else 0.0
    out = []
    keys = feats(trades[0]).keys() if trades else []
    for k in keys:
        vals = sorted({feats(t)[k] for t in trades})
        for v in vals:
            o = [t["r"] for t in old if feats(t)[k] == v]; n = [t["r"] for t in new if feats(t)[k] == v]
            if len(o) + len(n) < 15:
                continue
            ao = float(np.mean(o)) if o else None; an = float(np.mean(n)) if n else None
            verdict = "not enough data"
            if len(o) >= 25 and len(n) >= 10:
                if ao > base_o and an > base_n:
                    verdict = "better in both periods: lean in"
                elif ao < base_o and an < base_n:
                    verdict = "worse in both periods: avoid or size down"
                else:
                    verdict = "mixed: no reliable lesson"
            out.append({"factor": k, "value": v, "n_2021_25": len(o), "avg_r_2021_25": None if ao is None else round(ao, 3),
                        "win_2021_25": round(100 * float(np.mean([x > 0 for x in o])), 1) if o else None,
                        "n_2026": len(n), "avg_r_2026": None if an is None else round(an, 3),
                        "win_2026": round(100 * float(np.mean([x > 0 for x in n])), 1) if n else None, "verdict": verdict})
    losers = [t for t in trades if t["r"] < 0]; winners = [t for t in trades if t["r"] > 0]
    summary = {
        "baseline_avg_r": {"2021_25": round(base_o, 3), "2026": round(base_n, 3)},
        "losses": {"count": len(losers),
                   "stopped_within_2_bars_pct": round(100 * float(np.mean([(t.get("bars_held") or 99) <= 2 and t["exit"] == "STOP" for t in losers])), 1) if losers else None,
                   "never_reached_0_3R_pct": round(100 * float(np.mean([(t.get("mfe") or 0) < 0.3 for t in losers])), 1) if losers else None,
                   "were_plus_1R_then_lost_pct": round(100 * float(np.mean([(t.get("mfe") or 0) >= 1 for t in losers])), 1) if losers else None},
        "wins": {"count": len(winners),
                 "hit_target_pct": round(100 * float(np.mean([t["exit"] == "TARGET" for t in winners])), 1) if winners else None,
                 "median_bars_held": float(np.median([t.get("bars_held") or 0 for t in winners])) if winners else None,
                 "avg_win_r": round(float(np.mean([t["r"] for t in winners])), 2) if winners else None},
        "how_it_learns": "Each factor's average R is compared with the overall average separately in 2021-25 and in 2026. Only a pattern "
                         "that holds in both periods counts as a lesson; candidate rules are tested on the full history before the bot "
                         "adopts them (never changed from one period alone)."}
    return {"summary": summary, "factors": out}


fy._slim = _slim          # also applied in the spawned workers: they re-import this module


def _stats(T, days):
    if not T:
        return None
    p = np.array([t["pnl"] for t in T]); r = np.array([t["r"] for t in T])
    eq = np.cumsum([d["pnl"] for d in days]); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(eq) else 0.0
    wk = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in T)
    allwk = {dt.date.fromisoformat(d["date"]).isocalendar()[:2] for d in days}
    gl = -p[p < 0].sum()
    return {"trades": len(T), "per_week": round(len(T) / max(len(days) / 5, 1e-9), 2),
            "weeks_2plus_pct": round(100 * sum(wk[w] >= 2 for w in allwk) / max(len(allwk), 1)),
            "win_pct": round(100 * float((p > 0).mean()), 1), "avg_win_r": round(float(r[r > 0].mean()), 2) if (r > 0).any() else None,
            "avg_loss_r": round(float(r[r <= 0].mean()), 2) if (r <= 0).any() else None,
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum()), 2), "max_dd": round(dd, 2),
            "worst_day": round(min(d["pnl"] for d in days), 2), "best_day": round(max(d["pnl"] for d in days), 2),
            "median_stop_pts": round(float(np.median([t["risk_pts"] for t in T])), 1),
            "median_micros": int(np.median([t["qty"] for t in T])), "median_risk_usd": round(float(np.median([t["risk_usd"] for t in T])), 0),
            "half_size_trades": sum(1 for t in T if t["half"])}


def _evals(days):
    from engine.analytics import PLANS, simulate_eval
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    out = {}
    for H, key in ((10, "within_2_weeks"), (20, "within_1_month")):
        c = collections.Counter()
        for i in range(len(days) - H + 1):
            c[simulate_eval(pn[i:i + H], plan, lo[i:i + H])["result"]] += 1
        n = sum(c.values()) or 1
        out[key] = {"starts": n, "pass_pct": round(100 * c["PASS"] / n, 1), "fail_pct": round(100 * c["FAIL"] / n, 1)}
    k, runs = 0, []
    while k < len(days):
        x = simulate_eval(pn[k:], plan, lo[k:])
        runs.append({"start": days[k]["date"], "result": x["result"], "sessions": x["days"]})
        if x["result"] == "OPEN":
            break
        k += x["days"]
    out["back_to_back"] = {"passed": sum(r["result"] == "PASS" for r in runs), "failed": sum(r["result"] == "FAIL" for r in runs), "runs": runs}
    return out


# ------------------------------------------------------------------------------------------------ LIT (live_model.json "lit")
LIT_NAMES = {"pdh": "prior day high", "pdl": "prior day low", "pwh": "prior week high", "pwl": "prior week low",
             "pmh": "prior month high", "pml": "prior month low", "nwog": "weekly opening gap", "ndog": "daily opening gap",
             "bu_h": "equal highs (build-up)", "bu_l": "equal lows (build-up)"}


def _lit_name(n):
    if n in LIT_NAMES:
        return LIT_NAMES[n]
    from engine.lit_live import LBL
    base, hl = (n.rsplit("_", 1) + [""])[:2]
    return f"{LBL.get(base, base)} {'high' if hl == 'h' else 'low' if hl == 'l' else ''}".strip()


def _lit_session(t):
    m = _et(t["entry_t"]).hour * 60 + _et(t["entry_t"]).minute
    return "London (02:00-08:00)" if m < 480 else "NY AM (08:00-12:00)" if m < 720 else "NY PM (12:00-15:30)"


def _report_lit(t, strategy):
    d = 1 if t["side"] == "LONG" else -1
    why = [f"Swept {', '.join(_lit_name(n) for n in t['swept']) or 'a liquidity level'} (extreme {t['sweep_ext']:,.2f}, "
           f"{t['depth_atr']:.2f} ATR past the level)",
           f"Inducement taken first: {t['idm_n']} swing{'s' if t['idm_n'] != 1 else ''} within 1 ATR of the level, "
           "run through on the way to the extreme",
           f"Displacement: biggest candle body {t['disp']:.2f} ATR, then a 5m CISD close through {t['cisd_level']:,.2f}"]
    if t.get("how"):
        why.append("inside the high/low-of-week window (Tue 03:00 - Wed 11:30 ET)")
    entry = ("limit at the CISD level, filled on the tap" if t["entry_kind"] == "limit" else
             f"limit tapped, then a 1m CISD: market entry at the next {t['trigger_tf']} open + 1 tick")
    plan = (f"{entry}. Stop {t['stop']:,.2f}, 1 tick beyond the sweep extreme ({t['risk_pts']:.2f} pts) -> {t['qty']} micros, "
            f"${t['risk_usd']:,.0f} at risk; target {t['target']:,.2f} ({t['target_label']}, {t['plan_rr']:.2f}R); breakeven at 1R, "
            "flat at 15:55 ET")
    mfe = t.get("mfe") or 0.0
    res = (f"{t['exit']} at {_et(t['exit_t']):%H:%M} after {t.get('bars_held') or '?'} {t['trigger_tf']} bars: {t['r']:+.2f}R, "
           f"${t['pnl']:+,.0f}; best point +{mfe:.2f}R")
    lessons = []
    if t["r"] < 0:
        if (t.get("bars_held") or 99) <= 3 and t["exit"] == "STOP":
            lessons.append("stopped almost at once: the sweep extreme did not hold")
        if mfe < 0.3:
            lessons.append("never moved in favour after the CISD")
        elif mfe >= 0.9:
            lessons.append(f"reached +{mfe:.1f}R and still lost")
        if t["risk_pts"] >= 40:
            lessons.append("wide stop: sized down by the 800x20/stop rule")
    else:
        if t["exit"] == "TARGET":
            lessons.append("the VIX one-day move was reached" if "VIX" in t["target_label"] and "banked" not in t["target_label"]
                           else "banked at 8R on the way to the VIX band")
        if t["exit"] == "BE":
            lessons.append("breakeven after +1R: no loss")
        if t["exit"] == "TIME" and t["r"] > 0:
            lessons.append("closed at 15:55 in profit, target not reached")
    if d == 1 and t.get("how") is False:
        pass
    return {"strategy": strategy, "date": t["day"], "time": f"{_et(t['entry_t']):%H:%M} ET", "side": t["side"],
            "why": why, "plan": plan, "result": res, "lessons": lessons}


def _lessons_lit(trades):
    """LIT factors, 2021-25 vs 2026 (LIT is judged on 2026; 2021-25 had no 1m bars, so its entries are 5m)."""
    def feats(t):
        return {"Session": _lit_session(t), "Side": t["side"], "Execution bars": t["trigger_tf"],
                "Stop size": "under 20 pts" if t["risk_pts"] < 20 else "20-40 pts" if t["risk_pts"] < 40 else "40-80 pts",
                "Day": _et(t["entry_t"]).strftime("%A"), "High/low-of-week window": "yes" if t.get("how") else "no",
                "Target banked at 8R": "yes" if "banked" in (t.get("target_label") or "") else "no",
                "Swept a daily/weekly level": "yes" if set(t["swept"]) & {"pdh", "pdl", "pwh", "pwl", "pmh", "pml"} else "no",
                "Swept a session box": "yes" if any(n[:3] in ("asi", "lon", "ny8", "ny9", "pre") for n in t["swept"]) else "no",
                "Entry": t["entry_kind"]}
    old = [t for t in trades if t["day"] < "2026-01-01"]; new = [t for t in trades if t["day"] >= "2026-01-01"]
    base_o = float(np.mean([t["r"] for t in old])) if old else 0.0; base_n = float(np.mean([t["r"] for t in new])) if new else 0.0
    out = []
    for k in (feats(trades[0]).keys() if trades else []):
        for v in sorted({feats(t)[k] for t in trades}):
            o = [t["r"] for t in old if feats(t)[k] == v]; n = [t["r"] for t in new if feats(t)[k] == v]
            if len(o) + len(n) < 15:
                continue
            ao = float(np.mean(o)) if o else None; an = float(np.mean(n)) if n else None
            verdict = "not enough data"
            if len(o) >= 25 and len(n) >= 10:
                verdict = ("better in both periods: lean in" if ao > base_o and an > base_n else
                           "worse in both periods: avoid or size down" if ao < base_o and an < base_n else "mixed: no reliable lesson")
            out.append({"factor": k, "value": v, "n_2021_25": len(o), "avg_r_2021_25": None if ao is None else round(ao, 3),
                        "win_2021_25": round(100 * float(np.mean([x > 0 for x in o])), 1) if o else None,
                        "n_2026": len(n), "avg_r_2026": None if an is None else round(an, 3),
                        "win_2026": round(100 * float(np.mean([x > 0 for x in n])), 1) if n else None, "verdict": verdict})
    losers = [t for t in trades if t["r"] < 0]; winners = [t for t in trades if t["r"] > 0]
    summary = {
        "baseline_avg_r": {"2021_25": round(base_o, 3), "2026": round(base_n, 3)},
        "losses": {"count": len(losers),
                   "stopped_within_2_bars_pct": round(100 * float(np.mean([(t.get("bars_held") or 99) <= 2 and t["exit"] == "STOP" for t in losers])), 1) if losers else None,
                   "never_reached_0_3R_pct": round(100 * float(np.mean([(t.get("mfe") or 0) < 0.3 for t in losers])), 1) if losers else None,
                   "were_plus_1R_then_lost_pct": round(100 * float(np.mean([(t.get("mfe") or 0) >= 1 for t in losers])), 1) if losers else None},
        "wins": {"count": len(winners),
                 "hit_target_pct": round(100 * float(np.mean([t["exit"] == "TARGET" for t in winners])), 1) if winners else None,
                 "median_bars_held": float(np.median([t.get("bars_held") or 0 for t in winners])) if winners else None,
                 "avg_win_r": round(float(np.mean([t["r"] for t in winners])), 2) if winners else None},
        "how_it_learns": "Each factor's average R is compared with the overall average separately in 2021-25 and in 2026. LIT is "
                         "judged on 2026 (owner order 2026-10-18); 2021-25 has no 1m bars, so there it enters on 5m bars and is a "
                         "reference only. A rule is adopted only after it is picked on Jan-Jun 2026 and holds on Jul-Oct 2026."}
    return {"summary": summary, "factors": out}


def main_lit(lm):
    """The LIT replay (engine/lit.py run_x on the whole history = what engine/lit_live.py does every poll, checked by
    tests/test_lit_live.py) in the same bundle shape as the engine's."""
    from engine import lit
    from engine.data import load
    from tools import lit_final as F
    t0 = time.time()
    P = {**lit.DEFAULTS, **(lm.get("lit") or {})}
    T = sorted(F.run(P), key=lambda t: t["entry_t"])
    M, C = F.market(P["ref"], P["extra_boxes"])
    cand = {(z["i"], z["dir"]): z for z in C}
    sess = list(F.SESS)
    label = lm.get("label") or "LIT"
    trades = []
    for t in T:
        z = cand[(t["i"], t["dir"])]
        d, q = int(t["dir"]), int(t["qty"])
        pts = (t["pnl"] / q + lit.COMM) / lit.PV
        exit_px = round((t["entry_px"] + d * pts) * 4) / 4
        rr = (t["target_px"] - t["entry_px"]) * d / t["risk_pts"]
        banked = bool(P.get("max_rr")) and abs(rr - P["max_rr"]) < 0.01
        tl = ("VIX band" if "vix" in P["classes"] else "level") + (f" (banked at {P['max_rr']:g}R)" if banked else "")
        fill_limit = abs(t["entry_px"] - min(float(z["ref_d"]), z["trig_c"]) * d) < 1e-6
        x = {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "side": "LONG" if d == 1 else "SHORT",
             "entry": t["entry_px"], "stop": t["stop_px"], "target": t["target_px"], "exit_price": exit_px,
             "exit": "TIME" if t["exit"] == "EOD" else t["exit"], "trigger": "LIT", "grade": None, "regime": None,
             "risk_pts": round(t["risk_pts"], 2), "qty": q, "risk_usd": round(t["risk_usd"], 2), "r": round(t["r"], 3),
             "pnl": round(t["pnl"], 2), "half": bool(t.get("half")), "low": t["low"],
             "pools": [_lit_name(n) for n in z["swept"]], "swept": z["swept"], "sweep_ext": round(z["ext_d"] * d, 2), "zone": None,
             "target_label": tl, "plan_rr": round(rr, 2),
             "conf_tags": [f"inducement x{len(z['idm_a'])}", f"displacement {z['disp']:.2f} ATR", f"sweep depth {z['depth_atr']:.2f} ATR"]
                          + (["high/low-of-week window"] if z["how"] else []) + ([f"{t.get('tf', 5)}m execution"]),
             "htf_trend": None, "m15_trend": None, "pd_pos": None, "open_loc": None, "mfe": t.get("mfe"), "bars_held": t.get("bars_held"),
             "checklist": [], "trigger_tf": f"{t.get('tf', 5)}m", "score": None, "smc": {},
             "depth_atr": z["depth_atr"], "disp": z["disp"], "idm_n": sum(1 for dd, aa in z["idm_a"] if dd <= (P["idm_a"] or [9, 999])[0] and aa <= (P["idm_a"] or [9, 999])[1]),
             "how": bool(z["how"]), "cisd_level": round(float(z["ref_d"]) * d, 2), "entry_kind": "limit" if fill_limit else "1m CISD"}
        x["report"] = _report_lit(x, label)
        trades.append(x)
    by = collections.defaultdict(list)
    for t in trades:
        by[t["day"]].append(t)
    days = []
    for dd in sess:
        cum = low = 0.0
        for t in by.get(dd, []):
            low = min(low, cum + t["low"]); cum += t["pnl"]; low = min(low, cum)
        days.append({"date": dd, "pnl": round(cum, 2), "low": round(low, 2), "trades": len(by.get(dd, []))})
    for t in trades:
        t.pop("low")
    first, last = sess[0], sess[-1]
    spans = [("2026 YTD", "2026-01-01", last), ("2026 H1 (picked on)", "2026-01-01", "2026-06-30"),
             ("2026 H2 (check)", "2026-07-01", last), ("2021-25 (reference)", "2021-01-01", "2025-12-31")] \
        + [(str(y), f"{y}-01-01", f"{y}-12-31") for y in range(int(first[:4]), int(last[:4]) + 1)] + [("All years", first, last)]
    periods = {}
    for name, lo, hi in spans:
        T2 = [t for t in trades if lo <= t["day"] <= hi]; D2 = [d for d in days if lo <= d["date"] <= hi]
        if D2:
            st = _stats(T2, D2) or {}
            if st:
                st["per_month"] = round(st["net"] / max(len(D2) / 21.0, 1e-9), 0)
            periods[name] = {"from": D2[0]["date"], "to": D2[-1]["date"], **st, "eval": _evals(D2)}
    months = collections.OrderedDict()
    for t in trades:
        m = months.setdefault(t["day"][:7], {"net": 0.0, "trades": 0, "wins": 0})
        m["net"] = round(m["net"] + t["pnl"], 2); m["trades"] += 1; m["wins"] += t["pnl"] > 0
    buckets = []
    for a, b in ((0, 20), (20, 30), (30, 45), (45, 81)):
        s_ = [t for t in trades if a <= t["risk_pts"] < b]
        if s_:
            r = np.array([t["r"] for t in s_])
            buckets.append({"stop_pts": f"{a}-{b if b < 81 else 80}", "trades": len(s_), "win_pct": round(100 * float((r > 0).mean()), 1),
                            "avg_r": round(float(r.mean()), 3), "median_micros": int(np.median([t["qty"] for t in s_])),
                            "median_risk_usd": round(float(np.median([t["risk_usd"] for t in s_])), 0)})
    nq = load("NQ", "5m")
    bundle = {
        "meta": {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "strategy": label, "chosen": lm.get("chosen"),
                 "model": "lit", "params": P, "equity_filter": None, "rules": "STRATEGY.md", "judged_on": lm.get("judged_on"),
                 "data": {"source": "TradingView CME NQ1! continuous futures, 5-minute bars (data/NQ_5m.csv); 1-minute bars for 2026 "
                                    "(data/NQ_1m.csv) for the entry and trade management; VIX daily (data/VIX_1d.csv)",
                          "first_session": first, "last_session": last, "sessions": len(sess), "bars": int(len(nq.t))},
                 "costs": {"instrument": "MNQ micro ($2/pt)", "commission_round_trip_per_micro": lit.COMM, "slippage_pts": lit.SLIP},
                 "sizing": {"rule": lm.get("size_rule"), "eval_safe_option": lm.get("eval_safe_option")},
                 "method": "LIT replay (engine/lit.py run_x, every value known at the close of its bar). The live loop runs the same "
                           "code on the recent bars (engine/lit_live.py): tests/test_lit_live.py replays every 2026 session and gets the "
                           "same trades. 2026 days with full 1m bars enter and are managed on 1m bars; 2021-25 (no 1m data) on 5m bars, "
                           "so 2021-25 is a reference line, not a check of the 1m entry. Evals use the MFFU Builder 50K rules ($3k "
                           "target, $2k end-of-day trailing max loss locking at $50,100).",
                 "seconds": round(time.time() - t0)},
        "periods": periods, "months": months, "stop_buckets": buckets, "lessons": _lessons_lit(trades), "days": days, "trades": trades,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, separators=(",", ":"))
    p26 = periods.get("2026 YTD", {})
    print(f"wrote {OUT} (LIT): {len(trades)} trades, {len(days)} sessions | 2026: {p26.get('trades')} trades, PF {p26.get('pf')}, "
          f"net {p26.get('net')}, max DD {p26.get('max_dd')} | {time.time() - t0:.0f}s")


def main(procs=11):
    lm0 = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    if lm0.get("model") == "lit":
        return main_lit(lm0)
    from multiprocessing import Pool

    from engine import equity_filter as eqf
    from engine import sizing as szm
    from engine.data import load
    from tools.strategy_lab import COMMISSION_RT, SLIP_PTS
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    params, eqf_cfg, sizing_cfg = lm["params"], lm.get("equity_filter"), lm.get("sizing")
    t0 = time.time()
    with Pool(procs) as pool:
        outs = pool.map(fy.bt, fy.live_jobs(params, "export"), chunksize=4)
    res = fy.merge(outs, "export")
    sess = sorted({d["date"] for d in res["days"]})
    T = sorted(res["trades"], key=lambda t: t["entry_t"])
    led = [{"entry_t": t["entry_t"], "exit_t": t["exit_t"], "r": t["r"]} for t in T]
    tmp = os.path.join(ROOT, "research", "lab", "_export_ledger.json")
    json.dump(led, open(tmp, "w"))
    trades = []
    for t in T:
        st = eqf.status(eqf_cfg, before_t=t["entry_t"], path=tmp)
        m = st.get("mult", 1.0)
        if m <= 0:
            continue
        rq = szm.route_qty(int(t["qty"] or 0), t, m, sizing_cfg, params)      # cold x late; the fast-eval press is not in the headline
        q, m = rq["qty"], rq["mult"]
        k = q / t["qty"] if t["qty"] else m
        trades.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "side": "LONG" if t["dir"] == 1 else "SHORT",
                       "entry": t.get("entry"), "stop": t.get("stop"), "target": t.get("target"), "exit_price": t.get("exit_price"),
                       "exit": t.get("exit"), "trigger": t.get("trigger"), "grade": t.get("grade"), "regime": t.get("regime"),
                       "risk_pts": round(t["risk_pts"], 2), "qty": q, "risk_usd": round(t["risk_pts"] * 2.0 * q, 2),
                       "r": round(t["r"], 3), "pnl": round(t["pnl"] * k, 2), "half": m < 1,
                       "low": -min(t["mae"], max(1.0, -t["r"])) * t["risk_pts"] * 2.0 * q,
                       **{f: t.get(f) for f in ("pools", "sweep_ext", "zone", "target_label", "conf_tags", "htf_trend", "m15_trend",
                                                "pd_pos", "open_loc", "mfe", "bars_held", "checklist", "trigger_tf", "score", "smc")}})
    os.remove(tmp)
    for t in trades:
        t["report"] = _report(t, lm.get("label") or "Liquidity Engine")
    by = collections.defaultdict(list)
    for t in trades:
        by[t["day"]].append(t)
    days = []
    for d in sess:
        cum = low = 0.0
        for t in by.get(d, []):
            low = min(low, cum + t["low"]); cum += t["pnl"]; low = min(low, cum)
        days.append({"date": d, "pnl": round(cum, 2), "low": round(low, 2), "trades": len(by.get(d, []))})
    for t in trades:
        t.pop("low")
    periods = {}
    first, last = sess[0], sess[-1]
    spans = [("2026 YTD", "2026-01-01", last)] + [(str(y), f"{y}-01-01", f"{y}-12-31") for y in range(int(first[:4]), int(last[:4]) + 1)] \
        + [("All years", first, last)]
    for name, lo, hi in spans:
        T2 = [t for t in trades if lo <= t["day"] <= hi]; D2 = [d for d in days if lo <= d["date"] <= hi]
        if D2:
            periods[name] = {"from": D2[0]["date"], "to": D2[-1]["date"], **(_stats(T2, D2) or {}), "eval": _evals(D2)}
    months = collections.OrderedDict()
    for t in trades:
        m = months.setdefault(t["day"][:7], {"net": 0.0, "trades": 0, "wins": 0})
        m["net"] = round(m["net"] + t["pnl"], 2); m["trades"] += 1; m["wins"] += t["pnl"] > 0
    buckets = []
    for a, b in ((0, 20), (20, 30), (30, 45), (45, 61)):
        s = [t for t in trades if a <= t["risk_pts"] < b]
        if s:
            r = np.array([t["r"] for t in s])
            buckets.append({"stop_pts": f"{a}-{b if b < 61 else 60}", "trades": len(s), "win_pct": round(100 * float((r > 0).mean()), 1),
                            "avg_r": round(float(r.mean()), 3), "median_micros": int(np.median([t["qty"] for t in s])),
                            "median_risk_usd": round(float(np.median([t["risk_usd"] for t in s])), 0)})
    nq = load("NQ", "5m")
    bundle = {
        "meta": {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "strategy": lm.get("label"), "chosen": lm.get("chosen"),
                 "params": params, "equity_filter": eqf_cfg, "rules": "STRATEGY.md",
                 "data": {"source": "TradingView CME NQ1! continuous futures, 5-minute bars (data/NQ_5m.csv)",
                          "first_session": first, "last_session": last, "sessions": len(sess), "bars": int(len(nq.t))},
                 "costs": {"instrument": "MNQ micro ($2/pt)", "commission_round_trip_per_micro": COMMISSION_RT, "slippage_pts": SLIP_PTS},
                 "sizing": sizing_cfg,
                 "method": "Exact live-loop replay: for every session the engine sees only the last 20 days of bars (as the live bot), "
                           "cold-streak and late-entry sizing applied from what was known at entry (no look-ahead). Evals use the "
                           "MFFU Builder 50K rules ($3k target, $2k end-of-day trailing max loss locking at $50,100). The fast-eval "
                           "press, when on, is not in this headline: see research run risk_fast_press1000.",
                 "seconds": round(time.time() - t0)},
        "periods": periods, "months": months, "stop_buckets": buckets, "lessons": _lessons(trades), "days": days, "trades": trades,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, separators=(",", ":"))
    p26 = periods.get("2026 YTD", {})
    print(f"wrote {OUT}: {len(trades)} trades, {len(days)} sessions | 2026: {p26.get('trades')} trades, PF {p26.get('pf')}, "
          f"net {p26.get('net')}, max DD {p26.get('max_dd')} | {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
