"""The OLYMPUS effects library (tools/web_public/olympus/fx-*.js, docs/OLYMPUS_FX.md, the lab olympus/fx-lab.html).

42 reusable, theme-aware, tier-aware effects (cards, buttons, numbers, text, bursts, sky / weather / surfaces for three.js scenes) and the
zero-edit wiring in olympus.js / olympus.css (data-oly-fx="shimmer|tilt|glow|odometer|ripple", opt-out). Runs in Chromium (WebGL through
SwiftShader) at 390 x 844 (device pixel ratio 3, like an iPhone), on the real site layout, every request off the origin refused.
  a. static: the files, 30+ effects, every effect in the lab and in the docs with exactly three usage lines, the kit rules (Safari 16 safe,
     no external URL, no localStorage write, no console.log), the wiring and the opt-out in the kit, the library's weight
  b. every effect on every tier (ultra / high / low / off): it starts, runs, reports its tier, makes no error, respects the caps (canvas pixel
     ratio and pixel budget, pooled particles per tier), and stop() (twice) leaves NOTHING behind: no ticker, canvas, DOM node, scene object,
     geometry or texture; off runs no loop at all
  c. prefers-reduced-motion = off for every effect (no loop, no scene object), no error
  d. the hidden tab: the shared loop draws no frame, and runs again when the tab is back
  e. live tier changes: OLYMPUS.setFx() (the kit's one quality setting) and the lab switch rebuild the running effects (fewer particles on low,
     nothing on off), then stop leaves nothing
  f. the scene effects are visible (the stage changes) and the lightning flashes the scene
  g. the zero-edit wiring: data-oly-fx pulls in only the files it needs, shimmer / glow / ripple are CSS, tilt / odometer / ripple work on a
     plain element, the opt-out works (element, ancestor, page, OLYMPUS.fxUI), later-added elements are wired, a page without the attribute
     or with effects off / reduced motion loads no fx file
    python -X utf8 -m tests.test_olympus_fx
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
LAB = "/olympus/fx-lab.html"
RES: list = []
# per tier: canvas pixel ratio cap, canvas pixel budget, particles per effect (fx-core.js CAPS)
CAPS = {"ultra": (2, 1_600_000, 2000), "high": (1.5, 1_100_000, 1200), "low": (1, 520_000, 400), "off": (1, 520_000, 0)}
SELF_FINISH = {"confetti", "sparkleBurst", "toast", "shockwave"}      # they end by themselves: may be gone before the check
NO_DIFF = {"lightning", "skeleton"}                                   # lightning waits for its first strike (tested on its own)
WIRE_FILES = ("fx-core.js", "fx-ui.js", "fx-text.js", "fx-burst.js", "fx-sky.js", "fx-weather.js", "fx-surface.js")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ a. static
def test_static():
    files = sorted(glob.glob(os.path.join(KIT, "fx-*.js")))
    names = [os.path.basename(f) for f in files]
    want = {"fx-core.js", "fx-ui.js", "fx-text.js", "fx-burst.js", "fx-three.js", "fx-sky.js", "fx-weather.js", "fx-surface.js"}
    check("a. the library's files are there", want <= set(names), sorted(want - set(names)))
    check("a. fx-lab.html and docs/OLYMPUS_FX.md exist", os.path.exists(os.path.join(KIT, "fx-lab.html")) and os.path.exists(os.path.join(ROOT, "docs", "OLYMPUS_FX.md")))
    src = {n: read(os.path.join(KIT, n)) for n in names}
    allsrc = "\n".join(src.values())
    defined = re.findall(r"(?:FX\.define|def)\(\s*'(\w+)'", allsrc)
    check("a. at least 30 effects are defined (%d)" % len(defined), len(set(defined)) >= 30 and len(defined) == len(set(defined)), sorted(defined))
    lab = read(os.path.join(KIT, "fx-lab.html"))
    check("a. the lab lists effects from the registry (every defined effect is in it, grouped, with a tier switcher)",
          "FX.list()" in lab and all(f'data-t="{t}"' in lab for t in ("ultra", "high", "low", "off")) and "__fxLab" in lab)
    doc = read(os.path.join(ROOT, "docs", "OLYMPUS_FX.md"))
    bad = []
    for n in sorted(set(defined)):
        m = re.search(r"### `%s`\n.*?```js\n(.*?)```" % n, doc, re.S)
        lines = [ln for ln in (m.group(1).strip().split("\n") if m else []) if ln.strip()]
        if not m or len(lines) != 3 or f"OLYMPUS_FX.{n}(" not in lines[0]:
            bad.append((n, len(lines)))
    check("a. docs/OLYMPUS_FX.md: every effect has a section with exactly 3 usage lines", not bad, bad)
    check("a. the docs say tiers, reduced motion, the opt-out and the wiring",
          all(x in doc for x in ("data-oly-fx-off", "data-oly-fx-ui", "OLYMPUS.fxUI", "prefers-reduced-motion", "ultra", "odometer", "tests/test_olympus_fx.py")))
    bad = [n for n in names if re.search(r"\?\.|\?\?|\(\?<[=!]|\.at\(|color-mix\(|:has\(", src[n].replace("'?.'", ""))]
    check("a. the library is Safari 16 safe (no ?. ?? lookbehind .at() color-mix :has)", not bad, bad)
    ext = [n for n in names if re.search(r"""(?:import|from|src=|href=|url\()[^\n]{0,8}['"(]https?://""", src[n])]
    check("a. no external URL is loaded by the library (no CDN)", not ext, ext)
    check("a. the library never writes localStorage (the quality choice is the kit's) and never logs", not re.search(r"localStorage\.(set|remove)Item|console\.log", allsrc))
    core = src["fx-core.js"]
    check("a. fx-core.js: ONE requestAnimationFrame, the hidden-tab pause, the tier rules (OLYMPUS.fx, reduced motion), the caps",
          len(re.findall(r"requestAnimationFrame\(", core)) == 2 and "raf = requestAnimationFrame(frame)" in core and "hidden()" in core and "OLYMPUS.fx" in core.replace("O.fx", "OLYMPUS.fx")
          and "prefers-reduced-motion" in core and "CAPS" in core and "IntersectionObserver" in core)
    check("a. the other files never schedule frames themselves (they use ctx.tick on the shared loop)",
          not any("requestAnimationFrame" in src[n] for n in names if n != "fx-core.js"))
    total = sum(len(v.encode()) for v in src.values())
    ui = sum(len(src[n].encode()) for n in ("fx-core.js", "fx-ui.js", "fx-text.js", "fx-burst.js"))
    # 2026-11-11: the cinema stack (fx-cine.js, only ever loaded by a 3D scene) joined: the whole library <= 200 KB, the 2D / UI part a page
    # pays for on its own <= 80 KB, fx-cine.js <= 60 KB
    check("a. the library is small (all %d KB <= 200; the 2D / UI part %d KB <= 80 and loads without any three.js; fx-cine.js %d KB <= 60)" % (total // 1024, ui // 1024, len(src.get("fx-cine.js", "").encode()) // 1024),
          total < 200 * 1024 and ui < 80 * 1024 and len(src.get("fx-cine.js", "").encode()) < 60 * 1024
          and not any("THREE" in src[n] or "import " in src[n] for n in ("fx-core.js", "fx-ui.js", "fx-text.js", "fx-burst.js")))
    js, css = read(os.path.join(KIT, "olympus.js")), read(os.path.join(KIT, "olympus.css"))
    check("a. olympus.js wiring: data-oly-fx scan, lazy files, observer, OLYMPUS.fxUI, opt-out (element / ancestor / html attribute / meta)",
          all(x in js for x in ("data-oly-fx", "fx-' + name + '.js", "MutationObserver", "O.fxUI", "data-oly-fx-off", "data-oly-fx-ui", "olympus-fx-ui")))
    check("a. olympus.css wiring: shimmer / glow / ripple in CSS with zero specificity, low = still, off = nothing, reduced motion, opt-out",
          all(x in css for x in ('[data-oly-fx~="shimmer"]', '[data-oly-fx~="glow"]', '[data-oly-fx~="ripple"]', 'html[data-fx="low"]', 'html[data-fx="off"]',
                                 "[data-oly-fx-off]", 'html[data-oly-fx-ui="off"]', "oly-fx-sweep", "oly-fx-rip")) and css.count(":where(") >= 8)
    bad = [p for p in (r"color-mix\(", r":has\(", r"\(\?<[=!]", r"\.at\(", r"\?\.", r"\?\?") if re.search(p, js + css)]
    check("a. olympus.js / olympus.css stay Safari 16 safe and ES5 after the wiring", not bad, bad)


# ------------------------------------------------------------------ the browser
def new_page(br, origin, query="", fx=None, reduced=False, mobile=True):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=mobile, has_touch=mobile,
                         reduced_motion="reduce" if reduced else "no-preference")
    off_site: list = []
    reqs: list = []

    def route(r):
        if r.request.url.startswith(origin):
            reqs.append(r.request.url)
            return r.continue_()
        off_site.append(r.request.url)
        return r.abort()
    ctx.route("**/*", route)
    init = COUNT_DRAWS + (f"try {{ localStorage.setItem('jfx', {json.dumps(fx)}); }} catch (e) {{}}" if fx else "try { localStorage.removeItem('jfx'); } catch (e) {}")
    ctx.add_init_script(init)
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") and "GL Driver" not in m.text and "favicon" not in m.text else None)
    p.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
    p.goto(origin + LAB + query)
    p.wait_for_function("() => window.__fxLab && (window.__fxLab.ready || window.__fxLab.error)", timeout=180000)
    err = p.evaluate("() => window.__fxLab.error || null")
    if err:
        errs.append("lab: " + err)
    elif "bare=1" not in query and not reduced and fx != "off":
        # the lab carries data-oly-fx elements (the wiring section): wait until the kit has wired them, that is the baseline
        p.wait_for_function("() => OLYMPUS_FX.stats().active >= 3", timeout=60000)
    return ctx, p, errs, off_site, reqs


FRAMES = "(n) => new Promise((r) => { let i = 0; const f = () => (++i >= n ? r() : requestAnimationFrame(f)); requestAnimationFrame(f); })"

RUN = """async ([name, wait]) => {
  const FX = OLYMPUS_FX, L = __fxLab, r = L.rc.renderer, frames = %s;
  const count = (o) => { let n = 0; o.traverse(() => n++); return n; };
  const snap = () => ({ kids: count(L.scene), g: r.info.memory.geometries, t: r.info.memory.textures,
    nodes: document.body.querySelectorAll('*').length, canv: document.querySelectorAll('[data-oly-fx-canvas]').length });
  await frames(2); L.rc.render();
  const b = Object.assign(snap(), { stats: FX.stats() });
  const h = L.run(name);
  await frames(3); await new Promise((x) => setTimeout(x, wait));
  if (FX.info(name).kind === 'scene') L.rc.render();            // the stage draws no loop in the tests: one frame uploads what the effect made
  const d = Object.assign(snap(), { stats: FX.stats(), tier: h.tier, stopped: h.stopped, kind: FX.info(name).kind });
  L.stop(name); L.stop(name); h.stop();
  await frames(2);
  const a = Object.assign(snap(), { stats: FX.stats() });
  return { b, d, a, hasStop: typeof h.stop === 'function' };
}""" % FRAMES

LIT = """() => { const c = document.getElementById('stage'); __fxLab.rc.render(); const g = document.createElement('canvas'); g.width = 195; g.height = 211;
  const x = g.getContext('2d', { willReadFrequently: true }); x.drawImage(c, 0, 0, 195, 211); return Array.from(x.getImageData(0, 0, 195, 211).data); }"""


def diff_px(a, b):
    n = 0
    for i in range(0, len(a), 4):
        if abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2]) > 18:
            n += 1
    return n


