"""Zenith pages (2026-11-04, JOB 28 "every tab looks sick, no blank-looking pages"): zenpagescore.js (window.ZenithPages, byte-identical on
both apps), the phone glue zenith_pages.js, the PC glue web_next/js/next/zenith_pages_pc.js, the visual pass in zenith.css / zenith_pc.css,
the Bridge and pc/ pages. Read-only UI.

  a. static   core byte-identical on both apps; phone index.html loads zenith.css?v=7+, zenpagescore.js then zenith_pages.js before embed.js;
              PC index.html loads zenith_pc.css and the two scripts; the new files never fetch / POST / route / arm; Bridge + pc/ pages keep their
              content and honour reduced motion
  b. phone    Playwright 390x844: an empty page (Performance) gets the "what you will see here" card with a SAMPLE label, a sample chart, the
              page's own description and links; no sideways scroll; a chip opens Home; a loading page shows ghost cards; real content
              replaces both; Home (a real page) gets no sample card; no page errors
  c. PC       server.py + Playwright 1440x900: a loading page (Cold-Streak Filter) shows ghost cards, an empty page shows the sample card,
              the cc home stays untouched

  python -X utf8 -m tests.test_zenith_pages [--no-browser] [--shots <dir>]
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def part_a():
    core = rd("tools", "web_public", "zenpagescore.js")
    check("a. zenpagescore.js byte-identical on both apps", core == rd("web_next", "js", "next", "zenpagescore.js"))
    idx = rd("tools", "web_public", "index.html")
    head = idx[:idx.find("</head>")]
    check("a. phone: zenith.css?v=7+ in the head", any(f"zenith.css?v={n}" in head for n in range(6, 40)))
    o = [idx.find(f'src="{n}?v=') for n in ("zenith_money.js", "zenpagescore.js", "zenith_pages.js", "embed.js")]
    check("a. phone: zenpagescore.js then zenith_pages.js after zenith_money.js, before embed.js", all(i > 0 for i in o) and o == sorted(o), o)
    pidx = rd("web_next", "index.html")
    check("a. PC: zenith_pc.css + zenpagescore.js + zenith_pages_pc.js loaded", all(s in pidx for s in ("/css/zenith_pc.css", "/js/next/zenpagescore.js", "/js/next/zenith_pages_pc.js")))
    for n in (("tools", "web_public", "zenpagescore.js"), ("tools", "web_public", "zenith_pages.js"), ("web_next", "js", "next", "zenith_pages_pc.js")):
        s = rd(*n)
        check(f"a. {n[-1]} is read-only (no fetch, no POST, no /api/, no arm / order call)", all(w not in s for w in ("fetch(", "POST", "/api/", "arm_c", "place_order", "XMLHttpRequest")))
    css = rd("tools", "web_public", "zenith.css")
    check("a. zenith.css: the sample card, skeleton, aurora and reduced motion", all(w in css for w in (".zp-peek", ".zp-skel", ".space-css::after", "prefers-reduced-motion")))
    check("a. PC css carries the same pass", all(w in rd("web_next", "css", "zenith_pc.css") for w in (".zp-peek", ".zp-skel", ".space-css::after")))
    br, pc = rd("tools", "web_public", "bridge", "index.html"), rd("tools", "web_public", "pc", "index.html")
    check("a. Bridge page: visual pass, content kept, reduced motion honoured", re.search(r"JOB \d+", br) and 'id="ringArc"' in br and "prefers-reduced-motion" in br)
    check("a. pc/ page: three steps + the download link kept, reduced motion honoured", "FRESH_START.bat" in pc and pc.count('class="n"') == 3 and ("prefers-reduced-motion" in pc or ("animation" not in pc and "transition" not in pc)))   # AGORA: the page has no motion at all


def part_b(shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] b. phone Playwright not installed")
        return
    from tests import test_blitz_tab as TB
    F = TB.build()
    tmp = tempfile.mkdtemp(prefix="le_zp_")
    try:
        s = TB.site(tmp, F)
        lvp = os.path.join(tmp, "liveview.json")
        json.dump(F["lv"], open(lvp, "w"), default=str)
        srv = TB.serve(s)
        base = f"http://127.0.0.1:{srv.server_address[1]}/"
        with sync_playwright() as p:
            br = TB.launch(p)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            ctx.clock.install(time=F["T"])
            errs = []
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            lj = json.dumps(TB.live_json(F, "off"), default=str)

            def route(r):
                u = r.request.url
                if "liveview.json" in u:
                    r.fulfill(path=lvp, content_type="application/json")
                elif "/live.json" in u:
                    r.fulfill(status=200, body=lj, content_type="application/json")
                else:
                    r.fulfill(status=404, body="{}")
            pg.route("**/api.github.com/**", route)
            pg.route("**/raw.githubusercontent.com/**", route)
            pg.goto(base + "#/today")
            pg.wait_for_selector(".pl-home .su-accts", timeout=30000)
            pg.wait_for_timeout(1500)
            if pg.query_selector("#moInstX"):
                pg.click("#moInstX")
            check("b. the core is loaded (kindOf: calendar, curve, bars, list)", pg.evaluate("() => [ZenithPages.kindOf('pnlcal'), ZenithPages.kindOf('perf'), ZenithPages.kindOf('edge'), ZenithPages.kindOf('journal')].join()") == "cal,curve,bars,list")
            pg.evaluate("() => { location.hash = '#/perf'; }")
            try:
                pg.wait_for_selector("#page .zp-peek", timeout=20000)
                got = True
            except Exception:
                got = False
            txt = pg.evaluate("() => { const e = document.querySelector('#page .zp-peek'); return e ? e.innerText : ''; }")
            check("b. an empty page (Performance) gets the 'what you will see here' card", got and "what you will see here" in txt, txt[:200])
            check("b. the sample is marked 'Sample, not your data' and says when it fills in", "not your data" in txt.lower() and "when it fills in" in txt.lower(), txt[:300])
            check("b. the sample has tiles and a chart with the drawdown floor", pg.evaluate("() => !!document.querySelector('#page .zp-peek .zp-tiles span') && !!document.querySelector('#page .zp-peek .zp-svg .zp-floor')"))
            check("b. no sideways scroll with the card", pg.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 0)
            if shots:
                pg.screenshot(path=os.path.join(shots, "zp_perf_p13.png"), full_page=True)
            pg.click("#page .zp-peek [data-zp-go='today']")
            pg.wait_for_function("() => location.hash === '#/today'", timeout=5000)
            check("b. a link in the card opens Home", True)
            pg.wait_for_timeout(2200)
            check("b. Home (a real page) gets no sample card", pg.evaluate("() => !document.querySelector('#page .zp-peek')"))
            # a loading page: ghost cards; real content replaces them; no sample card on a page with content
            pg.evaluate("() => { location.hash = '#/stops'; }")
            pg.wait_for_timeout(500)
            pg.evaluate("() => { const e = document.getElementById('page'); e.innerHTML = '<div class=\"muted\">Loading…</div>'; }")
            try:
                pg.wait_for_selector("#page .zp-skel", timeout=5000)
                ok = True
            except Exception:
                ok = False
            check("b. a loading page shows ghost cards", ok)
            pg.evaluate("() => { const e = document.getElementById('page'); e.innerHTML = [1, 2, 3, 4].map((i) => '<div class=\"card\"><div class=\"card-h\"><h3>Card ' + i + '</h3></div><p>' + 'Real content for this card with enough words to count as a card with something in it. '.repeat(2) + '</p></div>').join(''); }")
            pg.wait_for_timeout(2400)
            check("b. real content replaces the ghost cards and gets no sample card", pg.evaluate("() => !document.querySelector('#page .zp-skel') && !document.querySelector('#page .zp-peek')"))
            check("b. no page errors", not errs, errs)
            br.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_c(shots):
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn
    except Exception:
        print("[SKIP] c. PC Playwright / uvicorn not installed")
        return
    import atexit
    from tests.shots_board import free_port, snapshot_files, restore_files
    from tests import test_blitz_tab as TB
    snap = snapshot_files()
    atexit.register(restore_files, snap)
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
    import server
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(300):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    with sync_playwright() as p:
        br = TB.launch(p)
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(f"pc pageerror: {str(e)[:240]}"))
        pg.goto(f"http://127.0.0.1:{port}/?fxoff", wait_until="domcontentloaded")
        pg.wait_for_function("() => window.LE && window.LE.go && window.ZenithPages", timeout=60000)
        check("c. PC: the core and the glue are loaded", pg.evaluate("() => typeof ZenithPages.peek === 'function'"))
        TB.pc_go(pg, "cc")
        pg.wait_for_timeout(2500)
        check("c. PC: the Home (cc) page is untouched (no sample card, no ghost cards)", pg.evaluate("() => !document.querySelector('.page.active .zp-peek, .page.active .zp-skel')"))
        # a page of our own (the app's pages re-render when their data arrives, and the app may open Start by itself: the helper
        # puts ours back on top and sets its content again until the glue has reacted)
        SHOW = """(html) => { document.querySelectorAll('.nx .page.active').forEach((e) => { if (e.id !== 'page-zptest') e.classList.remove('active'); });
          let e = document.getElementById('page-zptest');
          if (!e) { e = document.createElement('section'); e.className = 'page'; e.id = 'page-zptest'; document.querySelector('.nx .main').appendChild(e); }
          e.classList.add('active'); if (e.dataset.zp !== html) { e.innerHTML = html; e.dataset.zp = html; } }"""

        def show(html, sel, text=""):
            # the card and (when given) its text in ONE wait: the app may re-render and switch the active page between two separate
            # reads, which read an empty text now and then (QUALITY 2026-11-21: the flaky sample-card check)
            cond = ("(a) => { const e = document.querySelector('.page.active ' + a[0]); return !!e && (!a[1] || e.innerText.toLowerCase().includes(a[1])); }")
            for _ in range(14):
                pg.evaluate(SHOW, html)
                try:
                    pg.wait_for_function(cond, arg=[sel, text], timeout=2200)
                    return True
                except Exception:
                    pass
            return False
        ok = show('<div class="muted">Loading…</div>', ".zp-skel")
        check("c. PC: a loading page shows ghost cards", ok)
        ok = show('<div class="empty"><b>No data yet.</b>It fills after the first trade.</div>', ".zp-peek", "not your data")
        txt = pg.evaluate("() => { const e = document.querySelector('.page.active .zp-peek'); return e ? e.innerText : ''; }")
        check("c. PC: an empty page shows the sample card, marked as a sample", ok, txt[:200])
        check("c. PC: no sideways scroll", pg.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 0)
        if shots:
            pg.screenshot(path=os.path.join(shots, "zp_study_pc.png"))
        check("c. PC: no page errors", not errs, errs)
        br.close()
    srv.should_exit = True


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    part_a()
    if "--no-browser" not in sys.argv:
        part_b(shots)
        part_c(shots)
    n, ok = len(RES), sum(RES)
    print(f"\nZenith pages: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
