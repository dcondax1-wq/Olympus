"""The real-phone budget pass (QA round 6, docs/QA_ROUND6.md): what the site costs a mid-range iPhone, and that it survives one.

  a. static (no browser): tools/phone_budget.py arithmetic; per-page eager-load budgets on the source pages (blocking KB / files before the
     first paint, three.js never eager on the hero pages that use olympus/lazy3d.js); the contracts in olympus.js (LITE auto-detection,
     the WebGL guard), render.js (context loss / restore, GPU buffers freed on hide), sfx.js (format fallback), lazy3d.js
  b. LITE auto-detection in Chromium: deviceMemory 2 GB / Save-Data -> data-fx=low + data-oly-auto, the owner's stored choice wins; on LITE
     the NQ page never requests three.js and keeps its 2D columns; on HD three.js arrives after the first paint and the 3D mounts
  c. WebGL context loss (WEBGL_lose_context): the render core's page (render-lab) and a bare three.js page (NQ) never go black: the
     still / backdrop shows while lost, data-oly-gl says so, and after restore the core rebuilds (restores >= 1) and draws again
  d. audio: the first tap unlocks (context running); a host with no .m4a (Safari-style format order) falls back to .ogg after one failed
     request; with no audio files at all the synth plays, at most 2 failed requests, no console error, no page error
  e. Jarvis app switching: 10 switches between 3D apps, then home: no AudioContext / WebGL context / canvas of a closed app is still
     alive after GC (WeakRef registry across frames), one app frame at most, JS heap growth bounded
    python -X utf8 -m tests.test_phone_budget            (--static: only a.)
Browser parts run under `flock -w 2400 /tmp/olympus_browser.lock` (one browser on the machine).
"""
from __future__ import annotations

import http.server
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
WEB = os.path.join(ROOT, "tools", "web_public")
import phone_budget as PB  # noqa: E402

RES: list = []
LAZY = {"nq": ("nqscene.js", "nq3d"), "mint": ("mintscene.js", "mint3d"), "helios": ("sunload.js", "helios-sun"), "aegis": ("shieldload.js", "aegis-shield"),
        "chrysos": ("towerload.js", "chrysos-tower"), "symposium": ("hallload.js", "sym-hall"), "ergasterion": ("floorload.js", "erg-floor")}
