"""CONNECT THE DAY (team X2, 2026-11-14): tools/ics_parse.py + tools/calendar_sync.py, the private /site/day/ route of engine/live_site.py.
Fixtures in tests/fixtures/calendar/ (Google, iCloud, Outlook, six shift apps, DST). Fake network and temp folders only: never a real
calendar, never the real %USERPROFILE%\\.olympus, never data/day/.
    python -X utf8 -m tests.test_calendar_sync            (a parser  b recurring  c zones / DST  d shift apps  e the day's sentence
                                                          f week line  g sync + privacy  h the PC route  i the feeds  j the inbox)
    python -X utf8 -m tests.test_calendar_sync --only=a,b
"""
from __future__ import annotations

import datetime as dt
import re
import json
import os
import shutil
import stat
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import calendar_sync as CS  # noqa: E402
from tools import ics_parse as I  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "calendar")
RES = []
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv[1:] if a.startswith("--only=")), None)
NY = I.new_york()
UTC = dt.timezone.utc


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def part(k):
    return ONLY is None or k in ONLY


def rd(name):
    with open(os.path.join(FX, name), encoding="utf-8") as fh:
        return fh.read()


def utc(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=UTC).timestamp()


MON_0800 = utc(2026, 11, 16, 13, 0)          # Monday 16 Nov 2026, 08:00 EST
SHIFT_PARTS = rd("shiftapps.ics").split("===\n")
SHIFT_URLS = ["https://app.wheniwork.com/ical/abc.ics", "https://once.deputy.com/my/ical/abc", "https://app.7shifts.com/ical/abc",
              "https://app.joinhomebase.com/ical/abc", "https://api.getsling.com/ical/abc", "https://app.hotschedules.com/ical/abc"]
SECRET_URLS = {"google": "https://calendar.google.com/calendar/ical/demo.owner%40gmail.com/private-0123456789abcdef/basic.ics",
               "icloud": "webcal://p52-caldav.icloud.com/published/2/MTIzNDU2Nzg5MDEyMzQ1Ng-secret",
               "outlook": "https://outlook.office365.com/owa/calendar/aaaa@contoso.com/bbbbsecret/reachcalendar.ics"}


def occ(text, a, b):
    cal = I.parse(text)
    return cal, I.occurrences(cal, a, b)


def nyd(y, mo, d, h=0, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=NY)


def at_ny(o):
    return o["start"].astimezone(UTC).astimezone(NY)


def by_title(lst, t):
    return [o for o in lst if o["title"] == t]


# ------------------------------------------------------------------------------------------------ a. the parser
def test_parser():
    g = rd("google.ics").replace("\n", "\r\n")               # Google serves CRLF
    cal = I.parse(g)
    check("a. Google: calendar name and X-WR-TIMEZONE read, 7 VEVENTs (5 masters, 2 overrides), nothing bad", cal.name == "demo.owner@gmail.com"
          and cal.tz_name == "America/New_York" and len(cal.events) == 5 and sum(len(v) for v in cal.overrides.values()) == 2 and cal.bad == 0,
          (cal.name, cal.tz_name, len(cal.events), cal.overrides.keys(), cal.bad))
    check("a. escaped text: 'Dentist\\, check-up' reads as 'Dentist, check-up ...'", any(e["title"].startswith("Dentist, check-up") for e in cal.events))
    check("a. split_prop: quoted parameter with a colon", I.split_prop('DTSTART;TZID="A:B";X=1:20261114T090000') == ("DTSTART", {"TZID": "A:B", "X": "1"}, "20261114T090000"))
    check("a. folded lines are joined (DESCRIPTION across two lines)", "555-0100 any time" in "".join(I.unfold("DESCRIPTION:Call 555-010\r\n 0 any time")))
    check("a. DURATION P1DT2H30M / -PT15M / junk", I.duration("P1DT2H30M") == dt.timedelta(days=1, hours=2, minutes=30) and I.duration("-PT15M") == -dt.timedelta(minutes=15)
          and I.duration("soon") is None)
    d, ad = I.parse_dt("20261120", {"VALUE": "DATE"}, NY)
    t, _ = I.parse_dt("20261117T150000Z", {}, NY)
    f, _ = I.parse_dt("20261117T100000", {}, I.zone("America/Denver"))
    check("a. DATE / UTC Z / floating time", d == dt.date(2026, 11, 20) and ad and t.tzinfo == UTC and f.astimezone(NY).hour == 12, (d, t, f))
    junk = I.parse("not a calendar at all\nBEGIN:VEVENT\nSUMMARY:x\nEND:VEVENT")
    check("a. a broken file never raises: the event without DTSTART is counted bad", junk.bad == 1 and not junk.events)
    empty = I.parse("")
    check("a. an empty text -> an empty calendar", not empty.events and empty.bad == 0)


# ------------------------------------------------------------------------------------------------ b. recurring events
def test_recurring():
    g = rd("google.ics")
    _, o = occ(g, nyd(2026, 11, 9), nyd(2026, 12, 1))
    gym = sorted(at_ny(x).strftime("%m-%d %H:%M") for x in o if x["title"].startswith("Gym"))
    check("b. Google weekly MO,TH: EXDATE 19 Nov gone, 23 Nov moved to 19:00 (RECURRENCE-ID), 26 Nov cancelled", gym ==
          ["11-09 18:00", "11-12 18:00", "11-16 18:00", "11-23 19:00", "11-30 18:00"], gym)
    check("b. a cancelled single event is left out", not by_title(o, "Cancelled call"))
    trip = by_title(o, "Weekend trip")
    check("b. all-day 20-22 Nov: one entry, dates kept, TRANSP:TRANSPARENT = not busy", len(trip) == 1 and trip[0]["all_day"] and trip[0]["start"] == dt.date(2026, 11, 20)
          and trip[0]["end"] == dt.date(2026, 11, 22) and trip[0]["busy"] is False, trip)
    _, o2 = occ(g, nyd(2027, 1, 1), nyd(2027, 2, 1))
    check("b. UNTIL=20261231T225959Z: no gym in January 2027", not [x for x in o2 if x["title"].startswith("Gym")])
    c = rd("icloud.ics")
    _, o = occ(c, nyd(2026, 9, 1), nyd(2027, 4, 1))
    call = [at_ny(x).strftime("%Y-%m-%d %H:%M") for x in by_title(o, "Family video call")]
    check("b. iCloud monthly BYDAY=2TU 17:00 Pacific with DURATION 1h30 -> 20:00 ET on the 2nd Tuesday", call[:4] == ["2026-09-08 20:00", "2026-10-13 20:00", "2026-11-10 20:00", "2026-12-08 20:00"]
          and all((x["end"] - x["start"]) == dt.timedelta(minutes=90) for x in by_title(o, "Family video call")), call)
    rent = [at_ny(x).strftime("%Y-%m-%d") for x in by_title(o, "Pay rent online")]
    check("b. MONTHLY BYDAY=-1FR COUNT=6: the last Friday, six times", rent == ["2026-10-30", "2026-11-27", "2026-12-25", "2027-01-29", "2027-02-26", "2027-03-26"], rent)
    bd = [x["start"] for x in by_title(o, "Mom's birthday")]
    check("b. YEARLY all-day from 1990: the 2026 birthday is there", dt.date(2026, 11, 19) in bd, bd)
    check("b. YEARLY INTERVAL=4 from 2024: nothing in 2026", not by_title(o, "Every four years"))
    _, o3 = occ(c, nyd(2028, 11, 1), nyd(2028, 12, 1))
    check("b. ... and it is back in 2028", len(by_title(o3, "Every four years")) == 1)
    # rules built here: BYMONTHDAY negative, BYSETPOS, interval weekly, COUNT across the window start
    base = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x\nSUMMARY:T\nDTSTART;TZID=America/New_York:{s}\nDTEND;TZID=America/New_York:{e}\nRRULE:{r}\nEND:VEVENT\nEND:VCALENDAR\n"
    _, o = occ(base.format(s="20260131T080000", e="20260131T090000", r="FREQ=MONTHLY;BYMONTHDAY=-1"), nyd(2026, 1, 1), nyd(2026, 5, 1))
    check("b. BYMONTHDAY=-1: the last day of each month (Jan 31, Feb 28, Mar 31, Apr 30)", [x["start"].day for x in o] == [31, 28, 31, 30], [x["start"] for x in o])
    _, o = occ(base.format(s="20260130T080000", e="20260130T090000", r="FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;COUNT=3"), nyd(2026, 1, 1), nyd(2026, 6, 1))
    check("b. BYSETPOS=-1 with weekdays: the last working day (Jan 30, Feb 27, Mar 31)", [x["start"].date().isoformat() for x in o] == ["2026-01-30", "2026-02-27", "2026-03-31"], [x["start"] for x in o])
    _, o = occ(base.format(s="20261102T090000", e="20261102T170000", r="FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE"), nyd(2026, 11, 1), nyd(2026, 12, 1))
    check("b. WEEKLY INTERVAL=2 BYDAY=MO,WE: every other week", [x["start"].day for x in o] == [2, 4, 16, 18, 30], [x["start"].day for x in o])
    _, o = occ(base.format(s="20261001T090000", e="20261001T100000", r="FREQ=DAILY;COUNT=10"), nyd(2026, 10, 8), nyd(2026, 11, 1))
    check("b. DAILY COUNT=10 counts from DTSTART, not from the window (Oct 8, 9, 10 left)", [x["start"].day for x in o] == [8, 9, 10], [x["start"].day for x in o])
    _, o = occ(base.format(s="20261101T080000", e="20261101T081500", r="FREQ=HOURLY"), nyd(2026, 11, 1), nyd(2026, 11, 3))
    cal = I.parse(base.format(s="20261101T080000", e="20261101T081500", r="FREQ=HOURLY"))
    I.occurrences(cal, nyd(2026, 11, 1), nyd(2026, 11, 3))
    check("b. an unsupported rule (HOURLY): the first instance only, counted as skipped", len(o) == 1 and cal.skipped == 1, (len(o), cal.skipped))
    _, o = occ(base.format(s="20261102T090000", e="20261102T170000", r="FREQ=DAILY"), nyd(2026, 11, 1), nyd(2026, 11, 15))
    check("b. an endless DAILY rule stops at the window (14 instances, no runaway)", len(o) == 13, len(o))


