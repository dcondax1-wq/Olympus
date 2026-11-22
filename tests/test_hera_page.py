"""HERA, the OLYMPUS plan-and-payouts screen (tools/web_public/hera/, AGORA look, 2026-11-09): the 12-month money roadmap, the payout calendar, cash in / out, the next account to buy.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the saved-copy fixture equals the roadmap file the site publishes (plutus/roadmap.json)
  b. the maths in node (heracore.js): the roadmap checker (hostile input), the headline, the chart geometry, the month card, the payout rows / calendar, cash, the re-buy ranking
  c. Chromium 390 x 844 (and 375 x 667): the real roadmap file, the other half, the month slider, the calendar, the DEMO copy when the file is missing, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_hera_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "hera", "Hera"
check = AK.check
ROAD = os.path.join(AK.WEB, "plutus", "roadmap.json")
FIX = os.path.join(AK.WEB, APP, "fixture.json")


def test_static():
    AK.static_kit(APP, NAME, reads=("../plutus/roadmap.json", "../home.json"))
    road, fx = json.load(open(ROAD, encoding="utf-8")), json.load(open(FIX, encoding="utf-8"))
    same = all(fx["versions"][k]["months"] == road["versions"][k]["months"] and fx["versions"][k]["mid"] == road["versions"][k]["mid"] for k in ("H1", "H2"))
    check("a. the saved copy (fixture.json) has the same 12 months, middle paths and accounts as the roadmap file the site publishes (rebuild it when the study is rerun)",
          same and [a["id"] for a in fx["accounts"]] == [a["id"] for a in road["accounts"]] and fx["order"]["rebuy"] == road["order"]["rebuy"], "fixture is stale")
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page order: the big number, the chart, cash in and out, the payout calendar, the next account to buy, the caveats",
          html.index('id="big"') < html.index('id="chart"') < html.index('id="cashTiles"') < html.index('id="cal"') < html.index('id="buyList"') < html.index('id="cav"'))
    check("a. the month slider is a native range input with a label (44 px tall in the CSS)", 'type="range"' in html and 'for="mslider"' in html and "min-height: 44px" in AK.read(os.path.join(AK.WEB, APP, "hera.css")))


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const raw = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), o = {};
  o.words = [C.money(13105.4), C.money(-106), C.moneyS(246), C.dayWord('2026-12-21'), C.monthWord('2027-11-05'), C.dayWord('x'), C.daysBetween('2026-11-09', '2026-12-21'), C.daysBetween('a', 'b')];
  const road = C.readRoadmap(raw);
  o.road = { keys: Object.keys(road.versions), n: road.versions.H2.months.length, acc: road.accounts.map((a) => a.id), cons: road.conservative, paid: road.paid, first: road.first_session, todo: road.todo.length, cav: road.caveats.length, best: road.best };
  const hd = C.headline(road, 'H2'), h1 = C.headline(road, 'H1');
  o.head = [hd.mid, hd.lo, hd.hi, hd.in, hd.out, hd.months, hd.until, hd.text, h1.mid, C.headline(road, 'zzz').mid, C.headline(null, 'H2')];
  const g = C.chart(road.versions.H2.months, 360, 220), mo = road.versions.H2.months;
  o.chart = { pts: g.pts.length, start: g.line.startsWith('M'), band: g.band.endsWith('Z'), zero: g.zeroY > 0 && g.zeroY < 220, inside: g.pts.every(([x, y]) => x >= 0 && x <= 360 && y >= 0 && y <= 220), up: g.y(mo[11].cum) < g.y(mo[0].cum), bandWider: g.y(mo[11].hi) < g.y(mo[11].lo), grid: g.grid.length > 1, lo: g.lo <= 0, one: C.chart([{ cum: 5, lo: 1, hi: 9 }], 100, 100).pts.length, none: C.chart([], 1, 1) };
  const mi = C.monthInfo(mo, 2);
  o.month = [mi.m, mi.label, mi.in, mi.out, mi.cum, mi.text.startsWith('Cash in $977, cash out $37: +$941 this month. Running total $1,187'), C.monthInfo(mo, 99).m, C.monthInfo(mo, 'x').m, C.monthInfo([], 1), C.monthLabel(mo[0])];
  const pr = C.payoutRows(road, 'H2', '2026-11-09');
  o.pay = { order: pr.rows.map((r) => r.short), days: pr.rows.map((r) => r.days), early: pr.rows[0].daysEarly, late: pr.rows[0].daysLate, axis: [pr.axis.min, pr.axis.max, pr.axis.today], x: pr.rows.map((r) => [r.x0 <= r.xt, r.xt <= r.x1, r.x1 <= 1]).flat().every(Boolean), pastDays: C.payoutRows(road, 'H2', '2027-03-01').rows.map((r) => r.days), empty: C.payoutRows({ accounts: [], conservative: 'H2' }, 'H2', '2026-11-09'), h1first: C.payoutRows(road, 'H1', '2026-11-09').rows[0].typical, nullRoad: C.payoutRows(null, 'H2', 'x').rows.length };
  const cal = C.calendar(pr.rows);
  o.cal = [cal[0].text, cal[0].sub, cal[0].month, C.calendar(C.payoutRows(road, 'H2', '2027-03-01').rows)[0].sub];
  const cs = C.cash(road, 'H2'); o.cash = [cs.in, cs.out, cs.net, cs.paid, C.cash(null, 'H2')];
  const b = C.buyNext(road, 'H2'), b1 = C.buyNext(road, 'H1');
  o.buy = { rank: b.rank.map((r) => [r.short, r.price, r.gain, r.per]), top: b.top.short, text: b.text, h1: b1.rank.map((r) => r.short), now: b.now, todo: b.todo.length > 10, none: C.buyNext(null, 'H2'), empty: C.buyNext({ rebuy: { H2: {} }, todo: [], best: '' }, 'H2').text };
  // hostile input
  const bad = (x) => C.readRoadmap(x);
  o.evil = [bad(null), bad('x'), bad({}), bad({ versions: 5 }), bad({ versions: { H2: { months: [{ cum: 1, from: '2026-11-01' }] } } }), bad({ versions: { H2: { months: [1, 2, 3] } } })];
  const one = bad({ versions: { H1: { label: '<b>x</b>', months: [1, 2, 3].map((m) => ({ m, from: '2026-1' + m + '-01', cum: m * 100, in: 'x', out: null })) } }, caveats: ['a <script>b</script> c', 7, ''], todo: 'not a list', accounts: [null, { id: 5 }, { id: 'lit50', price: '91.8', H1: { first: ['2026-12-01', 'bad', '2027-01-01', '2027-02-01'], net12: 'x' } }] });
  o.one = [Object.keys(one.versions), one.versions.H1.label, one.versions.H1.months[0].lo, one.versions.H1.months[0].in, one.caveats, one.todo, one.accounts.length, one.accounts[0].price, one.accounts[0].per.H1.first.length, one.conservative];
  const card = C.jarvisCard(road, 'H2', '2026-11-09');
  o.card = [card.name, card.status.label, card.kpis.map((k) => k.value).join('|'), card.lines, card.lines.every((l) => l.length <= 120), C.jarvisCard(null, 'H2', '2026-11-09').status.level];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, ROAD)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: $13,105 rounded, -$106, +$246, 'Dec 21', 'Nov 2027', junk -> empty / null, 2026-11-09 to 2026-12-21 is 42 days", o["words"] == ["$13,105", "-$106", "+$246", "Dec 21", "Nov 2027", "", 42, None], o["words"])
    r = o["road"]
    check("b. the real roadmap file reads clean: both halves with 12 months, three accounts, the cautious half (H2) is the default, $197.80 already paid, the first session, the todo list and the caveats",
          r["keys"] == ["H1", "H2"] and r["n"] == 12 and r["acc"] == ["atlas25", "lit50", "blitz25"] and r["cons"] == "H2" and r["paid"] == 197.8 and r["first"] == "2026-11-05" and r["todo"] >= 3 and r["cav"] >= 3 and r["best"] == "Buy all three on day 1.", r)
    hd = o["head"]
    check("b. the headline: typical $13,105, bad run $9,759, good run $14,892, cash in $13,082 / out $161, 12 months to 2027-11-05, the sentence says typical / 1 in 10 / after every fee; an unknown half falls back; no file -> null",
          hd[:7] == [13105, 9759, 14892, 13082, 161, 12, "2027-11-05"] and hd[7] == "Typical cash to you by Nov 2027: $13,105. A bad run (1 in 10): $9,759. A good run (1 in 10): $14,892. After every fee." and hd[8] == 14345 and hd[9] == 13105 and hd[10] is None, hd)
    c = o["chart"]
    check("b. the chart: 12 points inside the box, a line and a closed band, the zero line is inside, cash rises from month 1 to 12, the band is wider than the line, grid lines, one point and no point are safe",
          c["pts"] == 12 and c["start"] and c["band"] and c["zero"] and c["inside"] and c["up"] and c["bandWider"] and c["grid"] and c["lo"] and c["one"] == 1 and c["none"] is None, c)
    check("b. a month card: month 2 = Dec 7 to Jan 6, in $977, out $37, total $1,187 with the sentence; a month past the end clamps to 12, junk to 1, no months -> null; the month name",
          o["month"] == [2, "Dec 7 to Jan 6", 977, 37, 1187, True, 12, 1, None, "Nov"], o["month"])
    p = o["pay"]
    check("b. the payout rows (2026-11-09): ATLAS, then Zlarior, then BLITZ by typical date; 42 / 92 / 113 days; ATLAS could be 15 days away or 105; the axis runs from today to the slowest date; bars are ordered and inside 0..1; once a date passes the days go negative; the better half is earlier",
          p["order"] == ["ATLAS", "Zlarior", "BLITZ"] and p["days"] == [42, 92, 113] and p["early"] == 15 and p["late"] == 105 and p["axis"][0] == "2026-11-09" and p["axis"][2] == 0 and p["x"] and p["pastDays"][0] < 0 and p["h1first"] < "2026-12-21" and p["empty"]["axis"] is None and p["nullRoad"] == 0, p)
    check("b. the calendar words: 'Dec 21: ATLAS first payout (typical)', 'in 42 days; could be Nov 24 to Feb 22', grouped by month, 'due now' once passed", o["cal"] == ["Dec 21: ATLAS first payout (typical)", "in 42 days; could be Nov 24 to Feb 22", "Dec 2026", "due now"], o["cal"])
    check("b. cash: in $13,082, out $161, net $12,921, $197.80 already paid and not counted; no file -> null", o["cash"] == [13082, 161, 12921, 197.8, None], o["cash"])
    b = o["buy"]
    check("b. next account to buy (cautious half): ATLAS 25K first ($43, +$3,087, $72 back per $1), then Zlarior ($91.80, +$544), then BLITZ ($63, +$194); the sentence names it; the better half ranks by its own numbers; empty -> no sentence",
          b["rank"] == [["ATLAS", 43, 3087, 72], ["Zlarior", 91.8, 544, 6], ["BLITZ", 63, 194, 3]] and b["top"] == "ATLAS" and b["text"].startswith("Next eval to buy once an account has had its 5th payout: ATLAS 25K at $43. The study adds $3,087") and b["h1"][0] == "ATLAS" and b["now"] == "Buy all three on day 1." and b["todo"] and b["none"] is None and b["empty"] == "", b)
    e = o["one"]
    check("b. hostile roadmap files: null / text / empty / wrong shapes / too few months -> null (the page then shows its saved copy, labelled)", o["evil"] == [None] * 6, o["evil"])
    check("b. a thin file is cleaned, never trusted: tags removed, bad numbers become 0 or the cum value, non-lists dropped, bad dates and junk accounts removed",
          e[0] == ["H1"] and "<" not in e[1] and e[2] == 100 and e[3] == 0 and all("<" not in c for c in e[4]) and e[4] == ["a b c"] and e[5] == [] and e[6] == 1 and e[7] == 91.8 and e[8] == 3 and e[9] == "H2", e)
    cd = o["card"]
    check("b. the Jarvis card: Hera, '$13,105 | $9,759 | Dec 21', two lines <= 120; no plan -> level off", cd[0] == "Hera" and cd[1] == "Plan: $13,105 in 12 months" and cd[2] == "$13,105|$9,759|Dec 21" and len(cd[3]) == 2 and cd[4] and cd[5] == "off", cd)


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
            AK.open_app(p, origin, APP, "?at=2026-11-09T15:00:00Z")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, big: document.querySelector('#big').textContent, chips: [...document.querySelectorAll('#vers button')].map((b) => b.textContent), on: document.querySelector('#vers [aria-pressed=true]').textContent,
              txt: document.querySelector('#bigText').textContent, mH: document.querySelector('#mH').textContent, slider: [document.querySelector('#mslider').min, document.querySelector('#mslider').max, document.querySelector('#mslider').value],
              cash: document.querySelector('#cashTiles').innerText, cal: [...document.querySelectorAll('#calList li')].map((l) => l.querySelector('b').textContent), buy: [...document.querySelectorAll('#buyList li b')].map((b) => b.textContent), buyText: document.querySelector('#buyText').textContent,
              paths: document.querySelectorAll('#chart path').length, circles: document.querySelectorAll('#chart circle').length, calSvg: document.querySelectorAll('#cal circle').length, font: getComputedStyle(document.querySelector('h1')).fontFamily,
              reads: performance.getEntriesByType('resource').filter((r) => /plutus\\/roadmap/.test(r.name)).length }) """)
            check("c. the real roadmap file: no DEMO chip, '$13,105', the cautious half on, month 12 selected, cash in / out, three calendar rows (ATLAS first), the buy ranking (ATLAS first), a band + a line + a marker on the chart",
                  not d["demo"] and d["big"] == "$13,105" and d["chips"] == ["Cautious", "Better half"] and d["on"] == "Cautious" and d["slider"] == ["1", "12", "12"] and d["mH"].startswith("Month 12") and "$13,082" in d["cash"] and "$161" in d["cash"]
                  and d["cal"][0] == "Dec 21: ATLAS first payout (typical)" and len(d["cal"]) == 3 and d["buy"][0] == "1. ATLAS 25K" and "ATLAS 25K at $43" in d["buyText"] and d["paths"] == 2 and d["circles"] == 1 and d["calSvg"] == 3 and d["reads"] == 1, d)
            check("c. AGORA look: a serif title", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")))
            AK.shot(p, "hera-real")
            p.locator("#mslider").fill("2")
            p.wait_for_timeout(150)
            m = p.evaluate("() => [document.querySelector('#mH').textContent, document.querySelector('#mText').textContent, document.querySelector('#mTiles').innerText, document.querySelector('#mslider').getAttribute('aria-valuetext')]")
            check("c. slide to month 2: 'Month 2: Dec 7 to Jan 6', cash in $977 / out $37, running total $1,187, the slider says it aloud", m[0] == "Month 2: Dec 7 to Jan 6" and "$977" in m[2] and "$37" in m[2] and "$1,187" in m[2] and "Running total $1,187" in m[1] and "$1,187" in m[3], m)
            p.locator("#vers [data-k=H1]").click()
            p.wait_for_timeout(150)
            h1 = p.evaluate("() => [document.querySelector('#big').textContent, document.querySelector('#vers [aria-pressed=true]').textContent, document.querySelector('#status').textContent.slice(0, 40)]")
            check("c. the better half: $14,345, its chip is pressed, the status line is spoken", h1[0] == "$14,345" and h1[1] == "Better half" and h1[2].startswith("Typical cash to you"), h1)
            check("c. every tap target is at least 44 x 44 px (the chips, the slider, the summary)", not AK.taps(p), AK.taps(p)[:4])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (AK.no_sideways(p), AK.corner(p), errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-09T15:00:00Z&v=H1&month=6")
            q = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#big').textContent, document.querySelector('#mH').textContent.slice(0, 7), document.querySelector('#vers [aria-pressed=true]').textContent, performance.getEntriesByType('resource').filter((r) => /plutus\\/roadmap/.test(r.name)).length]")
            check("c. DEMO (?demo=1, the saved copy): the chip, the same numbers, ?v=H1&month=6 opens the better half at month 6, the real file is never read", q == [True, "$14,345", "Month 6", "Better half", 0], q)
            ctx.close()
            srv2, origin2 = AK.serve({"/plutus/roadmap.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "")
            n = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#big').textContent, document.querySelectorAll('#calList li').length]")
            check("c. no roadmap file on the site: the saved copy appears by itself, labelled DEMO, never blank", n[0] and n[1] == "$13,105" and n[2] == 3, n)
            ctx.close()
            srv2.shutdown()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
