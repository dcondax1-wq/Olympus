"""The evaluation math behind the Prop Eval Tracker product (the same rules as the spreadsheet formulas and the web app's JS).

Generic prop-firm rules, entered by the buyer (no firm is named or implied):
  start balance, profit target, max loss ($) of type "EOD trailing" (the level follows the best end-of-day balance),
  "Intraday trailing" (follows the best balance during the day) or "Static"; optionally the trail stops at start + $X;
  optional daily loss limit, consistency rule (best day <= X% of total profit) and minimum trading days.
Per day: net P&L after fees, and optionally the lowest and highest balance during the day.

A breach is equity AT or BELOW the max-loss level at any moment (we only know the day's low if the buyer types it; without it
the end-of-day balance is used). For intraday trailing we assume the day's high came before its low (the cautious reading).
It tracks rules; it predicts nothing. This mirrors our own MFFU math (research/lit/mffu_rules.json: EOD trailing, lock at start + $100).
"""
from __future__ import annotations

import math

TYPES = ("EOD trailing", "Intraday trailing", "Static")

# $ per 1.00 point of price, from the exchanges' contract specs (index points; metals and oil per $1.00 move)
INSTRUMENTS = {
    "MNQ (Micro Nasdaq-100)": 2.0, "NQ (E-mini Nasdaq-100)": 20.0, "MES (Micro S&P 500)": 5.0, "ES (E-mini S&P 500)": 50.0,
    "M2K (Micro Russell 2000)": 5.0, "RTY (E-mini Russell 2000)": 50.0, "MYM (Micro Dow)": 0.5, "YM (E-mini Dow)": 5.0,
    "MGC (Micro Gold)": 10.0, "GC (Gold)": 100.0, "MCL (Micro Crude Oil)": 100.0, "CL (Crude Oil)": 1000.0,
}


def compute(rules: dict, days: list) -> dict:
    start = float(rules["start"])
    max_loss = float(rules["max_loss"])
    kind = rules.get("type", "EOD trailing")
    if kind not in TYPES:
        raise ValueError(f"type must be one of {TYPES}")
    lock = start + float(rules["lock"]) if rules.get("lock") not in (None, "") else math.inf
    daily = float(rules["daily_limit"]) if rules.get("daily_limit") not in (None, "") else None
    target = float(rules.get("target") or 0)
    cons = float(rules["consistency"]) if rules.get("consistency") not in (None, "") else None     # a fraction, e.g. 0.4
    min_days = int(rules.get("min_days") or 0)
    bal, hwm, floor = start, start, start - max_loss
    rows, breached, best = [], None, 0.0
    for d in days:
        pnl = float(d["pnl"])
        end = bal + pnl
        low = min(end, float(d["low"])) if d.get("low") not in (None, "") else end
        high = max(end, float(d["high"])) if d.get("high") not in (None, "") else end
        if kind == "Intraday trailing":
            in_effect = max(floor, min(max(hwm, high) - max_loss, lock))
        else:
            in_effect = floor
        day_loss = max(0.0, bal - low)
        hit = low <= in_effect + 1e-9
        if kind == "EOD trailing":
            hwm = max(hwm, end)
        elif kind == "Intraday trailing":
            hwm = max(hwm, end, high)
        new_floor = in_effect if kind == "Static" else max(in_effect, min(hwm - max_loss, lock))
        status = "BREACHED" if hit else ("DAILY LIMIT" if daily is not None and day_loss >= daily - 1e-9 else
                                         ("CAREFUL" if end - new_floor <= 0.25 * max_loss + 1e-9 else "OK"))
        if hit and breached is None:
            breached = d.get("date") or len(rows) + 1
        best = max(best, pnl)
        rows.append({"date": d.get("date"), "pnl": pnl, "end": round(end, 2), "hwm": round(hwm, 2), "floor_in_effect": round(in_effect, 2),
                     "floor_after": round(new_floor, 2), "dd_left": round(end - new_floor, 2), "day_loss": round(day_loss, 2), "status": status})
        bal, floor = end, new_floor
    profit = bal - start
    share = best / profit if profit > 0 else None
    cons_ok = True if cons is None else (share is not None and share <= cons + 1e-9)
    n = len(days)
    if breached is not None:
        status = "BREACHED"
    elif target and profit >= target - 1e-9 and n >= min_days and cons_ok:
        status = "TARGET MET"
    elif bal - floor <= 0.25 * max_loss + 1e-9:
        status = "CAREFUL"
    else:
        status = "OK"
    need = None
    if cons is not None and profit > 0 and not cons_ok:
        need = round(best / cons - profit, 2)
    return {"balance": round(bal, 2), "floor": round(floor, 2), "dd_left": round(bal - floor, 2), "profit": round(profit, 2),
            "target_left": round(max(0.0, target - profit), 2), "days": n, "best_day": round(best, 2),
            "best_share": None if share is None else round(share, 4), "consistency_ok": cons_ok, "more_profit_needed": need,
            "breached": breached, "status": status, "rows": rows}


def size(dd_left: float, stop_points: float, dollars_per_point: float, risk_fraction: float = 0.10, cost_per_contract: float = 0.0,
         risk_dollars: float | None = None) -> dict:
    """Size follows the stop: contracts = floor(risk $ / (stop x $/pt + costs)). Risk = a share of drawdown left unless fixed."""
    risk = float(risk_dollars) if risk_dollars else max(0.0, float(dd_left)) * float(risk_fraction)
    per = float(stop_points) * float(dollars_per_point) + float(cost_per_contract)
    n = int(math.floor(risk / per + 1e-9)) if per > 0 else 0
    loss = n * per
    streak = int(math.floor(dd_left / loss + 1e-9)) if loss > 0 else None
    return {"risk": round(risk, 2), "per_contract": round(per, 2), "contracts": n, "loss_if_stopped": round(loss, 2), "losses_in_a_row": streak}
