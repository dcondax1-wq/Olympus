"""ORGANIZE (day-a11y 2026-11-21, owner: "more organized"; docs/OLYMPUS_MAP.md): the site's structure holds.

    python -X utf8 -m tests.test_olympus_nav            (--static: no browser)
a. the link crawler (static): every local link on every page (href / src / data-to; Home's links are from the site root) opens a real file: no 404;
   every app in the catalog has a real folder
b. the structure (node, olympus/gate-catalog.js): every live app sits in exactly one arena (6 arenas + Everything else, the same six the Home shows);
   every retired app has a LIVE replacement; the one place per fact is a live app; every arena page lists its apps
c. reachability (static): Home links each arena's page, so every live app is <= 2 taps from Home (Home > arena page > app, or the arena tile);
   every Olympus page has the way back (gate-nav: Home + arena breadcrumb) loaded directly, through a11y.js or through agora-ui.js; the public
   client pages (agency demos, audits, showcase, factory, caller portal) never get Olympus navigation
d. browser 390 px: the breadcrumb reads Home > arena (> app) and Home is one tap; a retired app opens its replacement (?stay=1 keeps it);
   the arena page lists its apps grouped; the 'main copy' chips on a page that repeats a fact; no sideways scroll
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
W = os.path.join(ROOT, "tools", "web_public")
FAILS: list = []
N = [0]
SKIP_DIRS = {"node_modules", "three-addons", "f", "towns"}
PUBLIC = re.compile(r"^agency/(demos|audit|showcase|factory|portal|f|launch|intake)/")   # + launch / intake: client-facing (2026-11-21)
LINK = re.compile(r"""(?:href|src|data-to)\s*=\s*["']([^"'#?]+?)(?:[?#][^"']*)?["']""")


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:400]}]"))
    if not ok:
        FAILS.append(name)


def pages() -> list:
    out = []
    for dp, ds, fs in os.walk(W):
        ds[:] = [d for d in ds if d not in SKIP_DIRS]
        out += [os.path.relpath(os.path.join(dp, f), W).replace(os.sep, "/") for f in fs if f.endswith(".html")]
    return sorted(out)


def text(p: str) -> str:
    with open(os.path.join(W, p), encoding="utf-8", errors="ignore") as f:
        return f.read()


def strip(t: str) -> str:
    """the page without comments and scripts' string-built URLs (a link in a comment or a template is not a link)"""
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    return re.sub(r"<script\b[^>]*>.*?</script>", lambda m: m.group(0) if "src=" in m.group(0)[:200] and m.group(0).count("\n") == 0 and len(m.group(0)) < 400 else "", t, flags=re.S)


def local_links(p: str) -> list:
    """[(raw, resolved path from the site root)] for every local link on the page"""
    t, base = strip(text(p)), os.path.dirname(p)
    rooted = p == "gate/index.html"              # Home's links are written from the site root (GATE_BASE rewrites them)
    out = []
    for u in LINK.findall(t):
        if re.match(r"^(https?:|mailto:|tel:|sms:|data:|javascript:|blob:|about:|//)", u) or re.search(r"[${}+<>]|'\s*\+|\(", u) or not u.strip():
            continue
        r = os.path.normpath(os.path.join("" if rooted else base, u)).replace(os.sep, "/")
        out.append((u, r))
    return out


def exists(r: str) -> bool:
    f = os.path.join(W, r)
    return os.path.isfile(f) or os.path.isfile(os.path.join(f, "index.html"))


# files the PC publishes next to the site (not in the repo: the JSON feeds, and icons/ that tools/build_web_dashboard.py copies from web/icons): fine
GENERATED = re.compile(r"(^|/)(home|data|live|edge|status_feed|kalshi|wrapped|truth|summary|feed|board|brief|pantheon|jarvis|me|money|scoreboard|index)\.json$|\.json$")


def crawl():
    P = pages()
    broken = []
    for p in P:
        if PUBLIC.match(p):
            continue
        for u, r in local_links(p):
            if r.startswith(("..", "icons/")) or GENERATED.search(r) or r.endswith((".png", ".jpg", ".webp", ".mp3", ".ogg", ".wasm", ".glb", ".gltf", ".woff2")):
                continue
            if not exists(r):
                broken.append(f"{p} -> {u}")
    check(f"a. the link crawler: every local page / script / style link on the {len(P)} pages opens a real file (no 404)", not broken, broken[:12])
    return P


