"""Brain 3D: each bot's brain as a 3D kit module (day-arenas 2026-11-21, DESIGN; spec research/handoff/2026-11-21/brain3d/SPEC.md).
  a. static: olympus/brain3d.js (window.Brain3D, classic script), brain3d.css (OLYMPUS NIGHT, a fixed ratio), brain3d-scene.js (an ES module that
     imports only the local three.js + olympus/three-addons, never a CDN), the lab page, the API note
  b. Chromium, phone 390 x 844 (B3_NO_BROWSER=1 skips): the 2D first paint is there at once (the steps in order + the schematic), the 3D
     mounts (a canvas, mode '3d', 10 regions + 8 ring nodes for Zlarior, 3 lobes for ATLAS), update() moves the list + the caption,
     a tap on a list row and on a region in the canvas both fire 'tap' with the id, reduced motion = a still frame (no synapses, no loop),
     no WebGL keeps the 2D, dispose() leaves nothing, no page error, layout shift under 0.02
    python -X utf8 -m tests.test_brain3d
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p):
    return open(os.path.join(WEB, *p), encoding="utf-8").read()


def static():
    js, css, sc, lab = read("olympus", "brain3d.js"), read("olympus", "brain3d.css"), read("olympus", "brain3d-scene.js"), read("olympus", "brain3d-lab.html")
    check("a. brain3d.js: window.Brain3D with mount / update / on('tap') / dispose, the scene only by dynamic import (three.js never in the first paint)",
          "window.Brain3D = { mount: mount" in js and all(k in js for k in ("update: function", "on: function", "dispose: function", "import(BASE + 'brain3d-scene.js?v="))
          and "three.module" not in js)
    imps = re.findall(r"""^import .* from '([^']+)';""", sc, re.M)
    check("a. brain3d-scene.js imports only the local three.js + olympus/three-addons", imps and all(i == "../jarvis/three.module.min.js" or i.startswith("./three-addons/") for i in imps)
          and "http" not in "".join(imps), imps)
    check("a. the 3D is capped (30 fps, pixel ratio <= 2), paused off screen / hidden tab, reduced motion = a still frame, context loss -> 2D",
          "now - last < 31" in sc and "Math.min(window.devicePixelRatio || 1, low ? 1.5 : 2)" in sc.replace("  ", " ") and "IntersectionObserver" in sc
          and "document.hidden" in sc and "prefers-reduced-motion: reduce" in sc and "webglcontextlost" in sc and "scene.onLost" in js, "caps")
    bad = [c for c in re.findall(r"#[0-9a-fA-F]{6}\b", css + sc) if c.lower() in ("#231d16", "#2a2112", "#3a2d14", "#1f1a12")]
    check("a. OLYMPUS NIGHT colours (violet glow, gold accent, mint passed, red blocked), no brown", all(k in css for k in ("#9d59ee", "#f1c14b", "#77db89", "#ef4444", "#3e255e"))
          and not bad and "aspect-ratio: var(--b3-ratio" in css, bad)
    check("a. the lab page: Zlarior's 10 steps + ATLAS's 3 lobes over one ring, on brain3d.css + brain3d.js",
          'href="brain3d.css?v=' in lab and 'src="brain3d.js?v=' in lab and "layout: 'lobes'" in lab and "['done', 'Done / journal']" in lab)
    api = os.path.join(ROOT, "research", "handoff", "2026-11-21", "brain3d", "API.md")
    check("a. the API note for the NQ team (research/handoff/2026-11-21/brain3d/API.md)", os.path.exists(api)
          and all(k in open(api, encoding="utf-8").read() for k in ("Brain3D.mount", ".update(", "'tap'", ".dispose()", "stageStates", "ringStates")))


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass


NO_GL = """(() => { const g = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (t, o) {
  return /webgl/i.test(String(t)) ? null : g.call(this, t, o); }; })();"""
