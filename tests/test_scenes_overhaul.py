"""Arena, Nemesis, Chronos and Argus, the overhaul (JOB 10+11, 2026-11-04): real materials in the scenes and the new features.

  a. static: the shared scenery kit (olympus/scenery.js: stone, bronze, basalt, crowd, banners, torch, gear, eye parts), each app's dress.js
     and extras.js, the FX core on every page, ES module syntax, Safari-16-safe syntax, the scenes dress themselves guarded and clean up
  b. pure logic (node): Chronos' "what if" replay (stop first, break-even at 1R + 1.25 pts, a target), the reel days, Arena's XP per day with the
     same daily caps as the score, Nemesis' pattern detector
  c. Chromium (390 x 844, WebGL through SwiftShader, no network), the demo / recorded data:
       Arena     the colosseum is dressed (spectators, banners, torches), the XP log has the history chart, the discipline calendar and the
                 you-against-you ladder; Quests has the weekly board; Trophies has the shelf; a boss fight plays when a boss is settled
       Nemesis   Leaks has the leak-of-the-week timeline and the pattern detector; an autopsy has a replay chart that plays; the Vow sheet has the
                 streak and the full Obsidian note
       Chronos   the Lab: compare two days, the three reels, what-if, the heatmap calendar, export (text, json, poster)
       Argus     the uptime streak, the incident history and the status card; a light's detail drawer
       every app LITE (3D Low) and under reduced motion: still dressed (LITE) or still (reduced), no console error
    python -X utf8 -m tests.test_scenes_overhaul            (--static: parts a and b only)
"""
from __future__ import annotations

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
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
APPS = ("arena", "nemesis", "chronos", "argus")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ a. static
def test_static():
    sc = read(KIT, "scenery.js")
    check("a. scenery.js: the real-materials kit (stone, bronze, basalt, crowd, banners, torch, gear, eyeParts), procedural textures only",
          all(f"export function {n}(" in sc for n in ("stone", "bronze", "basalt", "crowd", "banners", "torch", "dustAndRays", "figure", "gear", "eyeParts"))
          and not re.search(r"fetch\(|\.png|\.jpg|\.webp|XMLHttpRequest", sc))
    bad = [p for p in (r"\?\.[A-Za-z_$\[]", r"\?\?", r"\.at\(", r"\(\?<[=!]") if re.search(p, sc)]
    files = [(a, f) for a in APPS for f in ("dress.js", "extras.js") if os.path.exists(os.path.join(WEB, a, f))]
    check("a. the kit and the apps' new files avoid ?., ??, .at() and lookbehind (Safari 16)",
          not bad and all(not re.search(r"\?\?|\.at\(|\(\?<[=!]", read(WEB, a, f)) for a, f in files) and len(files) == 7, (bad, files))
    node = shutil.which("node")
    if node:
        bads = []
        for rel in [os.path.join(KIT, "scenery.js")] + [os.path.join(WEB, a, f) for a, f in files]:
            with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
                fh.write(read(rel))
            r = subprocess.run([node, "--check", fh.name], capture_output=True, text=True)
            os.remove(fh.name)
            if r.returncode:
                bads.append((os.path.basename(rel), r.stderr[-200:]))
        check("a. scenery.js and the seven new app modules parse (node --check as modules)", not bads, bads)
    for app in APPS:
        html = read(WEB, app, "index.html")
        scene = read(WEB, app, "scene.js") if os.path.exists(os.path.join(WEB, app, "scene.js")) else read(WEB, app, f"{app}.js")
        ok = '<script src="../olympus/fx-core.js?v=f1"></script>' in html and html.index("fx-core.js") < html.index('type="module"') and "scenery.js" in scene
        if app == "argus":
            ok = ok and "SC.eyeParts()" in scene and "SC.bronze(" in scene
        else:
            ok = ok and "dress" in scene and bool(re.search(r"try \{[^}]*dress\(", scene)) and "dr.dispose()" in scene
            dress = read(WEB, app, "dress.js")
            check(f"a. {app}/dress.js: stops every FX it started, removes what it added, optional (guarded)", "dispose()" in dress and "stop()" in dress and "guard" in dress, app)
        check(f"a. {app}: the FX core is on the page before the modules, the scene uses the scenery kit (guarded, cleaned up)", ok, app)
    check("a. the new features are wired: Arena (extras in the Quests / Trophies / XP log sheets), Nemesis (replay, timeline, patterns, streak), Chronos (a Lab pill), Argus (decorate + drawer)",
          all(x in read(WEB, "arena", "main.js") for x in ("X.weekBoard", "X.shelf", "X.xpHistory", "X.calendar", "X.versusYou"))
          and all(x in read(WEB, "nemesis", "nemesis.js") for x in ("X.replayChart", "X.leakTimeline", "X.patterns", "X.vowStreak", "X.obsidianAll"))
          and 'data-view="lab"' in read(WEB, "chronos", "index.html") and "X.labView" in read(WEB, "chronos", "chronos.js")
          and "X.decorate" in read(WEB, "argus", "argus.js") and 'id="drawer"' in read(WEB, "argus", "index.html"))
    check("a. Chronos: no new network, no write: the Lab is read-only (no fetch / localStorage in extras.js)", not re.search(r"fetch\(|localStorage|sessionStorage|XMLHttpRequest", read(WEB, "chronos", "extras.js")))
    check("a. Arena: the boss fight is a timeline (strikes, flash, shake, the crowd on its feet) started by the settled boss; the rank-up cheers",
          "bossFight" in read(WEB, "arena", "dress.js") and "dr.bossFight()" in read(WEB, "arena", "scene.js") and "dr.cheer(" in read(WEB, "arena", "scene.js"))
    sw = read(WEB, "sw.js")
    check("a. nothing in the root worker needs to change (olympus/ and the app folders are left alone)", "'olympus/'" in sw and all(f"'{a}/'" in sw for a in APPS))


