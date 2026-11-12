"""MINT CITY, the money machines as a giant marble city (tools/web_public/mintcity/, AGORA look, 2026-11-10): five districts (treasury tower, market stalls, oracle temple, household quarter, harbour with scales)
round a golden pillar; building heights follow each stream's estimate; instanced buildings with a LOD; camera tours; tap a district, then Open its app.

  a. static: the files, the kit lines, the AGORA look, read-only, no storage, the Jarvis card, the manifest, the DEMO fixture, the 3D scene is a separate optional module
  b. the city plan in node (mintcitycore.js): deterministic, heights follow the estimates, the pillar follows the combined estimate, instance counts per tier, LOD rule, tours, junk input
  c. Chromium 390 x 844 (and 375 x 667 LITE): the 2D map and the list (DEMO, a real index, a missing index), pick a district, the 3D city (instanced, LOD, tours, a tap on the city), taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_mintcity_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "mintcity", "Mint City"
check = AK.check
IDS = ["chrysos", "mercury", "sibyl", "oikos", "arbiter"]


def test_static():
    AK.static_kit(APP, NAME, reads=("../money/index.json",))
    d = os.path.join(AK.WEB, APP)
    js, scene, html, core = (AK.read(os.path.join(d, n)) for n in ("mintcity.js", "mintcityscene.js", "index.html", "mintcitycore.js"))
    check("a. the 3D city is its own optional module loaded by the page, never imported by mintcity.js (no WebGL / LITE keeps the map and the list)", "mintcityscene.js" in html and "from './mintcityscene" not in js and "MINTCITY3D" in js)
    check("a. the scene uses the local three.js only, InstancedMesh for the buildings, a LOD rule from the core, no bloom, no network", "../jarvis/three.module.min.js" in scene and "InstancedMesh" in scene and "lodDetail" in scene and not re.search(r"https?://|Bloom", scene))
    check("a. the scene frees what it makes (dispose of instances, geometry, materials, renderer, listeners) and pauses when the tab is hidden", all(x in scene for x in ("dispose()", "removeEventListener", "visibilitychange", "cancelAnimationFrame")))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    mint = json.load(open(os.path.join(AK.WEB, "mint", "fixture.json"), encoding="utf-8"))
    check("a. the fixture: five streams in order, all sample, 'not real' in the note, the same five headlines as Mint's", [s["id"] for s in fx["streams"]] == IDS and all(s["status"] == "sample" for s in fx["streams"]) and "not real" in fx["note"].lower() and [s["headline"] for s in fx["streams"]] == [s["headline"] for s in mint["streams"]])
    check("a. the districts link to the five money apps (../chrysos/ ... ../arbiter/)", all(f"href: '../{i}/'" in core for i in IDS))
    check("a. no browser storage at all, nothing sent anywhere", not re.search(r"localStorage|sessionStorage|indexedDB", js + scene + core))
    check("a. the page order: the golden pillar, the city, the selected district, the five districts", html.index('id="hero"') < html.index('id="cityCard"') < html.index('id="sheet"') < html.index('id="listCard"'))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const row = (id, st, base) => ({ id, status: st, age_min: 10, headline: { text: id + ' headline', usd_month: base }, usd_month: { low: base * 0.3, base, high: base * 1.5 } });
  const five = (vals, st) => C.streamsFrom({ streams: C.IDS.map((id, i) => row(id, st || 'ok', vals[i])) });
  const A = five([1339, 0, 8, 111, 37]), B = five([100, 100, 100, 100, 100]), E = C.streamsFrom(null);
  o.words = [C.money(1495), C.money(null), C.money(-60), C.rangeText(0, 2990), C.rangeText(null, 1), C.ageText(1), C.ageText(30), C.ageText(180), C.ageText(5000), C.ageText(null)];
  o.streams = [E.map((s) => s.id).join(), E.every((s) => s.status === 'none' && s.base == null), E[0].headline, A[0].place, A[2].href, C.normStream('oikos', { status: 'weird', headline: 12, usd_month: { base: 'x' } }).status, C.normStream('mercury', { status: 'sample', headline: { text: 'x', usd_month: null } }).base];
  const hs = C.heights(A), hb = C.heights(B), he = C.heights(E);
  o.heights = [hs.map((h) => Math.round(h * 100) / 100), hb.every((h) => h === C.MAX_H), he.every((h) => h === C.MIN_H), hs[0] === C.MAX_H, hs[1] === C.MIN_H, hs[3] > hs[4] && hs[4] > hs[2] && hs[2] > hs[1]];
  o.pillar = [C.pillarHeight(null), C.pillarHeight(0), C.pillarHeight(3000), C.pillarHeight(99999), C.pillarHeight(1500), C.pillarHeight(1495) < C.pillarHeight(2990)];
  const c = C.combine(A), cs = C.combine(five([1, 2, 3, 4, 5], 'sample')), ce = C.combine(E);
  o.combine = [c.base, c.n, c.allSample, c.text, cs.allSample, cs.why, ce.n, ce.text];
  const pH = C.cityPlan(A, 'high'), pM = C.cityPlan(A, 'mid'), pL = C.cityPlan(A, 'low'), pH2 = C.cityPlan(A, 'high');
  o.plan = [pH.districts.map((d) => d.id).join(), JSON.stringify(pH) === JSON.stringify(pH2), C.count(pH) > C.count(pM) && C.count(pM) > C.count(pL), C.count(pH) >= 400, C.count(pL) >= 150, pH.filler.length, pH.pillar.h, pH.districts.map((d) => d.parts.length > 5).every(Boolean)];
  const kinds = new Set(), cols = new Set(); let bad = 0, maxY = 0;
  for (const d of pH.districts) for (const b of d.parts) { kinds.add(b.k); cols.add(b.c); if (![b.x, b.y, b.z, b.sx, b.sy, b.sz, b.ry].every(Number.isFinite) || b.sx <= 0 || b.sy <= 0 || b.sz <= 0) bad++; maxY = Math.max(maxY, b.y + b.sy / 2); }
  o.parts = [[...kinds].sort().join(), [...cols].sort().join(), bad, maxY <= C.MAX_H + 12];
  const tower = (plan) => Math.max(...plan.districts[0].parts.map((b) => b.y + b.sy / 2)), scales = (plan) => Math.max(...plan.districts[4].parts.map((b) => b.y + b.sy / 2));
  const pBig = C.cityPlan(five([1339, 100, 100, 100, 1339]), 'high'), pSmall = C.cityPlan(five([50, 100, 100, 100, 50]), 'high');
  o.follow = [tower(pBig) > tower(pSmall) + 5, scales(pBig) > scales(pSmall) + 3, pBig.districts[0].H > pSmall.districts[0].H, tower(pBig) >= pBig.districts[0].H];
  const ctr = [0, 1, 2, 3, 4].map((i) => C.districtCenter(i, 5)), dist = ctr.map((p) => Math.hypot(p.x, p.z));
  o.ring = [dist.every((d) => Math.abs(d - C.RING) < 1e-9), Math.round(ctr[0].x), Math.round(ctr[0].z), new Set(ctr.map((p) => p.x.toFixed(2))).size];
  const near = (p, d) => Math.hypot(p.x - d.cx, p.z - d.cz);
  o.local = pH.districts.every((d) => d.parts.every((b) => near(b, d) < 13));
  o.lod = [C.lodDetail(60, 'high'), C.lodDetail(80, 'high'), C.lodDetail(60, 'mid'), C.lodDetail(40, 'mid'), C.lodDetail(40, 'low'), C.lodDetail(30, 'low'), C.lodDetail(60, 'zzz')];
  const cam = C.poseToCam(C.OVERVIEW), cf = C.poseToCam(C.focusPose(2, 5));
  o.cam = [cam.pos.every(Number.isFinite), Math.round(Math.hypot(cam.pos[0], cam.pos[2], cam.pos[1] - 2)), cf.look.map((v) => Math.round(v)), Math.hypot(cf.pos[0] - cf.look[0], cf.pos[2] - cf.look[2]) < 30];
  const f0 = C.tourPose('fly', 0), f6 = C.tourPose('fly', 6000), f5 = C.tourPose('fly', 5500), fN = C.tourPose('fly', -100), p0 = C.tourPose('pillar', 0), p4 = C.tourPose('pillar', 4000), bogus = C.tourPose('nope', 0);
  o.tours = [f0.dist === C.OVERVIEW.dist, Math.abs(f6.tx - C.districtCenter(0, 5).x) < 1.5 || f6.dist < C.OVERVIEW.dist, f5.dist <= C.OVERVIEW.dist, [f0, f6, f5, fN, p0, p4].every((p) => Object.values(p).every(Number.isFinite)), p0.tx === 0 && p0.dist < 25, Math.abs(p4.yaw - Math.PI) < 1e-9, bogus.dist === C.OVERVIEW.dist];
  const lp = C.lerpPose({ yaw: 3.0, pitch: 0.2, dist: 10, tx: 0, tz: 0 }, { yaw: -3.0, pitch: 0.4, dist: 20, tx: 10, tz: 10 }, 0.5);
  o.lerp = [Math.round(lp.dist), Math.round(lp.tx), Math.abs(lp.yaw) > 3 || Math.abs(lp.yaw) < 0.1 ? 'short-way' : 'long-way', C.lerpPose(C.OVERVIEW, C.OVERVIEW, 5).dist];
  const a = C.rng(5), b = C.rng(5), x = []; for (let i = 0; i < 4; i++) x.push(a() === b()); o.rng = [x.every(Boolean), C.seedOf('a') !== C.seedOf('b'), (() => { const r = C.rng(1); for (let i = 0; i < 200; i++) { const v = r(); if (v < 0 || v >= 1) return false; } return true; })()];
  const card = C.jarvisCard(A, 1793394000000), cardS = C.jarvisCard(five([1, 2, 3, 4, 5], 'sample'), 0);
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.lines.length, Number.isInteger(card.t), cardS.status.level, cardS.status.label];
  const nr = (id, lo, b, hi) => C.normStream(id, { id, status: 'ok', age_min: 5, headline: { text: id }, usd_month: { low: lo, base: b, high: hi }, items: [] });
  const nn = C.combine([nr('chrysos', -42, 1339, 2235), nr('mercury', 5, 20, 30)]);
  o.neg = [C.rangeText(-42, 2235), C.rangeText(0, 510), nn.low, nn.text, nn.text.includes('$-')];
  console.log(JSON.stringify(o));
});
"""


