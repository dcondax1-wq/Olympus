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
# the perf budget per app (390 x 844, HD, SwiftShader): draw calls and triangles per frame (three.js renderer.info), the JS
# heap, layouts per frame (one at most: DOM writes batched, never a read after a write in the frame loop). Measured on
# 2026-11-03 with ~25% headroom; docs/OLYMPUS_DESIGN.md has the table.
BUDGET = {
    "datacity": (120, 700_000), "mind": (30, 20_000), "tree": (0, 0), "oracle": (170, 10_000), "odeon": (20, 40_000),
    "fates": (24, 30_000), "hermes": (0, 0), "prometheus": (110, 5_000), "tyche": (200, 40_000),
}
HEAP_MB, LAYOUTS_PER_FRAME = 40, 1.25   # 1.25: room for the day-sprint HUDs (Odeon 1.11 under load)

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
          all(x in js for x in ("sfx: function (name)", "window.OLYMPUS_QUIET", "'sfx.js?v=s1'", "k.play(name)")) and "O.sfx('rankup')" in arena and "O && O.sfx" in arena)
    check("a. the kit: olympus.js reads and writes 'jfx' (Jarvis's key), caps the pixel ratio, pauses on a hidden tab",
          "KEY = 'jfx'" in js and "level === 'off' ? 1 : l ? 1.5 : 2" in js and "visibilityState" in js)
    jarvis = read(os.path.join(WEB, "jarvis", "index.html"))
    check("a. Jarvis keeps its 3D level in the same 'jfx' key with the same four levels",
          "g('jfx')" in jarvis and "rawSet('jfx', level)" in jarvis and "['ultra', 'high', 'low', 'off']" in jarvis)
    bad = [p for p in (r"color-mix\(", r":has\(", r"\(\?<[=!]", r"\.at\(", r"\?\.", r"\?\?") if re.search(p, js + css)]
    check("a. the kit is Safari 16 safe (no color-mix, :has, lookbehind, .at(), and ES5-only syntax in the classic script)", not bad, bad)
    check("a. the kit: Jarvis's fonts, the type scale, 44 px taps, safe areas, the orb's 80 x 160, dvh with a vh fallback, reduced motion",
          "../jarvis/orbitron.woff2" in css and "--oly-t-label" in css and "--oly-tap: 44px" in css
          and all(f"safe-area-inset-{e}" in css for e in ("top", "right", "bottom", "left")) and "--oly-orb-w: 80px; --oly-orb-h: 160px" in css
          and "--oly-vh: 100vh" in css and "@supports (height: 100dvh)" in css and "prefers-reduced-motion: reduce" in css)
    check("a. the veil never takes a tap", re.search(r"\.oly-veil \{[^}]*pointer-events: none", css))
    for app, (_, entry, _) in APPS.items():
        html = read(os.path.join(WEB, app, "index.html"))
        i_css, i_js = html.find("../olympus/olympus.css"), html.find(f'../olympus/olympus.js?v=o2" data-app="{app}"')
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
        if top in APPS or top in ("jarvis", "olympus"):
            q = p.lstrip("/")
            if q.endswith("/"):
                q += "index.html"
            return os.path.join(WEB, *q.split("/"))
        return os.path.join(WEB, "__missing__")


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-precise-memory-info"],
                              **({"executable_path": exe} if exe else {}))


def page(br, origin, fx=None, reduced=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                         reduced_motion="reduce" if reduced else "no-preference")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    init = COUNT_DRAWS
    init += f"try {{ localStorage.setItem('jfx', {json.dumps(fx)}); }} catch (e) {{}}" if fx else "try { localStorage.removeItem('jfx'); } catch (e) {}"
    ctx.add_init_script(init)
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    return ctx, p, errs


def wait_ready(p, ms=40000):
    try:
        p.wait_for_function("() => window.OLYMPUS && OLYMPUS.state() === 'ready'", timeout=ms)
        p.wait_for_function("() => !document.querySelector('.oly-veil')", timeout=3000)
        return True
    except Exception:
        return False


def metrics(cdp):
    return {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}


def test_app(br, origin, app, table):
    q, entry, qbtn = APPS[app]
    url = f"{origin}/{app}/{q}"
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
    check(f"b. {app}: jfx=high -> data-fx=high, the HD look, <= 2 pixels per CSS px (dpr 3 phone)",
          st["fx"] == "high" and st["lite"] == "0" and 1.5 < ratio <= 2.01, (st["fx"], st["lite"], ratio))
    check(f"e. {app}: no sideways scroll at 390 x 844", st["sx"] <= 0 and st["bx"] <= 0, (st["sx"], st["bx"]))
    # perf: layouts per frame over 2 s, the heap, renderer.info
    cdp = ctx.new_cdp_session(p)
    cdp.send("Performance.enable")
    m0, f0 = metrics(cdp), p.evaluate("window.__frames")
    p.wait_for_timeout(2000)
    m1, f1 = metrics(cdp), p.evaluate("window.__frames")
    frames = max(1, f1 - f0)
    lpf = (m1.get("LayoutCount", 0) - m0.get("LayoutCount", 0)) / frames
    spf = (m1.get("RecalcStyleCount", 0) - m0.get("RecalcStyleCount", 0)) / frames
    heap = m1.get("JSHeapUsedSize", 0) / 1e6
    s = p.evaluate("OLYMPUS.stats()")
    row = {"app": app, "three": s.get("three"), "calls": s.get("calls"), "triangles": s.get("triangles"), "points": s.get("points"),
           "geometries": s.get("geometries"), "textures": s.get("textures"), "programs": s.get("programs"),
           "pixelRatio": s.get("pixelRatio"), "heap_mb": round(heap, 1), "layouts_per_frame": round(lpf, 2), "styles_per_frame": round(spf, 2),
           "fps_headless": round(frames / 2, 1)}
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
        only = [a for a in sys.argv[1:] if a in APPS] or list(APPS)
        for app in only:
            test_app(br, origin, app, table)
        if "mind" in only:
            test_mind_labels(br, origin)
        br.close()
    srv.shutdown()
    return table


if __name__ == "__main__":
    t0 = time.time()
    tab = main()
    if "--table" in sys.argv and tab:
        print("\n| app | three.js | draw calls | triangles | geometries | textures | programs | pixel ratio | JS heap MB | layouts/frame | fps (headless) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in tab:
            print(f"| {r['app']} | {'yes' if r['three'] else 'no'} | {r['calls'] if r['three'] else '-'} | {r['triangles'] if r['three'] else '-'} | "
                  f"{r['geometries'] if r['three'] else '-'} | {r['textures'] if r['three'] else '-'} | {r['programs'] if r['three'] else '-'} | "
                  f"{r['pixelRatio'] if r['three'] else '-'} | {r['heap_mb']} | {r['layouts_per_frame']} | {r['fps_headless']} |")
    if "--json" in sys.argv and tab:
        print(json.dumps(tab))
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
