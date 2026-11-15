"""OLYMPUS IA v2: the nine hubs (docs/OLYMPUS_IA_V2.md, 2026-11-14). Owner: "Make it very organized ... it always looks the same: 'Trading', 'Money', 'Life'
subcategories. I want something more organized." The hubs are DATA in olympus/gate-catalog.js; the live lines are olympus/hub-status.js; the hub page is
tools/web_public/hub/ (hub/?h=<hub>&t=<tab>); breadcrumbs + Go to are olympus/gate-nav.js (agora-ui.js loads it on every AGORA app). The home: test_gate_page.

  a. static: the files, the tags in order, ES5 / no markup from data / read only / storage, colours only through the AGORA tokens (hub.css, gate.css),
     the agora-ui.js loader for gate-nav, the doc
  b. node: every app in exactly one hub and tab, each tab has one best app, every fold points at the best of its own tab, the breadcrumb of every app,
     the hub lines (bots fresh / old / missing, Kalshi, money, my shift, research), demo cards never shown as live
  c. Chromium 390 x 844: every hub page (title, tabs, best card, folded duplicates, breadcrumb Home > Hub), every app reachable home -> hub -> app (2 taps),
     ?t= deep links, "Show it here" embeds the app, the live strip of Bots & Evals / Kalshi / My Money / Plan & Day, Settings & Help lists every app (83),
     an unknown hub = the list of hubs, gate-nav on an AGORA app without its own tag, 375 x 667 reduced motion; taps >= 44 px, no sideways scroll
    python -X utf8 -m tests.test_hubs            (--static: parts a and b only; screenshots with AGORA_SHOTS=<dir>)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
H = os.path.join(AK.WEB, "hub")
CAT = os.path.join(AK.WEB, "olympus", "gate-catalog.js")
HSJ = os.path.join(AK.WEB, "olympus", "hub-status.js")
NAV = os.path.join(AK.WEB, "olympus", "gate-nav.js")
HUBS = ["today", "me", "bots", "kalshi", "money", "plan", "research", "jarvis", "worlds", "settings"]     # + Me (2026-11-14, a page hub: tests/test_me_hub.py)
NAMES = ["Today", "Me", "Bots & Evals", "Kalshi", "My Money", "Plan & Day", "Research", "Jarvis", "Worlds", "Settings & Help"]
NOW = "2026-11-12T15:00:00Z"            # Thursday 10:00 New York: the LIT window is open
N_APPS = 84                              # 82 + Agency (2026-11-14) + Business (2026-11-15)
NOW_S = int(datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc).timestamp())


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//[^\n]*|\s//\s[^\n]*", "", js)


def no_colour_literals(css):
    """the rules (the :where(:root) fallback block aside) use tokens only: no #hex, no rgb()/rgba() with numbers"""
    body = re.sub(r":where\(:root\)\s*\{.*?\n\}", "", css, flags=re.S)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", body)


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    names = ["index.html", "hub.js", "hub.css", "icon.svg"]
    check("a. the files: hub/index.html, hub.js, hub.css, icon.svg, olympus/hub-status.js, docs/OLYMPUS_IA_V2.md",
          all(os.path.isfile(os.path.join(H, n)) for n in names) and os.path.isfile(HSJ) and os.path.isfile(os.path.join(AK.ROOT, "docs", "OLYMPUS_IA_V2.md")))
    html, js, css, hs, nav, cat = (AK.read(p) for p in (os.path.join(H, "index.html"), os.path.join(H, "hub.js"), os.path.join(H, "hub.css"), HSJ, NAV, CAT))
    order = ["../olympus/agora.css?v=a4", "hub.css?v=h3", "me.css?v=m2", "../olympus/themes.js?v=o6", "../olympus/gate-catalog.js?v=nv1", "../olympus/hub-status.js?v=h2",
             '../olympus/gate-nav.js?v=g4" data-app="hub" defer', "me.js?v=m2", "hub.js?v=h3"]
    pos = [html.find(x) for x in order]
    check("a. the page loads agora.css, hub.css, me.css, the theme engine, the catalog, hub-status, gate-nav (data-app=hub, deferred), me.js (the Me hub) and hub.js, in that order, all in <head>",
          all(p >= 0 for p in pos) and pos == sorted(pos) and max(pos) < html.index("</head>"), dict(zip(order, pos)))
    check("a. the page: AGORA theme, viewport-fit=cover, ONE h1, a polite live strip, a tablist + tabpanel, the hub list as plain links (works without the script), Home",
          '<html lang="en" data-theme="agora">' in html and "viewport-fit=cover" in html and html.count("<h1") == 1 and 'aria-live="polite"' in html
          and 'role="tablist"' in html and 'role="tabpanel"' in html and all(f'href="index.html?h={h}"' in html for h in HUBS) and 'href="../gate/index.html"' in html)
    check("a. the hub sets <html data-oly-district=<hub>> from ?h= before paint (the theme's per-district mix follows the hub)",
          "d.setAttribute('data-oly-district', m[1])" in html and "setAttribute('data-oly-district', H.id)" in js)
    code = strip_comments(js) + strip_comments(hs)
    es6 = [p for p in (r"=>", r"\blet\s", r"\bconst\s", r"`", r"\bclass\s+\w+\s*[{e]", r"\.\.\.\w", r"\.at\(", r"\(\?<[=!]") if re.search(p, code)]
    check("a. hub.js and hub-status.js are ES5 classic scripts (Safari 12+ safe, no build step)", not es6, es6)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if re.search(p, js + hs + html)]
    check("a. no markup from data: text through textContent / createElementNS only", not bad and "textContent" in js and "createElementNS" in js, bad)
    check("a. read only: no XHR / WebSocket / sendBeacon / POST / cookies / web address; it fetches home.json, kalshi.json, money/scoreboard.json and the hub's jarvis.json cards",
          not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|document\.cookie|https?://(?!www\.w3\.org)", js + hs + html)
          and set(re.findall(r"getJSON\(([^)]*)\)", js)) == {"base + 'kalshi.json'", "base + 'money/scoreboard.json'", "base + 'home.json'", "base + a.path + 'jarvis.json'"})
    ls = set(re.findall(r"localStorage\.(\w+)", js + hs))
    check("a. storage: 'gate.recent.v1' (Recent, the Gate's key) written, 'planner.today.v1' only read; every call in try / catch",
          ls <= {"getItem", "setItem"} and "setItem('gate.recent.v1'" in js and "'planner.today.v1'" in hs and "setItem('planner" not in js + hs
          and all("try {" in ln for ln in (js + hs).splitlines() if "localStorage." in ln), ls)
    lit = {n: no_colour_literals(AK.read(p)) for n, p in (("hub.css", os.path.join(H, "hub.css")), ("gate.css", os.path.join(AK.WEB, "gate", "gate.css")))}
    check("a. colours only through the AGORA tokens (hub.css, gate.css): no colour literal outside the :where(:root) fallback block (zero specificity, so agora.css and the themes win)",
          not any(lit.values()) and ":where(:root)" in css, lit)
    check("a. the AGORA look: serif titles, tabular numbers, no neon / glow / techno font; taps >= 44 px, safe areas, 176 px clear of Jarvis's corner, reduced motion, LITE",
          "--ag-serif" in css and "tabular-nums" in css and not AK.BANNED_LOOK.search(css + js + hs) and css.count("min-height: 44px") >= 3
          and "safe-area-inset" in css and "176px" in css and "prefers-reduced-motion: reduce" in css and 'data-oly-lite="1"' in css)
    ui = AK.read(os.path.join(AK.WEB, "olympus", "agora-ui.js"))
    check("a. agora-ui.js adds gate-nav.js?v=g4 next to itself on every AGORA app (never framed, never twice, data-ag-nonav opts out); every page loads agora-ui.js?v=2",
          "new URL('gate-nav.js?v=g4', meSrc)" in ui and "if (framed || window.OLYMPUS_GATE_NAV" in ui and "data-ag-nonav" in ui and "script[src*=\"gate-nav.js\"]" in ui
          and not re.search(r"agora-ui\.js\?v=1\"", "".join(AK.read(os.path.join(AK.WEB, a, "index.html")) for a in os.listdir(AK.WEB) if os.path.isfile(os.path.join(AK.WEB, a, "index.html")))))
    check("a. gate-nav: breadcrumb (nav aria-label=Breadcrumb, aria-current on the last crumb), 'Home' instead of 'Gate', the nine hubs first in Go to",
          "'Breadcrumb'" in nav and "'aria-current', 'page'" in nav and "label.textContent = 'Home'" in nav and "'Hubs'" in nav and "hub/index.html?h=" in nav and "'gate.recent.v1'" in nav)
    doc = AK.read(os.path.join(AK.ROOT, "docs", "OLYMPUS_IA_V2.md"))
    check(f"a. docs/OLYMPUS_IA_V2.md: the nine hubs, the duplicates folded, every app ({N_APPS} rows), the wiring for the lead",
          all(n in doc for n in NAMES) and "Duplicates folded" in doc and doc.count("| **best** |") + doc.count("| also |") + doc.count("| folded into ") == N_APPS
          and "OTHER_APPS" in doc and "build_web_dashboard.py" in doc)


