"""Owner manual (tools/web_public/hub/manual.html + manual.css + manual.js, docs/OWNER_MANUAL.md; 2026-11-20 day-manual).
  a. facts: 10 emergency cards, each 1-3 steps; every copy line is in BOTH the page and the doc and is a real command (the module
     file exists and has the flag; every .bat named exists); the key numbers match accounts.json / the docs; glossary words present
  b. links: every relative href resolves to a file, every #anchor has its id; no private ids, emails, tailnet names or IPs;
     no network (no http(s) src / href in the page, no fetch in the js), textContent only
  c. Chromium 390 x 844, dark AND light: no console errors, layout shift 0, no sideways scroll, taps >= 44 px, #sos-8 opens
     card 8, Copy answers, the colour switch sticks after a reload
    python -X utf8 -m tests.test_owner_manual          (MANUAL_NO_BROWSER=1 skips c; run c under flock -w 2400 /tmp/olympus_browser.lock)
    python -X utf8 -m tests.test_owner_manual --shots  (also writes research/handoff/2026-11-20/manual/*.png at deviceScaleFactor 2)
"""
from __future__ import annotations

import functools
import glob
import html.parser
import http.server
import json
import os
import re
import sys
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.page_bg import PAGE_BG_JS, night_black  # noqa: E402  (the effective page background: OLYMPUS NIGHT paints <html>)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
HUB = os.path.join(WEB, "hub")
DOC = os.path.join(ROOT, "docs", "OWNER_MANUAL.md")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-20", "manual")
RES: list = []
PRIVATE = re.compile(r"ts\.net|tailscale\.net|@[A-Za-z0-9-]+\.[a-z]{2,}|dcondax1|demetrades|\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b[A-Z]{3,6}\d{8,}\b|MFFUEVRPD|\bPA-?\d{4,}", re.I)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def rd(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class Parse(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.srcs, self.codes, self.cards = set(), [], [], [], {}
        self._code = None
        self._card = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag in ("script", "link", "img") and (a.get("src") or (tag == "link" and a.get("href"))):
            self.srcs.append(a.get("src") or a.get("href"))
        if tag == "code":
            self._code = ""
        if tag == "details" and (a.get("id") or "").startswith("sos-"):
            self._card = a["id"]
            self.cards[self._card] = 0
        if tag == "li" and self._card:
            self.cards[self._card] += 1

    def handle_endtag(self, tag):
        if tag == "code" and self._code is not None:
            self.codes.append(self._code.strip())
            self._code = None
        if tag == "details":
            self._card = None

    def handle_data(self, d):
        if self._code is not None:
            self._code += d


def part_a(page, doc, p):
    cards = p.cards
    check("a. 10 emergency cards sos-1..sos-10, each 1-3 steps", sorted(cards, key=lambda k: int(k[4:])) == [f"sos-{i}" for i in range(1, 11)]
          and all(1 <= n <= 3 for n in cards.values()), cards)
    check("a. the page has 6 copy lines (4 + hand-trade window, keep-alive status: 2026-11-21)", len(p.codes) == 6, p.codes)
    missing = [c for c in p.codes if c not in doc]
    check("a. every copy line of the page is also in docs/OWNER_MANUAL.md", not missing, missing)
    bad = []
    for c in p.codes:
        m = re.match(r"python -X utf8 -m engine\.(\w+)(.*)$", c)
        if not m:
            bad.append(c)
            continue
        src = os.path.join(ROOT, "engine", m.group(1) + ".py")
        if not os.path.exists(src):
            bad.append(c)
            continue
        code = rd(src)
        for flag in re.findall(r"--[a-z][a-z-]+", m.group(2)):
            if flag not in code:
                bad.append(f"{c} ({flag})")
        if m.group(1) == "accounts" and "status" not in code:
            bad.append(c)
    check("a. every copy line is a real engine module with that flag", not bad, bad)
    bats = sorted(set(re.findall(r"\b([A-Z_]{3,})\.bat\b", page + doc)))
    nob = [b for b in bats if not os.path.exists(os.path.join(ROOT, b + ".bat"))]
    check(f"a. every .bat named exists ({len(bats)})", bats and not nob, nob)
    acc = json.loads(rd(os.path.join(WEB, "business", "accounts.json")))
    names = [a["name"] for a in acc["accounts"]]
    check("a. every account of accounts.json is in the cast", all(n in page for n in ("Zlarior 50K", "ATLAS 25K", "Zlarior 25K #2", "Rapid EOD 25K"))
          and len(names) == 4, names)
    facts = ["$91.80", "$63", "$97.20", "$27,100", "80%", "90%", "30%", "Jan 15, 2027", "02:00-15:30", "16:45-17:00", "05:15-05:30",
             "$2.50", "-$13.75", "I ACCEPT LIVE RISK", "HOLD TO KILL", ":8444/safety/", ":8444/kalshi-live/", "/add-account/", "Limit 0"]
    miss = [f for f in facts if not (f in page and f in doc)]
    check("a. key facts in both the page and the doc (prices, payout, tax, hours, K8, phrases, pages)", not miss, miss)
    # 2026-11-21 landing (lead): New this week = 7 cards, each What / When / 1-3 steps / You see, in the page AND the doc, and every
    # quoted screen text is the code's own
    new = re.findall(r'<details id="new-(\d)"', page)
    check("a. New this week: 7 cards new-1..new-7 (one jump-bar tap: #new), each with What, When, 1-3 steps",
          new == [str(i) for i in range(1, 8)] and '<a href="#new">New</a>' in page and all(f"### N{i}." in doc for i in range(1, 8))
          and all(1 <= c.count("<li>") <= 3 and "<b>What:</b>" in c and "<b>When:</b>" in c for c in re.findall(r'<details id="new-\d".*?</details>', page, re.S)), new)
    said = {   # text the owner reads in the manual -> the file that prints / shows it
        "(LIT + ATLAS): ": "engine/go.py", "Arm and start trading": "web_next/js/next/start.js", "Entry blocked": "engine/guards.py",
        "Left alone (your hand-trade window).": "engine/guards.py", "HEDGE BLOCKED: ATLAS close not confirmed": "engine/live.py",
        "KEEP ALIVE ON": "KEEPALIVE_ON.bat", "[OK] Keep-alive is ON.": "KEEPALIVE_ON.bat", "[OK] Keep-alive is OFF on every account.": "KEEPALIVE_OFF.bat",
        "did not go through": "engine/keepalive.py", "Connected: test delivered": "engine/alerts_box.py", "Olympus alerts are ON": "engine/alerts_box.py",
        "TEST: Zlarior 50K LONG opened": "engine/alert_bus.py", "PAYOUT READY: request": "engine/funded_life.py",
        "WAIT: this is payout": "engine/funded_life.py", "Ask Claude before you request it.": "engine/funded_life.py",
        "Update rolled back": "engine/autoupdate.py", "Update crash loop: ROLLBACK FAILED": "engine/autoupdate.py", "Add to Home Screen": "tools/web_public/hub/setup.html"}
    wrong = [f"{t} ({f})" for t, f in said.items() if t not in rd(os.path.join(ROOT, f)) or t not in page or t not in doc]
    check(f"a. New this week: {len(said)} quoted screen texts are the code's own and in both the page and the doc", not wrong, wrong)
    nfacts = ["$2,100", "$4,100", "$1,000", "$2,000", "-$2.40", "-$22.90", "15:33-15:48 ET", ":8444/alerts/", "5 of 5", "23:00-07:00 ET",
              "START_BOT.bat", "ALERTS_SETUP.bat", "TEST_ALERT.bat", "ALERTS_OFF.bat"]
    nmiss = [f for f in nfacts if not (f in page and f in doc)]
    kp = rd(os.path.join(ROOT, "engine", "funded_life.py"))
    check("a. New this week: payout line $1,000 at $2,100 (25K) / $2,000 at $4,100 (50K), keep-alive cost and window, alerts page, in both",
          not nmiss and '"ask_above": 2000.0' in kp and 'PREFIX = "/alerts"' in rd(os.path.join(ROOT, "engine", "alerts_box.py"))
          and '"scope": "../"' in rd(os.path.join(WEB, "gate", "manifest.webmanifest")), nmiss)
    zh = rd(os.path.join(HUB, "zeus.js"))
    check("a. bot hours = the ZEUS page's (engine/live_board.py)", "02:00-15:30 ET" in zh and "MACD 02:00-05:00 + 09:30-11:00" in zh
          and "EMA 03:00-09:30 (not Mon)" in zh and "S/R 09:30-12:00" in zh)
    srv = rd(os.path.join(ROOT, "server.py"))
    ps = rd(os.path.join(ROOT, "engine", "phone_safety.py"))
    check("a. kill switch as coded: /api/live/kill turns auto-resume off; phone KILL also reaches Kalshi", "@app.post(\"/api/live/kill\")" in srv
          and "_ar.disable(\"kill switch\")" in srv and "kalshi_live.phone_press" in ps and 'PREFIX = "/safety"' in ps)
    check("a. add-account page + Kalshi stop exist", 'PREFIX = "/add-account"' in rd(os.path.join(ROOT, "engine", "account_box.py"))
          and "engine.kalshi_live --stop" in rd(os.path.join(ROOT, "KALSHI_STOP.bat")))
    words = ["Room", "Drawdown", "Floor", "To pass", "Eval / funded", "DLL", "EOD", "Limit 0", "R", "PF", "Win %", "Twin", "Edge check",
             "Circuit breaker", "Sweep", "Stop / target", "MNQ", "Flat", "Armed", "Paper", "PC SILENT", "Kill switch", "Decide card", "ZEUS Lab"]
    gl = page.split('id="words"', 1)[-1]
    gmiss = [w for w in words if f"<dt>{w}" not in gl or f"**{w}" not in doc]
    check(f"a. glossary: {len(words)} words in the page and the doc", not gmiss, gmiss)


def part_b(page, js, css, p):
    bad = []
    for h in p.hrefs:
        if h.startswith(("http://", "https://", "mailto:")):
            bad.append(h)
            continue
        path, _, frag = h.partition("#")
        if not path:
            if frag not in p.ids:
                bad.append(h)
            continue
        f = os.path.normpath(os.path.join(HUB, path.split("?")[0]))
        if path.endswith("/"):
            f = os.path.join(f, "index.html")
        if not os.path.exists(f):
            bad.append(h)
    check(f"b. every link resolves ({len(p.hrefs)} links, anchors included)", not bad, bad)
    check("b. no external file: css / js / icon are local", all(not s.startswith(("http", "//")) for s in p.srcs), p.srcs)
    check("b. manual.js: no fetch / XHR / innerHTML, localStorage in try/catch", not re.search(r"fetch\(|XMLHttpRequest|innerHTML", js)
          and "try {" in js and "localStorage" in js)
    check("b. dark default + light (prefers-color-scheme and the switch)", "prefers-color-scheme: light" in css and ':root[data-mode="light"]' in css)
    check("b. no private ids, emails, tailnet names or IPs (page, css, js, doc)", not PRIVATE.search(page + js + css + rd(DOC)),
          PRIVATE.findall(page + rd(DOC)))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


CLS_JS = """window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({type: 'layout-shift', buffered: true});"""


def part_c(shots: bool):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] c. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/hub/manual.html"
    if shots:
        os.makedirs(SHOTS, exist_ok=True)
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            for scheme in ("dark", "light"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, color_scheme=scheme,
                                     device_scale_factor=2 if shots else 1)
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=204, body=""))
                ctx.add_init_script(CLS_JS)
                errs: list = []
                pg = ctx.new_page()
                pg.set_default_timeout(30000)
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                pg.goto(url)
                pg.wait_for_function("window.OWNER_MANUAL && window.OWNER_MANUAL.ready")
                pg.wait_for_timeout(600)
                bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                lum = sum(int(x) for x in re.findall(r"\d+", bg)[:3]) / 3
                check(f"c. {scheme}: page follows the phone (body {bg})", (lum < 60) if scheme == "dark" else (lum > 200), bg)
                if shots:
                    pg.screenshot(path=os.path.join(SHOTS, f"manual-top-{scheme}.png"))
                pg.click("#sos-8 summary")
                pg.wait_for_timeout(150)
                open8 = pg.evaluate("document.getElementById('sos-8').open")
                pg.click("#sos-8 .mn-copy button")
                pg.wait_for_timeout(200)
                said = pg.text_content("#sos-8 .mn-copy button")
                check(f"c. {scheme}: card 8 opens, Copy answers ({said})", open8 and said in ("Copied", "Selected"), (open8, said))
                if shots:
                    pg.evaluate("document.getElementById('sos-8').scrollIntoView({block: 'start'})")
                    pg.wait_for_timeout(150)
                    pg.screenshot(path=os.path.join(SHOTS, f"manual-kill-{scheme}.png"))
                    for sec in ("cast", "day", "money", "words"):
                        pg.evaluate(f"document.getElementById('{sec}').scrollIntoView({{block: 'start'}})")
                        pg.wait_for_timeout(150)
                        pg.screenshot(path=os.path.join(SHOTS, f"manual-{sec}-{scheme}.png"))
                pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                pg.wait_for_timeout(150)
                wide = pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                small = pg.evaluate("[...document.querySelectorAll('.mn-top a, .mn-mode, .mn-jump a, .mn-copy button, .mn-sos summary, .mn-links a')]"
                                    ".map(e => e.getBoundingClientRect()).filter(r => r.width > 0 && (r.height < 44 || r.width < 44)).length")
                check(f"c. {scheme}: no sideways scroll (all cards open), every tap >= 44 px", wide and small == 0, (wide, small))
                cls = pg.evaluate("window.__cls")
                check(f"c. {scheme}: layout shift 0 ({cls:.4f})", cls < 0.001, cls)
                check(f"c. {scheme}: no console / page errors", not errs, errs)
                ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark")
            pg = ctx.new_page()
            pg.goto(url + "#sos-3")
            pg.wait_for_function("window.OWNER_MANUAL && window.OWNER_MANUAL.ready")
            check("c. manual.html#sos-3 opens card 3", pg.evaluate("document.getElementById('sos-3').open"))
            pg.click("#mode")
            pg.click("#mode")
            pg.reload()
            pg.wait_for_function("window.OWNER_MANUAL && window.OWNER_MANUAL.ready")
            m = pg.evaluate("document.documentElement.getAttribute('data-mode')")
            bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
            check(f"c. switch Auto -> Dark -> Light sticks after a reload on a dark phone ({m}, {bg})", m == "light"
                  and pg.text_content("#mode").strip() == "Light", (m, bg))
            ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark")
            pg = ctx.new_page()
            pg.goto(url)
            pg.wait_for_function("window.OWNER_MANUAL && window.OWNER_MANUAL.ready")
            pg.evaluate("navigator.serviceWorker.ready.then(() => true)")
            pg.wait_for_timeout(500)
            ctx.set_offline(True)
            ok = False
            try:
                pg.reload()
                pg.wait_for_function("window.OWNER_MANUAL && window.OWNER_MANUAL.ready", timeout=8000)
                ok = (pg.text_content("h1") or "").strip() == "Owner manual" and pg.eval_on_selector_all("#sos .mn-sos details", "e => e.length") == 10 and pg.eval_on_selector_all("#new details", "e => e.length") == 7 \
                    and (night_black(bg := pg.evaluate(PAGE_BG_JS)) or "20, 17, 14" in bg)   # the saved look: OLYMPUS NIGHT (the default) or AGORA
            except Exception as e:  # noqa: BLE001
                ok = str(e)[:200]
            check("c. offline: the page, its css and js load from the saved copy (manual-sw.js)", ok is True, ok)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    page, js, css = (rd(os.path.join(HUB, n)) for n in ("manual.html", "manual.js", "manual.css"))
    doc = rd(DOC)
    p = Parse()
    p.feed(page)
    part_a(page, doc, p)
    part_b(page, js, css, p)
    if not os.environ.get("MANUAL_NO_BROWSER"):
        part_c("--shots" in sys.argv)
    n = sum(RES)
    print(f"\nowner_manual: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
