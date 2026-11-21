"""The OLYMPUS render core (tools/web_public/olympus/render.js + materials.js + three-addons/, docs/OLYMPUS_RENDER.md).

  a. static: the vendored addons are three r160 (the same as jarvis/three.module.min.js) and import only '../../jarvis/
     three.module.min.js' or each other; render.js / materials.js import only relative paths; no external URL anywhere
  b. the pipeline builds in Chromium (WebGL2 through SwiftShader) on every tier, with the pass budget per tier:
     ultra / high = scene + bloom + finish (3, 4x MSAA, HDR), low = scene + finish with FXAA (2, no bloom), off = 1 (direct);
     pixel ratio <= 2 on high (<= 1.5 on low, 1 when off), up to 3 on ultra (perf v2: Ultra 4K = the full device ratio, and over 2x the scene
     buffer is not multisampled: FXAA instead); the frame is not black; no console error; no request off the site
  c. the tiers switch live: setQuality(), and OLYMPUS.setFx() (Jarvis's 'jfx' key) when the app did not force a level;
     prefers-reduced-motion with no choice starts on low
  d. slow frames step the quality down (ultra -> high -> low), never stored in 'jfx'
  e. the hidden tab: no WebGL draw call while document.hidden, drawing again once visible
  f. every material factory compiles (marble, metal x3, glass, glass + transmission, neon, fresnelRim, nebula, starfield, beam)
  g. Jarvis's home backdrop (jarvis/backdrop.js) runs on the core (3 passes at high), hides the flat 2D layers, and draws
     nothing while an app is open
  h. the portal jump (jarvis/portal.js): opening an app plays the warp over the loading frame, it ends by itself, a tap
     skips it, reduced motion gets the 0.2 s fade; no page error
    python -X utf8 -m tests.test_olympus_render
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time

from tests import browser_kit as BK  # noqa: E402  (load-aware limits, shared launch)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.test_olympus_kit import COUNT_DRAWS, HIDE, launch, serve  # noqa: E402  (the kit's server and browser)

WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
ADDONS = os.path.join(KIT, "three-addons")
LAB = "/olympus/render-lab.html"
# tier -> (passes, pass names, MSAA samples, bloom, fxaa, max pixel ratio)
TIERS = {
    "ultra": (3, ["scene", "bloom", "finish"], 4, True, False, 3),      # perf v2: up to the device ratio (3 here); over 2x: MSAA 0 + FXAA (below)
    "high": (3, ["scene", "bloom", "finish"], 4, True, False, 2),
    "low": (2, ["scene", "finish"], 0, False, True, 1.5),
    "off": (1, ["direct"], 0, False, False, 1),
}
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def code_only(src):
    """the code without whole-line // comments and /* */ blocks (three's GLTFLoader explains resource paths with an example URL in a comment)"""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("//"))


def test_static():
    three = read(os.path.join(WEB, "jarvis", "three.module.min.js"))
    rev = re.search(r'const \w+="(\d+)"', three)
    check("a. jarvis/three.module.min.js is r160", rev and rev.group(1) == "160", rev and rev.group(1))
    pkg = read(os.path.join(ADDONS, "VERSION")).strip()
    check("a. the vendored addons are three 0.160.0 (the same version)", pkg == "three@0.160.0", pkg)
    bad = []
    for f in sorted(glob.glob(os.path.join(ADDONS, "*.js"))):
        for spec in re.findall(r"from\s+'([^']+)'", code_only(read(f))):
            if spec != "../../jarvis/three.module.min.js" and not re.fullmatch(r"\./\w+\.js", spec):
                bad.append((os.path.basename(f), spec))
    check("a. every addon imports only ../../jarvis/three.module.min.js or a sibling", not bad, bad)
    for name in ("render.js", "materials.js"):
        specs = re.findall(r"from\s+'([^']+)'", read(os.path.join(KIT, name)))
        check(f"a. {name} imports only site-relative paths", specs and all(s.startswith(".") for s in specs), specs)
    urls = [f for f in glob.glob(os.path.join(KIT, "**", "*.*"), recursive=True)
            if f.endswith((".js", ".html")) and re.search(r"(?:import|from|src=|href=)[^\n]{0,8}['\"]https?://", code_only(read(f)))]
    check("a. no external URL is loaded by the kit (no CDN)", not urls, urls)
    build = read(os.path.join(ROOT, "tools", "build_web_dashboard.py"))
    check("a. the site build publishes the app folders' subfolders (olympus/three-addons/)",
          "shutil.copytree(os.path.join(src_dir, name), os.path.join(out, app, name), dirs_exist_ok=True)" in build)
    for f in ("render.js", "materials.js"):
        src = read(os.path.join(KIT, f))
        check(f"a. {f}: no localStorage write (the owner's choice is the kit's)", "localStorage" not in src)


