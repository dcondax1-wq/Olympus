"""NQ DASH exports for the phone (night-nqdash2 2026-11-20): two small public copies of files the site did not publish yet.
  1. research/lab/payday_plan.json (tools/money/payday_plan.py) -> tools/web_public/business/payday.json: each account's "first payout"
     date range for the MFFU account center (business/mffu.html, ../nqdeep.js payout()). Only dates, $ and odds per account name.
  2. data/news/events.csv (the bot's own high-impact US calendar: BLS, Fed, ...) -> tools/web_public/nq/news_week.json: the events from
     7 days back to 28 days ahead, for the NQ page's "News this week" card (../nqdeep.js weekNews()).
No account ids, no balances, no network.

    python tools/nqdash_export.py            # rewrite both
    python tools/nqdash_export.py --check    # exit 1 when a public copy is out of date (the news copy is checked for today's window)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "research", "lab", "payday_plan.json")
OUT = os.path.join(ROOT, "tools", "web_public", "business", "payday.json")
KEEP = ("name", "first_pay_p10", "first_pay_p25", "first_pay_med", "first_pay_p75", "first_pay_p90", "first_pay_usd", "first_pay_usd_p10",
        "p_by_dec31", "p_by_jan15", "p_by_jan31", "p_no_pay_6m", "p_lost_before_pay", "funded_med", "funded_p10", "p_funded_by_dec31")
ACCTS = ("Z50", "N25", "A25", "R25")
NEWS_SRC = os.path.join(ROOT, "data", "news", "events.csv")
NEWS_OUT = os.path.join(ROOT, "tools", "web_public", "nq", "news_week.json")


def build(plan: dict) -> dict:
    rows = {}
    for m, r in (plan.get("rows") or {}).items():
        acc = (r or {}).get("accounts") or {}
        rows[m] = {"accounts": {k: {f: acc[k].get(f) for f in KEEP if f in acc[k]} for k in ACCTS if isinstance(acc.get(k), dict)}}
    return {"v": 1, "src": "research/lab/payday_plan.json (tools/money/payday_plan.py), copied by tools/nqdash_export.py",
            "what": "ESTIMATES: the first payout date per account from 1,000 simulated runs of each market kind. Not a promise.",
            "date": plan.get("date"), "n": plan.get("n"), "markets": plan.get("markets") or {}, "rows": rows}


def news(path: str, today: dt.date) -> dict:
    lo, hi, ev = today - dt.timedelta(days=7), today + dt.timedelta(days=28), []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                d = dt.date.fromisoformat((r.get("date") or "").strip())
            except ValueError:
                continue
            if lo <= d <= hi and (r.get("impact") or "").strip().lower() == "high":
                ev.append({"date": d.isoformat(), "time": (r.get("time_et") or "").strip()[:5], "title": (r.get("event") or "").strip()[:70],
                           "impact": "high", "country": "USD"})
    ev.sort(key=lambda e: (e["date"], e["time"]))
    return {"v": 1, "src": "data/news/events.csv (the bot's high-impact US calendar), copied by tools/nqdash_export.py", "built": today.isoformat(),
            "from": lo.isoformat(), "to": hi.isoformat(), "events": ev}


def _write(path: str, obj: dict, check: bool) -> bool:
    text = json.dumps(obj, indent=1, ensure_ascii=False) + "\n"
    cur = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    name = os.path.relpath(path, ROOT)
    if check:
        print(f"{name} is current" if cur == text else f"{name} is OUT OF DATE: run python tools/nqdash_export.py")
        return cur == text
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {name} ({len(text)} bytes)")
    return True


def main(argv: list[str]) -> int:
    check = "--check" in argv
    with open(SRC, encoding="utf-8") as fh:
        ok = _write(OUT, build(json.load(fh)), check)
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    ok = _write(NEWS_OUT, news(NEWS_SRC, today), check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
