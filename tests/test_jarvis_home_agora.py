"""Jarvis home, AGORA (2026-11-10): the calm front page, the districts and the courtyard. Static + node only (no browser; the browser side lives in
tests.test_jarvis_hub and tools/phone_fit_audit.py).
  a. one set of districts: districts.js = switcher.js DIST = atlas.js zones (same ids, same app lists; Atlas calls Money 'risk')
  b. no neon / violet / glow / techno left in the Jarvis UI files and the 3D scene (colours, fonts, text-shadow, bloom)
  c. home-data.js: the cards from facts (top 3 nudges, bots with "Drawdown left $X of $max loss", the Mint estimate with its range, the next event),
     never blank with nothing, demo data labelled, junk in -> plain words out
  d. courtyard.js: five doorways (one per district), instanced, LITE and still-frame rules, no renderer of its own
  e. the files: index.html has #htoday + the slim What's new banner (no toast over content), home-cards.js is an ES module
    python -X utf8 -m tests.test_jarvis_home_agora
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(js):
    r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=JV, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr[-600:])
    return json.loads(r.stdout)


def part_a():
    d = node("import('./districts.js').then((m) => console.log(JSON.stringify(m.DISTRICTS)))")
    sw = read(JV, "switcher.js")
    atlas = read(ROOT, "tools", "web_public", "atlas", "atlas.js")
    ok_sw = ok_atlas = True
    for x in d:
        m = re.search(r"\{ id: '%s', title: '%s', colour: '%s', ids: \[([^\]]*)\] \}" % (x["id"], x["title"], re.escape(x["colour"])), sw)
        ok_sw = ok_sw and bool(m) and re.findall(r"'([a-z0-9-]+)'", m.group(1)) == x["ids"]
        aid = "risk" if x["id"] == "money" else x["id"]
        m2 = re.search(r"\{ id:'%s', title:'%s', colour:'%s'[^\n]*?ids:\[([^\]]*)\]" % (aid, x["title"], re.escape(x["colour"])), atlas)
        ok_atlas = ok_atlas and bool(m2) and re.findall(r"'([a-z0-9-]+)'", m2.group(1)) == x["ids"]
    check("a. five districts in Atlas order (Market, Research, Money, Command, Life)", [x["title"] for x in d] == ["Market", "Research", "Money", "Command", "Life"], d)
    check("a. switcher.js DIST equals districts.js (ids, colours, app lists)", ok_sw)
    check("a. atlas.js zones equal districts.js (Atlas's 'risk' is Money)", ok_atlas)
    out = node("""import('./districts.js').then((m) => console.log(JSON.stringify({ a: m.districtOf({ id: 'zenith' }), b: m.districtOf({ id: 'mint' }), c: m.districtOf({ id: 'x-new', group: 'life' }), d: m.districtOf({ id: 'x-new' }),
        e: m.byDistrict([{ id: 'planner' }, { id: 'oracle' }, { id: 'zzz' }]).map((x) => [x.id, x.apps.length]), f: m.searchApps([{ id: 'mint', name: 'Mint', sub: 'money estimate' }, { id: 'oracle', name: 'Oracle' }], 'money est').map((a) => a.id) })))""")
    check("a. districtOf: the Atlas list first, else the app's group, else Command; byDistrict keeps empty districts; searchApps needs every word",
          out == {"a": "market", "b": "money", "c": "life", "d": "command", "e": [["market", 1], ["research", 0], ["money", 0], ["command", 1], ["life", 1]], "f": ["mint"]}, out)


def part_b():
    files = ["jarvis.css", "home3d.css", "home3d.js", "courtyard.js", "switcher.js", "home-cards.js", "home-data.js", "bots-ui.js", "assist-ui.js", "briefing.js", "districts.js"]
    bad = []
    for f in files:
        t = read(JV, f)
        for pat, why in [(r"#(?:a855f7|7c3aed|22d3ee|ff2bd6|1ff5a4|4fe3ff|34f5b0|ff7a1a)\b", "neon hex"), (r"125,\s*211,\s*252", "cyan fallback"), (r"text-shadow:\s*0 0", "glow text-shadow"),
                         (r"(?:Orbitron|Rajdhani)", "techno font"), (r"\bblur\((?:[3-9]\d)px", "heavy blur"), (r"\b(?:holographic|cyber|quantum)\b", "banned word")]:
            if re.search(pat, t) and not (f == "jarvis.css" and why == "techno font"):
                bad.append((f, why))
    check("b. no neon hex, cyan fallback, glow, techno font, heavy blur or banned word in the Jarvis UI files", not bad, bad)
    css = read(JV, "jarvis.css")
    check("b. jarvis.css: only the Agora theme tokens; no HUD ring, globe, grid floor, scanlines, projector pad, title glow",
          css.count(':root[data-theme="') <= 1 and not any(x in css for x in (".hudring", ".bgglobe", ".floor {", ".scan {", ".pad {", "glowT", "scanS")))
    h3 = read(JV, "home3d.js")
    check("b. home3d.js: bloom never raised, warm status colours (no 74,222,128 / 255,77,109), stars warm", "bloom" not in h3.lower().replace("bloom: bloom", "") and "74,222,128" not in h3 and "255,77,109" not in h3 and "setRGB(1, 0.92, 0.78)" in h3)
    bd = read(JV, "backdrop.js")
    m = re.search(r"bloom: \{ strength: ([0-9.]+)", bd)
    check("b. backdrop.js bloom strength <= 0.25", m and float(m.group(1)) <= 0.25, m and m.group(1))


def part_c():
    js = """
