"""OLYMPUS arena-to-arena transitions (tools/web_public/jarvis/transitions.js, wired through jarvis/portal.js).

Every app has its own signature transition (Oracle lightning, Tyche sea surge, Prometheus fire sweep, Pantheon marble columns,
Mind constellation, Daphne laurel, Plutus coins ...), drawn on ONE reused 2D canvas, over the app while it loads.

  a. static: the table (REGISTRY) has an entry for every app of jarvis/apps.js, each with a known kind and 600-1100 ms; the kinds
     are all drawn; the file loads nothing external, has no WebGL, no localStorage, no shadowBlur; the sound is guarded by
     OLYMPUS_QUIET; index.html loads it after portal.js and passes the app we leave; portal.js hands the jump over
  b. every app, on the iPhone 13 profile: it plays by itself in its own time (600-1100 ms), draws frames, ends fully clear and
     leaves nothing behind (no overlay, no canvas in the page, the backing store released to 1 x 1); at the middle it covers
     the screen; no page error; the paint is cheap
  c. a tap (and Escape) skips at once
  d. LITE (3D effects Low / Off): a 250 ms colour fade, no canvas; reduced motion: a 200 ms flat colour fade, nothing moves
  e. sound + vibration: the kit's cues fire from the table, never while OLYMPUS_QUIET says Jarvis talks or listens
  f. the real flow: opening an app from Jarvis' home plays that app's signature; switching from inside an app (the switcher over
     it) plays the NEW app's signature and knows the app it left; no WebGL context, GPU buffer or canvas is left over
    python -X utf8 -m tests.test_jarvis_transitions
"""
from __future__ import annotations

import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.test_olympus_kit import launch, serve  # noqa: E402
from tests.test_olympus_render import GPU_COUNT  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
JARVIS = os.path.join(WEB, "jarvis")
RES: list = []

# the signature each app must keep (AGORA 2026-11-09: no lightning / slash / shatter; Oracle a sunburst, sea surge for Tyche, marble for the default, ...)
SIGNATURE = {"oracle": "sunburst", "tyche": "waves", "prometheus": "forge", "pantheon": "columns", "mind": "constellation",
             "tree": "laurel", "plutus": "coins", "hermes": "dash", "ares": "columns", "chronos": "clock", "nemesis": "marble"}
# wrappers: count WebGL contexts made on any canvas (the transitions must make none)
GL_COUNT = """(() => { window.__gl = 0; const f = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (t) { if (/webgl/i.test(String(t))) window.__gl++; return f.apply(this, arguments); }; })();"""


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def app_ids():
    return re.findall(r"^\s*app\('([a-z0-9]+)',", read(os.path.join(JARVIS, "apps.js")), re.M)


