#!/usr/bin/env python3
"""PYTHIA dates: builds tools/web_public/pythia/events.json from RULES and from the repo's own saved calendar, and never invents a date. Stdlib only, offline (it reads local files, no fetch).

    python tools/money/pythia_dates.py                      # rewrite tools/web_public/pythia/events.json (range and asof from the file's own "generated" block)
    python tools/money/pythia_dates.py --from 2026-10-26 --to 2027-03-31 --asof 2026-11-10 --out events.json
    python tools/money/pythia_dates.py --check             # exit 1 when events.json is not exactly what this script would write (a test runs this)
    python tools/money/pythia_dates.py --selftest

Three kinds of date, kept apart in the file:
  1. RULE dates (verify false when the rule alone makes the date certain): jobless claims every Thursday (Wednesday when Thursday is a market holiday), the monthly options expiry (third Friday; Thursday when
     that Friday is Good Friday), quad witching and the quarterly NQ expiry (third Friday of Mar / Jun / Sep / Dec), and the roll (Thursday, 8 days before the expiry; docs/ROLL_DEC_2026.md and engine/roll_watch.py).
  2. RULE dates that agencies or exchanges can move (verify true): market holidays and early closes (US holiday rules; CME futures hours differ from stocks, so they say "check the CME calendar"), and the jobs report (NFP).
     NFP rule (BLS): the third Friday after the end of the week that contains the 12th of the data month. tests keep the rule honest against the 37 releases in data/build_news.py (read from the BLS archive):
     it matches all but a short, named list of exceptions (the 2025 shutdown and weeks next to a holiday), listed in NFP_EXCEPTIONS below.
  3. SAVED-CALENDAR dates (verify true): FOMC decisions, CPI, PPI and the other releases in data/news/events.csv, which tools/data/build_news.py built from federalreserve.gov and bls.gov (and the weekly news hub).
     Every one says where it came from. Anything the repo does not carry (retail sales, the CPI / PPI after the last saved one) stays in "undated" with the NAME of the official calendar to look it up
     (text only, nothing is fetched): federalreserve.gov FOMC calendars, bls.gov release calendar, census.gov economic indicators calendar.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "tools", "web_public", "pythia", "events.json")
CAL = os.path.join(ROOT, "data", "news", "events.csv")
D = dt.date
DEFAULT = {"from": "2026-10-26", "to": "2027-03-31", "asof": "2026-11-10"}
ABOUT = ("Built by tools/money/pythia_dates.py from rules and from the repo's saved calendar (data/news/events.csv). Never guessed: a date is here only when a rule or a saved official calendar gives it; "
         "verify: true means confirm it on the official page (agencies move releases and exchanges change holiday hours). A release whose date is not known is in 'undated' with the name of the official "
         "calendar to look it up (text only). All times are New York (ET) clock times.")
CONFIRM = {
    "cpi": "bls.gov, Release calendar, Consumer Price Index",
    "ppi": "bls.gov, Release calendar, Producer Price Index",
    "retail": "census.gov, Economic Indicators calendar, Advance Monthly Retail Sales",
    "fomc": "federalreserve.gov, Monetary Policy, FOMC calendars",
}
# the NFP rule vs the BLS archive in data/build_news.py: the releases the plain rule does NOT give (checked by tests/test_pythia_page.py)
NFP_EXCEPTIONS = {
    "2025-01-10": "New Year week: the rule gives Jan 3, BLS released on Jan 10",
    "2026-07-02": "July 4 fell on a Saturday (observed Friday Jul 3): BLS released on Thursday July 2",
    "2025-07-03": "July 4 fell on a Friday: BLS released on Thursday July 3",
    "2025-11-20": "2025 federal shutdown: delayed release", "2025-12-16": "2025 federal shutdown: delayed release",
    "2026-01-09": "after the shutdown the schedule was reset", "2026-02-11": "after the shutdown the schedule was reset",
}


# ------------------------------------------------------------------------------------------------ date rules
def nth_weekday(y, m, dow, n):
    d = D(y, m, 1)
    return d + dt.timedelta(days=(dow - d.weekday()) % 7 + 7 * (n - 1))


def last_weekday(y, m, dow):
    d = D(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - dow) % 7)


def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo, da = divmod(h + l - 7 * m + 114, 31)
    return D(y, mo, da + 1)


def nfp(y, m):
    """BLS Employment Situation by the plain rule: the third Friday after the Saturday that ends the week containing the 12th of the DATA month (y, m)."""
    d12 = D(y, m, 12)
    sat = d12 + dt.timedelta(days=(5 - d12.weekday()) % 7)          # the week is Sunday to Saturday: it ends on a Saturday (the 12th itself may be one)
    return sat + dt.timedelta(days=20)


def holidays(y):
    """{date: (name, kind, closed_stocks)} for one year by the NYSE rules. kind: 'closed' (stocks and futures), 'partial' (stocks closed, CME on holiday hours), 'bond' (stocks open), 'early'."""
    out = {}

    def put(d, name, kind):
        out[d] = (name, kind)
    ny = D(y, 1, 1)
    if ny.weekday() != 5:                                          # a Saturday New Year's is NOT observed on the Friday
        put(ny + dt.timedelta(days=1) if ny.weekday() == 6 else ny, "New Year's Day", "closed")
    put(nth_weekday(y, 1, 0, 3), "Martin Luther King Jr. Day", "partial")
    put(nth_weekday(y, 2, 0, 3), "Presidents Day", "partial")
    put(easter(y) - dt.timedelta(days=2), "Good Friday", "closed")
    put(last_weekday(y, 5, 0), "Memorial Day", "partial")
    for (m, dd, name) in ((6, 19, "Juneteenth"), (7, 4, "Independence Day"), (12, 25, "Christmas Day")):
        d = D(y, m, dd)
        put(d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d, name, "closed")
    put(nth_weekday(y, 9, 0, 1), "Labor Day", "partial")
    tg = nth_weekday(y, 11, 3, 4)
    put(tg, "Thanksgiving", "closed")
    put(tg + dt.timedelta(days=1), "Day after Thanksgiving", "early")
    c24 = D(y, 12, 24)
    if c24.weekday() < 5 and c24 not in out:
        put(c24, "Christmas Eve", "early")
    put(D(y, 11, 11), "Veterans Day", "bond")
    return out


def quarterly(y, m):
    return m in (3, 6, 9, 12)


def contract(y, m):
    """the MNQ contract month name the roll moves TO after the (y, m) quarterly expiry, e.g. (2026, 12) -> 'MNQ 03-27'."""
    ny, nm = (y + 1, 3) if m == 12 else (y, m + 3)
    return f"MNQ {nm:02d}-{ny % 100:02d}"


# ------------------------------------------------------------------------------------------------ the saved calendar
def read_calendar(path=CAL):
    rows = []
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if re.match(r"^\d{4}-\d{2}-\d{2}$", r.get("date", "")) and re.match(r"^\d\d:\d\d$", r.get("time_et", "")) and r.get("event"):
                    rows.append(r)
    except OSError:
        pass
    return rows


def classify(row):
    """(kind, title, impact) of one saved-calendar row, or None to skip it (claims come from the weekly rule; the press conference is part of the decision)."""
    ev, imp = row["event"], row["impact"].strip().lower()
    low = ev.lower()
    if "unemployment claims" in low or "press conference" in low:
        return None
    if low.startswith("fomc") and "minutes" in low:     # day-archive 2026-11-20: the minutes (3 weeks after a meeting) are not a decision
        return "other", "FOMC minutes 2:00 PM (" + (ev.split("(", 1)[1].rstrip(")") if "(" in ev else "last meeting") + ")", "med"
    if low.startswith("fomc"):
        return "fomc", "FOMC decision 2:00 PM" + (" with projections" if "projections" in low else "") + ", press conference 2:30 PM", "high"
    if low.startswith("cpi"):
        return "cpi", "CPI (consumer prices)", "high"
    if low.startswith("ppi"):
        return "ppi", "PPI (producer prices)", "med"
    if low.startswith("non-farm payrolls"):
        return "nfp", "Jobs report (NFP)", "high"
    if "pce" in low or low.startswith("gdp"):
        return "other", ev, "high" if "pce" in low else "med"
    return "other", ev, "med" if imp == "high" else "low"


# ------------------------------------------------------------------------------------------------ the build
def build(start, end, asof, cal_rows):
    s, e = D.fromisoformat(start), D.fromisoformat(end)
    events, seen = [], set()

    def add(d, time, kind, title, impact, verify, src, **extra):
        if not (s <= d <= e):
            return
        key = (d.isoformat(), kind, time, title)
        if key in seen:
            return
        seen.add(key)
        ev = {"date": d.isoformat(), "time": time, "kind": kind, "title": title, "impact": impact}
        ev.update(extra)
        ev["verify"] = verify
        ev["src"] = src
        events.append(ev)
    hol = {}
    for y in range(s.year, e.year + 1):
        hol.update(holidays(y))
    for d, (name, kind) in sorted(hol.items()):
        if kind == "closed":
            add(d, None, "holiday", f"{name}: US markets closed", "low", True, "US market holiday rule; check the CME holiday calendar for futures", closed=True)
        elif kind == "partial":
            add(d, None, "holiday", f"{name}: stock market closed, CME futures on holiday hours (check)", "med", True, "US market holiday rule; CME holiday hours: check the CME holiday calendar", partial=True)
        elif kind == "early":
            add(d, "13:15", "early", f"{name}: early close 1:15 PM ET", "med", True, "CME equity futures short day; check the CME holiday calendar", close_et="13:15")
        elif kind == "bond":
            add(d, None, "holiday", f"{name}: stocks trade, bond market closed", "low", False, "NYSE holiday calendar: stock market open")
    # options expiry, quad witching, NQ expiry and the roll
    d0 = D(s.year, s.month, 1)
    months = []
    while d0 <= e:
        months.append((d0.year, d0.month))
        d0 = D(d0.year + (d0.month == 12), d0.month % 12 + 1, 1)
    for (y, m) in months:
        fri = nth_weekday(y, m, 4, 3)
        if fri in hol and hol[fri][1] == "closed":
            fri -= dt.timedelta(days=1)                              # Good Friday: expiry on Thursday
        if quarterly(y, m):
            add(fri, "09:30", "quad", f"Quad witching and {['', '', '', 'March', '', '', 'June', '', '', 'September', '', '', 'December'][m]} NQ expiry", "med", False, "Third Friday of the quarter month; the quarterly NQ contract expires 9:30 AM ET")
            roll = fri - dt.timedelta(days=8)
            add(roll, "00:00", "roll", f"NQ roll: orders switch to {contract(y, m)} (8 days before expiry)", "med", False, "docs/ROLL_DEC_2026.md, engine/roll_watch.py: Thursday 00:00 ET, 8 days before the expiry")
            add(roll - dt.timedelta(days=1), "16:00", "roll", f"Your roll step: switch the NinjaTrader chart to {contract(y, m)}", "med", False, "docs/ROLL_DEC_2026.md: the evening before, after 16:00 ET")
        else:
            add(fri, "09:30", "opex", "Monthly options expiration (third Friday)", "low", False, "Third Friday of the month")
    # the jobs report by the BLS rule (the saved calendar wins when it has the month)
    saved = [(r, classify(r)) for r in cal_rows]
    saved_nfp = {r["date"][:7] for r, c in saved if c and c[0] == "nfp"}
    moved = []
    for (y, m) in months:
        dm = D(y - (m == 1), (m - 2) % 12 + 1, 1)                    # the data month is the month before the release month
        rel = nfp(dm.year, dm.month)
        if rel in hol and hol[rel][1] in ("closed", "partial") and s <= rel <= e:
            moved.append((dm, rel))                                     # the rule lands on a holiday: BLS moves it, and the new day is not a rule
        elif rel.strftime("%Y-%m") not in saved_nfp and s <= rel <= e and rel.isoformat() not in NFP_EXCEPTIONS:
            add(rel, "08:30", "nfp", f"Jobs report (NFP, {dm.strftime('%B')} data)", "high", True, "BLS rule: the third Friday after the week that contains the 12th; confirm on bls.gov")
    for r, c in saved:
        if not c:
            continue
        kind, title, impact = c
        d = D.fromisoformat(r["date"])
        src = f"data/news/events.csv ({r['source']}); confirm on the official page"
        if kind == "nfp":
            title += f", {(d.replace(day=1) - dt.timedelta(days=1)).strftime('%B')} data"
        add(d, r["time_et"], kind, title, impact, True, src)
    # claims: every Thursday at 08:30, on Wednesday when Thursday is a closed market day
    skip, d = [], s
    while d <= e:
        if d.weekday() == 3 and d in hol and hol[d][1] == "closed":
            skip.append(d.isoformat())
            add(d - dt.timedelta(days=1), "08:30", "claims", "Jobless claims (moved to Wednesday for the holiday)", "low", True, "Labor Department moves the Thursday release when Thursday is a holiday")
        d += dt.timedelta(days=1)
    events.sort(key=lambda x: (x["date"], x["time"] or "", x["kind"], x["title"]))
    # what the repo does not carry: named, never dated
    last = {k: max([r["date"] for r, c in saved if c and c[0] == k] or [""]) for k in ("cpi", "ppi")}
    undated = []
    for k, title in (("cpi", "CPI (consumer prices)"), ("ppi", "PPI (producer prices)")):
        after = f" after {last[k]}" if last[k] else ""
        undated.append({"kind": k, "title": f"{title}: the release{after}", "approx": "mid-month, 8:30 AM ET", "impact": "high" if k == "cpi" else "med", "verify": True, "confirm": CONFIRM[k], "src": "not in the saved calendar yet"})
    undated.append({"kind": "retail", "title": "Retail sales", "approx": "mid-month, 8:30 AM ET", "impact": "med", "verify": True, "confirm": CONFIRM["retail"], "src": "not in the saved calendar"})
    for dm, rel in moved:
        undated.append({"kind": "nfp", "title": f"Jobs report (NFP, {dm.strftime('%B')} data): the rule gives {rel.isoformat()}, a market holiday, so BLS moves it", "approx": "the week of that holiday, 8:30 AM ET", "impact": "high", "verify": True,
                        "confirm": "bls.gov, Release calendar, Employment Situation", "src": "rule date falls on a holiday"})
    fomc_last = max([r["date"] for r, c in saved if c and c[0] == "fomc"] or [""])
    if not fomc_last or fomc_last < end:
        undated.append({"kind": "fomc", "title": "FOMC decisions after " + (fomc_last or "the saved calendar"), "approx": "see the Fed calendar", "impact": "high", "verify": True, "confirm": CONFIRM["fomc"], "src": "not in the saved calendar"})
    weekly = [{"kind": "claims", "title": "Jobless claims", "dow": 3, "time": "08:30", "impact": "low", "verify": False, "skip": skip, "src": "US Labor Department: every Thursday 8:30 AM ET"}]
    return {"v": 1, "updated": asof, "generated": {"by": "tools/money/pythia_dates.py", "from": start, "to": end, "asof": asof, "calendar": "data/news/events.csv"}, "about": ABOUT, "weekly": weekly, "events": events, "undated": undated}


def render(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pythia dates: rule-based and saved-calendar events for events.json (never invents a date).")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to")
    ap.add_argument("--asof")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--calendar", default=CAL)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    prev = None
    try:
        with open(a.out, encoding="utf-8") as fh:
            prev = json.load(fh).get("generated")
    except (OSError, ValueError, AttributeError):
        pass
    g = {**DEFAULT, **(prev or {})}
    start, end, asof = a.start or g["from"], a.to or g["to"], a.asof or g["asof"]
    text = render(build(start, end, asof, read_calendar(a.calendar)))
    if a.check:
        try:
            cur = open(a.out, encoding="utf-8").read()
        except OSError:
            cur = None
        ok = cur == text
        print("events.json is in step" if ok else "events.json is NOT what pythia_dates.py writes: run  python tools/money/pythia_dates.py")
        return 0 if ok else 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, a.out)
    print(f"wrote {a.out} ({start} to {end}, as of {asof})")
    return 0


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    bad = []

    def ck(name, ok, info=""):
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))
        if not ok:
            bad.append(name)
    ck("easter: 2026 Apr 5, 2027 Mar 28, 2024 Mar 31", [easter(2026), easter(2027), easter(2024)] == [D(2026, 4, 5), D(2027, 3, 28), D(2024, 3, 31)])
    h26, h27 = holidays(2026), holidays(2027)
    ck("holidays 2026: Thanksgiving Nov 26 closed, Nov 27 early, Christmas Fri Dec 25, Christmas Eve Dec 24 early, Veterans Nov 11 bond", h26[D(2026, 11, 26)][1] == "closed" and h26[D(2026, 11, 27)][1] == "early" and h26[D(2026, 12, 25)][1] == "closed" and h26[D(2026, 12, 24)][1] == "early" and h26[D(2026, 11, 11)][1] == "bond")
    ck("holidays 2027: New Year Fri Jan 1, MLK Jan 18, Presidents Feb 15, Good Friday Mar 26 (closed)", h27[D(2027, 1, 1)][1] == "closed" and D(2027, 1, 18) in h27 and D(2027, 2, 15) in h27 and h27[D(2027, 3, 26)][0] == "Good Friday")
    ck("a Saturday New Year's is not observed on the Friday (2022); a Saturday Christmas is (2021-12-24); a Sunday July 4 moves to Monday (2021)", D(2021, 12, 31) not in holidays(2022) and D(2021, 12, 24) in holidays(2021) and D(2021, 7, 5) in holidays(2021))
    ck("NFP rule: Nov 6 2026, Dec 4 2026, and Jan 1 2027 (a holiday: that one is left undated)", [nfp(2026, 10), nfp(2026, 11), nfp(2026, 12)] == [D(2026, 11, 6), D(2026, 12, 4), D(2027, 1, 1)], [nfp(2026, 10), nfp(2026, 11), nfp(2026, 12)])
    ev = build(DEFAULT["from"], DEFAULT["to"], DEFAULT["asof"], read_calendar())
    es = ev["events"]
    by = lambda k: [e["date"] for e in es if e["kind"] == k]
    ck("rule dates: opex Nov 20 / Jan 15 / Feb 19, quad witching Dec 18 and Mar 19, the rolls Dec 10 and Mar 11 (8 days before), your steps the evening before", by("opex") == ["2026-11-20", "2027-01-15", "2027-02-19"] and by("quad") == ["2026-12-18", "2027-03-19"] and [e["date"] for e in es if e["kind"] == "roll" and e["time"] == "00:00"] == ["2026-12-10", "2027-03-11"] and [e["date"] for e in es if e["kind"] == "roll" and e["time"] == "16:00"] == ["2026-12-09", "2027-03-10"], [by("opex"), by("quad")])
    ck("the roll titles name the next contract: MNQ 03-27 after Dec 2026, MNQ 06-27 after Mar 2027", any("MNQ 03-27" in e["title"] for e in es if e["kind"] == "roll") and any("MNQ 06-27" in e["title"] for e in es if e["kind"] == "roll"))
    ck("claims: the weekly rule skips Nov 26, and a dated Wednesday Nov 25 replaces it", ev["weekly"][0]["skip"] == ["2026-11-26"] and "2026-11-25" in by("claims"))
    ck("FOMC decisions come from the saved calendar (Dec 9 2026, Jan 27 and Mar 17 2027), verify true, each with its source file; nothing is made up for day 1", by("fomc") == ["2026-10-28", "2026-12-09", "2027-01-27", "2027-03-17"] and all(e["verify"] and "events.csv" in e["src"] for e in es if e["kind"] == "fomc"), by("fomc"))
    ck("FOMC minutes (3 weeks after a meeting) are never a decision: Nov 18 / Dec 30 / Feb 17 are 'FOMC minutes', kind other (day-archive 2026-11-20)",
       not any("minutes" in e["title"].lower() for e in es if e["kind"] == "fomc") and [e["date"] for e in es if e["title"].startswith("FOMC minutes")] == ["2026-11-18", "2026-12-30", "2027-02-17"])
    ck("NFP: Nov 6 and Jan 8 (the BLS date for the Jan 1 holiday) from the saved calendar, Dec 4 / Feb 5 / Mar 5 from the BLS rule, all verify true", by("nfp") == ["2026-11-06", "2026-12-04", "2027-01-08", "2027-02-05", "2027-03-05"] and all(e["verify"] for e in es if e["kind"] == "nfp"), by("nfp"))
    ck("CPI Nov 10 and PPI Nov 13 (and the later ones the saved calendar holds, day-archive 2026-11-20) come from the saved calendar; the next CPI / PPI and retail sales are UNDATED with the official calendar named (no date field)", by("cpi")[:1] == ["2026-11-10"] and by("ppi")[:1] == ["2026-11-13"] and {u["kind"] for u in ev["undated"]} >= {"cpi", "ppi", "retail"}
       and all("date" not in u and u["confirm"] and u["verify"] for u in ev["undated"]) and any("bls.gov" in u["confirm"] for u in ev["undated"]) and any("census.gov" in u["confirm"] for u in ev["undated"]), [u["title"] for u in ev["undated"]])
    ck("no claims or press-conference rows are copied from the saved calendar (the weekly rule and the decision cover them)", not any("press conference 2:30 PM" not in e["title"] and e["kind"] == "other" and "Claims" in e["title"] for e in es))
    ck("deterministic: building twice gives the same text", render(ev) == render(build(DEFAULT["from"], DEFAULT["to"], DEFAULT["asof"], read_calendar())))
    ck("a missing saved calendar still builds the rule dates and leaves CPI / PPI undated, never dated", (lambda x: x["events"] and not any(e["kind"] in ("cpi", "ppi", "fomc") for e in x["events"]) and any(u["kind"] == "fomc" for u in x["undated"]))(build(DEFAULT["from"], DEFAULT["to"], DEFAULT["asof"], [])))
    src = open(os.path.abspath(__file__), encoding="utf-8").read().split("# ----", 1)[0]
    ck("offline: no network import", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|ssl)\b", src, re.M))
    d = tempfile.mkdtemp(prefix="pythia-")
    out = os.path.join(d, "events.json")
    ck("write then --check agree", main(["--out", out]) == 0 and main(["--out", out, "--check"]) == 0)
    open(out, "a").write(" ")
    ck("--check fails when the file drifts", main(["--out", out, "--check"]) == 1)
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