def lab(br, origin, query="", fx=None, reduced=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                         reduced_motion="reduce" if reduced else "no-preference")
    off_site: list = []

    def route(r):
        if r.request.url.startswith(origin):
            return r.continue_()
        off_site.append(r.request.url)
        return r.abort()
    ctx.route("**/*", route)
    init = COUNT_DRAWS + (f"try {{ localStorage.setItem('jfx', {json.dumps(fx)}); }} catch (e) {{}}" if fx
                          else "try { localStorage.removeItem('jfx'); } catch (e) {}")
    ctx.add_init_script(init)
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
    p.goto(origin + LAB + query)
    p.wait_for_function("() => window.__lab && (window.__lab.rc || window.__lab.flat) && OLYMPUS.state() === 'ready'", timeout=180000)
    p.wait_for_timeout(700)
    return ctx, p, errs, off_site


LIT = """() => { const c = document.getElementById('lab'); __lab.rc.render(); const g = document.createElement('canvas'); g.width = 39; g.height = 84;
  const x = g.getContext('2d'); x.drawImage(c, 0, 0, 39, 84); const d = x.getImageData(0, 0, 39, 84).data; let s = 0;
  for (let i = 0; i < d.length; i += 4) s += d[i] + d[i + 1] + d[i + 2]; return s / (d.length / 4) / 3; }"""


def test_tiers(br, origin):
    for tier, (n, names, samples, bloom, fxaa, dpr) in TIERS.items():
        ctx, p, errs, off = lab(br, origin, f"?q={tier}")
        s = p.evaluate("() => __lab.rc.stats()")
        check(f"b. {tier}: {n} pass(es) {names}", s["passes"] == n and s["names"] == names, s)
        if tier == "ultra" and s["dpr"] > 2.05:          # perf v2: over 2 pixels per CSS pixel the scene buffer is not multisampled (FXAA in the finish)
            samples, fxaa = 0, True
        check(f"b. {tier}: MSAA {samples}, bloom {bloom}, FXAA {fxaa}", (s["samples"], s["bloom"], s["fxaa"]) == (samples, bloom, fxaa), s)
        check(f"b. {tier}: pixel ratio {s['dpr']} <= {dpr}", 0 < s["dpr"] <= dpr, s)
        if tier != "off":
            check(f"b. {tier}: HDR (half-float) buffers and a PMREM environment", s["hdr"] and s["env"] == "night", s)
        lum = p.evaluate(LIT)
        check(f"b. {tier}: the frame is lit (mean {lum:.0f}/255)", lum > 12, lum)
        check(f"b. {tier}: no console error, nothing requested off the site", not errs and not off, (errs, off))
        ctx.close()


