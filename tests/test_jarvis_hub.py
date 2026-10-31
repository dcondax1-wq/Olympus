"""The Jarvis hub (tools/web_public/jarvis/, owner 2026-10-31): one Home Screen app that opens on the Jarvis screen and
switches between Zenith (this dashboard), the Planner and the other projects, each kept loaded in its own frame.
Runs the real hub page in Chromium on a local copy of the site layout (<site>/jarvis/ next to stand-in Zenith / Planner
pages), with the live feed served from a stub, and checks:
  a. the files and the build step that publishes jarvis/ with every site build
  b. the Jarvis screen: greeting, the market line, a card per project (Zenith with the bots' numbers from the live feed,
     the Planner with today's plan read from its own saved data, Kalshi asking for its link)
  c. switching: the bar opens each dashboard in its own frame, a dashboard is never reloaded by switching away and back,
     #planner opens the Planner directly
  d. Jarvis answers: the bots' status / room / target from the live feed, today's plan, the market, and "open planner"
  e. a pasted Kalshi link is kept and opens inside the hub; an added dashboard shows in the bar
  f. phone width: no sideways scroll, no page errors
    python -X utf8 -m tests.test_jarvis_hub      (temp folder + a local server; nothing else touched)
"""
from __future__ import annotations

import datetime as dt
import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
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


def site(tmp):
    base = os.path.join(tmp, "nq-dashboard")
    shutil.copytree(JV, os.path.join(base, "jarvis"))
    os.makedirs(os.path.join(base, "icons"))
    shutil.copy(os.path.join(JV, "icon-192.png"), os.path.join(base, "icons", "icon-192.png"))
    with open(os.path.join(base, "index.html"), "w") as f:
        f.write("<!doctype html><title>Zenith stub</title><h1 id='z'>Zenith stub</h1><script>window.loads=(window.loads||0)+1;</script>")
    os.makedirs(os.path.join(base, "planner"))
    shutil.copy(os.path.join(JV, "icon-192.png"), os.path.join(base, "planner", "icon-192.png"))
    today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    S = {"events": [{"id": "e1", "title": "Gym", "date": today, "allDay": False, "start": "07:30", "end": "08:30", "repeat": "none"},
                    {"id": "e2", "title": "Review fills", "date": "2026-01-05", "allDay": False, "start": "16:15", "repeat": "daily"}],
         "tasks": [{"id": "t1", "title": "Buy BLITZ 25K", "date": today, "done": False}, {"id": "t2", "title": "Old", "date": today, "done": True}],
         "projects": [{"id": "p1", "name": "Kalshi bot"}]}
    with open(os.path.join(base, "planner", "index.html"), "w") as f:
        f.write("<!doctype html><title>Planner stub</title><h1>Planner stub</h1><script>"
                f"localStorage.setItem('planner.v1', JSON.stringify({json.dumps(S)}));window.loads=(window.loads||0)+1;</script>")
    os.makedirs(os.path.join(base, "kalshi-stub"))
    with open(os.path.join(base, "kalshi-stub", "index.html"), "w") as f:
        f.write("<!doctype html><title>Kalshi stub</title><h1>Kalshi stub</h1>")
    return tmp


