"""The Jarvis hub (tools/web_public/jarvis/, owner 2026-10-31; modes and the old Jarvis look 2026-11-01): one Home Screen app
that opens on the Jarvis screen (the owner's old violet HUD: J.A.R.V.I.S., the core with its HUD ring, STANDBY, the voice
row, HUD panels, the glass command dock), switches Jarvis <-> Zenith in one tap, and opens the Planner, Kalshi and added
dashboards. Runs the real hub page in Chromium on local copies of the site layout (<site>/jarvis/ next to stand-in Zenith /
Planner pages), with the live feed, kalshi.json and the crypto prices served from stubs (nothing leaves the machine), and checks:
  a. the files (fonts + OFL.txt, icons), the service worker (jarvis-v4: every part and font saved on its own, the 3.5 s rule,
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
Runs A (fallbacks), B (stand-ins), C (the folder as is) and the missing-part runs each get their own copy of the site.
    python -X utf8 -m tests.test_jarvis_hub      (temp folder + a local server; nothing else touched; ~1 min)
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
                  "lines": [], "level": "ok"}}
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


def part_a():
    for f in ("index.html", "manifest.webmanifest", "sw.js", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png",
              "data.js", "jarvis.css", "OFL.txt") + FONTS:
        check(f"a. jarvis/{f} exists", os.path.exists(os.path.join(JV, f)))
    m = json.load(open(os.path.join(JV, "manifest.webmanifest"), encoding="utf-8"))
    check("a. manifest: Jarvis, standalone, own scope, black like the old Jarvis, icons j2",
          m["name"] == "Jarvis" and m["short_name"] == "Jarvis" and m["display"] == "standalone" and m["scope"] == "./"
          and m["theme_color"] == "#000000" and all(i["src"].endswith("?v=j2") for i in m["icons"]), m)
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("a. the site build publishes jarvis/ and kalshi/ with every build (every top-level file: fonts and parts too)",
          'for app in ("jarvis", "kalshi"):' in b and 'os.path.join(out, app, name)' in b)
    check("a. kalshi/index.html exists", os.path.exists(os.path.join(KS, "index.html")))
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    check("a. the hub's service worker only handles its own folder", "u.pathname.startsWith(scope.pathname)" in sw)
    # 2026-10-31 (Jarvis would not open on the owner's iPhone): Zenith's worker covers the whole site; it used to delete
    # every other cache (Jarvis's and the Planner's saved copies) and handle their pages, so a dropped connection left Jarvis
    # with nothing to open. Each worker now keeps to its own folder and its own caches, and Jarvis's saved copy answers errors.
    check("a. Jarvis's worker deletes only its own old caches and answers a 404 / no connection from its saved copy",
          "k.startsWith('jarvis-')" in sw and "(await saved(req)) || r" in sw and "Response.error()" in sw)
    # 2026-11-01 ("Jarvis is just a white screen"): an iPhone Home Screen app is white while its page loads or after a failed load
    check("a. opening Jarvis waits on the network at most NAV_WAIT_MS when a saved copy exists; no network + no copy = a dark Retry page",
          "const NAV_WAIT_MS = 3500;" in sw and "Promise.race([net, slow])" in sw and "return copy || offlinePage();" in sw
          and "background:#000" in sw and "location.reload()" in sw)
    check("a. worker v4: data.js, jarvis.css, the fonts and every separate part in SHELL, each saved on its own (a missing part is skipped)",
          "const CACHE = 'jarvis-v4';" in sw and all(f"'./{f}'" in sw for f in ("data.js",) + PARTS + FONTS) and "'./jarvis.css?v=j4'" in sw
          and "SHELL.map((u) => c.add(u).catch(() => null))" in sw)
    check("a. no #dashboard shortcuts in the manifest (Jarvis always opens on its own screen)", "shortcuts" not in m, m.get("shortcuts"))
    zsw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    check("a. Zenith's worker stays out of jarvis/ and planner/ and deletes only its own caches (le-public-*)",
          "const OTHER_APPS = ['jarvis/', 'planner/', 'kalshi/'" in zsw and "if (OTHER_APPS.some(" in zsw
          and "ks.filter((k) => k.startsWith('le-public-') && k !== CACHE)" in zsw and "k !== CACHE && k !== BADGE" not in zsw)
    page = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(JV, "jarvis.css"), encoding="utf-8").read()
    data = open(os.path.join(JV, "data.js"), encoding="utf-8").read()
    check("a. each separate part is loaded on its own with import() and has a fallback in the page",
          all(f"'./{f}', (m) => typeof m." in page for f in PARTS) and "return import(path).then(" in page and "function fallbackBrain(" in page
          and 'id="orb"' in page and "html[data-state=" in css and "D.fallbackApps" in page and "frameView(a)" in page, [f for f in PARTS if f"'./{f}', (m)" not in page])
    check("a. kalshi.json from the Kalshi bot's own repo (kalshi-feed, main): raw first, then the API (security review 2026-11-01)",
          "raw.githubusercontent.com/${OWNER}/kalshi-feed/main/kalshi.json" in data and "api.github.com/repos/${OWNER}/kalshi-feed/contents/kalshi.json?ref=main" in data
          and "ref=kalshi" not in data and data.index("URLS.kalshiRaw") < data.index("URLS.kalshiApi, {"))
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
          "prefers-reduced-motion" in css and ".paused" in css and "visibilitychange" in page and "html,body{background:#000" in page.replace(" ", ""))
    check("a. the old Jarvis look: Reactor by default (a saved 'jtheme' wins), the Eclipse tokens (#000, #a855f7 / #7c3aed / #c084fc, #ece9f2 / #8a8499), the Reactor family and more",
          "g('jtheme') || 'reactor'" in page and all(x in css for x in ("--bg: #000", "--c: #a855f7", "--c2: #7c3aed", "--c3: #c084fc", "--txt: #ece9f2", "--mut: #8a8499", "--c3: #22d3ee",
                                 'data-theme="reactor"', 'data-theme="reactor-stark"', 'data-theme="reactor-ice"', 'data-theme="reactor-emerald"',
                                 'data-theme="obsidian"', 'data-theme="tokyo"')) and "g('jtheme')" in page and "rawSet('jtheme', k)" in page)
    check("a. Orbitron and Rajdhani self-hosted (woff2, font-display: swap, OFL.txt), scanlines, the 48px grid, clipped-corner panels with the tick",
          all(f'url("{f}")' in css for f in FONTS) and css.count("font-display: swap") == 5 and "SIL Open Font License" in open(os.path.join(JV, "OFL.txt"), encoding="utf-8").read()
          and "repeating-linear-gradient(0deg" in css and "background-size: 48px 48px" in css
          and "clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px))" in css)
    keys = re.findall(r"\['(\w+)', ", page[page.index("function moreKeys()"):page.index("function renderMore()")])
    check("a. PC-only features left out quietly: the ⋯ keys have no wake word, double clap, look-at-my-screen or Kill",
          len(keys) == 12 and not set(keys) & {"wake", "clap", "screen", "kill"}, keys)


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(**({"executable_path": exe} if exe else {}))


def feeds(ctx, kal):
    now = int(time.time())
    live = json.loads(json.dumps(LIVE))
    live["t"] = now - 120
    live["board"]["trades"][0].update(entry_t=now - 7200, exit_t=now - 5400)

    def feed(r):
        if "kalshi.json" in r.request.url:
            return (r.fulfill(status=200, content_type="application/json", body=json.dumps(kal["j"])) if kal["on"]
                    else r.fulfill(status=404, content_type="text/plain", body="404: Not Found"))
        return r.fulfill(status=200, content_type="application/json", body=json.dumps(live))
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())       # nothing leaves the machine
    ctx.route("https://api.github.com/**", feed)
    ctx.route("https://raw.githubusercontent.com/**", feed)
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


def new_page(br, width=390, sw=False, boot=False, voice=False, height=844, **kw):
    ctx = br.new_context(viewport={"width": width, "height": height}, device_scale_factor=2, service_workers="allow" if sw else "block", **kw)
    kal = kalshi_feed()
    feeds(ctx, kal)
    if not boot:                                   # the boot screen plays once per launch: skipped where it is not the subject
        ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); } catch (e) {}")
    if voice:
        ctx.add_init_script(FAKE_VOICE)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, p, errs, kal


def ready(p):
    p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=10000)


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
    p.click('.bar [data-app="home"]')
    p.wait_for_timeout(300)
    p.click('.bar [data-app="zenith"]')
    p.wait_for_timeout(300)
    loads = p.evaluate("document.querySelector('#v-zenith iframe').contentWindow.loads")
    check("c. Jarvis screen and back does not reload Zenith (loaded once)", loads == 1, loads)
    check("c. the open-on-its-own button shows for a dashboard", p.locator("#out").is_visible())
    p.click('.bar [data-app="planner"]')
    p.wait_for_timeout(500)
    check("c. Planner opens in its own frame", p.frame_locator("#v-planner iframe").locator("h1").inner_text() == "Planner stub")
    check("c. one dashboard loaded at a time: opening the Planner lets Zenith go (iPhone memory)",
          p.locator("#v-zenith").count() == 0 and p.locator("iframe").count() == 1, p.locator("iframe").count())
    check("c. the start note is gone once Jarvis runs", p.locator("#boot").count() == 0)
    p.click('.bar [data-app="home"]')
    p.wait_for_timeout(300)
    check("c. back to Jarvis", p.locator("#home").is_visible() and not p.locator("#out").is_visible() and p.locator("#dock").is_visible())

    ask = asker(p)
    a1 = ask("How are the bots?")
    check("d. status: the verdict, Zlarior and ATLAS numbers", "RUNNING" in a1 and "Zlarior 50K" in a1 and "$1,106" in a1 and "ATLAS 25K" in a1, a1)
    a2 = ask("how much room do I have")
    check("d. room", "$1,106" in a2 and "$750" in a2, a2)
    a3 = ask("how far to target")
    check("d. target", "$3,726" in a3 and "$1,750" in a3, a3)
    a4 = ask("what's on today")
    check("d. today's plan from the Planner", "Gym" in a4 and "Buy BLITZ 25K" in a4 and "Old" not in a4, a4)
    a5 = ask("is the market open")
    check("d. the market, and when it opens or closes next", "NQ market" in a5 and re.search(r"(Opens|Closes) in \d", a5), a5)
    check("d. status / room / target carry BLITZ next to Zlarior and ATLAS",
          "BLITZ 25K" in a1 and "$612" in a1 and "BLITZ 25K: $612 of room above the floor ($24,500)" in a2 and "BLITZ: $1,388 to the target" in a3,
          (a1, a2, a3))
    a8 = ask("today's p&l")
    check("d. P&L: Zlarior, ATLAS and BLITZ (today and this week)", "Zlarior today +$213" in a8 and "ATLAS today" in a8
          and "BLITZ today +$95, this week +$140" in a8, a8)
    a9 = ask("how's blitz")
    check("d. 'how's blitz' answers BLITZ alone (not 'Opening Zenith')", "BLITZ 25K: today +$95, room $612, $1,388 to target, 2 trades today" in a9
          and "Zlarior" not in a9 and "Opening" not in a9 and p.locator("#home").is_visible(), a9)
    a10 = ask("blitz room")
    check("d. 'blitz room' answers BLITZ's room alone", "BLITZ 25K: $612" in a10 and "Zlarior" not in a10, a10)
    a15 = ask("btc price")
    check("d. the latest answer is the line under the core", "BTC $77,000" in p.text_content("#says"), p.text_content("#says"))
    check("d. the old add-ons answer too: crypto, the verse, the quote", "BTC $77,000 (+1.5% in 24 h)" in a15 and "ETH $2,250" in a15
          and "KJV" in ask("verse of the day") and '"' in ask("quote of the day"), a15)
    a6 = ask("open planner")
    p.wait_for_timeout(800)
    check("d. 'open planner' switches to the Planner", "Opening Planner" in a6 and p.locator("#v-planner").is_visible(), a6)
    p.click('.bar [data-app="home"]')
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
    p.click('.bar [data-app="home"]')
    p.wait_for_timeout(300)
    p.click("#addB")
    p.fill("#addName", "Clipper")
    p.fill("#addUrl", url + "kalshi-stub/")
    p.click('#addF button[type="submit"]')
    p.wait_for_timeout(500)
    check("e. an added dashboard shows in the bar and opens", "Clipper" in p.inner_text("#apps") and p.locator("#v-x-clipper").is_visible())
    fr = p.evaluate("(() => { const f = document.querySelector('#v-x-clipper iframe'); return [f.getAttribute('allow') || '', f.getAttribute('sandbox')]; })()")
    p.click('.bar [data-app="home"]')
    p.click("#addB")
    p.fill("#addName", "Other")
    p.fill("#addUrl", url.replace("127.0.0.1", "localhost") + "kalshi-stub/")      # another origin: another site
    p.click('#addF button[type="submit"]')
    p.wait_for_timeout(500)
    fo = p.evaluate("(() => { const f = document.querySelector('#v-x-other iframe'); return f ? [f.getAttribute('allow'), f.getAttribute('sandbox') || ''] : null; })()")
    check("e. frames: this site's apps get the phone's features (allow, no sandbox); another site's page is sandboxed, never allowed to move Jarvis",
          "microphone" in fr[0] and fr[1] is None and fo and fo[0] is None and "allow-scripts" in fo[1] and "allow-same-origin" in fo[1]
          and "allow-top-navigation" not in fo[1], (fr, fo))
    p.click('.bar [data-app="home"]')
    more(p, "apps")
    p.wait_for_timeout(200)
    p.click('#setApps [data-rm="x-other"]')
    p.click("#setX")
    p.click('.bar [data-app="home"]')
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
    hw = p.evaluate("(() => { const h = document.querySelector('.home-in'); return [h.scrollWidth, h.clientWidth, Math.max(...[...h.children].map((c) => c.getBoundingClientRect().right))]; })()")
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
    p.click('.bar [data-app="zenith"]')
    p.wait_for_timeout(500)
    z = p.evaluate("window.__zen")
    check("h. Zenith mode: zenith-mode.js mounted in its own view, shown, the Planner frame let go",
          z and z["mounts"] == 1 and z["shows"] == [""] and p.locator("#zen").is_visible() and p.locator("#zenStub").is_visible()
          and p.locator("iframe").count() == 0 and p.evaluate("document.documentElement.dataset.zenith") == "module", z)
    check("h. Zenith mode's badge (onState) shows on the ZENITH pill", p.text_content('.bar [data-app="zenith"] .bdg') == "3")
    p.click('.bar [data-app="home"]')
    p.wait_for_timeout(300)
    p.click('.bar [data-app="zenith"]')
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
    p.click('.bar [data-app="kalshi"]')
    p.wait_for_timeout(400)
    z = p.evaluate("window.__zen")
    check("h. another dashboard lets Zenith go (unload: one dashboard at a time)", z["unloads"] == 1 and p.locator("#v-kalshi").is_visible(), z)
    p.click('.bar [data-app="home"]')
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
        p.click('.bar [data-app="zenith"]')
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
    p.click('.bar [data-app="zenith"]')
    p.wait_for_timeout(1200)
    zen_ok = p.locator("#zen").is_visible() or p.locator("#v-zenith").is_visible()
    if p.locator(".zm-back").count() and p.locator(".zm-back").is_visible():
        p.click(".zm-back")                         # Zenith mode covers the bar: its own control goes back
    else:
        p.click('.bar [data-app="home"]')
    p.wait_for_timeout(500)
    check("j. as is: one tap to Zenith mode and back", zen_ok and p.locator("#home").is_visible() and p.evaluate("document.documentElement.dataset.mode") == "jarvis", ds)
    has = p.evaluate("""async () => {
        const reg = await Promise.race([navigator.serviceWorker.ready, new Promise((ok) => setTimeout(() => ok(null), 6000))]);
        if (!reg) return 'no worker';
        for (let i = 0; i < 30; i++) {
          const c = await caches.open('jarvis-v4');
          const got = await Promise.all(['./index.html', './data.js', './jarvis.css?v=j4', './orbitron.woff2', './rajdhani-500.woff2'].map((u) => c.match(u)));
          if (got.every(Boolean)) return 'ok';
          await new Promise((ok) => setTimeout(ok, 200));
        }
        return 'missing';
    }""")
    check("j. the worker installs and saves the page, data.js, jarvis.css and the fonts (a part not on the site is skipped)", has == "ok", has)
    p.reload()
    ready(p)
    p.wait_for_timeout(300)
    # QA 2026-11-01: on a slow network only the page waits (3.5 s), then its files come from the saved copy at once; it used to
    # wait 3.5 s more for each file (css, data.js ...): usable after ~10 s instead of ~3.6 s
    SLOW["s"] = 6.0
    t0 = time.time()
    p.reload(wait_until="commit")
    try:
        p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=15000)
        took = time.time() - t0
    except Exception:                                   # noqa: BLE001 - reported below
        took = 99.0
    SLOW["s"] = 0.0
    check("j. slow network (every answer 6 s): the saved copy is up and usable in ~3.5 s (the page's own files never wait again)", took < 5.5, round(took, 2))
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
          off_ok is True and lum < 70 and "$1,106" in p.text_content("#cards") and p.evaluate("document.fonts.check('700 16px Orbitron')"), (off_ok, lum))
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
            for (const q of ['.vrow', '#hint']) {
              document.querySelector(q).scrollIntoView({ block: 'end' });
              const r = R(q);
              if (r[1] < home[1] - 0.5 || r[3] > home[3] + 0.5) out.push(q + ' not reachable');
              for (const k of Object.keys(stack)) if (hit(r, stack[k])) out.push(q + ' under ' + k);
            }
            document.getElementById('home').scrollTop = 0;
            return out;
        })()""")
        check(f"k. {sz}: the dock, the next chip and the search button never cover the hint or the mic row (both reachable, nothing over them)", not ov, ov)
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
    p.goto(url + "planner/")
    p.goto(url + "jarvis/")
    ready(p)
    booting = p.evaluate("!!document.getElementById('bootfx') && getComputedStyle(document.getElementById('bootfx')).display !== 'none'")
    t0 = time.time()
    p.wait_for_function("!document.getElementById('bootfx')", timeout=3000)
    took = time.time() - t0
    check("l. the boot screen: J.A.R.V.I.S. and its boot log on the first open, gone within 1.2 s", booting and took < 1.3, (booting, took))
    p.wait_for_timeout(600)
    look = p.evaluate("""(async () => {
        await document.fonts.ready;
        const cs = getComputedStyle(document.documentElement), t = document.querySelector('.title');
        return { c: cs.getPropertyValue('--c').trim(), bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme,
                 orb: document.fonts.check('700 16px Orbitron'), raj: document.fonts.check('500 16px Rajdhani'),
                 tfont: getComputedStyle(t).fontFamily, title: t.textContent, state: document.getElementById('state').textContent,
                 hudBot: document.getElementById('hudBot').textContent, hudTop: document.getElementById('hudTop').textContent,
                 says: document.getElementById('says').textContent, ticks: document.querySelectorAll('#ticks .tk.on').length,
                 bars: document.querySelectorAll('#vbars i').length, fx: document.documentElement.dataset.fx };
    })()""")
    check("l. Reactor by default (the violet reactor of the app icon: violet #a95cff, cyan #22d3ee); Orbitron and Rajdhani loaded (self-hosted); the title in Orbitron",
          look["c"] == "#a95cff" and look["theme"] == "reactor" and look["orb"] and look["raj"] and look["tfont"].lstrip('"').startswith("Orbitron")
          and look["title"] == "J.A.R.V.I.S.", look)
    check("l. the core's HUD ring: the clock and STANDBY along the bottom, the market / bots / Kalshi along the top, Zlarior's room as ticks; 32 voice bars",
          re.match(r"\d\d:\d\d:\d\d · STANDBY$", look["hudBot"]) and "NQ" in look["hudTop"] and "KALSHI" in look["hudTop"] and look["ticks"] == 20
          and look["state"] == "STANDBY" and look["bars"] == 32 and "Tap the core or type below to speak with me." in look["says"] and look["fx"] == "high", look)
    if p.evaluate("document.documentElement.dataset.brain") == "module":
        check("l. brain.js: the old Jarvis's line under the core until the first question ('Good day. Tap the core ...')", look["says"].startswith("Good day. Tap the core"), look["says"])
    if p.evaluate("document.documentElement.dataset.core") == "module":
        c3 = p.evaluate("[getComputedStyle(document.querySelector('.hudring')).display, getComputedStyle(document.querySelector('.globe')).display, !!document.querySelector('#coreSlot canvas'), window.__jarvis.core()]")
        check("l. core-visual.js: the 3D reactor in the centre (its own HUD ring, globe and dial: the 2D ones step aside)",
              c3[0] == "none" and c3[1] == "none" and c3[2] and c3[3] and c3[3].get("design") == "reactor", c3)
    head = p.evaluate("[document.getElementById('kpct').textContent, document.getElementById('npnl').textContent, document.getElementById('nsub').textContent]")
    check("l. KALSHI TODAY says NOT CONNECTED while kalshi.json is missing; NQ BOTS TODAY adds the three accounts (+$308)",
          head[0] == "NOT CONNECTED" and head[1] == "+$308" and head[2].startswith("3 accounts"), head)
    panels = p.text_content("#panels")
    check("l. the systems panels: the market (NQ last 21,234.50, next open / close), the activity feed (a Zlarior trade), add-ons (verse, quote, BTC / ETH / SOL), system core (bot loop)",
          "21,234.50" in panels and re.search(r"(Opens|Closes) in \d", panels) and "Zlarior · LONG 3 · target" in panels and "+$413" in panels
          and "Verse of the day" in panels and "KJV" in panels and "Quote of the day" in panels and "$77,000" in panels and "$94.52" in panels
          and "+1.5%" in panels and "−1.6%" in panels and "Bot loop" in panels and "PC LIVE" in panels, panels[:600])
    nxt = p.text_content("#next")
    check("l. the next-event chip from the Planner (or 'Nothing scheduled today')", "Gym" in nxt or "Review fills" in nxt or "Nothing" in nxt or "TO-DO" in nxt, nxt)
    p.click("#moreB")
    keys = p.evaluate("[...document.querySelectorAll('#more [data-key]')].map((b) => b.dataset.key + ':' + b.textContent)")
    check("l. the ⋯ menu: Core, Full screen, Theme, AI key, Hold-to-talk, 3D, Tilt (off), Alerts, Sound, Hide $, Briefing, Apps",
          [k.split(":")[0] for k in keys] == ["core", "full", "theme", "aikey", "hold", "fx", "tilt", "alerts", "sound", "hide", "brief", "apps"]
          and "tilt:Tilt off" in keys and "fx:3D: high" in keys, keys)
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
    check("l. Theme opens the Look sheet: 12 themes (Reactor first, Eclipse ... Custom), effects levels, the core designs, sounds, calm motion (off), tilt",
          p.locator("#look").is_visible() and p.locator("#themes .th").count() == 12 and p.locator('#fxSeg [aria-pressed="true"]').inner_text() == "High"
          and p.locator("#coreSeg button").count() == 2 and p.get_attribute("#themes .th >> nth=0", "data-theme-k") == "reactor"
          and not p.locator("#setCalm").is_checked())
    p.click("#setCalm")
    calm = p.evaluate("localStorage.getItem('jarvis.calm')")
    p.click("#setCalm")
    check("l. Calm motion: kept on this phone (the 3D core then follows the iPhone's reduce-motion switch)", calm == "true"
          and p.evaluate("localStorage.getItem('jarvis.calm')") == "false", calm)
    p.click('#themes [data-theme-k="reactor-stark"]')
    st = p.evaluate("[getComputedStyle(document.documentElement).getPropertyValue('--c').trim(), localStorage.getItem('jtheme')]")
    check("l. Reactor Stark: gold accents, saved as 'jtheme'", st == ["#ffbe3d", "reactor-stark"], st)
    p.click("#lookX")
    p.reload()
    ready(p)
    th = p.evaluate("[document.documentElement.dataset.theme, getComputedStyle(document.documentElement).getPropertyValue('--c').trim(), !!document.getElementById('bootfx')]")
    check("l. reopened: the theme is there from the first paint; no boot screen again in the same launch", th == ["reactor-stark", "#ffbe3d", False], th)
    p.evaluate("window.__jarvis.setTheme('reactor')")
    # voice: tap the big mic, Jarvis hears, answers out loud in the phone's voice (1.06 / 1.1), the state word follows
    p.evaluate("window.__utter = 'is the market open'; window.__states = []; window.__said = []")
    p.click("#bigmic")
    p.wait_for_function("window.__said.length > 0", timeout=6000)
    p.wait_for_function("document.documentElement.dataset.state === 'idle'", timeout=4000)
    said, states = p.evaluate("[window.__said, window.__states]")
    check("l. voice: tap the mic -> LISTENING -> THINKING -> SPEAKING -> STANDBY; the answer is read at rate 1.06, pitch 1.1",
          "market" in said[0][0].lower() and abs(said[0][1] - 1.06) < 1e-6 and abs(said[0][2] - 1.1) < 1e-6
          and [s for s in states if s in ("listening", "thinking", "speaking", "idle")][:4] == ["listening", "thinking", "speaking", "idle"], (said, states))
    p.click("#hf")
    p.wait_for_function("window.__srStarts >= 3", timeout=8000)
    p.click("#hf")
    p.wait_for_timeout(300)
    hf = p.evaluate("[window.__srStarts, document.getElementById('hf').getAttribute('aria-pressed'), window.__said.length]")
    check("l. hands-free: keeps listening after each answer while on; off stops it", hf[0] >= 3 and hf[1] == "false" and hf[2] >= 2, hf)
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
    p.click('.bar [data-app="home"]')
    check("l. no page errors in the look run", not errs, errs)
    ctx.close()
    # the OS 'reduce motion' setting: the effects start low (nothing spins), no boot screen
    ctx, p, errs, _ = new_page(br, boot=True, reduced_motion="reduce")
    p.goto(url + "jarvis/")
    ready(p)
    rm = p.evaluate("[document.documentElement.dataset.fx, getComputedStyle(document.querySelector('.orb .r1')).animationName, !!document.getElementById('bootfx')]")
    check("l. reduced motion: effects low, the rings still, no boot screen", rm == ["low", "none", False], rm)
    check("l. no page errors with reduced motion", not errs, errs)
    ctx.close()


def main():
    part_a()
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
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis hub: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