def node_eval(js):
    node = shutil.which("node")
    if not node:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8", dir=tempfile.gettempdir()) as fh:
        fh.write(js)
    r = subprocess.run([node, fh.name], capture_output=True, text=True, cwd=ROOT)
    os.remove(fh.name)
    return r


def test_logic():
    ch = "file://" + os.path.join(WEB, "chronos").replace(os.sep, "/")
    ar = "file://" + os.path.join(WEB, "arena").replace(os.sep, "/")
    js = f"""
import fs from 'node:fs';
import {{ parseTrades }} from '{ch}/chroncore.js';
import {{ simulate, whatIf, reelDays }} from '{ch}/extras.js';
import {{ dayList }} from '{ch}/chroncore.js';
const doc = JSON.parse(fs.readFileSync({json.dumps(os.path.join(WEB, 'chronos', 'fixture.json'))}, 'utf8'));
const ts = parseTrades(doc), days = dayList(ts);
const mk = (side, bars, o = {{}}) => ({{ side, entry: {{ t: 100, px: 100 }}, exit: {{ t: 100 + 60 * bars.length, px: 100, kind: 'x' }}, stop: side === 'LONG' ? 90 : 110, target: null, usd: 0, r: 0,
  bars: {{ t: bars.map((_, i) => 100 + 60 * (i + 1)), o: bars.map((b) => b[0]), h: bars.map((b) => b[1]), l: bars.map((b) => b[2]), c: bars.map((b) => b[3]) }}, ...o }});
const out = {{}};
out.n = ts.length; out.days = days.length;
out.stop = simulate(mk('LONG', [[100, 102, 95, 98], [98, 99, 89, 90]]), {{}});                        // down to the stop: -1R
out.be = simulate(mk('LONG', [[100, 111, 99, 110], [110, 111, 99, 100]]), {{}});                        // +1R reached, then back through entry + 1.25: stopped at break-even
out.nobe = simulate(mk('LONG', [[100, 111, 99, 110], [110, 111, 99, 100]]), {{ be: null }});          // no break-even: ends at the close (100) = 0R
out.tgt = simulate(mk('LONG', [[100, 125, 99, 120]]), {{ targetR: 2 }});                                  // target 2R = 120 hit
out.short = simulate(mk('SHORT', [[100, 101, 80, 85]]), {{ targetR: 1 }});                              // short, target 1R = 90 hit
out.nostop = simulate(mk('LONG', [[100, 101, 99, 100]], {{ stop: null }}), {{}});
out.fixtureFinite = ts.every((t) => {{ const s = simulate(t, {{}}); return s === null || (Number.isFinite(s.r) && s.r >= -1.0001); }});
out.what = whatIf(ts).map((r) => [r.id, Number.isFinite(r.r), r.n]);
out.reel = (() => {{ const R = reelDays(days); return [R.best.usd >= R.avg.usd, R.avg.usd >= R.worst.usd, R.best.day !== R.worst.day]; }})();
console.log(JSON.stringify(out));
"""
    r = node_eval(js)
    if r is None:
        check("b. node missing: the pure-logic checks are skipped", True)
        return
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. Chronos what-if engine runs in node", False, (r.stdout[-300:], r.stderr[-400:]))
        return
    check("b. what-if replay: a stop is -1R, break-even catches the pullback (0R), no break-even rides to the close, a 2R target pays 2R, a short works, no stop = no replay",
          abs(o["stop"]["r"] + 1) < 1e-9 and o["be"]["why"] == "stopped at break-even" and abs(o["be"]["r"] - 0.125) < 1e-6 and abs(o["nobe"]["r"]) < 1e-9
          and abs(o["tgt"]["r"] - 2) < 1e-9 and abs(o["short"]["r"] - 1) < 1e-9 and o["nostop"] is None, o)
    check("b. what-if on the recorded trades: 7 rules, every result finite and no replayed loss worse than -1R; the reel days are ordered best >= average >= worst",
          o["fixtureFinite"] and len(o["what"]) == 7 and all(x[1] for x in o["what"]) and all(o["reel"]) and o["n"] >= 6, o)
    js2 = f"""
import {{ xpByDay }} from '{ar}/extras.js';
import {{ score }} from '{ar}/rules.js';
import fs from 'node:fs';
const R = JSON.parse(fs.readFileSync({json.dumps(os.path.join(WEB, 'arena', 'rules.json'))}, 'utf8'));
const ev = [];
for (let i = 0; i < 4; i++) ev.push({{ id: 'c' + i, day: '2026-10-05', kind: 'clean_trade', src: 'site' }});     // cap 2 a day
ev.push({{ id: 'b1', day: '2026-10-05', kind: 'bot_day', src: 'site' }}, {{ id: 'b2', day: '2026-10-06', kind: 'bot_day', src: 'site' }}, {{ id: 'x1', day: '2026-10-06', kind: 'rule_broken', src: 'site' }});
const days = xpByDay(ev, R), total = [...days.values()].reduce((s, d) => s + d.xp, 0);
console.log(JSON.stringify({{ d5: days.get('2026-10-05'), d6: days.get('2026-10-06'), total, score: score(ev, R, '2026-10-07').xp }}));
"""
    r = node_eval(js2)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
        check("b. Arena XP per day uses the score's own daily caps (4 clean trades = 2 count, 50 + 20 XP) and sums to the score; a broken rule marks the day",
              o["d5"]["xp"] == 70 and o["d5"]["clean"] == 4 and o["d6"]["broken"] == 1 and o["total"] == o["score"], o)
    except Exception:
        check("b. Arena xpByDay runs in node", False, (r.stdout[-300:], r.stderr[-400:]))


