"""Week-ahead economic-event risk calendar for the live bot and the TradingView Pine strategy.

The Pine strategy cannot read a news feed, so each week its blackout windows are pasted into an input string:
one entry per release, "YYYY-MM-DD HH:MM" in ET (the release time; the Pine applies the before/after minutes).

Sources merged here (all times ET, America/New_York):
  1. SCHEDULE below: official release calendars, checked 2026-10-16
       BLS   https://www.bls.gov/schedule/2026/home.htm   (CPI, PPI, Employment Situation, JOLTS, ECI)
       BEA   https://www.bea.gov/news/schedule              (GDP, Personal Income & Outlays / PCE, trade)
       Fed   https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm  + /newsevents/2026-october|november.htm
       Census https://www.census.gov/economic-indicators/calendar-listview-2026.html (durables, housing, adv. indicators)
       ISM   rob-report-calendar (via search; site requires login)   Conference Board / UMich / ADP: inferred + search
  2. Forex Factory weekly feed (engine.news.ff_calendar, current week only)
  3. data/news/events.csv + ff_archive.csv (engine.news.historical_events)

US daylight saving ends Sun 2026-11-01 02:00: every time here stays ET wall-clock (EDT before, EST after).
UK clocks change a week earlier (Sun 2026-10-25), so European releases land one hour later in ET Oct 26-30.

CLI
  python -m engine.calendar_week                       # print next week's table + Pine string
  python -m engine.calendar_week --weeks 2 --write     # update tradingview/blackouts.txt, research/WEEK_AHEAD.md,
                                                       #   append new rows to data/news/events.csv (de-duplicated)
  python -m engine.calendar_week --start 2026-10-19 --weeks 3 --impact medium
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from zoneinfo import ZoneInfo

ET_TZ = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_CSV = os.path.join(ROOT, "data", "news", "events.csv")
BLACKOUTS_TXT = os.path.join(ROOT, "tradingview", "blackouts.txt")
PINE = os.path.join(ROOT, "tradingview", "liquidity_engine.pine")
BRIEF_MD = os.path.join(ROOT, "research", "WEEK_AHEAD.md")
DST_END = dt.date(2026, 11, 1)

# confidence: "official" = on the publisher's own release calendar; "official-search" = publisher's calendar seen via
# search snippets (page not fetchable); "inferred" = from the publisher's standing rule / third-party calendars.
# Event names for CPI / NFP / PPI / FOMC match data/build_news.py so events.csv stays de-duplicated.
SCHEDULE = [
    # ---- week of 2026-10-19 (FOMC blackout for Fed speakers runs Sat Oct 17 -> Thu Oct 29)
    ("2026-10-20", "08:30", "Housing Starts / Building Permits", "low", "census.gov", "official"),
    ("2026-10-22", "08:30", "Unemployment Claims", "medium", "dol.gov", "inferred"),
    ("2026-10-23", "09:45", "S&P Global Flash PMIs", "medium", "spglobal.com", "inferred"),
    ("2026-10-23", "10:00", "UMich Consumer Sentiment (final Oct)", "medium", "sca.isr.umich.edu", "inferred"),
    # ---- week of 2026-10-26
    ("2026-10-27", "08:30", "Durable Goods Orders", "medium", "census.gov", "official"),
    ("2026-10-27", "10:00", "CB Consumer Confidence", "high", "conference-board.org", "inferred"),
    ("2026-10-27", "10:00", "New Home Sales", "medium", "census.gov", "official"),
    ("2026-10-28", "08:30", "Advance Goods Trade / Retail & Wholesale Inventories", "low", "census.gov", "official"),
    ("2026-10-28", "14:00", "FOMC rate decision", "high", "federalreserve.gov", "official"),
    ("2026-10-28", "14:30", "FOMC press conference", "high", "federalreserve.gov", "official"),
    ("2026-10-29", "08:30", "GDP Q3 advance estimate", "high", "bea.gov", "official"),
    ("2026-10-29", "08:30", "Personal Income & Outlays / Core PCE (Sep)", "high", "bea.gov", "official"),
    ("2026-10-29", "08:30", "Unemployment Claims", "medium", "dol.gov", "inferred"),
    ("2026-10-30", "08:30", "Employment Cost Index Q3", "medium", "bls.gov", "official"),
    # ---- week of 2026-11-02 (US clocks back Sun Nov 1; midterm elections Tue Nov 3)
    ("2026-11-02", "10:00", "ISM Manufacturing PMI", "high", "ismworld.org", "official-search"),
    ("2026-11-03", "10:00", "JOLTS Job Openings (Sep)", "high", "bls.gov", "official"),
    ("2026-11-04", "08:15", "ADP Non-Farm Employment (Oct)", "high", "adp.com", "inferred"),
    ("2026-11-04", "08:30", "Trade Balance (Sep)", "low", "bea.gov", "official"),
    ("2026-11-04", "10:00", "ISM Services PMI", "high", "ismworld.org", "official-search"),
    ("2026-11-05", "08:30", "Unemployment Claims", "medium", "dol.gov", "inferred"),
    ("2026-11-05", "08:30", "Productivity & Unit Labor Costs Q3 (prelim)", "medium", "bls.gov", "official"),
    ("2026-11-06", "08:30", "Non-Farm Payrolls (jobs report)", "high", "bls.gov", "official"),
    # ---- week of 2026-11-09 (shown with --weeks 4)
    ("2026-11-10", "08:30", "CPI (consumer inflation)", "high", "bls.gov", "official"),
    ("2026-11-12", "08:30", "Unemployment Claims", "medium", "dol.gov", "inferred"),
    ("2026-11-13", "08:30", "PPI (producer inflation)", "high", "bls.gov", "official"),
    # named without "FOMC": model.py / news.guard treat any event containing "FOMC" as an FOMC day (PM off)
    ("2026-11-18", "14:00", "Fed meeting minutes (Oct 27-28)", "high", "federalreserve.gov", "official"),
]

# context notes per day, not blackouts (unscheduled / after-hours / overnight risk)
DAY_NOTES = {
    "2026-10-19": "Fed speaker blackout in force (no Fed chair/governor remarks expected until after Oct 28).",
    "2026-10-26": "UK/EU clocks went back Sun Oct 25: London data and the London open are one hour later in ET this week.",
    "2026-10-28": "Mega-cap earnings cluster this week (MSFT/GOOGL/META/AAPL/AMZN typically report the last week of "
                  "October, after the close): overnight gaps possible. Dates not confirmed here.",
    "2026-11-02": "First session on EST (US clocks went back Sun Nov 1). CME still opens 18:00 ET; killzones unchanged in ET.",
    "2026-11-03": "US midterm elections: results arrive overnight into Wed Nov 4 (no scheduled time).",
    "2026-11-04": "Post-election session: overnight gap / trend risk from the results, plus ADP and ISM Services.",
}
# days with no high-impact release but unscheduled risk worth a manual look
ELEVATED_DAYS = {}

# canonical key so the FF feed's "Core CPI m/m" and our "CPI (consumer inflation)" don't double-list
_KEYS = [("minutes", "fomc_min"),("press conf", "fomc_pc"), ("fomc", "fomc"), ("federal funds", "fomc"),
         ("cpi", "cpi"), ("ppi", "ppi"), ("non-farm", "nfp"), ("payroll", "nfp"), ("adp", "adp"), ("gdp", "gdp"),
         ("pce", "pce"), ("personal", "pce"), ("retail sales", "retail"), ("ism manufacturing", "ism_m"),
         ("ism services", "ism_s"), ("jolts", "jolts"), ("claims", "claims"), ("uom", "umich"), ("umich", "umich"),
         ("consumer confidence", "cb"), ("cb consumer", "cb"), ("durable", "durables"), ("employment cost", "eci"),
         ("warsh", "chair"), ("fed chair", "chair"), ("powell", "chair")]


def _key(name: str) -> str:
    n = name.lower()
    for frag, k in _KEYS:
        if frag in n:
            return k
    return n[:20]


def _params():
    p = {"news_before_min": 15, "news_after_min": 30, "news_flatten_min": 5, "fomc_pm_off": True,
         "entry_windows": [[570, 690], [810, 930]], "flat_mod": 955}
    try:
        from .model import DEFAULTS
        p.update({k: DEFAULTS[k] for k in p if k in DEFAULTS})
    except Exception:
        pass
    return p


def _rank(impact):
    return {"high": 3, "medium": 2, "low": 1}.get((impact or "").lower(), 0)


def week_start(d: dt.date) -> dt.date:
    """Monday of the trading week containing d (Sat/Sun roll forward to the coming Monday)."""
    if d.weekday() >= 5:
        return d + dt.timedelta(days=7 - d.weekday())
    return d - dt.timedelta(days=d.weekday())


def collect(start: dt.date, end: dt.date, min_impact="low", use_feed=True):
    """Every USD event with start <= date <= end, merged from SCHEDULE, the FF feed and the stored calendars."""
    rows = {}

    def add(date, time_et, event, impact, source, conf):
        if not (start <= dt.date.fromisoformat(date) <= end) or _rank(impact) < _rank(min_impact):
            return
        k = (date, time_et, _key(event))
        old = rows.get(k)
        if old is None:
            rows[k] = {"date": date, "time_et": time_et, "event": event, "impact": impact, "source": source,
                       "confidence": conf}
        else:   # the same release seen twice: keep the higher impact, note the extra source
            if _rank(impact) > _rank(old["impact"]):
                old["impact"] = impact
            if source not in old["source"]:
                old["source"] += f" + {source}"
            if conf == "official":
                old["confidence"] = "official"

    for r in SCHEDULE:
        add(*r)
    try:
        from . import news
        if use_feed:
            for e in news.ff_calendar():
                if e["currency"] != "USD" or e["impact"] not in ("high", "medium", "low"):
                    continue
                t = dt.datetime.fromtimestamp(e["t"], ET_TZ)
                add(t.strftime("%Y-%m-%d"), t.strftime("%H:%M"), e["event"], e["impact"], "forexfactory", "ff-feed")
        for e in news.historical_events(("high", "medium")):
            add(e["date"], str(e["time_et"])[:5], e["event"], e["impact"], e["source"], "stored")
    except Exception as exc:  # feed/archive unavailable: SCHEDULE alone still produces a calendar
        print("calendar_week: news sources unavailable:", exc)
    return sorted(rows.values(), key=lambda r: (r["date"], r["time_et"], -_rank(r["impact"])))


def _dt(r):
    return dt.datetime.fromisoformat(f"{r['date']} {r['time_et']}").replace(tzinfo=ET_TZ)


def _hhmm(x: dt.datetime):
    return x.strftime("%H:%M")


def _kz_hits(a: dt.datetime, b: dt.datetime, p):
    names = {0: "NY AM killzone 09:30-11:30", 1: "NY PM killzone 13:30-15:30"}
    m0, m1 = a.hour * 60 + a.minute, b.hour * 60 + b.minute
    return [names.get(i, f"window {i}") for i, (w0, w1) in enumerate(p["entry_windows"]) if m0 < w1 and m1 > w0]


def dashboard_rows(start: dt.date, end: dt.date, min_impact="medium", use_feed=True):
    """Dashboard dicts: date, time ET, event, impact, source, confidence, blackout start/end, flatten time, killzones."""
    p = _params()
    out = []
    evs = collect(start, end, min_impact, use_feed)
    fomc_days = {r["date"] for r in evs if r["impact"] == "high" and _key(r["event"]) in ("fomc", "fomc_pc")}
    for r in evs:
        t = _dt(r)
        hi = r["impact"] == "high"
        b0 = t - dt.timedelta(minutes=p["news_before_min"])
        b1 = t + dt.timedelta(minutes=p["news_after_min"])
        fl = t - dt.timedelta(minutes=p["news_flatten_min"]) if p["news_flatten_min"] else None
        out.append({**r, "weekday": t.strftime("%a"), "utc_offset": t.strftime("%z"),
                    "blackout_start": _hhmm(b0) if hi else None, "blackout_end": _hhmm(b1) if hi else None,
                    "flatten_at": _hhmm(fl) if hi and fl else None,
                    "killzones_hit": _kz_hits(b0, b1, p) if hi else [],
                    "fomc_pm_off": bool(hi and p["fomc_pm_off"] and r["date"] in fomc_days),
                    "t": int(t.timestamp())})
    return out


def pine_entries(start: dt.date, end: dt.date, use_feed=True):
    """Unique high-impact release times as 'YYYY-MM-DD HH:MM' (ET). Two releases at the same minute = one entry."""
    seen = []
    for r in collect(start, end, "high", use_feed):
        if r["impact"] != "high":
            continue
        s = f"{r['date']} {r['time_et']}"
        if s not in seen:
            seen.append(s)
    return seen


def pine_format():
    """Separator the Pine input expects: reads tradingview/liquidity_engine.pine. Returns ',' | '\\n' | None (no input yet)."""
    try:
        src = open(PINE, encoding="utf-8").read()
    except OSError:
        return None
    low = src.lower()
    if "blackout" not in low and "news" not in low:
        return None
    for line in src.splitlines():
        ln = line.lower()
        if "str.split" in ln and ("blackout" in ln or "news" in ln):
            if '"\\n"' in line:
                return "\n"
            if '","' in line.replace(" ", "") or "', '" in line:
                return ","
    return ","  # input.string / input.text_area exists but separator not detected: comma is the safe default


def pine_string(start: dt.date, end: dt.date, sep=",", use_feed=True):
    return sep.join(pine_entries(start, end, use_feed))


# ------------------------------------------------------------------ outputs
def _day_plan(rows, day: str):
    """Risk level + recommended action for one trading day."""
    hi = [r for r in rows if r["date"] == day and r["impact"] == "high"]
    keys = {_key(r["event"]) for r in hi}
    if day in ELEVATED_DAYS and not hi:
        return "ELEVATED", ELEVATED_DAYS[day]
    am = [r for r in hi if any("AM" in k for k in r["killzones_hit"])]
    pause = ", ".join(sorted({f"{r['blackout_start']}-{r['blackout_end']}" for r in am}))
    if keys & {"fomc", "fomc_pc"}:
        return "HIGH", "NO PM SESSION. This is automatic: no entries after 13:00 ET, and any open trade is closed by " \
                       "13:55. The AM session runs as normal, but pre-FOMC mornings are often range-bound. Half size is " \
                       "reasonable."
    if keys & {"cpi", "nfp"}:
        return "HIGH", "NORMAL, with a manual check at 09:25. If the 08:30 print has already moved NQ more than its " \
                       "usual full opening range, treat it as a trend day and skip the AM session (NO AM SESSION). " \
                       "Reversal setups fail on trend days. The bot's blackout ends at 09:00, before the killzone opens."
    if keys & {"gdp", "pce"}:
        return "ELEVATED", "NORMAL. The 08:30 print sets up the first sweep at the open. The bot's blackout ends at 09:00."
    if am:
        return "ELEVATED", f"NORMAL. The bot pauses entries {pause} for the 10:00 release, inside the AM killzone."
    if hi:
        return "NORMAL", "NORMAL. The release falls outside the killzones."
    return "LOW", "NORMAL."


def write_blackouts(start, end, use_feed=True, path=BLACKOUTS_TXT):
    fmt = pine_format()
    entries = pine_entries(start, end, use_feed)
    p = _params()
    lines = [
        "# Liquidity Engine - news blackout input for tradingview/liquidity_engine.pine",
        f"# Generated {dt.datetime.now(ET_TZ):%Y-%m-%d %H:%M} ET by `python -m engine.calendar_week` for {start} .. {end}",
        "# Each entry = a HIGH-impact USD release time, ET wall clock (EDT before 2026-11-01, EST after).",
        f"# The Pine applies the window itself: {p['news_before_min']} min before -> {p['news_after_min']} min after, "
        f"flatten {p['news_flatten_min']} min before.",
        "# FOMC days (14:00 decision): the bot's 'no entries after 13:00' rule is NOT expressible as a release time;",
        "#   the Pine must apply it itself (or turn the PM killzone off manually on those dates): "
        + (", ".join(sorted({e[:10] for e, _ in _fomc_pairs(start, end, use_feed)})) or "none in range"),
        "# Paste ONE of the two blocks below (without the # lines) into the strategy's blackout input.",
        "# Pine input detected in liquidity_engine.pine: "
        + ("no (input not added yet) - both formats written" if fmt is None else ("newline-separated" if fmt == "\n" else "comma-separated")),
        "",
        "# --- comma-separated (one line) ---",
        ",".join(entries),
        "",
        "# --- one per line ---",
        *entries,
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return entries


def _fomc_pairs(start, end, use_feed):
    return [(f"{r['date']} {r['time_et']}", r) for r in collect(start, end, "high", use_feed)
            if _key(r["event"]) in ("fomc", "fomc_pc")]


def append_events_csv(start, end, use_feed=True, path=EVENTS_CSV):
    """Append high/medium rows not already in events.csv (by date+time+event, and by date+time+canonical key)."""
    have_exact, have_key = set(), set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                have_exact.add((r["date"], r["time_et"][:5], r["event"]))
                have_key.add((r["date"], r["time_et"][:5], _key(r["event"])))
    new = []
    for r in collect(start, end, "medium", use_feed):
        if r["confidence"] == "stored":
            continue
        k1 = (r["date"], r["time_et"], r["event"])
        k2 = (r["date"], r["time_et"], _key(r["event"]))
        if k1 in have_exact or k2 in have_key:
            continue
        have_exact.add(k1)
        have_key.add(k2)
        src = r["source"].split(" + ")[0]
        new.append([r["date"], r["time_et"], r["event"], r["impact"], src])
    if new:
        needs_nl = False
        if os.path.exists(path) and os.path.getsize(path):
            with open(path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                needs_nl = f.read(1) not in (b"\n", b"\r")
        with open(path, "a", encoding="utf-8", newline="") as f:
            if needs_nl:
                f.write("\n")
            w = csv.writer(f, lineterminator="\n")
            w.writerows(new)
    return new


def write_brief(start, end, use_feed=True, path=BRIEF_MD):
    rows = dashboard_rows(start, end, "medium", use_feed)
    p = _params()
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    unconfirmed = [r for r in rows if r["impact"] == "high" and r["confidence"] not in ("official", "stored")]
    L = [f"# Week-ahead risk brief: {start:%a %d %b} to {end:%a %d %b %Y}",
         "",
         f"_Generated {dt.datetime.now(ET_TZ):%Y-%m-%d %H:%M} ET by `python -m engine.calendar_week --write`. "
         "All times are New York time (ET)._",
         "",
         "## How the bot handles news",
         "",
         f"- No new entries from {p['news_before_min']} minutes before to {p['news_after_min']} minutes after any "
         "high-impact US release. An open trade is closed "
         f"{p['news_flatten_min']} minutes before the release.",
         "- On FOMC days there are no entries after 13:00 ET, so the afternoon killzone is off.",
         "- The bot only enters inside the killzones (09:30-11:30 and 13:30-15:30 ET). An 08:30 release's blackout "
         "(08:15-09:00) ends before the morning killzone opens, so it does not stop the bot trading the open. "
         "It does shape the open: the 08:30 move sets the overnight levels that get swept.",
         "- 10:00 releases (ISM, JOLTS, Conference Board) fall inside the morning killzone: entries pause 09:45-10:30.",
         "- In the backtests, news days were not where the strategy lost money. The losing stretches came from "
         "trending regimes. The blackout is a safety net, not an edge, so sitting out whole days costs trade count "
         "(the target is 1-4 trades a week).",
         "",
         "## Clock changes",
         "",
         "- **Sun 25 Oct**: UK and EU clocks go back. For Oct 26-30, European data and the London open come one hour "
         "later in ET than usual.",
         "- **Sun 1 Nov**: US daylight saving ends (EDT to EST). Release times, killzones and the 18:00 ET Globex open "
         "stay the same in ET. TradingView (America/New_York) and the Python bot (zoneinfo) both follow ET wall-clock "
         "time automatically. Any tool that runs on UTC moves one hour that night.",
         ""]
    for wk in sorted({week_start(x) for x in days}):
        L += [f"## Week of {wk:%a %d %b}", ""]
        for x in [y for y in days if week_start(y) == wk]:
            ds = x.isoformat()
            level, action = _day_plan(rows, ds)
            L.append(f"### {x:%a %d %b}: risk {level}")
            L.append("")
            day_rows = [r for r in rows if r["date"] == ds]
            if not day_rows:
                L.append("- No scheduled medium or high-impact US releases.")
            for r in day_rows:
                tag = "**HIGH**" if r["impact"] == "high" else r["impact"]
                extra = ""
                if r["impact"] == "high":
                    kz = ", ".join(r["killzones_hit"]) or "no killzone"
                    extra = f" | blackout {r['blackout_start']}-{r['blackout_end']}, flatten {r['flatten_at']} | hits: {kz}"
                conf = "" if r["confidence"] in ("official", "stored") else f" _(confidence: {r['confidence']})_"
                L.append(f"- {r['time_et']} {r['event']} ({tag}){extra}{conf}")
            if ds in DAY_NOTES:
                L.append(f"- Note: {DAY_NOTES[ds]}")
            L += ["", f"**Action:** {action}", ""]
    la0, la1 = end + dt.timedelta(days=1), end + dt.timedelta(days=9)
    ahead = [r for r in dashboard_rows(la0, la1, "high", use_feed) if r["impact"] == "high"]
    L += [f"## Look-ahead: {la0:%d %b} to {la1:%d %b} (high impact only; the next run's Pine string will include these)", ""]
    L += [f"- {r['weekday']} {r['date']} {r['time_et']} {r['event']}"
          + ("" if r["confidence"] in ("official", "stored") else f" _(confidence: {r['confidence']})_")
          + (f" | hits: {', '.join(r['killzones_hit'])}" if r["killzones_hit"] else "") for r in ahead] or ["- none known"]
    L += [f"- Note: {DAY_NOTES[k]} ({k})" for k in sorted(DAY_NOTES) if la0.isoformat() <= k <= la1.isoformat()]
    L.append("")
    unconfirmed += [r for r in ahead if r["confidence"] not in ("official", "stored")]
    L += ["## Not confirmed from the publisher's own page", ""]
    L += [f"- {r['date']} {r['time_et']} {r['event']} ({r['confidence']}, {r['source']})" for r in unconfirmed] or ["- none"]
    L += ["- Fed speeches: neither the Fed's October nor its November calendar lists any speeches. Fed speakers are in "
          "their pre-FOMC blackout from Oct 17 to Oct 29. A chair speech added later appears on the Forex Factory feed "
          "the week it happens. Re-run this command on Sunday.",
          "- Weekly jobless claims are medium-impact on Forex Factory, so they get no blackout.",
          "",
          "## Weekly routine",
          "",
          "1. Sunday afternoon: `python -m engine.calendar_week --weeks 2 --write` (pulls the new Forex Factory week).",
          "2. Paste the block from `tradingview/blackouts.txt` into the Pine strategy's blackout input.",
          "3. Read this file and note any day marked HIGH.",
          ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    return rows


def _table(rows):
    out = [f"{'date':10} {'day':3} {'ET':5} {'impact':6} {'blackout':11} {'flat':5} {'conf':15} event"]
    for r in rows:
        bo = f"{r['blackout_start']}-{r['blackout_end']}" if r["blackout_start"] else ""
        out.append(f"{r['date']} {r['weekday']} {r['time_et']} {r['impact']:6} {bo:11} {r['flatten_at'] or '':5} "
                   f"{r['confidence']:15} {r['event']}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", help="any day of the first week (YYYY-MM-DD); default = the coming Monday")
    ap.add_argument("--weeks", type=int, default=1)
    ap.add_argument("--impact", default="medium", choices=["low", "medium", "high"], help="min impact for the table")
    ap.add_argument("--write", action="store_true", help="update blackouts.txt, WEEK_AHEAD.md and append to events.csv")
    ap.add_argument("--no-feed", action="store_true", help="skip the Forex Factory refresh")
    a = ap.parse_args(argv)
    today = dt.datetime.now(ET_TZ).date()
    start = dt.date.fromisoformat(a.start) if a.start else today + dt.timedelta(days=7 - today.weekday())
    start = week_start(start)
    end = start + dt.timedelta(days=7 * a.weeks - 3)  # through Friday of the last week
    feed = not a.no_feed
    rows = dashboard_rows(start, end, a.impact, feed)
    print(_table(rows))
    fmt = pine_format()
    print("\nPine blackout string (" + ("comma" if fmt in (None, ",") else "newline") + "):")
    print(pine_string(start, end, "," if fmt is None else fmt, feed))
    if a.write:
        write_blackouts(start, end, feed)
        write_brief(start, end, feed)
        horizon = max(end, max(dt.date.fromisoformat(r[0]) for r in SCHEDULE))
        new = append_events_csv(start, horizon, feed)   # Python bot gets every known future release, not just 2 weeks
        print(f"\nwrote {BLACKOUTS_TXT}\nwrote {BRIEF_MD}\nappended {len(new)} rows to {EVENTS_CSV}")
        for r in new:
            print("  +", ",".join(r))


if __name__ == "__main__":
    main()