# ------------------------------------------------------------------------------------------------ c. time zones and the clock change
def test_zones():
    d = rd("dst.ics")
    cal, o = occ(d, nyd(2026, 2, 1), nyd(2026, 12, 31))
    w = by_title(o, "Weekly 9am")
    check("c. a weekly 09:00 New York event stays 09:00 through the clock change (UTC 13:00 -> 14:00)", [at_ny(x).hour for x in w] == [9, 9, 9]
          and [x["start"].astimezone(UTC).hour for x in w] == [13, 14, 14], [(x["start"], x["start"].astimezone(UTC)) for x in w])
    amb = by_title(o, "Ambiguous hour")[0]
    check("c. 01:30 on the clock-back night = the first one (EDT, 05:30 UTC)", amb["start"].astimezone(UTC).strftime("%H:%M") == "05:30", amb["start"].astimezone(UTC))
    gap = by_title(o, "Gap hour")[0]
    check("c. 02:30 on the clock-forward night does not exist: read as 03:30 EDT (07:30 UTC)", gap["start"].astimezone(UTC).strftime("%H:%M") == "07:30"
          and at_ny(gap).strftime("%H:%M") == "03:30", (gap["start"].astimezone(UTC), at_ny(gap)))
    lon = [at_ny(x).strftime("%m-%d %H:%M") for x in by_title(o, "London call")]
    check("c. London 14:00 weekly in New York: 09:00, then 10:00 while only the US has moved its clocks, then 09:00", lon ==
          ["03-02 09:00", "03-09 10:00", "03-16 10:00", "03-23 10:00", "03-30 09:00"], lon)
    isl = {x["title"]: x["start"].astimezone(UTC).strftime("%H:%M") for x in o if x["title"].startswith("Island")}
    check("c. a zone Python does not know (Custom/Island): the file's own VTIMEZONE rules (+02 summer, +01 winter)", isl == {"Island noon (summer)": "10:00", "Island noon (winter)": "11:00"}, isl)
    night = by_title(o, "Night shift over the clock change")[0]
    check("c. a night shift 22:00 -> 06:00 over the clock change lasts 9 real hours", (night["end"] - night["start"]) == dt.timedelta(hours=9)
          or (night["end"].astimezone(UTC) - night["start"].astimezone(UTC)) == dt.timedelta(hours=9), (night["start"], night["end"]))
    check("c. the broken event is counted, not shown", cal.bad == 1 and not by_title(o, "No start at all"))
    segs = CS._segments(night["start"], night["end"])
    check("c. ... and it is cut at midnight into two New York days", [s[0] for s in segs] == ["2026-10-31", "2026-11-01"] and segs[0][1:] == (1320, 1440) and segs[1][1:] == (0, 360), segs)
    # the rule-based zone (no tzdata on the PC) gives the same offsets as Python's database, every hour of 2026-2027
    us = I.us_rule("America/New_York", -5)
    ok, bad = 0, []
    t = dt.datetime(2026, 1, 1, tzinfo=UTC)
    while t < dt.datetime(2028, 1, 1, tzinfo=UTC):
        a, b = t.astimezone(NY), t.astimezone(us)
        if a.replace(tzinfo=None) == b.replace(tzinfo=None) and a.utcoffset() == b.utcoffset():
            ok += 1
        else:
            bad.append((t, a, b))
        t += dt.timedelta(hours=1)
    check("c. the US rule zone = the zone database for every hour of 2026-2027 (from UTC)", not bad, bad[:3])
    bad2 = []
    for day in (dt.date(2026, 3, 8), dt.date(2026, 11, 1), dt.date(2027, 3, 14), dt.date(2027, 11, 7), dt.date(2026, 7, 4), dt.date(2026, 12, 25)):
        for mins in range(0, 1440, 15):
            naive = dt.datetime.combine(day, dt.time()) + dt.timedelta(minutes=mins)
            if naive.replace(tzinfo=NY).utcoffset() != naive.replace(tzinfo=us).utcoffset():
                bad2.append(naive)
    check("c. ... and for every wall-clock quarter hour of the clock-change days (fold 0)", not bad2, bad2[:4])
    for name, want in (("Eastern Standard Time", "America/New_York"), ("Pacific Standard Time", "America/Los_Angeles"), ("/mozilla.org/20050126_1/America/Chicago", "America/Chicago")):
        z = I.zone(name)
        check(f"c. TZID '{name}' -> {want}", z is not None and dt.datetime(2026, 7, 1, 12, tzinfo=z).utcoffset() == dt.datetime(2026, 7, 1, 12, tzinfo=I.zone(want)).utcoffset())
    check("c. 'UTC+05:30' style and an unknown name", I.zone("UTC+05:30").utcoffset(None) == dt.timedelta(minutes=330) and I.zone("Nowhere/Land") is None)


# ------------------------------------------------------------------------------------------------ d. the shift apps
def shift_cals():
    names = ["When I Work", "Deputy", "7shifts", "Homebase", "Sling", "HotSchedules"]
    return [({"name": n, "url": u, "work": None}, t, {"ok": True}) for n, u, t in zip(names, SHIFT_URLS, SHIFT_PARTS)]


def all_cals():
    return [({"name": "Personal", "url": CS.normalize_url(SECRET_URLS["google"]), "work": None}, rd("google.ics").replace("\n", "\r\n"), {"ok": True}),
            ({"name": "Family", "url": CS.normalize_url(SECRET_URLS["icloud"]), "work": None}, rd("icloud.ics"), {"ok": True}),
            ({"name": "Office", "url": CS.normalize_url(SECRET_URLS["outlook"]), "work": True}, rd("outlook.ics"), {"ok": True})] + shift_cals()


def test_shift_apps():
    col = CS.collect(shift_cals(), MON_0800)
    rows = {c["name"]: c for c in col["calendars"]}
    check("d. every shift app's address is a work calendar by its host", all(rows[n]["work"] is True for n in rows), {n: rows[n]["work"] for n in rows})
    ev = {(e["cal"], e["day"], e["start"], e["end"]): e for e in col["events"]}
    want = [("When I Work", "2026-11-16", "09:00", "17:00"), ("Deputy", "2026-11-17", "07:00", "15:30"), ("7shifts", "2026-11-18", "22:00", "06:00"),
            ("Homebase", "2026-11-17", "12:00", "18:00"), ("Sling", "2026-11-18", "16:00", "22:00"), ("HotSchedules", "2026-11-20", "07:00", "15:30"),
            ("7shifts", "2026-11-21", "17:00", "23:00")]
    miss = [w for w in want if w not in ev or not ev[w]["work"]]
    check("d. UTC shifts, Chicago / Denver (floating + X-WR-TIMEZONE) / quoted TZID shifts land at the right New York hours, flagged work", not miss, (miss, sorted(ev)))
    check("d. an Open Shift is not yours and Time Off is not work", not any(e["work"] for e in col["events"] if "Open Shift" in e["title"] or "Time Off" in e["title"]))
    nd = col["per_day"]["2026-11-19"]["segs"]
    check("d. the 7shifts night shift continues on Thursday 00:00-06:00", any(s["from"] == 0 and s["to"] == 360 and s["work"] for s in nd), nd)
    cal = I.Calendar()
    check("d. a personal calendar: 'Shift at the store' is work, 'Work dinner' is not a shift app but still reads as work, 'Lunch' is a break",
          CS._is_work({"name": "Personal", "url": "https://calendar.google.com/x"}, cal, "Shift at the store", False)
          and not CS._is_work({"name": "Personal", "url": "https://calendar.google.com/x"}, cal, "Dentist", False)
          and not CS._is_work({"name": "Work", "url": "https://x.example/y", "work": True}, cal, "Lunch break", False))
    check("d. work: false on a calendar wins over its host", not CS._is_work({"name": "Shifts", "url": SHIFT_URLS[0], "work": False}, cal, "Cashier", False))


