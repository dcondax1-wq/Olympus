"""The Jarvis hub (tools/web_public/jarvis/, owner 2026-10-31; modes and the old Jarvis look 2026-11-01): one Home Screen app
that opens on the Jarvis screen (the owner's old violet HUD: J.A.R.V.I.S., the core with its HUD ring, STANDBY, the voice
row, HUD panels, the glass command dock), switches Jarvis <-> Zenith in one tap, and opens the Planner, Kalshi and added
dashboards. Runs the real hub page in Chromium on local copies of the site layout (<site>/jarvis/ next to stand-in Zenith /
Planner pages), with the live feed, kalshi.json and the crypto prices served from stubs (nothing leaves the machine), and checks:
  a. the files (fonts + OFL.txt, icons), the service worker (jarvis-v5: every part and font saved on its own, the 3.5 s rule,
     the dark offline page), the build step that publishes jarvis/, Safari 16 / offline safety, the old look's tokens
  b. the Jarvis screen: greeting, the market line, a card per project (Zenith with the bots' numbers from the live feed,
     the Planner with today's plan read from its own saved data, Kalshi waiting for the bot until kalshi.json is published)
  c. switching: the mode switch opens each dashboard, a dashboard is never reloaded by switching away and back,
     an old #planner address starts on the Jarvis screen
  d. Jarvis answers (the built-in brain): the bots' status / room / target from the live feed, today's plan, the market, "open X"
  e. Kalshi: waiting for the bot, then its numbers; an added dashboard shows in the bar; settings (smart mode, voice, apps)
  f. phone width, no page errors
  g. data.js: getFacts() and the Planner's 'planner.today.v1' summary
  h. the separate parts through their contracts (stand-in brain.js, core-visual.js, apps.js, zenith-mode.js): Zenith mode
     mounts once, shows / hides / lets go, its badge, its own exit; the brain's answers, cards, routes and smart mode; apps.js's
     cards (renderCard, cachedStatus, posted cards)
  i. each part missing on its own: the built-in fallback takes over, no page errors
  j. the folder as it is (whatever parts are merged), with its service worker: starts, answers, both modes, opens offline
  k. phone sizes 375 x 667, 375 / 390 x 844, 430 x 932: no sideways scroll, the mode switch on screen, never a white screen (the
     main colour), the fixed dock / chip / search button never over the hint or the mic row, real taps land on every card
  l. the look and its features: fonts, the Eclipse theme, KALSHI TODAY / NQ BOTS TODAY, the HUD ring and state word, the
     panels (market, activity, add-ons, system core), the dock and its ⋯ keys, themes kept, effects levels, reduced motion,
     the boot screen (once, <= 1.2 s), the command palette, voice (tap, hands-free; the phone's voice at 1.06 / 1.1)
  s. the System view (2026-11-02): the header strip (one verdict, one dot per system), the System panel (the PC with CPU /
     RAM, Zlarior, ATLAS, BLITZ, Kalshi, the Planner; the one thing to do), the orb's strip and alert dot, "status" /
     "how's the pc"; light (no blur)
  p. the OLYMPUS apps (2026-11-03): the built-ins from apps.js (Data City, Mind, Daphne next to Zenith, the Planner, Kalshi),
     the OLYMPUS grid on the Jarvis screen (grouped tiles in each app's colour, live status from its jarvis.json, one-time
     stagger), an app whose folder is not on the site shown as "not on the site yet" and never opened, the orb's groups and
     group chips, its scrollable 44 px quick row, the ring's most used six plus "more"
Waiting: every start waits on the page's own ready marker (html[data-ready], window.__jarvisReadyMs), never on a wall clock: on
a loaded machine the 3D core, drawn in software, can hold the page's main thread for seconds after Jarvis has started, which
only delays when the test sees the marker (measured 2026-11-03: ready at 0.4-1.1 s on the page's clock, seen 10-16 s later).
Runs A (fallbacks), B (stand-ins), C (the folder as is) and the missing-part runs each get their own copy of the site.
    python -X utf8 -m tests.test_jarvis_hub      (temp folder + a local server; nothing else touched; ~4 min)
Screenshots of the phone sizes: set JARVIS_SHOTS=<folder>.
"""
from __future__ import annotations

import datetime as dt
import functools
import glob
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
KS = os.path.join(ROOT, "tools", "web_public", "kalshi")
PARTS = ("brain.js", "core-visual.js", "apps.js", "zenith-mode.js")
FONTS = ("orbitron.woff2", "rajdhani-400.woff2", "rajdhani-500.woff2", "rajdhani-600.woff2", "rajdhani-700.woff2")
# the stylesheet tag the page loads (index.html `jarvis.css?v=jNN`): the worker must save that same file (SHELL, CORE); read here,
# never typed, since every look change bumps it (j13 -> j16 on 2026-11-10, commit 3bd5d75, and the pins here went stale)
JCSS = "jarvis.css?v=" + re.search(r'id="jcss" href="jarvis\.css\?v=(j\d+)"', open(os.path.join(JV, "index.html"), encoding="utf-8").read()).group(1)
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


LIVE = {"v": 1, "kind": "le-live", "t": 0, "price": 21234.5,
        "pc_verdict": {"code": "RUNNING", "label": "RUNNING: bot trading", "level": "good", "reason": "heartbeat fresh"},
        "board": {"running": True,
                  "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "balance": 49273.8, "floor": 48168.2,
                          "room": 1105.6, "to_target": 3726.2, "today_pnl": 212.5, "week_pnl": -224.5, "status": "open", "room_frac": 0.55},
                  "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "balance": 24750.4, "floor": 24000.0,
                            "room": 750.4, "to_target": 1749.6, "today_pnl": 0.0, "status": "open"},
                  # BLITZ on account C (engine/live_publish.blitz_block / live_board.blitz_now card)
                  "blitz": {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "badge": "SIM", "balance": 25112.3, "floor": 24500.0,
                            "room": 612.3, "to_target": 1387.7, "today_pnl": 95.25, "week_pnl": 140.0, "status": "open", "off": False,
                            "trades_today": 2, "waiting": "Waiting for the 14:30 check."},
                  "trades": [{"acct": "lit", "side": "LONG", "qty": 3, "exit": "TARGET", "usd": 412.5, "r": 2.1, "entry_t": 0, "exit_t": 0, "open": False}],
                  "health": {"items": [{"key": "loop", "label": "Bot loop", "value": "running", "ok": True, "warn": False, "detail": "the bot runs"}]},
                  "lines": [], "level": "ok"},
        # the PC's health lines (engine/live_publish.pc_health_summary), for the System view
        "pc_health": {"t": 0, "level": "ok", "cpu": 23, "ram": 61, "lines": [
            {"key": "cpu", "label": "CPU", "level": "ok", "text": "CPU 23%"},
            {"key": "ram", "label": "Memory (RAM)", "level": "ok", "text": "RAM 61% in use (2.2 of 3.6 GB)"},
            {"key": "nt", "label": "NinjaTrader", "level": "ok", "text": "NinjaTrader running, 900 MB"}]}}
CRYPTO = {"bitcoin": {"usd": 77000, "usd_24h_change": 1.5}, "ethereum": {"usd": 2250.4, "usd_24h_change": -0.4}, "solana": {"usd": 94.52, "usd_24h_change": -1.55}}

# stand-ins for the parts built on their own (the contracts in index.html's header), to check the shell uses them right
STUB = {
    "brain.js": """
export function createBrain({ getFacts, open, now }) {
  const log = window.__stubBrain = { asks: [], smart: null, nowOk: now() instanceof Date };
  return {
    smart: { on: false, model: '' },
    async ask(text) {
      log.asks.push(text);
      const f = getFacts();
      if (/open planner/i.test(text)) return { text: 'STUB opening the planner', open: 'planner' };
      if (/zenith route/i.test(text)) { open('zenith', 'perf'); return { text: 'STUB zenith route' }; }
      if (/open blitz/i.test(text)) return { text: 'STUB blitz', open: 'zenith', route: '#/blitz' };
      return { text: 'STUB ' + f.market.text + ' | room ' + (f.live && f.live.lit ? f.live.lit.room : 'none') + ' | apps ' + f.apps.map((a) => a.id).join(','),
               speak: 'stub', cards: [{ title: 'Stub card', kv: [['Room', '$1']] }] };
    },
    async briefing() { return { text: 'STUB briefing: all quiet', speak: 'stub briefing' }; },
    suggestions() { return ['Stub suggestion']; },
    setSmart(o) { log.smart = o; this.smart = { on: !!o.on, model: o.model || '', hasKey: !!o.key }; return true; },
  };
}
""",
    "core-visual.js": """
export function mountCore(el, { size }) {
  const d = document.createElement('div');
  d.id = 'stubCore'; d.dataset.size = size; d.style.cssText = 'position:absolute;inset:0;border-radius:50%;background:#0d2a3a';
  el.appendChild(d);
  window.__coreStates = [];
  return { setState(s) { d.dataset.state = s; window.__coreStates.push(s); }, setLevel(v) { d.dataset.level = v; }, destroy() { d.remove(); } };
}
""",
    "apps.js": """
const L = [
  { id: 'zenith', name: 'Zenith', sub: 'NQ bots', url: '../', builtin: true, removable: false },
  { id: 'planner', name: 'Planner', sub: 'Calendar', url: '../planner/', builtin: true, removable: false },
  { id: 'kalshi', name: 'Kalshi', sub: 'Kalshi bot', url: '../kalshi/', glyph: 'K', builtin: true, removable: false },
  { id: 'stubapp', name: 'StubApp', url: '../kalshi-stub/', statusUrl: '../kalshi-stub/jarvis.json', extra: true, removable: true },
];
const CARD = { app: 'stubapp', name: 'StubApp', status: { level: 'ok', label: 'Stub OK' }, kpis: [{ label: 'Users', value: '42' }], lines: [], t: Math.floor(Date.now() / 1000) };
export function listApps() { return L.slice(); }
export function addApp({ name, url }) { if (!url) return { ok: false, field: 'url', error: 'STUB needs a link' }; const a = { id: 'x-' + name.toLowerCase(), name, url, extra: true, removable: true }; L.push(a); return { ok: true, app: a }; }
export function removeApp(id) { const i = L.findIndex((a) => a.id === id); if (i < 0) return false; L.splice(i, 1); return true; }
export function cachedStatus(app) { return app.id === 'stubapp' ? CARD : null; }
export async function appStatus(app) { return app.id === 'stubapp' ? Object.assign({}, CARD, { status: { level: 'ok', label: 'Stub fresh' } }) : null; }
export function renderCard(card, doc) {
  const b = doc.createElement('button'); b.type = 'button'; b.className = 'card jx-card'; b.dataset.app = card.app;
  b.textContent = card.name + ' · ' + card.status.label + ' · ' + card.kpis.map((k) => k.label + ' ' + k.value).join(', ');
  return b;
}
export function listen(win, cb) { win.__stubPost = cb; return () => {}; }
export function ascendSlot() { return { enabled: false }; }
export async function findAscend() { return { ok: false, error: 'STUB: Ascend is not on this site yet. Paste its link instead.' }; }
""",
    "zenith-mode.js": """
export function mountZenithMode({ host, onExit, onState }) {
  const z = window.__zen = { mounts: ((window.__zen && window.__zen.mounts) || 0) + 1, shows: [], hides: 0, unloads: 0 };
  host.innerHTML = '<div id="zenStub"><h1>Zenith mode stub</h1><button id="zenExit" type="button">Back to Jarvis</button></div>';
  host.querySelector('#zenExit').onclick = () => onExit();
  let on = false;
  return { show(route) { on = true; z.shows.push(route || ''); if (onState) onState({ route: route || '', title: 'Zenith', badge: 3, active: true }); },
           hide() { on = false; z.hides++; }, isActive() { return on; }, unload() { z.unloads++; } };
}
export function zenithRouteFor(text) { return /blitz/i.test(text) ? '#/blitz' : null; }
""",
}


def site(tmp, name, parts):
    """A copy of the site layout under tmp/name/nq-dashboard/. parts: 'none' (every separate part removed: the fallbacks),
    'stub' (the stand-ins), 'stub-but:<file>' (stand-ins, that one missing) or 'asis' (the folder as it is)."""
    base = os.path.join(tmp, name, "nq-dashboard")
    shutil.copytree(JV, os.path.join(base, "jarvis"))
    shutil.copytree(KS, os.path.join(base, "kalshi"))
    shutil.copytree(os.path.join(os.path.dirname(JV), "olympus"), os.path.join(base, "olympus"))   # the OLYMPUS theme engine
    for f in PARTS:
        dst = os.path.join(base, "jarvis", f)
        if parts == "none" and os.path.exists(dst):
            os.remove(dst)
        elif parts == "stub" or (parts.startswith("stub-but:") and f != parts.split(":", 1)[1]):
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(STUB[f])
        elif parts.startswith("stub-but:") and os.path.exists(dst):
            os.remove(dst)
    os.makedirs(os.path.join(base, "icons"))
    shutil.copy(os.path.join(JV, "icon-192.png"), os.path.join(base, "icons", "icon-192.png"))
    with open(os.path.join(base, "index.html"), "w") as f:
        f.write("<!doctype html><title>Zenith stub</title><style>body{background:#0b0b0d;color:#eee}</style><h1 id='z'>Zenith stub</h1><script>window.loads=(window.loads||0)+1;</script>")
    os.makedirs(os.path.join(base, "planner"))
    shutil.copy(os.path.join(JV, "icon-192.png"), os.path.join(base, "planner", "icon-192.png"))
    today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    S = {"events": [{"id": "e1", "title": "Gym", "date": today, "allDay": False, "start": "07:30", "end": "08:30", "repeat": "none"},
                    {"id": "e2", "title": "Review fills", "date": "2026-01-05", "allDay": False, "start": "16:15", "repeat": "daily"}],
         "tasks": [{"id": "t1", "title": "Buy BLITZ 25K", "date": today, "done": False}, {"id": "t2", "title": "Old", "date": today, "done": True}],
         "projects": [{"id": "p1", "name": "Kalshi bot"}]}
    with open(os.path.join(base, "planner", "index.html"), "w") as f:
        f.write("<!doctype html><title>Planner stub</title><style>body{background:#0b0b0d;color:#eee}</style><h1>Planner stub</h1><script>"
                f"localStorage.setItem('planner.v1', JSON.stringify({json.dumps(S)}));window.loads=(window.loads||0)+1;</script>")
    # the Planner is a built-in app now (live: true): its status card, so the shell finds it on the site (the card shows the next thing / FREE)
    with open(os.path.join(base, "planner", "jarvis.json"), "w") as f:
        json.dump({"v": 1, "name": "Planner", "status": {"level": "ok", "label": "Day plan"}, "kpis": [{"label": "Next", "value": "Gym"}],
                   "lines": ["Nothing else today"], "t": int(time.time()) - 60}, f)
    os.makedirs(os.path.join(base, "datacity"))
    with open(os.path.join(base, "datacity", "index.html"), "w") as f:
        f.write("<!doctype html><title>Data City stub</title><meta name='theme-color' content='#05060f'><style>body{background:#05060f;color:#eee}</style><h1>Data City stub</h1>")
    with open(os.path.join(base, "datacity", "jarvis.json"), "w") as f:
        json.dump({"v": 1, "name": "Data City", "status": {"level": "ok", "label": "25 pass the noise guard"},
                   "kpis": [{"label": "Combos tested", "value": "19,942"}], "lines": ["Data to 2026-11-02"], "t": int(time.time()) - 60,
                   "theme": "#05060f"}, f)
    os.makedirs(os.path.join(base, "kalshi-stub"))
    with open(os.path.join(base, "kalshi-stub", "index.html"), "w") as f:
        f.write("<!doctype html><title>Kalshi stub</title><style>body{background:#0b0b0d;color:#eee}</style><h1>Kalshi stub</h1>")
    return f"{name}/nq-dashboard/"


SLOW = {"s": 0.0}                                    # a slow network: every answer of the local site waits this long


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass

    def do_GET(self):
        if SLOW["s"]:
            time.sleep(SLOW["s"])
        return super().do_GET()


def serve(root):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _old_ok(sw):
    """the worker's OLD list: every earlier Jarvis copy, newest first, from the one before CACHE down to jarvis-v4 (bump_versions
    pushes the old name on; typing the list here went stale at jarvis-v26 while the worker moved on to v34)"""
    cur = re.search(r"const CACHE = 'jarvis-v(\d+)';", sw)
    old = re.search(r"const OLD = \[([^\]]*)\];", sw)
    return bool(cur and old) and re.findall(r"'jarvis-v(\d+)'", old.group(1)) == [str(v) for v in range(int(cur.group(1)) - 1, 3, -1)]