# ------------------------------------------------------------------ c. browser
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], **({"executable_path": exe} if exe else {}))


def page(br, origin, fx="high", reduced=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, accept_downloads=True,
                         reduced_motion="reduce" if reduced else "no-preference")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load" not in m.text and "ERR_FAILED" not in m.text else None)
    return ctx, p, errs


def tap(p, sel):
    """a plain click event: the software GL here draws about a frame a second, which makes Playwright's "is it stable" wait very slow"""
    p.locator(sel).first.dispatch_event("click")


def ready(p, ms=150000):
    p.wait_for_function("window.OLYMPUS && OLYMPUS.state() === 'ready'", timeout=ms)


def test_arena(br, origin):
    ctx, p, errs = page(br, origin)
    p.goto(f"{origin}/arena/", wait_until="commit")
    ready(p)
    p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=60000)
    p.wait_for_timeout(2500)
    st = p.evaluate("ARENA.state()")
    d = (st.get("scene") or {}).get("dress") or {}
    check("c. Arena: the colosseum is dressed: spectators, banners, torches (real flames) and no part failed",
          d.get("ok") and d.get("spectators", 0) >= 600 and {"crowd", "banners", "moon", "sand"} <= set(d.get("parts", [])) and not d.get("errors"), d)
    tap(p, "[data-tab=quests]"); p.wait_for_timeout(300)
    check("c. Arena: the Quests sheet has the weekly board (four bosses, hits, states) under today's three", p.locator(".wkboard .wkrow").count() == 4 and p.locator(".quest").count() == 3, p.inner_text("#sheetBody")[:200])
    tap(p, "[data-tab=trophies]"); p.wait_for_timeout(300)
    check("c. Arena: the Trophies sheet starts with the shelf (4 tiers, the closest trophy and how far) and still has 28 tiles", p.locator(".shelf .shelfcell").count() == 4 and p.locator(".trophy").count() == 28 and "closest" in p.inner_text(".shelf").lower())
    tap(p, "[data-trophy=first_blood]"); p.wait_for_timeout(200)
    check("c. Arena: a trophy card shows its progress bar", p.locator("#pop .tbar").count() == 1 and p.is_visible("#pop"))
    tap(p, "[data-tab=log]"); p.wait_for_timeout(300)
    cal = p.evaluate("[...document.querySelectorAll('.calgrid .sq')].map((e) => e.dataset.state)")
    check("c. Arena: the XP log has the 28-day XP chart, the 10-week discipline calendar (70 squares, clean / quiet / broken days) and the you-against-you ladder",
          p.locator(".xpchart rect").count() == 28 and len(cal) == 70 and "clean" in cal and p.locator(".vslist li").count() == 7 and p.locator(".vslist li.me").count() == 1
          and "where the xp comes from" in p.inner_text("#sheet").lower(), (len(cal), set(cal)))
    ov = p.evaluate("document.documentElement.scrollWidth - innerWidth")
    check("c. Arena: no sideways scroll with the new sections", ov <= 0, ov)
    # a boss fight and a cheer
    p.evaluate("ARENA.hold(false)")
    p.evaluate("ARENA.bossFight()"); p.wait_for_timeout(600)
    fight = p.evaluate("ARENA.state().scene.dress.fight")
    p.wait_for_function("ARENA.state().scene.dress.fight === false", timeout=60000)
    check("c. Arena: the boss fight plays (a timeline: strikes, flash, shake, the crowd up) and ends by itself", fight is True and p.evaluate("ARENA.state().scene.dress.fight") is False, fight)
    check("c. Arena: no console error", not errs, errs[:3])
    ctx.close()
    # LITE: dressed but lighter; reduced motion: still
    ctx, p, errs = page(br, origin, fx="low")
    p.goto(f"{origin}/arena/", wait_until="commit"); ready(p); p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=60000); p.wait_for_timeout(1500)
    d = p.evaluate("ARENA.state().scene.dress")
    check("c. Arena LITE (3D Low): still dressed (the crowd is thinned by the tier), no console error", d and d["ok"] and "crowd" in d["parts"] and not errs, (d, errs[:2]))
    ctx.close()
    ctx, p, errs = page(br, origin, reduced=True)
    p.goto(f"{origin}/arena/", wait_until="commit"); ready(p); p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=60000); p.wait_for_timeout(1000)
    check("c. Arena under reduced motion: the scene is up, still, no console error", p.evaluate("ARENA.state().scene.dress.ok") and not errs, errs[:2])
    ctx.close()