# ------------------------------------------------------------------------------------------------ e. the day's sentence (shifts over the trading windows)
def day_with(segs, day="2026-11-16", mkt=None, live=False):
    return CS.advise(day, {"segs": [{"from": a, "to": b, "work": w, "busy": True, "brk": br, "title": ""} for a, b, w, br in segs], "allday": []}, mkt or {}, live_needed=live)


def test_advice():
    a = day_with([(540, 1020, True, False)])
    check("e. 9-5 on a Monday: 'You work 9-5 today: the bot trades alone; check at lunch 12:30.'", a["text"] == "You work 9-5 today: the bot trades alone; check at lunch 12:30.", a["text"])
    check("e. ... 390 minutes of the 02:00-15:30 window at work, check at 12:30, warn", a["overlap_mins"] == 390 and a["check_at"] == "12:30" and a["tone"] == "warn", a)
    check("e. ... the 10:45 plan is read at lunch, the 16:05 summary after work", any("10:45 midday plan: read it at lunch 12:30" in n and "16:05 day summary: read it after work (5 pm)" in n for n in a["notes"]), a["notes"])
    b = day_with([(540, 1020, True, False), (735, 765, False, True)])
    check("e. a lunch break in the calendar (12:15) is the check time", b["check_at"] == "12:15" and "on your break 12:15" in b["text"], b["text"])
    c = day_with([])
    check("e. no work: free for the whole session", c["text"].startswith("No work today: you are free for the whole session") and c["check_at"] == "10:45", c)
    d = day_with([(1020, 1380, True, False)])
    check("e. an evening shift 5-11 pm is after the session", d["overlap_mins"] == 0 and "after the session" in d["text"] and "5-11 pm" in d["text"], d["text"])
    e = day_with([(420, 780, True, False)])
    check("e. a 7-1 shift: check 'on a break' 10:30 am, free from 1 pm with 2 h 30 min of entries left",
          "check on a break 10:30 am" in e["text"] and any("free from 1 pm: 2 h 30 min of the entry window left" in n for n in e["notes"]), (e["text"], e["notes"]))
    f = day_with([(540, 1020, True, False)], day="2026-11-21")
    check("e. Saturday: the bot does not trade, the shift is still said", f["closed"] and f["text"] == "Weekend: the bot does not trade. You work 9-5.", f["text"])
    g = day_with([(540, 1020, True, False)], day="2026-11-26", mkt={"closed": True, "early": None, "news": []})
    check("e. Thanksgiving (pythia closed): market closed", g["closed"] and g["text"].startswith("Market closed today"), g["text"])
    h = day_with([(540, 1020, True, False)], day="2026-11-27", mkt={"closed": False, "early": "13:15", "news": []})
    check("e. early close 13:15: the entry window ends 12:45 and the note says so", h["entry_window"] == ["02:00", "12:45"] and any("Early close 13:15 ET" in n for n in h["notes"]), h)
    i = day_with([(540, 1020, True, False)], mkt={"closed": False, "early": None, "news": [{"time": "08:30", "title": "CPI", "impact": "high"}, {"time": "14:00", "title": "FOMC decision", "impact": "high"}]})
    check("e. news: CPI 08:30 before the shift is listed, FOMC 14:00 lands during the shift", any(n == "CPI 08:30 ET." for n in i["notes"]) and any(n.startswith("FOMC decision 14:00 ET lands during your shift") for n in i["notes"]), i["notes"])
    j = day_with([(540, 1020, True, False)], live=True)
    check("e. a funded / live account on the board: the presence note (the bot never arms live)", any("live account needs you present" in n for n in j["notes"]), j["notes"])
    k = day_with([(1320, 1440, True, False)], day="2026-11-18")
    check("e. a 10 pm shift starting late: after the session", "after the session" in k["text"], k["text"])
    m = day_with([(0, 360, True, False), (540, 1020, True, False)], day="2026-11-19")
    check("e. the end of a night shift (12-6 am) + a day shift: both said, the 01:45 plan read at lunch", "12-6 am" in m["text"] and any("01:45 morning plan" in n for n in m["notes"]), (m["text"], m["notes"]))
    check("e. time words: 9-5, 7 am-3:30 pm, 5-11 pm, 10 pm-6 am, noon, midnight", [CS.span_words(540, 1020), CS.span_words(420, 930), CS.span_words(1020, 1380), CS.span_words(1320, 360 + 1440)]
          == ["9-5", "7-3:30", "5-11 pm", "10 pm-6 am"] and CS.say_time(720) == "noon" and CS.say_time(0) == "midnight" and CS.say_time(750) == "12:30",
          [CS.span_words(540, 1020), CS.span_words(420, 930), CS.span_words(1020, 1380), CS.span_words(1320, 1800)])
    fb = CS.free_blocks({"segs": [{"from": 540, "to": 1020, "busy": True}, {"from": 1080, "to": 1140, "busy": True}, {"from": 1150, "to": 1160, "busy": False}]})
    check("e. free blocks: 07:00-09:00, 17:00-18:00, 19:00-23:00 (a not-busy entry does not block)", [(b["start"], b["end"]) for b in fb] == [("07:00", "09:00"), ("17:00", "18:00"), ("19:00", "23:00")], fb)
    out = CS.build(all_cals(), MON_0800, {}, pythia={"events": [{"date": "2026-11-18", "time": "14:00", "title": "Fed minutes", "impact": "med", "kind": "fomc"},
                                                                {"date": "2026-11-26", "closed": True, "kind": "holiday", "title": "Thanksgiving", "impact": "low"}]}, trade={"ok": False})
    mon = out["days"]["2026-11-16"]
    check("e. the real fixtures, Monday: Office 9-5 + When I Work 9-5 = 9-5, lunch break 12:15 from Outlook", mon["work"] == [{"start": "09:00", "end": "17:00", "mins": 480}]
          and mon["check_at"] == "12:15", mon)
    check("e. ... Wednesday's Fed minutes during the shifts is a note", any(n.startswith("Fed minutes 14:00 ET lands during your shift") for n in out["days"]["2026-11-18"]["notes"]), out["days"]["2026-11-18"]["notes"])
    check("e. ... Thanksgiving is closed", out["days"]["2026-11-26"]["closed"])
    check("e. 22 days in the file (7 back, today, 14 ahead)", len(out["days"]) == 22 and min(out["days"]) == "2026-11-09" and max(out["days"]) == "2026-11-30")


# ------------------------------------------------------------------------------------------------ f. hours worked vs $ made trading
def test_week():
    office = [all_cals()[2]]
    trade = {"ok": True, "cash_week": 0.0, "eval_week": 240.0, "cash_per_month": None, "plan_per_month": 1290.0}
    out = CS.build(office, MON_0800, {"wage": {"hourly": 20}}, pythia=None, trade=trade)
    w = out["week"]
    check("f. 40 h this week from the Office calendar, $800 at $20 an hour", w["work_hours"] == 40 and w["pay_week"] == 800, w)
    check("f. the line: hours, pay, trading cash, eval P&L is not cash, the paycheck a month and the plan cover",
          w["line"] == "This week: 40 h at work, about $800 pay. Trading: $0 cash this week, eval P&L +$240 (not cash until a payout). To quit: the paycheck is about $3,467 a month; no trading cash rate yet (the plan estimate $1,290 a month would cover 37%).",
          w["line"])
    out2 = CS.build(office, MON_0800, {"wage": {"hourly": 20}}, trade={**trade, "cash_per_month": 520.0}, checks=[("2026-10-30", 1500.0), ("2026-11-13", 1500.0)])
    w2 = out2["week"]
    check("f. paychecks from the money import beat the typed wage (2 x $1,500 two weeks apart -> $750 a week, $3,250 a month), trading covers 16%",
          w2["pay"]["src"] == "import" and w2["pay"]["week_usd"] == 750 and w2["pay"]["month_usd"] == 3250 and w2["covers_pct"] == 16, w2)
    out3 = CS.build(office, MON_0800, {}, trade=trade)
    check("f. no pay known: it says how to add it", out3["week"]["pay"]["src"] is None and "--wage" in out3["week"]["pay"]["text"], out3["week"]["pay"])
    tmp = tempfile.mkdtemp()
    try:
        led = os.path.join(tmp, "ledger.json")
        json.dump({"entries": [{"kind": "income", "amount": 1400, "date": "2026-11-06", "acct": "general", "note": "Paycheck ACME"},
                               {"kind": "income", "amount": 999, "date": "2026-11-06", "note": "sold a bike"},
                               {"kind": "payout_in", "amount": 2000, "date": "2026-11-06", "note": "MFFU payout"}]}, open(led, "w"))
        inb = os.path.join(tmp, "money.jsonl")
        open(inb, "w").write(json.dumps({"type": "paycheck", "usd": 1400, "date": "2026-11-13"}) + "\nnot json\n" + json.dumps({"type": "expense", "usd": 50}) + "\n")
        pc = CS.paychecks(led, inb)
        check("f. paychecks: a Ledger income tagged paycheck + a money-inbox paycheck; a bike sale, a payout and junk are not pay", pc == [("2026-11-06", 1400.0), ("2026-11-13", 1400.0)], pc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tr = CS.trading_of(MON_0800, sb={"totals": {"week": {"net": 12.5}, "month": {"net": -80}}, "run_rate": {"cash_per_month": None, "plan": {"per_month": 1290}},
                                     "_accounts": {"lit": {"has": True, "paper": False, "week": 300}, "blitz": {"has": True, "paper": True, "week": 999}}})
    check("f. trading_of: cash from the scoreboard, eval P&L of the real accounts only (BLITZ paper left out)", tr["cash_week"] == 12.5 and tr["eval_week"] == 300 and tr["plan_per_month"] == 1290, tr)
    real = CS.trading_of(MON_0800, site_dir=os.path.join(ROOT, "tests", "fixtures", "argus"))
    check("f. trading_of on the repo's real scoreboard code never raises", isinstance(real, dict) and "ok" in real, real)


# ------------------------------------------------------------------------------------------------ g. sync, settings and privacy
class Net:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, headers, timeout):
        self.calls.append({"url": url, "headers": dict(headers)})
        r = self.routes.get(url)
        if r is None:
            raise OSError("no route")
        if isinstance(r, Exception):
            raise r
        return r


