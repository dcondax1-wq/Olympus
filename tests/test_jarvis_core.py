"""The Jarvis core (tools/web_public/jarvis/core-visual.js): the animated centrepiece of Jarvis mode on the owner's phone.
Runs the real module in Chromium (a local server on the jarvis/ folder) and checks:
  a. the file: exports mountCore, under 25 KB, no libraries / CDN / network, no syntax newer than iPhone Safari 16
  b. it mounts: one canvas in the element, retina backing store (devicePixelRatio, capped at 2), the handle's three methods
  c. every state renders: idle / listening / thinking / speaking / alert each draw a non-blank frame and look different
     (alert is red / amber); setLevel drives the voice pulse; unknown states are ignored
  d. destroy(): the animation loop stops (no frame after it), every listener and observer it added is removed, the canvas
     goes, later calls are harmless
  e. it pauses while the page is hidden and while the core is off-screen, and resumes after
  f. prefers-reduced-motion: one static frame (no loop), one new frame per state change, none for setLevel
  g. slow frames drop detail (frame times faked at 40 ms), fast frames keep full detail
  h. the demo page (core-demo.html): the state buttons work, no sideways scroll at 390 px, no console errors anywhere
    python -X utf8 -m tests.test_jarvis_core                    (a local server on a temp copy; nothing else touched)
    python -X utf8 -m tests.test_jarvis_core --shots <dir>      (also saves a 390 px screenshot of each state)
"""
from __future__ import annotations

import functools
import glob
import http.server
import os
import re
import shutil
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
MOD = os.path.join(JV, "core-visual.js")
STATES = ["idle", "listening", "thinking", "speaking", "alert"]
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


# counters installed before any page script: rAF requests / runs (and fake frame times), canvas frames (one clearRect
# per frame), live event listeners, observers, visibility override
PROBE = r"""
(() => {
  const P = window.__p = { req: 0, run: 0, cancel: 0, draws: 0, step: 0, ft: 0, live: new Set(), obs: [], hidden: false };
  const rq = window.requestAnimationFrame.bind(window), cc = window.cancelAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => { P.req++; return rq((ts) => { P.run++; cb(P.step ? (P.ft += P.step) : ts); }); };
  window.cancelAnimationFrame = (id) => { P.cancel++; return cc(id); };
  const clr = CanvasRenderingContext2D.prototype.clearRect;
  CanvasRenderingContext2D.prototype.clearRect = function (...a) { P.draws++; return clr.apply(this, a); };
  const key = new WeakMap(); let n = 0;
  const id = (o) => { if (!key.has(o)) key.set(o, ++n); return key.get(o); };
  const add = EventTarget.prototype.addEventListener, rem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (t, f, o) { if (f) P.live.add(id(this) + ':' + t + ':' + id(f)); return add.call(this, t, f, o); };
  EventTarget.prototype.removeEventListener = function (t, f, o) { if (f) P.live.delete(id(this) + ':' + t + ':' + id(f)); return rem.call(this, t, f, o); };
  for (const name of ['IntersectionObserver', 'ResizeObserver']) {
    const O = window[name];
    if (!O) continue;
    window[name] = class extends O {
      constructor(cb, o) { super(cb, o); this.__on = 0; this.__kind = name; P.obs.push(this); }
      observe(t, o) { this.__on++; return super.observe(t, o); }
      disconnect() { this.__on = 0; return super.disconnect(); }
    };
  }
  Object.defineProperty(Document.prototype, 'hidden', { configurable: true, get() { return P.hidden; } });
  Object.defineProperty(Document.prototype, 'visibilityState', { configurable: true, get() { return P.hidden ? 'hidden' : 'visible'; } });
  P.setHidden = (h) => { P.hidden = h; document.dispatchEvent(new Event('visibilitychange')); };
  // what the canvas shows: alpha-weighted mean colour, lit share, brightness by ring (8 bands from the centre out)
  P.sig = () => {
    const c = document.querySelector('#el canvas'); if (!c) return null;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, w = c.width, h = c.height, cx = w / 2, cy = h / 2;
    let r = 0, g = 0, b = 0, a = 0, lit = 0; const band = new Array(8).fill(0), bn = new Array(8).fill(0);
    for (let y = 0; y < h; y += 2) for (let x = 0; x < w; x += 2) {
      const i = (y * w + x) * 4, al = d[i + 3] / 255, rr = Math.hypot(x - cx, y - cy) / (w / 2);
      r += d[i] * al; g += d[i + 1] * al; b += d[i + 2] * al; a += al; if (d[i + 3] > 60) lit++;
      const k = Math.min(7, Math.floor(rr * 8)); band[k] += (d[i] + d[i + 1] + d[i + 2]) * al / 765; bn[k]++;
    }
    const n = (w / 2) * (h / 2);
    return { r: r / (a || 1), g: g / (a || 1), b: b / (a || 1), a: a / n, lit: lit / n, band: band.map((v, k) => v / (bn[k] || 1)) };
  };
})();
"""

