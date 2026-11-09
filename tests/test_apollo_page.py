"""APOLLO, the OLYMPUS weekly review (tools/web_public/apollo/, AGORA look, 2026-11-09): this week's trades, right / wrong, discipline from Mnemosyne's card, the ONE rule.

  a. static: the files, the kit lines, the AGORA look, read-only (it only READS 'journal.card.v1'), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (apollocore.js): weeks and Mondays, the summary, every right / wrong line, the card parser (hostile input), the rule ladder (every branch)
  c. Chromium 390 x 844 (and 375 x 667): the DEMO week, the real odeon/trades.json, Mnemosyne's card from localStorage, switching week, LITE / reduced motion, taps >= 44 px, no console error
    python -X utf8 -m tests.test_apollo_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "apollo", "Apollo"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../odeon/trades.json",), storage="read")
    js = AK.read(os.path.join(AK.WEB, APP, "apollo.js")) + AK.read(os.path.join(AK.WEB, APP, "apollocore.js"))
    check("a. Apollo only READS Mnemosyne's card (localStorage.getItem('journal.card.v1')): it never writes any storage, cookie or database",
          "localStorage.getItem('journal.card.v1')" in js and not re.search(r"localStorage\.(setItem|removeItem|clear)|sessionStorage|indexedDB|document\.cookie", js))
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page order: weeks, the week in one line, right, wrong, discipline, the ONE rule; a link to Mnemosyne",
          html.index('id="weeks"') < html.index('id="hero"') < html.index('id="right"') < html.index('id="wrong"') < html.index('id="discCard"') < html.index('id="ruleCard"') and 'href="../journal/"' in html)
    fx = json.loads(AK.read(os.path.join(AK.WEB, APP, "fixture.json")))
    check("a. the fixture: two weeks of made-up trades with R, and a made-up Mnemosyne card", len(fx["trades"]) >= 8 and {t["wk"] for t in fx["trades"]} == {0, -1} and all("r" in t for t in fx["trades"]) and fx["card"]["lines"][1].startswith("Next week:"))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.words = [C.money(-437), C.moneyS(566), C.rWord(1.33), C.rWord(-1.03), C.rWord(0), C.rWord(0.7, true), C.both(687, 1.61, false), C.both(-12, null, false)];
  o.dates = [C.mondayOf('2026-11-09'), C.mondayOf('2026-11-15'), C.mondayOf('2026-11-12'), C.addDays('2026-11-30', 1), C.addDays('2026-03-01', -1), C.dayWord('2026-11-09'), C.dayWord('bad')];
  const fx = { trades: [
    { wk: 0, dow: 0, side: 'LONG', usd: 566, r: 1.33, risk_usd: 425, mfe_r: 1.4, held_min: 60, exit: { kind: 'TARGET' } }, { wk: 0, dow: 1, side: 'SHORT', usd: -437, r: -1.03, risk_usd: 425, mfe_r: 0.3, held_min: 19, exit: { kind: 'STOP' } },
    { wk: 0, dow: 1, side: 'LONG', usd: -12, r: -0.03, risk_usd: 425, mfe_r: 1.1, held_min: 40, exit: { kind: 'BE' } }, { wk: 0, dow: 2, side: 'SHORT', usd: 640, r: 1.5, risk_usd: 425, mfe_r: 1.6, held_min: 90, exit: { kind: 'TARGET' } },
    { wk: 0, dow: 3, side: 'LONG', usd: -380, r: -0.89, risk_usd: 425, mfe_r: 0.3, held_min: 15, exit: { kind: 'CUT' } }, { wk: 0, dow: 3, side: 'SHORT', usd: 310, r: 0.73, risk_usd: 425, mfe_r: 2.4, held_min: 220, exit: { kind: 'FLAT' } },
    { wk: -1, dow: 0, side: 'LONG', usd: 412, r: 0.97, risk_usd: 425, mfe_r: 1.1, held_min: 80, exit: { kind: 'TARGET' } }, { wk: -1, dow: 2, side: 'SHORT', usd: -560, r: -1.32, risk_usd: 425, mfe_r: 0.1, held_min: 12, exit: { kind: 'STOP' } },
    { wk: -1, dow: 4, side: 'LONG', usd: 319, r: 0.75, risk_usd: 425, mfe_r: 0.9, held_min: 110, exit: { kind: 'FLAT' } }] };
  const T = C.demoTrades(fx, '2026-11-11'), W = C.weeks(T);
  o.weeks = { n: T.length, w: W.map((w) => [w.from, w.to, w.trades.length, w.label]), pick: [C.pickWeek(W, '2026-11-11'), C.pickWeek(W, '2026-11-02'), C.pickWeek(W, '2027-01-01'), C.pickWeek([], '2026-11-11')], asc: W[0].trades.every((t, i, a) => i === 0 || a[i - 1].day <= t.day) };
  const s0 = C.summarize(W[0].trades), s1 = C.summarize(W[1].trades), se = C.summarize([]);
  o.s0 = [s0.n, s0.wins, s0.losses, s0.be, s0.winPct, s0.net, s0.netR, s0.pf, s0.best.usd, s0.worst.usd, s0.gaveBack.length, s0.bigLoss.length, s0.avgHold, JSON.stringify(s0.exits), s0.byDay.map((d) => d.usd).join(',')];
  o.s1 = [s1.n, s1.net, s1.netR, s1.bigLoss.length, s1.pf, s1.byDay.map((d) => d.n).join('')];
  o.se = [se.n, se.net, se.pf, se.winPct, se.best, se.worst, C.notes(se, []).right.length, C.notes(se, []).wrong.length];
  const n0 = C.notes(s0, W[0].trades), n1 = C.notes(s1, W[1].trades);
  o.n0 = { right: n0.right, wrong: n0.wrong };
  o.n1 = { right: n1.right.length, wrong: n1.wrong };
  // the card parser: hostile input
  const good = { v: 1, name: 'MNEMOSYNE', status: { level: 'ok', label: 'x' }, kpis: [{ label: 'Rated', value: '11 of 14' }, { label: '', value: 'x' }, 7], lines: ['You interfered on 2 of your last 9 trades, it cost $838.', 'Next week: once I am in <b>I do not touch</b> the stop', 5], t: 1 };
  const c = C.parseCard(JSON.stringify(good));
  o.card = { name: c.name, kpis: c.kpis.length, lines: c.lines.length, rule: c.rule, lvl: c.status.level, tags: JSON.stringify(c).includes('<') };
  o.evil = [C.parseCard(null), C.parseCard('not json'), C.parseCard('{"v":2,"lines":["a"]}'), C.parseCard({ v: 1, lines: 'x' }), C.parseCard({ v: 1, lines: [], kpis: [] }), C.parseCard('x'.repeat(30000)), C.parseCard({ v: 1, lines: ['ok'], status: { level: 'neon' } }).status.level, C.parseCard({ v: 1, lines: ['a', 'b', 'c', 'd', 'e'] }).lines.length, C.parseCard({ v: 1, lines: ['a'.repeat(500)] }).lines[0].length];
  // the rule ladder
  const base = (x) => ({ n: 3, net: 100, bigLoss: [], gaveBack: [], ...x });
  o.rule = [C.oneRule(s0, c).id, C.oneRule(s0, null).id, C.oneRule(s1, null).id, C.oneRule(se, null).id, C.oneRule(base({ gaveBack: [1, 2] }), null).id, C.oneRule(base({ net: -50 }), null).id, C.oneRule(base({}), null).id, C.oneRule(base({}), { rule: '' }).id];
  o.ruleText = [C.oneRule(s0, c).text, C.oneRule(s0, null).text.slice(0, 20)];
  const card = C.jarvisCard(s0, W[0], C.oneRule(s0, null));
  o.jc = [card.name, card.status.level, card.kpis.map((k) => k.value).join('|'), card.lines.map((l) => l.length <= 120).join(), card.lines[1].startsWith('Next week: ')];
  const junk = C.normTrades({ trades: [null, { day: 'x', usd: 1 }, { day: '2026-11-09', usd: 'z' }, { day: '2026-11-09', usd: 50, risk_usd: 100, id: 'a<b>' }, { day: '2026-11-09', usd: -10, r: -0.5, entry: { t: 5 } }] });
  o.junk = [junk.length, junk.map((t) => [t.r, t.est]), junk[0].id];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. money words with their R: -$437, +$566, +1.3R, -1.0R, 0.0R, ~+0.7R, '+$687 (+1.6R)', and no R at all -> 0.0R",
          o["words"] == ["-$437", "+$566", "+1.3R", "-1.0R", "0.0R", "~+0.7R", "+$687 (+1.6R)", "-$12 (0.0R)"], o["words"])
    check("b. dates: Monday of a Monday / Sunday / Thursday, a month and a leap-free February step, 'Nov 9', junk -> empty", o["dates"] == ["2026-11-09", "2026-11-09", "2026-11-09", "2026-12-01", "2026-02-28", "Nov 9", ""], o["dates"])
    w = o["weeks"]
    check("b. the fixture becomes real dates; two weeks Monday-Sunday, newest first, trades oldest-to-newest inside a week; the week that holds today opens (else the newest, an empty list -> 0)",
          w["n"] == 9 and w["w"] == [["2026-11-09", "2026-11-15", 6, "Week of Nov 9"], ["2026-11-02", "2026-11-08", 3, "Week of Nov 2"]] and w["pick"] == [0, 1, 0, 0] and w["asc"], w)
    s = o["s0"]
    check("b. a week in numbers: 6 trades, 3 won / 3 lost (the -$12 breakeven exit is a tiny loss), 50%, +$687, +1.6R, PF 1.83, best $640, worst -$437, one trade that gave back 1.5R+, no loss past 1.25R, the exits and the $ per day",
          s[:14] == [6, 3, 3, 0, 50, 687, 1.61, 1.83, 640, -437, 1, 0, 74, '{"TARGET":2,"STOP":1,"BE":1,"CUT":1,"FLAT":1}'] and s[14] == "566,-449,640,-70,0", s)
    x = o["s1"]
    check("b. last week: +$171, +0.4R, one loss past 1.25R, PF 1.31; the empty week is all zero, never a division error", x == [3, 171, 0.4, 1, 1.31, "10101"] and o["se"] == [0, 0, 0, None, None, None, 1, 0], (x, o["se"]))
    n = o["n0"]
    check("b. right: the week's money with R, the best trade with its exit, 'every loss stayed near 1R', breakeven, targets",
          n["right"][0] == "The week made +$687 (+1.6R) from 6 trades." and n["right"][1].startswith("Best trade: short on Nov 11, +$640 (+1.5R) (it reached its target)") and "3 of 3" in n["right"][2] and n["right"][3].startswith("1 trade closed at breakeven") and n["right"][4] == "2 trades reached the target.", n["right"])
    check("b. wrong: the worst trade with $ and R and how it ended, the trade that gave back 1.5R, no scolding about the bot; last week names the loss past 1.25R and the fills",
          n["wrong"][0] == "Worst trade: short on Nov 10, -$437 (-1.0R) (it was stopped out)." and "gave a lot of it back" in n["wrong"][1] and len(n["wrong"]) == 2 and any("bigger than 1.25R" in t and "-$560 (-1.3R)" in t and "Check the fills" in t for t in o["n1"]["wrong"]), (n["wrong"], o["n1"]))
    c = o["card"]
    check("b. Mnemosyne's card: 2 lines kept, the bad kpis dropped, tags stripped, 'Next week:' becomes the rule", c["name"] == "MNEMOSYNE" and c["kpis"] == 1 and c["lines"] == 2 and c["rule"] == "once I am in I do not touch the stop" and not c["tags"] and c["lvl"] == "ok", c)
    check("b. a hostile card: null, text, wrong version, lines not a list, nothing in it, 30 KB of junk -> none; an unknown level -> off; at most 3 lines; each line cut at 160", o["evil"] == [None, None, None, None, None, None, "off", 3, 160], o["evil"])
    check("b. the ONE rule ladder: your own rule first, then fills (a big loss), hold (two gave back), size (losing week), quiet (no trades), steady; an empty own rule is ignored",
          o["rule"] == ["journal", "steady", "fills", "quiet", "hold", "size", "steady", "steady"] and o["ruleText"][0] == "Once I am in I do not touch the stop" and o["ruleText"][1] == "Keep doing nothing: ", (o["rule"], o["ruleText"]))
    check("b. the Jarvis card: Apollo, green for a winning week, '+$687 | +1.6R | 6', every line <= 120, the second line is the rule", o["jc"] == ["Apollo", "ok", "+$687|+1.6R|6", "true,true", True], o["jc"])
    check("b. junk trade rows are dropped (2 of 5 kept), a missing R is estimated from the risk ($50 / $100 = ~0.5R) and flagged, tags in ids are stripped", o["junk"][0] == 2 and sorted(o["junk"][1]) == [[-0.5, False], [0.5, True]] and "<" not in o["junk"][2], o["junk"])


def trades_file():
    import datetime
    mon = datetime.date.fromisoformat("2026-11-09")
    rows = [(0, 566, 1.33, "TARGET"), (1, -437, -1.03, "STOP"), (2, 640, 1.5, "TARGET")]
    return json.dumps({"app": "odeon", "trades": [{"id": f"real.{i}", "day": str(mon + datetime.timedelta(days=d)), "side": "LONG", "qty": 5, "usd": u, "r": r, "risk_usd": 425, "mfe_r": 1.0, "exit": {"kind": k}, "entry": {"t": 1793000000 + i}} for i, (d, u, r, k) in enumerate(rows)]})


CARD = json.dumps({"v": 1, "name": "MNEMOSYNE", "status": {"level": "ok", "label": "x"}, "kpis": [{"label": "Rated", "value": "3 of 3"}], "lines": ["You followed the plan on all 3 trades.", "Next week: no new trades after a loss"], "t": 5})


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
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-11T15:00:00Z")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, chips: [...document.querySelectorAll('#weeks button')].map((b) => b.textContent), on: document.querySelector('#weeks [aria-pressed=true]').textContent, big: document.querySelector('#big').textContent,
              right: document.querySelectorAll('#right li').length, wrong: document.querySelectorAll('#wrong li').length, disc: document.querySelector('#discCard').innerText, rule: document.querySelector('#ruleText').textContent, note: document.querySelector('#discNote').textContent,
              bars: document.querySelectorAll('#bars rect').length, h1: document.querySelectorAll('h1').length, font: getComputedStyle(document.querySelector('h1')).fontFamily, reads: performance.getEntriesByType('resource').filter((r) => /trades\\.json/.test(r.name)).length }) """)
            check("c. DEMO (?demo=1): the chip, two weeks to pick (this week on), '+$687 (+1.6R)', right and wrong lists, five day bars, the example Mnemosyne card, the rule from it, never reads the real file",
                  d["demo"] and d["chips"] == ["Week of Nov 9", "Week of Nov 2"] and d["on"] == "Week of Nov 9" and d["big"] == "+$687 (+1.6R)" and d["right"] == 5 and d["wrong"] == 2 and "You interfered on 2" in d["disc"] and d["rule"] == "Once I am in, I do not touch the stop or the target"
                  and "Example journal" in d["note"] and d["bars"] == 5 and d["h1"] == 1 and d["reads"] == 0, d)
            check("c. AGORA look: serif title", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")))
            AK.shot(p, "apollo-demo")
            p.locator("#weeks button").nth(1).click()
            p.wait_for_timeout(150)
            w = p.evaluate("() => ({ h: document.querySelector('#weekH').textContent, big: document.querySelector('#big').textContent, wrong: document.querySelector('#wrong').textContent, status: document.querySelector('#status').textContent })")
            check("c. tap last week: +$171 (+0.4R), the big loss past 1.25R is named, the status line is spoken", w["big"] == "+$171 (+0.4R)" and "bigger than 1.25R" in w["wrong"] and "Week of Nov 2" in w["status"], w)
            check("c. every tap target is at least 44 x 44 px", not AK.taps(p), AK.taps(p)[:4])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # ---- the real trades + the owner's own Mnemosyne card in localStorage
            srv2, origin2 = AK.serve({"/odeon/trades.json": trades_file()})
            ctx, p, errs, seen, off = AK.page(br, origin2, storage={"journal.card.v1": CARD})
            AK.open_app(p, origin2, APP, "?at=2026-11-11T15:00:00Z")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, big: document.querySelector('#big').textContent, disc: document.querySelector('#discCard').innerText, rule: document.querySelector('#ruleText').textContent, note: document.querySelector('#discNote').textContent,
              ls: Object.keys(localStorage).filter((k) => /journal|apollo/.test(k)) })""")
            check("c. the real trades file: no DEMO chip, '+$769 (+1.8R)', Mnemosyne's card from this phone (not the example), the owner's own rule, and Apollo wrote nothing to storage",
                  not r["demo"] and r["big"] == "+$769 (+1.8R)" and "followed the plan on all 3" in r["disc"] and r["rule"] == "No new trades after a loss" and "From your Mnemosyne" in r["note"] and r["ls"] == ["journal.card.v1"], r)
            check("c. it read the site's trades file and nothing off the origin", any("odeon/trades.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=2026-11-11T15:00:00Z")
            n = p.evaluate("() => [document.querySelector('#discCard').innerText, document.querySelector('#ruleText').textContent]")
            check("c. real trades but no Mnemosyne journal on this phone: a friendly line to start one, and a rule from the week's facts", "No journal yet" in n[0] and "Mnemosyne" in n[0] and len(n[1]) > 10, n)
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/odeon/trades.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "")
            srv3.shutdown()
            e = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#big').textContent]")
            check("c. no trades file on the site: the DEMO week appears by itself, never blank", e[0] and e[1].startswith(("+$", "-$", "$")) and len(e[1]) > 4, e)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
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
