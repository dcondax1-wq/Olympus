"""Edge to edge on an iPhone Home Screen app (night-fitperf 2026-11-19, owner at 5:02 AM: "the dock sits way above the bottom with an
empty black band under it, on every screen"; "some stuff lags"). The real pages in Chromium as an iPhone 15 (393 x 852, touch, the
home-bar safe area: CDP Emulation.setSafeAreaInsetsOverride top 59 / bottom 34; navigator.standalone = true as the Home Screen app):
  a. Jarvis home: the dock sits 18 px above the edge (the safe area less 16: clear of the home bar), its solid base runs to the
     bottom edge (the last pixel row is the base's colour, no band), the page itself never scrolls
  b. hostBadge lifts the dock for a REAL web-host badge only: our own fixed layers in the bottom-right corner (a toast, a pill, a
     card) never lift it; a "Powered by Netlify" badge does, and the dock comes back down when it goes
  c. fitDock: a visual viewport shorter than the screen with NO text field focused (iOS 26 Home Screen apps report one after the
     keyboard went) never floats the dock; with the field focused it rides above the "keyboard"; blur puts it back
  d. every app inside Jarvis: its frame reaches the screen's bottom edge (no band under it), the page inside reads the phone's safe
     area itself (so its bar sits ONE safe area up, not two), and a fixed bar of the app sits at most ~one safe area + 12 px up
  e. the pages opened directly (Zenith, ZEUS hub, NQ, MFFU, World, Kalshi, Plan, Mnemosyne's edge, kit apps): the page's own
     colour paints the bottom edge (no unpainted black band), its last bar sits at most one safe area + 12 px up, no page error
  f. the start is quicker: the apps list is asked of apps.js about once per render (D.listApps memo), not once per tile
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_fit_edge        (~2-4 min on a calm machine)
"""
from __future__ import annotations

import functools
import http.server
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []
W, H, SAT, SAB = 393, 852, 59, 34
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
INIT = ("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
        " localStorage.setItem('jarvis.tour.seen', '1'); localStorage.setItem('jarvis.orb.tips', '3'); localStorage.setItem('olympus.welcome.v1', '1');"
        " Object.defineProperty(navigator, 'standalone', { get: () => true }); } catch (e) {}")
R = """(q) => { const e = typeof q === 'string' ? document.querySelector(q) : q; if (!e) return null; const cs = getComputedStyle(e);
  if (cs.display === 'none' || cs.visibility === 'hidden') return null; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 ? [r.left, r.top, r.right, r.bottom].map(Math.round) : null; }"""
# the lowest fixed bar that spans most of the width (a tab bar, a dock): its gap to the bottom edge, or null
BAR = """(doc) => { doc = doc || document; const win = doc.defaultView, Hh = win.innerHeight, Ww = win.innerWidth; let best = null;
  for (const e of doc.querySelectorAll('body *')) { const s = win.getComputedStyle(e); if (s.position !== 'fixed' || s.display === 'none' || s.visibility === 'hidden') continue;
    const r = e.getBoundingClientRect(); if (r.width < Ww * 0.5 || r.height < 24 || r.height > Hh * 0.45 || r.bottom < Hh - 160 || r.bottom > Hh + 1) continue;
    const gap = Math.round(Hh - r.bottom); if (!best || gap < best.gap) best = { gap, sel: e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') }; } return best; }"""
SAB_OF = """(doc) => { const p = doc.createElement('div'); p.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;visibility:hidden;padding-bottom:env(safe-area-inset-bottom,0px)';
  (doc.body || doc.documentElement).appendChild(p); const v = parseFloat(doc.defaultView.getComputedStyle(p).paddingBottom) || 0; p.remove(); return v; }"""


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


class Srv(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


def phone(br, origin):
    ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, is_mobile=True, has_touch=True, user_agent=UA, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.fulfill(status=200, body="{}", headers={"Access-Control-Allow-Origin": "*"}))
    ctx.add_init_script(INIT)
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)[:200]))
    cdp = ctx.new_cdp_session(p)
    cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAT, "bottom": SAB, "left": 0, "right": 0}})
    try:
        cdp.send("Emulation.setEmulatedMedia", {"features": [{"name": "display-mode", "value": "standalone"}]})
    except Exception:  # noqa: BLE001  (navigator.standalone covers the pages' own checks)
        pass
    return ctx, p, errs


def bottom_row(p):
    """the mean colour of the screen's last 2 pixel rows"""
    from io import BytesIO
    from PIL import Image, ImageStat
    im = Image.open(BytesIO(p.screenshot(clip={"x": 0, "y": H - 2, "width": W, "height": 2}))).convert("RGB")
    return tuple(int(v) for v in ImageStat.Stat(im).mean)


def rgb(css: str):
    import re
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", css or "")
    return tuple(int(x) for x in m.groups()) if m else None


