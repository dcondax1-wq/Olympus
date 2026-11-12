"""THE GATE, the OLYMPUS front door (tools/web_public/gate/, AGORA look, 2026-11-12). Owner: "When I click the dashboard link there's just a shit ton of buttons ...
make something that's very easy on how to get to things." One page: a "Right now" card (bots on / quiet / old numbers with the age, drawdown left, today's $, the next
trade window; older than 6 h = one "Bring the bots back" button), three Start-here tiles (1 tap), four district doors that open a short sheet (2 taps to any app), a search
by name / purpose / plain words, the last 4 apps opened, the labs under a small Workshop link. Plus olympus/gate-nav.js: "< Gate" and "Go to" on any app.

  a. static: the files, ES5 / no build / no CDN, no markup from data, read-only, storage in try / catch, the AGORA look, the base-path line, the gate-nav tag in the 10 apps
  b. the catalog in node: every app folder and every apps-list row is in it once, every path exists, districts short (most useful <= 6), the search finds plain words
  c. Chromium 390 x 844 (and 375 x 667, reduced motion): fresh / quiet / old / missing / broken home.json, the artifact copy at the site root, the district sheets
     (every app in 2 taps), the search and Enter, Recent, a partial copy marks missing apps, gate-nav on NQ / Kalshi / Cities / Polis, taps >= 44 px, no sideways scroll
    python -X utf8 -m tests.test_gate_page            (--static: parts a and b only)
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
    check("a. the page: AGORA theme, viewport-fit=cover, theme-color, colour scheme dark, ONE h1, a polite live status line, a dialog sheet with a label",
          '<html lang="en" data-theme="agora">' in html and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'name="color-scheme" content="dark"' in html
          and html.count("<h1") == 1 and 'role="status"' in html and 'aria-live="polite"' in html and 'role="dialog"' in html and 'aria-modal="true"' in html)
    check("a. one base-path line: gate/ -> '../', the site root (olympus-live.html) -> ''; gate.css, the catalog and gate.js load from GATE_BASE, in order (async = false)",
          r"/\/gate\/(index\.html)?$/.test(p) ? '../' : ''" in html and "window.GATE_BASE = b" in html and "b + 'gate/gate.css" in html
          and "'olympus/gate-catalog.js?v=g1', 'gate/gate.js?v=g1'" in html and "s.async = false" in html)
    check("a. the three Start-here tiles are plain links in the page (they work even if gate.js fails): Today = the dashboard, Bots = nq/, Jarvis = jarvis/",
          all(f'data-to="{p}"' in html for p in ("index.html", "nq/index.html", "jarvis/index.html")) and html.count('class="g-tile"') == 3)
    check("a. four district doors (Trading, Money, Life, Worlds) and the Workshop link at the bottom; no lab is linked from the page itself",
          [m for m in re.findall(r'class="g-door" data-district="(\w+)"', html)] == ["trading", "money", "life", "worlds"] and 'data-district="workshop"' in html
          and not re.search(r"href=\"[^\"]*lab", html))
    check("a. the order on the page: Right now, Start here, Recent, the districts, the search, the footer",
          html.index('id="now"') < html.index('id="startH"') < html.index('id="recentSec"') < html.index('id="distH"') < html.index('id="q"') < html.index('class="g-foot"'))
    code = strip_comments(js) + strip_comments(nav) + strip_comments(cat)
    es6 = [p for p in (r"=>", r"\blet\s", r"\bconst\s", r"`", r"\bclass\s+\w+\s*[{e]", r"\.\.\.\w", r"\.at\(", r"\(\?<[=!]") if re.search(p, code)]
    check("a. ES5 classic scripts (no arrow, let, const, template string, class, spread, .at, lookbehind): Safari 12+ safe, no build step", not es6, es6)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if re.search(p, js + nav + cat + html)]
    check("a. no markup from data: text through textContent / createElementNS only", not bad and "textContent" in js and "createElementNS" in js and "textContent" in nav, bad)
    check("a. read only: no XHR / WebSocket / sendBeacon / POST / cookies / web address; the Gate fetches only home.json (and a HEAD per app link to spot a partial copy)",
          not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|document\.cookie|https?://(?!www\.w3\.org)", js + nav + cat + html)
          and set(re.findall(r"getJSON\(([^)]*)\)", js)) == {"base + 'home.json'", "url"} and "method: 'HEAD'" in js and "fetch(" not in nav)
    ls = set(re.findall(r"localStorage\.(\w+)", js + nav))
    check("a. storage: only localStorage 'gate.recent.v1' (and the Gate's 'gate.now.v1'), every call inside try / catch; no sessionStorage / indexedDB",
          ls <= {"getItem", "setItem"} and "'gate.recent.v1'" in js and "'gate.recent.v1'" in nav and "'gate.now.v1'" in js and not re.search(r"sessionStorage|indexedDB", js + nav)
          and all("try {" in ln for ln in (js + nav).splitlines() if "localStorage." in ln), ls)
    check("a. truth.js is the one source for drawdown and data age (a module tag), with a light copy of its rules only when it does not load; 6 h = old, 20 min = fresh",
          "olympus/truth.js?v=q6a" in js and "T.agesOf(home, t)" in js and "T.accountsOf(home)" in js and "lightAges" in js and "STALE_S = 6 * 3600" in js and "FRESH_S = 20 * 60" in js)
    check("a. the words: 'Drawdown left' with 'of $X max loss', 'Bring the bots back' -> nq/ with its 5 steps (?howto=1), 'Old numbers', 'Not hearing from your PC for'",
          "'Drawdown left'" in js and "' max loss, '" in js and 'data-to="nq/index.html?howto=1"' in html and ">Bring the bots back<" in html and "'Old numbers'" in js and "'Not hearing from your PC for '" in js)
    check("a. the AGORA look: its tokens (night #14110e, gold #c8a24a, serif titles, tabular numbers), no neon / glow / techno font in the Gate or gate-nav",
          "#14110e" in css and "#c8a24a" in css and "--ag-serif" in css and "tabular-nums" in css and not AK.BANNED_LOOK.search(css + js + nav + html.split("-->")[-1]))
    check("a. phone rules in the CSS: taps >= 44 px, safe areas, 176 px clear of Jarvis's corner at the end, reduced motion, LITE, no sideways scroll",
          css.count("min-height: 44px") >= 2 and "safe-area-inset" in css and "176px" in css and "prefers-reduced-motion: reduce" in css and 'data-oly-lite="1"' in css and "overflow-x: hidden" in css)
    check("a. gate-nav: one classic script, nothing when framed (inside Jarvis), the Gate link + 'Go to' (44 px), the catalog from its own folder (apps-list.js as a fallback)",
          "if (framed) return;" in nav and "'Go to'" in nav and "min-height:44px" in nav and "olympus/gate-catalog.js?v=g1" in nav and "olympus/apps-list.js" in nav and "aria-modal" in nav)
    tagged = {}
    for app in TEN:
        h = AK.read(os.path.join(AK.WEB, app, "index.html"))
        tagged[app] = h.count('<script src="../olympus/gate-nav.js?v=g1" defer></script>') == 1 and ("agora-ui.js" not in h or h.index("agora-ui.js") < h.index("gate-nav.js")) and h.index("gate-nav.js") < h.index("</head>")
    check("a. the gate-nav tag (once, deferred, in <head>, after agora-ui.js) in the 10 busiest apps: " + ", ".join(TEN), all(tagged.values()), tagged)


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
    folders = sorted(n for n in os.listdir(AK.WEB) if os.path.isfile(os.path.join(AK.WEB, n, "index.html")) and n != "gate")
    missing = [f for f in folders if f not in ids]
    check(f"b. every app folder of the site ({len(folders)}) is in the catalog", not missing, missing)
    listed = re.findall(r'\{"id": "([^"]+)"', AK.read(os.path.join(AK.WEB, "olympus", "apps-list.js")))
    lmiss = [i for i in listed if ("today" if i == "zenith" else i) not in ids]
    check(f"b. every row of olympus/apps-list.js ({len(listed)}) is in the catalog (zenith = Today, the dashboard)", not lmiss, lmiss)
    nopath = [a["id"] for a in apps if a["path"] and not os.path.isfile(os.path.join(AK.WEB, a["path"] + ("index.html" if a["path"].endswith("/") else "")))]
    check("b. every path in the catalog exists in the site", not nopath, nopath)
    ws = {a["id"] for a in apps if a["district"] == "workshop"}
    check("b. the Workshop holds exactly the 8 labs (agora, env, fx, sfx, people, polis, polis-life, render), and no lab sits anywhere else", ws == LABS, ws ^ LABS)
    dist = {d["id"] for d in C["districts"]}
    check("b. districts: Trading, Money, Life, Worlds (+ the Workshop); every app is in one of them or Start here", dist == {"trading", "money", "life", "worlds", "workshop"}
          and all(a["district"] in dist | {"start"} for a in apps))
    tops = {d: sum(1 for a in apps if a["district"] == d and a["section"] == "top") for d in ("trading", "money", "life", "worlds")}
    check("b. each district opens with at most 6 'most useful' apps", all(1 <= n <= 6 for n in tops.values()), tops)
    long = [a["id"] for a in apps if len(a["label"]) > 28 or len(a["line"]) > 60 or not a["line"]]
    check("b. every app has a plain label (<= 28 characters) and a one-line purpose (<= 60)", not long, long)
    check("b. Start here = Today, Bots (nq), Jarvis", C["start"] == ["today", "nq", "jarvis"])
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
            tiles = p.evaluate("() => [...document.querySelectorAll('.g-tile')].map((a) => a.href)")
            check("c. the three Start-here tiles go to the dashboard, nq/ and jarvis/ (1 tap) from gate/", tiles == [f"{origin}/index.html", f"{origin}/nq/index.html", f"{origin}/jarvis/index.html"], tiles)
            t = AK.taps(p)
            check("c. every tap target >= 44 x 44, no sideways scroll, Jarvis's corner free at the end, no console error, nothing off the origin",
                  not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:4], AK.corner(p), errs[:3], off[:3]))
            vis = p.evaluate("() => { const r = (s) => document.querySelector(s).getBoundingClientRect().bottom; return [r('#now'), r('.g-tiles')]; }")
            check("c. at 390 x 844 the Right now card and the three Start-here tiles are on the first screen", vis[1] <= 844, vis)

            # the district sheets: every app 2 taps away
            seen_ids, first = {}, {}
            for did in ("trading", "money", "life", "worlds"):
                p.click(f'.g-door[data-district="{did}"]')
                p.wait_for_timeout(450)
                info = p.evaluate("() => ({ open: !document.querySelector('#sheet').hidden, title: document.querySelector('#sheetH').textContent, secs: [...document.querySelectorAll('#sheetBody .g-sec')].map((h) => h.textContent),"
                                  " ids: [...document.querySelectorAll('#sheetBody a.g-row')].map((a) => a.dataset.app), hrefs: [...document.querySelectorAll('#sheetBody a.g-row')].map((a) => a.href),"
                                  " top: document.querySelectorAll('#sheetBody .g-list.g-top a').length, focus: document.activeElement.id })")
                first[did] = info
                for i in info["ids"]:
                    seen_ids[i] = seen_ids.get(i, 0) + 1
                bad = [h for h in info["hrefs"] if not os.path.isfile(os.path.join(AK.WEB, h.replace(origin + "/", "")))]
                check(f"c. the {did} door opens its sheet ('{info['title']}', {len(info['ids'])} apps, 'Most useful'/'Most visited' first with {info['top']} apps), every link is a real page, focus on Close",
                      info["open"] and info["title"].lower() == did and info["secs"][0] in ("Most useful", "Most visited") and 1 <= info["top"] <= 6 and not bad and info["focus"] == "sheetClose", (info["secs"], bad[:3]))
                t = AK.taps(p)
                check(f"c. the {did} sheet: taps >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
                p.keyboard.press("Escape")
                p.wait_for_timeout(200)
                closed = p.evaluate(f"() => [document.querySelector('#sheet').hidden, document.activeElement.dataset.district]")
                check(f"c. Escape closes the {did} sheet and focus returns to its door", closed == [True, did], closed)
            C = catalog() or {"apps": []}
            want = {a["id"] for a in C.get("apps", []) if a["district"] in ("trading", "money", "life", "worlds")}
            check(f"c. every app ({len(want)}) is in exactly one district sheet: Gate -> door -> app = 2 taps (Today and Jarvis are tiles: 1 tap)",
                  set(seen_ids) == want and all(v == 1 for v in seen_ids.values()) and first["trading"]["ids"][0] == "nq", (set(seen_ids) ^ want, [k for k, v in seen_ids.items() if v > 1]))
            p.click("#workshopBtn")
            p.wait_for_timeout(400)
            ws = p.evaluate("() => [...document.querySelectorAll('#sheetBody a.g-row')].map((a) => a.dataset.app)")
            check("c. the small Workshop link opens the 8 labs (and the labs appear nowhere else on the page)", set(ws) == LABS and p.evaluate("() => [...document.querySelectorAll('main a')].filter((a) => /lab/.test(a.href)).length") == 0, ws)
            p.click("#scrim", position={"x": 20, "y": 10})
            p.wait_for_timeout(200)
            check("c. a tap on the dimmed page closes the sheet", p.evaluate("() => document.querySelector('#sheet').hidden"))

            # search
            res = {}
            for q in ("money", "drawdown", "kalshi", "journal", "qqqzz"):
                p.fill("#q", q)
                p.wait_for_timeout(120)
                res[q] = p.evaluate("() => [[...document.querySelectorAll('#results a.g-row')].map((a) => a.dataset.app), document.querySelector('#results').textContent]")
            check("c. the search box: money -> Mint + Ledger, drawdown -> Aegis, kalshi -> Kalshi first, journal -> the journal first, nonsense -> a plain 'Nothing found' line",
                  {"mint", "ledger"} <= set(res["money"][0]) and "aegis" in res["drawdown"][0] and res["kalshi"][0][0] == "kalshi" and res["journal"][0][0] == "journal"
                  and not res["qqqzz"][0] and "Nothing found" in res["qqqzz"][1], {k: v[0] for k, v in res.items()})
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
                ctx.close()
                s2.shutdown()

            # missing and broken data, the cached numbers
            for name, body in (("missing (404)", None), ("broken", "not json {")):
                s3, o3 = serve({"/home.json": body})
                ctx, p, errs, seen, off = AK.page(br, o3)
                open_gate(p, o3)
                r = p.evaluate(NOWCARD)
                check(f"c. home.json {name}: 'No numbers', a plain line, no button, the trade window still shown from the clock, the tiles and doors still work, no console error",
                      r["state"] == "none" and r["badge"] == "No numbers" and r["line"] == "No bot numbers reached this page." and not r["btn"] and r["facts"] == ["Trade windowOpen nowuntil 15:30 ET"]
                      and p.evaluate("() => document.querySelectorAll('.g-tile').length === 3 && !!window.OLYMPUS_GATE") and not errs, (r, errs[:2]))
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
            check("c. storage blocked (private mode): the page still works, no Recent row, no console error", p.evaluate("() => document.querySelector('#recentSec').hidden && document.querySelectorAll('.g-door').length === 4") and not errs, errs[:2])
            ctx.close()
            s4.shutdown()

            # the artifact copy at the site root, a partial copy
            s5, o5 = serve({"/home.json": home_json(300), "/olympus-live.html": html, "/odeon/index.html": None})
            ctx, p, errs, seen, off = AK.page(br, o5)
            open_gate(p, o5, path="olympus-live.html")
            r = p.evaluate("() => ({ base: window.GATE_BASE, tiles: [...document.querySelectorAll('.g-tile')].map((a) => a.href), css: !!getComputedStyle(document.querySelector('.g-tile')).borderRadius })")
            check("c. copied to the site root as olympus-live.html: base '' and the tiles go to index.html, nq/index.html, jarvis/index.html; styled; no console error",
                  r["base"] == "" and r["tiles"] == [f"{o5}/index.html", f"{o5}/nq/index.html", f"{o5}/jarvis/index.html"] and r["css"] and not errs, (r, errs[:2]))
            p.click('.g-door[data-district="trading"]')
            p.wait_for_function("() => document.querySelector('#sheetBody a.g-row[data-app=\"odeon\"]') && /g-gone/.test(document.querySelector('#sheetBody a.g-row[data-app=\"odeon\"]').className)", timeout=15000)
            gone = p.evaluate("() => [...document.querySelectorAll('#sheetBody a.g-gone')].map((a) => a.dataset.app)")
            check("c. a partial copy (odeon/ missing here): its row is dimmed and says 'not in this link'; the others stay normal", gone == ["odeon"], gone)
            AK.shot(p, "gate-root-trading")
            ctx.close()
            s5.shutdown()

            # gate-nav on the apps
            for app, sel in (("nq", "header.top .ag-navback"), ("kalshi", "a.olyback"), ("cities", "a.gn-back"), ("polis", "a.gn-back")):
                ctx, p, errs, seen, off = AK.page(br, origin)
                p.goto(f"{origin}/{app}/")
                p.wait_for_function("window.OLYMPUS_GATE_NAV && window.OLYMPUS_GATE_NAV.placed()", timeout=60000)
                p.wait_for_timeout(500)
                r = p.evaluate("(sel) => { const a = document.querySelector(sel), g = document.querySelector('.gn-go'), ra = a && a.getBoundingClientRect(), rg = g && g.getBoundingClientRect();"
                               " return { text: a && a.textContent.trim(), href: a && a.href, go: !!g, top: ra && Math.round(ra.top), goTop: rg && Math.round(rg.top), goR: rg && Math.round(rg.right), h: rg && Math.round(rg.height),"
                               " rec: JSON.parse(localStorage.getItem('gate.recent.v1') || '[]')[0] }; }", sel)
                check(f"c. {app}: the back link reads Gate and opens gate/, 'Go to' (44 px) sits in the top row on the right, this app is remembered for Recent",
                      r["text"] in ("Gate", "← Gate") and r["href"] == f"{origin}/gate/index.html" and r["go"] and r["h"] >= 44 and r["goTop"] < 140 and r["goR"] <= 390 and r["rec"] == app, r)
                check(f"c. {app} with gate-nav: no sideways scroll, no console error", AK.no_sideways(p) and not errs, errs[:3])
                if app == "nq":
                    p.click(".gn-go")
                    p.wait_for_timeout(400)
                    p.fill("#gnQ", "kalshi")
                    p.wait_for_timeout(200)
                    g = p.evaluate("() => ({ open: !document.querySelector('.gn-sheet').hidden, first: (document.querySelector('.gn-body a.gn-item[data-app]') || {}).href, gate: [...document.querySelectorAll('.gn-body a.gn-gate')].map((a) => a.href) })")
                    check("c. Go to on NQ: the sheet opens, 'kalshi' finds the Kalshi bot first, the Gate is always one tap", g["open"] and g["first"] == f"{origin}/kalshi/index.html" and g["gate"] == [f"{origin}/gate/index.html"], g)
                    p.fill("#gnQ", "")
                    p.wait_for_timeout(150)
                    dl = p.evaluate("() => [...document.querySelectorAll('.gn-dist')].map((a) => a.href.replace(location.origin, ''))")
                    check("c. Go to with an empty box: Start here and the four districts (each opens the Gate on that district's sheet)", dl == ["/gate/index.html?d=trading", "/gate/index.html?d=money", "/gate/index.html?d=life", "/gate/index.html?d=worlds"], dl)
                    t = AK.taps(p)
                    check("c. the Go to sheet: every tap >= 44 px", not t, t[:4])
                    p.keyboard.press("Escape")
                    p.wait_for_timeout(200)
                    check("c. Escape closes the Go to sheet", p.evaluate("() => document.querySelector('.gn-sheet').hidden"))
                    p.evaluate("() => window.scrollTo(0, 1400)")
                    p.wait_for_timeout(500)
                    bar = p.evaluate("() => { const b = document.querySelector('.ag-appbar'); return b ? [b.classList.contains('on'), (b.querySelector('.ag-navback') || {}).textContent, !!b.querySelector('.gn-go')] : null; }")
                    check("c. scrolled down, the compact bar has '< Gate' and the Go to icon", bar == [True, "Gate", True], bar)
                ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/gate/?d=money&now={NOW}")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000)
            check("c. gate/?d=money (Go to -> Money) opens the Money sheet at once", p.evaluate("() => !document.querySelector('#sheet').hidden && document.querySelector('#sheetH').textContent === 'Money'"))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            open_gate(p, origin)
            p.click('.g-door[data-district="life"]')
            p.wait_for_timeout(300)
            anim = p.evaluate("() => document.getAnimations().length")
            check("c. 375 x 667, reduced motion: the sheet appears without animation, no sideways scroll, every tap >= 44 px, no console error",
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
