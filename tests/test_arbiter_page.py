"""ARBITER, money machine #5 (tools/money/arbiter.py + tools/web_public/arbiter/, AGORA look, 2026-11-10): a PAPER-ONLY spread and funding finder.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture (equal to the scanner's own sample output), the data contract
  b. the scanner (tools/money/arbiter.py --selftest and --fixture --out) and the page maths in node (arbitercore.js): clean, scales, paper marks, Jarvis card
  c. Chromium 390 x 844 (and 375 x 667): DEMO page, the scales tilt, pick an idea, filter, open and close a paper position, the real ../money/arbiter.json, LITE / reduced motion, taps, no sideways scroll
    python -X utf8 -m tests.test_arbiter_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "arbiter", "Arbiter"
check = AK.check
PY = os.path.join(AK.ROOT, "tools", "money", "arbiter.py")


def test_static():
    AK.static_kit(APP, NAME, reads=("../money/arbiter.json",), storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "arbiter.js")) + AK.read(os.path.join(d, "arbitercore.js"))
    check("a. browser storage only for the paper positions (one key, try/catch), nothing else is kept", len(re.findall(r"localStorage\.", js)) == 2 and "sessionStorage" not in js and "indexedDB" not in js and "arbiter.paper.v1" in js)
    check("a. it never trades: no order / key / wallet / sign words in the page code", not re.search(r"api[_-]?key|secret|wallet|private key|place_?order|new_?order|signTransaction", js, re.I))
    py = AK.read(PY)
    check("a. the scanner is stdlib only, paper only, never POSTs and never reads a key", not re.search(r"^\s*(import|from)\s+(requests|aiohttp|ccxt|numpy|pandas)", py, re.M) and 'mode": "paper"' in py and not re.search(r"method\s*=\s*['\"]POST|api[_-]?key", py.split("def selftest")[0], re.I))
    check("a. the scanner never touches the trading bot: no import of engine / live_model", not re.search(r"\bengine\b\s*import|import\s+engine|live_model", py))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. page order: best idea, the scales, the list, the idea in full, paper positions, the cautions", html.index('id="headline"') < html.index('id="scales"') < html.index('id="list"') < html.index('id="selWhy"') < html.index('id="pos"') < html.index('id="notes"'))
    check("a. the words 'Why this usually disappears' and the exchange-risk warning are on the page, and the paper-only warning is up top", "Why this usually disappears" in html and "Exchange and loss risk" in html and html.index("Paper only") < html.index('id="scales"'))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    out = subprocess.run([sys.executable, PY, "--fixture", "--out", tempfile.mkdtemp(prefix="arb-")], capture_output=True, text=True, timeout=60)
    check("a. the scanner runs offline with --fixture", out.returncode == 0 and "Best paper idea" in out.stdout, out.stderr[-300:])
    tmp = tempfile.mkdtemp(prefix="arb-")
    subprocess.run([sys.executable, PY, "--fixture", "--out", tmp], capture_output=True, timeout=60)
    fresh = json.load(open(os.path.join(tmp, "arbiter.json"), encoding="utf-8"))
    check("a. the page's fixture.json equals the scanner's own sample output (regenerate it with --fixture when the maths change)", fresh == fx, "run: python tools/money/arbiter.py --fixture --out tools/web_public/arbiter && mv arbiter.json fixture.json")
    check("a. the data contract: v 1, id arbiter, mode paper, status sample, headline text + usd_month, items with title / detail / usd / score / risk", fx["v"] == 1 and fx["id"] == "arbiter" and fx["mode"] == "paper" and fx["status"] == "sample" and fx["headline"]["usd_month"] > 0
          and all(all(k in i for k in ("title", "detail", "usd", "score", "risk", "why", "warning", "net_apr", "hurdle_apr")) for i in fx["items"]))


def test_scanner():
    r = subprocess.run([sys.executable, PY, "--selftest"], capture_output=True, text=True, timeout=120)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    check("b. tools/money/arbiter.py --selftest passes (funding, peg and two-venue maths, junk input, the contract)", r.returncode == 0 and "passed" in last, r.stdout[-500:] + r.stderr[-300:])


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.words = [C.money(1234.4), C.moneyS(-60), C.money2(5.4), C.pct(2.256, 2), C.aprText(22.7), C.aprText(145.2), C.daysText(1), C.daysText(30), C.riskWord('med'), C.ago('2026-11-10T06:00:00Z', Date.parse('2026-11-10T09:00:00Z'))];
  const raw = { v: 1, status: 'ok', asof: '2026-11-10T06:00:00Z', headline: { text: 'Best <b>idea</b>', usd_month: 12 }, notes: ['n1', 5, '<i>x</i>'], items: [
    { kind: 'funding', title: 'A', detail: 'd', usd: 20, net_apr: 24, hurdle_apr: 8, score: 70, risk: 'med', gain_usd: 6, cost_usd: 2, hold_days: 30, capital_usd: 1000, exposed_usd: 1000, gain_pct: 0.6, cost_pct: 0.2, why: 'w', warning: 'x' },
    { kind: 'peg', title: 'B', usd: 5, net_apr: 3, hurdle_apr: 8, score: 900, risk: 'weird', hold_days: 'x' },
    { kind: 'nope', title: 'C', usd: 1, net_apr: 1 }, null, 7, { kind: 'venues', title: '', usd: 1, net_apr: 1 }, { kind: 'venues', title: 'D', usd: 'x', net_apr: 1 }] };
  const c = C.clean(raw);
  o.clean = [c.items.length, c.items[1].risk, c.items[1].score, c.items[1].hold_days, c.headline, c.notes, c.demo, c.status, C.clean(null).items.length, C.clean(null).demo, C.clean({ items: 'x' }).status, C.clean({ status: 'ok' }).demo];
  const A = c.items[0], B = c.items[1];
  o.beats = [C.beats(A), C.beats(B), C.verdict(A).startsWith('It beats the bar'), C.verdict(B).startsWith('It does not clear the bar'), C.verdict(null)];
  o.filter = [C.filterItems(c.items, 'peg').length, C.filterItems(c.items, 'all').length, C.filterItems(c.items, 'funding')[0].title];
  const g1 = C.scaleGeo(10, 5, 100, 80, 60), g2 = C.scaleGeo(5, 10, 100, 80, 60), g3 = C.scaleGeo(7, 7, 100, 80, 60), g4 = C.scaleGeo(0, 0, 100, 80, 60), g5 = C.scaleGeo(1000, 1, 100, 80, 60);
  o.geo = [g1.angle > 0, g1.left.y > g1.right.y, g1.heavier, g1.coinsL, g1.coinsR, g2.angle < 0, g2.left.y < g2.right.y, g2.heavier, g3.angle, g3.heavier, g4.coinsL, g4.coinsR, g5.coinsR, g5.coinsL, Math.abs(g5.angle) <= C.MAX_TILT,
    Math.round(Math.hypot(g1.right.x - g1.left.x, g1.right.y - g1.left.y)), Math.round(g3.left.x), Math.round(g3.left.y)];
  const sc = C.scalesFor(A);
  o.scales = [sc.a.left, sc.a.right, sc.b.left, sc.b.right, sc.a.labelL, sc.b.labelR, sc.a.line.includes('$6.00') && sc.a.line.includes('estimate'), C.scalesFor(null)];
  const p = C.newPosition(A, 1000000, 1000), t0 = p.opened;
  o.pos = [p.title, p.capital, p.exposed, p.entry_apr, C.newPosition(null, 1, 1), C.cleanPositions([p, { title: 5 }, null, { title: 'q', opened: 'x', capital: 1 }]).length, C.cleanPositions('x').length];
  const day = 86400000, m0 = C.markPosition(p, c.items, t0), m15 = C.markPosition(p, c.items, t0 + 15 * day), m30 = C.markPosition(p, c.items, t0 + 30 * day), m60 = C.markPosition(p, c.items, t0 + 60 * day);
  o.mark = [Math.round(m0.net * 100) / 100, Math.round(m15.net * 100) / 100, Math.round(m30.net * 100) / 100, Math.round(m60.net * 100) / 100, m0.state, m30.done, m60.done, m15.words.startsWith('Still there')];
  const gone = C.markPosition(p, [], t0), dead = C.markPosition(p, [{ ...A, net_apr: -1 }], t0), narrow = C.markPosition(p, [{ ...A, net_apr: 5 }], t0);
  o.states = [gone.state, dead.state, narrow.state, gone.words.includes('Close it on paper'), narrow.words.includes('narrowed')];
  const tot = C.totals([p, p], c.items, t0 + 30 * day);
  o.totals = [tot.n, Math.round(tot.net * 100) / 100, tot.exposed];
  const card = C.jarvisCard(c, 1793394000), empty = C.jarvisCard(C.clean({ status: 'ok', items: [] }), 5), demo = C.jarvisCard(C.clean({ status: 'sample', items: raw.items }), 5);
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.kpis[1].value, card.kpis[2].value, card.lines.length, Number.isInteger(card.t), empty.status.level, empty.kpis[1].value, demo.status.level];
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
    check("b. words: $1,234, -$60, $5.40, 2.26%, 22.7% a year, 145% a year, 1 day, 30 days, Medium risk, '3 hours ago'",
          o["words"] == ["$1,234", "-$60", "$5.40", "2.26%", "22.7% a year", "145% a year", "1 day", "30 days", "Medium risk", "3 hours ago"], o["words"])
    check("b. clean: junk items (wrong kind, no title, null, text money) dropped; unknown risk -> high; score and days clamped; no < > in text; notes filtered; an ok scan is not demo; null -> a sample",
          o["clean"] == [2, "high", 100, 1, "Best bidea/b", ["n1", "ix/i"], False, "ok", 0, True, "sample", False], o["clean"])
    check("b. beats the bar: 24% against 8% yes, 3% against 8% no, with plain verdict sentences", o["beats"] == [True, False, True, True, "Pick an idea to weigh it."], o["beats"])
    check("b. the kind filter", o["filter"] == [1, 2, "A"], o["filter"])
    check("b. scale geometry: the heavier side goes down, up to 14 degrees; equal = level; empty = no coins; coins 1..8; the beam keeps its length (120)",
          o["geo"] == [True, True, "left", 8, 4, True, True, "right", 0, "even", 0, 0, 1, 8, True, 120, 40, 80], o["geo"])
    check("b. scales for an idea: A weighs $6.00 earned against $2.00 costs, B weighs 24% against the 8% bar; the null idea has none", o["scales"][:7] == [6, 2, 24, 8, "Earns $6.00", "Bar 8%", True] and o["scales"][7] is None, o["scales"])
    check("b. a paper position keeps the entry numbers; junk positions are dropped", o["pos"][:4] == ["A", 1000, 1000, 24] and o["pos"][4] is None and o["pos"][5] == 1 and o["pos"][6] == 0, o["pos"])
    check("b. the mark: day 0 is the entry cost (-$2.00), half way -$2 + $3 = +$1.00, a full hold +$4.00, and it stops growing after the hold (it is carry earned minus costs paid)",
          o["mark"] == [-2, 1, 4, 4, "open", True, True, True], o["mark"])
    check("b. a spread that is gone, no longer beats its costs, or has halved says so in plain words (close it on paper)", o["states"] == ["gone", "gone", "narrow", True, True], o["states"])
    check("b. totals add up: two positions, +$8.00, $2,000 on exchanges", o["totals"] == [2, 8, 2000], o["totals"])
    check("b. the Jarvis card: Arbiter, ok, 3 kpis (ideas 2, the top-scored idea's yearly % and monthly $), 2 lines, integer t; no ideas -> warn; sample -> off",
          o["card"] == ["Arbiter", "ok", 3, "2", "3%", "$5", 2, True, "warn", "0%", "off"], o["card"])


def live_json():
    fx = json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8"))
    fx.pop("demo", None)
    fx.pop("note", None)
    fx["status"] = "ok"
    fx["asof"] = "2099-01-01T00:00:00Z"
    fx["items"] = fx["items"][:2]
    fx["items"][0]["title"] = "Live test idea (Binance)"
    fx["headline"]["text"] = "Live test headline."
    return json.dumps(fx)


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
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#headline').textContent, pill: document.querySelector('#statusPill').textContent, warn: document.querySelector('#paperWarn').textContent,
              ideas: document.querySelectorAll('#list .idea').length, kinds: [...document.querySelectorAll('#kinds button')].map((b) => b.textContent), svg: !!document.querySelector('#scales svg'), aa: document.querySelector('#scales svg').dataset.angleA, ab: document.querySelector('#scales svg').dataset.angleB,
              coins: document.querySelector('#scales svg').dataset.coins, pans: document.querySelectorAll('#scales svg ellipse').length, why: document.querySelector('#selWhy').textContent.length, warnr: document.querySelector('#selWarn').textContent,
              tiles: document.querySelector('#selTiles').textContent, kv: document.querySelector('#selKv').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, notes: document.querySelectorAll('#notes li').length,
              empty: document.querySelector('#pos').textContent })""")
            check("c. DEMO: the chip, 'Sample data', the headline says estimate, the paper-only warning, seven ideas, four chips (All 7, Funding, Pegs, Two venues)",
                  d["demo"] and d["pill"] == "Sample data" and "estimate" in d["head"] and "Paper only" in d["warn"] and d["ideas"] == 7 and d["kinds"][0] == "All 7" and len(d["kinds"]) == 4, d)
            check("c. two marble scales are drawn (SVG, many shapes), tilted, with coin stacks; the idea in full has a why, an exchange warning, the money left on the exchange and 'estimate'",
                  d["svg"] and d["pans"] >= 8 and float(d["aa"]) != 0 and float(d["ab"]) != 0 and len(d["coins"].split(",")) == 4 and d["why"] > 40 and "exchange" in d["warnr"].lower() and "estimate" in d["tiles"] and "Left on an exchange or venue$1,000" in d["kv"], d)
            check("c. AGORA look: serif title, warm dark body; a paper list that starts empty with a plain sentence", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)" and "No paper positions yet" in d["empty"], d)
            AK.shot(p, "arbiter-demo")
            p.locator("#list .idea").nth(1).click()
            p.wait_for_timeout(800)
            s = p.evaluate("() => [document.querySelector('#selTitle').textContent, document.querySelectorAll('#list .idea[aria-pressed=true]').length, document.querySelector('#status').textContent]")
            first = p.evaluate("() => window.ARBITER.S.data.items[1].title")
            check("c. tap the second idea: the full card and the spoken status line follow it", s[0] == first and s[1] == 1 and first[:20] in s[2] and "Paper only" in s[2], s)
            p.locator("#kinds [data-kind=peg]").click()
            p.wait_for_timeout(700)
            k = p.evaluate("() => [document.querySelectorAll('#list .idea').length, document.querySelector('#selTitle').textContent, document.querySelector('#kinds [aria-pressed=true]').textContent]")
            check("c. the Pegs chip keeps only peg ideas (one in the sample) and moves the scales to it", k[0] == 1 and "peg gap" in k[1] and k[2].startswith("Pegs"), k)
            p.locator("#kinds [data-kind=all]").click()
            p.locator("#openBtn").click()
            p.wait_for_timeout(300)
            o1 = p.evaluate("() => ({ rows: document.querySelectorAll('#pos .posrow').length, txt: document.querySelector('#pos').textContent, btn: document.querySelector('#openBtn').textContent, dis: document.querySelector('#openBtn').disabled, store: localStorage.getItem('arbiter.paper.v1'), note: document.querySelector('#trNote').textContent })")
            check("c. open a $1,000 paper position: one row marked 'so far' (starts at the entry cost, a minus), the button says 'Already open on paper', the note adds it up and says it is an estimate, 'No money moved'",
                  o1["rows"] == 1 and "so far" in o1["txt"] and "-$" in o1["txt"] and o1["btn"] == "Already open on paper" and o1["dis"] and o1["store"] and "estimate" in o1["note"], o1)
            p.reload()
            p.wait_for_function("window.ARBITER && window.ARBITER.ready()", timeout=60000)
            p.wait_for_timeout(500)
            n = p.evaluate("() => document.querySelectorAll('#pos .posrow').length")
            check("c. the paper position survives a reload (this browser only)", n == 1, n)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, the idea rows, the open and close buttons)", not t, t[:5])
            p.locator("#pos .posrow button").first.click()
            p.wait_for_timeout(200)
            c0 = p.evaluate("() => [document.querySelectorAll('#pos .posrow').length, document.querySelector('#pos').textContent]")
            check("c. 'Close on paper' removes it and the empty sentence returns", c0[0] == 0 and "No paper positions yet" in c0[1], c0)
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            srv2, origin2 = AK.serve({"/money/arbiter.json": live_json()})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#headline').textContent, pill: document.querySelector('#statusPill').textContent, ideas: document.querySelectorAll('#list .idea').length, sel: document.querySelector('#selTitle').textContent })")
            check("c. the real ../money/arbiter.json: no DEMO chip, 'Live scan', its own headline and its two ideas", not r["demo"] and r["pill"] == "Live scan" and r["head"] == "Live test headline." and r["ideas"] == 2 and r["sel"] == "Live test idea (Binance)", r)
            check("c. the real run reads only the site's files and no console error", any("money/arbiter.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/money/arbiter.json": "{ not json"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "")
            b = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#list .idea').length]")
            check("c. a broken scan file never blanks the page: it falls back to the sample (DEMO, seven ideas)", b == [True, 7] and not errs, (b, errs[:2]))
            ctx.close()
            srv3.shutdown()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            lite = p.evaluate("() => [document.querySelector('#scales svg').dataset.angleA, document.querySelectorAll('#scales svg').length]")
            check("c. 375 x 667, LITE, reduced motion: the scales are drawn at once, no sideways scroll, every tap >= 44 px, no error", float(lite[0]) != 0 and lite[1] == 1 and AK.no_sideways(p) and not AK.taps(p) and not errs, (lite, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_scanner()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
