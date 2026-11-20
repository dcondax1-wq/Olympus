"""How do I... (tools/web_public/hub/help.html + help.js + help.json, 2026-11-18, night-help).
  a. the data: 24 questions (add an account, eval passed, payout, phone safety, restart, update, PC silent, Limit 0, accounts, ZEUS Lab,
     taxes, holidays, buy next, Kalshi, Cloudflare, MFFU address check); each 2-4 steps, a "where", at most ONE copy line, a link to a
     page that exists (or https), facts that match the code (prices, the safety line, the payout line, PC_DOCTOR.bat, UPDATE.bat, phrase)
  b. the page: AGORA look, textContent only (no innerHTML), one GET of help.json, no write, no outside script; linked from ZEUS (Help),
     the Doors page, Business, and the More door (olympus/doors.js = web_next copy): find('help') / find('how do I') find it
  c. node, the pure part: filler words skipped ("how do I pause" = pause), every word must match, valid() rules
  d. Chromium 390 x 844 (ntfy routed to an empty answer): 24 cards, typing filters, one hit opens itself, #payout opens that answer,
     Copy button, no sideways scroll, 44 px taps, no page errors
    python -X utf8 -m tests.test_help_page        (HELP_NO_BROWSER=1 skips d; run d only under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
HUB = os.path.join(WEB, "hub")
RES: list = []
WANT = ["add-account", "eval-passed", "payout", "safety", "restart", "update", "pc-silent", "limit-0", "accounts", "lab", "taxes", "holidays",
        "buy-next", "kalshi", "cloudflare", "address-check", "decide", "morning-brief", "weekly-review", "mffu-view", "live-trades",
        "circuit-breaker", "other-markets", "rapid-lit-bank", "steps", "manual"]   # + manual (day-manual 2026-11-20: the owner manual)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return f.read()


def page_exists(href):
    p = href.split("#")[0].split("?")[0]
    full = os.path.normpath(os.path.join(HUB, p))
    return os.path.isfile(os.path.join(full, "index.html")) if p.endswith("/") else os.path.isfile(full)


def part_a():
    data = json.loads(rd(HUB, "help.json"))
    items = data.get("items") or []
    by = {it["id"]: it for it in items}
    check("a. help.json: the 24 questions, in order, ids unique", [it["id"] for it in items] == WANT, [it["id"] for it in items])
    bad = [it["id"] for it in items if not (2 <= len(it.get("steps") or []) <= 4 and it.get("q") and it.get("where") and it.get("words"))]
    check("a. every answer: 2-4 steps, a question, a 'where' (the click or icon), search words", not bad, bad)
    multi = [it["id"] for it in items if not isinstance(it.get("copy", ""), str) or "\n" in it.get("copy", "")]
    check("a. at most ONE copy-paste line each (a string, no newline)", not multi, multi)
    links = [(it["id"], it["link"]["href"]) for it in items if not (it.get("link") or {}).get("label")
             or not (it["link"]["href"].startswith("https://") or page_exists(it["link"]["href"]))]
    check("a. every answer links to the page where it is done (a page in the site, or an https page)", not links, links)
    txt = json.dumps(data)
    check("a. nothing private: no account id, no e-mail, no Tailscale address, no GitHub account name",
          not re.search(r"[\w.-]+@[\w-]+\.\w|\.ts\.net|dcondax|EVBLDR\d|SFBLDR\d|demetrades", txt), re.findall(r"\.ts\.net|dcondax|@\w+\.\w+", txt))
    # the facts, checked against the code / docs they come from
    acc = rd(ROOT, "docs", "NEW_ACCOUNT.md")
    goals = rd(ROOT, "tools", "money", "goals_build.py")
    buy = " ".join(by["buy-next"]["steps"])
    check("a. prices = the owner's CLUB prices (NEW_ACCOUNT.md + goals_build PRICE) and the $150 budget (goals_build BUDGET)",
          all(p in buy for p in ("$63", "$91.80", "$97.20", "$165")) and all(p in acc for p in ("$63", "$91.80", "$97.20", "$165"))
          and "BUDGET = 150.0" in goals and "$150" in buy, buy)
    ps = rd(ROOT, "engine", "phone_safety.py")
    check("a. phone safety: the exact turn-on line of engine/phone_safety.py, /safety/ on the private link, never a link to it",
          by["safety"]["copy"] in ps and 'HOW_ON = "' + by["safety"]["copy"] + '"' in ps and "/safety/" in " ".join(by["safety"]["steps"])
          and "ts.net" not in by["safety"]["link"]["href"], by["safety"])
    pb = rd(ROOT, "docs", "FUNDED_25K_PLAYBOOK.md")
    pay = " ".join(by["payout"]["steps"])
    check("a. payout: $27,100, ask $1,000, 80% = $800, 30% = $240 to the tax pot (FUNDED_25K_PLAYBOOK + payout_coach), the record line",
          all(x in pay for x in ("$27,100", "$1,000", "$800", "$240")) and "$27,100" in pb and "--payout" in by["payout"]["copy"]
          and "pay_max\": 1000.0" in rd(ROOT, "engine", "payout_coach.py") and by["payout"]["link"]["href"].endswith("accounts.html#coach")
          and 'id="coach"' in rd(WEB, "business", "accounts.html"), pay)
    check("a. the .bat files and icons named exist: ADD_ACCOUNT, UPDATE, PC_DOCTOR, START_BOT, STOP_BOT, LIVE_LINK; LE START / LE STOP BOT shortcuts",
          all(os.path.isfile(os.path.join(ROOT, b)) for b in ("ADD_ACCOUNT.bat", "UPDATE.bat", "PC_DOCTOR.bat", "START_BOT.bat", "STOP_BOT.bat", "LIVE_LINK.bat"))
          and "'LE START'" in rd(ROOT, "scripts", "make_shortcuts.ps1") and "'LE STOP BOT'" in rd(ROOT, "scripts", "make_shortcuts.ps1"))
    upd = rd(ROOT, "UPDATE.bat")
    check("a. update: [OK] / [FIX] are UPDATE.bat's own words; the read-only check line exists in engine/autoupdate.py",
          "[FIX]" in upd and "[OK]" in upd and "--source-status" in rd(ROOT, "engine", "autoupdate.py") and "[FIX]" in " ".join(by["update"]["steps"]))
    pcd = rd(ROOT, "docs", "PC_DOCTOR.md")
    check("a. PC silent: PC_DOCTOR.bat, MOST LIKELY CAUSE / NEXT STEP, the doctor page on the PC",
          "MOST LIKELY CAUSE" in pcd and "NEXT STEP" in pcd and by["pc-silent"]["copy"] in pcd and "PC_DOCTOR.bat" in by["pc-silent"]["where"])
    rs = " ".join(by["restart"]["steps"])
    check("a. restart: only flat, 17:00-18:00 ET, STOP then START, the phrase typed by the owner (engine/go.py's own phrase), never a copy line of it",
          "flat" in rs and "17:00-18:00 ET" in rs and "LE STOP BOT" in rs and "I ACCEPT LIVE RISK" in rs and "I ACCEPT LIVE RISK" in rd(ROOT, "engine", "go.py")
          and "ACCEPT" not in by["restart"]["copy"])
    ep = by["eval-passed"]
    onb = rd(ROOT, "engine", "onboard.py")
    check("a. eval passed: MFFU Upgrade, the Start page 'Move ATLAS here (funded)' (engine/onboard.py), the lit25 --funded line, not armed",
          "Upgrade" in " ".join(ep["steps"]) and "here (funded)" in onb and "Move ATLAS here (funded)" in " ".join(ep["steps"])
          and "engine.lit25 --funded" in ep["copy"] and "engine.lit25 --funded" in onb and "NOT armed" in " ".join(ep["steps"]))
    lim = rd(WEB, "trading", "index.html")
    check("a. Limit 0: the Trading page's own help card (16:10-18:00 ET, Active / Failed / Passed) is the link",
          'id="helpCard"' in lim and "16:10" in " ".join(by["limit-0"]["steps"]) and by["limit-0"]["link"]["href"] == "../trading/#helpCard")
    cme = rd(ROOT, "docs", "DAILY_CHECKLIST.md")
    hol = " ".join(by["holidays"]["steps"])
    check("a. holidays: Nov 26 13:00, Nov 27 + Dec 24 13:15, Dec 25 + Jan 1 closed, 15 min / 5 min (DAILY_CHECKLIST Holiday plan)",
          all(x in hol for x in ("Nov 26", "13:00", "13:15", "Dec 25", "Jan 1", "15 min", "5 min")) and "halts 13:00" in cme and "early close 13:15" in cme)
    check("a. taxes: 30% tax pot, Jan 15, 2027 (business/taxes.html); address check: bank statement PDF (goals_build WEEK)",
          "30%" in " ".join(by["taxes"]["steps"]) and "Jan 15, 2027" in " ".join(by["taxes"]["steps"]) and "Jan 15, 2027" in rd(WEB, "business", "taxes.html")
          and "bank statement" in " ".join(by["address-check"]["steps"]) and "bank statement PDF" in goals)
    cf = rd(ROOT, "docs", "HOSTING.md")
    check("a. Cloudflare: the setup line and the site name of docs/HOSTING.md, the key never in a chat",
          by["cloudflare"]["copy"] in cf and "olympus-dash.pages.dev" in " ".join(by["cloudflare"]["steps"]) and "Never paste the key" in " ".join(by["cloudflare"]["steps"]))


def part_b():
    html, js = rd(HUB, "help.html"), rd(HUB, "help.js")
    check("b. AGORA look (agora.css, data-theme agora), title 'How do I', a search box, phone viewport",
          'data-theme="agora"' in html and "../olympus/agora.css" in html and "<title>How do I</title>" in html and 'id="q" type="search"' in html
          and "width=device-width" in html)
    check("b. text only: no innerHTML / outerHTML / insertAdjacentHTML / document.write in help.js",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", js))
    check("b. read only: one GET of help.json, no POST, no localStorage, no outside script",
          js.count("fetch(") == 1 and "fetch('help.json" in js and "POST" not in js and "localStorage" not in js
          and not re.search(r'<script src="https?:', html) and [x for x in re.findall(r'<script src="([^"]+)"', html) if "olympus/warp.js" not in x] == ["help.js?v=8"], re.findall(r'<script src="([^"]+)"', html))   # + the world-to-world jump (olympus/warp.js, tests.test_warp)
    z, dr, biz = rd(HUB, "zeus.html"), rd(HUB, "doors.html"), rd(WEB, "business", "index.html")
    check("b. linked: ZEUS (a Help button), the Doors page (top + bottom), Business (a Help card)",
          '<a href="help.html" id="helpBtn">Help</a>' in z and 'id="helpLink"' in dr and dr.count('href="help.html"') >= 2 and 'href="../hub/help.html"' in biz)
    a, b = rd(WEB, "olympus", "doors.js"), rd(ROOT, "web_next", "js", "next", "doors.js")
    check("b. olympus/doors.js = web_next/js/next/doors.js", a == b)
    script = ("const D = require(process.argv[1]); const L = require(process.argv[2]); const H = require(process.argv[3]); const J = require(process.argv[4]);"
              "const f = (q) => D.find(q, L).items.map((x) => x.item.href);"
              "const g = (q) => H.filter(J.items, q).map((x) => x.id);"
              "console.log(JSON.stringify({ help: f('help'), how: f('how do I'), howp: f('how do i payout'), more: D.door('more').items.map((x) => x.href),"
              " n: D.DOORS.map((d) => d.items.length), arch: L.filter((a) => a.id === 'archive').map((a) => D.words(a).indexOf('rejected') >= 0),"
              " pause: g('how do I pause'), silent: g('pc silent'), pay: g('payout'), none: g('zzzz'), all: g('how do I').length, tax: g('Taxes?'),"
              " valid: J.items.every(H.valid), bad: H.valid({ id: 'x', q: 'q', where: 'w', steps: ['one'], link: { href: 'a', label: 'b' } }),"
              " terms: H.terms('How do I restart my bot?') }));")
    r = subprocess.run(["node", "-e", script, os.path.join(WEB, "olympus", "doors.js"), os.path.join(WEB, "olympus", "apps-list.js"),
                        os.path.join(HUB, "help.js"), os.path.join(HUB, "help.json")], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout)
    except ValueError:
        check("b/c. node loads doors.js + help.js", False, r.stderr[-400:])
        return
    check("b. launcher / Doors search: 'help', 'how do I' and 'how do i payout' find hub/help.html (the More door's shortcut; doors still 5-8 shortcuts)",
          "hub/help.html" in o["help"] and "hub/help.html" in o["how"] and "hub/help.html" in o["howp"] and "hub/help.html" in o["more"]
          and all(5 <= n <= 8 for n in o["n"]) and o["arch"] == [True], o)
    check("c. filler words skipped: 'How do I restart my bot?' -> restart, bot", o["terms"] == ["restart", "bot"], o["terms"])
    check("c. search (best first): 'how do I pause' -> the phone safety answer first; 'pc silent' -> PC silent; 'payout' -> payout first; 'Taxes?' -> taxes; nonsense -> none; empty -> all 26",
          o["pause"][:1] == ["safety"] and o["silent"][:1] == ["pc-silent"] and o["pay"][:1] == ["payout"] and "taxes" in o["tax"] and o["none"] == [] and o["all"] == 26,
          {k: o[k] for k in ("pause", "silent", "pay", "tax", "none", "all")})
    check("c. valid(): every answer of help.json passes; one step only fails", o["valid"] is True and o["bad"] is False, (o["valid"], o["bad"]))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_d():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] d. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/hub/"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=""))
            outside: list = []
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: (outside.append(r.request.url), r.fulfill(status=204, body="")))
            errs: list = []
            p = ctx.new_page()
            p.set_default_timeout(30000)
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(base + "help.html")
            p.wait_for_function("window.HELP_PAGE && window.HELP_PAGE.ready")
            n = p.eval_on_selector_all(".hp-q", "els => els.length")
            cnt = p.text_content("#count")
            check("d. 390 px: 26 question cards, '26 questions'", n == 26 and cnt.strip() == "26 questions", (n, cnt))
            p.fill("#q", "payout")
            vis = p.eval_on_selector_all(".hp-q:not([hidden])", "els => els.map(e => e.id)")
            check("d. typing 'payout' filters the list as you type (payout first, fewer cards)", vis[:1] == ["payout"] and len(vis) < 25, vis)
            p.fill("#q", "how do I pause")
            one = p.evaluate("(() => { const v = [...document.querySelectorAll('.hp-q:not([hidden])')]; return v.map(e => [e.id, e.open]); })()")
            check("d. 'how do I pause' -> the phone safety answer first", one[:1] and one[0][0] == "safety", one)
            p.fill("#q", "pc silent")
            one = p.evaluate("(() => { const v = [...document.querySelectorAll('.hp-q:not([hidden])')]; return v.map(e => [e.id, e.open]); })()")
            check("d. 'pc silent' -> only the PC silent answer, opened by itself", one == [["pc-silent", True]], one)
            p.fill("#q", "zzzz")
            em = p.evaluate("(() => { const e = document.getElementById('empty'); return [e.hidden, e.textContent, e.querySelectorAll('a').length]; })()")
            check("d. nothing found: a plain message + a link to the four doors", em[0] is False and "Nothing found" in em[1] and em[2] == 1, em)
            p.fill("#q", "")
            p.goto(base + "help.html#payout")
            p.wait_for_function("window.HELP_PAGE && window.HELP_PAGE.ready")
            pay = p.evaluate("(() => { const e = document.getElementById('payout'); const go = e.querySelector('a.hp-go'); const c = e.querySelector('.hp-copy button');"
                             " return { open: e.open, steps: e.querySelectorAll('.hp-steps li').length, go: go && go.getAttribute('href'), copy: !!c,"
                             " code: (e.querySelector('.hp-copy code') || {}).textContent }; })()")
            check("d. #payout opens that answer: 4 steps, the copy line + Copy button, 'Open: Payout coach' link",
                  pay["open"] and pay["steps"] == 4 and pay["go"] == "../business/accounts.html#coach" and pay["copy"] and "--payout" in str(pay["code"]), pay)
            p.click("#payout .hp-copy button")
            p.wait_for_timeout(200)
            btn = p.text_content("#payout .hp-copy button")
            p.evaluate("document.querySelectorAll('.hp-q').forEach(d => d.open = true)")
            wide = p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            small = p.evaluate("[...document.querySelectorAll('.hp-nav a, .hp-q summary, .hp-copy button, a.hp-go, .hp-links a')]"
                               ".map(e => e.getBoundingClientRect()).filter(r => r.width > 0 && (r.height < 44 || r.width < 44)).length")
            check("d. Copy answers (Copied / Selected), every answer open: no sideways scroll, every tap >= 44 px",
                  btn in ("Copied", "Selected") and wide and small == 0, (btn, wide, small))
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errs.append(str(e)))
            p2.goto(base + "zeus.html")
            hb = p2.evaluate("(() => { const a = document.getElementById('helpBtn'); const r = a.getBoundingClientRect(); return [a.getAttribute('href'), Math.round(r.height), "
                             "document.documentElement.scrollWidth <= window.innerWidth + 1]; })()")
            check("d. ZEUS page: the Help button (44 px, no sideways scroll)", hb[0] == "help.html" and hb[1] >= 44 and hb[2], hb)
            check("d. no page errors, nothing fetched off the site", not errs and not [u for u in outside if "ntfy.sh" not in u], (errs, outside))
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    if not os.environ.get("HELP_NO_BROWSER"):
        part_d()
    n = sum(RES)
    print(f"\nhelp_page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
