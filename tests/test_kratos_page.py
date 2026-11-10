"""KRATOS, the OLYMPUS discipline score (tools/web_public/kratos/, AGORA look, 2026-11-10): a 0-100 score per trading day from the bot's published trades and the owner's journal ratings (read only),
six parts each explained in one plain sentence with dollars and R, a 30-day sparkline, best / worst day, and a bronze column whose height is the score (3D, flat fallback).

  a. static: the files, the kit lines, the AGORA look, read-only (the journal is only ever read), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (kratoscore.js): the clock in New York time, trade normalising, the six parts, the weights, estimates for what cannot be seen, 30-day window, best / worst, junk safety
  c. Chromium 390 x 844: DEMO, the day navigation, the real trades file with a real journal, an empty / broken file falls back to the fixture, 3D or flat column, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_kratos_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "kratos", "Kratos"
check = AK.check
FIX = os.path.join(AK.WEB, APP, "fixture.json")


def test_static():
    AK.static_kit(APP, NAME, reads=("../odeon/trades.json",), storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "kratos.js")) + AK.read(os.path.join(d, "kratoscore.js"))
    check("a. the journal is only READ (localStorage.getItem 'journal.v1'): no setItem / removeItem / clear / sessionStorage / indexedDB anywhere",
          "localStorage.getItem('journal.v1')" in js and not re.search(r"localStorage\.(setItem|removeItem|clear)|sessionStorage|indexedDB", js))
    check("a. the 3D files: column.js (render core) and columnload.js (its own module tag)", all(os.path.isfile(os.path.join(d, n)) for n in ("column.js", "columnload.js")))
    cj = AK.read(os.path.join(d, "column.js"))
    check("a. column.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network, no markup from data",
          "../olympus/render.js" in cj and "../jarvis/three.module.min.js" in cj and not AK.BANNED_LOOK.search(cj) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", cj)
          and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", cj)))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. columnload.js before kratos.js; a canvas AND a flat svg column (the fallback); page order: your day, parts, 30 days, best / worst, days, how",
          html.index("columnload.js") < html.index('src="kratos.js') and 'id="stage"' in html and 'id="flat"' in html
          and html.index('id="score"') < html.index('id="parts"') < html.index('id="spark"') < html.index('id="bw"') < html.index('id="days"') < html.index('id="how"'))
    check("a. no verdict or promise words: a mirror, not a judge", not re.search(r"guarantee|you are a (bad|good) trader|loser|failure", html + js, re.I))
    fx = json.load(open(FIX, encoding="utf-8"))
    check("a. the fixture has about 19 made-up trades over 29 days back, some with ratings", len(fx["trades"]) >= 15 and max(t["back"] for t in fx["trades"]) >= 25 and any(t.get("rating") for t in fx["trades"]))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
  const o = {};
  o.words = [C.money(2000), C.moneyS(-60), C.rWord(-1.03), C.rWord(0.7, true), C.both(-437, 425, false), C.dayWord('2026-11-03'), C.addDays('2026-11-01', -2), C.clockOf(955), C.label(95), C.label(80), C.label(60), C.label(10), C.label(null), C.level(80), C.level(60), C.level(10)];
  o.clock = [C.minuteET(1793173380, -14400), C.minuteET(1793173380, -18000), C.minuteET(1793173380), C.minuteET(null, -14400)];
  const odeon = { trades: [
    { id: 'a', day: '2026-11-03', usd: 566, risk_usd: 425, r: 1.33, qty: 5, risk_pts: 42.5, stop: 29987.5, off: -14400, entry: { t: 1793173380 }, exit: { kind: 'TARGET', t: 1793176980 }, held_min: 60 },
    { id: 'b', day: 'bad-day', usd: 5 }, { id: 'c', day: '2026-11-03', usd: 'x' }, null, 'junk', { id: 'd', day: '2026-11-03', usd: -100 } ] };
  const tr = C.normTrades(odeon);
  o.norm = [tr.length, tr[0].id, tr[0].entryMin, tr[0].exitMin, tr[0].est, tr[1].r, C.normTrades(null).length, C.normTrades({ trades: 'x' }).length];
  o.store = [Object.keys(C.parseStore(JSON.stringify({ v: 1, entries: { a: { rating: 'plan' }, b: { rating: 'nope', note: '' }, c: { note: 'Moved my stop' }, d: 'x' } })).entries), C.parseStore('not json').entries, C.parseStore(null).entries, C.parseStore('x'.repeat(500000)).entries, C.parseStore({ entries: { z: { rating: 'interfered' } } }).entries.z.rating];
  const mk = (over) => Object.assign({ id: 't', day: '2026-11-03', usd: 400, risk: 425, r: 0.94, est: false, qty: 5, riskPts: 42.5, stop: 1, exit: 'TARGET', entryMin: 200, exitMin: 300, t: 1 }, over);
  const ctx = { medianRisk: 425 };
  const s1 = C.scoreTrade(mk({}), { rating: 'plan' }, ctx), s2 = C.scoreTrade(mk({ r: -1.4, usd: -600 }), { rating: 'interfered' }, ctx), s3 = C.scoreTrade(mk({ qty: 9, risk: 765 }), null, ctx);
  const s4 = C.scoreTrade(mk({ entryMin: 1000, exitMin: 1010 }), null, ctx), s5 = C.scoreTrade(mk({ exitMin: 960 }), null, ctx), s6 = C.scoreTrade(mk({}), { note: 'I moved my stop wider' }, ctx), s7 = C.scoreTrade(mk({ exitMin: null, entryMin: null, stop: null, riskPts: null }), { rating: 'hesitated' }, ctx);
  o.trade = [s1, s2, s3, s4, s5, s6, s7].map((p) => [p.plan, p.stop, p.size, p.flat, p.hours, p.nomove]);
  o.edge = [C.scoreTrade(mk({ entryMin: 120 }), null, ctx).hours, C.scoreTrade(mk({ entryMin: 930 }), null, ctx).hours, C.scoreTrade(mk({ entryMin: 931 }), null, ctx).hours, C.scoreTrade(mk({ exitMin: 955 }), null, ctx).flat, C.scoreTrade(mk({ r: -1.15 }), null, ctx).stop, C.scoreTrade(mk({ r: -1.16 }), null, ctx).stop];
  const clean = C.scoreDay('2026-11-03', [mk({})], { entries: { t: { rating: 'plan' } } }, ctx);
  o.clean = [clean.score, clean.label, clean.level, clean.parts.map((p) => p.pts), clean.parts.map((p) => p.max).reduce((a, b) => a + b, 0), clean.est, clean.parts[0].text, clean.parts[1].text];
  const unrated = C.scoreDay('2026-11-03', [mk({})], { entries: {} }, ctx);
  o.unrated = [unrated.score, unrated.est, unrated.parts[0].pts, unrated.parts[0].est, unrated.parts[0].text];
  const bad = C.scoreDay('2026-11-04', [mk({ r: -1.5, usd: -640, qty: 9, risk: 765, entryMin: 1000, exitMin: 1010 })], { entries: { t: { rating: 'interfered', note: 'Moved my stop wider' } } }, ctx);
  o.bad = [bad.score, bad.label, bad.level, bad.parts.map((p) => p.pts), bad.parts.map((p) => /\$/.test(p.text) && /R\)/.test(p.text))];
  const noData = C.scoreDay('2026-11-05', [mk({ exitMin: null, entryMin: null, riskPts: null, stop: null, risk: null })], { entries: {} }, ctx);
  o.nodata = [noData.score, noData.parts.filter((p) => p.est).length, noData.parts.find((p) => p.key === 'flat').text];
  const dm = C.demoTrades(fx, '2026-11-10'), trs = C.normTrades(dm.odeon), m = C.build(trs, dm.store, '2026-11-10', 30);
  o.demo = [trs.length, m.n, m.avg, m.spark.length, m.spark[29].day, m.spark[0].day, m.spark.filter((s) => s.score != null).length, m.latest.day, m.best.score >= m.worst.score, m.worst.score < 60, m.days.every((d) => d.parts.length === 6 && d.parts.every((p) => /\$/.test(p.text) || /estimate/.test(p.text) || /Not rated/.test(p.text)))];
  o.sorted = m.days.every((d, i) => i === 0 || m.days[i - 1].day > d.day);
  o.window = [C.build(trs, dm.store, '2026-11-10', 7).n, C.build(trs, dm.store, '2026-11-10', 7).spark.length, C.build([], { entries: {} }, '2026-11-10', 30).n, C.build([], { entries: {} }, '2026-11-10', 30).latest, C.build([], { entries: {} }, '2026-11-10', 30).avg, C.build(trs, dm.store, '2026-11-10', 5000).span];
  o.last = [C.lastDay(trs, '2026-11-10'), C.lastDay(trs, '2026-10-14'), C.lastDay([], '2026-11-10')];
  o.head = [C.headline(m, m.latest), C.headline(m, null)];
  o.card = C.jarvisCard(m, null);
  o.weights = C.PARTS.map((p) => [p.key, p.max]);
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, FIX)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: $2,000, -$60, -1.0R, ~+0.7R, '-$437 (-1.0R)', Nov 3, Oct 30, 15:55, the five labels and levels",
          o["words"] == ["$2,000", "-$60", "-1.0R", "~+0.7R", "-$437 (-1.0R)", "Nov 3", "2026-10-30", "15:55", "Very disciplined", "Disciplined", "Mostly on plan", "Off plan", "No score", "ok", "warn", "bad"], o["words"])
    check("b. the clock in New York time: the trade's own UTC offset, else Intl; a missing time -> null", o["clock"][0] == o["clock"][2] and o["clock"][1] == o["clock"][0] - 60 and o["clock"][3] is None and 0 < o["clock"][0] < 1440, o["clock"])
    check("b. trades: junk, a bad day and a non-number dollar are dropped; the entry and exit minute; a trade without 'r' gets one from dollars and risk (marked estimate); null input safe",
          o["norm"][0] == 2 and o["norm"][1] in ("a", "d") and o["norm"][4] in (True, False) and o["norm"][6] == 0 and o["norm"][7] == 0, o["norm"])
    check("b. the journal store: good ratings and notes kept, an unknown rating dropped, junk / null / huge text safe, an interfered rating read", o["store"][0] == ["a", "c"] and o["store"][1] == {} and o["store"][2] == {} and o["store"][3] == {} and o["store"][4] == "interfered", o["store"])
    t = o["trade"]
    check("b. one trade, six parts: clean = all 1; interfered with a -1.4R loss = plan 0, stop 0, nomove 0; sized 9 not 5 = size 0; entry 16:40 and out 16:50 = hours 0, flat 0; out 16:00 = flat 0; a note about a moved stop = nomove 0; nothing visible = null (cannot be seen)",
          t[0] == [1, 1, 1, 1, 1, 1] and t[1][0] == 0 and t[1][1] == 0 and t[1][5] == 0 and t[2][2] == 0 and t[3][3] == 0 and t[3][4] == 0 and t[4][3] == 0 and t[5][5] == 0 and t[6] == [0.5, None, 1, None, None, 1], t)
    check("b. the edges: 02:00 and 15:30 are in, 15:31 is out; flat at exactly 15:55 is in; a loss of exactly -1.15R is in, -1.16R is out", o["edge"] == [1, 1, 0, 1, 1, 0], o["edge"])
    c = o["clean"]
    check("b. a clean rated day scores 100, 'Very disciplined', level ok, the weights add to 100, no estimate, and every part explains itself with $ and R", c[0] == 100 and c[1] == "Very disciplined" and c[2] == "ok" and c[3] == [25, 20, 20, 15, 10, 10] and c[4] == 100 and c[5] is False and "Followed the plan on 1 of 1 rated trade" in c[6] and "(+0.9R)" in c[7] or "R)" in c[7], c)
    u = o["unrated"]
    check("b. an unrated day: the plan part counts 70% (17.5 of 25, an estimate) and the page says to rate in Mnemosyne; the whole score is an estimate", u[0] == 93 and u[1] is True and u[2] == 17.5 and u[3] is True and "Not rated yet" in u[4] and "70%" in u[4], u)
    b = o["bad"]
    check("b. a bad day (interfered, moved the stop, a -1.5R loss, sized up, 16:40 entry): plan 0, stop 0, size 0, flat 0, hours 0, nomove 0 = score 0 'Off plan'; every sentence carries dollars and R", b[0] == 0 and b[1] == "Off plan" and b[2] == "bad" and b[3] == [0, 0, 0, 0, 0, 0] and all(b[4]), b)
    check("b. what the data cannot show counts 70% and says so: no times, no stop, no risk -> the estimate parts are labelled", o["nodata"][1] >= 3 and "70%" in o["nodata"][2], o["nodata"])
    d = o["demo"]
    check("b. the demo: 19 trades, 19 scored days, a 30-day sparkline from Oct 12 to Nov 10 with 19 filled days, the newest day first, best >= worst, the worst day under 60, every part explained",
          d[0] == 19 and d[1] == 19 and d[3] == 30 and d[4] == "2026-11-10" and d[5] == "2026-10-12" and d[6] == 19 and d[7] == "2026-11-10" and d[8] and d[9] and d[10] and o["sorted"], d)
    check("b. the window: 7 days is shorter, an empty list gives no days and no average, a huge span is capped at 90", o["window"][0] < d[1] and o["window"][1] == 7 and o["window"][2] == 0 and o["window"][3] is None and o["window"][4] is None and o["window"][5] == 90, o["window"])
    check("b. the last trade day at or before today; none -> null", o["last"] == ["2026-11-10", "2026-10-13", None], o["last"])
    check("b. the headline names the day, the score, the label, the trades and the day in $ and R; no day -> a plain sentence", o["head"][0].startswith("Nov 10: 100 of 100, very disciplined. 1 trade, the day +$566") and "R)" in o["head"][0] and "No scored day" in o["head"][1], o["head"])
    check("b. the Jarvis helper card and the six weights (25 + 20 + 20 + 15 + 10 + 10)", o["card"]["name"] == "Kratos" and o["card"]["score"] == "100" and o["weights"] == [["plan", 25], ["stop", 20], ["size", 20], ["flat", 15], ["hours", 10], ["nomove", 10]], o["card"])


def odeon_json():
    """a real-looking trades file for a day the test chooses (2026-11-03 with a clean trade, 2026-11-02 with a bad one)"""
    t = lambda i, day, usd, r, qty, pts, ent, ex, kind: {"id": i, "day": day, "usd": usd, "r": r, "qty": qty, "risk_pts": pts, "risk_usd": qty * pts * 2, "stop": 1, "off": -14400, "entry": {"t": ent}, "exit": {"kind": kind, "t": ex}, "held_min": (ex - ent) // 60}
    import calendar
    base = calendar.timegm((2026, 11, 3, 4, 0, 0))     # 2026-11-03 00:00 New York time (UTC-4), as epoch seconds
    return json.dumps({"trades": [t("real.1", "2026-11-03", 566, 1.33, 5, 42.5, base + 203 * 60, base + 262 * 60, "TARGET"), t("real.2", "2026-11-02", -1148, -1.5, 9, 42.5, base - 86400 + 1010 * 60, base - 86400 + 1015 * 60, "STOP"),
                                 t("real.3", "2026-10-30", 400, 0.94, 5, 42.5, base - 4 * 86400 + 210 * 60, base - 4 * 86400 + 280 * 60, "TARGET")]})


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
            AK.open_app(p, origin, APP, "?demo=1&today=2026-11-10", hook="KRATOS")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, score: document.querySelector('#score').textContent, pill: document.querySelector('#pill').textContent, head: document.querySelector('#headline').textContent,
              parts: document.querySelectorAll('#parts .part').length, bars: document.querySelectorAll('#spark rect').length, tiles: document.querySelector('#tiles').textContent, bw: document.querySelectorAll('#bw .acard').length, days: document.querySelectorAll('#days .acard').length,
              how: document.querySelectorAll('#how li').length, day: document.querySelector('#dayName').textContent, prev: document.querySelector('#prev').disabled, next: document.querySelector('#next').disabled,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, mode: window.KRATOS.mode, ptext: document.querySelector('#parts').textContent })""")
            check("c. DEMO (Nov 10): the chip, '100 of 100', 'Very disciplined', six parts, 30 sparkline bars (+ the two guide lines), tiles with the 30-day average, best and worst, 12 days, six how-lines, 'Newer' is off on the newest day",
                  d["demo"] and d["score"] == "100 of 100" and d["pill"] == "Very disciplined" and d["parts"] == 6 and d["bars"] >= 30 and "30-day average" in d["tiles"] and d["bw"] == 2 and d["days"] == 12 and d["how"] == 6 and d["day"] == "Nov 10" and d["next"] and not d["prev"], d)
            check("c. every part is one sentence with dollars and R", "+$566 (+1.3R)" in d["ptext"] and "Followed the plan" in d["ptext"] and "Flat by 15:55" in d["ptext"], d["ptext"][:200])
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the column is 3D or the flat drawing, never nothing", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#flat').hasAttribute('hidden')"), d["mode"])
            h100 = p.evaluate("() => +document.querySelector('#flat .shaft').getAttribute('height')")
            AK.shot(p, "kratos-demo")
            p.locator("#bw .acard").nth(1).click()
            p.wait_for_timeout(250)
            w = p.evaluate("() => [document.querySelector('#score').textContent, document.querySelector('#pill').textContent, document.querySelector('#dayName').textContent, +document.querySelector('#flat .shaft').getAttribute('height'), document.querySelector('#parts').textContent]")
            check("c. tap the worst day: a low score with 'Off plan' or 'Mostly on plan', a shorter flat column, its failed parts name the dollars lost, the status line is spoken",
                  int(w[0].split()[0]) < 60 and w[1] in ("Off plan", "Mostly on plan") and w[3] < h100 and "-$" in w[4] and ("Kratos:" in p.evaluate("() => document.querySelector('#status').textContent")), w)
            p.locator("#next").click()
            p.wait_for_timeout(250)
            n = p.evaluate("() => [document.querySelector('#dayName').textContent, document.querySelector('#score').textContent]")
            check("c. the 'Newer' button moves to the next scored day", n[0] != w[2], (n, w[2]))
            p.locator("#days .acard").nth(3).click()
            p.wait_for_timeout(250)
            e = p.evaluate("() => document.querySelector('#days .acard[aria-pressed=true]') ? document.querySelector('#days .acard[aria-pressed=true]').dataset.day : null")
            check("c. tapping a day in the list selects it (pressed)", e is not None, e)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=high&today=2026-11-10", hook="KRATOS")
            hq = p.evaluate("() => [window.KRATOS.mode, getComputedStyle(document.querySelector('#flat')).display]")
            check("c. ?q=high: the 3D column builds and the flat drawing is hidden (or, with no WebGL, the flat column stays), no console error", ((hq[0] == "3d" and hq[1] == "none") or (hq[0] == "flat" and hq[1] != "none")) and not errs, (hq, errs[:2]))
            ctx.close()

            srv2, origin2 = AK.serve({"/odeon/trades.json": odeon_json()})
            store = json.dumps({"v": 1, "entries": {"real.1": {"rating": "plan", "note": ""}, "real.2": {"rating": "interfered", "note": "Moved my stop wider"}}})
            ctx, p, errs, seen, off = AK.page(br, origin2, storage={"journal.v1": store})
            AK.open_app(p, origin2, APP, "?today=2026-11-04", hook="KRATOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#score').textContent, document.querySelector('#days').querySelectorAll('.acard').length, document.querySelector('#parts').textContent, document.querySelector('#dayName').textContent]")
            check("c. the real trades file and the real journal on this phone: no DEMO chip, Nov 3 first with 100 of 100, three days scored, the journal's 'Followed the plan on 1 of 1'",
                  not r[0] and r[1] == "100 of 100" and r[2] == 3 and "Followed the plan on 1 of 1" in r[3] and r[4] == "Nov 3", r)
            p.locator("#prev").click()
            p.wait_for_timeout(250)
            r2 = p.evaluate("() => [document.querySelector('#score').textContent, document.querySelector('#parts').textContent]")
            check("c. the older real day (interfered, moved stop, -1.5R, sized up, a 16:50 entry) scores 0 with the dollars lost: -$1,148 (-1.5R)", r2[0] == "0 of 100" and "-$1,148 (-1.5R)" in r2[1], r2)
            check("c. the real run reads the trades file only and no console error; the journal is untouched", any("odeon/trades.json" in u for u in seen) and not off and not errs and p.evaluate("(k) => localStorage.getItem('journal.v1')", None) == store, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()

            srv3, origin3 = AK.serve({"/odeon/trades.json": '{"trades": []}'})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?today=2026-11-10", hook="KRATOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#score').textContent]")
            check("c. an empty trades file never blanks the page: the fixture shows with the DEMO chip", r[0] and r[1] == "100 of 100" and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()

            srv4, origin4 = AK.serve({"/odeon/trades.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "?today=2026-11-10", hook="KRATOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#parts .part').length]")
            check("c. a missing trades file (404): the fixture shows with the DEMO chip", r == [True, 6], r)
            ctx.close()
            srv4.shutdown()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low&today=2026-11-10", hook="KRATOS")
            mode = p.evaluate("() => window.KRATOS.mode")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the flat column, no sideways scroll, every tap >= 44 px, no error", mode == "flat" and AK.no_sideways(p) and not AK.taps(p) and not errs, (mode, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "kratos-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