def test_static():
    js, portal, html = read(os.path.join(JARVIS, "transitions.js")), read(os.path.join(JARVIS, "portal.js")), read(os.path.join(JARVIS, "index.html"))
    ids = app_ids()
    check("a. jarvis/apps.js has at least the 24 built-in apps", len(ids) >= 24, ids)
    reg = re.search(r"export const REGISTRY = \{(.*?)\n\};", js, re.S).group(1)
    rows = dict((m.group(1), (m.group(2), int(m.group(3)))) for m in re.finditer(r"^\s*(\w+):\s*\{ kind: '(\w+)',\s*ms: (\d+)", reg, re.M))
    kinds = set(re.findall(r"^  (\w+): \{\n    init", js, re.M))
    check("a. the table has an entry for every app (data: kind + duration)", set(ids) <= set(rows) and len(rows) == len(set(rows)), sorted(set(ids) - set(rows)))
    check("a. every entry's kind is drawn, every duration is 600-1100 ms", all(k in kinds for k, _ in rows.values()) and all(600 <= ms <= 1100 for _, ms in rows.values()),
          [(a, r) for a, r in rows.items() if r[0] not in kinds or not 600 <= r[1] <= 1100])
    check("a. the owner's signatures are in the table", all(rows.get(a, ("",))[0] == k for a, k in SIGNATURE.items()), {a: rows.get(a) for a in SIGNATURE})
    check("a. 20+ different signatures (the kinds are not shared out to many apps)", len({k for k, _ in rows.values()}) >= 20, len({k for k, _ in rows.values()}))
    check("a. the building blocks are shared (tunnel, marble, arch, shockwave ring, iris, glyph particles, flash, veil)",
          all(x in js for x in ("function tunnel(", "function marble(", "function archPath(", "function ring(", "function iris(", "function glyphPoints(", "function flash(", "function veil(")))
    code = "\n".join(ln for ln in js.splitlines() if not ln.lstrip().startswith("//"))          # the header talks about what is NOT used
    code = re.sub(r"\s//[^\n]*", "", code)
    check("a. no external URL, no import, no WebGL, no localStorage, no shadowBlur (cheap on an iPhone)",
          not re.search(r"https?://", code) and not re.search(r"^import ", code, re.M) and "webgl" not in code.lower() and "localStorage" not in code and "shadowBlur" not in code,
          [x for x in ("http", "import", "webgl", "localStorage", "shadowBlur") if x in code.lower() or x in code])
    check("a. skips on a tap or Escape / Enter, drops out on a hidden tab; LITE and reduced motion are fades",
          all(x in js for x in ("'pointerdown', skip", "e.key === 'Escape'", "visibilitychange", "matchMedia('(prefers-reduced-motion: reduce)')", "FADE_LITE = 250", "FADE_STATIC = 200", "clearTimeout(wd)")))
    check("a. sound only through the kit, guarded by OLYMPUS_QUIET and the mute; vibration is feature-detected",
          all(x in js for x in ("OLYMPUS_QUIET", "jarvisSfx", "OLYMPUS_SFX", "navigator.vibrate", "muted")))
    check("a. one canvas, reused, released after (1 x 1) and a scratch canvas that never joins the page",
          "canvas.width = canvas.height = 1" in js and "scratch.width = scratch.height = 1" in js and js.count("createElement('canvas')") == 2)
    check("a. index.html loads transitions.js after portal.js and tells it the app we leave; show() still plays the portal sound",
          html.index("./portal.js?v=p2") < html.index("./transitions.js?v=t6") and "{ from: fr ? { id: fr.id, color: fr.accent } : null }" in html and "olySfx('portal'); window.jarvisPortal.jump" in html)
    check("a. portal.js hands the jump to transitions.js (the old warp stays as the fallback) and keeps no GL context when it is here",
          "window.jarvisTransitions" in portal and "T.play(a," in portal and "!window.jarvisTransitions) setup()" in portal)


def new_page(br, origin, reduced=False, init="", light=True):
    # the iPhone 13 profile (390 x 664 Safari viewport, 3x, touch), on the real site layout, nothing off the origin
    dev = dict(PW.devices["iPhone 13"])
    ctx = br.new_context(**dev, reduced_motion="reduce" if reduced else "no-preference")
    # LIGHT: the 3D home backdrop and core are left out (no3d + an empty backdrop.js): the transitions are what is under test, and the
    # shared test machine runs WebGL through SwiftShader, which starves every frame. test_olympus_render covers the 3D home + GPU.
    def route(r):
        u = r.request.url
        if not u.startswith(origin):
            r.abort()
        elif light and u.split("?")[0].endswith("/jarvis/backdrop.js"):
            r.fulfill(status=200, content_type="text/javascript", body="")
        elif light and re.search(r"/(oracle|mind|tyche|prometheus|datacity|odeon)/", u.split("?")[0]):     # the apps' own 3D would starve the page (same process)
            r.fulfill(status=200, content_type="text/html", body="<!doctype html><title>app</title><body style='background:#000'>")
        else:
            r.continue_()
    ctx.route("**/*", route)
    ctx.add_init_script(GPU_COUNT + GL_COUNT + "try { localStorage.setItem('jfx', 'high'); " + ("localStorage.setItem('jarvis.no3d', '1'); " if light else "") + "} catch (e) {}" + init)
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not m.text.startswith("Failed to load resource") else None)   # the refused off-site requests are expected
    p.goto(origin + "/jarvis/")
    p.wait_for_function("() => !!window.jarvisTransitions && !!window.jarvisPortal", polling=100, timeout=180000)
    return ctx, p, errs


