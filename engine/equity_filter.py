"""Equity-curve filter: trade real money only while the strategy is working.

Every signal the engine produces is recorded in a shadow ledger, whether or not it was traded. Before a new entry is
routed, the filter sums the R of the last `lookback` shadow trades that finished before that entry. If the sum is above
`min_sum_r`, the entry is traded; otherwise it is tracked on paper only, and trading resumes as soon as the shadow
record turns positive again.

Evidence (research: tools/equity_filter_study.py, live pick, lookback picked on 2021-24 only):
  lookback 15: 2021-24 -$1,922 -> +$5,005 | 2025 +$3,860 -> +$5,906 | 2026 +$11,630 -> +$10,339 with PF 2.41 -> 2.99,
  win rate 26% -> 32%, max drawdown -$3,147 -> -$1,174. Neighbours 14-18 all improve every period.

Config (live_model.json): "equity_filter": {"lookback": 15, "min_sum_r": 0.0, "cold_mode": "skip" | "half", "cold_size": 0.25}
(missing/null = off). "half" keeps every setup (2+ a week) and trades the cold streak at a fraction of full size instead of
sitting out: "cold_size" (default 0.5) is that fraction. Research 2026-10-17 (research/writeups/risk-summary.md): 0.25 beats
0.5 at every lookback and threshold tested on 2021-25 (+$10.2k vs +$6.5k, max DD -$9.2k vs -$11.4k, 1-month eval fails
9.6% -> 7.5%) and costs $0.6k in 2026.
"""
from __future__ import annotations

import datetime as _dt
import time as _time
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "data", "shadow_ledger.json")
SEED = os.path.join(ROOT, "data", "shadow_ledger_seed.json")


def load(path: str = LEDGER) -> list:
    for p in (path, SEED):
        try:
            with open(p, encoding="utf-8") as fh:
                rows = json.load(fh)
            return sorted(rows, key=lambda x: x["entry_t"])
        except Exception:
            continue
    return []


def save(rows: list, path: str = LEDGER) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sorted(rows, key=lambda x: x["entry_t"])[-500:], fh)
    os.replace(tmp, path)


def record(trades: list, path: str = LEDGER) -> int:
    """Add completed engine trades (dicts with entry_t, exit_t, pnl_r or r) to the shadow ledger. Returns rows added."""
    rows = load(path)
    have = {int(x["entry_t"]) for x in rows}
    added = 0
    for t in trades or []:
        et = int(t.get("entry_t") or 0)
        if not et or et in have or not t.get("exit_t"):
            continue
        r = t.get("pnl_r", t.get("r"))
        if r is None:
            continue
        rows.append({"entry_t": et, "exit_t": int(t["exit_t"]), "r": round(float(r), 4), "day": t.get("day")})
        have.add(et)
        added += 1
    if added:
        save(rows, path)
    return added


def status(cfg: dict | None, before_t: int | None = None, path: str = LEDGER) -> dict:
    """{"enabled", "on", "mult", "sum_r", "n", "lookback", "reason"} for an entry at before_t (unix seconds).
    on = full size. During a cold streak cold_mode "skip" (default) gives mult 0 (paper only), "half" gives mult 0.5."""
    if not cfg:
        return {"enabled": False, "on": True, "mult": 1.0, "reason": "equity filter off"}
    lb = int(cfg.get("lookback", 15))
    thr = float(cfg.get("min_sum_r", 0.0))
    half = cfg.get("cold_mode", "skip") == "half"
    cold_size = min(1.0, max(0.0, float(cfg.get("cold_size", 0.5)))) if half else 0.0
    rows = [x for x in load(path) if before_t is None or int(x["exit_t"]) < int(before_t)]
    last = rows[-lb:]
    s = round(sum(float(x["r"]) for x in last), 2)
    on = len(last) < lb or s > thr
    mult = 1.0 if on else cold_size
    size_word = "half" if abs(cold_size - 0.5) < 1e-9 else "quarter" if abs(cold_size - 0.25) < 1e-9 else f"{cold_size:g}x"
    reason = (f"last {len(last)} signals {s:+.2f}R > {thr:+.1f}R: full size" if on else
              f"last {len(last)} signals {s:+.2f}R <= {thr:+.1f}R: cold streak, "
              + (f"{size_word} size until it turns positive" if half else "paper only until it turns positive"))
    return {"enabled": True, "on": on, "mult": mult, "sum_r": s, "n": len(last), "lookback": lb, "reason": reason}

