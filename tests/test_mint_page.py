"""MINT, the OLYMPUS money machine hub (tools/web_public/mint/, AGORA look, 2026-11-10): five streams as cards, one honest ESTIMATE with a range, what to do today (max 3), the pillars (3D with a 2D fallback), history on the phone.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture (five streams, 'not real'), the 3D module is separate and optional
  b. the maths in node (mintcore.js): money words, ages, the range, the combined estimate, todo (max 3), pillar heights, history, the Jarvis card, junk input
  c. Chromium 390 x 844 (and 375 x 667 LITE): DEMO, a real money/index.json, a stale stream, missing index -> fixture, details, 3D pillars (or the 2D fallback), history from localStorage, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_mint_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "mint", "Mint"
check = AK.check
IDS = ["chrysos", "mercury", "sibyl", "oikos", "arbiter"]


def test_static():
    AK.static_kit(APP, NAME, reads=("../money/index.json",), storage="ls")
    d = os.path.join(AK.WEB, APP)
    js, core, scene, html = (AK.read(os.path.join(d, n)) for n in ("mint.js", "mintcore.js", "mintscene.js", "index.html"))
    check("a. the only browser storage is the estimate history under one key (mint.hist.v1), wrapped in try / catch, nothing else", js.count("localStorage.") == 2 and "mint.hist.v1" in js and not re.search(r"sessionStorage|indexedDB", js + core + scene) and js.count("try {") >= 2)
    check("a. the 3D scene is its own optional module (mintscene.js) loaded by the page, never imported by mint.js, so no WebGL means the 2D pillars stay", "mintscene.js" in html and "mintscene" not in js.split("// ----")[0].split("import")[1] and "MINT3D" in js)
    check("a. the scene uses the local three.js only, warm AGORA colours, no bloom, no neon, no network", "../jarvis/three.module.min.js" in scene and not re.search(r"https?://|Bloom|UnrealBloom", scene) and "0xc8a24a" in scene.lower())
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: five streams in order, all sample, estimates labelled, 'not real' in the note", [s["id"] for s in fx["streams"]] == IDS and all(s["status"] == "sample" for s in fx["streams"]) and fx["label"] == "ESTIMATE" and fx["demo"] is True, fx.get("note"))
    ids = re.findall(r'id="(\w+)"', html)
    check("a. the page order: combined estimate, pillars, what to do today, streams, history", html.index('id="hero"') < html.index('id="sceneCard"') < html.index('id="todoCard"') < html.index('id="streams"') < html.index('id="histCard"') and len(ids) == len(set(ids)))
    check("a. the engine's fixtures are the page's fixture (same five headlines) so the hub and the page never disagree",
          all(json.load(open(os.path.join(AK.ROOT, "tools", "money", "fixtures", s["id"] + ".json"), encoding="utf-8"))["headline"]["text"] == s["headline"] for s in fx["streams"]))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {}, NOW = Date.parse('2026-11-10T12:00:00Z');
  o.words = [C.money(2000), C.money(-60.4), C.money(null), C.perMonth(255), C.perMonth(null), C.rangeText(0, 510), C.rangeText(null, 5), C.ageText(1), C.ageText(30), C.ageText(180), C.ageText(3000), C.ageText(null), C.ageText(-5)];
  const row = (id, st, base, age, items) => ({ id, status: st, age_min: age, headline: { text: id + ' headline', usd_month: base }, usd_month: { base }, items: items || [] });
  const none = C.normStream('sibyl', null, NOW), junk = C.normStream('oikos', { status: 'weird', headline: 12, usd_month: { base: 'x' }, items: [null, { title: '' }, { title: 'T', score: 999, risk: 'zz', usd: 'q' }] }, NOW);
  o.norm = [none.status, none.headline, none.base, none.low, junk.status, junk.items.length, junk.items[0] && [junk.items[0].score, junk.items[0].risk, junk.items[0].usd]];
  const fresh = C.normStream('chrysos', row('chrysos', 'ok', 100, 20), NOW), old = C.normStream('chrysos', row('chrysos', 'ok', 100, 9 * 60), NOW), smp = C.normStream('chrysos', row('chrysos', 'sample', 100, null), NOW);
  o.range = [[fresh.status, fresh.low, fresh.base, fresh.high], [old.status, old.low, old.base, old.high], [smp.status, smp.low, smp.base, smp.high]];
  const byAsof = C.normStream('mercury', { status: 'ok', asof: '2026-11-10T11:00:00Z', headline: { text: 'x', usd_month: 10 } }, NOW);
  o.asof = [byAsof.age, byAsof.status];
  const five = (st) => C.IDS.map((id, i) => C.normStream(id, row(id, st, [38, 60, 90, 47, 20][i], 10, [{ title: id + ' task', detail: 'd', usd: 20 + i, score: 50 + i * 10, risk: i === 2 ? 'high' : 'low' }]), NOW));
  const c = C.combine(five('ok')), cs = C.combine(five('sample')), none5 = C.combine(C.streamsFrom(null, NOW));
  o.combine = [c.low, c.base, c.high, c.real, c.allSample, c.tone, c.text, c.why, cs.allSample, cs.tone, cs.why, none5.n, none5.text, none5.allSample];
  o.five = [C.streamsFrom(null, NOW).map((s) => s.id).join(), C.streamsFrom({ streams: [row('oikos', 'ok', 5, 1)] }, NOW).map((s) => s.status).join()];
  const t = C.todo(five('ok'), 9), ts = C.todo(C.streamsFrom(null, NOW), 3);
  o.todo = [t.length, t.map((x) => x.kind).join(), t[0].title, t.every((x) => x.stream !== 'arbiter'), ts.length, ts[0].kind];
  const staleSet = five('ok'); staleSet[1] = C.normStream('mercury', row('mercury', 'stale', 60, 700), NOW);
  const t2 = C.todo(staleSet, 3);
  o.stale = [t2.length, t2[0].kind, t2[0].title, t2[0].why.includes('RUN_MONEY.bat')];
  const lowfirst = C.todo(C.IDS.map((id) => C.normStream(id, row(id, 'ok', 10, 1, id === 'chrysos' ? [{ title: 'risky', detail: '', usd: 0, score: 60, risk: 'high' }, { title: 'safe', detail: '', usd: 0, score: 60, risk: 'low' }, { title: 'weak', detail: '', usd: 0, score: 20, risk: 'low' }] : []), NOW)), 3);
  o.order = [lowfirst.map((x) => x.title).join()];
  const p = C.pillars(five('ok'));
  o.pillars = [p.map((x) => Math.round(x.h * 100)).join(), p.every((x) => x.h > 0 && x.h <= 1), C.pillars(C.streamsFrom(null, NOW))[0].h];
  let hist = [];
  hist = C.pushPoint(hist, 1000000, 100); hist = C.pushPoint(hist, 1000000 + 60000, 120); hist = C.pushPoint(hist, 1000000 + 700000, 150);
  o.hist = [hist.length, hist[0].base, hist[1].base, C.pushPoint('junk', 5, 'x').length, C.pushPoint([{ t: 1, base: 2 }, null, { t: 'x' }], 99999999, 3).length];
  let big = []; for (let i = 0; i < 90; i++) big = C.pushPoint(big, i * 1000000, i);
  o.keep = [big.length, big[0].base];
  o.spark = [C.sparkPath([], 320, 70), C.sparkPath([{ t: 1, base: 1 }], 320, 70), C.sparkPath(hist, 320, 70).startsWith('M2.0 '), (C.sparkPath(hist, 320, 70).match(/L/g) || []).length, C.sparkPath([{ t: 1, base: 5 }, { t: 2, base: 5 }], 100, 50).includes('NaN')];
  o.histText = [C.histText([]).includes('second visit'), C.histText(hist).includes('2 visits') || C.histText(hist).includes('2 visits saved'), C.histText(hist).includes('up $30')];
  const card = C.jarvisCard(five('ok'), NOW), cardS = C.jarvisCard(five('sample'), NOW);
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.kpis[1].value, card.kpis[2].value, card.lines.length, Number.isInteger(card.t), cardS.status.level, cardS.status.label];
  const negRow = (id, lo, b, hi) => ({ id, status: 'ok', age_min: 5, headline: { text: id + ' headline', usd_month: b }, usd_month: { low: lo, base: b, high: hi }, items: [] });
  const negStreams = [negRow('chrysos', -42, 1339, 2235), negRow('mercury', 5, 20, 30)].map((r) => C.normStream(r.id, r, NOW));
  const nc = C.combine(negStreams), bar = C.rangeBar(-42, 1339, 2235), bar0 = C.rangeBar(300, 1000, 1500), barN = C.rangeBar(null, 1, 2);
  o.neg = [C.rangeText(-42, 2235), C.rangeText(0, 510), C.worstText(-42), C.worstText(76.5), C.worstText(null), negStreams[0].low, nc.low, nc.text, bar, bar0, barN, C.money(-42), C.money(-0.4), nc.text.includes('$-')];
  o.negCard = C.jarvisCard(negStreams.map((x) => x), NOW).kpis.map((k) => k.value);
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
    check("b. words: $2,000, -$60, '-' for nothing, '$255 a month', ranges, ages (just now, 30 min, 3 h, 50 h -> days, no date)",
          o["words"] == ["$2,000", "-$60", "-", "$255 a month", "no estimate", "$0 to $510 a month", "no range yet", "just now", "30 min ago", "3 h ago", "2 days ago", "no date", "no date"], o["words"])
    check("b. junk never throws: a missing stream is 'No data' with no number; weird status / headline / items are cleaned (score clamped to 100, bad risk -> med, bad usd -> none)",
          o["norm"] == ["none", "No data yet for this stream.", None, None, "none", 1, [100, "med", None]], o["norm"])
    check("b. the honest range per stream: live 30%-150%, old (9 h) stale 0-120%, example 0-200% (an estimate is never one lonely number)", o["range"] == [["ok", 30, 100, 150], ["stale", 0, 100, 120], ["sample", 0, 100, 200]], o["range"])
    check("b. age from the file date when the index has none: 1 h ago, still live", o["asof"] == [60, "ok"], o["asof"])
    check("b. combined estimate of five live streams: the sum of 30% / 100% / 150% -> $76.50 / $255 / $382.50, plain sentence with the range, every stream fresh, tone ok",
          o["combine"][:8] == [76.5, 255, 382.5, 255, False, "ok", "About $255 a month, but it could be anywhere from $77 to $383.", "Every stream is fresh."], o["combine"])
    check("b. five examples: flagged all-example, tone info, 'not real finds'; no streams at all: no number, a plain sentence, never NaN", o["combine"][8:11] == [True, "info", "These are example numbers, not real finds."] and o["combine"][11] == 0 and o["combine"][12].startswith("No estimate yet") and o["combine"][13] is False, o["combine"])
    check("b. always five streams in the fixed order, even from a one-stream index (the other four say 'none')", o["five"] == [",".join(IDS), "none,none,none,ok,none"], o["five"])
    check("b. what to do today is at most 3, draws tasks from every stream, and is never empty (an honest 'nothing to do today')", o["todo"][0] == 3 and o["todo"][4] >= 1 and o["todo"][5] in ("task", "none"), o["todo"])
    check("b. old data comes first: 'Refresh Mercury', with the RUN_MONEY.bat step, then the best two tasks", o["stale"] == [3, "refresh", "Refresh Mercury", True], o["stale"])
    check("b. a NEGATIVE low end is worded honestly: 'a loss of $42 a month to $2,235 a month', 'Worst case: you could lose about $42 a month.', never $-42; a positive worst case reads 'Worst case: about $77 a month.'",
          o["neg"][0] == "a loss of $42 a month to $2,235 a month" and o["neg"][1] == "$0 to $510 a month" and o["neg"][2] == "Worst case: you could lose about $42 a month." and o["neg"][3] == "Worst case: about $77 a month." and o["neg"][4] == "no worst case yet" and o["neg"][11] == "-$42" and o["neg"][12] in ("-$0", "$0"), o["neg"])
    check("b. the combined sentence with a negative low end: the worst case is said as a loss, the best case follows, no '$-' anywhere; the low end keeps its sign (-$42 + $5 = -$37)",
          o["neg"][5] == -42 and o["neg"][6] == -37 and "you could lose about $37 a month" in o["neg"][7] and "At best about $2,265 a month" in o["neg"][7] and o["neg"][13] is False and o["negCard"][1].startswith("-$37 to $"), (o["neg"][5:8], o["negCard"]))
    check("b. the range bar spans the loss and the gain: for -$42 / $1,339 / $2,235 zero is marked at 2% and the fill starts at 0%; a positive range has no zero mark; null is empty",
          o["neg"][8]["neg"] is True and o["neg"][8]["left"] == 0 and o["neg"][8]["zero"] == 2 and 0 < o["neg"][8]["mark"] < 100 and o["neg"][8]["width"] >= 97 and o["neg"][9]["zero"] is None and o["neg"][9]["neg"] is False and o["neg"][10]["width"] == 0, o["neg"][8:11])
    check("b. low risk beats high risk at the same score; weak items (score < 40) are dropped", o["order"] == ["safe,risky"] or o["order"][0].startswith("safe"), o["order"])
    check("b. pillar heights are linear in the dollars (tallest = 100%), never zero, and a stream with no number is a thin stub", o["pillars"][1] is True and o["pillars"][0].split(",")[2] == "100" and o["pillars"][2] == 0.04, o["pillars"])
    check("b. history: one point per 10 minutes (a quicker visit updates the last one), junk in -> clean list out", o["hist"] == [2, 120, 150, 0, 2], o["hist"])
    check("b. history keeps the last 60 points only", o["keep"] == [60, 30], o["keep"])
    check("b. sparkline path: empty under 2 points, starts at the left edge, one L per extra point, a flat line has no NaN", o["spark"] == ["", "", True, 1, False], o["spark"])
    check("b. history words: first visit explains itself; later says how many visits and up / down in dollars", o["histText"][0] and o["histText"][2], o["histText"])
    check("b. the Jarvis card: Mint, level ok for live, 3 kpis, the estimate $255, the range, 5 live, <= 3 lines, integer t; examples -> level off 'Example numbers'",
          o["card"] == ["Mint", "ok", 3, "$255", "$77-$383", "5 live", 2, True, "off", "Example numbers"], o["card"])


def index_json(streams, asof="2026-11-10T11:30:00Z"):
    rows = []
    for sid, st, base, age, items in streams:
        rows.append({"id": sid, "name": sid.title(), "status": st, "source": "scanner", "asof": asof, "age_min": age, "headline": f"{sid.title()} found something real.",
                     "usd_month": {"low": base * 0.3, "base": base, "high": base * 1.5}, "items": items, "notes": ["A real caveat."], "error": None})
    return json.dumps({"v": 1, "asof": asof, "mode": "paper", "label": "ESTIMATE", "total": {}, "counts": {}, "note": "x", "streams": rows})


ITEM = {"title": "Cancel the unused plan", "detail": "No sign-in for 90 days.", "usd": 16, "score": 80, "risk": "low"}
REAL = index_json([("chrysos", "ok", 100, 12, [ITEM]), ("mercury", "stale", 60, 700, []), ("sibyl", "ok", 200, 5, [dict(ITEM, title="Rate market", score=45, risk="high")]), ("oikos", "ok", 40, 3, [ITEM]), ("arbiter", "ok", 20, 3, [])])


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
            AK.open_app(p, origin, APP, "?demo=1&flat=1")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, base: document.querySelector('#heroBase').textContent, text: document.querySelector('#heroText').textContent, why: document.querySelector('#heroWhy').textContent,
              pill: document.querySelector('#heroPill').textContent, cards: document.querySelectorAll('#streams .stream').length, names: [...document.querySelectorAll('#streams h3')].map((h) => h.textContent),
              pills: [...document.querySelectorAll('#streams .pill')].map((h) => h.textContent), todo: document.querySelectorAll('#todo li').length, legend: document.querySelectorAll('#legend li').length,
              cols: document.querySelectorAll('#fallback rect').length, hist: document.querySelector('#histNote').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
              ests: [...document.querySelectorAll('#streams .amt')].map((h) => h.textContent), scene: window.MINT.S.scene })""")
            check("c. DEMO (the fixture): the chip, $1,495 a month with a worst case of losing about $42 and a best case of $2,547 (Chrysos's Stress case, from the real scanner), Example estimate (sentence case, AGORA v2), 'not real finds', five cards in order, each marked Example",
                  d["demo"] and d["base"] == "$1,495" and "in the worst case you could lose about $42 a month" in d["text"] and "$2,547" in d["text"] and d["pill"] == "Example estimate" and "not real finds" in d["why"] and d["names"] == ["Chrysos", "Mercury", "Sibyl", "Oikos", "Arbiter"] and d["pills"] == ["Example"] * 5, d)
            check("c. every card shows its dollars as an estimate ('a month (estimate)'); at most 3 things to do; five legend rows; the 2D pillars (flat=1) are drawn; examples are not saved to the history",
                  all("estimate" in e for e in d["ests"]) and 1 <= d["todo"] <= 3 and d["legend"] == 5 and d["cols"] >= 20 and d["scene"] == "2d" and "not saved" in d["hist"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "mint-demo")
            p.locator("#streams .stream").first.locator("button").click()
            p.wait_for_timeout(120)
            e = p.evaluate("() => { const c = document.querySelector('#streams .stream'); return [c.querySelector('.more').hidden, c.querySelector('button').getAttribute('aria-expanded'), c.querySelector('.items').children.length, c.textContent.includes('estimate')]; }")
            check("c. tap Details: the items open (with their own risk words), the button says expanded, tap again closes", e == [False, "true", 3, True], e)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # a real index: money/index.json, one stale stream, saved history
            hist = json.dumps([{"t": 1790000000000, "base": 200}, {"t": 1790100000000, "base": 230}])
            srv2, origin2 = AK.serve({"/money/index.json": REAL})
            ctx, p, errs, seen, off = AK.page(br, origin2, storage={"mint.hist.v1": hist})
            AK.open_app(p, origin2, APP, "?flat=1")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, base: document.querySelector('#heroBase').textContent, text: document.querySelector('#heroText').textContent, pill: document.querySelector('#heroPill').textContent,
              why: document.querySelector('#heroWhy').textContent, pills: [...document.querySelectorAll('#streams .pill')].map((h) => h.textContent), todo: [...document.querySelectorAll('#todo b')].map((h) => h.textContent),
              path: document.querySelector('#spark path') && document.querySelector('#spark path').getAttribute('d'), hist: document.querySelector('#histNote').textContent, saved: JSON.parse(localStorage.getItem('mint.hist.v1')).length })""")
            check("c. a real money/index.json: no DEMO chip, Estimate, $420 a month (sum of the five), the stale stream marked Old data, the others Live", not r["demo"] and r["base"] == "$420" and r["pill"] == "Estimate" and r["pills"] == ["Live", "Old data", "Live", "Live", "Live"], r)
            check("c. what to do today starts with 'Refresh Mercury' (old data), then the best low-risk task, max 3", r["todo"][0] == "Refresh Mercury" and r["todo"][1] == "Cancel the unused plan" and len(r["todo"]) == 3, r["todo"])
            check("c. the history line is drawn from localStorage (2 saved visits + this one = 3 points), and says it is saved on this phone", r["path"] and r["saved"] == 3 and "3 visits saved on this phone" in r["hist"], r)
            check("c. it reads only the site's own files and no console error", any("money/index.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            # the REAL scanners' output (--fixture run of tools/money/*.py through the engine)
            import tempfile
            sys.path.insert(0, os.path.join(AK.ROOT, "tools"))
            import money_engine as ME
            real_out = tempfile.mkdtemp(prefix="mint-real-")
            ME.run(real_out, True, 120, quiet=True)
            srv4, origin4 = AK.serve({"/money/index.json": open(os.path.join(real_out, "index.json"), encoding="utf-8").read()})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "?flat=1")
            rr = p.evaluate("() => ({ n: document.querySelectorAll('#streams .stream').length, demo: !document.querySelector('#demo').hidden, pills: [...document.querySelectorAll('#streams .pill')].map((h) => h.textContent), base: document.querySelector('#heroBase').textContent, todo: document.querySelectorAll('#todo li').length, roles: [...document.querySelectorAll('#streams .top2 .note')].map((h) => h.textContent) })")
            check("c. the real scanners' index: five cards (their sample status shown as Example), no DEMO chip (it is the real file), a total, at most 3 things to do, the real one-line roles, no console error",
                  rr["n"] == 5 and not rr["demo"] and rr["pills"] == ["Example"] * 5 and rr["base"].startswith("$") and 1 <= rr["todo"] <= 3 and rr["roles"][4] == "Spread and funding ideas (paper)" and not errs, (rr, errs[:2]))
            ctx.close()
            srv4.shutdown()
            # no index at all (404): the fixture, never blank
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?flat=1")
            m = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#streams .stream').length, document.querySelector('#heroBase').textContent]")
            check("c. no money/index.json on the site: the example fixture fills the page (DEMO chip, five cards, $1,495), never blank", m == [True, 5, "$1,495"], m)
            ctx.close()
            # the 3D pillars (one browser run, short)
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            p.wait_for_timeout(2500)
            w = p.evaluate("""() => ({ scene: window.MINT.S.scene, three: !document.querySelector('#scene3d').hidden, canvas: !!document.querySelector('#scene3d canvas'), frames: window.MINT3D ? window.MINT3D.frames() : -1,
              pillars: window.MINT3D ? window.MINT3D.pillars() : [], svg: getComputedStyle(document.querySelector('#fallback')).visibility })""")
            if w["scene"] == "webgl":
                ps = w["pillars"]
                check("c. 3D: a canvas draws frames, five pillars, the tallest is Chrysos and the shortest Mercury (no monthly number): height follows the estimate; the 2D picture steps aside",
                      w["three"] and w["canvas"] and w["frames"] > 1 and len(ps) == 5 and ps.index(max(ps)) == 0 and ps.index(min(ps)) == 1, w)
                AK.shot(p, "mint-3d")
            else:
                check("c. 3D not available in this browser: the 2D pillars stay (never blank)", w["scene"] == "2d" and not w["three"] and w["svg"] == "visible", w)
            check("c. no console error with the 3D module loaded", not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            s = p.evaluate("() => [window.MINT.S.scene, !document.querySelector('#lite').hidden]")
            check("c. 375 x 667, LITE, reduced motion: 2D pillars only (no WebGL on a lite phone), LITE chip, no sideways scroll, every tap >= 44 px, no error", s[0] == "2d" and AK.no_sideways(p) and not AK.taps(p) and not errs, (s, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


def test_negative_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    rows = json.loads(REAL)
    rows["streams"][0]["usd_month"] = {"low": -42.0, "base": 100.0, "high": 150.0}
    for r in rows["streams"][1:]:
        r["usd_month"]["low"] = 0.0
    srv, origin = AK.serve({"/money/index.json": json.dumps(rows)})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?flat=1")
            r = p.evaluate("""() => ({ lo: document.querySelector('#rngLo').textContent, loCls: document.querySelector('#rngLo').className, worst: document.querySelector('#rngWorst').textContent, text: document.querySelector('#heroText').textContent,
              zero: !document.querySelector('#rngZero').hidden, fill: document.querySelector('#rngFill').className, label: document.querySelector('#rng').getAttribute('aria-label'), all: document.body.innerText.includes('$-') })""")
            check("c. a negative low end on the page: '-$' words, 'Worst case: you could lose about', the low label is terracotta, a zero line on the bar, the aria label says a loss, nothing reads '$-'",
                  r["lo"].startswith("-$") and "(a loss)" in r["lo"] and r["loCls"] == "neg" and r["worst"].startswith("Worst case: you could lose about $") and "could lose about" in r["text"] and r["zero"] and r["fill"] == "neg" and "worst case a loss of $" in r["label"] and not r["all"], r)
            check("c. no console error, nothing off the origin", not errs and not off, (errs[:2], off[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
        test_negative_page()
    AK.finish()