def test_city():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node is not installed: city maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: $1,495, '-' for nothing, ranges, ages", o["words"] == ["$1,495", "-", "-$60", "$0 to $2,990 a month", "no range yet", "just now", "30 min ago", "3 h ago", "3 days ago", "no date"], o["words"])
    check("b. always five districts in the fixed order; a missing one is 'No data'; the place names and app links are right; junk status is cleaned; a null estimate stays null",
          o["streams"] == [",".join(IDS), True, "No data yet for this stream.", "The treasury tower", "../sibyl/", "none", None], o["streams"])
    check("b. heights are linear in the estimate: the biggest stream is the tallest (15), no estimate is the lowest (1.6), equal streams are equal, order follows the dollars", o["heights"][0] == [15, 1.6, 1.68, 2.71, 1.97] and all(o["heights"][1:]), o["heights"])
    check("b. the golden pillar follows the combined estimate: 6 m with no estimate, 30 m from $3,000 a month, 18 m at $1,500, never beyond 30 m, taller for a bigger estimate", o["pillar"] == [6, 6, 30, 30, 18, True], o["pillar"])
    check("b. a NEGATIVE low end: 'a loss of $42 a month to $2,235 a month', the combined sentence says 'you could lose about $37 a month', the low end keeps its sign, never '$-'",
          o["neg"][0] == "a loss of $42 a month to $2,235 a month" and o["neg"][1] == "$0 to $510 a month" and o["neg"][2] == -37 and "you could lose about $37 a month" in o["neg"][3] and o["neg"][4] is False, o["neg"])
    check("b. the combined estimate is the sum ($1,495), says 'estimate', examples are flagged ('Example numbers, not real finds'), no streams -> no number and a plain sentence",
          o["combine"][0] == 1495 and o["combine"][1] == 5 and o["combine"][2] is False and "an estimate" in o["combine"][3] and o["combine"][4] is True and o["combine"][5].startswith("Example") and o["combine"][6] == 0 and o["combine"][7].startswith("No estimate yet"), o["combine"])
    check("b. the city plan: the same plan every time (seeded), fewer buildings per tier (high > mid > low), 400+ on high and 150+ on low, 260 filler blocks, the pillar from the estimate, every district has a real set of buildings",
          o["plan"][0] == ",".join(IDS) and o["plan"][1] and o["plan"][2] and o["plan"][3] and o["plan"][4] and o["plan"][5] == 260 and o["plan"][7] is True, o["plan"])
    check("b. building kinds are box / cyl / roof in the six marble-bronze-gold palette keys, every number finite and sizes positive, nothing taller than the district limit", o["parts"] == ["box,cyl,roof", "aegean,bronze,gold,marble,olive,terra", 0, True], o["parts"])
    check("b. the landmarks follow the estimate: a bigger Chrysos is a taller tower, a bigger Arbiter a taller pair of scales, the district height is carried in the plan", all(o["follow"]), o["follow"])
    check("b. the five districts sit on a ring round the pillar (24 m), the first at the top, all in different places; every building stays inside its own district", o["ring"] == [True, 0, -24, 5] and o["local"] is True, (o["ring"], o["local"]))
    check("b. LOD rule: detail under the near distance (74 high, 52 mid, 34 low), one block beyond; an unknown tier counts as high", o["lod"] == [True, False, False, True, False, True, True], o["lod"])
    check("b. camera poses are finite; the overview is about 72 away; a district focus looks at that district and sits close", o["cam"][0] and o["cam"][1] in range(70, 74) and o["cam"][3], o["cam"])
    check("b. tours: the fly-through starts at the overview, visits the districts, holds then glides, never NaN even at a negative time; the pillar tour circles the pillar (a half turn at 4 s); an unknown tour is the overview", all(o["tours"]), o["tours"])
    check("b. poses blend the short way round and a time past 1 is clamped", o["lerp"][0] == 15 and o["lerp"][1] == 5 and o["lerp"][2] == "short-way" and o["lerp"][3] == 72, o["lerp"])
    check("b. the seeded random is repeatable and stays in [0, 1)", all(o["rng"]), o["rng"])
    check("b. the Jarvis card: Mint City, ok for live, 3 kpis, the estimate, one line, integer t; examples -> level off 'Example numbers'", o["card"] == ["Mint City", "ok", 3, "$1,495", 1, True, "off", "Example numbers"], o["card"])


