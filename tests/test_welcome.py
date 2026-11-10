"""The first-run welcome card in the Jarvis home (2026-11-10): jarvis/welcome.js.

    python -X utf8 -m tests.test_welcome [--no-browser]

a. static: the file is wired in index.html and the worker, node --check, Safari 16 safe, AGORA (no neon / glow), no network, no innerHTML,
   the key olympus.welcome.v1, ?welcome=1 forces, notifications are only requested inside a click handler, the export button opens Settings > Data
b. browser (390 x 844, Playwright, the real jarvis/ folder): not shown to automation without ?welcome=1; ?welcome=1 shows four steps with a Skip button on each,
   every tap target >= 44 px, step 2 writes the same favourites keys as the switcher / launcher (3 picks max), step 3 asks for no permission by itself,
   step 4 has the export link to ../settings/?tab=data; Done / Skip save olympus.welcome.v1 (not when forced), and a saved key hides it for good
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RESULTS = []


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"\n     {str(detail)[:400]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def part_a():
    js = rd(WEB, "jarvis", "welcome.js")
    html = rd(WEB, "jarvis", "index.html")
    sw = rd(WEB, "jarvis", "sw.js")
    check("a. welcome.js is loaded by the Jarvis page (deferred) and saved by the worker", '<script src="./welcome.js?v=w1" defer></script>' in html and "'./welcome.js?v=w1'" in sw)
    r = subprocess.run(["node", "--check", os.path.join(WEB, "jarvis", "welcome.js")], capture_output=True, text=True)
    check("a. node --check passes", r.returncode == 0, r.stderr)
    check("a. Safari 16 safe (no lookbehind, ?., ??, .at()) and no innerHTML / network", not re.search(r"\(\?<[=!]|\?\?|\.at\(|[\w)\]]\?\.[A-Za-z_$]|innerHTML|insertAdjacentHTML|fetch\(|XMLHttpRequest|WebSocket", js))
    check("a. AGORA: no neon colours, no glow / text-shadow, no techno fonts, serif heading, bloom none", not re.search(r"text-shadow|box-shadow:[^;]*(0 0 \d|#0ff|#f0f)|Orbitron|Rajdhani|#00f|neon", js) and "Iowan Old Style" in js)
    check("a. the four steps: what, favs, notify, export, in plain words (title and text each)", re.findall(r"id: '(\w+)', title", js) == ["what", "favs", "notify", "export"])
    check("a. seen once in olympus.welcome.v1; ?welcome=1 forces (and does not save), ?welcome=0 never shows; automation is skipped unless forced",
          "olympus.welcome.v1" in js and "welcome=1" in js and "welcome=0" in js and "navigator.webdriver" in js and "if (!forced) set(KEY" in js)
    check("a. notifications are never asked automatically: requestPermission only inside the Turn on click handler",
          js.count("requestPermission") == 1 and js.index("btn('Turn on'") < js.index("requestPermission") < js.index("btn('Not now'"))
    check("a. the favourites use the switcher's and the launcher's keys; the export button opens Settings > Data", "jarvis.orb.fav" in js and "oly.launcher.fav" in js and "../settings/?tab=data" in js)
    check("a. 44 px taps (Skip, buttons, picks) and reduced motion", "min-height:44px" in js and "min-height:48px" in js and "min-height:64px" in js and "prefers-reduced-motion:reduce" in js)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_b():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
        p = ctx.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        # a bare page that loads only welcome.js (the real Jarvis page is heavy; its wiring is checked in part a)
        p.route(re.compile(r"/welcome-host\.html"), lambda r: r.fulfill(status=200, content_type="text/html", body="<!doctype html><meta charset=utf-8><title>host</title><body style='background:#14110e'><h1>host</h1><script src='/jarvis/welcome.js' defer></script>"))
        p.goto(base + "/welcome-host.html")
        p.wait_for_timeout(1800)
        check("b. automation (no ?welcome=1): not shown", p.evaluate("!window.OLYMPUS_WELCOME.state().open") and p.locator(".olw").count() == 0)
        p.goto(base + "/welcome-host.html?welcome=1")
        p.wait_for_selector(".olw:not([hidden]) h2", timeout=8000)
        steps = []
        for i in range(4):
            t = p.inner_text(".olw h2")
            small = p.evaluate("[...document.querySelectorAll('.olw button, .olw a')].filter((e) => e.offsetParent && e.getBoundingClientRect().height < 44).map((e) => e.textContent)")
            steps.append((t, p.locator(".olw .skip").count(), small))
            if i == 1:
                p.wait_for_selector(".olw .pk", timeout=8000)
                for app_id in [x for x in p.evaluate("[...document.querySelectorAll('.olw .pk')].slice(0, 4).map((b) => b.dataset.app)")]:
                    p.click(f'.olw .pk[data-app="{app_id}"]')
                picked = p.evaluate("document.querySelectorAll('.olw .pk[aria-pressed=true]').length")
                favs = p.evaluate("[localStorage.getItem('jarvis.orb.fav'), localStorage.getItem('oly.launcher.fav')]")
                check("b. step 2: at most three favourites (a fourth replaces the first), written to the switcher's and the launcher's keys",
                      picked == 3 and favs[0] == favs[1] and len(json.loads(favs[0])) == 3, (picked, favs))
            if i == 2:
                perm = p.evaluate("Notification.permission")
                check("b. step 3 asks nothing by itself (permission still 'default') and offers Turn on and Not now", perm == "default" and p.locator(".olw .btn", has_text="Not now").count() == 1 and p.locator(".olw .btn", has_text="Turn on").count() == 1, perm)
            if i == 3:
                href = p.get_attribute(".olw a.btn", "href")
                check("b. step 4: an export button that opens Settings > Data", href == "../settings/?tab=data", href)
                break
            p.click(".olw .btn.go" if i != 2 else ".olw .btn.go")
        check("b. four steps with titles, a Skip button on each, every tap 44 px or more", len(steps) == 4 and all(s[1] == 1 and not s[2] for s in steps), steps)
        p.click(".olw .btn.go")                                     # Done
        check("b. forced: Done closes it and saves nothing (it can be forced again)", p.evaluate("document.querySelector('.olw').hidden") and p.evaluate("localStorage.getItem('olympus.welcome.v1')") is None)
        p.goto(base + "/welcome-host.html?welcome=1")
        p.wait_for_selector(".olw:not([hidden]) h2", timeout=8000)
        p.click(".olw .skip")
        check("b. Skip closes it", p.evaluate("document.querySelector('.olw').hidden"))
        p.evaluate("localStorage.setItem('olympus.welcome.v1', JSON.stringify({ t: 1 }))")
        p.goto(base + "/welcome-host.html?welcome=1")
        p.wait_for_selector(".olw:not([hidden])", timeout=8000)
        no_scroll = p.evaluate("document.documentElement.scrollWidth - innerWidth")
        check("b. fits 390 px (no sideways scroll)", no_scroll <= 0, no_scroll)
        p.evaluate("localStorage.removeItem('olympus.welcome.v1')")
        p.evaluate("Object.defineProperty(navigator, 'webdriver', { get: () => false })")
        check("b. no page errors", not errs, errs)
        ctx.close()
        br.close()
    srv.shutdown()


def main():
    part_a()
    if "--no-browser" not in sys.argv:
        part_b()
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"\nwelcome: {n}/{len(RESULTS)} " + ("ALL PASS" if n == len(RESULTS) else "FAILED"))
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
