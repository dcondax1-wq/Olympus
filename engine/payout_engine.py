"""PAYOUT ENGINE (big-payout 2026-11-26, lead: "money in the owner's pocket"). READ-ONLY: it NEVER requests a payout (the owner does,
in the MFFU dashboard), never trades, sizes, arms or routes. It only plans.

For every funded account the PC knows (ATLAS's Builder 25K: engine/account_b.funded_status; extra funded Builders:
engine/funded_life.local_status; funded Rapid EODs: engine/rapid.status) it says, in plain words:
  next payout: $X possible on <date> ($Y to you), keep $Z (the buffer: balance after the payout), and what blocks it now
The rules are MFFU's (research/lit/mffu_rules.json, re-read on MFFU's pages 2026-11-26: Builder 25K $1,100 buffer, $250-$1,000 a
request; 50K $2,100, $500-$2,000; 80 %; best day <= 50 % of the cycle; >= 2 traded days; 48 h after the first trade; 5 sim
payouts = live, so the owner takes 1-4 only. Rapid EOD: daily, $500 min, no cap, 90 %, $250 (25K) / $500 (50K) net since the last).
The date is a forecast at the account's own recent pace (its cycle's mean traded day, else the plan's typical day), counted in
trading days (no weekends, no CME holidays): an estimate, said as one.
The request habit comes from research/payout/results.json (the 12-month policy study) when it exists.

  python -X utf8 -m engine.payout_engine              every funded account, plain words
  python -X utf8 -m engine.payout_engine --today      the Telegram /today line
  python -X utf8 -m engine.payout_engine --tile       write the Money page tile (data/payout_tile.json, gitignored)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILE_PATH = os.path.join(ROOT, "data", "payout_tile.json")
STUDY_PATH = os.path.join(ROOT, "research", "payout", "results.json")
CME_CLOSED = {"2025-12-25", "2026-01-01", "2026-04-03", "2026-11-26", "2026-12-25", "2027-01-01", "2027-03-26"}
LAST = 4


def _f(x, d=None):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def usd(x) -> str:
    v = _f(x, 0.0) or 0.0
    return f"${v:,.0f}"


def add_trading_days(day: str, n: int) -> str:
    d = dt.date.fromisoformat(day)
    k = 0
    while k < n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in CME_CLOSED:
            k += 1
    return d.isoformat()


def habit(plan_key: str | None, path: str | None = None) -> str | None:
    """The 12-month study's pick for this kind of account (research/payout/results.json), plain words."""
    try:
        R = json.load(open(path or STUDY_PATH, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    acct = "50K LIT" if plan_key == "builder50k" else "25K ATLAS"
    p = (R.get("pick") or {}).get(acct) or {}
    a = p.get("adopt")
    return {"today = max": "ask for the full max each time (the study's pick)", "asap": "ask as soon as MFFU allows (the study's pick)",
            "half": "ask at half the max (the study's pick)", "max + cushion": "ask the max once 30 % more sits above the buffer",
            "cycle-timed": "ask by the cycle schedule (the study's pick)"}.get(a)


def builder_row(t: dict, key: str, today: str) -> dict:
    """One Builder funded tracker (engine/funded_life.track) -> the plan row."""
    t = t or {}
    nm = t.get("name") or t.get("label") or "Builder"
    split = _f(t.get("split"), 0.8) or 0.8
    n = int(_f(t.get("payouts_n"), 0) or 0)
    row = {"key": key, "name": nm, "kind": "builder", "plan": t.get("plan"), "balance": _f(t.get("balance")),
           "payouts_n": n, "status": t.get("status"), "blocks": []}
    if t.get("lost"):
        row.update(line="the funded account is lost: no payout", blocks=["account lost"])
        return row
    if n >= LAST:
        row.update(line="4 payouts taken: do NOT take #5 (MFFU moves you to live, every sim account sleeps); close it",
                   blocks=["payout #5 guard"])
        return row
    amt = min(_f(t.get("request_max"), 0.0) or 0.0, _f(t.get("ask_amount"), 0.0) or 0.0) or (_f(t.get("ask_amount"), 0.0) or 0.0)
    keep = _f(t.get("buffer_balance"))
    row["keep_balance"] = keep
    row["floor_after"] = _f(t.get("mll_after_payout"))
    if t.get("ready"):
        a = _f(t.get("max_request"), amt) or amt
        row.update(next_amount=a, to_you=round(a * split, 2), next_date=today, ready=True,
                   line=f"REQUEST TODAY: {usd(a)} ({usd(a * split)} to you); after it keep {usd(keep)} (the buffer)")
        return row
    # what blocks it, and when it should clear at this account's pace
    blocks = []
    to_ask = _f(t.get("to_ask"), 0.0) or 0.0
    cprof, cdays = _f(t.get("cycle_profit"), 0.0) or 0.0, int(_f(t.get("cycle_days"), 0) or 0)
    from . import funded_life as FL
    typ = float((FL.PLANS.get(t.get("plan") or "") or {}).get("typical_day") or 150.0)
    pace = cprof / cdays if cdays and cprof > 0 else typ
    pace = max(25.0, min(pace, 2 * typ))
    need_days = []
    if to_ask > 0:
        blocks.append(f"{usd(to_ask)} more profit to reach the ask line ({usd(t.get('ask_at_balance'))})")
        need_days.append(int(math.ceil(to_ask / pace)))
    if int(_f(t.get("more_days"), 0) or 0) > 0:
        md = int(_f(t.get("more_days"), 0) or 0)
        if not t.get("cons_ok", True):
            blocks.append(f"best day is {t.get('best_day_pct')}% of the cycle (50% max): {usd(t.get('cons_need_profit'))} more spread over days")
        elif cdays < int(_f(t.get("cycle_days_need"), 2) or 2):
            blocks.append(f"{int(_f(t.get('cycle_days_need'), 2)) - cdays} more traded day(s) in the cycle")
        need_days.append(md)
    ef = t.get("eligible_from")
    days = max(need_days) if need_days else 0
    date = add_trading_days(today, days) if days else today
    if ef and ef > date:
        blocks.append(f"MFFU's 48 h after the first trade: from {ef}")
        date = ef
    if t.get("eligible") and not t.get("ready"):
        blocks.insert(0, f"MFFU would pay {usd(t.get('max_request'))} now; the plan waits for the max {usd(t.get('ask_amount'))}")
    row.update(next_amount=amt, to_you=round(amt * split, 2), next_date=date, ready=False, blocks=blocks[:3], pace=round(pace),
               line=f"next payout: {usd(amt)} possible about {date} ({usd(amt * split)} to you), keep {usd(keep)}; "
                    + ("; ".join(blocks[:2]) if blocks else "building"))
    return row


def rapid_row(st: dict, key: str, label: str | None, today: str) -> dict:
    st = st or {}
    a = st.get("payout") or {}
    nm = label or st.get("label") or "Rapid EOD"
    row = {"key": key, "name": nm, "kind": "rapid", "balance": _f(st.get("balance")), "status": st.get("stage"), "blocks": []}
    if a.get("ready"):
        amt = _f(a.get("request"), 0.0) or 0.0
        row.update(ready=True, next_amount=amt, to_you=_f(a.get("to_you"), round(amt * 0.9, 2)), next_date=today,
                   keep_balance=_f(a.get("keep_at")),
                   line=f"REQUEST TODAY: {usd(amt)} ({usd(_f(a.get('to_you'), amt * 0.9))} to you); keep {usd(a.get('keep_at'))}")
        return row
    why = a.get("wait") or (f"{usd(a.get('since_short'))} more net since the last payout (MFFU's rule)" if a.get("since_short") is not None
                            else f"{usd(a.get('to_next'))} to go (the bot keeps {usd(a.get('keep_at'))} in)")
    row.update(ready=False, next_amount=_f(a.get("next_request"), 500.0), next_date=None, keep_balance=_f(a.get("keep_at")),
               blocks=[why], line=f"next payout: daily once {why}")
    return row


def gather(today: str | None = None, sources=None) -> list:
    """Every funded account -> rows. sources (tests) = {"atlas": tracker|None, "extras": [trackers], "rapids": [(key, status, label)]}."""
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date().isoformat()
    rows = []
    if sources is None:
        sources = {"atlas": None, "extras": [], "rapids": []}
        try:
            from . import account_b as AB
            s = AB.funded_status(today=today)
            if s.get("ok"):
                sources["atlas"] = s.get("tracker")
        except Exception:  # noqa: BLE001
            pass
        try:
            from . import funded_life as FL
            sources["extras"] = list(FL.local_status(today=today))
        except Exception:  # noqa: BLE001
            pass
        try:
            from . import rapid as R
            for slot in R.SLOTS:
                st = R.status(slot=slot)
                if st.get("on") and st.get("stage") == "funded":
                    sources["rapids"].append((slot, st, R.plan_info(R.read(R.slot_path(slot)) or {}).get("label")))
        except Exception:  # noqa: BLE001
            pass
    if sources.get("atlas"):
        rows.append(builder_row({**sources["atlas"], "name": sources["atlas"].get("name") or "ATLAS 25K"}, "atlas", today))
    for t in sources.get("extras") or []:
        rows.append(builder_row(t, f"x:{t.get('id')}", today))
    for key, st, label in sources.get("rapids") or []:
        rows.append(rapid_row(st, key, label, today))
    for r in rows:
        r["habit"] = habit(r.get("plan")) if r["kind"] == "builder" else None
    return rows


def today_line(rows: list | None = None) -> str:
    """The Telegram /today answer: one line per funded account, plain words (no ids)."""
    rows = gather() if rows is None else rows
    if not rows:
        return "Payouts: no funded account yet."
    ready = [r for r in rows if r.get("ready")]
    head = (f"Payouts: {len(ready)} ready today" if ready else "Payouts: none ready today") + \
        (f" ({usd(sum(r.get('to_you') or 0 for r in ready))} to you)" if ready else "")
    return "\n".join([head] + [f"- {r['name']}: {r['line']}" for r in rows])


def tile(rows: list | None = None, now: float | None = None) -> dict:
    """The Money page tile (JSON only; the lead wires the page). Small, no ids, no account names beyond the bot's labels."""
    rows = gather() if rows is None else rows
    nxt = sorted([r for r in rows if r.get("next_date")], key=lambda r: r["next_date"])
    out = {"v": 1, "t": int(now or time.time()), "n": len(rows),
           "ready_today": sum(1 for r in rows if r.get("ready")),
           "ready_to_you": round(sum(r.get("to_you") or 0 for r in rows if r.get("ready")), 2),
           "next": ({"name": nxt[0]["name"], "date": nxt[0]["next_date"], "amount": nxt[0].get("next_amount"),
                     "to_you": nxt[0].get("to_you")} if nxt else None),
           "rows": [{"name": r["name"], "kind": r["kind"], "ready": bool(r.get("ready")), "amount": r.get("next_amount"),
                     "to_you": r.get("to_you"), "date": r.get("next_date"), "keep": r.get("keep_balance"),
                     "blocks": (r.get("blocks") or [])[:2], "line": str(r.get("line"))[:160], "habit": r.get("habit")} for r in rows],
           "note": "read-only plan: the owner requests in the MFFU dashboard; dates are estimates at each account's own pace"}
    return out


def write_tile(path: str | None = None, rows: list | None = None) -> bool:
    try:
        p = path or TILE_PATH
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(tile(rows), fh, separators=(",", ":"))
        from . import fsutil
        fsutil.replace(p + ".tmp", p)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:])
    rows = gather()
    if "--tile" in a:
        ok = write_tile(rows=rows)
        print(("wrote " + os.path.relpath(TILE_PATH, ROOT)) if ok else "tile not written")
        return 0 if ok else 1
    print(today_line(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