# blocking bytes (raw, before gzip) / files before the first paint, per page, on the source tree; root and jarvis are the lead's shells:
# held at today's size so they never grow (root = 528 kB of inline HTML, see the report)
BLOCK_KB, BLOCK_N = 300, 9
SHELL = {"root": (760, 6), "jarvis": (420, 3)}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    raw = {"fcp": 1000, "nav": {"t": 2048, "d": 4096, "e": 300},
           "res": [{"n": "http://x/a.js?v=1", "t": 1024, "d": 3072, "e": 900}, {"n": "http://x/jarvis/three.module.min.js", "t": 10240, "d": 20480, "e": 2000},
                   {"n": "http://x/b.css", "t": 512, "d": 512, "e": 950}], "gl": 2, "gl_page": 1, "heap": 1048576 * 3, "lcp": 1200, "ready": 1500}
    r = PB.summarize(raw)
    check("a. summarize: bytes / requests before the first paint, JS parsed, three.js, contexts",
          r["kb_fcp"] == 3.5 and r["req_fcp"] == 3 and r["req"] == 4 and r["js_kb"] == 23.0 and r["three"] and r["gl"] == 2 and r["gl_page"] == 1
          and r["ready_ms"] == 1500 and r["heap_mb"] == 3.0, r)
    check("a. over_budget names each broken line; a page without a first paint fails",
          PB.over_budget({"fcp_ms": 9000, "kb_fcp": 10, "req_fcp": 3, "js_kb": 10, "gl": 3}) == ["fcp_ms 9000 > 6000", "gl 3 > 1"]
          and "no first paint" in PB.over_budget({"fcp_ms": 0}), PB.over_budget({"fcp_ms": 9000, "gl": 3}))
    t = PB.table_lines([("nq", r), ("x", {"error": "boom"})])
    check("a. the table has a header, a row per page and the error row", len(t) == 4 and t[2].startswith("| nq | 1000 |") and "error: boom" in t[3], t)
    check("a. page_url: root, a folder, a single html file",
          PB.page_url("http://h", "root") == "http://h/" + PB.QUERY and PB.page_url("http://h", "nq") == "http://h/nq/" + PB.QUERY
          and PB.page_url("http://h", "olympus-live.html") == "http://h/olympus-live.html" + PB.QUERY)

    rows = {p: PB.static_row(WEB, p) for p in PB.PAGES if not p.endswith(".html")}
    bad = []
    for p, row in rows.items():
        kb, n = SHELL.get(p, (BLOCK_KB, BLOCK_N))
        if "error" in row or row["block_kb"] > kb or row["block_n"] > n:
            bad.append((p, row.get("block_kb"), row.get("block_n")))
    check(f"a. every page's render-blocking files stay within budget (<= {BLOCK_KB} kB raw / {BLOCK_N} files; root / jarvis held at today's size)", not bad, bad)
    check("a. Polis: the POLIS libraries are deferred (the page + <= 6 blocking files, was 13: ~380 kB of script before the first paint)",
          rows["polis"]["block_n"] <= 7 and rows["polis"]["block_kb"] < 160, rows["polis"])
    eager3 = [p for p in LAZY if rows[p]["three"]]
    check("a. three.js is never in the eager graph of the lazy 3D pages (" + ", ".join(LAZY) + ")", not eager3, eager3)
    tags = []
    for p, (src, ev) in LAZY.items():
        html = read(os.path.join(WEB, p, "index.html"))
        m = re.search(r'<script src="\.\./olympus/lazy3d\.js[^"]*" data-src="' + re.escape(src) + r'[^"]*" data-skip="lite" data-event="' + re.escape(ev) + r'" defer></script>', html)
        if not m or ('<script type="module" src="' + src) in html:
            tags.append(p)
    check("a. each lazy page loads its 3D module through lazy3d.js (data-src, data-skip=lite, data-event = the module's own ready event), never a module tag", not tags, tags)
    for p, (src, ev) in LAZY.items():
        mod = read(os.path.join(WEB, p, src))
        if ("'" + ev + "'") not in mod:
            tags.append(p + ": " + src + " does not fire " + ev)
    check("a. the data-event of each page is the event its module really fires", not tags, tags)

    oly, rnd, sfx, lz = (read(os.path.join(WEB, "olympus", f)) for f in ("olympus.js", "render.js", "sfx.js", "lazy3d.js"))
    check("a. olympus.js: LITE auto-detection from Save-Data, prefers-reduced-data, a 2g line, deviceMemory, cores (never cores alone on Apple); never stored",
          all(k in oly for k in ("saveData === true", "prefers-reduced-data: reduce", "effectiveType", "deviceMemory", "hardwareConcurrency", "!apple && hc && hc <= 2",
                                 "data-oly-auto", "auto: function"))
          and "var level = stored() || fallback();" in oly and "set(KEY, autoWhy" not in oly)
    check("a. olympus.js: every WebGL canvas gets the guard (getContext wrapped once), the loss is restorable (preventDefault), a still / backdrop shows, data-oly-gl",
          all(k in oly for k in ("P.getContext = wrap", "webglcontextlost", "e.preventDefault()", "oly-gl-still", "webglcontextrestored", "data-oly-gl", "toDataURL('image/jpeg'", "radial-gradient(")))
    check("a. render.js: a lost context draws nothing, a restore rebuilds environment + composer and draws; GPU buffers freed after 20 s hidden and on pagehide",
          all(k in rnd for k in ("webglcontextlost', onLost", "webglcontextrestored', onRestored", "environment(); build(); size(true);", "HIDE_MS = 20000",
                                 "'pagehide', onPageHide", "'pageshow', onPageShow", "removeEventListener('webglcontextlost', onLost)", "restores"))
          and "if (dead || asleep || lost || pageHidden()) return false;" in rnd)
    check("a. sfx.js: a missing format falls back to the other, an HTML answer is never decoded, both missing = synth for the session (no more requests)",
          all(k in sfx for k in ("smpDead", "!smpDead", "text\\/html", "if (!fmtUsed) smpDead = true;", "dead: smpDead")))
    check("a. lazy3d.js: no probe context (WebGL checked without one), after the first paint, never while hidden, skip on LITE (loads on HD)",
          all(k in lz for k in ("WebGLRenderingContext", "requestAnimationFrame", "D.hidden", "O.lite()", "O.onFx", "import(url)", "IntersectionObserver")))