def test_switch(br, origin):
    ctx, p, errs, _ = lab(br, origin, "?gpu=1", fx="high")
    # a touch before each draw: the kit's idle frame cap (30 fps after 4 s without input) would skip a second draw within 33 ms
    got = p.evaluate("""() => { const rc = __lab.rc, out = [rc.quality(), rc.stats().passes], touch = () => window.dispatchEvent(new Event('pointermove'));
      rc.setQuality('low'); touch(); out.push(rc.quality(), rc.stats().passes, rc.render());
      rc.setQuality('off'); touch(); out.push(rc.stats().passes, rc.render());
      OLYMPUS.setFx('ultra'); touch(); out.push(rc.quality(), rc.stats().passes, rc.stats().samples, rc.render(), rc.stats().dpr); return out; }""")
    # Ultra 4K on this 3x phone renders at the full 3x: no MSAA buffer over 2x (FXAA), 4 samples at 2x or less
    msaa = 0 if got[-1] > 2.05 else 4
    check("c. setQuality high -> low -> off and OLYMPUS.setFx('ultra') rebuild the pipeline (3 -> 2 -> 1 -> 3 passes; ultra over 2x: FXAA, no MSAA)",
          got[:-1] == ["high", 3, "low", 2, True, 1, True, "ultra", 3, msaa, True], got)
    check("c. no console error while switching tiers", not errs, errs)
    ctx.close()
    ctx, p, errs, _ = lab(br, origin, "?gpu=1", reduced=True)
    check("c. prefers-reduced-motion with no choice starts on low", p.evaluate("() => __lab.rc.quality()") == "low")
    ctx.close()


def test_policy(br, origin):
    """i. the tier policy: software GL (SwiftShader here) is held to LITE; ?q= forces a tier; ?gpu=1 lifts the software cap; rc.forced / rc.software say which."""
    probe = """() => { const rc = __lab.rc; return { q: rc.quality(), passes: rc.stats().passes, forced: rc.forced, software: rc.software }; }"""
    out = {}
    for name, query, fx in (("kit high", "", "high"), ("q=ultra", "?q=ultra", "low"), ("gpu=1", "?gpu=1", "high")):
        ctx, p, errs, _ = lab(br, origin, query, fx=fx)
        out[name] = p.evaluate(probe)
        out[name]["errs"] = errs
        ctx.close()
    check("i. software GL with the kit at high is held to LITE (2 passes); rc.software is true",
          out["kit high"]["q"] == "low" and out["kit high"]["passes"] == 2 and out["kit high"]["software"] is True and out["kit high"]["forced"] is None, out["kit high"])
    check("i. ?q=ultra forces the tier over the kit and over the software cap (3 passes), rc.forced = 'ultra'",
          out["q=ultra"]["q"] == "ultra" and out["q=ultra"]["passes"] == 3 and out["q=ultra"]["forced"] == "ultra", out["q=ultra"])
    check("i. ?gpu=1 lifts the software cap (the kit's high, 3 passes)", out["gpu=1"]["q"] == "high" and out["gpu=1"]["passes"] == 3 and out["gpu=1"]["software"] is False, out["gpu=1"])


def test_adapt(br, origin):
    ctx, p, errs, _ = lab(br, origin, "?still=1", fx=None)
    got = p.evaluate("""async () => {
      const { createRenderer } = await import('./render.js'), T = await import('../jarvis/three.module.min.js');
      const L = window.__lab, seen = [];
      L.rc.dispose();
      // an empty scene: the 48 ms busy loop is the whole cost of a frame (SwiftShader draws the lab at ~8 fps). 48, not 32: once the kit is idle
      // (4 s without a touch) it caps frames at 30 fps, and a 33 ms frame is then full rate, not slow; the frames are slow for the page's own
      // JavaScript, so the core steps the tier (a smaller buffer would not help: perf v2)
      const rc = createRenderer({ canvas: document.getElementById('lab'), scene: new T.Scene(), camera: new T.PerspectiveCamera(),
        quality: 'ultra', adapt: 'always', onQuality: (q) => seen.push(q), maxDpr: 0.25 });
      rc.start(() => { const t = performance.now(); while (performance.now() - t < 48) {} });
      for (let i = 0; i < 60 && seen.length < 2; i++) await new Promise((r) => setTimeout(r, 500));   // <= 30 s
      await new Promise((r) => setTimeout(r, 4000));                                                 // and it stays on low
      rc.stop();
      return { seen, now: rc.quality(), stored: localStorage.getItem('jfx') };
    }""")
    check("d. slow frames step ultra -> high -> low, never below, never stored", got["seen"][:2] == ["high", "low"]
          and got["now"] == "low" and got["stored"] is None, got)
    ctx.close()


