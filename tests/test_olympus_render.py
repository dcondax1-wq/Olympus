"""The OLYMPUS render core (tools/web_public/olympus/render.js + materials.js + three-addons/, docs/OLYMPUS_RENDER.md).

  a. static: the vendored addons are three r160 (the same as jarvis/three.module.min.js) and import only '../../jarvis/
     three.module.min.js' or each other; render.js / materials.js import only relative paths; no external URL anywhere
  b. the pipeline builds in Chromium (WebGL2 through SwiftShader) on every tier, with the pass budget per tier:
     ultra / high = scene + bloom + finish (3, 4x MSAA, HDR), low = scene + finish with FXAA (2, no bloom), off = 1 (direct);
     pixel ratio <= 2 (<= 1.5 on low, 1 when off); the frame is not black; no console error; no request off the site
  c. the tiers switch live: setQuality(), and OLYMPUS.setFx() (Jarvis's 'jfx' key) when the app did not force a level;
     prefers-reduced-motion with no choice starts on low
  d. slow frames step the quality down (ultra -> high -> low), never stored in 'jfx'
  e. the hidden tab: no WebGL draw call while document.hidden, drawing again once visible
  f. every material factory compiles (marble, metal x3, glass, glass + transmission, neon, fresnelRim, nebula, starfield, beam)
    python -X utf8 -m tests.test_olympus_render
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.test_olympus_kit import COUNT_DRAWS, HIDE, launch, serve  # noqa: E402  (the kit's server and browser)

WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
ADDONS = os.path.join(KIT, "three-addons")
LAB = "/olympus/render-lab.html"
# tier -> (passes, pass names, MSAA samples, bloom, fxaa, max pixel ratio)
TIERS = {
    "ultra": (3, ["scene", "bloom", "finish"], 4, True, False, 2),
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


def test_static():
    three = read(os.path.join(WEB, "jarvis", "three.module.min.js"))
    rev = re.search(r'const \w+="(\d+)"', three)
    check("a. jarvis/three.module.min.js is r160", rev and rev.group(1) == "160", rev and rev.group(1))
    pkg = read(os.path.join(ADDONS, "VERSION")).strip()
    check("a. the vendored addons are three 0.160.0 (the same version)", pkg == "three@0.160.0", pkg)
    bad = []
    for f in sorted(glob.glob(os.path.join(ADDONS, "*.js"))):
        for spec in re.findall(r"from\s+'([^']+)'", read(f)):
            if spec != "../../jarvis/three.module.min.js" and not re.fullmatch(r"\./\w+\.js", spec):
                bad.append((os.path.basename(f), spec))
    check("a. every addon imports only ../../jarvis/three.module.min.js or a sibling", not bad, bad)
    for name in ("render.js", "materials.js"):
        specs = re.findall(r"from\s+'([^']+)'", read(os.path.join(KIT, name)))
        check(f"a. {name} imports only site-relative paths", specs and all(s.startswith(".") for s in specs), specs)
    urls = [f for f in glob.glob(os.path.join(KIT, "**", "*.*"), recursive=True)
            if f.endswith((".js", ".html")) and re.search(r"(?:import|from|src=|href=)[^\n]{0,8}['\"]https?://", read(f))]
    check("a. no external URL is loaded by the kit (no CDN)", not urls, urls)
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
    p.wait_for_function("() => window.__lab && (window.__lab.rc || window.__lab.flat) && OLYMPUS.state() === 'ready'", timeout=40000)
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
        check(f"b. {tier}: MSAA {samples}, bloom {bloom}, FXAA {fxaa}", (s["samples"], s["bloom"], s["fxaa"]) == (samples, bloom, fxaa), s)
        check(f"b. {tier}: pixel ratio {s['dpr']} <= {dpr}", 0 < s["dpr"] <= dpr, s)
        if tier != "off":
            check(f"b. {tier}: HDR (half-float) buffers and a PMREM environment", s["hdr"] and s["env"] == "night", s)
        lum = p.evaluate(LIT)
        check(f"b. {tier}: the frame is lit (mean {lum:.0f}/255)", lum > 12, lum)
        check(f"b. {tier}: no console error, nothing requested off the site", not errs and not off, (errs, off))
        ctx.close()


def test_switch(br, origin):
    ctx, p, errs, _ = lab(br, origin, "", fx="high")
    got = p.evaluate("""() => { const rc = __lab.rc, out = [rc.quality(), rc.stats().passes];
      rc.setQuality('low'); out.push(rc.quality(), rc.stats().passes, rc.render());
      rc.setQuality('off'); out.push(rc.stats().passes, rc.render());
      OLYMPUS.setFx('ultra'); out.push(rc.quality(), rc.stats().passes, rc.stats().samples, rc.render()); return out; }""")
    check("c. setQuality high -> low -> off and OLYMPUS.setFx('ultra') rebuild the pipeline (3 -> 2 -> 1 -> 3 passes)",
          got == ["high", 3, "low", 2, True, 1, True, "ultra", 3, 4, True], got)
    check("c. no console error while switching tiers", not errs, errs)
    ctx.close()
    ctx, p, errs, _ = lab(br, origin, "", reduced=True)
    check("c. prefers-reduced-motion with no choice starts on low", p.evaluate("() => __lab.rc.quality()") == "low")
    ctx.close()


def test_adapt(br, origin):
    ctx, p, errs, _ = lab(br, origin, "?still=1", fx=None)
    got = p.evaluate("""async () => {
      const { createRenderer } = await import('./render.js'), T = await import('../jarvis/three.module.min.js');
      const L = window.__lab, seen = [];
      L.rc.dispose();
      // an empty scene: the 32 ms busy loop is the whole cost of a frame (SwiftShader draws the lab at ~8 fps)
      const rc = createRenderer({ canvas: document.getElementById('lab'), scene: new T.Scene(), camera: new T.PerspectiveCamera(),
        quality: 'ultra', adapt: 'always', onQuality: (q) => seen.push(q), maxDpr: 0.25 });
      rc.start(() => { const t = performance.now(); while (performance.now() - t < 32) {} });
      for (let i = 0; i < 60 && seen.length < 2; i++) await new Promise((r) => setTimeout(r, 500));   // <= 30 s
      await new Promise((r) => setTimeout(r, 4000));                                                 // and it stays on low
      rc.stop();
      return { seen, now: rc.quality(), stored: localStorage.getItem('jfx') };
    }""")
    check("d. slow frames step ultra -> high -> low, never below, never stored", got["seen"][:2] == ["high", "low"]
          and got["now"] == "low" and got["stored"] is None, got)
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
        test_adapt(br, origin)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
