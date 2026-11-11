"""POLIS (tools/web_public/polis/, the city home of OLYMPUS, AGORA look, 2026-11-11, docs/POLIS_25.md items 19-25) and its painted skyline module
olympus/polis-skyline.js + olympus/polis-skyline-sky.js.

  a. static: the files, the kit lines, the AGORA look, read only (published JSON of this site only), ES5 in every script, no CDN, the Jarvis card, the manifest, the fixture,
     the row in tools/new_apps.json and its wiring section
  b. node: the real sky (Polaris at New York's latitude, the noon Sun, the November sunset azimuth, Orion and the Pleiades up at 10 PM in November), the city map (every app placed once,
     in its district, at least 64 design units apart = 44 px taps), the core (fresh news, the ships, the treasury, a record, the assembly motions, the citizens' rolls, the weather)
  c. Chromium 390 x 844 (and 375 x 667, 1280 x 800): no console errors, a building per app with 44 px taps, tap shows its name, tap again enters, the plain list fallback, the night
     sky at a fixed night time (stars, constellations on screen, Orion named), fresh glow from a fresh jarvis.json, gold motes when today's money is up, the four ships, the assembly,
     the rolls, LITE and reduced motion still draw, no sideways scroll
    python -X utf8 -m tests.test_polis_page            (--static: parts a and b only)
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_polis_page
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "polis", "Polis"
check = AK.check
D = os.path.join(AK.WEB, APP)
OLY = os.path.join(AK.WEB, "olympus")
READS = ("../home.json", "../kalshi.json", "../olympus/people.json", "../ergasterion/queue.json", "./sky.json")
SCRIPTS = [os.path.join(OLY, "polis-skyline.js"), os.path.join(OLY, "polis-skyline-sky.js"), os.path.join(D, "poliscore.js"), os.path.join(D, "polis.js")]
NIGHT = "2026-11-12T03:00:00Z"   # 10 PM in New York on 11 November 2026


def test_static():
    AK.static_kit(APP, NAME, reads=READS)
    html = AK.read(os.path.join(D, "index.html"))
    es6 = []
    for p in SCRIPTS:
        src = re.sub(r"//[^\n]*|/\*.*?\*/", "", AK.read(p), flags=re.S)
        src = re.sub(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"", "''", src)
        for pat, what in ((r"=>", "arrow"), (r"\blet\s", "let"), (r"\bconst\s", "const"), (r"`", "template"), (r"\bclass\s+[A-Z]", "class"), (r"^\s*(?:import|export)\b", "module syntax"), (r"\.\.\.[a-zA-Z(\[]", "spread")):
            if re.search(pat, src, re.M):
                es6.append(f"{os.path.basename(p)}: {what}")
    check("a. ES5 in every script of the city (no arrows, let / const, template strings, classes, imports, spread): the page module is ES5 too", not es6, es6)
    joined = "".join(AK.read(p) for p in SCRIPTS) + html
    check("a. nothing from a CDN or another site at run time (no http(s) address in the scripts or the page body)", not re.search(r"https?://(?!www\.w3\.org)", re.sub(r"<!--.*?-->", "", joined, flags=re.S).split("</head>")[-1] + "".join(AK.read(p) for p in SCRIPTS)), None)
    order = [html.index(x) for x in ('src="../olympus/apps-list.js', 'src="../olympus/polis-skyline-sky.js', 'src="../olympus/polis-skyline.js', 'src="poliscore.js', 'type="module" src="polis.js')]
    check("a. the scripts load in order: the app list, the sky, the skyline, the core (plain scripts), then the page module", order == sorted(order), order)
    ids = ('id="hero"', 'id="pan"', 'id="world"', 'id="plaque"', 'id="pkEnter"', 'id="ships"', 'id="treasury"', 'id="motions"', 'id="consts"', 'id="rolls"', 'id="directory"', 'id="dirList"', 'class="skip"')
    check("a. the page has every part: the city (pan, world, plaque with Enter), harbour + treasury, assembly, night sky, rolls, the directory (list fallback) and a skip link to it",
          all(x in html for x in ids), [x for x in ids if x not in html])
    sky = AK.read(os.path.join(OLY, "polis-skyline-sky.js"))
    check("a. the sky method is written down in the module (RA / Dec J2000, sidereal time, hour angle, New York latitude, the projection)",
          all(w in sky for w in ("J2000", "sidereal", "hour angle", "40.7128", "projects alt / az")), None)
    sk = AK.read(os.path.join(OLY, "polis-skyline.js"))
    check("a. the skyline honours LITE and reduced motion (no loop, still frames) and pauses when hidden; tiles keep each canvas under 1024 px wide",
          "st.quality !== 'low'" in sk and "!st.reduced" in sk and "doc.hidden" in sk and "tileW = 1024" in sk, None)
    apps = json.load(open(os.path.join(ROOT, "tools", "new_apps.json"), encoding="utf-8"))
    row = next((a for a in apps["apps"] if a["id"] == APP), None)
    scenes = "stars smoke coins embers neurons skyline torches threads streaks bars leaves columns shards rings maze".split()
    wiring = AK.read(os.path.join(ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the row in tools/new_apps.json (an existing intro scene, a description under 80 characters) and its wiring section in docs/NEW_APPS_WIRING.md",
          row is not None and row["name"] == NAME and len(row["description"]) < 80 and row["flavour"][0] in scenes and "# Wiring POLIS" in wiring and APP not in apps.get("pending", []), row)


# ------------------------------------------------------------------------------------------------ b. node
HARNESS = r"""
global.self = global;
const SKY = require(process.argv[2]), SK = require(process.argv[3]), C = require(process.argv[4]), L = require(process.argv[5]);
const fs = require('fs'), people = JSON.parse(fs.readFileSync(process.argv[6], 'utf8')), queue = JSON.parse(fs.readFileSync(process.argv[7], 'utf8'));
const out = {};
const night = Date.parse('2026-11-12T03:00:00Z');
out.polaris = SKY.altaz(37.955, 89.264, night).alt;
const noon = SKY.sun(Date.parse('2026-11-11T17:00:00Z')); out.noon = [noon.alt, noon.az];
const set = SKY.sun(Date.parse('2026-11-11T21:40:00Z')); out.sunset = [set.alt, set.az];
const v = SKY.visible(night); out.up = v.up.map((u) => u.id); out.orion = v.up.find((u) => u.id === 'orion') || null;
out.phases = ['dawn', 'day', 'dusk', 'night'].map((p) => SKY.phase(SKY.timeFor(p, night)).name);
out.moon = SKY.moon(night); out.mw = SKY.milkyWay().length; out.nConst = SKY.CONSTELLATIONS.length;
out.lines = SKY.CONSTELLATIONS.every((c) => c.lines.every((l) => l[0] < c.stars.length && l[1] < c.stars.length));
const M = SK.layout(L); out.n = M.buildings.length; out.apps = L.length;
out.ids = M.buildings.map((b) => b.id).sort().join(',') === L.map((a) => a.id).sort().join(',');
out.groups = M.buildings.every((b) => b.district === (L.find((a) => a.id === b.id).group));
let minGap = 1e9; const rows = {}; M.buildings.forEach((b) => { (rows[b.district + b.row] = rows[b.district + b.row] || []).push(b.x); });
Object.values(rows).forEach((xs) => { xs.sort((a, b) => a - b); for (let i = 1; i < xs.length; i++) minGap = Math.min(minGap, xs[i] - xs[i - 1]); }); out.minGap = minGap;
out.zenith = M.buildings.find((b) => b.id === 'zenith'); out.mint = M.buildings.filter((b) => b.type === 'mint').map((b) => b.id);
out.inWorld = M.buildings.every((b) => b.x > 0 && b.x < M.W && b.y > 150 && b.y < M.H);
const pal = SK.palette(-20, false, {}), pd = SK.palette(30, false, {}), pk = SK.palette(2, false, {}), pr = SK.palette(30, false, { cloud: 1, rain: 1 });
out.pal = [pal.night, pal.stars, pd.night, pd.stars, pk.golden > 0.5, pr.strength < pd.strength * 0.6];
const nowS = 1794400000;
out.fresh = [C.fresh({ t: nowS - 3600, status: { level: 'ok' } }, nowS), C.fresh({ t: nowS - 3600, status: { level: 'off', label: 'Demo data' } }, nowS), C.fresh({ t: nowS - 200000, status: { level: 'ok' } }, nowS), C.fresh(null, nowS), C.fresh({ t: 'x', status: { level: 'warn' } }, nowS)];
const home = { live: { pc: { t: nowS - 120, running: true, blitz: { t: nowS - 60, eval: { today: -80 } } } }, board: { lit: { today_pnl: 412.5 }, atlas: { today_pnl: 0 } } };
const H = C.ships(home, { t: nowS - 50000, running: true, today_pnl: 3 }, nowS, {}); out.ships = H.ships.map((s) => s.key + ':' + s.state + ':' + s.usd); out.shipsDemo = H.demo;
out.stopped = C.ships({ live: { pc: { t: nowS - 60, running: false } }, board: { lit: { today_pnl: 0 } } }, null, nowS, {}).ships[0].state;
out.demoShips = C.ships(null, null, nowS, JSON.parse(fs.readFileSync(process.argv[8], 'utf8'))); out.demoShips = [out.demoShips.demo, out.demoShips.ships.map((s) => s.state).join(',')];
out.treasury = C.treasury(H); out.treasuryDown = C.treasury(C.ships({ live: { pc: { t: nowS - 60, running: true } }, board: { lit: { today_pnl: -50 } } }, null, nowS, {}));
const days = []; for (let i = 0; i < 10; i++) days.push(['2026-11-0' + i, 10 + i]); days.push(['2026-11-11', 25]);
out.record = [C.record(null, { today_pnl: 25, days }, nowS).on, C.record(null, { today_pnl: 15, days }, nowS).on, C.record(null, { today_pnl: 25, days: days.slice(0, 3) }, nowS).on];
const mhome = { live: { pc: { mind: { proposals: [{ id: 'a', idea: 'Half size after a buildup sweep', bot: 'lit', status: 'rejected', evidence: { h2: 'H2: PF 2.91 -> 3.23', h1: 'H1', r2125: 'ref', usd_month: -544 } }, { id: 'b', idea: 'Skip lunch for BLITZ', bot: 'blitz', status: 'candidate', evidence: { h2: 'H2 better', usd_month: 120 }, change: 'blitz.skip_lunch = true' }, { idea: '<b>x</b>', status: 'odd' }] } } } };
const A = C.motions(mhome, queue, {}); out.motions = [A.motions.length, A.motions[0].status, A.motions[0].stone, A.motions[1].usd_month, A.motions[2].title.indexOf('<') < 0, A.raised.length > 0, A.demo];
const A2 = C.motions(null, queue, {}); out.motions2 = [A2.motions.length, A2.raised.length, A2.src]; const A3 = C.motions(null, null, { motions: [{ title: 'x' }] }); out.motions3 = [A3.demo, A3.motions.length];
const R = C.citizens(people); out.rolls = [R.n, people.people.length, R.list.every((p) => p.name && p.role && p.deme), R.list[0].id.split(':')[0]];
out.wx = [C.weather(null, 'rain', nowS).rain, C.weather({ t: nowS - 60, cloud: 0.5, text: 'Cloudy' }, null, nowS).src, C.weather({ t: nowS - 90000, cloud: 1 }, null, nowS).src, C.weather(null, null, nowS).cloud];
out.money = [C.money(412.5), C.money(-80), C.money(2000), C.money(0)];
console.log(JSON.stringify(out));
"""


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("b. node is installed (needed for the core checks)", False, "no node")
        return
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"polis-test-{os.getpid()}.cjs")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(HARNESS)
    try:
        r = subprocess.run([exe, tmp, os.path.join(OLY, "polis-skyline-sky.js"), os.path.join(OLY, "polis-skyline.js"), os.path.join(D, "poliscore.js"), os.path.join(OLY, "apps-list.js"),
                            os.path.join(OLY, "people.json"), os.path.join(AK.WEB, "ergasterion", "queue.json"), os.path.join(D, "fixture.json")], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(tmp)
    if r.returncode:
        check("b. the node harness runs", False, r.stderr[-900:])
        return
    o = json.loads(r.stdout)
    check(f"b. the sky is real: Polaris stands at New York's latitude ({o['polaris']:.2f} deg, 40.0-41.5), the noon Sun on 11 Nov is ~31.6 deg up in the south ({o['noon'][0]:.1f} / {o['noon'][1]:.0f}), it sets in the west-south-west ({o['sunset'][1]:.0f} deg)",
          40.0 <= o["polaris"] <= 41.5 and 30.5 <= o["noon"][0] <= 32.5 and 170 <= o["noon"][1] <= 195 and 240 <= o["sunset"][1] <= 252 and abs(o["sunset"][0]) < 2, o)
    check(f"b. at 10 PM in New York in November Orion is rising in the east ({o['orion']}), the Pleiades, Taurus, Perseus, Cassiopeia and Draco are up; {o['nConst']} constellations, every line joins two of its own stars",
          o["orion"] and 60 <= o["orion"]["az"] <= 130 and 10 <= o["orion"]["alt"] <= 40 and {"pleiades", "taurus", "perseus", "cassiopeia", "draco", "pegasus"} <= set(o["up"]) and "scorpius" not in o["up"] and o["nConst"] >= 18 and o["lines"], o["up"])
    check("b. ?phase= finds a dawn, a day, a dusk and a night time on that New York day; the Milky Way band has 60 points; the Moon has a lit fraction", o["phases"] == ["dawn", "day", "dusk", "night"] and o["mw"] == 60 and 0 <= o["moon"]["frac"] <= 1, o["phases"])
    check(f"b. the city map: every app ({o['apps']}) is one building, in its own district (Trading on the Acropolis, Money at the harbour and mint, Life in the gardens), inside the picture",
          o["n"] == o["apps"] and o["ids"] and o["groups"] and o["inWorld"], o)
    check(f"b. buildings on a terrace stand at least 64 design units apart ({o['minGap']}): 44 px taps never overlap on a phone; Zenith is the Parthenon on the hilltop; the mint is the treasury",
          o["minGap"] >= 64 and o["zenith"]["type"] == "parthenon" and o["zenith"]["row"] == -1 and "mint" in o["mint"], o["minGap"])
    check("b. the light: deep night has stars and lit windows, noon has neither, the low Sun is golden, rain dims the sun light", o["pal"] == [1, 1, 0, 0, True, True], o["pal"])
    check("b. fresh news: a card from 1 hour ago glows, a demo / off card, a 2-day-old card, no card or a bad time never glow", o["fresh"][0] > 0.9 and o["fresh"][1:] == [0, 0, 0, 0], o["fresh"])
    check("b. the ships: LIT returning with +$412.50, ATLAS under sail, BLITZ returning with -$80, Kalshi in port (its report is 14 h old); a stopped bot stays in port; no data = the DEMO harbour",
          o["ships"] == ["lit:returning:412.5", "atlas:sail:0", "blitz:returning:-80", "kalshi:port:0"] and not o["shipsDemo"] and o["stopped"] == "port" and o["demoShips"] == [True, "sail,port,returning,sail"], o["ships"])
    check("b. the treasury: +$332.50 over the bots with a report today is up (gold motes); a red day is not", o["treasury"]["up"] and abs(o["treasury"]["today"] - 332.5) < 0.01 and not o["treasuryDown"]["up"], (o["treasury"], o["treasuryDown"]))
    check("b. a record (the shooting star) only when today beats every earlier day of at least 5 published days", o["record"] == [True, False, False], o["record"])
    check("b. the assembly: the Mind's proposals become motions (open ones first, white stone for a candidate, the $ a month kept, markup stripped), with the matters it raised",
          o["motions"][0] == 3 and o["motions"][1] == "candidate" and o["motions"][2] == "white" and o["motions"][4] and o["motions"][5] and not o["motions"][6], o["motions"])
    check("b. without home.json the board still shows the Mind's matters from ergasterion/queue.json; with nothing at all, the DEMO motions of the fixture", o["motions2"][0] == 0 and o["motions2"][1] >= 3 and "queue.json" in o["motions2"][2] and o["motions3"] == [True, 1], (o["motions2"], o["motions3"]))
    check(f"b. the citizens' rolls: every person of people.json ({o['rolls'][1]}) with a name, a role and a deme; the bots first", o["rolls"][0] == o["rolls"][1] and o["rolls"][2] and o["rolls"][3] == "bot", o["rolls"])
    check("b. the weather: ?wx= wins, a fresh sky.json is used, an old one is ignored, no file = a fair sky", o["wx"] == [0.8, "sky.json", "none", 0.12], o["wx"])
    check("b. dollars in plain words", o["money"] == ["+$412.50", "-$80", "+$2,000", "$0"], o["money"])


# ------------------------------------------------------------------------------------------------ c. the browser
def wait_ready(p):
    p.wait_for_function("window.POLIS && window.POLIS.ready() && window.POLIS.cardsDone()", timeout=120000, polling=300)
    p.wait_for_timeout(600)


CANVAS_STARS = """() => { const c = document.querySelector('.polis-canvas'), x = c.getContext('2d'), w = c.width, h = Math.round(c.height * 0.3);
  const d = x.getImageData(0, 0, w, h).data; let bright = 0, sum = 0; for (let i = 0; i < d.length; i += 4) { const l = (d[i] + d[i + 1] + d[i + 2]) / 3; sum += l; if (l > 170) bright++; }
  return { bright, mean: sum / (d.length / 4) }; }"""


def test_browser():
    try:
        import playwright  # noqa: F401
    except Exception:
        check("c. Playwright is installed", False, "no playwright")
        return
    now = int(time.time())
    fresh_card = json.dumps({"v": 1, "name": "Oracle", "status": {"level": "ok", "label": "Radar online"}, "kpis": [], "lines": [], "t": now - 1800, "theme": "#14110e"})
    home = json.dumps({"live": {"pc": {"t": now - 90, "running": True}}, "board": {"lit": {"today_pnl": 412.5}, "atlas": {"today_pnl": 0}}})
    srv, origin = AK.serve(overrides={"/oracle/jarvis.json": fresh_card})
    srv2, origin2 = AK.serve(overrides={"/home.json": home, "/oracle/jarvis.json": fresh_card})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?t={NIGHT}")
            wait_ready(p)
            n = p.evaluate("window.OLYMPUS_APPS_LIST.length")
            spots = p.evaluate("""() => [...document.querySelectorAll('.spot:not(.ship)')].map((e) => { const r = e.getBoundingClientRect(); return [e.dataset.id, Math.round(r.width), Math.round(r.height)]; })""")
            check(f"c. 390x844: the page is ready with no console errors, one 44 px button per building ({len(spots)} for {n} apps)", not errs and len(spots) == n and all(w >= 44 and h >= 44 for _, w, h in spots), errs[:3] or [s for s in spots if s[1] < 44 or s[2] < 44][:5])
            info = p.evaluate("window.POLIS.info()")
            px = p.evaluate(CANVAS_STARS)
            check(f"c. the night sky at a fixed night time (10 PM New York): phase night, stars at full strength, constellations on screen {info['onScreen'][:6]}, bright star pixels in the sky ({px['bright']}), a dark sky (mean {px['mean']:.0f})",
                  info["phase"] == "night" and info["stars"] > 0.95 and len(info["onScreen"]) >= 2 and px["bright"] >= 40 and px["mean"] < 90, (info, px))
            names = p.evaluate("[...document.querySelectorAll('#consts b')].map((b) => b.textContent)")
            check("c. the sky card names what is up now: Orion, the Pleiades and Draco among them", {"Orion", "The Pleiades", "Draco"} <= set(names), names)
            p.evaluate("window.POLIS.walk('life')")
            p.wait_for_timeout(900)
            info2 = p.evaluate("window.POLIS.info()")
            check("c. walking the city turns the sky (the azimuth at the centre moves east when you walk to the gardens)", info2["azCentre"] < info["azCentre"] - 20 or info2["azCentre"] > info["azCentre"] + 300, (info["azCentre"], info2["azCentre"]))
            # tap a building: its name; tap again: enter
            p.evaluate("window.POLIS.walk('trading')")
            p.wait_for_timeout(900)
            p.click('.spot[data-id="oracle"]')
            p.wait_for_timeout(300)
            plaque = p.evaluate("({ hidden: document.getElementById('plaque').hidden, name: document.getElementById('pkName').textContent, href: document.getElementById('pkEnter').getAttribute('href'), fresh: document.getElementById('pkFresh').textContent })")
            check("c. tap a building: the plaque shows its name, what it is, its fresh news and an Enter link to its folder", not plaque["hidden"] and plaque["name"] == "Oracle" and plaque["href"] == "../oracle/" and "Fresh news" in plaque["fresh"], plaque)
            st = p.evaluate("({ fresh: Object.keys(window.POLIS.state.fresh), n: window.POLIS.state.freshN })")
            check(f"c. fresh news glows: the Oracle card published 30 minutes ago is fresh; demo / off cards never glow ({st['n']} fresh)", "oracle" in st["fresh"] and "hestia" not in st["fresh"], st)
            with p.expect_navigation(timeout=30000):
                p.click('.spot[data-id="oracle"]')
            check("c. tap it again: you enter the app", p.url.rstrip("/").endswith("/oracle"), p.url)
            p.go_back()
            wait_ready(p)
            lst = p.evaluate("[...document.querySelectorAll('#dirList a.dl')].map((a) => [a.dataset.id, a.getAttribute('href'), Math.round(a.getBoundingClientRect().height)])")
            check(f"c. the plain list fallback: every app as a link ({len(lst)}), at least 44 px high, grouped by district", len(lst) == n and all(h >= 44 for _, _, h in lst) and p.evaluate("document.querySelectorAll('#dirList h3').length") == 3, lst[:3])
            ships = p.evaluate("[...document.querySelectorAll('#ships .ship')].map((a) => a.textContent)")
            sspots = p.evaluate("document.querySelectorAll('.spot.ship').length")
            check(f"c. the harbour: the four bots as ships in the list and on the map (DEMO here: no bot report on this test site): {[s[:24] for s in ships]}", len(ships) == 4 and sspots == 4 and "DEMO" in p.text_content("#harLead"), ships)
            mot = p.evaluate("document.querySelectorAll('#motions .motion').length")
            raised = p.evaluate("document.querySelectorAll('#raised li').length")
            check(f"c. the assembly board: the Mind's matters from ergasterion/queue.json ({raised}) and a stone for each motion", raised >= 3 and mot == 0 and "queue.json" in p.text_content("#asmLead"), (mot, raised))
            rolls = p.evaluate("document.querySelectorAll('#rolls .roll').length")
            p.click("#rollMore")
            rolls2 = p.evaluate("document.querySelectorAll('#rolls .roll').length")
            check(f"c. the citizens' rolls: 12 shown, all {rolls2} after 'Show all' (name, role, deme)", rolls == 12 and rolls2 >= 30 and "Deme of" in p.text_content("#rolls"), (rolls, rolls2))
            p.evaluate("window.scrollTo(0, 0)")
            bad = [x for x in AK.taps(p) if not x.startswith("spot")]
            check("c. every tap target outside the map is at least 44 px; nothing is under Jarvis's corner; no sideways scroll", not bad and not AK.corner(p) and AK.no_sideways(p), (bad[:5], AK.corner(p)))
            check("c. it reads only this site (nothing off-origin)", not off, off[:3])
            AK.shot(p, "polis-night")
            ctx.close()

            # money up: the treasury gives off gold motes; LIT comes back with cargo
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?phase=day&pan=money")
            wait_ready(p)
            p.wait_for_timeout(1500)
            m = p.evaluate("({ motes: window.POLIS.state.city.state.motes.length, up: window.POLIS.state.model.treasury.up, lit: window.POLIS.state.harbour.ships[0].state, demo: !document.getElementById('demo').hidden, tre: document.getElementById('treasury').textContent, phase: window.POLIS.info().phase, fps: window.POLIS.info().frames })")
            check(f"c. today's money up: gold motes rise over the mint ({m['motes']}), LIT returns with cargo, the treasury line says so; daylight; the loop runs ({m['fps']} frames)", m["up"] and m["motes"] > 0 and m["lit"] == "returning" and "+$412.50" in m["tre"] and m["phase"] == "day" and m["fps"] > 10 and not errs, (m, errs[:3]))
            ctx.close()

            # LITE and reduced motion: still frames, no loop, still the full city
            for lite, red in ((True, False), (False, True)):
                ctx, p, errs, seen, off = AK.page(br, origin, lite=lite, reduced=red)
                AK.open_app(p, origin, APP, "?phase=dusk")
                wait_ready(p)
                f1 = p.evaluate("window.POLIS.info().frames")
                p.wait_for_timeout(1200)
                f2 = p.evaluate("window.POLIS.info().frames")
                spots = p.evaluate("document.querySelectorAll('.spot:not(.ship)').length")
                check(f"c. {'LITE' if lite else 'reduced motion'}: the city draws ({f1} frames) but does not animate ({f2 - f1} more in 1.2 s), every building is there, no console errors", f1 >= 1 and f2 - f1 <= 2 and spots == n and not errs, (f1, f2, errs[:3]))
                ctx.close()

            # small phone and desktop
            for w, hgt in ((375, 667), (1280, 800)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=hgt)
                AK.open_app(p, origin, APP, "?phase=dawn")
                wait_ready(p)
                check(f"c. {w}x{hgt}: no console errors, no sideways page scroll, the map scrolls sideways inside its frame, the title is readable",
                      not errs and AK.no_sideways(p) and p.evaluate("document.getElementById('pan').scrollWidth > document.getElementById('pan').clientWidth") and p.is_visible("h1"), errs[:3])
                ctx.close()
    finally:
        srv.shutdown()
        srv2.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