def until(p, js, ms=45000):
    """Wait for a condition in the page (the machine may be slow: never a fixed sleep for something that has to happen)."""
    try:
        p.wait_for_function(js, timeout=ms)
        return True
    except Exception:
        return False


def check_effect(name, tier, res, reduced=False):
    b, d, a = res["b"], res["d"], res["a"]
    st, cap = d["stats"], CAPS[tier]
    label = f"b. {name} @ {tier}" if not reduced else f"c. {name} (reduced motion)"
    probs = []
    if not res["hasStop"]:
        probs.append("no stop()")
    if d["tier"] != tier:
        probs.append(f"tier {d['tier']}")
    if st["errors"]:
        probs.append(f"errors {st['errors']}")
    if tier != "off" and not d["stopped"] and st["active"] < b["stats"]["active"] + 1 and name not in SELF_FINISH:
        probs.append("not active")
    if st["overCap"] or st["particles"] > cap[2]:
        probs.append(f"particles {st['particles']} > {cap[2]}")
    for c in st["canvases"]:
        if c["px"] > cap[1] or c["dpr"] > cap[0] + 0.02:
            probs.append(f"canvas {c}")
    if tier == "off" and (st["running"] > b["stats"]["running"] or st["tickers"] > b["stats"]["tickers"]):
        probs.append(f"off runs a loop: {st['running']} / {st['tickers']}")
    if d["kind"] == "scene" and tier == "off" and d["kids"] != b["kids"]:
        probs.append("off adds scene objects")
    if d["kind"] == "scene" and tier != "off" and d["kids"] <= b["kids"] and name not in ("glowOutline",):
        probs.append("adds nothing to the scene")
    bs, ast = b["stats"], a["stats"]
    if ast["active"] != bs["active"] or ast["tickers"] != bs["tickers"] or ast["canvases"] or ast["running"] != bs["running"] or ast["particles"]:
        probs.append(f"after stop: {ast} (before {bs})")
    for k in ("kids", "g", "t", "nodes", "canv"):
        if a[k] != b[k] and not (k == "t" and name == "glassPanel" and tier == "ultra" and a[k] - b[k] == 1):
            # (glassPanel with transmission: three itself keeps ONE refraction buffer per renderer once a transmissive object has drawn)
            probs.append(f"leak {k}: {b[k]} -> {a[k]}")
    check(label + ": starts, runs, caps hold, stop() leaves nothing", not probs, probs)


def test_every_effect(br, origin):
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still&small=1")
    names = p.evaluate("() => OLYMPUS_FX.names()")
    check("b. the lab loaded every effect (%d)" % len(names), len(names) >= 30, names)
    only = [n for n in os.environ.get("OLY_FX_ONLY", "").split(",") if n]        # OLY_FX_ONLY=glassPanel,progressRing: re-check a few quickly
    names = [n for n in names if not only or n in only]
    for tier in ("ultra", "high", "low", "off"):
        p.evaluate("(t) => __fxLab.setTier(t)", tier)
        for n in names:
            res = p.evaluate(RUN, [n, 200])
            check_effect(n, tier, res)
    check("b. no page error, no console error or warning, no failed request", not errs, errs[:5])
    check("b. no request left the site", not off, off[:3])
    # the particle counts really drop with the tier
    p.evaluate("(t) => __fxLab.setTier(t)", "ultra")
    counts = {}
    for t in ("ultra", "high", "low", "off"):
        p.evaluate("(t) => __fxLab.setTier(t)", t)
        counts[t] = p.evaluate("() => { const h = __fxLab.run('rain'); const n = OLYMPUS_FX.stats().particles; __fxLab.stop('rain'); return n; }")
    check("b. particle counts follow the tier (rain: %s)" % counts, counts["ultra"] > counts["high"] > counts["low"] > counts["off"] == 0 and counts["ultra"] <= 2000, counts)
    ctx.close()