# ------------------------------------------------------------------------------------------------ the browser
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve():
    class Srv(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass
    srv = Srv(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def new_page(br, origin, init=None, fx=None, block_off_site=True):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
    if fx:
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    for s in init or []:
        ctx.add_init_script(s)
    if block_off_site:
        ctx.route(re.compile(r"^(?!" + re.escape(origin) + ").*"), lambda r: r.abort())
    p = ctx.new_page()
    p.__errs = []
    p.on("pageerror", lambda e: p.__errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: p.__errs.append(m.text) if m.type == "error" else None)
    return ctx, p


def requested(p, part):
    return p.evaluate("(s) => performance.getEntriesByType('resource').filter((r) => r.name.indexOf(s) >= 0).map((r) => [r.name, r.startTime])", part)


MEM2 = "Object.defineProperty(Navigator.prototype, 'deviceMemory', { get: () => 2, configurable: true });"
SAVE = "Object.defineProperty(Navigator.prototype, 'connection', { get: () => ({ saveData: true, effectiveType: '4g', addEventListener() {} }), configurable: true });"


def test_auto_lite(br, origin):
    rows = {}
    for name, init, fx in (("plain", [], None), ("memory", [MEM2], None), ("savedata", [SAVE], None), ("owner", [MEM2], "high")):
        ctx, p = new_page(br, origin, init, fx)
        p.goto(origin + "/nq/?welcome=0&intro=0")
        p.wait_for_function("window.NQ && window.NQ.ready()", timeout=30000)
        p.wait_for_timeout(1500)
        rows[name] = p.evaluate("[document.documentElement.dataset.fx, document.documentElement.getAttribute('data-oly-auto') || '', OLYMPUS.auto(), OLYMPUS.lite(), OLYMPUS.chosen()]")
        rows[name].append(len(requested(p, "three.module.min.js")))
        rows[name].append(p.evaluate("!document.getElementById('fallback') || getComputedStyle(document.getElementById('fallback')).visibility !== 'hidden'"))
        ctx.close()
    check("b. no low-end signal on this machine: HD (data-fx=high, no auto)", rows["plain"][:3] == ["high", "", ""], rows["plain"])
    check("b. deviceMemory 2 GB: LITE by itself (data-fx=low, data-oly-auto=memory), not stored as the owner's choice",
          rows["memory"][:5] == ["low", "memory", "memory", True, False], rows["memory"])
    check("b. Save-Data: LITE by itself (save-data)", rows["savedata"][:3] == ["low", "save-data", "save-data"], rows["savedata"])
    check("b. the owner's stored choice wins over the signals (jfx=high on a 2 GB device: HD, no auto)", rows["owner"][:4] == ["high", "", "", False], rows["owner"])
    check("b. on auto-LITE the NQ page never requests three.js (~650 kB of script) and keeps its 2D columns",
          rows["memory"][5] == 0 and rows["savedata"][5] == 0 and rows["memory"][6] is True, rows)


def test_lazy_hd(br, origin):
    ctx, p = new_page(br, origin, [], "high")
    p.goto(origin + "/nq/?welcome=0&intro=0&gpu=1")
    p.wait_for_function("window.NQ && window.NQ.ready() && window.OLYMPUS_LAZY3D && OLYMPUS_LAZY3D.list().some((x) => x.ok)", timeout=45000)
    p.wait_for_function("!!window.NQ3D", timeout=20000)
    fcp = p.evaluate("(performance.getEntriesByType('paint').find((e) => e.name === 'first-contentful-paint') || {}).startTime || 0")
    three = requested(p, "three.module.min.js")
    ok3d = p.wait_for_function("window.NQ.S.scene === 'webgl' || window.NQ.S.scene === '2d'", timeout=20000) and p.evaluate("window.NQ.S.scene")
    check("b. HD: three.js is requested once, after the first paint (lazy3d), and the 3D columns mount",
          len(three) == 1 and fcp > 0 and three[0][1] >= fcp and ok3d == "webgl", [fcp, three, ok3d])
    gl = p.evaluate("OLYMPUS.gl()")
    check("b. HD: one live WebGL context on the page, at most 2 made (nqscene's own probe + its renderer; lazy3d makes none)", gl["live"] == 1 and gl["made"] <= 2, gl)
    check("b. HD: no console error, no page error (a missing optional data file in the source tree is the browser's own network line)",
          not [e for e in p.__errs if "Failed to load resource" not in e], p.__errs)
    ctx.close()


CENTER_DARK = """(sel) => new Promise((res) => {
  const c = document.querySelector(sel); const r = c.getBoundingClientRect(); res([r.left + r.width / 2, r.top + r.height / 2, r.width, r.height]);
})"""


def center_rgb(p, xy):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(p.screenshot())).convert("RGB")
    k = im.width / 390.0
    box = (int((xy[0] - 40) * k), int((xy[1] - 40) * k), int((xy[0] + 40) * k), int((xy[1] + 40) * k))
    px = [im.getpixel((x, y)) for x in range(box[0], box[2], 4) for y in range(box[1], box[3], 4)]
    return [round(sum(c[i] for c in px) / len(px)) for i in range(3)]


def test_context_loss(br, origin, shots=None):
    # the render core's own page: a scene drawn through createRenderer
    ctx, p = new_page(br, origin, [], None)
    p.goto(origin + "/olympus/render-lab.html?q=low")
    p.wait_for_function("window.__lab && window.__lab.rc && window.__lab.rc.stats().calls > 0", timeout=45000)
    p.wait_for_timeout(2500)                                   # past 1.5 s of frames: the still is taken
    xy = p.evaluate(CENTER_DARK, "canvas")
    before = center_rgb(p, xy)
    p.evaluate("window.__lx = window.__lab.renderer.getContext().getExtension('WEBGL_lose_context'); window.__lx.loseContext()")
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'lost'", timeout=10000)
    p.wait_for_timeout(400)
    lost = center_rgb(p, xy)
    bg = p.evaluate("(() => { const o = document.querySelector('.oly-gl-still'); return o ? getComputedStyle(o).backgroundImage : ''; })()")
    if shots:
        p.screenshot(path=os.path.join(shots, "ctx_lost.jpg"), type="jpeg", quality=70)
    p.evaluate("window.__lx.restoreContext()")
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'ok' && window.__lab.rc.stats().restores >= 1", timeout=15000)
    p.wait_for_timeout(1500)
    st = p.evaluate("(() => { const s = window.__lab.rc.stats(); return [s.lost, s.restores, s.calls, s.passes, s.env]; })()")
    after = center_rgb(p, xy)
    if shots:
        p.screenshot(path=os.path.join(shots, "ctx_restored.jpg"), type="jpeg", quality=70)
    dark = lambda c: max(c) < 14 or min(c) > 240               # black, or the browser's own white "lost" placeholder
    check("c. render core, context lost: the canvas shows the still / AGORA backdrop (never black), html[data-oly-gl=lost]",
          not dark(lost) and "url(\"data:image/jpeg" in bg and "radial-gradient" in bg, [before, lost, bg[:80]])
    check("c. render core, restored: the core rebuilt (restores >= 1) and draws again, the picture is back (not black)",
          st[0] is False and st[1] >= 1 and st[2] > 0 and not dark(after), [st, after])
    check("c. render core: no console error, no page error through the loss and the restore",
          not [e for e in p.__errs if "Context Lost" not in e and "context lost" not in e.lower()], p.__errs)
    ctx.close()

    # a bare three.js page (NQ's columns): the kit's guard alone
    ctx, p = new_page(br, origin, [], "high")
    p.goto(origin + "/nq/?welcome=0&intro=0&gpu=1")
    p.wait_for_function("window.NQ && window.NQ.S.scene === 'webgl' && window.NQ3D.frames() > 5", timeout=60000)
    sel = "#scene3d canvas"
    p.evaluate("(s) => { window.__lx = document.querySelector(s).getContext('webgl2').getExtension('WEBGL_lose_context'); window.__lx.loseContext(); }", sel)
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'lost'", timeout=10000)
    bg = p.evaluate("(() => { const o = document.querySelector('.oly-gl-still'); return o ? getComputedStyle(o).backgroundImage : ''; })()")
    xy = p.evaluate(CENTER_DARK, sel)
    lost = center_rgb(p, xy)
    if shots:
        p.screenshot(path=os.path.join(shots, "ctx_lost_nq.jpg"), type="jpeg", quality=70)
    p.evaluate("window.__lx.restoreContext()")
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'ok'", timeout=15000)
    gone = p.evaluate("!document.querySelector('.oly-gl-still') && document.querySelector('#scene3d canvas').style.visibility !== 'hidden'")
    check("c. bare three.js page (NQ): the guard's overlay shows the backdrop while lost (not black, not the browser's white placeholder) and goes on restore",
          ("radial-gradient" in bg or "url(" in bg) and max(lost) >= 14 and min(lost) <= 240 and gone, [bg[:80], lost, gone])
    ctx.close()


SAFARI_FMT = """(() => { const f = HTMLMediaElement.prototype.canPlayType; HTMLMediaElement.prototype.canPlayType = function (t) {
  return /ogg/.test(String(t)) ? '' : f.call(this, t); }; })();"""


def test_audio(br, origin):
    out = {}
    for name, block in (("no-m4a", r"\.m4a(\?|$)"), ("none", r"\.(m4a|ogg)(\?|$)")):
        ctx, p = new_page(br, origin, [SAFARI_FMT], None)
        audio = []
        ctx.on("request", lambda r: audio.append(r.url) if re.search(r"/assets/audio/.*\.(m4a|ogg)", r.url) else None)
        p.route(re.compile(r".*/assets/audio/.*" + block), lambda r: r.fulfill(status=404, body="not here", content_type="text/plain"))
        p.goto(origin + "/nq/?welcome=0&intro=0")
        p.wait_for_function("window.NQ && window.NQ.ready() && !!window.OLYMPUS_SFX", timeout=30000)
        st0 = p.evaluate("OLYMPUS_SFX.state().ctxState")
        p.touchscreen.tap(195, 300)
        p.wait_for_timeout(300)
        p.mouse.click(195, 320)
        p.wait_for_function("OLYMPUS_SFX.state().unlocked && OLYMPUS_SFX.state().ctxState === 'running'", timeout=10000)
        p.wait_for_function("(() => { const s = OLYMPUS_SFX.samples(); return s.pending.length === 0 && (s.loaded.length > 0 || s.dead); })()", timeout=20000)
        sm = p.evaluate("OLYMPUS_SFX.samples()")
        played = p.evaluate("OLYMPUS_SFX.play('tap')")
        p.wait_for_timeout(500)
        out[name] = {"before_tap": st0, "samples": {k: sm[k] for k in ("fmt", "loaded", "failed", "dead")}, "played": played,
                     "m4a": len([u for u in audio if ".m4a" in u]), "ogg": len([u for u in audio if ".ogg" in u]),
                     "errors": [e for e in p.__errs if "Failed to load resource" not in e]}
        ctx.close()
    a, b = out["no-m4a"], out["none"]
    check("d. before the first tap nothing sounds (no running context); the tap unlocks it (running)", a["before_tap"] in ("none", "suspended") and b["before_tap"] in ("none", "suspended"), out)
    check("d. a host without .m4a (Safari's format order): falls back to .ogg, the files load, at most 2 failed .m4a requests",
          a["samples"]["fmt"] == "ogg" and "ui" in a["samples"]["loaded"] and not a["samples"]["dead"] and a["m4a"] <= 2, a)
    check("d. no audio files at all: the synth plays (play() true), the recorded layer stops trying (dead), at most 2 + 2 failed requests",
          b["played"] is True and b["samples"]["dead"] is True and b["m4a"] <= 2 and b["ogg"] <= 2, b)
    check("d. no console error and no page error in either case (the failed loads are the browser's own network lines)", not a["errors"] and not b["errors"], out)


REG = """(() => {
  const top = (() => { try { return window.top.__pbReg ? window.top : window; } catch (e) { return window; } })();
  // add() runs in the TOP window's realm: the arrays and WeakRefs it makes belong to the top window (an array or WeakRef made in the app's
  // frame and kept by the top window would keep that frame's whole realm, and every canvas in it, alive: the very leak this measures)
  if (window === window.top) window.__pbReg = { ac: [], gl: [], cv: [], add(kind, x, path) { this[kind].push([new WeakRef(x), String(path)]); } };
  const reg = () => { try { return window.top.__pbReg; } catch (e) { return null; } };
  const A = window.AudioContext || window.webkitAudioContext;
  if (A) { const W = function (...a) { const c = new A(...a); const r = reg(); if (r) r.add('ac', c, location.pathname); return c; }; W.prototype = A.prototype; window.AudioContext = W; window.webkitAudioContext = W; }
  const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (k, ...rest) {
    const c = g.call(this, k, ...rest);
    if (c && /webgl/.test(String(k)) && !this.__pbr) { this.__pbr = 1; const r = reg(); if (r) { r.add('gl', c, location.pathname); r.add('cv', this, location.pathname); } }
    return c;
  };
})();"""
ALIVE = """(() => { const r = window.__pbReg, n = (xs) => xs.filter((x) => x[0].deref()).map((x) => x[1]);
  return { ac: n(r.ac), gl: n(r.gl), cv: n(r.cv), made: [r.ac.length, r.gl.length], frames: document.querySelectorAll('iframe').length,
    heap: performance.memory ? performance.memory.usedJSHeapSize : 0 }; })()"""


def gc(p, n=4):
    for _ in range(n):
        p.evaluate("window.gc && window.gc()")
        p.wait_for_timeout(250)


def test_switch_memory(br, origin):
    ctx, p = new_page(br, origin, [REG, "try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); } catch (e) {}"], "high")
    p.goto(origin + "/jarvis/?welcome=0&intro=0")
    p.wait_for_function("window.__jarvis && document.documentElement.dataset.ready", timeout=60000)
    apps = ["helios", "symposium", "nq", "aegis", "polis", "mint", "chrysos", "ergasterion", "colosseum", "pythia"]
    heaps = []
    for i, a in enumerate(apps):
        p.evaluate("(a) => window.__jarvis.show(a)", a)
        p.wait_for_function("(a) => { const f = document.querySelector('#v-' + a + ' iframe'); return f && f.contentDocument && f.contentDocument.readyState === 'complete'; }", arg=a, timeout=60000)
        p.wait_for_timeout(1500)
        p.mouse.click(195, 460)                                 # a tap inside the app: its sound engine unlocks (an AudioContext per frame)
        p.wait_for_timeout(1200)
        if i in (1, len(apps) - 1):
            gc(p)
            heaps.append(p.evaluate(ALIVE)["heap"])
    p.evaluate("window.__jarvis.show('home')")
    p.wait_for_timeout(1500)
    gc(p, 8)
    alive = p.evaluate(ALIVE)
    kept = "/" + apps[-1] + "/"                                # Jarvis keeps the last app loaded for a quick return (by design)
    stray = [x for x in alive["ac"] + alive["cv"] if not x.startswith("/jarvis/") and x != kept]
    grow = (heaps[-1] - heaps[0]) / 1048576.0 if len(heaps) == 2 else None
    check(f"e. 10 app switches in Jarvis: at most one app frame kept (now {alive['frames']})", alive["frames"] <= 1, alive)
    check("e. after the switches + GC no AudioContext / WebGL canvas of a closed app is still alive (made: %d audio contexts, %d WebGL contexts)" % tuple(alive["made"]),
          not stray, stray)
    check("e. JS heap growth from switch 2 to switch 10 stays under 25 MB (%.1f MB)" % (grow or -1), grow is not None and grow < 25, heaps)
    check("e. no page error while switching", not [e for e in p.__errs if e.startswith("pageerror")], p.__errs[:6])
    ctx.close()
    return {"alive": alive, "heap_growth_mb": grow}


def main():
    test_static()
    if "--static" in sys.argv:
        return
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    srv, origin = serve()
    shots = None
    for a in sys.argv:
        if a.startswith("--shots="):
            shots = a.split("=", 1)[1]
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    with sync_playwright() as pw:
        br = BK.launch(pw, args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-precise-memory-info", "--js-flags=--expose-gc",
                                 "--autoplay-policy=user-gesture-required"])
        for name, fn in (("lite", lambda: test_auto_lite(br, origin)), ("lazy", lambda: test_lazy_hd(br, origin)),
                         ("ctx", lambda: test_context_loss(br, origin, shots)), ("audio", lambda: test_audio(br, origin)),
                         ("switch", lambda: print(test_switch_memory(br, origin)))):
            if only and name not in only:
                continue
            try:
                fn()
            except Exception as e:  # a section that cannot run is a failure with its reason, the others still run
                check(f"{name}: the section ran", False, repr(e)[:400])
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