CLS = """window.__cls = 0; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__cls += e.value; (window.__clsE = window.__clsE || []).push([Math.round(e.startTime), e.value, (e.sources || []).map(x => x.node && (x.node.id || x.node.className || x.node.nodeName) + '' )]); } })
  .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}"""


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/olympus/brain3d-lab.html"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

            def page(**kw):
                init = kw.pop("init", "")
                ctx = b.new_context(viewport={"width": 390, "height": 844}, **kw)
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"GL Driver|GPU stall|WebGL", m.text) else None)
                p.add_init_script(CLS + init)
                return ctx, p, errs

            def wait3d(p, which="zl", ms=15000):
                try:
                    p.wait_for_function(f"window.__lab && __lab.{which}.mode === '3d' && document.querySelector('#{which} .b3-stage.b3-on')", timeout=ms)
                    return True
                except Exception:  # noqa: BLE001
                    return False

            # ---- the normal phone
            ctx, p, errs = page()
            p.goto(url, wait_until="domcontentloaded")
            p.wait_for_function("window.__lab", timeout=8000)
            first = p.evaluate("""() => ({ li: document.querySelectorAll('#zl .b3-list li').length, svg: !!document.querySelector('#zl svg.b3-2d'),
              cur: (document.querySelector('#zl .b3-list li[data-state=current] .b3-n') || {}).textContent || '', mode: __lab.zl.mode,
              ring: document.querySelectorAll('#zl .b3-ring span').length, now: (document.querySelector('#zl .b3-now span') || {}).textContent || '' })""")
            check("b. the 2D first paint at once: 10 steps in order, the schematic, the ring chips, the caption, step 4 'Sweep' current",
                  first["li"] == 10 and first["svg"] and first["ring"] == 8 and first["cur"].startswith("Sweep") and "0.5 ATR" in first["now"], first)
            ok = wait3d(p)
            st = p.evaluate("__lab.zl.stats()") if ok else None
            check("b. the 3D mounts (a canvas, mode '3d', 10 regions, 8 ring nodes, synapses moving, pixel ratio <= 2)", ok and st and st["regions"] == 10 and st["ring"] == 8
                  and st["synapses"] > 0 and st["dpr"] <= 2 and p.locator("#zl canvas.b3-gl").count() == 1, st)
            if ok:
                f0 = p.evaluate("__lab.zl.stats().frames")
                p.wait_for_timeout(1000)
                f1 = p.evaluate("__lab.zl.stats().frames")
                check("b. it animates (about 30 fps, capped)", 5 <= f1 - f0 <= 36, (f0, f1))
            p.click("#zlNext")
            up = p.evaluate("""() => ({ cur: (document.querySelector('#zl .b3-list li[data-state=current] .b3-n') || {}).textContent || '',
              passed: document.querySelectorAll('#zl .b3-list li[data-state=passed]').length, now: document.querySelector('#zl .b3-now span').textContent })""")
            check("b. update(): Next step moves the list (Inducement current, 4 passed) and the caption", up["cur"].startswith("Inducement") and up["passed"] == 4
                  and "pull into" in up["now"], up)
            p.click("#zlBlock")
            check("b. update(): a block turns the step red", p.evaluate("document.querySelector('#zl .b3-list li[data-state=blocked]') !== null"))
            p.locator("#zl .b3-list li").nth(2).click()
            check("b. a tap on a list row fires 'tap' with the step id", p.evaluate("JSON.stringify(window.__lastTap)") == '["map","stage"]', p.evaluate("JSON.stringify(window.__lastTap)"))
            if ok:
                p.evaluate("document.getElementById('zl').scrollIntoView({block: 'start'})")
                p.wait_for_timeout(300)
                hit = None
                for sid in ("sweep", "cisd", "trade", "map", "window", "limit"):
                    w = p.evaluate(f"__lab.zl.where('{sid}')")
                    box = p.locator("#zl canvas.b3-gl").bounding_box()
                    if not w or not w["front"]:
                        continue
                    p.evaluate("window.__lastTap = null")
                    p.mouse.click(box["x"] + w["x"], box["y"] + w["y"])
                    p.wait_for_timeout(120)
                    got = p.evaluate("window.__lastTap")
                    if got and got[1] == "stage":
                        hit = (sid, got[0])
                        break
                check("b. a tap on a region in the 3D fires 'tap' with that region's id", hit and hit[0] == hit[1], hit)
                w = p.evaluate("__lab.zl.where('dd', 'ring')")
                check("b. where(): ring nodes sit under the brain, inside the canvas", w and 0 < w["x"] < 390 and w["y"] > p.evaluate("__lab.zl.where('data').y"), w)
            p.evaluate("document.getElementById('at').scrollIntoView()")
            okA = wait3d(p, "at")
            sa = p.evaluate("__lab.at.stats()") if okA else None
            check("b. ATLAS: 3 lobes (EMA, MACD, S/R) over one 6-node ring, in 3D after scrolling to it", okA and sa["regions"] == 3 and sa["ring"] == 6
                  and p.locator("#at .b3-list li").count() == 3, sa)
            p.click("#atArm")
            check("b. ATLAS update(): Arm MACD makes it current", p.evaluate("document.querySelector('#at .b3-list li[data-state=current] .b3-n').textContent").startswith("MACD"))
            cls = p.evaluate("window.__cls")
            check("b. no layout shift while the 3D arrives (CLS < 0.02)", cls < 0.02, (cls, p.evaluate("window.__clsE")))
            p.evaluate("__lab.zl.dispose(); __lab.at.dispose()")
            gone = p.evaluate("""() => ({ c: document.querySelectorAll('canvas').length, n: document.querySelectorAll('.b3').length, m: __lab.zl.stats() })""")
            check("b. dispose(): no canvas, no nodes, no scene left", gone["c"] == 0 and gone["n"] == 0 and gone["m"] is None, gone)
            check("b. no page error (normal phone)", not errs, errs[:4])
            ctx.close()

            # ---- reduced motion: a still frame
            ctx, p, errs = page(reduced_motion="reduce")
            p.goto(url, wait_until="domcontentloaded")
            okR = wait3d(p)
            if okR:
                s1 = p.evaluate("__lab.zl.stats()")
                p.wait_for_timeout(800)
                s2 = p.evaluate("__lab.zl.stats()")
                p.click("#zlNext")
                p.wait_for_timeout(300)
                s3 = p.evaluate("__lab.zl.stats()")
                check("b. reduced motion: a still frame (no synapses, no running loop), redrawn on a change", s1["reduce"] and s1["synapses"] == 0 and not s2["running"]
                      and s2["frames"] == s1["frames"] and s3["frames"] > s2["frames"], (s1, s2, s3))
            else:
                check("b. reduced motion: the 3D still mounts", False, p.evaluate("__lab && __lab.zl.mode"))
            check("b. no page error (reduced motion)", not errs, errs[:4])
            ctx.close()

            # ---- no WebGL: the 2D stays
            ctx, p, errs = page(init=NO_GL)
            p.goto(url, wait_until="load")
            p.wait_for_timeout(2500)
            r = p.evaluate("""() => ({ mode: __lab.zl.mode, c: document.querySelectorAll('canvas.b3-gl').length, li: document.querySelectorAll('#zl .b3-list li').length,
              svg: getComputedStyle(document.querySelector('#zl svg.b3-2d')).opacity })""")
            check("b. no WebGL: the 2D brain + the steps stay (no canvas, mode '2d')", r["mode"] == "2d" and r["c"] == 0 and r["li"] == 10 and r["svg"] == "1", r)
            check("b. no page error (no WebGL)", not errs, errs[:4])
            ctx.close()
            b.close()
    finally:
        srv.shutdown()


def main():
    static()
    if os.environ.get("B3_NO_BROWSER") != "1":
        browser()
    n = len(RES)
    print(json.dumps({"passed": sum(RES), "total": n}))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