def jarvis(br, origin, reduced=False):
    """Jarvis's home on the real site layout (no network: its live cards stay offline), with jfx = high"""
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                         reduced_motion="reduce" if reduced else "no-preference")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script(COUNT_DRAWS + "try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(origin + "/jarvis/")
    return ctx, p, errs


def test_jarvis(br, origin):
    ctx, p, errs = jarvis(br, origin)
    try:
        p.wait_for_function("() => window.__jarvisBackdrop && window.__jarvisBackdrop.state !== 'loading' && window.__jarvisBackdrop.frames > 2",
                            timeout=180000)
    except Exception:
        pass
    b = p.evaluate("() => Object.assign({}, window.__jarvisBackdrop, { stats: null, bg3d: document.documentElement.dataset.bg3d,"
                   " stars: getComputedStyle(document.getElementById('stars')).display })")
    # QA 2026-11-21: the sky starts at the low tier (2 passes: its first frames cost least) and earns the chosen tier (high: 3 passes)
    # after 30 fast frames; a slow machine (this software GL) keeps low, or holds a still frame
    check("g. Jarvis home: the 3D backdrop is up on the render core (the low tier's 2 passes at start / on a slow machine, 3 at high) and the flat 2D layers step aside",
          b.get("state") == "on" and (b.get("quality"), b.get("passes")) in (("low", 2), ("high", 3)) and b.get("bg3d") == "on" and b.get("stars") == "none", b)
    p.evaluate("() => window.jarvisPortal.warm()")
    p.evaluate("() => document.querySelector('[data-app=\"oracle\"]').click()")
    s0 = p.evaluate("() => Object.assign({}, window.__jarvisPortal, { overlay: !!document.querySelector('.jportal') })")
    check("h. opening an app plays the portal warp over it (overlay up, the app's frame already loading underneath)",
          s0["mode"] == "warp" and s0["active"] and s0["overlay"] and s0["app"] == "oracle"
          and p.evaluate("() => !!document.querySelector('iframe[src*=\"oracle\"]')"), s0)
    f0 = p.evaluate("() => window.__jarvisBackdrop.frames")
    p.wait_for_timeout(2200)
    s1 = p.evaluate("() => Object.assign({}, window.__jarvisPortal, { overlay: !!document.querySelector('.jportal') })")
    check("h. the warp ends by itself (~0.8 s) and leaves nothing behind", not s1["active"] and not s1["overlay"] and 0 < s1["ms"] < BK.limit_ms(2500, "warp ends"), s1)
    f1 = p.evaluate("() => window.__jarvisBackdrop.frames")
    check("g. the backdrop draws nothing while an app is open", f1 - f0 <= 1, (f0, f1))
    p.evaluate("() => window.jarvisPortal.jump({ id: 'mind', name: 'Mind', color: '#5eead4' })")
    p.locator(".jportal").dispatch_event("pointerdown")
    check("h. a tap skips the warp at once", p.evaluate("() => !window.__jarvisPortal.active && !document.querySelector('.jportal')"))
    check("h. no page error from the backdrop or the portal", not errs, errs[:4])
    ctx.close()
    ctx, p, errs = jarvis(br, origin, reduced=True)
    p.wait_for_function("() => !!window.jarvisPortal", timeout=120000)
    mode = p.evaluate("() => window.jarvisPortal.jump({ id: 'oracle', name: 'Oracle', color: '#7fe9ff' })")
    try:                                               # a 0.2 s fade: wait for it to be gone (a loaded machine runs its timers late), not a fixed 600 ms
        p.wait_for_function("() => !document.querySelector('.jportal-fade, .jportal')", timeout=int(BK.limit_ms(5000, "fade gone")))
    except Exception:
        pass
    check("h. reduced motion: a 0.2 s fade instead of the warp, gone after", mode == "fade"
          and p.evaluate("() => !document.querySelector('.jportal-fade, .jportal')"), mode)
    ctx.close()


# live GPU buffers of the page's own WebGL2 contexts: framebuffers, multisampled renderbuffers, textures (net of deletes)
GPU_COUNT = """(() => {
  if (window.top !== window) return;
  const P = WebGL2RenderingContext.prototype, live = { fb: new Set(), msaa: new Set(), tex: new Set() };
  window.__gpu = () => ({ fb: live.fb.size, msaa: live.msaa.size, tex: live.tex.size });
  const wrap = (name, fn) => { const f = P[name]; P[name] = function () { const r = f.apply(this, arguments); fn.call(this, r, arguments); return r; }; };
  wrap('createFramebuffer', (r) => live.fb.add(r)); wrap('deleteFramebuffer', (_, a) => live.fb.delete(a[0]));
  wrap('createTexture', (r) => live.tex.add(r)); wrap('deleteTexture', (_, a) => live.tex.delete(a[0]));
  wrap('renderbufferStorageMultisample', function (_, a) { const rb = this.getParameter(this.RENDERBUFFER_BINDING); if (a[1] > 0 && rb) live.msaa.add(rb); });
  wrap('deleteRenderbuffer', (_, a) => live.msaa.delete(a[0]));
})();"""
GPU = "() => window.__gpu()"
CLICK = "(id) => document.querySelector('[data-app=\"' + id + '\"]').click()"


def jarvis_gpu(br, origin, fx):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script(GPU_COUNT + f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(origin + "/jarvis/")
    p.wait_for_function("() => window.__jarvisBackdrop && __jarvisBackdrop.frames > 3", timeout=240000)
    if fx == "high":                                   # the core's composer comes up after the backdrop on a slow machine: wait for its 2 MSAA buffers
        settle(p, 2)
    p.wait_for_timeout(int(BK.limit_ms(2500, "gpu settle")))
    return ctx, p, errs


def settle(p, msaa):
    """back on the home: wait (the machine may be slow) until the core's multisampled buffers are back, then let the loop run"""
    try:
        p.wait_for_function("(n) => window.__gpu().msaa >= n", arg=msaa, timeout=60000)
    except Exception:
        pass
    p.wait_for_timeout(int(BK.limit_ms(1500, "gpu settle")))


def test_gpu(br, origin):
    """Memory on iPhone terms: home -> open an app -> back. The covered home releases its render targets (not only its loop),
    coming back restores them, and one MSAA composer is alive at a time."""
    ctx, p, errs = jarvis_gpu(br, origin, "high")
    home = p.evaluate(GPU)
    bd = p.evaluate("() => __jarvisBackdrop.stats()")
    check("i. home at high: ONE multisampled composer (the core's: 2 MSAA buffers), the backdrop has none (FXAA instead)",
          bd["samples"] == 0 and bd["fxaa"] and home["msaa"] == 2, (bd, home))
    p.evaluate(CLICK, "oracle")
    p.wait_for_timeout(int(BK.limit_ms(2500, "gpu settle")))
    app = p.evaluate(GPU)
    asleep = p.evaluate("() => __jarvisBackdrop.asleep")
    check("i. app open: the home's backdrop and core release their buffers (0 MSAA, fewer framebuffers and textures than at home)",
          asleep is True and app["msaa"] == 0 and app["fb"] < home["fb"] and app["tex"] < home["tex"], (home, app, asleep))
    f0 = p.evaluate("() => __jarvisBackdrop.frames")
    p.wait_for_timeout(int(BK.limit_ms(800, "gpu settle")))
    check("i. app open: no home frame is drawn", p.evaluate("() => __jarvisBackdrop.frames") == f0)
    p.evaluate(CLICK, "home")
    settle(p, home["msaa"])
    back = p.evaluate(GPU)
    f1 = p.evaluate("() => __jarvisBackdrop.frames")
    p.wait_for_timeout(int(BK.limit_ms(800, "gpu settle")))
    f2 = p.evaluate("() => __jarvisBackdrop.frames")
    check("i. back home: the same buffers are restored (framebuffers, MSAA, textures as before) and it draws again",
          back["msaa"] == home["msaa"] and back["fb"] == home["fb"] and abs(back["tex"] - home["tex"]) <= 2 and f2 > f1
          and p.evaluate("() => __jarvisBackdrop.asleep") is False, (home, back, f1, f2))
    for _ in range(3):                                 # three more round trips: still no growth
        p.evaluate(CLICK, "oracle")
        p.wait_for_timeout(int(BK.limit_ms(1200, "gpu settle")))
        p.evaluate(CLICK, "home")
        settle(p, home["msaa"])
    p.wait_for_timeout(int(BK.limit_ms(1500, "gpu settle")))
    again = p.evaluate(GPU)
    print("   live GPU buffers (framebuffers / MSAA renderbuffers / textures): home", home, "| app open", app, "| back", back,
          "| after 4 trips", again, flush=True)
    check("i. four round trips: live buffers do not grow", again["fb"] == home["fb"] and again["msaa"] == home["msaa"]
          and again["tex"] <= home["tex"] + 2, (home, again))
    check("i. no page error through the trips", not errs, errs[:3])
    ctx.close()
    ctx, p, errs = jarvis_gpu(br, origin, "low")
    bd = p.evaluate("() => __jarvisBackdrop.stats()")
    g = p.evaluate(GPU)
    check("i. low: no bloom (2 passes), no MSAA anywhere, backdrop pixel ratio <= 1.25",
          bd["names"] == ["scene", "finish"] and not bd["bloom"] and bd["dpr"] <= 1.25 and g["msaa"] == 0, (bd, g))
    ctx.close()


def test_hidden(br, origin):
    ctx, p, errs, _ = lab(br, origin, "?q=high")
    p.evaluate(HIDE, True)
    p.evaluate("window.__draws = 0")
    p.wait_for_timeout(1200)
    hidden = p.evaluate("window.__draws")
    p.evaluate(HIDE, False)
    p.wait_for_timeout(1200)
    shown = p.evaluate("window.__draws")
    check("e. hidden tab: no WebGL draw; drawing again once visible", hidden == 0 and shown > 0, (hidden, shown))
    ctx.close()


def test_materials(br, origin):
    ctx, p, errs, _ = lab(br, origin, "?q=high&still=1")
    got = p.evaluate("""async () => {
      const T = await import('../jarvis/three.module.min.js'), M = await import('./materials.js');
      const L = window.__lab, g = new T.Group(), out = [];
      const add = (name, obj) => { const o = obj.isMaterial ? new T.Mesh(new T.SphereGeometry(0.3, 16, 12), obj) : obj; g.add(o); out.push(name); };
      add('marble', M.marble({ gold: true })); for (const k of ['gold', 'chrome', 'gunmetal']) add(k, M.metal({ kind: k }));
      add('glass', M.glass()); add('glass-transmission', M.glass({ transmission: true })); add('neon', M.neon());
      add('rim', M.fresnelRim(new T.MeshStandardMaterial(), { color: '#ff0' })); add('nebula', M.nebula()); add('stars', M.starfield({ count: 200 }));
      add('beam', M.energyBeam()); g.position.set(0, 2, 4); L.scene.add(g);
      g.traverse((o) => { if (o.update) o.update(1, 1); });
      L.rc.render();
      const gl = L.rc.renderer.getContext(), progs = L.rc.renderer.info.programs.map((x) => x.name);
      return { out, ok: gl.getError() === 0, progs: progs.length, colors: JSON.stringify(M.colors()) };
    }""")
    check("f. every material compiles and draws (no GL error)", got["ok"] and len(got["out"]) == 11, got)
    check("f. no console error from the materials", not errs, errs)
    ctx.close()


def main():
    test_static()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return
    srv, origin = serve()
    with sync_playwright() as pw:
        br = launch(pw)
        test_tiers(br, origin)
        test_switch(br, origin)
        test_hidden(br, origin)
        test_materials(br, origin)
        test_policy(br, origin)
        test_adapt(br, origin)
        test_jarvis(br, origin)
        test_gpu(br, origin)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
