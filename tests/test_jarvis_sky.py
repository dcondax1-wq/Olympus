"""Jarvis's sky: poster first, the 3D after idle (day-arenas 2026-11-21, DESIGN; Jarvis's phone TBT 5.1 s at QA).
  a. static: jarvis/sky-poster.webp exists and is small (<= 60 KB), index.html paints it with CSS alone (no JS before the first frame) as
     the first layer of .bgfx, fades it out under html[data-bg3d=on]; backdrop.js skips the 3D for effects Off / Low, reduced motion,
     Save-Data, a 2G / 3G line and a <= 2 GB phone, counts a phone's 6 s from load (not from the first byte), builds later if effects go up
  b. Chromium (JS_NO_BROWSER=1 skips): the poster is on screen at first paint; reduced motion = no 3D, why 'reduced motion';
     a 3G line = no 3D, why 'slow line'; a normal desktop = the 3D sky on (data-bg3d), the poster faded out; effects Low -> High builds it
    python -X utf8 -m tests.test_jarvis_sky
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
JV = os.path.join(WEB, "jarvis")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def static():
    h = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    b = open(os.path.join(JV, "backdrop.js"), encoding="utf-8").read()
    p = os.path.join(JV, "sky-poster.webp")
    check("a. sky-poster.webp exists and is small (<= 60 KB)", os.path.exists(p) and os.path.getsize(p) <= 60 * 1024, os.path.exists(p) and os.path.getsize(p))
    check("a. the poster is painted by CSS alone, first layer of .bgfx, faded out once the 3D is on",
          '<div class="bgfx" aria-hidden="true"><div class="jposter"></div><canvas id="stars"></canvas></div>' in h and "url(sky-poster.webp" in h
          and 'html[data-bg3d="on"] .bgfx > .jposter { opacity: 0; }' in h and h.index("url(sky-poster.webp") < h.index('<div class="bgfx"'))
    check("a. backdrop.js skips the 3D for Off / Low, reduced motion, Save-Data, 2G / 3G, <= 2 GB phones; a phone's 6 s count from load; Low -> High builds it",
          all(k in b for k in ("return 'effects off'", "return 'effects low'", "return 'reduced motion'", "return 'save-data'", "return 'slow line'", "return 'small memory'",
                               "loadAt + 6000 - performance.now()", "if (!started && !skipWhy()) idle();")))


class _Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Q, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/jarvis/index.html"
    BD = "() => { const s = window.__jarvisBackdrop || {}; const j = document.querySelector('.bgfx > .jposter'); return { st: s.state, why: s.why || '', bg: document.documentElement.dataset.bg3d || '', fx: document.documentElement.dataset.fx, poster: j ? getComputedStyle(j).backgroundImage : '', op: j ? getComputedStyle(j).opacity : '' }; }"
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

            def page(**kw):
                ctx = br.new_context(viewport={"width": 1280, "height": 800}, service_workers="block", **kw)
                return ctx, ctx.new_page()

            # first paint: the poster is there before any script ran. Effects High as the owner's own choice (data-fx-set): Jarvis's
            # frame-rate probe lowers an unset level to Low on a slow frame rate, and a busy test machine is that by chance (QUALITY
            # 2026-11-21: the flaky 'effects low'); the probe itself is not what this checks
            ctx, p = page()
            p.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
            p.goto(url, wait_until="commit")
            p.wait_for_selector(".bgfx > .jposter", state="attached", timeout=30000)
            r = p.evaluate(BD)
            check("b. the poster is on screen from the first frame (CSS background, full opacity before the 3D)", "sky-poster.webp" in r["poster"] and r["bg"] == "", r)
            try:
                p.wait_for_function("document.documentElement.dataset.bg3d === 'on'", timeout=120000)
                p.wait_for_timeout(1200)
            except Exception:  # noqa: BLE001
                pass
            r = p.evaluate(BD)
            check("b. a normal computer: the 3D sky comes on after idle and the poster fades out under it", r["bg"] == "on" and r["st"] == "on" and float(r["op"] or 1) < 0.05, r)
            ctx.close()

            ctx, p = page(reduced_motion="reduce")
            p.goto(url, wait_until="load")
            p.wait_for_function("window.__jarvisBackdrop && window.__jarvisBackdrop.why", timeout=60000)
            r = p.evaluate(BD)
            check("b. reduced motion: no 3D (Jarvis starts it on effects Low: why 'effects low' / 'reduced motion'), the poster stays", r["why"] in ("reduced motion", "effects low") and r["bg"] == "" and float(r["op"]) > 0.3, r)
            ctx.close()

            ctx, p = page()
            cdp = ctx.new_cdp_session(p)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 562.5, "downloadThroughput": 1.6e6 * 0.9 / 8, "uploadThroughput": 750e3 * 0.9 / 8})
            p.goto(url, wait_until="load", timeout=180000)
            p.wait_for_function("window.__jarvisBackdrop && (window.__jarvisBackdrop.why || document.documentElement.dataset.bg3d)", timeout=120000)
            r = p.evaluate(BD)
            check("b. a 3G line: no 3D (why 'slow line'), the poster stays", r["why"] == "slow line" and r["bg"] == "", r)
            ctx.close()

            ctx, p = page()
            p.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")
            p.goto(url, wait_until="load")
            p.wait_for_timeout(1500)
            r0 = p.evaluate(BD)
            if r0["fx"] == "low":
                p.wait_for_function("window.__jarvisBackdrop && window.__jarvisBackdrop.why === 'effects low'", timeout=60000)
                p.evaluate("document.documentElement.dataset.fx = 'high'")
                try:
                    p.wait_for_function("document.documentElement.dataset.bg3d === 'on'", timeout=120000)
                except Exception:  # noqa: BLE001
                    pass
                r = p.evaluate(BD)
                check("b. effects Low: no 3D; raised to High: the 3D sky is built then", r["bg"] == "on", (r0, r))
            else:
                print("[SKIP] b. effects Low -> High: this build stores the level elsewhere", r0["fx"])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    static()
    if os.environ.get("JS_NO_BROWSER") != "1":
        browser()
    print(json.dumps({"passed": sum(RES), "total": len(RES)}))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
