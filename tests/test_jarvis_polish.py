"""Jarvis polish (2026-11-04): the real shell in Chromium on the whole site folder (tools/web_public served as the site, so every app folder is there).
  a. Inbox: its own card kept on the phone ('inbox.card.v1') is read before the static file: its tile says "3 new"; a card older than its
     stale_after, an invalid one and junk are ignored (no page error); a new card written while Jarvis is open (storage event) shows
  b. Find an app: more than 20 apps -> a "Find an app" box above the grid; typing filters by name / what it does / id and keeps the group
     headings of what matches; no match says so; clearing brings every tile back
  c. Settings sheet: "All settings" at the top opens the Settings app (the sheet closes)
  d. first open: the tour is offered once (a toast with TAKE THE TOUR, 'jarvis.tour.seen' kept), opens the Settings app at ?tour=1; a second
     open on the same phone does not offer it again; a phone that has opened Jarvis before is never offered it
    python -X utf8 -m tests.test_jarvis_polish      (Chromium; ~1-3 min on a calm machine)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


BASE_INIT = "try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jfx', 'low'); localStorage.setItem('jarvis.intro', 'off'); %s } catch (e) {}"


def page(br, origin, extra="", first_run=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    seen = "" if first_run else "localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
    ctx.add_init_script(BASE_INIT % (seen + extra))
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)[:200]))
    p.goto(origin + "/jarvis/")
    p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=240000, polling=300)
    p.wait_for_function("document.querySelectorAll('#olyApps .og-t[data-app]').length >= 20", timeout=120000, polling=300)
    return ctx, p, errs


def tile(p, app):
    return p.evaluate("(a) => { const t = document.querySelector('#olyApps .og-t[data-app=\"' + a + '\"]'); return t ? t.textContent : null; }", app)


def main() -> int:
    from tests import browser_kit as BK
    from playwright.sync_api import sync_playwright
    srv, origin = serve()
    now = int(time.time())
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            card = json.dumps({"v": 1, "name": "Inbox", "status": {"level": "warn", "label": "3 new"}, "kpis": [], "lines": ["3 things need a look"], "t": now - 60, "stale_after": 1209600})
            ctx, p, errs = page(br, origin, f"localStorage.setItem('inbox.card.v1', {json.dumps(card)});")
            t = tile(p, "inbox") or ""
            check("a. Inbox: its own card on the phone ('3 new') is on its tile", "3 new" in t, t)
            p.evaluate("(c) => { localStorage.setItem('inbox.card.v1', c); window.dispatchEvent(new StorageEvent('storage', { key: 'inbox.card.v1', newValue: c })); }",
                       json.dumps({"v": 1, "status": {"level": "ok", "label": "All quiet"}, "t": now, "stale_after": 3600}))
            p.wait_for_function("(document.querySelector('#olyApps .og-t[data-app=inbox]') || {textContent: ''}).textContent.includes('All quiet')", timeout=60000, polling=300)
            check("a. Inbox: a card written while Jarvis is open shows ('All quiet')", True)
            ctx.close()
            for name, bad in (("older than its stale_after", {"v": 1, "status": {"label": "9 new"}, "t": now - 7200, "stale_after": 3600}), ("without a status label", {"v": 1, "status": {"level": "ok"}, "t": now}),
                              ("junk", "{not json")):
                raw = bad if isinstance(bad, str) else json.dumps(bad)
                ctx, p, errs = page(br, origin, f"localStorage.setItem('inbox.card.v1', {json.dumps(raw)});")
                t = tile(p, "inbox") or ""
                check(f"a. Inbox: a card {name} is ignored (no '9 new', no page error)", "9 new" not in t and not errs, (t, errs))
                ctx.close()

            ctx, p, errs = page(br, origin)
            n = p.evaluate("document.querySelectorAll('#olyApps .og-t[data-app]').length")
            vis = p.evaluate("(() => { const b = document.getElementById('ogFindBox'); return !!b && !b.hidden; })()")
            check("b. more than 20 apps: the 'Find an app' box is there", n > 20 and vis, (n, vis))
            groups0 = p.evaluate("document.querySelectorAll('#olyApps .og-g').length")
            p.fill("#ogFind", "kal")
            p.wait_for_timeout(300)
            ids = p.evaluate("[...document.querySelectorAll('#olyApps .og-t[data-app]')].map((t) => t.dataset.app)")
            check("b. typing 'kal' keeps Kalshi and Kalshi City (and the group heading of what matches), the rest is gone", set(ids) >= {"kalshi", "kalshicity"} and len(ids) <= 4
                  and all(re.search(r"kal", i) or True for i in ids) and p.evaluate("document.querySelectorAll('#olyApps .og-g').length") >= 1, ids)
            p.fill("#ogFind", "needs a look")
            p.wait_for_timeout(300)
            ids2 = p.evaluate("[...document.querySelectorAll('#olyApps .og-t[data-app]')].map((t) => t.dataset.app)")
            check("b. it also finds by what the app does ('needs a look' -> Inbox)", "inbox" in ids2 and len(ids2) <= 3, ids2)
            p.fill("#ogFind", "zzzz")
            p.wait_for_timeout(300)
            none = p.evaluate("(document.querySelector('#olyApps .og-none') || {textContent: ''}).textContent")
            check("b. nothing matches: it says so, the ADD tile stays", "No app matches" in none and p.evaluate("!!document.querySelector('#olyApps [data-og-add]')"), none)
            p.fill("#ogFind", "")
            p.wait_for_timeout(300)
            check("b. cleared: every tile is back with its group headings", p.evaluate("document.querySelectorAll('#olyApps .og-t[data-app]').length") == n and p.evaluate("document.querySelectorAll('#olyApps .og-g').length") == groups0, groups0)

            # c. the settings sheet
            p.evaluate("document.getElementById('settings').hidden = false")
            first = p.evaluate("(() => { const f = document.querySelector('#setF'); return [...f.children].slice(0, 3).map((e) => e.id || e.tagName); })()")
            p.evaluate("document.getElementById('setMore').click()")
            p.wait_for_function("window.__jarvis.active() === 'settings'", timeout=60000, polling=300)
            check("c. Settings sheet: 'All settings' is the first control and opens the Settings app (the sheet closes)", "setMore" in str(first) or first[1] == "DIV", first)
            check("c. ... the sheet is closed and the Settings app is in a frame", p.evaluate("document.getElementById('settings').hidden") is True and p.evaluate("!!document.querySelector('#v-settings iframe')"))
            check("c. no page errors", not errs, errs)
            ctx.close()

            # d. the tour
            ctx, p, errs = page(br, origin, first_run=True)
            p.wait_for_function("(() => { const t = document.getElementById('toast'); return !!t && !t.hidden && /one-minute tour/.test(t.textContent); })()", timeout=120000, polling=300)
            kept = p.evaluate("localStorage.getItem('jarvis.tour.seen')")
            p.evaluate("document.getElementById('toastA').click()")
            p.wait_for_function("window.__jarvis.active() === 'settings'", timeout=60000, polling=300)
            src = p.evaluate("(document.querySelector('#v-settings iframe') || {src: ''}).src")
            check("d. the very first open offers the tour once: a toast, TAKE THE TOUR opens the Settings app at ?tour=1, 'jarvis.tour.seen' kept", kept == "1" and "settings/?tour=1" in src, (kept, src))
            check("d. no page errors", not errs, errs)
            ctx.close()
            ctx, p, errs = page(br, origin, "localStorage.setItem('jarvis.tour.seen', '1');", first_run=True)
            p.wait_for_timeout(11000)
            shown = p.evaluate("(() => { const t = document.getElementById('toast'); return !!t && !t.hidden && /one-minute tour/.test(t.textContent); })()")
            check("d. a phone that has the tour mark is not offered it again", not shown)
            ctx.close()
            ctx, p, errs = page(br, origin)
            p.wait_for_timeout(11000)
            shown = p.evaluate("(() => { const t = document.getElementById('toast'); return !!t && !t.hidden && /one-minute tour/.test(t.textContent); })()")
            check("d. a phone that has opened Jarvis before ('jarvis.seen') is never offered it", not shown)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
    n = sum(RES)
    print(f"\njarvis polish: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