def test_sync():
    tmp = tempfile.mkdtemp()
    try:
        home = os.path.join(tmp, "olympus")
        out = os.path.join(tmp, "day")
        cfgp = os.path.join(home, "calendars.json")
        check("g. webcal:// -> https://", CS.normalize_url(SECRET_URLS["icloud"]).startswith("https://p52-caldav.icloud.com/"))
        check("g. refused: http://, a password in the address, spaces, javascript:, empty", all(CS.normalize_url(u) is None for u in
              ["http://calendar.google.com/x.ics", "https://user:pw@example.com/x.ics", "https://a b.com/x", "javascript:alert(1)", "", None]))
        cfg = CS.load_config(cfgp)
        for k, u in SECRET_URLS.items():
            cfg, _ = CS.add_calendar(cfg, u, k.title(), True if k == "outlook" else None)
        for u in SHIFT_URLS[:2]:
            cfg, _ = CS.add_calendar(cfg, u)
        cfg["wage"] = {"hourly": 18.5}
        CS.save_config(cfg, cfgp)
        names = [c["name"] for c in CS.load_config(cfgp)["calendars"]]
        check("g. calendars saved outside the repo; a shift app's address is named Work and marked work", names == ["Google", "Icloud", "Outlook", "Work", "Work 5"]
              and CS.load_config(cfgp)["calendars"][3]["work"] is True, names)
        if os.name == "posix":
            check("g. calendars.json is readable by you only (0600)", stat.S_IMODE(os.stat(cfgp).st_mode) == 0o600, oct(os.stat(cfgp).st_mode))
        try:
            CS.add_calendar(cfg, "http://evil.example/x.ics")
            check("g. a bad address raises a plain error", False)
        except ValueError as e:
            check("g. a bad address raises a plain error", "https://" in str(e))
        routes = {CS.normalize_url(SECRET_URLS["google"]): (200, rd("google.ics").encode()), CS.normalize_url(SECRET_URLS["icloud"]): (200, rd("icloud.ics").encode()),
                  CS.normalize_url(SECRET_URLS["outlook"]): (200, rd("outlook.ics").encode()), SHIFT_URLS[0]: (200, SHIFT_PARTS[0].encode()),
                  SHIFT_URLS[1]: (200, b"<html><body>Please sign in</body></html>")}
        net = Net(routes)
        d = CS.sync(MON_0800, cfg_path=cfgp, work_dir=out, opener=net, site_dir=tmp, trade={"ok": False}, feeds=False, say=lambda *_: None)
        check("g. one sync: 5 GETs, a generic User-Agent (no name, no e-mail), no cookie / auth header", len(net.calls) == 5
              and all(set(c["headers"]) == {"User-Agent", "Accept"} and "@" not in c["headers"]["User-Agent"] for c in net.calls), net.calls[:1])
        rows = {c["name"]: c for c in d["calendars"]}
        check("g. the sign-in page is refused with a plain reason, the others are OK", rows["Work 5"]["ok"] is False and "did not return a calendar" in (rows["Work 5"]["error"] or "")
              and all(rows[n]["ok"] for n in ("Google", "Icloud", "Outlook", "Work")), rows)
        p = os.path.join(out, "day.json")
        text = open(p, encoding="utf-8").read()
        leaks = [s for s in ["private-0123456789abcdef", "bbbbsecret", "MTIzNDU2Nzg5MDEyMzQ1Ng", "/ical/abc", "demo.owner", "gmail.com", "friend.person", "Secret Street",
                             "meet.example.com", "555-0100", "dr.smile", "contoso", "Main Street Store\",\"location", "LOCATION", "DESCRIPTION", "ATTENDEE", "mailto", "https://"] if s in text]
        check("g. day.json carries no address, no e-mail, no location / description / attendee, no link", not leaks, leaks)
        check("g. day.json: private, today's sentence, the calendars by host only", d["private"] is True and d["today"] == "2026-11-16" and d["days"]["2026-11-16"]["text"].startswith("You work 9-5 today")
              and rows["Google"]["host"] == "calendar.google.com", (d["today"], d["days"]["2026-11-16"]["text"]))
        check("g. the dentist's e-mail in a title is scrubbed", any(e["title"] == "Dentist, check-up with (email)" for e in d["events"]), [e["title"] for e in d["events"] if "Dentist" in e["title"]])
        if os.name == "posix":
            check("g. day.json is 0600 and the cached copies too", stat.S_IMODE(os.stat(p).st_mode) == 0o600 and all(stat.S_IMODE(os.stat(os.path.join(out, "cache", f)).st_mode) == 0o600 for f in os.listdir(os.path.join(out, "cache"))))
        caches = os.listdir(os.path.join(out, "cache"))
        check("g. cache files are named by a hash, never by the address", len(caches) == 4 and all(len(f) == 16 and f.endswith(".ics") for f in caches), caches)
        net2 = Net({})                                    # the network is down: the last good copies
        d2 = CS.sync(MON_0800 + 3600, cfg_path=cfgp, work_dir=out, opener=net2, site_dir=tmp, trade={"ok": False}, feeds=False, say=lambda *_: None)
        rows2 = {c["name"]: c for c in d2["calendars"]}
        check("g. network down: each calendar uses its last good copy (marked), the shifts are still there", rows2["Google"]["cached"] and not rows2["Google"]["ok"]
              and d2["days"]["2026-11-16"]["work"] == d["days"]["2026-11-16"]["work"], rows2["Google"])
        big = Net({**routes, CS.normalize_url(SECRET_URLS["google"]): (200, b"BEGIN:VCALENDAR\n" + b"X" * (CS.MAX_ICS_BYTES + 10))})
        d3 = CS.sync(MON_0800 + 7200, cfg_path=cfgp, work_dir=out, opener=big, site_dir=tmp, trade={"ok": False}, feeds=False, say=lambda *_: None)
        check("g. a calendar over 5 MB is refused", "larger than 5 MB" in ({c["name"]: c for c in d3["calendars"]}["Google"]["error"] or ""))
        # maybe_run: the 15-minute hook
        env = {"OLYMPUS_HOME": os.path.join(tmp, "nobody")}
        check("g. maybe_run with no calendars.json: does nothing, says nothing", CS.maybe_run(MON_0800, work_dir=os.path.join(tmp, "x"), env=env, say=lambda *_: (_ for _ in ()).throw(AssertionError("spoke"))) is None)
        said = []
        r1 = CS.maybe_run(MON_0800 + 5 * 3600, work_dir=out, cfg_path=cfgp, opener=Net(routes), say=said.append, env={})
        r2 = CS.maybe_run(MON_0800 + 5 * 3600 + 600, work_dir=out, cfg_path=cfgp, opener=Net(routes), say=said.append, env={})
        check("g. maybe_run syncs, then waits 14 minutes", r1 is not None and r2 is None and any("your day:" in s for s in said), said)
        check("g. LE_CALENDAR=0 turns it off", CS.maybe_run(MON_0800 + 9 * 3600, work_dir=out, cfg_path=cfgp, opener=Net(routes), env={"LE_CALENDAR": "0"}) is None)
        boom = CS.maybe_run(MON_0800 + 10 * 3600, work_dir=out, cfg_path=cfgp, opener=lambda *a: (_ for _ in ()).throw(RuntimeError("x")), say=said.append, env={})
        check("g. a failing network never raises out of maybe_run", boom is not None)
        # --list masks the addresses; --setup asks plain questions
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            CS.main(["--config", cfgp, "--out", out, "--list"])
        lst = buf.getvalue()
        check("g. --list shows the host only, never the secret part", "calendar.google.com" in lst and "private-0123" not in lst and "bbbbsecret" not in lst and "abc" not in lst.replace("abc", "", 0) or "/ical/abc" not in lst, lst)
        answers = iter(["webcal://p52-caldav.icloud.com/published/2/NEWSECRET", "n", "", "http://bad", SHIFT_URLS[2], "", "", "", "", "19.75"])
        said = []
        cfg2p = os.path.join(tmp, "o2", "calendars.json")
        c2 = CS.setup(ask=lambda q: next(answers), say=said.append, cfg_path=cfg2p)
        check("g. setup: paste, work or not, name, a bad address asked again, a shift app defaults to work, pay saved",
              [(c["name"], c["work"]) for c in c2["calendars"]] == [("Personal", False), ("Work", True)] and c2["wage"] == {"hourly": 19.75}
              and any("[FIX] that is not a calendar address" in s for s in said) and not any("NEWSECRET" in s for s in said), (c2, said))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # nothing private in the repo or the public site
    hits = []
    for base in (os.path.join(ROOT, "tools", "web_public"),):
        for dp, _dn, fn in os.walk(base):
            for f in fn:
                if f in ("calendars.json", "day.json"):
                    hits.append(os.path.join(dp, f))
    check("g. no calendars.json / day.json anywhere in the public site folder", not hits, hits)
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("g. data/day/ and data/inbox/ are gitignored", "\ndata/day/\n" in gi and "\ndata/inbox/\n" in gi)
    src = open(os.path.join(ROOT, "tools", "calendar_sync.py"), encoding="utf-8").read()
    check("g. calendar_sync never writes into a site folder (no web_public / pc_publish / live_site write path)", "write_json(os.path.join(work_dir" in src
          and "web_public\", \"day" not in src and "site_dir, \"day" not in src)
    pcr = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    check("g. the PC report's 15-minute task calls calendar_sync.maybe_run (softly)", "_cal.maybe_run(" in pcr)


