"""Zenith mode in the Jarvis hub (owner 2026-11-01: "on Jarvis I can switch between that mode [Jarvis], zenith mode with all
of the features"): tools/web_public/jarvis/zenith-mode.js (the full-screen Zenith layer, its floating back control and the
postMessage protocol) and Zenith's side (index.html's head + embed.js: inside-Jarvis detection, safe areas, the settings code).
Runs the real Zenith app (a copy of tools/web_public with a live-board fixture) in Chromium, inside a small Jarvis page that
mounts the module the way the hub does, with iPhone safe areas simulated (--zm-safe-*), and checks:
  a. static    the module's API + the protocol documented at its top; sw.js le-public-v50+ with the three kept lines; index.html
               loads embed.js last and adapts in its head; the settings code never lists a secret
  b. mode      show(): one full-screen layer over the Jarvis bar, Zenith inside it knows it is in Jarvis; hide() / the control:
               onExit, Zenith paused (document.hidden) but alive: the same document, its route and scroll kept
  c. control   at 375 / 390 / 430 px: inside the screen and its safe areas, never over Zenith's header, sub-bar, tab bar or
               the scroll-to-top slot; it steps aside while a full-screen layer is open; dragging docks it to the other edge
               (remembered) and is not a tap
  d. protocol  Zenith -> Jarvis: route, title, alert badge, layout; Jarvis -> Zenith: open a route (show('#/blitz'),
               zenithRouteFor("open BLITZ")); a wrong origin, another window, a real cross-origin frame or a bad route are ignored
  e. inside    data-jarvis + the safe areas once (no double padding, also in a frame below a bar), no intro, no Add to Home
               Screen card, no notification prompt, the Settings "Inside Jarvis" card, links to other sites open on their own
  f. settings  the code round trip from a separate Zenith app (its own storage, like the iPhone): only the listed keys move,
               never a key, a push state or what was seen; Apply reloads with them, Undo goes back
  h. worker    Zenith's service worker (sw.js v50) when the site answers 404 for everything (GitHub's "Site not found"), drops
               every connection or answers after 7 s: the saved copy (in under 5.5 s when slow), data flagged as the last
               copy, an older saved version of a file; no copy and no site = a dark Retry page
  g.           no page errors anywhere
    python -X utf8 -m tests.test_zenith_mode        (temp folder + a local server; nothing else touched)
"""
from __future__ import annotations

import base64
import glob
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
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    zm, sw, idx, em = rd("tools", "web_public", "jarvis", "zenith-mode.js"), rd("tools", "web_public", "sw.js"), rd("tools", "web_public", "index.html"), rd("tools", "web_public", "embed.js")
    top = zm[:zm.index("const NS_J")]
    check("a. zenith-mode.js: export function mountZenithMode({host, onExit}) -> {show(route?), hide(), isActive()}",
          "export function mountZenithMode(opts = {})" in zm and all(f"{k}," in zm or f"{k}:" in zm for k in ("show", "hide", "isActive")))
    check("a. the protocol is documented at the top: both directions, every type, same-site origin + source checks",
          all(w in top for w in ("Zenith -> Jarvis", "Jarvis -> Zenith", "hello", "state", "layout", "exit", "open", "insets", "visible", "ping",
                                 "targetOrigin", "event.origin", "event.source")))
    check(f"a. sw.js: {ZCACHE} (v50+), OTHER_APPS (every OLYMPUS app folder) / live.json bypass / own-cache cleanup kept as they were",
          f"const CACHE = '{ZCACHE}';" in sw and int(ZCACHE.rsplit("v", 1)[1]) >= 50
          and "const OTHER_APPS = ['jarvis/', 'planner/', 'kalshi/', 'datacity/', 'mind/', 'tree/', 'oracle/', 'odeon/', 'fates/', 'hermes/', 'prometheus/', 'tyche/', 'pantheon/', 'olympus/', 'arena/', 'bridge/', 'ares/', 'plutus/', 'athena/', 'forum/', 'labyrinth/', 'argus/', 'nemesis/', 'chronos/', 'hephaestus/', 'cities/', 'kalshicity/', 'settings/', 'inbox/', 'ledger/', 'journal/', 'observatory/', 'atlascity/', 'delphi/', 'pnyx/', 'pc/', 'atlas/', 'hestia/', 'demeter/', 'apollo/', 'hera/', 'dionysus/', 'clio/', 'mint/', 'mintcity/', 'mercury/', 'chrysos/', 'sibyl/', 'oikos/', 'arbiter/', 'stoa/', 'aegis/', 'lyceum/', 'nike/', 'kronos/', 'moirai/', 'epilogue/', 'argo/', 'kratos/', 'pythia/', 'gallery/', 'kairos/', 'compass/', 'pheme/', 'harmonia/', 'helios/', 'ergasterion/', 'archive/', 'pinakes/', 'colosseum/', 'nq/', 'symposium/', 'herald/'];" in sw and "url.pathname.endsWith('live.json')) return;" in sw
          and "k.startsWith('le-public-') && k !== CACHE" in sw)
    head = idx[:idx.index("</head>")]
    check("a. index.html: the inside-Jarvis check in the head (frame + same site), embed.js loaded last, no intro inside Jarvis",
          "window.frameElement" in head and "data-jarvis" in head and "--jz-sa-" in head
          and idx.index('src="polish.js?v=') < idx.index('src="embed.js?v=') and "window.LE_JARVIS)) { el.remove();" in idx)
    carry = em[em.index("const CARRY = {"):em.index("const GROUP_NAME")]
    check("a. the settings code lists no secret or device state (le.jarvis.*, push, seen, gyro, remote drafts)",
          not any(k in carry for k in ("le.jarvis", "le.push", "act.seen", "le.gyro", "rcCmd", "levels_posted", "plus.acked", "intro.day")))
    check("a. Safari 16: no regex look-behind, no top-level await in the module", "(?<" not in zm and "(?<" not in em and not re.search(r"^await ", zm, re.M))