def serve(root):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def part_a():
    for f in ("index.html", "manifest.webmanifest", "sw.js", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png"):
        check(f"a. jarvis/{f} exists", os.path.exists(os.path.join(JV, f)))
    m = json.load(open(os.path.join(JV, "manifest.webmanifest")))
    check("a. manifest: Jarvis, standalone, own scope", m["name"] == "Jarvis" and m["short_name"] == "Jarvis" and m["display"] == "standalone" and m["scope"] == "./", m)
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("a. the site build publishes jarvis/ with every build", 'os.path.join(WEB, "jarvis")' in b and 'os.path.join(out, "jarvis", name)' in b)
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    check("a. the hub's service worker only handles its own folder", "u.pathname.startsWith(scope.pathname)" in sw)


def run_browser(url):
    from playwright.sync_api import sync_playwright
    import time
    live = dict(LIVE, t=int(time.time()) - 120)
    with sync_playwright() as pw:
        import glob
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)   # as tools/icon_options_build
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ctx.route("https://api.github.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(live)))
        ctx.route("https://raw.githubusercontent.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(live)))
        p = ctx.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        # the Planner saves its data on this site first (as on the phone once it was opened)
        p.goto(url + "planner/")
        p.goto(url + "jarvis/")
        p.wait_for_timeout(900)
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
        check("b. Kalshi card asks for its link", p.locator("#link-kalshi").count() == 1)
        chips = p.inner_text("#apps")
        check("c. the bar lists Jarvis, Zenith, Planner, Kalshi", all(x in chips for x in ("Jarvis", "Zenith", "Planner", "Kalshi")), chips)
        p.click('[data-app="zenith"] >> nth=0')
        p.wait_for_timeout(600)
        zf = p.frame_locator("#v-zenith iframe")
        check("c. Zenith opens in its own frame, the Jarvis screen hides",
              zf.locator("#z").inner_text() == "Zenith stub" and p.locator("#home").is_hidden(), p.locator("#home").is_hidden())
        p.click('.chip[data-app="planner"]')
        p.wait_for_timeout(500)
        check("c. Planner opens in its own frame", p.frame_locator("#v-planner iframe").locator("h1").inner_text() == "Planner stub")
        p.click('.chip[data-app="zenith"]')
        p.wait_for_timeout(300)
        loads = p.evaluate("document.querySelector('#v-zenith iframe').contentWindow.loads")
        check("c. switching back does not reload Zenith (loaded once)", loads == 1 and p.locator("#v-planner").is_hidden(), loads)
        check("c. the open-on-its-own button shows for a dashboard", p.locator("#out").is_visible())
        p.click('.chip[data-app="home"]')
        p.wait_for_timeout(300)
        check("c. back to Jarvis", p.locator("#home").is_visible() and not p.locator("#out").is_visible())

        def ask(q):                    # the chat keeps the last 8 messages: start each question on an empty chat
            p.evaluate("document.getElementById('talk').innerHTML = ''")
            p.fill("#q", q)
            p.press("#q", "Enter")
            p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=5000)
            return p.locator(".msg.j").first.inner_text()
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
        p.click('.chip[data-app="home"]')
        a7 = ask("open kalshi")
        check("d. Kalshi without a link: says how to link it", "not linked yet" in a7, a7)
        # e. paste the Kalshi link
        p.fill("#link-kalshi", url + "kalshi-stub/")
        p.press("#link-kalshi", "Enter")
        p.wait_for_timeout(700)
        check("e. a pasted Kalshi link opens inside Jarvis", p.frame_locator("#v-kalshi iframe").locator("h1").inner_text() == "Kalshi stub")
        p.reload()
        p.wait_for_timeout(700)
        check("e. the Kalshi link is kept", p.locator("#link-kalshi").count() == 0 and "Open Kalshi inside Jarvis" in p.inner_text("#cards"))
        p.click("#addB")
        p.fill("#addName", "Clipper")
        p.fill("#addUrl", url + "kalshi-stub/")
        p.click('#addF button[type="submit"]')
        p.wait_for_timeout(500)
        check("e. an added dashboard shows in the bar and opens", "Clipper" in p.inner_text("#apps") and p.locator("#v-x-clipper").is_visible())
        p.goto(url + "jarvis/#planner")
        p.wait_for_timeout(700)
        check("c. #planner opens the Planner directly", p.locator("#v-planner").is_visible() and p.locator("#home").is_hidden())
        p.goto(url + "jarvis/")
        p.wait_for_timeout(500)
        w = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check("f. phone width: no sideways scroll", w[0] <= w[1], w)
        hw = p.evaluate("(() => { const h = document.querySelector('.home-in'); return [h.scrollWidth, h.clientWidth, Math.max(...[...h.children].map((c) => c.getBoundingClientRect().right))]; })()")
        check("f. phone width: the Jarvis screen fits inside its gutter (nothing clipped on the right)", hw[0] <= hw[1] and hw[2] <= 390 - 15.5, hw)
        check("f. no page errors", not errs, errs)
        br.close()


def main():
    part_a()
    tmp = site(tempfile.mkdtemp(prefix="le_jarvis_"))
    srv = serve(tmp)
    try:
        run_browser(f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/")
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\njarvis hub: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
