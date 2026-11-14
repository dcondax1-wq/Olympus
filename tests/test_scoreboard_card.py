"""The Ledger's Scoreboard card (tools/web_public/ledger/scoreboardcore.js + ledger.js scoreCard, 2026-11-13): the site's money/scoreboard.json
(tools/money_scoreboard.py) shown in AGORA style on the Overview tab: week / month / all-time tiles, ROI, run-rate, the next milestone and ETA,
each source's net, paper results (never cash), every source's status chip and age, the missing ones listed.
  a. static: the core is pure (no DOM, no fetch, no innerHTML), the page reads the file with GET only and writes it only as text
  b. the core in node: view() on a real scoreboard, on nothing and on junk; money words; ages
  c. the page in Chromium at 390 x 844: the card with a file, without one, with junk; inside the 16 px gutters; nothing leaves the page
    python -X utf8 -m tests.test_scoreboard_card            (SC_NO_BROWSER=1 skips c; run the browser part under the shared lock:
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_scoreboard_card)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import money_scoreboard as MS  # noqa: E402
from tests import test_ledger_page as LP  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "ledger")
CORE = os.path.join(PAGE, "scoreboardcore.js")
HOME_REAL = os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def scoreboard(now):
    home = json.load(open(HOME_REAL, encoding="utf-8"))
    feed = {"v": 3, "kind": "kalshi", "t": now - 300, "balance": 55.81, "total_pnl": -81.77, "days": [[MS.today_et(now), -1.5]]}
    return MS.build({"home": home, "home_file": "home.json", "kalshi": feed, "kalshi_file": "kalshi.json",
                     "rules": json.load(open(os.path.join(PAGE, "rules.json"), encoding="utf-8")),
                     "plans": json.load(open(os.path.join(WEB, "plutus", "plans.json"), encoding="utf-8"))}, now)


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    core = open(CORE, encoding="utf-8").read()
    js = open(os.path.join(PAGE, "ledger.js"), encoding="utf-8").read()
    check("a. the core is pure: no DOM, no fetch / XHR / storage, no innerHTML, no import", not re.search(r"document\.|window\.|fetch\(|XMLHttpRequest|localStorage|innerHTML|^import ", core, re.M))
    check("a. ledger.js imports the core, reads ../money/scoreboard.json with its GET helper, checks its kind, and builds the card with textContent only",
          "import * as SB from './scoreboardcore.js'" in js and "getJSON('../money/scoreboard.json')" in js and "SB.ok(score)" in js and "function scoreCard()" in js
          and "out.push(scoreCard())" in js and not re.search(r"innerHTML|insertAdjacentHTML", js))
    html = open(os.path.join(PAGE, "index.html"), encoding="utf-8").read()
    check("a. the page's own files carry a new version (ledger.js / ledger.css ?v=s1) so the phone fetches the new card", "ledger.js?v=s1" in html and "ledger.css?v=s2" in html)
    check("a. AGORA: the card reuses the page's glass card, the AGORA number tiles (.snap / .ag-money) and chips; no neon, glow or techno font in the new CSS",
          ".sbsrc" in open(os.path.join(PAGE, "ledger.css"), encoding="utf-8").read() and not re.search(r"text-shadow|Orbitron|Rajdhani|#0ff|cyan", open(os.path.join(PAGE, "ledger.css"), encoding="utf-8").read().split("Scoreboard card")[-1]))


# ------------------------------------------------------------------------------------------------ b. the core in node
def part_b():
    now = time.time()
    sb = scoreboard(now)
    tmp = tempfile.mkdtemp(prefix="sc_core_")
    try:
        p = os.path.join(tmp, "sb.json")
        json.dump(sb, open(p, "w", encoding="utf-8"))
        js = ("import fs from 'fs'; import * as V from " + json.dumps("file://" + CORE) + ";"
              "const sb = JSON.parse(fs.readFileSync(" + json.dumps(p) + ", 'utf8')); const now = " + str(now + 120) + ";"
              "const out = { v: V.view(sb, now), none: V.view(null, now), junk: V.view({ kind: 'x', totals: 3 }, now), half: V.view({ kind: V.KIND, totals: { all: { net: 5 } } }, now),"
              " words: [V.usd(1234.4), V.usd(-5), V.usd(5, true), V.usd(0, true), V.usd(null), V.ageWords(59), V.ageWords(3 * 3600 + 120), V.ageWords(2 * 86400 + 3600)], tone: [V.tone(10), V.tone(-10), V.tone(0.2), V.tone(null)] };"
              "console.log('@@' + JSON.stringify(out));")
        r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, timeout=60)
        line = [x for x in r.stdout.splitlines() if x.startswith("@@")]
        if not line:
            check("b. the core runs in node", False, r.stderr[-400:])
            return
        o = json.loads(line[-1][2:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    v = o["v"]
    T = sb["totals"]
    check("b. three tiles (this week, this month, net cash all time) with the scoreboard's own numbers, signed", v["ok"] and [t["k"] for t in v["tiles"]] == ["This week", "This month", "Net cash, all time"]
          and v["tiles"][2]["v"] == MS.money(T["all"]["net"], True) and v["tiles"][2]["cls"] == "neg", v["tiles"])
    rows = {r[0]: r[1] for r in v["rows"]}
    check("b. rows: ROI on eval fees (-100%: fees, no payout), run-rate 'too early', the plan estimate ($1,290 a month, not cash), the next milestone $10,000 and its ETAs",
          rows.get("ROI on eval fees") == "-100%" and (rows.get("Run-rate (real cash)") == "too early" or rows.get("Run-rate (real cash)", "").endswith("a month"))
          and rows.get("Plan estimate (not cash)") == "$1,290 a month" and "Next milestone $10,000" in rows and "ETA at the plan estimate" in rows, rows)
    names = [r[0] for r in v["bySource"]]
    check("b. by source: each eval account (with its paper line), Kalshi (real money); paper ones (BLITZ, second strategies) in their own list",
          any("50K" in n for n in names) and any("ATLAS" in n for n in names) and "Kalshi bot (real money)" in names and any("not cash" in r[3] for r in v["bySource"])
          and any("BLITZ" in p[0] for p in v["paper"]) and any("Second" in p[0] for p in v["paper"]), (names, v["paper"]))
    st = {s["name"]: s for s in v["sources"]}
    check("b. every source with a status chip and an age: the old PC report is 'old' (warn), the ledger and money machines 'missing' (bad, 'not found'), Kalshi ok with minutes",
          st["NQ accounts (eval / funded, paper P&L)"]["status"] == "old" and st["NQ accounts (eval / funded, paper P&L)"]["chip"] == "warn"
          and st["Your ledger (payouts, deposits, fees)"]["status"] == "missing" and st["Your ledger (payouts, deposits, fees)"]["age"] == "not found"
          and st["Kalshi bot (real money)"]["status"] == "ok" and st["Kalshi bot (real money)"]["age"].endswith("minutes ago"), st)
    check("b. the missing line names them and says nothing is made up; the foot says paper only and that the PC ledger is not in the public copy",
          v["missing"].startswith("Missing: ") and "Nothing is made up" in v["missing"] and "Paper only" in v["foot"] and "not in this public copy" in v["foot"], (v["missing"], v["foot"]))
    check("b. no file, junk, or a file of another kind -> not ok, with the plain 'not on the site yet' text; a half file still works (no crash, dashes)",
          not o["none"]["ok"] and not o["junk"]["ok"] and "not on the site yet" in o["none"]["text"] and o["half"]["ok"] and o["half"]["tiles"][0]["v"] == "-", o["half"])
    check("b. money words and ages: $1,234 / -$5 / +$5 / $0 / '-'; 'less than a minute', '3 hours 2 minutes', '2 days 1 hour'; tones",
          o["words"] == ["$1,234", "-$5", "+$5", "$0", "-", "less than a minute", "3 hours 2 minutes", "2 days 1 hour"] and o["tone"] == ["pos", "neg", "dim", "dim"], o["words"])


# ------------------------------------------------------------------------------------------------ c. the page
def part_c():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="sc_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(LP.Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}/nq-dashboard/ledger/"
    outside = []
    shots = os.environ.get("SC_SHOTS")

    def site(score):
        s = LP.make_site(tmp, home=True)
        if score is not None:
            os.makedirs(os.path.join(s, "money"), exist_ok=True)
            with open(os.path.join(s, "money", "scoreboard.json"), "w", encoding="utf-8") as fh:
                fh.write(score if isinstance(score, str) else json.dumps(score))
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def open_():
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, reduced_motion="reduce")
                ctx.add_init_script("try { if (!localStorage.getItem('jfx')) localStorage.setItem('jfx', 'low'); } catch (e) {}")

                def guard(route):
                    u = route.request.url
                    if u.startswith(f"http://127.0.0.1:{port}") or u.startswith(("data:", "blob:")):
                        return route.continue_()
                    if not u.startswith(LP.RAW_PREFIX):
                        outside.append(u)
                    return route.abort()
                ctx.route("**/*", guard)
                p = ctx.new_page()
                p.set_default_timeout(40000)
                p.errs, p.posts = [], []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and p.errs.append(m.text))
                p.on("request", lambda r: r.method != "GET" and p.posts.append(r.url))
                p.goto(base + "?today=" + MS.today_et(time.time()))
                p.wait_for_function("document.body.dataset.ready === '1' && window.LG && LG.state().scene && LG.state().scene.drawn > 0", timeout=240000)
                return ctx, p

            now = time.time()
            site(scoreboard(now))
            ctx, p = open_()
            card = p.locator("#p-over #score")
            txt = card.inner_text() if card.count() else ""
            check("c. with the file: the Scoreboard card is on the Overview, right after the three numbers, titled 'Scoreboard: every money source'",
                  card.count() == 1 and p.evaluate("(() => { const c = [...document.querySelectorAll('#p-over > article.card')]; return c.indexOf(document.getElementById('score')); })()") == 1
                  and p.inner_text("#score h2") == "Scoreboard: every money source", txt[:200])
            check("c. ... three tiles (week, month, net cash all time), ROI on eval fees, the run-rate, the next milestone and its ETA at the plan estimate",
                  p.locator("#score .snapt").count() == 3 and "Net cash, all time" in txt and "ROI on eval fees" in txt and "Run-rate (real cash)" in txt
                  and "Next milestone $10,000" in txt and "ETA at the plan estimate" in txt, txt[:600])
            check("c. ... by source with each eval account and Kalshi; paper results under 'On paper (not cash)'; every source with a chip and its age; the missing line",
                  "By source (cash)" in txt and "Kalshi bot (real money)" in txt and "On paper (not cash)" in txt and p.locator("#score .sbsrc li").count() >= 7
                  and p.locator("#score .sbsrc .chip.bad").count() >= 1 and "minutes ago" in txt and "Missing: " in txt, txt[-900:])
            ov = p.evaluate(LP.GEOM)
            check("c. ... at 390 x 844 inside the 16 px gutters, no sideways scroll; no page error; only GET requests, nothing outside the site", not ov and not p.errs and not p.posts and not outside, (ov[:5], p.errs[:3], p.posts[:3], outside[:3]))
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.evaluate("document.getElementById('score').scrollIntoView()")
                p.screenshot(path=os.path.join(shots, "scoreboard_card.png"), full_page=False)
            ctx.close()
            for label, score in (("no file", None), ("junk", "{not json"), ("another kind", {"kind": "other", "totals": {"all": {"net": 99999}}})):
                site(score)
                ctx, p = open_()
                t = p.inner_text("#score") if p.locator("#score").count() else ""
                check(f"c. {label}: the card says the scoreboard is not on the site yet, invents nothing, no page error, the rest of the Ledger is as before",
                      "not on the site yet" in t and "99,999" not in t and not p.errs and p.is_visible("#net") and p.locator("#p-over article.card").count() >= 3, (t[:200], p.errs[:3]))
                ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_b()
    if os.environ.get("SC_NO_BROWSER") != "1":
        part_c()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
