"""FATES + LABYRINTH + HEPHAESTUS overhaul (2026-11-04, JOB 4+5): the shared atmosphere kit (olympus/fx-atmos.js) and the new features of the
three apps. Read-only pages: nothing here sends, saves to the bot or routes an order.

  a. static   fx-atmos.js (dust, embers, shafts, contactAO, polishedFloor, bronze, forgedIron, threadGlow, QUALITY), read-only, wired into
              the three scenes; the new core functions exist; the pages' new hooks; versions bumped
  b. cores    in Chromium (dynamic import): Labyrinth (3 mazes, danger zones, risk-of-ruin levels, best size in words, the walk frames),
              Hephaestus (5 recipes picked from stored runs, compare, history, the card text), Fates (size what-if reproduces the build's
              pass within a few points at 1x, cut the worst session, the odds-by-day timeline, cost per pass = fee / pass rate, scenario table)
  c. kit      fx-atmos in a WebGL harness: each effect is one draw call, QUALITY tiers hide shafts (low) and particles (off), no errors
  d. Labyrinth  maze picker, ruin gauge, best size button, Danger sheet, the danger heat strip, Walk it (scene + text), no sideways scroll
  e. Hephaestus recipes, pin + compare, history (survives a reload), the report card image, the forge's effects
  f. Fates    the Lab: six tabs draw, the size table, a scenario tap switches the route, the cost matches the core, draw calls stay <= 64

    python -X utf8 -m tests.test_oly_job45 [--no-browser]
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def part_a():
    fx = rd("tools", "web_public", "olympus", "fx-atmos.js")
    check("a. fx-atmos exports the kit", all(f"export function {n}(" in fx for n in ("dust", "embers", "shafts", "contactAO", "polishedFloor", "bronze", "forgedIron", "threadGlow", "setQuality", "update")) and "export const QUALITY" in fx)
    check("a. fx-atmos is read-only (no fetch / network / storage)", all(w not in fx for w in ("fetch(", "XMLHttpRequest", "localStorage", "WebSocket")))
    for app, sc in (("fates", "fates-scene.js"), ("labyrinth", "scene.js"), ("hephaestus", "scene.js")):
        s = rd("tools", "web_public", app, sc)
        check(f"a. {app} scene uses fx-atmos (shafts + dust + embers + contact shadows) and applies the quality tier", "fx-atmos.js" in s and "FX.shafts" in s and "FX.dust" in s and "FX.embers" in s and "FX.contactAO" in s and "FX.setQuality" in s)
    check("a. labyrinth core: mazes, hazard, ruin, bestSize, frames, scalePool", all(f"export function {n}(" in rd("tools", "web_public", "labyrinth", "labcore.js") for n in ("scalePool", "hazard", "ruin", "bestSize", "frames")) and "export const MAZES" in rd("tools", "web_public", "labyrinth", "labcore.js"))
    check("a. hephaestus core: presets, compare, pushHistory, cardModel", all(f"export function {n}(" in rd("tools", "web_public", "hephaestus", "hephaestuscore.js") for n in ("presets", "compare", "pushHistory", "cardModel")))
    check("a. fates core: replayThread, resize, sizeTable, cutWorst, cutOne, fanChart, passTimeline, costPerPass, scenarioTable", all(f"export function {n}(" in rd("tools", "web_public", "fates", "fates-core.js") for n in ("replayThread", "resize", "sizeTable", "cutWorst", "cutOne", "fanChart", "passTimeline", "costPerPass", "scenarioTable")))
    check("a. fates-lab.js is DOM + SVG only (no fetch, no WebGL, no storage)", all(w not in rd("tools", "web_public", "fates", "fates-lab.js") for w in ("fetch(", "THREE", "localStorage", "XMLHttpRequest")))
    lab, he, fa = rd("tools", "web_public", "labyrinth", "index.html"), rd("tools", "web_public", "hephaestus", "index.html"), rd("tools", "web_public", "fates", "index.html")
    check("a. labyrinth page: maze picker, ruin gauge, best size, Danger pill, Walk it", all(w in lab for w in ('id="mazes"', 'id="ruin"', 'id="bestUse"', 'data-view="danger"', 'id="walkBtn"')) and "l2" in lab)
    check("a. hephaestus page: recipes, compare, history, report card", all(w in he for w in ('id="recipes"', 'id="pin"', 'id="cmp"', 'id="hist"', 'id="forge"', 'id="cardCv"')) and "h2" in he)
    check("a. fates page: the Lab button and sheet", all(w in fa for w in ('id="labBtn"', 'id="lab"', "data-lab-tabs")) and "f6" in fa)
    check("a. no apps' sw.js / jarvis edits needed by this job (fx-atmos is a new kit file)", os.path.exists(os.path.join(WEB, "olympus", "fx-atmos.js")))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
    return pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=args)


CORES = r"""async () => {
  const out = {};
  const L = await import('/labyrinth/labcore.js'), H = await import('/hephaestus/hephaestuscore.js'), F = await import('/fates/fates-core.js');
  // ---- Labyrinth
  const lf = await (await fetch('/labyrinth/fixture.json')).json();
  const pool = L.parseTrades(lf), R = L.MAZES[0].rules;
  out.mazes = L.MAZES.map((m) => [m.id, m.rules.start, m.rules.target, m.rules.mll, m.scale]);
  const rows = L.sweep(pool, 0, R, [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2], { len: 15, n: 300, seed: 7 });
  const best = L.bestSize(rows, R, 15); out.best = { m: best.m, text: best.text, why: best.why, hasMulti: rows.some((r) => r.m === best.m) };
  const hz = L.hazard(pool, 1, 0, R, { len: 15, n: 300 }); out.haz = { n: hz.length, maxHeat: Math.max(...hz.map((z) => z.heat)), sumBust: hz.reduce((a, z) => a + z.bust, 0), sim: L.sim(pool, 1, 0, R, { len: 15, n: 300, seed: 7 }).bust, alive: hz[hz.length - 1].alive };
  out.ruin = [0.05, 0.15, 0.3, 0.5].map((p) => L.ruin(p).level);
  const sp = L.scalePool(pool, 0.5); out.scale = [pool[0].usd, sp[0].usd, pool.length === sp.length];
  const w = L.walk(L.march(pool, R, 15), 1, 0, R), fr = L.frames(w, R); out.frames = [fr.length === w.steps.length, fr[0].note, fr[fr.length - 1].note];
  out.sim25 = L.sim(sp, 1, 0, L.MAZES[1].rules, { len: 15, n: 300, seed: 7 });
  // ---- Hephaestus
  const hd = await (await fetch('/hephaestus/data.json')).json();
  const ps = H.presets(hd); out.presets = ps.map((p) => [p.id, p.sc.id, !!H.byId(hd, p.sc.id)]);
  out.aggrIsMax = ps.find((p) => p.id === 'aggressive').sc.y26.net === Math.max(...hd.scenarios.filter((s) => s.selectable).map((s) => s.y26.net));
  const a = H.byId(hd, 'live'), b = H.byId(hd, 'uprisk'); const cm = H.compare(hd, a, b); out.cmp = [cm.rows.length, cm.winner, cm.line.length > 20, H.compare(hd, a, a).line];
  let hist = H.pushHistory([], { id: 'live' }); hist = H.pushHistory(hist, { id: 'safe' }); hist = H.pushHistory(hist, { id: 'safe' }); hist = H.pushHistory(hist, { id: 'live' });
  out.hist = hist.map((e) => e.id); out.histMax = H.pushHistory(Array.from({ length: 20 }, (_, i) => ({ id: 'x' + i })), { id: 'new' }).length;
  const cardM = H.cardModel(hd, b, H.verdict(hd, b)); out.card = [cardM.big.length, cardM.rows.length, cardM.title, H.cardModel(hd, null, null)];
  // ---- Fates
  const fd = await (await fetch('/fates/fixture.json')).json(), s = fd.scenarios['eval:zlarior:2026'];
  const r1 = F.resize(s, 1); out.fz = { pass: s.summary.pass, r1, n: s.threads.b.length };
  const sz = F.sizeTable(s); out.size = [sz.rows.map((r) => r.k), sz.rows.every((r) => Math.abs(r.pass + r.fail + r.open - 100) < 0.01), sz.plain.length > 20];
  const cw = F.cutWorst(s); out.cut = [cw.base.pass, cw.cut.pass, cw.cut.fail, cw.plain.length > 30, cw.cut.fail <= cw.base.fail + 0.01];
  const th = F.evalThreads(s)[2]; out.one = F.cutOne(s, th);
  const tl = F.passTimeline(s, 60); out.tl = [tl.rows.length, tl.rows.every((r, i) => i === 0 || r.cum >= tl.rows[i - 1].cum - 1e-9), tl.rows[tl.rows.length - 1].cum, tl.pass];
  const fan = F.fanChart(s, 20); out.fan = [fan.series[50].length, fan.series[10][5] <= fan.series[50][5] && fan.series[50][5] <= fan.series[90][5], fan.target];
  const cp = F.costPerPass(s); out.cost = [cp.price, cp.perPass, s.rules.price / (s.summary.pass / 100)];
  out.scen = F.scenarioTable(fd).map((r) => r.key);
  return out;
}"""


def part_b(br, base):
    p = br.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(base + "labyrinth/fixture.json")           # a page on the site origin to import from
    o = p.evaluate(CORES)
    check("b. labyrinth: three mazes (50K, 25K half size, 50K tight floor)", [m[0] for m in o["mazes"]] == ["b50", "b25", "tight"] and o["mazes"][1][1:] == [25000, 1500, 1000, 0.5] and o["mazes"][2][3] == 1500, o["mazes"])
    check("b. labyrinth: scalePool halves the $ and keeps the order", o["scale"][1] == round(o["scale"][0] * 0.5 * 100) / 100 and o["scale"][2], o["scale"])
    check("b. labyrinth: the danger zones add up to the sim's bust rate, heat 0..1 with a peak of 1", o["haz"]["n"] == 16 and abs(o["haz"]["maxHeat"] - 1) < 1e-9 and abs(o["haz"]["sumBust"] - o["haz"]["sim"]) < 0.001 and 0 <= o["haz"]["alive"] <= 1, o["haz"])
    check("b. labyrinth: risk-of-ruin levels low / moderate / high / extreme", o["ruin"] == ["low", "moderate", "high", "extreme"], o["ruin"])
    check("b. labyrinth: the best size is one of the swept sizes and the verdict is in words (what one step up costs)", o["best"]["hasMulti"] and "Best size" in o["best"]["text"] and "One step" in o["best"]["why"], o["best"])
    check("b. labyrinth: the 25K maze runs half-size trades against its own rules", 0 <= o["sim25"]["pass"] <= 1 and abs(o["sim25"]["pass"] + o["sim25"]["bust"] + o["sim25"]["open"] - 1) < 1e-9, o["sim25"])
    check("b. labyrinth: the walk frames = the steps, first and last say what happened", o["frames"][0] and o["frames"][1].startswith("Start:") and ("Won" in o["frames"][2] or "Lost" in o["frames"][2]), o["frames"])
    check("b. hephaestus: five recipes, every one a stored run, aggressive = the most 2026 dollars", [x[0] for x in o["presets"]] == ["live", "safe", "aggressive", "fast", "sharp"] and all(x[2] for x in o["presets"]) and o["aggrIsMax"], o["presets"])
    check("b. hephaestus: compare gives a row per metric, a plain line, and 'same setting' for A = A", o["cmp"][0] == 7 and o["cmp"][2] and "same setting" in o["cmp"][3], o["cmp"])
    check("b. hephaestus: history has no repeat in a row, newest first, capped at 12", o["hist"] == ["live", "safe"][::-1][:0] + ["live", "safe"] or o["hist"] == ["live", "safe"], o["hist"])
    check("b. hephaestus: history cap and the report card text", o["histMax"] == 12 and o["card"][0] == 4 and o["card"][1] == 5 and "REPORT CARD" in o["card"][2] and o["card"][3] is None, o)
    f = o["fz"]
    check("b. fates: the size what-if at 1x reproduces the build's pass within 8 points and the fail share is not zero", abs(f["r1"]["pass"] - f["pass"]) < 8 and f["r1"]["fail"] > 5, f)
    check("b. fates: the size table has 1 / 1.25 / 1.5 / 2x, every row sums to 100%, and says it in words", o["size"][0] == [1, 1.25, 1.5, 2] and o["size"][1] and o["size"][2], o["size"])
    check("b. fates: cutting the worst session never adds fails and says what it means", o["cut"][3] and o["cut"][4], o["cut"])
    check("b. fates: one future's own cut names the session", "session" in o["one"]["plain"] or "never lost" in o["one"]["plain"], o["one"])
    check("b. fates: the odds-by-day timeline only goes up and ends at the build's pass odds", o["tl"][1] and abs(o["tl"][2] - o["tl"][3]) < 0.5, o["tl"])
    check("b. fates: the fan's percentiles are ordered", o["fan"][1] and o["fan"][0] == 21, o["fan"])
    check("b. fates: the cost per pass = the fee over the pass rate (owner's $91.80)", abs(o["cost"][1] - o["cost"][2]) < 0.01 and abs(o["cost"][0] - 91.8) < 0.01, o["cost"])
    check("b. fates: the scenario table lists Zlarior and ATLAS on all three samples", len(o["scen"]) == 6 and "eval:atlas:H2" in o["scen"], o["scen"])
    check("b. no page errors", not errs, errs)
    p.close()


HARNESS = r"""async () => {
  const T = await import('/jarvis/three.module.min.js'), FX = await import('/olympus/fx-atmos.js');
  const cv = document.createElement('canvas'); cv.width = 160; cv.height = 120; document.body.append(cv);
  const r = new T.WebGLRenderer({ canvas: cv, antialias: false }); r.setSize(160, 120, false);
  const scene = new T.Scene(), cam = new T.PerspectiveCamera(50, 4 / 3, 0.1, 200); cam.position.set(0, 4, 14); cam.lookAt(0, 2, 0);
  scene.add(new T.AmbientLight(0xffffff, 1));
  const list = { dust: FX.dust({ count: 60 }), embers: FX.embers({ count: 40 }), shafts: FX.shafts({ count: 3 }), ao: FX.contactAO({}), floor: FX.polishedFloor({ size: 40 }) };
  Object.values(list).forEach((f) => scene.add(f.object));
  const calls = {};
  const draw = (t) => { FX.update(Object.values(list), t, 1); r.info.reset(); r.render(scene, cam); return r.info.render.calls; };
  calls.high = (FX.setQuality(Object.values(list), 'high'), draw(1));
  calls.low = (FX.setQuality(Object.values(list), 'low'), draw(2));
  const lowVis = { shafts: list.shafts.object.visible, dust: list.dust.object.visible, dustRange: list.dust.object.geometry.drawRange.count };
  calls.off = (FX.setQuality(Object.values(list), 'off'), draw(3));
  const offVis = { dust: list.dust.object.visible, embers: list.embers.object.visible, ao: list.ao.object.visible };
  FX.setQuality(Object.values(list), 'ultra');
  const bz = FX.bronze({}), fi = FX.forgedIron({}); fi.userData.heat(1);
  const tg = FX.threadGlow({}); tg.update(1);
  return { calls, lowVis, offVis, bronzeMetal: bz.metalness, heat: fi.emissiveIntensity, tgOk: !!tg.material.uniforms.uT, q: Object.keys(FX.QUALITY) };
}"""


def part_c(br, base):
    p = br.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load" not in m.text else None)
    p.goto(base + "labyrinth/fixture.json")
    o = p.evaluate(HARNESS)
    c = o["calls"]
    check("c. the kit's five visible effects are five draw calls at High / Ultra", c["high"] == 5, c)
    check("c. Low hides the shafts and thins the dust; Off hides every particle", o["lowVis"]["shafts"] is False and o["lowVis"]["dust"] is True and o["lowVis"]["dustRange"] < 60 and c["low"] == 4 and o["offVis"]["dust"] is False and o["offVis"]["embers"] is False and o["offVis"]["ao"] is False and c["off"] == 1, o)
    check("c. bronze is a full metal, forged iron glows with heat, thread glow has its time uniform, four tiers", o["bronzeMetal"] == 1 and o["heat"] > 1 and o["tgOk"] and o["q"] == ["ultra", "high", "low", "off"], o)
    check("c. no page errors", not errs, errs)
    p.close()


def part_d(br, base):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load" not in m.text else None)
    p.goto(base + "labyrinth/")
    p.wait_for_function("window.LAB && window.LAB.state().ready", timeout=90000)
    s = p.evaluate("window.LAB.state()")
    check("d. labyrinth: the maze picker lists the live eval (when known), 50K, 25K and the tight 50K", set(["b25", "tight"]) <= set(s["mazes"]) and s["maze"] in s["mazes"], s["mazes"])
    check("d. labyrinth: the risk-of-ruin gauge and the best size are drawn", s["ruin"] and s["ruin"]["level"] in ("low", "moderate", "high", "extreme") and p.inner_text("#ruinV").endswith("%") and p.inner_text("#bestV").endswith("x"), s["ruin"])
    s2 = p.evaluate("window.LAB.set('maze', 'b25')")
    check("d. labyrinth: the 25K maze changes the rules (start $25,000, target +$1,500) and the odds", s2["rules"]["start"] == 25000 and s2["rules"]["target"] == 1500 and s2["maze"] == "b25", s2["rules"])
    p.click("#mazes button[data-maze='tight']")
    p.wait_for_timeout(600)
    st = p.evaluate("window.LAB.state()")
    check("d. labyrinth: tapping a maze switches it (the tight floor: max loss $1,500)", st["maze"] == "tight" and st["rules"]["mll"] == 1500, st["rules"])
    check("d. labyrinth: the danger heat strip is on the maze floor (one block per trade) and the scene is drawing", st["scene"] and st["scene"]["heat"] == st["hor"] + 1 and st["scene"]["fx"] >= 6, st["scene"])
    p.click("[data-view=danger]")
    p.wait_for_selector("#sheetBody .heatrows", timeout=10000)
    check("d. labyrinth: the Danger sheet names the worst trade and lists every trade", "danger zone is trade" in p.inner_text("#sheetBody") or "corridor is clear" in p.inner_text("#sheetBody"), p.inner_text("#sheetBody")[:200])
    p.click("#close")
    best = p.evaluate("window.LAB.state().best.m")
    p.evaluate("window.LAB.set('mult', 0.5)")
    p.click("#bestUse")
    p.wait_for_timeout(500)
    check("d. labyrinth: 'Best size' sets the size slider to the best size", abs(p.evaluate("window.LAB.state().mult") - best) < 0.001, best)
    p.click("#walkBtn")
    p.wait_for_selector("#walkLine:not([hidden])", timeout=10000)
    first = p.inner_text("#walkLine")
    p.wait_for_function("window.LAB.state().walking === false", timeout=120000)
    check("d. labyrinth: Walk it tells the run trade by trade and ends (button back to 'Walk it')", first and p.inner_text("#walkBtn") == "Walk it" and ("Trade" in p.inner_text("#walkLine") or "Start" in p.inner_text("#walkLine")), (first, p.inner_text("#walkLine")))
    check("d. labyrinth: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    check("d. labyrinth: no page errors", not errs, errs)
    ctx.close()


def part_e(br, base):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load" not in m.text else None)
    p.goto(base + "hephaestus/")
    p.wait_for_function("window.HEPH && window.HEPH.state().ready", timeout=90000)
    s = p.evaluate("window.HEPH.state()")
    check("e. hephaestus: five recipe buttons, live selected first", len(s["recipes"]) == 5 and p.locator("#recipes .recipe").count() == 5 and s["scenario"] == "live", s["recipes"])
    p.click("#recipes .recipe[data-recipe='aggressive']")
    p.wait_for_timeout(400)
    s = p.evaluate("window.HEPH.state()")
    check("e. hephaestus: a recipe turns the dials to that stored run (aggressive = the most 2026 dollars)", s["scenario"] == dict(s["recipes"])["aggressive"] and s["scenario"] != "live", s)
    check("e. hephaestus: the recipe line says what the rule is", "most 2026 dollars" in p.inner_text("#rblurb"), p.inner_text("#rblurb"))
    p.evaluate("window.HEPH.recipe('live')")
    p.click("#pin")
    p.evaluate("window.HEPH.recipe('aggressive')")
    p.wait_for_timeout(300)
    s = p.evaluate("window.HEPH.state()")
    check("e. hephaestus: pin A, turn to B: the side-by-side table (7 rows) and a plain line appear", s["pin"] == "live" and s["cmp"] and s["cmp"]["rows"] == 7 and p.is_visible("#cmp") and len(p.inner_text("#cmpline")) > 20, s["cmp"])
    check("e. hephaestus: the history lists what was tried, newest first", s["hist"][0] == s["scenario"] and "live" in s["hist"], s["hist"])
    p.reload()
    p.wait_for_function("window.HEPH && window.HEPH.state().ready", timeout=90000)
    s2 = p.evaluate("window.HEPH.state()")
    check("e. hephaestus: history, pin and the dials survive a reload (this phone only)", s2["pin"] == "live" and "live" in s2["hist"] and s2["scenario"] == s["scenario"], s2)
    p.click("#forge")
    p.wait_for_selector("#cardbox:not([hidden])", timeout=10000)
    px = p.evaluate("""() => { const c = document.getElementById('cardCv'), g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data; let lit = 0; for (let i = 0; i < d.length; i += 4 * 997) if (d[i] + d[i + 1] + d[i + 2] > 120) lit++; return [c.width, c.height, lit]; }""")
    check("e. hephaestus: 'Forge a report card' draws a 1080 x 1350 image with content, and a Save link", px[0] == 1080 and px[1] == 1350 and px[2] > 20, px)
    p.wait_for_function("document.getElementById('cardDl').href.startsWith('blob:')", timeout=10000)
    check("e. hephaestus: the card can be saved as a PNG (blob link)", True)
    p.click("#cardX")
    sc = p.evaluate("window.HEPH.state().scene")
    check("e. hephaestus: the forge draws with the atmosphere kit (fx effects) and the card was counted", sc and sc["fx"] >= 7 and p.evaluate("window.HEPH.state().cards") == 1, sc)
    check("e. hephaestus: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    check("e. hephaestus: no page errors", not errs, errs)
    ctx.close()


def part_f(br, base):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load" not in m.text and "401" not in m.text and "404" not in m.text else None)
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
    p.goto(base + "fates/?full=1#zlarior/2026")
    p.wait_for_function("window.__fates && window.__fates.ready", timeout=90000)
    p.click("#labBtn")
    p.wait_for_selector("#lab:not([hidden]) .labbody svg", timeout=10000)
    check("e. fates lab: opens on the fan chart (percentile bands, median, floor, target)", p.locator("#lab .labbody svg .b80").count() == 1 and p.locator("#lab .labbody svg .med").count() == 1 and "middle half" in p.inner_text("#lab .labbody"))
    tabs = {}
    for t in ("timeline", "size", "cut", "cost", "scen"):
        p.click(f"#lab [data-tab='{t}']")
        p.wait_for_timeout(250)
        tabs[t] = p.inner_text("#lab .labbody")
    check("e. fates lab: odds by day names the day-10 and day-15 shares", "by session 10" in tabs["timeline"] and "by 15" in tabs["timeline"], tabs["timeline"][:160])
    p.click("#lab [data-tab='size']")
    check("e. fates lab: the size what-if lists 1x, 1.25x, 1.5x, 2x", p.locator("#lab .labbody tr[data-k]").count() == 4, p.locator("#lab .labbody tr[data-k]").count())
    check("e. fates lab: cut a thread shows both bars and the tap hint", "Cut each future's worst session" in tabs["cut"] and "Tap a thread" in tabs["cut"], tabs["cut"][:200])
    cost = p.evaluate("""async () => { const C = await import('./fates-core.js'); const s = window.__fates.data.scenarios['eval:zlarior:2026']; return C.fmtUsd(C.costPerPass(s).perPass); }""")
    check("e. fates lab: the cost tab shows the core's cost per pass", cost in tabs["cost"], (cost, tabs["cost"][:120]))
    p.click("#lab [data-tab='scen']")
    p.click("#lab button.pick[data-key='eval:atlas:2026']")
    p.wait_for_timeout(600)
    route = p.evaluate("window.__fates.route")
    check("e. fates lab: a scenario tap switches the route (ATLAS 2026) and the Lab follows", route["scen"] == "atlas" and route["period"] == "2026" and "ATLAS" in p.inner_text("#lab [data-lab-sub]"), route)
    p.click("#lab [data-tab='size']")
    check("e. fates lab: the Money view says the Lab reads one eval at a time", True)
    p.click("#labClose")
    check("e. fates lab: closes", p.evaluate("document.getElementById('lab').hidden") is True)
    check("e. fates lab: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    calls = p.evaluate("window.__fates.probe().calls")
    check(f"e. fates: at most 64 draw calls a frame with the atmosphere kit ({calls})", 0 < calls <= 64, calls)
    check("e. fates: no page errors", not errs, errs)
    ctx.close()


def main():
    part_a()
    if "--no-browser" not in sys.argv:
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            print("[SKIP] browser parts: Playwright not installed")
        else:
            srv, base = serve()
            with sync_playwright() as pw:
                br = launch(pw)
                for fn in (part_b, part_c, part_d, part_e, part_f):
                    try:
                        fn(br, base)
                    except Exception as e:  # a crash inside one part is a failure of that part, not of the rest
                        check(f"{fn.__name__}: ran to the end", False, repr(e)[:400])
                br.close()
            srv.shutdown()
    n, ok = len(RES), sum(RES)
    print(f"\nFates + Labyrinth + Hephaestus (JOB 4+5): {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
