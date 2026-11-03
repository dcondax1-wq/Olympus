"""The Kalshi page (tools/web_public/kalshi/, owner 2026-11-01): the dashboard of the Kalshi bot's kalshi.json (contract:
engine/kalshi_publish.py; v2 adds `strategies` and `equity`). The bot runs 24/7 on its own server with real money (about
$68), three live strategies, often 0 open bets and many 15-minute trades a day. Runs the real page in Chromium on a local copy
of the site layout (<site>/kalshi/), kalshi.json served from a stub that can answer 404 / the file / 500 / bad JSON / no
connection / later, and checks:
  a. the files and the static rules (no CDN, fonts only self-hosted, Safari-16-safe script, inputs >= 16px, reduced motion,
     safe areas, the old Jarvis look and its eclipse / reactor themes)
  b. waiting (404 from the feed's own repo, demetrades2000-coder/kalshi-feed): the "Connect your Kalshi bot" card with the
     one step for the bot's own chat (#step inside #body), Copy; raw first, then the GitHub API, no other address; the
     preview with sample data (every section, the SAMPLE banner, Exit preview, never kept, gone once real data exists)
  c. the publisher's own sample through clean(): KPI header, curve from the days, daily bars (one per day), calendar, stats,
     the open position (side tag, "10 × 42¢ → 55¢", countdown), the trade
  d. the real bot (spec kalshi_bot.md section 7 mapping): LIVE · real money, cents everywhere, 0 open bets, trades grouped by
     day with UP / DOWN tags and assets, 24 h equity, the three strategies, today's W / L
  e. a wide sample (6 bets, 30 trades, 2+ months of days and equity): every section, the touch / mouse / keyboard scrub,
     ranges, sort / filter / search, details, show more, calendar months and days
  f. stale (> 15 min), stopped, error (no copy), bad JSON, offline copy, loading (no copy / saved copy), Refresh
  g. escaping (<script> and <img onerror> in every text), empty lists, junk values
  h. its own theme (data-theme kalshi, theme-color #010a07): Jarvis's 'jtheme' never changes it
  v3. contract v3 (2026-11-03): alerts (the bot's + settles-soon), live edge on open bets, Edge & sizing (Kelly per bet, the
     calculator), by market, by price (win vs break-even, ROI), calibration; a v2 feed works them out from the trades list
     and says so; junk v3 values never break a section
  i. 375 / 390 / 430 px: no sideways scroll, nothing past the 16 px gutter, numbers not cut off
  j. no page errors (uncaught exceptions or a section that failed), no failed same-site request, no font asked by the page
  kit. the server script's pin (kit.json from the site build): a valid sha256 = the pinned step and Copy, anything else
     (invalid, missing, slower than 3 s) = today's text exactly
  k. the service worker (kalshi/sw.js, scope ./): its own 'kalshi-*' cache with each shell file, never kalshi.json; offline
     and a 404 site open the saved copy; a slow site shows the copy within 3.5 s and the late answer refreshes it; no copy +
     offline = a small dark Retry page; an update deletes only 'kalshi-*' caches; Jarvis's fonts saved by the worker only
    python -X utf8 -m tests.test_kalshi_page          (temp folder + a local server; nothing else touched)
KALSHI_SHOTS=<dir> also saves screenshots of each state there; KALSHI_FONTS_DIR=<dir> takes the .woff2 fonts from there
(default: tools/web_public/jarvis/, where Jarvis keeps Orbitron and Rajdhani).
"""
from __future__ import annotations

import datetime as dt
import functools
import glob
import hashlib
import http.server
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import kalshi_publish as kp  # noqa: E402

KS = os.path.join(ROOT, "tools", "web_public", "kalshi")
JV_ICON = os.path.join(ROOT, "tools", "web_public", "jarvis", "icon-192.png")
STEP = ("Open your kalshi-server chat in the Claude app and paste: Set up Jarvis for my Kalshi bot by following "
        "https://demetrades2000-coder.github.io/nq-dashboard/kalshi/SETUP.md")
PASTE = STEP.split("paste: ", 1)[1]
# the server script's pin: the site build writes kalshi/kit.json ({"v":1, "file":"kalshi_status_vm.py", "sha256":"<64 hex>"})
KIT_SHA = hashlib.sha256(b"kalshi_status_vm.py (test stand-in)").hexdigest()
STEP_PINNED = STEP + f" (only run kalshi_status_vm.py if its sha256 is {KIT_SHA})"
PASTE_PINNED = STEP_PINNED.split("paste: ", 1)[1]
KIT_JSON = json.dumps({"v": 1, "file": "kalshi_status_vm.py", "sha256": KIT_SHA})
NY = ZoneInfo("America/New_York")
SHOTS = os.environ.get("KALSHI_SHOTS")
FONTS = []
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def usd(x, sign=False):
    """The page's money format: real money, always to the cent, a real minus sign."""
    r = math.floor(abs(x) * 100 + 0.5 + 1e-9) / 100
    s = "" if r == 0 else ("−" if x < 0 else "+" if sign and x > 0 else "")
    return s + "$" + f"{r:,.2f}"


def money(s):
    return float(s.replace("−", "-").replace("$", "").replace(",", "").replace("+", "").strip())


def half_up(x):
    return int(math.floor(x + 0.5))


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def et_day(t):
    return dt.datetime.fromtimestamp(t, NY).date().isoformat()


def v2(raw, now, **extra):
    """kalshi.json as the phone gets it: the publisher's clean(); v2 lists kept if this publisher does not keep them yet."""
    j = kp.clean(raw, now)
    for k in ("strategies", "equity"):
        if raw.get(k) is not None and not j.get(k):
            j[k] = raw[k]
    j.update(extra)
    return j


# ------------------------------------------------------------------ samples
def sample(now):
    """The publisher's own sample (the contract), as the phone receives it."""
    return kp.clean({**kp.SAMPLE, "t": int(now) - 60}, now)


def realbot(now):
    """The owner's bot, mapped as in the spec's section 7: real money, 3 live books, 0 open bets, 40 recent trades of
    15-minute coin markets (sides yes/no, titles from the tickers), the BTC hourly late favourite and gold 5 PM."""
    now = int(now)
    rng = random.Random(11)
    trades, t = [], now - 420
    coins = ["ETH", "BTC", "HYPE"]
    for i in range(40):
        et = dt.datetime.fromtimestamp(t + 900, NY)
        if i % 9 == 4:
            tk = f"KXBTCD-{et:%y}{et.strftime('%b').upper()}{et:%d%H}-T80499.99"
            title, price, n = f"Bitcoin above $80,500 at {et.strftime('%I %p').lstrip('0')} ET {et:%b} {et.day}", 0.93, 6
        elif i % 13 == 7:
            tk, title, price, n = f"KXGOLD-{et:%y}{et.strftime('%b').upper()}{et:%d}-17", "Gold 5 PM close", 0.9, 4
        else:
            c = coins[i % 3]
            tk = f"KX{c}15M-{et:%y}{et.strftime('%b').upper()}{et:%d%H%M}-15"
            title, price, n = f"{c} up or down · 15 min to {et.strftime('%I:%M %p').lstrip('0')} ET {et:%b} {et.day}", round(rng.uniform(0.955, 0.975), 4), rng.randint(10, 20)
        win = rng.random() < 0.88
        pnl = round(n * (1 - price) - 0.02 * n, 2) if win else round(-n * price - 0.02 * n, 2)
        trades.append({"t": t, "ticker": tk, "title": title, "side": "yes" if rng.random() < 0.6 else "no", "action": "buy",
                       "contracts": n, "price": price, "pnl": None if i == 0 else pnl})
        t -= rng.randint(1500, 3300)
    today = dt.datetime.now(NY).date()
    today_pnl = round(sum(x["pnl"] for x in trades if x["pnl"] is not None and et_day(x["t"]) == today.isoformat()), 2)
    days = [[(today - dt.timedelta(days=i)).isoformat(), round(rng.uniform(-9, 4.5), 2)] for i in range(55, 0, -1)] + [[today.isoformat(), today_pnl]]
    bal, equity = 66.2, []
    for i in range(96, -1, -1):
        bal = round(max(60.0, bal + rng.uniform(-0.45, 0.5)), 2)
        equity.append([now - i * 900, bal])
    equity[-1][1] = 67.98
    strategies = [
        {"name": "15-min favourites", "mode": "live", "running": True, "today_pnl": 3.23, "total_pnl": -21.37, "trades": 612, "wins": 571, "losses": 41},
        {"name": "Late favourite (BTC hourly)", "mode": "live", "running": True, "today_pnl": 0.41, "total_pnl": 5.12, "trades": 48, "wins": 45, "losses": 3},
        {"name": "Gold 5 PM", "mode": "live", "running": True, "today_pnl": 0.0, "total_pnl": 1.8, "trades": 9, "wins": 8, "losses": 1},
    ]
    raw = {"name": "Kalshi Edge v2", "mode": "live", "running": True, "status": "Trading · 3 live strategies · 0 open bets", "t": now - 40,
           "balance": 67.98, "today_pnl": today_pnl, "week_pnl": -36.48, "total_pnl": -14.45, "note": "Real money · main account",
           "positions": [], "trades": trades, "days": days, "strategies": strategies, "equity": equity}
    return v2(raw, now), trades


PNLS = [2.5, 1.2, -0.8, None, 3.4, -1.5, -2.0, 0.9, None, 4.1, 1.1, -0.6, 2.2, None, -3.3, 1.8, 0.7, 5.0, -1.1, None,
        2.6, -0.4, 1.5, None, 0.8, -2.2, 3.1, 1.0, None, -0.9]                      # newest first