def part_a():
    for f in ("index.html", "manifest.webmanifest", "sw.js", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png",
              "data.js", "jarvis.css", "OFL.txt") + FONTS:
        check(f"a. jarvis/{f} exists", os.path.exists(os.path.join(JV, f)))
    m = json.load(open(os.path.join(JV, "manifest.webmanifest"), encoding="utf-8"))
    check("a. manifest: Jarvis, standalone, own scope, black like the old Jarvis, icons j5 (the gold temple, 2026-11-18)",
          m["name"] == "Olympus" and m["short_name"] == "Olympus" and m["display"] == "standalone" and m["scope"] == "./"
          and m["theme_color"] == "#14110e" and all(i["src"].endswith("?v=j5") for i in m["icons"]), m)
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    tup = re.search(r'for app in \(([^)]*)\):', b)
    published = set(re.findall(r'"([a-z0-9-]+)"', tup.group(1))) if tup else set()
    # every app of apps.js with a folder is published by the build (the list grows: read from apps.js; Zenith is the site root, the Planner has its own build)
    need = {"jarvis", "kalshi"} | {a["id"] for a in _REG["apps"] if a["id"] not in ("zenith", "planner")}
    check("a. the site build publishes jarvis/ and kalshi/ and every app of apps.js with every build (every top-level file: fonts and parts too)",
          tup and need <= published and 'os.path.join(out, app, name)' in b, sorted(need - published))
    check("a. kalshi/index.html exists", os.path.exists(os.path.join(KS, "index.html")))
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    check("a. the hub's service worker only handles its own folder", "u.pathname.startsWith(scope.pathname)" in sw)
    # 2026-10-31 (Jarvis would not open on the owner's iPhone): Zenith's worker covers the whole site; it used to delete
    # every other cache (Jarvis's and the Planner's saved copies) and handle their pages, so a dropped connection left Jarvis
    # with nothing to open. Each worker now keeps to its own folder and its own caches, and Jarvis's saved copy answers errors.
    check("a. Jarvis's worker deletes only its own old caches and answers a 404 / no connection from its saved copy",
          "k.startsWith('jarvis-')" in sw and "return copy || r || Response.error();" in sw and "Response.error()" in sw)
    check("a. the saved copy comes only from Jarvis's own caches, by name (never an origin-wide lookup: another page could write it)",
          "const c = await caches.open(CACHE);" in sw
          and all("cacheName: name" in ln for ln in sw.splitlines() if "caches.match(" in ln))
    # 2026-11-01 ("Jarvis is just a white screen"): an iPhone Home Screen app is white while its page loads or after a failed load
    check("a. opening Jarvis waits on the network at most NAV_WAIT_MS when a saved copy exists; no network + no copy = a dark Retry page",
          "const NAV_WAIT_MS = 3500;" in sw and "Promise.race([net, slow])" in sw and "return copy || offlinePage();" in sw
          and "background:#000" in sw and "location.reload()" in sw)
    check("a. worker v14: data.js, jarvis.css, the fonts, every separate part, switcher.js, the new brain's obsidian.js / memory.js / "
          "assist-ui.js and voice-mode.js in SHELL, each saved on its own (a missing part is skipped)",
          "const CACHE = 'jarvis-v79';" in sw and all(f"'./{f}'" in sw for f in ("data.js", "switcher.js", "obsidian.js", "memory.js", "assist-ui.js", "voice-mode.js", "tools.js", "voice-out.js") + PARTS + FONTS)
          and f"'./{JCSS}'" in sw and "SHELL.map((u) => c.add(new Request(u, { cache: 'reload' })).catch(() => null))" in sw)
    shell = re.search(r"const SHELL = \[([^\]]*)\]", sw)
    shell_files = re.findall(r"'\./([^'?]+)", shell.group(1)) if shell else []
    check("a. every file of SHELL is in the folder (a part the page loads is never left out of the saved copy, nor a saved file missing)",
          shell_files and all(os.path.exists(os.path.join(JV, f)) for f in shell_files if f)
          and all(f"'./{f}'" in sw for f in re.findall(r"load\('\w+', '\./([\w-]+\.js)'", open(os.path.join(JV, "index.html"), encoding="utf-8").read())),
          [f for f in shell_files if f and not os.path.exists(os.path.join(JV, f))])
    # 2026-11-01 ("Just a black screen" on the iPhone): no endless network wait, the previous copy as a fallback, old copies kept
    # until the new one holds every core file, and the page draws even when its stylesheet never arrives
    check("a. worker v6: never an endless network wait (NET_MAX_MS for a page or file with no copy; then the dark page / a failed file)",
          "const NET_MAX_MS = 9000;" in sw and "copy ? NAV_WAIT_MS : NET_MAX_MS" in sw and "return offlinePage();" in sw
          and "await net" not in sw.replace("await Promise.race([net", ""))
    check("a. worker v6: a file this copy lacks comes from the previous Jarvis copy; old copies go only when every CORE file is saved",
          _old_ok(sw) and "for (const name of [CACHE, ...OLD])" in sw
          and f"const CORE = ['./index.html', './{JCSS}', './data.js'];" in sw
          and "CORE.map((u) => c.match(u, { ignoreSearch: true }))" in sw)
    jhtml = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    check("a. the page draws without its stylesheet after 5 s (a stylesheet still on the way keeps an iPhone screen black)",
          'id="jcss"' in jhtml and "n.media = 'print'" in jhtml and "}, 5000);" in jhtml)
    # 2026-11-01 ("Jarvis isn't opening" on the iPhone): WebKit stops the old worker's downloads when a new one takes over
    check("a. worker v5+ takes over only when the page asks ('jarvis:activate', sent while Jarvis is out of sight), never mid-start",
          "self.skipWaiting();" not in sw.split("addEventListener('message'")[0] and "if (e.data === 'jarvis:activate') self.skipWaiting();" in sw)
    check("a. no #dashboard shortcuts in the manifest (Jarvis always opens on its own screen)", "shortcuts" not in m, m.get("shortcuts"))
    zsw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    zo = re.search(r"const OTHER_APPS = \[([^\]]*)\]", zsw)          # the list grows (gate/ went first in round 7): read it, never pin its start
    zother = set(re.findall(r"'([\w-]+/)'", zo.group(1))) if zo else set()
    check("a. Zenith's worker stays out of jarvis/ and planner/ and deletes only its own caches (le-public-*)",
          {"jarvis/", "planner/", "kalshi/"} <= zother and "if (OTHER_APPS.some(" in zsw
          and "ks.filter((k) => k.startsWith('le-public-') && k !== CACHE)" in zsw and "k !== CACHE && k !== BADGE" not in zsw)
    page = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(JV, "jarvis.css"), encoding="utf-8").read()
    data = open(os.path.join(JV, "data.js"), encoding="utf-8").read()
    check("a. each separate part is loaded on its own with import() and has a fallback in the page",
          all(f"'./{f}', (m) => typeof m." in page for f in PARTS) and "return import(path).then(" in page and "function fallbackBrain(" in page
          and 'id="orb"' in page and "html[data-state=" in css and "D.fallbackApps" in page and "frameView(a)" in page, [f for f in PARTS if f"'./{f}', (m)" not in page])
    # night-bugsweep 2026-11-19: the kalshi-feed repo is on the suspended account (a 404 on every load): this site's own copy only, the PC feed first
    check("a. kalshi.json: this site's own copy only (never the suspended account's kalshi-feed repo); the PC feed's Kalshi cards come first",
          "kalshiLocal: '../kalshi.json'" in data and "kalshi-feed/main" not in data and "kalshi-feed/contents" not in data and "ref=kalshi" not in data
          and "pcHasKalshi()" in data)
    check("a. data.js exports getFacts, the refreshes, the change event, the add-ons", all(x in data for x in (
        "export function getFacts()", "export function refreshLive()", "export function refreshKalshi()", "export function onChange(",
        "'planner.today.v1'", "export const fallbackApps", "export function refreshCrypto(", "export const VERSES", "export const QUOTES")))
    # iPhone (Safari 16): no external fonts / CDNs, no syntax newer than Safari 16, reduced motion respected, dark first paint
    css_nc = re.sub(r"/\*.*?\*/", "", css, flags=re.S)       # comments may name what is not used
    src = page + css_nc + data
    check("a. offline-safe and Safari 16 safe: no external fonts or scripts, no regex lookbehind, no CSS nesting / @property, prefixed blur",
          "fonts.googleapis" not in src and "fonts.gstatic" not in src and "<script src=\"http" not in page and "@import" not in css_nc
          and "(?<=" not in src and "(?<!" not in src and "@property" not in css_nc and "&:" not in css_nc and "& " not in css_nc.replace("&amp;", "")
          and css_nc.count("-webkit-backdrop-filter") >= css_nc.count(" backdrop-filter") - css_nc.count("-webkit-backdrop-filter"), "")
    check("a. reduced motion respected, animations pause while hidden, dark before the stylesheet loads",
          "prefers-reduced-motion" in css and ".paused" in css and "visibilitychange" in page and "html,body{background:#14110e" in page.replace(" ", ""))
    check("a. the AGORA look (2026-11-10): ONE theme, Agora, whatever an old copy saved; its tokens (#14110e, gold #c8a24a / bronze #9c6b3c / #e0b060, ivory #f3ece0 / #9a8f7d); the neon themes, the HUD ring, the grid floor, the globe and the scanlines are gone",
          "d.setAttribute('data-theme', 'agora')" in page and 'data-theme="agora"' in css
          # 2026-11-14 (team T2, the 32 looks): each Agora token is a look slot whose fallback is the Agora value (the default stays byte-identical)
          and all(re.search(re.escape(k) + r": (?:var\(--oly-th-[\w-]+, )?" + re.escape(v), css) for k, v in (("--bg", "#14110e"), ("--c", "#c8a24a"), ("--c2", "#9c6b3c"), ("--c3", "#e0b060"), ("--txt", "#f3ece0"), ("--mut", "#9a8f7d")))
          and not any(x in css for x in ('data-theme="reactor', 'data-theme="eclipse"', 'data-theme="tokyo"', 'data-theme="aurora"', '.hudring', '.bgglobe', '.floor {', '.scan {', 'glowT', '#a855f7', '#22d3ee'))
          and 'class="hudring"' not in page and 'id="bgglobe"' not in page and 'class="scan"' not in page and "rawSet('jtheme', k)" in page)
    check("a. no Orbitron / Rajdhani is loaded (the woff2 files stay on disk), a serif heading font, no clipped corners; the old fonts keep their licence file",
          all(os.path.isfile(os.path.join(JV, f)) for f in FONTS) and "@font-face" not in css and "Iowan Old Style" in css and "clip-path: polygon(" not in css
          and "SIL Open Font License" in open(os.path.join(JV, "OFL.txt"), encoding="utf-8").read())
    keys = re.findall(r"\['(\w+)', ", page[page.index("function moreKeys()"):page.index("function renderMore()")])
    check("a. PC-only features left out quietly: the ⋯ keys have no wake word, double clap, look-at-my-screen or Kill",
          len(keys) == 13 and "obsidian" in keys and not set(keys) & {"wake", "clap", "screen", "kill"}, keys)


from tests import browser_kit as BK  # noqa: E402  (shared launch: one reused browser, load-scaled timeouts, one retry of a flaky wait)


def launch(pw):
    return BK.launch(pw)


def feeds(ctx, kal):
    now = int(time.time())
    live = json.loads(json.dumps(LIVE))
    live["t"] = now - 120
    live["pc_health"]["t"] = now - 150
    live["board"]["trades"][0].update(entry_t=now - 7200, exit_t=now - 5400)

    def feed(r):
        if "kalshi.json" in r.request.url:
            return (r.fulfill(status=200, content_type="application/json", body=json.dumps(kal["j"])) if kal["on"]
                    else r.fulfill(status=404, content_type="text/plain", body="404: Not Found"))
        return r.fulfill(status=200, content_type="application/json", body=json.dumps(live))
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())       # nothing leaves the machine
    ctx.route("https://api.github.com/**", feed)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    # Jarvis (../kalshi.json) and the Kalshi page read this site's own copy only: <site>/kalshi.json, next to jarvis/ and kalshi/. The test
    # sites live at /<variant>/nq-dashboard/ (site()), so the stub answers there (night-jarvisfix 2026-11-20: the route night-bugsweep added
    # on 2026-11-19, 1b66c7e6, matched only /kalshi.json at the server root, so the published feed never reached the page here)
    ctx.route(re.compile(r"^http://(127\.0\.0\.1|localhost):\d+/(?:[\w-]+/nq-dashboard/)?kalshi\.json(\?.*)?$"), feed)
    ctx.route("https://api.coingecko.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(CRYPTO),
                                                                  headers={"Access-Control-Allow-Origin": "*"}))


def kalshi_feed():
    from engine import kalshi_publish as kp
    return {"on": False, "j": kp.clean({**kp.SAMPLE, "t": int(time.time()) - 60})}


# the phone's speech, faked: a recognizer that hears window.__utter, and a voice that records what it says
FAKE_VOICE = """
window.__said = []; window.__srStarts = 0;
class FakeSR {
  start() { window.__srStarts++; this.t = setTimeout(() => {
    const r = [Object.assign([{ transcript: window.__utter || 'is the market open' }], { isFinal: true })];
    if (this.onresult) this.onresult({ results: r }); setTimeout(() => this.onend && this.onend(), 30); }, 150); }
  stop() { clearTimeout(this.t); setTimeout(() => this.onend && this.onend(), 10); }
  abort() { clearTimeout(this.t); if (this.onend) this.onend(); }
}
window.SpeechRecognition = FakeSR; window.webkitSpeechRecognition = FakeSR;
if (window.speechSynthesis) { speechSynthesis.speak = (u) => { window.__said.push([u.text, u.rate, u.pitch]); setTimeout(() => u.onend && u.onend(), 150); }; speechSynthesis.cancel = () => {}; }
document.addEventListener('DOMContentLoaded', () => { window.__states = [];
  new MutationObserver(() => { const s = document.documentElement.dataset.state; if (window.__states[window.__states.length - 1] !== s) window.__states.push(s); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-state'] }); });
"""


def new_page(br, width=390, sw=False, boot=False, voice=False, height=844, news=False, **kw):
    ctx = br.new_context(viewport={"width": width, "height": height}, device_scale_factor=2, service_workers="allow" if sw else "block", **kw)
    ctx.add_init_script("try { localStorage.setItem('oly.hiddenBots', '[]'); } catch (e) {}")   # BLITZ shown for these pinned checks (hidden by default since 2026-11-15: tests.test_hidden_bots / test_blitz_tab)
    kal = kalshi_feed()
    feeds(ctx, kal)
    if not boot:                                   # the boot screen plays once per launch: skipped where it is not the subject
        ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); } catch (e) {}")
    if not news:                                   # so is the What's new card (once per release)
        ctx.add_init_script("try { localStorage.setItem('jarvis.seen', JSON.stringify('j9')); } catch (e) {}")
    if voice:
        ctx.add_init_script(FAKE_VOICE)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, p, errs, kal


def ready(p, timeout=60000):
    """Until Jarvis's start finished: the page's own marker (set ~0.5 s into the start). The long limit only matters on a loaded
    machine, where the software-drawn 3D core can hold the main thread after the start (see the module docstring)."""
    p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=timeout, polling=100)


def go(p, app):
    """Switch app like the owner: Jarvis's bar on the Jarvis screen; inside a dashboard (its own screen, no Jarvis bar since
    2026-11-02) the orb, then the app in its quick row."""
    if p.locator(".bar").is_visible():
        p.click(f'.bar [data-app="{app}"]')
        return
    p.click("#nxOrb")
    p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=30000)
    p.wait_for_timeout(450)
    p.click(f'.nx-qb[data-nx="{app}"]')


def add_sheet(p, name, link):
    """The + sheet like the owner: open it, type the name and the link (each checked: a loaded machine can land a fill before the
    sheet is up), Add. -> what the fields held when Add was tapped."""
    p.click("#addB")
    p.wait_for_function("!document.getElementById('sheet').hidden", timeout=10000)
    for _ in range(3):
        p.fill("#addName", name)
        p.fill("#addUrl", link)
        if p.input_value("#addName") == name and p.input_value("#addUrl") == link:
            break
        p.wait_for_timeout(200)
    sent = [p.input_value("#addName"), p.input_value("#addUrl")]
    p.click('#addF button[type="submit"]')
    return sent


def asker(p):
    def ask(q):                    # the chat keeps the last messages: start each question on an empty chat
        p.evaluate("document.getElementById('talk').innerHTML = ''")
        p.fill("#q", q)
        p.press("#q", "Enter")
        p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=8000)
        return p.locator(".msg.j").first.inner_text()
    return ask


def more(p, key):
    if p.locator("#more").is_hidden():
        p.click("#moreB")
    p.click(f'#more [data-key="{key}"]')


