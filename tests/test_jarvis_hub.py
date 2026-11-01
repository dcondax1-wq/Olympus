"""The Jarvis hub (tools/web_public/jarvis/, owner 2026-10-31; modes 2026-11-01): one Home Screen app that opens on the Jarvis
screen, switches Jarvis <-> Zenith in one tap, and opens the Planner, Kalshi and added dashboards.
Runs the real hub page in Chromium on local copies of the site layout (<site>/jarvis/ next to stand-in Zenith / Planner
pages), with the live feed served from a stub, and checks:
  a. the files, the service worker (jarvis-v4: every part saved on its own) and the build step that publishes jarvis/
  b. the Jarvis screen: greeting, the market line, a card per project (Zenith with the bots' numbers from the live feed,
     the Planner with today's plan read from its own saved data, Kalshi waiting for the PC until kalshi.json is published)
  c. switching: the mode switch / bar opens each dashboard, a dashboard is never reloaded by switching away and back,
     an old #planner address starts on the Jarvis screen
  d. Jarvis answers (the built-in brain): the bots' status / room / target from the live feed, today's plan, the market, "open X"
  e. Kalshi: waiting for the PC, then the PC's numbers; an added dashboard shows in the bar
  f. phone width, no page errors
  g. data.js: getFacts() and the Planner's 'planner.today.v1' summary
  h. the separate parts through their contracts (stand-in brain.js, core-visual.js, apps.js, zenith-mode.js): Zenith mode
     mounts once, shows / hides, its own exit returns to Jarvis; the brain's answers, cards and smart-mode settings
  i. each part missing on its own: the built-in fallback takes over, no page errors
  j. the folder as it is (whatever parts are merged), with its service worker: starts, answers, both modes, opens offline
  k. phone widths 375 / 390 / 430: no sideways scroll, the bar fits, never a white screen (the screenshot's main colour)
  l. the look: the HUD centerpiece, the status ring, the readouts
Runs A (fallbacks), B (stand-ins), C (the folder as is) each get their own copy of the site and their own browser context.
    python -X utf8 -m tests.test_jarvis_hub      (temp folder + a local server; nothing else touched)
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
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


LIVE = {"v": 1, "kind": "le-live", "t": 0,
        "pc_verdict": {"code": "RUNNING", "label": "RUNNING: bot trading", "level": "good", "reason": "heartbeat fresh"},
        "board": {"running": True,
                  "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "balance": 49273.8, "floor": 48168.2,
                          "room": 1105.6, "to_target": 3726.2, "today_pnl": 212.5, "week_pnl": -224.5, "status": "open"},
                  "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "balance": 24750.4, "floor": 24000.0,
                            "room": 750.4, "to_target": 1749.6, "today_pnl": 0.0, "status": "open"},
                  # BLITZ on account C (engine/live_publish.blitz_block / live_board.blitz_now card)
                  "blitz": {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "badge": "SIM", "balance": 25112.3, "floor": 24500.0,
                            "room": 612.3, "to_target": 1387.7, "today_pnl": 95.25, "week_pnl": 140.0, "status": "open", "off": False,
                            "trades_today": 2, "waiting": "Waiting for the 14:30 check."}}}

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
  { id: 'zenith', name: 'Zenith', sub: 'NQ bots', url: '../', icon: '../icons/icon-192.png' },
  { id: 'planner', name: 'Planner', sub: 'Calendar', url: '../planner/', icon: '../planner/icon-192.png' },
  { id: 'kalshi', name: 'Kalshi', sub: 'Kalshi bot', url: '../kalshi/', glyph: 'K' },
  { id: 'stubapp', name: 'StubApp', url: '../kalshi-stub/', statusUrl: '../kalshi-stub/status.json' },
];
export function listApps() { return L.slice(); }
export function addApp({ name, url }) { const a = { id: 'x-' + name.toLowerCase(), name, url }; L.push(a); return a; }
export function removeApp(id) { const i = L.findIndex((a) => a.id === id); if (i >= 0) L.splice(i, 1); }
export async function appStatus(app) { return app.id === 'stubapp' ? { status: 'Stub OK', level: 'ok', kv: [['Users', '42']] } : null; }
""",
    "zenith-mode.js": """
export function mountZenithMode({ host, onExit }) {
  const z = window.__zen = { mounts: ((window.__zen && window.__zen.mounts) || 0) + 1, shows: [], hides: 0 };
  host.innerHTML = '<div id="zenStub"><h1>Zenith mode stub</h1><button id="zenExit" type="button">Back to Jarvis</button></div>';
  host.querySelector('#zenExit').onclick = () => onExit();
  let on = false;
  return { show(route) { on = true; z.shows.push(route || ''); }, hide() { on = false; z.hides++; }, isActive() { return on; } };
}
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


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def serve(root):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def part_a():
    for f in ("index.html", "manifest.webmanifest", "sw.js", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png",
              "data.js", "jarvis.css"):
        check(f"a. jarvis/{f} exists", os.path.exists(os.path.join(JV, f)))
    m = json.load(open(os.path.join(JV, "manifest.webmanifest")))
    check("a. manifest: Jarvis, standalone, own scope", m["name"] == "Jarvis" and m["short_name"] == "Jarvis" and m["display"] == "standalone" and m["scope"] == "./", m)
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("a. the site build publishes jarvis/ and kalshi/ with every build", 'for app in ("jarvis", "kalshi"):' in b and 'os.path.join(out, app, name)' in b)
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
          and "background:#0b0b0d" in sw and "location.reload()" in sw)
    check("a. worker v4: data.js, jarvis.css and every separate part in SHELL, each saved on its own (a missing part is skipped)",
          "const CACHE = 'jarvis-v4';" in sw and all(f"'./{f}'" in sw for f in ("data.js",) + PARTS) and "'./jarvis.css?v=j4'" in sw
          and "SHELL.map((u) => c.add(u).catch(() => null))" in sw)
    m2 = json.load(open(os.path.join(JV, "manifest.webmanifest"), encoding="utf-8"))
    check("a. no #dashboard shortcuts in the manifest (Jarvis always opens on its own screen)", "shortcuts" not in m2, m2.get("shortcuts"))
    zsw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    check("a. Zenith's worker stays out of jarvis/ and planner/ and deletes only its own caches (le-public-*)",
          "const OTHER_APPS = ['jarvis/', 'planner/', 'kalshi/'];" in zsw and "if (OTHER_APPS.some(" in zsw
          and "ks.filter((k) => k.startsWith('le-public-') && k !== CACHE)" in zsw and "k !== CACHE && k !== BADGE" not in zsw)
    page = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(JV, "jarvis.css"), encoding="utf-8").read()
    data = open(os.path.join(JV, "data.js"), encoding="utf-8").read()
    check("a. each separate part is loaded on its own with import() and has a fallback in the page",
          all(f"'./{f}', (m) => typeof m." in page for f in PARTS) and "return import(path).then(" in page and "function fallbackBrain(" in page
          and "const orbCore" in page and "D.fallbackApps" in page and "frameView(a)" in page, [f for f in PARTS if f"'./{f}', (m)" not in page])
    check("a. data.js exports getFacts, the refreshes and the change event", all(x in data for x in (
        "export function getFacts()", "export function refreshLive()", "export function refreshKalshi()", "export function onChange(",
        "'planner.today.v1'", "export const fallbackApps")))
    # iPhone (Safari 16): no external fonts / CDNs, no syntax newer than Safari 16, reduced motion respected, dark first paint
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)       # comments may name what is not used
    src = page + css + data
    check("a. offline-safe and Safari 16 safe: no external fonts or scripts, no regex lookbehind, no CSS nesting / @property",
          "fonts.googleapis" not in src and "<script src=\"http" not in page and "@import" not in css and "(?<=" not in src and "(?<!" not in src
          and "@property" not in css and "&:" not in css and "& " not in css.replace("&amp;", ""), "")
    check("a. reduced motion respected, animations pause while hidden, dark before the stylesheet loads",
          "prefers-reduced-motion" in css and ".paused" in css and "visibilitychange" in page and "html,body{background:#0b0b0d" in page.replace(" ", ""))


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(**({"executable_path": exe} if exe else {}))


def feeds(ctx, kal):
    live = dict(LIVE, t=int(time.time()) - 120)

    def feed(r):
        if "kalshi.json" in r.request.url:
            return (r.fulfill(status=200, content_type="application/json", body=json.dumps(kal["j"])) if kal["on"]
                    else r.fulfill(status=404, content_type="text/plain", body="404: Not Found"))
        return r.fulfill(status=200, content_type="application/json", body=json.dumps(live))
    ctx.route("https://api.github.com/**", feed)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.anthropic.com/**", lambda r: r.fulfill(status=500, body="no calls out in tests"))


def kalshi_feed():
    from engine import kalshi_publish as kp
    return {"on": False, "j": kp.clean({**kp.SAMPLE, "t": int(time.time()) - 60})}


def new_page(br, width=390, sw=False):
    ctx = br.new_context(viewport={"width": width, "height": 844}, device_scale_factor=2, service_workers="allow" if sw else "block")
    kal = kalshi_feed()
    feeds(ctx, kal)
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
    cards = p.inner_text("#cards")
    check("b. Zenith card: the bots' status and numbers from the live feed",
          "RUNNING: bot trading" in cards and "$1,106" in cards and "+$213" in cards and "$750" in cards, cards[:400])
    check("b. Zenith card: BLITZ next to Zlarior and ATLAS (plan, badge, today, room, to target)",
          "BLITZ · MFFU Builder 25K · SIM" in cards and "$612" in cards and "+$95" in cards and "$1,388" in cards, cards[:600])
    check("b. Planner card: today's events and open tasks from its saved data",
          "Gym" in cards and "7:30 AM" in cards and "Review fills" in cards and "1" in cards and "Buy BLITZ 25K" in cards, cards[:400])
    check("b. Kalshi card: waiting for the PC while kalshi.json is not published", "Waiting for your PC" in cards and p.locator("#link-kalshi").count() == 0, cards[-300:])
    bar = p.inner_text(".bar")
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
    check("c. back to Jarvis", p.locator("#home").is_visible() and not p.locator("#out").is_visible())

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
    check("d. the market", "NQ market" in a5, a5)
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
    a6 = ask("open planner")
    p.wait_for_timeout(800)
    check("d. 'open planner' switches to the Planner", "Opening Planner" in a6 and p.locator("#v-planner").is_visible(), a6)
    p.click('.bar [data-app="home"]')
    a7 = ask("how's kalshi")
    check("d. Kalshi not published yet: says it is not connected (the bot runs only on the PC)", "not connected yet" in a7 and "PC" in a7, a7)
    a7b = ask("open kalshi")
    p.wait_for_timeout(900)
    kf = p.frame_locator("#v-kalshi iframe")
    check("e. 'open kalshi' opens the Kalshi page; not published yet: it shows the one step for the PC",
          "Opening Kalshi" in a7b and "Connect your Kalshi bot" in kf.locator("#body").text_content()
          and "docs/KALSHI_PUBLISH.md" in kf.locator("#step").inner_text(), a7b)
    # e. the PC publishes kalshi.json
    kal["on"] = True
    p.reload()
    ready(p)
    p.wait_for_timeout(700)
    cards2 = p.inner_text("#cards")
    check("e. Kalshi published: the card shows running, the mode, balance, today and open positions",
          "Running · PAPER" in cards2 and "$512.34" in cards2 and "+$18.50" in cards2, cards2[-320:])
    a11 = ask("how's kalshi")
    check("e. 'how's kalshi' answers from the PC's numbers (balance, today, week, positions)",
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
    p.click('.bar [data-app="home"]')
    p.click("#gear")
    p.wait_for_timeout(200)
    check("e. settings: voice on/off, smart mode (off without the new brain: says so) and the added dashboard to remove",
          p.locator("#settings").is_visible() and p.locator("#setVoice").is_checked() and p.locator("#setSmart").is_disabled()
          and "built-in rules" in p.inner_text("#smartState") and "Clipper" in p.inner_text("#setApps"), p.inner_text("#settings")[:300])
    p.click('#setApps [data-rm="x-clipper"]')
    p.wait_for_timeout(200)
    check("e. removing it from settings takes it off the bar", "Clipper" not in p.inner_text("#apps"))
    p.click("#setX")

    # g. data.js: the facts, and the Planner's own summary of today ('planner.today.v1') when it is today's
    f = p.evaluate("(() => { const f = window.__jarvis.facts(); return { keys: Object.keys(f).sort(), open: f.market.open, mtext: f.market.text, room: f.live && f.live.lit && f.live.lit.room,"
                   " ks: f.kalshiState, kb: f.kalshi && f.kalshi.balance, ev: f.planner && f.planner.ev.map((e) => e.title), apps: f.apps.map((a) => a.id) }; })()")
    check("g. getFacts(): now, market, live, kalshi + state, planner, apps",
          all(k in f["keys"] for k in ("now", "market", "live", "kalshi", "kalshiState", "planner", "apps")) and f["room"] == 1105.6
          and f["ks"] == "ok" and f["kb"] == 512.34 and "Gym" in (f["ev"] or []) and f["apps"][:3] == ["zenith", "planner", "kalshi"]
          and "NQ market" in f["mtext"], f)
    today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    p.evaluate("(d) => localStorage.setItem('planner.today.v1', JSON.stringify({ day: d, events: [{ title: 'Dentist', start: '15:00' }, { title: 'Holiday', allDay: true }],"
               " tasks: [{ title: 'Call broker', done: false }, { title: 'Done one', done: true }] }))", today)
    a13 = ask("what's on today")
    check("g. the Planner's 'planner.today.v1' summary (today's) is read first", "All day: Holiday" in a13 and "3:00 PM: Dentist" in a13
          and "Call broker" in a13 and "Done one" not in a13 and "Gym" not in a13, a13)
    p.evaluate("localStorage.setItem('planner.today.v1', JSON.stringify({ day: '2001-01-01', events: [{ title: 'Stale', start: '09:00' }], tasks: [] }))")
    a14 = ask("what's on today")
    check("g. a stale 'planner.today.v1' (another day) is ignored", "Stale" not in a14 and "Gym" in a14, a14)

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
    check("h. core-visual.js: mounted in the centerpiece (the CSS orb steps aside)", p.locator("#stubCore").count() == 1 and p.locator("#orb").is_hidden(),
          p.locator("#stubCore").count())
    check("h. apps.js: its list feeds the bar and the cards; appStatus() fills an added app's card",
          "StubApp" in p.inner_text("#apps") and "Stub OK" in p.inner_text("#cards") and "42" in p.inner_text("#cards"), p.inner_text("#cards")[-200:])
    check("h. brain.js: its suggestions", "Stub suggestion" in p.inner_text("#sugs"), p.inner_text("#sugs"))
    ask = asker(p)
    a = ask("anything")
    check("h. brain.js answers with getFacts() (market, live, apps) and its cards show", a.startswith("STUB NQ market") and "room 1105.6" in a
          and "zenith,planner,kalshi,stubapp" in a and "Stub card" in p.inner_text("#talk"), a)
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
    p.click('.bar [data-app="home"]')
    p.wait_for_timeout(300)
    p.click('.bar [data-app="zenith"]')
    p.wait_for_timeout(300)
    z = p.evaluate("window.__zen")
    check("h. one tap Jarvis <-> Zenith: hidden on Jarvis, shown again, mounted only once", z["mounts"] == 1 and z["hides"] >= 1 and len(z["shows"]) == 2
          and p.locator("#home").is_hidden(), z)
    p.click("#zenExit")
    p.wait_for_timeout(300)
    check("h. Zenith mode's own exit (onExit) returns to Jarvis", p.locator("#home").is_visible() and p.locator("#zen").is_hidden()
          and p.evaluate("document.documentElement.dataset.mode") == "jarvis")
    ask("zenith route")
    p.wait_for_timeout(800)
    z = p.evaluate("window.__zen")
    check("h. the brain can open Zenith at a route (open('zenith', 'perf'))", z["shows"][-1] == "perf" and p.locator("#zen").is_visible(), z)
    p.click('.bar [data-app="home"]')
    p.click("#gear")
    p.wait_for_timeout(200)
    check("h. settings: smart mode on offer with the new brain", not p.locator("#setSmart").is_disabled() and "No key saved" in p.inner_text("#smartState"))
    p.check("#setSmart")
    p.fill("#setKey", "test-key-not-real")
    p.fill("#setModel", "test-model")
    p.click('#setF button[type="submit"]')
    p.wait_for_timeout(200)
    sm = p.evaluate("window.__stubBrain.smart")
    ls = p.evaluate("JSON.stringify(Object.keys(localStorage).filter((k) => k.startsWith('jarvis')).map((k) => localStorage.getItem(k)))")
    check("h. smart mode: the key goes to the brain's setSmart, the shell keeps no copy",
          sm == {"on": True, "key": "test-key-not-real", "model": "test-model"} and "test-key-not-real" not in ls and p.input_value("#setKey") == "", (sm, ls[:200]))
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
        ok = ok and all(x in p.inner_text(".bar") for x in ("Planner", "Kalshi")) and "StubApp" not in p.inner_text(".bar")
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
    p.wait_for_timeout(900)
    zen_ok = p.locator("#zen").is_visible() or p.locator("#v-zenith").is_visible()
    p.click('.bar [data-app="home"]')
    p.wait_for_timeout(300)
    check("j. as is: one tap to Zenith mode and back", zen_ok and p.locator("#home").is_visible(), ds)
    has = p.evaluate("""async () => {
        const reg = await Promise.race([navigator.serviceWorker.ready, new Promise((ok) => setTimeout(() => ok(null), 6000))]);
        if (!reg) return 'no worker';
        for (let i = 0; i < 30; i++) {
          const c = await caches.open('jarvis-v4');
          const got = await Promise.all(['./index.html', './data.js', './jarvis.css?v=j4'].map((u) => c.match(u)));
          if (got.every(Boolean)) return 'ok';
          await new Promise((ok) => setTimeout(ok, 200));
        }
        return 'missing';
    }""")
    check("j. the worker installs and saves the page, data.js and jarvis.css (a part not on the site is skipped)", has == "ok", has)
    p.reload()
    ready(p)
    p.wait_for_timeout(300)
    ctx.set_offline(True)
    p.reload()
    try:
        ready(p)
        off_ok = p.locator("#home").is_visible()
    except Exception as e:                              # noqa: BLE001 - reported below
        off_ok = str(e)[:120]
    lum, white = dominant(p.screenshot())
    check("j. offline: Jarvis opens from its saved copy (page, data.js, styles), dark, cards from the last numbers",
          off_ok is True and lum < 70 and "$1,106" in p.inner_text("#cards"), (off_ok, lum))
    ctx.set_offline(False)
    check("j. no page errors as is", not errs, errs)
    ctx.close()
    # k. phone widths
    for wdt in (375, 390, 430):
        ctx, p, errs, _ = new_page(br, width=wdt)
        p.goto(url + "planner/")
        p.goto(url + "jarvis/")
        ready(p)
        p.wait_for_timeout(900)
        w = p.evaluate("""(() => {
            const de = document.documentElement, bar = document.querySelector('.bar-in').getBoundingClientRect();
            const over = [...document.querySelectorAll('#home *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > innerWidth + 0.5; })
              .filter((e) => !e.closest('.apps')).map((e) => e.tagName + '.' + e.className).slice(0, 4);
            return { sw: de.scrollWidth, cw: de.clientWidth, bar: bar.right, modes: document.querySelector('#modes').getBoundingClientRect().right, over };
        })()""")
        lum, white = dominant(p.screenshot())
        check(f"k. {wdt} px: no sideways scroll, nothing past the right edge, the mode switch fully on screen",
              w["sw"] <= w["cw"] and not w["over"] and w["modes"] <= wdt and w["bar"] <= wdt + 0.5, w)
        check(f"k. {wdt} px: never a white screen (main colour dark, {white:.1%} near-white)", lum < 70 and white < 0.06, (lum, white))
        if wdt == 390:
            p.screenshot(path=os.path.join(tempfile.gettempdir(), "jarvis_390.png")) if os.environ.get("JARVIS_SHOTS") else None
        check(f"k. {wdt} px: no page errors", not errs, errs)
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
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis hub: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
