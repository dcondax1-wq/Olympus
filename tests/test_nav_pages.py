"""The hub pages the owner uses to find his way (hub/help, steps, manual, zeus, doors; 2026-11-20 day-manual NAV team).
  a. static: each page's first top-row link is "Home" -> ../gate/index.html; help / steps / manual link each other and ZEUS;
     help, steps, zeus, manual carry the OLYMPUS look (FIRST PAINT copy + olympus/themes.js), like the Doors and the hubs
  b. Chromium 390 x 844, the default look AND Ivory (light): the page wears the look (dark / light background), no console error
     (data 404s of a site copy without the PC feed aside), no sideways scroll, every top-row tap >= 44 px, layout shift < 0.05
    python -X utf8 -m tests.test_nav_pages      (NAV_NO_BROWSER=1 skips b; run b under flock -w 2400 /tmp/olympus_browser.lock)
    python -X utf8 -m tests.test_nav_pages --shots   (+ research/handoff/2026-11-20/olympus2/nav/after/*.png, deviceScaleFactor 2)
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
HUB = os.path.join(WEB, "hub")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-20", "olympus2", "nav", "after")
RES: list = []
PAGES = {"help": ".hp-nav", "steps": ".st-nav", "manual": ".mn-top", "zeus": ".zs-nav", "doors": "nav"}
CLS_JS = """window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({type: 'layout-shift', buffered: true});"""


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"))


def rd(n):
    with open(os.path.join(HUB, n), encoding="utf-8") as f:
        return f.read()


def part_a():
    first = {}
    for p in PAGES:
        s = rd(p + ".html")
        m = re.search(r'<nav class="[^"]*"[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>', s)
        first[p] = (m.group(1), m.group(2).replace("&#9664;", "").strip()) if m else None
    check("a. every hub page starts its top row with Home -> the Gate", all(v and v[0] == "../gate/index.html" and v[1] == "Home" for v in first.values()), first)
    trio = {p: re.search(r'<nav class="(hp-nav|st-nav|mn-top)"[^>]*>(.*?)</nav>', rd(p + ".html"), re.S).group(2) for p in ("help", "steps", "manual")}
    want = {"help": ["zeus.html", "steps.html", "manual.html"], "steps": ["zeus.html", "help.html", "manual.html"], "manual": ["zeus.html", "help.html"]}
    bad = {p: [h for h in want[p] if f'href="{h}"' not in trio[p]] for p in trio}
    check("a. help / steps / manual: the top row links ZEUS and each other", not any(bad.values()), bad)
    nolook = [p for p in ("help", "steps", "zeus", "manual", "doors") if "olympus.theme.look." not in rd(p + ".html") or "olympus/themes.js" not in rd(p + ".html")]
    check("a. help, steps, zeus, manual, doors carry the OLYMPUS look (first-paint copy + themes.js)", not nolook, nolook)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_b(shots: bool):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] b. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    if shots:
        os.makedirs(SHOTS, exist_ok=True)
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            for look in ("agora", "ivory"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2 if shots else 1)
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=204, body=""))
                ctx.add_init_script(CLS_JS)
                if look != "agora":
                    pre = ctx.new_page()   # pick the look the way the Gate does: themes.js set() writes the id and the look copies
                    pre.goto(base + "hub/doors.html")
                    pre.wait_for_function("window.OLYMPUS_THEMES && window.OLYMPUS_THEMES.set")
                    pre.evaluate(f"window.OLYMPUS_THEMES.set('{look}')")
                    pre.close()
                for p, navsel in PAGES.items():
                    errs: list = []
                    pg = ctx.new_page()
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
                    pg.goto(base + f"hub/{p}.html")
                    pg.wait_for_timeout(1800)
                    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                    nums = [int(x) for x in re.findall(r"\d+", bg)[:3]]
                    lum = sum(nums) / 3 if nums else 0
                    if lum == 0 and "rgba(0, 0, 0, 0)" in bg:
                        bg = pg.evaluate("getComputedStyle(document.documentElement).backgroundColor")
                        lum = sum(int(x) for x in re.findall(r"\d+", bg)[:3]) / 3
                    ok_look = lum < 70 if look == "agora" else lum > 180
                    wide = pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                    small = pg.evaluate(f"[...document.querySelectorAll('{navsel} a, {navsel} button')].filter(e => {{ const r = e.getBoundingClientRect(); return r.width > 0 && (r.height < 44 || r.width < 44); }}).length")
                    cls = pg.evaluate("window.__cls")
                    if shots:
                        pg.screenshot(path=os.path.join(SHOTS, f"{p}-{'dark' if look == 'agora' else 'light'}.png"))
                    check(f"b. {p} [{look}]: wears the look ({bg}), no sideways scroll, top-row taps >= 44 px, CLS {cls:.3f} < 0.05, no console error",
                          ok_look and wide and small == 0 and cls < 0.05 and not errs, (bg, wide, small, cls, errs[:2]))
                    pg.close()
                ctx.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    if not os.environ.get("NAV_NO_BROWSER"):
        part_b("--shots" in sys.argv)
    n = sum(RES)
    print(f"\nnav_pages: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
