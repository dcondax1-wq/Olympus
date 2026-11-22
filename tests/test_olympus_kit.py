"""The OLYMPUS kit (tools/web_public/olympus/, docs/OLYMPUS_DESIGN.md): the nine 3D apps as ONE product.

Runs every app (Data City, Mind, Daphne, Oracle, Odeon, Fates, Hermes, Prometheus, Tyche) in Chromium (WebGL through
SwiftShader) at 390 x 844 (device pixel ratio 3, like an iPhone) on the real site layout (/<app>/, /jarvis/, /olympus/), with
every request off the page's origin refused (no network: each app falls back to its demo), and checks:
  a. static: each page links ../olympus/olympus.css before its own sheet and olympus.js (data-app = its id) before its
     modules; each app's code reads window.OLYMPUS and pauses on a hidden tab; the kit is Safari 16 safe (no color-mix, no
     :has, no lookbehind); the site build, the root worker and the pinned literals know olympus/
  b. the shared quality key: localStorage 'jfx' (Jarvis's own 3D-effects key) = high -> html[data-fx=high], the app's look
     HD (data-oly-lite=0), pixels <= 2 per CSS px; = low -> data-fx=low, LITE (data-oly-lite=1), pixels <= 1.5; an app's
     HD / LITE button writes the same key (so Jarvis follows); prefers-reduced-motion with no choice -> low
  c. the veil: the branded veil (OLYMPUS seal + the app's name) is up while loading, never takes a tap, and lifts on the
     first frame; when the app's code fails to load it removes itself and shows one line with Retry, and Retry reloads it
  d. the hidden tab: no draw call (WebGL or 2D) while document.hidden, drawing again once visible
  e. no sideways scroll, no console error, and the perf budget per app: draw calls / triangles (three.js renderer.info),
     JS heap, layouts per frame (no thrash)
    python -X utf8 -m tests.test_olympus_kit            (--table: print the perf table as markdown)
"""
from __future__ import annotations

import glob
import http.server
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
RES: list = []

# app id -> (the page's query/hash for a deterministic demo, the entry module (fails on purpose in c.), the HD/LITE button)
APPS = {
    "datacity": ("", "city.js", "#qB"),
    "mind": ("", "main.js", "#quality"),
    "tree": ("", "app.js", None),
    "oracle": ("?demo=1", "main.js", "#quality"),
    "odeon": ("?demo=1&autoplay=1", "app.js", None),
    "fates": ("", "fates.js", None),
    "hermes": ("#week,demo", "app.js", None),
    "prometheus": ("?demo=1", "forge.js", None),
    "tyche": ("?demo=1", "main.js", "#quality"),
}
# THE perf budget: one table, one run mode (2026-11-04). Every app is measured on the HD tier: the page is opened with ?gpu=1, which lifts the render core's
# software-GL cap (SwiftShader would otherwise hold every app to LITE and hide the bloom / finish passes and the HD pixel ratio), with the OLYMPUS level forced
# to 'high' (jfx) and generous waits (a busy shared box needs a minute to load a page). Draw calls and triangles per frame (three.js renderer.info) are portable;
# fps is not and is never judged. The budget is the measure + 25%, from `python tools/...`-free scratch runs of the same code path (docs/OLYMPUS_DESIGN.md has the
# table with the measures). The JS heap (HEAP_MB) and layouts per frame (LAYOUTS_PER_FRAME: DOM writes batched, never a read after a write in the frame loop) hold for all.
# arena: 2026-11-04 crowd LOD (olympus/scenery.js detail 'low' = 40 tris a spectator, 60% of the seats on a phone, a lighter arcade): HD phone scene ~258k -> 60k triangles.
#   app: (page query, budget calls, budget triangles)     calls 0 = no three.js scene (the heap only)
PERF = {
    "mind": ("", 44, 1_500), "tree": ("", 35, 60_000), "oracle": ("?demo=1", 200, 17_000), "odeon": ("?demo=1&autoplay=1", 53, 35_000), "fates": ("", 69, 26_500),
    "hermes": ("#week,demo", 0, 0), "prometheus": ("?demo=1", 66, 9_000), "tyche": ("?demo=1", 275, 30_700),
    "nemesis": ("?demo=1", 68, 30_000), "athena": ("?demo=1", 77, 7_900), "argus": ("?demo=1", 32, 118_500), "chronos": ("?demo=1", 84, 22_900),
    "cities": ("?demo=1", 27, 163_600), "kalshicity": ("?demo=1", 102, 52_200), "labyrinth": ("?demo=1", 60, 8_800), "hephaestus": ("?demo=1", 49, 5_500),
    "pantheon": ("?demo=1", 108, 31_600), "arena": ("?demo=1", 150, 75_000), "forum": ("?demo=1", 140, 9_000), "plutus": ("?demo=1", 24, 6_000),
    "ares": ("?demo=1", 50, 7_800), "kalshi": ("?demo=1", 0, 0),
    "datacity": ("", 120, 700_000),                                 # its own tiers are held by DATACITY_TIERS below
}
BUDGET = {a: (c, t) for a, (_, c, t) in PERF.items() if a in APPS}                      # the apps with a full kit case (test_app)
MORE = {a: v for a, v in PERF.items() if a not in APPS}                                 # the others: the budget alone (test_more)