def run_a(br, url):
    """Run A: every separate part missing (the built-in fallbacks): today's Jarvis, all its checks."""
    ctx, p, errs, kal = new_page(br)
    # the Planner saves its data on this site first (as on the phone once it was opened)
    p.goto(url + "planner/")
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_timeout(700)
    hello = p.text_content("#hello")
    when = p.text_content("#when")
    check("b. Jarvis screen: greeting and the market line", hello in ("Late night", "Good morning", "Good afternoon", "Good evening") and "NQ market" in when, (hello, when))
    cards = p.text_content("#cards")
    check("b. Zenith card: the bots' status and numbers from the live feed",
          "RUNNING: bot trading" in cards and "$1,106" in cards and "+$213" in cards and "$750" in cards, cards[:400])
    check("b. Zenith card: BLITZ next to Zlarior and ATLAS (plan, badge, today, room, to target)",
          "BLITZ · MFFU Builder 25K · SIM" in cards and "$612" in cards and "+$95" in cards and "$1,388" in cards, cards[:600])
    check("b. Planner card: today's events and open tasks from its saved data",
          "Gym" in cards and "7:30 AM" in cards and "Review fills" in cards and "1" in cards and "Buy BLITZ 25K" in cards, cards[:400])
    check("b. Kalshi card: waiting for the Kalshi bot (its own server) while kalshi.json is not published",
          "Waiting for the Kalshi bot" in cards and "own server" in cards and "your PC" not in cards and p.locator("#link-kalshi").count() == 0, cards[-300:])
    bar = p.text_content(".bar")
    check("c. the bar lists Jarvis, Zenith, Planner, Kalshi", all(x in bar for x in ("Jarvis", "Zenith", "Planner", "Kalshi")), bar)
    check("c. modes: a Jarvis / Zenith switch, Jarvis on", p.locator('#modes [data-app="home"][aria-current="page"]').count() == 1
          and p.locator('#modes [data-app="zenith"]').count() == 1 and p.evaluate("document.documentElement.dataset.mode") == "jarvis")
    check("c. fallbacks in use: every separate part missing", p.evaluate("['brain','core','apps','zenith'].map((k) => document.documentElement.dataset[k]).join()") == "fallback,fallback,fallback,fallback",
          p.evaluate("JSON.stringify(document.documentElement.dataset)"))
    p.click('[data-app="zenith"] >> nth=0')
    p.wait_for_timeout(600)
    zf = p.frame_locator("#v-zenith iframe")
    check("c. Zenith opens in its own frame (no zenith-mode.js), the Jarvis screen hides",
          zf.locator("#z").inner_text() == "Zenith stub" and p.locator("#home").is_hidden() and p.evaluate("document.documentElement.dataset.mode") == "zenith",
          p.locator("#home").is_hidden())
    check("c. the address stays the Jarvis screen (no #zenith: a reopen never starts inside a dashboard)", "#" not in p.url, p.url)
    check("c. the command dock and the search button are Jarvis mode only", p.locator("#dock").is_hidden() and p.locator("#fab").is_hidden())
    go(p, "home")
    p.wait_for_timeout(300)
    go(p, "zenith")
    p.wait_for_timeout(300)
    loads = p.evaluate("document.querySelector('#v-zenith iframe').contentWindow.loads")
    check("c. Jarvis screen and back does not reload Zenith (loaded once)", loads == 1, loads)
    tint = p.evaluate("[getComputedStyle(document.querySelector('.bar')).display, document.documentElement.dataset.switcher, getComputedStyle(document.querySelector('#v-zenith')).top]")
    check("c. a dashboard is its own screen (owner 2026-11-02): no Jarvis bar on it while the orb is there, the dashboard starts at the top",
          (tint[1] == "module" and tint[0] == "none" and tint[2] == "0px") or (tint[1] != "module" and p.locator("#out").is_visible()), tint)
    go(p, "planner")
    p.wait_for_timeout(500)
    check("c. Planner opens in its own frame", p.frame_locator("#v-planner iframe").locator("h1").inner_text() == "Planner stub")
    pt = p.evaluate("[getComputedStyle(document.body).backgroundColor, document.querySelector('meta[name=theme-color]').content, getComputedStyle(document.querySelector('.bar')).display]")
    check("c. the Planner shows with its own colour at the top (its theme-color behind the status bar), not Jarvis's bar",
          pt[2] == "none" and pt[1] != "#000000" and pt[0] not in ("rgba(0, 0, 0, 0)",), pt)
    check("c. one dashboard loaded at a time: opening the Planner lets Zenith go (iPhone memory)",
          p.locator("#v-zenith").count() == 0 and p.locator("iframe").count() == 1, p.locator("iframe").count())
    check("c. the start note is gone once Jarvis runs", p.locator("#boot").count() == 0)
    go(p, "home")
    p.wait_for_timeout(300)
    check("c. back to Jarvis", p.locator("#home").is_visible() and not p.locator("#out").is_visible() and p.locator("#dock").is_visible())

    ask = asker(p)
    p.evaluate("document.getElementById('home').scrollTop = 0")
    a1 = ask("How are the bots?")
    check("d. status: the verdict, Zlarior and ATLAS numbers", "RUNNING" in a1 and "Zlarior 50K" in a1 and "$1,106" in a1 and "ATLAS 25K" in a1, a1)
    p.wait_for_timeout(900)
    seen = p.evaluate("(() => { const m = [...document.querySelectorAll('.msg.j')].pop().getBoundingClientRect(), h = document.getElementById('home').getBoundingClientRect(); return [Math.round(m.top), Math.round(h.top), Math.round(h.bottom)]; })()")
    check("d. the answer comes into view: its top is inside the visible Jarvis screen (D1: it used to land below the first screen)",
          seen[1] - 1 <= seen[0] < seen[2] - 40, seen)
    a2 = ask("how much room do I have")
    check("d. room", "$1,106" in a2 and "$750" in a2, a2)
    a3 = ask("how far to target")
    check("d. target", "$3,726" in a3 and "$1,750" in a3, a3)
    a4 = ask("what's on today")
    check("d. today's plan from the Planner", "Gym" in a4 and "Buy BLITZ 25K" in a4 and "Old" not in a4, a4)
    a5 = ask("is the market open")
    check("d. the market, and when it opens or closes next", "NQ market" in a5 and re.search(r"(Opens|Closes) in \d", a5), a5)
    check("d. status / room / target carry BLITZ next to Zlarior and ATLAS",
          "BLITZ 25K" in a1 and "$612" in a1 and "BLITZ 25K: drawdown left $612" in a2 and "BLITZ: $1,388 to the target" in a3,
          (a1, a2, a3))
    a8 = ask("today's p&l")
    check("d. P&L: Zlarior, ATLAS and BLITZ (today and this week)", "Zlarior today +$213" in a8 and "ATLAS today" in a8
          and "BLITZ today +$95, this week +$140" in a8, a8)
    a9 = ask("how's blitz")
    check("d. 'how's blitz' answers BLITZ alone (not 'Opening Zenith')", "BLITZ 25K: today +$95, room $612, $1,388 to target, 2 trades today" in a9
          and "Zlarior" not in a9 and "Opening" not in a9 and p.locator("#home").is_visible(), a9)
    a10 = ask("blitz room")
    check("d. 'blitz room' answers BLITZ's room alone", "BLITZ 25K: drawdown left $612" in a10 and "Zlarior" not in a10, a10)
    a15 = ask("btc price")
    check("d. the latest answer is the line under the core", "BTC $77,000" in p.text_content("#says"), p.text_content("#says"))
    check("d. the old add-ons answer too: crypto, the verse, the quote", "BTC $77,000 (+1.5% in 24 h)" in a15 and "ETH $2,250" in a15
          and "KJV" in ask("verse of the day") and '"' in ask("quote of the day"), a15)
    a6 = ask("open planner")
    p.wait_for_timeout(800)
    check("d. 'open planner' switches to the Planner", "Opening Planner" in a6 and p.locator("#v-planner").is_visible(), a6)
    go(p, "home")
    a7 = ask("how's kalshi")
    check("d. Kalshi not published yet: says it is not connected (the bot runs on its own server)", "not connected yet" in a7 and "own server" in a7 and "PC" not in a7, a7)
    a7b = ask("open kalshi")
    p.wait_for_timeout(900)
    kf = p.frame_locator("#v-kalshi iframe")
    # the one step (2026-11-01): the Kalshi bot runs on its own server, so the step is a line for its own chat (kalshi/SETUP.md);
    # until the Kalshi page with that step is merged, the page in this tree still shows the older docs/KALSHI_PUBLISH.md step
    want = "kalshi/SETUP.md" if any("kalshi/SETUP.md" in open(os.path.join(KS, f), encoding="utf-8").read() for f in os.listdir(KS) if f.endswith((".js", ".html"))) else "docs/KALSHI_PUBLISH.md"
    check("e. 'open kalshi' opens the Kalshi page; not published yet: it shows the one step that connects the bot",
          "Opening Kalshi" in a7b and "Connect your Kalshi bot" in kf.locator("#body").text_content()
          and want in kf.locator("#step").inner_text(), (a7b, want))
    # e. the bot publishes kalshi.json
    kal["on"] = True
    p.reload()
    ready(p)
    p.wait_for_timeout(700)
    cards2 = p.text_content("#cards")
    check("e. Kalshi published: the card shows running, the mode, balance, today and open positions",
          "Running · PAPER" in cards2 and "$512.34" in cards2 and "+$18.50" in cards2, cards2[-320:])
    a11 = ask("how's kalshi")
    check("e. 'how's kalshi' answers from the bot's numbers (balance, today, week, positions)",
          "Kalshi (PAPER): running, balance $512.34, today +$18.50, this week +$42.10, 1 open position" in a11
          and "NYC high 58-59°F on Nov 2: YES x10, P&L +$1.30" in a11 and p.locator("#home").is_visible(), a11)
    a12 = ask("kalshi balance")
    check("e. 'kalshi balance' answers instead of switching", "balance $512.34" in a12 and p.locator("#home").is_visible(), a12)
    p.click('.card[data-app="kalshi"]')
    p.wait_for_timeout(900)
    kb = p.frame_locator("#v-kalshi iframe").locator("body").text_content()     # text_content: headings are upper-cased by CSS
    check("e. the Kalshi page inside Jarvis: balance, P&L, the open position, the trade and the daily bars",
          "$512.34" in kb and "+$18.50" in kb and "+$112.34" in kb and "NYC high 58-59°F on Nov 2" in kb and "10 × 42¢ → 55¢" in kb
          and "Recent trades" in kb and p.frame_locator("#v-kalshi iframe").locator("svg.bars rect").count() == 3, kb[:500])
    go(p, "home")
    p.wait_for_function("window.__jarvis.active() === 'home'", timeout=10000)
    sent = add_sheet(p, "Clipper", url + "kalshi-stub/")
    p.wait_for_function("!!document.getElementById('v-x-clipper') || !!document.getElementById('addErr').textContent", timeout=10000)
    check("e. an added dashboard shows in the bar and opens", "Clipper" in p.text_content("#apps") and p.locator("#v-x-clipper").is_visible(),
          [sent] + p.evaluate("[document.documentElement.dataset.mode, document.getElementById('addErr').textContent, document.getElementById('sheet').hidden, String(document.getElementById('apps') && document.getElementById('apps').textContent)]"))
    fr = p.evaluate("(() => { const f = document.querySelector('#v-x-clipper iframe'); return [f.getAttribute('allow') || '', f.getAttribute('sandbox')]; })()")
    go(p, "home")
    p.wait_for_function("window.__jarvis.active() === 'home'", timeout=10000)
    add_sheet(p, "Other", url.replace("127.0.0.1", "localhost") + "kalshi-stub/")      # another origin: another site
    try:
        p.wait_for_function("!!document.querySelector('#v-x-other iframe')", timeout=10000)
    except Exception:                                   # noqa: BLE001 - reported below
        pass
    fo = p.evaluate("(() => { const f = document.querySelector('#v-x-other iframe'); return f ? [f.getAttribute('allow'), f.getAttribute('sandbox') || ''] : null; })()")
    check("e. frames: this site's apps get the phone's features (allow, no sandbox); another site's page is sandboxed, never allowed to move Jarvis",
          "microphone" in fr[0] and fr[1] is None and fo and fo[0] is None and "allow-scripts" in fo[1] and "allow-same-origin" in fo[1]
          and "allow-top-navigation" not in fo[1], (fr, fo))
    go(p, "home")
    more(p, "apps")
    p.wait_for_timeout(200)
    p.click('#setApps [data-rm="x-other"]')
    p.click("#setX")
    # D1: the + sheet takes a bare link (no browser bubble: novalidate, a text field) and says what is wrong in its own words
    p.click("#addB")
    p.fill("#addName", "Bare")
    p.fill("#addUrl", "not a link")
    p.click('#addF button[type="submit"]')
    p.wait_for_timeout(200)
    bad = p.inner_text("#addErr")
    p.fill("#addUrl", "example.com/app/")
    p.click('#addF button[type="submit"]')
    p.wait_for_timeout(400)
    got = p.evaluate("[document.querySelector('#addF').noValidate, document.querySelector('#addUrl').type, [...document.querySelectorAll('#apps [data-app]')].map((b) => b.textContent).join(',')]")
    check("e. the + sheet: a bare link (example.com/app/) is added as https://; a wrong one gets its own message (no browser bubble)",
          "Paste a full link" in bad and got[0] is True and got[1] == "text" and "Bare" in got[2], (bad, got))
    go(p, "home")
    more(p, "apps")
    p.wait_for_timeout(200)
    p.click('#setApps [data-rm="x-bare"]')
    p.click("#setX")
    go(p, "home")
    more(p, "aikey")
    p.wait_for_timeout(200)
    check("e. settings (⋯ → AI key): voice on/off, smart mode (off without the new brain: says so) and the added dashboard to remove",
          p.locator("#settings").is_visible() and p.locator("#setVoice").is_checked() and p.locator("#setSmart").is_disabled()
          and "built-in rules" in p.inner_text("#smartState") and "Clipper" in p.inner_text("#setApps"), p.inner_text("#settings")[:300])
    p.click('#setApps [data-rm="x-clipper"]')
    p.wait_for_timeout(200)
    check("e. removing it from settings takes it off the bar", "Clipper" not in p.inner_text("#apps"))
    p.click("#setX")

    # g. data.js: the facts, and the Planner's own summary of today ('planner.today.v1') when it is today's
    f = p.evaluate("(() => { const f = window.__jarvis.facts(); return { keys: Object.keys(f).sort(), open: f.market.open, mtext: f.market.text, room: f.live && f.live.lit && f.live.lit.room,"
                   " ks: f.kalshiState, kb: f.kalshi && f.kalshi.balance, ev: f.planner && f.planner.ev.map((e) => e.title), apps: f.apps.map((a) => a.id),"
                   " next: f.market.next && f.market.next.mins, verse: f.extras.verse[1], btc: f.extras.crypto && f.extras.crypto.BTC.usd }; })()")
    check("g. getFacts(): now, market (+ the next open / close), live, kalshi + state, planner, apps, extras (verse, quote, crypto)",
          all(k in f["keys"] for k in ("now", "market", "live", "kalshi", "kalshiState", "planner", "apps", "extras")) and f["room"] == 1105.6
          and f["ks"] == "ok" and f["kb"] == 512.34 and "Gym" in (f["ev"] or []) and f["apps"][:3] == ["zenith", "planner", "kalshi"]
          and "NQ market" in f["mtext"] and isinstance(f["next"], int) and f["next"] > 0 and f["verse"] and f["btc"] == 77000, f)
    today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    p.evaluate("(d) => localStorage.setItem('planner.today.v1', JSON.stringify({ day: d, events: [{ title: 'Dentist', start: '15:00' }, { title: 'Holiday', allDay: true }],"
               " tasks: [{ title: 'Call broker', done: false }, { title: 'Done one', done: true }] }))", today)
    a13 = ask("what's on today")
    check("g. the Planner's 'planner.today.v1' summary (today's) is read first", "All day: Holiday" in a13 and "3:00 PM: Dentist" in a13
          and "Call broker" in a13 and "Done one" not in a13 and "Gym" not in a13, a13)
    p.evaluate("localStorage.setItem('planner.today.v1', JSON.stringify({ day: '2001-01-01', events: [{ title: 'Stale', start: '09:00' }], tasks: [] }))")
    a14 = ask("what's on today")
    check("g. a stale 'planner.today.v1' (another day) is ignored", "Stale" not in a14 and "Gym" in a14, a14)

    # junk in the Planner's keys (another app, an old format) never stops Jarvis: it starts, draws every card and answers
    today2 = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    p.evaluate("(d) => { localStorage.setItem('planner.v1', JSON.stringify({ events: 'junk', tasks: 5, projects: { a: 1 } }));"
               " localStorage.setItem('planner.today.v1', JSON.stringify({ day: d, events: { x: 1 }, tasks: 'x' })); }", today2)
    p.reload()
    ready(p)
    p.wait_for_timeout(300)
    j1 = [p.locator("#cards .card").count(), p.text_content("#cards"), asker(p)("what's on today")]
    p.evaluate("(d) => { localStorage.setItem('planner.v1', JSON.stringify({ events: [null, 5, 'x', { title: { a: 1 }, date: d, start: 7 }, { date: 9 }], tasks: [null, { title: ['t'], date: d }] }));"
               " localStorage.removeItem('planner.today.v1'); }", today2)
    p.reload()
    ready(p)
    p.wait_for_timeout(300)
    j2 = [p.locator("#cards .card").count(), asker(p)("what's on today")]
    check("g. junk in planner.v1 / planner.today.v1: Jarvis still starts, draws every card and answers (security review)",
          j1[0] >= 3 and "Today" in j1[1] and len(j1[2]) > 3 and j2[0] >= 3 and len(j2[1]) > 3 and not errs, (j1[0], j1[2], j2, errs))
    p.evaluate("localStorage.removeItem('planner.v1')")
    p.goto(url + "planner/")
    p.goto(url + "jarvis/#planner")
    p.reload()                                     # a fresh open at that address (as the iPhone reopening Jarvis)
    ready(p)
    p.wait_for_timeout(400)
    check("c. opened at #planner (an old saved address): starts on the Jarvis screen, the address is cleaned",
          p.locator("#home").is_visible() and p.locator("iframe").count() == 0 and "#" not in p.url, p.url)
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_timeout(300)
    w = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    check("f. phone width: no sideways scroll", w[0] <= w[1], w)
    # home v2 (2026-11-11): the hero's courtyard runs edge to edge on purpose; everything else (the hero's words, the tiles, the sections) keeps the 16 px gutter
    hw = p.evaluate("(() => { const h = document.querySelector('.home-in'); const kids = h.matches('[data-home=\"v2\"]') ? [...h.querySelectorAll(':scope > .hero > :not(.court), :scope > .tiles > *, :scope > .hbody > *')] : [...h.children]; return [h.scrollWidth, h.clientWidth, Math.max(...kids.map((c) => c.getBoundingClientRect().right))]; })()")
    check("f. phone width: the Jarvis screen fits inside its gutter (nothing clipped on the right)", hw[0] <= hw[1] and hw[2] <= 390 - 15.5, hw)
    check("f. no page errors", not errs, errs)
    ctx.close()


def run_b(br, url):
    """Run B: the stand-in parts: the shell calls each one through its contract."""
    ctx, p, errs, _ = new_page(br)
    p.goto(url + "planner/")
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("['brain','core','apps'].every((k) => document.documentElement.dataset[k] === 'module')", timeout=8000)
    p.wait_for_timeout(500)
    check("h. the parts load as modules (brain, centerpiece, apps)", True)
    check("h. core-visual.js: mounted in the centerpiece (the 2D reactor steps aside), sized to the stage",
          p.locator("#stubCore").count() == 1 and p.locator("#orb").is_hidden() and int(p.get_attribute("#stubCore", "data-size")) > 200,
          p.locator("#stubCore").count())
    cards = p.text_content("#cards")
    check("h. apps.js: its list feeds the bar; an added app's card is apps.js's own (renderCard), first from cachedStatus, then appStatus",
          "StubApp" in p.text_content("#apps") and p.locator("#cards .jx-card[data-app='stubapp']").count() == 1
          and "StubApp · Stub fresh · Users 42" in cards, cards[-200:])
    p.evaluate("window.__stubPost({ app: 'stubapp', name: 'StubApp', status: { level: 'warn', label: 'Posted' }, kpis: [], t: Math.floor(Date.now() / 1000) })")
    p.wait_for_timeout(200)
    check("h. apps.js: a card posted by an open app (listen) replaces it", "StubApp · Posted" in p.text_content("#cards"), p.text_content("#cards")[-200:])
    check("h. brain.js: its suggestions", "Stub suggestion" in p.inner_text("#sugs"), p.inner_text("#sugs"))
    check("h. CONNECT MY BRAIN shows while the brain can use a key and has none", p.locator("#brainF").is_visible())
    ask = asker(p)
    a = ask("anything")
    check("h. brain.js answers with getFacts() (market, live, apps) and its cards show", a.startswith("STUB NQ market") and "room 1105.6" in a
          and "zenith,planner,kalshi,stubapp" in a and "Stub card" in p.text_content("#talk"), a)
    states = p.evaluate("window.__coreStates")
    check("h. the centerpiece follows the conversation (thinking, then idle)", "thinking" in states and states[-1] == "idle", states)
    a2 = ask("open planner")
    p.wait_for_timeout(800)
    check("h. the brain's open: 'planner' switches to the Planner", a2 == "STUB opening the planner" and p.locator("#v-planner").is_visible(), a2)
    go(p, "zenith")
    p.wait_for_timeout(500)
    z = p.evaluate("window.__zen")
    check("h. Zenith mode: zenith-mode.js mounted in its own view, shown, the Planner frame let go",
          z and z["mounts"] == 1 and z["shows"] == [""] and p.locator("#zen").is_visible() and p.locator("#zenStub").is_visible()
          and p.locator("iframe").count() == 0 and p.evaluate("document.documentElement.dataset.zenith") == "module", z)
    check("h. Zenith mode's badge (onState) shows on the ZENITH pill", p.text_content('.bar [data-app="zenith"] .bdg') == "3")
    go(p, "home")
    p.wait_for_timeout(300)
    go(p, "zenith")
    p.wait_for_timeout(300)
    z = p.evaluate("window.__zen")
    check("h. one tap Jarvis <-> Zenith: hidden on Jarvis (kept loaded), shown again, mounted only once",
          z["mounts"] == 1 and z["hides"] >= 1 and z["unloads"] == 0 and len(z["shows"]) == 2 and p.locator("#home").is_hidden(), z)
    p.click("#zenExit")
    p.wait_for_timeout(300)
    check("h. Zenith mode's own exit (onExit) returns to Jarvis", p.locator("#home").is_visible() and p.locator("#zen").is_hidden()
          and p.evaluate("document.documentElement.dataset.mode") == "jarvis")
    ask("zenith route")
    p.wait_for_timeout(800)
    z = p.evaluate("window.__zen")
    check("h. the brain can open Zenith at a route (open('zenith', 'perf'))", z["shows"][-1] == "perf" and p.locator("#zen").is_visible(), z)
    go(p, "kalshi")
    p.wait_for_timeout(400)
    z = p.evaluate("window.__zen")
    check("h. another dashboard lets Zenith go (unload: one dashboard at a time)", z["unloads"] == 1 and p.locator("#v-kalshi").is_visible(), z)
    go(p, "home")
    ask("open blitz")
    p.wait_for_timeout(800)
    z = p.evaluate("window.__zen")
    check("h. a reply {open: 'zenith', route: '#/blitz'} opens Zenith at that page", z["shows"][-1] == "#/blitz", z)
    p.click("#zenExit")
    p.wait_for_timeout(200)
    more(p, "aikey")
    p.wait_for_timeout(200)
    check("h. settings: smart mode on offer with the new brain", not p.locator("#setSmart").is_disabled() and "No key saved" in p.inner_text("#smartState"))
    p.check("#setSmart")
    p.fill("#setKey", "test-key-not-real")
    p.fill("#setModel", "test-model")
    p.click('#setF button[type="submit"]')
    p.wait_for_timeout(200)
    sm = p.evaluate("window.__stubBrain.smart")
    ls = p.evaluate("JSON.stringify(Object.keys(localStorage).map((k) => localStorage.getItem(k)))")
    check("h. smart mode: the key goes to the brain's setSmart (with the provider and depth), the shell keeps no copy, CONNECT MY BRAIN goes away",
          sm.get("on") is True and sm.get("key") == "test-key-not-real" and sm.get("model") == "test-model" and sm.get("provider") == "groq"
          and sm.get("depth") == "auto" and "test-key-not-real" not in ls and p.input_value("#setKey") == "" and p.locator("#brainF").count() == 0, (sm, ls[:200]))
    p.click("#addB")
    p.wait_for_timeout(200)
    check("h. the + sheet offers 'Add Ascend' while apps.js has no Ascend", p.locator("#addAscend").is_visible())
    p.click("#addAscend")
    p.wait_for_timeout(300)
    check("h. Ascend not found: the name is filled in and the link asked for", p.input_value("#addName") == "Ascend" and "Paste its link" in p.inner_text("#addErr"),
          p.inner_text("#addErr"))
    p.fill("#addName", "Nolink")
    p.fill("#addUrl", "")
    p.click('#addF button[type="submit"]')
    p.wait_for_timeout(200)
    check("h. the + sheet shows apps.js's own error (r.error)", "STUB needs a link" in p.inner_text("#addErr"), p.inner_text("#addErr"))
    p.click("#addX")
    check("h. no page errors with the stand-in parts", not errs, errs)
    ctx.close()


def run_missing(br, url, part):
    """Run D: the stand-ins, with one part missing: its fallback takes over."""
    ctx, p, errs, _ = new_page(br)
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_timeout(600)
    k = {"brain.js": "brain", "core-visual.js": "core", "apps.js": "apps", "zenith-mode.js": "zenith"}[part]
    try:                                            # a failed part is tried once more (~0.7 s later) before its fallback takes over
        p.wait_for_function(f"document.documentElement.dataset.{k} !== 'loading'", timeout=6000)
    except Exception:
        pass
    ds = p.evaluate("JSON.stringify(document.documentElement.dataset)")
    ok = json.loads(ds).get(k) == "fallback"
    if part == "brain.js":
        a = asker(p)("is the market open")
        ok = ok and "NQ market" in a and not a.startswith("STUB")
    elif part == "core-visual.js":
        ok = ok and p.locator("#orb").is_visible() and p.locator("#stubCore").count() == 0
    elif part == "apps.js":
        ok = ok and all(x in p.text_content(".bar") for x in ("Planner", "Kalshi")) and "StubApp" not in p.text_content(".bar")
    else:
        go(p, "zenith")
        p.wait_for_timeout(700)
        ok = ok and p.frame_locator("#v-zenith iframe").locator("#z").inner_text() == "Zenith stub" and p.locator("#zen").is_hidden()
    check(f"i. {part} missing: the built-in fallback takes over, the rest still runs, no page errors", ok and not errs, (ds, errs))
    ctx.close()


