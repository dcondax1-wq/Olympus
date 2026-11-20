"""Siri + Shortcuts pack (tools/web_public/jarvis/shortcuts.html + shortcuts.js, team JARVIS 2026-11-20, owner: "Olympus should work like a real
app from the home screen") and Jarvis's one-time "Add to Home Screen" hint. Chromium at 390 x 844 on a local copy of the site:
  a. the files: a classic script, text through textContent only, no account ids anywhere on the page
  b. the page: six shortcuts with their Siri phrase, steps and Copy buttons (44 px+); the links are this site's own (nq/, kalshi/,
     agency/, agency/expert/, jarvis/?ask=...) and the status link is built from status_feed.json (ntfy .../json?poll=1&since=latest);
     no sideways scroll; no page errors; without status_feed.json the spoken ones point to their Jarvis version
  c. Jarvis on an iPhone in Safari: the "Make it an app" hint once (Siri shortcuts button); not again after it was seen; never on a
     computer and never when opened from the Home Screen
    python -X utf8 -m tests.test_jarvis_shortcuts      (temp server; ~60 s)
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RESULTS = []
IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"


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


def main():
    from playwright.sync_api import sync_playwright
    js = open(os.path.join(WEB, "jarvis", "shortcuts.js"), encoding="utf-8").read()
    check("a. shortcuts.js: a classic script, textContent only (no innerHTML)", "innerHTML" not in js and not re.search(r"^\s*(import|export)\s", js, re.M), None)
    topic = json.load(open(os.path.join(WEB, "status_feed.json"), encoding="utf-8"))["topic"]
    srv = serve(WEB)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    tmp = tempfile.mkdtemp(prefix="jsc_")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(base + "jarvis/shortcuts.html", wait_until="load")
            p.wait_for_function("window.SHORTCUTS && window.SHORTCUTS.ready", timeout=15000)
            heads = p.locator(".sc-card h2").all_inner_texts()
            want = ['"Hey Siri, How are my accounts"', '"Hey Siri, Is a bot in a trade"', '"Hey Siri, Open NQ"', '"Hey Siri, Open Kalshi"', '"Hey Siri, Ask Jarvis"', '"Hey Siri, Websites next step"']
            check("b. six shortcuts with their Siri phrase", heads == want, heads)
            urls = p.locator(".sc-copy code").all_inner_texts()
            feed = f"https://ntfy.sh/{topic}/json?poll=1&since=latest"
            check("b. the status link comes from status_feed.json (the PC's latest public post)", urls.count(feed) == 2, urls[:3])
            need = [base + "nq/", base + "kalshi/", base + "agency/", base + "agency/expert/", base + "jarvis/?ask=", base + "jarvis/?ask=How%20are%20my%20accounts%3F", base + "jarvis/?ask=Is%20a%20bot%20in%20a%20trade%3F"]
            check("b. every page link is this site's own (NQ, Kalshi, Agency, Website expert, Jarvis ask)", all(u in urls for u in need), [u for u in need if u not in urls])
            steps = p.locator(".sc-steps li").count()
            check("b. each shortcut has numbered steps starting in the Shortcuts app", steps >= 18 and p.locator(".sc-steps li").first.inner_text().startswith("Open the Shortcuts app"), steps)
            m = p.evaluate("""() => ({ sw: document.documentElement.scrollWidth, small: [...document.querySelectorAll('button, a')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height < 44; }).length,
              tiny: [...document.querySelectorAll('p, li, code, h2')].filter((e) => e.getClientRects().length && parseFloat(getComputedStyle(e).fontSize) < 15).length, text: document.body.innerText })""")
            check("b. no sideways scroll at 390 px, 44 px+ buttons and links, 15 px+ text", m["sw"] <= 390 and m["small"] == 0 and m["tiny"] == 0, {k: m[k] for k in ("sw", "small", "tiny")})
            check("a. no account ids on the page (names and dollars only)", not re.search(r"mffu|b25k|eval_|\b\d{4,}\b", re.sub(r"https?://\S+", " ", m["text"].lower())), None)
            p.locator(".sc-copy button").first.click()
            try:                                            # the clipboard answers a moment later
                p.wait_for_function("['Copied', 'Selected'].includes(document.querySelector('.sc-copy button').textContent)", timeout=5000)
            except Exception:                               # noqa: BLE001 - reported below
                pass
            check("b. Copy works (or selects the link when the clipboard is not allowed)", p.locator(".sc-copy button").first.inner_text() in ("Copied", "Selected"), p.locator(".sc-copy button").first.inner_text())
            check("b. no page errors", not errs, errs[:3])
            ctx.close()
            # without status_feed.json: the spoken ones point to their Jarvis version
            ctx = b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
            ctx.route(re.compile(r".*/status_feed\.json.*"), lambda r: r.fulfill(status=404, body=""))
            p = ctx.new_page()
            p.goto(base + "jarvis/shortcuts.html", wait_until="load")
            p.wait_for_function("window.SHORTCUTS && window.SHORTCUTS.ready", timeout=15000)
            t = p.locator("#sc-accounts").inner_text()
            check("b. no status_feed.json: the accounts shortcut says so and keeps the Jarvis version", "not available on this site copy" in t and "jarvis/?ask=How%20are%20my%20accounts" in t, t[:300])
            ctx.close()
            # c. the hint on Jarvis
            def jarvis(ua, standalone=False, seen=False):
                c = b.new_context(viewport={"width": 390, "height": 844}, user_agent=ua, is_mobile=True, has_touch=True, service_workers="block")
                c.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
                c.add_init_script("try { localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.tour.seen', '1'); localStorage.setItem('olympus.tour.done', '1');"
                                  " localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('jarvis.speak', 'off'); localStorage.setItem('jarvis.alerts.v1', JSON.stringify({ speak: false, brief: false }));"
                                  + (" localStorage.setItem('jarvis.pinHint', '1');" if seen else "") + " } catch (e) {}"
                                  + (" Object.defineProperty(navigator, 'standalone', { get: () => true });" if standalone else ""))
                pg = c.new_page()
                pg.goto(base + "jarvis/", wait_until="load")
                pg.wait_for_function("document.documentElement.dataset.ready", timeout=60000)
                return c, pg
            hint = "(() => { const b = document.getElementById('wnb'); return !!b && !b.hidden && /Add to Home Screen/.test(b.textContent); })()"
            c, pg = jarvis(IPHONE_UA)
            try:
                pg.wait_for_function(hint, timeout=40000)
                shown = True
            except Exception:                               # noqa: BLE001 - reported
                shown = False
            btn = pg.locator("#wnbA").inner_text() if shown else ""
            check("c. iPhone Safari: 'Make it an app' once, with a Siri shortcuts button", shown and btn == "Siri shortcuts" and pg.evaluate("localStorage.getItem('jarvis.pinHint')") == "1", btn)
            if shown:
                pg.click("#wnbA")
                pg.wait_for_url(re.compile(r".*/jarvis/shortcuts\.html$"), timeout=10000)
                check("c. the button opens the Siri shortcuts page", pg.url.endswith("/jarvis/shortcuts.html"), pg.url)
            c.close()
            for label, ua, standalone, seen in (("seen before", IPHONE_UA, False, True), ("opened from the Home Screen", IPHONE_UA, True, False), ("a computer", None, False, False)):
                c, pg = jarvis(ua or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", standalone, seen)
                pg.wait_for_timeout(16000)
                check(f"c. no hint when {label}", not pg.evaluate(hint), None)
                c.close()
            b.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\njarvis shortcuts: {len(RESULTS) - len(bad)}/{len(RESULTS)} {'ALL PASS' if not bad else 'FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