def hd(q):
    """the one run mode: the page query with ?gpu=1 added"""
    return ("?gpu=1" + q) if q.startswith("#") else ("?gpu=1" if not q else q + "&gpu=1")


# Data City by tier (2026-11-04, datacity/caps.js, docs/OLYMPUS_PERF.md): the page forces the tier with ?q= and the device hint with ?phone=; (calls, triangles) at the far
# overview and at the close-up of the densest district, measured at 390 x 844 / dpr 3 under SwiftShader + ~20% headroom. "phone-high" = a phone at the high tier (the
# phone-safe preset), "ultra" = a PC at ultra (the full city). The heap budget is HEAP_MB for phone-high.
# (query, calls, triangles at the worst of the load view and the close-up, calls at the FAR overview: camera 380 units out, the view a phone opens on).
# 2026-11-04 after the landmark meshes were merged (52 -> 15 draws) and the overview-only details hidden on phones: phone-high far overview 59 calls (was 78), worst 71.
# phone-high: the owner wants the full-detail Data City on phones (2026-11-09), so the budget is what it really measures
# (66 calls worst/far, 223k tris, 47.8 MB heap) with headroom; it used to be the thinned "phone-safe" preset (80 / 250k / far 60 / 40 MB).
DATACITY_TIERS = {"phone-high": ("?q=high&phone=1", 90, 250_000, 75), "ultra": ("?q=ultra&phone=0", 110, 700_000, 100)}
HEAP_MB, LAYOUTS_PER_FRAME = 40, 1.25   # 1.25: room for the day-sprint HUDs (Odeon 1.11 under load)
DATACITY_PHONE_HEAP_MB = 60   # phone-high Data City heap (measured 47.8 MB); the other apps keep HEAP_MB