def dominant(png):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB").resize((90, 195))
    px = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
    q = {}
    for r, g, b in px:
        key = (r // 32, g // 32, b // 32)
        q[key] = q.get(key, 0) + 1
    top = max(q, key=q.get)
    white = sum(1 for r, g, b in px if r > 225 and g > 225 and b > 225) / len(px)
    lum = (top[0] * 32 + 16) * .299 + (top[1] * 32 + 16) * .587 + (top[2] * 32 + 16) * .114
    return lum, white


def run_c(br, url):
    """Run C: the folder as it is (whatever separate parts are merged), with its service worker; then the phone widths."""
    ctx, p, errs, _ = new_page(br, sw=True)
    p.goto(url + "planner/")
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_timeout(800)
    ds = json.loads(p.evaluate("JSON.stringify(document.documentElement.dataset)"))
    check("j. as is: Jarvis starts on its own screen with the mode switch", p.locator("#home").is_visible() and ds.get("mode") == "jarvis"
          and p.locator('#modes [data-app="zenith"]').is_visible(), ds)
    a = asker(p)("is the market open")
    check("j. as is: Jarvis answers", len(a.strip()) > 3, a)
    go(p, "zenith")
    p.wait_for_timeout(1200)
    zen_ok = p.locator("#zen").is_visible() or p.locator("#v-zenith").is_visible()
    if p.locator("#nxOrb").count() and p.locator("#nxOrb").is_visible():
        p.click("#nxOrb")                           # Zenith mode covers the bar: the orb (switcher.js), then Jarvis in its quick row
        p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=30000)
        p.wait_for_timeout(450)
        p.click('.nx-qb[data-nx="home"]')
    elif p.locator(".zm-back").count() and p.locator(".zm-back").is_visible():
        p.click(".zm-back")                         # Zenith mode covers the bar: its own control goes back
    else:
        go(p, "home")
    p.wait_for_timeout(500)
    check("j. as is: one tap to Zenith mode and back", zen_ok and p.locator("#home").is_visible() and p.evaluate("document.documentElement.dataset.mode") == "jarvis", ds)
    has = p.evaluate("""async () => {
        const reg = await Promise.race([navigator.serviceWorker.ready, new Promise((ok) => setTimeout(() => ok(null), 6000))]);
        if (!reg) return 'no worker';
        for (let i = 0; i < 30; i++) {
          const c = await caches.open('jarvis-v79');
          const got = await Promise.all(['./index.html', './data.js', './%s', './orbitron.woff2', './rajdhani-500.woff2'].map((u) => c.match(u)));
          if (got.every(Boolean)) return 'ok';
          await new Promise((ok) => setTimeout(ok, 200));
        }
        return 'missing';
    }""".replace("'./%s'", f"'./{JCSS}'"))
    check("j. the worker installs and saves the page, data.js, jarvis.css and the fonts (a part not on the site is skipped)", has == "ok", has)
    p.reload()
    ready(p)
    p.wait_for_timeout(300)
    # QA 2026-11-01: on a slow network only the page waits (3.5 s), then its files come from the saved copy at once; it used to
    # wait 3.5 s more for each file (css, data.js ...): usable after ~10 s instead of ~3.6 s
    SLOW["s"] = 6.0
    p.reload(wait_until="commit")
    try:
        ready(p)
        # the page's own clock (from its navigation): when the saved page arrived, when its start finished
        t1, t2 = p.evaluate("[performance.getEntriesByType('navigation')[0].responseStart / 1000, window.__jarvisReadyMs / 1000]")
    except Exception:                                   # noqa: BLE001 - reported below
        t1, t2 = 99.0, 99.0
    SLOW["s"] = 0.0
    # the page itself waits up to 3.5 s; after it, the old chain waited 3.5 s more for each file (css, data.js, ...)
    check("j. slow network (every answer 6 s): the saved page in ~3.5 s, then usable at once (its own files never wait again)",
          t1 < 6.0 and t2 - t1 < 5.0, (round(t1, 2), round(t2 - t1, 2)))     # the old chain: 3.5 s per file after the page (7 s and more)
    p.wait_for_timeout(300)
    ctx.set_offline(True)
    p.reload()
    try:
        ready(p)
        off_ok = p.locator("#home").is_visible()
    except Exception as e:                              # noqa: BLE001 - reported below
        off_ok = str(e)[:120]
    p.wait_for_timeout(300)
    lum, white = dominant(p.screenshot())
    check("j. offline: Jarvis opens from its saved copy (page, data.js, styles, fonts), dark, cards from the last numbers",
          off_ok is True and lum < 70 and "$1,106" in p.text_content("#cards"), (off_ok, lum))
    ctx.set_offline(False)
    check("j. no page errors as is", not errs, errs)
    ctx.close()
    # k. phone sizes: 375 x 667 (iPhone SE), 375 / 390 x 844, 430 x 932
    for wdt, hgt in ((375, 667), (375, 844), (390, 844), (430, 932)):
        ctx, p, errs, _ = new_page(br, width=wdt, height=hgt)
        p.goto(url + "planner/")
        p.goto(url + "jarvis/")
        ready(p)
        p.wait_for_timeout(1000)
        w = p.evaluate("""(() => {
            const de = document.documentElement, bar = document.querySelector('.bar-in').getBoundingClientRect();
            const over = [...document.querySelectorAll('#home *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > innerWidth + 0.5 && !e.closest('[aria-hidden="true"]'); })
              .map((e) => e.tagName + '.' + e.className).slice(0, 4);
            const z = document.querySelector('#modes [data-app="zenith"]').getBoundingClientRect(), j = document.querySelector('#modes [data-app="home"]').getBoundingClientRect();
            const dock = document.querySelector('#dock').getBoundingClientRect();
            return { sw: de.scrollWidth, cw: de.clientWidth, bar: bar.right, z: [z.left, z.right], j: [j.left, j.right], dock: [dock.left, dock.right, dock.bottom], over };
        })()""")
        lum, white = dominant(p.screenshot())
        sz = f"{wdt} x {hgt}"
        check(f"k. {sz}: no sideways scroll, nothing past the right edge, JARVIS and ZENITH fully on screen, the dock inside",
              w["sw"] <= w["cw"] and not w["over"] and w["j"][0] >= 0 and w["z"][1] <= wdt and w["bar"] <= wdt + 0.5
              and w["dock"][0] >= 0 and w["dock"][1] <= wdt and w["dock"][2] <= hgt, w)
        check(f"k. {sz}: never a white screen (main colour dark, {white:.1%} near-white)", lum < 70 and white < 0.06, (lum, white))
        if os.environ.get("JARVIS_SHOTS"):
            os.makedirs(os.environ["JARVIS_SHOTS"], exist_ok=True)
            p.screenshot(path=os.path.join(os.environ["JARVIS_SHOTS"], f"jarvis_{wdt}x{hgt}.png"))
        # the fixed stack (the dock, the next chip, the search button) never covers the Jarvis screen: the screen scrolls above
        # it, and the hint and the HANDS-FREE · mic · VOICE row scrolled into view sit clear of all three
        ov = p.evaluate("""(() => {
            const R = (q) => { const r = document.querySelector(q).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
            const hit = (a, b) => a[0] < b[2] - 0.5 && b[0] < a[2] - 0.5 && a[1] < b[3] - 0.5 && b[1] < a[3] - 0.5;
            const stack = { dock: R('#dock'), chip: R('#next'), fab: R('#fab') }, home = R('#home'), out = [];
            for (const [a, b] of [['dock', 'chip'], ['dock', 'fab'], ['chip', 'fab']]) if (hit(stack[a], stack[b])) out.push(a + '/' + b);
            if (home[3] > Math.min(stack.dock[1], stack.chip[1], stack.fab[1]) + 0.5) out.push('home under the stack');
            for (const q of ['.vrow', '.hint2']) {
              document.querySelector(q).scrollIntoView({ block: 'end' });
              const r = R(q);
              if (r[1] < home[1] - 0.5 || r[3] > home[3] + 0.5) out.push(q + ' not reachable');
              for (const k of Object.keys(stack)) if (hit(r, stack[k])) out.push(q + ' under ' + k);
            }
            document.getElementById('home').scrollTop = 0;
            return out;
        })()""")
        check(f"k. {sz}: the dock, the next chip and the search button never cover the hint or the mic row (both reachable, nothing over them)", not ov, ov)
        if wdt >= 390:
            first = p.evaluate("(() => { document.getElementById('home').scrollTop = 0; const v = document.querySelector('.vrow').getBoundingClientRect(), h = document.getElementById('home').getBoundingClientRect(); return [Math.round(v.bottom), Math.round(h.bottom)]; })()")
            # AGORA home (2026-11-09): the hero, the Atlas card and the cards come first and the HANDS-FREE row is reached by scrolling
            # (it stays reachable: the check above); the first screen always holds the Ask Jarvis dock with its mic, in reach of the thumb
            dock = p.evaluate("(() => { const m = document.querySelector('#dock #bigmic, #dock .ask .key, #dock .ask button'), q = document.getElementById('q'); const r = (e) => e ? e.getBoundingClientRect() : null; const a = r(m), b = r(q); return [a && Math.round(a.bottom), b && Math.round(b.bottom), innerHeight]; })()")
            check(f"k. {sz}: the Ask Jarvis field and its mic are on the first screen (no scrolling)", dock[0] and dock[1] and dock[0] <= dock[2] and dock[1] <= dock[2], (first, dock))
        # D1: nothing cut short (KALSHI TODAY's words, the Market card's NQ last, the ⋯ keys), every tap target 44 px tall (pads count)
        tsz = """(q) => {
            const hitH = (el) => { el.scrollIntoView({ block: 'center', inline: 'center' }); const r = el.getBoundingClientRect(); if (r.height >= 43.5) return r.height;
              const x = r.left + r.width / 2, a = document.elementFromPoint(x, r.top - 4.5), b = document.elementFromPoint(x, r.bottom + 4.5);
              return r.height + (a && el.contains(a) ? 5 : 0) + (b && el.contains(b) ? 5 : 0); };
            const out = [];
            // a key the layout hides on purpose (display: none: Send on an empty field, 2026-11-18) is no tap target; it is measured once shown (below)
            for (const s of q) for (const el of document.querySelectorAll(s)) { if (!el.getClientRects().length) continue; const h = hitH(el); if (h < 43.5) out.push(s + ' ' + (el.textContent || '').trim().slice(0, 12) + ' ' + h); }
            document.getElementById('home').scrollTop = 0;
            return out;
        }"""
        small = p.evaluate(tsz, ['.bar .pm', '#addB', '.sug', '#next', '.pillb', '#bigmic', '#fab', '.ask .key', '#q'])
        if wdt > 360:                               # Send shows once something is typed (a phone up to 360 px wide: the keyboard's Send key sends)
            p.fill("#q", "status")
            sent = p.evaluate("(() => { const b = document.querySelector('.ask .key.send'); return !!b && b.getClientRects().length > 0; })()")
            small += p.evaluate(tsz, ['.ask .key.send']) + ([] if sent else ['.ask .key.send not shown with text typed'])
            p.fill("#q", "")
        p.click("#moreB")                          # the ⋯ menu covers the middle of a small phone: its keys on their own
        small += p.evaluate(tsz, ['#more .key'])
        cut = p.evaluate("""[...document.querySelectorAll('#kpct, #kusd, #npnl, #p-market .kv strong, #more .key, .hsub')].filter((e) => e.scrollWidth > e.clientWidth + 0.5)
            .map((e) => (e.id || e.className) + ':' + e.textContent.slice(0, 24))""")
        p.click("#moreB")
        check(f"k. {sz}: nothing cut short (KALSHI TODAY, the market's NQ last, the ⋯ keys) and every tap target is 44 px tall", not cut and not small, (cut, small))
        if (wdt, hgt) == (390, 844):
            # real taps: the centre of every card hits the card itself (no decorative layer over it), and a real tap opens it
            hits = p.evaluate("""[...document.querySelectorAll('#cards [data-app]')].map((c) => { c.scrollIntoView({ block: 'center' });
                const r = c.getBoundingClientRect(), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                return [c.dataset.app, !!e && c.contains(e)]; })""")
            p.evaluate("document.getElementById('home').scrollTop = 0")
            p.locator('#cards [data-app="kalshi"]').click()
            p.wait_for_timeout(600)
            check("k. 390 x 844: every card takes a real tap at its centre, and a real tap on the Kalshi card opens Kalshi",
                  hits and all(h[1] for h in hits) and p.locator("#v-kalshi").is_visible(), hits)
        check(f"k. {sz}: no page errors", not errs, errs)
        ctx.close()


def run_look(br, url):
    """Run L: the old Jarvis look and its features, on the folder as it is."""
    ctx, p, errs, kal = new_page(br, boot=True, voice=True)
    # the boot screen timed on the page's own clock, from its first log line to its removal (2026-11-18: read after ready() on a busy
    # machine it had already gone, the start's feed requests holding the main thread for seconds after the ready marker)
    ctx.add_init_script("""(() => { const B = window.__bootfx = { shown: false, t0: 0, gone: 0, log: '', lt: [] };
      try { new PerformanceObserver((l) => { for (const e of l.getEntries()) B.lt.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch (e) { B.ltOff = true; }
      const mo = new MutationObserver(() => {
        const el = document.getElementById('bootfx'), lg = document.getElementById('bootlog');
        if (el && lg && lg.textContent && !B.t0) { B.t0 = performance.now(); B.shown = getComputedStyle(el).display !== 'none'; }
        if (lg && lg.textContent) B.log = lg.textContent;
        if (B.t0 && !el && !B.gone) { B.gone = performance.now(); mo.disconnect(); } });
      mo.observe(document, { childList: true, subtree: true, characterData: true });
      // the line under the core as the brain set it, before the first-open briefing (briefing.js, 5.2 s after load) puts its title there:
      // on a busy machine the look below is read after that, so it reads this copy (2026-11-18 night-jgreen)
      const so = new MutationObserver(() => { const s = document.getElementById('says'); if (!s) return;
        if (!(window.__jarvisBrief && window.__jarvisBrief.runs)) B.says = s.textContent; });
      so.observe(document, { childList: true, subtree: true, characterData: true }); })();""")
    p.goto(url + "planner/")
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("!document.getElementById('bootfx')", timeout=8000)
    bt = p.evaluate("""(() => { const B = window.__bootfx; return { shown: B.shown, t0: B.t0, gone: B.gone, log: B.log, blocked: B.ltOff || !B.gone ? null
        : Math.round(B.lt.reduce((t, [s, d]) => t + Math.max(0, Math.min(B.gone, s + d) - Math.max(B.t0, s)), 0)) }; })()""")
    # its own time = the page's clock less the main thread's blocked time (the software-drawn 3D core and the start's feeds hold a test
    # machine's main thread for a second: its 0.84 s timer then fires late), like the intro's fade below; the wall clock under 4 s
    took = (bt["gone"] - bt["t0"] - (bt["blocked"] or 0)) / 1000 if bt["t0"] and bt["gone"] and bt["blocked"] is not None else 99
    # Classic Jarvis (the default again, 2026-11-18): the HUD boot log as it was (f8df6008: > CORE .... ONLINE, > ZENITH · NQ BOTS ...)
    check("l. the boot screen: the HUD boot log (> CORE ... ONLINE) on the first open, gone within 1.2 s of its own time (the wall clock < 4 s)",
          bt["shown"] and bt["log"].startswith("> CORE ") and "ONLINE" in bt["log"] and took < 1.3
          and bt["gone"] - bt["t0"] < BK.limit_ms(4000, "boot screen wall", cap=4900), (bt, took))
    p.wait_for_timeout(600)
    look = p.evaluate("""(async () => {
        await document.fonts.ready;
        const cs = getComputedStyle(document.documentElement), t = document.querySelector('.title');
        return { c: cs.getPropertyValue('--c').trim(), bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme,
                 orb: document.fonts.check('700 16px Orbitron'), raj: document.fonts.check('500 16px Rajdhani'),
                 tfont: getComputedStyle(t).fontFamily, title: t.textContent, state: document.getElementById('state').textContent,
                 hud: !!document.querySelector('#hud, .hudring, #hudBot, #hudTop'),
                 says: (window.__jarvisBrief && window.__jarvisBrief.runs && window.__bootfx.says) || document.getElementById('says').textContent, ticks: 0,
                 bars: document.querySelectorAll('#vbars i').length, fx: document.documentElement.dataset.fx,
                 jlook: document.documentElement.dataset.jlook || '', saved: localStorage.getItem('jarvis.look') };
    })()""")
    # 2026-11-18 (owner: Jarvis "back to how it was"): Classic Jarvis is the default look again (violet HUD on the Agora theme,
    # data-jlook="classic", Orbitron titles); AGORA gold is the opt-in ('jarvis.look' = 'agora': tests.test_jarvis_classic)
    check("l. Classic Jarvis by default (violet #a855f7 on the Agora theme, nothing saved); the title OLYMPUS in Orbitron",
          look["c"] == "#a855f7" and look["theme"] == "agora" and look["jlook"] == "classic" and look["saved"] is None
          and look["tfont"].lstrip('"').startswith("Orbitron") and look["title"] == "OLYMPUS", look)
    check("l. no HUD ring around the core any more (AGORA); the state word, 32 voice bars and the line under the core",
          not look["hud"]
          and look["state"] == "Standby" and look["bars"] == 32 and "Tap the core or type below to speak with me." in look["says"] and look["fx"] == "high", look)
    if p.evaluate("document.documentElement.dataset.brain") == "module":
        check("l. brain.js: the old Jarvis's line under the core until the first question ('Good day. Tap the core ...')", look["says"].startswith("Good day. Tap the core"), look["says"])
    if p.evaluate("document.documentElement.dataset.core") == "module":
        c3 = p.evaluate("[!document.querySelector('.hudring') ? 'none' : 'x', !document.querySelector('.pad') ? 'none' : 'x', !!document.querySelector('#coreSlot canvas'), window.__jarvis.core()]")
        check("l. core-visual.js: the 3D reactor in the centre (its own HUD ring and dial: the 2D ones step aside)",
              c3[0] == "none" and c3[1] == "none" and c3[2] and c3[3] and c3[3].get("design") == "reactor", c3)
    bg = p.evaluate("[!!document.querySelector('#bgglobe, .floor, .scan, .hudring, .pad'), !!document.querySelector('.bgfx')]")
    check("l. the backdrop is calm: no wireframe globe, grid floor, scanlines or projector pad (the 3D courtyard, or the plain marble dark, is all there is)", bg[0] is False and bg[1], bg)
    # the Kalshi state settles when its first answer lands (a 404 here): wait for it rather than for a fixed time (night-fitperf 2026-11-19:
    # the boot screen now leaves ~0.5 s sooner, so a fixed wait after it read the box while it still said LINKING…)
    try:
        p.wait_for_function("document.getElementById('kpct').textContent !== 'LINKING…' && document.getElementById('kpct').textContent !== '--'", timeout=15000, polling=200)
    except Exception:  # noqa: BLE001  (the check below says what it shows)
        pass
    head = p.evaluate("[document.getElementById('kpct').textContent, document.getElementById('npnl').textContent, document.getElementById('nsub').textContent]")
    check("l. KALSHI TODAY says OFFLINE (not connected yet) while kalshi.json is missing; NQ BOTS TODAY adds the three accounts (+$308)",
          head[0] == "OFFLINE" and head[1] == "+$308" and head[2].startswith("3 accounts"), head)
    panels = p.text_content("#panels")
    check("l. the systems panels: the market (NQ last 21,234.50, next open / close), the activity feed (a Zlarior trade), add-ons (verse, quote, BTC / ETH / SOL), system core (bot loop)",
          "21,234.50" in panels and re.search(r"(Opens|Closes) in \d", panels) and "Zlarior · LONG 3 · target" in panels and "+$413" in panels
          and "Verse of the day" in panels and "KJV" in panels and "Quote of the day" in panels and "$77,000" in panels and "$94.52" in panels
          and "+1.5%" in panels and "−1.6%" in panels and "Bot loop" in panels and "PC LIVE" in panels, panels[:600])
    nxt = p.text_content("#next")
    check("l. the next-event chip from the Planner (or 'Nothing scheduled today')", "Gym" in nxt or "Review fills" in nxt or "Nothing" in nxt or "TO-DO" in nxt, nxt)
    p.click("#moreB")
    keys = p.evaluate("[...document.querySelectorAll('#more [data-key]')].map((b) => b.dataset.key + ':' + b.textContent)")
    check("l. the ⋯ menu: Core, Full screen, Theme, AI key, Hold-to-talk, 3D, Tilt (off), Alerts, Sound, Hide $, Briefing, Apps, Obsidian",
          [k.split(":")[0] for k in keys] == ["core", "full", "theme", "aikey", "hold", "fx", "tilt", "alerts", "sound", "hide", "brief", "apps", "obsidian"]
          and "tilt:Tilt: off" in keys and "fx:3D: high" in keys and "hold:Hold-talk: on" in keys and "sound:Sound: off" in keys, keys)
    p.click('#more [data-key="fx"]')
    fx = p.evaluate("[document.documentElement.dataset.fx, localStorage.getItem('jfx'), document.documentElement.dataset.fxSet]")
    check("l. 3D key: high -> low, kept on this phone", fx == ["low", "low", "1"], fx)
    p.click('#more [data-key="fx"]')
    p.click('#more [data-key="fx"]')
    p.click('#more [data-key="fx"]')                     # off -> ultra -> high
    p.click('#more [data-key="core"]')
    core = p.evaluate("[document.getElementById('orb').dataset.design, localStorage.getItem('jcorestyle')]")
    c3d = p.evaluate("window.__jarvis.core()")
    check("l. Core key: the next core design (Singularity), kept (and the 3D core follows when it is here)",
          core == ["singularity", "singularity"] and (c3d is None or c3d.get("design") == "singularity"), (core, c3d))
    p.click('#more [data-key="hide"]')
    hid = p.evaluate("[document.documentElement.classList.contains('money-hidden'), getComputedStyle(document.getElementById('npnl')).filter]")
    check("l. Hide $: every $ figure on the Jarvis screen blurs", hid[0] is True and "blur" in hid[1], hid)
    p.click('#more [data-key="hide"]')
    p.click('#more [data-key="theme"]')
    p.wait_for_timeout(200)
    tg = p.evaluate("""(() => { const t = document.getElementById('setSound'), cs = getComputedStyle(t);
        const segs = [...document.querySelectorAll('#look .seg3 button')].map((b) => [getComputedStyle(b).textTransform, b.getBoundingClientRect().height]);
        const over = [...document.querySelectorAll('#look .seg3 button, #look .th, #look h2, #look h3')].some((b) => b.scrollWidth > b.clientWidth + 0.5);
        return [cs.appearance || cs.webkitAppearance, cs.width, cs.height, getComputedStyle(t, '::before').content, segs.every((x) => x[0] === 'none' && x[1] >= 43.5) && !over]; })()""")
    check("l. the sheets' switches are pill toggles (46 x 26, a knob), the segment buttons in sentence case (AGORA: no upper case) and 44 px", tg[0] == "none" and tg[1] == "46px" and tg[2] == "26px"
          and tg[3] == '""' and tg[4], tg)
    check("l. Theme opens the Look sheet: one theme (Agora; the neon ones were removed), effects levels, the core designs, sounds, calm motion (off), tilt",
          p.locator("#look").is_visible() and p.locator("#themes .th").count() == 1 and p.locator('#fxSeg [aria-pressed="true"]').inner_text().upper() == "HIGH"
          and p.locator("#coreSeg button").count() == 2 and p.get_attribute("#themes .th >> nth=0", "data-theme-k") == "agora"
          and not p.locator("#setCalm").is_checked())
    p.click("#setCalm")
    calm = p.evaluate("localStorage.getItem('jarvis.calm')")
    p.click("#setCalm")
    check("l. Calm motion: kept on this phone (the 3D core then follows the iPhone's reduce-motion switch)", calm == "true"
          and p.evaluate("localStorage.getItem('jarvis.calm')") == "false", calm)
    p.evaluate("localStorage.setItem('jtheme', 'reactor-stark')")      # an old copy's neon theme: ignored, the default look stays
    p.click("#lookX")
    p.reload()
    ready(p)
    th = p.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.jlook || '', getComputedStyle(document.documentElement).getPropertyValue('--c').trim(), !!document.getElementById('bootfx')]")
    check("l. an old saved neon theme is ignored: the default Classic violet on the Agora theme from the first paint; no boot screen again in the same launch",
          th == ["agora", "classic", "#a855f7", False], th)
    # voice: tap the big mic, Jarvis hears, answers out loud in her voice at its own pace (tts.js: rate 1.0 / pitch 1.0, 2026-11-03), the state word follows
    p.evaluate("window.__utter = 'is the market open'; window.__states = []; window.__said = []")
    p.click("#bigmic")
    p.wait_for_function("window.__said.length > 0", timeout=6000)
    p.wait_for_function("document.documentElement.dataset.state === 'idle'", timeout=4000)
    said, states = p.evaluate("[window.__said, window.__states]")
    check("l. voice: tap the mic -> LISTENING -> THINKING -> SPEAKING -> STANDBY; the answer is read at the voice's own pace (rate and pitch 1.0 within +-12%; the words by speech-text.js 2026-11-18)",
          "market" in said[0][0].lower() and abs(said[0][1] - 1.0) < 0.12 and abs(said[0][2] - 1.0) < 0.12
          and [s for s in states if s in ("listening", "thinking", "speaking", "idle")][:4] == ["listening", "thinking", "speaking", "idle"], (said, states))
    p.click("#hf")
    p.wait_for_function("window.__srStarts >= 3", timeout=8000)
    p.click("#hf")
    p.wait_for_timeout(300)
    hf = p.evaluate("[window.__srStarts, document.getElementById('hf').getAttribute('aria-pressed'), window.__said.length]")
    check("l. hands-free: keeps listening after each answer while on; off stops it", hf[0] >= 3 and hf[1] == "false" and hf[2] >= 2, hf)
    # let the last hands-free answer finish before the next questions (it would land in their chat)
    p.wait_for_timeout(1500)
    p.wait_for_function("window.__jarvis.state() === 'idle'", timeout=8000)
    p.wait_for_timeout(500)
    # the brain as it is in this folder (brain.js when merged, else the built-in one)
    real = p.evaluate("document.documentElement.dataset.brain") == "module"
    ask = asker(p)
    ask("hide my balance")
    hid1 = p.evaluate("[document.documentElement.classList.contains('money-hidden'), localStorage.getItem('jarvis.hide')]")
    ask("show my balance")
    hid2 = p.evaluate("[document.documentElement.classList.contains('money-hidden'), localStorage.getItem('jarvis.hide')]")
    if real:
        check("l. the brain's control replies: 'hide my balance' blurs the $ figures, 'show my balance' brings them back (one switch, jarvis.hide)",
              hid1 == [True, "1"] and hid2 == [False, "0"], (hid1, hid2))
        more(p, "aikey")
        p.wait_for_timeout(200)
        sheet = p.evaluate("[document.getElementById('setProv').value, document.getElementById('setProv').disabled, [...document.querySelectorAll('#setDepth button')].map((b) => b.dataset.depth), document.getElementById('smartState').textContent]")
        check("l. AI key with brain.js: Groq by default, Gemini and Anthropic, depth auto / quick / think / deep, its state shown",
              sheet[0] == "groq" and sheet[1] is False and sheet[2] == ["auto", "quick", "think", "deep"] and "No key saved" in sheet[3] and "Groq" in sheet[3], sheet)
        p.fill("#setKey", "sk-ant-test-not-real")
        prov = p.input_value("#setProv")
        p.fill("#setKey", "gsk_test_not_real")
        p.click('#setDepth [data-depth="think"]')
        p.click('#setF button[type="submit"]')
        p.wait_for_timeout(200)
        more(p, "aikey")
        p.wait_for_timeout(200)
        st1 = p.inner_text("#smartState")
        keys = p.evaluate("Object.keys(localStorage).filter((k) => (localStorage.getItem(k) || '').includes('gsk_test_not_real'))")
        p.click("#setForget")
        st2 = p.inner_text("#smartState")
        p.click("#setX")
        check("l. AI key: the provider follows the key (sk-ant- Anthropic, gsk_ Groq); saved with depth think and on; kept only in the brain's own storage; Clear keys drops it",
              prov == "anthropic" and "A key is saved" in st1 and "Groq" in st1 and "depth think" in st1 and " on" in st1 and keys == ["jarvis.smart"]
              and "removed" in st2, (prov, st1, keys, st2))
    else:
        check("l. hide / show balance by voice: the built-in brain has no such control (brain.js not merged here)", hid1[0] is False, hid1)
    p.click("#fab")
    p.fill("#palQ", "planner")
    p.press("#palQ", "Enter")
    p.wait_for_timeout(600)
    check("l. the search button: the command palette ('planner' -> Open Planner)", p.locator("#v-planner").is_visible())
    go(p, "home")
    check("l. no page errors in the look run", not errs, errs)
    ctx.close()
    # What's new: once per release, as the old Jarvis's popup; "what's new" shows it again
    ctx, p, errs, _ = new_page(br, news=True)
    # Keep the first-card assertion independent of scheduled bot cards in ET clock windows.
    ctx.add_init_script("try { localStorage.setItem('jarvis.bots.set', JSON.stringify({ on: true, plan: false, recap: false, rituals: false })); } catch (e) {}")
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("(() => { const t = document.getElementById('wnb'); return !!t && !t.hidden; })()", timeout=12000)
    tt = p.text_content("#wnb")
    bn = p.evaluate("(() => { const r = document.getElementById('wnb').getBoundingClientRect(), c = document.getElementById('htoday') || document.querySelector('.hpanel'), q = c.getBoundingClientRect(); return [getComputedStyle(document.getElementById('wnb')).position, r.bottom <= q.top + 1, r.height]; })()")
    p.click("#wnbA")
    p.wait_for_timeout(300)
    wn = p.text_content("#talk")
    p.reload()
    ready(p)
    p.wait_for_timeout(2600)
    again = p.locator("#wnb").count() == 0 or p.locator("#wnb").is_hidden()
    a = asker(p)("what's new")
    check("l. What's new: a card once per release (Show me -> the notes), not again after; 'what's new' shows the notes any time",
          "What's new" in tt and bn[0] == "static" and bn[1] and bn[2] < 120 and "What's new in Jarvis" in wn and "Every app is its own dashboard" in wn and again and "What's new in Jarvis" in a and not errs, (tt, bn, again, a[:80], errs))
    ctx.close()
    # the OS 'reduce motion' setting: the effects start low (nothing spins), no boot screen
    ctx, p, errs, _ = new_page(br, boot=True, reduced_motion="reduce")
    p.goto(url + "jarvis/")
    ready(p)
    rm = p.evaluate("[document.documentElement.dataset.fx, getComputedStyle(document.querySelector('.orb .r1')).animationName, !!document.getElementById('bootfx')]")
    check("l. reduced motion: effects low, the rings still, no boot screen", rm == ["low", "none", False], rm)
    check("l. no page errors with reduced motion", not errs, errs)
    ctx.close()


