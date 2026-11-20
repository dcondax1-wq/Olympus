"""PANEL FX (tools/web_public/trading/panelfx.js + .css, day-a11y 2026-11-20, owner: "It needs some 3D, it needs some effects"):
Trading, Business (index, accounts, mffu) and Planner.

    python -X utf8 -m tests.test_panelfx            (--static: no browser)
a. static: the effects load after the content (defer, at the end of body, the css injected by the script), the navy look on Trading +
   Business (nq/nqtheme.css), the Planner has no gold token left, no network / storage in the layer
b. browser 390 x 844: the aurora runs (2D canvas, fixed, behind), cards are glass, chart lines glow, nothing moves the layout (the cards'
   boxes are the same before and after the effects), no sideways scroll; reduced motion: one still frame, no reveal hiding a card
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PAGES = {"trading/": "nq", "business/": "nq", "business/accounts.html": "nq", "business/mffu.html": "nq", "planner/": "planner"}
FAILS: list = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:300]}]"))
    if not ok:
        FAILS.append(name)


def read(p):
    with open(os.path.join(WEB, p), encoding="utf-8") as fh:
        return fh.read()


def static():
    js, css = read("trading/panelfx.js"), read("trading/panelfx.css")
    for page, look in PAGES.items():
        html = read(page + ("index.html" if page.endswith("/") else ""))
        tag = re.search(r'<script src="(?:\.\./trading/)?panelfx\.js\?v=\d+" data-look="(\w+)"[^>]*defer></script>', html)
        check(f"a. {page}: panelfx.js deferred at the end of the body, look '{look}'", bool(tag) and tag.group(1) == look and html.index("panelfx.js") > html.index("</main>"))
        check(f"a. {page}: no render-blocking effects stylesheet (panelfx.js adds it after the paint)", "panelfx.css" not in html)
        if look == "nq":
            check(f"a. {page}: the navy trading-terminal look (nq/nqtheme.css) loaded last in <head>", '../nq/nqtheme.css' in html and html.index("nqtheme.css") > html.index("agora.css") and html.index("nqtheme.css") < html.index("</head>"))
    pl = read("planner/planner.css")
    check("a. planner: the kit's gold tokens point at its sea blue (no gold)", "--ag-gold: #7fa7c2 !important" in pl and "--oly-th-a8: #7fa7c2 !important" in pl)
    check("a. planner sundial: no gold left in the drawing", not re.search(r"#c8a24a|#e0b060", read("planner/plannerscene.js")))
    check("a. the layer: no network, no storage, no innerHTML", not re.search(r"fetch\(|XMLHttpRequest|localStorage|sessionStorage|innerHTML", js))
    check("a. the layer: reduced motion honoured (JS still frame + CSS)", "prefers-reduced-motion" in js and "prefers-reduced-motion" in css and "st.aurora = 'still'" in js)
    check("a. the aurora is out of the layout before its css lands (inline position:fixed)", "position:fixed" in js)


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP browser: no Python playwright")
        return
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    from tests import agora_kit as AK
    srv, origin = AK.serve()
    # the layout boxes (offsetTop chain: a reveal's translateY is paint, not layout, and never a layout shift)
    BOX = "() => [...document.querySelectorAll('main .ag-card, main .card')].slice(0, 8).map(c => { let y = 0; for (let e = c; e; e = e.offsetParent) y += e.offsetTop; return [y, c.offsetHeight]; })"
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for page, look in PAGES.items():
                for rm in ("no-preference", "reduce"):
                    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion=rm, service_workers="block")
                    ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
                    p = ctx.new_page()
                    errs = []
                    p.on("pageerror", lambda e: errs.append(str(e)))
                    p.goto(f"{origin}/{page}", wait_until="load")
                    p.wait_for_function("window.PANELFX && PANELFX.state().aurora !== 'none'", timeout=15000)
                    p.wait_for_timeout(1200)
                    s = p.evaluate("PANELFX.state()")
                    if rm == "reduce":
                        hidden = p.evaluate("() => [...document.querySelectorAll('.pfx-wait')].filter(c => getComputedStyle(c).opacity !== '1').length")
                        check(f"b. {page} reduced motion: the aurora is one still frame, no card hidden for a reveal", s["aurora"] == "still" and s["frames"] == 0 and hidden == 0, (s, hidden))
                        ctx.close()
                        continue
                    check(f"b. {page}: no page error, the aurora runs behind the cards (fixed canvas, look {look})",
                          not errs and s["aurora"] == "live" and s["look"] == look and p.evaluate("getComputedStyle(document.querySelector('.pfx-aurora')).position") == "fixed", (errs, s))
                    glass = p.evaluate("() => { const c = document.querySelector('main .ag-card, main .card'); return c ? getComputedStyle(c).boxShadow : ''; }")
                    check(f"b. {page}: cards are glass with a glow", "rgba" in glass and glass != "none", glass)
                    before = p.evaluate(BOX)
                    p.evaluate("PANELFX.stop(); document.documentElement.classList.remove('pfx'); document.querySelectorAll('.pfx-wait').forEach(c => c.classList.remove('pfx-wait', 'pfx-in'))")
                    p.wait_for_timeout(100)
                    after = p.evaluate(BOX)
                    check(f"b. {page}: the effects move nothing (card boxes identical with and without them)", before == after, (before[:3], after[:3]))
                    wide = p.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                    check(f"b. {page}: no sideways scroll", wide <= 1, wide)
                    if page == "trading/":
                        check("b. trading: the chart lines glow (at most 12)", 1 <= s["charts"] <= 12, s)
                    ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    static()
    if "--static" not in sys.argv:
        browser()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
