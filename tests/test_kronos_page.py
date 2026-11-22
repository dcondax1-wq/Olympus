"""KRONOS, the OLYMPUS calendar of money (tools/web_public/kronos/, AGORA look, 2026-11-10): a month grid of the daily P&L, the best and worst weekday and hour in $ with n, what a normal bad week looks like
(honest percentiles, n shown, no band below 8 weeks) and a marble sundial whose shadow is today's P&L against a typical day. Read only.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the 3D dial is a separate light module, the wiring rows exist
  b. the maths in node (kronoscore.js): dates, the month grid, weekday / hour buckets with n, the weekly band and its honesty rules, the sundial, junk input, no markup from data
  c. Chromium 390 x 844 (and 375 x 667): the DEMO case, month navigation, the Backtest chip, the 3D dial (and the flat twin with ?q=off), the real trades.json, the fallback when only backtest trades exist, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_kronos_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "kronos", "Kronos"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../odeon/trades.json",))
    d = os.path.join(AK.WEB, APP)
    html = AK.read(os.path.join(d, "index.html"))
    check("a. the page order: the sundial and today, the month, the weekday, the hour, the normal bad week", html.index('id="stage"') < html.index('id="grid"') < html.index('id="wkRows"') < html.index('id="hrRows"') < html.index('id="bandCard"'))
    check("a. the 3D dial is its own module tag (a failed load can never stop the page) and the flat twin exists", 'src="kronosdial.js' in html and "KRONOS_DIAL_FAIL" in html and 'id="flat"' in html)
    dial = AK.read(os.path.join(d, "kronosdial.js"))
    check("a. the dial is light: the render core + materials, bloom <= .25, a dpr cap <= 1.5, no data, no network, idle rules (hidden, frameGap, reduced motion)",
          "olympus/render.js" in dial and re.search(r"strength:\s*0\.(?:[0-2]\d?)\b", dial) and "maxDpr: 1.5" in dial and "O.hidden()" in dial and "frameGap" in dial and "RM" in dial and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket", dial))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: 42 invented trade days with a fixed 'today' (2026-11-06), every trade has a day, a $ result, its risk and an entry time",
          len(fx["trades"]) == 42 and fx["today"] == "2026-11-06" and all(t["day"] and isinstance(t["usd"], int) and t["risk_usd"] > 0 and t["entry"]["t"] > 1e9 for t in fx["trades"]))
    sc = AK.read(os.path.join(d, "kronos.js")) + AK.read(os.path.join(d, "kronoscore.js"))
    check("a. read only, paper: no order, key or write code in the page", not re.search(r"\b(placeOrder|submitOrder|api[_-]?key|Authorization|\.post\()", sc, re.I))
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the wiring rows for the lead are in docs/NEW_APPS_WIRING.md (a section named Kronos)", re.search(r"^# .*KRONOS", wiring, re.M | re.I) is not None)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const fx = JSON.parse(process.argv[3]);
  const live = C.normTrades(fx, 'live'), v = C.view(live, fx.today);
  o.words = [C.usd0(-1234.6), C.usd0S(565), C.usd0S(0.2), C.rWord(565, 425), C.rWord(-437, 425), C.both(-437, 425), C.both(100, null), C.hourWord(0), C.hourWord(13), C.monthWord('2026-10'), C.dayWord('2026-10-28')];
  o.dates = [C.dowOf('2026-11-06'), C.dowOf('2026-11-09'), C.mondayOf('2026-11-08'), C.addDays('2026-12-31', 1), C.addMonths('2026-12', 1), C.addMonths('2026-01', -1), C.etHour(1793173380), C.etDay(1793173380), C.etHour(null), C.etDay(0)];
  o.sets = [live.length, C.normTrades(fx, 'back').length, C.normTrades({ trades: [{ day: '2026-01-05', usd: 10, src: 'backtest' }, { day: '2026-01-06', usd: 20, src: 'paper' }, { day: 'bad', usd: 5 }, { day: '2026-01-07' }, 7, { day: '2026-01-08', usd: -5 }] }, 'live').length, C.normTrades({ trades: [{ day: '2026-01-05', usd: 10, src: 'backtest' }] }, 'back').length, C.normTrades(null, 'live').length];
  o.view = [v.n, v.days, v.net, v.unit, v.typical, v.today, v.todayN, v.from, v.to];
  const g = C.monthGrid(v.dm, '2026-10', v.unit), nov = C.monthGrid(v.dm, '2026-11', v.unit), feb = C.monthGrid(new Map(), '2026-02', null);
  o.grid = [g.cells.length, g.weeks, g.cells[0].day, g.cells[0].inMonth, g.cells[3].day, g.cells[3].inMonth, g.total, g.days, g.green, g.red, g.trades, nov.cells.length, nov.total, nov.days, feb.cells.length, feb.weeks, feb.total, feb.cells.every((c) => c.usd === null)];
  o.cell = (() => { const c = g.cells.find((x) => x.usd != null); return [c.day, c.usd, c.n, c.word]; })();
  o.months = [C.monthsWithData(v.dm, '2026-11'), C.monthsWithData(new Map(), '2026-11')];
  o.wk = [v.wk.rows.map((r) => [r.label, r.n, r.usd]), v.wk.best.label, v.wk.worst.label, v.wk.enough, C.bucketWord(v.wk.best, v.unit)];
  o.hr = [v.hr.rows.map((r) => [r.label, r.n, r.usd]), v.hr.best.label, v.hr.worst.label, v.hr.known];
  const few = C.view(C.normTrades({ trades: [{ day: '2026-11-02', usd: 100, risk_usd: 50, entry: { t: 1793000000 } }, { day: '2026-11-03', usd: -50, risk_usd: 50, entry: { t: 1793000000 } }] }, 'live'), '2026-11-03');
  o.few = [few.wk.enough, few.wk.best, few.hr.enough, few.band.enough, few.band.n, C.bandLines(few.band, few.unit)[0], few.dial.word.length > 10];
  o.band = [v.band.enough, v.band.n, v.band.worst, v.band.p10, v.band.p20, v.band.p50, v.band.p80, v.band.best, v.band.losing, C.bandLines(v.band, v.unit).length, C.bandLines(v.band, v.unit)[1]];
  o.pct = [C.pct([1, 2, 3, 4, 5], 0.5), C.pct([1, 2, 3, 4], 0.5), C.pct([10], 0.2), C.pct([], 0.5), C.pct([0, 100], 0.1)];
  o.dial = [C.sundial(0, 100, 50).shadow, C.sundial(200, 100, 50).shadow, C.sundial(-500, 100, 50).shadow, C.sundial(1e6, 100, 50).shadow, C.sundial(-1e6, 100, 50).tone, C.sundial(null, 100, 50).tone, C.sundial(50, 0, 50).shadow, C.sundial(150, 100, 50).z, C.sundial(150, 100, 50).tone, C.sundial(-150, 100, 50).word, v.dial.word, C.shadowAngle(12), C.shadowAngle(9) < 0, C.shadowAngle(15) > 0, C.shadowAngle(null), C.shadowAngle(3) === C.shadowAngle(6)];
  o.head = [C.headline(v, 'live'), C.headline(C.view([], '2026-11-06'), 'live').startsWith('No real or paper trades'), C.headline(C.view([], '2026-11-06'), 'back'), C.headline(C.view(live.filter((t) => t.day < '2026-11-06'), '2026-11-06'), 'live').startsWith('No trade today yet.')];
  o.choose = [C.chooseData(null, fx).src, C.chooseData(fx, null).src, C.chooseData({ trades: [] }, fx).src, C.chooseData(null, null), C.chooseData(null, fx).today, C.chooseData({ trades: [{ day: '2026-01-01', usd: 5, src: 'backtest' }] }, fx).src];
  const evil = C.view(C.normTrades({ trades: [{ day: '2026-11-02', usd: '<b>5</b>', src: '<i>x</i>' }, { day: '2026-11-03', usd: 12, risk_usd: 'zz', src: 'real<script>' }] }, 'live'), '2026-11-03');
  o.evil = [evil.n, evil.net, evil.unit, JSON.stringify(evil.dial).includes('<')];
  const card = C.jarvisCard(v, 'live'), cardB = C.jarvisCard(C.view([], '2026-11-06'), 'back');
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.kpis[2].value, card.lines[1], cardB.status.level, cardB.lines[1], Number.isInteger(card.t), JSON.stringify(card).length < 8192, /[<>]/.test(JSON.stringify(card))];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    import shutil
    if not shutil.which("node"):
        check("b. node is not installed: maths skipped", True)
        return
    fx = AK.read(os.path.join(AK.WEB, APP, "fixture.json"))
    o = AK.node(APP, HARNESS, fx)
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: whole dollars, a sign, every dollar with its R (1R = the average risk), no R without a risk, 12 AM / 1 PM, month and day names",
          o["words"] == ["-$1,235", "+$565", "$0", "+1.3R", "-1.0R", "-$437 (-1.0R)", "+$100 (0.0R)", "12 AM", "1 PM", "October 2026", "Oct 28"], o["words"])
    check("b. dates: Friday = 4, Monday = 0, the Monday of a Sunday, year rollover, months back and forward, the New York hour and day of an epoch, null in -> null out",
          o["dates"] == [4, 0, "2026-11-02", "2027-01-01", "2027-01", "2025-12", 3, "2026-10-28", None, None], o["dates"])
    check("b. sets: the demo has 42 live trades and no backtest; real + paper are 'live', backtest is its own set; bad days, missing $, junk rows and null are dropped",
          o["sets"] == [42, 0, 2, 1, 0], o["sets"])
    check("b. the demo view: 42 trades on 42 days, net $13,343, 1R $425, a typical day $683, today +$565 on 1 trade, 2026-08 to 2026-11", o["view"][:7] == [42, 42, 13343, 425, 682.55, 565, 1] and o["view"][7].startswith("2026-0") and o["view"][8] == "2026-11-06", o["view"])
    check("b. the month grid: October 2026 is 5 whole weeks starting Monday Sep 28 (out of month), Oct 1 is the 4th square; $3,431 over 16 days (5 green, 11 red, 16 trades); November 2026 is 6 weeks (it starts on a Sunday): $1,925 over 4 days; an empty February is 5 weeks and all empty",
          o["grid"] == [35, 5, "2026-09-28", False, "2026-10-01", True, 3431, 16, 5, 11, 16, 42, 1925, 4, 35, 5, 0, True], o["grid"])
    check("b. a day square carries its $ and its R in words; the months with data are listed oldest first and include today's month even when empty", o["cell"][3].endswith(")") and "R)" in o["cell"][3] and o["months"][0][0] == "2026-08" and o["months"][0][-1] == "2026-11" and o["months"][1] == ["2026-11"], (o["cell"], o["months"]))
    check("b. best and worst weekday in $ with n: Wednesday +$7,728 over 10 trades is best, Thursday -$1,004 over 7 is worst; the sentence names the n",
          o["wk"][1:4] == ["Wednesday", "Thursday", True] and ["Wednesday", 10, 7728] in o["wk"][0] and ["Thursday", 7, -1004] in o["wk"][0] and "over 10 trades" in o["wk"][4] and "R)" in o["wk"][4], o["wk"])
    check("b. best and worst hour (New York, at entry) with n: 9 AM is best, 3 AM is worst; all 42 trades have an hour", o["hr"][1:] == ["9 AM", "3 AM", 42] and ["9 AM", 11, 6943] in o["hr"][0], o["hr"])
    check("b. honesty: two trades give no best / worst weekday or hour and no weekly band ('n=2', 'no claim is made'); a bucket needs 3+ trades",
          o["few"][0] is False and o["few"][1] is None and o["few"][2] is False and o["few"][3] is False and o["few"][4] == 1 and "n=1" in o["few"][5] and "no claim is made" in o["few"][5], o["few"])
    check("b. the weekly band from 14 weeks (n shown): worst -$850, 1 in 10 -$301, 1 in 5 -$30, middle +$678, 1 in 5 good +$1,789, best +$3,570; 3 losing weeks; every $ with its R",
          o["band"][:9] == [True, 14, -850, -300.9, -30.4, 677.5, 1789.4, 3570, 3] and o["band"][9] == 3 and "-$301 (-0.7R)" in o["band"][10] and "-$850 (-2.0R)" in o["band"][10], o["band"])
    check("b. percentiles interpolate: median of 1..5 is 3, of 1..4 is 2.5, one value is itself, nothing is null, 10% of 0..100 is 10", o["pct"] == [3, 2.5, 10, None, 10], o["pct"])
    check("b. the sundial: a flat day = shadow 1; +$200 on a typical $100 = 0.2 (clamped short); -$500 = 2.2 (clamped long); extremes stay inside 0.18..2.2; no trade = the middle, tone none; a loss reads 'a hard day, a long shadow'",
          o["dial"][:5] == [1, 0.2, 2.2, 0.18, "loss"] and o["dial"][5] == "none" and o["dial"][6] == 1 and o["dial"][7] == 1.5 and o["dial"][8] == "gain" and "a hard day, a long shadow" in o["dial"][9] and "a good day, a shortening shadow" in o["dial"][10], o["dial"])
    check("b. the shadow direction follows the clock: noon straight, morning one side, afternoon the other, clamped to 6 AM - 6 PM, null = noon", o["dial"][11:] == [0, True, True, 0, True], o["dial"])
    check("b. the headline states today with its R, the days and trades, net and a typical day; empty sets say so in plain words, never blank; a day without a trade says 'No trade today yet'",
          o["head"][0] == "Today +$565 (+1.3R). 42 trading days so far (42 trades): net +$13,343 (+31.4R). A typical day moves $683." and o["head"][1] is True and o["head"][2] == "No backtest trades in the file." and o["head"][3] is True, o["head"])
    check("b. choosing the data: a real file wins, an empty or missing one falls back to the labelled demo (with its fixed today), a backtest-only file still counts as a file, nothing at all gives null",
          o["choose"] == ["demo", "file", "demo", None, "2026-11-06", "file"], o["choose"])
    check("b. no markup survives from data: a '<b>5</b>' dollar value is dropped, tags in the source are stripped, a bad risk is ignored", o["evil"][0] == 1 and o["evil"][1] == 12 and o["evil"][2] is None and o["evil"][3] is False, o["evil"])
    check("b. the Jarvis card: Kronos, a level, 3 kpis (today, net, days), a source line, an integer t, under 8 KB, no markup; an empty backtest is 'off'",
          o["card"] == ["Kronos", "ok", 3, "+$565", "42", "Real and paper trades only.", "off", "Backtest numbers: history, not a promise.", True, True, False], o["card"])


def real_trades(rows, extra=None):
    out = []
    for i, (day, usd, src) in enumerate(rows):
        out.append({"day": day, "usd": usd, "risk_usd": 400, "src": src, "entry": {"t": 1793000000 + i * 86400}, "bars": {}, "events": []})
    return json.dumps({"app": "odeon", "n": len(out), "trades": out, **(extra or {})})


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
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#head').textContent, tiles: document.querySelector('#heroTiles').textContent,
              dial: document.querySelector('#dialWord').textContent, chips: [...document.querySelectorAll('#sets button')].map((b) => b.textContent), month: document.querySelector('#monthTitle').textContent,
              cells: document.querySelectorAll('#grid .cell').length, up: document.querySelectorAll('#grid .cell.up').length, dn: document.querySelectorAll('#grid .cell.dn').length, now: document.querySelectorAll('#grid .cell.now').length,
              mt: document.querySelector('#monthTiles').textContent, wk: document.querySelector('#wkText').textContent, hr: document.querySelector('#hrText').textContent, wkRows: document.querySelectorAll('#wkRows > li').length,
              band: document.querySelector('#bandPill').textContent, bandText: document.querySelector('#bandText').textContent, bandRows: document.querySelectorAll('#bandRows > li').length, next: document.querySelector('#nextM').disabled,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor })""")
            check("c. DEMO: the chip, 'Example numbers: Today +$565 (+1.3R)', the sundial words, two set chips with their counts (42 / 0)",
                  d["demo"] and d["head"].startswith("Example numbers: Today +$565 (+1.3R)") and "Today+$565+1.3R" in d["tiles"].replace(" ", "") and "a shortening shadow" in d["dial"] and d["chips"] == ["Real and paper (42)", "Backtest (0)"], d)
            check("c. the month opens on today's month (November 2026): 6 weeks of squares (Nov 2026 starts on a Sunday), today outlined, the next-month button is off (nothing later), green and red squares",
                  d["month"] == "November 2026" and d["cells"] == 42 and d["now"] == 1 and d["next"] is True and d["up"] + d["dn"] >= 3, d)
            check("c. best / worst weekday and hour in $ with n in the words, 5 weekday rows, the weekly band says n=14 with 6 rows under a range bar",
                  "Best weekday: Wednesday" in d["wk"] and "over 10 trades" in d["wk"] and "Best hour" in d["hr"] and "9 AM" in d["hr"] and d["wkRows"] == 5 and d["band"] == "n=14 weeks" and "n=14" in d["bandText"] and d["bandRows"] == 6, d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "kronos-demo")
            p.locator("#prevM").click()
            p.wait_for_timeout(150)
            m = p.evaluate("() => [document.querySelector('#monthTitle').textContent, document.querySelector('#nextM').disabled, document.querySelectorAll('#grid .cell.now').length, document.querySelector('#status').textContent]")
            check("c. the previous-month button goes to October 2026 and the status line speaks it; the next button is on again", m[0] == "October 2026" and m[1] is False and m[2] == 0 and "October" in m[3], m)
            p.locator("#sets button", has_text="Backtest").click()
            p.wait_for_timeout(200)
            b = p.evaluate("() => [document.querySelector('#head').textContent, document.querySelector('#sets [aria-pressed=true]').textContent, document.querySelectorAll('#grid .cell').length > 0, document.querySelector('#bandPill').textContent, document.querySelector('#wkText').textContent]")
            check("c. the Backtest chip: an empty set says so in plain words, never blank; no band (0 weeks, no claim), no best weekday", "No backtest trades" in b[0] and b[1].startswith("Backtest") and b[2] and b[3].startswith("Too few weeks") and "Not enough trades" in b[4], b)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (the month buttons, the chips)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            dial = p.evaluate("() => { const d = window.KRONOS.dial; return d ? { q: d.quality(), lite: d.lite, shown: !document.querySelector('#stage').hidden && document.querySelector('#flat').hasAttribute('hidden'), size: [document.querySelector('#stage').clientWidth, document.querySelector('#stage').clientHeight] } : null }")
            if dial is None:
                check("c. 3D: no WebGL here, so the flat sundial is shown (the page still works)", p.evaluate("() => window.KRONOS.flat === true && !document.querySelector('#flat').hasAttribute('hidden')"))
            else:
                check("c. 3D: the marble sundial is up, the flat twin is hidden, the canvas has a real size", dial["shown"] and dial["size"][0] > 200 and dial["size"][1] > 100, dial)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=off")
            q = p.evaluate("() => ({ flat: window.KRONOS.flat, dial: !!window.KRONOS.dial, svg: !document.querySelector('#flat').hasAttribute('hidden'), canvas: document.querySelector('#stage').hidden, lines: document.querySelectorAll('#flat line').length })")
            check("c. ?q=off (3D Off): the flat marble sundial is drawn instead (12 hour marks and the shadow), the page works the same, no error", q["flat"] and not q["dial"] and q["svg"] and q["canvas"] and q["lines"] == 13 and not errs, (q, errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
            rows = [("2026-11-02", -437, "real"), ("2026-11-03", 310, "paper"), ("2026-11-04", 120, "backtest"), ("2026-11-05", 640, "real")]
            srv2, origin2 = AK.serve({"/odeon/trades.json": real_trades(rows)})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=2026-11-06T15:00:00Z")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#head').textContent, chips: [...document.querySelectorAll('#sets button')].map((b) => b.textContent), month: document.querySelector('#monthTitle').textContent, now: document.querySelectorAll('#grid .cell.now').length, band: document.querySelector('#bandText').textContent, wk: document.querySelector('#wkText').textContent })")
            check("c. the real trades.json (real + paper only; the backtest trade is left out): no DEMO chip, 3 trades on 3 days net +$513, today (Nov 6, New York) has no trade yet, today's square is outlined, the band says n=1 'no claim is made'",
                  not r["demo"] and "No trade today yet. 3 trading days so far (3 trades): net +$513" in r["head"] and r["chips"] == ["Real and paper (3)", "Backtest (1)"] and r["month"] == "November 2026" and r["now"] == 1 and "n=1" in r["band"] and "no claim is made" in r["band"] and "Not enough trades" in r["wk"], r)
            check("c. the real run reads only the site's files and no console error", any("odeon/trades" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/odeon/trades.json": real_trades([("2026-11-02", 100, "backtest"), ("2026-11-03", -50, "backtest")])})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?q=off")
            r = p.evaluate("() => [document.querySelector('#sets [aria-pressed=true]').textContent, document.querySelector('#srcNote').textContent, document.querySelector('#head').textContent]")
            check("c. only backtest trades in the file: it shows the backtest and says there are no real or paper trades yet (never blank)", r[0].startswith("Backtest") and "No real or paper trades in the file yet" in r[1] and "2 trading days" in r[2] and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()
            srv4, origin4 = AK.serve({"/odeon/trades.json": "{broken"})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "?q=off")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#head').textContent]")
            check("c. a broken trades.json falls back to the labelled demo, never blank", r[0] is True and r[1].startswith("Example numbers") and not errs, (r, errs[:2]))
            ctx.close()
            srv4.shutdown()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