# ------------------------------------------------------------------------------------------------ h. the PC's private route
def test_route():
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception as e:  # noqa: BLE001
        check("h. fastapi test client available", False, e)
        return
    from engine import live_site as LS
    tmp = tempfile.mkdtemp()
    old = {k: os.environ.get(k) for k in ("LE_DAY_DIR", "LE_SITE_DIR")}
    try:
        os.environ["LE_DAY_DIR"] = os.path.join(tmp, "day")
        site = os.path.join(tmp, "site")
        os.makedirs(os.path.join(site, "day"))
        open(os.path.join(site, "index.html"), "w").write("<!doctype html>")
        json.dump({"leak": True}, open(os.path.join(site, "day", "day.json"), "w"))
        os.environ["LE_SITE_DIR"] = site
        app = FastAPI()
        LS.install(app)
        cl = TestClient(app, client=("127.0.0.1", 50000), base_url="http://localhost")   # the PC itself / tailscale serve (loopback)
        r = cl.get("/site/day/day.json")
        check("h. before a sync: 404 with a plain reason, and a day.json in a site folder is NEVER served", r.status_code == 404 and "no calendar connected" in r.json()["error"], (r.status_code, r.text))
        os.makedirs(os.environ["LE_DAY_DIR"])
        json.dump({"kind": "olympus-day", "today": "2026-11-16"}, open(os.path.join(os.environ["LE_DAY_DIR"], "day.json"), "w"))
        r = cl.get("/site/day/day.json", headers={"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "me@example.com"})
        check("h. after a sync: served from data/day/ over the phone link, no-store", r.status_code == 200 and r.json()["kind"] == "olympus-day"
              and r.headers.get("cache-control") == "no-store" and r.headers.get("x-olympus-source") == "calendar_sync", (r.status_code, r.headers))
        r = cl.get("/site/day/calendars.json")
        r2 = cl.get("/site/day/cache/x.ics")
        check("h. only the known file names: calendars.json / anything else under day/ is 404", r.status_code == 404 and r2.status_code == 404, (r.status_code, r2.status_code))
        r = cl.get("/site/day/day.json", headers={"Tailscale-Funnel-Request": "1", "X-Forwarded-For": "1.2.3.4"})
        check("h. a Funnel (internet) request is refused", r.status_code == 403)
        r = cl.post("/site/day/day.json", headers={"X-Forwarded-For": "100.64.0.2"})
        check("h. a POST over the link is refused (read only)", r.status_code == 403)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ k. the phone side in node: olympus/day.js, the copilot's Work line, the briefing
def fixture_day(now_s, extras=None):
    return CS.build(all_cals(), now_s, {"wage": {"hourly": 18.5}}, pythia={"events": [{"date": "2026-11-18", "time": "14:00", "title": "Fed minutes", "impact": "med", "kind": "fomc"}]},
                    trade={"ok": True, "cash_week": 0.0, "eval_week": 120.0, "cash_per_month": None, "plan_per_month": 1290.0}, extras=extras)


WEATHER = {"weather": {"src": "api.weather.gov", "place": "Columbus, OH", "t": int(MON_0800) - 1800, "periods": [{"name": "Today", "temp": 51, "unit": "F", "short": "Chance Rain Showers", "rain": 40}],
                       "alerts": [{"event": "Wind Advisory", "headline": "Wind Advisory until 6 PM"}]},
           "headlines": {"t": int(MON_0800) - 1800, "items": [{"title": "Federal Reserve issues FOMC statement", "source": "federalreserve.gov", "t": int(MON_0800) - 7200, "tags": ["fed"]},
                                                              {"title": "Consumer Price Index news release", "source": "bls.gov", "t": int(MON_0800) - 3600, "tags": ["cpi"]}]}}


def test_node():
    import subprocess
    tmp = tempfile.mkdtemp()
    try:
        now_ms = int((MON_0800 - 6 * 3600 + 600) * 1000)            # Monday 02:10 ET
        dp, ip = os.path.join(tmp, "day.json"), os.path.join(tmp, "inbox.json")
        json.dump(fixture_day(now_ms / 1000, WEATHER), open(dp, "w"))
        json.dump({"kind": "olympus-inbox", "items": [{"id": "i1", "type": "task", "text": "Call the bank", "t": 1}, {"id": "i2", "type": "note", "text": "Idea: size down on CPI days", "due": "2026-11-17", "t": 2}]}, open(ip, "w"))
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "connect_day_harness.mjs"), dp, ip, str(now_ms)], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            check("k. node harness runs", False, r.stderr[-1500:])
            return
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("k. norm: the file is read, junk files are refused", o["norm"] == 22 and o["normBad"], o["norm"])
    t = o["today"]
    check("k. today(): ok, the day's sentence, the shift, the lunch break check", t["state"] == "ok" and t["text"] == "You work 9-5 today: the bot trades alone; check on your break 12:15."
          and t["work"] == [{"start": "09:00", "end": "17:00", "mins": 480}] and t["checkAt"] == "12:15", t)
    check("k. no file (the public site): 'missing' and how to connect, nothing invented", o["missing"]["state"] == "missing" and "tools/bat/CONNECT_DAY.bat" in o["missing"]["text"] and not o["missing"]["work"])
    check("k. a file 40 h old is 'old' (the PC may be off); 2 h old says its age", o["old"] == "old" and o["late"]["state"] == "late" and "2 h ago" in o["late"]["note"], (o["old"], o["late"].get("note")))
    rw = o["rows"]
    check("k. copilot rows: 01:45 the sentence, 10:45 'at work until 5 pm; check at 12:15', 16:05 hours today + the week line, none without a file",
          rw["a"]["text"].startswith("Work: You work 9-5 today") and rw["b"]["text"].startswith("Work: at work until 5 pm; check at 12:15") and rw["c"]["text"].startswith("Work: 8 h at work today. This week: ")
          and rw["none"] is None and rw["a"]["say"] == "What's my day?", rw)
    check("k. time words: 5 pm, 12:30, noon, 9:30 am, midnight, midnight, ''", o["said"] == ["5 pm", "12:30", "noon", "9:30 am", "midnight", "midnight", ""], o["said"])
    br = o["brief"]
    check("k. the briefing lines: Work, Weather (Columbus 51°F, rain 40%, the wind advisory), Headlines (Fed, CPI)", [x["k"] for x in br] == ["work", "weather", "news"]
          and o["weather"] == "Columbus, OH: Today 51°F, chance rain showers, 40% rain. Alert: Wind Advisory." and "Federal Reserve issues FOMC statement (federalreserve.gov)" in br[2]["text"], br)
    check("k. the inbox: a task and a note with its day; junk dropped, markup stripped", [(x["id"], x["kind"], x["due"]) for x in o["inbox"]] == [("i1", "task", ""), ("i2", "note", "2026-11-17")]
          and o["inboxBad"][0] == 0 and [x["text"] for x in o["inboxBad"][1]] == ["b hi /b"], o["inboxBad"])
    ev = o["evil"]
    check("k. hostile day text: no markup survives, a bad shift time is dropped, an unknown tone becomes info", "<" not in ev["text"] and "<" not in "".join(ev["notes"]) and ev["work"] == [] and ev["tone"] == "info", ev)
    check("k. a two-day all-day entry shows on its second day too (the weekend trip on Saturday)", "Weekend trip" in o["eventsAllDay"], o["eventsAllDay"])
    m = [x["text"] for x in o["morning"]["rows"]]
    check("k. Jarvis 01:45 Morning plan: the Work line is the second line, the foot names day/day.json", len(m) >= 3 and m[1].startswith("Work: You work 9-5 today")
          and "day/day.json (your calendars)" in o["morning"]["foot"], (m, o["morning"]["foot"]))
    check("k. 10:45 Midday plan: 'at work until 5 pm; check at 12:15'", any(x["text"].startswith("Work: at work until 5 pm") for x in o["midday"]["rows"]), [x["text"] for x in o["midday"]["rows"]])
    sm = [x["text"] for x in o["summary"]["rows"]]
    check("k. 16:05 Day summary: the last line is hours worked + the week line (hours vs $ trading)", sm and sm[-1].startswith("Work: 8 h at work today. This week: ") and "To quit" in sm[-1], sm)
    check("k. without a day file the cards are exactly as before (no Work line)", not any(x["text"].startswith("Work:") for x in o["noDay"]["rows"]) and len(o["noDay"]["rows"]) <= 6)
    check("k. 'what's my day', 'what is my schedule today', 'do i work today', 'hours worked vs trading', 'when do i work' -> my_day; 'should i trade today' stays trade_today",
          o["match"] == ["my_day"] * 5 + ["trade_today"], o["match"])
    a = o["answer"]
    check("k. the answer: the sentence, the notes, free time, the week line, read only, opens nothing by itself", a and a["intent"] == "copilot_my_day" and a["text"].startswith("You work 9-5 today")
          and "Free: 7 am-9 am" in a["text"] and "This week:" in a["text"] and "Read only" in a["text"] and a.get("app") == "planner", a)
    check("k. no day file: my_day hands over to the older skills (null), never a made-up day", o["answerMissing"] is None, o["answerMissing"])
    bl = [x["k"] for x in o["brf"]["lines"]]
    check("k. the morning briefing carries Work, Weather and Headlines after Today's plan; without them it is unchanged",
          bl[:6] == ["bots", "drawdown", "today", "work", "weather", "news"] and [x["k"] for x in o["brfNone"]["lines"]] == ["bots", "drawdown", "today", "kalshi", "todos"], bl)


