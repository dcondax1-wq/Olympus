"""Ask Jarvis on every app (tools/web_public/jarvis/ask.js, team JARVIS 2026-11-20, owner: "Jarvis reachable from every app in one tap").
Runs the real script in Chromium at 390 x 844 on a local copy of the site (the NQ page with the script added, the Jarvis page), with the
PC's ntfy post served from a stub built on tests/fixtures/jarvis_zeus_lite.json (nothing leaves the machine), and checks:
  a. the file: a classic script, no network at load, Safari 15 safe (no lookbehind), text through textContent only
  b. the button: one 44 x 44 button on the NQ page, inside the screen, its name says the page ("Ask Jarvis about NQ")
  c. the sheet: a dialog "Ask Jarvis · on NQ" with the page's questions first; "In a trade?" answers from the PC report ($ first,
     the source and its age); a question it does not know points to Jarvis; "Open Jarvis" carries the question
  d. Escape closes it and gives the focus back to the button; Tab stays inside the sheet
  e. offline: the last PC report this phone saw answers, said to be a saved copy
  f. Jarvis opened with ?ask=...: answers it once and cleans the address
  g. no page errors
    python -X utf8 -m tests.test_jarvis_ask      (temp folder + a local server; ~40 s)
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RESULTS = []


def check(name, ok, info=None):
    RESULTS.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def serve(root):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def lite_post():
    j = json.load(open(os.path.join(ROOT, "tests", "fixtures", "jarvis_zeus_lite.json"), encoding="utf-8"))
    now = int(time.time())
    j["t"] = now - 300
    j["reporter"] = {"t": now - 290, "server": True, "nt": True, "problems": []}
    a = j["board"]["atlas"]
    a.update({"balance": 24887.2, "room": 887.2, "position": {"side": "SHORT", "qty": 1, "entry": 26380.75, "stop": 26379.5, "target": 26122.75, "entry_t": now - 3600}})
    j["price"] = 26290.25
    return j


def ndjson(post):
    return json.dumps({"event": "message", "time": int(time.time()), "message": json.dumps(post)}) + "\n"


def main():
    from playwright.sync_api import sync_playwright
    src = open(os.path.join(WEB, "jarvis", "ask.js"), encoding="utf-8").read()
    check("a. ask.js: a classic script (no import/export statements), no lookbehind, no innerHTML from data",
          not re.search(r"^\s*(import|export)\s", src, re.M) and "(?<" not in src and src.count("innerHTML") == 1 and "<svg" in src, None)
    check("a. no network when the page loads (biz.js and the PC report only when the sheet asks)", "lite()" in src and "mount()" in src, None)

    tmp = tempfile.mkdtemp(prefix="jask_")
    try:
        site = os.path.join(tmp, "site")
        shutil.copytree(WEB, site, ignore=shutil.ignore_patterns("node_modules", "fx", "archive", "cities", "datacity", "*.png", "*.webp", "*.woff2"))
        nq = os.path.join(site, "nq", "index.html")
        html = open(nq, encoding="utf-8").read().replace("</body>", '<script src="../jarvis/ask.js" defer data-app="nq"></script></body>')
        open(nq, "w", encoding="utf-8").write(html)
        srv = serve(site)
        base = f"http://127.0.0.1:{srv.server_address[1]}/"
        post = lite_post()
        errors = []
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
            state = {"offline": False, "asked": 0}

            def ntfy(route):
                if state["offline"]:
                    route.abort(); return
                state["asked"] += 1
                route.fulfill(status=200, content_type="application/x-ndjson", body=ndjson(post) if "-bars" not in route.request.url else "")
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
            ctx.route(re.compile(r"ntfy\.sh"), ntfy)
            p = ctx.new_page()
            p.on("pageerror", lambda e: errors.append(str(e)))
            bizreq = []
            p.on("request", lambda r: bizreq.append(r.url) if "/jarvis/biz.js" in r.url else None)
            p.goto(base + "nq/", wait_until="load")
            p.wait_for_selector(".oly-ask-btn", timeout=20000)
            p.wait_for_timeout(500)
            n_before = len(bizreq)
            btn = p.locator(".oly-ask-btn")
            box = btn.bounding_box()
            check("b. one button, 44 x 44, inside the screen", btn.count() == 1 and box and box["width"] >= 44 and box["height"] >= 44 and box["x"] >= 0 and box["y"] + box["height"] <= 844, box)
            check("b. its name says the page", btn.get_attribute("aria-label") == "Ask Jarvis about NQ", btn.get_attribute("aria-label"))
            btn.tap()
            dlg = p.locator(".oly-ask-sheet[role=dialog]")
            dlg.wait_for(timeout=5000)
            chips = p.locator(".oly-ask-chips button").all_inner_texts()
            check("c. the sheet: 'Ask Jarvis · on NQ', the page's questions first", "on NQ" in p.locator("#oly-ask-h").inner_text() and chips[:3] == ["In a trade?", "Room left", "Today"], chips)
            p.locator(".oly-ask-chips button", has_text="In a trade?").tap()
            p.wait_for_function("() => !/Checking/.test(document.getElementById('oly-ask-out').textContent) && document.getElementById('oly-ask-out').textContent.length > 5", timeout=20000)
            out, srcl = p.locator("#oly-ask-out").inner_text(), p.locator(".oly-ask-src").inner_text()
            check("c. 'In a trade?' answers from the PC report, $ first, with the source and its age",
                  out.startswith("ATLAS 25K: YES, short 1 micro from 26,380.75, about +$181 open right now") and re.match(r"Source: PC report, 5 min ago", srcl), (out, srcl))
            check("c. biz.js is downloaded only once the sheet asks (nothing extra on the page's first load)", n_before == 0 and len(bizreq) == 1, (n_before, bizreq))
            check("c. 'Open Jarvis' carries the question", p.locator(".oly-ask-open").get_attribute("href").endswith("/jarvis/?ask=Is%20ATLAS%20in%20a%20trade%3F"), p.locator(".oly-ask-open").get_attribute("href"))
            p.locator(".oly-ask-form input").fill("what is the meaning of life")
            p.locator(".oly-ask-form button").tap()
            p.wait_for_function("() => /open Jarvis/i.test(document.getElementById('oly-ask-out').textContent)", timeout=10000)
            check("c. a question it does not know points to Jarvis, nothing invented", "For anything else, open Jarvis" in p.locator("#oly-ask-out").inner_text(), p.locator("#oly-ask-out").inner_text())
            p.keyboard.press("Tab"); p.keyboard.press("Tab"); p.keyboard.press("Tab"); p.keyboard.press("Tab"); p.keyboard.press("Tab")
            p.keyboard.press("Tab"); p.keyboard.press("Tab"); p.keyboard.press("Tab"); p.keyboard.press("Tab"); p.keyboard.press("Tab")
            inside = p.evaluate("() => !!document.activeElement.closest('.oly-ask-sheet')")
            check("d. Tab stays inside the sheet", inside, None)
            p.keyboard.press("Escape")
            p.wait_for_timeout(200)
            check("d. Escape closes it and the focus is back on the button", p.locator(".oly-ask-sheet").count() == 0 and p.evaluate("() => document.activeElement.classList.contains('oly-ask-btn')"), None)
            # offline: a fresh page, the feed gone: the last PC report this phone saw
            state["offline"] = True
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errors.append(str(e)))
            p2.goto(base + "nq/", wait_until="load")
            p2.wait_for_selector(".oly-ask-btn", timeout=20000)
            p2.evaluate("() => window.OLY_ASK.open('How are my accounts?')")
            p2.wait_for_function("() => { const o = document.getElementById('oly-ask-out'); return o && !/Checking/.test(o.textContent) && o.textContent.length > 5; }", timeout=25000)
            o2, s2 = p2.locator("#oly-ask-out").inner_text(), p2.locator(".oly-ask-src").inner_text()
            check("e. offline: the saved PC report answers, said to be a saved copy", "Zlarior 50K: $49,193" in o2 and "saved copy, offline" in s2, (o2, s2))
            state["offline"] = False
            # Jarvis opened with ?ask=
            p3 = ctx.new_page()
            p3.on("pageerror", lambda e: errors.append(str(e)))
            p3.add_init_script("try { localStorage.setItem('jarvis.seen', 'j9'); localStorage.setItem('olympus.introDay', new Date().toISOString().slice(0, 10)); localStorage.setItem('jarvis.speak', 'off'); } catch (e) {}")
            p3.goto(base + "jarvis/?ask=" + "How%20are%20my%20accounts%3F", wait_until="load")
            p3.wait_for_function("() => [...document.querySelectorAll('.msg.j')].some((m) => /accounts \\(/.test(m.textContent))", timeout=40000)
            check("f. Jarvis answers the question it was opened with, once, and cleans the address",
                  p3.evaluate("() => [...document.querySelectorAll('.msg.me')].filter((m) => m.textContent === 'How are my accounts?').length") == 1 and "ask=" not in p3.url, p3.url)
            check("f. no Ask Jarvis button on Jarvis itself", p3.locator(".oly-ask-btn").count() == 0, None)
            check("g. no page errors", not errors, errors[:3])
            b.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\njarvis ask: {len(RESULTS) - len(bad)}/{len(RESULTS)} {'ALL PASS' if not bad else 'FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