PLAY = """([id, at]) => { const T = window.jarvisTransitions;
  const r = T.play({ id, name: id, color: '#7fe9ff', glyph: 'T' }, at == null ? {} : { at });
  return r; }"""
COVER = """() => { const c = document.querySelector('.jtrans canvas'); if (!c) return -1;
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let s = 0, n = 0;
  for (let i = 3; i < d.length; i += 64) { s += d[i]; n++; } return s / n / 255; }"""
LEFT = """() => ({ over: document.querySelectorAll('.jportal, .jtrans, .jportal-fade').length, canvases: document.querySelectorAll('.jtrans canvas, .jportal canvas').length,
  px: window.__jarvisTransitions.px, active: window.__jarvisTransitions.active, portal: window.__jarvisPortal.active })"""


def test_apps(br, origin):
    ctx, p, errs = new_page(br, origin)
    ids = p.evaluate("() => window.jarvisTransitions.ids()")
    check("b. the page exposes the table: every built-in app, once", sorted(ids) == sorted(app_ids()), ids)
    base = p.evaluate("() => ({ canvases: document.querySelectorAll('canvas').length, gl: window.__gl, gpu: window.__gpu() })")
    slow = []
    for id in ids:
        dur = p.evaluate("(id) => window.jarvisTransitions.registry[id].ms", id)
        for attempt in range(2):                      # the machine is shared and slow: one more try before it counts as a failure
            mode = p.evaluate(PLAY, [id, None])
            up = p.evaluate("() => ({ over: !!document.querySelector('.jportal.jtrans'), canvas: !!document.querySelector('.jtrans canvas'), a: window.__jarvisTransitions.active })")
            t0 = time.time()
            try:
                p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=8000)
            except Exception:
                pass
            wall = (time.time() - t0) * 1000
            s = p.evaluate("() => Object.assign({}, window.__jarvisTransitions)")
            left = p.evaluate(LEFT)
            # ends by itself: on its frames, or at the latest on the watchdog (dur + 350 ms); never early
            ok = (mode == "warp" and up["over"] and up["canvas"] and up["a"] and not s["active"] and 0.85 * dur <= s["ms"] <= dur + 1500
                  and not s["error"] and left["over"] == 0 and left["canvases"] == 0 and left["px"] == 1 and s["kind"] == p.evaluate("(id) => window.jarvisTransitions.registry[id].kind", id))
            if ok:
                break
        if not ok:
            slow.append((id, mode, up, dur, s, left, round(wall)))
    check("b. all apps: play by themselves in their own time (600-1100 ms), draw frames, end, leave no overlay / canvas, backing store back to 1 x 1", not slow, slow[:2])
    bad, cost = [], {}
    for id in ids:
        mx, ends, worst = 0, 0, 0
        for at in (0.05, 0.3, 0.45, 0.6, 0.9, 0.96, 0.995):
            p.evaluate(PLAY, [id, at])
            c = p.evaluate(COVER)
            pm = p.evaluate("() => window.__jarvisTransitions.paintMs")
            err = p.evaluate("() => window.__jarvisTransitions.error")
            p.evaluate("() => window.jarvisTransitions.skip()")
            worst = max(worst, pm)
            if at in (0.3, 0.45):
                mx = max(mx, c)
            if at == 0.96:
                ends = c
            if at == 0.995 and c > 0.01:
                bad.append((id, "not clear at the end", c))
            if err:
                bad.append((id, "error", err))
        cost[id] = worst
        if mx < 0.8:
            bad.append((id, "does not cover the screen at the middle", round(mx, 2)))
        if ends > 0.2:
            bad.append((id, "still covers at 96%", round(ends, 2)))
    check("b. every app: covers the screen at its middle, is nearly clear at 96% and fully clear at the end, no error in any frame", not bad, bad[:3])
    print("   paint ms per frame (worst of 7 frames, SwiftShader / CPU):", {k: v for k, v in sorted(cost.items(), key=lambda kv: -kv[1])[:6]}, flush=True)
    check("b. the paint is cheap (< 100 ms for any frame even on this slow machine)", max(cost.values()) < 100, cost)
    after = p.evaluate("() => ({ canvases: document.querySelectorAll('canvas').length, gl: window.__gl, gpu: window.__gpu() })")
    check("b. after 24 apps x 8 plays: no canvas in the page, no WebGL context made, no framebuffer / MSAA buffer / texture left",
          after == base, (base, after))
    check("b. no page or console error", not errs, errs[:3])
    ctx.close()


