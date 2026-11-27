"""THE DECEMBER MONEY PLAN (night-of-december 2026-11-27). PAPER / READ-ONLY: changes no bot, size, switch or account.

    python -X utf8 tools/december_plan.py [--month 2026-12] [--offline]
        -> tools/web_public/nq/december.json (the dashboard card) + docs/DECEMBER_PLAN.md (plain words)

Sources (no new data): engine/cme_calendar (closures / early halts, entry + flat cuts), data/news/events.csv (Tier-1 releases,
engine/news_official), engine/roll_watch.next_roll (the NQ / MNQ roll), the PC's k7 block (engine/clock7: MFFU 7-day clocks;
tools/board.fetch_lite, else the last december.json), research/forecast/forecast.json (tools/forecast.py on research/plans/rank.py:
pass / fail / first payout by session from today's balances), docs/ACCOUNT_RULES.md (payout rules), STRATEGY.md (trades a week),
research/writeups/taxes-2026-11-17.md (taxes). Public site file: no account ids, no names beyond the bot names.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from engine import cme_calendar as CME  # noqa: E402

OUT = os.path.join(ROOT, "tools", "web_public", "nq", "december.json")
DOC = os.path.join(ROOT, "docs", "DECEMBER_PLAN.md")
EVENTS = os.path.join(ROOT, "data", "news", "events.csv")
FORECAST = os.path.join(ROOT, "research", "forecast", "forecast.json")
FORECAST_CUM = os.path.join(ROOT, "research", "forecast", "forecast_cum.json")   # tools/forecast.py's by-session curves
LIT_FLAT_BEFORE = 5            # STRATEGY.md section 7: LIT closes 5 min before a high-impact release
LIT_WK = {"2026-like": 2.91, "H2": 2.56}      # STRATEGY.md "How LIT performed" (trades a week)
ATLAS_WK = {"2026-like": 2.16}                # STRATEGY.md ATLAS table (setups a week, 2026)
ACCTS = {  # forecast key -> what the plan shows (bot names only; owner's account ids stay private)
    "zlarior": {"name": "Zlarior 50K eval", "bots": "LIT", "k7": "mffu50k_eval", "target": 3000, "price": 91.80},
    "fresh25": {"name": "Zlarior 25K #2 eval", "bots": "LIT", "k7": "b25k_2", "target": 1500, "price": 63.00},
    "rapid1": {"name": "Rapid EOD 25K eval", "bots": "LIT + ATLAS", "k7": "rapid", "target": 1500, "price": 97.20},
    "atlas": {"name": "ATLAS 25K funded", "bots": "ATLAS", "k7": "atlas"},
}
ATLAS_PAY = {"buffer": 1100, "first_min_profit": 1350, "first_min_ask": 250, "goal_profit": 2100, "goal_ask": 1000, "split": 0.8}


def sessions(start: dt.date, n: int) -> list:
    """The next n CME trading dates from `start` (weekdays without a full closure)."""
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5 and not CME.full_closure(d):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def first_session(made):
    """The forecast's session 1 = the first CME session not yet over when it ran (made = 'YYYY-MM-DD HH:MM UTC')."""
    try:
        t = dt.datetime.strptime(str(made)[:16], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).astimezone(CME.ET)
    except ValueError:
        return None
    d = t.date() if t.hour < 18 else t.date() + dt.timedelta(days=1)     # after 18:00 ET the next trading date has begun
    if t.hour < 18 and t.hour * 60 + t.minute >= CME.flat_cut(d, 970):
        d += dt.timedelta(days=1)                                        # today's session is over
    return sessions(d, 1)[0]