def test_reduced(br, origin):
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still&small=1", reduced=True)
    check("c. reduced motion: the effects' tier is off", p.evaluate("() => OLYMPUS_FX.tier()") == "off")
    for n in p.evaluate("() => OLYMPUS_FX.names()"):
        check_effect(n, "off", p.evaluate(RUN, [n, 120]), reduced=True)
    check("c. no error with reduced motion", not errs, errs[:5])
    ctx.close()


def test_hidden(br, origin):
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still&small=1")
    p.evaluate("(t) => __fxLab.setTier(t)", "high")
    base = p.evaluate("() => OLYMPUS_FX.stats()")          # the lab's own data-oly-fx elements are wired: that is the baseline
    p.evaluate("() => { __fxLab.run('rain'); __fxLab.run('countUp'); __fxLab.run('fireflies'); }")
    p.wait_for_timeout(500)
    f0 = p.evaluate("() => OLYMPUS_FX.stats().frames")
    check("d. the shared loop runs while the tab is visible", f0 > 0)
    p.evaluate(HIDE, True)
    p.wait_for_timeout(300)
    f1 = p.evaluate("() => OLYMPUS_FX.stats()")
    p.wait_for_timeout(700)
    f2 = p.evaluate("() => OLYMPUS_FX.stats()")
    check("d. a hidden tab draws no effect frame and asks for none", f2["frames"] == f1["frames"] and not f2["raf"], (f1["frames"], f2["frames"], f2["raf"]))
    p.evaluate(HIDE, False)
    until(p, "() => OLYMPUS_FX.stats().frames > %d" % (f2["frames"] + 2))
    f3 = p.evaluate("() => OLYMPUS_FX.stats().frames")
    check("d. frames run again once the tab is visible", f3 > f2["frames"] + 2, (f2["frames"], f3))
    p.evaluate("() => __fxLab.stopAll()")
    s = p.evaluate("() => OLYMPUS_FX.stats()")
    check("d. after stopAll nothing is left but the wired elements", s["active"] == base["active"] and s["tickers"] == base["tickers"], (s, base))
    p.wait_for_timeout(200)
    f4, f5 = p.evaluate("() => OLYMPUS_FX.stats().frames"), None
    p.wait_for_timeout(400)
    f5 = p.evaluate("() => OLYMPUS_FX.stats().frames")
    check("d. with no effect running the loop asks for no frame", f4 == f5, (f4, f5))
    check("d. no error", not errs, errs[:3])
    ctx.close()


def test_live_tiers(br, origin):
    # the kit's own quality key: OLYMPUS.setFx() rebuilds the running effects (the lab does not pin the tier here)
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still&small=1", fx="high")
    base = p.evaluate("() => OLYMPUS_FX.stats()")
    p.evaluate("() => { window.H = { f: __fxLab.run('fireflies'), t: __fxLab.run('tilt'), r: __fxLab.run('progressRing'), c: __fxLab.run('confetti') }; }")
    p.wait_for_timeout(300)
    s = p.evaluate("() => ({ tiers: Object.values(H).map(h => h.tier), parts: OLYMPUS_FX.stats().particles })")
    check("e. effects start on the kit's tier (jfx=high)", s["tiers"] == ["high"] * 4, s)
    p.evaluate("() => OLYMPUS.setFx('low')")
    p.wait_for_timeout(300)
    s2 = p.evaluate("() => ({ tiers: Object.values(H).map(h => h.tier), stopped: Object.values(H).map(h => h.stopped), parts: OLYMPUS_FX.stats().particles, active: OLYMPUS_FX.stats().active })")
    check("e. OLYMPUS.setFx('low') rebuilds the running effects on low, with fewer particles",
          all(t == "low" for t, x in zip(s2["tiers"], s2["stopped"]) if not x) and s2["parts"] < s["parts"], (s, s2))
    p.evaluate("() => OLYMPUS.setFx('off')")
    until(p, "() => !OLYMPUS_FX.stats().raf")                 # a frame already asked for runs once and asks for no more
    s3 = p.evaluate("() => OLYMPUS_FX.stats()")
    check("e. off: the loop stops (nothing runs, nothing draws)", s3["running"] == 0 and s3["particles"] == 0 and not s3["raf"], s3)
    p.evaluate("() => OLYMPUS.setFx('ultra')")
    p.wait_for_timeout(300)
    s4 = p.evaluate("() => ({ tiers: Object.values(H).filter(h => !h.stopped).map(h => h.tier), parts: OLYMPUS_FX.stats().particles })")
    check("e. back to ultra: effects run again, the full counts", s4["tiers"] and all(t == "ultra" for t in s4["tiers"]) and s4["parts"] > s2["parts"], s4)
    p.evaluate("() => __fxLab.stopAll()")
    s5 = p.evaluate("() => OLYMPUS_FX.stats()")
    check("e. stop leaves nothing", s5["active"] == base["active"] and s5["tickers"] == base["tickers"] and not s5["canvases"], (s5, base))
    # a stopped handle is harmless
    ok = p.evaluate("(n) => { const h = OLYMPUS_FX.rain(__fxLab.scene); h.stop(); h.stop(); return h.stopped && OLYMPUS_FX.stats().active === n; }", base["active"])
    check("e. stop() twice is harmless; a bad target gives a no-op handle, never a throw",
          ok and p.evaluate("() => { const a = OLYMPUS_FX.tilt(null), b = OLYMPUS_FX.rain({}); a.stop(); b.stop(); return !!a.error && !!b.error; }"))
    check("e. no error", not errs, errs[:3])
    ctx.close()


def test_visible(br, origin):
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still")
    p.evaluate("(t) => __fxLab.setTier(t)", "high")
    p.wait_for_timeout(300)
    p.evaluate("() => __fxLab.stopAll()")
    p.evaluate(FRAMES, 3)
    base, base2 = p.evaluate(LIT), None
    p.evaluate(FRAMES, 3)
    base2 = p.evaluate(LIT)
    noise = diff_px(base, base2)
    weak, shown = [], {}
    for n in p.evaluate("() => OLYMPUS_FX.list().filter(i => i.kind === 'scene').map(i => i.name)"):
        if n in NO_DIFF:
            continue
        p.evaluate("(n) => { __fxLab.stopAll(); __fxLab.run(n); }", n)
        p.evaluate(FRAMES, 6)
        p.wait_for_timeout(500)
        shown[n] = diff_px(base, p.evaluate(LIT))
        print(f"  .. {n}: {shown[n]} px changed", flush=True)
        if shown[n] < noise + 6:
            weak.append((n, shown[n], noise))
        p.evaluate("() => __fxLab.stopAll()")
    check("f. every scene effect changes the stage (%d effects, stage noise %d px)" % (len(shown), noise), not weak, weak)
    # lightning: a strike lights the scene up, then it dies away
    p.evaluate("() => { __fxLab.stopAll(); window.LT = __fxLab.run('lightning'); window.LT.set && 0; }")
    p.evaluate(FRAMES, 2)
    p.evaluate("() => { LT.call('strike'); }")
    p.evaluate(FRAMES, 2)
    on = p.evaluate("() => LT.call('flash')")
    lit = diff_px(base, p.evaluate(LIT))
    p.wait_for_timeout(1500)
    p.evaluate(FRAMES, 4)
    off_f = p.evaluate("() => LT.call('flash')")
    check("f. lightning: a strike flashes the scene (flash %.2f, %d px lit) and it dies away (%.2f)" % (on or 0, lit, off_f or 0), (on or 0) > 0.05 and lit > noise + 100 and off_f < 0.05, (on, lit, off_f))
    p.evaluate("() => __fxLab.stopAll()")
    check("f. no error", not errs, errs[:3])
    ctx.close()