# When to buy or reset the MFFU Builder 50K eval (research/writeups/monte-carlo-evals.md, state-matched Monte Carlo, all
# years; research/writeups/eval-game.md, real history): the filter's state on the eval's first session is the biggest
# single factor. Odds of passing / failing within 2 weeks and 1 month, median sessions to pass, median weeks to funded.
EVAL_TIMING = {
    "warmed": {"pass_2w": 0.131, "fail_2w": 0.011, "pass_1m": 0.261, "fail_1m": 0.045, "median_pass": 19, "funded_wk": 13.8},
    "full": {"pass_2w": 0.110, "fail_2w": 0.021, "pass_1m": 0.218, "fail_1m": 0.084, "median_pass": 20, "funded_wk": 12.4},
    "stale": {"pass_2w": 0.050, "fail_2w": 0.040, "pass_1m": 0.069, "fail_1m": 0.124, "median_pass": 30, "funded_wk": 20.0},
    "cold": {"pass_2w": 0.008, "fail_2w": 0.001, "pass_1m": 0.043, "fail_1m": 0.016, "median_pass": 36, "funded_wk": 22.2},
}
WARMED_SESSIONS = 5      # "just warmed": the filter switched back to full size within the last 5 sessions (eval-game.md)
STALE_SESSIONS = 20      # full size for 20+ sessions: the worst start in 2021-25 (7% pass / 12% fail within a month)


def sessions_since_flip(cfg: dict | None, now: int | None = None, path: str = LEDGER) -> int | None:
    """Weekdays since the filter last switched from cold back to full size, from the shadow ledger; None when the ledger
    is shorter than the lookback or has never been cold."""
    if not cfg:
        return None
    lb, thr = int(cfg.get("lookback", 15)), float(cfg.get("min_sum_r", 0.0))
    rows = sorted(load(path), key=lambda x: int(x["exit_t"]))
    if len(rows) < lb:
        return None
    on_prev, flip_t = True, None
    for j in range(len(rows)):
        on = j + 1 < lb or sum(float(x["r"]) for x in rows[max(0, j - lb + 1):j + 1]) > thr
        if on and not on_prev:
            flip_t = int(rows[j]["exit_t"])
        on_prev = on
    if flip_t is None or not on_prev:
        return None
    d0 = _dt.datetime.fromtimestamp(flip_t, _ET).date()
    d1 = _dt.datetime.fromtimestamp(int(now or _time.time()), _ET).date()
    n, d = 0, d0
    while d < d1:
        d += _dt.timedelta(days=1)
        n += d.weekday() < 5
    return n


def eval_timing(status: dict | None, since_flip: int | None = None) -> dict:
    """When to buy or reset the eval: 'wait' in a cold streak, 'go' at full size (best within WARMED_SESSIONS of the
    switch back to full size; weakest after STALE_SESSIONS at full size). status = status(cfg); since_flip =
    sessions_since_flip(cfg)."""
    st = status or {}
    if not st.get("enabled"):
        return {"verdict": "go", "state": "full", "since_flip": None, "best": False,
                "reason": "no cold-streak filter: eval odds are the full-size odds", **EVAL_TIMING["full"]}
    cold = not st.get("on", True)
    rec = f"last {st.get('n', 0)} signals {float(st.get('sum_r') or 0):+.2f}R"
    if cold:
        key, reason = "cold", (f"cold streak ({rec}): an eval started now passes {EVAL_TIMING['cold']['pass_1m']:.0%} within a month "
                               f"(median {EVAL_TIMING['cold']['median_pass']} sessions); wait for the switch back to full size, "
                               f"the best moment to start ({EVAL_TIMING['warmed']['pass_1m']:.0%})")
    elif since_flip is not None and since_flip <= WARMED_SESSIONS:
        key, reason = "warmed", (f"the filter switched back to full size {since_flip} session{'s' if since_flip != 1 else ''} ago ({rec}): "
                                 f"the best moment to start, {EVAL_TIMING['warmed']['pass_1m']:.0%} pass / "
                                 f"{EVAL_TIMING['warmed']['fail_1m']:.0%} fail within a month in 2021-25, 50% pass in 2026")
    elif since_flip is not None and since_flip >= STALE_SESSIONS:
        key, reason = "stale", (f"full size for {since_flip} sessions ({rec}): a late start; in 2021-25 these passed "
                                f"{EVAL_TIMING['stale']['pass_1m']:.0%} and failed {EVAL_TIMING['stale']['fail_1m']:.0%} within a month; "
                                f"the best starts come right after a cold streak ends")
    else:
        key, reason = "full", (f"full size ({rec}): an eval started now passes {EVAL_TIMING['full']['pass_1m']:.0%} within a month, "
                               f"fails {EVAL_TIMING['full']['fail_1m']:.0%}, median {EVAL_TIMING['full']['median_pass']} sessions to pass")
    return {"verdict": "wait" if cold else "go", "state": key, "since_flip": since_flip, "best": key == "warmed",
            "reason": reason, **EVAL_TIMING[key]}
