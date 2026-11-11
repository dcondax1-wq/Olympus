"""SYMPOSIUM, the hall where you meet everyone (tools/web_public/symposium/, AGORA look, 2026-11-11), on top of the people kit (olympus/people.js).

  a. static: the files, the kit lines, the AGORA look, read-only (no markup from data, no network except ./fixture.json; the people come through the kit), the Jarvis card, the manifest, the wiring row
  b. the pure parts in node (symposiumcore.js): seating, who is in front, the ready-made duels, new faces, the request box (grouping, JSON), the Jarvis card, "Make my character"
  c. Chromium 390 x 844 and 375 x 667 (LITE = the portrait wall; high = the 3D hall when WebGL is there): tap a person and talk, chips, leave a request, the request box with
     "Copy for Claude" and export, round table, the stand-up with who is blocked, a debate with a neutral summary, make my character, the built-in cast when people.json is missing,
     reduced motion, every tap >= 44 px, no sideways scroll, no console error, nothing off the page's origin
    python -X utf8 -m tests.test_symposium_page            (--static: parts a and b only)
    browser part: flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_symposium_page
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "symposium", "Symposium"
check = AK.check
D = os.path.join(AK.WEB, APP)


def test_static():
    AK.static_kit(APP, NAME, reads=())
    html, js, css = (AK.read(os.path.join(D, n)) for n in ("index.html", "symposium.js", "symposium.css"))
    hall = AK.read(os.path.join(D, "hall.js"))
    check("a. the page: the hall first, then new faces, then six tabs (Meet, Round table, Stand-up, Debate, Requests, Me), each a real tab with its panel",
          html.index('id="hallCard"') < html.index('id="newCard"') < html.index('id="tabs"') and all(f'id="tab-{t}"' in html and f'id="p-{t}"' in html and f'aria-controls="p-{t}"' in html for t in ("meet", "table", "standup", "debate", "requests", "me"))
          and html.count('role="tab"') == 6 and html.count('role="tabpanel"') == 6)
    check("a. the people come from the shared kit (olympus/people.js?v=p2) and its stylesheet; the 3D hall is optional (hallload.js) and uses the render core, three r160 and people3d.js",
          "from '../olympus/people.js?v=p2'" in js and "../olympus/people.css?v=p2" in html and 'src="hallload.js' in html and "../olympus/render.js" in hall and "../jarvis/three.module.min.js" in hall and "../olympus/people3d.js" in hall
          and "figureInstanced" in hall)
    check("a. the 3D hall is calm: bloom <= .25, no neon colours, warm background and fog; LITE or no WebGL keeps the portrait wall", re.search(r"strength: 0\.(0\d|1\d|2[0-5]?)\b", hall) is not None and not AK.BANNED_LOOK.search(hall)
          and "'low' || q === 'off'" in hall and not re.search(r"#(?:0ff|00f|f0f|0f0)\b|#00ffff|#ff00ff", hall, re.I) and 'html[data-oly-lite="1"] .stage { display: none; }' in css)
    check("a. the request box: Copy for Claude, Export JSON, Clear all (two taps); the foot says paper and suggestions only and R next to every dollar",
          all(x in html for x in ("Copy for Claude", "Export JSON", "Clear all")) and "Tap again to clear all" in js and "paper and suggestions only" in html and "with its R" in html)
    check("a. make my character: a name, the looks, Randomise, Save; kept through the kit (olympus.me.v1), the page itself stores nothing", all(x in html for x in ("Make my character", "Randomise", "Save my character")) and "P.setMe(" in js and "localStorage" not in js)
    check("a. VOICES: a 'Voices' switch over the hall (off until tapped, through the kit), the hall lends its figures to the kit (P.stage: stageFor, release, walk, card; lip sync through the kit's speak / viseme / expression events),"
          " speech bubbles and work cards over the hall, 'Let them talk' in the Round table; stand-up, debate and the talks are said out loud with P.say",
          all(x in html for x in ('id="voiceBtn"', "Voices: off", 'id="hallCards"', "Let them talk", 'id="togetherChips"', 'id="togetherOut"')) and all(x in js for x in ("P.stage({", "P.say(", "P.voice.set(", "P.talkTogether(", "S.hall.stageFor(", "S.hall.walk(", "S.hall.release()", "voiced("))
          and all(x in hall for x in ("stageFor(i)", "release()", "walk(i)", "olympus:people:expression", "focus(i, off)")) and ".cardsover" in css)
    apps = json.loads(AK.read(os.path.join(AK.ROOT, "tools", "new_apps.json")))["apps"]
    row = next((a for a in apps if a["id"] == APP), None)
    scenes = "stars smoke coins embers neurons skyline torches threads streaks bars leaves columns shards rings maze".split()
    check("a. the wiring row in tools/new_apps.json (id, name, group, accent, glyph, description < 80, ambient, flavour from an existing scene, transition) and a section in docs/NEW_APPS_WIRING.md",
          row is not None and row["name"] == NAME and row["group"] in ("trading", "money", "life") and re.fullmatch(r"#[0-9a-f]{6}", row["accent"]) and len(row["description"]) < 80 and row["flavour"][0] in scenes
          and isinstance(row["transition"], dict) and "symposium" in AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md")).lower(), row)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const P = (id, kind, extra) => ({ id, kind, name: id.split(':').pop().toUpperCase(), title: 't', ...(extra || {}) });
  const people = [P('champion:a', 'champion'), P('scanner:x', 'scanner'), P('bot:lit', 'bot'), P('builder:b1', 'builder'), P('scanner:y', 'scanner'), P('mind', 'mind'), P('keeper:m', 'keeper'), P('champion:f', 'champion', { fallen: true }), P('bot:atlas', 'bot'), P('champion:c', 'champion')];
  o.order = C.order(people).map((p) => p.id);
  o.groups = C.groups(people).map((g) => g.name + ':' + g.people.length);
  const L = C.seats(37), L1 = C.seats(1), L0 = C.seats(0);
  const d = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
  o.seats = { n: L.seats.length, r: Math.round(L.r * 100) / 100, couches: L.couches, ring: L.seats.every((s) => Math.abs(Math.hypot(s.x, s.z) - L.r) < 1e-9), gap: Math.round(Math.min(...L.seats.map((s, i) => d(s, L.seats[(i + 1) % 37]))) * 100) / 100,
    faces: L.seats.every((s) => Math.abs(Math.sin(s.ry) * L.r + s.x) < 1e-6 && Math.abs(Math.cos(s.ry) * L.r + s.z) < 1e-6), one: [L1.seats.length, L1.r, L1.couches], zero: L0.seats.length, small: C.seats(4).r };
  const k = C.couchAt(L, 0), kLast = C.couchAt(L, L.couches - 1);
  o.couch = [Math.abs(Math.hypot(k.x, k.z) - L.r) < 0.1, k.wide, kLast.wide];
  o.front = [C.front(L, 0, 3), C.front(L, Math.PI, 1)[0], C.front(L, 0, 0).length, C.front(L, L.seats[9].a, 1)[0], C.front(L, 0, 99).length];
  o.turn = [Math.round(C.turn(0.1, 6.2) * 100) / 100, Math.round(C.turn(6.2, 0.1) * 100) / 100, C.turn(1, 1), Math.round(C.yawFor(L, 9) * 1000) === Math.round(L.seats[9].a * 1000), C.yawFor(L, 999)];
  o.scope = [C.scopeIds(people, 'all').length, C.scopeIds(people, 'bot'), C.scopeIds(people, 'nope').length, C.scopeIds(null, 'all').length, C.SCOPES.length];
  o.pairs = C.pairs(people).map((p) => p.a + '|' + p.b + '|' + p.topic);
  o.pairsNone = C.pairs([P('bot:lit', 'bot')]).length;
  o.trios = C.trios(people).map((g) => g.ids.join('+') + '|' + g.topic + '|' + g.label);
  o.triosNone = C.trios([P('bot:lit', 'bot')]).length;
  const now = Date.parse('2026-11-11T15:00:00Z'), F = (asof, extra) => ({ asof, status: 'idle', ...(extra || {}) });
  const rows = [{ person: people[2], facts: F('2026-11-11T14:00:00Z', { status: 'working' }) }, { person: people[1], facts: F('2026-11-11T14:30:00Z', { sample: true, status: 'sample' }) }, { person: people[5], facts: F('2026-11-08T10:00:00Z', { blocked: 'old' }) }, { person: people[3], facts: F('2026-11-10T09:00:00Z') }, { person: people[6], facts: F(null) }, { person: people[0], facts: F('2026-11-12T20:00:00Z') }];
  o.fresh = C.newFaces(rows, now, 12).map((r) => r.id + ':' + r.why);
  o.freshNone = [C.newFaces([], now).length, C.newFaces(null, now).length, C.newFaces(rows, now, 1).length];
  const h = C.headline(rows), hd = C.headline([{ person: people[1], facts: { sample: true, status: 'sample' } }]);
  o.head = [h.n, h.working, h.blocked, h.sample, h.demo, h.text, hd.demo, C.headline([]).demo, C.headline([]).text];
  const reqs = [{ rid: '1', id: 'bot:lit', name: 'LIT', text: 'first', time: '2026-11-11T10:00:00.000Z' }, { rid: '2', id: 'mind', name: 'M', text: 'think <b>', time: '2026-11-11T12:00:00.000Z' }, { rid: '3', id: 'bot:lit', name: 'LIT', text: 'second', time: '2026-11-11T11:00:00.000Z' }, { id: 'x' }, null];
  const g = C.groupRequests(reqs, (id) => (id === 'mind' ? 'Metis' : ''));
  o.req = [g.map((x) => x.id + ':' + x.name + ':' + x.rows.map((r) => r.text).join('/')), C.groupRequests(null).length];
  const j = JSON.parse(C.requestsJson(reqs, (id) => (id === 'mind' ? 'Metis' : ''), '2026-11-11T15:00:00Z'));
  o.json = [j.v, j.requests.length, j.requests[1].name, j.requests[1].text, j.exported, /Nothing here was sent/.test(j.what), Object.keys(j.requests[0]).sort().join(',')];
  o.when = [C.whenText('2026-11-11T10:05:33.000Z'), C.whenText('junk'), C.whenText(null)];
  const card = C.jarvisCard(h, 3, 1794355200.7), cd = C.jarvisCard(hd, 0, 5), c0 = C.jarvisCard(null, 0, 0), cok = C.jarvisCard({ n: 5, blocked: 0, working: 2, sample: 0, demo: false, text: 'x' }, 1, 9);
  o.card = [card.status, card.kpis.map((x) => x.label + '=' + x.value), card.lines.length, Number.isInteger(card.t), cd.status.level, c0.status.level, cok.status, Math.max(...card.lines.map((x) => x.length)) <= 120, JSON.stringify(card).length < 8192];
  // looks
  const LISTS = { SKINS: ['#a', '#b'], HAIRS: ['#c', '#d'], HAIR_STYLES: ['short', 'bun'], OUTFITS: ['#1', '#2', '#3', '#4'], BUILDS: ['slim'], EYES: ['dot', 'wide'], BROWS: ['flat'], MOUTHS: ['smile'] };
  let seed = 7; const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const looks = []; for (let i = 0; i < 40; i++) looks.push(C.randomLook(rand, LISTS));
  o.random = [looks.every((l) => LISTS.SKINS.indexOf(l.skin) >= 0 && LISTS.OUTFITS.indexOf(l.outfit) >= 0 && l.accent !== l.outfit && l.height >= 0.9 && l.height <= 1.1 && C.CARRY.indexOf(l.accessory) >= 0 && typeof l.face.glasses === 'boolean'), new Set(looks.map((l) => JSON.stringify(l))).size > 20];
  const spec = { skin: '#a', hair: '#c', hairStyle: 'bun', outfit: '#1', accent: '#2', build: 'slim', accessory: 'none', height: 1, face: { eyes: 'dot', brows: 'flat', mouth: 'smile', beard: 'none', glasses: false, freckles: false } };
  const l1 = C.setLook(C.lookOf(spec), 'face.eyes', 'wide'), l2 = C.setLook(l1, 'skin', '#b'), l3 = C.setLook(null, 'hairStyle', 'bun');
  o.look = [C.getLook(spec, 'face.eyes'), C.getLook(spec, 'skin'), l1.face.eyes, l1.skin, l2.skin, l2.face.eyes, C.lookOf(spec).face.eyes, l3.hairStyle, JSON.stringify(l3.face), C.LOOKS.length, C.LOOKS.every((x) => x.key && x.label && x.from), Object.keys(C.WORD).length > 25];
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
    check("b. colleagues sit together: bots, scanners, thinkers, builders, keepers, champions (the given order inside a craft)",
          o["order"] == ["bot:lit", "bot:atlas", "scanner:x", "scanner:y", "mind", "builder:b1", "keeper:m", "champion:a", "champion:f", "champion:c"] and o["groups"][0] == "Bots:2" and o["groups"][-1] == "Champions and rejected ideas:3", (o["order"], o["groups"]))
    s = o["seats"]
    check("b. 37 seats on one ring, two to a couch (19 couches), nobody closer than 0.7 to a neighbour, everyone faces the table; one person and nobody are handled",
          s["n"] == 37 and s["couches"] == 19 and s["ring"] is True and s["gap"] >= 0.7 and s["faces"] is True and s["one"] == [1, 2.3, 1] and s["zero"] == 1 and s["small"] == 2.3, s)
    check("b. a couch sits between its two seats; the odd last couch is a single", o["couch"] == [True, True, False], o["couch"])
    check("b. the seats in front of a camera angle (nearest first), and the shortest turn between two angles", o["front"][0][0] == 0 and set(o["front"][0]) == {0, 1, 36} and o["front"][1] in (18, 19) and o["front"][2] == 0 and o["front"][3] == 9 and o["front"][4] == 37
          and o["turn"] == [-0.18, 0.18, 0, True, 0], (o["front"], o["turn"]))
    check("b. who answers the round table: everyone, or one craft", o["scope"] == [10, ["bot:lit", "bot:atlas"], 0, 0, 7], o["scope"])
    check("b. the ready-made duels: two scanners, two champions, a bot against a rejected idea, a champion against a rejected idea, two bots, a builder and a thinker",
          o["pairs"][:3] == ["scanner:x|scanner:y|Who found more for the owner?", "champion:a|champion:c|Who makes more money?", "bot:lit|champion:f|What could go wrong?"] and len(o["pairs"]) == 6 and o["pairsNone"] == 0, o["pairs"])
    check("b. let them talk: ready-made groups of two or three (the bots, the scanners, a champion with a rejected idea and a bot, a builder with a thinker), each with a topic; one person alone gets none",
          o["trios"][0] == "bot:lit+bot:atlas|How did today go?|LIT and ATLAS" and o["trios"][1].startswith("scanner:x+scanner:y|What did you find?") and any(t.startswith("champion:a+champion:f+bot:lit|") for t in o["trios"])
          and any(t.startswith("builder:b1+mind|") for t in o["trios"]) and o["triosNone"] == 0, o["trios"])
    check("b. new and active today: only real files from the last day and a half, newest first; sample data, old files, missing and future times never count",
          o["fresh"] == ["bot:lit:working now", "builder:b1:updated today"] and o["freshNone"] == [0, 0, 1], (o["fresh"], o["freshNone"]))
    check("b. the headline counts people, working, blocked and sample; DEMO only when everyone shows sample data",
          o["head"][:5] == [6, 1, 1, 1, False] and o["head"][5] == "6 people in the hall. 1 working, 1 blocked, 1 showing sample data (not real)." and o["head"][6] is True and o["head"][7] is False and o["head"][8].startswith("0 people"), o["head"])
    check("b. the request box groups the notes per person (oldest note first, the person with the newest note first) and ignores junk rows",
          o["req"] == [["mind:Metis:think <b>", "bot:lit:LIT:first/second"], 0], o["req"])
    check("b. export JSON: v 1, every note with id, name, text (markup stripped) and time; it says nothing was sent", o["json"] == [1, 3, "Metis", "think b", "2026-11-11T15:00:00Z", True, "id,name,text,time"], o["json"])
    check("b. times read plainly in UTC", o["when"] == ["2026-11-11 10:05 UTC", "", ""], o["when"])
    c = o["card"]
    check("b. the Jarvis card: warn + '1 blocked', People / Working / Requests, two lines <= 120, integer t; demo -> off; all fine -> ok",
          c[0] == {"level": "warn", "label": "1 blocked"} and c[1] == ["People=6", "Working=1", "Requests=3"] and c[2] == 2 and c[3] is True and c[4] == "off" and c[5] == "off" and c[6] == {"level": "ok", "label": "Everyone is fine"} and c[7] is True and c[8] is True, c)
    check("b. Randomise always gives a valid look (trim differs from the chiton, height 0.9 to 1.1) and many different ones", o["random"] == [True, True], o["random"])
    check("b. changing one choice keeps the others (flat keys + face{})", o["look"] == ["dot", "#a", "wide", "#a", "#b", "wide", "dot", "bun", "{}", 11, True, True], o["look"])


# ------------------------------------------------------------------------------------------------ c. Chromium
def home_json():
    import time
    return json.dumps({"t": int(time.time()) - 120, "accounts": [
        {"id": "mffu50k_eval", "name": "Zlarior 50K", "conn": {"connected": True}, "eval": {"room": 1420, "mll": 2000, "to_target": 2580}, "pnl": {"today": 312, "week": 640}},
        {"id": "acctb", "name": "ATLAS 25K", "conn": {"connected": False}, "eval": {"room": 240, "mll": 1000}, "pnl": {"today": -60, "week": 140}}]})


WALL = "() => document.querySelectorAll('#wall .who').length"
STATE = "() => window.SYMPOSIUM.state()"
SHEET = """() => { const r = document.querySelector('.pp-root'); if (!r || r.hidden) return null; document.getAnimations().forEach((x) => { try { x.finish(); } catch (e) {} }); const s = r.querySelector('.pp-sheet').getBoundingClientRect(), i = r.querySelector('.pp-in').getBoundingClientRect();
  return { name: r.querySelector('.pp-name').textContent, title: r.querySelector('.pp-title').textContent, status: r.querySelector('.pp-sttext').textContent, them: [...r.querySelectorAll('.pp-them:not(.pp-typing) .pp-text')].map((e) => e.textContent), me: [...r.querySelectorAll('.pp-me .pp-text')].map((e) => e.textContent),
    chips: [...r.querySelectorAll('.pp-chip')].map((e) => e.textContent), src: [...r.querySelectorAll('.pp-src')].map((e) => e.textContent), face: !!r.querySelector('.pp-face svg'), bottom: Math.round(s.bottom), top: Math.round(s.top), inputBottom: Math.round(i.bottom), vh: innerHeight, mic: !r.querySelector('.pp-mic').hidden,
    voice: r.querySelector('.pp-tools .pp-btn:nth-child(4)').textContent, modal: r.querySelector('.pp-sheet').getAttribute('aria-modal'), typing: r.querySelectorAll('.pp-typing').length }; }"""


CARD = """(id) => { const P = window.OLYMPUS_PEOPLE, all = [...document.querySelectorAll('.pp-log .pp-card')], c = all[all.length - 1]; if (!c) return null;
  const bits = []; const tw = document.createTreeWalker(c, NodeFilter.SHOW_TEXT); while (tw.nextNode()) { if (tw.currentNode.parentNode.nodeName !== 'title') bits.push(tw.currentNode.nodeValue); }
  const text = bits.join(' \\n '), corp = P.talk.corpus(P.get(id), P.factsNow(id), []);
  return { title: c.querySelector('.pp-ctitle').textContent, src: c.querySelector('.pp-src').textContent, bars: c.querySelectorAll('.pp-chart rect').length, lines: c.querySelectorAll('.pp-cl').length, ung: P.talk.ungrounded(text, corp), n: all.length }; }"""
GROUNDED = """(rows) => { const P = window.OLYMPUS_PEOPLE, bad = []; for (const [id, text] of rows) { const u = P.talk.ungrounded(text, P.talk.corpus(P.get(id), P.factsNow(id), [])); if (u.length) bad.push(id + ': ' + u.join(',')); } return bad; }"""


def ask(p, text):
    n = p.evaluate("() => document.querySelectorAll('.pp-them:not(.pp-typing)').length")
    p.fill(".pp-in", text)
    p.press(".pp-in", "Enter")
    p.wait_for_function(f"() => document.querySelectorAll('.pp-them:not(.pp-typing)').length > {n} && !document.querySelector('.pp-typing')", timeout=15000)
    return p.evaluate(SHEET)


def pixel_spread(p, sel):
    """How much the pixels of an element differ (a blank or one-colour canvas is ~0)."""
    import io
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return 99
    im = Image.open(io.BytesIO(p.query_selector(sel).screenshot())).convert("L")
    return round(ImageStat.Stat(im).stddev[0], 1)


def test_people_lab():
    """The people lab (olympus/people-lab.html): every person on a turntable, every pose / face / mouth, the lineup within budget, non-blank at 390 x 844."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("d. people lab skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/olympus/people-lab.html?still=1")
            p.wait_for_function("window.PEOPLE_LAB && window.PEOPLE_LAB.ready()", timeout=120000, polling=300)
            p.wait_for_timeout(800)
            info = p.evaluate("window.PEOPLE_LAB.info()")
            if not info.get("turn"):
                check("d. people lab: no WebGL here, the portraits stay", p.evaluate("document.querySelectorAll('#grid .cell').length") > 30)
                return
            ln = info["line"]
            check(f"d. the lab's lineup: {ln['people']} people in {ln['calls']} draw calls and {ln['tris']} triangles (<= 45 / 160k; the crowd is {ln['crowdCalls']} draw calls)",
                  ln["calls"] <= 45 and ln["tris"] <= 160000 and ln["crowdCalls"] == 2, ln)
            ids = p.evaluate("window.PEOPLE_LAB.ids()")
            states = []
            for k, pose in enumerate(["wave", "think", "hammer", "write", "read", "weigh", "telescope", "type", "carry", "cheer", "shrug", "slump"]):
                r = p.evaluate("(o) => window.PEOPLE_LAB.show(o)", {"id": ids[k % len(ids)], "pose": pose, "expr": "happy" if k % 2 else "thinking", "angle": 0.3, "frames": 14 if pose in ("wave", "cheer", "shrug") else 40})
                states.append((pose, r["state"]["pose"], r["triangles"]))
            check("d. every pose plays on a real person (the lab's turntable), within the figure budget", all(a == b and t <= 12000 for a, b, t in states), states)
            spreads = []
            for e in ["neutral", "happy", "surprised"]:
                p.evaluate("(o) => window.PEOPLE_LAB.show(o)", {"id": ids[0], "pose": "idle", "expr": e, "mouth": "O" if e == "surprised" else None, "angle": 0})
                spreads.append(pixel_spread(p, "#turn"))
            check(f"d. the turntable at 390 x 844 is not blank (pixel spread {spreads})", min(spreads) > 12, spreads)
            AK.shot(p, "people-lab-390")
            check("d. the lab's buttons are >= 44 px taps; no sideways scroll; no console error, nothing off origin", AK.taps(p) == [] and AK.no_sideways(p) and errs == [] and off == [], (AK.taps(p)[:4], errs[:3], off[:3]))
            ctx.close()
    finally:
        srv.shutdown()


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve(overrides={"/home.json": home_json()})
    try:
        with AK.browser() as br:
            # ---- 1. LITE at 390 x 844: the portrait wall, a talk, a request, the box, round table, stand-up, debate, me
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True)
            AK.open_app(p, origin, APP, "?fast=1")
            st = p.evaluate(STATE)
            n = st["n"]
            check(f"c. LITE 390 x 844: the hall opens as a wall of {n} portraits (no 3D), the status line counts people, working and blocked", n >= 30 and p.evaluate(WALL) == n and st["hall"] is False and st["lite"] is True and not p.is_visible("#stage")
                  and re.match(rf"{n} people in the hall\. \d+ working, \d+ blocked", p.inner_text("#status")) is not None and p.is_visible("#lite"), (st, p.inner_text("#status")))
            check("c. every portrait is the kit's cartoon avatar (an inline SVG, 56 px) with the person's name; Meet groups everyone by craft with a status pill and what they are doing",
                  p.evaluate("() => [...document.querySelectorAll('#wall .who')].every((b) => b.querySelector('svg.pp-portrait') && b.querySelector('.whoname').textContent && b.getBoundingClientRect().height >= 44)")
                  and p.evaluate("() => document.querySelectorAll('#meetList .pcard').length") == n and p.evaluate("() => document.querySelectorAll('#meetList .grouph').length") == 6
                  and p.evaluate("() => [...document.querySelectorAll('#meetList .pcard')].every((c) => c.querySelector('.pill').textContent && c.querySelector('.pdoing').textContent.length > 8)"))
            check("c. the real home.json makes LIT 'Working' and ATLAS 'Stale'; a worker without a file says 'Sample data'",
                  p.inner_text('.pcard[data-id="bot:lit"] .pill') == "Working" and p.inner_text('.pcard[data-id="bot:atlas"] .pill') == "Stale" and p.inner_text('.pcard[data-id="scanner:sibyl"] .pill') == "Sample data")
            check("c. taps >= 44 px, no sideways scroll, nothing in Jarvis's corner", AK.taps(p) == [] and AK.no_sideways(p) and AK.corner(p) == [], (AK.taps(p), AK.corner(p)))
            AK.shot(p, "symposium-lite-390")
            p.evaluate("window.scrollTo(0, 0)")
            p.click('.pcard[data-id="bot:lit"]')
            p.wait_for_function("() => document.querySelectorAll('.pp-them .pp-text').length > 0", timeout=15000)
            s = p.evaluate(SHEET)
            check("c. tap LIT: the chat sheet opens (a modal dialog) with the portrait, name, title and status dot; the greeting uses the time of day and LIT's real numbers; four suggested questions",
                  s and s["name"] == "Phoibos" and "LIT" in s["title"] and s["status"].startswith("Working") and s["face"] and s["modal"] == "true" and re.match(r"(Good (morning|afternoon|evening))", s["them"][0]) is not None
                  and "+$312 today" in s["them"][0] and len(s["chips"]) == 6 and s["chips"][4:] == ["Show me your work", "Walk with me"] and s["voice"] == "Voice: off", s)
            check("c. the sheet fits the screen: its text box is on screen above the bottom edge", s["bottom"] <= s["vh"] + 1 and s["inputBottom"] <= s["vh"] and s["top"] >= 0, s)
            a1 = ask(p, "how much drawdown is left")
            a2 = ask(p, "buy it now")
            check("c. a typed question is answered from the facts with its source; an order is refused in character",
                  a1["them"][-1].startswith("Drawdown left $1,420 of $2,000 max loss.") and a1["me"][-1] == "how much drawdown is left" and any("home.json" in x for x in a1["src"]) and a2["them"][-1].startswith("I can't place orders: paper and suggestions only."), (a1["them"][-1], a2["them"][-1]))
            p.click(".pp-chip >> nth=0")
            p.wait_for_function("() => document.querySelectorAll('.pp-them:not(.pp-typing)').length >= 4 && !document.querySelector('.pp-typing')", timeout=15000)
            check("c. a suggestion chip asks its question; every tap target in the sheet is at least 44 px", len(p.evaluate(SHEET)["me"]) == 3 and AK.taps(p) == [], AK.taps(p))
            AK.shot(p, "symposium-chat-390")
            w = ask(p, "what are you working on?")
            c = p.evaluate(CARD, "bot:lit")
            check("c. SHOW WORK: 'what are you working on?' answers AND puts LIT's work card in the chat: its paper account with today / week / drawdown, the source (home.json), every number on it from LIT's own facts",
                  c and c["title"] == "My paper account" and c["lines"] >= 3 and "home.json" in c["src"] and c["ung"] == [] and len(w["them"]) >= 4, c)
            check("c. the card's taps are >= 44 px and nothing scrolls sideways", AK.taps(p) == [] and AK.no_sideways(p), AK.taps(p))
            p.click(".pp-tools .pp-btn:nth-child(4)")
            on = [p.inner_text(".pp-tools .pp-btn:nth-child(4)"), p.evaluate("localStorage.getItem('olympus.people.speak')")]
            p.wait_for_timeout(300)
            p.click(".pp-tools .pp-btn:nth-child(4)")
            off2 = [p.inner_text(".pp-tools .pp-btn:nth-child(4)"), p.evaluate("localStorage.getItem('olympus.people.speak')")]
            check("c. VOICE: one tap turns LIT's own voice on (remembered on this phone), a second tap off; nothing breaks without a phone voice (murmur + captions)", on == ["Voice: on", "1"] and off2 == ["Voice: off", "0"], (on, off2))
            p.evaluate("() => { window.OLYMPUS = window.OLYMPUS || {}; window.OLYMPUS.go = (u) => { window.__went = u; }; }")
            n0 = p.evaluate("() => document.querySelectorAll('.pp-them .pp-text').length")
            p.fill(".pp-in", "walk with me")
            p.press(".pp-in", "Enter")
            p.wait_for_function("() => !!window.__went", timeout=10000)
            went, said = p.evaluate("() => window.__went"), p.evaluate("() => [...document.querySelectorAll('.pp-them .pp-text')].pop().textContent")
            check("c. WALK WITH ME: LIT says where its work lives and leads you there (its own app)", said.startswith("Walk with me. My work lives in") and went.startswith("../") and went.endswith("/") and p.evaluate("() => document.querySelectorAll('.pp-them .pp-text').length") == n0 + 1, (said, went))
            p.click(".pp-tools .pp-btn >> text=Leave a request")
            p.fill(".pp-reqtext", "Show the stop distance on the card")
            p.click(".pp-req .pp-primary")
            p.wait_for_function("() => /Noted/.test(document.querySelector('.pp-log').textContent)", timeout=8000)
            stored = json.loads(p.evaluate("localStorage.getItem('olympus.requests.v1')"))
            check("c. 'Leave a request' saves the note on this phone (olympus.requests.v1: id, text, time) and says nothing was sent", len(stored) == 1 and stored[0]["id"] == "bot:lit" and stored[0]["text"] == "Show the stop distance on the card" and "nothing was sent" in p.inner_text(".pp-log"), stored)
            p.keyboard.press("Escape")
            p.wait_for_function("() => document.querySelector('.pp-root').hidden", timeout=5000)
            check("c. Escape closes the sheet and the page scrolls again", not p.evaluate("document.documentElement.classList.contains('pp-open')"))
            # requests tab
            p.click("#tab-requests")
            p.fill("#reqText", "Check the weather picks")
            p.select_option("#reqWho", "scanner:sibyl")
            p.click("#reqForm button[type=submit]")
            p.wait_for_function("() => document.querySelectorAll('#reqList .reqgroup').length === 2", timeout=8000)
            p.click("#reqCopy")
            p.wait_for_function("() => !document.getElementById('reqBlock').hidden", timeout=8000)
            block = p.input_value("#reqBlock")
            check("c. the request box: the notes grouped per person, and 'Copy for Claude' gives one text block with both people",
                  "For Phoibos (bot:lit" in block and "Show the stop distance on the card" in block and "For Manto (scanner:sibyl" in block and "Check the weather picks" in block and block.startswith("Requests from the owner"), block[:300])
            with p.expect_download(timeout=8000) as dl:
                p.click("#reqExport")
            exported = json.loads(open(dl.value.path(), encoding="utf-8").read())
            check("c. 'Export JSON' saves olympus-requests.json with both notes", dl.value.suggested_filename == "olympus-requests.json" and len(exported["requests"]) == 2 and exported["requests"][0]["name"] == "Phoibos", exported)
            check("c. the request box at 390 px: taps >= 44 px, no sideways scroll", AK.taps(p) == [] and AK.no_sideways(p), AK.taps(p))
            AK.shot(p, "symposium-requests-390")
            p.click("#reqList .reqrow button >> nth=0")
            p.click("#reqClear")
            armed = p.inner_text("#reqClear")
            p.click("#reqClear")
            check("c. remove one note, then 'Clear all' asks for a second tap and empties the box", armed == "Tap again to clear all" and p.evaluate("localStorage.getItem('olympus.requests.v1')") == "[]" and "The box is empty" in p.inner_text("#reqList"), armed)
            # round table
            p.click("#tab-table")
            p.click("#tableChips .chip >> nth=0")
            p.wait_for_function("() => { const s = window.SYMPOSIUM.state(); return s.table && document.querySelectorAll('#tableOut .trow').length === s.table.n; }", timeout=20000)
            tb = p.evaluate(STATE)["table"]
            first = p.evaluate("() => [...document.querySelectorAll('#tableOut .trow')].slice(0, 3).map((r) => r.querySelector('.tname').textContent + ': ' + r.querySelector('.ttext').textContent)")
            check(f"c. round table 'How did yesterday go?': {tb['n']} of {tb['asked']} answer in turn, each from their own data, each with a portrait you can tap", tb["q"] == "How did yesterday go?" and tb["n"] == tb["asked"] == n and all(len(x) > 20 for x in first)
                  and re.match(rf"\d+ of {n} had something to say", p.inner_text("#tableNote")) is not None, (tb["n"], first))
            p.select_option("#tableScope", "bot")
            p.fill("#tableQ", "how much drawdown is left")
            p.press("#tableQ", "Enter")
            p.wait_for_function("() => { const s = window.SYMPOSIUM.state(); return s.table && s.table.q === 'how much drawdown is left' && document.querySelectorAll('#tableOut .trow').length === s.table.n; }", timeout=20000)
            bots = p.evaluate("() => [...document.querySelectorAll('#tableOut .trow .ttext')].map((e) => e.textContent)")
            check("c. a typed question for the bots only: four answers, LIT's with 'Drawdown left $1,420 of $2,000 max loss'", len(bots) == 4 and any(b.startswith("Drawdown left $1,420 of $2,000 max loss") for b in bots), bots)
            AK.shot(p, "symposium-table-390")
            trios = p.evaluate("() => window.SYMPOSIUM.trios().map((g) => g.label)")
            p.click("#togetherChips .chip >> nth=0")
            p.wait_for_function("() => { const t = window.SYMPOSIUM.together(); return t && t.done; }", timeout=30000)
            tg = p.evaluate("() => window.SYMPOSIUM.together()")
            rows = p.evaluate("() => [...document.querySelectorAll('#togetherOut .trow')].map((r) => [r.classList.contains('right'), r.querySelector('.tname').textContent, r.querySelector('.ttext').textContent])")
            bad = p.evaluate(GROUNDED, [[t["id"], t["text"]] for t in tg["turns"]])
            check(f"c. LET THEM TALK: {len(trios)} ready-made groups; the bots talk to each other ({tg['n']} turns, by name, one asks another what could go wrong), each number from the speaker's own facts, then a neutral summary",
                  len(trios) >= 3 and tg["n"] >= 5 and len(rows) == tg["n"] and bad == [] and any("what could go wrong" in r[2] for r in rows) and p.is_visible("#togetherBox") and "not a forecast" in p.inner_text("#togetherSummary"), (trios, tg, bad))
            check("c. the talk at 390 px: taps >= 44 px, no sideways scroll", AK.taps(p) == [] and AK.no_sideways(p), AK.taps(p))
            # stand-up
            p.click("#tab-standup")
            lines = p.evaluate("() => [...document.querySelectorAll('#suList .ttext')].map((e) => e.textContent)")
            summary = p.inner_text("#suSummary")
            check("c. the stand-up: one 'Yesterday / Today / Blocked' line per person and a 'Who is blocked' summary that names ATLAS's keeper (not connected)",
                  len(lines) == n and all(re.match(r"Yesterday: .+ Today: .+ Blocked: .+", x) for x in lines) and summary.startswith("Blocked: ") and "Telamon" in summary and p.evaluate("() => document.querySelectorAll('#suBlockedList li').length") >= 1, (len(lines), summary))
            p.click("#suPlay")
            p.wait_for_function("() => document.getElementById('suName').textContent.indexOf(' of ') > 0", timeout=8000)
            mid = p.inner_text("#suName")
            p.wait_for_function("() => !window.SYMPOSIUM.state().suOn && document.getElementById('suName').textContent === 'That was everyone.'", timeout=30000)
            check("c. 'Play the stand-up' walks through everyone like a meeting (1 of N ...) and ends on the blocked summary", re.search(rf"\(\d+ of {n}\)", mid) is not None and p.inner_text("#suLine") == summary and p.is_visible("#suPlay"), mid)
            AK.shot(p, "symposium-standup-390")
            # debate
            p.click("#tab-debate")
            chips = p.evaluate("() => [...document.querySelectorAll('#dbPairs .chip')].map((e) => e.textContent)")
            p.click("#dbPairs .chip >> nth=1")
            p.wait_for_function("() => !document.getElementById('dbSummaryBox').hidden", timeout=20000)
            turns = p.evaluate("() => [...document.querySelectorAll('#dbOut .trow')].map((r) => [r.classList.contains('right'), r.querySelector('.ttext').textContent])")
            dsum = p.inner_text("#dbSummary")
            check("c. a debate between two champions: six turns, left and right, real numbers ($ and profit factor), then a neutral summary that names both and picks no winner",
                  len(chips) >= 4 and len(turns) == 6 and [t[0] for t in turns] == [False, True, False, True, False, True] and any("$" in t[1] for t in turns) and dsum.startswith("Neutral summary.") and "not a forecast" in dsum and "winner" not in dsum, (chips, dsum))
            p.select_option("#dbB", p.evaluate("document.getElementById('dbA').value"))
            p.click("#dbGo")
            p.wait_for_function("() => /Pick two different people/.test(document.getElementById('dbOut').textContent)", timeout=8000)
            check("c. the same person twice is refused politely; the debate at 390 px: taps >= 44 px, no sideways scroll", AK.taps(p) == [] and AK.no_sideways(p), AK.taps(p))
            AK.shot(p, "symposium-debate-390")
            # me
            p.click("#tab-me")
            p.wait_for_function("() => document.querySelectorAll('#meOptions .lookrow').length === 11", timeout=8000)
            before = p.evaluate("() => document.querySelector('#meFace svg').outerHTML.length + '|' + JSON.stringify(window.SYMPOSIUM.state().look)")
            p.click("#meRandom")
            after = p.evaluate("() => document.querySelector('#meFace svg').outerHTML.length + '|' + JSON.stringify(window.SYMPOSIUM.state().look)")
            p.click('#meOptions [data-key="hairStyle"][data-val="bun"]')
            p.click("#meGlasses") if not p.evaluate("window.SYMPOSIUM.state().look.face.glasses") else None
            p.fill("#meName", "Alex")
            p.click("#meSave")
            me = json.loads(p.evaluate("localStorage.getItem('olympus.me.v1')"))
            check("c. make my character: eleven rows of choices, Randomise changes the face, a tap picks a hair style and glasses, Save keeps name + look in olympus.me.v1 (LITE: the 2D preview only)",
                  before != after and me["name"] == "Alex" and me["look"]["hairStyle"] == "bun" and me["look"]["face"]["glasses"] is True and p.inner_text("#meNote").startswith("Saved. Alex")
                  and p.get_attribute('#meOptions [data-key="hairStyle"][data-val="bun"]', "aria-pressed") == "true" and not p.is_visible("#meCanvas") and p.evaluate(STATE)["turn"] is False, me)
            check("c. the character page at 390 px: every swatch and choice >= 44 px, no sideways scroll", AK.taps(p) == [] and AK.no_sideways(p), AK.taps(p))
            AK.shot(p, "symposium-me-390")
            p.click("#tab-meet")
            p.click('.pcard[data-id="mind"]')
            p.wait_for_function("() => document.querySelectorAll('.pp-them .pp-text').length > 0", timeout=15000)
            g = p.evaluate(SHEET)
            a3 = ask(p, "do you remember me")
            check("c. the next person greets the owner by name; the chat shows his own character; a person remembers only his last question, on this phone",
                  "Alex" in g["them"][0] and p.evaluate("() => !!document.querySelector('.pp-me .pp-ava svg')") and ("first talk on this phone" in a3["them"][-1] or "Last time you asked me" in a3["them"][-1]), (g["them"][0], a3["them"][-1]))
            p.keyboard.press("Escape")
            check("c. LITE run: no console error and nothing requested off the page's origin", errs == [] and off == [], (errs[:4], off[:4]))
            ctx.close()

            # ---- 2. 375 x 667, reduced motion, people.json missing -> the built-in cast
            srv2, origin2 = AK.serve(overrides={"/olympus/people.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin2, 375, 667, reduced=True, lite=True)
            AK.open_app(p, origin2, APP, "?demo=1")
            st = p.evaluate(STATE)
            check("c. 375 x 667 with no people.json: the built-in cast of 14 (never blank), the DEMO tag, and the status says the roster file is missing",
                  st["n"] == 14 and p.evaluate(WALL) == 14 and p.is_visible("#demo") and "built-in cast" in p.inner_text("#status"), (st["n"], p.inner_text("#status")))
            check("c. 375 x 667: taps >= 44 px, no sideways scroll, nothing in Jarvis's corner", AK.taps(p) == [] and AK.no_sideways(p) and AK.corner(p) == [], (AK.taps(p), AK.corner(p)))
            p.evaluate("window.scrollTo(0, 0)")
            p.click("#wall .who >> nth=2")
            p.wait_for_function("() => document.querySelectorAll('.pp-them .pp-text').length > 0", timeout=15000)
            s = p.evaluate(SHEET)
            a = ask(p, "what did you find")
            check("c. 375 x 667: the chat sheet fits (text box on screen), sample numbers are labelled 'Sample data, not real', taps >= 44 px, reduced motion shows no typing dots afterwards",
                  s["bottom"] <= 668 and s["inputBottom"] <= 667 and s["top"] >= 0 and "Sample data, not real" in a["them"][-1] and a["typing"] == 0 and AK.taps(p) == [], (s, a["them"][-1], AK.taps(p)))
            AK.shot(p, "symposium-chat-375")
            p.keyboard.press("Escape")
            p.click("#tab-standup")
            p.click("#suPlay")
            p.wait_for_function("() => document.getElementById('suName').textContent.indexOf('1 of 14') > 0", timeout=8000)
            p.click("#suNext")
            two = p.inner_text("#suName")
            p.click("#suStop")
            check("c. the stand-up has Next and Stop; no console error, nothing off origin", "(2 of 14)" in two and p.is_visible("#suPlay") and errs == [] and off == [], (two, errs[:4], off[:4]))
            ctx.close()
            srv2.shutdown()

            # ---- 3. high quality: the 3D hall (when WebGL is there)
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?q=high&direct=0")
            p.wait_for_timeout(1500)
            st = p.evaluate(STATE)
            if st["hall"]:
                check(f"c. high: the 3D hall is up: everyone on couches around the table in {st['calls']} draw calls (<= 40), {st['tags']} tappable portraits over the people facing you",
                      0 < st["calls"] <= 40 and 1 <= st["tags"] <= 7 and p.is_visible("#hall3d") and not p.is_visible("#wall") and p.inner_text("#viewBtn") == "Show as a list", st)
                check("c. the portraits over the hall are >= 44 px taps and the page has no sideways scroll", AK.taps(p) == [] and AK.no_sideways(p), AK.taps(p))
                hv = p.evaluate("() => { const h = window.SYMPOSIUM_HALL; return h ? { close: h.closeUps().length, tris: h.triangles(), calls: h.drawCalls() } : null; }")
                check(f"c. people v2 in the hall: {hv and hv['close']} close-up figures across the table (the rest one crowd), {hv and hv['tris']} triangles (<= 160k), {hv and hv['calls']} draw calls (<= 40)",
                      hv is not None and 1 <= hv["close"] <= 5 and hv["tris"] <= 160000 and hv["calls"] <= 40, hv)
                spread = pixel_spread(p, "#hall3d")
                check(f"c. the hall at 390 x 844 is not blank (pixel spread {spread})", spread > 12, spread)
                AK.shot(p, "symposium-hall-390")
                p.evaluate("window.scrollTo(0, 0)")
                p.evaluate("() => document.querySelector('#hallTags .htag:not([hidden])').click()")
                p.wait_for_function("() => document.querySelectorAll('.pp-them .pp-text').length > 0", timeout=15000)
                check("c. tapping a portrait in the hall opens that person's chat", p.evaluate(SHEET)["name"] != "")
                p.wait_for_timeout(1800)
                sp = p.evaluate("() => window.SYMPOSIUM_HALL && window.SYMPOSIUM_HALL.speaker()")
                check("c. the one you talk to is a close-up figure that waves, then talks to you (pose wave / talk)", sp is not None and sp["pose"] in ("wave", "talk"), sp)
                p.wait_for_function("() => !!document.querySelector('#stage .pp-say')", timeout=8000)
                sp = p.evaluate("() => { const b = document.querySelector('#stage .pp-say'), r = b.getBoundingClientRect(), s = document.getElementById('stage').getBoundingClientRect(); return { who: b.querySelector('.pp-sayname').textContent, said: b.querySelector('.pp-sayon').textContent, h: Math.round(r.height), inside: r.left >= s.left - 1 && r.right <= s.right + 1 && r.top >= s.top - 1, speaker: window.SYMPOSIUM.speaking(), calls: window.SYMPOSIUM.state().calls, tagsHidden: document.getElementById('stage').classList.contains('speaking') }; }")
                p.wait_for_timeout(900)
                later = p.evaluate("() => { const b = document.querySelector('#stage .pp-say'); return b ? b.querySelector('.pp-sayon').textContent.length : -1; }")
                name = p.evaluate(SHEET)["name"]
                check("c. SPEECH IN THE WORLD: the person who talks becomes a full figure in the hall, an AGORA speech bubble with their name follows their head (inside the stage, >= 44 px), the words appear as spoken, the floating name tags step aside; still <= 45 draw calls",
                      sp["who"] == name and sp["inside"] and sp["h"] >= 44 and sp["speaker"] >= 0 and sp["tagsHidden"] and (later > len(sp["said"]) or later == -1) and 0 < sp["calls"] <= 45, (sp, later))
                pid = p.evaluate("() => window.SYMPOSIUM.people()[window.SYMPOSIUM.speaking()]")
                ask(p, "show me your work")
                p.wait_for_function("() => !!document.querySelector('#hallCards .pp-card')", timeout=8000)
                p.wait_for_timeout(1200)
                c = p.evaluate(CARD, pid)
                mini = p.evaluate("() => { const m = document.querySelector('#hallCards .pp-card'), r = m.getBoundingClientRect(), s = document.getElementById('stage').getBoundingClientRect(); return { mini: m.classList.contains('pp-mini'), inside: r.left >= s.left - 1 && r.right <= s.right + 1, w: Math.round(r.width) }; }")
                check("c. SHOW WORK in the hall: the work card in the chat (every number from that person's facts, with its source) and a small one beside the figure, inside the stage",
                      c and c["ung"] == [] and c["src"].startswith("From: ") and mini["mini"] and mini["inside"] and mini["w"] <= 180, (c, mini))
                AK.shot(p, "symposium-hall-chat-390")
                p.keyboard.press("Escape")
                p.wait_for_timeout(300)
                check("c. closing the chat puts the speaker back in the crowd and clears the card", p.evaluate("() => window.SYMPOSIUM.speaking()") == -1 and p.evaluate("() => document.querySelectorAll('#hallCards .pp-card').length") == 0)
                p.click("#viewBtn")
                check("c. 'Show as a list' swaps the hall for the portrait wall, and back is offered", p.is_visible("#wall") and not p.is_visible("#stage") and p.inner_text("#viewBtn") == "Show the 3D hall")
                p.click("#tab-me")
                p.wait_for_timeout(600)
                check("c. make my character has the live 3D turntable on high", p.evaluate(STATE)["turn"] is True and p.is_visible("#meCanvas"))
                AK.shot(p, "symposium-me-3d-390")
            else:
                check("c. high: no 3D here (" + (st["why"] or "no WebGL") + "): the portrait wall stays, never blank", p.evaluate(WALL) == st["n"] and p.is_visible("#wall"), st)
            check("c. high run: no console error and nothing off origin", errs == [] and off == [], (errs[:4], off[:4]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
        test_people_lab()
    AK.finish()