# ------------------------------------------------------------------------------------------------ b. node
HARNESS = r"""
const C = require(process.argv[1]), HS = require(process.argv[2]), A = JSON.parse(process.argv[3]);
const t = A.now;
const card = (level, label, kpis) => ({ v: 1, status: { level, label }, kpis: kpis || [] });
const home = (age, rooms) => ({ live: { pc: { t: t - age, running: true } }, board: { data_t: t - age, lit: { room: rooms[0], mll: 2000, today_pnl: 100 }, atlas: { room: rooms[1], mll: 1000, today_pnl: -20 } } });
const N = (h) => HS.summarize(h, null, t);
const P = HS.planOf({ day: '2026-11-12', events: [{ title: 'Work shift', start: '08:00', end: '16:00' }, { title: 'Gym', start: '18:00', end: '19:00' }], tasks: [{ done: true }, {}] }, t);
const out = {
  hubs: C.hubs.map((h) => ({ id: h.id, name: h.name, count: h.count, legacy: h.legacy, q: h.q, sections: h.sections.map((s) => s[0]), see: h.see })),
  lay: Object.fromEntries(C.hubs.map((h) => [h.id, C.layout(h.id).map((s) => ({ id: s.id, best: s.best && s.best.id, bestFold: s.best && s.best.fold, peers: s.peers.map((a) => a.id), folded: s.folded.map((a) => [a.id, a.fold]) }))])),
  apps: C.apps.map((a) => ({ id: a.id, hub: a.hub, district: a.district, section: a.section, fold: a.fold, path: a.path })),
  crumbs: Object.fromEntries(C.apps.map((a) => [a.id, C.crumbOf(a.id)])),
  mix: [C.mixOf('aegis'), C.mixOf('kalshi'), C.mixOf('nope'), C.hub('today') && C.hub('today').count, C.hubOf('today') && C.hubOf('today').id],
  lines: {
    fresh: HS.hubLine('bots', { N: N(home(300, [1145, 822])) }),
    old: HS.hubLine('bots', { N: N(home(3 * 86400, [1145, 822])) }),
    none: HS.hubLine('bots', { N: { has: false, accts: [] } }),
    today: HS.hubLine('today', { N: N(home(300, [1145, 822])), P }),
    kalshi: HS.hubLine('kalshi', { K: HS.kalshiOf({ t: t - 60, balance: 2410.55, today_pnl: -3.2, positions: [1, 2, 3] }, t) }),
    kalshiNone: HS.hubLine('kalshi', { K: HS.kalshiOf(null, t) }),
    money: HS.hubLine('money', { M: HS.moneyOf({ totals: { month: { net: -40 }, all: { net: 1585 } } }) }),
    moneyNone: HS.hubLine('money', { M: HS.moneyOf({}) }),
    plan: HS.hubLine('plan', { P }),
    research: HS.hubLine('research', { cards: { hephaestus: card('ok', 'Read-only workshop', [{ label: '2026 net (live)', value: '$43,820' }, { label: 'Jul-Oct PF', value: '2.91' }]) } }),
    researchDemo: HS.hubLine('research', { cards: { hephaestus: card('off', 'Demo data', [{ label: 'x', value: '1' }]) } }),
  },
  plan: P,
  planOld: HS.planOf({ day: '2026-11-11', events: [{ title: 'Work shift', start: '08:00', end: '16:00' }] }, t),
  shiftLine: HS.shiftLine(P),
  cards: [HS.cardLine(card('ok', 'Zlarior pass odds 67%', [{ label: 'Zlarior pass', value: '67%' }])), HS.cardLine(card('off', 'Demo data')), HS.cardLine(card('ok', 'Example numbers')), HS.cardLine(null)],
  win: HS.windowLine(HS.nextWindow({}, t)),
};
process.stdout.write(JSON.stringify(out));
"""