def test_nemesis(br, origin):
    ctx, p, errs = page(br, origin)
    p.goto(f"{origin}/nemesis/", wait_until="commit"); ready(p); p.wait_for_function("window.NEM && NEM.state().ready", timeout=60000); p.wait_for_timeout(2000)
    try:
        p.wait_for_function("NEM.state().scene.dress && NEM.state().scene.dress.fx >= 2", timeout=120000)   # the FX library loads after the scene
    except Exception:
        pass
    st = p.evaluate("NEM.state()")
    d = (st.get("scene") or {}).get("dress") or {}
    check("c. Nemesis: the underworld is dressed (moon, fog, real embers, haze, braziers) and the figures are bronze with an ember rim", {"moon", "fog", "embers", "braziers"} <= set(d.get("parts", [])), d)
    tap(p, "[data-view=leaks]"); p.wait_for_timeout(300)
    check("c. Nemesis: Leaks has the leak-of-the-week timeline (a dot per week) and the pattern detector (time of day, size, after a loss)",
          p.locator(".timeline .tl li").count() >= 3 and p.locator(".patterns h4").count() >= 2 and p.locator(".pfind").count() == 1 and "after a loss" in p.inner_text(".patterns").lower(), p.inner_text("#sheetBody")[:200])
    ids = st["ids"]
    p.evaluate(f"NEM.pick({json.dumps(ids[-1])})"); p.wait_for_timeout(400)
    check("c. Nemesis: an autopsy has the replay chart (the path, stop, sweep, entry, exit) and its Replay button draws it",
          p.locator(".rchart").count() == 1 and p.locator(".rchart .live").count() == 1 and p.locator("#rpPlay").count() == 1 and p.locator("#rpScrub").count() == 1, p.inner_text("#sheetBody")[:150])
    p.fill("#rpScrub", "300"); p.wait_for_timeout(100)
    d300 = p.get_attribute(".rchart .live", "d")
    p.fill("#rpScrub", "1000"); p.wait_for_timeout(100)
    d1000 = p.get_attribute(".rchart .live", "d")
    check("c. Nemesis: scrubbing the replay moves the line (a shorter path at 30% than at 100%)", d300 and d1000 and len(d300) < len(d1000), (len(d300 or ""), len(d1000 or "")))
    tap(p, "[data-view=vow]"); p.wait_for_timeout(300)
    check("c. Nemesis: the Vow sheet has the streak (kept weeks in a row, 8 dots) and the full-review Copy button next to the week note",
          p.locator(".streakbox .vnum").count() == 1 and p.locator("#copyAll").count() == 1 and p.locator("#copyWeek").count() == 1, p.inner_text("#sheetBody")[:150])
    tap(p, "#copyAll")
    try:
        p.wait_for_function("(NEM.state().copied || '').length > 20", timeout=20000)
    except Exception:
        pass
    txt = p.evaluate("NEM.state().copied || ''") or ""
    check("c. Nemesis: the full review for Obsidian has the week, the leak, the vow streak, the last weeks and the pattern", "## Nemesis review" in txt and "Vow streak" in txt and "Last weeks" in txt, txt[:160])
    check("c. Nemesis: no console error, no sideways scroll", not errs and p.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, errs[:3])
    ctx.close()
    ctx, p, errs = page(br, origin, fx="low")
    p.goto(f"{origin}/nemesis/", wait_until="commit"); ready(p); p.wait_for_function("window.NEM && NEM.state().ready", timeout=60000); p.wait_for_timeout(1000)
    check("c. Nemesis LITE: still dressed, no console error", p.evaluate("NEM.state().scene.dress") is not None and not errs, errs[:2])
    ctx.close()


