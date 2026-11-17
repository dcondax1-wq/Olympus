"""The official Tier-1 calendar fetcher (engine/news_official.py): offline, saved pages only, never the network.

    python -X utf8 -m tests.test_news_official        # ~2 s

  a. BLS schedule pages (CPI, jobs report, PPI): every row, 08:30 ET, weekdays
  b. Fed FOMC calendar: decisions, projections '*', minutes 'Released' dates, else 3 weeks later (derived); notation votes skipped
  c. merge: past rows never touched, a fetched kind's future rows replaced (a stale meeting removed), other kinds kept,
     every new row names its source and fetch day, meta written, a second run changes nothing
  d. failures keep the old file: no network, an 'Access Denied' page, a page that parses to nothing
  e. the committed calendar: every month Dec 2026 - Dec 2027 has its CPI and jobs report, so the 08:30 blanket never fires
  f. the PC ops task runs it once a day after 16:35 ET; its files never block an auto-update
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import news_official as N  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "news", "official")
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)


def fx(name):
    with open(os.path.join(FX, name), encoding="utf-8") as fh:
        return fh.read()


OLD = """date,time_et,event,impact,source
2026-10-29,08:30,GDP Q3 advance estimate,high,bea.gov
2026-11-06,08:30,Non-Farm Payrolls (jobs report),high,bls.gov
2026-11-10,08:30,CPI (consumer inflation),high,bls.gov
2026-11-18,14:00,Fed meeting minutes (Oct 27-28),high,federalreserve.gov
2026-12-04,08:30,Non-Farm Payrolls (jobs report),high,MFFU T1 news calendar 2026 (help center)
2026-12-30,14:00,FOMC minutes (Dec meeting),high,MFFU T1 news calendar 2026 (help center)
2027-01-29,08:30,GDP Q4 advance estimate,high,bea.gov
2027-12-08,14:00,FOMC rate decision + projections,high,federalreserve.gov
2027-12-08,14:30,FOMC press conference,high,federalreserve.gov
2027-12-29,14:00,FOMC minutes (Dec meeting),high,federalreserve.gov (3 weeks after the meeting; derived)
"""


def parsers():
    for slug, first, last in (("bls_cpi", "2026-11-10", "2027-12-10"), ("bls_empsit", "2026-11-06", "2027-12-03"),
                              ("bls_ppi", "2026-11-13", "2027-12-15")):
        rows = N.parse_bls_schedule(fx(slug + ".htm"))
        check(f"a. {slug}: 14 releases {first} .. {last}, all 08:30, weekdays",
              len(rows) == 14 and rows[0][0] == first and rows[-1][0] == last and {h for _, h in rows} == {"08:30"}
              and all(dt.date.fromisoformat(d).weekday() < 5 for d, _ in rows), rows[:2])
    row = "<table><tr><td>March 2027</td><td>Apr. 13, 2027</td><td>10:00 AM</td></tr><tr><td>no date</td></tr></table>"
    check("a. a non-08:30 time is read; a row without a date is skipped", N.parse_bls_schedule(row) == [("2027-04-13", "10:00")],
          N.parse_bls_schedule(row))
    m = N.parse_fomc(fx("fed_fomc.htm"))
    by = {e["decision"]: e for e in m}
    y27 = [d for d in by if d.startswith("2027")]
    check("b. Fed 2027: 8 meetings, the last on Nov 17, none in December",
          len(y27) == 8 and max(y27) == "2027-11-17" and not any(d.startswith("2027-12") for d in y27), y27)
    check("b. Sep 2026 has projections, minutes released Oct 7 (read, not derived)",
          by["2026-09-16"]["sep"] and by["2026-09-16"]["minutes"] == "2026-10-07" and not by["2026-09-16"]["minutes_derived"],
          by.get("2026-09-16"))
    check("b. Dec 2026 minutes = 3 weeks later (Dec 30, MFFU's date), marked derived",
          by["2026-12-09"]["minutes"] == "2026-12-30" and by["2026-12-09"]["minutes_derived"], by.get("2026-12-09"))
    nv = ('<h4>2027 FOMC Meetings</h4><div class="fomc-meeting__month"><strong>January</strong></div>'
          '<div class="fomc-meeting__date">26-27 (notation vote)</div>'
          '<div class="fomc-meeting__month"><strong>March</strong></div><div class="fomc-meeting__date">16-17*</div><p>x</p>')
    got = N.parse_fomc(nv + " 2028 FOMC Meetings")
    check("b. a notation vote is skipped; '*' = projections", [(e["decision"], e["sep"]) for e in got] == [("2027-03-17", True)], got)
    got = sorted((r["time_et"], r["event"]) for r in N.rows_for(N.SOURCES[3], fx("fed_fomc.htm"), "2026-11-17")
                 if r["date"] == "2027-11-17")
    check("b. rows on Nov 17 2027: decision 14:00, presser 14:30, the Oct minutes 14:00",
          got == [("14:00", "FOMC minutes (Oct meeting)"), ("14:00", "FOMC rate decision"), ("14:30", "FOMC press conference")], got)


def merge(tmp):
    ev, meta = os.path.join(tmp, "events.csv"), os.path.join(tmp, "meta.json")
    with open(ev, "w", encoding="utf-8") as fh:
        fh.write(OLD)
    s = N.refresh(from_dir=FX, events_path=ev, meta_path=meta, today="2026-11-17", log=lambda *a: None)
    rows = N.read_events(ev)
    keys = {(r["date"], r["time_et"], r["event"]) for r in rows}
    check("c. 4/4 sources OK, events.csv rewritten", s["ok"] == 4 and s["changed"], s)
    check("c. past rows untouched (Nov 6 jobs, Nov 10 CPI, Oct 29 GDP)",
          [r for r in rows if r["date"] < "2026-11-17"] == [dict(zip(N.COLS, ln.split(","))) for ln in OLD.splitlines()[1:4]],
          [r for r in rows if r["date"] < "2026-11-17"])
    check("c. the stale Dec 8 2027 meeting and its Dec 29 minutes are gone; Nov 17 2027 decision + minutes Dec 8 are in",
          ("2027-12-08", "14:00", "FOMC rate decision + projections") not in keys
          and not any(k[0] == "2027-12-29" for k in keys)
          and ("2027-11-17", "14:00", "FOMC rate decision") in keys and ("2027-12-08", "14:00", "FOMC minutes (Nov meeting)") in keys,
          sorted(k for k in keys if k[0] >= "2027-11"))
    check("c. other kinds kept (Jan 2027 GDP)", ("2027-01-29", "08:30", "GDP Q4 advance estimate") in keys)
    check("c. Nov 18 minutes: one row (the old name replaced), MFFU's Dec dates confirmed by the official pages",
          sum(1 for k in keys if k[0] == "2026-11-18") == 1 and ("2026-12-04", "08:30", "Non-Farm Payrolls (jobs report)") in keys
          and ("2026-12-30", "14:00", "FOMC minutes (Dec meeting)") in keys, sorted(k for k in keys if k[0] < "2027"))
    new = [r for r in rows if r["date"] >= "2026-11-17" and N.kind_of(r["event"])]
    check("c. every new row names its source and the fetch day",
          new and all("(fetched 2026-11-17" in r["source"] for r in new), {r["source"] for r in new})
    check("c. PPI is medium (not an MFFU Tier-1), CPI / jobs high",
          {r["impact"] for r in new if "PPI" in r["event"]} == {"medium"}
          and {r["impact"] for r in new if N.kind_of(r["event"]) in ("cpi", "nfp")} == {"high"})
    m = json.load(open(meta, encoding="utf-8"))
    check("c. meta: every source ok with its url, fetch day and coverage",
          all(v["ok"] and v["fetched"] == "2026-11-17" and v["url"].startswith("https://") for v in m["sources"].values())
          and m["sources"]["bls_cpi"]["coverage"] == ["2026-12-10", "2027-12-10"], m["sources"].get("bls_cpi"))
    s2 = N.refresh(from_dir=FX, events_path=ev, meta_path=meta, today="2026-11-17", log=lambda *a: None)
    check("c. a second run changes nothing", not s2["changed"] and not s2["added"] and not s2["removed"], s2)
    return ev, meta


def failures(tmp, ev, meta):
    before = open(ev, "rb").read()

    def down(url):
        raise OSError("network down")
    s = N.refresh(fetch=down, events_path=ev, meta_path=meta, raw_dir=os.path.join(tmp, "raw"), today="2026-11-18",
                  log=lambda *a: None)
    m = json.load(open(meta, encoding="utf-8"))
    check("d. no network: events.csv byte-identical, 0 sources OK", open(ev, "rb").read() == before and s["ok"] == 0, s)
    check("d. no network: meta keeps the last good fetch day and records the error",
          m["sources"]["bls_cpi"]["fetched"] == "2026-11-17" and not m["sources"]["bls_cpi"]["ok"]
          and "network down" in m["sources"]["bls_cpi"]["error"], m["sources"]["bls_cpi"])
    denied = "<html><head><title>Access Denied</title></head><body><h2>Access Denied</h2></body></html>"

    class R:
        def __init__(self, b):
            self.b = b

        def read(self, n=-1):
            return self.b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    old_open = N.urllib.request.urlopen
    N.urllib.request.urlopen = lambda req, timeout=0: R(denied.encode())
    try:
        err = None
        try:
            N.http_get("https://www.bls.gov/schedule/news_release/cpi.htm")
        except RuntimeError as e:
            err = str(e)
        check("d. a BLS 'Access Denied' page is a failure, not an empty schedule", err == "access denied page", err)
    finally:
        N.urllib.request.urlopen = old_open
    pages = {s["url"]: fx(s["slug"] + ".htm") for s in N.SOURCES}
    pages[N.SOURCES[0]["url"]] = "<html><body><p>The schedule moved.</p></body></html>"      # CPI page changed: 0 rows
    with open(ev, "w", encoding="utf-8") as fh:
        fh.write(OLD + "2027-01-13,08:30,CPI (consumer inflation),high,old row\n")
    s = N.refresh(fetch=pages.get, events_path=ev, meta_path=meta, raw_dir=os.path.join(tmp, "raw"), today="2026-11-17",
                  log=lambda *a: None)
    rows = N.read_events(ev)
    check("d. a page that parses to nothing keeps that kind's old rows (CPI), the others update",
          s["ok"] == 3 and any(r["source"] == "old row" for r in rows)
          and not any("bls.gov release schedule" in r["source"] and "CPI" in r["event"] for r in rows)
          and any("bls.gov release schedule" in r["source"] and "Payrolls" in r["event"] for r in rows),
          s["sources"]["bls_cpi"])


def committed():
    from engine import multi_account as MA
    MA._NEWS["key"] = None
    MA.tier1_releases("2027-01-04")
    months = [f"{y}-{m:02d}" for y, m in [(2026, 12)] + [(2027, k) for k in range(1, 13)]]
    miss = [mo for mo in months if mo not in MA._NEWS["cpi"] or mo not in MA._NEWS["nfp"]]
    check("e. data/news/events.csv: CPI + jobs report known for every month Dec 2026 - Dec 2027 (no 08:30 blanket)", not miss, miss)
    hm = lambda day: [dt.datetime.fromtimestamp(x, N.ET_TZ).strftime("%H:%M") for x in MA.tier1_releases(day)]
    check("e. a plain Tuesday in Jan 2027 has no window; Jan 13 CPI and Jan 8 jobs do",
          hm("2027-01-05") == [] and hm("2027-01-13") == ["08:30"] and hm("2027-01-08") == ["08:30"],
          (hm("2027-01-05"), hm("2027-01-13"), hm("2027-01-08")))
    check("e. Nov 17 2027 FOMC (14:00 + 14:30) is a Tier-1 day; no phantom Dec 8 2027 decision (only its minutes)",
          hm("2027-11-17") == ["14:00", "14:30"] and hm("2027-12-08") == ["14:00"], (hm("2027-11-17"), hm("2027-12-08")))
    srcs = {r["source"] for r in N.read_events() if r["date"] >= "2026-12-01" and N.kind_of(r["event"]) in ("cpi", "nfp", "fomc")}
    check("e. every Dec 2026+ Tier-1 row comes from bls.gov / federalreserve.gov with a fetch day",
          srcs and all("(fetched " in s and (s.startswith("bls.gov") or s.startswith("federalreserve.gov")) for s in srcs), srcs)


def ops_hook():
    from engine import ops_checks as O
    t = lambda h, m: dt.datetime(2026, 11, 18, h, m, tzinfo=N.ET_TZ).timestamp()
    check("f. the PC ops task refreshes the calendar once a day after 16:35 ET",
          not O.calendar_due({}, t(16, 30)) and O.calendar_due({}, t(16, 40))
          and not O.calendar_due({"last_calendar_day": "2026-11-18"}, t(20, 0)))
    from engine import generated_files as G
    check("f. events.csv + official_meta.json are bot-made files (a refresh on the PC never blocks an update)",
          G.is_generated("data/news/events.csv") and G.is_generated("data/news/official_meta.json"))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="newsoff-")
    try:
        parsers()
        ev, meta = merge(tmp)
        failures(tmp, ev, meta)
        committed()
        ops_hook()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