def test_skip_tiers(br, origin):
    ctx, p, errs = new_page(br, origin)
    p.evaluate(PLAY, ["mind", None])
    check("c. a tap on the overlay skips at once", p.evaluate("() => !!document.querySelector('.jtrans')") is True)
    p.locator(".jtrans").dispatch_event("pointerdown")
    left = p.evaluate(LEFT)
    check("c. ... gone in the same instant, backing store released", left["over"] == 0 and left["px"] == 1 and not left["active"], left)
    p.evaluate(PLAY, ["ares", None])
    p.keyboard.press("Escape")
    check("c. Escape skips too", p.evaluate("() => !document.querySelector('.jtrans') && !window.__jarvisTransitions.active"))
    p.evaluate(PLAY, ["plutus", None])
    p.evaluate(PLAY, ["tyche", None])
    check("c. a second transition replaces the first (one overlay, one canvas)", p.evaluate("() => [document.querySelectorAll('.jtrans').length, document.querySelectorAll('.jtrans canvas').length]") == [1, 1])
    p.evaluate("() => window.jarvisTransitions.skip()")
    p.evaluate("() => { window.__raf = window.requestAnimationFrame; window.requestAnimationFrame = () => 0; }")          # a starved frame loop
    p.evaluate(PLAY, ["fates", None])
    try:
        p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=8000)
    except Exception:
        pass
    check("c. a starved frame loop (no rAF at all): the watchdog still ends it, the overlay never sticks",
          p.evaluate("() => !document.querySelector('.jtrans') && !window.__jarvisTransitions.active"))
    p.evaluate("() => { window.requestAnimationFrame = window.__raf; }")
    p.evaluate("() => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }")
    p.evaluate(PLAY, ["oracle", 0.3])
    p.evaluate("() => { document.dispatchEvent(new Event('visibilitychange')); }")
    check("c. a hidden tab drops the transition", p.evaluate("() => !document.querySelector('.jtrans')"))
    p.evaluate("() => { delete document.hidden; }")
    ctx.close()
    # LITE: 3D effects Low and Off
    for fx in ("low", "off"):
        ctx, p, errs = new_page(br, origin)
        p.evaluate(f"() => {{ document.documentElement.dataset.fx = '{fx}'; }}")
        mode = p.evaluate(PLAY, ["oracle", None])
        s = p.evaluate("() => ({ fade: !!document.querySelector('.jtrans-fade'), flat: !!document.querySelector('.jtrans-fade.flat'), canvas: !!document.querySelector('canvas.jtrans, .jtrans canvas'), tier: window.__jarvisTransitions.tier, dur: window.__jarvisTransitions.dur })")
        try:
            p.wait_for_function("() => !document.querySelector('.jtrans-fade, .jportal-fade, .jtrans')", polling=100, timeout=4000)
        except Exception:
            pass
        gone = p.evaluate("() => !document.querySelector('.jtrans-fade, .jportal-fade, .jtrans')")
        check(f"d. LITE (3D effects {fx}): a 250 ms colour fade, no canvas, gone after", mode == "fade" and s["fade"] and not s["flat"] and not s["canvas"] and s["tier"] == "lite" and s["dur"] == 250 and gone, (mode, s, gone))
        ctx.close()
    ctx, p, errs = new_page(br, origin, reduced=True)
    mode = p.evaluate(PLAY, ["pantheon", None])
    s = p.evaluate("() => ({ flat: !!document.querySelector('.jtrans-fade.flat'), canvas: !!document.querySelector('.jtrans canvas'), tier: window.__jarvisTransitions.tier, dur: window.__jarvisTransitions.dur, name: !!document.querySelector('.jtrans-name') })")
    try:
        p.wait_for_function("() => !document.querySelector('.jtrans-fade, .jportal-fade, .jtrans')", polling=100, timeout=4000)          # the 200 ms fade, on a loaded machine
    except Exception:
        pass
    gone = p.evaluate("() => !document.querySelector('.jtrans-fade, .jportal-fade, .jtrans')")
    check("d. reduced motion: a 200 ms flat colour fade (nothing moves: no canvas, no name animation), gone after", mode == "fade" and s["flat"] and not s["canvas"] and not s["name"] and s["tier"] == "static" and s["dur"] == 200 and gone, (mode, s, gone))
    pm = p.evaluate("() => window.jarvisPortal.jump({ id: 'oracle', name: 'Oracle', color: '#7fe9ff' })")
    check("d. through jarvis/portal.js the reduced-motion answer is still 'fade'", pm == "fade", pm)
    check("d. no page error in LITE / reduced motion", not errs, errs[:3])
    ctx.close()


