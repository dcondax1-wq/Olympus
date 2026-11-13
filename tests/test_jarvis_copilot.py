"""Jarvis money copilot (J1, 2026-11-13): tools/web_public/jarvis/copilot.js (the answers), copilot-card.js (the home card) and their wiring
(skills.js asks the copilot right after the safety guard; jdata.js loads fates/jarvis.json; index.html mounts #hcopilot). Checks:
  a. the files: copilot.js parses as an ES module, Safari 16 safe, no DOM, no fetch, no absolute URL, no key, no order words, imports only
     ./jdata.js and ../olympus/truth.js; copilot-card.js the same rules for the page side (fetch only through jdata.js); index.html has the
     mount and the versioned module tag; skills.js loads copilot.js lazily (a missing file = the older answers)
  b. tests/test_jarvis_copilot.mjs in node (TZ America/New_York): 50+ phrasings and the ones it must leave alone, GO / CAREFUL / SIT OUT on
     normal / news / holiday / weekend / late / stale-PC / low-room / daily-loss days, the loss budget, P&L with best / worst / win rate / $ a
     month, pass odds, what changed (with and without yesterday's snapshot), Kalshi's day, the 01:45 / 10:45 / 16:05 cards, junk, the wiring
  c. Chromium (one page, under flock /tmp/olympus_browser.lock): the real Jarvis page over the real site files with a fixture home.json and
     kalshi.json, the clock fixed: the 01:45 card at 02:10 ET, the 16:05 card at 16:20 ET, a tap on a card line asks Jarvis and the answer
     names its sources; typed questions answer from the copilot; 375 px wide: no sideways scroll, every line >= 44 px; ?demo=1 is labelled;
     no page error; nothing leaves the machine
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_jarvis_copilot      (~1 min)
"""
from __future__ import annotations

import datetime as dt
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from zoneinfo import ZoneInfo

from tests import browser_kit as BK  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WP = os.path.join(ROOT, "tools", "web_public")
JV = os.path.join(WP, "jarvis")
RES: list = []
NY = ZoneInfo("America/New_York")


def check(name, ok, info=""):
    RES.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def code(src):
    """the source without // comments (a URL in a comment is not a fetch)"""
    return re.sub(r"(^|[^:'\"\\])//[^\n]*", r"\1", src)


