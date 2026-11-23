"""MFFU Builder Sim Funded tracker (2026-10-25, owner: "this bot should start making us money once we pass evals").
Read-only: it never requests a payout, never arms or routes anything. One tracker per funded account (LIT on the Builder
50K, ATLAS / LIT on a Builder 25K) from that account's closed P&L per day and the payouts the owner recorded.

MFFU Builder Sim Funded rules (help center 2026-10-24, research/lit/mffu_rules.json, research/handoff/2026-10-25/A4):
                     Builder 50K                     Builder 25K
  max loss (MLL)     $2,000 EOD trailing             $1,000 EOD trailing        locks at start + $100; after the first
                                                                                 payout the MLL sits at start + $100
  soft daily loss    $1,000                          $600                       trading paused for the day, no breach
  buffer             $2,100 above start               $1,100                     must stay in the account
  request            min $500, max $2,000             min $250, max $1,000       per cycle, 80% to the trader
  consistency        best day <= 50% of the cycle's profit (soft: not a breach, trade more days; resets after a payout)
  cycle              >= 2 traded days in the cycle; the first request 48 h after the first funded trade
  sim payouts        5, then MFFU moves the account to live (Blue Row Capital)
The owner's plan (CLAUDE.md, the phone's payout goal; weekend landing 2026-11-21, was $1,500 / $750): ask only once the max
request sits above the buffer, $2,000 on a 50K (at $4,100 MFFU profit) / $1,000 on a 25K (at $2,100), then take that max.

  python -X utf8 -m engine.funded_life                       every funded account's tracker (data/accounts.json + state)
  python -X utf8 -m engine.funded_life --demo                a worked example (no files read)
Pushes (engine/push.text_payload, stable keys: sent once): "PAYOUT READY: request $X", "consistency: best day is N% of
the cycle, trade M more days", "FUNDED ACCOUNT LOST", "5 sim payouts done: MFFU moves you to live".
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1

# per plan: $ relative to the start balance (MFFU shows sim funded from $0: "profit" = our balance - start)
PLANS = {
    "builder50k": {"label": "MFFU Builder 50K", "start": 50000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "buffer": 2100.0,
                   "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8, "cons": 0.5, "cycle_days": 2, "first_wait_h": 48,
                   "max_payouts": 5, "max_micros": 40, "ask_above": 2000.0, "typical_day": 300.0, "price": 91.80,
                   "preset": "mffu_builder_50k"},
    "builder25k": {"label": "MFFU Builder 25K", "start": 25000.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "buffer": 1100.0,
                   "pay_min": 250.0, "pay_max": 1000.0, "split": 0.8, "cons": 0.5, "cycle_days": 2, "first_wait_h": 48,
                   "max_payouts": 5, "max_micros": 20, "ask_above": 1000.0, "typical_day": 150.0, "price": 63.00,
                   "preset": "mffu_builder_25k"},
}
# MFFU per person (help center, conflicting wording, research/lit/mffu_rules.json "accounts"): 1 active sim-funded Builder
# 50K; up to 2 active sim-funded 25K; a general article says up to 5 sim funded (25K/50K). The plan uses 1 x 50K + 2 x 25K.
MAX_FUNDED = {"builder50k": 1, "builder25k": 2}
STOP_AFTER = 4                 # take payouts 1-4, never the 5th (fleet plan 2026-11-22; engine/payout_autopilot.BUILDER_LAST)


def _num(x, d=None):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def _money(x) -> str:
    v = float(x or 0)
    return f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def plan_of(key: str | None = None, start: float | None = None) -> dict:
    """The plan by key ("builder50k" / "builder25k" / a multi_account preset) or by the start balance."""
    k = str(key or "").lower().replace(" ", "").replace("_", "")
    for pk, p in PLANS.items():
        if k in (pk, p["preset"].replace("_", ""), "mffu" + pk):
            return dict(p, key=pk)
    if start is not None and abs(float(start) - 25000.0) < 1:
        return dict(PLANS["builder25k"], key="builder25k")
    return dict(PLANS["builder50k"], key="builder50k")


def payout_rules(rules: dict | None) -> dict:
    """The buffer / request / consistency numbers for engine/sizing.funded_cycle from a multi_account rules dict."""
    p = plan_of(None, _num((rules or {}).get("start"), 50000.0))
    return {k: p[k] for k in ("buffer", "pay_min", "pay_max", "cons", "cycle_days", "max_payouts")}


def _add_days(day: str, n: int) -> str:
    return (_dt.date.fromisoformat(day) + _dt.timedelta(days=n)).isoformat()


def _next_weekday(day: str) -> str:
    d = _dt.date.fromisoformat(day)
    while d.weekday() >= 5:
        d += _dt.timedelta(days=1)
    return d.isoformat()


# ---------------------------------------------------------------------------------------------------- the tracker
def track(day_pnl: dict, payouts: dict | None = None, plan: str | dict | None = "builder50k", today: str | None = None,
          today_cum: float = 0.0, start: str | None = None, name: str | None = None, prior: float = 0.0) -> dict:
    """The funded account now. day_pnl = closed P&L per traded day since the funded start (today's may be in it or in
    today_cum, not both); payouts = {day: $ withdrawn at that day's end}. -> balance, floor, room, buffer progress,
    cycle profit, best day vs 50%, traded days, the first-payout date (48 h after the first trade), eligibility, the max
    request, payouts n of 5, what to do. prior = $ on the account before the bot traded it (the funded balance at the
    funded start - the plan start, engine/account_b.py "funded_balance"): it counts in the balance and the trailing floor
    as one day before the start (engine/sizing.funded_state's "0000-00-00"), never as a traded day of the cycle. 0 = as
    before. Pure: no file, no clock unless today is None."""
    P = plan if isinstance(plan, dict) else plan_of(plan)
    today = today or _dt.date.today().isoformat()
    days = {str(d): float(v) for d, v in (day_pnl or {}).items() if str(d) != "0000-00-00"}
    if today_cum:
        days[today] = round(days.get(today, 0.0) + float(today_cum), 2)
    pay = {str(d): float(v) for d, v in (payouts or {}).items() if _num(v, 0) > 0}
    # balance / floor (engine/sizing.funded_state rule: EOD trailing, lock at start + $100, payouts lower the balance only)
    bal = peak = 0.0
    floor = -P["mll"]
    if prior:
        bal = float(prior)
        peak = max(peak, bal)
        floor = min(max(floor, peak - P["mll"]), P["lock"])
    for d in sorted(set(days) | set(pay)):
        bal += days.get(d, 0.0)
        if d < today or d in pay:
            peak = max(peak, bal)
            floor = min(max(floor, peak - P["mll"]), P["lock"])
        bal -= pay.get(d, 0.0)
    if pay:
        floor = max(floor, P["lock"])                # after the first payout the MLL sits at start + $100
    room = round(bal - floor, 2)
    last = max(pay) if pay else ""
    cyc = {d: v for d, v in days.items() if d > last and abs(v) > 1e-9}
    cprof = round(sum(cyc.values()), 2)
    best = round(max(cyc.values()), 2) if cyc else 0.0
    best_day = max(cyc, key=lambda d: cyc[d]) if cyc else None
    cons = float(P["cons"])
    best_pct = round(100.0 * best / cprof, 1) if cprof > 0 else None
    cons_ok = cprof > 0 and best <= cons * cprof + 1e-9
    need_profit = round(max(0.0, best / cons - cprof), 2) if cprof > 0 or best > 0 else 0.0
    traded = sorted(d for d, v in days.items() if abs(v) > 1e-9)
    first_trade = traded[0] if traded else None
    eligible_from = _next_weekday(_add_days(first_trade, int(math.ceil(P["first_wait_h"] / 24.0)))) if first_trade else None
    above = round(bal - P["buffer"], 2)
    n_pay = len(pay)
    graduated = n_pay >= int(P["max_payouts"])
    lost = room <= 0
    max_req = round(min(P["pay_max"], max(0.0, above)), 2) if above >= P["pay_min"] else 0.0
    why = []                                           # why MFFU would refuse a request today
    if lost:
        why.append("max-loss floor reached: the funded account is gone")
    if graduated:
        why.append(f"{n_pay} sim payouts done: MFFU moves the account to live")
    if eligible_from is None:
        why.append("no funded trade yet (first request 48 h after the first trade)")
    elif today < eligible_from:
        why.append(f"first request from {eligible_from} (48 h after the first trade {first_trade})")
    if above < P["pay_min"]:
        why.append(f"{_money(max(0.0, above))} above the {_money(P['buffer'])} buffer, MFFU's minimum is {_money(P['pay_min'])}")
    if len(cyc) < int(P["cycle_days"]):
        why.append(f"{len(cyc)} traded day(s) in this cycle, {int(P['cycle_days'])} needed")
    if not cons_ok and cprof > 0:
        why.append(f"best day {_money(best)} is {best_pct:.0f}% of the cycle's {_money(cprof)} (max {cons * 100:.0f}%)")
    elif cprof <= 0 and cyc:
        why.append(f"cycle profit {_money(cprof)}: nothing to pay yet")
    eligible = not why
    # fleet plan 2026-11-22 (research/writeups/fleet-plan-2026-11-22.md): take payouts 1-4, NEVER the 5th (MFFU moves you to live
    # and every sim account sleeps): after the 4th the tracker never says "ready" again (engine/payout_autopilot warns instead)
    stop4 = n_pay >= STOP_AFTER and not graduated
    ready = eligible and above >= P["ask_above"] and not stop4   # the owner's plan: ask once the max sits above the buffer
    # trade M more days (consistency + the 2-day minimum), at a typical day that does not beat the best day
    typ = [v for d, v in cyc.items() if v > 0 and d != best_day]
    per = min(best, sum(typ) / len(typ)) if typ else float(P["typical_day"])
    per = max(1.0, min(per, best) if best > 0 else per)
    m_cons = int(math.ceil(need_profit / per)) if need_profit > 0 else 0
    m_days = max(0, int(P["cycle_days"]) - len(cyc))
    more_days = max(m_cons, m_days)
    to_ask = round(max(0.0, P["buffer"] + P["ask_above"] - bal), 2)
    goal = P["buffer"] + P["ask_above"]
    out = {"v": VERSION, "name": name or P["label"], "plan": P.get("key"), "label": P["label"], "start": start, "today": today,
           "balance": round(P["start"] + bal, 2), "profit": round(bal, 2), "floor": round(P["start"] + floor, 2), "room": room,
           "locked": floor >= P["lock"] - 1e-9, "mll_after_payout": round(P["start"] + P["lock"], 2),
           "buffer": P["buffer"], "buffer_balance": round(P["start"] + P["buffer"], 2), "above_buffer": above,
           "ask_at_balance": round(P["start"] + goal, 2), "to_ask": to_ask,
           "ask_amount": min(P["pay_max"], P["ask_above"]), "ask_goal": round(goal, 2),   # MFFU's $0 view: $1,000 at $2,100 (25K)
           "buffer_frac": round(max(0.0, min(1.0, bal / goal)) if goal else 0.0, 4),
           "cycle_start": (_add_days(last, 1) if last else (start or first_trade)), "cycle_profit": cprof, "cycle_days": len(cyc),
           "cycle_days_need": int(P["cycle_days"]), "best_day": best, "best_day_on": best_day, "best_day_pct": best_pct,
           "cons_limit_pct": cons * 100, "cons_ok": cons_ok, "cons_need_profit": need_profit,
           "cons_frac": round(min(1.0, best / (cons * cprof)), 4) if cprof > 0 else (1.0 if best > 0 else 0.0),
           "more_days": more_days, "first_trade": first_trade, "eligible_from": eligible_from, "eligible": eligible,
           "ready": ready, "max_request": max_req if eligible else 0.0, "request_min": P["pay_min"], "request_max": P["pay_max"],
           "to_you": round((max_req if eligible else 0.0) * P["split"], 2), "split": P["split"],
           "payouts_n": n_pay, "payouts_max": int(P["max_payouts"]), "paid_gross": round(sum(pay.values()), 2),
           "paid_to_you": round(sum(pay.values()) * P["split"], 2), "graduated": graduated, "lost": lost, "why": why}
    out["stop4"] = stop4
    out["status"] = ("lost" if lost else "graduated" if graduated else "stop" if stop4 else "ready" if ready else "eligible" if eligible else
                     "consistency" if (cprof > 0 and not cons_ok) else "building")
    out["text"] = sentence(out)
    return out


def sentence(t: dict) -> str:
    """One plain line for the phone / PC card."""
    s = t.get("status")
    if s == "lost":
        return f"{t['name']}: the max-loss floor was reached, the funded account is gone. Buy a new eval."
    if s == "graduated":
        return f"{t['name']}: {t['payouts_n']} sim payouts done ({_money(t['paid_to_you'])} to you): MFFU moves you to live."
    if s == "stop":
        return (f"{t['name']}: 4 payouts taken. Do NOT take payout #5 (MFFU moves you to live and every sim account sleeps): "
                "close this account.")
    if s == "ready":
        return f"PAYOUT READY on {t['name']}: request {_money(t['max_request'])} in the MFFU dashboard ({_money(t['to_you'])} to you)."
    if s == "eligible":
        return (f"{t['name']}: MFFU would pay {_money(t['max_request'])} now; your plan waits for {_money(t['ask_amount'])} at "
                f"{_money(t['ask_goal'])} ({_money(t['to_ask'])} to go).")
    if s == "consistency":
        return (f"{t['name']}: consistency: best day is {t['best_day_pct']:.0f}% of the cycle, trade {t['more_days']} more "
                f"day(s) (about {_money(t['cons_need_profit'])} more profit on other days).")
    bits = [f"{_money(t['to_ask'])} to the payout line ({_money(t['ask_amount'])} at {_money(t['ask_goal'])} MFFU profit)"]
    if t.get("eligible_from") and t["today"] < t["eligible_from"]:
        bits.append(f"first request from {t['eligible_from']}")
    if t["cycle_days"] < t["cycle_days_need"]:
        bits.append(f"{t['cycle_days']}/{t['cycle_days_need']} traded days")
    return f"{t['name']}: " + ", ".join(bits) + f"; payouts {t['payouts_n']}/{t['payouts_max']}."


# ---------------------------------------------------------------------------------------------------- pushes
def notices(t: dict, now) -> list:
    """The pushes due for this tracker (stable keys: the notifier sends each once). Never a request: the owner asks MFFU."""
    from . import push
    out = []
    nm = t.get("name") or "funded"
    cyc = t.get("cycle_start") or "c0"
    base = f"funded:{nm}:{t.get('payouts_n', 0)}:{cyc}"

    def pl(sub, title, body, key):
        p = push.text_payload("PC", "ops", title[:120], body[:900], key=key, t=int(now), url="#/money")
        p["tag"] = f"le-funded-{sub}"
        out.append(p)
    s = t.get("status")
    if s == "ready":
        # the record line: an extra account's (engine.eval_life --payout --id) or t["record_cmd"] (ATLAS's account B:
        # engine.account_b --payout), "{day}" / "{amount}" filled in
        rec = (str(t["record_cmd"]).replace("{day}", str(t["today"])).replace("{amount}", f"{t['max_request']:.0f}")
               if t.get("record_cmd") else
               f"python -X utf8 -m engine.eval_life --payout {t['today']}={t['max_request']:.0f}" + (f" --id {t['id']}" if t.get("id") else ""))
        pl("ready", f"PAYOUT READY: request {_money(t['max_request'])}",
           f"{nm}: balance {_money(t['balance'])}, {_money(t['above_buffer'])} above the {_money(t['buffer'])} buffer, best day "
           f"{t['best_day_pct']:.0f}% of the cycle, {t['cycle_days']} traded days. Request {_money(t['max_request'])} in the MFFU "
           f"dashboard ({_money(t['to_you'])} to you at 80%). Then record it: {rec}"
           f". Payout {t['payouts_n'] + 1} of {t['payouts_max']}. The bot never requests it for you."
           + (f" WAIT: this is payout {t['payouts_max']} of {t['payouts_max']}: after it MFFU moves this account to LIVE and your other "
              "MFFU sim accounts go dormant. Ask Claude before you request it." if t["payouts_n"] + 1 >= t["payouts_max"] else ""),
           base + ":ready")
    elif s == "consistency" and _num(t.get("above_buffer"), 0) > 0:     # below the buffer there is no payout to wait for yet
        pl("cons", f"consistency: best day is {t['best_day_pct']:.0f}% of the cycle, trade {t['more_days']} more days",
           f"{nm}: best day {_money(t['best_day'])} of a {_money(t['cycle_profit'])} cycle; MFFU pays only when no day is more than "
           f"50%. About {_money(t['cons_need_profit'])} more profit on other days ({t['more_days']} day(s)). Not a breach: just keep "
           "trading; the bot sizes down near the cap.", f"{base}:cons:{t.get('best_day_on')}")
    elif s == "lost":
        pl("lost", "FUNDED ACCOUNT LOST", f"{nm}: the max-loss floor {_money(t['floor'])} was reached. The bot stopped trading "
           "it. Buy a new MFFU eval at your price ($91.80 50K / $63 25K with a code last time).", base + ":lost")
    elif s == "graduated":
        pl("grad", "5 sim payouts done: MFFU moves you to live", f"{nm}: {_money(t['paid_to_you'])} paid to you. MFFU moves the "
           "account to live; live trading needs you present (the bot never arms it).", base + ":grad")
    return out


# ---------------------------------------------------------------------------------------------------- the accounts
def from_account(a: dict, today: str | None = None) -> dict | None:
    """data.json / heartbeat account section (engine/accounts.build_accounts, kind "funded") -> its tracker, or None."""
    if not isinstance(a, dict) or a.get("kind") != "funded" or a.get("error"):
        return None
    if not a.get("funded") and not a.get("days"):
        return None                                  # nothing to rebuild from (old heartbeat): the balance-only view
    f = a.get("funded") or {}
    rules = a.get("plan_rules") or {}
    P = plan_of(f.get("plan") or f.get("preset"), _num(rules.get("start"), None))
    days = {str(d): float(v) for d, v in (a.get("days") or []) if d}
    start = f.get("start") or (a.get("eval") or {}).get("start")
    if start:
        days = {d: v for d, v in days.items() if d >= str(start)}
    t = track(days, f.get("payouts") or {}, P, today=today, start=start, name=a.get("name"))
    t["id"] = a.get("id")
    return t


def block(accounts: list | None, today: str | None = None) -> dict:
    """data.json / /api/next/goals "funded": every funded account's tracker + the plan-only lines when there is none."""
    rows = []
    for a in accounts or []:
        try:
            t = from_account(a, today)
        except Exception as e:                       # one card, never the page
            t = {"id": (a or {}).get("id"), "name": (a or {}).get("name"), "error": f"{e.__class__.__name__}: {str(e)[:100]}"}
        if t:
            rows.append(t)
    return {"v": VERSION, "accounts": rows, "n": len(rows),
            "default": "Eval passed -> the bot stops trading that eval and tells you. Funded trading starts only after you run "
                       "python -X utf8 -m engine.eval_life --to-funded --account \"<Name>\" --start <first funded day>.",
            "rules": {k: {kk: p[kk] for kk in ("buffer", "pay_min", "pay_max", "ask_above", "mll", "dll", "max_payouts", "split")}
                      for k, p in PLANS.items()},
            "max_funded": MAX_FUNDED}


def local_status(path: str | None = None, state_path: str | None = None, today: str | None = None) -> list:
    """The PC: every funded extra account in data/accounts.json, from its routed closes (data/live_state_accounts.json)."""
    from . import multi_account as ma
    out = []
    sp = state_path or ma._state_path_for(None)
    try:
        blobs = json.load(open(sp, encoding="utf-8")).get("accounts") or {}
    except Exception:
        blobs = {}
    for r in ma.load_file(path or ma.ACCOUNTS_PATH):
        if (r.get("mode") or "") != "funded":
            continue
        f = r.get("funded") or {}
        days = {}
        for row in (blobs.get(r.get("id")) or {}).get("closes") or []:
            d, p = str(row[0]), float(row[2])
            if not f.get("start") or d >= str(f["start"]):
                days[d] = round(days.get(d, 0.0) + p, 2)
        t = track(days, f.get("payouts") or {}, plan_of(r.get("preset")), today=today, start=f.get("start"),
                  name=r.get("name") or r.get("id"))
        t["id"] = r.get("id")
        out.append(t)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.funded_life", description="MFFU sim funded payout tracker (read-only)")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--file", default=None)
    a = ap.parse_args(argv)
    if a.demo:
        d = {"2026-11-03": 900.0, "2026-11-04": -300.0, "2026-11-05": 1500.0, "2026-11-06": 700.0, "2026-11-09": 1600.0}
        t = track(d, {}, "builder50k", today="2026-11-09", start="2026-11-03", name="demo 50K")
        print(json.dumps(t, indent=1))
        return 0
    rows = local_status(a.file)
    if not rows:
        print("No funded account yet. After a pass the bot stops that eval and tells you; then: "
              "python -X utf8 -m engine.eval_life --to-funded --account \"<Name>\" --start <first funded day>")
    for t in rows:
        print(t["text"])
    print(json.dumps(rows, indent=1)) if rows else None
    return 0


if __name__ == "__main__":
    sys.exit(main())
