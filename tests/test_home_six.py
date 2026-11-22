"""THE 6 MAIN DASHBOARDS (owner 2026-11-22: "when I open Olympus it goes to More with all the other dashboards. I want 6 main dashboards").

    python -X utf8 -m tests.test_home_six            (--static: no browser)
a. static: both Olympus manifests start at Home (gate/); the Jarvis page's launch guard is the first script in <head>; Home's 6 tiles are plain links
   in the owner's order (NQ Bot, Jarvis, Websites, Data City + Research, Money, Kalshi) to real pages, each with at most 2 short links; More hides the rest
b. browser 390 x 844 as the installed app (navigator.standalone): a fresh launch on the Jarvis page lands on Home; the Jarvis tile then opens Jarvis
   (no bounce); a #link or ?stay=1 stays; a normal browser tab never moves; Home opens on the 6 with More closed, an old #more address is dropped,
   More is never remembered after a reload; every tile and link is 44 px, no sideways scroll, no page error
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
W = os.path.join(ROOT, "tools", "web_public")
FAILS: list = []
N = [0]
ORDER = ["nq", "jarvis", "agency", "data", "money", "kalshi"]


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:400]}]"))
    if not ok:
        FAILS.append(name)


def text(p):
    with open(os.path.join(W, p), encoding="utf-8") as f:
        return f.read()


def static():
    jm, gm = json.loads(text("jarvis/manifest.webmanifest")), json.loads(text("gate/manifest.webmanifest"))
    # the Jarvis manifest keeps start_url ./ (its own folder: tests.test_homescreen / test_jarvis_hub), and an icon already on the phone keeps the address
    # it was saved with anyway: the launch guard below is what sends the installed app to Home
    check("a. the 'Olympus' apps: Home's manifest starts at Home; Jarvis's stays in its folder (the launch guard moves it)",
          gm["start_url"] == "./" and jm["start_url"] == "./" and jm.get("scope") == "../", (jm.get("start_url"), gm.get("start_url")))
    j = text("jarvis/index.html")
    head = j.split("</head>")[0]
    g = head.find("olympus.home.v1"), head.find("<script")
    check("a. Jarvis's launch guard: the first script in <head>; only standalone, never in a frame, not with a #link or ?stay=1, once per launch, location.replace to ../gate/",
          g[0] > 0 and head.find("<script") == head.rfind("<script", 0, g[0]) and "display-mode: standalone" in head and "window.top !== window" in head
          and "location.hash" in head and "stay=1" in head and "location.replace('../gate/')" in head)
    h = text("gate/index.html")
    tiles = re.findall(r'<div class="g-arena" data-arena="([a-z]+)"[^>]*><a class="g-amain" data-to="([^"]+)"', h)
    check("a. Home: exactly 6 tiles in the owner's order (NQ Bot, Jarvis, Websites, Data City, Money, Kalshi)", [t[0] for t in tiles] == ORDER, tiles)
    want = {"nq": "nq/index.html", "jarvis": "jarvis/index.html", "agency": "agency/index.html", "data": "cities/world/index.html", "money": "business/mffu.html", "kalshi": "kalshi/index.html"}
    check("a. each tile opens its dashboard (Data City = the world city, Money = My MFFU Accounts) and the page exists",
          all(want[a] == u and os.path.isfile(os.path.join(W, u)) for a, u in tiles), tiles)
    subs = {}
    for m in re.finditer(r'data-arena="([a-z]+)".*?<span class="g-subs">(.*?)</span>', h):
        subs[m.group(1)] = re.findall(r'data-to="([^"#]+)(?:#[^"]*)?"', m.group(2))
    check("a. at most 2 short links per tile, each to a real page (trades + brain, brief + inbox, factory + portal, research + tests, Decide + pipeline, the desk)",
          len(subs) == 6 and all(0 < len(v) <= 2 for v in subs.values()) and all(os.path.isfile(os.path.join(W, u)) for v in subs.values() for u in v)
          and "agency/portal/index.html" in subs["agency"] and "business/pipeline.html" in subs["money"] and "clio/index.html" in subs["data"] and "nq/brain.html" in subs["nq"], subs)
    css, js = text("gate/gate.css"), text("gate/arenas.js")
    check("a. More: one button under the tiles; Right now / Everything else / pins / recent / look hidden until it is tapped; nothing stored about it; an old #more dropped",
          'id="moreBtn"' in h and "html:not(.g-more-open) #elseSec" in css and "html:not(.g-more-open) #now" in css and "g-more-open" in js
          and "localStorage" not in js.split("function more()")[1] and "replaceState" in js.split("function more()")[1])


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
    STANDALONE = "Object.defineProperty(navigator, 'standalone', { get: () => true })"     # the installed iPhone app
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)

            def ctx(app=True):
                c = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce", service_workers="block")
                c.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
                if app:
                    c.add_init_script(STANDALONE)
                return c
            c = ctx()
            p = c.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)[:120]))
            p.goto(f"{origin}/jarvis/", wait_until="load")
            p.wait_for_url(re.compile(r"/gate/"), timeout=15000)
            p.wait_for_selector(".g-arena")
            check("b. the installed app opened on the Jarvis page (its saved address) lands on Home with the 6", "/gate/" in p.url and p.locator(".g-arena").count() == 6, p.url)
            p.click(".g-arena[data-arena='jarvis'] .g-amain")
            p.wait_for_url(re.compile(r"/jarvis/"), timeout=15000)
            p.wait_for_timeout(1500)
            check("b. then the Jarvis tile opens Jarvis (no bounce back to Home in the same launch)", "/jarvis/" in p.url, p.url)
            c.close()
            c = ctx()
            p = c.new_page()
            p.goto(f"{origin}/jarvis/?stay=1", wait_until="load")
            p.wait_for_timeout(1200)
            stay = "/jarvis/" in p.url
            c.close()
            c = ctx()
            p = c.new_page()
            p.goto(f"{origin}/jarvis/#nq", wait_until="load")
            p.wait_for_timeout(1200)
            check("b. ?stay=1 or a #app link (a notification) stays on Jarvis", stay and "/jarvis/" in p.url, p.url)
            c.close()
            c = ctx(app=False)
            p = c.new_page()
            p.goto(f"{origin}/jarvis/", wait_until="load")
            p.wait_for_timeout(1500)
            check("b. a normal browser tab never moves (only the installed app's launch)", "/jarvis/" in p.url, p.url)
            c.close()
            c = ctx()
            p = c.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)[:120]))
            p.goto(f"{origin}/gate/#more", wait_until="load")
            p.wait_for_selector(".g-arena")
            p.wait_for_timeout(800)
            r = p.evaluate("""() => ({ url: location.pathname + location.hash, open: document.documentElement.classList.contains('g-more-open'),
              now: getComputedStyle(document.getElementById('now')).display, tiles: [...document.querySelectorAll('.g-arena')].map((t) => [t.dataset.arena, Math.round(t.getBoundingClientRect().bottom)]),
              more: Math.round(document.getElementById('moreBtn').getBoundingClientRect().bottom), wide: document.documentElement.scrollWidth - innerWidth,
              small: [...document.querySelectorAll('.g-arena a, #moreBtn')].map((e) => [e.textContent.trim().slice(0, 14), Math.round(e.getBoundingClientRect().height)]).filter((x) => x[1] < 43.5) })""")
            check("b. Home opens on the 6 (an old #more address dropped, More closed, Right now hidden), all 6 and More on the first 390 x 844 screen",
                  r["url"] == "/gate/" and not r["open"] and r["now"] == "none" and [t[0] for t in r["tiles"]] == ORDER and all(t[1] <= 844 for t in r["tiles"]) and r["more"] <= 844, r)
            check("b. every tile, link and More >= 44 px; no sideways scroll; no page error", not r["small"] and r["wide"] <= 1 and not errs, (r["small"], r["wide"], errs))
            p.click("#moreBtn")
            p.wait_for_timeout(300)
            opened = p.evaluate("getComputedStyle(document.getElementById('elseSec')).display") != "none"
            p.reload(wait_until="load")
            p.wait_for_selector(".g-arena")
            p.wait_for_timeout(500)
            closed = p.evaluate("!document.documentElement.classList.contains('g-more-open') && getComputedStyle(document.getElementById('elseSec')).display === 'none'")
            check("b. More opens the rest; after a reload (a new launch) Home is back on the 6: More is never remembered", opened and closed, (opened, closed))
            c.close()
            br.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    static()
    if "--static" not in sys.argv:
        browser()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
