#!/usr/bin/env python3
"""SUNDAY MONEY REPORT (owner 2026-11-13): the money scoreboard as one plain table + three lines (what made money, what lost, what to
change), written to docs/reports/money_week_<sunday>.md (gitignored: it holds your own figures) and pushed to your phone on your
PRIVATE ntfy alert topic (the one tools/pc_report.py made, %USERPROFILE%\\.olympus\\ntfy.json, never in the repo). Read-only, paper only.

  python tools/weekly_money_report.py              write the report now and push it (any day)
  python tools/weekly_money_report.py --dry-run    print the report and the push, write and send nothing
  python tools/weekly_money_report.py --no-push    write the report, send nothing
  options: --site DIR (default: the PC's last built site data/pc_publish/site, else tools/web_public)  --ledger FILE  --now EPOCH_S

Scheduled with no new task: tools/pc_report.py (the 15-minute task OlympusPCReport) calls maybe_run() after its own run, and it
sends once a week, on Sunday from 17:00 New York time (state in data/money_report/state.json). LE_MONEY_WEEKLY=0 turns that off.
The suggestion line never says to arm, route or go live: that stays the owner's. Test: python -X utf8 -m tests.test_weekly_money_report
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import money_scoreboard as MS  # noqa: E402

REPORTS = os.path.join(ROOT, "docs", "reports")
WORK = os.path.join(ROOT, "data", "money_report")
PC_SITE = os.path.join(ROOT, "data", "pc_publish", "site")
SEND_FROM_HOUR = 17               # Sunday 17:00 ET onwards
MAX_PUSH = 3800                   # ntfy turns a longer message into a file


def et_now(now_s: float) -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(now_s, ZoneInfo("America/New_York"))
    except Exception:
        return dt.datetime.fromtimestamp(now_s - 5 * 3600, dt.timezone.utc)


def pick_site(site: str | None) -> str:
    if site:
        return site
    return PC_SITE if os.path.isfile(os.path.join(PC_SITE, "home.json")) else MS.WEB


# ------------------------------------------------------------------------------------------------ the three lines
def three_lines(sb: dict) -> list:
    cash = [(r["name"], r["week"]) for r in sb["by_source"] if MS.num(r.get("week")) is not None]      # real money this week, by source
    up = max(cash, key=lambda r: r[1], default=None)
    down = min(cash, key=lambda r: r[1], default=None)
    # paper this week: each eval / funded account's simulated P&L, and BLITZ (never cash)
    pw = [(f"{r['paper']['bot']} {r['kind']}", r["paper"].get("week")) for r in sb["by_source"] if r.get("paper")]
    pw += [(p["name"], p.get("week")) for p in sb["paper"] if p["id"] != "second"]
    pw = [(n, w) for n, w in pw if MS.num(w) is not None]
    best_paper = max(pw, key=lambda x: x[1], default=None)
    made = (f"Made money: {up[0]} {MS.money(up[1], True)} this week." if up and up[1] > 0.004 else "Made money: nothing put cash in this week.")
    if best_paper and best_paper[1] > 0.004:
        made += f" On paper (not cash): {best_paper[0]} {MS.money(best_paper[1], True)}."
    lost = f"Lost: {down[0]} {MS.money(down[1], True)} this week." if down and down[1] < -0.004 else "Lost: nothing took cash out this week."
    worst_paper = min(pw, key=lambda x: x[1], default=None)
    if worst_paper and worst_paper[1] < -0.004:
        lost += f" On paper: {worst_paper[0]} {MS.money(worst_paper[1], True)}."
    return [made, lost, "Change: " + suggestion(sb)]


def suggestion(sb: dict) -> str:
    """the ONE thing to change, by plain rules (first that applies). Never arming, routing or going live."""
    src = {s["id"]: s for s in sb["sources"]}
    T = sb["totals"]
    if src.get("ledger", {}).get("status") == "missing":
        return "save your Ledger's Export JSON as data/money_ledger.json on the PC, so payouts and Kalshi deposits count here."
    for sid in ("accounts", "kalshi"):
        s = src.get(sid) or {}
        if s.get("status") == "stale":
            return f"fix the {s['name']} feed: its numbers are {s['age']}."
    kal = next((r for r in sb["by_source"] if r["id"] == "kalshi"), None)
    if kal and (MS.num(kal.get("month")) or 0) < -0.004 and (MS.num(kal.get("week")) or 0) < -0.004:
        return f"Kalshi lost {MS.money(-kal['month'])} this month: read Kalshi City's 'If you change the bot' before next week (suggestions only)."
    if (MS.num(T["all"].get("pending")) or 0) > 0:
        return f"{MS.money(T['all']['pending'])} of payouts requested: record each one in the Ledger when it lands."
    if (sb["roi"].get("back") or 0) <= 0 and (sb["roi"].get("fees") or 0) > 0:
        return "no payout yet, so no change: the first cash comes when the 50K is funded and pays out. Keep the plan."
    return "no change: keep the plan."


# ------------------------------------------------------------------------------------------------ the report
def report(sb: dict, now_s: float) -> dict:
    day = sb["today"]
    T = sb["totals"]
    lines = three_lines(sb)
    title = f"Money week to {day}: net {MS.money(T['week']['net'], True)}"
    md = [f"# Money week to {day}", "",
          f"Paper only, read-only. Built {sb['built']} from {len(sb['sources'])} sources ({len(sb['missing'])} missing).", "",
          MS.table(sb), "", "## The week in three lines", ""] + [f"{i + 1}. {x}" for i, x in enumerate(lines)] + [""]
    if sb.get("notes"):
        md += ["## Honest limits", ""] + [f"- {n}" for n in sb["notes"]] + [""]
    push = [f"Week: in {MS.money(T['week']['cash_in'])}, out {MS.money(T['week']['cash_out'])}, net {MS.money(T['week']['net'], True)}",
            f"Month: net {MS.money(T['month']['net'], True)}. All time: net {MS.money(T['all']['net'], True)}",
            f"ROI on eval fees: {sb['roi']['text']}"]
    if sb.get("next"):
        push.append("Next: " + sb["next"]["text"])
    push += [""] + lines
    if sb["missing"]:
        push.append("Missing: " + ", ".join(m["name"] for m in sb["missing"]))
    body = "\n".join(push)
    if len(body.encode("utf-8")) > MAX_PUSH:
        body = body.encode("utf-8")[:MAX_PUSH].decode("utf-8", "ignore")
    return {"day": day, "title": title, "lines": lines, "markdown": "\n".join(md), "push": body}


def write_report(rep: dict, out_dir: str = REPORTS) -> str:
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"money_week_{rep['day']}.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(rep["markdown"])
    return p


def push(rep: dict, http=None, env=None, feed_path=None) -> tuple:
    """-> (ok, why). Your private alert topic of tools/pc_report.py; nothing when there is none."""
    from tools import pc_report as PR
    cfg = PR.load_cfg(env, feed_path)
    if not cfg["topic"] or not cfg["on"]:
        return False, "no private alert topic (python tools/pc_report.py --setup makes one)"
    return PR.ntfy_post(cfg["ntfy"], cfg["topic"], rep["push"], title=rep["title"], priority="default", tags="moneybag", http=http)


def run(now_s=None, site=None, ledger=None, out_dir=REPORTS, send=True, http=None, env=None, feed_path=None) -> dict:
    now_s = time.time() if now_s is None else now_s
    sb = MS.build(MS.gather(pick_site(site), ledger or MS.DEFAULT_LEDGER), now_s, include_ledger=True)
    rep = report(sb, now_s)
    rep["file"] = write_report(rep, out_dir)
    rep["sent"], rep["why"] = push(rep, http=http, env=env, feed_path=feed_path) if send else (False, "not sent (--no-push)")
    return rep


def due(now_s: float, state: dict) -> str | None:
    """the Sunday (ET) whose report is due now, else None: Sunday from 17:00 ET, once"""
    t = et_now(now_s)
    if t.weekday() != 6 or t.hour < SEND_FROM_HOUR:
        return None
    day = t.date().isoformat()
    return None if state.get("sent_day") == day else day


def maybe_run(now_s=None, work: str = WORK, http=None, env=None, out_dir=REPORTS, say=print, feed_path=None, site=None, ledger=None) -> dict | None:
    """The hook tools/pc_report.py calls every 15 minutes: does the Sunday report once. Never raises."""
    try:
        e = os.environ if env is None else env
        if str(e.get("LE_MONEY_WEEKLY", "1")) == "0":
            return None
        now_s = time.time() if now_s is None else now_s
        sp = os.path.join(work, "state.json")
        state = MS.read_json(sp) or {}
        day = due(now_s, state)
        if not day:
            return None
        rep = run(now_s, site=site, ledger=ledger, out_dir=out_dir, http=http, env=env, feed_path=feed_path)
        state.update(tried_day=day, tried_t=int(now_s), why=rep["why"])
        if rep["sent"] or str(rep["why"]).startswith("no private alert topic"):      # sent, or nowhere to send: once is enough
            state.update(sent_day=day, sent_t=int(now_s))
        os.makedirs(work, exist_ok=True)
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        say(f"  [OK]  Sunday money report: {rep['file']} ({'sent to your phone' if rep['sent'] else rep['why']})")
        return rep
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] Sunday money report skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The Sunday money report: a plain table + 3 lines, to docs/reports/ and your phone.")
    ap.add_argument("--site")
    ap.add_argument("--ledger")
    ap.add_argument("--now", type=float)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--out-dir", default=REPORTS)
    a = ap.parse_args(argv)
    now_s = time.time() if a.now is None else a.now
    if a.dry_run:
        sb = MS.build(MS.gather(pick_site(a.site), a.ledger or MS.DEFAULT_LEDGER), now_s, include_ledger=True)
        rep = report(sb, now_s)
        print(rep["markdown"])
        print("\n[dry] push title:", rep["title"])
        print(rep["push"])
        return 0
    rep = run(now_s, site=a.site, ledger=a.ledger, out_dir=a.out_dir, send=not a.no_push)
    print(f"money report -> {rep['file']}; push: {'sent' if rep['sent'] else rep['why']}")
    for x in rep["lines"]:
        print("  " + x)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print("money report failed softly:", f"{e.__class__.__name__}: {str(e)[:200]}")
        sys.exit(0)