# ------------------------------------------------------------------------------------------------ a. the files
def part_a():
    cp, card, sk, jd, page = read(JV, "copilot.js"), read(JV, "copilot-card.js"), read(JV, "skills.js"), read(JV, "jdata.js"), read(JV, "index.html")
    for name, src in (("copilot.js", cp), ("copilot-card.js", card)):
        r = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
        check(f"a. {name} parses as an ES module", r.returncode == 0, r.stderr[-400:])
        check(f"a. {name} is Safari 16 safe (no regex lookbehind, no optional chaining)", not re.search(r"\(\?<[=!]", src) and "?." not in code(src).replace("'?.'", ""))
        check(f"a. {name}: no key, no absolute URL, no order / arming words", not re.search(r"gsk_[A-Za-z0-9]{8}|AIza[A-Za-z0-9]{8}|github_pat_|sk-ant-|https?://", code(src))
              and not re.search(r"place_?order|submitOrder|armLive|go_live|\.arm\(", src))
    imports = re.findall(r"^import [^;]* from '([^']+)';", cp, re.M)
    check("a. copilot.js imports only ./jdata.js and ../olympus/truth.js (the one source of account numbers)", sorted(imports) == ["../olympus/truth.js", "./jdata.js"], imports)
    check("a. copilot.js: no DOM, no fetch, no eval", not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\beval\(|new Function", code(cp)))
    check("a. copilot.js reads the accounts through truth.js accountsOf / agesOf", "accountsOf(h)" in cp and "agesOf(h, now / 1000)" in cp)
    check("a. copilot-card.js fetches only through jdata.js loadSources (relative files) and asks the brain's skills first",
          "J.loadSources({ fetch:" in card and "sk.card()" in card and not re.search(r"fetch\(\s*['\"]", card))
    check("a. copilot-card.js: a tap asks Jarvis (data-say), nothing opens or acts by itself", 'data-say="' in card and "data-app" not in card)
    check("a. skills.js: the copilot is loaded lazily and asked right after the safety guard, before the v3 skills and the router",
          "import('./copilot.js')" in sk and "const g = v3.guard(text); if (g) return g;" in sk and sk.find("copilotAsk(text, now)") < sk.find("return v3.early(text, now);") and "early: (raw, opt) => early(raw" in sk)
    check("a. jdata.js loads fates/jarvis.json (Fates' pass odds) with the other files", "fatesCard: '../fates/jarvis.json'" in jd and "Object.keys(XFILES)" in jd)
    check("a. index.html: #hcopilot above #htoday and the versioned module tag", page.find('id="hcopilot"') > 0 and page.find('id="hcopilot"') < page.find('id="htoday"')
          and re.search(r'<script type="module" src="\./copilot-card\.js\?v=cp\d+"></script>', page))
    doc = read(ROOT, "docs", "JARVIS_API.md")
    miss = [n for n in ("copilot.js", "copilot-card.js", "jarvis.copilot.v1", "createCopilot", "cardFor", "GO / CAREFUL / SIT OUT", "#hcopilot", "fates/jarvis.json") if n not in doc]
    check("a. docs/JARVIS_API.md documents the copilot (module, card, storage key, wiring)", not miss, miss)


# ------------------------------------------------------------------------------------------------ b. node
def part_b():
    r = subprocess.run(["node", os.path.join(ROOT, "tests", "test_jarvis_copilot.mjs")], capture_output=True, text=True, timeout=180, env={**os.environ, "TZ": "America/New_York"})
    out = (r.stdout + r.stderr).strip()
    m = re.search(r"(\d+) passed, (\d+) failed", out)
    check("b. node: phrasings, verdicts, loss budget, P&L, pass odds, what changed, Kalshi, cards, junk, wiring", r.returncode == 0 and m and int(m.group(1)) >= 140, out[-1500:])
    if m:
        print(f"   node unit tests: {m.group(1)} passed, {m.group(2)} failed")


# ------------------------------------------------------------------------------------------------ c. Chromium
def fixture_home(now_s):
    T = int(now_s)
    return {"built": dt.datetime.fromtimestamp(T - 300, dt.timezone.utc).isoformat(), "home_only": True,
            "live": {"pc": {"t": T - 240, "present": True, "running": True, "mind": {"plans": {"lit": {"t": T - 600, "headline": "Zlarior game plan for today: structure favours longs"}}}},
                     "notices": [{"t": T - 3600, "kind": "outcome", "title": "Zlarior closed +$27"}]},
            "accounts": [],
            "board": {"t": T - 300, "data_t": T - 240, "running": True,
                      "lit": {"room": 1133, "mll": 2000, "balance": 49133, "to_target": 3867, "target_balance": 53000, "profit": -867, "today_pnl": 27, "week_pnl": -410,
                              "dll": 1000, "dll_used": 0, "status": "open", "quiet_days": 2, "trades_today": 0, "max_day": 1, "micros": {"qty": 3, "risk_usd": 450, "win_usd": 1800}},
                      "atlas": {"room": 746, "mll": 1000, "balance": 24746, "to_target": 1754, "profit": -254, "today_pnl": 0, "week_pnl": 0, "status": "open"},
                      "progress": {"lit": {"session": 6, "sessions": 10, "sessions_left": 4, "odds": {"rows": {"H2": {"p10": 58.6, "f10": 20.9, "pass_med": 9}}},
                                           "expected": {"per_month": 2670, "trades_per_week": 2.6}, "actual": {"per_month_pace": -3035}}},
                      "real": {"trades": [{"acct": "lit", "src": "live", "day": "2026-11-13", "entry_t": T - 9000, "side": "LONG", "qty": 3, "usd": 27, "r": 0.06},
                                          {"acct": "lit", "src": "live", "day": "2026-11-10", "entry_t": T - 300000, "side": "SHORT", "qty": 3, "usd": 1350, "r": 3}]},
                      "trades": [], "blocks": [], "lines": []}}


def fixture_kalshi(now_s):
    T = int(now_s)
    return {"t": T - 120, "mode": "live", "running": True, "status": "Running", "balance": 61.4, "today_pnl": 4.1, "week_pnl": -3.3, "total_pnl": -75,
            "positions": [{"title": "BTC above 98k", "side": "yes", "contracts": 10, "avg_price": 92}], "trades": [{"t": T - 3000, "pnl": 4.1, "title": "BTC hourly"}]}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def run_browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("c. playwright available", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WP))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)

            def page(at, width=390, q=""):
                ctx = br.new_context(viewport={"width": width, "height": 844}, device_scale_factor=1, service_workers="block")
                now_s = at.timestamp()
                seen = []
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())            # nothing leaves the machine
                ctx.route(re.compile(r"/home\.json(\?.*)?$"), lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(fixture_home(now_s))))
                ctx.route(re.compile(r"/kalshi\.json(\?.*)?$"), lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(fixture_kalshi(now_s))))
                ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.speak', 'off'); } catch (e) {}")
                ctx.clock.set_fixed_time(at)
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.on("request", lambda r: seen.append(r.url))
                p.goto(url + "jarvis/" + q)
                p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000, polling=200)
                p.wait_for_function("(() => { const c = document.getElementById('hcCopilot'); return c && c.querySelectorAll('.hc-row').length >= 2; })()", timeout=60000, polling=200)
                return ctx, p, errs, seen

            def ask(p, q):
                p.evaluate("document.getElementById('talk').innerHTML = ''")
                p.fill("#q", q)
                p.press("#q", "Enter")
                p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=20000)
                return p.locator(".msg.j").first.inner_text()

            # 02:10 ET Friday: the 01:45 morning plan
            ctx, p, errs, seen = page(dt.datetime(2026, 11, 13, 2, 10, tzinfo=NY))
            c = p.evaluate("(() => { const c = document.getElementById('hcCopilot'); return { slot: c.dataset.slot, kind: c.dataset.kind, h: c.querySelector('h2').innerText, rows: [...c.querySelectorAll('.hc-row')].map((b) => [b.innerText, b.dataset.say]), foot: (c.querySelector('.hc-age') || {}).innerText || '' }; })()")
            check("c. 02:10 ET: the Morning plan card (slot 01:45) with its verdict chip, the accounts' loss budget, Kalshi and the foot with file ages",
                  c["slot"] == "01:45" and c["kind"] == "morning" and c["h"].startswith("Morning plan") and re.search(r"GO|CAREFUL|SIT OUT", c["h"])
                  and any("can lose $1,000 today" in r[0] for r in c["rows"]) and any(r[0].startswith("Kalshi: +$4.10 today") for r in c["rows"])
                  and "home.json" in c["foot"] and "ago" in c["foot"], c)
            check("c. every card line asks a question", all(r[1] for r in c["rows"]), c["rows"])
            top = p.locator("#hcCopilot .hc-row").first
            top.scroll_into_view_if_needed()
            top.click()
            p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=20000)
            a = p.locator(".msg.j").first.inner_text()
            check("c. a tap on the card's first line asks 'Should I trade today?' and Jarvis answers GO / CAREFUL / SIT OUT with its sources",
                  re.match(r"^(GO|CAREFUL|SIT OUT):", a) and "From home.json" in a and "not an order" in a, a[:600])
            a = ask(p, "how much can I lose today")
            check("c. typed 'how much can I lose today': per account, today and before the eval fails", "Zlarior 50K: today $1,000 before the daily limit" in a and "$1,133 before the eval fails" in a and "From home.json" in a, a[:600])
            a = ask(p, "how close am I to passing")
            check("c. typed 'how close am I to passing': $ to go, wins needed, the published odds", "$3,867 to go" in a and "3 winning trades" in a and "58.6% pass within 10 sessions" in a, a[:600])
            a = ask(p, "kalshi exposure today")
            check("c. typed 'kalshi exposure today': today, settled bets, $ at risk", "Kalshi today: +$4.10" in a and "$9 at risk" in a, a[:600])
            check("c. no page error; every request stays on the local site", not errs and all(u.startswith(url) or u.startswith("data:") or u.startswith("blob:") for u in seen), (errs[:3], [u for u in seen if not u.startswith(url)][:5]))
            ctx.close()
            # 16:20 ET Friday: the 16:05 day summary, at 375 px
            ctx, p, errs, _ = page(dt.datetime(2026, 11, 13, 16, 20, tzinfo=NY), width=375)
            c = p.evaluate("(() => { const c = document.getElementById('hcCopilot'); return { slot: c.dataset.slot, h: c.querySelector('h2').innerText, rows: [...c.querySelectorAll('.hc-row')].map((b) => [b.innerText, Math.round(b.getBoundingClientRect().height)]), sx: document.documentElement.scrollWidth - document.documentElement.clientWidth }; })()")
            check("c. 16:20 ET: the Day summary (slot 16:05) with today's $ per account and the trade", c["slot"] == "16:05" and c["h"].startswith("Day summary") and "+$27" in c["h"]
                  and any(r[0].startswith("Zlarior 50K: +$27 today; drawdown left $1,133 of $2,000") for r in c["rows"]) and any(r[0].startswith("1 trade today") for r in c["rows"]), c)
            check("c. 375 px: no sideways scroll and every card line is at least 44 px tall", c["sx"] <= 0 and all(r[1] >= 44 for r in c["rows"]), c)
            check("c. no page error at 16:20", not errs, errs[:3])
            ctx.close()
            # ?demo=1: example numbers, labelled
            ctx, p, errs, _ = page(dt.datetime(2026, 11, 13, 9, 0, tzinfo=NY), q="?demo=1")
            k = p.evaluate("document.querySelector('#hcCopilot .cp-k').innerText")
            check("c. ?demo=1: the card says its numbers are examples", "example" in k.lower(), k)
            ctx.close()
    finally:
        srv.shutdown()


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False, "node not found")
        return 1
    part_a()
    part_b()
    if os.environ.get("COPILOT_NO_BROWSER") != "1":
        run_browser()
    bad = [n for n, ok in RES if not ok]
    print(f"\njarvis copilot: {len(RES) - len(bad)}/{len(RES)} {'ALL PASS' if not bad else 'FAILED: ' + '; '.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