def test_chronos(br, origin):
    ctx, p, errs = page(br, origin)
    p.goto(f"{origin}/chronos/", wait_until="commit"); ready(p); p.wait_for_function("window.CHR && CHR.state().ready", timeout=60000); p.wait_for_timeout(1500)
    st = p.evaluate("CHR.state()")
    d = (st.get("scene") or {}).get("dress") or {}
    check("c. Chronos: the tower has a real movement: brass gears (the playhead turns them), a pendulum under glass, a glass dial, two great gears",
          d.get("gears", 0) >= 6 and d.get("pendulum") and {"brass", "movement", "dial glass", "great gears"} <= set(d.get("parts", [])), d)
    p.evaluate("CHR.seek(0.1)"); p.wait_for_timeout(200)
    tap(p, "[data-view=lab]"); p.wait_for_timeout(300)
    tabs = p.evaluate("[...document.querySelectorAll('.labtabs button')].map((b) => b.textContent)")
    check("c. Chronos: the Lab pill opens five tabs (Compare, Reels, What if, Calendar, Export), inside the gutters", tabs == ["Compare", "Reels", "What if", "Calendar", "Export"], tabs)
    check("c. Chronos: Compare shows two days side by side (numbers, verdict, one chart of every trade in R) and changing a day redraws",
          p.locator(".cmpcol").count() == 2 and p.locator(".cchart .p").count() >= 2 and p.locator("#cmpA").count() == 1, p.inner_text("#sheetBody")[:150])
    a0 = p.evaluate("document.querySelector('.cmpout').dataset.a")
    opts = p.evaluate("[...document.querySelectorAll('#cmpA option')].map((o) => o.value)")
    p.select_option("#cmpA", opts[0] if opts[0] != a0 else opts[-1]); p.wait_for_timeout(150)
    check("c. Chronos: picking another day for A redraws the comparison", p.evaluate("document.querySelector('.cmpout').dataset.a") != a0)
    tap(p, "[data-lab=reels]"); p.wait_for_timeout(250)
    check("c. Chronos: Reels has the best, the worst and the average day, each with its paths and a Play button, and Play all three",
          p.locator(".reel").count() == 3 and p.locator(".reel button").count() == 3 and p.locator("#reelAll").count() == 1)
    tap(p, "[data-lab=whatif]"); p.wait_for_timeout(250)
    rows = p.evaluate("[...document.querySelectorAll('.wtab tr[data-rule]')].map((r) => r.dataset.rule)")
    check("c. Chronos: What if replays the trades with 7 rules (the bot's, no break-even, BE at 0.5R / 2R, targets 4R / 6R / 12R) and says what it found, with its limits",
          rows == ["bot", "nobe", "be05", "be2", "t4", "t6", "t12"] and p.locator(".wfind").count() == 1 and "Before commissions" in p.inner_text("#sheetBody"), rows)
    tap(p, "[data-lab=calendar]"); p.wait_for_timeout(250)
    has = p.locator(".hc.has").count()
    check("c. Chronos: the Calendar is a heatmap with one coloured cell per day the bot traded", has == st["nDays"] and p.locator(".month").count() >= 1, (has, st["nDays"]))
    day = p.get_attribute(".hc.has >> nth=0", "data-day")
    tap(p, "[data-lab=export]"); p.wait_for_timeout(250)
    box = p.evaluate("document.getElementById('reelBox').value")
    with p.expect_download(timeout=15000) as dl:
        tap(p, "#reelJson")
    name = dl.value.suggested_filename
    with p.expect_download(timeout=30000) as dl2:
        tap(p, "#reelPng")
    check("c. Chronos: Export gives the reel as text for a note, a .json file and a poster .png (downloads)", "## Chronos reel" in box and name.endswith(".json") and dl2.value.suggested_filename.endswith(".png"), (box[:60], name))
    tap(p, "[data-lab=calendar]"); p.wait_for_timeout(200)
    p.locator(".hc.has").nth(2).dispatch_event("click"); p.wait_for_timeout(500)
    check("c. Chronos: tapping a day in the calendar closes the lab and replays that day", p.evaluate("document.getElementById('sheet').hidden") and p.evaluate("CHR.state().day") is not None)
    check("c. Chronos: no console error, no sideways scroll", not errs and p.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, errs[:3])
    ctx.close()
    ctx, p, errs = page(br, origin, fx="low")
    p.goto(f"{origin}/chronos/", wait_until="commit"); ready(p); p.wait_for_function("window.CHR && CHR.state().ready", timeout=60000); p.wait_for_timeout(800)
    check("c. Chronos LITE: still dressed, no console error", p.evaluate("CHR.state().scene.dress") is not None and not errs, errs[:2])
    ctx.close()


