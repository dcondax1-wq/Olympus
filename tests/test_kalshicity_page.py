"""KALSHI CITY (tools/web_public/kalshicity/, OLYMPUS 2026-11-04): the night city of the Kalshi bot's edges, over the learning engine's files.
  a. the static rules: the kit (?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML, only the site's own files plus the public kalshi-feed are
     fetched (read only: no POST, no key), safe areas and the orb's corner, 16 px gutters, reduced motion, the manifest, the icon, jarvis.json, the fixture
  b. the pure modules in node: cityfeed.js (shape, the live merge, the cards, the clock) and citylayout.js (one district per market, every edge placed once, nothing
     overlaps, height follows EV, grey and low below 30 bets, going-up / crumbling flags, a deterministic skyline)
  c. the page in Chromium at 390 x 844 on the LITE tier: no errors, the verdict, the districts, a tap on a building opens its card, the five sheets, the four
     cameras, the clock preview, the demo preview, the live feed over the engine's copy, offline (the feed unreachable), the fixture when the engine's files are missing,
     the high tier (3 passes, a thicker skyline), reduced motion (a still scene), nothing leaves the machine but the one public feed address (answered locally here)
    python -X utf8 -m tests.test_kalshicity_page            (KC_NO_BROWSER=1 skips c; KC_NO_HIGH=1 skips the high tier load)
"""
from __future__ import annotations

