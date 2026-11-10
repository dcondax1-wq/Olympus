"""PHEME, the OLYMPUS word on the street (tools/pheme_build.py + tools/web_public/pheme/, AGORA look, 2026-11-10): today's and the next two weeks' scheduled releases with a plain 'why it matters for NQ' and what the bots do,
and a history card per kind of release (the last 8 days: how far NQ travelled, in points and in $ for one MNQ micro, n shown). HISTORY ONLY: no forecast. Read only.

  a. static: the builder's selftest and --check, stats.json checked against the raw 5m file for real days, the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the new_apps.json row, the wiring rows
  b. the maths in node (phemecore.js): money and dates, the history sentences with their n, honesty for thin and empty kinds, the schedule, coverage, junk input, no markup from data
  c. Chromium 390 x 844 (and 375 x 667): the DEMO case, kind chips, the 3D rack (tap a column -> its row; the flat twin with ?q=off), the real stats.json on a CPI day and an FOMC day, old numbers warned, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_pheme_page            (--static: parts a and b only)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "pheme", "Pheme"
check = AK.check
BUILD = os.path.join(AK.ROOT, "tools", "pheme_build.py")


def raw_range(day):
    """the 08:00-16:00 ET high-low of one day, straight from data/NQ_5m.csv (independent of the builder's code path)."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    hi, lo, n = -1e18, 1e18, 0
    with open(os.path.join(AK.ROOT, "data", "NQ_5m.csv"), encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            t, _o, h, l, *_ = line.split(",")
            d = dt.datetime.fromtimestamp(int(t), et)
            if d.strftime("%Y-%m-%d") == day and 480 <= d.hour * 60 + d.minute < 960:
                hi, lo, n = max(hi, float(h)), min(lo, float(l)), n + 1
    return round(hi - lo, 2), n


def test_static():
    r = subprocess.run([sys.executable, "-I", BUILD, "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the builder's own selftest passes (tools/pheme_build.py --selftest)", r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
    r2 = subprocess.run([sys.executable, "-I", BUILD, "--check"], capture_output=True, text=True, timeout=300)
    check("a. stats.json is EXACTLY what `python tools/pheme_build.py` writes from data/news/events.csv and data/NQ_5m.csv (rebuild it after either file changes)", r2.returncode == 0, r2.stdout[-300:] + r2.stderr[-200:])
    AK.static_kit(APP, NAME, reads=("./stats.json",))
    d = os.path.join(AK.WEB, APP)
    st = json.load(open(os.path.join(d, "stats.json"), encoding="utf-8"))
    row = st["kinds"]["cpi"]["rows"][0]
    rr, n = raw_range(row["date"])
    check(f"a. an independent check against the raw 5m file: the newest CPI row ({row['date']}) has a day range of {row['day_range']} points, and reading data/NQ_5m.csv again gives {rr} from {n} bars", abs(rr - row["day_range"]) < 0.01 and n >= 90, (row, rr, n))
    row2 = st["kinds"]["fomc"]["rows"][0]
    rr2, n2 = raw_range(row2["date"])
    check(f"a. same for the newest FOMC row ({row2['date']}): {row2['day_range']} vs the raw file {rr2}", abs(rr2 - row2["day_range"]) < 0.01 and n2 >= 90, (row2, rr2))
    check("a. every figure has its n: each kind lists n_listed, n_with_data, and last / all summaries with n; the last rows are at most 8; dollars are points x $2; nothing is invented for a kind with no data",
          all(k["n_with_data"] >= 8 and len(k["rows"]) == 8 and k["last"]["day"]["n"] == 8 and all(abs(x["day_usd"] - round(x["day_range"] * 2)) <= 1 for x in k["rows"]) for k in st["kinds"].values()) and st["usd_per_point"] == 2.0 and "not a forecast" in st["label"], {k: v["n_with_data"] for k, v in st["kinds"].items()})
    with open(os.path.join(AK.ROOT, "data", "news", "events.csv"), encoding="utf-8", newline="") as fh:
        cal = [x for x in csv.DictReader(fh)]
    ev = st["events"]
    check("a. the schedule is the saved calendar (press conferences dropped, decisions kept): every row of events.csv from 60 days before the build date on is in stats.json, with its source",
          len(ev) >= 40 and all(e["source"] for e in ev) and not any("press conference" in e["title"].lower() for e in ev) and {e["date"] for e in ev if e["kind"] == "fomc"} >= {"2026-12-09", "2027-01-27"} and any(e["kind"] == "cpi" and e["date"] == "2026-11-10" for e in ev)
          and len([c for c in cal if c["date"] >= (dt.date.fromisoformat(st["built"]) - dt.timedelta(days=60)).isoformat() and "press conference" not in c["event"].lower()]) <= len(ev), (len(ev), st["built"]))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. the page order: today, history (with the rack), the next two weeks", html.index('id="todayEv"') < html.index('id="histCard"') < html.index('id="stage"') < html.index('id="weekEv"'))
    check("a. the 3D rack is its own module tag (a failed load can never stop the page) and the flat twin exists", 'src="phemerack.js' in html and "PHEME_RACK_FAIL" in html and 'id="flat"' in html)
    rack = AK.read(os.path.join(d, "phemerack.js"))
    check("a. the rack is light: the render core + materials, 8 columns, bloom <= .25, a dpr cap <= 1.5, no data, no network, idle rules (hidden, frameGap, reduced motion)",
          "olympus/render.js" in rack and "const N = 8" in rack and re.search(r"strength:\s*0\.(?:[0-2]\d?)\b", rack) and "maxDpr: 1.5" in rack and "O.hidden()" in rack and "frameGap" in rack and "RM" in rack and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket", rack))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: invented 'Example' events and numbers, a fixed today (2026-11-10), 4 kinds with 8 rows each", all(e["title"].startswith("Example") for e in fx["events"]) and fx["today"] == "2026-11-10" and all(len(k["rows"]) == 8 for k in fx["kinds"].values()) and set(fx["kinds"]) == {"cpi", "nfp", "ppi", "fomc"})
    sc = AK.read(os.path.join(d, "pheme.js")) + AK.read(os.path.join(d, "phemecore.js"))
    check("a. history only, read only: no forecast / predict / signal / order / key words in the page code", not re.search(r"\b(forecast|predict\w*|trade signal|placeOrder|submitOrder|api[_-]?key|Authorization|\.post\()", re.sub(r"`[^`]*`|'[^'\n]*'|\"[^\"\n]*\"", "", re.sub(r"//[^\n]*", "", sc)), re.I))
    check("a. the honest label is on the page and in the data: 'History, not a forecast' and 'A range is not a profit or a loss'", "History, not a forecast" in AK.read(os.path.join(d, "phemecore.js")) and "not a profit or a loss" in AK.read(os.path.join(d, "phemecore.js")) and "not a profit or a loss" in html)
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))["apps"]
    row = next((a for a in na if a["id"] == "pheme"), None)
    scenes = set(re.findall(r"^  SC\.(\w+) =", AK.read(os.path.join(AK.WEB, "olympus", "intro-app.js")), re.M))
    check("a. tools/new_apps.json has the Pheme row: group trading, a hex accent, a glyph, a description under 80 characters, an ambient bed, an EXISTING intro scene, a transition",
          bool(row) and row["group"] == "trading" and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"] and len(row["description"]) < 80 and row["ambient"] and row["flavour"][0] in scenes and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["transition"]["ms"], row)
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the wiring rows for the lead are in docs/NEW_APPS_WIRING.md (a section named Pheme)", re.search(r"^# .*PHEME", wiring, re.M | re.I) is not None)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {}, fx = JSON.parse(process.argv[3]), real = JSON.parse(process.argv[4]), v = C.chooseData(null, fx).v, rv = C.normStats(real);
  o.words = [C.usd(758), C.usd(-12.4), C.usd(null), C.pts(296.25), C.pts(1234.56), C.pts(null), C.perMicro(296.25), C.perMicro(null), C.hmWord('08:30'), C.hmWord('14:00'), C.hmWord('00:05'), C.hmWord('x')];
  o.dates = [C.dowOf('2026-11-10'), C.addDays('2026-12-31', 1), C.daysBetween('2026-11-09', '2026-11-10'), C.dayWord('2026-11-10'), C.dayLong('2026-12-09'), C.etDay(1793173380), C.etDay(Date.UTC(2026, 10, 1, 4, 30) / 1000), C.etDay(Date.UTC(2026, 10, 1, 5, 30) / 1000), C.etDay(null)];
  o.choose = [C.chooseData(real, fx).src, C.chooseData(null, fx).src, C.chooseData({ kinds: {}, baseline: {} }, fx).src, C.chooseData(null, null), C.chooseData(fx, null).src, C.chooseData(fx, null).v.demo];
  o.view = [Object.keys(v.kinds), v.events.length, v.base.days, v.base.day.avg, Object.keys(v.base.win), v.built, v.lastBar, v.calLast, v.demo, rv.demo, Object.keys(rv.kinds), rv.events.length > 40, rv.base.days];
  const h = C.history(v, 'cpi');
  o.hist = [h.lines.length, h.lines[0], h.lines[1], h.lines[2], h.tiles.map((t) => t.v + '|' + t.n), h.thin, h.ratio, h.ratioW, h.k.rows.length];
  const hr = C.history(rv, 'nfp');
  o.real = [hr.lines[0], hr.lines[2], hr.lines[3], hr.thin, hr.tiles[0].v, C.history(rv, 'fomc').k.last.day.n];
  const few = C.normStats({ ...real, kinds: { cpi: { ...real.kinds.cpi, rows: real.kinds.cpi.rows.slice(0, 3), last: { day: { n: 3, avg: 100, median: 90 }, window: { n: 3, avg: 50, median: 40 } }, all: { day: { n: 3, avg: 100, median: 90 }, window: { n: 3, avg: 50, median: 40 } } } } });
  const hf = C.history(few, 'cpi');
  o.few = [hf.thin, hf.lines[hf.lines.length - 1], hf.lines[0].includes('(n=3)')];
  const none = C.normStats({ ...real, kinds: { cpi: { ...real.kinds.cpi, rows: [], last: { day: { n: 0 }, window: { n: 0 } }, all: { day: { n: 0 }, window: { n: 0 } } } } });
  const hn = C.history(none, 'cpi');
  o.none = [hn.lines.length, hn.lines[0], hn.tiles.length, hn.thin, C.history(none, 'zzz'), C.rackBars(none, 'cpi').values.length];
  o.rack = [C.rackBars(v, 'cpi').values, C.rackBars(v, 'cpi').typical, C.rackBars(v, 'fomc').values.length, C.rackBars(v, 'zzz').values.length, C.rowWords(v.kinds.cpi.rows[0])];
  o.head = [C.headline(v, '2026-11-10'), C.headline(v, '2026-11-11'), C.headline(v, '2026-12-30'), C.headline(rv, '2026-11-10'), C.headline(rv, '2026-12-09')];
  o.sched = [C.schedule(v, '2026-11-11', 14, true).map((x) => x.word + ':' + x.events.length), C.schedule(v, '2026-11-11', 3, false).length, C.eventsOn(v, '2026-11-10').map((e) => e.kind)];
  o.cov = [C.coverage(v, '2026-11-10').word, C.coverage(v, '2026-11-10').stale, C.coverage(v, '2026-12-20').stale, C.coverage(rv, '2026-11-10').age, C.coverage({ built: '', calLast: '', lastBar: '' }, '2026-11-10').word.includes('unknown date')];
  o.words2 = [C.WHY.cpi.includes('interest rates'), C.WHY.fomc.includes('2:00 PM ET'), C.botWords({ kind: 'cpi' }).includes('LIT has no news pause'), C.botWords({ kind: 'cpi' }).includes('2:00 AM to 3:30 PM ET'), C.botWords({ kind: 'cpi' }).includes('flat at 3:55 PM ET'), C.botWords({ kind: 'cpi' }).includes('15 minutes before to 30 minutes after'), C.botWords({ kind: 'fomc' }).includes('1:00 PM ET'), Object.keys(C.WHY).every((k) => C.KINDS.includes(k)), C.LABEL.includes('not a forecast')];
  const evil = C.normStats({ ...real, built: '2026-11-10', events: [{ date: '2026-11-10', time: '99:99', title: '<b>CPI</b> now', kind: 'zzz', impact: 'huge' }, { date: 'bad', title: 'x' }, { date: '2026-11-11' }, 7], kinds: { cpi: { ...real.kinds.cpi, label: '<i>CPI</i>', rows: [{ date: '2026-09-11', time: '08:30', day_range: 'zz', window_range: 5 }, ...real.kinds.cpi.rows.slice(0, 1)] } } });
  o.evil = [evil.events.length, evil.events[0].title, evil.events[0].kind, evil.events[0].impact, evil.events[0].time, evil.kinds.cpi.label, evil.kinds.cpi.rows.length, Object.keys(evil.kinds), C.normStats(null), C.normStats({}), C.normStats({ kinds: { cpi: 5 }, baseline: {} })];
  const card = C.jarvisCard(v, '2026-11-10'), cardR = C.jarvisCard(rv, '2026-11-10'), cardS = C.jarvisCard(rv, '2027-01-20'), cardQ = C.jarvisCard(rv, '2026-11-12');
  o.card = [card.name, card.status.level, cardR.status.level, cardR.status.label, cardS.status.level, cardS.status.label, cardQ.status.label, card.kpis.length, card.kpis[0].value, card.kpis[1].value, card.lines[1], Number.isInteger(card.t), JSON.stringify(card).length < 8192, /[<>]/.test(JSON.stringify(card))];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    import shutil
    if not shutil.which("node"):
        check("b. node is not installed: maths skipped", True)
        return
    fx = AK.read(os.path.join(AK.WEB, APP, "fixture.json"))
    real = AK.read(os.path.join(AK.WEB, APP, "stats.json"))
    o = AK.node(APP, HARNESS, fx, real)
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: whole dollars, 296.25 pts shown as 296.3, thousands commas, n/a for nothing, one micro = $2 a point (296.25 -> $593), clock words with ET", o["words"] == ["$758", "-$12", "$0", "296.3", "1,234.6", "n/a", 593, None, "8:30 AM ET", "2:00 PM ET", "12:05 AM ET", ""], o["words"])
    check("b. dates: Tuesday, year rollover, one day between, the words, and the New York day of an epoch (the Nov 1 night: 04:30 UTC is still Oct 31 in New York? no: 00:30 EDT Nov 1; 05:30 UTC is 00:30 EST Nov 1)", o["dates"][:6] == [1, "2027-01-01", 1, "Tue Nov 10", "Wednesday, December 9", "2026-10-28"] and o["dates"][6] == "2026-11-01" and o["dates"][7] == "2026-11-01" and o["dates"][8] is None, o["dates"])
    check("b. choosing the data: the built file wins, a missing or empty one falls back to the labelled demo, a stats-shaped fixture still works, nothing at all gives null", o["choose"] == ["file", "demo", "demo", None, "demo", True], o["choose"])
    check("b. the views: demo has 4 kinds, 6 example events, a 400-day yardstick and the two release windows; the real file has 4 kinds and 40+ scheduled events from 1,100+ ordinary days",
          o["view"][:5] == [["cpi", "nfp", "ppi", "fomc"], 6, 400, 290, ["08:30", "14:00"]] and o["view"][5:9] == ["2026-11-09", "2026-11-06", "2026-11-20", True] and o["view"][9] is False and o["view"][10] == ["cpi", "nfp", "ppi", "fomc"] and o["view"][11] is True and o["view"][12] > 1000, o["view"])
    check("b. the CPI history in plain sentences with n: 8 days, 378.8 points a day on average (median 365) = $758 for one micro, 228.8 in the first 30 minutes = $458, an ordinary day 290 points (n=400); the tiles repeat them; the ratio is 1.31 for the day and 3.81 for the 30 minutes",
          o["hist"][0] == 3 and o["hist"][1] == "Last 8 CPI days (n=8): between 8 AM and 4 PM ET the price travelled 378.8 points on average (median 365), about $758 for one MNQ micro." and "228.8 points on average (n=8), about $458" in o["hist"][2]
          and "n=400 days" in o["hist"][3] and o["hist"][4][0] == "378.8 pts|$758 per micro" and o["hist"][4][2] == "290 pts|$580 per micro · n=400" and o["hist"][5] is False and o["hist"][6] == 1.31 and o["hist"][7] == 3.81 and o["hist"][8] == 8, o["hist"])
    check("b. the real file's jobs-report card: n=8, a longer line for all 34 days, 8 rows; FOMC last 8", "Last 8 Jobs days (n=8)" in o["real"][0] and "n=1103 days" in o["real"][1] and "all 34 Jobs days" in o["real"][2] and o["real"][3] is False and o["real"][4].endswith(" pts") and o["real"][5] == 8, o["real"])
    check("b. thin history says so: 3 days -> 'Only 3 days: too few to say much.', n=3 in the first sentence; a kind with no data shows ONE sentence naming n and no numbers or tiles; an unknown kind gives null", o["few"] == [True, "Only 3 days: too few to say much.", True] and o["none"][0] == 1 and "No past CPI day with price data" in o["none"][1] and o["none"][2] == 0 and o["none"][3] is True and o["none"][4] is None and o["none"][5] == 0, (o["few"], o["none"]))
    check("b. the rack's bars: 8 values oldest first (450 ... 330) against an ordinary day of 290; FOMC has 8; an unknown kind has none; a row in words with its dollars", o["rack"][0] == [450, 380, 300, 520, 350, 410, 290, 330] and o["rack"][1] == 290 and o["rack"][2] == 8 and o["rack"][3] == 0 and o["rack"][4] == "Fri Sep 11 2026: day 330 pts ($660), first 30 minutes 240 pts ($480)", o["rack"])
    check("b. headlines: two releases (one high: CPI) on Nov 10; 'No scheduled release today. Next: ...' on a quiet day; the end of the calendar says so; real data on the CPI day and the FOMC day",
          o["head"][0] == "2 scheduled releases today, 1 of them high impact (CPI). History below, no forecast." and o["head"][1] == "No scheduled release today. Next: Example: jobless claims, Thu Nov 12 8:30 AM ET." and o["head"][2] == "No scheduled release today. Nothing later in the saved calendar."
          and o["head"][3].startswith("1 scheduled release today, 1 of them high impact (CPI)") and o["head"][4].startswith("1 scheduled release today, 1 of them high impact (FOMC)"), o["head"])
    check("b. the schedule lists only busy days (4 in the demo fortnight) or every day when asked; events on a day by kind", o["sched"][0] == ["Thu Nov 12:1", "Fri Nov 13:1", "Wed Nov 18:1", "Fri Nov 20:1"] and o["sched"][1] == 3 and o["sched"][2] == ["cpi", "ism"], o["sched"])
    check("b. coverage in words: when it was built, where the calendar and the price history end; a build more than 21 days old is stale; an unknown date is said, not guessed",
          o["cov"][0] == "Built 2026-11-09 (1 day ago). The saved calendar runs to Fri Nov 20 2026; the price history in the numbers ends Fri Nov 6 2026." and o["cov"][1] is False and o["cov"][2] is True and o["cov"][3] == 0 and o["cov"][4] is True, o["cov"])
    check("b. the plain words: why a release matters (rates), the FOMC times, and the bots' real rules (LIT has no news pause; entries 2:00 AM to 3:30 PM ET; flat at 3:55 PM ET; the shadow engine pauses 15 min before to 30 after; FOMC afternoons stop at 1:00 PM ET); the label says not a forecast", all(o["words2"]), o["words2"])
    check("b. no markup survives from data: tags stripped, a bad time dropped, an unknown kind -> other, an unknown impact -> low, bad rows dropped, a row with a non-number is dropped; null / junk -> null",
          o["evil"][:4] == [1, "CPI now", "other", "low"] and o["evil"][4] == "" and o["evil"][5] == "CPI" and o["evil"][6] == 1 and o["evil"][7] == ["cpi"] and o["evil"][8:] == [None, None, None], o["evil"])
    check("b. the Jarvis card: Pheme, 'off' for the demo, warn on a high-impact day (2 releases), warn when the build is old, ok on a quiet day with 'Quiet today' / '1 release today', 3 kpis, 'History only', an integer t, under 8 KB, no markup",
          o["card"][:2] == ["Pheme", "off"] and o["card"][2] == "warn" and o["card"][3] == "1 release today" and o["card"][4] == "warn" and o["card"][5] == "Old numbers" and o["card"][7] == 3 and o["card"][8] == "2" and o["card"][9] == "1" and o["card"][10] == "History only, never a forecast." and o["card"][11] and o["card"][12] and not o["card"][13], o["card"])


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#head').textContent, today: document.querySelector('#todayWord').textContent, todayEv: document.querySelectorAll('#todayEv > li').length,
              chips: [...document.querySelectorAll('#kinds button')].map((b) => b.textContent), on: document.querySelector('#kinds [aria-pressed=true]').textContent, title: document.querySelector('#hTitle').textContent, pill: document.querySelector('#hPill').textContent,
              tiles: document.querySelector('#hTiles').textContent, lines: document.querySelector('#hLines').textContent, rows: document.querySelectorAll('#hRows tr').length, week: document.querySelectorAll('#weekEv > li').length,
              cov: document.querySelector('#cov').textContent, note: document.querySelector('#hNote').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor })""")
            check("c. DEMO: the chip, 'Example numbers: 2 scheduled releases today, 1 of them high impact (CPI)', the four kind chips, CPI open with n=8, the tiles in points and $ per micro, 8 rows, the next two weeks has 4 busy days",
                  d["demo"] and d["head"].startswith("Example numbers: 2 scheduled releases today") and d["chips"] == ["CPI", "Jobs", "PPI", "FOMC"] and d["on"] == "CPI" and d["pill"] == "n=8" and "378.8 pts" in d["tiles"] and "$758 per micro" in d["tiles"] and d["rows"] == 8 and d["week"] == 4 and d["todayEv"] == 2, d)
            check("c. the history sentences carry n and dollars; the note says history, not a forecast, a range is not a profit or a loss, $2 a point; the coverage line says when it was built",
                  "Last 8 CPI days (n=8)" in d["lines"] and "about $758 for one MNQ micro" in d["lines"] and "History, not a forecast" in d["note"] and "not a profit or a loss" in d["note"] and "$2 per point" in d["note"] and d["cov"].startswith("Built 2026-11-09"), d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "pheme-demo")
            e = p.evaluate("""() => { const li = document.querySelector('#todayEv > li'); const det = li.querySelector('details'); det.open = true; return { title: li.querySelector('b').textContent, why: det.textContent, pills: [...li.querySelectorAll('.pill')].map((x) => x.textContent) } }""")
            check("c. a release shows its time (ET), an impact pill, and under 'Why it matters for NQ, and what the bots do' the plain reason and the bots' rules (no news pause, entries 2:00 AM to 3:30 PM ET, flat 3:55 PM ET)",
                  e["title"].startswith("8:30 AM ET · Example") and "High" in e["pills"] and "interest rates" in e["why"] and "LIT has no news pause" in e["why"] and "flat at 3:55 PM ET" in e["why"], e)
            p.locator("#kinds button", has_text="FOMC").click()
            p.wait_for_timeout(200)
            f = p.evaluate("() => [document.querySelector('#hTitle').textContent, document.querySelector('#kinds [aria-pressed=true]').textContent, document.querySelectorAll('#hRows tr').length, document.querySelector('#hLines').textContent.includes('2:00 PM') || document.querySelector('#hLines').textContent.includes('14:00') || document.querySelector('#hLines').textContent.includes('FOMC'), document.querySelector('#status').textContent]")
            check("c. the FOMC chip switches the card (title, 8 rows, FOMC sentences) and speaks it", "FOMC decision" in f[0] and f[1] == "FOMC" and f[2] == 8 and f[3] and "FOMC" in f[4], f)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, the 'see the last 8' buttons, the summaries)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            rk = p.evaluate("() => { const r = window.PHEME.rack; return r ? { n: r.count(), h: r.heights(), line: r.line(), shown: !document.querySelector('#stage').hidden && document.querySelector('#flat').hidden, size: [document.querySelector('#stage').clientWidth, document.querySelector('#stage').clientHeight] } : null }")
            if rk is None:
                check("c. 3D: no WebGL here, so the flat rack is shown (the page still works)", p.evaluate("() => window.PHEME.flat === true && !document.querySelector('#flat').hidden"))
            else:
                p.locator("#kinds button", has_text="CPI").click()
                p.wait_for_timeout(400)
                rk = p.evaluate("() => { const r = window.PHEME.rack; return { n: r.count(), h: r.heights(), line: r.line(), shown: !document.querySelector('#stage').hidden && document.querySelector('#flat').hidden, size: [document.querySelector('#stage').clientWidth, document.querySelector('#stage').clientHeight] } }")
                top = max(rk["h"] + [rk["line"]])
                check("c. 3D: the marble rack is up with 8 columns whose heights follow the 8 day ranges (the tallest, 520 points, fills the rack; the gold line sits at an ordinary day, 290 / 520), the flat twin is hidden, the canvas has a real size",
                      rk["n"] == 8 and abs(max(rk["h"]) - 2.3) < 0.01 and abs(rk["line"] - 290 / 520 * 2.3) < 0.01 and rk["shown"] and rk["size"][0] > 200 and rk["size"][1] > 100 and top <= 2.31, rk)
                pos = p.evaluate("() => window.PHEME.rack.screenOf(3)")
                if pos and pos["front"]:
                    p.mouse.click(pos["x"], pos["y"])
                    p.wait_for_timeout(300)
                    sel = p.evaluate("() => [window.PHEME.S.row, window.PHEME.rack.selected, document.querySelectorAll('#hRows tr.sel').length]")
                    check("c. tap a column in 3D: that day's row is selected in the table (column 3 of 8 = the 5th newest) and on the rack", sel == [4, 3, 1], (pos, sel))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=off")
            q = p.evaluate("() => ({ flat: window.PHEME.flat, rack: !!window.PHEME.rack, svg: !document.querySelector('#flat').hidden, canvas: document.querySelector('#stage').hidden, bars: document.querySelectorAll('#flat rect').length })")
            check("c. ?q=off (3D Off): the flat marble rack is drawn instead (8 columns + the base), the page works the same, no error", q["flat"] and not q["rack"] and q["svg"] and q["canvas"] and q["bars"] == 9 and not errs, (q, errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-11-10T14:35:00Z&q=off")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#head').textContent, on: document.querySelector('#kinds [aria-pressed=true]').textContent, lines: document.querySelector('#hLines').textContent, rows: document.querySelectorAll('#hRows tr').length, cov: document.querySelector('#cov').textContent, today: document.querySelector('#todayWord').textContent })")
            check("c. the real stats.json on CPI day (Nov 10, New York): no DEMO chip, '1 scheduled release today, 1 of them high impact (CPI)', the CPI card is open with real numbers (n=8, 35 CPI days in the history), built 2026-11-10",
                  not r["demo"] and r["head"].startswith("1 scheduled release today, 1 of them high impact (CPI)") and r["on"] == "CPI" and "Last 8 CPI days (n=8)" in r["lines"] and "n=1103 days" in r["lines"] and r["rows"] == 8 and r["cov"].startswith("Built 2026-11-10") and r["today"] == "Tuesday, November 10 (New York)", r)
            check("c. the real run reads only the site's own stats.json and no console error", any("pheme/stats.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-12-09T15:00:00Z&q=off")
            r = p.evaluate("() => [document.querySelector('#head').textContent, document.querySelector('#kinds [aria-pressed=true]').textContent, document.querySelector('#hLines').textContent.slice(0, 40), document.querySelector('#cov').className]")
            check("c. FOMC day (Dec 9, 10:00 ET): '1 scheduled release today, 1 of them high impact (FOMC)', the FOMC card opens by itself", r[0].startswith("1 scheduled release today, 1 of them high impact (FOMC)") and r[1] == "FOMC" and r[2].startswith("Last 8 FOMC days (n=8)"), r)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2027-01-20T15:00:00Z&q=off")
            r = p.evaluate("() => [document.querySelector('#cov').textContent, document.querySelector('#cov').className]")
            check("c. a build more than three weeks old is warned in words ('newer releases may be missing')", "newer releases may be missing" in r[0] and "warnnote" in r[1], r)
            ctx.close()
            srv2, origin2 = AK.serve({"/pheme/stats.json": "{broken"})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?q=off")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#head').textContent]")
            check("c. a broken stats.json falls back to the labelled demo, never blank", r[0] is True and r[1].startswith("Example numbers") and not errs, (r, errs[:2]))
            ctx.close()
            srv2.shutdown()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