NODE = r"""
const C = require(process.argv[1]);
const live = C.apps.filter((a) => !C.retired(a.id));
const out = { arenas: C.arenas.map((x) => x.id), noArena: live.filter((a) => !C.arenaOf(a.id)).map((a) => a.id),
  noRep: C.RETIRED.filter((id) => C.byId(id) && !C.replacementOf(id)).map((id) => id),
  repRetired: C.RETIRED.filter((id) => C.replacementOf(id) && C.retired(C.replacementOf(id).id)),
  facts: Object.keys(C.FACTS).map((k) => [k, C.FACTS[k].path || C.FACTS[k].app, !!C.byId(C.FACTS[k].app) && !C.retired(C.FACTS[k].app)]),
  layout: C.arenas.map((x) => [x.id, x.count, C.arenaLayout(x.id).reduce((n, s) => n + s.apps.length, 0), x.front]),
  paths: live.map((a) => [a.id, a.path]), crumb: C.arenaCrumb('fates'), front: C.arenaCrumb('nq'), factsBoard: C.factsOn('board').map((f) => f.fact) };
console.log(JSON.stringify(out));
"""


def structure():
    node = shutil.which("node")
    if not node:
        print("SKIP node")
        return None
    r = subprocess.run([node, "-e", NODE, os.path.join(W, "olympus", "gate-catalog.js")], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("b. the catalog loads in node", False, r.stderr[-300:])
        return None
    o = json.loads(r.stdout)
    six = re.findall(r"var TILES = \[([^\]]*)\]", text("gate/arenas.js"))      # the 6 tiles' ids (2026-11-22)
    six = re.findall(r"'([a-z]+)'", six[0]) if six else []
    check("b. the arenas are the Home's 6 dashboards in the same order + Everything else", o["arenas"] == six + ["else"], (o["arenas"], six))
    check("b. every live app sits in an arena", not o["noArena"], o["noArena"])
    check("b. every retired app opens a LIVE replacement", not o["noRep"] and not o["repRetired"], (o["noRep"], o["repRetired"]))
    check("b. one place per fact: accounts / payout / 7-day clocks each owned by one live page (My MFFU Accounts)", all(f[2] and exists(f[1]) for f in o["facts"]) and {f[0] for f in o["facts"]} == {"accounts", "payout", "clocks"}, o["facts"])
    check("b. every arena page lists its apps (the count = the grouped list), each arena but Everything else has a front page",
          all(x[1] == x[2] and x[1] > 0 for x in o["layout"]) and all(x[3] for x in o["layout"] if x[0] != "else"), o["layout"])
    check("b. the breadcrumb data: Home > NQ Bot > Pass odds; an arena's front page is the arena itself",
          o["crumb"]["arenaName"] == "NQ Bot" and o["crumb"]["app"] == "Pass odds" and o["crumb"]["path"] == "hub/arena.html?a=nq" and o["front"]["front"], o["crumb"])
    check("b. a page that repeats a fact links to its one place (Board: accounts, payout, clocks)", sorted(o["factsBoard"]) == ["accounts", "clocks", "payout"], o["factsBoard"])
    missing = [f"{i} -> {p}" for i, p in o["paths"] if not exists(p or "index.html")]
    check("a. every live app in the catalog has a real page", not missing, missing)
    return o


def reach(P, o):
    g = text("gate/index.html")
    arena_links = set(re.findall(r'data-to="hub/arena\.html\?a=([a-z]+)"', g))
    want = set(o["arenas"]) if o else {"nq", "jarvis", "agency", "data", "money", "kalshi", "else"}
    check("c. Home links every arena's page (so every live app is <= 2 taps from Home)", want <= arena_links, sorted(want - arena_links))
    a11y = text("olympus/a11y.js")
    check("c. a11y.js loads the breadcrumb (gate-nav.js) on every page that has neither it nor the AGORA shell; never on Home, in a frame or on the public pages",
          "gate-nav.js?v=g14" in a11y and "agency\\/(demos|audit|showcase|factory|portal|f)" in a11y and "data-ag-nonav" in a11y and "window.top !== window" in a11y)
    lost = []
    for p in P:
        if PUBLIC.match(p) or p == "gate/index.html":
            continue
        t = text(p)
        if not any(k in t for k in ("gate-nav.js", "a11y.js", "agora-ui.js", "data-ag-nonav")):
            lost.append(p)
    check("c. every Olympus page has the way home (gate-nav directly, or through a11y.js / agora-ui.js) or opts out on purpose", not lost, lost[:12])
    leak = [p for p in P if PUBLIC.match(p) and re.search(r"gate-nav\.js|olympus/a11y\.js|agora-ui\.js", text(p))]
    check("c. the public client pages never load Olympus navigation", not leak, leak)


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP browser: no Python playwright")
        return
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    from tests import agora_kit as AK
    srv, origin = AK.serve()
    js = """() => { const n = document.querySelector('[data-gn=crumbs]'); const h = n && n.querySelector('[data-gn=gate]');
      return { url: location.pathname + location.search, crumbs: n ? [...n.querySelectorAll('a,span.gn-cur')].map(e => e.textContent.replace(/[←◂<]/g, '').trim()).filter(Boolean) : null,
        home: h ? h.getAttribute('href') : '', arena: n && n.querySelector('[data-gn=hub]') ? n.querySelector('[data-gn=hub]').getAttribute('href') : '',
        facts: [...document.querySelectorAll('[data-gn=facts] a')].map(a => a.getAttribute('data-fact') + '>' + a.getAttribute('href')),
        wide: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) - innerWidth } }"""
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce", service_workers="block")
            ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => false })")   # a real phone: the retired-app redirect is on
            ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())

            def visit(u, wait="[data-gn=crumbs]"):
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)[:120]))
                p.goto(f"{origin}/{u}", wait_until="load")
                try:
                    p.wait_for_selector(wait, timeout=12000)
                except Exception:  # noqa: BLE001
                    pass
                p.wait_for_timeout(400)
                return p, p.evaluate(js), errs
            rows = {}
            for u in ("board/", "fates/", "ares/", "pc/", "hub/help.html", "widget/", "kalshi/", "ledger/"):
                p, o, errs = visit(u)
                rows[u] = o
                p.close()
            bad = {u: o for u, o in rows.items() if not o["crumbs"] or o["crumbs"][0] != "Home" or not o["home"].endswith("gate/index.html") or o["wide"] > 1}
            check("d. 390 px: Home first in the breadcrumb on every sampled page (Board, Fates, Ares, PC, Help, Widget, Kalshi, Ledger), no sideways scroll", not bad, bad)
            check("d. the arena crumb: Fates = Home > NQ Bot > Pass odds (links the arena page)",
                  rows["fates/"]["crumbs"] == ["Home", "NQ Bot", "Pass odds"] and rows["fates/"]["arena"].endswith("hub/arena.html?a=nq"), rows["fates/"])
            check("d. pages without the AGORA shell got the way home too (Board, Ares, PC, Help: before 2026-11-21 they had none)",
                  all(rows[u]["crumbs"] and rows[u]["home"] for u in ("board/", "ares/", "pc/", "hub/help.html")), {u: rows[u]["crumbs"] for u in ("board/", "ares/", "pc/", "hub/help.html")})
            check("d. Board repeats accounts / payouts / clocks: one 'main copy' chip links My MFFU Accounts",
                  len(rows["board/"]["facts"]) == 1 and rows["board/"]["facts"][0].startswith("accounts payout clocks>") and rows["board/"]["facts"][0].endswith("business/mffu.html"), rows["board/"]["facts"])
            p, o, _ = visit("delphi/")
            check("d. a retired app (Delphi) opens its replacement (Helios), saying where it came from", o["url"] == "/helios/index.html?from=delphi", o["url"])
            p.close()
            p, o, _ = visit("delphi/?stay=1")
            check("d. ?stay=1 keeps the old page (nothing deleted)", o["url"].startswith("/delphi/"), o["url"])
            p.close()
            p, o, errs = visit("hub/arena.html?a=nq", wait=".ar-item")
            items = p.evaluate("[...document.querySelectorAll('.ar-item')].map(a => a.getAttribute('data-app'))")
            front = p.get_attribute("#arFront", "href")
            check("d. the NQ Bot arena page: its front page first, then its apps grouped, Home > NQ Bot, no retired app listed",
                  front and front.endswith("nq/index.html") and "fates" in items and "aegis" in items and "delphi" not in items and o["crumbs"][:2] == ["Home", "NQ Bot"]
                  and len(p.query_selector_all(".ar-sec h2")) >= 4 and not errs and o["wide"] <= 1, (front, items[:6], o, errs))
            p.click(".ar-item[data-app='fates']")
            p.wait_for_url(re.compile(r"/fates/"))
            p.wait_for_selector("[data-gn=gate]", timeout=12000)
            p.click("[data-gn=gate]", timeout=8000)          # a real tap: nothing (Fates' 3D scene) may cover the Home link
            p.wait_for_url(re.compile(r"/gate/"))
            check("d. Home > NQ Bot page > Pass odds, then one tap on Home goes Home", "/gate/" in p.url, p.url)
            p.close()
            p, o, _ = visit("hub/arena.html?a=else", wait=".ar-item")
            check("d. the Everything else page lists Settings and the PC steps", {"settings", "pc"} <= set(p.evaluate("[...document.querySelectorAll('.ar-item')].map(a => a.getAttribute('data-app'))")))
            p.close()
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    P = crawl()
    o = structure()
    reach(P, o)
    if "--static" not in sys.argv:
        browser()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