def wide(now, long_text=False):
    """Everything at once: 6 bets (YES / NO and the bot's UP / DOWN), 30 trades, 70 days, 60 days of equity."""
    now = int(now)
    rng = random.Random(7)
    today = dt.datetime.now(NY).date()
    days = []
    for i in range(70, -1, -1):
        d = today - dt.timedelta(days=i)
        if d.weekday() == 6 and i > 0:
            continue                                                 # gaps: no P&L on Sundays
        days.append([d.isoformat(), round(rng.uniform(-24, 31), 2)])
    bal, equity = 400.0, []
    for i in range(240, -1, -1):                                     # every 6 h for 60 days
        bal = round(bal + rng.uniform(-6, 7), 2)
        equity.append([now - i * 6 * 3600, bal])
    pos = [
        {"ticker": "KXHIGHNY-26NOV02-B58.5", "title": "NYC high 58-59°F on Nov 2", "side": "yes", "contracts": 10, "avg_price": 0.42,
         "price": 0.55, "value": 5.5, "pnl": 1.3, "closes": iso(now + 30 * 3600)},
        {"ticker": "KXFED-26DEC-T4.25", "title": "Fed cuts rates in December", "side": "no", "contracts": 25, "avg_price": 0.61,
         "price": 0.48, "value": 12.0, "pnl": -3.25, "closes": iso(now + 40 * 86400)},
        {"ticker": "KXBTCD-26NOV0117-T80499.99", "title": "Bitcoin above $80,500 at 5 PM ET Nov 1", "side": "UP", "contracts": 40, "avg_price": 0.18,
         "price": 0.31, "value": 12.4, "pnl": 5.2, "closes": iso(now + 45 * 60)},
        {"ticker": "KXNBA-26OCT31-LAL", "title": "Lakers win on Oct 31", "side": "no", "contracts": 5, "avg_price": 0.35,
         "price": 0.0, "value": 0.0, "pnl": -1.75, "closes": iso(now - 3 * 3600)},
        {"ticker": "KXETH15M-26NOV051215-15", "title": "ETH up or down · 15 min to 12:15 PM ET Nov 5", "side": "DOWN", "contracts": 12, "avg_price": 0.5,
         "price": 0.57, "value": 6.84, "pnl": 0.84, "closes": iso(now + 4 * 86400)},
        {"ticker": "KXGOLD-26NOV09-17", "title": "Gold 5 PM close", "side": "yes", "contracts": 8, "avg_price": 0.22,
         "price": 0.2, "value": 1.6, "pnl": -0.16, "closes": iso(now + 8 * 86400)},
    ]
    if long_text:
        pos[4]["title"] = "Will_the_high_temperature_in_Chicago_be_above_70_degrees_on_November_5th_" * 2
        pos[5]["title"] = ("Will gold close above two thousand seven hundred dollars at five in the afternoon on the ninth of November, "
                           "as published by the exchange")
    trades = []
    for i, pnl in enumerate(PNLS):
        p = pos[i % len(pos)]
        trades.append({"t": now - 3600 - i * 7 * 3600, "ticker": p["ticker"], "title": p["title"], "side": p["side"],
                       "action": "buy" if pnl is None else "sell", "contracts": 5 + i, "price": 0.3 + (i % 5) / 10, "pnl": pnl})
    strategies = [
        {"name": "Weather edge" + (" with a long name for a narrow phone screen" if long_text else ""), "mode": "paper", "running": True,
         "today_pnl": 12.4, "total_pnl": 80.5, "trades": 41, "wins": 26, "losses": 15},
        {"name": "Fed fade", "mode": "paper", "running": False, "today_pnl": 0, "total_pnl": -12.25, "trades": 9, "wins": 3, "losses": 6},
        {"name": "Crypto momentum", "mode": "demo", "running": True, "today_pnl": 6.1, "total_pnl": 1044.09, "trades": 1230, "wins": 718, "losses": 512},
    ]
    raw = {**kp.SAMPLE, "t": now - 60, "positions": pos, "trades": trades, "days": days, "strategies": strategies, "equity": equity}
    if long_text:
        raw.update(balance=12345.67, today_pnl=-1234.56, week_pnl=10234.5, total_pnl=-11234.99)
    return v2(raw, now)


# ------------------------------------------------------------------ site + feed stub
def site(tmp):
    base = os.path.join(tmp, "nq-dashboard")
    shutil.copytree(KS, os.path.join(base, "kalshi"))
    # the OLYMPUS theme engine the page loads (../olympus/themes.js), published with the site
    shutil.copytree(os.path.join(os.path.dirname(KS), "olympus"), os.path.join(base, "olympus"))
    os.makedirs(os.path.join(base, "jarvis"))
    if os.path.exists(JV_ICON):
        shutil.copy(JV_ICON, os.path.join(base, "jarvis", "icon-192.png"))
    for f in glob.glob(os.path.join(os.environ.get("KALSHI_FONTS_DIR") or os.path.dirname(JV_ICON), "*.woff2")):
        shutil.copy(f, os.path.join(base, "jarvis", os.path.basename(f)))      # Jarvis's fonts: the widths are tested with them
        FONTS.append(os.path.basename(f))
    with open(os.path.join(base, "kalshi", "kit.json"), "w", encoding="utf-8") as f:     # written by the site build
        f.write(KIT_JSON)
    with open(os.path.join(base, "host.html"), "w", encoding="utf-8") as f:             # Jarvis-like: a bar below the notch, the page framed
        f.write('<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                '<style>html,body{margin:0;height:100%;background:#000}.bar{height:calc(52px + env(safe-area-inset-top,0px))}'
                'iframe{display:block;width:100%;height:calc(100% - 52px - env(safe-area-inset-top,0px));border:0}</style>'
                '<div class="bar"></div><iframe id="f" src="kalshi/"></iframe>')
    return tmp


SITE = {"mode": "ok", "slow": 0.0, "kit_slow": 0.0}          # the site's kalshi/ folder: ok | down (every connection dropped) | 404 (GitHub's 404)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):         # the browser gave up on a dropped ("down") answer
            pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")      # always asked again (the worker, not the HTTP cache, keeps copies)
        super().end_headers()

    def do_GET(self):
        if "/kalshi/" in self.path or (SITE["mode"] != "ok" and ".woff2" in self.path):   # the page's folder (and Jarvis's fonts)
            if SITE["mode"] == "down":
                self.close_connection = True
                return
            if SITE["mode"] == "404":
                body = b"<!doctype html><title>Site not found \xc2\xb7 GitHub Pages</title><h1>404</h1><p>File not found</p>"
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if SITE["slow"]:
                time.sleep(SITE["slow"])
            if SITE["kit_slow"] and self.path.split("?")[0].endswith("/kit.json"):
                time.sleep(SITE["kit_slow"])
        return super().do_GET()


def serve(root):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# the feed's own repo (security review 2026-11-01): raw first (with a ?t= cache-buster), then the GitHub API; nothing else answers
FEED_RAW = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
FEED_API = "https://api.github.com/repos/demetrades2000-coder/kalshi-feed/contents/kalshi.json?ref=main"
FEED = {"mode": "404", "j": None, "held": [], "hits": 0, "raw": None, "api": None, "n": {"raw": 0, "api": 0}, "wrong": []}


def feed(route):
    u = route.request.url
    src = "raw" if u.split("?")[0] == FEED_RAW else "api" if u == FEED_API else None
    if src is None:                                  # any other address (e.g. the old Pages-repo branch) never answers
        if "kalshi" in u:
            FEED["wrong"].append(u)
        return route.abort()
    FEED["hits"] += 1
    FEED["n"][src] += 1
    m = FEED[src] or FEED["mode"]                    # a per-source mode, else the shared one
    if m == "ok":
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(FEED["j"]))
    if m == "404":
        return route.fulfill(status=404, content_type="text/plain", body="404: Not Found")
    if m == "500":
        return route.fulfill(status=500, content_type="text/plain", body="server error")
    if m == "bad":
        return route.fulfill(status=200, content_type="application/json", body="{not json")
    if m == "hold":
        FEED["held"].append(route)
        return None
    return route.abort()


def release():
    for r in FEED["held"]:
        try:
            r.fulfill(status=200, content_type="application/json", body=json.dumps(FEED["j"]))
        except Exception:
            pass
    FEED["held"] = []


def text(p, sel="#body"):
    return p.locator(sel).inner_text()


def ready(p, timeout=8000):
    p.wait_for_function("document.querySelector('#refresh').getAttribute('aria-busy') === 'false'", timeout=timeout)


def shot(p, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        p.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=True)


# every visible control's hit area, probed where a finger lands: 22 px left / right / up / down of its center must still hit it
TARGETS = """() => {
  const out = [];
  for (const e of document.querySelectorAll('.top button, #body button, #body select, #body input, #body summary')) {
    if (!e.getClientRects().length || getComputedStyle(e).visibility === 'hidden') continue;
    e.scrollIntoView({ block: 'center', inline: 'nearest' });
    const r = e.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const pts = [[cx - 21.5, cy], [cx + 21.5, cy], [cx, cy - 21.5], [cx, cy + 21.5]];
    const miss = pts.filter(([x, y]) => { const h = document.elementFromPoint(x, y); return !h || (h !== e && !e.contains(h)); });
    if (miss.length) out.push((e.getAttribute('data-act') || e.id || e.className || e.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  window.scrollTo(0, 0);
  return out;
}"""