def test_marble(br, origin):
    """The marble floor really mirrors the scene on high / ultra (a reflection buffer), and not on low."""
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still&small=1")
    counts = {}
    for tier in ("high", "low"):
        p.evaluate("(t) => __fxLab.setTier(t)", tier)
        p.evaluate("() => { __fxLab.stopAll(); __fxLab.rc.render(); }")
        t0 = p.evaluate("() => __fxLab.rc.renderer.info.memory.textures")
        p.evaluate("() => { __fxLab.run('marbleFloor'); }")
        p.evaluate(FRAMES, 3)
        p.evaluate("() => __fxLab.rc.render()")             # the stage draws no loop here: one frame runs the mirror's pre-render
        p.evaluate("() => __fxLab.rc.render()")
        counts[tier] = p.evaluate("() => __fxLab.rc.renderer.info.memory.textures") - t0
        p.evaluate("() => __fxLab.stopAll()")
    check("f. marbleFloor: a reflection buffer on high, none on low (extra textures %s)" % counts, counts["high"] > counts["low"], counts)
    check("f. no error (marbleFloor)", not errs, errs[:3])
    ctx.close()


def test_elements(br, origin):
    """Behaviour of the card / button / number effects on their samples."""
    ctx, p, errs, off, _ = new_page(br, origin, "?stage=still&small=1")
    p.evaluate("(t) => __fxLab.setTier(t)", "high")
    # odometer: the digits roll when the app writes a number, and the plain text is back after
    p.evaluate("() => { __fxLab.run('odometer'); }")
    p.wait_for_timeout(100)
    p.evaluate("() => { __fxLab.hosts.odometer.textContent = '1,291.7'; }")
    p.wait_for_timeout(100)
    mid = p.evaluate("() => { const e = __fxLab.hosts.odometer; return { cols: e.querySelectorAll('.oly-odo-c').length, text: e.textContent }; }")
    try:                                              # the machine may be slow: wait for the roll to end, not a fixed time
        p.wait_for_function("() => !__fxLab.hosts.odometer.querySelector('.oly-odo')", timeout=30000)
    except Exception:
        pass
    end = p.evaluate("() => { const e = __fxLab.hosts.odometer; return { cols: e.querySelectorAll('.oly-odo-c').length, text: e.textContent, html: e.innerHTML }; }")
    check("e. odometer: rolls columns on a change, the text stays the number, and settles back to plain text",
          mid["cols"] >= 3 and mid["text"] == "1,291.7" and end["cols"] == 0 and end["text"] == "1,291.7" and "<" not in end["html"], (mid, end))
    p.evaluate("() => __fxLab.stopAll()")
    # countUp ends on the exact text; typewriter ends on the full text and gives it back on stop
    p.evaluate("() => { __fxLab.hosts.countUp.scrollIntoView({ block: 'center' }); __fxLab.run('countUp'); }")   # an element effect sleeps while its element is off screen
    try:
        p.wait_for_function("() => __fxLab.hosts.countUp.textContent === '12,840'", timeout=40000)
    except Exception:
        pass
    cu = p.evaluate("() => __fxLab.hosts.countUp.textContent")
    p.evaluate("() => __fxLab.stopAll()")
    check("e. countUp: counts to 12,840", cu == "12,840", cu)
    p.evaluate("() => { __fxLab.hosts.typewriter.scrollIntoView({ block: 'center' }); __fxLab.run('typewriter'); }")
    try:
        p.wait_for_function("() => __fxLab.hosts.typewriter.textContent.replace('\\u258d', '').length > 3", timeout=40000)
    except Exception:
        pass
    part = p.evaluate("() => __fxLab.hosts.typewriter.textContent")
    p.evaluate("() => __fxLab.stopAll()")
    full = p.evaluate("() => __fxLab.hosts.typewriter.textContent")
    check("e. typewriter: types part of the text, stop gives the full text back", 0 < len(part.replace("▍", "")) < len(full) and full == "OLYMPUS online. All systems nominal.", (part, full))
    # tilt leans and comes back; magnetic / ripple leave no style behind after stop
    SAMPLES = ['tilt', 'magnetic', 'ripple', 'neonPulse', 'gradientBorder', 'glassSpecular', 'skeleton']
    before = p.evaluate("""(ns) => ns.map((n) => { const e = __fxLab.hosts[n]; return [n, e.getAttribute('style') || '', e.className, e.children.length]; })""", SAMPLES)
    p.evaluate("() => { ['tilt', 'magnetic', 'ripple', 'neonPulse', 'gradientBorder', 'glassSpecular', 'skeleton'].forEach((n) => __fxLab.run(n)); }")
    p.evaluate("() => __fxLab.hosts.tilt.scrollIntoView({ block: 'center' })")
    box = p.evaluate("() => { const r = __fxLab.hosts.tilt.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    p.mouse.move(box[0] + box[2] * 0.9, box[1] + box[3] * 0.2)
    p.wait_for_timeout(500)
    tilt = p.evaluate("() => __fxLab.hosts.tilt.style.transform")
    check("e. tilt: leans toward the pointer (perspective + rotate)", "perspective" in tilt and "rotateY" in tilt, tilt)
    p.evaluate("() => __fxLab.stopAll()")
    after = p.evaluate("""(ns) => ns.map((n) => { const e = __fxLab.hosts[n]; return [n, e.getAttribute('style') || '', e.className, e.children.length]; })""", SAMPLES)
    check("e. stop() puts every sample element back (same inline style, classes and children as before the effect)", before == after, [(b, a) for b, a in zip(before, after) if b != a])
    # toast: a status message, removed when done; confetti / sparks stay inside the canvas caps
    p.evaluate("() => { __fxLab.run('toast'); }")
    p.wait_for_timeout(300)
    t = p.evaluate("() => { const e = document.querySelector('.oly-fx-toast'); return e ? [e.getAttribute('role'), e.textContent] : null; }")
    p.evaluate("() => __fxLab.stopAll()")
    gone = p.evaluate("() => !document.querySelector('.oly-fx-toasts')")
    check("e. toast: role=status with its text, gone after stop", t and t[0] == "status" and "Order filled" in t[1] and gone, (t, gone))
    p.evaluate("() => { __fxLab.run('confetti'); }")
    p.wait_for_timeout(200)
    cv = p.evaluate("() => OLYMPUS_FX.stats().canvases")      # (the sample button may be scrolled off screen: the burst starts from the screen's edge)
    p.evaluate("() => __fxLab.stopAll()")
    check("e. confetti: one full-screen canvas under the high caps (<= 1.5 px per px, <= 1.1 MP)", len(cv) == 1 and cv[0]["dpr"] <= 1.52 and cv[0]["px"] <= 1_100_000, cv)
    check("e. no error", not errs, errs[:3])
    ctx.close()


def test_wiring(br, origin):
    ctx, p, errs, off, reqs = new_page(br, origin, "?bare=1&stage=still&small=1")
    until(p, "() => window.OLYMPUS_FX && OLYMPUS_FX.stats().byName.odometer && OLYMPUS_FX.stats().byName.tilt && OLYMPUS_FX.stats().byName.ripple")
    p.wait_for_timeout(300)
    got = {f for f in WIRE_FILES if any(u.split("?")[0].endswith("/" + f) for u in reqs)}
    check("g. the wiring loads only what the attributes need (core + ui + text; not burst or the 3D files)", got == {"fx-core.js", "fx-ui.js", "fx-text.js"}, got)
    by = p.evaluate("() => OLYMPUS_FX.stats().byName")
    check("g. tilt, ripple and odometer wired (shimmer / glow are CSS and need no script)", by.get("tilt") == 1 and by.get("ripple") == 1 and by.get("odometer") == 1 and "shimmer" not in by and "glow" not in by, by)
    css = p.evaluate("""() => { const a = getComputedStyle(document.getElementById('wire-shimmer'), '::after'), g = getComputedStyle(document.getElementById('wire-glow'));
      const o = getComputedStyle(document.getElementById('wire-off'), '::after'), og = getComputedStyle(document.getElementById('wire-off'));
      return { shim: a.content, anim: a.animationName, pos: getComputedStyle(document.getElementById('wire-shimmer')).position, glow: g.animationName,
        offShim: o.content, offGlow: og.animationName }; }""")
    check("g. shimmer and glow animate from the CSS alone", css["shim"] == '""' and css["anim"] == "oly-fx-sweep" and css["glow"] == "oly-fx-glow" and css["pos"] == "relative", css)
    check("g. opt-out: data-oly-fx-off on an ancestor switches the CSS effects off", css["offShim"] in ("none", "normal") and css["offGlow"] == "none", css)
    p.evaluate("() => document.getElementById('wire-tilt').scrollIntoView({ block: 'center' })")
    r = p.evaluate("() => { const r = document.getElementById('wire-tilt').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    p.mouse.move(r[0] + r[2] * 0.85, r[1] + r[3] * 0.25)
    until(p, "() => document.getElementById('wire-tilt').style.transform.includes('perspective')")
    tf = p.evaluate("() => document.getElementById('wire-tilt').style.transform")
    check("g. data-oly-fx=tilt leans on a plain element", "perspective" in tf, tf)
    p.evaluate("() => document.getElementById('wire-ripple').scrollIntoView({ block: 'center' })")
    r = p.evaluate("() => { const r = document.getElementById('wire-ripple').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    p.mouse.move(r[0] + 20, r[1] + 20)
    p.mouse.down()
    p.wait_for_timeout(120)
    rip = p.evaluate("() => { const e = document.getElementById('wire-ripple'); return [e.classList.contains('oly-fx-rip-go'), e.style.getPropertyValue('--oly-ox'), getComputedStyle(e, '::before').animationName]; }")
    p.mouse.up()
    check("g. data-oly-fx=ripple starts a ring at the tap point", rip[0] and rip[1] and rip[2] == "oly-fx-rip", rip)
    p.evaluate("() => { document.getElementById('wire-odo').textContent = '2,006.4'; }")
    p.wait_for_timeout(100)
    mid = p.evaluate("() => document.getElementById('wire-odo').querySelectorAll('.oly-odo-c').length")
    until(p, "() => !document.getElementById('wire-odo').querySelector('.oly-odo')")
    end = p.evaluate("() => document.getElementById('wire-odo').innerHTML")
    check("g. data-oly-fx=odometer rolls an ordinary textContent write, then plain text again", mid >= 3 and end == "2,006.4", (mid, end))
    # later-added elements, removal, the opt-outs
    p.evaluate("""() => { const b = document.createElement('button'); b.id = 'late'; b.setAttribute('data-oly-fx', 'ripple'); b.textContent = 'late'; document.body.appendChild(b);
      const o = document.createElement('div'); o.setAttribute('data-oly-fx-off', ''); const c = document.createElement('button'); c.id = 'optout'; c.setAttribute('data-oly-fx', 'ripple'); o.appendChild(c); document.body.appendChild(o);
      const d = document.createElement('button'); d.id = 'self'; d.setAttribute('data-oly-fx', 'ripple'); d.setAttribute('data-oly-fx-off', ''); document.body.appendChild(d); }""")
    until(p, "() => OLYMPUS_FX.stats().byName.ripple === 2")
    by = p.evaluate("() => OLYMPUS_FX.stats().byName")
    check("g. an element added later is wired; elements under data-oly-fx-off (ancestor or itself) are not", by.get("ripple") == 2, by)
    p.evaluate("() => { document.getElementById('late').remove(); }")
    until(p, "() => OLYMPUS_FX.stats().byName.ripple === 1")
    by = p.evaluate("() => OLYMPUS_FX.stats().byName")
    check("g. a removed element's effect is stopped", by.get("ripple") == 1, by)
    p.evaluate("() => { document.getElementById('self').removeAttribute('data-oly-fx-off'); }")
    until(p, "() => OLYMPUS_FX.stats().byName.ripple === 2")
    by = p.evaluate("() => OLYMPUS_FX.stats().byName")
    check("g. taking data-oly-fx-off away wires the element", by.get("ripple") == 2, by)
    p.evaluate("() => OLYMPUS.fxUI(false)")
    until(p, "() => OLYMPUS_FX.stats().active === 0")
    s = p.evaluate("() => ({ active: OLYMPUS_FX.stats().active, attr: document.documentElement.getAttribute('data-oly-fx-ui'), shim: getComputedStyle(document.getElementById('wire-shimmer'), '::after').content })")
    check("g. OLYMPUS.fxUI(false): every wired effect stops and the CSS ones go off", s["active"] == 0 and s["attr"] == "off" and s["shim"] in ("none", "normal"), s)
    p.evaluate("() => OLYMPUS.fxUI(true)")
    until(p, "() => OLYMPUS_FX.stats().active >= 4")
    s = p.evaluate("() => OLYMPUS_FX.stats().active")
    check("g. OLYMPUS.fxUI(true) brings them back (%d wired)" % s, s >= 4, s)
    p.evaluate("() => { document.documentElement.setAttribute('data-fx', 'off'); }")
    sh = p.evaluate("() => getComputedStyle(document.getElementById('wire-shimmer'), '::after').content")
    p.evaluate("() => { document.documentElement.setAttribute('data-fx', 'low'); }")
    lo = p.evaluate("() => { const a = getComputedStyle(document.getElementById('wire-shimmer'), '::after'); return [a.animationName, a.opacity]; }")
    check("g. tiers in CSS: low = a still sheen (no animation), off = nothing", sh in ("none", "normal") and lo[0] == "none" and float(lo[1]) < 1, (sh, lo))
    check("g. no error on the wiring page", not errs, errs[:3])
    ctx.close()
    # no attribute, no file: a page without data-oly-fx, with effects off, and with reduced motion
    ctx, p, errs, off, reqs = new_page(br, origin, "?bare=1&stage=still&small=1", fx="off")
    p.wait_for_timeout(2500)
    check("g. effects off in the kit: no fx file is requested", not [u for u in reqs if "/fx-" in u.split("?")[0] and "fx-lab" not in u], [u for u in reqs if "/fx-" in u])
    ctx.close()
    ctx, p, errs, off, reqs = new_page(br, origin, "?bare=1&stage=still&small=1", reduced=True)
    p.wait_for_timeout(2500)
    check("g. reduced motion: no fx file is requested", not [u for u in reqs if "/fx-" in u.split("?")[0] and "fx-lab" not in u], [u for u in reqs if "/fx-" in u])
    ctx.close()
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    reqs2: list = []
    ctx.route("**/*", lambda r: (reqs2.append(r.request.url), r.continue_())[1] if r.request.url.startswith(origin) else r.abort())
    p = ctx.new_page()
    p.goto(origin + "/olympus/render-lab.html?q=off")
    p.wait_for_timeout(3000)
    check("g. a page without data-oly-fx loads no fx file (the kit costs nothing there)", not [u for u in reqs2 if "/fx-" in u], [u for u in reqs2 if "/fx-" in u])
    ctx.close()


# ------------------------------------------------------------------ h. the cinema stack (olympus/fx-cine.js + the render core's post, 2026-11-11)
SCENE_HOOKS = {"symposium/hall.js": "focus", "ergasterion/floor.js": "sparks", "colosseum/arena.js": "laurel", "cities/athens.js": "birds",
               "cities/hellas.js": "sand", "jarvis/home3d.js": "fireflies"}
# Round 4 budgets per scene: high <= 45 draw calls / 160k triangles, LITE <= 28 / 80k (measured on the lab stage with the whole stack on)
BUDGET = {"ultra": (45, 160_000), "high": (45, 160_000), "low": (28, 80_000)}


def hexes(text):
    return [h for h in re.findall(r"['\"]#([0-9a-fA-F]{6})['\"]", text)]


def neon(h):
    """a neon colour: very saturated AND very bright in the cool / acid hues (green, cyan, blue, violet, magenta); warm fire hues are allowed"""
    import colorsys
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s > 0.75 and v > 0.8 and 75 <= hue * 360 <= 335


def test_cinema_static():
    cine = read(os.path.join(KIT, "fx-cine.js"))
    render = read(os.path.join(KIT, "render.js"))
    check("h. fx-cine.js: the stack (cinema, burst, focus, setTime) with ultra / high / low / off tiers, fixed pools, every piece one draw",
          all(x in cine for x in ("export function cinema(", "burst(kind, at, bo)", "focus(target, fo)", "setTime(t, ms)", "export const TIER", "export const POOL",
                                  "ultra:", "high:", "low:", "off:", "InstancedBufferGeometry", "PCFSoftShadowMap")))
    tier = {m.group(1): m.group(2) for m in re.finditer(r"^\s+(ultra|high|low|off): \{ (shadow: .*?) \},?$", cine, re.M)}
    nums = {k: dict((a, float(b)) for a, b in re.findall(r"(\w+): ([0-9.]+)", v)) for k, v in tier.items()}
    check("h. tiers: shadow maps only on high / ultra (2048 / 1024), LITE has none and no focus blur, off has no particles / birds / pool",
          nums.get("ultra", {}).get("shadow") == 2048 and nums.get("high", {}).get("shadow") == 1024 and nums.get("low", {}).get("shadow") == 0
          and nums.get("low", {}).get("focus") == 0 and nums.get("off", {}).get("particles") == 0 and nums.get("off", {}).get("pool") == 0
          and nums.get("off", {}).get("birds") == 0 and nums["ultra"]["pool"] >= nums["high"]["pool"] >= nums["low"]["pool"], nums)
    pool = re.search(r"POOL = Object\.freeze\(\{ particles: (\d+), burst: (\d+) \}\)", cine)
    check("h. the pools are bounded: <= 2000 particles a piece, <= 420 burst slots a draw, and every tier's pool fits under it",
          pool and int(pool.group(1)) <= 2000 and int(pool.group(2)) <= 420 and all(v.get("pool", 0) <= int(pool.group(2)) for v in nums.values()), pool and pool.groups())
    bad = [h for h in hexes(cine) + hexes(render.split("export const GRADES")[1].split("export function makeEnvironment")[0]) if neon(h)]
    check("h. no neon colour in the cinema stack or the colour grades (AGORA: gold, bronze, olive, terracotta, aegean, fire)", not bad, bad)
    m = re.search(r"BLOOM_MAX = ([0-9.]+)", render)
    strengths = [float(x) for x in re.findall(r"bloom: \{ strength: ([0-9.]+)", render)]
    check("h. render core: bloom capped at .25 (BLOOM_MAX, every tier, setBloom and app overrides go through capBloom)",
          m and float(m.group(1)) <= 0.25 and strengths and max(strengths) <= 0.25 and render.count("capBloom(") >= 2, (m and m.group(1), strengths))
    check("h. render core: the post stays ONE finish pass (LUT grade, focus blur, AgX are defines in it, no new Pass class)",
          "#ifdef LUT" in render and "#ifdef DOF" in render and "AGX_TONE_MAPPING" in render and render.count("extends Pass") == 1
          and "setGrade(gr)" in render and "setFocus(f)" in render and "onFrame(fn)" in render and "onTier(fn)" in render)
    miss = []
    for f, word in SCENE_HOOKS.items():
        s = read(os.path.join(WEB, f))
        if "FX HOOK" not in s or "import('../olympus/fx-cine.js')" not in s or ".catch(" not in s.split("import('../olympus/fx-cine.js')")[1][:1400] or word not in s:
            miss.append(f)
    check("h. the scene hooks are in (Symposium, Ergasterion, Colosseum, Athens, Hellas, Jarvis home), marked FX HOOK, loaded lazily and optional (.catch)", not miss, miss)
    tr = read(os.path.join(WEB, "jarvis", "transitions.js"))
    lm = re.search(r"LEVEL_MS = (\d+)", tr)
    check("h. transitions: marble door, scroll unroll and camera fly-through kinds, level() for in-app levels in <= 600 ms, reduced motion = the fade",
          all(f"  {k}: {{" in tr for k in ("door", "scroll", "flythrough")) and "export function level(" in tr and lm and int(lm.group(1)) <= 600
          and "clamp(entry.ms, 300, 600)" in tr and "FADE_STATIC" in tr)


CINE_RUN = """async ([tier, extra]) => {
  const L = __fxLab, rc = L.rc, frames = %s;
  const count = (o) => { let n = 0; o.traverse(() => n++); return n; };
  rc.render(); await frames(2);
  const b = { kids: count(L.scene), g: rc.renderer.info.memory.geometries };
  const st = L.cine(true, extra || {});
  for (let i = 0; i < 4; i++) { rc.render(); await frames(1); }
  let worst = { calls: 0, triangles: 0 };
  for (let i = 0; i < 8; i++) { rc.render(); const s = rc.stats(); if (s.calls > worst.calls) worst = { calls: s.calls, triangles: s.triangles }; await frames(1); }
  const cs = L.cineState(), lab = window.__olyCine.list();
  return { b, st, cs, worst, rs: rc.stats(), post: rc.post(), lab };
}""" % FRAMES


def lum_stats(p):
    # rc.draw() always draws (rc.render() skips a frame inside the governor's frame gap, and then the WebGL buffer read here is empty:
    # mean 0 under load); the read is in the same task as the draw, so it sees that frame
    return p.evaluate("""() => { const c = document.getElementById('stage'), rc = __fxLab.rc; if (rc.draw) rc.draw(); else rc.render(); const g = document.createElement('canvas'); g.width = 78; g.height = 60;
      const x = g.getContext('2d', { willReadFrequently: true }); x.drawImage(c, 0, 0, 78, 60); const d = x.getImageData(0, 0, 78, 60).data; let s = 0, s2 = 0, n = d.length / 4;
      for (let i = 0; i < d.length; i += 4) { const l = (d[i] + d[i + 1] + d[i + 2]) / 3; s += l; s2 += l * l; } const m = s / n; return [m, Math.sqrt(Math.max(0, s2 / n - m * m))]; }""")


def test_cinema(br, origin):
    shots = os.path.join(ROOT, "docs", "shots", "effects")
    os.makedirs(shots, exist_ok=True)
    for tier in ("high", "low", "ultra", "off"):
        ctx, p, errs, off, _ = new_page(br, origin, f"?q={tier}&time=golden", fx=tier)
        r = p.evaluate(CINE_RUN, [tier, {}])
        cs, worst = r["cs"], r["worst"]
        if tier in BUDGET:
            calls, tris = BUDGET[tier]
            check(f"h. {tier}: the whole stack inside the Round 4 budget ({worst['calls']} draw calls <= {calls}, {worst['triangles']:,} triangles <= {tris:,}; post passes included)",
                  0 < worst["calls"] <= calls and worst["triangles"] <= tris, (worst, cs))
        check(f"h. {tier}: the stack follows the tier (shadow map {cs['shadowMap']}, {cs['particles']} particles, {cs['poolSlots']} burst slots), grade '{r['rs']['grade']}'",
              cs["tier"] == tier and cs["shadowMap"] == {"ultra": 2048, "high": 1024}.get(tier, 0) and cs["particles"] <= 4000
              and cs["poolSlots"] <= 840 and (cs["poolSlots"] == 0) == (tier == "off") and r["rs"]["grade"] == "golden" and not cs["error"], cs)
        if tier in ("high", "low"):
            spam = p.evaluate("""async () => { const L = __fxLab; let n = 0; const c = window.__olyCine; for (let i = 0; i < 60; i++) n += (L.cineBurst || ((k, a) => 0))('coins', [0, 1, 0]);
              for (let i = 0; i < 6; i++) { L.rc.render(); await new Promise((r) => setTimeout(r, 16)); } return c.list()[0]; }""")
            check(f"h. {tier}: 60 coin bursts in a row stay inside the fixed pool ({spam['live']} live <= {spam['poolSlots']} slots), no allocation grows it",
                  spam["live"] <= spam["poolSlots"] and spam["bursts"] >= 60, spam)
            f = p.evaluate("""async () => { const L = __fxLab; const ok = L.cineFocus(L.orb); for (let i = 0; i < 30; i++) { L.rc.render(); await new Promise((r) => setTimeout(r, 16)); }
              return [ok, L.rc.post()]; }""")
            check(f"h. {tier}: the speaker focus {'blurs the background (dof ' + str(round(f[1]['dof'], 2)) + ')' if tier == 'high' else 'is off on LITE (no blur pass, no cost)'}",
                  (f[0] is True and f[1]["dof"] > 0.5) if tier == "high" else (f[0] is False and f[1]["dof"] == 0), f)
            t = p.evaluate("() => { const c = __fxLab.cineSetTime('night'); __fxLab.rc.render(); return [__fxLab.rc.stats().grade, window.__olyCine.list()[0].time]; }")
            check(f"h. {tier}: setTime('night') moves the light and the grade to night", t == ["night", "night"], t)
            b = p.evaluate("() => { __fxLab.rc.setBloom({ strength: 0.9 }); return __fxLab.rc.stats().bloomStrength; }")
            check(f"h. {tier}: an app asking for bloom .9 gets <= .25 ({b})", b <= 0.25, b)
            p.evaluate("() => __fxLab.cineSetTime('golden')")
            m, sd = lum_stats(p)
            p.screenshot(path=os.path.join(shots, f"lab-{tier}-golden.jpg"), type="jpeg", quality=60)
            check(f"h. {tier}: 390 x 844 screenshot is not blank (mean {m:.0f}, contrast {sd:.0f}) -> docs/shots/effects/lab-{tier}-golden.jpg", m > 25 and sd > 8, (m, sd))
        a = p.evaluate("""async () => { const L = __fxLab; L.cine(false); L.rc.render(); await new Promise((r) => setTimeout(r, 30)); L.rc.render();
          let n = 0; L.scene.traverse(() => n++); return { kids: n, g: L.rc.renderer.info.memory.geometries, live: window.__olyCine.list().length }; }""")
        check(f"h. {tier}: dispose() leaves nothing (scene objects {r['b']['kids']} -> {a['kids']}, geometries {r['b']['g']} -> {a['g']})",
              a["kids"] == r["b"]["kids"] and a["g"] <= r["b"]["g"] and a["live"] == 0, (r["b"], a))
        check(f"h. {tier}: no page error, console error or warning, nothing off the site", not errs and not off, (errs[:4], off[:3]))
        ctx.close()
    # reduced motion: the look stays, nothing moves, no burst
    ctx, p, errs, off, _ = new_page(br, origin, "?q=high&time=golden", reduced=True)
    r = p.evaluate(CINE_RUN, ["high", {}])
    z = p.evaluate("() => [__fxLab.cineBurst('sparks', [0, 1, 0]), window.__olyCine.list()[0]]")
    check("h. reduced motion: the stack keeps its still look (sky, light, grade) but no burst pool, no burst, nothing moves",
          r["cs"]["reduced"] is True and "sky" in r["cs"]["pieces"] and r["cs"]["poolSlots"] == 0 and z[0] == 0 and r["rs"]["grade"] == "golden", (r["cs"], z))
    check("h. reduced motion: no error", not errs, errs[:4])
    ctx.close()
    # transitions: the cinematic three play under 600 ms and end clear; reduced motion gets the flat fade
    for reduced in (False, True):
        ctx, p, errs, off, _ = new_page(br, origin, "?bare=1", reduced=reduced)
        res = p.evaluate("""async () => { const T = await import('../jarvis/transitions.js'); document.documentElement.dataset.fx = 'high'; const out = {};
          for (const k of T.LEVEL_KINDS) { const m = T.level(k, { glyph: 'Σ' }); await new Promise((r) => setTimeout(r, 1100));
            out[k] = { mode: m, dur: window.__jarvisTransitions.dur, ms: window.__jarvisTransitions.ms, active: window.__jarvisTransitions.active, err: window.__jarvisTransitions.error,
              left: !!document.querySelector('.jtrans, .jtrans-fade') }; }
          return out; }""")
        if not reduced:
            check("h. transitions door / scroll / flythrough: each plays for <= 600 ms (560) and ends fully clear, no error",
                  all(v["mode"] == "warp" and v["dur"] <= 600 and 0 < v["ms"] <= 600 + 900 and not v["active"] and not v["err"] and not v["left"] for v in res.values()), res)
        else:
            check("h. transitions with reduced motion: the 200 ms flat fade for every level kind", all(v["mode"] == "fade" and v["dur"] == 200 and not v["left"] for v in res.values()), res)
        ctx.close()


# ------------------------------------------------------------------ env-kit (2026-11-11, the environment art pass)
ASSETS = os.path.join(WEB, "assets")
ENV_NODE = r"""
import * as K from '%s';
const out = {};
const kit = K.envKit({ tier: 'high' }), lite = K.envKit({ tier: 'low' });
const B = kit.builder();
B.column({ x: 0, z: 0, h: 4, r: 0.3 }); B.column({ x: 2, z: 0, h: 4, r: 0.3 });
B.steps({ x: 0, z: 0, w: 4, d: 3, h: 0.5, n: 3 }); B.entablature({ x: 0, z: 0, y: 4, w: 4 }); B.roof({ x: 0, z: 0, y: 5, w: 4, d: 3 });
B.wall({ x0: -3, z0: 2, x1: 3, z1: 2, door: 0.5 }); B.kline({ x: 0, z: 3, color: '#c96a4a' }); B.table({ x: 1, z: 3 }); B.brazier({ x: -2, z: 3 }); B.anvil({ x: 2, z: 4 });
const g = B.build(null);
out.draws = g.children.length; out.tris = g.userData.stats.tris; out.mats = g.children.map((m) => m.name).sort();
out.allMerged = g.children.every((m) => m.geometry.index && m.geometry.getAttribute('uv') && m.geometry.getAttribute('color'));
const m = kit.mat('marble'), ml = lite.mat('marble'), mu = kit.mat('marble:uv');
out.same = kit.mat('marble') === m; out.fallback = !!(m.userData.ek && m.userData.ek.tEkC.value && m.userData.ek.tEkC.value.image.width === 1);
out.keys = [m.customProgramCacheKey(), ml.customProgramCacheKey(), mu.customProgramCacheKey()];
out.defines = [Object.keys(m.defines || {}), Object.keys(ml.defines || {}), Object.keys(mu.defines || {})];
out.lambert = kit.mat('plaster', { lambert: true, vertexColors: true, dual: 'roof' }).type;
out.shaft = K.shaftGeo({ h: 4, r: 0.3 }).index.count / 3; out.shaftLite = K.shaftGeo({ h: 4, r: 0.3, lite: true }).index.count / 3;
out.tex = K.TEX_NAMES; out.hdri = Object.keys(K.HDRI); out.packs = Object.keys(K.PACKS); out.heroes = Object.values(K.HEROES).map((h) => h.file);
out.packFiles = Object.values(K.PACKS).map((p) => p.file); out.hdriFiles = Object.values(K.HDRI).map((h) => h.file);
out.budget = K.BUDGET;
console.log(JSON.stringify(out));
"""


def test_env_static():
    import subprocess
    import tempfile
    ek = read(os.path.join(KIT, "env-kit.js"))
    lic = read(os.path.join(ROOT, "docs", "ASSETS_LICENSES.md"))
    files = sorted(os.path.relpath(f, WEB).replace(os.sep, "/") for f in glob.glob(os.path.join(ASSETS, "**", "*"), recursive=True) if os.path.isfile(f))
    rows = [ln for ln in lic.splitlines() if ln.startswith("| ") and ("| CC0 |" in ln or "| CC0 1.0 " in ln)]      # the cast row spells out "CC0 1.0 (url)"
    import re as _re
    _stem = lambda f: f.rsplit("/", 1)[-1].rsplit(".", 1)[0]      # the audio block names files by family (arena = arena.ogg + arena.m4a)
    missing = [f for f in files if not any(f.split("assets/", 1)[1].split("/")[-1] in r or f in r
               or (f.startswith("assets/audio/") and (_stem(f) == "manifest" or _re.search(r"[|,] *" + _re.escape(_stem(f)) + r" *(,|\|)", r))) for r in rows)]
    check(f"i. env-kit: every one of the {len(files)} files under assets/ has a CC0 row in docs/ASSETS_LICENSES.md (asset, author, source, licence, files)",
          files and not missing and all(r.count("|") >= 6 for r in rows), missing[:8])
    total = sum(os.path.getsize(os.path.join(WEB, f)) for f in files)
    check(f"i. env-kit: the art stays inside the phone budget: {total / 1048576:.1f} MB for the whole site (<= 25 MB), no raw source packs (only .webp / .glb / .hdr / tex.json, and the sound .ogg / .m4a)",
          total <= 25 * 1048576 and all(f.endswith((".webp", ".glb", ".hdr", "tex.json", ".ogg", ".m4a", "audio/manifest.json")) for f in files), total)
    big = [f for f in files if os.path.getsize(os.path.join(WEB, f)) > 600 * 1024]
    check("i. env-kit: no single file over 600 KB (textures 512 px webp, LITE 256 px; HDRIs 256 x 128; models meshopt + webp)", not big, big)
    check("i. env-kit: CC0 sources only, loaders vendored (three r160, no CDN), the render core takes its HDRI through setEnvironment",
          "polyhaven" in lic.lower() and "kaykit" in lic.lower() and "http" not in re.sub(r"(//[^\n]*|/\*.*?\*/)", "", ek, flags=re.S).replace("import.meta.url", "")
          and all(os.path.exists(os.path.join(KIT, "three-addons", f)) for f in ("GLTFLoader.js", "RGBELoader.js", "BufferGeometryUtils.js", "meshopt_decoder.module.js"))
          and "setEnvironment(tex)" in read(os.path.join(KIT, "render.js")))
    with tempfile.TemporaryDirectory() as td:
        h = os.path.join(td, "env.mjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(ENV_NODE % ("file://" + os.path.join(KIT, "env-kit.js").replace(os.sep, "/")))
        r = subprocess.run(["node", h], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("i. env-kit runs in node", False, (r.stdout[-400:], r.stderr[-800:]))
        return
    check(f"i. the builder merges a whole temple (columns, steps, entablature, roof, a wall with a door, a couch, a table, a brazier, an anvil) into ONE draw per material: {o['draws']} draws, {o['tris']} triangles",
          o["draws"] == len(set(o["mats"])) <= 12 and o["tris"] < 12000 and o["allMerged"] and "ek:marble:uv" in o["mats"] and "ek:roof:uv" in o["mats"], o)
    check("i. materials are cached per key, start on a 1 px fallback (never blank when a file fails), triplanar on HD, one tap + no normal map on LITE, mesh UVs on ':uv'",
          o["same"] and o["fallback"] and not [d for d in o["defines"][0] if d.startswith("EK_")] and "EK_LITE" in o["defines"][1] and "EK_UV" in o["defines"][2] and len(set(o["keys"])) == 3 and o["lambert"] == "MeshLambertMaterial", o)
    check(f"i. a fluted Doric shaft is {o['shaft']} triangles on HD, {o['shaftLite']} on LITE", o["shaft"] <= 600 and o["shaftLite"] <= 100, (o["shaft"], o["shaftLite"]))
    exist = [f for f in o["packFiles"] + o["hdriFiles"] + o["heroes"] if not os.path.exists(os.path.join(ASSETS, f))]
    texmiss = [t for t in o["tex"] for sfx in ("_c.webp", "_n.webp", "_l.webp") if not os.path.exists(os.path.join(ASSETS, "tex", t + sfx))]
    check(f"i. every file the kit names exists: {len(o['tex'])} surfaces x 3, {len(o['hdri'])} HDRIs, {len(o['packs'])} prop packs, {len(o['heroes'])} hero models",
          not exist and not texmiss, (exist, texmiss))
    check("i. the budgets the scenes are held to: <= 45 draws / 160k triangles on high, <= 28 / 80k on LITE",
          o["budget"]["high"]["draws"] == 45 and o["budget"]["high"]["tris"] == 160000 and o["budget"]["low"]["draws"] == 28 and o["budget"]["low"]["tris"] == 80000, o["budget"])


def test_env(br, origin):
    """the env lab on high, LITE and with no asset at all (the fallback): no error, the art loads, inside the budgets, never blank"""
    for q, extra in (("high", ""), ("low", ""), ("high", "&noassets=1")):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
        ctx.add_init_script("try { localStorage.setItem('jfx', '%s'); } catch (e) {}" % q)
        p = ctx.new_page()
        errs: list = []
        p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "GL Driver" not in m.text else None)
        p.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
        p.goto(f"{origin}/olympus/env-lab.html?q={q}&time=golden{extra}")
        try:
            p.wait_for_function("() => window.ENV_LAB", timeout=60000)
            p.evaluate("() => window.ENV_LAB.ready")
            p.wait_for_timeout(2500)
            import io
            from PIL import Image, ImageStat
            # the picture: a few drawn frames after the files are in (a loaded machine can show a frame still being composed): look
            # again for up to 15 s until it is not blank; a scene that never draws stays at a flat contrast and fails below
            t_end = time.time() + 15
            while True:
                px = sum(ImageStat.Stat(Image.open(io.BytesIO(p.screenshot())).convert("L").resize((60, 130))).stddev)
                if px > 12 or time.time() > t_end:
                    break
                p.wait_for_timeout(500)
            m = p.evaluate("() => window.ENV_LAB.measure()")
            lim = (45, 160000) if q == "high" else (28, 80000)
            real = [e for e in errs if "favicon" not in e and "Failed to load resource" not in e]
            check(f"i. env lab {q}{' (no assets: the fallback colours)' if extra else ''}: {m['draws']} draws, {m['tris']} triangles (<= {lim[0]} / {lim[1]}), {m['files']} files loaded, "
                  f"texture memory about {m['texMB']} MB, env {m['env']}, not blank (contrast {px:.0f}), no error",
                  m["draws"] <= lim[0] and m["tris"] <= lim[1] and not m["failed"] and px > 12 and not real and (m["files"] > 5 if not extra else True)
                  and m["env"] == ("gradient" if q == "low" else "golden" if not extra else m["env"]) and m["texMB"] <= (40 if q == "high" else 12), (m, real[:3]))
        finally:
            ctx.close()


def main():
    from playwright.sync_api import sync_playwright
    test_static()
    test_cinema_static()
    test_env_static()
    srv, origin = serve()
    with sync_playwright() as pw:
        br = launch(pw)
        # python -X utf8 -m tests.test_olympus_fx [every reduced hidden live visible marble elements wiring cinema env]: run some sections only
        want = [a for a in sys.argv[1:] if not a.startswith("-")]
        for fn in (test_every_effect, test_reduced, test_hidden, test_live_tiers, test_visible, test_marble, test_elements, test_wiring, test_cinema, test_env):
            if want and fn.__name__.replace("test_", "").split("_")[0] not in want:
                continue
            try:
                fn(br, origin)
            except Exception as e:  # a crashed section is a failed check, and the rest still run
                check(f"{fn.__name__} ran to the end", False, repr(e)[:600])
        br.close()
    srv.shutdown()
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