HARNESS = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>core harness</title><link rel="icon" href="icon-192.png">
<style>html,body{margin:0;background:#04070c} #el{width:360px;margin:12px auto}</style></head>
<body><div id="el"></div><div id="pad" style="height:0"></div>
<script type="module">import { mountCore } from './core-visual.js'; window.mountCore = mountCore; window.ready = true;</script>
</body></html>"""


def part_a():
    ok = os.path.exists(MOD)
    check("a. core-visual.js exists", ok)
    if not ok:
        return
    src = open(MOD, encoding="utf-8").read()
    size = len(src.encode("utf-8"))
    check(f"a. under 25 KB unminified ({size:,} bytes)", size < 25 * 1024, size)
    check("a. an ES module that exports mountCore(el, opts)", re.search(r"export function mountCore\s*\(\s*el\s*,", src) is not None)
    check("a. no libraries, no CDN, no network (no import, no URL, no fetch)",
          not re.search(r"^\s*import\s", src, re.M) and "http://" not in src and "https://" not in src
          and "fetch(" not in src and "XMLHttpRequest" not in src and "import(" not in src)
    too_new = ["(?<=", "(?<!", "static {", "roundRect", "createConicGradient", "structuredClone", ".toSorted(", ".toReversed(",
               "Object.groupBy", ".findLast(", "ctx.reset(", "Array.fromAsync", "Promise.withResolvers"]
    code = re.sub(r"/\*.*?\*/", "", re.sub(r"//[^\n]*", "", src), flags=re.S)     # comments may name what is avoided
    hits = [t for t in too_new if t in code]
    check("a. nothing newer than iPhone Safari 16 (no lookbehind, static blocks, roundRect, conic gradients ...)", not hits, hits)
    demo = os.path.join(JV, "core-demo.html")
    check("a. core-demo.html exists and imports the module", os.path.exists(demo) and "from './core-visual.js'" in open(demo, encoding="utf-8").read())


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    h = functools.partial(Quiet, directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def mount(p, url, opts="{}"):
    p.goto(url + "__harness.html")
    p.wait_for_function("window.ready === true", timeout=10000)
    p.evaluate(f"window.core = window.mountCore(document.getElementById('el'), {opts})")


def frames_during(p, ms):
    a = p.evaluate("[__p.draws, __p.run]")
    p.wait_for_timeout(ms)
    b = p.evaluate("[__p.draws, __p.run]")
    return b[0] - a[0], b[1] - a[1]


def dist(s1, s2):
    tot1 = (s1["r"] + s1["g"] + s1["b"]) or 1
    tot2 = (s2["r"] + s2["g"] + s2["b"]) or 1
    chroma = sum(abs(s1[k] / tot1 - s2[k] / tot2) for k in "rgb")
    shape = sum(abs(x - y) for x, y in zip(s1["band"], s2["band"])) / (sum(s1["band"]) + sum(s2["band"]) or 1)
    return chroma + shape + abs(s1["a"] - s2["a"]) / max(s1["a"], s2["a"], 1e-6) * 0.5


def run_browser(url, shots):
    from playwright.sync_api import sync_playwright
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    errs = []

    def watch(p):
        p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)

    def harness(ctx):
        ctx.add_init_script(PROBE)
        ctx.route("**/__harness.html", lambda r: r.fulfill(status=200, content_type="text/html", body=HARNESS))
        p = ctx.new_page()
        watch(p)
        return p

    with sync_playwright() as pw:
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))

        # ---------------------------------------------------------- b + c: mount, every state, the level
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        p = harness(ctx)
        mount(p, url, "{detail: 3}")
        info = p.evaluate("""(() => { const el = document.getElementById('el'), c = el.querySelectorAll('canvas');
            return { n: c.length, w: c[0].width, cw: c[0].getBoundingClientRect().width, keys: Object.keys(window.core).sort() }; })()""")
        check("b. mounts one canvas inside the element", info["n"] == 1, info)
        check("b. the handle has setState, setLevel, destroy", all(k in info["keys"] for k in ("setState", "setLevel", "destroy")), info["keys"])
        check("b. retina: backing store = CSS width x devicePixelRatio (2)", abs(info["w"] - round(info["cw"] * 2)) <= 1, info)
        d, r = frames_during(p, 500)
        check("b. it animates (frames keep coming)", d >= 5 and r >= 5, (d, r))
        sig = {}
        for s in STATES:
            p.evaluate(f"core.setState('{s}')")
            p.wait_for_timeout(900)
            sig[s] = p.evaluate("__p.sig()")
            st = p.evaluate("core.stats().state")
            check(f"c. {s}: draws a non-blank frame", sig[s] and sig[s]["lit"] > 0.03 and st == s, (st, sig[s] and round(sig[s]["lit"], 4)))
        pairs = [(a, b, dist(sig[a], sig[b])) for i, a in enumerate(STATES) for b in STATES[i + 1:]]
        worst = min(pairs, key=lambda x: x[2])
        check("c. every state looks different from every other", worst[2] > 0.08, [(a, b, round(x, 3)) for a, b, x in pairs])
        al = sig["alert"]
        check("c. alert is red / amber (red well above blue)", al["r"] > 1.6 * al["b"] and al["r"] > al["g"], {k: round(al[k], 1) for k in "rgb"})
        p.evaluate("core.setState('speaking')")
        p.evaluate("window.__f = setInterval(() => core.setLevel(window.__lv), 40); window.__lv = 0")
        p.wait_for_timeout(700)
        quiet = p.evaluate("[core.stats().level, __p.sig().band]")
        p.evaluate("window.__lv = 1")
        p.wait_for_timeout(700)
        loud = p.evaluate("[core.stats().level, __p.sig().band]")
        p.evaluate("clearInterval(window.__f)")
        mid_q, mid_l = sum(quiet[1][3:6]), sum(loud[1][3:6])
        check("c. setLevel drives the voice pulse (level 0 -> 1: the level follows, the waveform ring brightens)",
              quiet[0] < 0.1 and loud[0] > 0.85 and mid_l > mid_q * 1.15, (quiet[0], loud[0], round(mid_q, 3), round(mid_l, 3)))
        p.evaluate("core.setState('nonsense'); core.setLevel('x'); core.setLevel(-3); core.setLevel(9)")
        check("c. an unknown state is ignored, bad levels are clamped (no throw)", p.evaluate("core.stats().state") == "speaking")

        # ---------------------------------------------------------- e: hidden page, off-screen
        p.evaluate("__p.setHidden(true)")
        p.wait_for_timeout(150)
        d, r = frames_during(p, 500)
        check("e. page hidden: the loop stops (no frames)", d == 0 and r == 0, (d, r))
        p.evaluate("__p.setHidden(false)")
        d, r = frames_during(p, 500)
        check("e. page visible again: frames resume", d >= 5, (d, r))
        p.evaluate("document.getElementById('el').style.marginTop = '3000px'")
        p.wait_for_timeout(300)
        d, r = frames_during(p, 500)
        check("e. core off-screen: the loop stops (IntersectionObserver)", d == 0 and r == 0, (d, r))
        p.evaluate("document.getElementById('el').style.marginTop = ''")
        p.wait_for_timeout(300)
        d, r = frames_during(p, 500)
        check("e. core back on screen: frames resume", d >= 5, (d, r))

        # ---------------------------------------------------------- d: destroy
        before = p.evaluate("__p.live.size")
        p.goto(url + "__harness.html")
        p.wait_for_function("window.ready === true", timeout=10000)
        base = p.evaluate("__p.live.size")
        p.evaluate("window.core = window.mountCore(document.getElementById('el'), {})")
        p.wait_for_timeout(300)
        added = p.evaluate("__p.live.size") - base
        p.evaluate("core.destroy()")
        pend = p.evaluate("[__p.draws, __p.run, __p.req]")
        p.wait_for_timeout(500)
        after = p.evaluate("[__p.draws, __p.run, __p.req]")
        check("d. destroy(): no frame after it (no draw, no rAF callback, no new rAF request)",
              after[0] == pend[0] and after[1] == pend[1] and after[2] == pend[2], (pend, after))
        left = p.evaluate("__p.live.size") - base
        check(f"d. destroy(): every event listener it added is removed ({added} added)", added >= 1 and left == 0, (added, left, before))
        obs = p.evaluate("__p.obs.map((o) => [o.__kind, o.__on])")
        check("d. destroy(): its IntersectionObserver and ResizeObserver are disconnected",
              any(k == "IntersectionObserver" for k, _ in obs) and all(on == 0 for _, on in obs), obs)
        check("d. destroy(): the canvas is removed", p.evaluate("document.querySelectorAll('#el canvas').length") == 0)
        p.evaluate("core.setState('alert'); core.setLevel(1); core.destroy()")
        d, r = frames_during(p, 300)
        check("d. calls after destroy() are harmless (no throw, no frames)", d == 0 and r == 0, (d, r))

        # ---------------------------------------------------------- g: slow frames drop detail
        mount(p, url)
        p.evaluate("__p.step = 40")
        p.wait_for_timeout(2500)
        slow = p.evaluate("core.stats()")
        check("g. slow frames (40 ms) drop the detail tier", slow["tier"] < 3, slow)
        p.evaluate("core.destroy()")
        mount(p, url)
        p.evaluate("__p.step = 16")
        p.wait_for_timeout(1500)
        fast = p.evaluate("core.stats()")
        check("g. fast frames (16 ms) keep full detail", fast["tier"] == 3, fast)
        p.evaluate("core.destroy()")
        ctx.close()

        # ---------------------------------------------------------- b: devicePixelRatio is capped at 2
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3)
        p = harness(ctx)
        mount(p, url, "{size: 300}")
        w = p.evaluate("(() => { const c = document.querySelector('#el canvas'); return [c.width, c.getBoundingClientRect().width]; })()")
        check("b. devicePixelRatio 3 is capped at 2 (300 px core -> 600 px backing store)", w == [600, 300], w)
        ctx.close()

        # ---------------------------------------------------------- f: reduced motion
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce")
        p = harness(ctx)
        mount(p, url)
        p.wait_for_timeout(600)
        c0 = p.evaluate("[__p.draws, __p.req, __p.sig().lit, core.stats().running]")
        check("f. reduced motion: exactly one static frame, no animation loop", c0[0] == 1 and c0[1] == 0 and not c0[3], c0)
        check("f. reduced motion: the static frame is not blank", c0[2] > 0.03, c0)
        p.evaluate("core.setLevel(0.9)")
        p.wait_for_timeout(200)
        check("f. reduced motion: setLevel draws nothing", p.evaluate("__p.draws") == 1)
        p.evaluate("core.setState('alert')")
        p.wait_for_timeout(400)
        c1 = p.evaluate("[__p.draws, __p.req, __p.sig()]")
        check("f. reduced motion: a state change draws exactly one new frame (alert is red)",
              c1[0] == 2 and c1[1] == 0 and c1[2]["r"] > 1.6 * c1[2]["b"], (c1[0], c1[1], {k: round(c1[2][k], 1) for k in "rgb"}))
        p.evaluate("core.destroy()")
        ctx.close()

        # ---------------------------------------------------------- h: the demo page (+ the screenshots)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        p = ctx.new_page()
        watch(p)
        p.goto(url + "core-demo.html?detail=3")
        p.wait_for_function("!!window.core", timeout=10000)
        p.click('button[data-s="thinking"]')
        p.wait_for_timeout(300)
        check("h. demo: the Thinking button switches the core", p.evaluate("core.stats().state") == "thinking"
              and p.get_attribute('button[data-s="thinking"]', "aria-pressed") == "true")
        w = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("h. demo: no sideways scroll at 390 px", w[0] <= w[1], w)
        if shots:
            os.makedirs(shots, exist_ok=True)
            for s in STATES:
                p.click(f'button[data-s="{s}"]')
                if s in ("listening", "speaking"):
                    p.evaluate("window.__f = setInterval(() => core.setLevel(0.55 + 0.4 * Math.abs(Math.sin(performance.now() / 180))), 40)")
                p.wait_for_timeout(1200 if s != "alert" else 450)
                p.screenshot(path=os.path.join(shots, f"core_{s}.png"))
                p.evaluate("clearInterval(window.__f)")
                print("   saved", os.path.join(shots, f"core_{s}.png"))
        ctx.close()
        br.close()
    check("h. no console errors or page errors", not errs, errs[:5])


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
