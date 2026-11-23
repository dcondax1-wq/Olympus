"""Thanksgiving week 2026 (night-newsweek 2026-11-23): the news calendar the bot and the brief read for Mon 11-23 .. Fri 11-27,
checked against the official schedules (bea.gov, census.gov, conference-board.org, fetched 2026-11-23; dol.gov's holiday-week
claims day), and the blackout windows they give. Reads the repo's own data/news/events.csv; changes nothing.

    python -X utf8 -m tests.test_news_week

 a. the week's rows load with the official day / time (claims, GDP, PCE, durables move to Wed 11-25; CB confidence Tue 11-24)
 b. MFFU Tier-1 (FOMC, minutes, jobs, CPI): NONE this week -> no Rapid-funded blackout Mon-Fri; the next one (Fri 12-04 08:30
    jobs report) blacks out exactly 08:27:00 .. 08:32:29 (the bot's 3 min / 2.5 min around MFFU's 2 / 2), the 08:30 fallback
    does not fire (November's CPI and jobs report are in the file)
 c. the LIT / ATLAS guard news filter is OFF by default (guards.DEFAULTS news False): the new rows change no trading
 d. the CME week: Thu 11-26 halt 13:00 ET, Fri 11-27 halt 13:15 ET (entry cut 15 min earlier); the brief's news line names
    Wednesday's releases
"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import multi_account as MA, news, guards as G, cme_calendar as C  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def ts(d, hh, mm, ss=0):
    y, m, dd = map(int, d.split("-"))
    return int(dt.datetime(y, m, dd, hh, mm, ss, tzinfo=ET).timestamp())


WEEK = ("2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27")
WANT = {("2026-11-24", "10:00", "CB Consumer Confidence (Nov)", "high"),
        ("2026-11-25", "08:30", "GDP Q3 second estimate", "high"),
        ("2026-11-25", "08:30", "Personal Income & Outlays / Core PCE (Oct)", "high"),
        ("2026-11-25", "08:30", "Durable Goods Orders (Oct)", "medium"),
        ("2026-11-25", "08:30", "Unemployment Claims (Thanksgiving week: Wednesday)", "medium"),
        ("2026-11-25", "10:00", "New Home Sales (Oct)", "medium"),
        ("2026-11-27", "08:30", "Advance Economic Indicators (Oct)", "low")}


def main():
    news._hist_cache.clear()
    ev = news.historical_events(("high", "medium", "low"))
    got = {(e["date"], e["time_et"], e["event"], e["impact"]) for e in ev if e["date"] in WEEK}
    check("a1. the week's 7 official rows load (day, time ET, event, impact)", WANT <= got, sorted(WANT - got))
    check("a2. nothing on Thanksgiving (Thu 11-26) and no Thursday claims row", not any(g[0] == "2026-11-26" for g in got), got)
    t = {e["event"]: e["t"] for e in ev if e["date"] in WEEK}
    check("a3. the times are exact ET instants", t["GDP Q3 second estimate"] == ts("2026-11-25", 8, 30)
          and t["CB Consumer Confidence (Nov)"] == ts("2026-11-24", 10, 0))
    MA._NEWS["key"] = None
    rel = {d: MA.tier1_releases(d) for d in WEEK}
    check("b1. MFFU Tier-1 this week: none (GDP / PCE / claims / CB are not Tier-1) -> no Rapid-funded blackout", all(v == [] for v in rel.values()), rel)
    nfp = MA.tier1_releases("2026-12-04")
    check("b2. the next Tier-1: Fri 12-04 08:30 (jobs report)", nfp == [ts("2026-12-04", 8, 30)], nfp)

    class Acct:
        def news_on(self):
            return True
    a = Acct()
    inside = [MA.Account.in_news(a, ts("2026-12-04", 8, 27, 0)), MA.Account.in_news(a, ts("2026-12-04", 8, 32, 29))]
    outside = [MA.Account.in_news(a, ts("2026-12-04", 8, 26, 59)), MA.Account.in_news(a, ts("2026-12-04", 8, 32, 30))]
    check("b3. the blackout is exactly 08:27:00 .. 08:32:29 (covers MFFU's 08:28 .. 08:32)", all(x == nfp[0] for x in inside)
          and all(x is None for x in outside) and MA.NEWS_PRE_S >= 120 and MA.NEWS_POST_S >= 120, (inside, outside))
    wed = [MA.Account.in_news(a, ts("2026-11-25", 8, 30)), MA.Account.in_news(a, ts("2026-11-25", 8, 29))]
    check("b4. Wed 11-25 08:30 (GDP / PCE / claims): no Rapid-funded blackout (not MFFU Tier-1)", wed == [None, None], wed)
    fb = {d: MA._fallback_830(d) & set(MA.tier1_releases(d)) for d in WEEK}
    check("b5. the 08:30 fail-closed fallback does not fire (November's CPI 11-10 and jobs 11-06 are in the file)",
          not any(fb.values()), fb)
    check("c. the LIT / ATLAS guard news filter is off by default: the new rows change no entry", G.DEFAULTS["news"] is False)
    halts = {d: C.early_close(d) for d in WEEK}
    check("d1. CME: Thu 11-26 halt 13:00 ET, Fri 11-27 halt 13:15 ET, Mon-Wed full days", halts == {"2026-11-23": None, "2026-11-24": None,
          "2026-11-25": None, "2026-11-26": 780, "2026-11-27": 795}, halts)
    check("d2. entry cut 15 min before the halt (12:45 Thu, 13:00 Fri)", (C.entry_cut("2026-11-26"), C.entry_cut("2026-11-27")) == (765, 780))
    try:
        from tools import morning_brief as MB
        line = MB.news_today(ts("2026-11-25", 7, 31))
        check("d3. the brief's news line on Wed 11-25 names GDP / PCE", "GDP" in line or "PCE" in line or "Personal Income" in line, line)
    except Exception as e:  # noqa: BLE001
        check("d3. the brief's news line", False, e)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