# ------------------------------------------------------------------------------------------------ the site
HARNESS = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#0b0b0d">
<title>Jarvis</title><style>
:root { --zm-safe-top: 47px; --zm-safe-bottom: 34px; }
html, body { margin: 0; height: 100%; background: #0b0b0d; color: #f4f4f6; font: 15px system-ui; }
/* as the hub does it (tools/web_public/jarvis/, 2026-11-01): the bar on top (z-index 30), each view a fixed box under it
   with its own z-index (a stacking context below the bar), the Zenith view hidden until Zenith mode */
.bar { position: fixed; inset: 0 0 auto; z-index: 30; height: 52px; padding-top: var(--zm-safe-top); background: #151518; display: flex; gap: 8px; align-items: center; }
.view { position: fixed; left: 0; right: 0; top: calc(52px + var(--zm-safe-top)); bottom: 0; z-index: 1; }
.view[hidden] { display: none; }
#home { padding: 120px 16px; }
</style></head><body>
<header class="bar" id="bar"><button id="goJ" type="button">Jarvis</button><button id="goZ" type="button">Zenith</button></header>
<main><section class="view" id="home"><h1>Jarvis home</h1></section><section class="view" id="zhost" aria-label="Zenith" hidden></section></main>
<script type="module">
import { mountZenithMode, zenithRouteFor } from './zenith-mode.js';
window.EXITS = 0; window.STATES = []; window.EVENTS = [];
const host = document.getElementById('zhost');
host.addEventListener('zenith:state', (e) => window.EVENTS.push(e.detail));
window.SWITCHED = [];
const APPS = [{ id: 'home', name: 'Jarvis', glyph: 'orb' }, { id: 'zenith', name: 'Zenith' }, { id: 'planner', name: 'Planner', icon: '../icons/icon-192.png' }, { id: 'kalshi', name: 'Kalshi', glyph: 'K' }];
const sw = /nosw/.test(location.search) ? {} : { apps: () => APPS, onSwitch: (id) => { window.SWITCHED.push(id); window.closeZ(); } };
window.ZM = mountZenithMode({ host, onExit: () => { window.EXITS++; window.closeZ(); }, onState: (s) => window.STATES.push(s), ...sw });
window.openZ = (r) => { host.hidden = false; return window.ZM.show(r); };
window.closeZ = () => { window.ZM.hide(); host.hidden = true; };
window.zenithRouteFor = zenithRouteFor;
document.getElementById('goZ').onclick = () => window.openZ();
window.MOUNTED = true;
</script></body></html>"""
# the old way: Zenith in a frame below a bar (the frame is not on the screen's edges: no safe area of its own)
BELOW_BAR = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>:root { --zm-safe-top: 47px; --zm-safe-bottom: 34px; } html, body { margin: 0; height: 100%; background: #0b0b0d; }
.bar { position: fixed; inset: 0 0 auto; height: 52px; padding-top: var(--zm-safe-top); background: #151518; }
iframe { position: fixed; left: 0; right: 0; top: calc(52px + var(--zm-safe-top)); bottom: var(--zm-safe-bottom); width: 100%; height: calc(100% - 52px - var(--zm-safe-top) - var(--zm-safe-bottom)); border: 0; }
</style></head><body><div class="bar"></div><iframe id="f" src="../#/today"></iframe></body></html>"""
EVIL = """<!doctype html><title>other site</title><script>
// another site (another port = another origin) tries both directions of the protocol
parent.postMessage({ ns: 'le-zenith', v: 1, type: 'state', route: '#/evil', title: 'Evil', badge: 99 }, '*');
parent.postMessage({ ns: 'le-zenith', v: 1, type: 'exit' }, '*');
for (let i = 0; i < parent.frames.length; i++) { try { parent.frames[i].postMessage({ ns: 'le-jarvis', v: 1, type: 'open', route: '#/remote' }, '*'); } catch (e) {} }
document.title = 'sent';
</script>"""


def site(tmp, now):
    from tests import test_space_ui as SU
    _b2, b3 = SU.boards(now)
    base = os.path.join(tmp, "nq-dashboard")
    shutil.copytree(WEB, base, ignore=shutil.ignore_patterns("fx", "node_modules", "icon_options"))
    if os.path.isdir(os.path.join(ROOT, "web", "icons")):
        shutil.copytree(os.path.join(ROOT, "web", "icons"), os.path.join(base, "icons"), dirs_exist_ok=True)
    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 600)),
            "live": {"last_run": now - 600, "runs": 1, "pc": {"present": True, "t": now - 60, "age_s": 60, "running": True, "every_s": 60, "host": "SURFACE"}},
            "accounts": [], "results": {"periods": {}}, "trades": [], "strategy": {}, "board": b3,
            "news": {"events": [{"t": now + 5400, "title": "Initial Jobless Claims", "impact": "high"}]}}
    data["live"]["notices"] = [{"key": f"pc:{now - 900}", "kind": "pc", "t": now - 900, "title": "PC bot · back online", "body": "Heartbeat again."},
                               {"key": f"timing:{now - 300}", "kind": "timing", "t": now - 300, "title": "Eval timing", "body": "Session 3 of 10."}]
    for n in ("data.json", "home.json"):
        json.dump(data, open(os.path.join(base, n), "w"), default=str)
    open(os.path.join(base, "jarvis", "zm-test.html"), "w").write(HARNESS)
    open(os.path.join(base, "jarvis", "zm-bar.html"), "w").write(BELOW_BAR)
    other = os.path.join(tmp, "other")
    os.makedirs(other)
    open(os.path.join(other, "evil.html"), "w").write(EVIL)
    return base, other


# the site can turn bad like GitHub Pages does: slow, every connection dropped, or "Site not found" for every file
SITE = {"mode": "ok", "delay": 7.0}
GH404_SITE = (b'<!DOCTYPE html><html><head><meta http-equiv="Content-type" content="text/html; charset=utf-8"><title>Site not found'
              b' &middot; GitHub Pages</title><style>body { background-color: #f1f1f1; }</style></head><body><h1>404</h1>'
              b"<p><strong>There isn't a GitHub Pages site here.</strong></p></body></html>")


def serve(d):
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=d, **k)

        def do_GET(self):
            m = SITE["mode"]
            if m == "down":
                self.close_connection = True
                return
            if m == "404":
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(GH404_SITE)))
                self.end_headers()
                self.wfile.write(GH404_SITE)
                return
            if m == "slow":
                time.sleep(SITE["delay"])
            return super().do_GET()

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


ZENITH_READY = "() => { const p = document.querySelector('#page'); return !!p && !p.querySelector(':scope > .skel') && p.textContent.trim().length > 40; }"
# Zenith's cache name as the checkout's worker has it (v50 when this test was written; v51 2026-11-03: the Scorecard)
ZCACHE = re.search(r"const CACHE = '(le-public-v\d+)';", open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()).group(1)
SAVED = """async () => { const c = await caches.open('""" + ZCACHE + """'); const g = async (u) => { const r = await c.match(u); return r ? (await r.text()).slice(0, 60) : null; };
  return { page: await g('./index.html'), data: await g('./data.json'), home: await g('./home.json') }; }"""


