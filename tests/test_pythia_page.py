"""PYTHIA, the OLYMPUS risk calendar (tools/web_public/pythia/, AGORA look, 2026-11-10): the next 14 days of market-moving events for NQ from a bundled, hand-maintained events.json (dates only when sure, "check date"
otherwise, unknown dates listed apart and never guessed), what the bots do around each, a risk colour, New York (ET) times from the daylight-saving rule, today's strip and a marble wheel of days in 3D. Read only.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, events.json is honest (every date follows its rule: third Fridays, the roll 8 days before the expiry, Thanksgiving), the wiring rows exist
  b. the maths in node (pythiacore.js): dates, New York time against Intl for two years incl. DST (Nov 1 2026, Mar 14 2027), the countdown across the fall-back night, the 14-day calendar, risk colours, the roll, junk input, no markup
  c. Chromium 390 x 844 (and 375 x 667): the Dec 7 window (FOMC, the roll, quad witching), the Oct 30 window across Nov 1, today's strip and live brief, the 3D wheel (and the flat twin with ?q=off), the fallback demo, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_pythia_page            (--static: parts a and b only)
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "pythia", "Pythia"
check = AK.check


def nth_weekday(y, m, dow, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(dow - d.weekday()) % 7 + 7 * (n - 1))
    return d


def test_static():
    gen = os.path.join(AK.ROOT, "tools", "money", "pythia_dates.py")
    r1 = subprocess.run([sys.executable, "-I", gen, "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the date generator's selftest passes (tools/money/pythia_dates.py --selftest)", r1.returncode == 0 and "ALL PASS" in r1.stdout, r1.stdout[-600:] + r1.stderr[-300:])
    r2 = subprocess.run([sys.executable, "-I", gen, "--check"], capture_output=True, text=True, timeout=300)
    check("a. events.json is EXACTLY what `python tools/money/pythia_dates.py` writes from the rules and data/news/events.csv (regenerate it after changing either)", r2.returncode == 0, r2.stdout[-300:] + r2.stderr[-200:])
    spec = importlib.util.spec_from_file_location("pythia_dates", gen)
    PD = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PD)
    bn = AK.read(os.path.join(AK.ROOT, "data", "build_news.py"))
    hist = re.search(r'NFP = """(.*?)"""', bn, re.S).group(1).split()
    miss = [h for h in hist if PD.nfp(*((lambda d: (d.year - (d.month == 1), (d.month - 2) % 12 + 1))(dt.date.fromisoformat(h)))).isoformat() != h]
    check("a. the NFP rule (third Friday after the week with the 12th) matches the BLS archive in data/build_news.py: " + f"{len(hist) - len(miss)} of {len(hist)} releases, and the ones it misses are EXACTLY the listed exceptions (shutdown, weeks next to a holiday)",
          len(hist) >= 36 and set(miss) == set(PD.NFP_EXCEPTIONS) and len(hist) - len(miss) >= 28, (miss, sorted(PD.NFP_EXCEPTIONS)))
    ho = PD.holidays(2026)
    check("a. holidays by rule: Thanksgiving Nov 26, Christmas Dec 25, early closes Nov 27 and Dec 24; and the roll rule is the docs' (Thursday 8 days before the expiry)", ho[dt.date(2026, 11, 26)][1] == "closed" and ho[dt.date(2026, 12, 25)][1] == "closed" and ho[dt.date(2026, 11, 27)][1] == "early" and ho[dt.date(2026, 12, 24)][1] == "early" and (dt.date(2026, 12, 18) - dt.timedelta(days=8)).isoformat() == "2026-12-10")
    AK.static_kit(APP, NAME, reads=("./events.json", "../home.json"))
    d = os.path.join(AK.WEB, APP)
    html = AK.read(os.path.join(d, "index.html"))
    check("a. the page order: today and the wheel, the live briefing, the 14 days, the day, coming up, dates to confirm", html.index('id="stage"') < html.index('id="liveCard"') < html.index('id="grid"') < html.index('id="dayList"') < html.index('id="nextList"') < html.index('id="undatedCard"'))
    check("a. the 3D wheel is its own module tag (a failed load can never stop the page) and the flat twin exists", 'src="pythiawheel.js' in html and "PYTHIA_WHEEL_FAIL" in html and 'id="flat"' in html)
    wheel = AK.read(os.path.join(d, "pythiawheel.js"))
    check("a. the wheel is light: the render core + materials, bloom <= .25, a dpr cap <= 1.5, no data, no network, idle rules (hidden, frameGap, reduced motion)",
          "olympus/render.js" in wheel and re.search(r"strength:\s*0\.(?:[0-2]\d?)\b", wheel) and "maxDpr: 1.5" in wheel and "O.hidden()" in wheel and "frameGap" in wheel and "RM" in wheel and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket", wheel))
    ev = json.load(open(os.path.join(d, "events.json"), encoding="utf-8"))
    evs = ev["events"]
    by = {}
    for e in evs:
        by.setdefault(e["kind"], []).append(e)
    check("a. events.json: every event has an ISO date, a valid kind and impact and a verify flag; times are HH:MM; the undated ones carry NO date and verify true (never guessed)",
          all(re.match(r"^\d{4}-\d{2}-\d{2}$", e["date"]) and e["impact"] in ("high", "med", "low") and isinstance(e["verify"], bool) and (e["time"] is None or re.match(r"^\d\d:\d\d$", e["time"])) for e in evs)
          and all("date" not in u and u["verify"] is True and u["approx"] for u in ev["undated"]) and {u["kind"] for u in ev["undated"]} == {"cpi", "ppi", "retail", "nfp"} and all(u["confirm"] for u in ev["undated"]), ev["undated"])
    third = lambda y, m: nth_weekday(y, m, 4, 3).isoformat()
    check("a. the rule dates are right: monthly expiry = third Friday of Nov 2026 (Nov 20), quad witching = third Friday of Dec (Dec 18), Thanksgiving = fourth Thursday (Nov 26), the early close is the Friday after, NFP = first Friday of Dec (Dec 4)",
          by["opex"][0]["date"] == third(2026, 11) == "2026-11-20" and by["quad"][0]["date"] == third(2026, 12) == "2026-12-18" and any(e["date"] == nth_weekday(2026, 11, 3, 4).isoformat() == "2026-11-26" and e["closed"] for e in by["holiday"])
          and any(e["date"] == "2026-11-27" and e["kind"] == "early" for e in evs) and "2026-12-04" in [e["date"] for e in by["nfp"]] and nth_weekday(2026, 12, 4, 1).isoformat() == "2026-12-04", by["nfp"])
    roll = [e for e in by["roll"] if e["time"] == "00:00"][0]
    check("a. the December roll: orders switch Thursday 2026-12-10 00:00 ET, exactly 8 days before the Dec 18 expiry (docs/ROLL_DEC_2026.md, engine/roll_watch.py), and the owner's step is Wednesday Dec 9 after 16:00 ET",
          roll["date"] == "2026-12-10" and dt.date(2026, 12, 10).weekday() == 3 and (dt.date(2026, 12, 18) - dt.date(2026, 12, 10)).days == 8 and any(e["date"] == "2026-12-09" and e["time"] == "16:00" for e in by["roll"]), by["roll"])
    doc = AK.read(os.path.join(AK.ROOT, "docs", "ROLL_DEC_2026.md"))
    check("a. the roll words agree with docs/ROLL_DEC_2026.md (Wed Dec 9 after 16:00 ET, Thu Dec 10 00:00, MNQ 03-27)", "Wed Dec 9, after 16:00 ET" in doc and "Thu 12-10, 00:00" in doc and "MNQ 03-27" in doc)
    fomc = by["fomc"]
    check("a. FOMC decisions (from the saved calendar): every one is a Wednesday at 14:00 ET marked 'check' (Oct 28, Dec 9 2026, Jan 27, Mar 17 2027); no 'day 1' is made up",
          [e["date"] for e in fomc] == ["2026-10-28", "2026-12-09", "2027-01-27", "2027-03-17"] and all(dt.date.fromisoformat(e["date"]).weekday() == 2 and e["time"] == "14:00" and e["verify"] is True for e in fomc), fomc)
    check("a. the weekly rule: jobless claims every Thursday 08:30 ET; Thanksgiving week is skipped and replaced by a dated Wednesday event; nothing is dated twice on one day with the same kind",
          ev["weekly"][0]["dow"] == 3 and ev["weekly"][0]["time"] == "08:30" and "2026-11-26" in ev["weekly"][0]["skip"] and any(e["date"] == "2026-11-25" and e["kind"] == "claims" for e in evs) and len({(e["date"], e["kind"], e["time"], e["title"]) for e in evs}) == len(evs))
    lit = json.load(open(os.path.join(AK.ROOT, "live_model.json"), encoding="utf-8")).get("lit", {})
    core = AK.read(os.path.join(d, "pythiacore.js"))
    m = re.search(r"RULES = \{ entryFrom: '(\d\d:\d\d)', entryTo: '(\d\d:\d\d)', flat: '(\d\d:\d\d)'", core)
    lit_src = AK.read(os.path.join(AK.ROOT, "engine", "lit.py")) + json.dumps(lit)
    check("a. the bots' rules in the words (entries 02:00-15:30 ET, flat 15:55 ET) are the ones in CLAUDE.md and the LIT code", bool(m) and m.groups() == ("02:00", "15:30", "15:55") and ("15:55" in lit_src or "15, 55" in lit_src or "1555" in lit_src or "955" in lit_src), m and m.groups())
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: invented 'Example:' events only, a fixed today and clock, an example live briefing for that day", all(e["title"].startswith("Example") for e in fx["events"]["events"]) and fx["today"] == "2026-11-10" and fx["now"].startswith("2026-11-10") and fx["home"]["live"]["brief"]["day"] == "2026-11-10")
    sc = AK.read(os.path.join(d, "pythia.js")) + core
    check("a. read only: no order, key or write code in the page", not re.search(r"\b(placeOrder|submitOrder|api[_-]?key|Authorization|\.post\()", sc, re.I))
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the wiring rows for the lead are in docs/NEW_APPS_WIRING.md (a section named Pythia)", re.search(r"^# .*PYTHIA", wiring, re.M | re.I) is not None)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {}, ev = JSON.parse(process.argv[3]), n = C.normEvents(ev);
  const E = (ymd, hm) => C.etToEpoch(ymd, hm), Z = (y, mo, d, h, mi) => Date.UTC(y, mo - 1, d, h, mi || 0) / 1000;
  o.dates = [C.dowOf('2026-12-09'), C.addDays('2026-12-31', 1), C.daysBetween('2026-11-10', '2026-12-10'), C.dayWord('2026-12-09'), C.dayLong('2026-11-01'), C.thirdFriday(2026, 11), C.thirdFriday(2026, 12), C.thirdFriday(2027, 3), C.firstFriday(2026, 12), C.nthWeekday(2026, 11, 3, 4), C.nqExpiry(2026, 12), C.nqRoll(2026, 12), C.nqRoll(2027, 3)];
  o.dst = [C.etOffset(Z(2026, 10, 31, 12)), C.etOffset(Z(2026, 11, 1, 5, 59) + 59), C.etOffset(Z(2026, 11, 1, 6)), C.etOffset(Z(2027, 3, 14, 6, 59)), C.etOffset(Z(2027, 3, 14, 7)), C.etOffset(Z(2026, 7, 4, 12)), C.etOffset(Z(2026, 1, 15, 12))];
  o.epoch = [E('2026-11-01', '08:30') - Z(2026, 11, 1, 0), E('2026-10-31', '08:30') - Z(2026, 10, 31, 0), E('2026-12-10', '00:00') - Z(2026, 12, 10, 0), E('2026-12-09', '14:00') - Z(2026, 12, 9, 0), E('2026-11-01', '01:30') - Z(2026, 11, 1, 0), E('2026-11-01', '02:30') - Z(2026, 11, 1, 0), E('2027-03-14', '03:00') - Z(2027, 3, 14, 0), E('2026-07-04', '09:30') - Z(2026, 7, 4, 0)];
  const f = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  let bad = 0, count = 0;
  for (let t = Z(2025, 12, 1, 0); t < Z(2028, 1, 1, 0); t += 3600 * 3 + 997) { const p = Object.fromEntries(f.formatToParts(new Date(t * 1000)).map((x) => [x.type, x.value])), m = C.etParts(t); count++; if (`${p.year}-${p.month}-${p.day}` !== m.ymd || +p.hour !== m.h || +p.minute !== m.m) bad++; }
  o.intl = [bad, count > 5000];
  const roundtrip = []; for (const [d, hm] of [['2026-11-01', '08:30'], ['2026-03-08', '09:30'], ['2027-03-14', '14:00'], ['2026-12-25', '00:00'], ['2026-11-02', '23:59']]) { const p = C.etParts(E(d, hm)); roundtrip.push(p.ymd === d && p.hm === hm); }
  o.round = roundtrip;
  o.hm = [C.hmWord('14:00'), C.hmWord('00:00'), C.hmWord('12:30'), C.hmWord('08:05'), C.hmWord('25:00'), C.hmWord(null)];
  o.cd = [C.countdown(E('2026-10-31', '08:30'), E('2026-11-01', '08:30')).word, C.countdown(E('2026-11-01', '08:30'), E('2026-11-02', '08:30')).word, C.countdown(E('2026-10-30', '11:00'), E('2026-11-05', '08:30')).word,
    C.countdown(100, 100 + 35 * 60).word, C.countdown(100, 130).word, C.countdown(100 + 3 * 3600, 100).word, C.countdown(100, 100 + 3600 + 600).word, C.countdown(100, 100 + 86400).word, C.countdown(100, 100 + 2 * 86400 + 3600).word];
  o.norm = [n.events.length, n.weekly.length, n.undated.length, n.updated, n.events.every((e) => e.verify !== undefined), n.undated.every((u) => u.verify === true)];
  const cal = C.calendar(n, '2026-12-07');
  o.cal = [cal.length, cal.map((d) => d.risk).join(','), cal[2].events.map((e) => e.kind + '@' + e.time).join(','), cal[3].events.map((e) => e.kind + '@' + e.time).join(','), cal[11].events[0].kind, cal[1].events.length, cal[0].word, cal[13].ymd];
  const calN = C.calendar(n, '2026-11-23');
  o.thanks = [calN.slice(0, 5).map((d) => d.ymd + ':' + d.risk + ':' + d.events.map((e) => e.kind).join('+')).join(' | ')];
  o.risk = [C.dayRisk([]), C.dayRisk([{ impact: 'low' }]), C.dayRisk([{ impact: 'low' }, { impact: 'high' }]), C.dayRisk([{ impact: 'med' }, { impact: 'low', closed: true }]), C.dayRisk([{ impact: 'high', closed: true }, { impact: 'high' }]), C.RISKWORD.high, C.RISKCLS.closed];
  const up = C.nextUp(cal, E('2026-12-07', '10:00'), 5);
  o.up = [up.map((e) => e.kind), up[0].cd.word, up[1].cd.word, up[2].cd.word, up[3].cd.word, C.nextUp(cal, E('2026-12-30', '10:00'), 5).length];
  const w = (k, extra) => C.botWords({ kind: k, time: '08:30', title: 'x', closed: false, ...(extra || {}) });
  o.words = [w('fomc', { time: '14:00' }).includes('2:00 PM ET'), w('fomc', { time: '14:00' }).includes('LIT has no news pause'), w('fomc', { time: '14:00' }).includes('2:00 AM to 3:30 PM ET'), w('fomc', { time: '14:00' }).includes('flat at 3:55 PM ET'),
    w('fomc', { time: null }).includes('day 2'), w('holiday', { closed: true }).startsWith('The market is closed'), w('early', { closeEt: '13:15' }).includes('1:15 PM ET') && w('early', { closeEt: '13:15' }).includes('be flat before the close yourself'),
    w('roll', { title: 'Your roll step: switch the NinjaTrader chart to MNQ 03-27' }).includes('next contract'), w('roll', { title: 'NQ roll: orders switch' }).includes('300 points'), w('quad').includes('expires'), w('zzz').includes('LIT has no news pause'), C.CALM_WORDS.includes('Nothing special')];
  const home = { live: { brief: { day: '2026-12-07', news: [{ time: '08:30', title: 'Core PCE', kind: 'Inflation', blackout: '08:25-08:40' }, { title: '<b>x</b>y' }, { time: '99:99', title: 'No time' }, 5] } } };
  o.live = [C.liveNews(home, '2026-12-07').map((x) => [x.time, x.title, x.blackout]), C.liveNews(home, '2026-12-08'), C.liveNews(null, '2026-12-07'), C.liveNews({ live: { brief: { day: '2026-12-07' } } }, '2026-12-07')];
  const fx = JSON.parse(process.argv[4]);
  o.choose = [C.chooseData(ev, fx).src, C.chooseData(null, fx).src, C.chooseData({ events: [] }, fx).src, C.chooseData(null, null), C.chooseData(null, fx).today, C.chooseData({ events: [], weekly: [{ title: 'w', dow: 1 }] }, fx).src];
  const junk = C.normEvents({ events: [{ date: 'bad', title: 'x' }, { date: '2026-12-01', title: '<b>Hi</b>', impact: 'zzz', kind: 'nope', time: '99:00' }, { date: '2026-12-02' }, 7], weekly: [{ title: 'w', dow: 9 }, { title: 'ok', dow: 2, time: '10:00' }], undated: [{ title: 'u<i>' }, {}] });
  o.junk = [junk.events.length, junk.events[0].title, junk.events[0].impact, junk.events[0].kind, junk.events[0].time, junk.events[0].verify, junk.weekly.length, junk.undated.length, junk.undated[0].title, C.normEvents(null), C.normEvents({}), C.normEvents({ events: 'x' })];
  o.stale = [C.staleWord('2026-11-10', '2026-11-20').startsWith('The list was updated 2026-11-10'), C.staleWord('2026-09-01', '2026-11-20').includes("80 days ago"), C.staleWord('', '2026-11-20').includes('no update date'), C.lastDate(n)];
  const card = C.jarvisCard(cal, E('2026-12-07', '10:00'), false), cardD = C.jarvisCard(cal, E('2026-12-07', '10:00'), true), cardH = C.jarvisCard(C.calendar(n, '2026-12-09'), E('2026-12-09', '10:00'), false);
  o.card = [card.name, card.status.level, cardD.status.level, cardH.status.level, cardH.status.label, card.kpis.length, card.kpis[0].value, card.kpis[1].value, card.kpis[2].value, card.lines[1].includes('New York'), Number.isInteger(card.t), JSON.stringify(card).length < 8192, /[<>]/.test(JSON.stringify(card))];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    import shutil
    if not shutil.which("node"):
        check("b. node is not installed: maths skipped", True)
        return
    ev = AK.read(os.path.join(AK.WEB, APP, "events.json"))
    fx = AK.read(os.path.join(AK.WEB, APP, "fixture.json"))
    o = AK.node(APP, HARNESS, ev, fx)
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. dates: Wed Dec 9, year rollover, 30 days between, the day words, third Fridays (Nov 20, Dec 18, Mar 19 2027), first Friday of Dec = Dec 4, Thanksgiving Nov 26, the Dec expiry Dec 18 and the roll 8 days before = Thu Dec 10 (Mar 2027: Mar 11)",
          o["dates"] == [2, "2027-01-01", 30, "Wed Dec 9", "Sunday, November 1", "2026-11-20", "2026-12-18", "2027-03-19", "2026-12-04", "2026-11-26", "2026-12-18", "2026-12-10", "2027-03-11"], o["dates"])
    check("b. New York offset from the DST rule: -4 on Oct 31, -4 until 05:59:59 UTC on Nov 1 then -5 (the clocks go back at 02:00 EDT), -5 until 06:59 UTC on Mar 14 2027 then -4, -4 in July, -5 in January", o["dst"] == [-4, -4, -5, -5, -4, -4, -5], o["dst"])
    check("b. ET clock to an instant: 08:30 on Nov 1 is 13:30 UTC (EST), on Oct 31 it is 12:30 UTC (EDT); the roll at 00:00 on Dec 10 is 05:00 UTC; the FOMC at 14:00 on Dec 9 is 19:00 UTC; the repeated 01:30 on the fall-back night is the first (EDT) one; 02:30 is EST; 03:00 on Mar 14 2027 is EDT; July is EDT",
          o["epoch"] == [13 * 3600 + 1800, 12 * 3600 + 1800, 5 * 3600, 19 * 3600, 5 * 3600 + 1800, 7 * 3600 + 1800, 7 * 3600, 13 * 3600 + 1800], o["epoch"])
    check("b. the rule equals the real New York clock (Intl) at more than 5,000 instants from Dec 2025 to Dec 2027, every DST edge included: 0 mismatches; clock -> instant -> clock round-trips", o["intl"] == [0, True] and all(o["round"]), (o["intl"], o["round"]))
    check("b. clock words: 2:00 PM ET, 12:00 AM ET, 12:30 PM ET, 8:05 AM ET; a bad time gives nothing", o["hm"] == ["2:00 PM ET", "12:00 AM ET", "12:30 PM ET", "8:05 AM ET", "", ""], o["hm"])
    check("b. countdowns: Oct 31 8:30 to Nov 1 8:30 ET is '1 day 1 hour' (the clocks go back, 25 real hours); Nov 1 to Nov 2 is '1 day'; Oct 30 11:00 to Nov 5 8:30 is '5 days 22 hours' (DST night inside); 35 min, 'now', '3 hours ago', '1 hour 10 min', 1 day, 2 days 1 hour",
          o["cd"] == ["in 1 day 1 hour", "in 1 day", "in 5 days 22 hours", "in 35 min", "now", "3 hours ago", "in 1 hour 10 min", "in 1 day", "in 2 days 1 hour"], o["cd"])
    check("b. events.json is read whole: 41 dated events, 1 weekly rule, 4 undated, the update date; every undated release is 'verify'", o["norm"] == [41, 1, 4, "2026-11-10", True, True], o["norm"])
    check("b. the Dec 7 window: 14 days; Dec 9 red (decision 14:00 + your roll step 16:00), Dec 10 amber (the roll at 00:00, then claims 08:30), Dec 17 light (claims), Dec 18 amber (quad witching); the rest calm",
          o["cal"][0] == 14 and o["cal"][1] == "calm,calm,high,med,calm,calm,calm,calm,calm,calm,low,med,calm,calm" and o["cal"][2] == "fomc@14:00,roll@16:00" and o["cal"][3] == "roll@00:00,claims@08:30" and o["cal"][4] == "quad" and o["cal"][5] == 0 and o["cal"][6] == "Mon Dec 7" and o["cal"][7] == "2026-12-20", o["cal"])
    check("b. Thanksgiving week: Nov 25 claims move to Wednesday (the Thursday rule skips Nov 26), Nov 26 is a closed day, Nov 27 is the early close (amber)",
          o["thanks"] == ["2026-11-23:calm: | 2026-11-24:calm: | 2026-11-25:low:claims | 2026-11-26:closed:holiday | 2026-11-27:med:early"], o["thanks"])
    check("b. risk colour: calm < low < amber < red; a closed day outranks everything", o["risk"] == ["calm", "low", "high", "closed", "closed", "Red day", "info"], o["risk"])
    check("b. coming up from Dec 7 10:00 ET: the Fed decision, your roll step, the roll, then claims, in that order with ET countdowns; past the end of the list nothing is invented",
          o["up"][0][:5] == ["fomc", "roll", "roll", "claims", "claims"] and o["up"][1:5] == ["in 2 days 4 hours", "in 2 days 6 hours", "in 2 days 14 hours", "in 2 days 22 hours"] and o["up"][5] == 0, o["up"])
    check("b. what the bots do, in plain words: FOMC names 2:00 PM ET and 'LIT has no news pause', the real rules (entries 2:00 AM to 3:30 PM ET, flat at 3:55 PM ET), an early close says be flat before it yourself, the roll step and the roll differ, a closed day says nothing to do",
          all(o["words"]), o["words"])
    check("b. the live briefing: only when the brief is for today; a bad time is dropped, tags stripped, junk rows ignored; no brief -> null; a brief without news -> null",
          o["live"][0] == [["08:30", "Core PCE", "08:25-08:40"], ["", "x y", ""], ["", "No time", ""]] and o["live"][1] is None and o["live"][2] is None and o["live"][3] is None, o["live"])
    check("b. choosing the data: the bundled file wins, a missing or empty file falls back to the labelled demo (with its fixed today), a file with only a weekly rule still counts, nothing at all gives null", o["choose"] == ["file", "demo", "demo", None, "2026-11-10", "file"], o["choose"])
    check("b. junk is harmless: bad dates and titleless rows dropped, tags stripped, a bad impact -> low, a bad kind -> other, a bad time -> all-day, verify defaults to true; a bad weekday rule is dropped; null in -> null out",
          o["junk"] == [1, "Hi", "low", "other", None, True, 1, 1, "u", None, None, None], o["junk"])
    check("b. the list's age in words, and its last date", o["stale"] == [True, True, True, "2027-03-26"], o["stale"])
    check("b. the Jarvis card: Pythia, ok on a calm day, 'off' for the demo, bad on the FOMC day ('Red day'), 3 kpis (today, events, next), a New York line, an integer t, under 8 KB, no markup",
          o["card"] == ["Pythia", "ok", "off", "bad", "Red day", 3, "Calm", "6", o["card"][8], True, True, True, False] and bool(o["card"][8]), o["card"])


def home_json(day):
    return json.dumps({"live": {"brief": {"day": day, "news": [{"time": "08:30", "title": "Core PCE Price Index", "kind": "Inflation", "blackout": "08:25-08:40"}]}}})


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve({"/home.json": home_json("2026-12-07")})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-12-07T15:00:00Z")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#riskPill').textContent, today: document.querySelector('#todayWord').textContent, todayEv: document.querySelector('#todayEv').textContent,
              btns: document.querySelectorAll('#grid .dbtn').length, risks: [...document.querySelectorAll('#grid .dbtn')].map((b) => b.dataset.risk).join(','), now: document.querySelectorAll('#grid .dbtn.now').length, sel: document.querySelector('#grid .dbtn.sel b').textContent,
              range: document.querySelector('#range').textContent, live: !document.querySelector('#liveCard').hidden, liveText: document.querySelector('#liveBox').textContent, next: [...document.querySelectorAll('#nextList > li')].map((l) => l.textContent),
              ud: document.querySelectorAll('#undated > li').length, udText: document.querySelector('#undated').textContent, udShown: !document.querySelector('#undatedCard').hidden, notes: document.querySelector('#notes').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor })""")
            check("c. Monday Dec 7 (10:00 ET): no DEMO chip, 'Calm day', 'Monday, December 7 · 10:00 AM ET now', the bot's words for a day with nothing scheduled, 14 day buttons, today outlined and selected",
                  not d["demo"] and d["pill"] == "Calm day" and d["today"] == "Monday, December 7 · 10:00 AM ET now" and "Nothing special" in d["todayEv"] and d["btns"] == 14 and d["now"] == 1 and d["sel"] == "7", d)
            check("c. the colours of the fortnight: Dec 8 amber, Dec 9 red, Dec 10 amber, Dec 17 light, Dec 18 amber; the range line names both ends", d["risks"] == "calm,calm,high,med,calm,calm,calm,calm,calm,calm,low,med,calm,calm" and d["range"] == "Mon Dec 7 to Sun Dec 20", d)
            check("c. the live briefing card shows (home.json brief is for today): 8:30 AM ET, Core PCE, the quiet window 08:25-08:40", d["live"] and "8:30 AM ET" in d["liveText"] and "Core PCE" in d["liveText"], d["liveText"])
            check("c. coming up: the Fed decision first, with its ET countdown and 'check date'; the four releases with no known date (CPI and PPI after the saved ones, retail sales, the January jobs report) sit in 'Dates to confirm' with the official calendar named; the list's age is in words",
                  d["next"][0].startswith("FOMC decision 2:00 PM") and "in 2 days 4 hours" in d["next"][0] and "check date" in d["next"][0] and d["ud"] == 4 and d["udShown"] and d["udText"].count("Confirm at: bls.gov") == 3 and "census.gov" in d["udText"] and "was updated 2026-11-10" in d["notes"], d["next"])
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "pythia-dec7")
            p.locator("#grid .dbtn").nth(2).click()
            p.wait_for_timeout(200)
            e = p.evaluate("""() => ({ title: document.querySelector('#dayTitle').textContent, pill: document.querySelector('#dayPill').textContent, evs: document.querySelectorAll('#dayList > li').length, text: document.querySelector('#dayList').textContent,
              pills: [...document.querySelectorAll('#dayList .pill')].map((x) => x.textContent), pressed: document.querySelectorAll('#grid [aria-pressed=true]').length, status: document.querySelector('#status').textContent })""")
            check("c. tap Dec 9: 'Wednesday, December 9', 'Red day', two events (the Fed at 2:00 PM ET and your roll step at 4:00 PM ET), High and 'Check date' pills, the bot's words (no news pause, entries 2:00 AM to 3:30 PM ET, flat at 3:55 PM ET), the status line speaks it",
                  e["title"] == "Wednesday, December 9" and e["pill"] == "Red day" and e["evs"] == 2 and "2:00 PM ET" in e["text"] and "4:00 PM ET" in e["text"] and "High" in e["pills"] and "Check date" in e["pills"] and "LIT has no news pause" in e["text"]
                  and "flat at 3:55 PM ET" in e["text"] and "MNQ 03-27" in e["text"] and e["pressed"] == 1 and "Red day" in e["status"], e)
            p.locator("#grid .dbtn").nth(3).click()
            p.wait_for_timeout(150)
            r = p.evaluate("() => [document.querySelector('#dayPill').textContent, document.querySelector('#dayList').textContent.includes('March contract'), document.querySelector('#dayList').textContent.includes('12:00 AM ET')]")
            check("c. tap Dec 10: amber, the roll at 12:00 AM ET with the March contract words", r == ["Amber day", True, True], r)
            p.locator("#nextW").click()
            p.wait_for_timeout(250)
            w = p.evaluate("() => ({ range: document.querySelector('#range').textContent, first: document.querySelector('#grid .dbtn b').textContent, sel: document.querySelector('#grid .dbtn.sel b').textContent, today: document.querySelectorAll('#grid .dbtn.now').length, back: document.querySelector('#todayBtn').disabled, quad: [...document.querySelectorAll('#grid .dbtn')].filter((b) => b.dataset.risk === 'med').length })")
            check("c. the next-week button moves the fortnight to Dec 14 - 27 (today is no longer in it, the Back-to-today button is on, Dec 18 is amber and Dec 24 the early close too)", w["range"] == "Mon Dec 14 to Sun Dec 27" and w["first"] == "14" and w["today"] == 0 and w["back"] is False and w["quad"] == 2, w)
            p.locator("#todayBtn").click()
            p.wait_for_timeout(250)
            w2 = p.evaluate("() => [document.querySelector('#range').textContent, document.querySelector('#todayBtn').disabled, document.querySelectorAll('#grid .dbtn.now').length]")
            check("c. Back to today restores Dec 7 - 20", w2 == ["Mon Dec 7 to Sun Dec 20", True, 1], w2)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (the day buttons, the week buttons)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            wh = p.evaluate("() => { const w = window.PYTHIA.wheel; return w ? { n: w.count, q: w.quality(), lite: w.lite, shown: !document.querySelector('#stage').hidden && document.querySelector('#flat').hidden, size: [document.querySelector('#stage').clientWidth, document.querySelector('#stage').clientHeight] } : null }")
            if wh is None:
                check("c. 3D: no WebGL here, so the flat wheel is shown (the page still works)", p.evaluate("() => window.PYTHIA.flat === true && !document.querySelector('#flat').hidden"))
            else:
                check("c. 3D: the marble wheel is up with 14 pillars, the flat twin is hidden, the canvas has a real size", wh["n"] == 14 and wh["shown"] and wh["size"][0] > 200 and wh["size"][1] > 100, wh)
                pos = p.evaluate("() => window.PYTHIA.wheel.screenOf(2)")
                if pos and pos["front"]:
                    p.mouse.click(pos["x"], pos["y"] - 8)
                    p.wait_for_timeout(300)
                    sel = p.evaluate("() => [window.PYTHIA.S.sel, window.PYTHIA.wheel.selected]")
                    check("c. tap a pillar in 3D: that day is selected in the list and on the wheel (3D picking works)", sel[0] == sel[1] and sel[0] >= 0, (pos, sel))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-10-30T15:00:00Z&q=off")
            q = p.evaluate("""() => ({ flat: window.PYTHIA.flat, wheel: !!window.PYTHIA.wheel, svg: !document.querySelector('#flat').hidden, canvas: document.querySelector('#stage').hidden, bars: document.querySelectorAll('#flat rect').length,
              next: [...document.querySelectorAll('#nextList > li')].map((l) => l.textContent), range: document.querySelector('#range').textContent, risks: [...document.querySelectorAll('#grid .dbtn')].map((b) => b.dataset.risk + ':' + b.querySelector('b').textContent).join(' '), live: document.querySelector('#liveCard').hidden })""")
            check("c. ?q=off (3D Off): the flat marble wheel is drawn instead (14 pillars), the page works the same, no error", q["flat"] and not q["wheel"] and q["svg"] and q["canvas"] and q["bars"] == 14 and not errs, (q, errs[:3]))
            check("c. the Oct 30 window crosses the Nov 1 clock change: it runs Oct 30 to Nov 12; the Thursday Nov 5 claims are '5 days 22 hours' away (not 5 days 21 or 23); Nov 11 (Veterans Day) is light; the brief for another day is not shown",
                  q["range"] == "Fri Oct 30 to Thu Nov 12" and any("Jobless claims" in x and "in 5 days 22 hours" in x for x in q["next"]) and "low:11" in q["risks"] and "low:5" in q["risks"] and "low:12" in q["risks"] and q["live"] is True, q)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?at=2026-12-07T15:00:00Z&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
            srv2, origin2 = AK.serve({"/pythia/events.json": None, "/home.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?q=off")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, today: document.querySelector('#todayWord').textContent, pill: document.querySelector('#riskPill').textContent, live: !document.querySelector('#liveCard').hidden, liveText: document.querySelector('#liveBox').textContent,
              first: document.querySelector('#todayEv').textContent })""")
            check("c. events.json missing: the labelled DEMO (invented 'Example' events, fixed clock Nov 10 09:35 ET), the example live briefing, never blank", r["demo"] and r["today"] == "Tuesday, November 10 · 9:35 AM ET now" and r["pill"] == "Red day" and r["live"] and "Example: core inflation" in r["liveText"] and "Example: inflation report" in r["first"] and not errs, (r, errs[:2]))
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/pythia/events.json": "{broken", "/home.json": home_json("2026-12-08")})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?at=2026-12-07T15:00:00Z&q=off")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#liveCard').hidden]")
            check("c. a broken events.json falls back to the labelled demo, never blank; a live briefing for another day is not shown as today's", r[0] is True and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
