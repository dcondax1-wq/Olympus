"""The Jarvis core (tools/web_public/jarvis/core-visual.js): the animated centrepiece of Jarvis mode on the owner's phone,
his violet 3D Gimbal Reactor (Three.js r160, vendored as jarvis/three.module.min.js) with a 2D HUD ring on top and a 2D
canvas core when WebGL is missing. Runs the real module in Chromium (WebGL through SwiftShader) on a local server and checks:
  a. the files: mountCore exported, own code lean, no network but the relative three import, nothing newer than iPhone
     Safari 16, three pinned (r160, MIT header, the published SHA-256)
  b. it mounts: the HUD canvas at once, then the WebGL reactor; retina backing stores, devicePixelRatio capped at 2
  c. every state renders and looks different (alert red / amber, listening turns the core red); setLevel drives the voice
     pulse; setTheme recolours; setDesign('singularity') swaps the scene; bad input is ignored
  d. destroy(): no frame after it, every listener (its own and three's) and observer removed, the element emptied
  e. it pauses while the page is hidden and while the core is off-screen, and resumes; a lost WebGL context falls back to
     the 2D core and the reactor comes back
  f. prefers-reduced-motion and effects 'off': static frames only (no loop), one new frame per state change; motion: 'always'
     opts out (the old Jarvis ignored the OS switch)
  g. slow frames step the effects down to 'low'; fast frames keep 'high'
  h. no WebGL: the 2D core draws every state, three is never fetched, no errors
  i. the demo page works at 390 px; no console errors anywhere
    python -X utf8 -m tests.test_jarvis_core                    (a local server on a temp copy; nothing else touched)
    python -X utf8 -m tests.test_jarvis_core --shots <dir>      (also saves a 390 px screenshot of each state)
"""
from __future__ import annotations

import base64
import functools
import glob
import hashlib
import http.server
import io
import os
import re
import shutil
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
MOD = os.path.join(JV, "core-visual.js")
THREE = os.path.join(JV, "three.module.min.js")
THREE_SHA256 = "PmkKx9GAsKrfCJG+o57sZD4p4tPnXJmxholRhmX2m6Y="      # three@0.160.0 build/three.module.min.js (jsDelivr = unpkg)
STATES = ["idle", "listening", "thinking", "speaking", "alert"]
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


# installed before any page script: rAF requests / runs (and fake frame times), live event listeners, observers, a
# visibility override, and (NOGL) a browser without WebGL
PROBE = r"""
(() => {
  const P = window.__p = { req: 0, run: 0, step: 0, ft: 0, live: new Set(), obs: [], hidden: false };
  const rq = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => { P.req++; return rq((ts) => { P.run++; cb(P.step ? (P.ft += P.step) : ts); }); };
  const key = new WeakMap(); let n = 0;
  const id = (o) => { if (!key.has(o)) key.set(o, ++n); return key.get(o); };
  const add = EventTarget.prototype.addEventListener, rem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (t, f, o) { if (f) P.live.add(id(this) + ':' + t + ':' + id(f)); return add.call(this, t, f, o); };
  EventTarget.prototype.removeEventListener = function (t, f, o) { if (f) P.live.delete(id(this) + ':' + t + ':' + id(f)); return rem.call(this, t, f, o); };
  for (const name of ['IntersectionObserver', 'ResizeObserver']) {
    const O = window[name];
    window[name] = class extends O {
      constructor(cb, o) { super(cb, o); this.__on = 0; this.__kind = name; P.obs.push(this); }
      observe(t, o) { this.__on++; return super.observe(t, o); }
      disconnect() { this.__on = 0; return super.disconnect(); }
    };
  }
  Object.defineProperty(Document.prototype, 'hidden', { configurable: true, get() { return P.hidden; } });
  Object.defineProperty(Document.prototype, 'visibilityState', { configurable: true, get() { return P.hidden ? 'hidden' : 'visible'; } });
  P.setHidden = (h) => { P.hidden = h; document.dispatchEvent(new Event('visibilitychange')); };
  if (window.NOGL) {
    const gc = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (k, o) { return /webgl/.test(k) ? null : gc.call(this, k, o); };
  }
})();
"""

