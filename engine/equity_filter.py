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