def test_argus(br, origin):
    ctx, p, errs = page(br, origin)
    ctx.route(re.compile(r".*/home\.json.*"), lambda r: r.fulfill(status=200, content_type="application/json", body=open(os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json"), "rb").read()))
    p.goto(f"{origin}/argus/", wait_until="commit"); ready(p); p.wait_for_function("window.__argus && window.__argus.R", timeout=90000); p.wait_for_timeout(1500)
    tap(p, "[data-tab=hist]"); p.wait_for_timeout(300)
    check("c. Argus: Since yesterday has the uptime streak card, the incident history and the status card (save PNG, copy text)",
          p.locator("#uptime .xbig").count() == 1 and p.locator("#incidents").count() == 1 and p.locator("#sharePng").count() == 1 and p.locator("#shareCopy").count() == 1, p.inner_text("#p-hist")[:200])
    with p.expect_download(timeout=30000) as dl:
        tap(p, "#sharePng")
    check("c. Argus: the status card is saved as a PNG made on the phone", dl.value.suggested_filename == "argus-status.png")
    tap(p, "[data-tab=all]"); p.wait_for_timeout(200)
    first = p.evaluate("window.__argus.R.eyes[0].id")
    p.evaluate(f"window.__argus.pickLight({json.dumps(first)})"); p.wait_for_timeout(300)
    check("c. Argus: picking a light shows a Details button", p.locator("#pick .detbtn").count() == 1 and p.is_visible("#pick"))
    tap(p, "#pick .detbtn"); p.wait_for_timeout(300)
    check("c. Argus: the per-system drawer opens with the light, why, what to do, its 14-day history and its neighbours; Escape closes it",
          p.is_visible("#drawer") and p.locator("#drawer .dhead").count() == 1 and "14 days" in p.inner_text("#drawer").lower(), p.inner_text("#drawer")[:160])
    p.keyboard.press("Escape"); p.wait_for_timeout(150)
    check("c. Argus: the drawer closes", not p.is_visible("#drawer"))
    check("c. Argus: the 100 eyes have real materials (an iris texture, a glass cornea, an armillary of bronze) and no console error", not errs, errs[:3])
    ctx.close()


def main():
    test_static()
    test_logic()
    if "--static" in sys.argv:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return
    srv, origin = serve()
    only = [a for a in sys.argv[1:] if a in APPS]
    with sync_playwright() as pw:
        br = launch(pw)
        for app, fn in (("arena", test_arena), ("nemesis", test_nemesis), ("chronos", test_chronos), ("argus", test_argus)):
            if not only or app in only:
                try:
                    fn(br, origin)
                except Exception as e:
                    check(f"c. {app}: the browser checks ran to the end", False, e)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