def part_sw(br, base, errs):
    """Zenith's service worker (sw.js v50) when the site is slow, answers 404 for everything, or is gone."""
    ctx, pg = new_page(br, 390, 844, errs, "zenith-sw")
    try:
        SITE["mode"] = "ok"
        pg.goto(base + "#/today")
        pg.wait_for_function(ZENITH_READY, timeout=30000)
        pg.evaluate("() => navigator.serviceWorker.register('sw.js').then(() => navigator.serviceWorker.ready).then(() => true)")
        pg.reload()                                            # now the worker answers every request and keeps the copies
        pg.wait_for_function(ZENITH_READY, timeout=30000)
        pg.wait_for_function("() => !!navigator.serviceWorker.controller", timeout=10000)
        t0 = time.time()
        sv = pg.evaluate(SAVED)
        while time.time() - t0 < 10 and not all(sv.values()):
            pg.wait_for_timeout(300)
            sv = pg.evaluate(SAVED)
        check(f"h. the worker keeps Zenith's page, data.json and home.json ({ZCACHE})", all(sv.values()) and sv["page"].lower().startswith("<!doctype html"), sv)
        # a picture / a file opened in a tab is no longer saved as the app's page
        p2 = ctx.new_page()
        p2.goto(base + "manifest.webmanifest")
        p2.wait_for_timeout(400)
        p2.close()
        check("h. a file opened in a tab is cached under its own address, never as the app's page", pg.evaluate(SAVED)["page"].lower().startswith("<!doctype html"))
        # 404 for every file (GitHub's "Site not found"): the saved copy, the data flagged as the last copy
        SITE["mode"] = "404"
        pg.reload()
        ok = True
        try:
            pg.wait_for_function(ZENITH_READY, timeout=12000)
        except Exception:
            ok = False
        t = pg.evaluate("() => ({ title: document.title, gh: /Site not found|GitHub Pages site/.test(document.body.innerText), bg: getComputedStyle(document.body).backgroundColor })")
        flag = pg.evaluate("() => fetch('data.json?t=' + Date.now(), { cache: 'no-store' }).then((r) => [r.status, r.headers.get('x-le-cache')])")
        ver = pg.evaluate("() => fetch('extras.js?v=999').then(async (r) => [r.status, (await r.text()).length > 1000])")
        check("h. a 404 site: Zenith opens from its saved copy, not GitHub's 'Site not found'; data.json is the last copy, flagged",
              ok and "Zenith" in t["title"] and not t["gh"] and flag == [200, "1"], (ok, t, flag))
        check("h. a 404 site: a new version of a file the site does not give falls back to the version saved before", ver == [200, True], ver)
        # gone (every connection dropped): the saved copy
        SITE["mode"] = "down"
        pg.reload()
        ok = True
        try:
            pg.wait_for_function(ZENITH_READY, timeout=12000)
        except Exception:
            ok = False
        check("h. offline: Zenith opens from its saved copy", ok and "Zenith" in pg.title(), pg.title())
        # slow (every answer after 7 s): the saved page after 3.5 s, the data right after it (the site was just slow)
        SITE["mode"] = "slow"
        t0 = time.time()
        pg.reload(wait_until="commit", timeout=20000)
        drawn = None
        while time.time() - t0 < BK.limit(14, 'slow-site wait'):
            try:
                if pg.evaluate(ZENITH_READY):
                    drawn = round(time.time() - t0, 1)
                    break
            except Exception:
                pass
            pg.wait_for_timeout(200)
        check("h. a slow site (7 s): Zenith opens from its saved copy in under 5.5 s, not white until the site answers", drawn is not None and drawn < BK.limit(5.5, "slow site saved copy", cap=6.9), drawn)
        SITE["mode"] = "ok"
        pg.wait_for_timeout(500)
        # no saved copy and no site: a small dark page with Retry, never white
        pg.evaluate("() => caches.open('" + ZCACHE + "').then((c) => Promise.all([c.delete('./index.html'), c.delete('./')]))")
        SITE["mode"] = "down"
        pg.reload()
        pg.wait_for_timeout(600)
        nc = pg.evaluate("() => ({ text: document.body.innerText, bg: getComputedStyle(document.body).backgroundColor })")
        check("h. no saved copy and no site: the dark Retry page", "Retry" in nc["text"] and nc["bg"] == "rgb(7, 8, 12)", nc)
    finally:
        SITE["mode"] = "ok"
        ctx.close()


from tests import browser_kit as BK  # noqa: E402  (shared launch: one reused browser, load-scaled timeouts, one retry of a flaky wait)


def launch(p):
    return BK.launch(p)


def new_page(br, w, h, errs, tag, origin=None):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=True, has_touch=True)
    if origin:
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    ctx.route("**/api.github.com/**", lambda r: r.fulfill(status=404, body="{}"))          # the live feeds: not published here
    ctx.route("**/raw.githubusercontent.com/**", lambda r: r.fulfill(status=404, body="{}"))
    ctx.route("**/fonts.g*/**", lambda r: r.abort())
    ctx.route("https://example.com/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<title>example</title>"))
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"{tag} pageerror: {str(e)[:240]}"))
    pg.on("console", lambda m: errs.append(f"{tag} console.error: {m.text[:200]}")
          if m.type == "error" and "Failed to load resource" not in m.text and "net::ERR" not in m.text else None)
    pg.on("console", lambda m: WARNS.append(f"{tag}: {m.text[:200]}")
          if m.type == "warning" and re.search(r"Unrecognized feature|allowfullscreen|[Aa]llow attribute", m.text) else None)
    return ctx, pg


WARNS = []          # the frame's allow list: Chromium warns on a feature it does not know and on allow + allowfullscreen


def zframe(pg, base):
    for f in pg.frames:
        if f != pg.main_frame and f.url.split("#")[0].split("?")[0] == base:
            return f
    return None


RECTS = """() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const c = getComputedStyle(e);
  if (c.display === 'none' || c.visibility === 'hidden') return null; const b = e.getBoundingClientRect(); return b.width && b.height ? [b.left, b.top, b.right, b.bottom] : null; };
  return { top: r('.top'), sub: r('#sub'), tabs: r('#tabs'), padTop: parseFloat(getComputedStyle(document.querySelector('.top')).paddingTop),
           tabsBottom: parseFloat(getComputedStyle(document.querySelector('#tabs')).bottom), W: innerWidth, H: innerHeight,
           sa: ['top', 'right', 'bottom', 'left'].map((k) => getComputedStyle(document.documentElement).getPropertyValue('--jz-sa-' + k).trim()) }; }"""
SA_LEFT = """() => { let n = 0; const walk = (rs) => { for (const r of rs) { if (r.cssRules && !r.style) walk(r.cssRules); else if ((r.cssText || '').indexOf('safe-area-inset') >= 0) n++; } };
  for (const s of document.styleSheets) { try { walk(s.cssRules); } catch (e) { /* another site's sheet */ } }
  return { n, lv: !!document.querySelector('link[data-lv]'), hd: !!document.querySelector('link[data-hd]') }; }"""
CTRL = "() => { const b = document.querySelector('.zm-back'); const r = b.getBoundingClientRect(); return { r: [r.left, r.top, r.right, r.bottom], cls: b.className, vis: getComputedStyle(b).visibility, op: +getComputedStyle(b).opacity }; }"


def overlaps(a, b, pad=0):
    return a and b and a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