def news(month: str) -> dict:
    by = {}
    try:
        with open(EVENTS, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["date"].startswith(month) or r["date"] == _next_month_first(month):
                    by.setdefault(r["date"], []).append({"t": r["time_et"], "what": r["event"], "impact": r["impact"]})
    except OSError:
        pass
    return by


def _next_month_first(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    return f"{y + (m == 12)}-{1 if m == 12 else m + 1:02d}-01"


def _hm(mod: int) -> str:
    return f"{mod // 60:02d}:{mod % 60:02d}"


K7_KEYS = ("id", "nm", "lf", "base", "dl", "hard", "left", "ses", "act", "on", "lvl")     # public-safe fields only


def k7_block(offline: bool) -> tuple:
    rows, src = _k7_raw(offline)
    return [{k: a.get(k) for k in K7_KEYS} for a in rows if isinstance(a, dict)], src


def _k7_raw(offline: bool) -> tuple:
    if not offline:
        try:
            import board as B
            d = B.fetch_lite()
            if d and isinstance(d.get("k7"), dict):
                return d["k7"].get("a") or [], "PC k7 block (board.fetch_lite)"
        except Exception:  # noqa: BLE001
            pass
    try:
        old = json.load(open(OUT, encoding="utf-8"))
        return old.get("k7_src_rows") or [], "last december.json"
    except (OSError, ValueError):
        return [], "none"


def _sub(t: str, m: int) -> str:
    h, mm = (int(x) for x in t.split(":"))
    return _hm(h * 60 + mm - m)


def day_rows(month: str, roll_day: dt.date, ev: dict, roll_names=("the old", "the next")) -> list:
    y, m = (int(x) for x in month.split("-"))
    d, rows = dt.date(y, m, 1), []
    while d.month == m:
        if d.weekday() < 5:
            iso = d.isoformat()
            closed = CME.full_closure(d)
            ec = CME.early_close(d)
            row = {"day": iso, "wd": d.strftime("%a"), "market": "closed" if closed else ("early" if ec is not None else "open"),
                   "halt": _hm(ec) if ec is not None else None, "news": ev.get(iso, []), "roll": d == roll_day, "flags": [], "bots": ""}
            if closed:
                row["bots"] = "CME closed: no session, no trades."
                row["flags"].append("closed")
            else:
                parts = []
                if ec is not None:
                    parts.append(f"half day: halt {_hm(ec)} ET; no new entry after {_hm(CME.entry_cut(d))}, everything flat by {_hm(CME.flat_cut(d))}")
                    row["flags"].append("early close")
                hi = [e for e in row["news"] if e["impact"] == "high"]
                for e in hi:
                    parts.append(f"{e['what']} {e['t']} ET: LIT flat by {_sub(e['t'], LIT_FLAT_BEFORE)} (5 min before); MFFU evals allow news")
                if hi:
                    row["flags"].append("news")
                for e in row["news"]:
                    if e["impact"] != "high":
                        parts.append(f"{e['what']} {e['t']} ET ({e['impact']}: no pause)")
                if row["roll"]:
                    parts.append(f"contract roll: orders move from {roll_names[0]} to {roll_names[1]} at 00:00 ET (roll_auto, hands-free)")
                    row["flags"].append("roll")
                row["bots"] = "; ".join(parts) if parts else "normal day: LIT and ATLAS take their usual setups, everything flat by 15:55 ET."
            rows.append(row)
        d += dt.timedelta(days=1)
    return rows


def k7_view(rows7: list, month: str) -> dict:
    y, m = (int(x) for x in month.split("-"))
    xmas_last = dt.date(y, 12, 21) if m == 12 else None
    out = {"rule": "MFFU closes an account after 7 calendar days with no executed trade; the bot's keep-alive trades 1 micro "
                   "when a clock gets short (switch on per account).",
           "accounts": [{"id": a.get("id"), "name": a.get("nm"), "last_fill": a.get("lf"), "safe_by": a.get("dl"),
                         "mffu_last_day": a.get("hard"), "keepalive_on": a.get("on")} for a in rows7]}
    if xmas_last:
        now = int(dt.datetime(y, 12, 22, 0, 0, tzinfo=CME.ET).timestamp())
        ip = CME.idle_plan(xmas_last.isoformat(), now)
        out["christmas_squeeze"] = (f"If an account's last trade is Mon Dec 21, its safe deadline is {ip['deadline']} and the only "
                                    f"session left is {ip['last_session']} (Christmas Eve half day, halt 13:15 ET): the keep-alive "
                                    f"must trade it, or trade any account that is quiet by Tue Dec 22.")
        now2 = int(dt.datetime(y, 12, 29, 0, 0, tzinfo=CME.ET).timestamp())
        ip2 = CME.idle_plan(f"{y}-12-28", now2)
        out["new_year"] = (f"New Year: Thu Dec 31 is a full day, Fri Jan 1 closed. Last trade Mon Dec 28 -> safe by {ip2['deadline']} "
                           f"({ip2['sessions_left']} sessions left): no squeeze.")
    return out


def weeks(days: list) -> list:
    by = {}
    for r in days:
        d = dt.date.fromisoformat(r["day"])
        mon = (d - dt.timedelta(days=d.weekday())).isoformat()
        w = by.setdefault(mon, {"week_of": mon, "sessions": 0.0})
        if r["market"] == "open":
            w["sessions"] += 1
        elif r["market"] == "early":
            w["sessions"] += 0.5            # a half day: about half the setups
    out = []
    for w in by.values():
        f = w["sessions"] / 5.0
        w["lit_trades"] = round(LIT_WK["2026-like"] * f, 1)
        w["atlas_trades"] = round(ATLAS_WK["2026-like"] * f, 1)
        out.append(w)
    return out


def forecast_view(F: dict, start: dt.date, month_end: dt.date) -> list:
    S = sessions(start, 40)
    k_end = sum(1 for d in S if d <= month_end)        # sessions from the forecast's run day to the month end
    out = []
    for key, meta in ACCTS.items():
        a = (F.get("accounts") or {}).get(key)
        if not a:
            continue
        row = {"key": key, "name": meta["name"], "bots": meta["bots"], "stage": a.get("stage"),
               "profit_now": (a.get("state") or {}).get("profit"), "room_now": (a.get("state") or {}).get("room")}
        for mk in ("2026-like", "2021-25-like"):
            m = a.get(mk) or {}
            if a.get("stage") == "funded":
                cum = m.get("payout_cum") or []
                med = m.get("first_payout_med_sessions")
                first_k = next((i + 1 for i, x in enumerate(cum) if x >= 5.0), None)     # the first day with a 5%+ chance
                row[mk] = {"payout_by_month_end_pct": cum[k_end - 1] if len(cum) >= k_end else None,
                           "earliest_day": S[first_k - 1].isoformat() if first_k else None,
                           "median_day": S[int(med) - 1].isoformat() if med and int(med) <= len(S) else None,
                           "payout_6m_pct": m.get("first_payout_pct"), "lost_6m_pct": m.get("lost_pct")}
            else:
                cum, fcum = m.get("pass_cum") or [], m.get("fail_cum") or []
                med = m.get("pass_med_sessions")
                row[mk] = {"pass_by_month_end_pct": cum[k_end - 1] if len(cum) >= k_end else None,
                           "fail_by_month_end_pct": fcum[k_end - 1] if len(fcum) >= k_end else None,
                           "median_pass_day": S[int(med) - 1].isoformat() if med and int(med) <= len(S) else None,
                           "pass_60_pct": m.get("pass_pct"), "fail_60_pct": m.get("fail_pct")}
        out.append(row)
    return out


def atlas_payout(fv: list) -> dict:
    a = next((r for r in fv if r["key"] == "atlas"), None)
    prof = (a or {}).get("profit_now") or 0.0
    g = (a or {}).get("2026-like") or {}
    return {"profit_now": round(prof, 2),
            "min_route": f"MFFU's first-payout minimum: profit ${ATLAS_PAY['first_min_profit']:,} (buffer ${ATLAS_PAY['buffer']:,} + $250) -> "
                         f"ask ${ATLAS_PAY['first_min_ask']} (${ATLAS_PAY['first_min_ask'] * ATLAS_PAY['split']:.0f} to you); "
                         f"${max(0, ATLAS_PAY['first_min_profit'] - prof):,.0f} more profit needed",
            "goal_route": f"The plan's first payout goal: ${ATLAS_PAY['goal_ask']:,} at ${ATLAS_PAY['goal_profit']:,} profit "
                          f"(${ATLAS_PAY['goal_ask'] * ATLAS_PAY['split']:.0f} lands); ${max(0, ATLAS_PAY['goal_profit'] - prof):,.0f} more needed",
            "forecast_earliest_day": g.get("earliest_day"), "forecast_median_day": g.get("median_day"),
            "forecast_by_month_end_pct": g.get("payout_by_month_end_pct"),
            "rules": "2 traded days a cycle, best day <= 50% of the cycle's profit, 48 h after the first funded trade; 5 sim payouts then live"}


TAXES = {"rule": "Move 30% of every payout into the tax pot the day it lands.",
         "dec_vs_jan": ("A payout that LANDS in December is 2026 income (paid with the Jan 15, 2027 quarterly 1040-ES for Sep-Dec); "
                        "one that lands in January is 2027 income (first 2027 quarterly due Apr 15, 2027). Same tax either way, "
                        "only the year and the due date move. Eval fees paid in 2026 lower 2026's profit."),
         "source": "research/writeups/taxes-2026-11-17.md (not tax advice: ask a pro for your own case)"}


def build(month="2026-12", offline=False, today=None) -> dict:
    today = today or dt.date.today()
    from engine import roll_watch as RW
    roll = RW.next_roll(today)
    roll_day = roll[0] if isinstance(roll, tuple) else (roll.get("day") if isinstance(roll, dict) else roll)
    if isinstance(roll_day, str):
        roll_day = dt.date.fromisoformat(roll_day[:10])
    if isinstance(roll_day, dt.datetime):
        roll_day = roll_day.date()
    ev = news(month)
    days = day_rows(month, roll_day, ev, (roll[1], roll[2]) if isinstance(roll, tuple) else ("the old", "the next"))
    rows7, src7 = k7_block(offline)
    try:
        F = json.load(open(FORECAST, encoding="utf-8"))
    except (OSError, ValueError):
        F = {}
    try:                                   # the by-session curves file (tools/forecast.py, same rows + pass_cum / payout_cum) wins
        C = json.load(open(FORECAST_CUM, encoding="utf-8"))
        if isinstance(C.get("accounts"), dict) and C["accounts"]:
            F = {**F, "made": C.get("made"), "accounts": C["accounts"]}
    except (OSError, ValueError):
        pass
    made = (F.get("made") or "")[:10]
    start = first_session(F.get("made")) or today
    y, m = (int(x) for x in month.split("-"))
    month_end = dt.date(y + (m == 12), 1 if m == 12 else m + 1, 1) - dt.timedelta(days=1)
    fv = forecast_view(F, start, month_end)
    n_open = sum(1 for r in days if r["market"] == "open")
    n_early = sum(1 for r in days if r["market"] == "early")
    doc = {"v": 1, "kind": "december-plan", "month": month, "made": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "paper_only": True, "note": "A plan to read: nothing here changes a bot, a size or an account.",
           "summary": {"sessions": n_open + n_early, "full_days": n_open, "half_days": n_early,
                       "closed": [r["day"] for r in days if r["market"] == "closed"],
                       "roll_day": roll_day.isoformat() if roll_day else None,
                       "news_high": [f"{r['day']} {e['t']} {e['what']}" for r in days for e in r["news"] if e["impact"] == "high"],
                       "lit_trades_month": round(sum(w["lit_trades"] for w in weeks(days)), 1),
                       "atlas_trades_month": round(sum(w["atlas_trades"] for w in weeks(days)), 1)},
           "caveats": ["Holiday hours (Dec 24 halt 13:15, Dec 25 closed, Dec 31 full day, Jan 1 closed) come from 5 years of CME bars "
                       "+ the rule (engine/cme_calendar); CME posts the exact hours about 2 weeks before: re-check around Dec 10.",
                       "The forecast is from today's balances on Jan-Oct 2026 (good) and 2021-25 (bad) market paths; the real "
                       "December can be either."],
           "days": days, "weeks": weeks(days), "k7": k7_view(rows7, month), "k7_src": src7, "k7_src_rows": rows7,
           "accounts": fv, "forecast_made": F.get("made"), "forecast_engine": F.get("engine"),
           "atlas_payout": atlas_payout(fv), "taxes": TAXES,
           "sources": ["engine/cme_calendar.py", "data/news/events.csv", "engine/roll_watch.py", src7, "research/forecast/forecast.json",
                       "docs/ACCOUNT_RULES.md", "STRATEGY.md", TAXES["source"]]}
    return doc


def _pct(x):
    return "-" if x is None else f"{x:.0f}%"


def _day(s):
    return "-" if not s else dt.date.fromisoformat(s).strftime("%a %b %d")


def markdown(doc: dict) -> str:
    s, ap = doc["summary"], doc["atlas_payout"]
    L = [f"# December {doc['month'][:4]} money plan", "",
         f"Built {doc['made']} by `python -X utf8 tools/december_plan.py` (dashboard: tools/web_public/nq/december.json). "
         "A plan to read: nothing here changes a bot, a size or an account.", "",
         "## The month in one look",
         f"- **{s['sessions']} trading sessions**: {s['full_days']} full days, {s['half_days']} half day(s); closed: "
         + ", ".join(_day(x) for x in s["closed"]) + ".",
         f"- **Contract roll {_day(s['roll_day'])}** 00:00 ET (Dec -> Mar contract, hands-free). The same morning has CPI at 08:30."
         if s["roll_day"] == "2026-12-10" else f"- **Contract roll {_day(s['roll_day'])}** 00:00 ET (hands-free).",
         "- **Big news:** " + "; ".join(s["news_high"]) + ". LIT goes flat 5 min before each; MFFU evals allow news trading.",
         f"- **Expected trades:** LIT about {s['lit_trades_month']:.0f} setups (copied to each LIT account), ATLAS about "
         f"{s['atlas_trades_month']:.0f} (2026 pace).",
         *[f"- Note: {c}" for c in doc["caveats"]], "",
         "## Your accounts by Dec 31 (forecast from today's balances, 1,000 paths)",
         "| account | bots | 2026-like market | 2021-25-like (bad) market |", "|---|---|---|---|"]
    for a in doc["accounts"]:
        g, b = a.get("2026-like") or {}, a.get("2021-25-like") or {}
        if a["stage"] == "funded":
            L.append(f"| {a['name']} (profit ${a['profit_now']:,.0f}) | {a['bots']} | first payout by Dec 31: {_pct(g.get('payout_by_month_end_pct'))}; "
                     f"median {_day(g.get('median_day'))} | {_pct(b.get('payout_by_month_end_pct'))} |")
        else:
            L.append(f"| {a['name']} (profit ${a['profit_now']:,.0f}) | {a['bots']} | pass {_pct(g.get('pass_by_month_end_pct'))} / fail "
                     f"{_pct(g.get('fail_by_month_end_pct'))}; median pass {_day(g.get('median_pass_day'))} | pass {_pct(b.get('pass_by_month_end_pct'))} / "
                     f"fail {_pct(b.get('fail_by_month_end_pct'))} |")
    L += ["", "## ATLAS funded: the first payout",
          f"- Profit now ${ap['profit_now']:,.0f}. {ap['min_route']}.", f"- {ap['goal_route']}.",
          f"- Forecast (2026-like): early case (5% of paths) {_day(ap['forecast_earliest_day'])}, median {_day(ap['forecast_median_day'])}, "
          f"{_pct(ap['forecast_by_month_end_pct'])} chance it is in by Dec 31. Rules: {ap['rules']}.",
          f"- **December cash, honest:** {_pct(ap['forecast_by_month_end_pct'])} x $800 = about "
          f"${(ap['forecast_by_month_end_pct'] or 0) / 100 * ATLAS_PAY['goal_ask'] * ATLAS_PAY['split']:,.0f} expected from ATLAS in December "
          "(2026-like market); the evals pay nothing until they pass and get funded (January at the earliest).", "",
          "## MFFU 7-day rule", f"- {doc['k7']['rule']}"]
    for a in doc["k7"]["accounts"]:
        L.append(f"- {a['name']}: last fill {_day(a['last_fill'])}, trade by {_day(a['safe_by'])} (MFFU's last day {_day(a['mffu_last_day'])}), "
                 f"keep-alive {'ON' if a['keepalive_on'] else 'OFF'}.")
    for k in ("christmas_squeeze", "new_year"):
        if doc["k7"].get(k):
            L.append(f"- {doc['k7'][k]}")
    L += ["", "## Week by week", "| week of | sessions | LIT setups | ATLAS setups |", "|---|---|---|---|"]
    for w in doc["weeks"]:
        L.append(f"| {_day(w['week_of'])} | {w['sessions']:g} | ~{w['lit_trades']:.1f} | ~{w['atlas_trades']:.1f} |")
    L += ["", "## Day by day", "| day | market | what the bots do |", "|---|---|---|"]
    for r in doc["days"]:
        mk = {"open": "open", "early": f"half day (halt {r['halt']})", "closed": "CLOSED"}[r["market"]]
        L.append(f"| {_day(r['day'])} | {mk} | {r['bots']} |")
    L += ["", "## Taxes", f"- {doc['taxes']['rule']}", f"- {doc['taxes']['dec_vs_jan']}", f"- Source: {doc['taxes']['source']}.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="2026-12")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    doc = build(a.month, a.offline)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write(markdown(doc))
    print(f"december plan: {doc['summary']['sessions']} sessions, roll {doc['summary']['roll_day']}, {len(doc['summary']['news_high'])} big news, "
          f"k7 from {doc['k7_src']} -> {os.path.relpath(OUT, ROOT)} + {os.path.relpath(DOC, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