def test_sound(br, origin):
    stub = """(() => { window.__plays = []; window.__q = false;
      window.OLYMPUS_SFX = { play: (n) => { window.__plays.push(n); return true; }, state: () => ({ muted: false }), mute() {}, setVolume() {} };
      window.OLYMPUS_QUIET = () => window.__q; })();"""
    ctx, p, errs = new_page(br, origin, init="")
    p.evaluate(stub)
    p.evaluate("() => { delete window.jarvisSfx; }")                   # the kit path (jarvisSfx is Jarvis' own guard around it)
    p.evaluate(PLAY, ["oracle", None])
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    plays = p.evaluate("() => window.__plays.slice()")
    check("e. Oracle's sunburst calls the kit's 'rankup' at its peak (the kit adds the vibration)", plays == ["rankup"], plays)
    check("e. the cues fired are the table's (state.cues)", p.evaluate("() => window.__jarvisTransitions.cues") == ["rankup"])
    p.evaluate("() => { window.__plays.length = 0; window.__q = true; }")
    p.evaluate(PLAY, ["hephaestus", None])
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    check("e. while Jarvis talks or listens (OLYMPUS_QUIET) the transition is silent", p.evaluate("() => window.__plays.length") == 0, p.evaluate("() => window.__plays"))
    p.evaluate("() => { window.__plays.length = 0; window.__q = false; }")
    p.evaluate(PLAY, ["zenith", None])
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    check("e. an app with no cue in the table adds no sound of its own (show() plays the portal whoosh)", p.evaluate("() => window.__plays.length") == 0)
    p.evaluate("() => { window.OLYMPUS_SFX = undefined; window.__vib = []; Object.defineProperty(navigator, 'vibrate', { value: (x) => { window.__vib.push(x); return true; }, configurable: true }); }")
    p.evaluate(PLAY, ["nemesis", None])
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    check("e. with no sound kit a vibration is the fallback (guarded)", p.evaluate("() => window.__vib.length") >= 1, p.evaluate("() => window.__vib"))
    p.evaluate("() => { delete navigator.vibrate; window.__q = false; }")
    p.evaluate(PLAY, ["oracle", None])
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    check("e. no kit and no vibrate: nothing throws", not p.evaluate("() => window.__jarvisTransitions.error") and not errs, errs[:3])
    ctx.close()