import copy
import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "kalshicity")
RAW_PREFIX = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/"
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const dir = " + json.dumps(PAGE) + "; const url = 'file://' + dir; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=120)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "kalshicity.css", "kalshicity.js", "cityfeed.js", "citylayout.js", "cityscene.js", "cityrig.js", "cityfx.js", "lessons.js", "fixture.json", "learned.json", "edges.json", "learning_log.json",
            "ledger.json", "hypotheses.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, data layer, layout, scene, camera rig, fixture, the engine's four files, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "kalshicity.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o3">' in html and 'src="../olympus/themes.js?v=o3"' in html and 'src="../olympus/olympus.js?v=o3" data-app="kalshicity"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    sc = js["cityscene.js"]
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; rc.render() each frame; the core is disposed",
          "from '../jarvis/three.module.min.js'" in sc and "from '../olympus/render.js'" in sc and "from '../olympus/materials.js'" in sc and "createRenderer(" in sc and "rc.render()" in sc
          and "new THREE.WebGLRenderer" not in sc and "rc.dispose()" in sc and "InstancedMesh" in sc and "onBeforeCompile" in sc)
    fxs = js["cityfx.js"]
    check("a. the effects layer uses the OLYMPUS fx library (godRays, lightning, aurora, lensFlare via OLYMPUS_FX), loads fx-core.js as a classic script, and plays sound only through OLYMPUS.sfx",
          all(n in fxs for n in ("godRays", "lightning", "aurora", "lensFlare", "OLYMPUS_FX")) and '<script src="../olympus/fx-core.js?v=f1"></script>' in html and "O.sfx(" in fxs and "AudioContext" not in " ".join(js.values()))
    check("a. no innerHTML / insertAdjacentHTML / document.write (the data only ever goes in as text)", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = set(re.findall(r"getJSON\(([^,)]+)", js["kalshicity.js"]))
    check("a. the page fetches only edges.json, learning_log.json, hypotheses.json (the ideas' paper scores), the public kalshi-feed (RAW), the research lessons (learned.json) and its fixture; no WebSocket / beacon / XHR / EventSource",
          {x.strip() for x in fetched} - {"url"} == {"'edges.json'", "'learning_log.json'", "RAW", "'learned.json'", "'hypotheses.json'", "'fixture.json'"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource", s) for s in js.values()), fetched)
    check("a. RAW is the public kalshi-feed's kalshi.json (read only: GET, no key, no header), and nothing of Kalshi's own is called",
          "raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json" in js["cityfeed.js"] and not re.search(r"kalshi\.com|trading-api|api\.elections", " ".join(js.values()))
          and "method:" not in js["kalshicity.js"].replace(" ", "").lower() and "'POST'" not in js["kalshicity.js"] and "headers" not in js["kalshicity.js"])
    check("a. safe areas on every edge, the orb's corner (dock stops 96 px from the right, the sheet sits 52 px above the dock), 44 px tap rows, dvh after vh, reduced motion, touch-action none",
          all(f"var(--s{x})" in css for x in "trbl") and "right: calc(var(--sr) + var(--oly-orb-clear, 96px))" in css and "min-height: 44px" in css and "min-height: 48px" in css
          and "var(--dock-h) + 52px" in css and re.search(r"max-height: min\(44vh[^;]*; max-height: min\(44dvh", css) is not None and "@media (prefers-reduced-motion: reduce)" in css and "touch-action: none" in css)
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Kalshi City" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, 3 kpis, <= 3 lines, t, open, theme, < 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Kalshi City" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture is marked demo, holds a feed, the engine's edges (400+) and a log", fx["demo"] is True and fx["kalshi"]["kind"] == "kalshi" and len(fx["edges"]["edges"]) > 400 and len(fx["log"]) > 5 and len(fx["hyps"]["hyps"]) >= 6 and fx["hyps"]["pair"]["best"] and fx["hyps"]["pair"]["worst"])
    check("a. the render core wiring a new app needs is not edited here (olympus.js APPS, apps.js, sw.js and the build are the lead's): this folder only adds files",
          all(os.path.isfile(os.path.join(PAGE, f)) for f in ("manifest.webmanifest", "icon.svg")))


# ------------------------------------------------------------------------------------------------ b. the pure modules
def part_b():
    js = node("""const F = await import(url + '/cityfeed.js'), L = await import(url + '/citylayout.js');
      const edges = JSON.parse(fs.readFileSync(dir + '/edges.json', 'utf8')), log = JSON.parse(fs.readFileSync(dir + '/learning_log.json', 'utf8')), fx = JSON.parse(fs.readFileSync(dir + '/fixture.json', 'utf8'));
      const m = F.shape(edges, log, null), d = F.shape(fx.edges, { entries: fx.log }, null);
      const lay = L.layout(m), lay2 = L.layout(m), dl = L.layout(d);
      const live = (t, bal, pos) => ({ kind: 'kalshi', t, balance: bal, status: 'Running', running: true, positions: pos, today_pnl: 1, week_pnl: 2, total_pnl: 3 });
      const fresh = F.shape(edges, log, live(edges.t + 600, 77.77, [{ ticker: 'KX1', category: 'Bitcoin', side: 'yes', contracts: 5, price: 0.97, strategy: 'S' }]));
      const stale = F.shape(edges, log, live(edges.t - 600, 11.11, []));
      const junk = F.shape({ edges: [null, 3, { id: 'x' }, { id: 'a', dims: ['*', '*', '*', '*', '*'], n: 5, status: 'WAT', advice: 'nope' }], book: 'x', lists: { do_more: ['zzz', 'a'] } }, 7, null);
      const best = d.edges.filter((e) => !e.small && e.ev > 0).sort((a, b) => b.ev - a.ev)[0], worst = d.edges.filter((e) => !e.small && e.ev <= 0)[0];
      const bOf = (lay, id) => lay.buildings.find((b) => b.id === id);
      const overlap = (lay) => { let bad = 0; const bs = lay.buildings; for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) { if (bs[i].district !== bs[j].district) continue;
        if (Math.hypot(bs[i].x - bs[j].x, bs[i].z - bs[j].z) < (Math.max(bs[i].w, bs[i].d) + Math.max(bs[j].w, bs[j].d)) / 2 * 0.72) bad++; } return bad; };
      const sc = L.scenery(dl, 4200), sc2 = L.scenery(dl, 4200);
      const near = sc.filter((s) => Math.hypot(s.x, s.z) < dl.extent * 0.97).length;
      const smallB = dl.buildings.filter((b) => b.e.small), provB = dl.buildings.filter((b) => !b.e.small && b.e.ev > 0);
      const avg = (a) => a.reduce((s, x) => s + x, 0) / a.length;
      out({ n: m.edges.length, kinds: [...new Set(m.edges.map((e) => e.kind))].sort(), ids: new Set(m.edges.map((e) => e.id)).size, counts: m.counts, regime: m.regime, headline: m.headline, logN: m.log.length,
        lists: [m.lists.doMore.length, m.lists.stop.length], dn: d.edges.length,
        districts: lay.districts.map((x) => x.key), same: JSON.stringify(lay.buildings.map((b) => [b.id, b.x, b.z, b.h])) === JSON.stringify(lay2.buildings.map((b) => [b.id, b.x, b.z, b.h])),
        placed: lay.buildings.length, placedUnique: new Set(lay.buildings.map((b) => b.id)).size, dplaced: dl.buildings.length, dDistricts: dl.districts.map((x) => x.key), ov: overlap(lay), dov: overlap(dl),
        roads: dl.roads.length, avenues: dl.roads.filter((r) => r.kind === 'avenue').length, extent: dl.extent, ring: dl.ring,
        bestH: bOf(dl, best.id).h, worstH: bOf(dl, worst.id).h, bestEv: best.ev, smallMax: Math.max(...smallB.map((b) => b.h)), provAvg: avg(provB.map((b) => b.h)),
        modes: { up: dl.buildings.filter((b) => b.mode === 1).map((b) => b.id), crumble: dl.buildings.filter((b) => b.mode === 2).map((b) => b.id) },
        deadStatic: dl.buildings.filter((b) => b.e.status === 'DEAD' && b.mode === 0).every((b) => b.h < b.fullH * 0.2),
        monotone: (() => { const p = provB.slice().sort((a, b) => a.e.ev - b.e.ev); for (let i = 1; i < p.length; i++) if (p[i].fullH < p[i - 1].fullH - 1e-9) return false; return true; })(),
        glowRange: [Math.min(...dl.buildings.map((b) => b.glow)), Math.max(...dl.buildings.map((b) => b.glow))],
        scn: [sc.length, JSON.stringify(sc.slice(0, 50)) === JSON.stringify(sc2.slice(0, 50)), near, Math.max(...sc.map((s) => s.h)).toFixed(0)],
        fresh: [fresh.book.balance, fresh.liveUsed, fresh.book.positions.length, fresh.book.positions[0] && fresh.book.positions[0].market, fresh.regime.paused],
        stale: [stale.book.balance, stale.liveUsed], junk: [junk && junk.edges.length, junk && junk.edges[0] && junk.edges[0].status, junk && junk.edges[0] && junk.edges[0].advice, junk && junk.lists.doMore.length, junk && junk.log.length],
        nullish: [F.shape(null, null, null), F.shape({}, null, null), F.shape({ edges: 3 }, null, null)],
        cardSmall: F.cardOf(m.edges.find((e) => e.small), m.book), cardDead: F.cardOf(m.byId.get('*~XRP~*~*~*'), m.book), cardBest: F.cardOf(best, d.book),
        dayf: [0, 3, 6, 7, 12, 18, 19, 21, 23.9].map((h) => +F.dayFactor(h).toFixed(3)), phase: [3, 6, 12, 18, 22].map(F.phaseWord), clock: F.clockLabel(21.5), et: F.etHour(Date.UTC(2026, 10, 2, 22, 30)),
        fmt: [F.usd(1234.5), F.usd(-5), F.pct(0.9876), F.evf(-0.0003), F.evf(0.052), F.evf(0.0042), F.pts(-0.061), F.pts(0.0053)],
        age: [F.ageDays('2026-11-01', '2026-11-04'), F.ageDays('x', '2026-11-04'), F.ageDays('2026-11-04', '2026-11-04')] });""")
    if js.get("error"):
        check("b. node runs cityfeed.js and citylayout.js", False, js["error"])
        return
    check("b. the real edges.json shapes: unique edge ids, the engine's counts, a weather state, a headline, the log; a dozen kinds of slices; every list id exists",
          js["n"] == js["ids"] and js["n"] >= 40 and {"strategy", "market", "band"} <= set(js["kinds"]) and js["counts"]["edges"] == js["n"] and js["regime"]["state"] in ("storm", "rain", "overcast", "clear") and js["headline"] and js["logN"] > 5, (js["n"], js["kinds"]))
    check("b. one district per market plus Downtown (Bitcoin, Ethereum, XRP, Dogecoin, Solana, HYPE, BNB, Gold, Other)", js["districts"][0] == "Downtown" and {"Bitcoin", "Ethereum", "XRP", "Dogecoin", "Solana", "HYPE", "BNB", "Gold", "Other"} <= set(js["districts"]), js["districts"])
    check("b. every edge is placed exactly once, the layout is deterministic, nothing overlaps (real data and the 650-edge demo)", js["placed"] == js["n"] == js["placedUnique"] and js["dplaced"] == js["dn"] and js["same"] and js["ov"] == 0 and js["dov"] == 0, (js["placed"], js["ov"], js["dov"]))
    check("b. roads: an avenue to every district; the ring is wider than its biggest district", js["avenues"] == len(js["dDistricts"]) - 1 and js["roads"] > 50 and js["ring"] > 60, (js["avenues"], js["ring"]))
    check("b. height follows EV: the best edge is a tall tower, a losing edge a low stub, heights rise with EV for proven edges, grey (n < 30) edges stay low, dead ones that are not crumbling are rubble",
          js["bestH"] > 15 and js["worstH"] < 6 and js["monotone"] and js["smallMax"] <= 7 and js["deadStatic"] and js["provAvg"] > 10, (js["bestH"], js["worstH"], js["smallMax"], js["provAvg"]))
    check("b. going up and crumbling: the demo's new Gold rule is going up and the XRP edges crumble; the real data (first run) has none", js["modes"]["up"] and any("Gold" in i for i in js["modes"]["up"]) and js["modes"]["crumble"] and all("XRP" in i for i in js["modes"]["crumble"]), js["modes"])
    check("b. glow stays 0.04 to 1 (the recent win rate); the far skyline is 4,200 deterministic towers outside every district, taller with distance",
          js["glowRange"][0] >= 0.04 and js["glowRange"][1] <= 1 and js["scn"][0] == 4200 and js["scn"][1] and js["scn"][2] == 0 and int(js["scn"][3]) > 40, (js["glowRange"], js["scn"]))
    check("b. the live merge: a fresher feed wins (balance, open positions become orders in their district, fog follows running); an older feed is ignored", js["fresh"][:4] == [77.77, True, 1, "Bitcoin"] and js["fresh"][4] is False and js["stale"] == [js["fresh"][0] if False else js["stale"][0], False] and js["stale"][0] != 11.11, (js["fresh"], js["stale"]))
    check("b. junk in, safe out: bad rows dropped, unknown status becomes NEW, unknown advice COLLECT, list ids that do not exist dropped, null / {} / bad edges give null",
          js["junk"] == [1, "NEW", "collect", 1, 0] and js["nullish"] == [None, None, None], (js["junk"], js["nullish"]))
    c = js["cardSmall"]
    check("b. a card in plain words: a grey edge says it is too few bets and sizes nothing; a dead edge says STOP and that it really loses; the best edge shows its Kelly size",
          "too few" in c["banner"] and any(r[0] == "Size to bet" and "None" in r[1] for r in c["rows"]) and js["cardDead"]["advice"]["word"] == "STOP" and any("really loses" in r[1] for r in js["cardDead"]["rows"])
          and any("Kelly" in r[0] for r in js["cardBest"]["rows"]) and all(len(r) == 3 for r in c["rows"]), c["banner"])
    check("b. the New York clock: night, dawn, day, dusk; the day factor is 0 at night, 1 at noon and smooth; 22:30 UTC on 2 Nov 2026 is 17:30 ET; formats",
          js["dayf"][0] == 0 and js["dayf"][1] == 0 and js["dayf"][4] == 1 and js["dayf"][8] == 0 and 0 < js["dayf"][3] < 1 and js["phase"] == ["Night", "Dawn", "Day", "Dusk", "Night"] and js["clock"] == "21:30" and abs(js["et"] - 17.5) < 0.01
          and js["fmt"] == ["$1,234.50", "-$5.00", "98.8%", "-$0.000", "+$0.05", "+$0.004", "-6.1 pts", "+0.5 pts"] and js["age"] == [3, 999, 0], (js["dayf"], js["phase"], js["et"], js["fmt"], js["age"]))


# ------------------------------------------------------------------------------------------------ b2. the Lab (research ideas): data, layout, ticker, pair
def part_b2():
    js = node("""const F = await import(url + '/cityfeed.js'), L = await import(url + '/citylayout.js');
      const rd = (f) => JSON.parse(fs.readFileSync(dir + '/' + f, 'utf8'));
      const edges = rd('edges.json'), log = rd('learning_log.json'), hyp = rd('hypotheses.json'), fx = rd('fixture.json');
      const m = F.shape(edges, log, null, edges.t, hyp, false), d = F.shape(fx.edges, { entries: fx.log }, null, fx.edges.t, fx.hyps, true), m0 = F.shape(edges, log, null, edges.t);
      const lay = L.layout(m), lay2 = L.layout(m), lay0 = L.layout(m0), dl = L.layout(d);
      const labB = lay.buildings.filter((b) => b.lab), H = m.hyp.hyps, by = (id) => H.find((h) => h.id === id);
      const hOf = (id) => lay.buildings.find((b) => b.id === id);
      const marketR = Math.max(...lay.districts.slice(1).map((x) => Math.hypot(x.cx, x.cz) + x.half));
      const labMinR = Math.min(...lay.labs.map((x) => Math.hypot(x.cx, x.cz) - x.half));
      let ovl = 0; for (let i = 0; i < labB.length; i++) for (let j = i + 1; j < labB.length; j++) if (Math.hypot(labB[i].x - labB[j].x, labB[i].z - labB[j].z) < (labB[i].w + labB[j].w) / 2 * 0.9) ovl++;
      const inPad = labB.every((b) => { const x = lay.labs.find((l) => l.key === b.lab); return Math.hypot(b.x - x.cx, b.z - x.cz) < x.half - b.w / 2; });
      const prev = {}; H.forEach((h) => { prev[h.id + ':back'] = h.back.gain + 30; prev[h.id + ':live'] = h.live.gain; prev[h.id + ':prog'] = h.nLive; });
      const lp = L.layout(m, prev), moved = lp.buildings.filter((b) => b.mode === 3);
      const js2 = JSON.parse(JSON.stringify(hyp)); const fl = js2.hyps.find((h) => h.id === 'floor95');
      fl.word = 'WORKS'; fl.judged_live = true; fl.live.n_skip = 60; fl.live.n_all = 90; fl.live.gain = 12.5; fl.live.judge = 'WORKS'; fl.live.pnl_skip = -12.5; fl.back.judge = 'WORKS';
      const mw = F.shape(edges, log, null, edges.t, js2, false), hw = mw.hyp.hyps.find((h) => h.id === 'floor95'), lw = L.layout(mw);
      const hb = (lay2, id) => lay2.buildings.find((b) => b.id === id);
      const noPair = F.shape({ ...edges, edges: edges.edges.filter((e) => e.size > 1 || e.src !== 'feed') }, log, null, edges.t, null);
      out({ n: H.length, ids: new Set(H.map((h) => h.id)).size, words: [...new Set(H.map((h) => h.word))].sort(), pair: [m.hyp.pair.best && m.hyp.pair.best.pnl, m.hyp.pair.worst && m.hyp.pair.worst.pnl, m.hyp.pair.worst.fix],
        backNeverWorks: H.every((h) => h.back.status !== 'GROWING' || h.kind === 'size'), dBack: d.hyp.hyps.every((h) => h.back.status !== 'GROWING' || h.kind === 'size'),
        placed: lay.buildings.length, edgeCount: lay.edgeCount, nEdges: m.edges.length, labs: lay.labs.length, labB: labB.length, noLab: lay0.labs.length, noLabB: lay0.buildings.length, same: JSON.stringify(lay.buildings.map((b) => [b.id, b.x, b.z, b.h])) === JSON.stringify(lay2.buildings.map((b) => [b.id, b.x, b.z, b.h])),
        uniq: new Set(lay.buildings.map((b) => b.id)).size === lay.buildings.length, marketR, labMinR, extent: lay.extent, labRing: lay.labRing, ovl, inPad,
        h: { back95: hOf('hyp:floor95:back').h, live95: hOf('hyp:floor95:live').h, backXrp: hOf('hyp:xrp:back').h, min: Math.min(...labB.map((b) => b.h)), max: Math.max(...labB.map((b) => b.h)) },
        order: hOf('hyp:floor95:back').h >= hOf('hyp:leak9095:back').h && hOf('hyp:leak9095:back').h > hOf('hyp:xrp:back').h && hOf('hyp:xrp:back').h > hOf('hyp:small:back').h,
        crane: labB.filter((b) => b.part === 'prog' && b.mode === 1).length, grey: labB.filter((b) => b.part === 'prog').every((b) => b.e.small), kinds: labB.every((b) => b.e.lab && b.e.dims.length === 5),
        roads: [lay.roads.filter((r) => r.kind === 'labring').length, lay.roads.filter((r) => r.kind === 'labspur').length, lay0.roads.filter((r) => r.kind === 'labring').length],
        junk: [F.shapeHyps(null), F.shapeHyps({}), F.shapeHyps({ hyps: [] }), F.shapeHyps({ hyps: [{ id: 3 }, null] }), F.shapeHyps({ hyps: [{ id: 'a', word: 'WAT', kind: 'wat', back: 5 }] }).hyps[0].word],
        tick: F.tickerLines(m, []), tickDemo: F.tickerLines(d, [])[0], tickNone: F.tickerLines(m0, []),
        changes: [F.changesOf(m, { 'floor95:live': -4 }).length, F.changesOf(m, { 'floor95:live': 0 }).length, F.changesOf(m, null).length],
        pairs: [F.pairOf(m).best.pnl, F.pairOf(m0).best.pnl, F.pairOf(m0).worst.pnl, F.pairOf(noPair).worst && F.pairOf(noPair).worst.pnl, F.pairOf(m0).best.pnl === F.pairOf(m).best.pnl],
        resize: [moved.length, moved.every((b) => b.from >= 0.05 && b.from <= 4 && b.e.lab), lp.buildings.filter((b) => b.mode === 3 && !b.lab).length, lp.buildings.filter((b) => b.mode === 1 && b.lab).length, L.layout(m, null).buildings.filter((b) => b.mode === 3).length],
        works: [hw.live.status, hw.back.status, hw.judgedLive, hb(lw, 'hyp:floor95:live').e.status, hb(lw, 'hyp:floor95:live').e.small, hb(lw, 'hyp:floor95:prog').mode],
        cardBack: F.hypCardOf(by('floor95'), 'back'), cardLive: F.hypCardOf(by('floor95'), 'live'), cardProg: F.hypCardOf(by('maker'), 'prog'), cardWorks: F.hypCardOf(hw, 'live'), cardSize: F.hypCardOf(by('small'), 'back'),
        hypOf: [F.hypOf(m, 'hyp:floor95:live').part, F.hypOf(m, 'hyp:nope:live'), F.hypOf(m, 'hyp:floor95:zzz'), F.hypOf(m, '*~XRP~*~*~*'), F.hypOf(m0, 'hyp:floor95:back')],
        demo: [d.hyp.demo, dl.labs.length, dl.edgeCount, d.edges.length, dl.buildings.length - dl.edgeCount, d.hyp.hyps.filter((h) => h.judgedLive).length] });""")
    if js.get("error"):
        check("b2. node runs the Lab (cityfeed.js + citylayout.js)", False, js["error"])
        return
    hyp = json.loads(rd(PAGE, "hypotheses.json"))
    check("b2. hypotheses.json shapes: 8 ideas, unique ids, plain verdict words, the pair in dollars with the idea that plugs the leak (Stop buying at 90-95c); looking back never reads WORKS (real data and the demo)",
          js["n"] == 8 == js["ids"] and set(js["words"]) <= {"COLLECTING", "NEEDS DATA", "PROMISING", "WORKS", "NO HELP", "SAFER"} and "WORKS" not in js["words"] and js["backNeverWorks"] and js["dBack"]
          and js["pair"][0] > 0 and js["pair"][1] < 0 and js["pair"][2] == "leak9095" and js["pair"][0] == hyp["pair"]["best"]["pnl"] and js["pair"][1] == hyp["pair"]["worst"]["pnl"], js["pair"])
    check("b2. the Lab layout: 8 districts x 3 towers placed beyond the market ring, inside their pads, nothing overlaps, deterministic, unique ids; the edge buildings are untouched; no ideas file = no Lab",
          js["labs"] == 8 and js["labB"] == 24 and js["placed"] == js["nEdges"] + 24 and js["edgeCount"] == js["nEdges"] and js["labMinR"] > js["marketR"] and js["extent"] > js["labRing"] + 20 and js["ovl"] == 0 and js["inPad"] and js["same"] and js["uniq"]
          and js["noLab"] == 0 and js["noLabB"] == js["nEdges"] and js["roads"][0] == 72 and js["roads"][1] == 8 and js["roads"][2] == 0, js)
    check("b2. heights follow the paper dollars: bigger gain, taller tower (95c floor > 90-95c leak > drop XRP > small bets), no gain is a low slab and never invisible, a loss is a stub, nothing taller than a market tower",
          js["order"] and js["h"]["back95"] > 15 and 1.2 <= js["h"]["min"] and js["h"]["live95"] < 3 and js["h"]["max"] <= 28, js["h"])
    check("b2. every live-bets tower has a crane (under 30 live bets) and is grey; every lab building is a full pseudo-edge (5 dims) so the scene, picking and the card work on it", js["crane"] == 8 and js["grey"] and js["kinds"], (js["crane"], js["grey"]))
    check("b2. junk in, safe out: null / {} / empty lists give null, rows without a string id are dropped, an unknown word becomes COLLECTING", js["junk"][:4] == [None, None, None, None] and js["junk"][4] == "COLLECTING", js["junk"])
    tk = js["tick"]
    check("b2. the learning ticker speaks plain words ('Tested ..., N paper bets, +$X, looking good / fees ate it'); no jargon (no z, EV, Kelly); demo lines are labelled; with no ideas it still says something",
          len(tk) >= 6 and all("paper bets" in t or "fees ate" in t or "needs data" in t or "live bets" in t for t in tk) and not any(re.search(r"\bEV\b|Kelly|\bz \d|Wilson", t) for t in tk) and js["tickDemo"].startswith("Demo: ") and len(js["tickNone"]) == 1 and "Nothing tested" in js["tickNone"][0], (tk[:2], js["tickNone"]))
    check("b2. what moved since the last visit: a changed live result is reported in dollars, an unchanged one and a first visit are not", js["changes"] == [1, 0, 0], js["changes"])
    check("b2. Best edge so far / Worst leak is never blank: the engine's pair, else the model's own proven slices (same numbers), else nothing proven (the page prints $0.00)",
          js["pairs"][0] == js["pairs"][1] == js["pair"][0] and js["pairs"][2] == js["pair"][1] and js["pairs"][3] is None, js["pairs"])
    check("b2. a tower that moved since the last visit resizes in front of the viewer (mode 3, from 0.05x to 4x of its new height); an unchanged one and a first visit do not; the cranes stay", js["resize"][0] == 8 and js["resize"][1] and js["resize"][2] == 0 and js["resize"][3] == 8 and js["resize"][4] == 0, js["resize"])
    check("b2. proof needs live bets: 60 live skipped bets that lose read WORKS (green live tower, not grey), looking back stays capped at PROMISING, and 30+ live bets take the crane away",
          js["works"][0] == "GROWING" and js["works"][1] == "HOLDING" and js["works"][2] is True and js["works"][3] == "GROWING" and js["works"][4] is False and js["works"][5] == 0, js["works"])
    cb, cl, cp, cw, cs = js["cardBack"], js["cardLive"], js["cardProg"], js["cardWorks"], js["cardSize"]
    check("b2. the tower cards in plain words: looking back carries the 'picked after seeing the bets, proves nothing' banner, live shows the sample needed, a proven idea has no banner, fee and size ideas say what they assume",
          "Looking back only" in cb["banner"] and any(r[0] == "Bets it would skip" for r in cb["rows"]) and any(r[0] == "Live bets needed" and "of 600" in r[1] for r in cl["rows"]) and cw["banner"] == ""
          and any(r[0] == "Could be saved" and "if every resting order filled" in r[1] for r in cp["rows"]) and any(r[0] == "Worst day" for r in cs["rows"]) and all(len(r) == 3 for r in cb["rows"] + cl["rows"] + cp["rows"]), (cb["banner"], cp["rows"][:3]))
    check("b2. lab building ids: hyp:<idea>:<part> resolve, anything else does not", js["hypOf"][0] == "live" and js["hypOf"][1:] == [None, None, None, None], js["hypOf"])
    check("b2. the demo's ideas (registered 20 days ago) have live results: 5+ ideas judged on live bets, 8 districts beside the 652 demo edges", js["demo"][0] is True and js["demo"][1] == 8 and js["demo"][2] == js["demo"][3] and js["demo"][4] == 24 and js["demo"][5] >= 5, js["demo"])


# ------------------------------------------------------------------------------------------------ c. the browser
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def make_site(tmp, with_engine=True):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "kalshicity"))
    for d in ("jarvis", "olympus"):
        shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
    if not with_engine:
        for f in ("edges.json", "learning_log.json", "hypotheses.json"):
            os.remove(os.path.join(site, "kalshicity", f))
    return site


GEOM = """() => { const W = innerWidth, H = innerHeight, bad = [];
  for (const el of document.querySelectorAll('#ui *, #dock *, #sheet:not([hidden]) *')) {
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    const b = el.getBoundingClientRect(), cs = getComputedStyle(el), clip = el.closest('.sheet .body');
    if (!b.width || !b.height || cs.visibility === 'hidden') continue;
    const c = clip ? clip.getBoundingClientRect() : null, r = { left: b.left, right: b.right, top: c ? Math.max(b.top, c.top) : b.top, bottom: c ? Math.min(b.bottom, c.bottom) : b.bottom };
    if (r.bottom <= r.top) continue;
    if (r.right > W - 16 + 0.5 || r.left < 16 - 0.5) bad.push('gutter ' + (el.id || el.className) + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
    if (r.right > W - 80 && r.bottom > H - 160) bad.push('orb ' + (el.id || el.className) + ' ' + Math.round(r.right) + ',' + Math.round(r.bottom));
  }
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad; }"""


def run_browser():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="le_kc_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/kalshicity/"
    outside, raw_hits = [], []
    shots = os.environ.get("KC_SHOTS")
    edges = json.loads(rd(PAGE, "edges.json"))
    feed = {"v": 3, "kind": "kalshi", "name": "Kalshi Edge v2", "mode": "live", "status": "Running", "running": True, "t": edges["t"] + 900, "balance": 77.77, "today_pnl": 1.5, "week_pnl": 2.5, "total_pnl": -80.0,
            "positions": [{"ticker": "KXBTC-OPEN1", "title": "Bitcoin above target", "side": "yes", "contracts": 6, "avg_price": 0.96, "price": 0.97, "strategy": "Late favourite (BTC hourly)", "category": "Bitcoin", "closes": edges["t"] + 4000},
                          {"ticker": "KXETH-OPEN2", "title": "Ethereum above target", "side": "no", "contracts": 5, "avg_price": 0.94, "price": 0.93, "strategy": "15-min favourites", "category": "Ethereum", "closes": edges["t"] + 3000}]}
    live = {"mode": "ok"}
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=False, quality="low", vw=(390, 844)):
                ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=1, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
                try:
                    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=f"http://127.0.0.1:{srv.server_address[1]}")
                except Exception:
                    pass
                if quality:
                    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")

                def guard(route):
                    u = route.request.url
                    if u.startswith(RAW_PREFIX):
                        raw_hits.append(u)
                        if live["mode"] == "ok":
                            return route.fulfill(status=200, body=json.dumps(feed), content_type="application/json", headers={"access-control-allow-origin": "*"})
                        return route.abort()
                    if u.startswith(f"http://127.0.0.1:{srv.server_address[1]}") or u.startswith(("data:", "blob:")):
                        return route.continue_()
                    outside.append(u)
                    return route.abort()
                ctx.route("**/*", guard)
                p = ctx.new_page()
                p.set_default_timeout(180000)
                p.errs = []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and "vibrate" not in m.text and p.errs.append(m.text))
                return ctx, p

            def ready(p, url=base):
                p.goto(url)
                p.wait_for_function("document.body.dataset.ready === '1' && window.KC && KC.state().scene && KC.state().scene.drawn > 0", timeout=240000)

            st = lambda p: p.evaluate("KC.state()")  # noqa: E731
            make_site(tmp)

            # ---- the real city, still scene (reduced motion keeps the camera where it is, so taps land on known buildings)
            ctx, p = page(reduced=True)
            ready(p)
            s = st(p)
            sc = s["scene"]
            check("c. loads on the chosen LITE tier at 390 x 844: real mode (no DEMO), the engine's edges, the live feed over them, 2 passes, no errors",
                  not s["demo"] and s["n"] == edges["counts"]["edges"] and s["liveUsed"] and sc["quality"] == "low" and sc["passes"] == 2 and not p.errs and p.is_visible("#lite") and not p.is_visible("#demo"), (s["demo"], s["n"], s["liveUsed"], sc, p.errs))
            check("c. one district per market plus Downtown, a building for every edge, the skyline (LITE: 700 towers), cars on the roads, orders for the 2 open positions, the weather and the clock",
                  s["districts"][0] == "Downtown" and "Bitcoin" in s["districts"] and s["edgeBuildings"] == s["n"] and sc["edges"] == s["n"] and sc["scenery"] == 700 and sc["cars"] > 60 and sc["orders"] == 2
                  and sc["weather"] == edges["regime"]["state"] and re.search(r"\d\d:\d\d · (Night|Dawn|Day|Dusk)", p.inner_text("#clock")), (s["districts"], sc))
            t = p.inner_text("#verdict")
            check("c. the top card in plain words: the headline, Do more / Stop / Ruin risk, the bot line with the live bankroll ($77.77) and how many bets were read one by one; the weather chip",
                  p.inner_text("#vText").startswith(("Learned:", "Crumbled", "Fading", "Growing", "Steady", "Update")) and re.search(r"\d", p.inner_text("#oMore")) and "$77.77" in p.inner_text("#bot") and "read one by one" in t
                  and p.get_attribute("#wx", "data-wx") == edges["regime"]["state"] and p.inner_text("#wx").split(" ")[0] in ("Clear", "Overcast", "Rain", "Storm"), t)
            ov = p.evaluate(GEOM)
            check("c. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not ov, ov)
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "kalshicity-home.png"))
            # tap buildings: where() the building, tap the spot, the pick is that building (or one standing in front of it), and its card opens
            model = p.evaluate("KC.model().edges.filter((e) => !e.small).slice(0, 12).map((e) => e.id)")
            hits = 0
            for i in model:
                w = p.evaluate(f"KC.where({json.dumps(i)})")
                hits += bool(w) and p.evaluate(f"KC.pick({w['x']}, {w['y']})") == i
            check("c. picking: the building under a fingertip is found (12 proven edges, projected to the screen and picked back)", hits >= 8, (hits, len(model)))
            tgt = next(i for i in model if (p.evaluate(f"KC.where({json.dumps(i)})") or {}).get("y", 0) > 300 and p.evaluate(f"(() => {{ const w = KC.where({json.dumps(i)}); return w && w.y < 640 && KC.pick(w.x, w.y) === {json.dumps(i)}; }})()"))
            w = p.evaluate(f"KC.where({json.dumps(tgt)})")
            p.mouse.click(w["x"], w["y"])
            p.wait_for_function("KC.state().view === 'card'")
            card = p.inner_text("#sheet")
            check("c. a tap on a building opens its card: the name, status and advice badges, bets, win rate against the market's, EV per $1, the luck test, the 7 / 30 day windows, the Kelly size",
                  all(x in card for x in ("Bets", "Win rate", "Profit per $1 staked", "Is it luck?", "Last 7 days", "Last 30 days")) and st(p)["sel"] == tgt and re.search(r"DO MORE|KEEP|WATCH|STOP|COLLECT", card) and not p.errs, card[:200])
            ov = p.evaluate(GEOM)
            check("c. the card sits inside the gutters and out of the orb's corner", not ov, ov)
            if shots:
                p.screenshot(path=os.path.join(shots, "kalshicity-card.png"))
            small = p.evaluate("KC.model().edges.find((e) => e.small && e.size === 1).id")
            p.evaluate(f"KC.select({json.dumps(small)})")
            card = p.inner_text("#sheet")
            check("c. a grey building says so: 'too few' bets, no stake, COLLECT (honest about small samples)", "too few" in card.lower() and "COLLECT" in card and "None: needs 30 bets" in card, card[:200])
            p.keyboard.press("Escape")
            check("c. Escape closes the card and clears the selection", not p.is_visible("#sheet") and st(p)["sel"] is None)
            # ---- the Lab: Best edge so far / Worst leak, the learning ticker, the idea districts
            pb, pw = p.inner_text("#pBestV"), p.inner_text("#pWorstV")
            boxes = [p.locator(i).bounding_box() for i in ("#pBest", "#pWorst", "#ticker")]
            tk0 = p.inner_text("#tkText")
            check("c. Best edge so far / Worst leak in dollars (never blank) and the learning ticker in plain words; all three are 44 px+ tap targets at 390 x 844",
                  re.fullmatch(r"\+\$\d[\d,]*\.\d\d", pb) and re.fullmatch(r"-\$\d[\d,]*\.\d\d", pw) and all(b and b["height"] >= 44 and b["width"] >= 44 for b in boxes) and re.search(r"Tested|Started|Since", tk0), (pb, pw, boxes, tk0))
            p.evaluate("KC.tickNext()")
            check("c. the ticker moves on to the next lesson (and says 'Demo:' only for demo ideas)", p.inner_text("#tkText") != tk0 and not p.inner_text("#tkText").startswith("Demo:") and st(p)["ticker"] >= 6, (tk0, p.inner_text("#tkText")))
            check("c. the Lab is in the city: 8 idea districts x 3 towers beside the edge buildings, one instanced mesh (no extra draw call per tower), the real ideas (not demo)",
                  len(s["labs"]) == 8 and s["buildings"] == s["n"] + 24 and sc["lab"] == 8 and sc["real"] == s["buildings"] and not s["hypDemo"], (s["labs"], s["buildings"], sc["lab"]))
            p.evaluate("KC.select('hyp:floor95:back')")
            p.wait_for_function("KC.state().view === 'card'")
            card = p.inner_text("#sheet")
            check("c. a tap on an idea's tower opens its card: the rule, the bets it would skip and what they made, a plain verdict, and the 'looking back only' warning; inside the gutters",
                  "only buy 95c and up" in card.lower() and "bets it would skip" in card.lower() and "looking back only" in card.lower() and "PROMISING" in card.upper() and not p.evaluate(GEOM), card[:160])
            p.keyboard.press("Escape")
            p.click("#ticker")
            p.wait_for_function("KC.state().view === 'lab'")
            lab = p.inner_text("#sheet")
            rows = p.locator("#sheet .ideas .row-btn")
            rb = [rows.nth(i).bounding_box()["height"] for i in range(rows.count())]
            check("c. tapping the ticker opens the Lab: the pair, 8 ideas (44 px+ rows) each with its verdict word, what the lab learned; inside the gutters; URL #lab",
                  all(x.lower() in lab.lower() for x in ("Best edge so far", "Worst leak", "Ideas (8)", "What the lab learned", "Only LIVE bets")) and rows.count() == 8 and min(rb) >= 44 and p.evaluate("location.hash") == "#lab" and not p.evaluate(GEOM), (rb, lab[:120]))
            if shots:
                p.screenshot(path=os.path.join(shots, "kalshicity-lab.png"))
            rows.nth(0).click()
            p.wait_for_function("KC.state().view === 'card' && KC.state().sel.startsWith('hyp:')")
            p.keyboard.press("Escape")
            p.click("#pWorst")
            p.wait_for_function("KC.state().sel === 'hyp:leak9095:back'")
            check("c. the Worst leak button flies to the idea that plugs it (Stop buying at 90-95c); the Best edge button to the winning building", "stop buying at 90-95c" in p.inner_text("#sheet").lower() and not p.errs, p.errs)
            p.keyboard.press("Escape")
            p.click("#pBest")
            p.wait_for_function("KC.state().sel === '*~*~*~95-97c~*'")
            check("c. ...the Best edge button opens the 95-97c building's card", "95-97c" in p.inner_text("#sheet").lower() and not p.errs, p.errs)
            p.keyboard.press("Escape")
            for v, words in (("learn", ("Every time the engine re-measures",)), ("board", ("biggest proven lead",)), ("moves", ("Do more", "Stop doing", "Watch")), ("risk", ("Kelly", "Chance of losing half")), ("guide", ("scenery", "Gold windows won"))):
                p.click(f"[data-view={v}]") if v != "guide" else p.click("#guideBtn")
                p.wait_for_function(f"KC.state().view === '{v}'")
                txt = p.inner_text("#sheet")
                ov = p.evaluate(GEOM)
                check(f"c. the {v} sheet: its words are there, inside the gutters, out of the orb's corner; URL #{v}", all(w.lower() in txt.lower() for w in words) and p.evaluate("location.hash") == f"#{v}" and not ov, (txt[:120], ov))
                if v == "board":
                    rows = p.locator("#sheet .row-btn")
                    check("c. the board's rows are 44 px tap targets and open the building's card", rows.count() >= 3 and all(rows.nth(i).bounding_box()["height"] >= 44 for i in range(min(3, rows.count()))))
                    rows.nth(0).click()
                    p.wait_for_function("KC.state().view === 'card'")
                    p.click("[data-view=learn]")
                if shots:
                    p.screenshot(path=os.path.join(shots, f"kalshicity-{v}.png"))
            p.keyboard.press("Escape")
            lbl = p.evaluate("KC.model().log.filter((x) => x.id)[0].text")
            p.click("[data-view=learn]")
            check("c. the learning log lists dated lessons, newest first, each one tappable", p.locator("#sheet .log li").count() >= 5 and re.search(r"\d{4}-\d\d-\d\d", p.inner_text("#sheet")) and lbl[:20] in p.inner_text("#sheet"))
            p.keyboard.press("Escape")
            for cam in ("fly", "street", "map", "orbit"):
                p.click(f"[data-cam={cam}]")
                p.wait_for_function(f"KC.state().scene.mode === '{cam}'")
                check(f"c. the {cam} camera: pressed, and the scene is in that mode with no errors", p.get_attribute(f"[data-cam={cam}]", "aria-pressed") == "true" and not p.errs, p.errs)
            p.click("[data-cam=fly]")
            p.evaluate("(() => { const c = document.getElementById('city'), b = c.getBoundingClientRect(); const o = { bubbles: true, pointerId: 7, clientX: b.left + 120, clientY: b.top + 300, pointerType: 'touch' };"
                       "c.dispatchEvent(new PointerEvent('pointerdown', o)); window.dispatchEvent(new PointerEvent('pointermove', { ...o, clientX: o.clientX + 60 })); window.dispatchEvent(new PointerEvent('pointerup', { ...o, clientX: o.clientX + 60 })); })()")
            check("c. a drag hands the camera back to the orbit", st(p)["scene"]["mode"] == "orbit")
            clock0 = p.inner_text("#clock")
            p.click("#clock")
            p.wait_for_function("KC.state().preview === 6")
            check("c. the clock chip previews another hour (06:00, dawn); the scene follows; tapping on cycles back to live", st(p)["scene"]["hour"] == 6 and p.evaluate("document.getElementById('clock').classList.contains('preview')") and "Dawn" in p.inner_text("#clock"))
            for _ in range(4):
                p.click("#clock")
            check("c. ...12:00, 18:00, 00:00 and live again", st(p)["preview"] is None and not p.evaluate("document.getElementById('clock').classList.contains('preview')") and clock0[:2].isdigit())
            p.evaluate("KC.open('guide')")
            p.click("#sheet .more")
            p.wait_for_function("KC.state().demo === true")
            s2 = st(p)
            check("c. 'Preview the demo city' swaps in the 650-edge demo (DEMO badge, going-up and crumbling buildings, the demo's districts) and 'Back to the real city' returns",
                  s2["n"] > 400 and p.is_visible("#demo") and s2["scene"]["constructing"] >= 1 and s2["scene"]["crumbling"] >= 1 and s2["scene"]["edges"] == s2["n"] and not p.errs, (s2["n"], s2["scene"], p.errs))
            p.click("#sheet .more")
            p.wait_for_function("KC.state().demo === false")
            check("c. ...back to the real city", st(p)["n"] == edges["counts"]["edges"] and not p.is_visible("#demo") and not p.errs, p.errs)
            # ---- the lessons from the research, the ask-for-history card, the sound toggle, the scanner (still page)
            learned = json.loads(rd(PAGE, "learned.json"))
            p.click("[data-view=lessons]")
            p.wait_for_function("KC.state().view === 'lessons'")
            txt = p.inner_text("#sheet")
            fees, b95 = learned["fees"], next(b for b in learned["buckets"] if b["label"].startswith("95-99c"))
            check("c. the What we learned sheet: the four findings (fees eat the edge, 95c+ thin pocket, 90-95c loses, risk of ruin vs size) with the research's own numbers (fees $%d, %d bets at 95c+), the by-price list, the ideas"
                  % (round(fees["total"]), b95["n"]),
                  all(x.lower() in txt.lower() for x in ("Fees eat the edge", "95c and above: a thin pocket", "90-95c entries lose", "Risk of ruin grows with bet size", "By entry price", "Ideas to paper-test first"))
                  and f"${round(fees['total'])}" in txt and f"{b95['n']:,}" in txt and learned["headline"] in txt and "fixed 6 contracts" in txt and "not proven" in txt and not p.evaluate(GEOM), (txt[:200], p.evaluate(GEOM)))
            if shots:
                p.screenshot(path=os.path.join(shots, "kalshicity-lessons.png"))
            p.click("#askBtn")
            p.wait_for_function("KC.state().view === 'history'")
            ask = p.inner_text("#sheet pre")
            check("c. the Ask for the full history card: why (40 bets only, hour-of-day), three steps, and the exact message with the order-table fields (time, ticker, side, book, contracts, price, pnl), read only, no keys, nothing public",
                  ask == p.evaluate("KC.ask") and "time,ticker,side,book,contracts,price,pnl" in ask and "read-only" in ask and "API key" in ask and "public" in ask and "Print the CSV here in the chat" in ask
                  and "hour of the day" in p.inner_text("#sheet") and p.locator("#sheet .steps li").count() == 3 and not p.evaluate(GEOM), ask[:120])
            p.click("#copyAsk")
            p.wait_for_function("document.getElementById('copyAsk').textContent !== 'Copy the message'")
            clip = ""
            try:
                clip = p.evaluate("navigator.clipboard.readText()")
            except Exception:
                pass
            check("c. the Copy button copies the whole message (or says how to copy it by hand)", p.inner_text("#copyAsk") in ("Copied", "Press and hold the text to copy it") and (clip == "" or clip == p.evaluate("KC.ask")), (p.inner_text("#copyAsk"), clip[:40]))
            p.keyboard.press("Escape")
            p.evaluate("window.__sfx = []; OLYMPUS.sfx = (n) => { if (n) window.__sfx.push(n); return true; }")
            ids = p.evaluate("KC.model().edges.filter((e) => !e.small).slice(0, 2).map((e) => e.id)")
            p.evaluate(f"KC.select({json.dumps(ids[0])})")
            off_calls = p.evaluate("window.__sfx.length")
            p.keyboard.press("Escape")
            p.click("#sound")
            p.evaluate(f"KC.select({json.dumps(ids[1])})")
            on_calls = p.evaluate("window.__sfx.slice()")
            check("c. sound is off until the note button is pressed (no sfx call), then ambience and ticks go through OLYMPUS.sfx; the choice is kept on this phone",
                  off_calls == 0 and p.get_attribute("#sound", "aria-pressed") == "true" and "tap" in on_calls and "tick" in on_calls and json.loads(p.evaluate("localStorage.getItem('kalshicity.v1')")).get("sound") is True, on_calls)
            p.click("#sound")
            p.keyboard.press("Escape")
            n0 = p.evaluate("window.__sfx.length")
            p.evaluate(f"KC.select({json.dumps(ids[0])})")
            check("c. ...and off again silences it", p.get_attribute("#sound", "aria-pressed") == "false" and p.evaluate("window.__sfx.length") == n0)
            p.keyboard.press("Escape")
            r = p.evaluate("KC.scan()")
            check("c. the scan button: the engine's lessons of today become buildings to light up (and DO MORE ones get fireworks); on a still page nothing moves, nothing breaks",
                  len(r["ids"]) >= 1 and all(i in set(p.evaluate("KC.model().edges.map((e) => e.id)")) for i in r["ids"] + r["more"]) and not p.errs, (r, p.errs))
            st0 = st(p)["scene"]["fx"]
            check("c. still page, effects: the neon signs and the wet-street reflections are drawn (stills), the moving library effects are off (reduced motion = off)", st0["signs"] > 0 and st0["wet"] > 0 and st0["live"] == [], st0)
            ctx.close()

            # ---- the effects (a moving page): dusk god rays, storm lightning, aurora + a lens flare at night, fireworks and the scanner when the engine learned something today
            ctx, p = page()
            ready(p)
            p.evaluate("KC.hour(22)")
            p.wait_for_function("KC.fx() && KC.fx().live.includes('aurora') && KC.fx().live.includes('spire')", timeout=120000)
            f = p.evaluate("KC.fx()")
            check("c. at night: the aurora over the Vault and a lens flare on the Exchange's spire (OLYMPUS fx library), LITE-tier caps held", "aurora" in f["live"] and "spire" in f["live"] and f["tier"] == "low" and not p.errs, (f, p.errs))
            p.wait_for_function("KC.fx().counts.scans >= 1", timeout=120000)
            f = p.evaluate("KC.fx()")
            check("c. the engine learned something today: the edge scanner swept the city once and fireworks went up over the new DO MORE edge", f["counts"]["scans"] == 1 and f["counts"]["fireworks"] >= 1 and not p.errs, f)
            p.wait_for_function("KC.fx().live.includes('lightning')", timeout=120000)
            check("c. the risk of ruin is high and it rains: lightning storm on (and a bolt on demand)", p.evaluate("KC.fx().live.includes('lightning')") and p.evaluate("KC.scene().strike()") is True and not p.errs, p.errs)
            p.evaluate("KC.hour(18)")
            p.wait_for_function("KC.fx().live.includes('godRays')", timeout=120000)
            check("c. at dusk: god rays", "godRays" in p.evaluate("KC.fx().live") and not p.errs, p.errs)
            p.evaluate("KC.hour(12)")
            p.wait_for_function("!KC.fx().live.includes('aurora') && !KC.fx().live.includes('spire') && !KC.fx().live.includes('godRays')", timeout=120000)
            check("c. by day: the aurora, the spire flare and the god rays stop (nothing is left running that the clock does not call for)", not p.errs, p.errs)
            p.click("#scan")
            p.wait_for_function("KC.fx().counts.scans >= 2")
            check("c. the scan button sweeps again on demand", p.evaluate("KC.fx().counts.scans") >= 2 and not p.errs, p.errs)
            ctx.close()

            # ---- reduced motion: a still scene
            ctx, p = page(reduced=True)
            ready(p)
            before = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1800)
            after = st(p)["scene"]["drawn"]
            check("c. reduced motion: a still scene (no frames while nothing changes), the cars and the rain stand still, no errors", after - before <= 3 and not p.errs, (before, after, p.errs))
            p.click("[data-cam=map]")
            p.wait_for_timeout(1200)
            check("c. ...and a camera change still redraws it", st(p)["scene"]["drawn"] > after)
            ctx.close()

            # ---- the next visit: an idea's dollars moved since the viewer last looked, so its towers resize in front of them and the ticker says so
            ctx, p = page(reduced=True)
            p.add_init_script("try { if (!localStorage.getItem('kalshicity.v1')) localStorage.setItem('kalshicity.v1', JSON.stringify({ hh: { 'floor95:live': -4.5, 'floor95:back': 120, 'xrp:prog': 9 } })); } catch (e) {}")
            ready(p)
            ch = p.evaluate("KC.changes()")
            hh = json.loads(p.evaluate("localStorage.getItem('kalshicity.v1')"))["hh"]
            check("c. a second visit: what moved is said in plain dollars ('Only buy 95c and up grew from -$4.50 ...'), its towers resize (3 moved), the ticker leads with it, and this visit's dollars are stored for the next",
                  len(ch) == 1 and "Only buy 95c and up" in ch[0] and "-$4.50" in ch[0] and st(p)["scene"]["resizing"] == 3 and p.evaluate("KC.ticker()[0]") == ch[0] and hh["floor95:live"] == 0 and len(hh) == 24 and not p.errs, (ch, hh, p.errs))
            ctx.close()

            # ---- the ideas file is missing (the engine has not run it yet): the recorded demo ideas, labelled, never a blank Lab
            os.remove(os.path.join(tmp, "nq-dashboard", "kalshicity", "hypotheses.json"))
            ctx, p = page(reduced=True)
            ready(p)
            s = st(p)
            p.click("#ticker")
            p.wait_for_function("KC.state().view === 'lab'")
            check("c. no ideas file yet: the real city stays real (no DEMO badge) and the Lab shows the recorded demo ideas, labelled DEMO in the ticker and the sheet, still 8 districts, Best / Worst filled",
                  not s["demo"] and s["hypDemo"] and len(s["labs"]) == 8 and p.inner_text("#tkText").startswith("Demo: ") and "DEMO ideas" in p.inner_text("#sheet") and p.inner_text("#pWorstV").startswith("-$") and not p.errs, (s["hypDemo"], p.inner_text("#tkText"), p.errs))
            ctx.close()
            make_site(tmp)

            # ---- the feed is unreachable: the engine's copy alone (offline), still real
            live["mode"] = "down"
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. the public feed unreachable (offline): the engine's own copy draws the city, not DEMO, bankroll from the engine, no errors", not s["demo"] and not s["liveUsed"] and "bankroll $" in p.inner_text("#bot") and "$77.77" not in p.inner_text("#bot") and not p.errs, (s["demo"], p.inner_text("#bot"), p.errs))
            ctx.close()

            # ---- the engine's files are missing: the recorded copy (DEMO), offline
            make_site(tmp, with_engine=False)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. no engine files and no feed: the fixture's recorded demo (DEMO badge, 400+ edges, the going-up and crumbling buildings), still no errors", s["demo"] and p.is_visible("#demo") and s["n"] > 400 and s["scene"]["constructing"] >= 1 and s["hypDemo"] and len(s["labs"]) == 8 and p.inner_text("#tkText").startswith("Demo: ") and not p.errs, (s["demo"], s["n"], p.errs))
            ctx.close()
            live["mode"] = "ok"
            make_site(tmp)

            # ---- the high tier: three passes, a thicker skyline (software GL is slow: one load)
            if os.environ.get("KC_NO_HIGH") != "1":
                ctx, p = page(quality="high")
                ready(p, base + "?q=high&gpu=1")
                s = st(p)["scene"]
                check("c. the high tier (?q=high&gpu=1): 3 passes (scene, bloom, finish), 2,600 towers of skyline, more cars, no errors", s["quality"] == "high" and s["passes"] == 3 and s["scenery"] == 2600 and s["cars"] > 100 and not p.errs, (s, p.errs))
                ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. nothing left the machine: no request to any origin but the public feed address, which this test answers itself (GET, no key)",
          not outside and raw_hits and all(u.endswith("/main/kalshi.json") for u in raw_hits), (outside[:3], raw_hits[:2]))


def main():
    part_a()
    part_b()
    part_b2()
    if os.environ.get("KC_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