# ------------------------------------------------------------------ a. files + static rules
def part_a():
    for f in ("index.html", "kalshi.js", "kalshi.css", "sw.js"):
        check(f"a. kalshi/{f} exists", os.path.exists(os.path.join(KS, f)))
    check("a. no file named like the kit's (the site build writes kalshi_status_vm.py, SETUP.md and kit.json into kalshi/)",
          not any(os.path.exists(os.path.join(KS, f)) for f in ("SETUP.md", "kalshi_status_vm.py", "kit.json")))
    html = open(os.path.join(KS, "index.html"), encoding="utf-8").read()
    js = open(os.path.join(KS, "kalshi.js"), encoding="utf-8").read()
    css = open(os.path.join(KS, "kalshi.css"), encoding="utf-8").read()
    sw = open(os.path.join(KS, "sw.js"), encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    check("a. the page keeps #body and #sub, loads kalshi.css + kalshi.js (versioned)",
          'id="body"' in html and 'id="sub"' in html and 'href="kalshi.css?v=' in html and 'src="kalshi.js?v=' in html)
    check("a. the one step is the exact text (tests/test_jarvis_hub reads it from #step)", f"const STEP0 = '{STEP}';" in js)
    check("a. the pin: kit.json (same origin, 3 s at most), a lowercase 64-hex sha256 only, the exact pinned wording, Copy takes it",
          "get('kit.json', {}, 3000)" in js and "/^[0-9a-f]{64}$/.test(h)" in js and "(only run kalshi_status_vm.py if its sha256 is ${h})" in js
          and "writeText(paste())" in js and "'./kit.json'" in sw and "u.searchParams.has('v')" in sw)
    check("a. the feed is read from its own repo kalshi-feed (raw first, then the API), never from the Pages repo",
          f"const RAW = '{FEED_RAW}';" in js and f"const API = '{FEED_API}';" in js and "ref=kalshi" not in js and "nq-dashboard/kalshi/kalshi.json" not in js
          and code.index("get(RAW") < code.index("get(API"))
    urls = set(re.findall(r"https?://[^\s'\"`)<>]+", html + js + css))
    allowed = ("https://raw.githubusercontent.com/", "https://api.github.com/", "http://www.w3.org/2000/svg",
               "https://demetrades2000-coder.github.io/nq-dashboard/kalshi/SETUP.md")
    fonts = re.findall(r"url\(\"?([^\")]+)\"?\)", css)
    check("a. no CDN or other site (only the feed on GitHub); fonts only self-hosted next to Jarvis, with system fallbacks",
          all(u.startswith(allowed) for u in urls) and "@import" not in css and fonts and all(f.startswith(("../jarvis/", "data:image/svg+xml")) for f in fonts)
          and '"Orbitron", "Bahnschrift"' in css and '"Rajdhani", "Segoe UI"' in css, (sorted(urls), fonts))
    risky = [w for w in ("(?<=", "(?<!", ".toSorted(", ".toReversed(", ".toSpliced(", ".findLast(", "Object.groupBy", "AbortSignal.timeout",
                         "structuredClone", "static {", ".at(-") if w in code]
    check("a. Safari 16 safe script (no lookbehind, Array copy methods, findLast, groupBy, AbortSignal.timeout ...)", not risky, risky)
    check("a. Safari 16 safe styles (no nesting, container queries, color-mix); clip-path also -webkit-",
          "@container" not in css and "color-mix(" not in css and not re.search(r"\{[^{}]*&[^{}]*\{", css) and "-webkit-clip-path" in css)
    check("a. Safari 16 layout: no grid / flex on <summary> (WebKit cannot), no CSS filter on SVG shapes (only on the <svg>)",
          not re.search(r"summary[^{},]*\{[^}]*display:\s*(grid|flex)", css) and not re.search(r"\.chart \.(ln|area|grid|base) \{[^}]*filter:", css))
    pre = css.split("@media (prefers-reduced-motion: no-preference)")[0]
    check("a. inputs and selects at 16px (no iPhone zoom); safe areas; every animation behind prefers-reduced-motion",
          re.search(r"\.q \{[^}]*font: 500 16px", css) and re.search(r"\.sel \{[^}]*font: 500 16px", css)
          and "env(safe-area-inset-left" in css and "env(safe-area-inset-bottom" in css and "viewport-fit=cover" in html
          and "@media (prefers-reduced-motion: no-preference)" in css and "animation:" not in pre)
    check("a. its own look (2026-11-03): the Kalshi mint + cyan tokens on a deep green-black, clipped panels with the glowing tick",
          ':root, :root[data-theme="kalshi"]' in css and "--bg: #010a07;" in css and "--c: #1fe5a6;" in css and "--cy: #38e1ff;" in css
          and "eclipse" not in css and "reactor" not in css and "clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px" in css
          and ".card::before" in css and "width: 36px; height: 2px" in css)
    check("a. its own top colour = its background (Jarvis's status-bar strip takes it); the theme set before paint, never Jarvis's 'jtheme'",
          '<meta name="theme-color" content="#010a07">' in html and "d.setAttribute('data-theme', 'kalshi')" in html
          and html.index("data-theme', 'kalshi'") < html.index('href="kalshi.css') and "jtheme" not in html + js)
    check("a. its own header: the K mark, KALSHI EDGE, the ticker tape (aria-hidden), the aurora; the tape animation behind reduced motion",
          'class="mark"' in html and '<span class="h1s">Edge</span>' in html and 'id="tape" aria-hidden="true" hidden' in html
          and 'class="aurora"' in html and ".tape-in { animation: tape" in css.split("@media (prefers-reduced-motion: no-preference)")[1])
    check("a. framed (inside Jarvis): a 'framed' class before paint drops the second notch inset; on its own the inset stays",
          "if (window.top !== window) d.classList.add('framed')" in html and html.index("framed") < html.index('href="kalshi.css')
          and "html.framed main { padding-top: 16px; }" in css and "padding: calc(16px + env(safe-area-inset-top, 0px))" in css)
    ver = re.search(r"kalshi\.js\?v=(\w+)", html).group(1)
    check("a. kalshi/sw.js: its own 'kalshi-*' cache and only those deleted, its own folder only, the 3.5 s rule, the page's versions",
          f"const CACHE = 'kalshi-{ver}';" in sw and "k.startsWith('kalshi-') && k !== CACHE" in sw and "u.pathname.startsWith(scope.pathname)" in sw
          and "const NAV_WAIT_MS = 3500;" in sw and f"'./kalshi.css?v={ver}'" in sw and f"'./kalshi.js?v={ver}'" in sw and f"kalshi.css?v={ver}" in html)
    ff = re.findall(r'@font-face \{ font-family: "(\w+)"; src: url\("\.\./jarvis/([\w-]+\.woff2)"\) format\("woff2"\);[^}]*font-display: swap; \}', css)
    check("a. Jarvis's fonts by plain @font-face (../jarvis/ orbitron + rajdhani-400/500/600/700, font-display: swap), kept by the worker for offline",
          sorted(f for _, f in ff) == ["orbitron.woff2", "rajdhani-400.woff2", "rajdhani-500.woff2", "rajdhani-600.woff2", "rajdhani-700.woff2"]
          and "navigator.serviceWorker.register('sw.js', { scope: './' })" in js and all(f"'../jarvis/{f}'" in sw for _, f in ff) and "FONT_URLS.indexOf" in sw, ff)
    check("a. every control at least 44 px (Refresh, buttons, sort, search, months, calendar days; hit pads for the compact ones)",
          all(re.search(pat, css) for pat in (r"\.refresh \{[^}]*height: 44px", r"\.btn \{[^}]*height: 44px", r"\.sel \{[^}]*height: 44px", r"\.q \{[^}]*height: 44px",
                                              r"\.nav \{[^}]*width: 44px; height: 44px", r"\.cd \{[^}]*height: 44px", r"\.more \{[^}]*height: 44px",
                                              r"::after \{[^}]*width: max\(100%, 44px\); height: max\(100%, 44px\)")))
    check("a. text wraps instead of being cut (no ellipsis, no line clamp)", "text-overflow: ellipsis" not in css and "line-clamp" not in css)
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("a. the site build publishes every file of kalshi/ (index.html, kalshi.js, kalshi.css, sw.js)",
          'for app in ("jarvis", "kalshi", "datacity", "mind", "tree", "oracle", "odeon", "fates", "hermes", "prometheus", "tyche", "olympus"):' in b and "for name in os.listdir(src_dir):" in b)


# ------------------------------------------------------------------ the browser parts
def run_browser(url, tmp):
    from playwright.sync_api import sync_playwright
    page_url = url + "kalshi/"
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ctx.route("https://raw.githubusercontent.com/**", feed)
        ctx.route("https://api.github.com/**", feed)
        p = ctx.new_page()
        errs, cons, dialogs, bad, fontres = [], [], [], [], []
        p.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and r.url.startswith(url.split("/nq-dashboard/")[0]) else None)
        p.on("response", lambda r: fontres.append((r.status, r.url.rsplit("/", 1)[1])) if ".woff2" in r.url else None)
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.on("console", lambda m: cons.append(m.text) if m.type == "error" and not re.search(r"Failed to load resource|net::ERR", m.text) else None)
        p.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))

        def open_(mode, j=None, clear=True, wait=True):
            FEED["mode"] = mode
            if j is not None:
                FEED["j"] = j
            if clear:
                p.goto(page_url)
                p.evaluate("localStorage.clear()")
            p.goto(page_url)
            if wait:
                ready(p)

        titles = lambda sel="#posList > li.pos summary .t": p.evaluate(  # noqa: E731
            f"[...document.querySelectorAll('{sel}')].map((t) => t.lastChild.textContent)")

        # ---- b. waiting
        open_("404")
        try:
            p.wait_for_function("(document.getElementById('step') || {}).textContent.indexOf('sha256') > 0", timeout=4000)
        except Exception:
            pass
        body = p.locator("#body").text_content()
        check("b. not published (404): the Connect card with the one step for the bot's own chat, pinned to the kit's sha256",
              "Connect your Kalshi bot" in body and p.locator("#body #step").inner_text() == STEP_PINNED
              and p.locator("#sub").inner_text() == "Not connected yet" and p.get_attribute("#body", "data-state") == "waiting", body[:300])
        check("b. the card says the bot runs on its own server, one paste connects it, every minute after; never 'PC'",
              "runs on its own server" in body and "One paste in its own chat" in body and "every minute" in body
              and not re.search(r"\bPC\b", body + p.inner_text("#foot")), body)
        check("b. waiting: no numbers, no sections", p.locator("#body .card").count() == 1 and p.locator("#sec-kpi").count() == 0)
        feats = [x.inner_text().strip().lower() for x in p.locator("#body .wait .feat li").all()]
        check("b. waiting: what lights up once connected (9 chips: alerts, live edge, Kelly, by market / price, calibration ...)",
              len(feats) == 9 and {"alerts", "kelly sizing", "calibration", "by market", "by price"} <= set(feats)
              and p.is_hidden("#tape"), feats)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=url.rstrip("/").rsplit("/", 1)[0])
        p.click("[data-act=copy]")
        p.wait_for_function("document.getElementById('copied').textContent.length > 0", timeout=3000)
        clip = p.evaluate("navigator.clipboard.readText().catch(() => '')")
        check("b. Copy puts the whole message to paste on the clipboard, the hash included", p.inner_text("#copied") == "Copied" and clip == PASTE_PINNED,
              (p.inner_text("#copied"), clip))
        shot(p, "1_waiting")

        # ---- b. the preview while not connected: the whole dashboard from a built-in sample, clearly marked, never kept
        check("b. a quiet 'Preview with sample data' under the step", p.locator("#body .wait [data-act=preview]").inner_text() == "Preview with sample data"
              and p.evaluate("(() => { const s = document.getElementById('step'), b = document.querySelector('[data-act=preview]'); "
                             "return !!(s.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); })()"))
        p.click("[data-act=preview]")
        bt = p.locator("#body").text_content()
        secs = {s_: p.locator(s_).count() for s_ in ("#sec-kpi", "#sec-eq", "#sec-pos", "#sec-strat", "#sec-days", "#sec-cal", "#sec-stats", "#sec-tr")}
        check("b. preview: every section from the sample, marked SAMPLE DATA, not your account, with Exit preview",
              p.get_attribute("#body", "data-state") == "preview" and all(v_ == 1 for v_ in secs.values()) and "Sample data, not your account" in p.locator("#previewBar").text_content()
              and p.locator("#previewBar [data-act=exit-preview]").inner_text().upper() == "EXIT PREVIEW" and "could not be shown" not in bt, (secs, bt[:200]))
        kpi = p.locator("#sec-kpi").text_content()
        bal = re.search(r"\$(\d+\.\d\d)", kpi)
        tags = {t_.inner_text() for t_ in p.locator("#trList .tag").all()}
        check("b. preview in the real bot's shape: balance about $68, 3 strategies, 24 h of equity, UP / DOWN trades, 0-1 open bets",
              bal and 60 <= float(bal.group(1)) <= 75 and p.locator("#sec-strat tbody tr").count() == 3 and "last 24 h" in p.inner_text("#eqRead")
              and {"UP", "DOWN"} <= tags and p.locator("#posList > li.pos").count() <= 1, (kpi[:120], tags))
        check("b. preview: never the LIVE · real money badge; the header says Preview", p.locator("#mode").count() == 0 and "PREVIEW" in p.inner_text("#sub").upper()
              and "not your account" in p.inner_text("#foot"))
        p.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        p.wait_for_timeout(150)
        bb = p.locator("#previewBar").bounding_box()
        check("b. the SAMPLE banner stays on screen while scrolling", bb and 0 <= bb["y"] <= 60, bb)
        shot(p, "1b_preview")
        check("b. the preview is never kept: no saved copy on the phone", p.evaluate("localStorage.getItem('kalshi.last')") is None)
        p.click("#previewBar [data-act=exit-preview]")
        check("b. Exit preview: back to the Connect card, step unchanged", p.get_attribute("#body", "data-state") == "waiting"
              and "Connect your Kalshi bot" in p.locator("#body").text_content() and p.locator("#body #step").inner_text() == STEP_PINNED and p.locator("#previewBar").count() == 0)
        p.click("[data-act=preview]")
        FEED["mode"] = "abort"                                  # no connection while previewing: still not kept as an offline copy
        p.reload()
        ready(p)
        check("b. the preview is not the offline copy: no connection after a preview = 'No connection', not the sample",
              p.get_attribute("#body", "data-state") == "error" and "No connection" in text(p) and p.evaluate("localStorage.getItem('kalshi.last')") is None)
        FEED["mode"] = "404"
        p.reload()
        ready(p)
        p.click("[data-act=preview]")
        FEED["mode"], FEED["j"] = "ok", sample(time.time())
        p.click("#refresh")
        ready(p)
        check("b. real data arrives during a preview: the real numbers, the banner gone for good",
              p.get_attribute("#body", "data-state") == "ok" and p.locator("#previewBar").count() == 0 and "$512.34" in text(p)
              and json.loads(p.evaluate("localStorage.getItem('kalshi.last')"))["balance"] == 512.34)
        FEED["mode"] = "404"
        p.reload()
        ready(p)
        check("b. once real data has existed on this phone: the waiting card has no preview button", p.get_attribute("#body", "data-state") == "waiting"
              and p.locator("[data-act=preview]").count() == 0)

        # ---- c. the publisher's sample (contract v1, through the real clean())
        open_("ok", sample(time.time()))
        body = p.locator("#body").text_content()
        sub = p.inner_text("#sub")
        check("c. KPI header: balance, today and week (with % of the start), all time, mode, running, updated",
              "$512.34" in body and "+$18.50" in body and "+3.7%" in body and "+$42.10" in body and "+9.0%" in body and "+$112.34" in body and "+28%" not in body
              and "Running" in sub.title() and "PAPER" in sub and "updated just now" in sub and p.get_attribute("#body", "data-state") == "ok", (sub, body[:300]))
        check("c. the bot's name and status line", "Kalshi bot" in body and "Watching 12 markets" in body)
        check("c. the open bet: YES tag, title, 10 × 42¢ → 55¢, a countdown, value and return",
              p.locator("#posList .tag.yes").count() == 1 and "NYC high 58-59°F on Nov 2" in body
              and "10 × 42¢ → 55¢" in body and re.search(r"closes in \d+[dhm]|closed · settling", p.inner_text("#posList .cdl")) and "$5.50 · +31%" in body, body[:600])
        check("c. one bet: no sort / filter controls", p.locator("#posSort").count() == 0 and p.locator("#posQ").count() == 0)
        check("c. the trade: Buy 10 @ 42¢ with its time, OPEN while unsettled, no show-more",
              "Buy 10 @ 42¢ · " in body and p.locator("#trList .open").count() == 1 and p.locator("#sec-tr .more").count() == 0)
        check("c. daily bars: one bar per day (3)", p.locator("svg.bars rect").count() == 3)
        check("c. no equity published: the curve is the running sum of the days (+$27.80) and says so",
              p.inner_text("#sec-eq h2").lower() == "cumulative p&l" and "+$27.80" in p.inner_text("#eqRead") and "From the daily P&L" in body
              and len(p.get_attribute("#chart path.ln", "d")) > 10)
        st = p.inner_text("#sec-stats")
        check("c. stats from the days while no trade has settled: 2 / 3 green, best / worst day, drawdown −$3.10",
              "No settled trades" in st and "2 / 3" in st and "+$18.50" in st and "−$3.10" in st.split("Best / worst day".upper())[-1], st)
        check("c. the calendar: the month of the last day, its P&L cell", p.locator("#sec-cal .cd.p4, #sec-cal .cd.p3, #sec-cal .cd.p2, #sec-cal .cd.p1").count() >= 1
              and p.inner_text("#calMonth").upper() == "NOVEMBER 2026", p.inner_text("#calMonth"))
        check("c. no strategies published: no strategies table", p.locator("#sec-strat").count() == 0)
        shot(p, "2_sample")

        # ---- d. the real bot
        rb, rtr = realbot(time.time())
        open_("ok", rb)
        body = p.locator("#body").text_content()
        check("d. LIVE · real money: a calm badge (mint, not red)", " ".join(p.locator("#mode").text_content().split()) == "LIVE · real money"
              and p.evaluate("getComputedStyle(document.getElementById('mode')).color") == "rgb(141, 255, 216)", (p.inner_text("#mode"), p.evaluate("getComputedStyle(document.getElementById('mode')).color")))
        today = dt.datetime.now(NY).date().isoformat()
        tw = sum(1 for x in rtr if x["pnl"] is not None and x["pnl"] > 0 and et_day(x["t"]) == today)
        tl = sum(1 for x in rtr if x["pnl"] is not None and x["pnl"] < 0 and et_day(x["t"]) == today)
        kpi = p.locator("#sec-kpi").text_content()
        check("d. KPIs to the cent: $67.98, today, week −$36.48, all time −$14.45; today's W / L as in the bot's money text",
              "$67.98" in kpi and usd(rb["today_pnl"], True) in kpi and "−$36.48" in kpi and "−$14.45" in kpi and (f"{tw}W {tl}L" in kpi if tw + tl else True)
              and "624W 45L" in kpi
              and "Kalshi Edge v2" in kpi and "Trading · 3 live strategies · 0 open bets" in kpi and "Real money · main account" in kpi, kpi)
        check("d. 0 open bets: says so, quietly", "No open bets right now." in p.inner_text("#sec-pos") and p.locator("#sec-pos .rows").count() == 0)
        check("d. 24 h of equity: the Equity curve, no range chips, 'last 24 h', the balance now",
              p.inner_text("#sec-eq h2").lower() == "equity" and p.locator("#sec-eq .seg").count() == 0 and "last 24 h" in p.inner_text("#eqRead")
              and "$67.98" in p.inner_text("#eqRead"), p.inner_text("#eqRead"))
        heads = [h.inner_text() for h in p.locator("#trList > li.day").all()]
        first_day = et_day(rtr[0]["t"])
        dp = dict((d, x) for d, x in rb["days"])
        check("d. trades grouped by day, the day's P&L in the header (Today first)",
              heads and heads[0].upper().startswith("TODAY" if first_day == today else "YESTERDAY") and usd(dp[first_day], True) in heads[0]
              and p.locator("#trList > li.row").count() == 10, heads)
        rows = p.locator("#trList > li.row")
        tags = [t.inner_text() for t in p.locator("#trList > li.row .tag").all()]
        check("d. 15-minute 'up or down' markets show UP / DOWN, the hourly 'above' market YES / NO",
              any(t in ("UP", "DOWN") for t in tags) and all(t in ("UP", "DOWN", "YES", "NO") for t in tags)
              and all(("UP" == t or "DOWN" == t) == ("up or down" in rtr[i]["title"]) for i, t in enumerate(tags)), tags)
        assets = [a.inner_text() for a in p.locator("#trList > li.row .asset").all()]
        check("d. the asset from the ticker (ETH / BTC / HYPE / GOLD)", assets and set(assets) <= {"ETH", "BTC", "HYPE", "GOLD"}, assets)
        r0 = rows.nth(0).inner_text()
        check("d. the newest trade: still OPEN, price to a tenth of a cent where it has one (e.g. 96.8¢)",
              "OPEN" in r0 and re.search(r"Buy \d+ @ 9\d(\.\d)?¢ · \d{1,2}:\d\d [AP]M", r0), r0)
        r1 = rows.nth(1).inner_text()
        check("d. a settled trade shows its P&L to the cent", usd(rtr[1]["pnl"], True) in r1, (r1, rtr[1]["pnl"]))
        p.click("#sec-tr .more")
        p.click("#sec-tr .more")
        p.click("#sec-tr .more")
        check("d. show more: all 40, still grouped", p.locator("#trList > li.row").count() == 40 and p.locator("#trList > li.day").count() >= 2)
        stt = p.locator("#sec-strat").text_content()
        check("d. the three live strategies: names, today, total, win rate, running",
              p.locator("#sec-strat tbody tr").count() == 3 and "15-min favourites" in stt and "Late favourite (BTC hourly)" in stt and "Gold 5 PM" in stt
              and "3 running" in stt and "Live · 612 trades · running" in stt and "+$3.23" in stt and "−$21.37" in stt and "93%" in stt and "571–41" in stt, stt)
        cell = p.locator(f"#sec-cal .cd[data-v='{today}'] em").inner_text()
        check("d. the calendar shows small days to the cent", cell == (re.sub(r"\$", "", usd(rb["today_pnl"], True)) if abs(rb["today_pnl"]) < 10 else cell), (cell, rb["today_pnl"]))
        shot(p, "3_realbot")

        # ---- e. a wide sample (contract v2, every list long)
        j = wide(time.time())
        open_("ok", j)
        check("e. 60 days of equity: ranges 1W / 1M / All (1M first)",
              p.inner_text("#sec-eq h2").lower() == "equity" and [b.text_content() for b in p.locator("#sec-eq .seg button").all()] == ["1W", "1M", "All"]
              and p.get_attribute("#sec-eq [data-v='1M']", "aria-pressed") == "true" and "past month" in p.inner_text("#eqRead"))
        eq = sorted(j["equity"])
        frm = eq[-1][0] - 30 * 86400
        i0 = next(i for i, e in enumerate(eq) if e[0] >= frm)
        first = eq[max(0, i0 - 1)][1]
        idle = p.inner_text("#eqRead")
        check("e. the curve's reading: the last balance and the change over the month",
              usd(eq[-1][1]) in idle and usd(eq[-1][1] - first, True) in idle, (idle, usd(eq[-1][1]), usd(eq[-1][1] - first, True)))
        box = p.locator("#chart").bounding_box()
        p.mouse.move(box["x"] + 0.5, box["y"] + box["height"] / 2)
        r1 = p.inner_text("#eqRead")
        check("e. mouse scrub: the far left reads the first point of the month, with its time", usd(first) in r1 and "past month" not in r1
              and p.locator("#chart .dot").is_visible() and p.locator("#chart .cross").is_visible(), (r1, usd(first)))
        p.mouse.move(box["x"] + box["width"] - 1, box["y"] + 10)
        check("e. mouse scrub: the far right reads the last point", usd(eq[-1][1]) in p.inner_text("#eqRead"))
        p.mouse.move(box["x"] + box["width"] / 2, box["y"] - 60)
        check("e. leaving the chart: back to the summary", "past month" in p.inner_text("#eqRead") and p.locator("#chart .dot").is_hidden())
        touch = p.evaluate("""() => { const el = document.getElementById('chart'), r = el.getBoundingClientRect();
            const ev = (type, x) => el.dispatchEvent(new PointerEvent(type, { pointerType: 'touch', pointerId: 7, isPrimary: true, bubbles: true, clientX: x, clientY: r.top + 20 }));
            ev('pointerdown', r.left + r.width * 0.25); const a = document.getElementById('eqRead').innerText;
            ev('pointermove', r.left + r.width * 0.75); const b = document.getElementById('eqRead').innerText;
            const dot = !document.querySelector('#chart .dot').hidden; ev('pointerup', r.left + r.width * 0.75);
            return [a, b, dot, document.getElementById('eqRead').innerText, !document.querySelector('#chart .dot').hidden]; }""")
        check("e. touch scrub: the finger moves the reading, lifting it goes back to the summary",
              touch[0] != touch[1] and touch[2] and "past month" not in touch[1] and "past month" in touch[3] and not touch[4], touch)
        p.focus("#chart")
        p.keyboard.press("Home")
        rk = p.inner_text("#eqRead")
        p.keyboard.press("ArrowRight")
        check("e. keyboard: Home reads the first point, the arrows step through", usd(first) in rk and p.inner_text("#eqRead") != rk, rk)
        p.keyboard.press("Escape")
        p.click("#sec-eq [data-v='1W']")
        check("e. range 1W: the reading and the chip follow, the choice is saved",
              "past week" in p.inner_text("#eqRead") and p.get_attribute("#sec-eq [data-v='1W']", "aria-pressed") == "true"
              and json.loads(p.evaluate("localStorage.getItem('kalshi.ui')"))["range"] == "1W")
        p.click("#sec-eq [data-v='All']")
        check("e. range All: since the first point", "since " in p.inner_text("#eqRead"), p.inner_text("#eqRead"))
        p.click("#sec-eq [data-v='1M']")
        # open bets
        seg = p.inner_text("#sec-pos .seg").split()
        check("e. 6 bets: side filter (All 6 / YES 4 / NO 2: UP counts as YES, DOWN as NO), sort, search",
              seg == ["ALL", "6", "YES", "3", "NO", "3"] or seg == ["All", "6", "YES", "3", "NO", "3"], seg)
        check("e. the bot's own UP / DOWN tags kept", p.locator("#posList .tag.yes", has_text="UP").count() == 1 and p.locator("#posList .tag.no", has_text="DOWN").count() == 1
              and p.locator("#posSort").count() == 1 and p.locator("#posQ").count() == 1)
        r0 = titles()
        check("e. sorted by closing time: the settling one first, then the one closing in under an hour (amber)",
              r0[0].startswith("Lakers") and r0[1].startswith("Bitcoin") and "closed · settling" in p.inner_text("#posList > li >> nth=0")
              and p.locator("#posList > li >> nth=1").locator(".cdn.soon").count() == 1
              and re.search(r"closes in (4[0-5]|3\d)m", p.inner_text("#posList > li >> nth=1")), r0)
        hdr = p.inner_text("#sec-pos .card-h")
        tv, tpnl = sum(x["value"] for x in j["positions"]), sum(x["pnl"] for x in j["positions"])
        check("e. the header totals: value and P&L of all bets", usd(tv) in hdr and usd(tpnl, True) in hdr, (hdr, usd(tv), usd(tpnl, True)))
        p.select_option("#posSort", "pnl")
        check("e. sort Best P&L: Bitcoin (+$5.20) first", titles()[0].startswith("Bitcoin"), titles())
        p.select_option("#posSort", "pnl-asc")
        check("e. sort Worst P&L: Fed (−$3.25) first", titles()[0].startswith("Fed cuts"), titles())
        p.select_option("#posSort", "value")
        check("e. sort Biggest: Bitcoin ($12.40) first", titles()[0].startswith("Bitcoin"), titles())
        p.select_option("#posSort", "name")
        check("e. sort A–Z", titles() == sorted(titles(), key=str.lower), titles())
        p.click("#sec-pos [data-act=side][data-v=no]")
        check("e. filter NO: the 3 NO / DOWN bets only", len(titles()) == 3 and p.locator("#posList .tag.no").count() == 3 and p.locator("#posList .tag.yes").count() == 0)
        p.click("#sec-pos [data-act=side][data-v=all]")
        p.fill("#posQ", "gold")
        check("e. search 'gold': the gold bet only, the field keeps its text", titles() == ["Gold 5 PM close"] and p.input_value("#posQ") == "gold", titles())
        p.fill("#posQ", "zzz")
        check("e. search with no match says so", "match" in p.inner_text("#posList"))
        p.fill("#posQ", "")
        p.select_option("#posSort", "closes")
        p.click("#posList > li >> nth=2 >> summary")
        det = p.inner_text("#posList > li >> nth=2")
        check("e. tapping a bet opens its details: market, cost, value, payout if it wins, close time",
              "KXHIGHNY-26NOV02-B58.5" in det and "$4.20" in det and "pays $10.00" in det and "+$5.80" in det and " ET" in det, det)
        # strategies
        stxt = p.locator("#sec-strat").text_content()
        check("e. strategies table: 3 rows, running / stopped, today, total, win rate, an All row",
              p.locator("#sec-strat tbody tr").count() == 3 and "2 running" in stxt and p.locator("#sec-strat .sdot.on").count() == 2
              and p.locator("#sec-strat .sdot.off").count() == 1 and "+$12.40" in stxt and "+$80.50" in stxt and "63%" in stxt and "26–15" in stxt
              and "−$12.25" in stxt and usd(80.5 - 12.25 + 1044.09, True) in stxt and "1,280 trades" in stxt, stxt)
        # stats
        pn = [x["pnl"] for x in sorted(j["trades"], key=lambda t: -t["t"]) if x.get("pnl") is not None]
        w, lo = [x for x in pn if x > 0], [x for x in pn if x < 0]
        tiles = {t.locator(".lab").inner_text().strip().upper(): t.inner_text() for t in p.locator("#sec-stats .stat").all()}
        wr = half_up(100 * len(w) / (len(w) + len(lo)))
        check("e. stats: win rate and W / L", f"{wr}%" in tiles.get("WIN RATE", "") and f"{len(w)}W · {len(lo)}L" in tiles.get("WIN RATE", ""), tiles)
        av = re.findall(r"[+−]\$[\d,.]+", tiles.get("AVG WIN / LOSS", ""))
        check("e. stats: average win / average loss", len(av) == 2 and abs(money(av[0]) - sum(w) / len(w)) < 0.006 and abs(money(av[1]) - sum(lo) / len(lo)) < 0.006, av)
        check("e. stats: best / worst trade", usd(max(pn), True) in tiles.get("BEST / WORST", "") and usd(min(pn), True) in tiles.get("BEST / WORST", ""), tiles.get("BEST / WORST"))
        cur, s0 = 0, (1 if pn[0] > 0 else -1)
        for x in pn:
            if (1 if x > 0 else -1) != s0:
                break
            cur += 1
        best, run = 0, 0
        for x in reversed(pn):
            run = run + 1 if x > 0 else 0
            best = max(best, run)
        streak = tiles.get("STREAK", "")
        check("e. stats: the current streak (newest first) and the best run",
              f"{cur} {('win' if cur == 1 else 'wins') if s0 > 0 else ('loss' if cur == 1 else 'losses')}" in streak and f"best run {best} wins" in streak, (streak, cur, best))
        check("e. stats: profit factor, green days, best / worst day, max drawdown",
              f"{sum(w) / -sum(lo):.2f}" in tiles.get("PROFIT FACTOR", "") and "GREEN DAYS" in tiles and "BEST / WORST DAY" in tiles
              and "from peak" in tiles.get("MAX DRAWDOWN", ""), tiles)
        check("e. stats name their sample (last N closed trades)", f"last {len(pn)} closed trades" in p.inner_text("#sec-stats"))
        # trades: show more
        n_tr = len(j["trades"])
        check("e. recent trades: 10 first, then Show more", p.locator("#trList > li.row").count() == 10 and "10 more · 20 left" in p.inner_text("#sec-tr .more").lower())
        p.click("#sec-tr .more")
        p.click("#sec-tr .more")
        check(f"e. Show more twice: all {n_tr}, then Show fewer", p.locator("#trList > li.row").count() == n_tr and p.inner_text("#sec-tr .more").lower() == "show fewer")
        p.click("#sec-tr .more")
        check("e. Show fewer: back to 10", p.locator("#trList > li.row").count() == 10)
        check("e. trades are newest first with sell P&L", "+$2.50" in p.inner_text("#trList > li.row >> nth=0") and "Sell 5 @ 30¢" in p.inner_text("#trList > li.row >> nth=0"),
              p.inner_text("#trList > li.row >> nth=0"))
        # calendar
        tday = dt.datetime.now(NY).date()
        dmap = dict((d, x) for d, x in j["days"])
        check("e. calendar opens on the latest month, today ringed", p.inner_text("#calMonth").upper() == tday.strftime("%B %Y").upper()
              and p.locator("#sec-cal .cd.today").count() == 1, p.inner_text("#calMonth"))
        wds = [x.inner_text() for x in p.locator("#sec-cal .wd").all()]
        mon0 = tday - dt.timedelta(days=tday.weekday())
        wk = sum(x for d, x in dmap.items() if mon0.isoformat() <= d <= tday.isoformat() and d[:7] == tday.isoformat()[:7])
        row = p.evaluate("""(k) => { const c = document.querySelector(`#sec-cal .cd[data-v='${k}']`); let n = c; while (n && !n.classList.contains('cw')) n = n.nextElementSibling; return n ? n.textContent : null; }""", tday.isoformat())
        check("e. calendar weeks start on Monday (the bot's week): this row's total is this week's days in the month",
              wds[:7] == ["M", "T", "W", "T", "F", "S", "S"] and row is not None and abs(money("$" + row.replace("+", "").replace("k", "")) - abs(wk)) < 0.06 * max(1, abs(wk)) if abs(wk) < 1000 else True, (wds, row, wk))
        p.click("#sec-cal [aria-label='Previous month']")
        pm = tday.replace(day=1) - dt.timedelta(days=1)
        in_pm = {d: x for d, x in dmap.items() if d.startswith(pm.strftime("%Y-%m"))}
        colored = p.locator("#sec-cal .cd[class*=' p'], #sec-cal .cd[class*=' n'], #sec-cal .cd.z").count()
        check("e. previous month: one colored cell per day with P&L, week totals, the month's total",
              p.inner_text("#calMonth").upper() == pm.strftime("%B %Y").upper() and colored == len(in_pm) and p.locator("#sec-cal .cw").count() >= 4
              and usd(sum(in_pm.values()), True) in p.inner_text("#sec-cal .card-h"), (colored, len(in_pm)))
        dk, dx = sorted(in_pm.items())[3]
        p.click(f"#sec-cal .cd[data-v='{dk}']")
        cr = p.inner_text("#calRead")
        d0 = dt.date.fromisoformat(dk) - dt.timedelta(days=dt.date.fromisoformat(dk).weekday())
        wsum = sum(dmap.get((d0 + dt.timedelta(days=i)).isoformat(), 0) for i in range(7))
        check("e. tapping a day reads its P&L and its week's (Monday-Sunday)", usd(dx, True) in cr and f"its week {usd(wsum, True)}" in cr
              and p.get_attribute(f"#sec-cal .cd[data-v='{dk}']", "aria-pressed") == "true", (cr, dk, dx, usd(wsum, True)))
        for _ in range(4):
            if p.locator("#sec-cal [aria-label='Previous month']").is_enabled():
                p.click("#sec-cal [aria-label='Previous month']")
        check("e. back at the first month with data: Previous is off, Next is on", p.locator("#sec-cal [aria-label='Previous month']").is_disabled()
              and p.locator("#sec-cal [aria-label='Next month']").is_enabled()
              and p.inner_text("#calMonth").upper() == dt.date.fromisoformat(j["days"][0][0]).strftime("%B %Y").upper())
        check("e. daily bars: the last 30 days", p.locator("svg.bars rect").count() == 30)
        shot(p, "4_wide")
        # new data while the sort picker is open: the page waits for it to close, then shows the new numbers
        p.focus("#posSort")
        FEED["j"] = {**j, "balance": 401.5, "t": int(time.time()) - 30}
        h1 = FEED["hits"]
        p.evaluate("window.dispatchEvent(new Event('online'))")                 # a timed refresh: the focus stays on the picker
        p.wait_for_function("document.querySelector('#refresh').getAttribute('aria-busy') === 'false'")
        p.wait_for_timeout(150)
        held = "$401.50" not in p.locator("#sec-kpi").text_content() and p.evaluate("document.activeElement.id") == "posSort"
        p.evaluate("document.activeElement.blur()")
        p.wait_for_timeout(100)
        check("e. new data while the sort picker is open: drawn once it closes (never closes it under the finger)",
              FEED["hits"] > h1 and held and "$401.50" in p.locator("#sec-kpi").text_content(), (FEED["hits"] - h1, held))
        FEED["j"] = j
        # refresh keeps the UI (sort) when nothing changed
        p.select_option("#posSort", "pnl")
        h0 = FEED["hits"]
        p.click("#refresh")
        ready(p)
        check("e. Refresh asks the feed again and keeps the sort", FEED["hits"] > h0 and p.input_value("#posSort") == "pnl")

        # ---- the feed's two addresses
        n0 = dict(FEED["n"])
        FEED["raw"], FEED["api"] = "500", None
        open_("ok", sample(time.time()))
        check("f. raw.githubusercontent down: the GitHub API of kalshi-feed answers, the numbers show",
              p.get_attribute("#body", "data-state") == "ok" and "$512.34" in text(p) and FEED["n"]["api"] > n0["api"], FEED["n"])
        n1 = dict(FEED["n"])
        FEED["raw"], FEED["api"] = None, None
        open_("404", clear=True)
        check("f. a 404 from kalshi-feed = not connected yet (waiting), without asking the API",
              p.get_attribute("#body", "data-state") == "waiting" and FEED["n"]["api"] == n1["api"] and FEED["n"]["raw"] > n1["raw"], FEED["n"])

        # ---- f. stale, stopped, error, offline copy, loading
        open_("ok", {**sample(time.time()), "t": int(time.time()) - 3600})
        check("f. stale (an hour old): amber pill, the note says the bot stopped sending, numbers still shown",
              "NOT UPDATING" in p.inner_text("#sub").upper() and p.locator("#pill.warn").count() == 1 and "every minute" in p.inner_text(".note.warn")
              and "1 h ago" in p.inner_text(".note.warn") and "$512.34" in text(p) and p.get_attribute("#body", "data-state") == "stale"
              and not re.search(r"\bPC\b", text(p)))
        shot(p, "5_stale")
        open_("ok", {**sample(time.time()), "running": False})
        check("f. the bot says it stopped: red Stopped pill", p.locator("#pill.bad").inner_text().upper() == "STOPPED")
        open_("500")
        check("f. error with no saved copy: says so, offers Try again", "No connection to the Kalshi feed right now" in text(p)
              and p.inner_text("#sub") == "Could not reach the Kalshi feed" and p.locator("[data-act=retry]").count() == 1
              and p.get_attribute("#body", "data-state") == "error")
        open_("bad")
        check("f. bad JSON counts as an error", p.get_attribute("#body", "data-state") == "error")
        FEED["mode"], FEED["j"] = "ok", sample(time.time())
        p.click("[data-act=retry]")
        ready(p)
        check("f. Try again recovers", p.get_attribute("#body", "data-state") == "ok" and "$512.34" in text(p))
        FEED["mode"] = "abort"
        p.reload()
        ready(p)
        check("f. no connection: the offline copy with its age, marked in the header",
              p.get_attribute("#body", "data-state") == "offline" and "OFFLINE COPY" in p.inner_text(".note.bad").upper() and "offline copy" in p.inner_text("#sub")
              and "$512.34" in text(p) and "+$18.50" in text(p))
        shot(p, "6_offline")
        FEED["mode"] = "ok"
        p.click(".note.bad [data-act=retry]")
        ready(p)
        check("f. back online: the note goes", p.locator(".note.bad").count() == 0 and p.get_attribute("#body", "data-state") == "ok")
        FEED["mode"] = "hold"
        p.reload()
        p.wait_for_timeout(250)
        check("f. loading with a saved copy: the copy at once, Refresh spinning", "$512.34" in text(p) and p.get_attribute("#refresh", "aria-busy") == "true"
              and p.get_attribute("#body", "data-state") == "loading")
        release()
        ready(p)
        FEED["mode"] = "hold"
        p.evaluate("localStorage.clear()")
        p.reload()
        p.wait_for_timeout(250)
        check("f. loading with nothing saved: placeholder cards, 'Loading…', busy",
              p.locator("#body .sk").count() == 3 and p.inner_text("#sub") == "Loading…" and p.get_attribute("#body", "aria-busy") == "true")
        shot(p, "7_loading")
        release()
        ready(p)
        check("f. then the data", p.get_attribute("#body", "data-state") == "ok" and p.get_attribute("#body", "aria-busy") == "false")

        # ---- g. escaping, empty, junk
        evil = '<script>window.__x=1</script><img src=x onerror="window.__x=2">'
        n0 = int(time.time())
        ev = v2({**kp.SAMPLE, "t": n0 - 60, "name": evil, "status": evil, "note": evil, "mode": evil,
                 "positions": [{**kp.SAMPLE["positions"][0], "title": evil + " pos", "ticker": evil}, {**kp.SAMPLE["positions"][0], "side": evil}],
                 "trades": [{**kp.SAMPLE["trades"][0], "title": evil + " trade", "action": evil, "side": evil}],
                 "strategies": [{"name": evil, "mode": evil, "running": True, "today_pnl": 1, "total_pnl": 2, "trades": 3, "wins": 2, "losses": 1}],
                 "equity": [[n0 - 86400, 500], [n0, 512.34]]}, n0)
        open_("ok", ev)
        p.wait_for_timeout(200)
        x = p.evaluate("[typeof window.__x, document.querySelectorAll('#body script, #body img, #sub img, #sub script').length]")
        bt = text(p)
        check("g. <script> / <img onerror> in names, titles, tickers, sides, status, note, mode: shown as text, never run",
              x == ["undefined", 0] and "<script>window.__x=1</script>" in bt and bt.count("onerror") >= 5 and not dialogs, (x, dialogs))
        p.click("#posList > li >> nth=0 >> summary")
        check("g. escaped in the details too", p.evaluate("document.querySelectorAll('#body img, #body script').length") == 0)
        emp = {**sample(time.time()), "positions": [], "trades": [], "days": [], "strategies": [], "equity": []}
        open_("ok", emp)
        bt = text(p)
        check("g. empty lists: each section says so, nothing breaks",
              "No open bets right now." in bt and "No trades yet." in bt and "No history yet" in bt and "No daily P&L yet." in bt and "No stats yet" in bt
              and p.locator("#sec-strat").count() == 0 and p.locator("#sec-cal").count() == 0 and "$512.34" in bt, bt[:500])
        junk = {"v": 1, "kind": "kalshi", "t": int(time.time()) - 60, "balance": "abc", "today_pnl": None, "running": "yes",
                "positions": "nope", "trades": {"a": 1}, "days": [1, ["x"], ["2026-10-30", "NaN"], {"date": "2026-10-31", "pnl": "4.5"}],
                "strategies": "no", "equity": [["a", "b"], [5, 6], None], "mode": 7}
        open_("ok", junk)
        bt = text(p)
        check("g. junk values: dashes, no crash, the one good day kept", "could not be shown" not in bt and "—" in bt
              and p.locator("svg.bars rect").count() == 1, bt[:400])

        # ---- h. its own theme (owner 2026-11-02 "everything its own dashboard"): Jarvis's theme never changes it
        open_("ok", sample(time.time()))
        acc = lambda: p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--c').trim()")  # noqa: E731
        bg = lambda: p.evaluate("getComputedStyle(document.body).backgroundColor")  # noqa: E731
        check("h. the Kalshi theme (mint #1fe5a6) on its own top colour's background", p.get_attribute("html", "data-theme") == "kalshi"
              and acc() == "#1fe5a6" and bg() == "rgb(1, 10, 7)", (acc(), bg()))
        for val in ("reactor", '"reactor-ice"', "eclipse"):
            p.evaluate(f"localStorage.setItem('jtheme', {json.dumps(val)})")
            p.reload()
            ready(p)
            check(f"h. Jarvis's jtheme {val} leaves it as it is", p.get_attribute("html", "data-theme") == "kalshi" and acc() == "#1fe5a6")
        p.evaluate("localStorage.removeItem('jtheme')")

        # ---- v3. alerts, live edge, Kelly, by market, by price, calibration (contract v3, 2026-11-03)
        n3 = int(time.time())
        closes = dt.datetime.fromtimestamp(n3 + 480, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        raw3 = {**kp.SAMPLE_V3, "t": n3 - 60, "balance": 100.0,
                "positions": [{"ticker": "KXETH15M-26NOV031215-15", "title": "ETH up or down", "side": "no", "contracts": 10, "avg_price": 0.9,
                               "price": 0.92, "prob": 0.97, "closes": closes, "category": "Ethereum"}],
                "kelly": {"fraction": 0.25, "bankroll": 100.0, "max_bet": 50},
                "alerts": [{"t": n3 - 300, "level": "bad", "text": "Down $12 today"}, {"t": n3 - 900, "level": "nonsense", "text": "<img src=x onerror=alert(1)>"}]}
        open_("ok", kp.clean(raw3))
        al = p.inner_text("#sec-al")
        check("v3. alerts: the bot's own (bad first, an unknown level = info, escaped) and 'settles soon' with its countdown",
              p.locator("#sec-al .al li").count() == 3 and p.locator("#sec-al .al li.bad").count() == 1 and "Down $12 today" in al
              and "<img src=x onerror=alert(1)>" in al and p.locator("#sec-al img").count() == 0 and "Settles soon" in al
              and p.locator("#sec-al .cdn[data-c]").count() == 1 and "1 needs you" in al, al)
        pos3 = p.inner_text("#sec-pos")
        # edge = chance 0.97 - price now 0.92 = +5.0c; EV = 10 x 0.05 = +$0.50
        check("v3. open bets: live edge on the row, Live edge EV and Next settles in the header",
              "edge +5.0¢" in pos3 and "+$0.50" in pos3 and "Next settles" in pos3, pos3[:300])
        k3 = p.inner_text("#sec-kelly")
        # full Kelly (0.97 - 0.92) / (1 - 0.92) = 62.5% (shown 62%, float); a quarter of $100 = $15.62; bet $9.00 = 0.58 of it -> on size
        check("v3. Edge & sizing: Kelly per open bet (62.5% full, quarter = $15.62 of the bot's bankroll), its size tag",
              "62%" in k3 and "$15.62" in k3 and "ON SIZE" in k3.upper() and "25% Kelly" in k3 and "$100.00" in k3, k3)
        p.click("#sec-kelly [data-act=kf][data-v='1']")
        check("v3. Full Kelly: capped at the bot's max bet ($50)", "$50.00 (max bet)" in p.inner_text("#sec-kelly")
              and p.get_attribute("#sec-kelly [data-v='1']", "aria-pressed") == "true", p.inner_text("#sec-kelly"))
        p.fill("#kcP", "62")
        p.fill("#kcC", "55")
        out3 = p.inner_text("#kcOut")
        # (0.62 - 0.55) / 0.45 = 15.6% full Kelly; $15.56 of $100 -> 28 contracts at 55c
        check("v3. the calculator: chance 62% at 55¢ -> 16% of the bankroll, +7.0¢ edge, bet $15.56 ≈ 28 contracts; inputs 16px",
              "16% of the bankroll" in out3 and "edge +7.0¢" in out3 and "$15.56" in out3 and "28 contracts" in out3
              and p.evaluate("getComputedStyle(document.getElementById('kcP')).fontSize") == "16px", out3)
        p.fill("#kcP", "40")
        check("v3. the calculator: a price above your chance = No bet", "No bet" in p.inner_text("#kcOut"))
        cat3 = p.inner_text("#sec-cat")
        check("v3. by market: the bot's categories, best first, win rate and ROI (Weather 27-14 = 66%, $80.40 on $402.50 = +20%)",
              cat3.index("Weather") < cat3.index("S&P 500 range") and "win 66%" in cat3 and "ROI +20%" in cat3 and "+$80.40" in cat3
              and "From the last" not in cat3 and p.locator("#sec-cat .dv i.pos").count() == 2, cat3)
        bk3 = p.inner_text("#sec-bk")
        check("v3. by price: ranges in cents, win rate vs break-even, ROI and P&L", "20–40¢" in bk3 and "40–60¢" in bk3 and "needs ~50%" in bk3
              and "+$61.20" in bk3 and p.locator("#sec-bk tbody tr").count() == 3, bk3)
        cb3 = p.inner_text("#sec-cb")
        check("v3. calibration: a dot per group, the diagonal, the bot's own chance named, the weighted gap in points",
              p.locator("#sec-cb circle").count() == 3 and p.locator("#sec-cb .cb-d").count() == 1 and "the bot's own chance" in cb3
              and "pts" in cb3, cb3)
        stt3 = p.inner_text("#sec-stats")
        check("v3. stats: all-time win rate and ROI from the bot's totals (34-19 = 64%; $112.34 on $542.50 = +21%)",
              "64%" in stt3 and "+21%" in stt3, stt3)
        check("v3. the ticker tape under the header (open bet and results), hidden from screen readers",
              p.is_visible("#tape") and "edge +5.0¢" in p.inner_text("#tape") and p.get_attribute("#tape", "aria-hidden") == "true")
        shot(p, "9_v3")
        # a v2 feed: the same sections from the recent trades list, said so; no alerts list -> a losing run is found
        lose = [{"t": n3 - 600 * i, "ticker": f"KXHYPE15M-X{i}", "title": "HYPE up or down", "side": "yes", "action": "buy", "contracts": 10,
                 "price": 0.96, "pnl": -9.6 if i < 3 else 0.4, "asset": "HYPE"} for i in range(8)]
        open_("ok", kp.clean({**kp.SAMPLE_V2, "t": n3 - 60, "trades": lose}))
        check("v3. a v2 feed: by market / by price / calibration from the trades list, labelled; a 3-loss run alert; Edge & sizing calculator",
              all(p.locator(x).count() == 1 for x in ("#sec-cat", "#sec-bk", "#sec-cb", "#sec-kelly"))
              and "From the last 8 settled trades" in p.inner_text("#sec-cat") and "3 losses in a row" in p.inner_text("#sec-al")
              and "95–97¢" in p.inner_text("#sec-bk") and "the price paid" in p.inner_text("#sec-cb"), p.inner_text("#sec-al"))
        junk3 = {**kp.SAMPLE_V2, "t": n3 - 60, "categories": "x", "buckets": [{"lo": "a"}], "calibration": [None, {"p": 5}], "alerts": {"a": 1},
                 "kelly": [1], "stats": "x", "positions": [{**kp.SAMPLE["positions"][0], "prob": "abc"}]}
        open_("ok", junk3)
        check("v3. junk v3 values (sent raw, not cleaned): no section fails, no page error", "could not be shown" not in text(p)
              and p.locator("#sec-al").count() == 1)

        # ---- i. notch insets (iPhone, emulated 47 px top / 34 px bottom): on its own the page clears the notch; inside Jarvis
        # (framed under its bar) it must not add the notch a second time
        cdp = ctx.new_cdp_session(p)
        cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": 47, "bottom": 34, "left": 0, "right": 0}})
        open_("ok", realbot(time.time())[0])
        own = p.evaluate("[document.documentElement.classList.contains('framed'), getComputedStyle(document.querySelector('main')).paddingTop, "
                         "Math.round(document.querySelector('h1').getBoundingClientRect().top)]")
        check("i. on its own with a 47 px notch: the page clears it (63 px top padding), not framed", own[0] is False and own[1] == "63px" and own[2] >= 63, own)
        p.goto(url + "host.html")
        fr = p.frame_locator("#f")
        fr.locator("#sec-kpi").wait_for(timeout=8000)
        inner = fr.locator("html").evaluate("(d) => [d.classList.contains('framed'), getComputedStyle(d.querySelector('main')).paddingTop, "
                                            "Math.round(d.querySelector('h1').getBoundingClientRect().top)]")
        check("i. inside Jarvis with a 47 px notch: no second inset (16 px under the bar, no empty band)",
              inner[0] is True and inner[1] == "16px" and inner[2] <= 20, inner)
        shot(p, "8a_framed_notch")
        cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": 0, "bottom": 0, "left": 0, "right": 0}})
        cdp.detach()

        # ---- i. phone widths (the preview too)
        p.set_viewport_size({"width": 375, "height": 844})
        open_("404")
        p.click("[data-act=preview]")
        m = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth, document.getElementById('previewBar').getBoundingClientRect().right, window.innerWidth]")
        check("i. 375px preview: no sideways scroll, the banner inside the gutters", m[0] <= m[1] and m[2] <= m[3] - 15.5, m)
        small = p.evaluate(TARGETS)
        check("i. 375px preview: every control's hit area at least 44 x 44 (calendar days, Refresh, ranges, Exit preview ...)", not small, small[:6])
        for wdt in (375, 390, 430):
            p.set_viewport_size({"width": wdt, "height": 844})
            for name, payload in (("wide", wide(time.time(), long_text=True)), ("real bot", realbot(time.time())[0])):
                open_("ok", payload)
                if FONTS:                                                       # measured with the final fonts (the page re-fits then)
                    try:
                        p.wait_for_function("document.fonts.check('700 15px Orbitron') && document.fonts.check('500 16px Rajdhani')", timeout=6000)
                        fin = True
                    except Exception:
                        fin = False
                    if wdt == 375 and name == "wide":
                        check("i. Jarvis's fonts in use (plain @font-face): Orbitron for numbers, Rajdhani for text", fin)
                p.evaluate("document.fonts.ready.then(() => true)")
                if p.locator("#posList > li.pos").count():
                    p.click("#posList > li >> nth=0 >> summary")
                m = p.evaluate("""() => {
                    const W = window.innerWidth, de = document.documentElement;
                    const els = [...document.querySelectorAll('.top, .top > *, #body > *, #body .card > *, #body .rows > li, #body .stat, #body .kpis > div, #body .cal > *, #body .tbl, #body .dl > div, #body .seg, #body .sel, #body .q')];
                    const out = els.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > W - 15.5 || r.left < 15.5); })
                      .map((e) => (e.id || e.className || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().left) + '-' + Math.round(e.getBoundingClientRect().right));
                    const cut = [...document.querySelectorAll('#body .fit, #body .cal .cd em, #body .cw, #body .tbl td:not(:first-child), #body .v, #body .v2, #body .kpis em, .sub > *')]
                      .filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.className + ':' + e.textContent);
                    const q = document.getElementById('posQ'), s = document.getElementById('posSort');
                    return [de.scrollWidth, de.clientWidth, out, cut, q ? getComputedStyle(q).fontSize : '16px', s ? getComputedStyle(s).fontSize : '16px'];
                }""")
                check(f"i. {wdt}px {name}: no sideways scroll, every card and row inside the 16 px gutters", m[0] <= m[1] and not m[2], m[:3])
                check(f"i. {wdt}px {name}: no number cut off (KPIs, stats, calendar, table, rows, header)", not m[3], m[3])
                check(f"i. {wdt}px {name}: search and sort at 16px (no zoom on focus)", m[4] == "16px" and m[5] == "16px", m[4:])
                cut = p.evaluate("""() => [...document.querySelectorAll('#body *, .top *')].filter((e) => { const c = getComputedStyle(e);
                    return (c.textOverflow === 'ellipsis' || c.overflowX === 'hidden') && e.getClientRects().length && e.scrollWidth > e.clientWidth + 1; })
                    .map((e) => (e.className || e.tagName) + ': ' + e.textContent.slice(0, 40))""")
                check(f"i. {wdt}px {name}: no text cut off anywhere (strategy lines, stats, rows wrap)", not cut, cut[:5])
                if wdt == 375:
                    small = p.evaluate(TARGETS)
                    check(f"i. 375px {name}: every control's hit area at least 44 x 44", not small, small[:6])
                shot(p, f"8_{name.replace(' ', '')}_{wdt}")
        check("j. no page errors", not errs, errs)
        check("j. no section failed and no script error in the console", not cons, cons[:5])
        miss = [b_ for b_ in bad if not (not FONTS and ".woff2" in b_[1])]     # a checkout without Jarvis's fonts: only those may be missing
        check("j. no failed same-site request (nothing missing on the site)", not miss, miss[:5])
        if FONTS:
            check("j. Jarvis's fonts load from ../jarvis/ (all 200)", fontres and all(st_ == 200 for st_, _ in fontres), fontres[:6])
        else:
            print("       (this checkout has no tools/web_public/jarvis/*.woff2: the font requests 404 here; strict once the fonts are in)")
        check("j. kalshi.json only ever asked from kalshi-feed (raw, then the API)", not FEED["wrong"], FEED["wrong"][:3])
        part_k(br, url, tmp)
        part_kit(br, url, tmp)
        br.close()


