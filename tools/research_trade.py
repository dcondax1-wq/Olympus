"""Trade-construction research (stops, targets, trade management, bias and filters, timing) on today's live strategy.

Every experiment below is stored in the run library (research/runs/, tools/runlib.py) with its trades, days and verdict.
Write-ups: research/writeups/ (leakage-check, stops, targets, management, bias-filters, trade-construction-summary).

  python tools/research_trade.py all              # reproduce every run (replays are cached in research/runs/_cache)
  python tools/research_trade.py run stp_buf15    # one or more runs by id
  python tools/research_trade.py list             # ids, methods and params
  python tools/research_trade.py table [family]   # headline table of the stored runs vs the right baseline

Three ways a run is computed (the method is written into each run's notes and "method" field):
  replay  - the exact live-loop replay (tools/runlib.replay: for every session the engine sees the last 20 days, as the
            live bot). The reference method; every number in the write-ups' headline tables comes from it.
  exitsim - management-only settings (breakeven, profit locks, time stop, giveback, exits in front of the pool): the
            entries cannot change (max 1 trade a day is decided before any management), so the exits are re-simulated
            bar by bar on the baseline replay's own entries with a line-by-line copy of the engine's exit block
            (sim_exit below). It reproduces the baseline replay trade for trade (768 of 768: exit, time, R, $).
  screen  - one engine pass over the whole history (2021-10 .. 2026-10) instead of one 20-day window per session. It
            matches the live-loop replay on 766 of 768 baseline trades (+14 extra trades), at ~1/30 of the CPU. Used to
            screen settings that change entries; promising ones are confirmed with a replay. Screen runs are compared
            with the screen baseline (run "screen_baseline"), never with the replay baseline.

Judging (CLAUDE.md): adopt only if better in 2026 AND 2021-25 (net and PF) with 2+ trades a week in both.
Real CME NQ1! 5m history only (data/NQ_5m.csv). Costs (commission + 1 tick slippage) included everywhere.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import runlib as rl  # noqa: E402

SCREEN_CACHE = os.path.join(rl.CACHE, "screen")
PROCS = 3
LEAK_NOTE = ("Leakage check (run leak_*): memory_seed and exit_learn have no effect on any replay (identical trades), "
             "so every comparison uses the live settings as they are.")

# ------------------------------------------------------------------------------------------------ experiments
# id, family, method, params, title, question (+ optional: rule = post-hoc rule name, sim = exit-simulator params,
# status / verdict overrides, note). Titles and questions are plain language for the owner (phone).
E = []


def X(id, family, method, params, title, question, **kw):
    E.append({"id": id, "family": family, "method": method, "params": params, "title": title, "question": question, **kw})


# ---- 0. leakage check (exact replays)
X("leak_memseed_off", "other", "replay", {"memory_seed": False}, "Leakage check: trade memory switched off",
  "Does the backtest read data/memory.db (paper trades, possibly from the future) and change any trade?", status="info")
X("leak_exitlearn_off", "other", "replay", {"exit_learn": False}, "Leakage check: exit learner switched off",
  "Does the walk-forward exit learner ever act in the live-loop replay?", status="info")
X("leak_both_off", "other", "replay", {"memory_seed": False, "exit_learn": False}, "Leakage check: memory and learner off",
  "Leak-free setting (what the cloud monitor effectively runs): same trades as the baseline?", status="info")
X("screen_baseline", "other", "screen", {}, "Screen reference: live strategy in one pass over 5 years",
  "What does the fast one-pass backtest give for today's live settings (the yardstick for every screen run)?",
  status="info")

# ---- 1. stops
for m in (0.5, 1.5, 2.0, 3.0):
    X(f"stp_buf{int(m * 10):02d}", "stops", "screen", {"stop_buffer_mult": m},
      f"Stop {2 * m:g} pts beyond the sweep (today 2)", f"Is a {2 * m:g}-point buffer beyond the sweep extreme better than 2?")
for v in (45, 50, 70, 80):
    X(f"stp_max{v}", "stops", "screen", {"spec": {"max_stop": float(v)}}, f"Widest stop {v} pts (today 60)",
      f"Should the widest allowed stop be {v} points instead of 60?")
for v in (8, 12, 15):
    X(f"stp_min{v}", "stops", "screen", {"spec": {"min_stop": float(v)}}, f"Tightest stop {v} pts (today 10)",
      f"Should the tightest stop be {v} points instead of 10?")
X("stp_ifvg", "stops", "screen", {"stop_mode": "ifvg"}, "Stop beyond the inverted gap, not the sweep",
  "Check: is a stop beyond the IFVG (closer) better than beyond the sweep extreme?")
for a in (0.15, 0.25, 0.5):
    X(f"stp_atr{int(a * 100):03d}", "stops", "screen", {"stop_buf_atr": a},
      f"Stop buffer = {a:g} x ATR beyond the sweep", f"Does a buffer that grows with volatility ({a:g} x the 5m ATR) beat a fixed 2 points?")

# ---- 2. targets
for v in (1.2, 2.0, 2.5, 3.0):
    X(f"tgt_minrr{int(v * 10)}", "targets", "screen", {"min_rr": v}, f"Draw must be at least {v:g}R away (today 1.5R)",
      f"Should the target pool be at least {v:g}R away instead of 1.5R?")
for v in (3, 4, 6, 8):
    X(f"tgt_maxrr{v}", "targets", "screen", {"max_rr": float(v)}, f"Bank profit at {v}R on the way (today 5R)",
      f"When the draw is far, bank at {v}R instead of 5R?")
X("tgt_major_next", "targets", "screen", {"target_mode": "major_next"}, "Aim for the second major pool, not the first",
  "Skip the nearest major pool and aim for the next one?")
for v in (0, 2):
    X(f"tgt_touch{v}", "targets", "exitsim", {"touch_ticks": v}, f"Target fills after {v} tick{'s' if v != 1 else ''} through (today 1)",
      f"Does the target order fill differently if it needs {v} ticks of trade-through?", sim={"touch_ticks": v})
for v in (4, 8, 16):
    X(f"tgt_front{v}", "targets", "exitsim", {"target_front_ticks": v}, f"Exit {v} ticks in front of the pool (today 1)",
      f"Does exiting {v} ticks ({v / 4:g} pts) before the pool catch more winners?", sim={"front_ticks": v},
      note="target_front_ticks is not an engine parameter: tested with the exit simulator only (no engine change needed, "
           "the effect is tiny).")

# ---- 3. management (exit simulator on the replay's entries; exact for these settings)
for v in (0, 0.75, 1.25, 1.5, 2.0):
    X(f"mgt_be{int(v * 100):03d}", "management", "exitsim", {"be_at_r": v},
      "No breakeven move" if v == 0 else f"Breakeven at +{v:g}R (today +1R)",
      "Should the stop ever move to breakeven?" if v == 0 else f"Move the stop to breakeven at +{v:g}R instead of +1R?",
      sim={"be_at_r": v})
for v in (0.75, 1.5):
    X(f"mgt_betrend{int(v * 100):03d}", "management", "exitsim", {"be_at_r_trending": v},
      f"Breakeven at +{v:g}R on trending days only", f"On trending days, move to breakeven at +{v:g}R?", sim={"be_at_r_trending": v})
for a, r in ((1.5, 0.5), (2.0, 0.5), (2.0, 1.0), (3.0, 1.0), (3.0, 1.5)):
    X(f"mgt_lock{int(a * 10)}_{int(r * 10)}", "management", "exitsim", {"lock_at_r": a, "lock_r": r},
      f"Lock +{r:g}R once the trade is +{a:g}R", f"After +{a:g}R, should the stop lock in +{r:g}R?",
      sim={"lock_at_r": a, "lock_r": r})
for v in (0, 15, 20, 45, 60):
    X(f"mgt_ts{v}", "management", "exitsim", {"time_stop_min": v}, "No time stop" if v == 0 else f"Time stop after {v} min (today 30)",
      "Should slow trades be cut at all?" if v == 0 else f"Cut a trade that is not +0.5R after {v} minutes instead of 30?",
      sim={"time_stop_min": v})
for v in (0.25, 1.0):
    X(f"mgt_tsr{int(v * 100):03d}", "management", "exitsim", {"time_stop_r_sim": v}, f"Time stop needs +{v:g}R in 30 min (today +0.5R)",
      f"Should the 30-minute check ask for +{v:g}R instead of +0.5R?", sim={"time_stop_r": v},
      note="The engine's time stop threshold (0.5R) is fixed in code: tested with the exit simulator only.")
for v in (0.75, 1.0):
    X(f"mgt_gb{int(v * 100):03d}", "management", "exitsim", {"exit_giveback_r": v}, f"Giveback exit after +{v:g}R (today +0.5R)",
      f"Exit on a close back through entry only after the trade was +{v:g}R?", sim={"exit_giveback_r": v})
X("mgt_nogb", "management", "exitsim", {"exit_rules": ""}, "No giveback exit", "Is the giveback exit worth having?",
  sim={"giveback": False})
X("mgt_ifvgfail", "management", "exitsim", {"ifvg_fail_exit": True}, "Exit when price closes back through the gap",
  "Exit as soon as a candle closes back through the far side of the inverted gap?", sim={"ifvg_fail_exit": True})
X("mgt_newsflat0", "management", "exitsim", {"news_flatten_min": 0}, "Keep trades open into news",
  "Does closing 5 minutes before high-impact news matter?", sim={"news_flatten_min": 0})

# ---- 4. bias and filters (screen = one pass; post-hoc = skip rule on the replay's trades, no replacement trade)
X("flt_regime_skip", "filters", "screen", {"regime_mode": "skip"}, "Skip trending markets (today: half size)",
  "Stand aside in a trending market instead of trading half size?")
X("flt_regime_off", "filters", "screen", {"regime_er10_max": 0}, "No trending-market rule", "Trade trending markets at full size?")
for v in (0, 1.2, 2.0):
    X(f"flt_range{int(v * 10)}", "filters", "screen", {"day_range_max": float(v)},
      "No big-range-day block" if v == 0 else f"Block entries once the day's range is {v:g}x normal (today 1.6x)",
      "Is the big-range-day block useful?" if v == 0 else f"Block new entries at {v:g}x the 20-day average range instead of 1.6x?")
for v in (25, 30):
    X(f"flt_vixmax{v}", "filters", "screen", {"vix_max": float(v)}, f"Skip days with VIX above {v}", f"Stand aside when yesterday's VIX closed above {v}?")
X("flt_vixmin13", "filters", "screen", {"vix_min": 13.0}, "Skip days with VIX below 13", "Stand aside in very quiet markets (VIX < 13)?")
X("flt_news_off", "filters", "screen", {"news_filter": False}, "No news blackout", "Is the news blackout (15 min before to 30 min after) useful?")
X("flt_arm_minor_off", "filters", "screen", {"arm_minor": False}, "Only major pools arm a setup",
  "Ignore sweeps of plain 15-minute swings?")
X("flt_min_score0", "filters", "screen", {"min_score": 0}, "Confluence score 0 is enough (today 1)", "Take setups with a confluence score of 0?")
X("flt_min_score2", "filters", "screen", {"min_score": 2}, "Confluence score 2 needed (today 1)", "Require a confluence score of 2?")
X("flt_long_only", "filters", "screen", {"short": False}, "Longs only", "Info: how do longs alone do?", status="info")
X("flt_short_only", "filters", "screen", {"long": False}, "Shorts only", "Info: how do shorts alone do?", status="info")
X("bias_w_htf0", "bias", "screen", {"w_htf": 0}, "Ignore the 1H trend", "Is the 1H trend point in the score useful?")
X("bias_w_htf2", "bias", "screen", {"w_htf": 2}, "1H trend counts double", "Should the 1H trend weigh more?")
X("bias_w_pd0", "bias", "screen", {"w_pd": 0}, "Ignore discount/premium", "Is the 1H discount/premium point useful?")
X("bias_w_m15_0", "bias", "screen", {"w_m15": 0}, "No penalty for a late 15m entry", "Is the 'late entry' penalty useful?")
X("bias_w_dol1", "bias", "screen", {"w_dol": 1}, "Bonus when trading toward the nearest major pool",
  "Should trades toward the nearest major untaken pool score a point?")
X("bias_w_dolm1", "bias", "screen", {"w_dol": -1}, "Penalty when trading toward the nearest major pool",
  "Trades toward the nearest major pool did worse after the fact: should they lose a point?")
X("bias_pdc1", "bias", "screen", {"w_pdc": 1}, "Score point for fading yesterday's candle",
  "Longs after a down day and shorts after an up day did better in both periods: should that score a point?")
X("bias_pwmid1", "bias", "screen", {"w_pwmid": 1}, "Score point for the prior-week side",
  "Longs above / shorts below last week's midpoint did better: should that score a point?")
X("bias_counter_cap3", "bias", "screen", {"counter_rr_cap": 3.0}, "Nearer target (3R) when fading higher-timeframe order flow",
  "When the 1D/4H/1H/15m gaps point against the trade, bank at 3R instead of aiming far?")
X("bias_pdc_skip", "bias", "posthoc", {}, "Info: only trades that fade yesterday's candle",
  "Hard filter version: what if trades that follow yesterday's candle were skipped?", rule="skip_follow_pd", status="info")
X("bias_pwmid_skip", "bias", "posthoc", {}, "Info: only trades on the prior-week side",
  "Hard filter version: what if trades against the prior-week midpoint side were skipped?", rule="skip_against_pwmid", status="info")
X("bias_wkopen_skip", "bias", "posthoc", {}, "Info: only longs below / shorts above the weekly open",
  "Hard filter: trade only longs below this week's open and shorts above it?", rule="skip_against_wkopen", status="info")
X("bias_smt_only", "bias", "posthoc", {}, "Info: only trades with NQ/ES SMT divergence",
  "Does SMT divergence (ES fails to make the new extreme) pick better trades? ES data starts 2025-04.",
  rule="skip_no_smt", status="info")

# ---- 5. timing
X("tim_am_only", "timing", "screen", {"entry_windows": [[570, 690]]}, "Morning killzone only (09:30-11:30)",
  "Trade only the morning window?")
X("tim_pm_only", "timing", "screen", {"entry_windows": [[810, 930]]}, "Afternoon killzone only (13:30-15:30)",
  "Trade only the afternoon window?")
X("tim_ext", "timing", "screen", {"entry_windows": [[570, 720], [780, 930]]}, "Wider windows (09:30-12:00, 13:00-15:30)",
  "Allow entries in wider windows?")
X("tim_am_late", "timing", "screen", {"entry_windows": [[600, 690], [810, 930]]}, "Morning window starts 10:00",
  "Skip the first 30 minutes after the open?")
for v in (30, 45, 90):
    X(f"tim_armexp{v}", "timing", "screen", {"arm_expiry_min": v}, f"Setup expires after {v} min (today 60)",
      f"Let an armed setup wait {v} minutes for its trigger instead of 60?")
for v, lab in ((420, "07:00"), (540, "09:00"), (570, "09:30")):
    X(f"tim_armstart{v}", "timing", "screen", {"arm_start": v}, f"Sweeps count from {lab} (today 08:00)",
      f"Should only sweeps from {lab} arm a setup?")


# ------------------------------------------------------------------------------------------------ exit simulator
_SIM = {}


def _sim_data():
    if not _SIM:
        from engine import news as _news
        from engine.data import load
        b = load("NQ", "5m")
        _SIM.update(B=b, idx={int(t): i for i, t in enumerate(b.t)},
                    ev=np.array([e["t"] for e in _news.historical_events(("high",))], dtype=np.int64))
    return _SIM


SIM_DEF = {"be_at_r": 1.0, "be_at_r_trending": 0, "lock_at_r": 0, "lock_r": 0, "time_stop_min": 30, "time_stop_r": 0.5,
           "exit_giveback_r": 0.5, "giveback": True, "ifvg_fail_exit": False, "news_flatten_min": 5, "touch_ticks": 1,
           "front_ticks": 1, "flat_mod": 955}


def sim_exit(t, P):
    """Re-run one replay trade's exit with management settings P: a line-by-line copy of engine/model.py run()
    'manage open position' (stop first, then target, flat time, news flatten, time stop, IFVG fail, giveback; breakeven and
    lock decided on the bar's close for the next bar). Entry, stop, target, size are the replay's."""
    S = _sim_data()
    B, ev = S["B"], S["ev"]
    p = {**SIM_DEF, **P}
    tick, slip = 0.25, 0.25
    d = int(t["dir"]); i0 = S["idx"][int(t["entry_t"])]
    e, stop, target, q = float(t["entry"]), float(t["stop"]), float(t["target"]), int(t["qty"])
    risk = (e - stop) * d
    if p["front_ticks"] != 1 and "cap" not in str(t.get("target_label") or ""):
        target -= d * (p["front_ticks"] - 1) * tick              # pool targets sit 1 tick in front of the pool today
    mfe = mae = 0.0
    managed, gb_seen = False, False
    tday, n, i = B.tday[i0], len(B.t), i0
    zone = t.get("zone")
    while True:
        o, h, l, c = B.o[i], B.h[i], B.l[i], B.c[i]
        mod, t_end = int(B.mod[i]), int(B.t[i]) + 300
        mae = max(mae, ((e - l) if d == 1 else (h - e)) / risk)
        mfe = max(mfe, ((h - e) if d == 1 else (e - l)) / risk)
        gb_cond = mfe >= p["exit_giveback_r"] and c * d < e * d
        gb_now = p["giveback"] and gb_cond and not gb_seen       # an exit signal acts on its first firing only
        gb_seen = gb_seen or gb_cond
        low_d, high_d, stop_d = (l if d == 1 else -h), (h if d == 1 else -l), stop * d
        if low_d <= stop_d:
            px, why = (min(o * d, stop_d) - slip) * d, ("BE/TRAIL" if managed else "STOP"); break
        if high_d >= target * d + p["touch_ticks"] * tick:
            px, why = target, "TARGET"; break
        if mod >= p["flat_mod"] or i + 1 >= n or B.tday[i + 1] != tday:
            px, why = c - d * slip, "TIME"; break
        if p["news_flatten_min"] and np.any((ev > t_end) & (ev <= t_end + p["news_flatten_min"] * 60)):
            px, why = c - d * slip, "NEWS FLAT"; break
        if p["time_stop_min"] and (i - i0 + 1) * 300 >= p["time_stop_min"] * 60 and mfe < p["time_stop_r"]:
            px, why = c - d * slip, "TIME STOP"; break
        if p["ifvg_fail_exit"] and zone and i > i0 and (c - zone[0 if d == 1 else 1]) * d < 0:
            px, why = c - d * slip, "IFVG FAIL"; break
        if gb_now:
            px, why = c - d * slip, "SIGNAL giveback"; break
        new = stop_d
        be_r = p["be_at_r_trending"] if (t.get("regime") == "trending" and p["be_at_r_trending"]) else p["be_at_r"]
        if be_r and mfe >= be_r:
            new = max(new, e * d + tick)
        if p["lock_at_r"] and mfe >= p["lock_at_r"]:
            new = max(new, e * d + p["lock_r"] * risk)
        if new > stop_d:
            stop, managed = new * d, True
        i += 1
    pnl = (px - e) * d * q * 2.0 - ((q // 10) * 4.5 + (q % 10) * 1.5)     # MNQ $2/pt; minis + micros commissions
    return {**t, "exit": why, "exit_price": float(px), "exit_t": int(B.t[i]), "pnl": round(pnl, 2),
            "r": round(pnl / (risk * q * 2.0), 3), "mfe": round(mfe, 3), "mae": round(mae, 3), "bars_held": i - i0 + 1}


def check_sim():
    """The simulator must reproduce the baseline replay trade for trade."""
    raw = rl.replay({}, procs=PROCS, quiet=True)
    bad = [t for t in raw["trades"] if (lambda s: s["exit"] != t["exit"] or s["exit_t"] != t["exit_t"] or abs(s["r"] - t["r"]) > 0.002
                                       or abs(s["pnl"] - t["pnl"]) > 0.02)(sim_exit(t, {}))]
    return len(raw["trades"]) - len(bad), len(raw["trades"])


# ------------------------------------------------------------------------------------------------ one-pass screen
def screen(extra):
    """One engine pass over the whole history with live params + extra (cached)."""
    from tools import export_backtest as ex  # noqa: F401  (rich trade record)
    from tools import five_year as fy
    params = {**rl.LIVE_PARAMS, **(extra or {})}
    key = hashlib.sha1((json.dumps(params, sort_keys=True) + rl._data_key() + ":screen1").encode()).hexdigest()[:16]
    path = os.path.join(SCREEN_CACHE, key + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    t0 = time.time()
    o = fy.bt(("screen", params, None, None))
    out = {"params": params, "sessions": sorted({d["date"] for d in o["days"]}), "trades": o["trades"], "seconds": round(time.time() - t0)}
    os.makedirs(SCREEN_CACHE, exist_ok=True)
    rl._dump(out, path, separators=(",", ":"))
    return out


# ------------------------------------------------------------------------------------------------ post-hoc context rules
_WK = {}


def _week_ctx():
    if _WK:
        return _WK
    from engine.data import load
    b = load("NQ", "5m")
    first, days = {}, []
    for i, d in enumerate(b.date_str):
        if d not in first:
            first[d] = i; days.append(d)
    wk = {d: dt.date.fromisoformat(d).isocalendar()[:2] for d in days}
    weeks = collections.OrderedDict()
    for d in days:
        weeks.setdefault(wk[d], []).append(d)
    info = {}
    for w, ds in weeks.items():
        a = first[ds[0]]
        k = days.index(ds[-1])
        z = first[days[k + 1]] if k + 1 < len(days) else len(b.t)
        info[w] = {"open": float(b.o[a]), "high": float(b.h[a:z].max()), "low": float(b.l[a:z].min())}
    day_oc = {}
    for k, d in enumerate(days):
        a = first[d]; z = first[days[k + 1]] if k + 1 < len(days) else len(b.t)
        day_oc[d] = (float(b.o[a]), float(b.c[z - 1]))
    _WK.update(days=days, wk=wk, wkeys=list(weeks), info=info, day_oc=day_oc)
    return _WK


def trade_ctx(t):
    """Weekly / daily context of a trade from bars that closed before it (prior day's candle, prior week's midpoint,
    this week's open). +1 = the trade agrees with the context as defined in each key."""
    W = _week_ctx()
    d, e = int(t["dir"]), float(t["entry"])
    k = W["wkeys"].index(W["wk"][t["day"]])
    out = {}
    if k > 0:
        pw = W["info"][W["wkeys"][k - 1]]
        out["pwmid"] = 1 if (e - (pw["high"] + pw["low"]) / 2) * d > 0 else -1     # long above / short below = +1
    out["wkopen"] = 1 if (W["info"][W["wk"][t["day"]]]["open"] - e) * d > 0 else -1   # long below / short above = +1
    j = W["days"].index(t["day"])
    if j > 0:
        po, pc = W["day_oc"][W["days"][j - 1]]
        out["fade_pd"] = 0 if pc == po else (1 if (pc - po) * d < 0 else -1)
    return out


RULES = {
    "skip_follow_pd": lambda t, ctx: 0.0 if trade_ctx(t).get("fade_pd") == -1 else 1.0,
    "skip_against_pwmid": lambda t, ctx: 0.0 if trade_ctx(t).get("pwmid") == -1 else 1.0,
    "skip_against_wkopen": lambda t, ctx: 0.0 if trade_ctx(t).get("wkopen") == -1 else 1.0,
    "skip_no_smt": lambda t, ctx: 1.0 if "SMT divergence" in (t.get("conf_tags") or []) else 0.0,
}


# ------------------------------------------------------------------------------------------------ run + judge
def _base(method):
    if method == "screen":
        o = screen({})
        T = rl.size(o)
        return rl.score(T, o)
    return rl.load("baseline") if os.path.exists(os.path.join(rl.RUNS, "baseline.json")) else rl.score(*(lambda r: (rl.size(r), r))(rl.replay({}, procs=PROCS)))


def _k(v):
    return f"{'+' if v >= 0 else '-'}${abs(v) / 1000:.1f}k"


def judge(S, B, status=None):
    """(status, verdict) by the CLAUDE.md rule, in plain words."""
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    if not a.get("n") or not b.get("n"):
        return status or "rejected", "No trades in one of the periods."
    tpw_ok = (a["tpw"] or 0) >= 2 and (b["tpw"] or 0) >= 2
    d26, d5 = a["net"] - A["net"], b["net"] - Bb["net"]
    p26, p5 = (a["pf"] or 0) - (A["pf"] or 0), (b["pf"] or 0) - (Bb["pf"] or 0)
    up26, up5 = d26 > 0 and p26 >= 0, d5 > 0 and p5 >= 0
    help26, help5 = d26 >= 1500 and p26 > 0, d5 >= 1500 and p5 > 0
    hurt26 = d26 < -max(750, 0.04 * abs(A["net"])) or p26 < -0.10
    hurt5 = d5 < -max(750, 0.04 * abs(Bb["net"])) or p5 < -0.03
    nums = (f"2026: PF {A['pf']} -> {a['pf']}, net {_k(A['net'])} -> {_k(a['net'])}; "
            f"2021-25: PF {Bb['pf']} -> {b['pf']}, net {_k(Bb['net'])} -> {_k(b['net'])}; "
            f"{a['tpw']} / {b['tpw']} trades a week.")
    if not tpw_ok:
        st, head = "rejected", f"Too few trades ({min(a['tpw'], b['tpw'])} a week)."
    elif up26 and up5:
        st, head = "adopt-candidate", "Better in both periods."
    elif (help26 and not hurt5) or (help5 and not hurt26):
        st, head = "promising", "Helps " + ("2026" if help26 else "2021-25") + " without hurting the other period."
    elif not up26 and not up5:
        st, head = "rejected", "Worse in both periods."
    else:
        st, head = "rejected", ("Better in 2026 only" if up26 else "Better in 2021-25 only") + ", worse in the other."
    return (status or st), f"{head} {nums}"


def compute(x):
    m = x["method"]
    if m == "replay":
        raw = rl.replay(x["params"], procs=PROCS, quiet=True)
    elif m == "screen":
        raw = screen(x["params"])
    elif m == "exitsim":
        base = rl.replay({}, procs=PROCS, quiet=True)
        raw = {**base, "trades": [sim_exit(t, x["sim"]) for t in base["trades"]]}
    elif m == "posthoc":
        raw = rl.replay({}, procs=PROCS, quiet=True)
    else:
        raise ValueError(m)
    T = rl.size(raw, rule=RULES[x["rule"]] if x.get("rule") else None)
    return raw, T, rl.score(T, raw)


METHOD_TXT = {
    "replay": "exact live-loop replay (20-day window per session) + cold-streak filter + sizing; costs included",
    "exitsim": "exits re-simulated on the baseline replay's entries (tools/research_trade.py sim_exit, reproduces the baseline "
               "replay 768/768 trades); cold-streak filter + sizing; costs included",
    "screen": "one-pass 5-year backtest (matches the live-loop replay on 766/768 baseline trades) + cold-streak filter + "
              "sizing; costs included; compared with run screen_baseline",
    "posthoc": "exact live-loop replay of the live strategy, trades filtered after the fact (a skipped setup gets no "
               "replacement trade later that day) + cold-streak filter + sizing; costs included",
}


def run(x, quiet=False):
    raw, T, S = compute(x)
    B = _base(x["method"])
    st, ver = judge(S, B, x.get("status"))
    if x["id"] == "screen_baseline":
        ver = (f"Reference for screen runs. {rl.line(S, '2026')} | {rl.line(S, '2021-25')}")
    if x.get("verdict"):
        ver = x["verdict"]
    if x.get("status_final"):
        st = x["status_final"]
    notes = " ".join(z for z in (f"Method: {METHOD_TXT[x['method']]}.", x.get("note", ""), LEAK_NOTE if not x["id"].startswith("leak") else "") if z)
    rec = rl.save(x["id"], x["title"], x["family"], x["question"], params=x["params"], trades=T, scored=S, status=st,
                  verdict=ver, notes=notes, writeup=WRITEUP.get(x["family"]), tags=[x["method"]])
    rec["method"] = METHOD_TXT[x["method"]]
    rl._dump(rec, os.path.join(rl.RUNS, x["id"] + ".json"), separators=(",", ":"))
    if not quiet:
        print(f"{x['id']:20s} {st:15s} | {rl.line(S, '2026')} | {rl.line(S, '2021-25')}", flush=True)
    return rec


WRITEUP = {"stops": "stops.md", "targets": "targets.md", "management": "management.md", "bias": "bias-filters.md",
           "filters": "bias-filters.md", "timing": "bias-filters.md", "other": "leakage-check.md", "combo": "trade-construction-summary.md"}


def by_id(i):
    for x in E:
        if x["id"] == i:
            return x
    raise KeyError(i)


def table(family=None):
    for x in E:
        if family and x["family"] != family:
            continue
        p = os.path.join(rl.RUNS, x["id"] + ".json")
        if not os.path.exists(p):
            print(f"{x['id']:20s} (not run)"); continue
        r = rl.load(x["id"])
        a, b = r["spans"]["2026"], r["spans"]["2021-25"]
        print(f"{x['id']:20s} {x['method']:8s} {r['status']:15s} 26: n={a.get('n')} tpw={a.get('tpw')} PF={a.get('pf')} net={a.get('net')} "
              f"dd={a.get('dd')} p20={a.get('p20')} | 21-25: n={b.get('n')} tpw={b.get('tpw')} PF={b.get('pf')} net={b.get('net')} dd={b.get('dd')} b2b={b.get('b2b')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for x in E:
            print(f"{x['id']:20s} {x['family']:11s} {x['method']:8s} {json.dumps(x['params'])}")
    elif cmd == "check_sim":
        print("simulator reproduces %d of %d baseline replay trades" % check_sim())
    elif cmd == "table":
        table(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd in ("all", "run"):
        ids = [x["id"] for x in E] if cmd == "all" else sys.argv[2:]
        order = {"screen": 0, "exitsim": 1, "posthoc": 2, "replay": 3}
        todo = sorted((by_id(i) for i in ids), key=lambda x: order[x["method"]])
        for x in todo:
            run(x)
    else:
        print(__doc__)