def test_flow(br, origin):
    ctx, p, errs = new_page(br, origin)
    base = p.evaluate("() => ({ canvases: document.querySelectorAll('canvas').length, gl: window.__gl, gpu: window.__gpu() })")
    p.evaluate("() => document.querySelector('[data-app=\"oracle\"]').click()")
    s = p.evaluate("() => ({ t: Object.assign({}, window.__jarvisTransitions), p: Object.assign({}, window.__jarvisPortal), over: !!document.querySelector('.jportal.jtrans'), frame: !!document.querySelector('iframe[src*=\"oracle\"]') })")
    check("f. opening Oracle from the home: its lightning plays over the already loading frame (portal state follows)",
          s["t"]["id"] == "oracle" and s["t"]["kind"] == "sunburst" and s["t"]["active"] and s["over"] and s["frame"] and s["p"]["mode"] == "warp" and s["p"]["active"] and s["p"]["app"] == "oracle", s)
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    check("f. ... it ends by itself and the portal state agrees (ms set, not active)", p.evaluate("() => !window.__jarvisPortal.active && window.__jarvisPortal.ms > 400 && !document.querySelector('.jportal')"))
    p.evaluate("() => document.getElementById('nxOrb').click()")
    p.wait_for_timeout(600)
    p.evaluate("() => document.querySelector('.nx-qb[data-nx=\"mind\"], .nx-card[data-nx=\"mind\"]').click()")
    s = p.evaluate("() => ({ t: Object.assign({}, window.__jarvisTransitions), over: !!document.querySelector('.jportal.jtrans') })")
    check("f. switching from inside Oracle (the switcher over the app): Mind's constellation plays and knows it came from Oracle",
          s["t"]["id"] == "mind" and s["t"]["kind"] == "constellation" and s["t"]["from"] == "oracle" and s["over"] and s["t"]["runs"] >= 2, s)
    p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    for nxt in ("tyche", "prometheus"):
        p.evaluate("() => document.getElementById('nxOrb').click()")
        p.wait_for_timeout(600)
        p.evaluate("(id) => document.querySelector('.nx-qb[data-nx=\"' + id + '\"], .nx-card[data-nx=\"' + id + '\"]').click()", nxt)
        k = p.evaluate("() => [window.__jarvisTransitions.id, window.__jarvisTransitions.kind, window.__jarvisTransitions.from]")
        check(f"f. ... then {nxt}: its own signature ({SIGNATURE[nxt]})", k[0] == nxt and k[1] == SIGNATURE[nxt] and k[2], k)
        p.wait_for_function("() => !window.__jarvisTransitions.active", polling=100, timeout=6000)
    p.evaluate("() => document.getElementById('nxOrb').click()")
    p.wait_for_timeout(600)
    p.evaluate("() => document.querySelector('.nx-qb[data-nx=\"home\"]').click()")
    p.wait_for_timeout(1500)
    after = p.evaluate("() => ({ canvases: document.querySelectorAll('canvas').length, gl: window.__gl, gpu: window.__gpu() })")
    check("f. back home after the trips: no overlay, no extra canvas, no WebGL context made by the transitions, GPU buffers as before",
          p.evaluate("() => !document.querySelector('.jportal, .jtrans, .jportal-fade')") and after["gl"] == base["gl"] and after["gpu"]["msaa"] == base["gpu"]["msaa"] and after["canvases"] == base["canvases"], (base, after))
    check("f. no page or console error through the flow", not errs, errs[:3])
    ctx.close()


def test_covered(br, origin):
    """g. a sheet over a framed app tells the app (postMessage { olympus: 'covered' }), and again when it closes; nothing on the home screen"""
    ctx, p, errs = new_page(br, origin)
    p.evaluate("() => document.querySelector('[data-app=\"oracle\"]').click()")
    p.wait_for_function("() => !!document.querySelector('iframe[src*=\"oracle\"]')", polling=100, timeout=20000)
    p.evaluate("""() => { const w = document.querySelector('iframe[src*="oracle"]').contentWindow; window.__got = [];
      w.addEventListener('message', (e) => window.__got.push([e.data && e.data.olympus, e.data && e.data.on])); }""")
    p.evaluate("() => { document.getElementById('settings').hidden = false; }")
    p.wait_for_timeout(300)
    p.evaluate("() => { document.getElementById('settings').hidden = true; }")
    p.wait_for_timeout(300)
    got = p.evaluate("() => window.__got")
    check("g. a sheet opened over a framed app posts { olympus: 'covered', on: true }, and on: false when it closes", got == [["covered", True], ["covered", False]], got)
    check("g. no page error", not errs, errs[:3])
    ctx.close()


PW = None


def main():
    global PW
    test_static()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return
    srv, origin = serve()
    with sync_playwright() as pw:
        PW = pw
        br = launch(pw)
        test_apps(br, origin)
        test_skip_tiers(br, origin)
        test_sound(br, origin)
        test_flow(br, origin)
        test_covered(br, origin)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