# ------------------------------------------------------------------------------------------------ b-g. the browser
def run_browser(base, other_base):
    from playwright.sync_api import sync_playwright
    errs = []
    origin = base.split("/nq-dashboard/")[0]
    with sync_playwright() as p:
        br = launch(p)
        # ---- f (first half): a separate Zenith app with its own storage (the iPhone's Zenith Home Screen app)
        cA, pA = new_page(br, 390, 844, errs, "zenith-app", origin)
        pA.goto(base + "#/today")
        pA.wait_for_function("() => window.ZenithCarry && window.POLISH", timeout=30000)
        pA.wait_for_timeout(600)
        alone = pA.evaluate("() => ({ dj: document.documentElement.dataset.jarvis || null, lej: window.LE_JARVIS === true, zij: !!window.ZenithInJarvis, inst: !!document.querySelector('#moInst') && document.querySelector('#moInst').offsetParent !== null, sa: getComputedStyle(document.documentElement).getPropertyValue('--jz-sa-top').trim() })")
        alone["env"] = pA.evaluate(SA_LEFT)["n"]
        check("e. outside Jarvis nothing changes: no data-jarvis, no protocol, no --jz-sa-*, env() untouched, the Add to Home Screen card still shows in a browser",
              alone["dj"] is None and not alone["lej"] and not alone["zij"] and alone["sa"] == "" and alone["inst"] and alone["env"] >= 7, alone)
        pA.evaluate("""() => { const s = (k, v) => localStorage.setItem(k, JSON.stringify(v));
          s('le.accent', 'teal'); s('le.more.zoom', 1.1); s('le.motion', false); s('le.more.notify', { fill: false }); s('le.trYear', '2025'); s('le.howto.rules', true);
          s('le.holo.tf', '1m'); localStorage.setItem('le-perf-tab', 'month');
          s('le.jarvis.llm', { key: 'sk-ant-SECRET', on: true }); s('le.push.posted', { id: 'abc', key: 'k', t: 1 }); s('le.act.seen', 123); s('le.gyro', true); s('le.rcCmd', 'kill');
          s('le.intro.day', '2026-11-01'); s('le.feat.q', 'x'); s('le.plus.levels_posted', 5); }""")
        pA.evaluate("() => { location.hash = '#/settings'; }")
        pA.wait_for_selector("#zcCard[data-where='app'] #zcCopy", timeout=15000)
        pA.click("#zcCopy")
        pA.wait_for_timeout(400)
        code = pA.evaluate("() => navigator.clipboard.readText()")
        dec = json.loads(base64.urlsafe_b64decode(code.split(".")[1] + "=" * (-len(code.split(".")[1]) % 4)).decode()) if code.startswith("ZEN1.") else {}
        keys = set((dec.get("s") or {}).keys())
        check("f. Zenith app > Settings > Copy settings code: one ZEN1 line on the clipboard with the listed settings",
              code.startswith("ZEN1.") and {"le.accent", "le.more.zoom", "le.motion", "le.more.notify", "le.trYear", "le.howto.rules", "le.holo.tf", "le-perf-tab"} <= keys, sorted(keys))
        check("f. never in the code: the AI key, the push subscription state, what was seen, tilt, remote-control drafts, searches",
              not keys & {"le.jarvis.llm", "le.push.posted", "le.act.seen", "le.gyro", "le.rcCmd", "le.intro.day", "le.feat.q", "le.plus.levels_posted"}
              and "SECRET" not in code and "sk-ant" not in json.dumps(dec), sorted(keys))
        cA.close()

        # ---- b. the mode switch (Jarvis page at 390 x 844, iPhone safe areas 47 / 34)
        ctx, pg = new_page(br, 390, 844, errs, "jarvis", origin)
        pg.goto(base + "jarvis/zm-test.html")
        pg.wait_for_function("() => window.MOUNTED === true", timeout=15000)
        lazy = pg.evaluate("() => ({ frames: document.querySelectorAll('iframe').length, active: ZM.isActive() })")
        check("b. mounted lazily: no Zenith frame until the first show() (iPhone memory)", lazy == {"frames": 0, "active": False}, lazy)
        pg.click("#goZ")
        pg.wait_for_function("() => ZM.state().ready && window.STATES.length > 0", timeout=30000)
        z = zframe(pg, base)
        z.wait_for_function("() => window.POLISH && document.querySelector('#tabs a')", timeout=30000)
        pg.wait_for_timeout(900)
        cov = pg.evaluate("""() => { const at = (x, y) => document.elementFromPoint(x, y); const b = document.getElementById('bar').getBoundingClientRect();
          return { active: ZM.isActive(), layer: getComputedStyle(document.querySelector('.zm-root')).visibility, top: at(200, b.top + 60).className, mid: at(200, 400).className,
                   theme: document.querySelector('meta[name=theme-color]').content, modal: document.querySelector('.zm-root').getAttribute('aria-modal') }; }""")
        cov["lift"] = pg.evaluate("() => document.getElementById('zhost').style.getPropertyValue('z-index')")
        check("b. show(): Zenith full screen over the Jarvis bar (the hub's view lifted above it, one layer, aria-modal), the status bar tint follows Zenith",
              cov["active"] and cov["layer"] == "visible" and cov["top"] == "zm-frame" and cov["mid"] == "zm-frame" and cov["theme"] == "#07080c" and cov["modal"] == "true"
              and "2147483000" in cov["lift"] and pg.evaluate("() => !!document.querySelector('#zhost .zm-root iframe.zm-frame')"), cov)
        tip = pg.evaluate("() => ({ n: localStorage.getItem('jarvis.zenith.tips'), t: document.querySelector('.zm-back .zm-tip').textContent, a: document.querySelector('.zm-back').getAttribute('aria-label') })")
        check("c. the control says what it does: 'Back to Jarvis' (its label, and a hint the first three times: 'hold for apps')",
              tip == {"n": "1", "t": "Back to Jarvis · hold for apps", "a": "Back to Jarvis"}, tip)
        inside = z.evaluate("() => ({ dj: document.documentElement.dataset.jarvis, lej: window.LE_JARVIS, splash: !!document.getElementById('splash'), inst: !!document.querySelector('#moInst') && document.querySelector('#moInst').offsetParent !== null, prompt: !!document.querySelector('#pushPrompt') && document.querySelector('#pushPrompt').offsetParent !== null })")
        check("e. inside Jarvis Zenith knows it (data-jarvis, LE_JARVIS): no intro, no Add to Home Screen card, no notification prompt",
              inside["dj"] == "on" and inside["lej"] is True and not inside["splash"] and not inside["inst"] and not inside["prompt"], inside)
        R = z.evaluate(RECTS)
        check("e. safe areas once: Jarvis's 47 / 34 px reach Zenith (header 10 + 47, tab bar 10 + 34 from the bottom), not doubled",
              R["sa"][0] == "47px" and R["sa"][2] == "34px" and abs(R["padTop"] - 57) < 0.6 and abs(R["tabsBottom"] - 44) < 0.6, R)
        s0 = pg.evaluate("() => window.STATES[window.STATES.length - 1]")
        check("d. Zenith -> Jarvis: hello / state with the route and the page title", s0 and s0["route"] == "#/today" and s0["title"] == "Home" and s0["active"], s0)
        # the alert badge: unseen activity (index.html actBadge) reaches Jarvis
        z.evaluate("() => { localStorage.setItem('le.act.seen', '0'); window.actBadge && window.actBadge(); }")
        pg.wait_for_timeout(300)
        bd = pg.evaluate("() => ZM.state().badge")
        n_unseen = z.evaluate("() => (typeof activity === 'function' ? activity().length : 0)")
        check("d. Zenith -> Jarvis: the alert badge (unseen activity, the same number as the app icon)", bd == n_unseen >= 2, (bd, n_unseen))
        z.evaluate("() => { localStorage.setItem('le.act.seen', String(Math.round(Date.now() / 1000) + 9e5)); window.actBadge && window.actBadge(); }")

        # ---- c. the control at 390 (then 375 and 430 below)
        def control_ok(tag, sa_top, sa_bottom):
            z.wait_for_timeout(150)
            R = z.evaluate(RECTS)
            C = pg.evaluate(CTRL)
            H, W = R["H"], R["W"]
            hdr = max([x[3] for x in (R["top"], R["sub"]) if x] or [0])
            tabs_top = R["tabs"][1] if R["tabs"] else H
            r = C["r"]
            ok = (r[1] >= max(hdr, sa_top) + 7.5 and r[3] <= tabs_top - 62 - 7.5 and r[3] <= H - sa_bottom and abs(r[2] - W) < 0.6 and r[0] >= W - 44.6
                  and not overlaps(r, R["top"]) and not overlaps(r, R["sub"]) and not overlaps(r, R["tabs"]) and r[2] - r[0] >= 43.5 and r[3] - r[1] >= 47.5
                  and C["vis"] == "visible")
            check(f"c. {tag}: the control is on the right edge, 44 x 48, between Zenith's header ({hdr:.0f}) and the tab bar's scroll-to-top slot ({tabs_top - 62:.0f}), over neither",
                  ok, {"ctrl": r, "hdr": hdr, "tabs": R["tabs"], "H": H, "W": W, "cls": C["cls"]})
        control_ok("390 x 844 (Home)", 47, 34)
        z.evaluate("() => { location.hash = '#/blitz'; }")
        pg.wait_for_function("() => ZM.state().route === '#/blitz'", timeout=10000)
        pg.wait_for_timeout(400)
        control_ok("390 x 844 (BLITZ, with its sub-bar)", 47, 34)
        st = pg.evaluate("() => ({ s: ZM.state(), ss: sessionStorage.getItem('jarvis.zenith.route') })")
        check("d. Zenith -> Jarvis: a tab in Zenith moves Jarvis's route + title (kept this session)",
              st["s"]["route"] == "#/blitz" and st["s"]["title"] == "BLITZ" and json.loads(st["ss"] or "null") == "#/blitz", st)
        for (w, h, top) in ((375, 812, 44), (430, 932, 59)):
            pg.evaluate(f"() => document.documentElement.style.setProperty('--zm-safe-top', '{top}px')")
            pg.set_viewport_size({"width": w, "height": h})
            pg.wait_for_timeout(700)
            R2 = z.evaluate(RECTS)
            check(f"c. {w} x {h}: Zenith gets the new safe area ({top} px) and fits the width", R2["sa"][0] == f"{top}px" and R2["W"] == w
                  and z.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), R2["sa"])
            control_ok(f"{w} x {h} (BLITZ)", top, 34)
        pg.evaluate("() => document.documentElement.style.setProperty('--zm-safe-top', '47px')")
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(500)
        # a full-screen layer in Zenith (the search palette): the control steps aside, and comes back
        z.click("#plFind")
        z.wait_for_selector("#plPal.on", timeout=5000)
        pg.wait_for_function("() => document.querySelector('.zm-back').classList.contains('cov')", timeout=4000)
        pg.wait_for_timeout(350)                          # its fade
        hid = pg.evaluate(CTRL)
        z.press("#plQ", "Escape")
        pg.wait_for_function("() => !document.querySelector('.zm-back').classList.contains('cov')", timeout=4000)
        pg.wait_for_timeout(350)
        back = pg.evaluate(CTRL)
        check("c. a full-screen layer (the search palette) open in Zenith: the control steps aside, then comes back",
              hid["vis"] == "hidden" and hid["op"] == 0 and back["vis"] == "visible" and back["op"] > 0.5, (hid, back))
        # drag to the left edge: docks there, remembered, not a tap
        r = pg.evaluate(CTRL)["r"]
        x0, y0 = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        pg.mouse.move(x0, y0)
        pg.mouse.down()
        pg.mouse.move(x0 - 120, y0 - 60, steps=6)
        pg.mouse.move(40, y0 - 90, steps=6)
        pg.mouse.up()
        pg.wait_for_timeout(450)
        d1 = pg.evaluate("() => ({ c: document.querySelector('.zm-back').className, r: document.querySelector('.zm-back').getBoundingClientRect().left, exits: window.EXITS, active: ZM.isActive(), dock: JSON.parse(localStorage.getItem('jarvis.zenith.dock') || 'null') })")
        check("c. drag: the control docks on the left edge, the spot is remembered, and a drag is not a tap (still in Zenith mode)",
              "left" in d1["c"].split() and d1["r"] == 0 and d1["exits"] == 0 and d1["active"] and d1["dock"] and d1["dock"]["side"] == "left", d1)
        control_left = pg.evaluate(CTRL)["r"]
        Rl = z.evaluate(RECTS)
        check("c. on the left edge it still keeps clear of the header and the tab bar", not overlaps(control_left, Rl["top"]) and not overlaps(control_left, Rl["sub"])
              and not overlaps(control_left, Rl["tabs"]), control_left)
        pg.mouse.move(22, (control_left[1] + control_left[3]) / 2)
        pg.mouse.down()
        pg.mouse.move(200, 500, steps=6)
        pg.mouse.move(380, 520, steps=6)
        pg.mouse.up()
        pg.wait_for_timeout(450)
        check("c. and back to the right edge", "left" not in pg.evaluate(CTRL)["cls"].split() and pg.evaluate("() => window.EXITS") == 0)

        # ---- b. back to Jarvis with the control: Zenith paused, alive, route + scroll kept
        z.evaluate("() => { window.__alive = 'same document'; scrollTo(0, 420); }")
        y_before = z.evaluate("() => scrollY")
        pg.click(".zm-back")
        pg.wait_for_timeout(450)
        b1 = pg.evaluate("() => ({ active: ZM.isActive(), exits: window.EXITS, layer: getComputedStyle(document.querySelector('.zm-root')).visibility, frames: document.querySelectorAll('.zm-frame').length, theme: document.querySelector('meta[name=theme-color]').content, bar: document.elementFromPoint(200, 70).closest('#bar') !== null })")
        zb = z.evaluate("() => ({ hidden: document.hidden, vs: document.visibilityState, hash: location.hash, alive: window.__alive })")
        b1["lift"] = pg.evaluate("() => document.getElementById('zhost').style.getPropertyValue('z-index')")
        check("b. the control goes back to Jarvis: onExit once, the layer hidden, the Jarvis bar usable, the status bar tint and the view's z-index back",
              not b1["active"] and b1["exits"] == 1 and b1["layer"] == "hidden" and b1["theme"] == "#0b0b0d" and b1["bar"] and b1["lift"] == "", b1)
        check("b. while Jarvis mode shows Zenith is paused like a backgrounded app (document.hidden) but alive: same document, same route",
              zb["hidden"] is True and zb["vs"] == "hidden" and zb["hash"] == "#/blitz" and zb["alive"] == "same document" and b1["frames"] == 1, zb)
        pg.click("#goZ")
        pg.wait_for_timeout(500)
        za = z.evaluate("() => ({ hidden: document.hidden, hash: location.hash, alive: window.__alive, y: scrollY })")
        check("b. Zenith mode again (the hub had hidden its view: display:none): no reload, the same page and scroll (Zenith resumes)",
              za["hidden"] is False and za["hash"] == "#/blitz" and za["alive"] == "same document" and abs(za["y"] - y_before) < 3 and pg.evaluate("() => ZM.isActive()"), za)

        # ---- d. Jarvis -> Zenith: open a route
        pg.evaluate("() => openZ('#/atlas/trades')")
        z.wait_for_function("() => location.hash === '#/atlas/trades'", timeout=8000)
        pg.wait_for_function("() => ZM.state().route === '#/atlas/trades'", timeout=8000)
        check("d. Jarvis -> Zenith: show('#/atlas/trades') opens that page, Zenith reports it back", True)
        rt = pg.evaluate("() => [zenithRouteFor('open BLITZ'), zenithRouteFor('blitz brain'), zenithRouteFor('show me the holodeck'), zenithRouteFor('zlarior results'), zenithRouteFor('open planner')]")
        check("d. zenithRouteFor: 'open BLITZ' -> #/blitz, 'blitz brain' -> #/blitz/brain, holodeck -> #/holo, Zlarior results -> #/perf, planner -> none",
              rt == ["#/blitz", "#/blitz/brain", "#/holo", "#/perf", None], rt)
        pg.evaluate("() => { closeZ(); openZ(zenithRouteFor('open BLITZ')); }")
        z.wait_for_function("() => location.hash === '#/blitz'", timeout=8000)
        check("d. Jarvis's brain hears 'open BLITZ': Zenith mode at #/blitz", pg.evaluate("() => ZM.isActive() && ZM.state().route") == "#/blitz")

        # ---- d. origin checks, both directions
        z.evaluate("""() => { const d = { ns: 'le-jarvis', v: 1, type: 'open', route: '#/settings' };
          window.dispatchEvent(new MessageEvent('message', { data: d, origin: 'https://evil.example', source: window.parent }));
          window.dispatchEvent(new MessageEvent('message', { data: d, origin: location.origin, source: window }));
          window.dispatchEvent(new MessageEvent('message', { data: d, origin: location.origin, source: null }));
          window.dispatchEvent(new MessageEvent('message', { data: { ...d, route: 'javascript:alert(1)' }, origin: location.origin, source: window.parent }));
          window.dispatchEvent(new MessageEvent('message', { data: { ...d, route: '#/x"><img src=x onerror=alert(1)>' }, origin: location.origin, source: window.parent })); }""")
        pg.wait_for_timeout(300)
        check("d. Zenith ignores an open from another origin, from a window that is not Jarvis, or with a bad route",
              z.evaluate("() => location.hash") == "#/blitz")
        pg.evaluate("""() => { const f = ZM.frame.contentWindow;
          window.dispatchEvent(new MessageEvent('message', { data: { ns: 'le-zenith', v: 1, type: 'exit' }, origin: 'https://evil.example', source: f }));
          window.dispatchEvent(new MessageEvent('message', { data: { ns: 'le-zenith', v: 1, type: 'state', route: '#/evil' }, origin: location.origin, source: window }));
          const x = document.createElement('iframe'); x.id = 'same'; x.srcdoc = '<p>x</p>'; document.body.appendChild(x);
          window.dispatchEvent(new MessageEvent('message', { data: { ns: 'le-zenith', v: 1, type: 'exit' }, origin: location.origin, source: x.contentWindow }));
          window.dispatchEvent(new MessageEvent('message', { data: { ns: 'le-zenith', v: 2, type: 'exit' }, origin: location.origin, source: f })); }""")
        pg.wait_for_timeout(200)
        g1 = pg.evaluate("() => ({ active: ZM.isActive(), exits: window.EXITS, route: ZM.state().route })")
        check("d. Jarvis ignores Zenith messages from another origin, another window of this site, or another protocol version",
              g1 == {"active": True, "exits": 1, "route": "#/blitz"}, g1)
        pg.evaluate(f"() => {{ const x = document.createElement('iframe'); x.id = 'evil'; x.src = '{other_base}evil.html'; x.style.cssText = 'position:fixed;left:0;top:0;width:10px;height:10px'; document.body.appendChild(x); }}")
        pg.wait_for_timeout(1500)
        g2 = pg.evaluate("() => ({ active: ZM.isActive(), exits: window.EXITS, route: ZM.state().route, title: ZM.state().title, badge: ZM.state().badge })")
        zh = z.evaluate("() => location.hash")
        check("d. a real frame of another site (other origin) posting both ways changes nothing (no exit, no route, no badge, Zenith stays)",
              g2["active"] and g2["exits"] == 1 and g2["route"] == "#/blitz" and g2["title"] != "Evil" and g2["badge"] != 99 and zh == "#/blitz", (g2, zh))
        pg.evaluate("() => { document.getElementById('evil').remove(); document.getElementById('same').remove(); }")

        # ---- e. a link to another site opens on its own; the frame stays on Zenith
        z.evaluate("() => { const a = document.createElement('a'); a.id = 'extL'; a.href = 'https://example.com/docs'; a.textContent = 'example'; a.style.cssText = 'position:fixed;left:40px;top:300px;z-index:99999;padding:20px;background:#fff'; document.body.appendChild(a); }")
        with pg.expect_popup(timeout=8000) as pop:
            z.click("#extL")
        pp = pop.value
        check("e. a link to another site opens on its own (never inside the frame), Zenith stays", "example.com" in pp.url and z.evaluate("() => location.hash") == "#/blitz"
              and zframe(pg, base) is not None, pp.url)
        pp.close()
        z.evaluate("() => document.getElementById('extL').remove()")

        # ---- e. full-screen Holodeck / Live View report 'cover' (when they open on this fixture)
        z.evaluate("() => { location.hash = '#/settings'; }")
        z.wait_for_selector("#zcCard[data-where='jarvis']", timeout=15000)
        sj = z.evaluate("""() => ({ card: !!document.querySelector('#zcCard[data-where=jarvis] #zcPaste'), home: [...document.querySelectorAll('.card h3')].some((h) => /^Home Screen app/.test(h.textContent.trim())),
          note: !!document.querySelector('#pushCardS .zc-jnote'), first: (() => { const c = document.getElementById('zcCard'); const p = document.getElementById('page'); return [...p.children].indexOf(c); })() })""")
        check("e. Settings inside Jarvis: the 'Inside Jarvis' card near the top, no install card, a note that notifications come to the Zenith app",
              sj["card"] and not sj["home"] and sj["note"] and 0 <= sj["first"] <= 3, sj)
        check("e. Settings inside Jarvis: 'Back to Jarvis' asks Jarvis (exit) and Jarvis goes back", True if (z.click("#zcBack") or True) and pg.wait_for_function("() => !ZM.isActive() && window.EXITS === 2", timeout=4000) else False)
        pg.click("#goZ")
        pg.wait_for_timeout(400)

        # ---- f (second half): paste the code from the Zenith app; Apply; Undo
        before = z.evaluate("() => ({ accent: document.documentElement.dataset.accent, zoom: localStorage.getItem('le.more.zoom'), key: localStorage.getItem('le.jarvis.llm') })")
        z.fill("#zcText", code[:40] + "\n" + code[40:])
        msg = z.inner_text("#zcMsg")
        check("f. Jarvis's Zenith > Settings > paste: it says what the code holds before anything changes",
              re.search(r"^\d+ settings from .+: look and motion \(\d+\)", msg) and "page choices" in msg and z.evaluate("() => !document.getElementById('zcApply').disabled")
              and before["zoom"] is None, (msg, before))
        bad_codes = [code[:30] + ("B" if code[30] != "B" else "C") + code[31:], code[:-12], "hello"]
        said = []
        for bc in bad_codes:
            z.fill("#zcText", bc)
            said.append((z.inner_text("#zcMsg"), z.evaluate("() => document.getElementById('zcApply').disabled")))
        check("f. a changed or cut code is refused (checksum), and text that is not a code says so; Apply stays off",
              "cut short or changed" in said[0][0] and "cut short or changed" in said[1][0] and "not a Zenith settings code" in said[2][0] and all(x[1] for x in said), said)
        z.fill("#zcText", code)
        hello_n = pg.evaluate("() => window.STATES.length")
        z.click("#zcApply")
        z.wait_for_function("() => window.ZenithCarry && document.readyState === 'complete' && performance.navigation && performance.getEntriesByType('navigation')[0].type === 'reload'", timeout=20000)
        z.wait_for_timeout(600)
        after = z.evaluate("() => ({ accent: document.documentElement.dataset.accent, motion: document.documentElement.dataset.motion, zoom: localStorage.getItem('le.more.zoom'), tr: localStorage.getItem('le.trYear'), pt: localStorage.getItem('le-perf-tab'), key: localStorage.getItem('le.jarvis.llm'), push: localStorage.getItem('le.push.posted'), seen: localStorage.getItem('le.act.seen') })")
        check("f. Apply: Zenith reloads with the Zenith app's settings (accent teal, motion off, text size, page choices) and nothing secret",
              after["accent"] == "teal" and after["motion"] == "off" and after["zoom"] == "1.1" and after["tr"] == '"2025"' and after["pt"] == "month"
              and after["key"] is None and after["push"] is None, after)
        pg.wait_for_function(f"() => window.STATES.length > {hello_n} || ZM.state().ready", timeout=10000)
        check("d. after Zenith reloads it says hello again and Jarvis keeps its route", pg.evaluate("() => ZM.state().ready && ZM.isActive()"))
        z.wait_for_selector("#zcUndo", timeout=10000)
        z.click("#zcUndo")
        z.wait_for_function("() => document.documentElement.dataset.accent === 'indigo'", timeout=20000)
        un = z.evaluate("() => ({ zoom: localStorage.getItem('le.more.zoom'), tr: localStorage.getItem('le.trYear'), undo: localStorage.getItem('le.carry.undo') })")
        check("f. Undo: back to the settings Jarvis's Zenith had before the paste", un["zoom"] is None and un["tr"] is None and un["undo"] is None, un)
        # ---- the audit inside the frame: clipboard, a download, notifications
        z.evaluate("() => { location.hash = '#/settings'; }")
        z.wait_for_selector("#zcCard[data-where='jarvis'] .zc-what summary", timeout=15000)
        z.click("#zcCard .zc-what summary")
        z.click("#zcCard #zcCopy")
        z.wait_for_timeout(300)
        clip = z.evaluate("() => navigator.clipboard.readText().catch((e) => 'ERR ' + e)")
        check("e. clipboard inside Jarvis: a copy button writes to the phone's clipboard", clip.startswith("ZEN1."), clip[:80])
        z.evaluate("() => { location.hash = '#/board'; }")
        z.wait_for_selector("[data-bd-csv]", timeout=15000)
        with pg.expect_download(timeout=8000) as dl:
            z.click("[data-bd-csv]")
        check("e. download inside Jarvis: the live board's Export CSV saves a file", dl.value.suggested_filename.endswith(".csv"), dl.value.suggested_filename)
        ctx.grant_permissions(["notifications"], origin=origin)
        ps = z.evaluate("""async () => { D.live.push = { vapid_public: 'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U' };
          const r = await pushEnsure(false); const reg = await navigator.serviceWorker.getRegistration(); const sub = reg ? await reg.pushManager.getSubscription() : null;
          return { state: r && r.state, sub: !!sub, perm: Notification.permission }; }""")
        check("e. notifications inside Jarvis: allowed for the site but never tapped here = no second subscription (no double pushes)",
              ps["perm"] == "granted" and ps["state"] == "off" and not ps["sub"], ps)
        # every tab renders inside Jarvis at phone width (no sideways scroll, no 'could not draw')
        bad = []
        for h in ("#/today", "#/lit", "#/atlas", "#/blitz", "#/real", "#/system", "#/liveview", "#/holo", "#/mission", "#/activity", "#/alerts"):
            z.evaluate(f"() => {{ location.hash = '{h}'; }}")
            z.wait_for_timeout(700)
            s = z.evaluate("() => ({ x: document.documentElement.scrollWidth - innerWidth, t: (document.querySelector('#page').innerText || '').length, err: /Could not draw this page/.test(document.querySelector('#page').innerText) })")
            if s["x"] > 1 or s["t"] < 40 or s["err"]:
                bad.append((h, s))
        check("e. every tab and Live View / Holodeck / Mission render inside Jarvis at 390 px: no sideways scroll, no 'could not draw'", not bad, bad)
        sa = z.evaluate(SA_LEFT)
        check("e. inside Jarvis every env(safe-area-inset-*) of Zenith's CSS reads Jarvis's insets, also the sheets added later (Live View, Holodeck)",
              sa["n"] == 0 and sa["lv"] and sa["hd"], sa)
        # the Holodeck full screen (on the iPhone: the page covers the screen) is a layer the control steps aside for
        z.evaluate("() => { location.hash = '#/holo'; }")
        z.wait_for_selector(".hd-root", timeout=15000)
        z.evaluate("() => document.querySelector('.hd-root').classList.add('hd-max')")
        pg.wait_for_function("() => document.querySelector('.zm-back').classList.contains('cov')", timeout=4000)
        z.evaluate("() => document.querySelector('.hd-root').classList.remove('hd-max')")
        pg.wait_for_function("() => !document.querySelector('.zm-back').classList.contains('cov')", timeout=4000)
        check("c. the Holodeck full screen: the control steps aside while it covers the screen, then comes back", True)
        z.evaluate("() => { location.hash = '#/alerts'; }")
        # ---- the switcher: hold the control = the other apps as chips; a chip = onSwitch(id); tap = back to Jarvis as before
        APPS_JS = """() => { const p = document.querySelector('.zm-apps'), b = document.querySelector('.zm-back').getBoundingClientRect();
          if (!p || p.hidden) return null; const r = p.getBoundingClientRect();
          return { names: [...p.querySelectorAll('.zm-chip')].map((c) => c.lastElementChild.textContent.trim()), h: Math.min(...[...p.querySelectorAll('.zm-chip')].map((c) => c.getBoundingClientRect().height)),
                   r: [r.left, r.top, r.right, r.bottom], ctrl: [b.left, b.top, b.right, b.bottom], W: innerWidth, H: innerHeight, exp: document.querySelector('.zm-back').getAttribute('aria-expanded') }; }"""
        def hold(ms=650, release_at=None):
            r = pg.evaluate(CTRL)["r"]
            pg.mouse.move((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
            pg.mouse.down()
            pg.wait_for_timeout(ms)
            if release_at:
                pg.mouse.move(*release_at, steps=4)
            pg.mouse.up()
            pg.wait_for_timeout(250)
        e0 = pg.evaluate("() => window.EXITS")
        hold()
        A = pg.evaluate(APPS_JS)
        Rz = z.evaluate(RECTS)
        tabs_top = Rz["tabs"][1] if Rz["tabs"] else A["H"]
        hdr = max([x[3] for x in (Rz["top"], Rz["sub"]) if x] or [0])
        check("c. switcher: holding the control shows the other apps as chips (Jarvis, Planner, Kalshi; not Zenith), 44 px tall, still in Zenith mode",
              A and A["names"] == ["Jarvis", "Planner", "Kalshi"] and A["h"] >= 43.5 and A["exp"] == "true"
              and pg.evaluate("() => ZM.isActive() && window.EXITS") == e0, A)
        look = pg.evaluate("""() => { const cs = (s) => getComputedStyle(document.querySelector(s)); const p = cs('.zm-back .zm-pill'), a = cs('.zm-apps'), c = cs('.zm-apps .zm-chip');
          const img = document.querySelector(".zm-apps .zm-chip[data-app='planner'] img.zm-ci"), gl = document.querySelector(".zm-apps .zm-chip[data-app='kalshi'] .zm-gl");
          return { pill: [p.borderTopColor, p.backgroundColor, p.boxShadow.includes('168, 85, 247')], apps: [a.borderTopColor, a.backgroundColor], font: c.fontFamily, upper: c.textTransform,
                   chipH: Math.min(...[...document.querySelectorAll('.zm-apps .zm-chip')].map((x) => x.getBoundingClientRect().height)),
                   img: !!img && img.complete && img.naturalWidth > 0, gl: gl && gl.textContent, ctl: [document.querySelector('.zm-back').offsetWidth, document.querySelector('.zm-back').offsetHeight] }; }""")
        check("c. Jarvis look: dark glass rgba(12,10,20,.85) with the violet #a855f7 border and glow, Orbitron labels, 44 px targets, the app's icon in its chip",
              look["pill"][:2] == ["rgba(168, 85, 247, 0.62)", "rgba(12, 10, 20, 0.85)"] and look["pill"][2] and look["apps"] == ["rgba(168, 85, 247, 0.55)", "rgba(12, 10, 20, 0.85)"]
              and "Orbitron" in look["font"] and look["upper"] == "uppercase" and look["chipH"] >= 44 and look["ctl"][0] >= 44 and look["ctl"][1] >= 44
              and look["img"] and look["gl"] == "K", look)
        pg.evaluate("() => { document.documentElement.style.setProperty('--c', '#ff2bd6'); document.documentElement.style.setProperty('--pr', '18,10,61'); }")
        pg.wait_for_timeout(400)                               # the chips' colour transition
        th = pg.evaluate("() => { const p = getComputedStyle(document.querySelector('.zm-back .zm-pill')), c = getComputedStyle(document.querySelector('.zm-apps .zm-chip')); return [p.borderTopColor, p.backgroundColor, c.borderTopColor]; }")
        pg.evaluate("() => { document.documentElement.style.removeProperty('--c'); document.documentElement.style.removeProperty('--pr'); }")
        check("c. the page's theme carries over (--c / --pr on Jarvis's <html>): a pink theme gives pink borders on its own glass",
              th == ["rgba(255, 43, 214, 0.62)", "rgba(18, 10, 61, 0.85)", "rgba(255, 43, 214, 0.32)"], th)
        check("c. switcher: the chips sit next to the control, inside the screen, between Zenith's header and its tab bar",
              A and A["r"][2] <= A["ctrl"][0] + 0.5 and A["r"][0] >= 0 and A["r"][1] >= hdr and A["r"][3] <= tabs_top and not overlaps(A["r"], Rz["tabs"]), (A, hdr, tabs_top))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)
        esc_closed = pg.evaluate(APPS_JS) is None
        hold()
        pg.mouse.click(60, 400)                               # outside the chips: they close, Zenith stays
        pg.wait_for_timeout(250)
        out_closed = pg.evaluate(APPS_JS) is None and pg.evaluate("() => ZM.isActive()")
        check("c. switcher: Escape or a tap outside closes the chips, Zenith mode stays", esc_closed and out_closed, (esc_closed, out_closed))
        hold()
        pg.click(".zm-apps .zm-chip[data-app='planner']")
        pg.wait_for_timeout(300)
        s1 = pg.evaluate("() => ({ sw: window.SWITCHED.slice(), active: ZM.isActive(), exits: window.EXITS })")
        check("c. switcher: the Planner chip calls onSwitch('planner') (the hub shows it), not onExit", s1 == {"sw": ["planner"], "active": False, "exits": e0}, s1)
        pg.evaluate("() => openZ()")
        pg.wait_for_timeout(400)
        pg.focus(".zm-back")
        pg.keyboard.press("ArrowLeft")
        pg.wait_for_timeout(150)
        k1 = pg.evaluate("() => document.activeElement && document.activeElement.dataset.app")
        pg.keyboard.press("ArrowRight")
        k2 = pg.evaluate("() => document.activeElement && document.activeElement.dataset.app")
        pg.keyboard.press("ArrowLeft")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(300)
        k3 = pg.evaluate("() => ({ active: ZM.isActive(), exits: window.EXITS })")
        check("c. switcher by keyboard: an arrow key opens the chips, arrows move, Enter on Jarvis goes back to Jarvis (onExit)",
              k1 == "home" and k2 == "planner" and k3 == {"active": False, "exits": e0 + 1}, (k1, k2, k3))
        pg.evaluate("() => openZ()")
        pg.wait_for_timeout(400)
        r = pg.evaluate(CTRL)["r"]
        pg.mouse.move((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        pg.mouse.down()
        pg.wait_for_timeout(650)                             # the chips open while the finger is still down
        kr = pg.evaluate("() => { const c = document.querySelector(\".zm-apps .zm-chip[data-app='kalshi']\"); if (!c) return null; const r = c.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        if kr:
            pg.mouse.move(kr[0], kr[1], steps=5)
        pg.mouse.up()
        pg.wait_for_timeout(300)
        s2 = pg.evaluate("() => ({ sw: window.SWITCHED.slice(), active: ZM.isActive() })")
        check("c. switcher: hold, slide onto Kalshi, let go = onSwitch('kalshi')", kr and s2 == {"sw": ["planner", "kalshi"], "active": False}, (s2, kr))
        pg.evaluate("() => openZ()")
        pg.wait_for_timeout(400)
        # the hub lets the frame go (iPhone memory) and opens Zenith again later: a fresh Zenith at the route it had
        pg.wait_for_function("() => ZM.state().route === '#/alerts'", timeout=8000)
        pg.evaluate("() => ZM.unload()")
        u1 = pg.evaluate("() => ({ frames: document.querySelectorAll('.zm-frame').length, active: ZM.isActive() })")
        pg.evaluate("() => openZ()")
        pg.wait_for_function("() => ZM.state().ready && document.querySelectorAll('.zm-frame').length === 1", timeout=30000)
        z = zframe(pg, base)
        u2 = z.evaluate("() => ({ hash: location.hash, alive: window.__alive || null })")
        check("b. unload() lets the frame go; the next show() loads Zenith again at the route it had", u1 == {"frames": 0, "active": False}
              and u2 == {"hash": "#/alerts", "alive": None}, (u1, u2))
        # without onSwitch the control only goes back to Jarvis (a hold does nothing else)
        pg.goto(base + "jarvis/zm-test.html?nosw")
        pg.wait_for_function("() => window.MOUNTED === true", timeout=15000)
        pg.evaluate("() => openZ('#/today')")
        pg.wait_for_function("() => ZM.state().ready", timeout=30000)
        ns = pg.evaluate("() => ({ sw: document.querySelector('.zm-back').classList.contains('sw'), popup: document.querySelector('.zm-back').getAttribute('aria-haspopup') })")
        hold()
        ns.update(pg.evaluate("() => ({ apps: !!document.querySelector('.zm-apps:not([hidden])'), active: ZM.isActive(), exits: window.EXITS })"))
        check("c. without onSwitch: no switcher; a hold is just a tap: back to Jarvis as before",
              ns == {"sw": False, "popup": None, "apps": False, "active": False, "exits": 1}, ns)
        ctx.close()

        # ---- e. the old way (a frame below a bar): no safe area doubled either
        ctx, pg = new_page(br, 390, 844, errs, "below-bar")
        pg.goto(base + "jarvis/zm-bar.html")
        pg.wait_for_function("() => { const f = document.getElementById('f'); return f.contentWindow && f.contentWindow.POLISH; }", timeout=30000)
        z = zframe(pg, base)
        R = z.evaluate(RECTS)
        check("e. Zenith in a frame below a bar (the bar already pads the top, the frame stops above the home bar): no extra padding",
              R["sa"] == ["0px", "0px", "0px", "0px"] and abs(R["padTop"] - 10) < 0.6 and abs(R["tabsBottom"] - 10) < 0.6, R)
        ctx.close()
        part_sw(br, base, errs)
        br.close()
    check("g. no page errors (Jarvis page, Zenith frames, the Zenith app)", not errs, errs[:6])
    check("g. no warnings about the frame's allow list (no 'web-share', no allowfullscreen next to allow)", not WARNS, WARNS[:4])


def main():
    part_a()
    tmp = tempfile.mkdtemp(prefix="le_zenith_mode_")
    try:
        base_dir, other_dir = site(tmp, int(time.time()))
        srv, srv2 = serve(tmp), serve(other_dir)
        try:
            run_browser(f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/", f"http://localhost:{srv2.server_address[1]}/")
        finally:
            srv.shutdown()
            srv2.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nzenith mode: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