def part_k(br, url, tmp):
    """The service worker: offline, a 404 site, a slow site, no saved copy, an update, Jarvis's fonts."""
    page_url = url + "kalshi/"
    kdir = os.path.join(tmp, "nq-dashboard", "kalshi")
    ver = re.search(r"kalshi\.js\?v=(\w+)", open(os.path.join(KS, "index.html"), encoding="utf-8").read()).group(1)
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    q = ctx.new_page()
    errs, bad = [], []
    q.on("pageerror", lambda e: errs.append(str(e)))
    nofont = lambda u: FONTS or ".woff2" not in u                    # noqa: E731  (a checkout without Jarvis's fonts: their 404s only)
    q.on("console", lambda m: errs.append((m.text, (m.location or {}).get("url", ""))) if m.type == "error" and SITE["mode"] == "ok" and not SITE["slow"]
         and nofont((m.location or {}).get("url", "")) and "kalshi.json" not in (m.location or {}).get("url", "") else None)   # the feed's 404 = waiting
    q.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and "127.0.0.1" in r.url and SITE["mode"] == "ok" and nofont(r.url) else None)
    pg = lambda: q.evaluate("document.title === 'Kalshi' && !!document.getElementById('body')")  # noqa: E731

    def until(js, timeout=10000):
        try:
            q.wait_for_function(js, timeout=timeout)
            return True
        except Exception:
            return False
    allc = "(async () => { const o = {}; for (const k of await caches.keys()) o[k] = (await (await caches.open(k)).keys()).map((r) => r.url); return o; })()"
    cn = f"kalshi-{ver}"
    FEED["mode"], FEED["j"] = "ok", realbot(time.time())[0]
    SITE.update(mode="ok", slow=0.0)
    q.goto(page_url)
    ready(q)
    reg = q.evaluate("navigator.serviceWorker.ready.then((r) => [r.scope, r.active ? r.active.state : ''])")
    check("k. the page registers kalshi/sw.js for its own folder", reg[0].endswith("/nq-dashboard/kalshi/") and reg[1] in ("activating", "activated"), reg)
    until(f"caches.open('{cn}').then((c) => c.keys()).then((k) => k.length >= 4)")
    c = q.evaluate(allc)
    urls = c.get(cn, [])
    shell = all(any(u.endswith(x) for u in urls) for x in ("/kalshi/", "/kalshi/index.html", f"/kalshi/kalshi.css?v={ver}", f"/kalshi/kalshi.js?v={ver}"))
    check(f"k. its own cache '{cn}' holds the page, its style and its script", list(c) == [cn] and shell, c)
    fonts = sorted(u.rsplit("/", 1)[1] for u in urls if u.endswith(".woff2"))
    if FONTS:
        check("k. Jarvis's fonts on the site: the worker keeps all five for offline",
              fonts == ["orbitron.woff2", "rajdhani-400.woff2", "rajdhani-500.woff2", "rajdhani-600.woff2", "rajdhani-700.woff2"], fonts)
    else:
        check("k. Jarvis's fonts not in this checkout: the worker keeps nothing for them", fonts == [], fonts)
    q.reload()
    ready(q)
    check("k. the next open is run by the worker", q.evaluate("!!navigator.serviceWorker.controller"))
    if FONTS:
        check("k. Orbitron and Rajdhani in use (plain @font-face)",
              until("document.fonts.check('700 15px Orbitron') && document.fonts.check('500 16px Rajdhani')", 6000))
    # offline: every connection to the site dropped, and the feed too
    SITE["mode"], FEED["mode"] = "down", "abort"
    q.reload()
    ready(q)
    check("k. offline: the page opens from its saved copy, with the numbers saved on this phone",
          pg() and q.get_attribute("#body", "data-state") == "offline" and "$67.98" in text(q) and q.locator("#sec-kpi").count() == 1)
    if FONTS:
        check("k. offline: still Orbitron and Rajdhani (the worker answers the fonts from its copy)",
              until("document.fonts.check('700 15px Orbitron') && document.fonts.check('500 16px Rajdhani')", 6000))
    shot(q, "k1_offline")
    # a 404 site
    SITE["mode"], FEED["mode"] = "404", "ok"
    q.reload()
    ready(q)
    check("k. a 404 site (GitHub's 'Site not found'): the saved copy, never GitHub's page",
          pg() and q.get_attribute("#body", "data-state") == "ok" and "$67.98" in text(q) and "Site not found" not in q.content())
    # a slow site: the saved copy within NAV_WAIT_MS (its style and script from their copies), the late answer refreshes it
    SITE.update(mode="ok", slow=6.0)
    idx = os.path.join(kdir, "index.html")
    orig = open(idx, encoding="utf-8").read()
    open(idx, "w", encoding="utf-8").write(orig.replace("</body>", "<!-- k-late -->\n</body>"))
    t0 = time.time()
    q.reload(wait_until="commit")
    drawn = until("document.title === 'Kalshi' && !!document.getElementById('body') && document.getElementById('body').getAttribute('data-state') === 'ok'", 15000)
    took = time.time() - t0
    check(f"k. a slow site (6 s): the saved copy is drawn in under 5 s ({took:.1f} s), style and script from their copies", drawn and took < 5.0, took)
    check("k. the late answer still refreshes the saved copy",
          until(f"caches.open('{cn}').then((c) => c.match(location.href)).then((r) => r ? r.text() : '').then((t) => t.indexOf('k-late') >= 0)", 12000))
    open(idx, "w", encoding="utf-8").write(orig)
    SITE["slow"] = 0.0
    q.wait_for_timeout(300)
    # no saved copy and offline: a small dark page with Retry
    q.evaluate(f"caches.delete('{cn}')")
    SITE["mode"] = "down"
    q.reload(wait_until="commit")
    retry = until("!!document.querySelector('button') && /Retry/.test(document.body.innerText)", 10000)
    bg = q.evaluate("getComputedStyle(document.body).backgroundColor") if retry else ""
    check("k. offline with no saved copy: a small dark page with Retry, never a browser error or a white screen",
          retry and "can’t reach the internet" in q.inner_text("body") and bg == "rgb(0, 0, 0)", (retry, bg))
    shot(q, "k2_retry")
    SITE["mode"] = "ok"
    q.click("text=Retry")
    back = until("document.title === 'Kalshi' && !!document.getElementById('body') && document.getElementById('body').getAttribute('data-state') === 'ok'", 10000)
    check("k. Retry once back online: the page again", back)
    # an update (a new cache name): only the old 'kalshi-*' copy goes, never another app's cache
    until(f"caches.open('{cn}').then((c) => c.keys()).then((k) => k.length >= 3)")
    q.evaluate("Promise.all([caches.open('jarvis-v3').then((c) => c.put('/x-jarvis', new Response('j'))),"
               " caches.open('le-public-x').then((c) => c.put('/x-zenith', new Response('z')))]).then(() => true)")
    swp = os.path.join(kdir, "sw.js")
    sw0 = open(swp, encoding="utf-8").read()
    open(swp, "w", encoding="utf-8").write(sw0.replace(f"const CACHE = '{cn}';", f"const CACHE = '{cn}u';"))
    q.evaluate("navigator.serviceWorker.getRegistration().then((r) => r.update()).then(() => true)")
    upd = until(f"caches.keys().then((k) => k.indexOf('{cn}u') >= 0 && k.indexOf('{cn}') < 0)", 15000)
    keys = q.evaluate("caches.keys()")
    check(f"k. an update: the old '{cn}' goes, Jarvis's and Zenith's caches stay", upd and "jarvis-v3" in keys and "le-public-x" in keys, keys)
    open(swp, "w", encoding="utf-8").write(sw0)
    c = q.evaluate(allc)
    check("k. kalshi.json never cached (the feed is cross-origin and left alone)", not any("kalshi.json" in u for v in c.values() for u in v), c)
    # kit.json is network first: a new pin on the site shows on the next open; offline, the saved pin stays
    kj = os.path.join(kdir, "kit.json")
    new = hashlib.sha256(b"a newer kalshi_status_vm.py").hexdigest()
    with open(kj, "w", encoding="utf-8") as f:
        f.write(json.dumps({"v": 1, "file": "kalshi_status_vm.py", "sha256": new}))
    FEED["mode"] = "404"
    q.reload()
    ready(q)
    check("k. kit.json network first: a new sha256 on the site is the step's on the next open",
          until(f"(document.getElementById('step') || {{}}).textContent.indexOf('{new}') > 0", 5000))
    SITE["mode"] = "down"
    q.reload()
    check("k. offline: the Connect card keeps the last pin (the worker's saved kit.json)",
          until(f"(document.getElementById('step') || {{}}).textContent.indexOf('{new}') > 0", 8000))
    SITE["mode"] = "ok"
    with open(kj, "w", encoding="utf-8") as f:
        f.write(KIT_JSON)
    check("k. no page or console errors, no failed same-site requests in the normal runs", not errs and not bad, (errs[:3], bad[:3]))
    ctx.close()


