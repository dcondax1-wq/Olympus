"""THE GATE, the OLYMPUS front door (tools/web_public/gate/, AGORA look, 2026-11-12; v2 2026-11-14 = the command center + nine hubs, docs/OLYMPUS_IA_V2.md). Owner: "When I click the dashboard link there's just a shit ton of buttons ...
make something that's very easy on how to get to things." One page: a "Right now" card (bots on / quiet / old numbers with the age, drawdown left, today's $, the next
trade window; older than 6 h = one "Bring the bots back" button), three Start-here tiles (1 tap), four district doors that open a short sheet (2 taps to any app), a search
by name / purpose / plain words, the last 4 apps opened, the labs under a small Workshop link. Plus olympus/gate-nav.js: "< Gate" and "Go to" on any app.

  a. static: the files, ES5 / no build / no CDN, no markup from data, read-only, storage in try / catch, the AGORA look, the base-path line, the gate-nav tag in the 10 apps
  b. the catalog in node: every app folder and every apps-list row is in it once, every path exists, districts short (most useful <= 6), the search finds plain words
  c. Chromium 390 x 844 (and 375 x 667, reduced motion): fresh / quiet / old / missing / broken home.json, the artifact copy at the site root, the district sheets
     (every app in 2 taps), the search and Enter, Recent, a partial copy marks missing apps, gate-nav on NQ / Kalshi / Cities / Polis, taps >= 44 px, no sideways scroll
    python -X utf8 -m tests.test_gate_page            (--static: parts a and b only)
v2 (2026-11-14): the district doors and their sheets are gone; the home shows Right now (+ Kalshi and my shift, each fact a link), the nine hub tiles
(hub/?h=<id>, each with a live line), the search and Recent. The hub pages themselves: tests/test_hubs.py.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
G = os.path.join(AK.WEB, "gate")
CAT = os.path.join(AK.WEB, "olympus", "gate-catalog.js")
NAV = os.path.join(AK.WEB, "olympus", "gate-nav.js")
TEN = ("nq", "helios", "aegis", "mint", "polis", "symposium", "ergasterion", "cities", "kalshi", "herald")
LABS = {"agora-lab", "env-lab", "fx-lab", "sfx-lab", "people-lab", "polis-lab", "polis-life-lab", "render-lab"}
HUBS = ["today", "bots", "kalshi", "money", "plan", "research", "jarvis", "worlds", "settings"]
NOW = "2026-11-12T15:00:00Z"            # Thursday 10:00 New York: the LIT window is open
NOW_S = int(datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc).timestamp())


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//[^\n]*|\s//\s[^\n]*", "", js)


def catalog():
    exe = shutil.which("node")
    if not exe:
        return None
    r = subprocess.run([exe, "-e", "process.stdout.write(JSON.stringify((() => { const G = require(process.argv[1]); return { apps: G.apps, districts: G.districts, start: G.start,"
                        " q: Object.fromEntries(['money', 'drawdown', 'kalshi', 'journal', 'news', 'discount', 'chatgpt', 'zzzz', '', 'risk stop'].map((q) => [q, G.find(q, 8).map((a) => a.id)])) }; })()))", CAT],
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else {"_error": r.stderr[-500:]}


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    names = ["index.html", "gate.js", "gate.css", "icon.svg"]
    check("a. the files: gate/index.html, gate.js, gate.css, icon.svg, olympus/gate-catalog.js, olympus/gate-nav.js",
          all(os.path.isfile(os.path.join(G, n)) for n in names) and os.path.isfile(CAT) and os.path.isfile(NAV))
    html, js, css, cat, nav = (AK.read(p) for p in (os.path.join(G, "index.html"), os.path.join(G, "gate.js"), os.path.join(G, "gate.css"), CAT, NAV))
    check("a. the page: AGORA theme, viewport-fit=cover, theme-color, colour scheme dark, ONE h1, a polite live status line, no sheet any more (hubs are pages)",
          '<html lang="en" data-theme="agora">' in html and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'name="color-scheme" content="dark"' in html
          and html.count("<h1") == 1 and 'role="status"' in html and 'aria-live="polite"' in html and 'role="dialog"' not in html)
    check("a. one base-path line: gate/ -> '../', the site root (olympus-live.html) -> ''; agora.css + gate.css, then themes, the catalog, hub-status and gate.js load from GATE_BASE, in order (async = false)",
          r"/\/gate\/(index\.html)?$/.test(p) ? '../' : ''" in html and "window.GATE_BASE = b" in html and "b + 'gate/gate.css?v=g3'" in html and "b + 'olympus/agora.css" in html
          and "'olympus/gate-catalog.js?v=g2', 'olympus/hub-status.js?v=h1', 'gate/gate.js?v=g3'" in html and "s.async = false" in html)
    tiles = re.findall(r'class="g-hub[^"]*" data-hub="(\w+)" data-to="hub/index.html\?h=(\w+)"', html)
    check("a. the nine hub tiles are plain links in the page (they work even if gate.js fails), in the owner's order: Today (wide) first ... Settings & Help last",
          [t[0] for t in tiles] == HUBS and all(a == b for a, b in tiles) and 'class="g-hub g-wide" data-hub="today"' in html and html.count('class="g-hline"') == 9)
    check("a. the Workshop link at the bottom opens Settings & Help > Workshop; no lab is linked from the page itself; no Trading / Money / Life district doors",
          'data-to="hub/index.html?h=settings&amp;t=workshop"' in html and not re.search(r"href=\"[^\"]*lab", html) and "g-door" not in html and "data-district" not in html)
    check("a. the order on the page: Right now, the hubs, the search, Recent, the footer",
          html.index('id="now"') < html.index('id="hubsH"') < html.index('id="q"') < html.index('id="recentSec"') < html.index('class="g-foot"'))
    hs = AK.read(os.path.join(AK.WEB, "olympus", "hub-status.js"))
    code = strip_comments(js) + strip_comments(nav) + strip_comments(cat) + strip_comments(hs)
    es6 = [p for p in (r"=>", r"\blet\s", r"\bconst\s", r"`", r"\bclass\s+\w+\s*[{e]", r"\.\.\.\w", r"\.at\(", r"\(\?<[=!]") if re.search(p, code)]
    check("a. ES5 classic scripts (no arrow, let, const, template string, class, spread, .at, lookbehind): Safari 12+ safe, no build step", not es6, es6)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if re.search(p, js + nav + cat + html)]
    check("a. no markup from data: text through textContent / createElementNS only", not bad and "textContent" in js and "createElementNS" in js and "textContent" in nav, bad)
    check("a. read only: no XHR / WebSocket / sendBeacon / POST / cookies / web address; the Gate fetches only home.json (+ the PC's /api/site/live.json when served from the PC, and a HEAD per app link to spot a partial copy)",
          not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|document\.cookie|https?://(?!www\.w3\.org)", js + nav + cat + html)
          and set(re.findall(r"getJSON\(([^)]*)\)", js)) == {"base + 'home.json'", "url", "LIVE_API", "base + 'kalshi.json'", "base + 'money/scoreboard.json'", "base + 'hephaestus/jarvis.json'", "base + 'plutus/jarvis.json'"} and "LIVE_API = '/api/site/live.json'" in js and "method: 'HEAD'" in js and "fetch(" not in nav)
    ls = set(re.findall(r"localStorage\.(\w+)", js + nav))
    check("a. storage: only localStorage 'gate.recent.v1' (and the Gate's 'gate.now.v1'; the Planner's 'planner.today.v1' read only), every call inside try / catch; no sessionStorage / indexedDB",
          ls <= {"getItem", "setItem"} and "'gate.recent.v1'" in js and "'gate.recent.v1'" in nav and "'gate.now.v1'" in js and "LS_PLAN = 'planner.today.v1'" in js
          and "lsSet(LS_PLAN" not in js and not re.search(r"sessionStorage|indexedDB", js + nav)
          and all("try {" in ln for ln in (js + nav).splitlines() if "localStorage." in ln), ls)
    check("a. truth.js is the one source for drawdown and data age (a module tag), with a light copy of its rules only when it does not load; 6 h = old, 20 min = fresh",
          "olympus/truth.js?v=q6a" in js and "T.agesOf(home, t)" in js and "T.accountsOf(home)" in js and "lightAges" in js and "STALE_S = 6 * 3600" in js and "FRESH_S = 20 * 60" in js)
    check("a. the words: 'Drawdown left' with 'of $X max loss', 'Bring the bots back' -> nq/ with its 5 steps (?howto=1), 'Old numbers', 'Not hearing from your PC for'",
          "'Drawdown left'" in js and "' max loss, '" in js and 'data-to="nq/index.html?howto=1"' in html and ">Bring the bots back<" in html and "'Old numbers'" in js and "'Not hearing from your PC for '" in js)
    check("a. the AGORA look: its tokens (night #14110e, gold #c8a24a, serif titles, tabular numbers), no neon / glow / techno font in the Gate or gate-nav",
          "#14110e" in css and "#c8a24a" in css and "--ag-serif" in css and "tabular-nums" in css and not AK.BANNED_LOOK.search(css + js + nav + html.split("-->")[-1]))
    check("a. phone rules in the CSS: taps >= 44 px, safe areas, 176 px clear of Jarvis's corner at the end, reduced motion, LITE, no sideways scroll",
          css.count("min-height: 44px") >= 2 and "safe-area-inset" in css and "176px" in css and "prefers-reduced-motion: reduce" in css and 'data-oly-lite="1"' in css and "overflow-x: hidden" in css)
    check("a. gate-nav: one classic script, nothing when framed (inside Jarvis), the Home link + breadcrumb + 'Go to' (44 px), the catalog from its own folder (apps-list.js as a fallback)",
          "if (framed) return;" in nav and "'Go to'" in nav and "min-height:44px" in nav and "olympus/gate-catalog.js?v=g2" in nav and "olympus/apps-list.js" in nav and "aria-modal" in nav)
    tagged = {}
    for app in TEN:
        h = AK.read(os.path.join(AK.WEB, app, "index.html"))
        tagged[app] = h.count('<script src="../olympus/gate-nav.js?v=g2" defer></script>') == 1 and ("agora-ui.js" not in h or h.index("agora-ui.js") < h.index("gate-nav.js")) and h.index("gate-nav.js") < (h.index("</body>") if app == "kalshi" else h.index("</head>"))
    check("a. the gate-nav tag (once, deferred, in <head> (Kalshi: its body, since 11-12), after agora-ui.js) in the 10 busiest apps (agora-ui.js adds it to every other AGORA app): " + ", ".join(TEN), all(tagged.values()), tagged)


# ------------------------------------------------------------------------------------------------ b. the catalog
def test_catalog():
    C = catalog()
    if C is None:
        check("b. node is available for the catalog checks", True)
        return
    if "_error" in C:
        check("b. the catalog runs in node", False, C["_error"])
        return
    apps = C["apps"]
    ids = [a["id"] for a in apps]
    check("b. no app twice in the catalog", len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1])
    folders = sorted(n for n in os.listdir(AK.WEB) if os.path.isfile(os.path.join(AK.WEB, n, "index.html")) and n not in ("gate", "hub"))
    missing = [f for f in folders if f not in ids]
    check(f"b. every app folder of the site ({len(folders)}) is in the catalog", not missing, missing)
    listed = re.findall(r'\{"id": "([^"]+)"', AK.read(os.path.join(AK.WEB, "olympus", "apps-list.js")))
    lmiss = [i for i in listed if ("today" if i == "zenith" else i) not in ids]
    check(f"b. every row of olympus/apps-list.js ({len(listed)}) is in the catalog (zenith = Today, the dashboard)", not lmiss, lmiss)
    nopath = [a["id"] for a in apps if a["path"] and not os.path.isfile(os.path.join(AK.WEB, a["path"] + ("index.html" if a["path"].endswith("/") else "")))]
    check("b. every path in the catalog exists in the site", not nopath, nopath)
    ws = {a["id"] for a in apps if a["section"] == "workshop"}
    check("b. Settings & Help > Workshop holds the 8 labs (+ the Agora Gallery of 3D shapes), and no lab sits anywhere else",
          ws == LABS | {"gallery"} and all(a["district"] == "settings" for a in apps if a["section"] == "workshop"), ws ^ LABS)
    dist = [d["id"] for d in C["districts"]]
    check("b. the districts ARE the nine hubs (the theme's per-district mix follows them); every app is in exactly one", dist == HUBS and all(a["district"] in dist for a in apps), dist)
    tabs = {}
    for a in apps:
        tabs.setdefault(a["district"] + "/" + a["section"], []).append(a["id"])
    big = {k: len(v) for k, v in tabs.items() if len(v) > 6 and not k.endswith("/workshop")}
    check("b. no tab holds more than 6 apps (the Workshop aside)", not big, big)
    long = [a["id"] for a in apps if len(a["label"]) > 28 or len(a["line"]) > 60 or not a["line"]]
    check("b. every app has a plain label (<= 28 characters) and a one-line purpose (<= 60)", not long, long)
    check("b. start (the fallback 'start here' list) = Bots (nq), the dashboard, Jarvis", C["start"] == ["nq", "today", "jarvis"])
    q = C["q"]
    check("b. the search finds plain words: money -> Mint and Ledger, drawdown -> Aegis, kalshi -> Kalshi first, journal -> the journal first, news -> Pheme / Pythia / Herald",
          {"mint", "ledger"} <= set(q["money"]) and "aegis" in q["drawdown"] and q["kalshi"][0] == "kalshi" and q["journal"][0] == "journal" and {"pheme", "pythia", "herald"} <= set(q["news"]), q)
    check("b. synonyms and AND: discount -> Mercury, chatgpt -> Bridge, 'risk stop' -> Aegis first, nonsense and an empty box find nothing",
          q["discount"][0] == "mercury" and q["chatgpt"][0] == "bridge" and q["risk stop"][:1] == ["aegis"] and q["zzzz"] == [] and q[""] == [], q)


# ------------------------------------------------------------------------------------------------ c. the browser
def home_json(age_s, running=True, room=1420):
    pc_t = NOW_S - age_s
    return json.dumps({"built": datetime.fromtimestamp(NOW_S - 600, timezone.utc).isoformat(), "live": {"pc": {"t": pc_t, "running": running}},
                       "board": {"t": NOW_S - 600, "data_t": pc_t, "running": running,
                                 "lit": {"id": "lit", "name": "Zlarior", "room": room, "mll": 2000, "balance": 49420, "today_pnl": 312,
                                         "windows": [{"open_t": NOW_S - 6 * 3600, "close_t": NOW_S + 5.5 * 3600, "label": "Thu 02:00-15:30 ET"}]},
                                 "atlas": {"id": "atlas", "name": "ATLAS", "room": 900, "mll": 1000, "today_pnl": -40}}})


def serve(over):
    class H(AK.Handler):
        overrides = dict(over)

        def do_GET(self):
            path = self.path.split("?")[0]
            body = self.overrides.get(path)
            if path.endswith(".html") and body:
                body = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def do_HEAD(self):
            path = self.path.split("?")[0]
            if path in self.overrides and self.overrides[path] is None:
                self.send_error(404)
                return
            super().do_HEAD()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=AK.WEB))
    srv.handle_error = lambda request, client_address: None     # a page left mid-download (Enter -> Aegis) is not an error
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def open_gate(p, origin, path="gate/", q=""):
    sep = "&" if "?" in q else ("?" if q else "?")
    p.goto(f"{origin}/{path}{q}{sep if q else '?'}now={NOW}")
    p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000, polling=200)
    p.wait_for_timeout(300)


NOWCARD = "() => ({ state: document.querySelector('#now').dataset.state, badge: document.querySelector('#nowBadge').textContent, line: document.querySelector('#nowLine').textContent," \
          " facts: [...document.querySelectorAll('#nowFacts .g-fact')].map((f) => f.textContent), btn: !document.querySelector('#bringBack').hidden," \
          " href: document.querySelector('#bringBack').href, truth: window.GATE.state.now && window.GATE.state.now.truth })"


def test_page():
    html = AK.read(os.path.join(G, "index.html"))
    plan = json.dumps({"v": 1, "day": "2026-11-12", "events": [{"title": "Work shift", "start": "08:00", "end": "16:00"}, {"title": "Walk", "start": "17:30", "end": "18:15"}],
                       "tasks": [{"title": "a", "done": True}, {"title": "b"}]})
    kal = json.dumps({"v": 3, "t": NOW_S - 1200, "running": True, "balance": 2410.55, "today_pnl": 3.4, "total_pnl": 410.55, "positions": [{}, {}]})
    sb = json.dumps({"totals": {"week": {"net": 120}, "month": {"net": 640}, "all": {"net": 1585}}})
    srv, origin = serve({"/home.json": home_json(300), "/olympus-live.html": html})
    try:
        with AK.browser() as br:
            # fresh numbers at gate/
            ctx, p, errs, seen, off = AK.page(br, origin)
            open_gate(p, origin)
            r = p.evaluate(NOWCARD)
            check("c. fresh report (5 min): 'Bots on', 'The bots are on. Last report 5 minutes ago.', drawdown $1,420 of $2,000 and $900 of $1,000, today +$272, the window open until 15:30 ET; no button; through truth.js",
                  r["state"] == "on" and r["badge"] == "Bots on" and r["line"] == "The bots are on. Last report 5 minutes ago." and r["facts"][0] == "Drawdown left$1,420of $2,000 max loss, Zlarior 50K"
                  and r["facts"][1] == "Drawdown left$900of $1,000 max loss, ATLAS 25K" and r["facts"][2].startswith("Today+$272") and r["facts"][3] == "Trade windowOpen nowuntil 15:30 ET" and not r["btn"] and r["truth"], r)
            go = p.evaluate("() => [...document.querySelectorAll('#nowFacts a.g-fact')].map((a) => a.href.replace(location.origin, ''))")
            check("c. each fact is a tap to the app with the detail: drawdown -> Aegis, today -> NQ, the window -> Kairos",
                  go == ["/aegis/index.html", "/aegis/index.html", "/nq/index.html", "/kairos/index.html"], go)
            tiles = p.evaluate("() => [...document.querySelectorAll('.g-hub')].map((a) => [a.dataset.hub, a.href.replace(location.origin, ''), a.querySelector('.g-hline').textContent, a.querySelector('.g-hcount').textContent])")
            check("c. the nine hub tiles open hub/?h=<hub> (1 tap) with their app counts (15 + 16 + 3 + 11 + 5 + 8 + 4 + 8 + 12 = 82)",
                  [t[0] for t in tiles] == HUBS and all(t[1] == f"/hub/index.html?h={t[0]}" for t in tiles)
                  and sum(int(t[3].split()[0]) for t in tiles) == 82 and tiles[0][3] == "15 apps", tiles)
            lines = {t[0]: t[2] for t in tiles}
            check("c. live hub lines: Bots & Evals '2 evals active, $1,420 / $900 left', Today 'Trade window open until 15:30 ET', Kalshi 'No Kalshi numbers yet' (no feed here)",
                  lines["bots"] == "2 evals active, $1,420 / $900 left" and lines["today"].startswith("Trade window open until 15:30 ET") and lines["kalshi"] == "No Kalshi numbers yet", lines)
            t = AK.taps(p)
            check("c. every tap target >= 44 x 44, no sideways scroll, Jarvis's corner free at the end, no console error, nothing off the origin",
                  not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:4], AK.corner(p), errs[:3], off[:3]))
            p.evaluate("() => window.scrollTo(0, 0)")
            vis = p.evaluate("() => { const r = (s) => document.querySelector(s).getBoundingClientRect().bottom; return [r('#now'), r('.g-hub.g-wide')]; }")
            check("c. at 390 x 844 the Right now card and the wide Today hub tile are on the first screen", vis[0] <= 844 and vis[1] <= 844, vis)
            p.click('#workshopLink')
            p.wait_for_url("**/hub/index.html?h=settings&t=workshop", timeout=30000)
            check("c. the small Workshop link opens Settings & Help on its Workshop tab", "h=settings&t=workshop" in p.url, p.url)
            p.goto(f"{origin}/gate/?now={NOW}")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000)

            # search
            res = {}
            for q in ("money", "drawdown", "kalshi", "journal", "qqqzz"):
                p.fill("#q", q)
                p.wait_for_timeout(120)
                res[q] = p.evaluate("() => [[...document.querySelectorAll('#results a.g-row')].map((a) => a.dataset.app), document.querySelector('#results').textContent]")
            check("c. the search box: money -> Mint + Ledger, drawdown -> Aegis, kalshi -> Kalshi first, journal -> the journal first, nonsense -> a plain 'Nothing found' line",
                  {"mint", "ledger"} <= set(res["money"][0]) and "aegis" in res["drawdown"][0] and res["kalshi"][0][0] == "kalshi" and res["journal"][0][0] == "journal"
                  and not res["qqqzz"][0] and "Nothing found" in res["qqqzz"][1], {k: v[0] for k, v in res.items()})
            check("c. each result says which hub it lives in ('in Bots & Evals')", "in Bots & Evals" in p.evaluate("() => { document.querySelector('#q').value = 'journal'; document.querySelector('#q').dispatchEvent(new Event('input')); return document.querySelector('#results').textContent; }"))
            p.fill("#q", "risk guard")
            p.wait_for_timeout(120)
            p.press("#q", "Enter")
            p.wait_for_url("**/aegis/index.html", timeout=30000)
            check("c. Enter opens the first result (risk guard -> Aegis)", p.url.endswith("/aegis/index.html"), p.url)
            p.goto(f"{origin}/gate/?now={NOW}")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000)
            rec = p.evaluate("() => [...document.querySelectorAll('#recent a')].map((a) => a.dataset.app)")
            check("c. Recent: the app just opened is first (Aegis remembered by the Gate and by gate-nav on Aegis), at most 4", rec[:1] == ["aegis"] and len(rec) <= 4, rec)
            AK.shot(p, "gate-fresh")
            ctx.close()

            # Kalshi, the money scoreboard and my shift (the Planner's summary on this phone)
            s1, o1 = serve({"/home.json": home_json(300), "/kalshi.json": kal, "/money/scoreboard.json": sb})
            ctx, p, errs, seen, off = AK.page(br, o1, storage={"planner.today.v1": plan})
            open_gate(p, o1)
            r = p.evaluate(NOWCARD)
            lines = p.evaluate("() => Object.fromEntries([...document.querySelectorAll('.g-hub')].map((a) => [a.dataset.hub, a.querySelector('.g-hline').textContent]))")
            check("c. with kalshi.json and today's plan: 'Kalshi $2,411 today +$3' and 'My shift Now to 16:00 Work shift' facts (taps to Kalshi and the Planner)",
                  "Kalshi$2,411today +$3" in r["facts"] and "My shiftNow to 16:00Work shift" in r["facts"] and not errs, (r["facts"], errs[:2]))
            check("c. ... and the hub lines: Kalshi 'Balance $2,411 · today +$3 · 2 open bets', My Money 'This month +$640 cash · all time +$1,585', Plan & Day starts 'On shift now until 16:00'",
                  lines["kalshi"] == "Balance $2,411 · today +$3 · 2 open bets" and lines["money"] == "This month +$640 cash · all time +$1,585" and lines["plan"].startswith("On shift now until 16:00"), lines)
            ctx.close()
            s1.shutdown()

            # quiet, old, stopped
            for age, running, state, badge, btn, line in ((2 * 3600, True, "quiet", "Quiet", False, "Last report from your PC 2 hours ago. The bots may still be trading."),
                                                          (3 * 86400 + 3600, True, "stale", "Old numbers", True, "Not hearing from your PC for 3 days 1 hour. These numbers are old."),
                                                          (240, False, "stopped", "Stopped", False, "Your PC reported 4 minutes ago: the bots are stopped there.")):
                s2, o2 = serve({"/home.json": home_json(age, running)})
                ctx, p, errs, seen, off = AK.page(br, o2)
                open_gate(p, o2)
                r = p.evaluate(NOWCARD)
                check(f"c. a report {age // 60} min old (running {running}): '{badge}', '{line[:40]}...', the 'Bring the bots back' button {'shown (-> nq/ 5 steps)' if btn else 'hidden'}",
                      r["state"] == state and r["badge"] == badge and r["line"] == line and r["btn"] == btn and (not btn or r["href"] == f"{o2}/nq/index.html?howto=1") and not errs, (r, errs[:2]))
                if state == "stale":
                    check("c. old numbers are labelled as the last report day, not 'Today'", any(f.startswith("Last report day") for f in r["facts"]), r["facts"])
                    bl = p.evaluate("() => document.querySelector('#hl-bots').textContent")
                    check("c. ... and the Bots & Evals tile says so: 'Old numbers (3 d ago) · 2 evals active ...'", bl.startswith("Old numbers (3 d ago) · 2 evals active"), bl)
                ctx.close()
                s2.shutdown()

            # missing and broken data, the cached numbers
            for name, body in (("missing (404)", None), ("broken", "not json {")):
                s3, o3 = serve({"/home.json": body})
                ctx, p, errs, seen, off = AK.page(br, o3)
                open_gate(p, o3)
                r = p.evaluate(NOWCARD)
                check(f"c. home.json {name}: 'No numbers', a plain line, no button, the trade window still shown from the clock, the hub tiles still work, no console error",
                      r["state"] == "none" and r["badge"] == "No numbers" and r["line"] == "No bot numbers reached this page." and not r["btn"] and r["facts"] == ["Trade windowOpen nowuntil 15:30 ET"]
                      and p.evaluate("() => document.querySelectorAll('.g-hub').length === 9 && !!window.OLYMPUS_GATE") and not errs, (r, errs[:2]))
                ctx.close()
                s3.shutdown()
            s4, o4 = serve({"/home.json": None})
            cache = json.dumps({"saved": NOW_S - 7200, "N": {"pcT": NOW_S - 9000, "pcAge": 1800, "running": True, "accts": [{"key": "lit", "name": "Zlarior 50K", "room": 1500, "mll": 2000}], "today": 50}})
            ctx, p, errs, seen, off = AK.page(br, o4, storage={"gate.now.v1": cache})
            open_gate(p, o4)
            r = p.evaluate(NOWCARD)
            foot = p.evaluate("() => document.querySelector('#nowFoot').textContent")
            check("c. offline-ish: no home.json but this phone saw numbers before -> they are shown, said to be the last ones seen, with their age",
                  r["line"].startswith("No new numbers reached this page") and r["facts"][0].startswith("Drawdown left$1,500") and foot == "Saved on this phone 2 hours ago." and not errs, (r, foot))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, o4)
            p.add_init_script("Storage.prototype.getItem = function () { throw new Error('blocked'); }; Storage.prototype.setItem = function () { throw new Error('blocked'); };")
            open_gate(p, o4)
            check("c. storage blocked (private mode): the page still works, no Recent row, no console error", p.evaluate("() => document.querySelector('#recentSec').hidden && document.querySelectorAll('.g-hub').length === 9") and not errs, errs[:2])
            ctx.close()
            s4.shutdown()

            # the artifact copy at the site root, a partial copy
            s5, o5 = serve({"/home.json": home_json(300), "/olympus-live.html": html, "/odeon/index.html": None})
            ctx, p, errs, seen, off = AK.page(br, o5)
            open_gate(p, o5, path="olympus-live.html")
            r = p.evaluate("() => ({ base: window.GATE_BASE, tiles: [...document.querySelectorAll('.g-hub')].map((a) => a.href), css: !!getComputedStyle(document.querySelector('.g-hub')).borderRadius })")
            check("c. copied to the site root as olympus-live.html: base '' and the hub tiles go to hub/index.html?h=...; styled; no console error",
                  r["base"] == "" and r["tiles"] == [f"{o5}/hub/index.html?h={h}" for h in HUBS] and r["css"] and not errs, (r, errs[:2]))
            p.fill("#q", "replay")
            p.wait_for_function("() => document.querySelector('#results a.g-row[data-app=\"odeon\"]') && /g-gone/.test(document.querySelector('#results a.g-row[data-app=\"odeon\"]').className)", timeout=15000)
            gone = p.evaluate("() => [...document.querySelectorAll('#results a.g-gone')].map((a) => a.dataset.app)")
            check("c. a partial copy (odeon/ missing here): its search row is dimmed and says 'not in this link'; the others stay normal", gone == ["odeon"], gone)
            AK.shot(p, "gate-root")
            ctx.close()
            s5.shutdown()

            # gate-nav on the apps: Home > Hub > app
            for app, sel, hub in (("nq", "header.top .ag-navback", "Bots & Evals"), ("kalshi", "a.olyback", "Kalshi"), ("cities", "a.gn-back", "Worlds"), ("polis", "a.gn-back", "Worlds")):
                ctx, p, errs, seen, off = AK.page(br, origin)
                p.goto(f"{origin}/{app}/")
                p.wait_for_function("window.OLYMPUS_GATE_NAV && window.OLYMPUS_GATE_NAV.placed() && document.querySelector('.gn-crumb') && document.querySelector('.gn-crumb').textContent", timeout=60000)
                p.wait_for_timeout(500)
                r = p.evaluate("(sel) => { const a = document.querySelector(sel), g = document.querySelector('.gn-go'), ra = a && a.getBoundingClientRect(), rg = g && g.getBoundingClientRect(), c = document.querySelector('.gn-crumb');"
                               " return { text: a && a.textContent.trim(), href: a && a.href, go: !!g, top: ra && Math.round(ra.top), goTop: rg && Math.round(rg.top), goR: rg && Math.round(rg.right), h: rg && Math.round(rg.height),"
                               " hub: c && c.textContent, hubHref: c && c.href, cur: (document.querySelector('.gn-cur') || {}).textContent, inNav: !!a.closest('nav.gn-crumbs'),"
                               " rec: JSON.parse(localStorage.getItem('gate.recent.v1') || '[]')[0] }; }", sel)
                check(f"c. {app}: the breadcrumb reads Home > {hub} > its name (Home -> gate/, {hub} -> its hub tab), 'Go to' (44 px) on the right of the top row, remembered for Recent",
                      r["text"] in ("Home", "← Home") and r["href"] == f"{origin}/gate/index.html" and r["inNav"] and r["hub"] == hub and "/hub/index.html?h=" in (r["hubHref"] or "") and r["cur"]
                      and r["go"] and r["h"] >= 44 and r["goTop"] < 140 and r["goR"] <= 390 and r["rec"] == app, r)
                check(f"c. {app} with gate-nav: no sideways scroll, no console error", AK.no_sideways(p) and not errs, errs[:3])
                if app == "nq":
                    p.click(".gn-go")
                    p.wait_for_timeout(400)
                    p.fill("#gnQ", "kalshi")
                    p.wait_for_timeout(200)
                    g = p.evaluate("() => ({ open: !document.querySelector('.gn-sheet').hidden, first: (document.querySelector('.gn-body a.gn-item[data-app]') || {}).href, gate: [...document.querySelectorAll('.gn-body a.gn-gate')].map((a) => a.href) })")
                    check("c. Go to on NQ: the sheet opens, 'kalshi' finds the Kalshi bot first, Home is always one tap", g["open"] and g["first"] == f"{origin}/kalshi/index.html" and g["gate"] == [f"{origin}/gate/index.html"], g)
                    p.fill("#gnQ", "")
                    p.wait_for_timeout(150)
                    dl = p.evaluate("() => ({ hubs: [...document.querySelectorAll('.gn-dist')].map((a) => a.href.replace(location.origin, '')), first: document.querySelector('.gn-body .gn-sec').textContent, here: (document.querySelector('.gn-dist.gn-here') || {}).dataset })")
                    check("c. Go to with an empty box: the nine HUBS first (each opens its hub page), this app's hub marked", dl["hubs"] == [f"/hub/index.html?h={h}" for h in HUBS] and dl["first"] == "Hubs" and dl["here"] == {"hub": "bots"}, dl)
                    t = AK.taps(p)
                    check("c. the Go to sheet: every tap >= 44 px", not t, t[:4])
                    p.keyboard.press("Escape")
                    p.wait_for_timeout(200)
                    check("c. Escape closes the Go to sheet", p.evaluate("() => document.querySelector('.gn-sheet').hidden"))
                    p.evaluate("() => window.scrollTo(0, 1400)")
                    p.wait_for_timeout(500)
                    bar = p.evaluate("() => { const b = document.querySelector('.ag-appbar'); return b ? [b.classList.contains('on'), (b.querySelector('.ag-navback') || {}).textContent, !!b.querySelector('.gn-go')] : null; }")
                    check("c. scrolled down, the compact bar has '< Home' and the Go to icon", bar == [True, "Home", True], bar)
                ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/gate/?d=money&now={NOW}")
            p.wait_for_url("**/hub/index.html?h=money", timeout=30000)
            check("c. an old link gate/?d=money (the v1 Money district) opens the My Money hub", p.url.endswith("/hub/index.html?h=money"), p.url)
            p.goto(f"{origin}/gate/?d=trading&now={NOW}")
            p.wait_for_url("**/hub/index.html?h=bots", timeout=30000)
            check("c. gate/?d=trading opens Bots & Evals", p.url.endswith("/hub/index.html?h=bots"), p.url)
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            open_gate(p, origin)
            anim = p.evaluate("() => document.getAnimations().length")
            check("c. 375 x 667, reduced motion: nothing animates, no sideways scroll, every tap >= 44 px, no console error",
                  anim == 0 and AK.no_sideways(p) and not AK.taps(p) and not errs, (anim, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_catalog()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
