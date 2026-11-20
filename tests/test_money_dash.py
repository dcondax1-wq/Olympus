"""Money dashboards (night-revamp-dash 2026-11-20): tools/money/dash_build.py -> business/dash.json + business/dashkit.js on the
Money pages (Goals, Accounts, Week, Lab, Business home).
  a. build     dash.json rebuilds from the repo's research files, < 60 KB; every block says BACKTEST / ESTIMATE and its date;
               the equity curve ends at the 2026 YTD net; the best / worst trade are the max / min of the 2026 trades
  b. pages     each page loads dashkit.css + dashkit.js (+ the widget lib where a live cockpit is); dashkit builds no markup from
               data (no innerHTML), sends nothing (no POST)
  c. browser   (skipped with --fast) at 390x844 every [data-dash] card draws (.dk-in, no "could not draw"), the cockpit shows the
               fixture PC post as LIVE with 3 accounts, no console error, no sideways scroll, tags on every card
    python -X utf8 -m tests.test_money_dash [--fast]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import http.server
import functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
FIX = os.path.join(ROOT, "tests", "fixtures", "widget")
RES: list = []
PAGES = {"goals.html": ["cockpit", "payday", "fan"], "accounts.html": ["cockpit", "payday"], "week.html": ["edge", "months", "equity", "trades"],
         "lab.html": ["labboard"], "index.html": ["cockpit"]}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def part_a():
    from tools.money import dash_build as DB
    d = DB.build()
    raw = json.dumps(d, separators=(",", ":"))
    check("a. builds, under 60 KB", len(raw) < DB.MAX_BYTES, len(raw))
    check("a. every block labelled with its kind and date", d["edge"]["label"] == "BACKTEST" and d["backtest"]["label"] == "BACKTEST"
          and d["plan"]["label"] == "ESTIMATE" and d["edge"]["built"] and d["backtest"]["built"] and d["plan"]["built"])
    bt = d["backtest"]
    ytd = (bt["periods"].get("2026 YTD") or {}).get("net")
    check("a. the 2026 equity curve ends at the 2026 YTD net (within $5)", bt["equity_2026"] and ytd is not None and abs(bt["equity_2026"][-1][1] - ytd) <= 5,
          (bt["equity_2026"][-1:], ytd))
    trades = [t for t in json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json")))["trades"] if str(t.get("day", "")).startswith("2026")]
    pn = [t["pnl"] for t in trades]
    check("a. best / worst trade = the max / min 2026 trade", round(max(pn)) == bt["best"]["pnl"] and round(min(pn)) == bt["worst"]["pnl"], (bt["best"], bt["worst"]))
    s = bt["stats_2026"]
    check("a. wins + losses + flat = trades", s["wins"] + s["losses"] + s["flat"] == s["n"] == len(trades), s)
    check("a. edge series has the light letter per day", all(len(x) == 3 and x[2] in "GAR?" for x in d["edge"]["series"]) and len(d["edge"]["series"]) > 50)
    check("a. plan: payout dates for the accounts in the money plan", any(a.get("first_pay") for a in d["plan"]["by_market"]["H2"]["accounts"]))
    committed = json.loads(read(os.path.join(BIZ, "dash.json")))
    check("a. the committed dash.json has the same blocks", all(k in committed for k in ("edge", "backtest", "plan")))


def part_b():
    js = read(os.path.join(BIZ, "dashkit.js"))
    check("b. dashkit.js: no innerHTML / insertAdjacentHTML", not re.search(r"innerHTML|insertAdjacentHTML|document\.write", js))
    check("b. dashkit.js: read only (no POST)", not re.search(r"POST", js))
    for page, kinds in PAGES.items():
        h = read(os.path.join(BIZ, page))
        have = re.findall(r'data-dash="(\w+)"', h)
        ok = have == kinds and "dashkit.css" in h and "dashkit.js" in h and (("olympus-widget.js" in h) == ("cockpit" in kinds))
        check(f"b. {page}: cards {kinds}, kit loaded", ok, have)


def part_c():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [SKIP] c. no playwright")
        return
    web = os.path.join(ROOT, "tools", "web_public")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=web)
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}/business/"
    lite, home = read(os.path.join(FIX, "lite.ndjson")), read(os.path.join(FIX, "home.json"))
    with sync_playwright() as p:
        try:
            br = p.chromium.launch()
        except Exception:                       # noqa: BLE001 - the sandbox's own chromium
            br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = br.new_context(viewport={"width": 390, "height": 844})
        ctx.route(re.compile(r"ntfy\.sh"), lambda r: r.fulfill(body=lite, content_type="application/x-ndjson", headers={"access-control-allow-origin": "*"}))
        ctx.route(re.compile(r"/home\.json"), lambda r: r.fulfill(body=home, content_type="application/json"))
        for page, kinds in PAGES.items():
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "404" not in m.text and "Failed to load" not in m.text else None)
            pg.goto(base + page, wait_until="domcontentloaded")
            try:
                pg.wait_for_function(f"() => document.querySelectorAll('[data-dash].dk-in').length === {len(kinds)}", timeout=20000)
            except Exception:                   # noqa: BLE001 - reported below
                pass
            r = pg.evaluate("""() => ({ n: document.querySelectorAll('[data-dash].dk-in').length,
                bad: [...document.querySelectorAll('[data-dash]')].filter(b => /could not draw|not here yet/.test(b.innerText)).map(b => b.dataset.dash),
                tags: [...document.querySelectorAll('[data-dash]')].every(b => b.querySelector('.dk-tag')),
                live: (document.querySelector('[data-dash=cockpit] .dk-head .dk-tag') || {}).textContent || '',
                accts: document.querySelectorAll('[data-dash=cockpit] .dk-acct').length,
                hs: document.documentElement.scrollWidth > innerWidth + 1 })""")
            check(f"c. {page}: every card drew, each with its tag", r["n"] == len(kinds) and not r["bad"] and r["tags"], r)
            if "cockpit" in kinds:
                check(f"c. {page}: the cockpit = the PC post (LIVE, or STALE once the fixture is old), 3 accounts", r["live"].startswith(("LIVE", "STALE")) and r["accts"] == 3, r)
            check(f"c. {page}: no console error, no sideways scroll", not errs and not r["hs"], (errs, r["hs"]))
            pg.close()
        br.close()
    srv.shutdown()


def main() -> int:
    part_a()
    part_b()
    if "--fast" not in sys.argv:
        part_c()
    print(f"{sum(RES)} passed, {len(RES) - sum(RES)} failed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