# the switch order: Jarvis, TRADING, LIFE, MONEY (apps.js BUILT_INS); the test site has Data City's folder, not the others'
def _registry():
    """apps.js is the one source of truth (the list GROWS): its groups and BUILT_INS, read with node, so no count or name is typed here."""
    out = subprocess.run(["node", "--input-type=module", "-e",
                          "import { createRequire } from 'module'; const d = createRequire(process.cwd() + '/')('../olympus/doors.js');"   # the orb's four doors (2026-11-18)
                          "import('./apps.js').then((m) => console.log(JSON.stringify({ groups: m.GROUPS.map((g) => ({ id: g.id, name: g.name })), apps: m.BUILT_INS.map((a) => ({ id: a.id, name: a.name, group: a.group, accent: a.accent || '', dist: d.DOORS.some((x) => x.ids.indexOf(a.id) >= 0) ? d.doorOf(a.id) : a.group === 'trading' ? 'zeus' : a.group === 'money' ? 'money' : 'more' })), dists: d.DOORS.map((x) => ({ id: x.id, title: x.title })) })))"],
                         cwd=JV, capture_output=True, text=True, timeout=60, check=True).stdout
    return json.loads(out)


_REG = _registry()
_GIDS = [g["id"] for g in _REG["groups"]]
_gi = lambda a: _GIDS.index(a["group"]) if a["group"] in _GIDS else len(_GIDS) - 1       # noqa: E731 - an unknown group is MORE
# the switch order: Jarvis, then each group's apps in apps.js order (the shell's byGroup)
SORTED_APPS = sorted(_REG["apps"], key=lambda a: _gi(a))                                  # stable: list order inside a group
ORDER = ["home"] + [a["id"] for a in SORTED_APPS]
GROUP_HEADS = [g["name"] for i, g in enumerate(_REG["groups"]) if any(_gi(a) == i for a in _REG["apps"])]
GROUP_IDS_USED = [g["id"] for i, g in enumerate(_REG["groups"]) if any(_gi(a) == i for a in _REG["apps"])]
NX_LABEL = {"home": "JARVIS", "zenith": "NQ BOT", "planner": "CALENDAR", "kalshi": "KALSHI"}   # index.html NX_NAMES
NAMES_ORDER = [NX_LABEL.get(i, next((a["name"] for a in _REG["apps"] if a["id"] == i), i).upper()) for i in ORDER]
# the test site only has these folders (stubs); every other app answers 404 and shows "not on the site yet"
ON_SITE = {"home", "zenith", "planner", "kalshi", "datacity"}
NOT_ON_SITE = [i for i in ORDER if i not in ON_SITE]
# the orb is organised by the FOUR DOORS (2026-11-18; five districts before): Jarvis, then ZEUS Trading, Money, Kalshi, More (switcher.js DIST = olympus/doors.js)
_DIDS = [d["id"] for d in _REG["dists"]]
D_SORTED = sorted(SORTED_APPS, key=lambda a: _DIDS.index(a["dist"]))                       # stable: apps.js order inside a district
D_ORDER = ["home"] + [a["id"] for a in D_SORTED]
D_USED = [d for d in _REG["dists"] if any(a["dist"] == d["id"] for a in _REG["apps"])]
D_HEADS = [d["title"] for d in D_USED]
D_IDS = [d["id"] for d in D_USED]
D_ALL5 = [d["id"] for d in _REG["dists"]]
D_WITH_EXTRAS = [d["title"] for d in _REG["dists"] if d["id"] == "more" or any(a["dist"] == d["id"] for a in _REG["apps"])]   # the added apps (Alpha, Beta, Gamma) sit in More
D_RING = [d["id"] for d in _REG["dists"] if d["id"] == "more" or any(a["dist"] == d["id"] and a["id"] in ("zenith", "planner", "kalshi", "datacity") for a in _REG["apps"])]   # doors with an app that opens (the test site)
D_DATACITY = next(a["dist"] for a in _REG["apps"] if a["id"] == "datacity")
D_NAMES_ORDER = [NX_LABEL.get(i, next((a["name"] for a in _REG["apps"] if a["id"] == i), i).upper()) for i in D_ORDER]
D_ON = [i for i in D_ORDER if i in ON_SITE]
D_MONEY_FIRST = next(a["id"] for a in D_SORTED if a["dist"] == "money")
MONEY_FIRST = next(a["id"] for a in SORTED_APPS if a["group"] == "money")       # the first MONEY app: the group chip glides its card to the middle
# each tile's colour: its accent in apps.js as "r,g,b" (read, never typed: the AGORA accents of 2026-11, commit 45637b2, replaced the old neon)
ACR = {a["id"]: ",".join(str(int(a["accent"][k:k + 2], 16)) for k in (1, 3, 5)) for a in _REG["apps"] if re.fullmatch(r"#[0-9a-fA-F]{6}", a["accent"] or "")}


def run_olympus(br, url):
    """p. the OLYMPUS apps (2026-11-03): the grid on the Jarvis screen, an app not on the site, the orb's groups, quick row and ring.
    The test site has Data City (its jarvis.json) but not Mind or Daphne (their folders missing)."""
    ctx, p, errs, _ = new_page(br)
    ctx.add_init_script("try { if (!localStorage.getItem('jarvis.orb.use')) localStorage.setItem('jarvis.orb.use', JSON.stringify({ kalshi: 4, datacity: 2 })); } catch (e) {}")   # once (init scripts run in every frame)
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("document.documentElement.dataset.switcher === 'module' && !!document.getElementById('nxOrb')", timeout=30000)
    # the cards arrive: Data City's from its jarvis.json, Mind's and Daphne's folders answer 404
    p.wait_for_function("""(ids) => { const t = (id) => document.querySelector(`#olyApps [data-app="${id}"]`);
        return t('datacity') && /19,942/.test(t('datacity').textContent) && ids.every((id) => t(id) && t(id).classList.contains('soon')); }""",
        arg=NOT_ON_SITE, timeout=30000, polling=100)
    g = p.evaluate("""(() => { const box = document.getElementById('olyApps');
        return { heads: [...box.querySelectorAll('.og-g')].map((h) => h.textContent), tiles: [...box.querySelectorAll('.og-t')].map((t) => ({ id: t.dataset.app || (t.dataset.ogAdd ? 'add' : ''),
          name: (t.querySelector('.og-n') || {}).textContent, v: (t.querySelector('.og-v') || {}).textContent || '', s: (t.querySelector('.og-s') || {}).textContent || '',
          soon: t.classList.contains('soon'), acr: t.style.getPropertyValue('--acr'), h: t.getBoundingClientRect().height, label: t.getAttribute('aria-label') })),
          cards: [...document.querySelectorAll('#cards > [data-own]')].map((c) => c.dataset.app || c.dataset.slot || '') }; })()""")
    t = {x["id"]: x for x in g["tiles"]}
    check("p. the OLYMPUS grid: TRADING, LIFE, MONEY with every app in the orb's order (+ ADD), each tile in its own colour, 44 px+",
          g["heads"] == GROUP_HEADS and [x["id"] for x in g["tiles"]] == ORDER[1:] + ["add"]
          and all(t[i]["acr"] == ACR[i] for i in ACR if i in t) and t["datacity"]["acr"] != t["tree"]["acr"] and all(x["h"] >= 44 for x in g["tiles"]),
          (g["heads"], [(i, t.get(i, {}).get("acr"), ACR[i]) for i in ACR if t.get(i, {}).get("acr") != ACR[i]][:6]))
    check("p. live status on the tiles: Data City from its jarvis.json (19,942 · 25 pass the noise guard), NQ BOT and KALSHI from the shell's own feeds",
          t["datacity"]["v"] == "19,942" and "25 pass the noise guard" in t["datacity"]["s"] and t["zenith"]["name"] == "NQ BOT" and t["zenith"]["v"].startswith("+$")
          and t["kalshi"]["v"] and "Data City" in t["datacity"]["label"], g["tiles"])
    check("p. an app whose folder is not on the site (Mind, Daphne): 'Not on the site yet', dimmed, never an error",
          t["mind"]["soon"] and t["tree"]["soon"] and "Not on the site yet" in t["mind"]["s"] and t["mind"]["v"] == "SOON" and not t["datacity"]["soon"], g["tiles"])
    check("p. the OLYMPUS apps are tiles, not cards: the project cards stay Zenith and Kalshi (the Planner is a tile since it joined apps.js)", g["cards"] == ["zenith", "kalshi"], g["cards"])
    # the stagger: once, when the grid comes into view (3D effects High here)
    st0 = p.evaluate("document.getElementById('olyApps').className")
    p.evaluate("document.getElementById('olyApps').scrollIntoView({ block: 'center' })")
    try:
        p.wait_for_function("!document.getElementById('olyApps').classList.contains('pre')", timeout=8000, polling=50)
        p.wait_for_function("!document.getElementById('olyApps').classList.contains('go')", timeout=8000, polling=100)
    except Exception:                                   # noqa: BLE001 - reported below
        pass
    op = p.evaluate("[...document.querySelectorAll('#olyApps .og-t')].map((t) => +getComputedStyle(t).opacity)")
    check("p. the tiles come in one after the other the first time the grid is seen (High), then stay put",
          "pre" in st0.split() and min(op) >= 0.55 and p.evaluate("document.getElementById('olyApps').className") == "og", (st0, op))
    # a tap on Mind (not on the site): a note, Jarvis stays; on Data City: it opens full screen in its own colour
    p.evaluate("document.querySelector('#olyApps [data-app=\"mind\"]').click()")
    p.wait_for_function("(() => { const t = document.getElementById('toast'); return !!t && !t.hidden && /not on the site yet/.test(t.textContent); })()", timeout=5000)
    check("p. a tap on an app not on the site: 'not on the site yet', Jarvis stays (no 404 page inside Jarvis)",
          p.evaluate("window.__jarvis.active()") == "home" and not p.locator("#v-mind").count())
    p.evaluate("document.querySelector('#olyApps [data-app=\"datacity\"]').click()")
    p.wait_for_function("window.__jarvis.active() === 'datacity' && !!document.querySelector('#v-datacity iframe')", timeout=8000)
    try:
        p.wait_for_function("document.querySelector('meta[name=\"theme-color\"]').content === '#05060f'", timeout=8000)
    except Exception:                                   # noqa: BLE001 - reported below
        pass
    dc = p.evaluate("[document.querySelector('#v-datacity iframe').src, document.querySelector('meta[name=\"theme-color\"]').content, document.documentElement.dataset.mode]")
    check("p. a tap on Data City opens it full screen (its own page in Jarvis's frame), its colour behind the status bar",
          dc[0].endswith("/datacity/") and dc[1] == "#05060f" and dc[2] == "app", dc)
    # the orb: groups, chips, the quick row
    p.click("#nxOrb")
    p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=5000)
    p.wait_for_timeout(450)
    o = p.evaluate("""(() => { const row = document.getElementById('nxRow');
        return { heads: [...document.querySelectorAll('#nxTrack .nx-gl')].map((h) => h.textContent), chips: [...document.querySelectorAll('#nxGroups .nx-gb')].map((b) => [b.dataset.nxJump, b.classList.contains('on'), Math.round(b.getBoundingClientRect().height)]),
          off: [...document.querySelectorAll('#nxTrack .nx-card.off')].map((c) => c.dataset.nx), now: (document.querySelector('#nxTrack .nx-card.now') || {}).dataset,
          q: [...row.querySelectorAll('.nx-qb')].map((b) => [b.dataset.nx, Math.round(b.getBoundingClientRect().height)]), seps: row.querySelectorAll('.nx-qs').length,
          scroll: [row.scrollWidth, row.clientWidth, getComputedStyle(row).overflowX], sw: document.documentElement.scrollWidth }; })()""")
    check("p. the orb is organised by the four doors: headings and chips (ZEUS Trading, Money, Kalshi, More; Data City's door, More, lit), the not-yet apps dimmed, Data City NOW",
          o["heads"] == D_HEADS and [c[0] for c in o["chips"]] == D_IDS and [c[0] for c in o["chips"] if c[1]] == [D_DATACITY] and all(c[2] >= 44 for c in o["chips"])
          and sorted(o["off"]) == sorted(NOT_ON_SITE) and o["now"] and o["now"].get("nx") == "datacity", o)
    check("p. the quick row: every app in group order with separators, 44 px+ buttons, one scrollable line (no page sideways scroll)",
          [x[0] for x in o["q"]] == D_ORDER and o["seps"] == len(D_USED) and all(x[1] >= 44 for x in o["q"])
          and o["scroll"][2] == "auto" and o["sw"] <= 390, o)
    p.click('#nxGroups [data-nx-jump="money"]')
    try:
        p.wait_for_function("""(id) => { const t = document.getElementById('nxTrack'), c = t.querySelector('.nx-card[data-nx="' + id + '"]');
            return Math.abs(c.offsetLeft + c.offsetWidth / 2 - (t.scrollLeft + t.clientWidth / 2)) < 45; }""", arg=D_MONEY_FIRST, timeout=20000, polling=50)      # a long smooth scroll over many cards (the list grows)
        jumped = True
    except Exception:                                   # noqa: BLE001 - reported below
        jumped = False
    check("p. a district chip glides the cards to that district (Money: its first app in the middle), the switcher stays open",
          jumped and p.evaluate("document.getElementById('nxRoot').classList.contains('on')"))
    p.click('#nxRow .nx-qb[data-nx="home"]')
    p.wait_for_function("window.__jarvis.active() === 'home'", timeout=5000)
    use = p.evaluate("JSON.parse(localStorage.getItem('jarvis.orb.use'))")
    check("p. every switch counts on this phone for the ring (Data City opened once more, Jarvis once)", use.get("datacity") == 3 and use.get("home") == 1 and use.get("kalshi") == 4, use)
    # the ring with more than six apps: the six most opened, then "more" (the whole switcher)
    p.evaluate("""() => import('./apps.js').then((A) => { for (const n of ['Alpha', 'Beta', 'Gamma']) A.addApp({ name: n, url: 'https://' + n.toLowerCase() + '.example/' }); })""")
    p.evaluate("localStorage.setItem('jarvis.orb.use', JSON.stringify({ 'x-gamma': 9, kalshi: 7, 'x-alpha': 5, zenith: 1 }))")
    p.reload()
    ready(p)
    p.wait_for_function("document.documentElement.dataset.switcher === 'module' && !!document.getElementById('nxOrb')", timeout=30000)
    r = p.evaluate("(() => { const b = document.getElementById('nxOrb').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()")
    p.mouse.move(r[0], r[1]); p.mouse.down()
    p.wait_for_function("document.querySelectorAll('.nx-fan.on .nx-fb').length > 0", timeout=5000)
    p.wait_for_function("[...document.querySelectorAll('.nx-fb')].every((b) => !b.getAnimations || !b.getAnimations().length)", timeout=5000)   # grown out
    ring = p.evaluate("[...document.querySelectorAll('.nx-fan.on .nx-fb')].map((b) => { const q = b.getBoundingClientRect(); return { id: b.dataset.nx || b.dataset.nxDist || (b.dataset.nxSearch ? 'SEARCH' : ''), x: q.left + q.width / 2, y: q.top + q.height / 2, w: q.width, h: q.height }; })")
    ids = [b["id"] for b in ring]
    check("p. the ring is two steps: hold shows the doors that have an app that opens here (of ZEUS Trading, Money, Kalshi, More) and Search; none on top of another, all on screen, 44 px+",
          ids == D_RING + ["SEARCH"] and all((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 >= 44 ** 2 for i, a in enumerate(ring) for b in ring[i + 1:])
          and all(30 <= b["x"] <= 360 and 30 <= b["y"] <= 844 and b["w"] >= 44 and b["h"] >= 44 for b in ring), ring)
    cmd = next(b for b in ring if b["id"] == "more")           # slide onto More and let go: its apps fan out (the added apps most opened first) with Back
    p.mouse.move((r[0] + cmd["x"]) / 2, (r[1] + cmd["y"]) / 2); p.mouse.move(cmd["x"], cmd["y"])
    p.mouse.up()
    p.wait_for_function("[...document.querySelectorAll('.nx-fan.on .nx-fb')].some((b) => b.dataset.nxBack)", timeout=5000)
    ring2 = p.evaluate("[...document.querySelectorAll('.nx-fan.on .nx-fb')].map((b) => b.dataset.nx || (b.dataset.nxBack ? 'BACK' : b.dataset.nxMore ? 'MORE' : '?'))")
    apps2 = [x for x in ring2 if x not in ("BACK", "MORE")]
    check("p. step 2: the door's most opened apps (Gamma 9, Alpha 5 first; at most four, then All <door>), then Back; Zenith / Kalshi are not in More",
          ring2[:2] == ["x-gamma", "x-alpha"] and len(apps2) <= 4 and ring2[-1] == "BACK" and ("x-beta" in apps2 or "MORE" in ring2) and not {"zenith", "kalshi"} & set(apps2), ring2)
    p.click('.nx-fan.on .nx-fb[data-nx-back]')
    p.wait_for_function("[...document.querySelectorAll('.nx-fan.on .nx-fb')].some((b) => b.dataset.nxSearch)", timeout=5000)
    p.click('.nx-fan.on .nx-fb[data-nx-search]')
    p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=5000)
    p.wait_for_timeout(300)
    check("p. Search on the ring opens the switcher with the search box ready", p.evaluate("document.activeElement && document.activeElement.id") == "nxFind")
    heads = p.evaluate("[...document.querySelectorAll('#nxTrack .nx-gl')].map((h) => h.textContent)")
    check("p. the whole switcher: the added apps sit in More (the doors stay in order)", heads == D_WITH_EXTRAS, heads)
    check("p. no page errors", not errs, errs)
    ctx.close()


