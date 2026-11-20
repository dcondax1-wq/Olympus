"""ZENITH Home start-up without jumps (day-arenas 2026-11-20, DESIGN; the dogfood audit: Zenith D, main content 10.8 s, CLS 1.08).
  a. static: index.html starts home.json in <head> (window.HOMEP0, picked up by main.js), fetches main / extras / hub first (fetchpriority),
     loads zenith_settle.js right after main.js, holds the NQ strip in the page from the first frame (#znNq before #page); main.js
     starts data.json only after Home's first draw on Home (2.5 s cap) and at once on every other page
  b. Chromium, phone 390 x 844, 4x CPU + a 1.6 Mbps / 150 ms line (ZS_NO_BROWSER=1 skips): Home's first draw comes from home.json, the
     layout shift over start-up stays under 0.1, the start-up changes were held (>= 1) and every still copy is gone afterwards (no
     .zs-ghost, no #page.zs-hold), no page error; a deep link to another page holds nothing and hides the NQ strip; leaving Home while
     a copy stands releases it
    python -X utf8 -m tests.test_zenith_settle
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p):
    return open(os.path.join(WEB, *p), encoding="utf-8").read()


def static():
    h, m, z = read("index.html"), read("main.js"), read("zenith_settle.js")
    head = h[:h.index("</head>")] if "</head>" in h else h[:20000]
    check("a. home.json starts in <head> (window.HOMEP0) and main.js picks it up",
          "window.HOMEP0 = fetch('home.json?t='" in head and "window.HOMEP = (window.HOMEP0 || fetch('home.json?t='" in m)
    check("a. main / extras / hub are fetched first (fetchpriority high), zenith_settle.js runs right after main.js",
          all(re.search(r'<script src="%s\?v=[\w]+" defer fetchpriority="high"></script>' % f, h) for f in (r"main\.js", r"extras\.js", r"hub\.js"))
          and h.index("main.js?v=") < h.index("zenith_settle.js?v=") < h.index("extras.js?v="))
    check("a. data.json waits for Home's first draw on Home (2.5 s cap) and loads at once elsewhere",
          "if (PAGE === 'today') Promise.race([window.HOMEP, new Promise((r) => setTimeout(r, 2500))])" in m and "else load('boot');" in m)
    i, j = h.find('id="znNq"'), h.find('<main class="page" id="page">')
    check("a. the NQ strip is in the page from the first frame, right before #page (the NQ note script fills it)",
          0 < i < j and "Open the new NQ page</a><script>" in h and "</script></section>\n    <main class=\"page\" id=\"page\">" in h)
    check("a. the settle script: only Home, only start-up (25 s), text-only changes never hold, a tap / focus / page change releases",
          all(k in z for k in ("STARTUP = 25000", "function home()", "function moves(", "'pointerdown', release", "'focusin', release", "hashchange")))


def browser():
    try:
        from playwright.sync_api import sync_playwright
        from tests import test_blitz_tab as TB
    except Exception as e:  # noqa: BLE001
        check("b. playwright + the Zenith fixture site", False, e)
        return
    tmp = tempfile.mkdtemp(prefix="zsettle_")
    try:
        F = TB.build()
        s = TB.site(tmp, F)
        lvp = os.path.join(tmp, "liveview.json")
        srv = TB.serve(s)
        base = f"http://127.0.0.1:{srv.server_address[1]}/"
        INIT = """window.__cls = 0; window.__home = 0; window.__d = 0;
          try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
          const tk = () => { const pg = document.getElementById('page'); if (!window.__home && pg && pg.querySelector(':scope > :not(.skel)')) window.__home = performance.now();
            try { if (!window.__d && typeof D !== 'undefined' && D) window.__d = performance.now(); } catch (e) {} if (!window.__home || !window.__d) requestAnimationFrame(tk); }; requestAnimationFrame(tk);"""
        with sync_playwright() as p:
            br = TB.launch(p)
            errs = []
            ctx, pg = TB.phone_ctx(br, F, lvp, "off", errs)
            ctx.add_init_script(INIT)
            cdp = ctx.new_cdp_session(pg)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150, "downloadThroughput": 1.6 * 1024 * 1024 / 8, "uploadThroughput": 750 * 1024 / 8})
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            pg.goto(base + "#/today", wait_until="load", timeout=120000)
            pg.wait_for_selector(".pl-home .su-accts", timeout=60000)
            pg.wait_for_timeout(9000)
            r = pg.evaluate("""() => ({ cls: +window.__cls.toFixed(3), home: Math.round(window.__home), d: Math.round(window.__d), S: window.ZENITH_SETTLE ? { holds: ZENITH_SETTLE.holds, released: ZENITH_SETTLE.released, longest: ZENITH_SETTLE.longest } : null,
              ghosts: document.querySelectorAll('.zs-ghost').length, held: !!document.querySelector('#page.zs-hold'), pages: document.querySelectorAll('#page').length })""")
            check(f"b. Home's first draw comes from home.json, before data.json is drawn (first draw {r['home']} ms, data {r['d']} ms)", r["home"] and (not r["d"] or r["home"] <= r["d"]), r)
            check(f"b. start-up layout shift under 0.1 on a phone line + 4x CPU (got {r['cls']})", r["cls"] < 0.1, r)
            check("b. the start-up changes were held behind a still copy, each released (none longer than 3.5 s), nothing left behind",
                  r["S"] and r["S"]["holds"] >= 1 and r["S"]["holds"] == r["S"]["released"] and r["S"]["longest"] <= 3500 and r["ghosts"] == 0 and not r["held"] and r["pages"] == 1, r)
            check("b. no page error on Home", not errs, errs[:3])
            ctx.close()

            # a deep link to another page: nothing held, the NQ strip hidden; leaving Home during start-up leaves no copy
            errs = []
            ctx, pg = TB.phone_ctx(br, F, lvp, "off", errs)
            pg.goto(base + "#/trades", wait_until="load", timeout=60000)
            pg.wait_for_timeout(4000)
            o = pg.evaluate("() => ({ holds: window.ZENITH_SETTLE ? ZENITH_SETTLE.holds : -1, nq: document.getElementById('znNq').hidden, ghosts: document.querySelectorAll('.zs-ghost').length })")
            check("b. another page (#/trades): nothing held, the NQ strip hidden", o == {"holds": 0, "nq": True, "ghosts": 0}, o)
            pg.goto(base + "#/today", wait_until="load", timeout=60000)
            pg.wait_for_function("() => window.ZENITH_SETTLE && document.querySelector('#page > :not(.skel)')", timeout=30000)
            pg.evaluate("() => { location.hash = '#/trades'; }")
            pg.wait_for_timeout(1500)
            g = pg.evaluate("() => ({ ghosts: document.querySelectorAll('.zs-ghost').length, held: !!document.querySelector('#page.zs-hold') })")
            check("b. leaving Home during start-up: no still copy left, the page shown", g == {"ghosts": 0, "held": False}, g)
            check("b. no page error on the other page", not errs, errs[:3])
            ctx.close()
            br.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    static()
    if os.environ.get("ZS_NO_BROWSER") != "1":
        browser()
    print(f"zenith settle: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