import * as H from './home-data.js';
const out = {};
const facts = { system: { todos: [{ id: 'atlas', level: 'warn', todo: 'ATLAS is close to its floor', app: 'zenith' }, { id: 'pc', level: 'bad', todo: 'Turn the PC on', app: 'zenith' }, { id: 'k', level: 'warn', todo: 'Kalshi not updating', app: 'kalshi' }, { id: 'x', level: 'warn', todo: 'Fourth thing', app: 'planner' }] },
  planner: { tasks: [{ title: 'Pay the invoice' }] }, apps: [] };
const n = H.nudgesFrom(facts, { nudges: () => [{ text: 'From the brain', tone: 'info' }] });
out.nudges = [n.items.map((x) => x.text), n.more];
const snap = { ok: true, bots: { lit: { size: '50K', today_pnl: 412, room: 1840, mll: 2000, room_frac: .92, status: 'idle', waiting: 'Waiting for London' }, atlas: { size: '25K', today_pnl: -96, room: 300, mll: 1500, room_frac: .2, status: 'idle' } } };
const bots = H.botsFrom(snap, { system: { rows: [] } });
out.bots = bots.map((b) => [b.name, b.level, H.drawdownLine(b)]);
out.dd = [H.drawdownLine({ room: 500 }), H.drawdownLine(null), H.drawdownLine({ room: -30, mll: 2000 })];
out.money = [H.moneyFrom({ total: { low: -42, base: 1495, high: 2547 }, counts: { ok: 0, stale: 0 } }), H.moneyFrom({ total: { low: 100, base: 400, high: 900 }, counts: { ok: 3, stale: 0 } }), H.moneyFrom({}), H.moneyFrom(null)];
const ev = { events: { events: [{ date: '2026-11-09', time: '08:30', title: 'Past', impact: 'low' }, { date: '2026-11-10', time: '14:00', title: 'Fed decision', impact: 'high' }, { date: '2026-11-17', time: '08:30', title: 'Later' }] } };
out.next = [H.nextEvent(ev, Date.parse('2026-11-10T15:00:00Z')), H.nextEvent(ev, Date.parse('2026-11-10T20:00:00Z')), H.nextEvent({}, Date.now()), H.nextEvent(null, Date.now())];
const empty = H.buildHome({});
out.empty = [empty.today.items.length, empty.bots.length, empty.money, empty.day.now, empty.day.next, empty.asks.length, empty.favs.length];
const demo = H.buildHome({ demo: true });
out.demo = [demo.demo, demo.today.items.length, demo.bots.length, demo.bots.map((b) => H.drawdownLine(b)), !!demo.money, !!demo.day.now, !!demo.day.next];
const junk = H.buildHome({ facts: 'x', snap: 7, money: [], events: 3, kairos: 'k', favs: 'nope', recent: { a: 1 }, apps: 5, api: { nudges() { throw new Error('boom'); } }, now: 'later' });
out.junk = [junk.today.items.length, junk.bots.length, junk.money, junk.favs.length];
const apps = [{ id: 'mint', name: 'Mint', glyph: 'M' }, { id: 'kairos', name: 'Kairos' }, { id: 'atlas', name: 'Atlas', glyph: 'A' }, { id: 'pythia', name: 'Pythia' }];
const fav = H.buildHome({ apps, favs: ['mint', 'ghost', 'atlas'], recent: ['atlas', 'kairos', 'pythia'] });
out.fav = [fav.favs.map((a) => a.id), fav.recent.map((a) => a.id), fav.recent.length && fav.favs[0].glyph, fav.recent[0].glyph];
console.log(JSON.stringify(out));
"""
    o = node(js)
    check("c. Today: at most 3 nudges, red before amber before info, the rest counted ('more')", o["nudges"][0][0] == "Turn the PC on" and len(o["nudges"][0]) == 3 and o["nudges"][1] == 3, o["nudges"])
    check("c. the bots strip: 'Drawdown left $X of $max loss' with both numbers; a close-to-floor account is amber / red",
          o["bots"] == [["Zlarior", "ok", "Drawdown left $1,840 of $2,000 max loss"], ["ATLAS", "bad", "Drawdown left $300 of $1,500 max loss"]]
          and o["dd"] == ["Drawdown left $500", "No drawdown number yet", "Drawdown left −$30 of $2,000 max loss"], (o["bots"], o["dd"]))
    mo = o["money"]
    check("c. Mint: an estimate with its low / base / high; example data flagged (live false), real data live; nothing = null",
          mo[0]["base"] == 1495 and mo[0]["low"] == -42 and mo[0]["high"] == 2547 and mo[0]["live"] is False and mo[1]["live"] is True and mo[2] is None and mo[3] is None, mo)
    nx = o["next"]
    check("c. Pythia: the next event at or after now (New York time), today's later event first, then the next dated one; no file = none",
          nx[0]["title"] == "Fed decision" and nx[0]["when"].startswith("Today 2:00 PM ET") and nx[0]["impact"] == "high" and nx[1]["title"] == "Later" and nx[2] is None and nx[3] is None, nx)
    check("c. nothing at all: empty parts (the cards then say plain words), the four ask chips still there", o["empty"] == [0, 0, None, None, None, 4, 0], o["empty"])
    check("c. demo: example nudges, two bots with their drawdown line, a money estimate and the market day, all flagged demo", o["demo"][0] is True and o["demo"][1] == 2 and o["demo"][2] == 2 and o["demo"][4] and o["demo"][5] and o["demo"][6]
          and o["demo"][3] == ["Drawdown left $1,840 of $2,000 max loss", "Drawdown left $1,240 of $1,500 max loss"], o["demo"])
    check("c. junk in (strings, numbers, a throwing API): no throw, empty parts", o["junk"] == [0, 0, None, 0], o["junk"])
    check("c. favourites keep their order and drop unknown ids; recent skips favourites; a glyph falls back to the first letter", o["fav"][0] == ["mint", "atlas"] and o["fav"][1] == ["kairos", "pythia"] and o["fav"][2] == "M" and o["fav"][3] == "K", o["fav"])
    hd = read(JV, "home-data.js")
    check("c. home-data.js: read only (no order / trade / arm words), no secrets, no key in any URL, 5 s timeout", not re.search(r"place_order|armLive|\.trade\(|apikey|api_key|token", hd, re.I) and "5000" in hd)


def part_d():
    c = read(JV, "courtyard.js")
    d = node("import('./courtyard.js').then((m) => console.log(JSON.stringify(m.DISTRICTS.map((x) => x.id))))")
    check("d. courtyard.js: five doorways, one per Atlas district, in order", d == ["market", "research", "money", "command", "life"], d)
    check("d. courtyard.js: instanced meshes only, no renderer / composer / render target / texture of its own, a still frame with reduced motion, LITE skips the paving and columns",
          c.count("inst(") >= 5 and not re.search(r"new T\.(?:WebGLRenderer|WebGLRenderTarget|EffectComposer|CanvasTexture)", c) and "matchMedia('(prefers-reduced-motion: reduce)')" in c and "if (!lite) {" in c and "AdditiveBlending" in c)
    check("d. courtyard.js: warm light, additive and faint: the doorway light stays under 0.2 strength (nothing reaches the bloom threshold)", "value: 0.16" in c and "UnrealBloom" not in c)
    h3 = read(JV, "home3d.js")
    check("d. home3d.js loads the courtyard after the scene is up and never lets it stop the home", "import('./courtyard.js" in h3 and ".catch(" in h3.split("import('./courtyard.js")[1].split("\n")[0])


def part_e():
    page = read(JV, "index.html")
    css = read(JV, "jarvis.css")
    check("e. index.html: the home cards mount (#htoday + home-cards.js module) and the Jarvis CSS is versioned", 'id="htoday"' in page and 'src="./home-cards.js?v=' in page and "jarvis.css?v=j16" in page)
    check("e. the What's new note is a slim banner in the page flow (#wnb, dismissible), not a toast over the top card; toasts sit above the dock",
          "function banner(" in page and "banner('Every app is its own dashboard" in page and ".wnb {" in css and "bottom: calc(var(--stack) + 8px)" in css and "top: auto" in css)
    hc = read(JV, "home-cards.js")
    check("e. home-cards.js: opens apps and asks only through the shell's [data-app] / [data-say] (no direct trading call), escapes everything, never blank", 'data-app="' in hc and "data-say" in hc and "esc(" in hc and "innerHTML = noteDemo" in hc and "No bot report yet" in hc)
    check("e. every tap target on the new cards is 44 px", all(x in css for x in (".hc-row { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 48px", ".hc-chip { min-height: 44px", ".hc-more { min-height: 44px")))
    sw = read(JV, "switcher.js")
    check("e. the orb: a two-step ring (districts + Search, then the district's apps + Back) and the map by district", all(x in sw for x in ("ringLevel", "nxSearch", "nxBack", "openDistrict", "data-nx-d=")))


def main():
    for part in (part_a, part_b, part_c, part_d, part_e):
        try:
            part()
        except Exception as e:  # noqa: BLE001
            check(part.__name__ + " ran", False, repr(e))
    n = sum(RES)
    print(f"\njarvis home agora: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
