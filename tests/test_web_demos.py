"""AGENCY 3D website demos (tools/web_public/agency/demos/, day-web-demos 2026-11-20): four sellable one-page sites for FICTIONAL local
businesses (restaurant, roofer, car detailer, real estate) + the gallery the owner opens in front of a prospect.
  a. static (no browser): every page is there, one h1, noindex, the "demo / fictional" strip, 555 phone links, the booking sheet, reviews,
     the map, the drawn 2D picture inside the 3D stage, lazy3d.js loads scene.js after paint, scenes import only local files (three r160 from
     jarvis/, RoomEnvironment from olympus/three-addons), no outside host in any src / import, first-load weight < 400 kB per page (the 3D
     comes later), thumbnails < 60 kB, the gallery links the 4 demos with prices, no private names anywhere
  b. Chromium at 390 x 844 (WD_NO_BROWSER=1 skips; run_area takes the browser lock): per demo the 3D stage starts after load (WebGL via
     SwiftShader), no console / page errors, no sideways scroll, layout shift <= 0.02, taps >= 44 px, sentences >= 15 px, nothing asked
     from another host, a pick changes the 3D picture, the booking sheet opens / validates / thanks without sending anything; without WebGL
     the drawn picture stays and the picks / slider still work; reduced motion = no auto-turn; the gallery's client mode hides prices and
     is remembered; "Make it theirs" opens a demo with the prospect's name / town / phone (text only: markup in the name stays text).
    python -X utf8 -m tests.test_web_demos
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "tools" / "web_public"
DEMOS_DIR = WEB / "agency" / "demos"
DEMOS = ["restaurant", "roofer", "detailer", "estate"]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ a. static
def static():
    files = {d: DEMOS_DIR / d / "index.html" for d in DEMOS}
    check("a. the gallery, the shared stage / styles / buttons and 4 demos (page + scene + thumbnail) exist",
          (DEMOS_DIR / "index.html").exists() and all((DEMOS_DIR / f).exists() for f in ("stage.js", "demo.css", "demo.js"))
          and all(files[d].exists() and (DEMOS_DIR / d / "scene.js").exists() and (DEMOS_DIR / d / "thumb.jpg").exists() for d in DEMOS))
    bad = {}
    for d, p in files.items():
        t = read(p)
        probs = []
        if len(re.findall(r"<h1[\s>]", t)) != 1: probs.append("h1")
        if 'name="robots" content="noindex"' not in t: probs.append("noindex")
        if not re.search(r'class="demo-strip"><span data-strip>Demo site · fictional', t): probs.append("strip")
        tels = re.findall(r'href="tel:\+1555010(\d{4})"', t)
        if len(tels) < 2 or any(not x.startswith("01") for x in tels): probs.append("555 tel")
        if not re.search(r'<dialog id="book" class="sheet"', t) or t.count("data-book") < 2 or "nothing is sent" not in t: probs.append("booking")
        if t.count('class="card review"') < 3: probs.append("reviews")
        if not re.search(r'class="map" role="img"', t): probs.append("map")
        st = re.search(r'<div id="stage" class="stage"[^>]*role="img"[^>]*aria-label="[^"]+">\s*<svg class="pic"', t)
        if not st: probs.append("2D picture in the stage")
        if not re.search(r'<script src="\.\./\.\./\.\./olympus/lazy3d\.js\?v=l2" data-src="scene\.js\?v=\w+" data-near="#stage" data-event="demo3d" defer>', t): probs.append("lazy3d")
        if re.search(r'(?:src|@import)\s*=?\s*["\(]?https?://', t): probs.append("outside src")
        if not re.search(r'<p class="lead">', t): probs.append("lead")
        if probs: bad[d] = probs
    check("a. each demo: one h1, noindex, the 'Demo site · fictional' strip, 555 numbers, the booking sheet (says nothing is sent), 3 reviews, the map, "
          "the drawn picture inside the stage, the 3D through lazy3d after paint, no outside src", not bad, bad)
    imports = {}
    for d in DEMOS + ["."]:
        p = DEMOS_DIR / d / ("scene.js" if d != "." else "stage.js")
        for m in re.findall(r"""^\s*import\s[^'"]*['"]([^'"]+)['"]""", read(p), re.M):
            imports.setdefault(m, []).append(d)
    allowed = {"../../../jarvis/three.module.min.js", "../stage.js", "../../../olympus/three-addons/RoomEnvironment.js"}
    check("a. the scenes import only local files: three r160 (jarvis/), the shared stage, RoomEnvironment (olympus/three-addons)",
          set(imports) <= allowed and (WEB / "jarvis" / "three.module.min.js").exists() and 'const t="160"' in read(WEB / "jarvis" / "three.module.min.js")[:4000], imports)
    lazy = read(WEB / "olympus" / "lazy3d.js")
    shared = sum((DEMOS_DIR / f).stat().st_size for f in ("demo.css", "demo.js")) + len(lazy.encode())
    weights = {d: files[d].stat().st_size + shared for d in DEMOS}
    g = DEMOS_DIR / "index.html"
    weights["gallery"] = g.stat().st_size + (DEMOS_DIR / "demo.css").stat().st_size + sum((DEMOS_DIR / d / "thumb.jpg").stat().st_size for d in DEMOS)
    check("a. first load < 400 kB raw per page before any 3D (page + demo.css + demo.js + lazy3d.js; the gallery with its 4 stills)",
          all(v < 400_000 for v in weights.values()), weights)
    thumbs = {d: (DEMOS_DIR / d / "thumb.jpg").stat().st_size for d in DEMOS}
    check("a. the gallery stills are small (< 60 kB each, own renders of the demos)", all(v < 60_000 for v in thumbs.values()), thumbs)
    gt = read(g)
    check("a. the gallery: the 4 demos linked, a price to build + monthly for each (8 data-price), the pitch lines and client mode",
          all(f'href="{d}/"' in gt for d in DEMOS) and gt.count("data-price=") == 8 and gt.count('class="pitch owner-only"') == 4 and 'id="client"' in gt
          and "html.client .owner-only { display: none !important; }" in gt and 'id="theirs"' in gt, gt.count("data-price="))
    priv = [str(p.relative_to(WEB)) for p in DEMOS_DIR.rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".css")
            and re.search(r"demetrades|gmail\.com|@[a-z0-9-]+\.(com|net)", read(p), re.I)]
    check("a. no private names or e-mail addresses in the demo files", not priv, priv)
    st = read(DEMOS_DIR / "stage.js")
    check("a. the stage: canvas fades in over the drawn picture (fixed ratio), pauses off screen / hidden tab, reduced motion = no auto-turn, "
          "a lost context keeps the picture, pan-y touch",
          all(s in st for s in ("IntersectionObserver", "document.hidden", "prefers-reduced-motion", "webglcontextlost", "touchAction = 'pan-y'", "host.classList.add('gl-on')")))