COUNT_DRAWS = """
(() => {
  window.__draws = 0;
  const wrap = (P, names) => { if (!P) return; for (const m of names) { const f = P[m]; if (typeof f !== 'function') continue;
    P[m] = function () { window.__draws++; return f.apply(this, arguments); }; } };
  wrap(window.WebGLRenderingContext && WebGLRenderingContext.prototype, ['drawArrays', 'drawElements']);
  wrap(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype, ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced', 'drawRangeElements']);
  wrap(window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype, ['fillRect', 'clearRect', 'drawImage', 'fill', 'stroke', 'fillText']);
  window.__frames = 0;
  const tick = () => { window.__frames++; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
})();
"""
HIDE = """(on) => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => on });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (on ? 'hidden' : 'visible') });
  document.dispatchEvent(new Event('visibilitychange'));
}"""
# the full-screen canvases (the 3D view, an effects layer); small static thumbnails are left out
CANVAS_RATIO = """() => Math.max(0, ...[...document.querySelectorAll('canvas')].filter((c) => c.clientWidth >= innerWidth * 0.9 && !c.hidden)
  .map((c) => c.width / c.clientWidth))"""


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ a. static
def test_static():
    js, css = read(os.path.join(KIT, "olympus.js")), read(os.path.join(KIT, "olympus.css"))
    arena = read(os.path.join(os.path.dirname(KIT), "arena", "main.js"))
    check("a. OLYMPUS.sfx(name): loads olympus/sfx.js lazily, never throws, no-op when missing or when the host says it is quiet (OLYMPUS_QUIET); Arena plays rankup through it, guarded",
          all(x in js for x in ("sfx: function (name)", "window.OLYMPUS_QUIET", "'sfx.js?v=s4'", "k.play(name)")) and "O.sfx('rankup')" in arena and "O && O.sfx" in arena)
    check("a. the kit: olympus.js reads and writes 'jfx' (Jarvis's key), caps the pixel ratio, pauses on a hidden tab",
          "KEY = 'jfx'" in js and "level === 'off' ? 1 : l ? 1.5 : 2" in js and "visibilityState" in js)
    render = read(os.path.join(KIT, "render.js"))
    check("a. power (docs/OLYMPUS_PERF.md): the kit has saver() (battery API, Save-Data, the owner's 'olympus.saver'), idle(), frameGap(), covered(); hidden() includes covered",
          all(x in js for x in ("getBattery", "saveData", "'olympus.saver'", "frameGap: function", "idle: function", "covered: function", "|| covered;", "data-oly-covered", "e.origin === location.origin")))
    # perf v2 (2026-11-14): the pixel ratio comes from the render-scale governor (olympus/render-scale.js); the saver cap of 1.5 lives in its range()
    rscale = read(os.path.join(KIT, "render-scale.js"))
    check("a. the render core keeps the kit's frame gap (30 fps idle on high, 15 on low), never steps down because of its own cap, caps the pixel ratio at 1.5 in saver (the governor's range), sleeps when covered",
          all(x in render for x in ("O.frameGap", "gap + 9", "saver: !!(Ok && Ok.saver && Ok.saver())", "pageHidden()", "O.onPower"))
          and "if (x.saver) { budget = Math.min(budget, 1.5); ceil = Math.min(ceil, 1.5); }" in rscale
          and all(x in js for x in ("idle ? (level === 'low' ? 66 : 33) : 0", "idle ? 500 : 0", "saverNow()) return idle ? 66 : 33")))
    check("a. ambience: every app of the kit has a bed in the AMBIENT table, each bed exists in sfx.js, none starts before a gesture or when muted / saver / Jarvis talks",
          all(f"{a}:" in js.split("var AMBIENT = {")[1].split("};")[0] for a in list(APPS) + list(MORE) + ["bridge"]) and "OLYMPUS_QUIET" in js
          and all(f"{b}: ['" in read(os.path.join(KIT, "sfx.js")) for b in ("wind", "forge", "sea", "city", "forest", "crowd", "chimes", "space")))   # 2026-11-11: the BED table maps old names to the new beds
    own = ["tree/app.js", "hermes/fx.js", "hermes/app.js", "tyche/main.js", "ares/ares.js", "plutus/plutus.js", "pantheon/pantheon.js", "forum/scene.js",
           "kalshicity/cityscene.js", "mind/main.js", "athena/athena.js", "oracle/main.js", "odeon/app.js", "prometheus/forge.js", "argus/argus.js", "datacity/city.js",
           "fates/fates.js", "labyrinth/scene.js", "hephaestus/scene.js", "arena/scene.js", "nemesis/scene.js", "chronos/scene.js", "chronos/chronos.js"]
    miss = [f for f in own if "frameGap" not in read(os.path.join(WEB, *f.split("/")))]
    check("a. every own frame loop (tree, hermes x2, tyche, ares, plutus, pantheon, forum, kalshicity, mind, athena, fates, labyrinth, hephaestus, arena, nemesis, chronos x2) keeps the kit's frame gap (idle / saver / Off) and sleeps hidden or covered", not miss, miss)
    scen = read(os.path.join(KIT, "scenery.js"))
    check("a. the shared crowd is low-poly by default (detail 'low' = 40 triangles a spectator, 'full' keeps the capsules) and thins evenly (density); the Arena asks for 60% on a phone",
          all(x in scen for x in ("detail = 'low'", "density = 1", "low ? new THREE.CylinderGeometry", "SphereGeometry(0.115, 4, 2)")) and "density: Math.min(innerWidth, innerHeight) < 600 ? 0.6 : 1" in read(os.path.join(WEB, "arena", "dress.js")))
    off_tier = [f for f in ("oracle/scene.js", "odeon/scene.js", "fates/fates-scene.js") if "=== 'off' ? 'off'" not in read(os.path.join(WEB, *f.split("/")))]
    check("a. oracle, odeon and fates: 3D Off is the core's 'off' tier (not forced to low by the software cap)", not off_tier, off_tier)
    ath = read(os.path.join(WEB, "athena", "athena.js"))
    check("a. athena's shelves are instanced (books, strips, scrolls, caps: InstancedMesh), tyche's 3D Off is the core's 'off' tier",
          ath.count("InstancedMesh(") == 1 and "instanceColor" in ath and "O.fx() === 'off' ? 'off'" in read(os.path.join(WEB, "tyche", "scene.js")))
    jv = read(os.path.join(WEB, "jarvis", "index.html"))
    check("a. Jarvis tells a framed app when a sheet covers it: { olympus: 'covered', on } on open and close (delimited block in index.html)",
          "==== OLYMPUS covered" in jv and "==== end OLYMPUS covered" in jv and "{ olympus: 'covered', on }, location.origin" in jv)
    jarvis = read(os.path.join(WEB, "jarvis", "index.html"))
    check("a. Jarvis keeps its 3D level in the same 'jfx' key with the same four levels",
          "g('jfx')" in jarvis and "rawSet('jfx', level)" in jarvis and "['ultra', 'high', 'low', 'off']" in jarvis)
    bad = [p for p in (r"color-mix\(", r":has\(", r"\(\?<[=!]", r"\.at\(", r"\?\.", r"\?\?") if re.search(p, js + css)]
    check("a. the kit is Safari 16 safe (no color-mix, :has, lookbehind, .at(), and ES5-only syntax in the classic script)", not bad, bad)
    check("a. the kit: AGORA's system fonts (serif display, no Orbitron), the type scale, 44 px taps, safe areas, the orb's 80 x 160, dvh with a vh fallback, reduced motion",
          "Iowan Old Style" in css and "--oly-display" in css and "@font-face" not in css and "--oly-t-label" in css and "--oly-tap: 44px" in css
          and all(f"safe-area-inset-{e}" in css for e in ("top", "right", "bottom", "left")) and "--oly-orb-w: 80px; --oly-orb-h: 160px" in css
          and "--oly-vh: 100vh" in css and "@supports (height: 100dvh)" in css and "prefers-reduced-motion: reduce" in css)
    check("a. the veil never takes a tap", re.search(r"\.oly-veil \{[^}]*pointer-events: none", css))
    for app, (_, entry, _) in APPS.items():
        html = read(os.path.join(WEB, app, "index.html"))
        i_css, i_js = html.find("../olympus/olympus.css"), html.find(f'../olympus/olympus.js?v=o24" data-app="{app}"')
        own = [m.start() for m in re.finditer(r'<link rel="stylesheet" href="(?!\.\./olympus)', html)] + [html.find("<style>")]
        mods = [m.start() for m in re.finditer(r'<script type="module"', html)]
        code = "".join(read(p) for p in glob.glob(os.path.join(WEB, app, "*.js")))
        check(f"a. {app}: the kit's sheet first, its script before the app's modules, the app reads OLYMPUS (quality, hidden tab)",
              i_css > 0 and all(i_css < o for o in own if o >= 0) and 0 < i_js < min(mods)
              and "window.OLYMPUS" in code and ".hidden()" in code and ("O?.track(" in code or "O.ready()" in code or "O?.ready()" in code
                                                                    or "from '../olympus/render.js'" in code),   # the render core lifts the veil (ready / track) itself
              (i_css, own, i_js, mods))
    build = read(os.path.join(ROOT, "tools", "build_web_dashboard.py"))
    sw = read(os.path.join(WEB, "sw.js"))
    check("a. the site build publishes olympus/ and the root worker leaves it alone",
          bool(re.search(r'for app in \([^)]*"olympus"[^)]*\):', build)) and bool(re.search(r"const OTHER_APPS = \[[^\]]*'olympus/'", sw)))