HARNESS = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>core harness</title><link rel="icon" href="icon-192.png">
<style>html,body{margin:0;background:#05030b} #el{width:360px;margin:12px auto}</style></head>
<body><div id="el"></div>
<script type="module">import { mountCore } from './core-visual.js'; window.mountCore = mountCore; window.ready = true;</script>
</body></html>"""


def part_a():
    ok = os.path.exists(MOD)
    check("a. core-visual.js exists", ok)
    if not ok:
        return
    src = open(MOD, encoding="utf-8").read()
    size = len(src.encode("utf-8"))
    check(f"a. own code stays lean: core-visual.js {size:,} bytes (< 60 KB; three itself is vendored apart)", size < 60 * 1024, size)
    check("a. an ES module that exports mountCore(el, opts)", re.search(r"export function mountCore\s*\(\s*el\s*,", src) is not None)
    imports = re.findall(r"import\s*\(\s*['\"]([^'\"]+)['\"]", src)
    check("a. no libraries from a CDN, no network: the only import is the vendored three, relative",
          imports == ["./three.module.min.js"] and not re.search(r"^\s*import\s", src, re.M) and "http://" not in src
          and "https://" not in src and "fetch(" not in src and "XMLHttpRequest" not in src, imports)
    code = re.sub(r"/\*.*?\*/", "", re.sub(r"//[^\n]*", "", src), flags=re.S)     # comments may name what is avoided
    too_new = ["(?<=", "(?<!", "static {", "roundRect", "createConicGradient", "structuredClone", ".toSorted(", ".toReversed(",
               "Object.groupBy", ".findLast(", "ctx.reset(", "Array.fromAsync", "Promise.withResolvers"]
    hits = [t for t in too_new if t in code]
    check("a. nothing newer than iPhone Safari 16 in core-visual.js", not hits, hits)
    ok = os.path.exists(THREE)
    check("a. three.module.min.js is vendored next to it", ok)
    if ok:
        raw = open(THREE, "rb").read()
        sha = base64.b64encode(hashlib.sha256(raw).digest()).decode()
        head = raw[:200].decode("utf-8", "replace")
        check("a. three is the pinned r160 build (published SHA-256), MIT licence header kept",
              sha == THREE_SHA256 and "SPDX-License-Identifier: MIT" in head and 'const t="160"' in raw[:400].decode("utf-8", "replace"), sha)
        t = raw.decode("utf-8", "replace")
        check("a. three has no regex lookbehind or class static blocks (Safari 16)", "(?<=" not in t and "(?<!" not in t and "static{" not in t)
    demo = os.path.join(JV, "core-demo.html")
    check("a. core-demo.html exists and imports the module", os.path.exists(demo) and "from './core-visual.js'" in open(demo, encoding="utf-8").read())


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def mount(p, url, opts="{}", step=0):
    p.goto(url + "__harness.html")
    p.wait_for_function("window.ready === true", timeout=15000, polling=100)
    if step:
        p.evaluate(f"__p.step = {step}")              # fake frame times from the very first frame
    p.evaluate(f"window.core = window.mountCore(document.getElementById('el'), {opts})")


def ready3d(p):
    p.wait_for_function("core.stats().three !== 'loading'", timeout=30000, polling=100)
    return p.evaluate("core.stats().three")


def counts(p):
    return p.evaluate("[core.stats().frames, core.stats().frames3, __p.run, __p.req]")


def during(p, ms):
    a = counts(p)
    p.wait_for_timeout(ms)
    b = counts(p)
    return [y - x for x, y in zip(a, b)]


def shot_sig(p):
    """What the core shows (the WebGL canvas and the HUD together): alpha-free screenshot on the page's dark background."""
    from PIL import Image
    import numpy as np
    img = np.asarray(Image.open(io.BytesIO(p.locator(".jcore").screenshot())).convert("RGB")).astype(float)
    h, w, _ = img.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot(xx - w / 2, yy - h / 2) / (w / 2)
    lum = img.mean(axis=2)
    lit = lum > 40
    mean = img[lit].mean(axis=0) if lit.any() else np.zeros(3)
    centre = img[rr < 0.3].mean(axis=0)
    band = [float(lum[(rr >= k / 8) & (rr < (k + 1) / 8)].mean()) for k in range(8)]
    return {"r": float(mean[0]), "g": float(mean[1]), "b": float(mean[2]), "lit": float(lit.mean()), "band": band,
            "cr": float(centre[0]), "cg": float(centre[1]), "cb": float(centre[2]), "lum": float(lum.mean())}


def canvas_sig(p):
    """The 2D canvas alone (the no-WebGL core): alpha-weighted colour and ring brightness."""
    return p.evaluate("""(() => {
      const c = document.querySelector('.jcore canvas'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      const w = c.width, h = c.height; let r = 0, g = 0, b = 0, a = 0, lit = 0; const band = new Array(8).fill(0), bn = new Array(8).fill(0);
      for (let y = 0; y < h; y += 2) for (let x = 0; x < w; x += 2) {
        const i = (y * w + x) * 4, al = d[i + 3] / 255, k = Math.min(7, Math.floor(Math.hypot(x - w / 2, y - h / 2) / (w / 2) * 8));
        r += d[i] * al; g += d[i + 1] * al; b += d[i + 2] * al; a += al; if (d[i + 3] > 60) lit++; band[k] += (d[i] + d[i + 1] + d[i + 2]) * al / 765; bn[k]++;
      }
      const n = (w / 2) * (h / 2);
      return { r: r / (a || 1), g: g / (a || 1), b: b / (a || 1), lit: lit / n, band: band.map((v, k) => v / (bn[k] || 1)) };
    })()""")


def dist(s1, s2):
    t1 = (s1["r"] + s1["g"] + s1["b"]) or 1
    t2 = (s2["r"] + s2["g"] + s2["b"]) or 1
    chroma = sum(abs(s1[k] / t1 - s2[k] / t2) for k in "rgb")
    shape = sum(abs(x - y) for x, y in zip(s1["band"], s2["band"])) / (sum(s1["band"]) + sum(s2["band"]) or 1)
    return chroma + shape


def run_browser(url, shots):
    from playwright.sync_api import sync_playwright
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    errs, fetched = [], []

    def watch(p):
        p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
        p.on("request", lambda r: fetched.append(r.url))

    def harness(ctx, nogl=False):
        if nogl:
            ctx.add_init_script("window.NOGL = true;")
        ctx.add_init_script(PROBE)
        ctx.route("**/__harness.html", lambda r: r.fulfill(status=200, content_type="text/html", body=HARNESS))
        p = ctx.new_page()
        watch(p)
        return p

    with sync_playwright() as pw:
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))

        def frames_pass(n, timeout=30000):          # wait for n more reactor frames (CI GPUs are software and slow)
            f0 = p.evaluate("core.stats().frames3")
            p.wait_for_function(f"core.stats().frames3 >= {f0 + n}", timeout=timeout, polling=100)

        # ---------------------------------------------------------- b + c: the animated 3D reactor
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        p = harness(ctx)
        mount(p, url, "{size: 240, effects: 'high', adapt: false}")
        first = p.evaluate("[document.querySelectorAll('#el .jcore canvas').length, core.stats().three]")
        check("b. mounts at once: the HUD canvas is up while three loads", first[0] >= 1 and first[1] in ("loading", "on"), first)
        check("b. the WebGL reactor comes up (three r160 loaded on demand)", ready3d(p) == "on", p.evaluate("core.stats()"))
        info = p.evaluate("""(() => { const cs = document.querySelectorAll('#el .jcore canvas'), b = document.querySelector('#el .jcore').getBoundingClientRect();
            return { n: cs.length, w2: cs[cs.length - 1].width, w3: cs[0].width, css: b.width, h: b.height, keys: Object.keys(core).sort() }; })()""")
        check("b. two canvases: the WebGL reactor under the 2D HUD, square", info["n"] == 2 and abs(info["css"] - info["h"]) < 1, info)
        check("b. the handle: setState, setLevel, destroy (+ setTheme, setDesign, stats)",
              all(k in info["keys"] for k in ("setState", "setLevel", "destroy", "setTheme", "setDesign", "stats")), info["keys"])
        check("b. retina: both backing stores = CSS width x devicePixelRatio 2",
              abs(info["w2"] - round(info["css"] * 2)) <= 1 and abs(info["w3"] - round(info["css"] * 2)) <= 1, info)
        a = counts(p)
        frames_pass(4)
        b = counts(p)
        check("b. it animates (HUD and reactor frames keep coming)", b[0] - a[0] >= 4 and b[1] - a[1] >= 4, (a, b))
        for s in STATES:
            p.evaluate(f"core.setState('{s}')")
            frames_pass(4)
            sg = shot_sig(p)
            check(f"c. {s}: animates and renders (state set, a lit frame)", p.evaluate("core.stats().state") == s and sg["lit"] > 0.05,
                  (p.evaluate("core.stats().state"), round(sg["lit"], 3)))
        p.evaluate("core.setState('speaking'); window.__lv = 0; window.__f = setInterval(() => core.setLevel(window.__lv), 30)")
        p.wait_for_function("core.stats().level < 0.08", timeout=30000, polling=100)
        frames_pass(2)
        q = [p.evaluate("core.stats().level"), shot_sig(p)]
        p.evaluate("window.__lv = 1")
        p.wait_for_function("core.stats().level > 0.9", timeout=30000, polling=100)
        frames_pass(2)
        lo = [p.evaluate("core.stats().level"), shot_sig(p)]
        p.evaluate("clearInterval(window.__f)")
        check("c. setLevel drives the voice pulse (level 0 -> 1: the level follows, the core brightens)",
              q[0] < 0.1 and lo[0] > 0.85 and lo[1]["lum"] > q[1]["lum"] * 1.08, (q[0], lo[0], round(q[1]["lum"], 1), round(lo[1]["lum"], 1)))
        p.evaluate("core.setState('nonsense'); core.setLevel('x'); core.setLevel(-3); core.setLevel(9); core.setDesign('nope'); core.setTheme(null)")
        check("c. unknown states / designs and bad levels are ignored (no throw)", p.evaluate("core.stats().state") == "speaking"
              and p.evaluate("core.stats().design") == "reactor")

        # ---------------------------------------------------------- e: hidden page, off-screen
        p.evaluate("__p.setHidden(true)")
        p.wait_for_timeout(300)
        d = during(p, 900)
        check("e. page hidden: the loop stops (no frames, no rAF)", d[0] == 0 and d[1] == 0 and d[2] == 0, d)
        p.evaluate("__p.setHidden(false)")
        a = counts(p)
        frames_pass(2)
        check("e. page visible again: frames resume", counts(p)[1] - a[1] >= 2)
        p.evaluate("document.getElementById('el').style.marginTop = '3000px'")
        p.wait_for_timeout(500)
        d = during(p, 900)
        check("e. core off-screen: the loop stops (IntersectionObserver)", d[0] == 0 and d[1] == 0 and d[2] == 0, d)
        p.evaluate("document.getElementById('el').style.marginTop = ''")
        a = counts(p)
        frames_pass(2)
        check("e. core back on screen: frames resume", counts(p)[1] - a[1] >= 2)
        # iOS drops WebGL contexts in the background: the 2D core takes over at once and the reactor comes back
        p.evaluate("document.querySelector('#el .jcore canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()")
        p.wait_for_function("core.stats().three !== 'on'", timeout=10000, polling=50)
        lost = p.evaluate("[core.stats().three, document.querySelectorAll('#el .jcore canvas').length]")
        p.wait_for_function("core.stats().three === 'on'", timeout=30000, polling=100)
        frames_pass(3)
        check("e. a lost WebGL context: the 2D core takes over, then the reactor comes back and runs",
              lost[1] == 1 and p.evaluate("document.querySelectorAll('#el .jcore canvas').length") == 2, lost)

        # ---------------------------------------------------------- d: destroy (with the reactor up)
        p.goto(url + "__harness.html")
        p.wait_for_function("window.ready === true", timeout=15000, polling=100)
        base = p.evaluate("__p.live.size")
        p.evaluate("window.core = window.mountCore(document.getElementById('el'), {size: 200})")
        ready3d(p)
        frames_pass(2)
        added = p.evaluate("__p.live.size") - base
        p.evaluate("window.__h = core; core.destroy()")
        a = p.evaluate("[__p.run, __p.req]")
        p.wait_for_timeout(700)
        b = p.evaluate("[__p.run, __p.req]")
        check("d. destroy(): no frame after it (no rAF callback, no new rAF request)", a == b, (a, b))
        left = p.evaluate("__p.live.size") - base
        check(f"d. destroy(): every event listener added (its own and three's: {added}) is removed", added >= 3 and left == 0, (added, left))
        obs = p.evaluate("__p.obs.map((o) => [o.__kind, o.__on])")
        check("d. destroy(): its IntersectionObserver and ResizeObserver are disconnected",
              any(k == "IntersectionObserver" for k, _ in obs) and all(on == 0 for _, on in obs), obs)
        check("d. destroy(): the element is left empty (both canvases gone)", p.evaluate("document.getElementById('el').children.length") == 0)
        p.evaluate("__h.setState('alert'); __h.setLevel(1); __h.setTheme({c: '#fff'}); __h.setDesign('singularity'); __h.destroy()")
        c1 = p.evaluate("[__p.run, __h.stats().frames]")
        p.wait_for_timeout(300)
        check("d. calls after destroy() are harmless (no throw, no frames)", p.evaluate("[__p.run, __h.stats().frames]") == c1)

        # ---------------------------------------------------------- g: slow frames step the effects down
        mount(p, url, "{size: 120, effects: 'high'}", step=40)
        ready3d(p)
        p.wait_for_function("core.stats().tier < 2", timeout=60000, polling=100)
        check("g. slow frames (40 ms) step the effects down to 'low'", p.evaluate("core.stats().effects") == "low", p.evaluate("core.stats()"))
        p.evaluate("core.destroy()")
        mount(p, url, "{size: 120, effects: 'high'}", step=16)
        ready3d(p)
        frames_pass(60, 60000)
        check("g. fast frames (16 ms) keep 'high'", p.evaluate("core.stats().effects") == "high", p.evaluate("core.stats()"))
        p.evaluate("core.destroy()")
        ctx.close()

        # ---------------------------------------------------------- b: devicePixelRatio 3 is capped at 2
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3)
        p = harness(ctx)
        mount(p, url, "{size: 300}")
        ready3d(p)
        w = p.evaluate("[...document.querySelectorAll('.jcore canvas')].map((c) => c.width)")
        check("b. devicePixelRatio 3 is capped at 2 (300 px core -> 600 px backing stores)", w == [600, 600], w)
        p.evaluate("core.destroy()")
        ctx.close()

        # ---------------------------------------------------------- f + c: reduced motion (static frames, so the looks compare exactly)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce")
        p = harness(ctx)
        mount(p, url, "{size: 300}")
        ready3d(p)
        p.wait_for_timeout(500)
        c0 = p.evaluate("[core.stats().frames, core.stats().frames3, __p.req, core.stats().running]")
        d = during(p, 900)
        check("f. reduced motion: a static reactor frame and no animation loop (no frames, no rAF over time)",
              c0[1] >= 1 and c0[2] == 0 and not c0[3] and d == [0, 0, 0, 0], (c0, d))
        p.evaluate("core.setLevel(0.9)")
        p.wait_for_timeout(200)
        check("f. reduced motion: setLevel draws nothing", p.evaluate("[core.stats().frames, core.stats().frames3]") == c0[:2])
        sig = {}
        for i, s in enumerate(STATES):
            p.evaluate(f"core.setState('{s}')")
            p.wait_for_timeout(250)
            sig[s] = shot_sig(p)
            c1 = p.evaluate("[core.stats().frames, core.stats().frames3, __p.req]")
            check(f"c. {s}: its own static frame (exactly one new frame per change, lit)", sig[s]["lit"] > 0.05 and (s == "idle" or c1 == [c0[0] + i, c0[1] + i, 0]),
                  (round(sig[s]["lit"], 3), c0, c1))
        pairs = [(a, b, dist(sig[a], sig[b])) for i, a in enumerate(STATES) for b in STATES[i + 1:]]
        check("c. every state looks different from every other", min(x for _, _, x in pairs) > 0.05, [(a, b, round(x, 3)) for a, b, x in pairs])
        al, li, idl = sig["alert"], sig["listening"], sig["idle"]
        check("c. alert is red / amber (red well above blue)", al["r"] > 1.25 * al["b"] and al["r"] > al["g"], {k: round(al[k]) for k in "rgb"})
        check("c. listening turns the core red (old Jarvis): centre redder than at idle",
              li["cr"] / (li["cb"] + 1) > 1.15 * idl["cr"] / (idl["cb"] + 1), (round(li["cr"]), round(li["cb"]), round(idl["cr"]), round(idl["cb"])))
        check("c. idle is the owner's violet (blue and red over green)", idl["b"] > idl["g"] and idl["r"] > idl["g"], {k: round(idl[k]) for k in "rgb"})
        p.evaluate("core.setState('idle'); core.setTheme({c: '#4fe3ff', c2: '#0284c7', c3: '#9d8cff', tint: '#e6fbff'})")
        p.wait_for_timeout(400)
        ice = shot_sig(p)
        check("c. setTheme recolours the reactor (Reactor Ice: blue over red)", ice["b"] > ice["r"] * 1.1 and ice["g"] > idl["g"],
              {k: round(ice[k]) for k in "rgb"})
        p.evaluate("core.setTheme({c: '#a855f7', c2: '#7c3aed', c3: '#c084fc', tint: '#e9ddff'}); core.setDesign('singularity')")  # noqa
        p.wait_for_timeout(600)
        sing = shot_sig(p)
        check("c. setDesign('singularity'): the black hole (a dark centre ringed by light)",
              p.evaluate("core.stats().design") == "singularity" and sing["band"][0] < idl["band"][0] * 0.6 and max(sing["band"][1:3]) > sing["band"][0] * 1.3,
              ([round(x) for x in sing["band"]], [round(x) for x in idl["band"]]))
        p.evaluate("core.destroy()")
        mount(p, url, "{size: 160, motion: 'always'}")
        ready3d(p)
        a = counts(p)
        frames_pass(3)
        check("f. motion: 'always' (the old Jarvis ignored the OS switch) animates even under reduced motion",
              counts(p)[1] - a[1] >= 3 and p.evaluate("core.stats().running"))
        p.evaluate("core.destroy()")
        ctx.close()
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        p = harness(ctx)
        mount(p, url, "{size: 200, effects: 'off'}")
        ready3d(p)
        p.wait_for_timeout(500)
        c0 = p.evaluate("[core.stats().frames3, __p.req, core.stats().running]")
        d = during(p, 900)
        check("f. effects 'off': a static reactor frame, no loop", c0[0] >= 1 and c0[1:] == [0, False] and d == [0, 0, 0, 0], (c0, d))
        p.evaluate("core.destroy()")
        ctx.close()

        # ---------------------------------------------------------- h: no WebGL -> the 2D core
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        p = harness(ctx, nogl=True)
        n0 = len(fetched)
        mount(p, url, "{adapt: false}")
        p.wait_for_timeout(300)
        st = p.evaluate("[core.stats().three, document.querySelectorAll('.jcore canvas').length]")
        check("h. no WebGL: the 2D core runs alone and three is never fetched",
              st == ["off", 1] and not any("three.module" in u for u in fetched[n0:]), (st, [u for u in fetched[n0:] if "three" in u]))
        s2 = {}
        for s in STATES:
            p.evaluate(f"core.setState('{s}')")
            p.wait_for_function(f"core.stats().frames >= {p.evaluate('core.stats().frames') + 12}", timeout=30000, polling=100)
            s2[s] = canvas_sig(p)
        check("h. no WebGL: every state draws a lit frame", all(s2[s]["lit"] > 0.03 for s in STATES), {s: round(s2[s]["lit"], 3) for s in STATES})
        pairs = [(a, b, dist(s2[a], s2[b])) for i, a in enumerate(STATES) for b in STATES[i + 1:]]
        check("h. no WebGL: the states look different, alert red", min(x for _, _, x in pairs) > 0.05 and s2["alert"]["r"] > 1.4 * s2["alert"]["b"],
              [(a, b, round(x, 3)) for a, b, x in pairs])
        p.evaluate("core.destroy()")
        ctx.close()
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        p = harness(ctx)
        mount(p, url, "{size: 300, webgl: false}")
        p.wait_for_timeout(300)
        g = p.evaluate("[core.stats().three, [...document.querySelectorAll('.jcore canvas')].map((c) => [c.width, c.height])]")
        check("h. webgl: false keeps the 2D core (three 'off'); its canvas is square at any size (300 px at 1x: 300 x 300)",
              g == ["off", [[300, 300]]], g)
        p.evaluate("core.destroy()")
        ctx.close()

        # ---------------------------------------------------------- i: the demo page (+ the screenshots)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        p = ctx.new_page()
        watch(p)
        p.goto(url + "core-demo.html?effects=high&adapt=0")
        p.wait_for_function("window.core && core.stats().three !== 'loading'", timeout=30000, polling=100)
        p.click('button[data-s="thinking"]')
        p.wait_for_timeout(300)
        check("i. demo: the Thinking button switches the core", p.evaluate("core.stats().state") == "thinking"
              and p.get_attribute('button[data-s="thinking"]', "aria-pressed") == "true")
        w = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("i. demo: no sideways scroll at 390 px", w[0] <= w[1], w)
        if shots:
            os.makedirs(shots, exist_ok=True)
            for s in STATES:
                p.click(f'button[data-s="{s}"]')
                if s in ("listening", "speaking"):
                    p.evaluate("window.__f = setInterval(() => core.setLevel(0.55 + 0.4 * Math.abs(Math.sin(performance.now() / 180))), 40)")
                frames_pass(14, 60000)
                p.screenshot(path=os.path.join(shots, f"core_{s}.png"))
                p.evaluate("clearInterval(window.__f)")
                print("   saved", os.path.join(shots, f"core_{s}.png"))
        ctx.close()
        br.close()
    check("i. no console errors or page errors anywhere", not errs, errs[:5])


def main():
    shots = None
    if "--shots" in sys.argv:
        shots = os.path.abspath(sys.argv[sys.argv.index("--shots") + 1])
    part_a()
    tmp = tempfile.mkdtemp(prefix="le_jcore_")
    site = os.path.join(tmp, "jarvis")
    shutil.copytree(JV, site)
    srv = serve(site)
    try:
        run_browser(f"http://127.0.0.1:{srv.server_address[1]}/", shots)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis core: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