# ------------------------------------------------------------------------------------------------ b. browser
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=str(WEB))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


NOISE = re.compile(r"GL Driver Message|GPU stall|WebGL-|swiftshader|Automatic fallback to software WebGL", re.I)

PAGE_PROBE = """() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.closest('dialog:not([open])'); };
  const small = [...document.querySelectorAll('.btn, .pick, .x, .demo-strip a, .back, [data-book]')].filter(vis)
    .filter(e => e.getBoundingClientRect().height < 43.5).map(e => (e.className || e.tagName) + ':' + Math.round(e.getBoundingClientRect().height) + ':' + e.textContent.trim().slice(0, 20));
  const tiny = [...document.querySelectorAll('p, li, .review p, .card p, .lead, .pick-note')].filter(vis)
    .filter(e => e.textContent.trim().split(/\\s+/).length > 4 && parseFloat(getComputedStyle(e).fontSize) < 14.9).map(e => e.className + ':' + getComputedStyle(e).fontSize + ':' + e.textContent.trim().slice(0, 30));
  const st = document.querySelector('#stage');
  return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, small, tiny, three: st ? st.dataset.three || '' : '',
    gl: !!(st && st.querySelector('canvas.stage-gl')), cls: window.__cls || 0, picOpacity: st && st.querySelector('.pic') ? getComputedStyle(st.querySelector('.pic')).opacity : null,
    auto: window.DEMO3D ? !window.DEMO3D.reduce : null, picks: Object.assign({}, window.DEMO_PICKS || {}) };
}"""

CLS_INIT = """window.__cls = 0; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}"""

NO_GL = "delete window.WebGLRenderingContext; delete window.WebGL2RenderingContext;"