def part_kit(br, url, tmp):
    """The pin on its own (no service worker): kit.json valid, invalid, missing or slow."""
    page_url = url + "kalshi/"
    kj = os.path.join(tmp, "nq-dashboard", "kalshi", "kit.json")
    ctx = br.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=url.rstrip("/").rsplit("/", 1)[0])
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    q = ctx.new_page()
    errs = []
    q.on("pageerror", lambda e: errs.append(str(e)))
    FEED.update(mode="404", raw=None, api=None)

    def step(content, slow=0.0):
        if content is None:
            if os.path.exists(kj):
                os.remove(kj)
        else:
            with open(kj, "w", encoding="utf-8") as f:
                f.write(content)
        SITE["kit_slow"] = slow
        q.goto(page_url)
        ready(q)
        q.wait_for_timeout(int(slow * 1000) + 700 if slow else 500)      # the pin settles (or is given up at 3 s)
        SITE["kit_slow"] = 0.0
        return q.locator("#step").inner_text()

    def copied():
        q.click("[data-act=copy]")
        q.wait_for_function("document.getElementById('copied').textContent.length > 0", timeout=3000)
        return q.evaluate("navigator.clipboard.readText().catch(() => '')")
    got = step(KIT_JSON)
    check("kit. a valid kit.json: the step is exactly the pinned line", got == STEP_PINNED, got)
    check("kit. Copy copies the whole line to paste, the hash included", copied() == PASTE_PINNED)
    for label, content in (("an uppercase hash", json.dumps({"v": 1, "sha256": KIT_SHA.upper()})), ("a 63-character hash", json.dumps({"v": 1, "sha256": KIT_SHA[:63]})),
                           ("a hash with a space", json.dumps({"v": 1, "sha256": KIT_SHA[:63] + " "})), ("no sha256", json.dumps({"v": 1, "file": "kalshi_status_vm.py"})),
                           ("a number", json.dumps({"v": 1, "sha256": 5})), ("a list", json.dumps([KIT_SHA])), ("bad JSON", "{not json"), ("no kit.json (404)", None)):
        got = step(content)
        check(f"kit. {label}: the step stays exactly today's text", got == STEP, got)
    check("kit. unpinned, Copy copies today's message", copied() == PASTE)
    got = step(KIT_JSON, slow=4.0)
    check("kit. kit.json slower than 3 s: today's text, nothing waits on it", got == STEP and q.get_attribute("#body", "data-state") == "waiting", got)
    with open(kj, "w", encoding="utf-8") as f:
        f.write(KIT_JSON)
    check("kit. no page errors", not errs, errs[:3])
    ctx.close()


def main():
    part_a()
    tmp = site(tempfile.mkdtemp(prefix="le_kalshi_page_"))
    srv = serve(tmp)
    try:
        run_browser(f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/", tmp)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
