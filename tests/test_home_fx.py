"""The living home (night-effects 2026-11-20): olympus/home-fx.js + home-fx.css on the Gate (gate/) and the Doors (hub/doors.html).

  a. static: both pages load the layer after shell.css; the JS is ES5-safe (no arrow / let / const / class), one requestAnimationFrame
     loop, device pixels capped at 2, a hidden tab and an off-screen hero stop it; only transform / opacity are animated in the CSS
  b. Chromium 390 x 844: the hero draws (canvas), no sideways scroll, no page error; Right now numbers count up to the exact text
     (?hfx=1), the trade-window ring is there; the loop sleeps once the hero is off screen; reduced motion -> one still frame, no loop;
     'oly.homefx' = 'off' -> no hero at all; the Doors page gets the hero, the glass doors and their emblems

    python tests/test_home_fx.py [--static]
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tests import test_gate_page as GP  # noqa: E402

check = AK.check
JS = os.path.join(AK.WEB, "olympus", "home-fx.js")
CSS = os.path.join(AK.WEB, "olympus", "home-fx.css")


def test_static():
    js, css = AK.read(JS), AK.read(CSS)
    gate, doors = AK.read(os.path.join(AK.WEB, "gate", "index.html")), AK.read(os.path.join(AK.WEB, "hub", "doors.html"))
    check("a. the Gate and the Doors load home-fx.css after shell.css and home-fx.js",
          gate.find("olympus/home-fx.css?v=") > gate.find("olympus/shell.css?v=") > 0 and "'olympus/home-fx.js?v=" in gate
          and doors.find("olympus/home-fx.css?v=") > doors.find("olympus/shell.css?v=") > 0 and "olympus/home-fx.js?v=" in doors)
    code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    check("a. ES5 for Safari 16: no arrow functions, let, const, class, template strings", not re.search(r"=>|\blet\s|\bconst\s|\bclass\s|`", code))
    check("a. one loop: a single requestAnimationFrame(tick) scheduler, DPR capped at 2, visibility + IntersectionObserver stop it",
          code.count("requestAnimationFrame(tick)") == 2 and "Math.min(2, W.devicePixelRatio" in code and "d.hidden" in code and "IntersectionObserver" in code)
    frames = re.findall(r"@keyframes[^{]+\{((?:[^{}]*\{[^{}]*\})*)[^{}]*\}", css)
    props = set(re.findall(r"([a-z-]+)\s*:", " ".join(re.sub(r"\d+%|from|to", "", f) for f in frames)))
    check("a. the keyframes animate only transform and opacity", props <= {"transform", "opacity"}, props)
    check("a. reduced motion stops every effect in the CSS", "@media (prefers-reduced-motion: reduce)" in css and "animation: none !important" in css)


def state(p):
    return p.evaluate("window.OLYMPUS_HOMEFX && window.OLYMPUS_HOMEFX.state()")


def test_browser():
    srv, origin = GP.serve({"/home.json": GP.home_json(300)})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/gate/?now={GP.NOW}&hfx=1")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000, polling=200)
            mid = p.evaluate("[...document.querySelectorAll('#nowFacts .g-fv')].map((e) => e.textContent)")
            p.wait_for_timeout(1600)
            end = p.evaluate("[...document.querySelectorAll('#nowFacts .g-fv')].map((e) => e.textContent)")
            s = state(p)
            check("b. Gate: the hero canvas draws, the loop runs, nothing frozen", s and s["hero"] and s["draws"] > 5 and not s["still"] and p.locator(".hfx-hero canvas").count() == 1, s)
            check("b. Gate: Right now money counts up and lands on the exact text ($1,420 drawdown left, +$272 today)",
                  "$1,420" in end and "+$272" in end and mid != end, (mid, end))
            ring = p.evaluate("(() => { const r = document.querySelector('#nowFacts .hfx-ring'); return r && { win: r.getAttribute('data-win'), off: +r.querySelector('.hfx-rv').getAttribute('stroke-dashoffset') }; })()")
            check("b. Gate: the trade-window ring sits on the open window (part used)", ring and ring["win"] == "open" and 0 < ring["off"] < 76, ring)
            check("b. Gate: the 'Bots on' badge pulses (live)", p.evaluate("getComputedStyle(document.querySelector('#nowBadge'), '::after').animationName") == "hfx-ping")
            check("b. Gate: four glass doors, each with its emblem and its light", p.locator(".g-dr .hfx-glyph").count() == 4 and p.locator(".g-dr .hfx-lit").count() == 4)
            check("b. Gate: the title still reads Olympus (letters for the intro, one label)", p.evaluate("document.querySelector('.g-title').getAttribute('aria-label')") == "Olympus"
                  and p.evaluate("document.querySelector('.g-title').textContent") == "Olympus")
            check("b. Gate: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            p.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            p.wait_for_timeout(900)
            s = state(p)
            check("b. Gate: the loop sleeps once the hero is off screen", s and not s["running"], s)
            p.evaluate("window.scrollTo(0, 0)")
            p.wait_for_timeout(500)
            check("b. Gate: and wakes when it is back", state(p)["running"])
            check("b. Gate: no page error", not errs, errs)
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            p.goto(f"{origin}/gate/?now={GP.NOW}")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000, polling=200)
            p.wait_for_timeout(600)
            s = state(p)
            check("b. reduced motion: one still frame, no loop", s and s["still"] and not s["running"] and s["draws"] == 1, s)
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, storage={"oly.homefx": "off"})
            p.goto(f"{origin}/gate/?now={GP.NOW}")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000, polling=200)
            check("b. 'oly.homefx' = off: no hero, no layer class", p.locator(".hfx-hero").count() == 0 and not p.evaluate("document.documentElement.classList.contains('hfx')"))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/hub/doors.html#zeus")
            p.wait_for_timeout(1500)
            s = state(p)
            check("b. Doors: hero, four doors with emblems, no sideways scroll, no page error",
                  s and s["hero"] and p.locator(".dr-door .hfx-glyph").count() == 4 and p.evaluate("document.documentElement.scrollWidth <= innerWidth") and not errs, (s, errs))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