def run_system(br, url):
    """Run S (2026-11-02, the System view): "everything combined and simple". One line per system (the PC, Zlarior, ATLAS,
    BLITZ, Kalshi, the Planner), one verdict (ALL GOOD / HEADS UP / NEEDS YOU + the one thing to do): the strip in the header,
    the System panel, the orb's strip and alert dot, and the brain's "status" / "how's the pc"."""
    css = open(os.path.join(JV, "jarvis.css"), encoding="utf-8").read()
    sw_src = open(os.path.join(JV, "switcher.js"), encoding="utf-8").read()
    new_rules = [ln for ln in css.splitlines() if re.match(r"^\.(sysbar|sysdots|srow|srows|stodo|panel\.sys)\b", ln)]
    nx_rules = [ln for ln in sw_src.splitlines() if ".nx-sys" in ln or ".nx-alert" in ln]
    check("s. light: the System strip, panel and orb strip use no backdrop blur and no animation of their own",
          new_rules and nx_rules and not any("backdrop" in ln or "animation" in ln for ln in new_rules + nx_rules), len(new_rules))
    ctx, p, errs, kal = new_page(br)
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("document.getElementById('sysv').textContent !== 'CHECKING' && document.querySelectorAll('#p-system .srow').length === 6", timeout=8000)
    s = p.evaluate("""() => ({ v: document.getElementById('sysv').textContent, t: document.getElementById('syst').textContent,
      dots: [...document.querySelectorAll('#sysdots i')].map((i) => i.textContent + ':' + i.className),
      rows: [...document.querySelectorAll('#p-system .srow')].map((r) => ({ id: r.dataset.sysRow, app: r.dataset.app, lvl: r.className.replace('srow ', ''),
        v: r.querySelector('.sv').textContent, t: r.querySelector('.st').textContent })),
      todo: !!document.querySelector('#p-system .stodo'), bar: document.getElementById('sysbar').getBoundingClientRect().height })""")
    rows = {r["id"]: r for r in s["rows"]}
    check("s. the header strip: ALL GOOD, 'Nothing needs you', one dot per system (PC Z A B K P)",
          s["v"] == "ALL GOOD" and s["t"] == "Nothing needs you" and [d.split(":")[0] for d in s["dots"]] == ["PC", "Z", "A", "B", "K", "P"] and s["bar"] >= 34, s)
    check("s. the System panel: PC (CPU / RAM from live.json pc_health, checked in), Zlarior +$213, ATLAS, BLITZ, Kalshi (not connected), Planner",
          list(rows) == ["pc", "lit", "atlas", "blitz", "kalshi", "planner"] and rows["pc"]["v"] == "CPU 23% · RAM 61%" and "checked in 2 min ago" in rows["pc"]["t"]
          and rows["pc"]["lvl"] == "ok" and rows["lit"]["v"] == "+$213" and "RUNNING" in rows["lit"]["t"] and rows["kalshi"]["v"] == "NOT LINKED"
          and rows["kalshi"]["app"] == "kalshi" and rows["planner"]["app"] == "planner" and not s["todo"], s["rows"])
    p.click("#sysbar")
    try:                                                # a smooth scroll (longer since the OLYMPUS grid sits above): waited for, not timed
        p.wait_for_function("(() => { const a = document.getElementById('p-system').getBoundingClientRect(), h = document.getElementById('home').getBoundingClientRect();"
                            " return h.top - 2 <= a.top && a.top < h.bottom - 100; })()", timeout=8000, polling=100)
    except Exception:                                   # noqa: BLE001 - reported below
        pass
    top = p.evaluate("(() => { const a = document.getElementById('p-system').getBoundingClientRect(), h = document.getElementById('home').getBoundingClientRect(); return [Math.round(a.top), Math.round(h.top), Math.round(h.bottom)]; })()")
    check("s. a tap on the strip brings the System panel into view", top[1] - 2 <= top[0] < top[2] - 100, top)
    p.click('#p-system .srow[data-sys-row="kalshi"]')
    p.wait_for_timeout(500)
    cur = p.evaluate("(document.querySelector('#modes [aria-current=\"page\"]') || {dataset: {}}).dataset.app")
    check("s. a tap on a line opens that system (Kalshi)", cur == "kalshi", cur)
    go(p, "home")
    p.wait_for_timeout(300)
    ask = asker(p)
    a1 = ask("status")
    check("s. 'status': the verdict first, then one line per system", a1.startswith("ALL GOOD: nothing needs you.") and "PC (bot server" in a1
          and "Zlarior (50K eval): +$213" in a1 and "Kalshi (its own server): NOT LINKED" in a1, a1)
    a2 = ask("how's the pc")
    check("s. 'how's the pc': the one fix first (none), its check-in, CPU and RAM", a2.startswith("The PC looks healthy: nothing to fix.") and re.search(r"checked in [2-9] min ago", a2) and "CPU 23%, RAM 61%" in a2, a2)
    a3 = ask("is everything ok")
    check("s. 'is everything ok' is the System answer too", re.sub(r"checked in \d+ min", "checked in N min", a3) == re.sub(r"checked in \d+ min", "checked in N min", a1), a3[:100])
    check("s. no page errors (all good)", not errs, errs)
    ctx.close()
    # a red health line on the PC: NEEDS YOU + the one thing to do, everywhere (strip, panel, orb, switcher)
    ctx, p, errs, kal = new_page(br)
    now = int(time.time())
    bad = json.loads(json.dumps(LIVE))
    bad["t"] = now - 60
    bad["pc_health"] = {"t": now - 60, "level": "bad", "cpu": 31, "ram": 96, "lines": [
        {"key": "cpu", "label": "CPU", "level": "ok", "text": "CPU 31%"},
        {"key": "ram", "label": "Memory (RAM)", "level": "bad", "text": "RAM 96% in use (3.5 of 3.6 GB): close other apps (browser tabs)"}]}
    ctx.route(re.compile(r"^https://(api\.github\.com|raw\.githubusercontent\.com)/.*live"),
              lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(bad)))
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("document.getElementById('sysv').textContent === 'NEEDS YOU'", timeout=8000)
    p.wait_for_function("document.documentElement.dataset.switcher === 'module' && !!document.getElementById('nxOrb')", timeout=8000)
    r = p.evaluate("""() => ({ t: document.getElementById('syst').textContent, bar: document.getElementById('sysbar').className,
      todo: (document.querySelector('#p-system .stodo') || {}).textContent || '', todoApp: (document.querySelector('#p-system .stodo') || {dataset: {}}).dataset.app,
      pc: document.querySelector('#p-system .srow[data-sys-row="pc"]').className, orb: document.getElementById('nxOrb').className,
      alert: getComputedStyle(document.querySelector('#nxOrb .nx-alert')).display })""")
    check("s. a red PC line: NEEDS YOU, the strip names it, the panel's one thing to do is the line's own fix, the PC line red",
          "bad" in r["bar"] and r["t"] == "PC: Memory (RAM) red" and "THE ONE THING" in r["todo"] and "RAM 96% in use" in r["todo"] and "close other apps" in r["todo"]
          and r["todoApp"] == "zenith" and "bad" in r["pc"], r)
    check("s. the orb carries a red dot while something needs the owner", "lv-bad" in r["orb"] and r["alert"] == "block", r)
    o = p.evaluate("(() => { const b = document.getElementById('nxOrb').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()")
    p.mouse.click(o[0], o[1])
    p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=30000)
    p.wait_for_timeout(450)
    st = p.evaluate("""() => { const s = document.getElementById('nxSys'), b = s.getBoundingClientRect();
      return { hidden: s.hidden, text: s.textContent, cls: s.className, dots: s.querySelectorAll('.nx-sd i').length, h: b.height, w: b.right <= innerWidth,
               cards: [...document.querySelectorAll('#nxTrack .nx-card')].map((c) => (c.querySelector('.nx-nm b') || {}).textContent) }; }""")
    check("s. the switcher: the System strip on top (NEEDS YOU, what, 6 dots, 44 px+), the app cards unchanged",
          not st["hidden"] and st["text"].startswith("NEEDS YOU") and "PC: Memory (RAM) red" in st["text"] and "bad" in st["cls"] and st["dots"] == 6
          and st["h"] >= 44 and st["w"] and st["cards"][:2] == ["JARVIS", "NQ BOT"] and {"CALENDAR", "KALSHI", "ADD"} <= set(st["cards"]), st)
    p.click("#nxSys")
    try:                                                # the switcher closes, then a smooth scroll: waited for, not timed
        p.wait_for_function("(() => { const a = document.getElementById('p-system').getBoundingClientRect(), h = document.getElementById('home').getBoundingClientRect();"
                            " return h.top - 2 <= a.top && a.top < h.bottom - 100; })()", timeout=8000, polling=100)
    except Exception:                                   # noqa: BLE001 - reported below
        pass
    after = p.evaluate("""(() => { const a = document.getElementById('p-system').getBoundingClientRect(), h = document.getElementById('home').getBoundingClientRect();
      return { open: document.getElementById('nxRoot').classList.contains('on'), home: !document.getElementById('home').hidden, top: [Math.round(a.top), Math.round(h.top), Math.round(h.bottom)] }; })()""")
    check("s. a tap on the switcher's strip closes it and shows the System panel on the Jarvis screen",
          not after["open"] and after["home"] and after["top"][1] - 2 <= after["top"][0] < after["top"][2] - 100, after)
    check("s. no page errors (needs you)", not errs, errs)
    ctx.close()