def index_json(base_vals, status="ok"):
    rows = []
    for sid, base in zip(IDS, base_vals):
        rows.append({"id": sid, "name": sid.title(), "status": status, "source": "scanner", "asof": "2026-11-10T11:30:00Z", "age_min": 12, "headline": f"{sid.title()} found something real.",
                     "usd_month": {"low": base * 0.3, "base": base, "high": base * 1.5} if base is not None else {"low": None, "base": None, "high": None}, "items": [], "notes": [], "error": None})
    return json.dumps({"v": 1, "asof": "2026-11-10T11:30:00Z", "mode": "paper", "label": "ESTIMATE", "streams": rows})


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
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, base: document.querySelector('#heroBase').textContent, pill: document.querySelector('#heroPill').textContent, text: document.querySelector('#heroText').textContent,
              rows: [...document.querySelectorAll('#list b')].map((b) => b.textContent), links: [...document.querySelectorAll('#list a')].map((a) => a.getAttribute('href')), labels: [...document.querySelectorAll('#list a')].map((a) => a.getAttribute('aria-label')),
              groups: document.querySelectorAll('#map g').length, chips: [...document.querySelectorAll('#chips button')].map((b) => b.textContent), scene: window.MINTCITY.S.scene, sheet: !document.querySelector('#sheet').hidden,
              map: getComputedStyle(document.querySelector('#mapWrap')).visibility, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor })""")
            check("c. DEMO (the fixture, flat): the chip, the golden pillar says $1,495 a month, Example estimate (sentence case, AGORA v2), five districts in the list with their dollars and an Open link each to the right app, the 2D map with five tappable districts, five district chips (no tours without 3D)",
                  d["demo"] and d["base"] == "$1,495" and d["pill"] == "Example estimate" and "you could lose about $42 a month" in d["text"] and "$2,547" in d["text"] and d["rows"] == ["Chrysos", "$1,339", "Mercury", "no estimate", "Sibyl", "$8", "Oikos", "$111", "Arbiter", "$37"]
                  and d["links"] == [f"../{i}/" for i in IDS] and d["labels"][0] == "Open the Chrysos app" and d["groups"] == 5 and d["chips"] == ["Chrysos", "Mercury", "Sibyl", "Oikos", "Arbiter"] and d["scene"] == "2d" and not d["sheet"] and d["map"] == "visible", d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "mintcity-2d")
            p.locator("#chips button", has_text="Sibyl").click()
            p.wait_for_timeout(150)
            s = p.evaluate("""() => ({ name: document.querySelector('#shName').textContent, href: document.querySelector('#shOpen').getAttribute('href'), open: document.querySelector('#shOpen').textContent, kv: document.querySelector('#shKv').textContent,
              pressed: document.querySelector('#chips [aria-pressed=true]').textContent, st: document.querySelector('#status').textContent })""")
            check("c. tap the Sibyl chip: the district sheet opens ('Sibyl: The oracle temple'), its estimate as an estimate with a range and 'Example', an 'Open Sibyl' link to ../sibyl/, the chip is pressed, the status line is spoken",
                  s["name"] == "Sibyl: The oracle temple" and s["href"] == "../sibyl/" and s["open"] == "Open Sibyl" and "Estimate$8 a month" in s["kv"] and "Example" in s["kv"] and s["pressed"] == "Sibyl" and "Open button" in s["st"], s)
            p.locator("#map g[data-id=oikos]").click()
            p.wait_for_timeout(150)
            o2 = p.evaluate("() => [document.querySelector('#shName').textContent, document.querySelector('#shOpen').getAttribute('href')]")
            check("c. tap a district on the 2D map: the same sheet for Oikos, link ../oikos/", o2 == ["Oikos: The household quarter", "../oikos/"], o2)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, Open links, the list)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # a real index
            srv2, origin2 = AK.serve({"/money/index.json": index_json([100, 200, None, 40, 20])})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?flat=1&district=mercury")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, base: document.querySelector('#heroBase').textContent, pill: document.querySelector('#heroPill').textContent, rows: [...document.querySelectorAll('#list li b.ag-num')].map((b) => b.textContent), sheet: document.querySelector('#shName').textContent, kv: document.querySelector('#shKv').textContent })")
            check("c. a real money/index.json: no DEMO chip, Estimate, $360 a month, no number for Sibyl ('no estimate'), ?district=mercury opens that sheet with 'Live'",
                  not r["demo"] and r["base"] == "$360" and r["pill"] == "Estimate" and r["rows"] == ["$100", "$200", "no estimate", "$40", "$20"] and r["sheet"].startswith("Mercury") and "Live" in r["kv"], r)
            check("c. it read the site's own file and no console error", any("money/index.json" in u for u in seen) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            srv2.shutdown()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?flat=1")
            m = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#list li').length, document.querySelector('#heroBase').textContent]")
            check("c. no money/index.json on the site: the example fixture fills the page (DEMO, five districts, $1,495), never blank", m == [True, 5, "$1,495"], m)
            ctx.close()
            # the 3D city (one browser run, short)
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            p.wait_for_timeout(3000)
            w = p.evaluate("() => ({ scene: window.MINTCITY.S.scene, three: !document.querySelector('#scene3d').hidden, canvas: !!document.querySelector('#scene3d canvas'), st: window.MINTCITY3D ? window.MINTCITY3D.state() : null, chips: [...document.querySelectorAll('#chips button')].map((b) => b.textContent), map: getComputedStyle(document.querySelector('#mapWrap')).visibility })")
            if w["scene"] == "webgl":
                st = w["st"]
                check("c. 3D: a canvas draws frames, the buildings are INSTANCED (hundreds of buildings in under 60 draw calls), the low tier is on (?q=low), the pillar is 6 + 24 x 1495/3000 = 18 m, the 2D map steps aside, the tour chips appear",
                      w["three"] and w["canvas"] and st["on"] and st["frames"] > 1 and st["instances"] >= 150 and st["drawsApprox"] < 60 and st["tier"] == "low" and abs(st["pillar"] - 17.94) < 0.1 and w["map"] == "hidden" and w["chips"][:3] == ["Overview", "Fly through", "Golden pillar"], w)
                check("c. LOD: from the overview (72 m away) the low tier shows every district as ONE block (no detail), the heights follow the estimates (Chrysos tallest)", st["lod"] == [0, 0, 0, 0, 0] and st["heights"].index(max(st["heights"])) == 0 and min(st["heights"]) == st["heights"][1], st)
                AK.shot(p, "mintcity-3d-overview")
                p.locator("#chips button", has_text="Oikos").click()
                p.wait_for_timeout(2200)
                f = p.evaluate("() => ({ st: window.MINTCITY3D.state(), sheet: document.querySelector('#shName').textContent })")
                check("c. tap the Oikos chip: the camera flies there (about 26 m from it), ONLY that district switches to full detail (LOD), the sheet opens", f["st"]["lod"] == [0, 0, 0, 1, 0] and f["sheet"].startswith("Oikos") and f["st"]["pose"]["dist"] < 30, f)
                AK.shot(p, "mintcity-3d-oikos")
                p.locator("#chips button", has_text="Fly through").click()
                p.wait_for_timeout(1500)
                tt = p.evaluate("() => [window.MINTCITY3D.state().tour, document.querySelector('#chips [aria-pressed=true]').textContent, document.querySelector('#status').textContent]")
                check("c. the Fly through tour starts (state and the pressed chip say so, the status line is spoken)", tt[0] == "fly" and tt[1] == "Fly through" and "Flying" in tt[2], tt)
                p.locator("#chips button", has_text="Golden pillar").click()
                p.wait_for_timeout(800)
                pl = p.evaluate("() => [window.MINTCITY3D.state().tour, window.MINTCITY3D.state().pose.dist]")
                check("c. the Golden pillar tour circles the pillar from 20 m", pl[0] == "pillar" and abs(pl[1] - 20) < 0.5, pl)
                p.locator("#chips button", has_text="Overview").click()
                p.wait_for_timeout(1500)
                # QA Round 7: the chip taps leave the city half scrolled under the app bar; a tap there hit the bar's back link and left the page.
                # Bring the city into view and only tap points where the city's own canvas is the top element.
                p.evaluate("() => document.querySelector('#city').scrollIntoView({ block: 'center' })")
                p.wait_for_timeout(400)
                box = p.locator("#city").bounding_box()
                got = None
                for fy in (0.4, 0.5, 0.6, 0.3, 0.7, 0.45, 0.55, 0.75, 0.8):
                    for fx in (0.5, 0.3, 0.7, 0.2, 0.8, 0.4, 0.6):
                        if not p.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && e.tagName === 'CANVAS' && !!e.closest('#city'); }",
                                          [box["x"] + box["width"] * fx, box["y"] + box["height"] * fy]):
                            continue
                        p.evaluate("() => { document.querySelector('#sheet').hidden = true; }")
                        p.mouse.click(box["x"] + box["width"] * fx, box["y"] + box["height"] * fy)
                        p.wait_for_timeout(60)
                        if p.evaluate("() => !document.querySelector('#sheet').hidden"):
                            got = p.evaluate("() => document.querySelector('#shName').textContent")
                            break
                    if got:
                        break
                check("c. a tap on a district IN the 3D city picks it (the sheet opens for the district under the finger)", got is not None and ":" in got, got)
                nan = p.evaluate("() => Object.values(window.MINTCITY3D.state().pose).every((v) => Number.isFinite(v))")
                check("c. the camera pose is always finite (drag, zoom and tours never produce NaN)", nan)
            else:
                check("c. 3D not available in this browser: the 2D map and the list stay (never blank)", w["scene"] == "2d" and not w["three"] and w["map"] == "visible", w)
            check("c. no console error with the 3D module loaded", not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            s = p.evaluate("() => [window.MINTCITY.S.scene, !document.querySelector('#lite').hidden, document.querySelectorAll('#list li').length, getComputedStyle(document.querySelector('#mapWrap')).visibility]")
            check("c. 375 x 667, LITE, reduced motion: the 2D map and the five districts only (no WebGL on a lite phone), LITE chip, no sideways scroll, every tap >= 44 px, no error", s == ["2d", True, 5, "visible"] and AK.no_sideways(p) and not AK.taps(p) and not errs, (s, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_city()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