# ------------------------------------------------------------------------------------------------ l. Chromium: the Planner's work card + inbox, Jarvis's card (under flock /tmp/olympus_browser.lock)
PLAN = json.dumps({"v": 2, "events": [], "tasks": [], "projects": [], "goals": [], "notes": [], "habits": [], "habitLog": {}, "checklist": [], "checks": {}, "postlist": [], "postChecks": {}, "post": {}, "focus": {}, "prefs": {}})
INBOX = {"kind": "olympus-inbox", "items": [{"id": "i1", "type": "task", "text": "Call the bank about the card", "t": 1}, {"id": "i2", "type": "note", "text": "Idea from the iPhone", "t": 2}]}


def test_planner_browser():
    from tests import agora_kit as AK
    day = fixture_day(MON_0800 + 2 * 3600, WEATHER)
    srv, origin = AK.serve({"/day/day.json": json.dumps(day), "/day/inbox.json": json.dumps(INBOX)})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"planner.agora.v2": PLAN})
            AK.open_app(p, origin, "planner", "?at=2026-11-16T15:00:00Z")
            p.wait_for_selector("#workCard", timeout=30000)
            w = p.evaluate("(() => { const c = document.getElementById('workCard'); return { h: c.querySelector('h2').innerText, lead: c.querySelector('#workLead').innerText,"
                           " rows: [...c.querySelectorAll('.mrow')].map((r) => r.innerText.replace(/\\s+/g, ' ')), week: (c.querySelector('#workWeek') || {}).innerText || '',"
                           " order: [...document.getElementById('v-today').children].map((s) => s.id || s.className).slice(0, 3) }; })()")
            check("l. Planner Today: 'Your work day' after the trading day, the sentence, the shifts from the calendars, the week line",
                  w["h"] == "Your work day" and w["lead"] == "You work 9-5 today: the bot trades alone; check on your break 12:15."
                  and any("Cashier at Main Street Store" in r and "work" in r for r in w["rows"]) and w["week"].startswith("This week: ") and w["order"][1] == "workCard", w)
            st = p.evaluate("JSON.parse(localStorage.getItem('planner.agora.v2'))")
            ids = p.evaluate("JSON.parse(localStorage.getItem('planner.inbox.v1'))")
            check("l. the iPhone inbox: the task is in today's tasks, the note in the notes (tag inbox), each remembered once",
                  any(t["text"] == "Call the bank about the card" and t["day"] == "2026-11-16" for t in st["tasks"])
                  and any(n["text"] == "Idea from the iPhone" and "inbox" in n["tags"] for n in st["notes"]) and ids["ids"] == ["i1", "i2"], (st["tasks"], st["notes"], ids))
            p.reload()
            p.wait_for_selector("#workCard", timeout=30000)
            st2 = p.evaluate("JSON.parse(localStorage.getItem('planner.agora.v2'))")
            check("l. reload (the test resets the plan on every load): the inbox items are remembered, so they are not added again",
                  not [t for t in st2["tasks"] if t["text"] == "Call the bank about the card"] and not st2["notes"], st2["tasks"])
            check("l. 390 px: no sideways scroll, no console error, nothing off the page's origin", AK.no_sideways(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "planner", "?demo=1&at=2026-11-16T15:00:00Z")
            p.wait_for_selector("#workCard", timeout=30000)
            check("l. ?demo=1: the work card is the labelled example, nothing from the inbox is added",
                  "(example)" in p.inner_text("#workCard h2") and p.evaluate("localStorage.getItem('planner.inbox.v1')") is None)
            ctx.close()
    finally:
        srv.shutdown()
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"planner.agora.v2": PLAN})
            AK.open_app(p, origin, "planner", "?at=2026-11-16T15:00:00Z")
            p.wait_for_function("window.PLANNER && window.PLANNER.ready()", timeout=30000)
            check("l. the public site (no day file): no work card, the Planner as before, no error", p.evaluate("!document.getElementById('workCard')") and not errs, errs[:3])
            ctx.close()
    finally:
        srv.shutdown()


def test_jarvis_browser():
    import functools
    import http.server
    import re as _re
    import threading
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    from tests import test_jarvis_copilot as TJ
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(TJ.Quiet, directory=TJ.WP))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    at = dt.datetime(2026, 11, 16, 2, 10, tzinfo=NY)
    day = json.dumps(fixture_day(at.timestamp(), WEATHER))
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="block")
            ctx.route(_re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())
            ctx.route(_re.compile(r"/home\.json(\?.*)?$"), lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(TJ.fixture_home(at.timestamp()))))
            ctx.route(_re.compile(r"/day/day\.json(\?.*)?$"), lambda r: r.fulfill(status=200, content_type="application/json", body=day))
            ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.speak', 'off'); } catch (e) {}")
            ctx.clock.set_fixed_time(at)
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "jarvis/")
            p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000, polling=200)
            p.wait_for_function("(() => { const c = document.getElementById('hcCopilot'); return c && [...c.querySelectorAll('.hc-row')].some((b) => b.innerText.startsWith('Work:')); })()", timeout=60000, polling=250)
            rows = p.evaluate("[...document.querySelectorAll('#hcCopilot .hc-row')].map((b) => [b.innerText, b.dataset.say])")
            check("l. Jarvis 02:10 ET: the Morning plan card has 'Work: You work 9-5 today: the bot trades alone; check on your break 12:15.', a tap asks \"What's my day?\"",
                  any(r[0].startswith("Work: You work 9-5 today: the bot trades alone; check on your break 12:15.") and r[1] == "What's my day?" for r in rows), rows)
            p.evaluate("document.getElementById('talk').innerHTML = ''")
            p.fill("#q", "what's my day")
            p.press("#q", "Enter")
            p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=20000)
            ans = p.locator(".msg.j").first.inner_text()
            check("l. Jarvis: \"what's my day\" answers with the shift, the free time and the week line", "You work 9-5 today" in ans and "This week:" in ans, ans[:400])
            check("l. Jarvis: no page error", not errs, errs[:3])
            ctx.close()
    finally:
        srv.shutdown()