def run_switcher(br, url):
    """Run N (2026-11-01, the orb, switcher.js): "a way to access each thing, so calendar, kalshi, Jarvis, and my nq bot and
    eventually other stuff, make a really cool way to change between stuff". One orb over every mode: tap = a live card per app,
    swipe = the next app, hold = the ring, drag = move it; it steps aside for the keyboard and the sheets."""
    ctx, p, errs, kal = new_page(br)
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("document.documentElement.dataset.switcher === 'module' && !!document.getElementById('nxOrb')", timeout=8000)
    o = p.evaluate("""() => { const b = document.getElementById('nxOrb').getBoundingClientRect(), cs = getComputedStyle(document.getElementById('nxOrb'));
      return { r: [b.left, b.top, b.right, b.bottom], W: innerWidth, H: innerHeight, vis: cs.visibility, op: +cs.opacity, z: +cs.zIndex,
               bar: document.querySelector('.dock, #dock') ? document.querySelector('.dock, #dock').getBoundingClientRect().top : innerHeight,
               nexus: document.documentElement.getAttribute('data-nexus') }; }""")
    r = o["r"]
    check("n. the orb: on screen at the right edge, a 56 px target, above the command bar, over everything (z), Zenith mode's own control hidden",
          r[2] <= o["W"] and r[2] > o["W"] - 20 and r[3] - r[1] >= 44 and r[0] >= 0 and r[1] >= 60 and r[3] <= o["bar"] and o["vis"] == "visible"
          and o["z"] >= 2147483100 and o["nexus"] == "1", o)
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    # tap: the switcher, one live card per app, Jarvis's marked NOW
    p.mouse.click(cx, cy)
    p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=30000)
    p.wait_for_timeout(450)
    cards = p.evaluate("""() => [...document.querySelectorAll('#nxTrack .nx-card')].map((c) => ({ id: c.dataset.nx || (c.dataset.nxAdd ? 'add' : ''),
      name: (c.querySelector('.nx-nm b') || {}).textContent, val: (c.querySelector('.nx-val') || {}).textContent || '', now: c.classList.contains('now'),
      lines: [...c.querySelectorAll('.nx-ln')].map((l) => l.textContent) }))""")
    names = [c["name"] for c in cards]
    check("n. tap: the switcher opens with JARVIS, then every app of apps.js in its door order (ZEUS Trading, Money, Kalshi, More; built from apps.js, so it grows by itself), and + ADD, Jarvis's card marked NOW",
          names == D_NAMES_ORDER + ["ADD"] and cards[0]["now"] and not any(c["now"] for c in cards[1:]), (names, D_NAMES_ORDER, cards[:2]))
    nq = next((c for c in cards if c["id"] == "zenith"), {})
    cal = next((c for c in cards if c["id"] == "planner"), {})
    check("n. the cards are live: NQ BOT shows today's $ across the accounts (+$308) and their status; CALENDAR the next thing or FREE",
          nq.get("val", "").startswith("+$3") and "account" in " ".join(nq.get("lines", [])) and cal.get("val") and cal.get("lines"), (nq, cal))
    geo = p.evaluate("""() => ({ sw: document.documentElement.scrollWidth, W: innerWidth, x: document.querySelector('.nx-x').getBoundingClientRect().width,
      c: [...document.querySelectorAll('#nxTrack .nx-card')].map((c) => c.getBoundingClientRect().height), q: [...document.querySelectorAll('.nx-qb')].map((b) => b.getBoundingClientRect().width) })""")
    check("n. the switcher fits the phone: no sideways scroll, 44 px close and quick buttons, tall cards",
          geo["sw"] <= geo["W"] and geo["x"] >= 44 and min(geo["q"]) >= 44 and min(geo["c"]) >= 260, geo)
    p.click('#nxTrack .nx-card[data-nx="planner"]')
    p.wait_for_timeout(500)
    st = p.evaluate("""() => ({ open: document.getElementById('nxRoot').classList.contains('on'), mode: document.documentElement.dataset.mode,
      cur: (document.querySelector('#modes [aria-current="page"]') || {}).dataset ? document.querySelector('#modes [aria-current="page"]').dataset.app : null,
      orb: getComputedStyle(document.getElementById('nxOrb')).visibility })""")
    check("n. a card opens its app (CALENDAR -> the Planner) and the switcher closes; the orb is back", not st["open"] and st["cur"] == "planner" and st["orb"] == "visible", st)
    # a swipe skips the apps that are not on the site: wait until the shell has heard that of each (a loaded machine probes them late; an
    # unprobed one is tried, says so and stays put)
    p.wait_for_function("(ids) => import('./apps.js').then((A) => ids.every((id) => A.missing(id)))", arg=NOT_ON_SITE, timeout=120000)
    # swipe: the next app (Planner -> Kalshi), then back the other way
    CUR = "(document.querySelector('#modes [aria-current=\"page\"]') || {dataset: {}}).dataset.app"

    def swipe(dx):
        before = p.evaluate(CUR)
        p.mouse.move(cx, cy); p.mouse.down()
        for k in (2, 5):                                # two quick moves: the flick must end within 600 ms of the finger's own clock, even on a loaded machine
            p.mouse.move(cx + dx * k / 5, cy + 2)
        p.mouse.up()
        p.wait_for_timeout(450)
        try:                                            # a loaded machine switches late: wait for the change (more apps = a heavier shell)
            p.wait_for_function(f"{CUR} !== {before!r}", timeout=6000, polling=100)
        except Exception:                               # noqa: BLE001 - reported by the check
            pass
        return p.evaluate("(document.querySelector('#modes [aria-current=\"page\"]') || {dataset: {}}).dataset.app")
    def swipe_to(dx, want):                              # a loaded machine can take a quick flick for a slow drag (the finger's own clock > 320 ms): once more
        got = swipe(dx)
        for _ in range(2):
            if got == want:
                break
            got = swipe(dx)
        return got
    e1 = D_ON[(D_ON.index("planner") - 1) % len(D_ON)]            # swiping right goes back: the app before the Planner in district order that can open (Kalshi); left comes back
    a1 = swipe_to(80, e1)
    a2 = swipe_to(-80, "planner")
    check("n. swipe the orb right: the previous app that can open in district order (the apps not on this site are skipped: Kalshi, before the Planner in Life); left: the next (the Planner)", a1 == e1 and a2 == "planner", (a1, a2, e1))
    # hold: the ring; slide onto Jarvis and let go
    cur_before = p.evaluate(CUR)                        # the app on screen (left out of the ring)
    p.mouse.move(cx, cy); p.mouse.down(); p.wait_for_timeout(520)
    p.wait_for_function("[...document.querySelectorAll('.nx-fb')].length > 0 && [...document.querySelectorAll('.nx-fb')].every((b) => !b.getAnimations || !b.getAnimations().length)", timeout=8000)   # grown out
    ring = p.evaluate("""() => [...document.querySelectorAll('.nx-fan.on .nx-fb')].map((b) => { const r = b.getBoundingClientRect(); return { id: b.dataset.nx || b.dataset.nxDist || (b.dataset.nxSearch ? 'SEARCH' : ''), x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width }; })""")
    home = next((b for b in ring if b["id"] == "home"), None)
    if home:
        p.mouse.move((cx + home["x"]) / 2, (cy + home["y"]) / 2); p.mouse.move(home["x"], home["y"])
    p.mouse.up(); p.wait_for_timeout(450)
    cur = p.evaluate("(document.querySelector('#modes [aria-current=\"page\"]') || {dataset: {}}).dataset.app")
    check("n. hold: the ring fans out Jarvis, the districts that have an app that can open, and Search (44 px+ each, on screen, none on another); slide onto Jarvis and let go: Jarvis",
          sorted(b["id"] for b in ring) == sorted((["home"] if cur_before != "home" else []) + [d for d in D_ALL5 if any(a["dist"] == d and a["id"] in ON_SITE and a["id"] != cur_before for a in _REG["apps"])] + ["SEARCH"]) and all(b["w"] >= 44 and 0 <= b["x"] <= 390 and 0 <= b["y"] <= 844 for b in ring)
          and all((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 >= 44 ** 2 for i, a in enumerate(ring) for b in ring[i + 1:])
          and cur == "home" and p.evaluate("!document.querySelector('.nx-fan.on')"), (ring, cur))
    # drag: move it (kept on this phone)
    p.mouse.move(cx, cy); p.mouse.down()
    for k in range(1, 9):
        p.mouse.move(cx - 4, cy - 18 * k); p.wait_for_timeout(60)
    p.mouse.up(); p.wait_for_timeout(300)
    moved = p.evaluate("""() => ({ pos: JSON.parse(localStorage.getItem('jarvis.orb') || 'null'), top: document.getElementById('nxOrb').getBoundingClientRect().top,
      cur: (document.querySelector('#modes [aria-current="page"]') || {dataset: {}}).dataset.app, open: document.getElementById('nxRoot').classList.contains('on') })""")
    check("n. drag: the orb moves up and stays there (kept on this phone); no app switch, no switcher",
          moved["pos"] and moved["pos"]["side"] == "r" and moved["top"] < r[1] - 80 and moved["cur"] == "home" and not moved["open"], moved)
    # it steps aside for the keyboard and the ⋯ keys: each state waited for (a 60 ms timer brings it back after the keyboard,
    # which a loaded machine can stretch past any fixed wait)
    def orb_is(state):
        try:
            p.wait_for_function(f"getComputedStyle(document.getElementById('nxOrb')).visibility === '{state}'", timeout=5000, polling=50)
        except Exception:                               # noqa: BLE001 - reported below
            pass
        return p.evaluate("getComputedStyle(document.getElementById('nxOrb')).visibility")
    p.focus("#q")
    kb = orb_is("hidden")
    p.evaluate("document.activeElement.blur()")
    kb2 = orb_is("visible")
    p.click("#moreB")
    mk = orb_is("hidden")
    p.click("#moreB")
    mk2 = orb_is("visible")
    check("n. the orb steps aside while typing and while the ⋯ keys are open, then comes back", (kb, kb2, mk, mk2) == ("hidden", "visible", "hidden", "visible"), (kb, kb2, mk, mk2))
    # Zenith mode: the orb stays on top, Zenith mode's own control is hidden; tap -> the switcher over Zenith
    go(p, "zenith"); p.wait_for_timeout(1200)
    z = p.evaluate("""() => { const o = document.getElementById('nxOrb').getBoundingClientRect(), x = o.left + o.width / 2, y = o.top + o.height / 2, h = document.elementFromPoint(x, y);
      const b = document.querySelector('.zm-back'); return { mode: document.documentElement.dataset.mode, top: !!h && !!h.closest('#nxOrb'), zm: b ? getComputedStyle(b).display : 'none', x, y }; }""")
    p.mouse.click(z["x"], z["y"]); p.wait_for_timeout(500)
    zo = p.evaluate("document.getElementById('nxRoot').classList.contains('on') && !!document.querySelector('#nxTrack .nx-card.now[data-nx=\"zenith\"]')")
    p.keyboard.press("Escape"); p.wait_for_timeout(500)
    zc = p.evaluate("!document.getElementById('nxRoot').classList.contains('on')")
    check("n. Zenith mode: the orb stays on top (Zenith mode's own control hidden); tap = the switcher with NQ BOT marked NOW; Escape closes",
          z["mode"] == "zenith" and z["top"] and z["zm"] == "none" and zo and zc, (z, zo, zc))
    p.click('.bar [data-app="home"]', force=True) if p.locator('.bar [data-app="home"]').is_visible() else None
    check("n. no page errors with the orb", not errs, errs)
    ctx.close()
    # a phone's touch: a tap opens the switcher and never lands on the card under the finger (the iPhone's copy click)
    ctx, p, errs, kal = new_page(br, is_mobile=True, has_touch=True)
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("!!document.getElementById('nxOrb')", timeout=8000)
    b = p.evaluate("(() => { const r = document.getElementById('nxOrb').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    p.touchscreen.tap(b[0], b[1]); p.wait_for_timeout(700)
    t = p.evaluate("""() => ({ open: document.getElementById('nxRoot').classList.contains('on'), mode: document.documentElement.dataset.mode })""")
    check("n. touch: a tap on the orb opens the switcher and stays on Jarvis (no copy click on a card)", t["open"] and t["mode"] == "jarvis", t)
    check("n. no page errors with the orb (touch)", not errs, errs)
    ctx.close()
    # reduced motion: no transitions; 375 px wide: no sideways scroll with the switcher open
    ctx, p, errs, kal = new_page(br, width=375, height=667, reduced_motion="reduce")
    p.goto(url + "jarvis/")
    ready(p)
    p.wait_for_function("!!document.getElementById('nxOrb')", timeout=8000)
    p.evaluate("document.getElementById('nxOrb').click()"); p.wait_for_timeout(300)
    rm = p.evaluate("""() => ({ t: getComputedStyle(document.getElementById('nxRoot')).transitionDuration, sw: document.documentElement.scrollWidth, W: innerWidth,
      open: document.getElementById('nxRoot').classList.contains('on'), tf: [...document.querySelectorAll('#nxTrack .nx-card')].map((c) => c.style.transform).filter(Boolean).length })""")
    check("n. reduced motion: no transitions and no card tilt; 375 x 667: no sideways scroll with the switcher open (Enter/Space opens it too)",
          # (no transition = none longer than 10 ms: the kit's olympus/a11y.css sets 0.001s under reduced motion so transitionend still fires)
          rm["open"] and all(float(x.strip().rstrip("s") or 0) <= 0.01 for x in rm["t"].split(",")) and rm["tf"] == 0 and rm["sw"] <= rm["W"], rm)
    ctx.close()


def part_intro_files():
    """o. the OLYMPUS intro in the page: self-contained (its own inline script, no file to fetch), every fail-safe in place."""
    page = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    m = re.search(r'<script id="olympus-intro">(.*?)</script>', page, re.S)
    js = m.group(1) if m else ""
    check("o. the intro script: inline right after its overlay (WebKit runs an async file only after the page's module), small, no fetch / import, Safari 16 safe",
          bool(js) and page.index('id="olyIntro"') < page.index('<script id="olympus-intro">') < page.index('<script type="module">')
          and not os.path.exists(os.path.join(JV, "intro.js")) and len(js.encode()) < 64_000 and "fetch(" not in js and "import " not in js and "XMLHttpRequest" not in js and "(?<" not in js
          and not re.search(r"[\w)\]]\?\.[A-Za-z_$]", js) and "??" not in js, len(js))
    # the entry v3 (night-intro3 2026-11-18): its own file, jarvis/entry.js, DEFERRED right after the overlay: a deferred file runs in document
    # order with the page's module, i.e. once the page is parsed and before Jarvis's start (an async file may run after it; the inline
    # intro script keeps the overlay, its deadlines and the skip, and waits for the entry at most 1.2 s); the shell's size stays put
    ef = os.path.join(JV, "entry.js")
    ejs = open(ef, encoding="utf-8").read() if os.path.exists(ef) else ""
    tag = '<script src="entry.js?v=e2" defer id="olyEntryJs"></script>'
    check("o. the entry (v3): jarvis/entry.js, deferred right after the overlay (before the intro script and Jarvis's module), under 56 KB, no fetch / "
          "import / font file (OLYMPUS is its own outlines, Cinzel OFL), Safari 16 safe, canvases at most 2x, nothing drawn per frame (no "
          "requestAnimationFrame, no WebGL): Web Animations only; the intro script waits for it at most 1.2 s",
          bool(ejs) and tag in page and page.index('id="olyIntro"') < page.index(tag) < page.index('<script id="olympus-intro">') < page.index('<script type="module">')
          and len(ejs.encode()) < 56_000 and "fetch(" not in ejs and "import " not in ejs and "XMLHttpRequest" not in ejs and "(?<" not in ejs
          and not re.search(r"[\w)\]]\?\.[A-Za-z_$]", ejs) and "??" not in ejs and "@font-face" not in ejs and "Math.min(2, W.devicePixelRatio || 1)" in ejs
          and "requestAnimationFrame" not in ejs and re.findall(r"getContext\('([\w-]+)'", ejs) == ["2d"] and "e.animate(frames" in ejs and "SIL Open Font License" in ejs
          and "W.__olyEntry = {" in ejs and "W.__olyEntryReady()" in ejs and "W.__olyEntry.build(w, mode === 'mark' ? 'mark' : 'still'" in js
          and "W.__olyEntryReady = go;" in js and "setTimeout(go, 1200)" in js, len(ejs))
    node = shutil.which("node")
    for name, code in (("intro", js), ("entry", ejs)):
        if not (node and code):
            continue
        import subprocess
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(code)
        r = subprocess.run([node, "--check", fh.name], capture_output=True, text=True)
        os.remove(fh.name)
        check(f"o. the {name} script parses (node --check): a syntax error would leave only its fail-safes", r.returncode == 0, r.stderr[-300:])
    check("o. the overlay is in the page with its own CSS deadline (gone by 0.95 s when intro.js never runs), above the orb, async script",
          '<div class="oly" id="olyIntro" aria-hidden="true">' in page
          and "if (!window.__olyIntro) { var o = document.getElementById('olyIntro'); if (o) o.style.visibility = 'hidden'; } }, 700);" in page
          and "html[data-intro] .oly{display:block;animation:olyGo .25s linear .7s forwards}" in page and "z-index:2147483640" in page
          and "@keyframes olyEnd" in page)
    check("o. the start script picks the version before the first paint: the 2.2 s entry (a new launch, 2026-11-18) / off (the same launch again, 3D Off) / calm (reduce motion) / fade (safe start, unfinished intro); the film only on request; none under automation",
          all(x in page for x in ("im = again ? 'off' : 'mark';", "im = 'calm'", "im = 'off'", "n > 0 || g('jarvis.intro.run')) im = 'fade'",
                                  "sessionStorage.getItem('jarvis.booted')", "20 * 60 * 1000", "(!navigator.webdriver || fo)", "g('jarvis.intro') !== 'off'")))
    check("o. the film: 10 s full / 5 s lite, six phases (heart, storm, rise, eclipse, word, portal), the sound cues, the logo texture, skip in 60 ms",
          all(x in js for x in ("full: 10, lite: 5", "full: 1, lite: 2", "'heart'", "'storm'", "'rise'", "'eclipse'", "'word'", "'portal'", "[8.68, 'portal']", "[2.35, 'pad']",
                                "[5.5, 'pad']", "[7.1, 'rankup']", "[0.28, 'tick']", "intro-logo.webp", "fadeOut(60, 'skipped')", "premultipliedAlpha: true")))
    sfxw = open(os.path.join(JV, "switcher.js"), encoding="utf-8").read()
    check("o. the OLYMPUS sound layer in Jarvis: sfx.js loaded async and in SHELL, ticks on taps (dock / cards / orb), the portal sound on an app open, a tap in the switcher, "
          "quiet while speaking / listening / over the intro, a toggle + volume in the settings sheet",
          all(x in page for x in ('src="../olympus/sfx.js?v=s4" id="olySfxJs" async', "function olyQuiet()", "root.hasAttribute('data-intro') || listening || speaking", "window.OLYMPUS_QUIET = olyQuiet",
                                  "olySfx('portal'); window.jarvisPortal.jump", "{ haptic(); olySfx('tick'); }", "#nxOrb", 'id="setOlySfx"', 'id="setOlyVol"', "k.mute(!$('#setOlySfx').checked)", "k.setVolume("))
          and "'../olympus/sfx.js?v=s4'" in open(os.path.join(JV, "sw.js"), encoding="utf-8").read() and "win.jarvisSfx('tap')" in sfxw)
    logo = os.path.join(JV, "intro-logo.webp")
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    head = open(logo, "rb").read(12) if os.path.exists(logo) else b""
    swr = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    ren = ["../olympus/render.js", "../olympus/materials.js"] + ["../olympus/three-addons/%s.js" % n for n in ("EffectComposer", "RenderPass", "ShaderPass", "MaskPass", "Pass", "CopyShader", "UnrealBloomPass", "LuminosityHighPassShader", "RoomEnvironment")]
    check("o. the render core (render.js, materials.js, the nine three-addons) is in the worker's SHELL and on disk, so the 3D backdrop and core work offline",
          all(f"'{f}'" in swr and os.path.exists(os.path.normpath(os.path.join(JV, f))) for f in ren), [f for f in ren if f"'{f}'" not in swr])
    check("o. the logo texture ships next to the page (WebP, 1024 x 512 = ring | peaks, under 60 KB), is in the worker's SHELL and is preloaded by the start script",
          head[:4] == b"RIFF" and head[8:12] == b"WEBP" and os.path.getsize(logo) < 60_000 and "'./intro-logo.webp'" in sw and "pl.href = 'intro-logo.webp'" in page,
          os.path.getsize(logo) if os.path.exists(logo) else None)
    check("o. the owner's sound kit (window.OLYMPUS_SFX.play) is called only when present and guarded (the intro ships no sound file of its own)",
          all(x in js for x in ("W.OLYMPUS_SFX", "typeof S.play === 'function'", "S.play(name)")) and not os.path.exists(os.path.join(JV, "sfx.js")))
    check("o. the intro's fail-safes: try/catch at start and in every frame, a kill timer, a lost context, a hidden page, the 0.65 s late rule, the unfinished flag",
          all(x in js for x in ("} catch (err) { fail(err); }", "} catch (e) { fail(e); }", "finish('deadline')", "webglcontextlost", "finish('hidden')",
                                "Date.now() - W.__olyT0 > 650", "ls('jarvis.intro.run', '1')", "ls('jarvis.intro.run', null)")))
    check("o. sound only after a gesture (userActivation / a skip tap / a replay), never on a cold open",
          "navigator.userActivation.hasBeenActive" in js and "return gesture ||" in js and "gesture = true;" in js)
    check("o. the start watchdog's note removes the intro; the boot log steps aside for it; the 3D core waits for its end (11 s at most: the film is 10 s)",
          "var o = document.getElementById('olyIntro'); if (o && o.parentNode) o.parentNode.removeChild(o);" in page
          and "window.addEventListener('oly:intro-end', () => bootEnd(), { once: true }); setTimeout(bootEnd, 11000);" in page)


# The intro's own clock, read in the page (this machine may be loaded: wall-clock times from Python would measure the test
# runner, not the phone). It records, in ms since the start script chose the intro (window.__olyT0):
#   ready      Jarvis's start finished (html[data-ready])          gone   the overlay left the page
#   end        the intro said it is over (oly:intro-end)            down   a tap's pointerdown
#   cover1s    at 1 s, whether the overlay still covers the mic (elementFromPoint: a faded, hidden overlay does not count)
INTRO_PROBE = """(() => {
  const P = window.__probe = {};
  const at = () => Math.round(Date.now() - (window.__olyT0 || Date.now()));
  window.addEventListener('oly:intro-end', () => { if (P.end == null) P.end = at(); });
  window.addEventListener('pointerdown', () => { P.down = at(); }, true);
  document.addEventListener('DOMContentLoaded', () => {
    const root = document.documentElement;
    new MutationObserver(() => {
      if (P.ready == null && root.dataset.ready === '1') P.ready = at();
      if (P.gone == null && !document.getElementById('olyIntro')) P.gone = at();
    }).observe(document, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-ready'] });
    setTimeout(() => {
      const b = document.getElementById('mic').getBoundingClientRect();
      const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
      P.cover1s = !!(e && e.closest('#olyIntro')); P.at1s = at();
    }, Math.max(0, 1000 - at()));
  });
})();"""
# a phone that cannot keep up: every frame costs 80 ms of main thread
SLOW_FRAMES = """(() => { const r = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (f) => r((t) => { const e = performance.now() + 80; while (performance.now() < e) { /* busy */ } f(t); }); })();"""
NO_WEBGL = """HTMLCanvasElement.prototype.getContext = (function (g) {
  return function (t) { return /webgl/.test(t) ? null : g.apply(this, arguments); }; })(HTMLCanvasElement.prototype.getContext);"""
# how long the page's main thread was blocked while the intro ran: the long tasks (Long Tasks API) overlapping the intro's own
# window [end - ms, end], end = when its overlay left the page. Its fade runs on timers (0.32 s + 0.48 s), and a timer fires only
# when the main thread is free, so on a slow machine Jarvis's own start (its scripts, data) makes the fade look longer. Measured
# 2026-11-11 (headless Chromium, software GL, 4 cpus, load 3/4; 6 runs each, Chrome CPU throttling): x1 ms 1.79-2.06 s,
# x2 3.35-3.61 s, x4 5.24-5.46 s, the intro's timers late by 0.8-0.96 / 2.1-2.3 / 4.6-4.8 s: the time follows the CPU, not the intro.
# Less the blocked time it stays 0.28-0.44 s at x1, x2 and x4 (a timer's wait can pass inside a long task, so this is a floor of the
# intro's own time; its length itself is pinned by st.len == 0.8).
FADE_PROBE = """(() => {
  const L = window.__lt = [];
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) L.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch (e) { window.__ltOff = true; }
  new MutationObserver((ms, mo) => { if (window.__olyIntro && window.__olyIntro.done && !document.getElementById('olyIntro')) { window.__introEnd = performance.now(); mo.disconnect(); } })
    .observe(document, { childList: true, subtree: true });
})();"""
BLOCKED = """(() => { const st = window.__olyIntro || {}, end = window.__introEnd, a = end - st.ms;
  if (window.__ltOff || !(end > 0)) return null;
  return Math.round((window.__lt || []).reduce((t, [s, d]) => t + Math.max(0, Math.min(end, s + d) - Math.max(a, s)), 0)); })()"""
# every phase a frame drew: read on each animation frame as well as every 25 ms (2026-11-18: a main thread held by Jarvis's start under the
# film leaves a phase one frame long, which a timer alone missed)
PHASE_LOG = """(() => { const L = window.__phases = []; const see = () => { const x = window.__olyIntro && window.__olyIntro.phase; if (x && L[L.length - 1] !== x) L.push(x); };
  setInterval(see, 25); (function f() { see(); requestAnimationFrame(f); })(); })();"""
SFX_KIT = """window.__sfx = []; window.OLYMPUS_SFX = { play(n) { window.__sfx.push(n); } };"""
INTRO_GONE = "!document.getElementById('olyIntro') && !document.documentElement.hasAttribute('data-intro')"
# the entry v3's scene right after it was built (the olympus-entry script): its 2D canvases, the 7 letters' canvases, its animations and
# what they move (only transform / opacity: the compositor runs them; the overlay's own CSS deadline, olyEnd, is not the scene's)
ENTRY_SCENE = """(() => { const sc = document.querySelector('#olyIntro .oly-s'); if (!sc) return { scene: false };
  const A = document.getAnimations().filter((a) => a.effect && a.effect.target && sc.contains(a.effect.target)), props = new Set();
  A.forEach((a) => a.effect.getKeyframes().forEach((k) => Object.keys(k).forEach((x) => { if (!/^(offset|computedOffset|easing|composite)$/.test(x)) props.add(x); })));
  const h = sc.querySelector('.oly-h'), word = h ? [...h.querySelectorAll('canvas.oly-2d')].filter((c) => c.getBoundingClientRect().top > innerHeight * 0.45 && c.getBoundingClientRect().width < 80) : [];
  return { scene: true, canvases: sc.querySelectorAll('canvas.oly-2d').length, letters: word.length, anims: A.length, props: [...props] }; })()"""
# ...read the moment the scene is built (a MutationObserver's callback runs once the building script is done): a loaded test machine
# can reach the page only after the 2.2 s entry is over
ENTRY_WATCH = """(() => { const see = %s;
  new MutationObserver((ms, mo) => { if (window.__entryScene || !document.querySelector('#olyIntro .oly-s .oly-h canvas')) return;
    window.__entryScene = Object.assign(see(), { gl: !!document.querySelector('#olyIntro canvas:not(.oly-2d)') }); mo.disconnect(); })
    .observe(document, { childList: true, subtree: true }); })();""" % ENTRY_SCENE[:-2]
# the hand-off, frame by frame (the scene held by jarvis.intro.hold, its animations set to t): the scene's opacity (1 = Jarvis hidden) and the
# temple + word's (the hero). Never two logos at once: once Jarvis shows (scene < 0.85) the hero is gone (<= 0.1)
HANDOFF = """(() => { const sc = document.querySelector('#olyIntro .oly-s'), h = sc && sc.querySelector('.oly-h'); if (!h) return null;
  const A = document.getAnimations().filter((a) => a.effect && a.effect.target && sc.contains(a.effect.target)), out = [];
  for (let t = 1400; t <= 2300; t += 20) { A.forEach((a) => { a.pause(); a.currentTime = t; }); out.push([t, +(+getComputedStyle(sc).opacity).toFixed(3), +(+getComputedStyle(h).opacity).toFixed(3)]); }
  return out; })()"""
MIC_WHO = """(() => { const b = document.getElementById('mic').getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return [e && (e.id || e.className || e.tagName), Math.round(b.top), Math.round(b.height), innerHeight]; })()"""
MIC_FREE = """(() => { const b = document.getElementById('mic').getBoundingClientRect();
  const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return !!e && !!e.closest('#mic'); })()"""


def intro_page(br, url, force="1", extra="", reduced=None, block=False, scale="0.3", init=(), cut=False, abort=None):
    """A phone (390 x 844) opening Jarvis with the intro allowed ('jarvis.intro.force'; '1' = let the intro choose its version).
    scale: the intro's render scale here (a software-rendered test browser draws ~2 fps at the phone's 1.5x; '' = the phone's)."""
    ctx, p, errs, _ = new_page(br, boot=(force == "1"), **({"reduced_motion": reduced} if reduced else {}))   # force "1" = the intro chooses: a new launch (no 'jarvis.booted' yet)
    sc = f"localStorage.setItem('jarvis.intro.scale', '{scale}');" if scale else ""
    nc = "" if cut else "localStorage.setItem('jarvis.intro.nocut', '1');"
    ctx.add_init_script(f"try {{ localStorage.setItem('jarvis.intro.force', '{force}'); {sc} {nc} {extra} }} catch (e) {{}}")
    # no 3D core here (core-visual.js blocked: the 2D core takes over): three.js in a software renderer on a busy machine stalls
    # the page for seconds right after the reveal, which would time the test machine, not the intro
    ctx.route(re.compile(r".*/core-visual\.js.*"), lambda r: r.abort())
    ctx.add_init_script(INTRO_PROBE)
    if abort:                                     # a file that never arrives
        ctx.route(re.compile(abort), lambda r: r.abort())
    for s in init:
        ctx.add_init_script(s)
    if block:                                     # the intro's script never gets going (as if it threw while being parsed)
        ctx.add_init_script("Object.defineProperty(window, '__olyIntro', { get() { return undefined; }, set() { throw new Error('blocked'); } });")
    p.goto(url + "jarvis/", wait_until="commit")
    return ctx, p, errs


def intro_state(p):
    return p.evaluate("JSON.parse(JSON.stringify({ st: window.__olyIntro || null, pr: window.__probe || {} }))")


def ready_slow(p):
    p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=30000)


def run_intro(br, url):
    """o. the OLYMPUS intro on a phone: plays and ends by itself, skips on a tap, removes itself on any error, cuts short on a
    phone that cannot keep up, never covers Jarvis past 1 s when it fails or never arrives, its versions, its replay; and the
    home extras that came with it (quick actions, today's timeline, the core's satellites)."""
    wait = lambda p, js, ms=40000: p.wait_for_function(js, timeout=ms)

    # 0. a cold open (2026-11-18, owner: the entry "looks made in the 2000s", then "looks wrong / cheap"): the 2.2 s entry v3 (night-intro3: a
    # storm, a lightning strike on the gold temple, OLYMPUS; 2D canvases moved by the Web Animations API), no WebGL, then Jarvis
    ctx, p, errs = intro_page(br, url, init=[SFX_KIT, ENTRY_WATCH])
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    mk = p.evaluate("window.__entryScene || { scene: false }")                               # as built (entry.js, deferred)
    mk_gl = mk.get("gl", True)                                                                # the film's WebGL canvas (the entry's are 2D: .oly-2d)
    ready_slow(p)
    s = intro_state(p)
    check("o. a cold open plays the 2.2 s entry: its scene (night sky, clouds, the bolt, the gold temple, OLYMPUS in 7 letters), no WebGL, it ends by itself "
          "(done) and the mic is tappable, no page errors",
          s["st"]["mode"] == "mark" and s["st"]["q"] == "scene" and s["st"]["len"] == 2.2 and s["st"]["state"] == "done" and not mk_gl and mk["scene"]
          and mk.get("canvases", 0) >= 20 and mk.get("letters") == 7 and s["st"].get("layers") == mk.get("canvases") and s["st"].get("dpr", 9) <= 2 and not s["st"]["err"]
          and p.evaluate(MIC_FREE) and not errs, (s, mk_gl, mk, errs))
    check("o. the entry moves only transform and opacity (the phone's compositor runs it while Jarvis starts underneath), with Web Animations it started itself",
          mk.get("anims", 0) >= 60 and mk.get("anims") == s["st"].get("anims") and set(mk.get("props", ["?"])) <= {"transform", "opacity"}, mk)
    check("o. the mark remembers the launch (the next start within 20 minutes gets the 0.5 s fade), no in-progress flag left",
          bool(p.evaluate("localStorage.getItem('jarvis.intro.day')")) and bool(p.evaluate("localStorage.getItem('jarvis.intro.at')")) and p.evaluate("localStorage.getItem('jarvis.intro.run')") is None)
    p.reload(wait_until="commit")
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. the same launch seen again (an app switch that reloaded the page) gets the 0.5 s fade, never the mark or the film again", s["st"]["mode"] == "off" and s["st"]["state"] == "done", s)
    ctx.close()
    ctx, p, errs = intro_page(br, url, "mark", "localStorage.setItem('jarvis.intro.hold', '1.6');")
    wait(p, "window.__olyIntro && window.__olyIntro.q === 'scene'")
    hc = p.evaluate(HANDOFF) or []
    bad = [x for x in hc if x[1] < 0.85 and x[2] > 0.1]
    check("o. the entry's hand-off: the full title until 1.7 s, then the temple and the word are gone before Jarvis shows through (never two logos), "
          "the clouds clear by 2.22 s (one composited fade, no jump)",
          bool(hc) and all(x[1] == 1 and x[2] == 1 for x in hc if x[0] <= 1700) and not bad and all(x[1] == 0 for x in hc if x[0] >= 2240) and not errs,
          (bad[:3], [x for x in hc if x[0] % 100 == 0], errs[:2]))
    ctx.close()
    # the entry script fails (or is missing): the plain stand-in (the Home Screen temple and OLYMPUS), still, and the same clean end
    ctx, p, errs = intro_page(br, url, "mark", init=["Object.defineProperty(window, '__olyEntry', { get() { return { build() { throw new Error('test: no scene'); } }; }, set() {} });"])
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    plain = p.evaluate("!!document.querySelector('#olyIntro .oly-c svg') && !document.querySelector('#olyIntro canvas')")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. the entry script failing: the plain stand-in (the Home Screen temple and OLYMPUS, still) instead, the error noted, it ends by itself, no page errors",
          plain and s["st"]["mode"] == "mark" and s["st"]["q"] == "still" and "no scene" in s["st"]["err"] and s["st"]["state"] == "done" and p.evaluate(MIC_FREE) and not errs, (plain, s, errs))
    ctx.close()
    ctx, p, errs = intro_page(br, url, "mark", abort=r".*/jarvis/entry\.js.*")                 # entry.js never arrives (offline, no saved copy)
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    ready_slow(p)
    s = intro_state(p)
    check("o. entry.js never arriving: the overlay waits 1.2 s at most, then the plain still, it ends by itself; Jarvis starts, no page errors",
          s["st"]["mode"] == "mark" and s["st"]["q"] == "still" and s["st"]["state"] == "done" and s["st"]["ms"] < BK.limit_ms(4500, "intro no entry") and p.evaluate(MIC_FREE) and not errs, (s, errs))
    ctx.close()

    # 1. the film on request ('jarvis.intro.force' = 'full', as the palette's replay asks for it): the 10 s film in WebGL, Jarvis starting underneath
    ctx, p, errs = intro_page(br, url, "full", init=[PHASE_LOG, SFX_KIT])
    wait(p, "window.__olyIntro && (window.__olyIntro.frames > 3 || window.__olyIntro.done)")
    wait(p, "window.__olyIntro.n > 0 || window.__olyIntro.done")           # the letters' sparks are built once Orbitron is in (1.8 s at most)
    s = intro_state(p)
    check("o. the film on request plays the full 10 s version in WebGL (its canvas, the OLYMPUS particles, the logo texture, frames running)",
          s["st"]["mode"] == "full" and s["st"]["len"] == 10 and s["st"]["state"] == "playing" and s["st"]["n"] > 0 and p.locator("#olyIntro canvas").count() == 1, s)
    check("o. while it plays it covers the screen (the mic under it), the boot log steps aside",
          p.evaluate(MIC_FREE.replace("closest('#mic')", "closest('#olyIntro')")) and p.locator("#bootfx").count() == 0, s)
    wait(p, INTRO_GONE)
    ready_slow(p)
    s = intro_state(p)
    check("o. it reveals Jarvis by itself at ~9.8 s of its clock and removes itself: overlay and data-intro gone, the mic tappable",
          s["st"]["state"] == "done" and 9500 <= s["pr"]["end"] <= 13500 and s["pr"]["gone"] >= s["pr"]["end"] and p.evaluate(MIC_FREE), (s, p.evaluate(MIC_WHO)))
    seen = p.evaluate("window.__phases")
    check("o. the film went through its six phases in order (heart, storm, rise, eclipse, word, portal), the logo texture was used, the sound kit was called for each cue",
          seen == ["heart", "storm", "rise", "eclipse", "word", "portal"] and s["st"]["logo"] is True
          and set(p.evaluate("window.__sfx")) >= {"tick", "pad", "rankup", "portal"} and s["st"]["cues"].count("rumble") == 2,   # the AGORA film: rumbles, not thunder
           (seen, s["st"]["cues"], p.evaluate("window.__sfx")))
    check("o. Jarvis started underneath it, never after it (ready before the intro's end)",
          s["pr"].get("ready") is not None and s["pr"].get("end") is not None and s["pr"]["ready"] < s["pr"]["end"], s["pr"])
    check("o. the day is remembered, the in-progress flag cleared, no page errors",
          bool(p.evaluate("localStorage.getItem('jarvis.intro.day')")) and p.evaluate("localStorage.getItem('jarvis.intro.run')") is None and not errs, errs)
    vr = p.evaluate("['#mic', '#q'].map((s) => document.querySelector(s).getBoundingClientRect().bottom)")
    check("o. after it, the Ask Jarvis field and the dock mic are on the first 390 x 844 screen (AGORA home: the HANDS-FREE row is below the cards)", all(0 < b <= 844 for b in vr), vr)

    # 2. the 1 s film version on request
    ctx.close()
    ctx, p, errs = intro_page(br, url, "short")
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. the 1 s film version (on request) ends by itself", s["st"]["mode"] == "short" and s["st"]["state"] == "done" and s["st"]["ms"] <= BK.limit_ms(4500, "intro short"), s)

    # 3. the replay (command palette: Play the OLYMPUS intro)
    ready_slow(p)
    played = p.evaluate("window.__olyIntroPlay('short')")
    wait(p, "window.__olyIntro && (window.__olyIntro.frames > 1 || window.__olyIntro.done)")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. the replay plays it again and ends the same way (the mic tappable after)",
          played is True and s["st"]["mode"] == "short" and s["st"]["state"] == "done" and p.evaluate(MIC_FREE), s)
    p.evaluate("document.getElementById('fab').click()")
    p.fill("#palQ", "olympus")
    check("o. the command palette lists it", "Play the OLYMPUS intro" in p.locator("#palList").inner_text(), p.locator("#palList").inner_text())
    ctx.close()

    # 4. a tap skips it, and the tap never lands on what is underneath (the core: talk)
    ctx, p, errs = intro_page(br, url, "full")
    wait(p, "window.__olyIntro && window.__olyIntro.frames > 2")
    ready_slow(p)
    p.mouse.click(195, 422)                       # the middle of the 390 x 844 screen (the AGORA home keeps the core lower, below the first screen)
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. a tap skips it: gone within 1 s of the tap (its own clock), the mic tappable",
          s["st"]["state"] == "skipped" and s["pr"]["gone"] - s["pr"]["down"] < BK.limit_ms(1000, "intro skip") and p.evaluate(MIC_FREE), s)
    check("o. the skip tap did not reach the core under it (Jarvis is not listening), no page errors",
          p.evaluate("document.documentElement.dataset.state") != "listening" and not errs, (p.evaluate("document.documentElement.dataset.state"), errs))
    ctx.close()

    # 5. it fails: at its start, in a frame, no WebGL, intro.js never arrives
    ctx, p, errs = intro_page(br, url, "full", "localStorage.setItem('jarvis.intro.fail', 'init');")
    wait(p, INTRO_GONE)
    ready_slow(p)
    wait(p, "window.__probe && window.__probe.cover1s !== undefined")
    s = intro_state(p)
    check("o. an error at its start removes it (state failed): the mic free by 1 s, Jarvis starts, no page error",
          s["st"]["state"] == "failed" and s["pr"].get("cover1s") is False and p.evaluate(MIC_FREE) and not errs, (s, errs))
    check("o. ...and the next start plays it again (the failure clears its in-progress flag)", p.evaluate("localStorage.getItem('jarvis.intro.run')") is None, "")
    ctx.close()
    ctx, p, errs = intro_page(br, url, "full", "localStorage.setItem('jarvis.intro.fail', 'frame');")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. an error in a frame removes it (state failed), no page error", s["st"]["state"] == "failed" and "frame" in s["st"]["err"] and not errs, (s, errs))
    ctx.close()
    ctx, p, errs = intro_page(br, url, "full", init=[NO_WEBGL, FADE_PROBE])
    wait(p, INTRO_GONE)
    s = intro_state(p)
    blk = p.evaluate(BLOCKED)
    s["blocked"] = blk
    # its own time (what it is on the wall clock less the main thread's blocked time) < 1.6 s (0.8 s by design); on the wall clock
    # < 4 s, still well short of the next version up (the 5 s lite film) and of the 11.2 s deadline that ends a film that hangs
    own = s["st"]["ms"] - (blk or 0)
    check("o. no WebGL: the still OLYMPUS word mark fades instead (its own time < 1.6 s, the wall clock < 4 s)",
          s["st"]["mode"] == "fade" and s["st"]["q"] == "still" and s["st"].get("len") == 0.8 and blk is not None
          and own < BK.limit_ms(1600, "intro fade") and s["st"]["ms"] < BK.limit_ms(4000, "intro fade wall", cap=4900), s)
    ctx.close()
    ctx, p, errs = intro_page(br, url, "full", block=True)
    ready_slow(p)
    wait(p, "window.__probe && window.__probe.cover1s !== undefined")
    s = intro_state(p)
    check("o. the intro script never runs: by 1 s its overlay no longer covers Jarvis (the 0.7 s / CSS deadlines), the mic tappable",
          s["st"] is None and s["pr"]["cover1s"] is False and p.evaluate(MIC_FREE), s)
    wait(p, INTRO_GONE, 5000)
    check("o. ...and the page tidies the dead overlay away", True)
    ctx.close()

    # 6. a phone that cannot keep up (every frame 80 ms) at the phone's own scale: a quick cut to the reveal, never a slideshow
    ctx, p, errs = intro_page(br, url, "full", init=[SLOW_FRAMES, FADE_PROBE], cut=True, scale="0.1")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    blk = p.evaluate(BLOCKED)
    s["blocked"] = blk
    # its own time (the wall clock less the main thread's blocked time on a loaded test machine, as the fade check above) < 3 s, and the wall
    # clock < 4.9 s (day-jarvis 2026-11-20: the wall clock alone failed now and then when other browser suites shared the CPU)
    check("o. a phone that cannot keep up: it cuts to the reveal early (before the 3.1 s reveal), never a slideshow",
          s["st"].get("slow") is True and s["st"]["state"] == "done" and blk is not None
          and s["pr"]["end"] - blk < BK.limit_ms(3000, "intro slow phone") and s["pr"]["end"] < BK.limit_ms(4000, "intro slow phone wall", cap=4900), s)
    ctx.close()

    # 7. the versions it picks by itself
    for label, kw, want, length in (("reduce motion: the calm 3.5 s version (the entry's last frame fading in and out, nothing moves)", {"reduced": "reduce"}, "calm", 3.5),
                                     ("3D effects Off: a 0.5 s fade", {"extra": "localStorage.setItem('jfx', 'off');"}, "off", 0.5),
                                     ("after a start that did not finish: the fade, never WebGL", {"extra": "localStorage.setItem('jarvis.unfinished', '1');"}, "fade", 0.8),
                                     ("after an intro that did not finish (the phone closed it): the fade", {"extra": "localStorage.setItem('jarvis.intro.run', '1');"}, "fade", 0.8)):
        ctx, p, errs = intro_page(br, url, **kw)
        wait(p, "window.__olyIntro && window.__olyIntro.mode")
        gl = p.evaluate("!!document.querySelector('#olyIntro canvas:not(.oly-2d)')")
        wait(p, INTRO_GONE)
        s = intro_state(p)
        # reduce motion: the entry's last frame (its scene, still); the quick versions use it only when entry.js is already there, else the
        # plain still at once (never a wait on a reload or a safe start): no animation either way
        check(f"o. {label}", s["st"]["mode"] == want and s["st"]["q"] == "still" and s["st"]["len"] == length and not gl and s["st"]["state"] == "done"
              and not s["st"].get("anims") and (want != "calm" or (s["st"].get("layers") or 0) >= 20), s)
        ctx.close()
    ctx, p, errs = intro_page(br, url, extra="localStorage.setItem('jarvis.intro', 'off');")
    ready_slow(p)
    check("o. switched off (Look → OLYMPUS intro): none", p.evaluate("!document.documentElement.hasAttribute('data-intro') && !(window.__olyIntro && window.__olyIntro.mode)"), intro_state(p))
    ctx.close()

    # 7b. 3D Low gets the same mark (no WebGL on any phone); the 5 s film (same phases at 2x) on request; a new launch an hour after the last
    # gets the mark, a restart within 20 minutes the 0.5 s fade
    ctx, p, errs = intro_page(br, url, extra="localStorage.setItem('jfx', 'low');")
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    check("o. 3D Low / a low-end phone: the same 2.2 s entry (no WebGL)", intro_state(p)["st"]["mode"] == "mark" and intro_state(p)["st"]["state"] == "done", intro_state(p))
    ctx.close()
    ctx, p, errs = intro_page(br, url, "lite", init=[PHASE_LOG])
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. the 5 s film (mode lite, on request), the same six phases, ends at ~4.9 s",
          s["st"]["mode"] == "lite" and s["st"]["q"] == "lite" and s["st"]["len"] == 5 and s["st"]["state"] == "done" and 4400 <= s["pr"]["end"] <= 8500
          and p.evaluate("window.__phases") == ["heart", "storm", "rise", "eclipse", "word", "portal"], s)
    ctx.close()
    day = "(() => { const d = new Date(); return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); })()"
    ctx, p, errs = intro_page(br, url, extra=f"localStorage.setItem('jarvis.intro.day', {day}); localStorage.setItem('jarvis.intro.at', String(Date.now() - 3600e3));")
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    check("o. a new launch an hour after the last one gets the mark", intro_state(p)["st"]["mode"] == "mark", intro_state(p))
    ctx.close()
    ctx, p, errs = intro_page(br, url, extra=f"localStorage.setItem('jarvis.intro.day', {day}); localStorage.setItem('jarvis.intro.at', String(Date.now() - 300e3));")
    wait(p, "window.__olyIntro && window.__olyIntro.mode")
    wait(p, INTRO_GONE)
    check("o. a start 5 minutes after the last one gets the 0.5 s fade (once per launch)", intro_state(p)["st"]["mode"] == "off", intro_state(p))
    ctx.close()
    # the logo file never arrives: the drawn stand-in plays, the film still ends by itself, no errors
    ctx, p, errs = intro_page(br, url, "full", init=[PHASE_LOG], abort=r".*/intro-logo\.webp.*")
    wait(p, "window.__olyIntro && window.__olyIntro.frames > 3")
    wait(p, INTRO_GONE)
    s = intro_state(p)
    check("o. the logo file missing: the drawn ring and peaks stand in, the film still ends by itself (done), no page errors",
          s["st"]["state"] == "done" and s["st"]["logo"] is False and 9500 <= s["pr"]["end"] <= 13500 and not errs, (s, errs))
    ctx.close()

    # 8. under automation with no test asking: no intro (every other check sees Jarvis at once); the home extras
    ctx, p, errs, _ = new_page(br)
    p.goto(url + "planner/")                      # the stand-in Planner saves today (Gym 7:30 AM, Review fills 4:15 PM, a task)
    p.goto(url + "jarvis/")
    ready_slow(p)
    check("o. under automation, unasked: no intro, and nothing waits for one (state off)",
          p.evaluate("!document.documentElement.hasAttribute('data-intro') && window.__olyIntro.state === 'off' && window.__olyIntro.done === true"), intro_state(p))
    qa = p.evaluate("[...document.querySelectorAll('#qa .qa-t')].map((b) => [b.dataset.qa, Math.round(b.getBoundingClientRect().height)])")
    check("o. quick actions: the wide Voice mode tile, then 8 tiles (briefing, system, NQ bot, planner, kalshi, search, hide $, look), each >= 44 px tall",
          [q[0] for q in qa] == ["voice", "brief", "system", "zenith", "planner", "kalshi", "search", "hide", "look"] and all(q[1] >= 44 for q in qa), qa)
    tl = p.evaluate("""(() => { const b = document.getElementById('p-today'); return { rows: b.querySelectorAll('.tl-row').length, now: !!b.querySelector('.tl-now'),
        ev: b.querySelectorAll('.tl-ev').length, task: !!b.querySelector('.tl-row.plan[data-app="planner"]'), next: b.querySelectorAll('.tl-row.next').length,
        head: b.querySelector('.tl-head').textContent }; })()""")
    # the stand-in Planner has Gym at 7:30 AM and Review fills at 4:15 PM today, and one open task (whatever the time of day)
    check("o. today's timeline: the trading day with the Planner's events on the day bar, the now needle, the to-do row, one NEXT row at most",
          tl["rows"] >= 3 and tl["now"] and tl["ev"] == 2 and tl["task"] and tl["next"] <= 1 and tl["head"], tl)
    sats = p.evaluate("[...document.querySelectorAll('#sats .sat')].map((s) => s.className.replace('sat ', ''))")
    dots = p.evaluate("[...document.querySelectorAll('#sysdots i')].map((i) => i.className)")
    check("o. the core's satellites: one per system, each coloured by that system's verdict (as the System strip)", sats == dots and len(sats) >= 4, (sats, dots))
    p.evaluate("document.querySelector('#sats .sat').click()")
    near = "Math.abs(document.getElementById('p-system').getBoundingClientRect().top) < 120"
    try:
        p.wait_for_function(near, timeout=5000)
    except Exception:
        pass
    check("o. a satellite opens the System panel and never starts listening",
          p.evaluate("document.documentElement.dataset.state") != "listening" and p.evaluate(near), p.evaluate("document.getElementById('p-system').getBoundingClientRect().top"))
    p.evaluate("window.scrollTo(0, 0)")
    p.click('#qa [data-qa="hide"]')
    p.wait_for_function("document.documentElement.classList.contains('money-hidden')", timeout=4000)
    p.wait_for_function("document.querySelector('#qa [data-qa=\"hide\"]').textContent.trim() === 'Show $'", timeout=4000)
    check("o. Hide $ hides the balances and its tile turns into Show $", True)
    p.click('#qa [data-qa="planner"]')
    p.wait_for_function("window.__jarvis.active() === 'planner'", timeout=6000)
    check("o. a quick action opens its app (Planner); no page errors", not errs, errs)
    ctx.close()


def main():
    part_a()
    part_intro_files()
    tmp = tempfile.mkdtemp(prefix="le_jarvis_")
    variants = {"A": site(tmp, "A", "none"), "B": site(tmp, "B", "stub"), "C": site(tmp, "C", "asis")}
    for f in PARTS:
        variants["D" + f] = site(tmp, "D" + f.split(".")[0], "stub-but:" + f)
    srv = serve(tmp)
    host = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = launch(pw)
            run_a(br, host + variants["A"])
            run_b(br, host + variants["B"])
            for f in PARTS:
                run_missing(br, host + variants["D" + f], f)
            run_c(br, host + variants["C"])
            run_look(br, host + variants["C"])
            run_switcher(br, host + variants["C"])
            run_olympus(br, host + variants["C"])
            run_system(br, host + variants["C"])
            run_intro(br, host + variants["C"])
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis hub: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