# ------------------------------------------------------------------ the server: the real site layout, nothing else
class Handler(http.server.SimpleHTTPRequestHandler):
    fail: set = set()

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in Handler.fail:
            self.send_error(404)
            return
        return super().do_GET()

    def translate_path(self, path):
        p = path.split("?")[0].split("#")[0]
        top = p.lstrip("/").split("/")[0]
        if top in APPS or top in MORE or top in ("jarvis", "olympus", "assets"):      # assets/: the shared CC0 art (olympus/env-kit.js)
            q = p.lstrip("/")
            if q.endswith("/"):
                q += "index.html"
            return os.path.join(WEB, *q.split("/"))
        q = p.lstrip("/")
        if q and "/" not in q and os.path.isfile(os.path.join(WEB, q)):    # the site's root files the apps load (pc_feed.js, age.css): on the real site too
            return os.path.join(WEB, q)
        return os.path.join(WEB, "__missing__")


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


from tests import browser_kit as BK  # noqa: E402  (shared launch: one reused browser, load-scaled timeouts, one retry of a flaky wait)


def launch(pw):
    return BK.launch(pw, args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-precise-memory-info"])


def page(br, origin, fx=None, reduced=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                         reduced_motion="reduce" if reduced else "no-preference")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    init = COUNT_DRAWS
    init += f"try {{ localStorage.setItem('jfx', {json.dumps(fx)}); }} catch (e) {{}}" if fx else "try { localStorage.removeItem('jfx'); } catch (e) {}"
    ctx.add_init_script(init)
    p = ctx.new_page()
    p.set_default_timeout(150000)                  # a busy shared box (software GL) can take a minute or two to load a page
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    return ctx, p, errs


def wait_ready(p, ms=120000):
    try:
        p.wait_for_function("() => window.OLYMPUS && OLYMPUS.state() === 'ready'", timeout=ms)
        p.wait_for_function("() => !document.querySelector('.oly-veil')", timeout=30000)   # software GL: the fade runs on ~1 frame/s
        return True
    except Exception:
        return False


def metrics(cdp):
    return {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}


def test_app(br, origin, app, table):
    q, entry, qbtn = APPS[app]
    url = f"{origin}/{app}/{hd(q)}"
    # ---- b. high + the veil + e. perf
    ctx, p, errs = page(br, origin, fx="high")
    p.goto(url)
    veil = p.evaluate("""() => { const v = document.querySelector('.oly-veil');
      return v ? { name: v.textContent, pe: getComputedStyle(v).pointerEvents, seal: !!v.querySelector('.oly-seal') } : null; }""")
    ok = wait_ready(p)
    check(f"c. {app}: the veil (seal + name, no taps) while loading, lifted on the first frame",
          ok and (veil is None or (veil["seal"] and veil["pe"] == "none" and "OLYMPUS" in veil["name"])), (ok, veil))
    p.wait_for_timeout(2500)
    st = p.evaluate("""() => ({ fx: document.documentElement.dataset.fx, lite: document.documentElement.dataset.olyLite,
      sx: document.documentElement.scrollWidth - innerWidth, bx: document.body.scrollWidth - innerWidth, stats: OLYMPUS.stats() })""")
    ratio = p.evaluate(CANVAS_RATIO)
    # perf v2 (2026-11-14): the render-scale governor may step a slow scene's resolution down (software GL here) from the HD budget (2x;
    # Data City 1.5x) toward its floor (1x): the HD look is the tier (data-fx high, no auto-LITE), the ratio is never above the budget
    check(f"b. {app}: jfx=high -> data-fx=high, the HD look, <= 2 pixels per CSS px (dpr 3 phone; the governor may lower a slow scene to 1x)",
          st["fx"] == "high" and st["lite"] == "0" and (0.99 <= ratio <= 2.01 if app != "datacity" else 0.99 <= ratio <= 1.51), (st["fx"], st["lite"], ratio))
    check(f"e. {app}: no sideways scroll at 390 x 844", st["sx"] <= 0 and st["bx"] <= 0, (st["sx"], st["bx"]))
    # perf: layouts per frame over 2 s, the heap, renderer.info
    cdp = ctx.new_cdp_session(p)
    cdp.send("Performance.enable")
    m0, f0 = metrics(cdp), p.evaluate("window.__frames")
    p.wait_for_timeout(2000)
    for _ in range(20):                                    # software GL on a busy box draws ~1 frame/s: measure over at least 8 frames (layouts per FRAME is the claim)
        if p.evaluate("window.__frames") - f0 >= 8:
            break
        p.wait_for_timeout(2000)
    m1, f1 = metrics(cdp), p.evaluate("window.__frames")
    frames = max(1, f1 - f0)
    lpf = (m1.get("LayoutCount", 0) - m0.get("LayoutCount", 0)) / frames
    spf = (m1.get("RecalcStyleCount", 0) - m0.get("RecalcStyleCount", 0)) / frames
    try:
        cdp.send("HeapProfiler.collectGarbage")             # the heap is the live set, not garbage waiting for a GC (it read 25-47 MB for the same page)
        m1 = metrics(cdp)
    except Exception:
        pass
    heap = m1.get("JSHeapUsedSize", 0) / 1e6
    s = p.evaluate("OLYMPUS.stats()")
    row = {"app": app, "three": s.get("three"), "calls": s.get("calls"), "triangles": s.get("triangles"), "points": s.get("points"),
           "geometries": s.get("geometries"), "textures": s.get("textures"), "programs": s.get("programs"),
           "pixelRatio": s.get("pixelRatio"), "heap_mb": round(heap, 1), "layouts_per_frame": round(lpf, 2), "styles_per_frame": round(spf, 2),
           "frames_measured": frames}
    table.append(row)
    calls, tris = BUDGET[app]
    within = (not s.get("three") or (s["calls"] <= calls and s["triangles"] <= tris)) and heap <= HEAP_MB and lpf <= LAYOUTS_PER_FRAME
    check(f"e. {app}: within the perf budget ({row['calls']} calls, {row['triangles']} tris, {row['heap_mb']} MB heap, "
          f"{row['layouts_per_frame']} layouts/frame)", within, row)
    # ---- d. the hidden tab
    p.evaluate(HIDE, True)
    p.wait_for_timeout(400)
    d0 = p.evaluate("window.__draws")
    p.wait_for_timeout(1500)
    d1 = p.evaluate("window.__draws")
    p.evaluate(HIDE, False)
    p.wait_for_timeout(1500)
    d2 = p.evaluate("window.__draws")
    check(f"d. {app}: no draw call while the tab is hidden, drawing again once visible", d1 == d0 and d2 > d1, (d0, d1, d2))
    # ---- b. the app's own HD / LITE button writes the shared key
    if qbtn:
        p.click(qbtn)
        p.wait_for_timeout(300)
        got = p.evaluate("() => [localStorage.getItem('jfx'), document.documentElement.dataset.fx, document.documentElement.dataset.olyLite]")
        check(f"b. {app}: its HD / LITE button writes the shared 'jfx' key (Jarvis follows)", got == ["low", "low", "1"], got)
    real = [e for e in errs if "net::ERR_FAILED" not in e and "Failed to load resource" not in e]
    check(f"e. {app}: no console error", not real, real[:3])
    ctx.close()
    # ---- b. low
    ctx, p, errs = page(br, origin, fx="low")
    p.goto(url)
    ok = wait_ready(p)
    p.wait_for_timeout(1200)
    st = p.evaluate("() => [document.documentElement.dataset.fx, document.documentElement.dataset.olyLite]")
    ratio = p.evaluate(CANVAS_RATIO)
    check(f"b. {app}: jfx=low -> data-fx=low, the LITE look, <= 1.5 pixels per CSS px", ok and st == ["low", "1"] and 0 < ratio <= 1.51, (ok, st, ratio))
    ctx.close()
    # ---- b. reduced motion, nothing chosen -> low
    ctx, p, errs = page(br, origin, reduced=True)
    p.goto(url)
    ok = wait_ready(p)
    got = p.evaluate("() => [document.documentElement.dataset.fx, OLYMPUS.reduced(), OLYMPUS.chosen()]")
    check(f"b. {app}: prefers-reduced-motion and no choice -> low, reduced, not stored", ok and got == ["low", True, False], (ok, got))
    ctx.close()
    # ---- c. the app's code fails to load: the veil goes, one line + Retry; Retry brings it back
    ctx, p, errs = page(br, origin, fx="high")
    Handler.fail = {f"/{app}/{entry}"}
    try:
        p.goto(url)
        p.wait_for_selector(".oly-err", timeout=15000)
        got = p.evaluate("""() => ({ veil: !!document.querySelector('.oly-veil'), text: document.querySelector('.oly-err').textContent,
          retry: !!document.querySelector('.oly-err .oly-err-retry'), state: OLYMPUS.state(),
          h: document.querySelector('.oly-err').getBoundingClientRect().height })""")
        check(f"c. {app}: its code missing -> the veil removes itself, one line with Retry", not got["veil"] and got["retry"]
              and "could not load" in got["text"] and got["state"] == "failed" and got["h"] < 120, got)
    except Exception as e:
        check(f"c. {app}: its code missing -> the veil removes itself, one line with Retry", False, e)
    finally:
        Handler.fail = set()
    try:
        p.click(".oly-err-retry")
        ok = wait_ready(p)
        check(f"c. {app}: Retry reloads the page and it comes up", ok and not p.query_selector(".oly-err"))
    except Exception as e:
        check(f"c. {app}: Retry reloads the page and it comes up", False, e)
    ctx.close()


def test_power(br, origin):
    """the kit's power layer on a live page (Mind): the owner's touch = full rate, idle = 30 fps on high / 15 on low, battery saver caps, covered = no draw"""
    ctx, p, errs = page(br, origin, fx="high")
    p.goto(f"{origin}/mind/")
    wait_ready(p)
    p.evaluate("() => window.dispatchEvent(new Event('pointermove'))")                      # a touch (dispatched: emulated touch pages do not always deliver a mouse move)
    p.evaluate("() => { window.__p = (k) => OLYMPUS.frameGap(); }")
    gap_active = p.evaluate("() => { window.dispatchEvent(new Event('pointermove')); return OLYMPUS.frameGap(); }")   # touch and read in one go (the machine can be slow between calls)
    p.wait_for_timeout(4400)
    gap_idle = p.evaluate("() => OLYMPUS.frameGap()")
    p.evaluate("() => window.dispatchEvent(new Event('pointermove'))")
    gap_back = p.evaluate("() => { window.dispatchEvent(new Event('pointermove')); return OLYMPUS.frameGap(); }")
    check("g. power: touching = every frame (gap 0), idle 4 s on high = 30 fps (33 ms), a touch brings the full rate back", (gap_active, gap_idle, gap_back) == (0, 33, 0), (gap_active, gap_idle, gap_back))
    sv = p.evaluate("() => { window.dispatchEvent(new Event('pointermove')); OLYMPUS.setSaver('on'); return [OLYMPUS.saver(), OLYMPUS.frameGap(), document.documentElement.dataset.olySaver, OLYMPUS.stats().power]; }")
    check("g. power: battery saver (the owner's switch) = 30 fps even while touching, html[data-oly-saver=1], reported in stats()", sv[0] is True and sv[1] == 33 and sv[2] == "1" and sv[3]["saver"] is True, sv)
    p.evaluate("() => OLYMPUS.setSaver('off')")
    check("g. power: the owner's 'off' beats a low battery; 'auto' goes back to the battery / Save-Data reading",
          p.evaluate("() => [OLYMPUS.saver(), (OLYMPUS.setSaver('auto'), OLYMPUS.saver())]") == [False, False])
    p.evaluate("() => OLYMPUS.covered(true)")
    p.wait_for_timeout(600)
    p.evaluate("window.__draws = 0")
    p.wait_for_timeout(1500)
    cov = p.evaluate("() => [window.__draws, OLYMPUS.hidden(), document.documentElement.dataset.olyCovered]")
    p.evaluate("() => OLYMPUS.covered(false)")
    p.wait_for_timeout(2500)
    after = p.evaluate("window.__draws")
    check("g. power: covered (a sheet over the scene) = hidden(): no draw call; uncovered = drawing again", cov[0] == 0 and cov[1] is True and cov[2] == "1" and after > 0, (cov, after))
    p.evaluate("() => window.postMessage({ olympus: 'covered', on: true }, location.origin)")
    p.wait_for_timeout(300)
    check("g. power: a same-origin postMessage { olympus: 'covered' } from the parent covers the scene", p.evaluate("() => OLYMPUS.covered()") is True)
    p.evaluate("() => OLYMPUS.covered(false)")
    # ambience: Mind's bed ('space') is wanted from the start, plays after the first touch, steps aside in saver / when the owner turns it off
    st0 = None
    try:
        p.wait_for_function("() => window.OLYMPUS_SFX && OLYMPUS_SFX.ambientState", polling=200, timeout=15000)
        st0 = p.evaluate("() => OLYMPUS_SFX.ambientState()")
        p.mouse.click(150, 400)
        p.wait_for_function("() => OLYMPUS_SFX.ambientState().playing === 'space'", polling=200, timeout=8000)
        st1 = p.evaluate("() => OLYMPUS_SFX.ambientState()")
        p.evaluate("() => OLYMPUS.setSaver('on')")
        sv = p.evaluate("() => OLYMPUS_SFX.ambientState().playing")
        p.evaluate("() => OLYMPUS.setSaver('auto')")
        back = p.evaluate("() => OLYMPUS_SFX.ambientState().playing")
        p.evaluate("() => OLYMPUS.ambience(false)")
        off = p.evaluate("() => OLYMPUS_SFX.ambientState().playing")
        p.evaluate("() => { window.OLYMPUS_QUIET = () => true; }")
        p.evaluate("() => OLYMPUS.ambience(true)")
        ok = st0["want"] == "space" and st0["playing"] == "" and st1["playing"] == "space" and sv == "" and back == "space" and off == ""
        check("g. ambience: Mind wants 'space' at load, nothing plays before a touch, it plays after one, battery saver silences it, 'auto' brings it back, the owner's switch stops it", ok, (st0, st1, sv, back, off))
    except Exception as e:
        check("g. ambience: Mind's bed starts after the first touch", False, (st0, e))
    ctx.close()
    ctx, p, errs = page(br, origin, fx="low")
    p.goto(f"{origin}/mind/")
    wait_ready(p)
    p.wait_for_timeout(4400)
    check("g. power: idle on low = 15 fps (66 ms)", p.evaluate("() => OLYMPUS.frameGap()") == 66)
    ctx.close()
    ctx, p, errs = page(br, origin, fx="off")
    p.goto(f"{origin}/mind/")
    wait_ready(p)
    p.evaluate("() => window.dispatchEvent(new Event('pointermove'))")
    g0 = p.evaluate("() => OLYMPUS.frameGap()")
    p.wait_for_timeout(4400)
    check("g. power: 3D effects Off = static: idle redraws at most twice a second (500 ms), a touch gives full rate", g0 == 0 and p.evaluate("() => OLYMPUS.frameGap()") == 500, g0)
    check("g. power: no console error", not [e for e in errs if "Failed to load resource" not in e], errs[:3])
    ctx.close()


def test_more(br, origin, app):
    q, calls, tris = MORE[app]
    ctx, p, errs = page(br, origin, fx="high")
    p.goto(f"{origin}/{app}/{hd(q)}")
    ok = wait_ready(p, 120000)
    p.wait_for_timeout(2500)
    cdp = ctx.new_cdp_session(p)
    cdp.send("Performance.enable")
    heap = metrics(cdp).get("JSHeapUsedSize", 0) / 1e6
    s = p.evaluate("() => (window.OLYMPUS ? OLYMPUS.stats() : {})")
    three = bool(s.get("three")) and calls > 0
    good = (not three or (s["calls"] <= calls and s["triangles"] <= tris)) and heap <= HEAP_MB
    check(f"e. {app}: within the perf budget ({s.get('calls')} calls / {calls}, {s.get('triangles')} tris / {tris}, {round(heap, 1)} MB heap)", good, (ok, s, heap))
    real = [e for e in errs if "net::ERR_FAILED" not in e and "Failed to load resource" not in e]
    check(f"e. {app}: no console error", not real, real[:3])
    ctx.close()


def test_mind_labels(br, origin):
    """Mind: no galaxy name ever sits under the top HUD (or the bottom stats)."""
    ctx, p, errs = page(br, origin, fx="high")
    p.goto(f"{origin}/mind/")
    wait_ready(p)
    p.wait_for_timeout(4000)
    bad = []
    for _ in range(6):
        bad += p.evaluate("""() => { const top = document.getElementById('top').getBoundingClientRect().bottom,
            bot = document.getElementById('bottom').getBoundingClientRect().top;
          return [...document.querySelectorAll('#labels .lbl:not(.note)')].filter((e) => !e.hidden && +e.style.opacity > 0.03)
            .map((e) => e.getBoundingClientRect()).filter((r) => r.top + r.height / 2 < top || r.top + r.height / 2 > bot)
            .map((r) => Math.round(r.top) + ' vs ' + Math.round(top)); }""")
        p.mouse.move(195, 500)
        p.mouse.down()
        p.mouse.move(195 + 40, 420, steps=4)
        p.mouse.up()
        p.wait_for_timeout(500)
    shown = p.evaluate("document.querySelectorAll('#labels .lbl:not(.note):not([hidden])').length")
    check("f. Mind: no cluster label under the top HUD or the bottom stats while orbiting", not bad and shown > 0, (bad[:4], shown))
    ctx.close()


def test_datacity_tiers(br, origin):
    """the Data City's budget per tier: phone-high (the phone-safe preset: <= 95 calls / 250k tris, heap <= 60 MB, full detail) and ultra (the full city)"""
    for name, (q, calls, tris, far_calls) in DATACITY_TIERS.items():
        ctx, p, errs = page(br, origin, fx="high")
        p.goto(f"{origin}/datacity/{q}&nolite=1")
        p.wait_for_function("window.__city && window.__city.ready", timeout=180000)
        cdp = ctx.new_cdp_session(p)
        cdp.send("Performance.enable")
        worst = {"calls": 0, "triangles": 0}
        for focus in (None, "(() => { const d = window.__app.L.districts.slice().sort((a, b) => b.n - a.n)[0]; window.__app.orbit.focus(d.cx, 0, d.cz, 45, 1.2); })()"):
            if focus:
                p.evaluate(focus)
            f0 = p.evaluate("window.__city.frames")
            p.wait_for_function(f"window.__city.frames >= {f0 + 8}", timeout=180000)
            s = p.evaluate("window.__city.stats()")
            worst = {"calls": max(worst["calls"], s["calls"]), "triangles": max(worst["triangles"], s["triangles"])}
        p.evaluate("window.__app.orbit.focus(0, 0, 0, 380, 0.9)")
        f0 = p.evaluate("window.__city.frames")
        p.wait_for_function(f"window.__city.frames >= {f0 + 12}", timeout=180000)
        far = p.evaluate("window.__city.stats()")
        heap = metrics(cdp).get("JSHeapUsedSize", 0) / 1e6
        prof = p.evaluate("window.__app.city.profile")
        ok = worst["calls"] <= calls and worst["triangles"] <= tris and far["calls"] <= far_calls and (name != "phone-high" or heap <= DATACITY_PHONE_HEAP_MB)
        check(f"e. datacity {name} ({prof}): worst {worst['calls']} calls / {calls}, {worst['triangles']} tris / {tris}, far overview {far['calls']} calls / {far_calls}, {round(heap, 1)} MB heap (budget {DATACITY_PHONE_HEAP_MB} on phone-high)", ok, (worst, far, heap, errs[:2]))
        ctx.close()


def main():
    table: list = []
    test_static()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return table
    srv, origin = serve()
    with sync_playwright() as pw:
        br = launch(pw)
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        only = [a for a in args if a in APPS] or ([] if any(a in MORE or a in ("power", "more", "tiers") for a in args) else list(APPS))
        for app in only:
            test_app(br, origin, app, table)
        if "mind" in only:
            test_mind_labels(br, origin)
        if not args or "power" in args:
            test_power(br, origin)
        if not args or "tiers" in args:
            test_datacity_tiers(br, origin)
        for app in [a for a in args if a in MORE] or (list(MORE) if not args or "more" in args else []):
            test_more(br, origin, app)
        br.close()
    srv.shutdown()
    return table


if __name__ == "__main__":
    t0 = time.time()
    tab = main()
    if "--table" in sys.argv and tab:
        print("\n| app | three.js | draw calls | triangles | geometries | textures | programs | pixel ratio | JS heap MB | layouts/frame | frames measured |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in tab:
            print(f"| {r['app']} | {'yes' if r['three'] else 'no'} | {r['calls'] if r['three'] else '-'} | {r['triangles'] if r['three'] else '-'} | "
                  f"{r['geometries'] if r['three'] else '-'} | {r['textures'] if r['three'] else '-'} | {r['programs'] if r['three'] else '-'} | "
                  f"{r['pixelRatio'] if r['three'] else '-'} | {r['heap_mb']} | {r['layouts_per_frame']} | {r['frames_measured']} |")
    if "--json" in sys.argv and tab:
        print(json.dumps(tab))
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