SECOND_PICK = {"restaurant": ("dish", "pasta"), "roofer": ("shingle", "terracotta"), "detailer": ("finish", "before"), "estate": ("room", "overview")}


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright is available", False, e)
        return
    srv = serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}/agency/demos/"
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for d in DEMOS:
            ctx = b.new_context(viewport={"width": 390, "height": 844})
            ctx.add_init_script(CLS_INIT)
            p = ctx.new_page()
            errs, outside = [], []
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not NOISE.search(m.text) else None)
            p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            p.on("request", lambda r: outside.append(r.url) if not r.url.startswith("http://127.0.0.1") and not r.url.startswith("data:") else None)
            p.goto(base + d + "/", wait_until="load")
            try:
                p.wait_for_function("() => (document.querySelector('#stage') || {}).dataset && document.querySelector('#stage').dataset.three === 'on'", timeout=15000)
            except Exception:  # noqa: BLE001
                pass
            p.wait_for_timeout(900)
            r = p.evaluate(PAGE_PROBE)
            first = p.evaluate("() => performance.getEntriesByType('resource').filter(e => !/three\\.module|scene\\.js|stage\\.js|RoomEnvironment/.test(e.name)).reduce((a, e) => a + (e.encodedBodySize || 0), 0) + (performance.getEntriesByType('navigation')[0] || {}).encodedBodySize")
            check(f"b. {d}: the 3D stage starts after load (canvas over the drawn picture), first load {round(first / 1024)} kB < 400",
                  r["three"] == "on" and r["gl"] and first < 400_000, (r["three"], r["gl"], first))
            check(f"b. {d}: no sideways scroll, layout shift <= 0.02 (got {r['cls']:.3f})", r["sw"] <= r["cw"] and r["cls"] <= .02, (r["sw"], r["cw"], r["cls"]))
            check(f"b. {d}: taps >= 44 px, sentences >= 15 px", not r["small"] and not r["tiny"], (r["small"], r["tiny"]))
            # a pick changes the 3D picture
            g, v = SECOND_PICK[d]
            p.evaluate("() => { const s = document.querySelector('#stage'); s.scrollIntoView({ block: 'center' }); window.DEMO3D && window.DEMO3D.setAuto(false); }")
            p.wait_for_timeout(500)
            before = p.locator("#stage").screenshot()
            p.locator(f'[data-group="{g}"] .pick[data-value="{v}"]').click()
            p.wait_for_timeout(1800)
            after = p.locator("#stage").screenshot()
            picks = p.evaluate("() => Object.assign({}, window.DEMO_PICKS)")
            pressed = p.locator(f'[data-group="{g}"] .pick[data-value="{v}"]').get_attribute("aria-pressed")
            check(f"b. {d}: the '{v}' pick is pressed, remembered and changes the 3D picture", picks.get(g) == v and pressed == "true" and before != after, (picks, pressed))
            if d == "roofer":
                s0 = p.locator("#stage").screenshot()
                p.locator("input[data-ba]").fill("90")
                p.wait_for_timeout(500)
                check("b. roofer: the before / after slider moves the cut on the 3D roof", p.locator("#stage").screenshot() != s0 and abs(p.evaluate("() => window.DEMO_PICKS.ba") - .9) < 1e-6)
            # the booking sheet: opens from the dock, needs the fields, thanks, sends nothing
            n0 = len(outside)
            p.locator(".dock [data-book]").click()
            opened = p.evaluate("() => document.getElementById('book').open")
            p.locator("#book button[type=submit]").click()
            still = p.evaluate("() => !document.querySelector('#book form').hidden")
            for sel, val in (("#book input[name=name]", "Test Person"), ("#book input[name=tel]", "5550100000")):
                p.locator(sel).fill(val)
            for sel in ("#book input[name=addr]", "#book input[name=car]"):
                if p.locator(sel).count():
                    p.locator(sel).fill("Test Road")
            p.locator("#book button[type=submit]").click()
            p.wait_for_timeout(200)
            thanks = p.evaluate("() => !document.querySelector('#book .done').hidden && document.querySelector('#book form').hidden")
            p.locator("#book .done [data-close]").click()
            closed = not p.evaluate("() => document.getElementById('book').open")
            check(f"b. {d}: the booking sheet opens, will not send empty, thanks, closes, and nothing leaves the phone",
                  opened and still and thanks and closed and len(outside) == n0, (opened, still, thanks, closed, outside[n0:]))
            check(f"b. {d}: no console or page error, nothing asked from another host", not errs and not outside, (errs[:3], outside[:3]))
            ctx.close()

            # no WebGL: the drawn picture stays, the picks still work, no errors
            ctx = b.new_context(viewport={"width": 390, "height": 844})
            ctx.add_init_script(NO_GL)
            p = ctx.new_page()
            errs2 = []
            p.on("pageerror", lambda e: errs2.append(str(e)))
            p.on("console", lambda m: errs2.append(m.text) if m.type == "error" else None)
            p.goto(base + d + "/", wait_until="load")
            p.wait_for_timeout(2500)
            r2 = p.evaluate(PAGE_PROBE)
            p.locator(f'[data-group="{g}"] .pick[data-value="{v}"]').click()
            ok_pick = p.evaluate(f"() => window.DEMO_PICKS['{g}'] === '{v}'")
            check(f"b. {d} without WebGL: the drawn picture stays (no canvas), the picks still work, no error",
                  r2["three"] != "on" and not r2["gl"] and r2["picOpacity"] == "1" and ok_pick and not errs2, (r2["three"], r2["picOpacity"], ok_pick, errs2[:2]))
            ctx.close()

        # reduced motion: no auto-turn
        ctx = b.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
        p = ctx.new_page()
        p.goto(base + "restaurant/", wait_until="load")
        try:
            p.wait_for_function("() => window.DEMO3D", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        check("b. reduced motion: the 3D does not turn by itself", p.evaluate("() => !!(window.DEMO3D && window.DEMO3D.reduce)"))
        ctx.close()

        # the gallery
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        p = ctx.new_page()
        errs3 = []
        p.on("pageerror", lambda e: errs3.append(str(e)))
        p.goto(base, wait_until="load")
        p.wait_for_timeout(600)
        g = p.evaluate("""() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, cards: document.querySelectorAll('.demo').length,
          imgs: [...document.querySelectorAll('.demo img')].filter(i => i.complete && i.naturalWidth > 0).length,
          prices: [...document.querySelectorAll('[data-price]')].filter(e => e.getClientRects().length).length })""")
        p.locator("#client").check()
        hidden = p.evaluate("() => [...document.querySelectorAll('[data-price], .pitch')].every(e => !e.getClientRects().length)")
        p.reload(wait_until="load")
        kept = p.evaluate("() => document.documentElement.classList.contains('client') && document.getElementById('client').checked")
        p.locator("#client").uncheck()
        back = p.evaluate("() => [...document.querySelectorAll('[data-price]')].filter(e => e.getClientRects().length).length")
        r = p.evaluate(PAGE_PROBE)
        check("b. gallery: 4 demo cards with their stills and 8 prices, no sideways scroll, taps >= 44 px, sentences >= 15 px",
              g["cards"] == 4 and g["imgs"] >= 2 and g["prices"] == 8 and g["sw"] <= g["cw"] and not r["small"] and not r["tiny"] and not errs3, (g, r["small"], r["tiny"], errs3))
        check("b. gallery: client mode hides prices and pitch lines, is remembered after a reload, and turns back off", hidden and kept and back == 8, (hidden, kept, back))
        # Make it theirs: the form builds the link, the demo shows their name / town / phone, markup stays text
        p.fill("#theirs [name=biz]", "Rosa's <img src=x onerror=alert(1)>Pizzeria")
        p.fill("#theirs [name=city]", "Springfield")
        p.fill("#theirs [name=tel]", "(555) 010-0199")
        p.select_option("#theirs [name=demo]", "roofer")
        with p.expect_navigation():
            p.click("#theirs button[type=submit]")
        p.wait_for_timeout(800)
        t = p.evaluate("""() => ({ path: location.pathname, logo: document.querySelector('.logo [data-biz]').textContent, strip: document.querySelector('[data-strip]').textContent,
          city: [...document.querySelectorAll('[data-city]')].map(e => e.textContent), imgs: document.querySelectorAll('main img, header img').length,
          tels: [...new Set([...document.querySelectorAll('a[href^="tel:"]')].map(a => a.getAttribute('href')))], shown: [...document.querySelectorAll('a[href^="tel:"]')].some(a => a.textContent.includes('(555) 010-0199')),
          fict: document.querySelector('[data-fict]').textContent, rev: document.querySelector('[data-reviews]').textContent })""")
        check("b. Make it theirs: the roofer demo opens with their name (markup stripped, 40 characters max), town, phone on every Call link; marked as a sample with sample reviews",
              t["path"].endswith("/roofer/") and t["logo"].startswith("Rosa's") and len(t["logo"]) <= 40 and "<" not in t["logo"] and t["imgs"] == 0 and t["strip"].startswith("Sample site for Rosa's")
              and set(t["city"]) == {"Springfield"} and t["tels"] == ["tel:+15550100199"] and t["shown"] and t["fict"] == "(sample site)" and "samples" in t["rev"], t)
        ctx.close()
        b.close()
    srv.shutdown()


def main():
    static()
    if os.environ.get("WD_NO_BROWSER") != "1":
        browser()
    n = len(RES)
    print(f"web demos: {sum(RES)}/{n} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