def node_out():
    exe = shutil.which("node")
    if not exe:
        return None
    r = subprocess.run([exe, "-e", HARNESS, CAT, HSJ, json.dumps({"now": NOW_S})], capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else {"_error": r.stderr[-800:]}


def test_node():
    O = node_out()
    if O is None:
        check("b. node is available for the catalog checks", True)
        return
    if "_error" in O:
        check("b. the catalog and hub-status run in node", False, O["_error"])
        return
    hubs, apps, lay = O["hubs"], O["apps"], O["lay"]
    check("b. the hubs in the home's order (the nine + Me, a page hub), named after the owner's jobs, each with its question", [h["id"] for h in hubs] == HUBS and [h["name"] for h in hubs] == NAMES
          and all(h["q"].endswith(("?", ")")) for h in hubs), [h["name"] for h in hubs])
    check(f"b. {N_APPS} apps, each in exactly one hub (district = hub, so the theme's mix follows it); the counts add up",
          len(apps) == N_APPS and all(a["hub"] in HUBS and a["district"] == a["hub"] for a in apps) and sum(h["count"] for h in hubs) == N_APPS, [h["count"] for h in hubs])
    seen = {}
    for h in HUBS:
        for s in lay[h]:
            for i in [s["best"]] + s["peers"] + [f[0] for f in s["folded"]]:
                seen[i] = seen.get(i, 0) + 1
    check("b. every app shows up exactly once across the hub tabs (best + also + folded): nothing lost, nothing twice",
          set(seen) == {a["id"] for a in apps} and all(v == 1 for v in seen.values()), [k for k, v in seen.items() if v != 1])
    bestless = [f"{h}/{s['id']}" for h in HUBS for s in lay[h] if not s["best"] or s["bestFold"]]
    check("b. every tab has one best app (never a folded duplicate)", not bestless, bestless)
    badfold = [(h, f) for h in HUBS for s in lay[h] for f in s["folded"] if f[1] != s["best"] and f[1] not in s["peers"]]
    check("b. every folded duplicate names an app shown above it in its own tab (the best one, or a separate job there: Chronos -> Kairos)", not badfold, badfold)
    want = {"stoa": "compass", "hestia": "compass", "delphi": "helios", "forum": "helios", "pheme": "pythia", "chronos": "kairos", "demeter": "aegis",
            "epilogue": "apollo", "hermes": "ledger", "plutus": "hera", "sibyl": "dionysus", "arena": "lyceum", "symposium": "ergasterion", "tyche": "kalshicity"}
    got = {a["id"]: a["fold"] for a in apps if a["fold"]}
    check("b. the duplicates of docs/OLYMPUS_IA_V2.md are folded: 4 morning briefs -> Helios, 3 'do now' -> Compass, risk -> Aegis, money plan -> Hera, ...", got == want, got)
    bests = {h: [s["best"] for s in lay[h]] for h in HUBS}
    check("b. the best app per job: Today = Compass / Helios / Pythia, Bots & Evals = NQ / Aegis / Fates / Odeon / Apollo, Kalshi = Kalshi / Dionysus, My Money = Ledger / Hera / Oikos / Mint",
          bests["today"] == ["compass", "helios", "pythia"] and bests["bots"] == ["nq", "aegis", "fates", "odeon", "apollo"] and bests["kalshi"] == ["kalshi", "dionysus"]
          and bests["money"] == ["ledger", "hera", "oikos", "mint"] and bests["jarvis"][0] == "jarvis" and bests["settings"][0] == "settings", bests)
    labs = {a["id"] for a in apps if a["section"] == "workshop"}
    check("b. dev and lab pages sit in Settings & Help > Workshop (8 labs + the shape gallery)", labs == {"agora-lab", "env-lab", "fx-lab", "sfx-lab", "people-lab", "polis-lab", "polis-life-lab", "render-lab", "gallery"}, labs)
    cr = O["crumbs"]
    check("b. every app has a breadcrumb: its hub name and a link to hub/?h=<hub>&t=<tab> (Aegis = Bots & Evals > Risk; the dashboard = Bots & Evals)",
          all(cr[a["id"]] and cr[a["id"]]["path"] == f"hub/index.html?h={a['hub']}&t={a['section']}" for a in apps)
          and cr["aegis"]["hubName"] == "Bots & Evals" and cr["aegis"]["sectionName"] == "Risk" and cr["today"]["hub"] == "bots", cr["aegis"])
    check("b. mixOf(app) = its hub (aegis -> bots, kalshi -> kalshi, unknown -> ''); hub('today') is the Today hub (15 apps), hubOf('today') is the dashboard's hub (bots)",
          O["mix"] == ["bots", "kalshi", "", 15, "bots"], O["mix"])
    see = [(h["id"], i) for h in hubs for i in h["see"] if i not in {a["id"] for a in apps} or next(a for a in apps if a["id"] == i)["hub"] == h["id"]]
    check("b. 'also useful here' only lists real apps that live in ANOTHER hub", not see, see)
    L = O["lines"]
    check("b. Bots & Evals line: fresh '2 evals active, $1,145 / $822 left' (ok); 3 days old 'Old numbers (3 d ago) · ...' (bad); no home.json 'No bot numbers reached this page'",
          L["fresh"] == {"text": "2 evals active, $1,145 / $822 left", "lvl": "ok"} and L["old"]["text"] == "Old numbers (3 d ago) · 2 evals active, $1,145 / $822 left" and L["old"]["lvl"] == "bad"
          and L["none"]["text"] == "No bot numbers reached this page", (L["fresh"], L["old"], L["none"]))
    check("b. Today line: the window and my shift ('Trade window open until 15:30 ET · On shift now until 16:00')", L["today"]["text"] == "Trade window open until 15:30 ET · On shift now until 16:00", L["today"])
    check("b. Kalshi line: 'Balance $2,411 · today −$3 · 3 open bets' (warn on a red day); no feed = 'No Kalshi numbers yet'",
          L["kalshi"] == {"text": "Balance $2,411 · today −$3 · 3 open bets", "lvl": "warn"} and L["kalshiNone"]["text"] == "No Kalshi numbers yet", (L["kalshi"], L["kalshiNone"]))
    check("b. My Money line: cash only 'This month −$40 cash · all time +$1,585'; no scoreboard = a plain line, no number",
          L["money"]["text"] == "This month −$40 cash · all time +$1,585" and not re.search(r"\$\d", L["moneyNone"]["text"]), (L["money"], L["moneyNone"]))
    check("b. Plan & Day line: shift, next event, tasks ('On shift now until 16:00 · Next: Gym 18:00 · 1 of 2 tasks done'); yesterday's summary is ignored",
          L["plan"]["text"] == "On shift now until 16:00 · Next: Gym 18:00 · 1 of 2 tasks done" and O["planOld"] == {"has": False}, (L["plan"], O["planOld"]))
    check("b. Research line: the live card's numbers ('2026 net (live) $43,820 · Jul-Oct PF 2.91'); a DEMO card is never shown as live",
          L["research"]["text"] == "2026 net (live) $43,820 · Jul-Oct PF 2.91" and L["researchDemo"]["text"] == "Backtests, edges and write-ups", (L["research"], L["researchDemo"]))
    check("b. status cards: a real one in a line; 'Demo data', 'Example numbers' and a missing card give nothing", O["cards"][0] == {"text": "Zlarior pass odds 67%", "lvl": "ok"} and O["cards"][1:] == [None, None, None], O["cards"])
    check("b. the trade window in words (Thursday 10:00 ET): 'Trade window open until 15:30 ET'", O["win"] == "Trade window open until 15:30 ET", O["win"])


# ------------------------------------------------------------------------------------------------ c. the browser
def home_json(age_s, room=1145):
    pc_t = NOW_S - age_s
    return json.dumps({"built": datetime.fromtimestamp(NOW_S - 600, timezone.utc).isoformat(), "live": {"pc": {"t": pc_t, "running": True}},
                       "board": {"t": NOW_S - 600, "data_t": pc_t, "running": True,
                                 "lit": {"id": "lit", "name": "Zlarior", "room": room, "mll": 2000, "balance": 49145, "today_pnl": 312,
                                         "windows": [{"open_t": NOW_S - 6 * 3600, "close_t": NOW_S + 5.5 * 3600, "label": "Thu 02:00-15:30 ET"}]},
                                 "atlas": {"id": "atlas", "name": "ATLAS", "room": 822, "mll": 1000, "today_pnl": -40}}})


KAL = json.dumps({"v": 3, "t": NOW_S - 1200, "running": True, "balance": 2410.55, "today_pnl": 3.4, "week_pnl": -12.0, "total_pnl": 410.55, "positions": [{}, {}]})
SB = json.dumps({"totals": {"week": {"net": 120}, "month": {"net": 640}, "all": {"net": 1585}}})
PLAN = json.dumps({"v": 1, "day": "2026-11-12", "events": [{"title": "Work shift", "start": "08:00", "end": "16:00"}, {"title": "Walk", "start": "17:30", "end": "18:15"}],
                   "tasks": [{"title": "a", "done": True}, {"title": "b"}, {"title": "c"}]})
STATE = """() => ({ title: document.querySelector('#hubName').textContent, q: document.querySelector('#hubQ').textContent, district: document.documentElement.dataset.olyDistrict,
  tabs: [...document.querySelectorAll('[role=tab]')].map((b) => [b.dataset.tab, b.getAttribute('aria-selected')]),
  best: (document.querySelector('#panel .hb-best') || {}).dataset, peers: [...document.querySelectorAll('#panel > .hb-list a.hb-row')].map((a) => a.dataset.app),
  folded: [...document.querySelectorAll('#panel details.hb-fold a.hb-row')].map((a) => a.dataset.app), foldOpen: !!(document.querySelector('#panel details.hb-fold') || {}).open,
  links: [...document.querySelectorAll('#panel a[data-app], #panel .hb-best a.hb-btn')].map((a) => a.href.replace(location.origin, '')),
  facts: [...document.querySelectorAll('#hubFacts .hb-fact')].map((f) => f.textContent),
  crumbs: [...document.querySelectorAll('nav.gn-crumbs a, nav.gn-crumbs .gn-cur')].filter((e) => getComputedStyle(e).display !== 'none' && e.textContent).map((e) => e.textContent.trim()),
  title2: document.title })"""


def open_hub(p, origin, q):
    p.goto(f"{origin}/hub/{q}{'&' if '?' in q else '?'}now={NOW}")
    p.wait_for_function("window.HUB && window.HUB.ready()", timeout=60000, polling=200)
    p.wait_for_function("window.OLYMPUS_GATE_NAV && window.OLYMPUS_GATE_NAV.placed()", timeout=30000, polling=200)
    p.wait_for_timeout(350)


def test_page():
    C = node_out() or {}
    lay = C.get("lay", {})
    apps = {a["id"]: a for a in C.get("apps", [])}
    srv, origin = AK.serve({"/home.json": home_json(300), "/kalshi.json": KAL, "/money/scoreboard.json": SB})
    shots = os.environ.get("AGORA_SHOTS")
    try:
        with AK.browser() as br:
            reached = set()
            for hid, name in zip(HUBS, NAMES):
                if hid == "me":                # a page hub (tiles and areas, no app tabs): tests/test_me_hub.py
                    continue
                ctx, p, errs, seen, off = AK.page(br, origin, storage={"planner.today.v1": PLAN})
                open_hub(p, origin, f"?h={hid}")
                r = p.evaluate(STATE)
                sec = lay.get(hid, [])
                check(f"c. {name}: the title, its question, <html data-oly-district={hid}>, one tab per job ({len(sec)}), the first selected, its best app first",
                      r["title"] == name and r["q"] and r["district"] == hid and [t[0] for t in r["tabs"]] == ([s["id"] for s in sec] if len(sec) > 1 else [])
                      and (len(sec) < 2 or r["tabs"][0][1] == "true") and (r["best"] or {}).get("app") == sec[0]["best"] and r["title2"] == f"{name} · Olympus", r)
                check(f"c. {name}: the breadcrumb Home > {name}", r["crumbs"][:2] == ["Home", name], r["crumbs"])
                for i, s in enumerate(sec):
                    if i:
                        p.click(f"#tab-{s['id']}")
                        p.wait_for_timeout(120)
                        r = p.evaluate(STATE)
                    for ln in r["links"]:
                        reached.add(ln)
                    ok = (r["best"] or {}).get("app") == s["best"] and r["peers"] == s["peers"] and r["folded"] == [f[0] for f in s["folded"]] and not r["foldOpen"]
                    check(f"c. {name} > {s['id']}: best {s['best']}, also {s['peers']}, folded (closed) {[f[0] for f in s['folded']]}", ok, r)
                    if shots and i == 0:
                        AK.shot(p, f"hub-{hid}")
                t = AK.taps(p)
                check(f"c. {name}: every tap >= 44 px, no sideways scroll, Jarvis's corner free, no console error, nothing off the origin",
                      not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:4], AK.corner(p), errs[:3], off[:2]))
                ctx.close()
            want = {("/index.html" if a["path"] == "" else "/" + a["path"] + ("index.html" if a["path"].endswith("/") else "")) for a in apps.values()}
            check(f"c. every app ({len(want)}) is reached from a hub tab: home -> hub -> app = 2 taps (folded ones included); nothing lost",
                  want <= reached, sorted(want - reached)[:8])

            # the live strips
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"planner.today.v1": PLAN})
            open_hub(p, origin, "?h=bots")
            f = p.evaluate(STATE)["facts"]
            check("c. Bots & Evals strip: 'Bots on, report 5 min ago', drawdown $1,145 of $2,000 and $822 of $1,000, today +$272",
                  f[0] == "BotsBots onreport 5 min ago" and f[1] == "Drawdown left$1,145of $2,000 max loss, Zlarior 50K" and f[2] == "Drawdown left$822of $1,000 max loss, ATLAS 25K"
                  and f[3].startswith("Today+$272"), f)
            open_hub(p, origin, "?h=kalshi")
            f = p.evaluate(STATE)["facts"]
            check("c. Kalshi strip: balance $2,411, today +$3, 2 open bets, updated 20 min ago", f[0].startswith("Balance$2,411") and f[1].startswith("Today+$3") and f[2].startswith("Open bets2") and f[3].startswith("Updated20 min ago"), f)
            open_hub(p, origin, "?h=money")
            r = p.evaluate("() => [[...document.querySelectorAll('#hubFacts .hb-fact')].map((f) => f.textContent), document.querySelector('#hubFoot').textContent]")
            check("c. My Money strip: this month +$640, all time +$1,585 (cash only, said in words), Kalshi", r[0][0].startswith("This month+$640") and r[0][1].startswith("All time+$1,585")
                  and r[1].startswith("Cash only") and r[0][2].startswith("Kalshi$2,411"), r)
            open_hub(p, origin, "?h=plan")
            f = p.evaluate(STATE)["facts"]
            check("c. Plan & Day strip: my shift (now to 16:00), next (17:30 Walk), tasks 1 of 3, the trade window", f[0] == "My shiftNow to 16:00Work shift" and f[1] == "Next on your plan17:30Walk"
                  and f[2] == "Tasks today1 of 3done" and f[3].startswith("Trade window"), f)
            open_hub(p, origin, "?h=today")
            f = p.evaluate(STATE)["facts"]
            check("c. Today strip: bots, the window, my shift, next, Kalshi", [x.split("$")[0][:10] for x in f] == ["BotsBots o", "Trade wind", "My shiftNo", "Next on yo", "Kalshi"], f)

            # deep link, embed, Settings A-Z, unknown hub
            open_hub(p, origin, "?h=bots&t=risk")
            r = p.evaluate(STATE)
            check("c. ?h=bots&t=risk opens the Risk tab (Aegis best; Pnyx, Labyrinth also; Demeter folded)", ["risk", "true"] in r["tabs"] and r["best"]["app"] == "aegis" and r["folded"] == ["demeter"], r)
            p.click("#tab-odds")
            p.wait_for_timeout(150)
            check("c. a tab tap puts the tab in the address (?h=bots&t=odds)", "h=bots&t=odds" in p.url, p.url)
            p.focus("#tab-odds")
            p.keyboard.press("ArrowRight")
            p.wait_for_timeout(120)
            check("c. arrow keys move between tabs (Pass odds -> Trades)", p.evaluate("() => document.activeElement.id") == "tab-trades" and p.evaluate(STATE)["best"]["app"] == "odeon")
            open_hub(p, origin, "?h=today")
            p.click("#panel .hb-best button[data-embed]")
            p.wait_for_selector("#panel .hb-embed iframe", timeout=10000)
            fr = p.evaluate("() => { const f = document.querySelector('#panel .hb-embed iframe'); return [f.src.replace(location.origin, ''), f.getBoundingClientRect().height, document.querySelector('#panel .hb-best button[data-embed]').textContent, document.querySelector('#panel .hb-best button[data-embed]').getAttribute('aria-expanded')]; }")
            check("c. 'Show it here' embeds the best app (Compass) in a frame below its card, the button becomes 'Hide'", fr[0] == "/compass/index.html" and fr[1] > 400 and fr[2] == "Hide" and fr[3] == "true", fr)
            p.wait_for_timeout(2500)
            inner = p.evaluate("() => { try { const d = document.querySelector('#panel .hb-embed iframe').contentDocument; return [d.documentElement.className, !!d.querySelector('.gn-crumbs')]; } catch (e) { return ['x', true]; } }")
            check("c. inside the frame the app knows it is framed and adds no second breadcrumb", "framed" in inner[0] and not inner[1], inner)
            open_hub(p, origin, "?h=settings&t=help")
            az = p.evaluate("() => [...document.querySelectorAll('#panel .hb-az a.hb-row')].map((a) => a.dataset.app)")
            check(f"c. Settings & Help > Help lists every app A to Z ({N_APPS}), each with its hub", len(az) == N_APPS and len(set(az)) == N_APPS, len(az))
            open_hub(p, origin, "?h=nope")
            r = p.evaluate("() => [document.querySelector('#indexH').textContent, [...document.querySelectorAll('a.hb-hubrow')].map((a) => a.dataset.hub), document.querySelector('#tabs').hidden]")
            check("c. an unknown hub (?h=nope) shows 'Pick a hub' and every hub", r == ["Pick a hub", HUBS, True], r)
            ctx.close()

            # gate-nav arrives by itself on an AGORA app without its own tag (Compass), and on a hub page Go to marks the hub
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/compass/")
            p.wait_for_function("window.OLYMPUS_GATE_NAV && window.OLYMPUS_GATE_NAV.placed() && document.querySelector('.gn-crumb') && document.querySelector('.gn-crumb').textContent", timeout=60000)
            r = p.evaluate("() => ({ own: !!document.querySelector('head script[src*=\"gate-nav.js\"][defer]'), crumbs: [...document.querySelectorAll('nav.gn-crumbs a, nav.gn-crumbs .gn-cur')].map((e) => e.textContent.trim()), hub: document.querySelector('.gn-crumb').href.replace(location.origin, '') })")
            check("c. Compass (no gate-nav tag of its own): agora-ui.js loads it; the breadcrumb reads Home > Today > What to do next, Today -> its Do now tab",
                  r["crumbs"] == ["Home", "Today", "What to do next"] and r["hub"] == "/hub/index.html?h=today&t=now" and AK.no_sideways(p) and not errs, (r, errs[:2]))
            if shots:
                AK.shot(p, "app-compass")
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            open_hub(p, origin, "?h=bots")
            p.click("#tab-review")
            p.click("#panel details.hb-fold summary")
            p.wait_for_timeout(150)
            anim = p.evaluate("() => document.getAnimations().length")
            check("c. 375 x 667, reduced motion: the folded duplicates open, nothing animates, no sideways scroll, every tap >= 44 px, no console error",
                  p.evaluate("() => document.querySelector('#panel details.hb-fold').open") and anim == 0 and AK.no_sideways(p) and not AK.taps(p) and not errs, (anim, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