def test_browser():
    try:
        test_planner_browser()
    except Exception as e:  # noqa: BLE001
        check("l. Planner in Chromium ran", False, f"{e.__class__.__name__}: {e}")
    try:
        test_jarvis_browser()
    except Exception as e:  # noqa: BLE001
        check("l. Jarvis in Chromium ran", False, f"{e.__class__.__name__}: {e}")


# ------------------------------------------------------------------------------------------------ i. the internet feeds (weather.gov, the official RSS)
POINTS = {"properties": {"forecast": "https://api.weather.gov/gridpoints/ILN/85,82/forecast", "relativeLocation": {"properties": {"city": "Columbus", "state": "OH"}}}}
FORECAST = {"properties": {"periods": [{"name": "Today", "temperature": 51, "temperatureUnit": "F", "shortForecast": "Chance Rain Showers", "probabilityOfPrecipitation": {"value": 40},
                                        "windSpeed": "10 to 15 mph", "isDaytime": True},
                                       {"name": "Tonight", "temperature": 38, "temperatureUnit": "F", "shortForecast": "Mostly Cloudy", "probabilityOfPrecipitation": {"value": None}, "isDaytime": False}]}}
ALERTS = {"features": [{"properties": {"event": "Wind Advisory", "headline": "Wind Advisory issued November 16 until 6 PM", "severity": "Moderate"}}]}
FED_RSS = """<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>FRB: Press Releases</title>
<item><title>Federal Reserve issues FOMC statement</title><link>https://www.federalreserve.gov/x.htm</link><pubDate>Mon, 16 Nov 2026 12:00:00 GMT</pubDate></item>
<item><title>Agencies announce dollar thresholds for smaller loan exemption</title><pubDate>Mon, 16 Nov 2026 11:00:00 GMT</pubDate></item>
<item><title>Minutes of the Federal Open Market Committee, October 2025</title><pubDate>Wed, 08 Oct 2025 18:00:00 GMT</pubDate></item>
</channel></rss>"""
BLS_ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>BLS</title>
<entry><title>Consumer Price Index news release</title><updated>2026-11-16T08:30:00-05:00</updated></entry>
<entry><title>County Employment and Wages</title><updated>2026-11-15T10:00:00-05:00</updated></entry>
</feed>"""
BOMB = """<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]><rss><channel><item><title>&lol2; cpi</title></item></channel></rss>"""


def feed_net(extra=None):
    r = {"https://api.weather.gov/points/39.9612,-82.9988": (200, json.dumps(POINTS).encode()), "https://api.weather.gov/gridpoints/ILN/85,82/forecast": (200, json.dumps(FORECAST).encode()),
         "https://api.weather.gov/alerts/active?point=39.9612,-82.9988": (200, json.dumps(ALERTS).encode()),
         "https://www.federalreserve.gov/feeds/press_all.xml": (200, FED_RSS.encode()), "https://www.bls.gov/feed/bls_latest.rss": (200, BLS_ATOM.encode())}
    r.update(extra or {})
    return Net(r)


def test_feeds():
    from tools import day_feeds as F
    cfg = {}
    geo = [{"name": "Columbus", "latitude": 32.46, "longitude": -84.98, "admin1": "Georgia"}, {"name": "Columbus", "latitude": 39.9612, "longitude": -82.9988, "admin1": "Ohio"}]
    place = F.set_city(cfg, "Columbus, OH", geocode=lambda c, s: geo)
    check("i. city by name: 'Columbus, OH' picks Ohio (not Georgia), saved as numbers", place == "Columbus, OH" and cfg["city"] == {"name": "Columbus, OH", "lat": 39.9612, "lon": -82.9988}, cfg)
    c2 = {}
    check("i. city by numbers, no lookup at all", F.set_city(c2, "39.9612, -82.9988") == "39.96,-83.00" and c2["city"]["lat"] == 39.9612)
    for bad in ("", "999,999"):
        try:
            F.set_city({}, bad, geocode=lambda c, s: [])
            check(f"i. a bad city '{bad}' raises a plain error", False)
        except ValueError:
            check(f"i. a bad city '{bad}' raises a plain error", True)
    net = feed_net()
    tmp = tempfile.mkdtemp()
    try:
        out = F.gather(cfg, MON_0800, tmp, opener=net, say=lambda *_: None)
        w = out["weather"]
        check("i. weather.gov: points -> forecast -> alerts; Columbus 51 F, 40% rain, the wind advisory", w and w["place"] == "Columbus, OH" and w["periods"][0]["temp"] == 51 and w["periods"][0]["rain"] == 40
              and w["alerts"][0]["event"] == "Wind Advisory" and w["src"] == "api.weather.gov", w)
        hd = [h["title"] for h in out["headlines"]["items"]]
        check("i. headlines: the FOMC statement (fed) and the CPI release (cpi) only; the loan notice, the county wages and the 2025 minutes are left out",
              hd == ["Consumer Price Index news release", "Federal Reserve issues FOMC statement"] or hd == ["Federal Reserve issues FOMC statement", "Consumer Price Index news release"], hd)
        check("i. headline tags and sources, no links kept", {h["source"] for h in out["headlines"]["items"]} == {"federalreserve.gov", "bls.gov"} and all(h["tags"] for h in out["headlines"]["items"])
              and "https://" not in json.dumps(out["headlines"]), out["headlines"])
        check("i. every request: https, a generic User-Agent, no cookie or key", all(c["url"].startswith("https://") and set(c["headers"]) == {"User-Agent", "Accept"} for c in net.calls), net.calls[:2])
        n1 = len(net.calls)
        F.gather(cfg, MON_0800 + 600, tmp, opener=net, say=lambda *_: None)
        check("i. asked at most once an hour (10 minutes later: no request)", len(net.calls) == n1, len(net.calls) - n1)
        F.gather(cfg, MON_0800 + 3600, tmp, opener=net, say=lambda *_: None)
        check("i. an hour later: the forecast again, the points lookup is remembered", sum(1 for c in net.calls[n1:] if "/points/" in c["url"]) == 0 and any("forecast" in c["url"] for c in net.calls[n1:]), [c["url"] for c in net.calls[n1:]])
        down = Net({})
        out3 = F.gather(cfg, MON_0800 + 2 * 3600, tmp, opener=down, say=lambda *_: None)
        check("i. the network is down: the last good weather and headlines stay", out3["weather"] and out3["weather"]["periods"][0]["temp"] == 51 and out3["headlines"]["items"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        F.parse_feed(BOMB.encode(), "x")
        check("i. a feed with entity declarations (an XML bomb) is refused", False)
    except ValueError:
        check("i. a feed with entity declarations (an XML bomb) is refused", True)
    try:
        F.get("http://www.bls.gov/feed/bls_latest.rss", opener=lambda *a: (200, b""))
        check("i. http:// is refused", False)
    except ValueError:
        check("i. http:// is refused", True)
    tmp = tempfile.mkdtemp()
    try:
        out = F.gather({"rss": []}, MON_0800, tmp, opener=Net({}), say=lambda *_: None)
        check("i. no city and rss: [] -> no weather, no headlines, nothing asked", out == {"weather": None, "headlines": None})
        # the whole sync: the feeds land in day.json and in the morning brief lines
        home = os.path.join(tmp, "o")
        cfgp = os.path.join(home, "calendars.json")
        c = CS.load_config(cfgp)
        c, _ = CS.add_calendar(c, SECRET_URLS["outlook"], "Office", True)
        c["city"] = cfg["city"]
        CS.save_config(c, cfgp)
        net = feed_net({CS.normalize_url(SECRET_URLS["outlook"]): (200, rd("outlook.ics").encode())})
        d = CS.sync(MON_0800, cfg_path=cfgp, work_dir=os.path.join(tmp, "day"), opener=net, site_dir=tmp, trade={"ok": False}, say=lambda *_: None)
        txt = json.dumps(d)
        check("i. sync: weather and headlines are in day.json, the weather.gov forecast address and the feed links are not", d["weather"]["periods"][0]["temp"] == 51 and d["headlines"]["items"]
              and "gridpoints" not in txt and "https://" not in txt, (d.get("weather"), "gridpoints" in txt))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ j. the phone inbox (POST /inbox/{kind}): appends a line, nothing else
def test_inbox():
    from engine import day_inbox as DI
    from engine import live_site as LS
    tmp = tempfile.mkdtemp()
    env = {"LE_INBOX_DIR": os.path.join(tmp, "inbox"), "LE_DAY_DIR": os.path.join(tmp, "day")}
    H = {"X-Olympus-Inbox": "1", "X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "me@example.com"}
    DI._HITS.clear()
    try:
        st, out = DI.accept("day", json.dumps({"text": "Call the bank <b>today</b>", "type": "task"}).encode(), "application/json", H, now_s=MON_0800, env=env)
        lines = open(os.path.join(env["LE_INBOX_DIR"], "day.jsonl"), encoding="utf-8").read().splitlines()
        rec = json.loads(lines[-1])
        check("j. a task: 200, one line appended (markup stripped, due today in New York), the reply in plain words", st == 200 and out["ok"] and out["said"] == "Added to your day: Call the bank b today /b"
              and rec["type"] == "task" and rec["due"] == "2026-11-16" and len(lines) == 1, (st, out, rec))
        st2, _ = DI.accept("day", b"Buy milk", "text/plain", H, now_s=MON_0800 + 1, env=env)
        st3, _ = DI.accept("day", json.dumps({"text": "Idea: size down on CPI", "type": "note", "due": "tomorrow"}).encode(), "application/json", H, now_s=MON_0800 + 2, env=env)
        snap = json.load(open(os.path.join(env["LE_DAY_DIR"], "inbox.json"), encoding="utf-8"))
        check("j. plain text = a task; a note for tomorrow; the Planner's snapshot day/inbox.json has all three", st2 == 200 and st3 == 200 and snap["kind"] == "olympus-inbox"
              and [(x["type"], x["due"]) for x in snap["items"]] == [("task", "2026-11-16"), ("task", "2026-11-16"), ("note", "2026-11-17")], snap)
        bad = [DI.accept("day", b'{"text":"x"}', "application/json", {"X-Forwarded-For": "1"}, now_s=MON_0800, env=env)[0],
               DI.accept("day", b'{"text":"x"}', "application/json", {**H, "Tailscale-Funnel-Request": "1"}, now_s=MON_0800, env=env)[0],
               DI.accept("day", b"x" * 3000, "text/plain", H, now_s=MON_0800, env=env)[0],
               DI.accept("day", b"{not json", "application/json", H, now_s=MON_0800, env=env)[0],
               DI.accept("day", b'{"text":"   "}', "application/json", H, now_s=MON_0800, env=env)[0],
               DI.accept("trading", b'{"text":"buy 10 NQ"}', "application/json", H, now_s=MON_0800, env=env)[0]]
        check("j. refused: no X-Olympus-Inbox header 403, Funnel 403, over 2 KB 413, bad JSON 400, empty 400, an unknown kind ('trading') 404", bad == [403, 403, 413, 400, 400, 404], bad)
        DI._HITS.clear()
        codes = [DI.accept("day", b"spam", "text/plain", H, now_s=MON_0800 + 100 + i, env=env)[0] for i in range(31)]
        check("j. 30 a 10 minutes, then 429", codes[:30] == [200] * 30 and codes[30] == 429, codes[-3:])
        DI._HITS.clear()
        old_max = DI.MAX_LINES
        DI.MAX_LINES = 5
        try:
            check("j. a full file (5,000 lines; 5 here) is refused with 507", DI.accept("day", b"one more", "text/plain", H, now_s=MON_0800 + 2000, env=env)[0] == 507)
        finally:
            DI.MAX_LINES = old_max
        files = sorted(os.path.relpath(os.path.join(dp, f), tmp) for dp, _dn, fn in os.walk(tmp) for f in fn)
        check("j. the only files it ever writes: inbox/day.jsonl and day/inbox.json", files == ["day/inbox.json", "inbox/day.jsonl"], files)
        DI.register("money", lambda body, now: ({"type": str(body.get("type") or ""), "usd": float(body.get("usd") or 0), "date": str(body.get("date") or "")}, "") if isinstance(body, dict) else (None, "json"))
        DI._HITS.clear()
        stm, _ = DI.accept("money", json.dumps({"type": "paycheck", "usd": 1400, "date": "2026-11-13"}).encode(), "application/json", H, now_s=MON_0800, env=env)
        check("j. the same shape for team X1's money inbox: POST /inbox/money -> inbox/money.jsonl, and calendar_sync reads its paychecks",
              stm == 200 and CS.paychecks(os.path.join(tmp, "nope.json"), os.path.join(env["LE_INBOX_DIR"], "money.jsonl")) == [("2026-11-13", 1400.0)])
        # the read-only guard: closed until install(), then ONLY POST /inbox/<kind>
        LS.POST_ALLOW.clear()
        DI._S["installed"] = False
        H = {k.lower(): v for k, v in H.items()}          # Starlette's headers are case-insensitive; the guard reads lower case
        before = LS.guard("POST", "/inbox/day", H)
        LS.allow_post(DI.allowed)
        DI._S["installed"] = True
        g = {p: (LS.guard(m, p, h) or (200, None))[0] for m, p, h in [("POST", "/inbox/day", H)]}
        rest = [LS.guard("POST", "/api/live/stop", H), LS.guard("POST", "/inbox/trading", H), LS.guard("PUT", "/inbox/day", H), LS.guard("DELETE", "/inbox/day", H),
                LS.guard("POST", "/inbox/day", {**H, "tailscale-funnel-request": "1"}), LS.guard("POST", "/inbox/day/../../api/live/arm", H), LS.guard("POST", "/site/day/day.json", H)]
        check("j. the guard: before install() a proxied POST /inbox/day is refused; after it, only POST /inbox/<kind> passes",
              before and before[0] == 403 and g["/inbox/day"] == 200 and all(r and r[0] == 403 for r in rest), (before, g, rest))
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            old = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                app = FastAPI()
                LS.install(app)

                @app.post("/api/live/stop")
                def _stop():
                    return {"stopped": True}
                DI.install(app)
                cl = TestClient(app, client=("127.0.0.1", 50000), base_url="http://localhost")   # tailscale serve proxies from loopback
                DI._HITS.clear()
                r = cl.post("/inbox/day", json={"text": "From the Shortcut", "type": "task"}, headers=H)
                r2 = cl.get("/site/day/inbox.json", headers=H)
                r3 = cl.post("/api/live/stop", headers=H)
                r4 = cl.options("/inbox/day", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-olympus-inbox"})
                r5 = cl.post("/inbox/day", content=b"no header", headers={"X-Forwarded-For": "100.64.0.2", "Content-Type": "text/plain"})
                check("j. the real routes: the Shortcut's POST 200, /site/day/inbox.json serves it, a stop over the link is still 403, a cross-site pre-flight gets no CORS allow, no header 403",
                      r.status_code == 200 and r.json()["said"] == "Added to your day: From the Shortcut" and r2.status_code == 200 and r2.json()["items"][-1]["text"] == "From the Shortcut"
                      and r3.status_code == 403 and "access-control-allow-origin" not in {k.lower() for k in r4.headers} and r5.status_code == 403,
                      (r.status_code, r.text[:200], r2.status_code, r3.status_code, dict(r4.headers), r5.status_code))
            finally:
                for k, v in old.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        except ImportError as e:
            check("j. fastapi test client available", False, e)
    finally:
        LS.POST_ALLOW.clear()
        DI._S["installed"] = False
        DI.KINDS.pop("money", None)
        DI._HITS.clear()
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(ROOT, "engine", "day_inbox.py"), encoding="utf-8").read()
    imports = sorted(set(re.findall(r"^\s*(?:from|import) ([\w.]+)", src, re.M)))
    check("j. day_inbox imports nothing of the bots (only the stdlib, fastapi, live_site and the stdlib-only fsutil.replace)", all(m in (".fsutil", "__future__", "datetime", "hashlib", "json", "os", "re", "threading", "time", "fastapi", "fastapi.responses", "zoneinfo", "engine") for m in imports)
          and "live_site" in src and not re.search(r"\b(ninjatrader|lit_live|live_model|arm|order)\w*\(", src), imports)
    srv = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    check("j. server.py installs day_inbox right after the live site, inside try/except (a failure only disables the inbox)",
          "_di.install(app)" in srv and srv.find("_ls.install(app") < srv.find("_di.install(app)") and "[day_inbox] disabled" in srv)


EXTRA = {"i": test_feeds, "j": test_inbox, "k": test_node}


def main():
    if part("a"):
        test_parser()
    if part("b"):
        test_recurring()
    if part("c"):
        test_zones()
    if part("d"):
        test_shift_apps()
    if part("e"):
        test_advice()
    if part("f"):
        test_week()
    if part("g"):
        test_sync()
    if part("h"):
        test_route()
    for k, fn in EXTRA.items():
        if part(k):
            fn()
    if ONLY is not None and "l" in ONLY:          # Chromium: only when asked, under flock -w 2400 /tmp/olympus_browser.lock
        test_browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} checks passed" + ("" if ok == n else f"  ({n - ok} FAILED)"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