def near(a, b, tol=14):
    return a is not None and b is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def main() -> int:
    try:
        from tests import browser_kit as BK
    except ImportError:
        import browser_kit as BK
    from playwright.sync_api import sync_playwright
    srv = Srv(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            # ------------------------------------------------------------------ a-c, f: the Jarvis home
            calls = "window.__appsCalls = 0;"
            ctx, p, errs = phone(br, origin)
            p.add_init_script(calls)
            p.goto(origin + "/jarvis/")
            p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=240000, polling=300)
            p.wait_for_function("document.querySelectorAll('#olyApps .og-t[data-app]').length >= 20", timeout=120000, polling=300)
            p.wait_for_timeout(1500)
            dock = p.evaluate(R, "#dock")
            gap = H - dock[3] if dock else None
            check(f"a. Jarvis home: the dock sits {gap} px above the edge (the home-bar safe area {SAB} less 16 = 18: clear of the home bar)", gap == SAB - 16, dock)
            base = p.evaluate("(() => { const s = getComputedStyle(document.querySelector('.dockfade'), '::after'); return [s.position, s.bottom, s.height, s.backgroundColor]; })()")
            row = bottom_row(p)
            check("a. Jarvis home: the dock's solid base runs to the bottom edge, and the last pixel row is the base's colour (no other band)",
                  base[0] == "fixed" and base[1] == "0px" and float(base[2].rstrip("px") or 0) >= H - dock[1] and near(row, rgb(base[3])), (base, row))
            sc = p.evaluate("[window.scrollY, document.documentElement.scrollHeight, innerHeight]")
            check("a. Jarvis home: the page itself never scrolls (its own scroller does)", sc[0] == 0 and sc[1] <= sc[2] + 1, sc)
            # b. our own fixed layers in the corner
            p.evaluate("""(() => { for (const [id, css] of [['ownToast', 'right:10px;bottom:20px;width:150px;height:56px'], ['ownPill', 'right:12px;bottom:90px;width:120px;height:40px'],
                  ['ownCard', 'right:8px;bottom:8px;width:200px;height:120px']]) { const e = document.createElement('div'); e.id = id; e.className = 'push-pill toast-like';
                  e.textContent = id; e.style.cssText = 'position:fixed;z-index:2147483647;background:#333;color:#fff;' + css; document.body.appendChild(e); } })()""")
            p.wait_for_timeout(1200)
            st = p.evaluate("[document.documentElement.style.getPropertyValue('--host-lift'), document.documentElement.getAttribute('data-host-badge')]")
            d2 = p.evaluate(R, "#dock")
            check("b. our own fixed layers in the bottom-right corner (a toast, a pill, a card) never lift the dock", st == ["", None] and d2 == dock, (st, d2, dock))
            p.evaluate("for (const id of ['ownToast', 'ownPill', 'ownCard']) document.getElementById(id).remove()")
            p.evaluate("""(() => { const b = document.createElement('div'); b.id = 'nl-badge-frame'; b.textContent = 'Powered by Netlify';
                  b.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;background:#fff;color:#000;padding:10px 14px;font:600 14px sans-serif'; document.body.appendChild(b); })()""")
            p.wait_for_timeout(1200)
            b, d3 = p.evaluate(R, "#nl-badge-frame"), p.evaluate(R, "#dock")
            check("b. a real web-host badge (Netlify's) lifts the dock above it", b and d3 and d3[3] <= b[1], (b, d3))
            p.evaluate("document.getElementById('nl-badge-frame').remove()")
            p.wait_for_timeout(1200)
            d4 = p.evaluate(R, "#dock")
            check("b. the badge gone: the dock is back in its place", d4 == dock, (d4, dock))
            # c. the keyboard: a phantom short visual viewport without focus never lifts; with the field focused it does
            fake = "(h) => { Object.defineProperty(visualViewport, 'height', { configurable: true, get: () => h }); visualViewport.dispatchEvent(new Event('resize')); }"
            p.evaluate("document.activeElement && document.activeElement.blur()")
            p.evaluate(fake, H - 120)
            p.wait_for_timeout(200)
            c1 = p.evaluate("[document.getElementById('dock').style.transform, document.getElementById('dock').classList.contains('kb')]")
            check("c. a visual viewport 120 px short with NO field focused (iOS after the keyboard went) never floats the dock", c1 == ["", False], c1)
            p.focus("#q")
            p.evaluate(fake, H - 120)
            p.wait_for_timeout(200)
            c2 = p.evaluate("[document.getElementById('dock').style.transform, document.getElementById('dock').classList.contains('kb')]")
            check("c. with the Ask field focused the dock rides 120 px up, above the keyboard", c2 == ["translateY(-120px)", True], c2)
            p.evaluate("document.activeElement.blur()")
            p.wait_for_timeout(300)
            c3 = p.evaluate("[document.getElementById('dock').style.transform, document.getElementById('dock').classList.contains('kb')]")
            p.evaluate(fake, H)
            check("c. the field let go: the dock is back down at once (even before the viewport grows back)", c3 == ["", False], c3)
            # f. the apps list: one ask of apps.js per render, not one per tile
            n = p.evaluate("""(async () => { const D = await import('./data.js'); const src = D.appsSource(); if (!src || src.fallback) return null; let k = 0;
                  const real = src.listApps; const spy = { ...src, listApps: (...a) => { k++; return real(...a); } }; D.setAppsSource(spy);
                  await new Promise((r) => setTimeout(r, 80)); k = 0; window.__jarvis.show('home'); await new Promise((r) => setTimeout(r, 400)); D.setAppsSource(src); return k; })()""")
            check(f"f. a home render asks apps.js for the app list {n} times (memo for the task; was once per tile, ~75+)", n is not None and n <= 6, n)
            check("a-c. no page errors on the Jarvis home", not errs, errs[:3])
            # ------------------------------------------------------------------ d: apps inside Jarvis
            for app in ("zenith", "nq", "kalshi", "athena", "oracle", "tyche", "plutus", "business"):
                p.evaluate("(id) => window.__jarvis.show(id)", app)
                try:
                    p.wait_for_function("""(id) => { const f = id === 'zenith' ? document.querySelector('.zm-frame') : document.querySelector('#v-' + id + ' iframe');
                        try { return !!f && !!f.contentDocument && f.contentDocument.readyState === 'complete' && !!f.contentDocument.body; } catch (e) { return false; } }""", arg=app, timeout=90000, polling=300)
                except Exception as e:  # noqa: BLE001
                    check(f"d. {app}: opens inside Jarvis", False, str(e)[:160])
                    continue
                p.wait_for_timeout(1800)
                res = p.evaluate("""([id, BAR, SAB_OF]) => { const f = id === 'zenith' ? document.querySelector('.zm-frame') : document.querySelector('#v-' + id + ' iframe');
                    const r = f.getBoundingClientRect(), d = f.contentDocument, bar = (new Function('return ' + BAR))()(d), sab = (new Function('return ' + SAB_OF))()(d);
                    return { bottom: Math.round(r.bottom), H: innerHeight, pad: f.classList.contains('pad-b'), bar, sab }; }""", [app, BAR, SAB_OF])
                check(f"d. {app} inside Jarvis: the frame reaches the bottom edge (was {SAB} px short: a band of Jarvis's colour under every app)",
                      res["bottom"] == res["H"] and not res["pad"], res)
                if app != "zenith":
                    check(f"d. {app} inside Jarvis: the page in the frame reads the phone's safe area itself ({res['sab']:g} px), so nothing pads twice", res["sab"] == SAB, res)
                if res["bar"]:
                    check(f"d. {app} inside Jarvis: its bottom bar ({res['bar']['sel']}) sits {res['bar']['gap']} px up: one safe area at most (+12), never two",
                          res["bar"]["gap"] <= SAB + 12, res)
            p.evaluate("window.__jarvis.show('home')")
            check("d. no page errors while switching apps", not errs, errs[:3])
            ctx.close()
            # ------------------------------------------------------------------ e: the pages on their own (as Home Screen apps)
            for path in ("", "hub/zeus.html", "nq/", "business/mffu.html", "cities/world/", "kalshi/", "business/plan.html", "journal/edge.html", "athena/", "oracle/", "tyche/", "plutus/"):
                ctx, p, errs = phone(br, origin)
                p.goto(origin + "/" + path, wait_until="load", timeout=120000)
                p.wait_for_timeout(2500)
                bar = p.evaluate(BAR, None)
                bg = p.evaluate("""(() => { const v = (e) => getComputedStyle(e).backgroundColor; const t = (c) => !c || c === 'transparent' || /rgba\\(.*,\\s*0\\)$/.test(c);
                    const h = v(document.documentElement), b = v(document.body); return t(h) ? (t(b) ? null : b) : h; })()""")
                row = bottom_row(p)
                name = path or "Zenith (/)"
                check(f"e. {name}: the page paints its own colour to the bottom edge (no unpainted band)", bg is not None and (row != (0, 0, 0) or near(rgb(bg), (0, 0, 0), 2) or bar), (bg, row, bar))
                if bar:
                    check(f"e. {name}: its bottom bar ({bar['sel']}) sits {bar['gap']} px up: at most one safe area + 12 (content runs under it)", bar["gap"] <= SAB + 12, bar)
                check(f"e. {name}: no page errors", not errs, errs[:3])
                ctx.close()
    finally:
        srv.shutdown()
    n = sum(RES)
    print(f"\nfit edge: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
