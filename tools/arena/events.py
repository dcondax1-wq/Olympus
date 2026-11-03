"""ARENA's verifiable trading events from the published site data (data.json, home.json). Pure: no I/O, no clock.

from_site(data, home, today) -> [event]   each {id, day (New York), kind, src: "site", t?, note}
  bot_day / bot_down   data.json perf.status, the Surface heartbeat's up % per weekday (engine/uptime.py): 90%+ / under 50%
  clean_trade          a closed trade that kept every rule HERMES checks (tools/hermes/wrapped.discipline): stop beyond the
  rule_broken          sweep, entry 02:00-15:30, flat by 15:55, hands off, and Zlarior's 1 trade a day (the 2nd one breaks it)
  plan_week            a finished week (Mon-Fri, judged from Saturday) with 2-4 Zlarior trades, all clean
  green_week           a finished week that closed green with every trade clean (the $ size never counts)
  lapse                an eval account with 7+ days between trades (or since its last one): a warning, no XP
  eval_passed          an account whose eval status says passed, or that is funded
  payout               each payout day recorded on a funded account (funded.payouts)
Nothing here reads a $ amount into XP: the amounts only decide green / not green, never how much.
"""
from __future__ import annotations

import datetime as dt

from tools.hermes import wrapped as W

UP_OK, UP_DOWN = 90.0, 50.0
PASSED = ("passed", "pass", "funded", "complete", "completed")


def _num(v):
    return W._num(v)


def _monday(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def uptime_events(data: dict) -> list:
    out = []
    parts = ((((data or {}).get("perf") or {}).get("status") or {}).get("parts")) or []
    surf = next((p for p in parts if isinstance(p, dict) and p.get("id") == "surface"), None)
    for row in (surf or {}).get("days") or []:
        if not (isinstance(row, (list, tuple)) and len(row) >= 2) or W._day(row[0]) is None:
            continue
        day, pct = row[0], _num(row[1])
        if pct is None or dt.date.fromisoformat(day).weekday() >= 5:
            continue
        if pct >= UP_OK:
            out.append({"id": f"bot_day:{day}", "day": day, "kind": "bot_day", "src": "site", "note": f"Heartbeat up {pct:.0f}% of the window"})
        elif pct < UP_DOWN:
            out.append({"id": f"bot_down:{day}", "day": day, "kind": "bot_down", "src": "site", "note": f"Heartbeat up {pct:.0f}% of the window"})
    return out


def broken_rules(t: dict) -> list:
    """The labels of the rules this one trade broke (HERMES's checks on a one-trade list)."""
    return [r["label"] for r in W.discipline([t])["rules"] if not r["ok"]]


def trade_events(trades: list) -> tuple[list, dict]:
    """(events, {trade id: clean?}): one event per closed trade, in order."""
    out, clean, per_day = [], {}, {}
    for t in trades:
        tid = f"trade:{t['account_id']}:{int(_num(t.get('entry_t')) or 0)}:{t['day']}"
        bad = broken_rules(t)
        if t["bot"] in ("Zlarior", "Paper twin"):
            k = (t["account_id"], t["day"])
            per_day[k] = per_day.get(k, 0) + 1
            if per_day[k] > 1:
                bad.append("1 trade a day")
        clean[tid] = not bad
        who = f"{t['bot']}{' (paper)' if t.get('paper') else ''}"
        out.append({"id": tid, "day": t["day"], "kind": "rule_broken" if bad else "clean_trade", "src": "site",
                    "t": int(_num(t.get("entry_t")) or 0),
                    "note": f"{who}: " + ("broke " + ", ".join(bad) if bad else "every rule kept")})
    return out, clean


def week_events(trades: list, clean: dict, today: str) -> list:
    """plan_week / green_week for every finished week (today past its Friday)."""
    weeks = {}
    for t in trades:
        weeks.setdefault(_monday(t["day"]), []).append(t)
    out = []
    for mon, T in sorted(weeks.items()):
        fri = (dt.date.fromisoformat(mon) + dt.timedelta(days=4)).isoformat()
        if today <= fri:
            continue                                            # not finished: 2-4 can still become 5
        ids = [f"trade:{t['account_id']}:{int(_num(t.get('entry_t')) or 0)}:{t['day']}" for t in T]
        all_clean = all(clean.get(i) for i in ids)
        z = [t for t in T if t["bot"] in ("Zlarior", "Paper twin")]
        if all_clean and 2 <= len(z) <= 4:
            out.append({"id": f"plan_week:{mon}", "day": fri, "kind": "plan_week", "src": "site",
                        "note": f"Week of {mon}: {len(z)} Zlarior trades, all inside the rules"})
        if all_clean and round(sum(t["pnl"] for t in T), 2) > 0:
            out.append({"id": f"green_week:{mon}", "day": fri, "kind": "green_week", "src": "site",
                        "note": f"Week of {mon}: green with every trade inside the rules"})
    return out


def account_events(data: dict, home: dict | None, trades: list, today: str) -> list:
    out = []
    accts = (data or {}).get("accounts") or (home or {}).get("accounts") or []
    days_by = {}
    for t in trades:
        days_by.setdefault(t["account_id"], set()).add(t["day"])
    for a in accts:
        if not isinstance(a, dict) or a.get("error") or str(a.get("id")) in W.PAPER_IDS or a.get("kind") == "paper":
            continue
        aid, name = str(a.get("id") or ""), str(a.get("name") or a.get("id") or "")
        ev = a.get("eval") if isinstance(a.get("eval"), dict) else {}
        fu = a.get("funded") if isinstance(a.get("funded"), dict) else None
        status = str(ev.get("status") or "").lower()
        if fu is not None or a.get("kind") == "funded" or status in PASSED:
            day = W._day((fu or {}).get("start")) or W._day(ev.get("passed_day")) or W._day(ev.get("today")) or today
            out.append({"id": f"eval_passed:{aid}", "day": day, "kind": "eval_passed", "src": "site", "note": f"{name}: eval passed"})
        for pday, amt in sorted(((fu or {}).get("payouts") or {}).items()):
            if W._day(pday) and (_num(amt) or 0) > 0:
                out.append({"id": f"payout:{aid}:{pday}", "day": pday, "kind": "payout", "src": "site", "note": f"{name}: payout recorded"})
        # 7-day inactivity: an open eval account with a gap of 7+ calendar days between trade days (or since the last one)
        days = sorted(days_by.get(aid, ()))
        if not days or status in ("failed", "fail", "breached") or fu is not None:
            continue
        for a_, b_ in zip(days, days[1:] + [today]):
            gap = (dt.date.fromisoformat(b_) - dt.date.fromisoformat(a_)).days
            if gap >= 8:
                lapse = (dt.date.fromisoformat(a_) + dt.timedelta(days=8)).isoformat()
                if lapse <= today:
                    out.append({"id": f"lapse:{aid}:{lapse}", "day": lapse, "kind": "lapse", "src": "site",
                                "note": f"{name}: 7 days without a trade after {a_}"})
    return out


def from_site(data: dict | None, home: dict | None, today: str) -> list:
    data = data or {}
    trades, _paper, _only = W.counted(data)
    tev, clean = trade_events(trades)
    ev = uptime_events(data) + tev + week_events(trades, clean, today) + account_events(data, home, trades, today)
    return [e for e in ev if e["day"] <= today]
