"""PAYOUT COACH (2026-11-17, owner: ATLAS's 25K passed, "make the most of payouts"; docs/FUNDED_25K_PLAYBOOK.md).

For one MFFU Builder sim-funded account: the cycle's profit, best day vs the 50% rule ("a $X day more and you'd need $Y more"),
days traded this cycle, the exact $ you can request today (or "not yet: need $Z more"), the plan (ask for the full $1,000 /
$2,000 max: research/writeups/payout-policy-funded25-2026-11-17.md), the 30% tax pot and the net, and the 7-day inactivity
countdown. Same numbers as tools/web_public/business/payoutcoach.js (the page's copy; tests/test_payout_coach.py runs both).

Pure and read only: no file, no order, never requests a payout (the owner asks MFFU). The PC's tracker (engine/funded_life.track,
night-life's lifecycle pushes in engine/board_events) feeds it through from_tracker(); otherwise the owner's typed numbers.

    python -X utf8 -m engine.payout_coach --balance 26400 --cycle-start 25000 --best 500 --days 3 --first 2026-11-19 --last 2026-11-24
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import sys

PLANS = {
    "builder25k": {"label": "Builder 25K", "start": 25000.0, "buffer": 1100.0, "pay_min": 250.0, "pay_max": 1000.0, "split": 0.8,
                   "cons": 0.5, "cycle_days": 2, "first_wait_days": 2, "max_payouts": 5, "lock": 100.0, "mll": 1000.0, "big_day": 1000.0},
    "builder50k": {"label": "Builder 50K", "start": 50000.0, "buffer": 2100.0, "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8,
                   "cons": 0.5, "cycle_days": 2, "first_wait_days": 2, "max_payouts": 5, "lock": 100.0, "mll": 2000.0, "big_day": 2000.0},
}
POLICY = {"key": "max", "text": "ask when the full max sits above the buffer"}
TAX, IDLE_DAYS = 0.30, 7


def _num(v):
    try:
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def _day(s):
    try:
        return _dt.date.fromisoformat(str(s)[:10]).isoformat() if s and len(str(s)) >= 10 else None
    except ValueError:
        return None


def _add(d, n):
    return (_dt.date.fromisoformat(d) + _dt.timedelta(days=n)).isoformat()


def _next_weekday(d):
    x = _dt.date.fromisoformat(d)
    while x.weekday() >= 5:
        x += _dt.timedelta(days=1)
    return x.isoformat()


def r2(v):
    return round(float(v) + 0.0, 2)


def usd(v) -> str:
    if v is None:
        return "-"
    v = float(v)
    return f"{'-' if v < 0 else ''}${math.floor(abs(v) + 0.5):,.0f}"


def coach(state: dict | None, plan: str = "builder25k", today: str | None = None) -> dict:
    """state = {balance, cycle_start_balance, best_day, cycle_days, first_trade, last_trade, payouts_n, room?}."""
    P = PLANS.get(plan) or PLANS["builder25k"]
    s = state or {}
    t = _day(today) or _dt.date.today().isoformat()
    bal = _num(s.get("balance"))
    if bal is None:
        return {"ok": False, "plan": P["label"], "text": "Type the balance (or wait for the PC) to see the payout coach."}
    profit = r2(bal - P["start"])
    n_pay = max(0, int(round(_num(s.get("payouts_n")) or 0)))
    cs = _num(s.get("cycle_start_balance"))
    cprof = r2(bal - (cs if cs is not None else P["start"]))
    best = max(0.0, _num(s.get("best_day")) or 0.0)
    days = max(0, int(round(_num(s.get("cycle_days")) or 0)))
    above = r2(profit - P["buffer"])
    o = {"ok": True, "plan": P["label"], "today": t, "balance": r2(bal), "profit": profit, "above_buffer": above, "cycle_profit": cprof,
         "best_day": best, "cycle_days": days, "cycle_days_need": P["cycle_days"], "payouts_n": n_pay, "payouts_max": P["max_payouts"],
         "why": []}
    o["best_pct"] = math.floor(1000.0 * best / cprof + 0.5) / 10 if cprof > 0 else None
    o["cons_ok"] = cprof > 0 and best <= P["cons"] * cprof + 1e-9
    o["cons_need"] = r2(max(0.0, best / P["cons"] - cprof))
    o["safe_day"] = r2(cprof) if o["cons_ok"] else 0
    X = P["big_day"]
    o["big_day"] = X
    o["big_day_need"] = r2(max(0.0, X - cprof) if X >= best else max(0.0, 2 * best - cprof - X))
    room = _num(s.get("room"))
    o["lost"] = room is not None and room <= 0
    o["graduated"] = n_pay >= P["max_payouts"]
    first = _day(s.get("first_trade"))
    o["eligible_from"] = _next_weekday(_add(first, P["first_wait_days"])) if first else _day(s.get("eligible_from"))
    money_need = r2(max(0.0, P["buffer"] + P["pay_min"] - profit))
    w = o["why"]
    if o["lost"]:
        w.append("the max-loss floor was reached: the account is gone")
    if o["graduated"]:
        w.append(f"{n_pay} sim payouts done: MFFU moves you to live")
    if not o["eligible_from"] and n_pay == 0:
        w.append("no funded trade yet (first request 2 days after it)")
    elif o["eligible_from"] and t < o["eligible_from"] and n_pay == 0:
        w.append(f"first request from {o['eligible_from']} (2 days after the first trade)")
    if money_need > 0:
        w.append(f"{usd(money_need)} more profit: {usd(max(0.0, above))} sits above the {usd(P['buffer'])} buffer, the minimum request is "
                 f"{usd(P['pay_min'])}")
    if days < P["cycle_days"]:
        w.append(f"{days} of {P['cycle_days']} traded days this cycle")
    if cprof > 0 and not o["cons_ok"]:
        w.append(f"best day {usd(best)} is {o['best_pct']:g}% of the cycle (max 50%): {usd(o['cons_need'])} more on other days, each under {usd(best)}")
    elif cprof <= 0 and days > 0:
        w.append(f"cycle profit {usd(cprof)}: nothing to pay yet")
    o["need_more"] = r2(max(money_need, o["cons_need"] if (cprof > 0 and not o["cons_ok"]) else 0.0))
    o["eligible"] = not w
    o["request_today"] = r2(min(P["pay_max"], above)) if o["eligible"] else 0
    o["first_at_min"] = bool(s.get("first_at_min")) and n_pay == 0        # night-payfirst: ATLAS's first payout at the minimum
    ask_at = P["pay_min"] if o["first_at_min"] else P["pay_max"]
    o["plan_line"] = r2(P["buffer"] + ask_at)
    o["plan_ready"] = o["eligible"] and above >= ask_at - 1e-9
    o["plan_wait"] = r2(ask_at - above) if (o["eligible"] and not o["plan_ready"]) else 0
    o["status"] = ("lost" if o["lost"] else "graduated" if o["graduated"] else "ready" if o["plan_ready"] else
                   "allowed" if o["eligible"] else "not_yet")
    req = o["request_today"]
    o["to_you"] = r2(req * P["split"])
    o["tax_pot"] = r2(o["to_you"] * TAX)
    o["net"] = r2(o["to_you"] - o["tax_pot"])
    o["after_balance"] = r2(bal - req)
    o["after_room"] = r2(bal - req - (P["start"] + P["lock"])) if req > 0 else None
    last = _day(s.get("last_trade"))
    if last:
        idle = max(0, (_dt.date.fromisoformat(t) - _dt.date.fromisoformat(last)).days)
        o.update(idle_days=idle, trade_by=_add(last, IDLE_DAYS - 1), idle_left=max(0, IDLE_DAYS - 1 - idle))
        o["idle_warn"] = o["idle_left"] <= 2
    else:
        o.update(idle_days=None, trade_by=None, idle_left=None, idle_warn=False)
    o["text"] = sentence(o)
    return o


def sentence(c: dict) -> str:
    if not c.get("ok"):
        return c.get("text", "")
    s = c["status"]
    if s == "lost":
        return "The floor was reached: this funded account is gone."
    if s == "graduated":
        return "5 sim payouts done: MFFU moves you to live (you trade it in person)."
    if s == "ready":
        return (f"REQUEST PAYOUT TODAY: {usd(c['request_today'])} ({usd(c['to_you'])} to you, {usd(c['net'])} after the 30% "
                "tax pot). MFFU dashboard > Payouts, then TRADE_HOME -> P.")
    if s == "allowed":
        return (f"MFFU would pay {usd(c['request_today'])} today; the plan waits for the full {usd(c['request_today'] + c['plan_wait'])} "
                f"({usd(c['plan_wait'])} more).")
    return "Not yet: " + (f"need {usd(c['need_more'])} more" if c["need_more"] > 0 else (c["why"][0] if c["why"] else "keep trading")) + "."


def from_tracker(f: dict | None, last_trade: str | None = None, start: float | None = None) -> dict | None:
    """engine/funded_life.track output (or live_board's "funded" subset) -> coach state."""
    if not isinstance(f, dict):
        return None
    bal = _num(f.get("balance"))
    if bal is None and _num(f.get("buffer_balance")) is not None and _num(f.get("above_buffer")) is not None:
        bal = r2(_num(f["buffer_balance"]) + _num(f["above_buffer"]))
    if bal is None and _num(f.get("profit")) is not None and start is not None:
        bal = float(start) + _num(f.get("profit"))
    cp = _num(f.get("cycle_profit"))
    return {"balance": bal, "cycle_start_balance": r2(bal - cp) if bal is not None and cp is not None else None,
            "best_day": _num(f.get("best_day")), "cycle_days": _num(f.get("cycle_days")), "first_trade": f.get("first_trade"),
            "last_trade": f.get("last_trade") or last_trade, "payouts_n": _num(f.get("payouts_n")), "room": 0.0 if f.get("lost") else _num(f.get("room")),
            "eligible_from": f.get("eligible_from"), "first_at_min": bool(f.get("first_at_min"))}


def lines(c: dict) -> list:
    """The card's rows (plain words, $ first): what the page shows."""
    if not c.get("ok"):
        return [c.get("text", "")]
    out = [c["text"],
           f"Cycle profit {usd(c['cycle_profit'])}; best day {usd(c['best_day'])}"
           + (f" = {c['best_pct']:g}% (max 50%)" if c["best_pct"] is not None else ""),
           (f"A {usd(c['big_day'])} day more and you'd need {usd(c['big_day_need'])} more to be under 50%" if c["big_day_need"] > 0
            else f"A {usd(c['big_day'])} day would still keep you under 50%")
           + (f" (biggest safe day now: {usd(c['safe_day'])})" if c["cons_ok"] else ""),
           f"Days traded this cycle: {c['cycle_days']} ({c['cycle_days_need']} needed)"]
    if c["request_today"] > 0:
        out.append(f"You can request {usd(c['request_today'])} today: {usd(c['to_you'])} to you, tax pot {usd(c['tax_pot'])}, net "
                   f"{usd(c['net'])}")
    else:
        out.append(f"Not yet: need {usd(c['need_more'])} more" if c["need_more"] > 0 else "Not yet: " + "; ".join(c["why"][:2]))
    if c.get("trade_by"):
        out.append(f"Inactivity: trade by {c['trade_by']} ({c['idle_left']} day(s) left; 7 days without a trade wipes the profits)")
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.payout_coach", description="MFFU funded payout coach (read only)")
    ap.add_argument("--plan", default="builder25k", choices=sorted(PLANS))
    ap.add_argument("--balance", type=float, required=True)
    ap.add_argument("--cycle-start", type=float, default=None, help="balance when this cycle began (start or after the last payout)")
    ap.add_argument("--best", type=float, default=0.0, help="best day this cycle, $")
    ap.add_argument("--days", type=int, default=0, help="traded days this cycle")
    ap.add_argument("--first", default=None, help="first funded trade day")
    ap.add_argument("--last", default=None, help="last trade day")
    ap.add_argument("--payouts", type=int, default=0)
    ap.add_argument("--today", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    c = coach({"balance": a.balance, "cycle_start_balance": a.cycle_start, "best_day": a.best, "cycle_days": a.days,
               "first_trade": a.first, "last_trade": a.last, "payouts_n": a.payouts}, a.plan, a.today)
    print(json.dumps(c, indent=1) if a.json else "\n".join(lines(c)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
