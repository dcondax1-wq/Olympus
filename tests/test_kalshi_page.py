"""The Kalshi page (tools/web_public/kalshi/, owner 2026-11-01): the dashboard of the Kalshi bot's kalshi.json (contract:
engine/kalshi_publish.py; v2 adds `strategies` and `equity`). The bot runs 24/7 on its own server with real money (about
$68), three live strategies, often 0 open bets and many 15-minute trades a day. Runs the real page in Chromium on a local copy
of the site layout (<site>/kalshi/), the site's own ../kalshi.json served from a stub that can answer 404 / the file / 500 / bad JSON /
the host's HTML page / no connection / later, and checks:
  a. the files and the static rules (no CDN, fonts only self-hosted, Safari-16-safe script, inputs >= 16px, reduced motion,
     safe areas, the old Jarvis look and its eclipse / reactor themes)
  b. waiting (404 for the site's own kalshi.json; the old kalshi-feed repo is retired, polish2 2026-11-19): the "Connect your Kalshi bot"
     card with the one step for the bot's own chat (#step inside #body), Copy; the site's copy only, no other address; the
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
  v4. the 2026-11-04 upgrade, on a paused-bot fixture shaped like the real feed (94% wins, negative total, flat 24 h equity, 41 days,
     0 open bets): the verdict banner (plain words, every line linked), the Paused pill, the living sparkline, streak chips, drawdown
     shading and the Live / Daily switch, the rest-state explainer, the heat map (tap / keys), calibration bands, the strategy race and
     battle, the risk-of-ruin gauge with its seeded Monte Carlo fan, the timeline, SVG asset badges, settle rings on open bets, Kelly
     presets, the Kalshi City link (HEAD check), the skeleton, reduced motion, 375 / 390 / 430 widths
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

from tests import browser_kit as BK  # noqa: E402  (load-aware limits, shared launch)
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import kalshi_publish as kp  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.page_bg import PAGE_BG_JS, night_black  # noqa: E402  (the effective page background: OLYMPUS NIGHT paints <html>)

KS = os.path.join(ROOT, "tools", "web_public", "kalshi")
JV_ICON = os.path.join(ROOT, "tools", "web_public", "jarvis", "icon-192.png")
JV_THREE = os.path.join(ROOT, "tools", "web_public", "jarvis", "three.module.min.js")
STEP = ("Open your kalshi-server chat in the Claude app and paste: Set up Jarvis for my Kalshi bot by following "
        "{SITE_URL}/kalshi/SETUP.md")
STEP_T = STEP                                  # the template: {SITE_URL} is filled by the page from location.origin
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
    if os.path.exists(JV_THREE):                                                       # the 3D header's one dependency (korb.js)
        shutil.copy(JV_THREE, os.path.join(base, "jarvis", "three.module.min.js"))
    for f in glob.glob(os.path.join(os.environ.get("KALSHI_FONTS_DIR") or os.path.dirname(JV_ICON), "*.woff2")):
        shutil.copy(f, os.path.join(base, "jarvis", os.path.basename(f)))      # Jarvis's fonts: the widths are tested with them
        FONTS.append(os.path.basename(f))
    with open(os.path.join(base, "kalshi", "kit.json"), "w", encoding="utf-8") as f:     # written by the site build
        f.write(KIT_JSON)
    with open(os.path.join(base, "status_feed.json"), "w", encoding="utf-8") as f:       # the PC's public status topic (a stub host here)
        json.dump({"ntfy": "https://ntfy.invalid", "topic": "olympus-test-status"}, f)
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
        if self.path.split("?")[0].endswith("/nq-dashboard/kalshi.json"):     # the feed: this site's own copy (FEED below)
            return site_feed(self)
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


# the feed: this site's own copy, <site>/kalshi.json (pc_publish), answered by the local server (so the page's worker never stands in the
# way). polish2 2026-11-19: the old feed repo (kalshi-feed on the suspended GitHub account, raw + API) is retired: any ask of it is WRONG.
FEED = {"mode": "404", "j": None, "held": [], "hits": 0, "site": None, "n": {"site": 0}, "wrong": []}


def _send(h, status, ctype, body):
    data = body.encode("utf-8") if isinstance(body, str) else body
    h.send_response(status)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


def site_feed(h):
    FEED["hits"] += 1
    FEED["n"]["site"] += 1
    m = FEED["site"] or FEED["mode"]                 # a one-off mode, else the shared one
    if m == "hold":                                  # answered with the file once release() says so
        ev = threading.Event()
        FEED["held"].append(ev)
        ev.wait(120)
        m = "ok"
    if m == "ok":
        return _send(h, 200, "application/json", json.dumps(FEED["j"]))
    if m == "404":
        return _send(h, 404, "text/plain", "404: Not Found")
    if m == "500":
        return _send(h, 500, "text/plain", "server error")
    if m == "bad":
        return _send(h, 200, "application/json", "{not json")
    if m == "html":                                  # a host that answers a missing file with its own page
        return _send(h, 200, "text/html; charset=utf-8", "<!doctype html><title>Site</title><h1>Home</h1>")
    h.close_connection = True                        # "abort": no answer at all (no connection)
    return None


def feed(route):
    """the old GitHub addresses: never asked (retired); a request there is recorded and dropped"""
    if "kalshi" in route.request.url:
        FEED["wrong"].append(route.request.url)
    return route.abort()


def release():
    for ev in FEED["held"]:
        ev.set()
    FEED["held"] = []


def old_bot_text(p):
    """The OLD kalshi-server bot's own words (as in check b: its card, the sub line, the foot): #sub + #body + #foot without the K8
    sections (K8 runs on the owner's PC, so they say 'PC' on purpose: #kpaused, #k8d, #k8s, the K8 status / live-day cards)."""
    return p.evaluate("""() => { const b = document.querySelector('#body'); const c = b ? b.cloneNode(true) : document.createElement('div');
      c.querySelectorAll('#kpaused, #k8d, #k8s, .k8d, .k8s').forEach((e) => e.remove());
      const t = (s) => { const e = document.querySelector(s); return e ? e.innerText : ''; };
      return t('#sub') + ' ' + c.textContent + ' ' + t('#foot'); }""")


def text(p, sel="#body"):
    return p.locator(sel).inner_text()


def ready(p, timeout=30000):
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
    check("a. the one step is the exact text (tests/test_jarvis_hub reads it from #step)", f"const STEP0 = '{STEP_T}';" in js
          and "location.origin" in js and "github.io" not in js and "{SITE_URL}" in js and "fillSite(STEP0)" in js)
    check("a. the pin: kit.json (same origin, 3 s at most), a lowercase 64-hex sha256 only, the exact pinned wording, Copy takes it",
          "get('kit.json', {}, 3000)" in js and "/^[0-9a-f]{64}$/.test(h)" in js and "(only run kalshi_status_vm.py if its sha256 is ${h})" in js
          and "writeText(paste())" in js and "'./kit.json'" in sw and "u.searchParams.has('v')" in sw)
    check("a. the feed is this site's own ../kalshi.json only: never the retired kalshi-feed repo (raw / API), never the Pages repo's branch",
          "const LOCAL = new URL('../kalshi.json', location.href).href;" in js and "get(LOCAL" in code and "kalshi-feed/main" not in js and "kalshi-feed/contents" not in js
          and "ref=kalshi" not in js and "nq-dashboard/kalshi/kalshi.json" not in js and 'data-fresh="site:kalshi.json"' in html and "kalshi-feed" not in html)
    urls = set(re.findall(r"https?://[^\s'\"`)<>]+", html + js + css))
    allowed = ("http://www.w3.org/2000/svg",
               )
    fonts = re.findall(r"url\(\"?([^\")]+)\"?\)", css)
    check("a. no CDN or other site (not even GitHub: the feed is the site's own copy); fonts only self-hosted next to Jarvis, with system fallbacks",
          all(u.startswith(allowed) for u in urls) and "@import" not in css and fonts and all(f.startswith(("../jarvis/", "data:image/svg+xml")) for f in fonts)
          and '"Iowan Old Style"' in css and '"SF Pro Rounded"' in css and "Orbitron" not in css and "Rajdhani" not in css, (sorted(urls), fonts))
    risky = [w for w in ("(?<=", "(?<!", ".toSorted(", ".toReversed(", ".toSpliced(", ".findLast(", "Object.groupBy", "AbortSignal.timeout",
                         "structuredClone", "static {", ".at(-") if w in code]
    check("a. Safari 16 safe script (no lookbehind, Array copy methods, findLast, groupBy, AbortSignal.timeout ...)", not risky, risky)
    check("a. Safari 16 safe styles (no nesting, container queries, color-mix); clip-path also -webkit-",
          "@container" not in css and "color-mix(" not in css and not re.search(r"\{[^{}]*&[^{}]*\{", css) and "clip-path" not in css)
    check("a. Safari 16 layout: no grid / flex on <summary> (WebKit cannot), no CSS filter on SVG shapes (only on the <svg>)",
          not re.search(r"summary[^{},]*\{[^}]*display:\s*(grid|flex)", css) and not re.search(r"\.chart \.(ln|area|grid|base) \{[^}]*filter:", css))
    pre = css.split("@media (prefers-reduced-motion: no-preference)")[0]
    check("a. inputs and selects at 16px (no iPhone zoom); safe areas; every animation behind prefers-reduced-motion",
          re.search(r"\.q \{[^}]*font: 500 16px", css) and re.search(r"\.sel \{[^}]*font: 500 16px", css)
          and "env(safe-area-inset-left" in css and "env(safe-area-inset-bottom" in css and "viewport-fit=cover" in html
          and "@media (prefers-reduced-motion: no-preference)" in css and "animation:" not in pre)
    agora = css
    check("a. its own look: the AGORA tokens underneath, then OLYMPUS NIGHT on top (owner 2026-11-20: black, violet #9d59ee, lavender, gold only as small accents, no cyan), no neon green, no HUD clip",
          ':root, :root[data-theme="kalshi"]' in css and "--bg: var(--oly-th-n3, #14110e);" in css and "--c: var(--oly-th-a8, #c8a24a);" in css and "--cy: var(--oly-th-info, #4b7a99);" in css
          and "#1fe5a6" not in css + agora and "#38e1ff" not in css + agora and "clip-path" not in css + agora
          and "AGORA layer" in css and "OLYMPUS NIGHT" in css and "--c: #9d59ee;" in css and "--bg: #000000;" in css and "#22d3ee" not in css)
    check("a. its own top colour = its background (Jarvis's status-bar strip takes it); the theme set before paint, never Jarvis's 'jtheme'",
          '<meta name="theme-color" content="#000000">' in html and "d.setAttribute('data-theme', 'kalshi')" in html
          and html.index("data-theme', 'kalshi'") < html.index('href="kalshi.css') and "jtheme" not in html + js)
    check("a. its own header: a column mark and the plain name Kalshi; no ticker tape, no aurora, no 3D orb",
          'class="mark"' in html and "<h1>Kalshi</h1>" in html and 'id="tape"' not in html and 'class="aurora"' not in html and "korb.js" not in html)
    check("a. framed (inside Jarvis): a 'framed' class before paint drops the second notch inset; on its own the inset stays",
          "if (window.top !== window) d.classList.add('framed')" in html and html.index("framed") < html.index('href="kalshi.css')
          and "html.framed main { padding-top: 16px; }" in css and "padding: calc(16px + env(safe-area-inset-top, 0px))" in css)
    ver = re.search(r"kalshi\.js\?v=(\w+)", html).group(1)
    check("a. kalshi/sw.js: its own 'kalshi-*' cache and only those deleted, its own folder only, the 3.5 s rule, the page's versions",
          f"const CACHE = 'kalshi-{ver}';" in sw and "k.startsWith('kalshi-') && k !== CACHE" in sw and "u.pathname.startsWith(scope.pathname)" in sw
          and "const NAV_WAIT_MS = 3500;" in sw and f"'./kalshi.css?v={ver}'" in sw and f"'./kalshi.js?v={ver}'" in sw and f"kalshi.css?v={ver}" in html)
    ff = re.findall(r'@font-face \{ font-family: "(\w+)"; src: url\("\.\./jarvis/([\w-]+\.woff2)"\) format\("woff2"\);[^}]*font-display: swap; \}', css)
    check("a. no techno fonts: no @font-face for Orbitron / Rajdhani (system fonts only)",
          not ff and "@font-face" not in css and "navigator.serviceWorker.register('sw.js', { scope: './' })" in js, ff)
    check("a. every control at least 44 px (Refresh, buttons, sort, search, months, calendar days; hit pads for the compact ones)",
          all(re.search(pat, css) for pat in (r"\.refresh \{[^}]*height: 44px", r"\.btn \{[^}]*height: 44px", r"\.sel \{[^}]*height: 44px", r"\.q \{[^}]*height: 44px",
                                              r"\.nav \{[^}]*width: 44px; height: 44px", r"\.cd \{[^}]*height: 44px", r"\.more \{[^}]*height: 44px",
                                              r"::after \{[^}]*width: max\(100%, 44px\); height: max\(100%, 44px\)")))
    check("a. text wraps instead of being cut (no ellipsis, no line clamp)", "text-overflow: ellipsis" not in css and "line-clamp" not in css)
    kfx = open(os.path.join(KS, "kfx.js"), encoding="utf-8").read() if os.path.exists(os.path.join(KS, "kfx.js")) else ""
    korb = open(os.path.join(KS, "korb.js"), encoding="utf-8").read() if os.path.exists(os.path.join(KS, "korb.js")) else ""
    check("x. clean modules: kfx.js (the look) before kalshi.js, both versioned (the worker's SHELL is the lead's: bump it with the page version)",
          kfx and html.index('src="kfx.js?v=') < html.index('src="kalshi.js?v='))
    kcode = re.sub(r"//[^\n]*", "", korb)
    check("x. the orb: three.js only from ../jarvis/ (the site's one copy), drawn by the OLYMPUS render core, no other address; paused when hidden or off screen; 30 fps at most; jfx 'off' = no WebGL",
          re.findall(r"import\(['\"]([^'\"]+)", kcode) == ["../jarvis/three.module.min.js", "../olympus/render.js"] and not re.findall(r"https?://", kcode)
          and "document.hidden" in kcode and "IntersectionObserver" in kcode and "now - last < 33" in kcode and "fx() === 'off'" in kcode)
    check("x. themes: one applyTheme(tokens), hex colours only, hooked to Olympus.theme() / onTheme and the 'olympus.theme' key",
          "window.applyTheme = applyTheme" in kfx and "HEX.test" in kfx and "O.onTheme" in kfx and "O.theme()" in kfx and "'olympus.theme'" in kfx)
    check("x. the hierarchy: Today -> Edge -> Performance -> Alerts, and the section bar for them",
          code.index("groupHtml('today'") < code.index("groupHtml('edge'") < code.index("groupHtml('perf'") < code.index("groupHtml('alerts'")
          and 'id="secnav"' in html and all(f'data-go="{g}"' in html for g in ("today", "edge", "perf", "alerts")))
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("a. the site build publishes every file of kalshi/ (index.html, kalshi.js, kalshi.css, sw.js)",
          re.search(r'for app in \(("[a-z]+", )*"kalshi"(, "[a-z]+")*\):', b) is not None and "for name in os.listdir(src_dir):" in b)


# ------------------------------------------------------------------ the browser parts
def run_browser(url, tmp):
    from playwright.sync_api import sync_playwright
    page_url = url + "kalshi/"
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        if "--only=guard" in sys.argv or "--only=whatif" in sys.argv or "--only=scan" in sys.argv or "--only=risk" in sys.argv or "--only=rewards" in sys.argv:   # one card, for a quick run
            (part_guard if "--only=guard" in sys.argv else part_scan if "--only=scan" in sys.argv else part_risk if "--only=risk" in sys.argv
             else part_rewards if "--only=rewards" in sys.argv else part_whatif)(br, url, tmp)
            br.close()
            return
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ctx.route("https://raw.githubusercontent.com/**", feed)
        ctx.route("https://api.github.com/**", feed)
        p = ctx.new_page()
        p.set_default_timeout(120000)                   # a busy box: software GL + many pages
        errs, cons, dialogs, bad, fontres = [], [], [], [], []
        p.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and r.url.startswith(url.split("/nq-dashboard/")[0]) and "/kalshicity/" not in r.url and "/nq-dashboard/kalshi.json" not in r.url and "/kalshi/k8.json" not in r.url else None)
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
              and p.locator("#tape").count() == 0, feats)
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
        check("d. LIVE · real money: a calm badge (OLYMPUS NIGHT lavender / violet / mint / gold, not red)", " ".join(p.locator("#mode").text_content().split()) == "LIVE · real money"
              and p.evaluate("getComputedStyle(document.getElementById('mode')).color") in ("rgb(218, 203, 240)", "rgb(157, 89, 238)", "rgb(119, 219, 137)", "rgb(241, 193, 75)"), (p.inner_text("#mode"), p.evaluate("getComputedStyle(document.getElementById('mode')).color")))
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
        # the newest small, non-zero day of the month on show (polish2 2026-11-19: the check read TODAY's cell, and today's P&L is $0.00 from
        # midnight ET until the first bet settles, so it failed every night; a $0 day has no cents to show and stays a plain "0")
        rdays = [(str(d[0]), d[1]) for d in rb.get("days") or [] if isinstance(d, (list, tuple)) and len(d) > 1 and isinstance(d[1], (int, float))]
        small = [(d, v) for d, v in rdays if d[:7] == today[:7] and 0.005 <= abs(v) < 10]
        cd, cv = small[-1] if small else (today, rb["today_pnl"])
        cell = p.locator(f"#sec-cal .cd[data-v='{cd}'] em").inner_text()
        want = "0" if abs(cv) < 0.005 else re.sub(r"\$", "", usd(cv, True)) if abs(cv) < 10 else cell
        check("d. the calendar shows small days to the cent (a $0 day a plain 0)", cell == want, (cd, cell, cv))
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
        p.evaluate("document.getElementById('chart').scrollIntoView({ block: 'center' })")   # Performance sits below Today and Edge
        p.wait_for_timeout(900)                                                                # the groups' one-time rise-in is over
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

        # ---- the feed's one address (the site's own copy)
        n1 = dict(FEED["n"])
        open_("404", clear=True)
        check("f. a 404 for the site's kalshi.json = not connected yet (waiting); the retired kalshi-feed never asked",
              p.get_attribute("#body", "data-state") == "waiting" and FEED["n"]["site"] > n1["site"] and not FEED["wrong"], (FEED["n"], FEED["wrong"][:2]))
        open_("html", clear=True)
        check("f. the host's own HTML page where kalshi.json would be = not connected yet too (never an error)",
              p.get_attribute("#body", "data-state") == "waiting", p.get_attribute("#body", "data-state"))

        # ---- f. stale, stopped, error, offline copy, loading
        open_("ok", {**sample(time.time()), "t": int(time.time()) - 3600})
        check("f. stale (an hour old): amber pill, the note says the bot stopped sending, numbers still shown",
              "NOT UPDATING" in p.inner_text("#sub").upper() and p.locator("#pill.warn").count() == 1 and "every minute" in p.inner_text(".note.warn")
              and "1 h ago" in p.inner_text(".note.warn") and "$512.34" in text(p) and p.get_attribute("#body", "data-state") == "stale"
              and not re.search(r"\bPC\b", old_bot_text(p)),
              (p.inner_text("#sub"), p.locator("#pill.warn").count(), p.inner_text(".note.warn")[:200] if p.locator(".note.warn").count() else None,
               p.get_attribute("#body", "data-state"), "$512.34" in text(p), re.findall(r".{60}\bPC\b.{20}", old_bot_text(p))[:3]))
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
        bg = lambda: p.evaluate(PAGE_BG_JS)  # noqa: E731
        check("h. the Kalshi theme (OLYMPUS NIGHT violet #9d59ee) on its black background", p.get_attribute("html", "data-theme") == "kalshi"
              and acc() == "#9d59ee" and night_black(bg()), (acc(), bg()))
        for val in ("reactor", '"reactor-ice"', "eclipse"):
            p.evaluate(f"localStorage.setItem('jtheme', {json.dumps(val)})")
            p.reload()
            ready(p)
            check(f"h. Jarvis's jtheme {val} leaves it as it is", p.get_attribute("html", "data-theme") == "kalshi" and acc() == "#9d59ee")
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
        check("v3. no ticker tape (AGORA): the open bets and results live in their cards", p.locator("#tape").count() == 0)
        shot(p, "9_v3")
        # ---- 2026-11-03: the edge map, the Kelly growth curve, the bet journal
        em = p.evaluate("""() => ({ svg: document.querySelectorAll('#sec-emap svg.emap').length, dots: document.querySelectorAll('#sec-emap circle.em-d').length,
            ok: document.querySelectorAll('#sec-emap circle.em-d.ok').length, fair: document.querySelectorAll('#sec-emap .em-fair').length,
            txt: document.getElementById('sec-emap').innerText, title: (document.querySelector('#sec-emap circle title') || {}).textContent || '' })""")
        check("x. Edge map: one bubble per open bet that carries the bot's chance (97% vs 92¢ = +5.0¢, over the min edge = green), the fair diagonal, a caption",
              em["svg"] == 1 and em["dots"] == 1 and em["ok"] == 1 and em["fair"] == 1 and "1 of 1 clear the min edge" in em["txt"] and "edge +5.0¢" in em["title"]
              and "ETH up or down" in em["title"], em)
        p.fill("#kcP", "62")
        p.fill("#kcC", "55")
        kc = p.inner_text("#kcCurve")
        check("x. Kelly growth curve: follows the calculator (62% at 55¢: full Kelly 16%, ¼ / ½ / Full / 2× marks, 2× Kelly past the zero line)",
              p.locator("#kcCurve svg .kc-l").count() == 1 and p.locator("#kcCurve svg .kc-m").count() == 4 and "62% at 55¢" in kc and "Full Kelly is 16%" in kc
              and "2× Kelly" in kc and "your numbers" in kc, kc)
        p.fill("#kcP", "40")
        check("x. Kelly growth curve: no edge = no curve, 'bet nothing'", p.locator("#kcCurve svg").count() == 0 and "Bet nothing" in p.inner_text("#kcCurve"))
        p.fill("#kcP", "")
        p.fill("#kcC", "")
        kc = p.inner_text("#kcCurve")
        check("x. Kelly growth curve: empty calculator = the open bets, averaged (97% at 92¢)", "97% at 92¢" in kc and "the open bets, averaged" in kc, kc)
        day0 = et_day(n3 - 1200)
        jt = [("Journal win with edge", 0.5, 0.6, 5.0, n3 - 1200), ("Journal loss with edge", 0.5, 0.6, -5.0, n3 - 1100),
              ("Journal loss no edge", 0.7, 0.65, -7.0, n3 - 1000), ("Journal win no edge", 0.7, 0.65, 3.0, n3 - 900)]
        raw_j = {**raw3, "trades": [{"t": t, "ticker": f"KXJ{i}", "title": ti, "side": "yes", "action": "settled", "contracts": 10, "price": pr, "prob": pb, "pnl": pn}
                                     for i, (ti, pr, pb, pn, t) in enumerate(jt)]}
        p.evaluate("localStorage.removeItem('kalshi.journal')")
        open_("ok", raw_j)
        jr = p.evaluate("""() => ({ rows: document.querySelectorAll('#sec-journal .jr').length, tags: [...document.querySelectorAll('#sec-journal .jr .kt')].map((e) => e.textContent.trim()),
            txt: document.getElementById('sec-journal').innerText, days: document.querySelectorAll('#sec-journal .jd').length })""")
        check("x. Bet journal: every settled bet by day with its process tag (earned / variance / no edge / luck), the day's W-L and net",
              jr["rows"] == 4 and sorted(jr["tags"]) == ["earned", "luck", "no edge", "variance"] and jr["days"] == 1 and "1W 1L" not in jr["txt"] and "2W 2L" in jr["txt"]
              and "−$4.00" in jr["txt"] and "50%" in jr["txt"] and "good bets when taken" in jr["txt"], jr)
        p.click("#sec-journal [data-act=jf][data-v=win]")
        w = p.locator("#sec-journal .jr").count()
        p.click("#sec-journal [data-act=jf][data-v=loss]")
        l = p.locator("#sec-journal .jr").count()
        p.click("#sec-journal [data-act=jf][data-v=all]")
        check("x. Bet journal: the Wins / Losses filter (2 and 2), All brings everything back", w == 2 and l == 2 and p.locator("#sec-journal .jr").count() == 4
              and p.get_attribute("#sec-journal [data-v=all]", "aria-pressed") == "true")
        p.click("#sec-journal .jn-b")
        fs = p.evaluate("getComputedStyle(document.getElementById('jnote')).fontSize")
        p.fill("#jnote", "Waited for the edge <b>today</b>")
        saved = p.evaluate("JSON.parse(localStorage.getItem('kalshi.journal') || '{}')")
        check("x. Bet journal: a note per day, kept on this phone only (localStorage), the editor is 16 px", fs == "16px" and saved.get(day0) == "Waited for the edge <b>today</b>", (fs, saved))
        p.click("#sec-journal .jn-b")
        shown = p.evaluate("(document.querySelector('#sec-journal .jn-t') || {}).textContent")
        check("x. Bet journal: the note shows as text (escaped), the button reads Note; no page error",
              shown == "Waited for the edge <b>today</b>" and p.locator("#sec-journal .jn-t b").count() == 0 and p.inner_text("#sec-journal .jn-b") == "Note", shown)
        shot(p, "9b_journal")
        p.evaluate("localStorage.removeItem('kalshi.journal')")
        open_("ok", kp.clean(raw3))
        # ---- x. 2026-11-03: the four groups, money (month, ROI), the section bar, the odometer, applyTheme, the orb
        ids = p.evaluate("[...document.querySelectorAll('#body > .grp')].map((g) => g.id)")
        where = p.evaluate("""() => Object.fromEntries(['sec-kpi', 'sec-pos', 'sec-edge', 'sec-kelly', 'sec-eq', 'sec-cal', 'sec-bk', 'sec-cb', 'sec-al', 'sec-tr']
            .map((i) => { const e = document.getElementById(i); return [i, e && e.closest('.grp') ? e.closest('.grp').id : null]; }))""")
        check("x. the hierarchy: Today (balance, open bets) -> Edge (live edge, Kelly) -> Performance (curve, calendar, buckets, calibration) -> Alerts",
              ids == ["g-today", "g-edge", "g-perf", "g-alerts"] and where == {"sec-kpi": "g-today", "sec-pos": "g-today", "sec-edge": "g-edge", "sec-kelly": "g-edge",
              "sec-eq": "g-perf", "sec-cal": "g-perf", "sec-bk": "g-perf", "sec-cb": "g-perf", "sec-al": "g-alerts", "sec-tr": "g-alerts"}, (ids, where))
        tiles = {t.locator(".lab").inner_text().strip().upper(): t.text_content() for t in p.locator("#sec-kpi .kpi").all()}
        mon = sum(x for d, x in raw3["days"] if d[:7] == dt.datetime.now(NY).date().isoformat()[:7])
        check("x. money: balance, today, week, month (the days since the 1st, ET), all time, ROI on the money bet, open bets",
              set(tiles) == {"TODAY", "WEEK", "MONTH", "ALL TIME", "ROI", "OPEN BETS"} and usd(mon, True) in tiles["MONTH"] and "+21%" in tiles["ROI"]
              and "on $542.50 bet" in tiles["ROI"] and "$9.20" in tiles["OPEN BETS"] and "$100.00" in p.locator("#sec-kpi .bal").text_content(), tiles)
        edge = p.inner_text("#sec-edge")
        check("x. the live edge card: EV, the average edge, EV on the money at risk, a bar per bet", "+$0.50 EV" in edge and "+5.0¢" in edge
              and p.locator("#sec-edge .edge-l li").count() == 1 and p.locator("#sec-edge .dv i.pos").count() == 1, edge)
        nav = p.evaluate("""() => { const b = [...document.querySelectorAll('#secnav [data-go]')]; return [document.getElementById('secnav').hidden,
            b.map((x) => Math.round(x.getBoundingClientRect().height)), document.querySelector('#secnav [data-go=alerts] b').textContent,
            document.querySelector('#secnav [data-go=alerts] b').className]; }""")
        check("x. the section bar: shown with data, 44 px taps, the alerts count (red when one needs you)",
              nav[0] is False and all(h >= 44 for h in nav[1]) and nav[2] == "3" and nav[3] == "bad", nav)
        p.click("#secnav [data-go=perf]")
        p.wait_for_function("(() => { const t = document.getElementById('g-perf').getBoundingClientRect().top, b = document.getElementById('secnav').getBoundingClientRect().bottom; return t <= b + 40; })()", timeout=20000)
        p.wait_for_timeout(1200)
        top = p.evaluate("[document.getElementById('g-perf').getBoundingClientRect().top, document.getElementById('secnav').getBoundingClientRect().bottom]")
        check("x. tapping Performance glides there, its heading just under the bar", top[1] - 2 <= top[0] <= top[1] + 40, top)
        p.evaluate("window.scrollTo(0, 0)")
        th = p.evaluate("""() => { const r = getComputedStyle(document.documentElement), o = window.applyTheme({ accent: '#ff00aa', accent2: 'red;}body{x', bg: '#000' });
            const a = [r.getPropertyValue('--c').trim(), r.getPropertyValue('--cr').trim(), r.getPropertyValue('--cy').trim(), JSON.stringify(o)];
            window.applyTheme(null); return a.concat([getComputedStyle(document.documentElement).getPropertyValue('--c').trim()]); }""")
        check("x. applyTheme(tokens): hex colours only (a CSS-looking value is dropped), null = the Kalshi colours again",
              th[0] == "#ff00aa" and th[1] == "255,0,170" and th[2] == "#4b7a99" and "accent2" not in th[3] and th[4] == "#9d59ee", th)
        check("x. the header mark is the plain SVG column: no 3D orb canvas (AGORA)", p.evaluate("!document.querySelector('canvas.orb') && !!document.querySelector('.mark svg')"))
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
        fpad = fr.locator("html").evaluate("""(d) => { const w = d.ownerDocument.defaultView; w.scrollTo(0, 1e6);
            const W = w.innerWidth, H = w.innerHeight, bad = [];
            for (const e of d.querySelectorAll('body *')) { const c = w.getComputedStyle(e); if (c.position !== 'fixed' && c.position !== 'sticky') continue;
              const r = e.getBoundingClientRect(); if (r.width && r.right > W - 80 && r.bottom > H - 160 && r.top < H && c.pointerEvents !== 'none') bad.push(e.id || e.className); }
            const f = d.ownerDocument.getElementById('foot').getBoundingClientRect();
            return [w.getComputedStyle(d.querySelector('main')).paddingBottom, bad, f.bottom <= H - 160]; }""")
        check("x. inside Jarvis's full-screen frame: nothing fixed in the orb's 80 x 160 px corner, the page ends above it (176 px + the home bar)",
              fpad[0] == "210px" and not fpad[1] and fpad[2], fpad)                  # 176 + the emulated 34 px bottom inset
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
                        p.wait_for_function("true", timeout=6000)
                        fin = True
                    except Exception:
                        fin = False
                    if wdt == 375 and name == "wide":
                        check("i. fonts settled (system fonts: SF Rounded for numbers, Iowan serif for headings)", fin)
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
            check("j. any Jarvis font that loads from ../jarvis/ is 200 (AGORA uses system fonts)", all(st_ == 200 for st_, _ in fontres), fontres[:6])
        else:
            print("       (this checkout has no tools/web_public/jarvis/*.woff2: the font requests 404 here; strict once the fonts are in)")
        check("j. kalshi.json only ever asked from this site (never the retired kalshi-feed repo, raw or API)", not FEED["wrong"], FEED["wrong"][:3])
        part_k(br, url, tmp)
        part_kit(br, url, tmp)
        part_v4(br, url, tmp)
        part_guard(br, url, tmp)
        part_risk(br, url, tmp)
        part_whatif(br, url, tmp)
        part_scan(br, url, tmp)
        part_rewards(br, url, tmp)
        br.close()


def part_k(br, url, tmp):
    """The service worker: offline, a 404 site, a slow site, no saved copy, an update, Jarvis's fonts."""
    page_url = url + "kalshi/"
    kdir = os.path.join(tmp, "nq-dashboard", "kalshi")
    ver = re.search(r"kalshi\.js\?v=(\w+)", open(os.path.join(KS, "index.html"), encoding="utf-8").read()).group(1)
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    ctx.route("https://ntfy.invalid/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=""))   # the stub status topic: no posts (never a real host)
    q = ctx.new_page()
    errs, bad = [], []
    q.on("pageerror", lambda e: errs.append(str(e)))
    nofont = lambda u: FONTS or ".woff2" not in u                    # noqa: E731  (a checkout without Jarvis's fonts: their 404s only)
    q.on("console", lambda m: errs.append((m.text, (m.location or {}).get("url", ""))) if m.type == "error" and SITE["mode"] == "ok" and not SITE["slow"]
         and nofont((m.location or {}).get("url", "")) and "kalshi.json" not in (m.location or {}).get("url", "") and "/kalshicity/" not in (m.location or {}).get("url", "") else None)   # the feed's 404 = waiting; Kalshi City's HEAD = 404 until that page exists
    q.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and "127.0.0.1" in r.url and SITE["mode"] == "ok" and nofont(r.url) and "/kalshicity/" not in r.url and "/nq-dashboard/kalshi.json" not in r.url and "/kalshi/k8.json" not in r.url else None)
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
        check("k. fonts settled",
              until("true", 6000))
    # offline: every connection to the site dropped, and the feed too
    SITE["mode"], FEED["mode"] = "down", "abort"
    q.reload()
    ready(q)
    check("k. offline: the page opens from its saved copy, with the numbers saved on this phone",
          pg() and q.get_attribute("#body", "data-state") == "offline" and "$67.98" in text(q) and q.locator("#sec-kpi").count() == 1)
    if FONTS:
        check("k. offline: fonts settled",
              until("true", 6000))
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
    check(f"k. a slow site (6 s): the saved copy is drawn in under 5 s ({took:.1f} s), style and script from their copies", drawn and took < BK.limit(5.0, "slow site saved copy", cap=5.9), took)
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
    bg = q.evaluate(PAGE_BG_JS) if retry else ""
    check("k. offline with no saved copy: a small dark page with Retry, never a browser error or a white screen",
          retry and "can’t reach the internet" in q.inner_text("body") and night_black(bg), (retry, bg))
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
    # the restored worker takes over before the next steps (else its install races the kit.json steps below for the cache)
    q.evaluate("navigator.serviceWorker.getRegistration().then((r) => r.update()).then(() => true)")
    until(f"caches.keys().then((k) => k.indexOf('{cn}') >= 0 && k.indexOf('{cn}u') < 0)", 15000)
    c = q.evaluate(allc)
    check("k. kalshi.json never cached (the feed lives outside the worker's kalshi/ folder and is left alone)", not any("kalshi.json" in u for v in c.values() for u in v), c)
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
    kept = until(f"(document.getElementById('step') || {{}}).textContent.indexOf('{new}') > 0", 8000)
    check("k. offline: the Connect card keeps the last pin (the worker's saved kit.json)", kept,
          "" if kept else (q.evaluate("(document.getElementById('step') || document.body).textContent.slice(-90)"),
                           q.evaluate("caches.match(location.href.split('#')[0].replace(/[^/]*$/, '') + 'kit.json').then((r) => r ? r.text() : 'none')")))
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
    FEED.update(mode="404", site=None)

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


# ------------------------------------------------------------------ v4. "every view looks sick" (2026-11-04)
def paused_bot(now):
    """The owner's bot as it was on 2026-11-04, rebuilt with made-up numbers in the same shape: Paused, 0 open bets, a flat 24 h
    equity, 41 days of P&L, 1,735 wins and 101 losses (94.5%) but a negative total, ten strategies, buckets, calibration, categories."""
    now = int(now)
    rng = random.Random(4)
    today = dt.datetime.now(NY).date()
    days = [[(today - dt.timedelta(days=i)).isoformat(), round(rng.uniform(-14, 18), 2)] for i in range(41, 0, -1)]
    days[3][1], days[22][1], days[30][1] = -101.64, 81.18, -47.11
    days.append([today.isoformat(), 0.0])
    names = [("15-min favourites", "KXDOGE15M", "DOGE"), ("Late favourite (BTC hourly)", "KXBTCD", "BTC"), ("15-min favourites", "KXXRP15M", "XRP"), ("15-min favourites", "KXETH15M", "ETH")]
    trades, t = [], now - 4000
    pn = {0: -5.89, 7: -18.33, 15: -4.4, 22: 0.76, 30: 0.64}
    for i in range(40):
        nm, tk, asset = [names[1], names[0], names[2], names[3]][i % 4]
        c, px = 6 + i % 7, 0.98 if asset == "BTC" else 0.967
        trades.append({"t": t, "ticker": f"{tk}-26NOV02{i:02d}", "title": f"{asset} up or down · {i}" if asset != "BTC" else f"Bitcoin above ${77000 + i * 100:,} at {i % 12 + 1} AM ET Nov 2",
                       "side": "yes" if i % 2 else "no", "action": "buy", "contracts": c, "price": px, "pnl": pn.get(i, round(c * (1 - px) - 0.02, 2)),
                       "asset": asset, "strategy": nm, "category": {"BTC": "Bitcoin", "DOGE": "Dogecoin", "XRP": "XRP", "ETH": "Ethereum"}[asset]})
        t -= 3300 + (i % 5) * 400
    strategies = [
        {"name": "15-min favourites", "mode": "off", "running": False, "today_pnl": 0.0, "total_pnl": -88.77, "trades": 1131, "wins": 1074, "losses": 57},
        {"name": "Late favourite (BTC hourly)", "mode": "live", "running": False, "today_pnl": 0.0, "total_pnl": 16.26, "trades": 182, "wins": 179, "losses": 3},
        {"name": "Gold 5 PM", "mode": "live", "running": False, "today_pnl": 0.0, "total_pnl": 7.13, "trades": 3, "wins": 3, "losses": 0},
        {"name": "Hourly BTC", "mode": "paper", "running": False, "today_pnl": 0.0, "total_pnl": 30.32, "trades": 291, "wins": 277, "losses": 14},
    ]
    buckets = [{"lo": 0.0, "hi": 0.2, "trades": 1, "wins": 0, "losses": 1, "pnl": -0.16, "staked": 0.76}, {"lo": 0.2, "hi": 0.4, "trades": 5, "wins": 0, "losses": 5, "pnl": -2.03, "staked": 6.84},
               {"lo": 0.6, "hi": 0.8, "trades": 35, "wins": 27, "losses": 8, "pnl": -29.44, "staked": 123.89}, {"lo": 0.8, "hi": 0.9, "trades": 135, "wins": 117, "losses": 18, "pnl": 16.18, "staked": 842.96},
               {"lo": 0.9, "hi": 0.95, "trades": 581, "wins": 536, "losses": 45, "pnl": -248.3, "staked": 5343.43}, {"lo": 0.95, "hi": 0.97, "trades": 715, "wins": 699, "losses": 16, "pnl": 136.98, "staked": 9181.72},
               {"lo": 0.97, "hi": 0.99, "trades": 360, "wins": 355, "losses": 5, "pnl": 68.96, "staked": 6093.35}]
    calib = [{"p": 0.19, "n": 1, "hit": 0.0}, {"p": 0.342, "n": 5, "hit": 0.0}, {"p": 0.7349, "n": 35, "hit": 0.7714}, {"p": 0.8617, "n": 135, "hit": 0.8667},
             {"p": 0.9277, "n": 581, "hit": 0.9225}, {"p": 0.961, "n": 715, "hit": 0.9776}, {"p": 0.9771, "n": 360, "hit": 0.9861}]
    cats = [{"name": "Bitcoin", "group": "Crypto", "trades": 623, "wins": 592, "losses": 31, "pnl": 51.82, "staked": 7546.64},
            {"name": "XRP", "group": "Crypto", "trades": 192, "wins": 178, "losses": 14, "pnl": -106.63, "staked": 1739.04},
            {"name": "Dogecoin", "group": "Crypto", "trades": 165, "wins": 158, "losses": 7, "pnl": -0.65, "staked": 2091.94},
            {"name": "NEAR", "group": "Crypto", "trades": 20, "wins": 19, "losses": 1, "pnl": -0.5, "staked": 200.0}]
    raw = {"v": 3, "kind": "kalshi", "name": "Kalshi Edge v2", "mode": "live", "status": "Paused", "running": False, "t": now - 20, "balance": 55.81,
           "today_pnl": 0.0, "week_pnl": -3.3, "total_pnl": -81.77, "note": "Real money · main account", "positions": [], "trades": trades, "days": days,
           "strategies": strategies, "equity": [[now - i * 900, 55.81] for i in range(97, -1, -1)], "categories": cats, "buckets": buckets, "calibration": calib,
           "alerts": [{"t": now - 20, "level": "warn", "text": "Paused"}], "kelly": {"bankroll": 55.81, "min_edge": 0.0},
           "stats": {"trades": 1836, "wins": 1735, "losses": 101, "staked": 21601.62, "pnl": -62.82, "avg_price": 0.9387}, "calib_basis": "price", "pub_t": now - 18}
    return raw


def part_v4(br, url, tmp):
    """The Kalshi page's 2026-11-04 upgrade: verdict, hero, heat map, race, battle, ruin, timeline, badges, rings, 3D links, skeleton."""
    page_url = url + "kalshi/"
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    p = ctx.new_page()
    p.set_default_timeout(120000)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"Failed to load resource|net::ERR", m.text) else None)

    def open_(j, clear=True):
        FEED["mode"], FEED["j"] = "ok", j
        if clear:
            p.goto(page_url)
            p.evaluate("localStorage.clear()")
        p.goto(page_url)
        ready(p, 20000)
        p.wait_for_selector("#sec-kpi")

    # ---------------------------------------------------------------- the paused bot, as the owner sees it today
    now = time.time()
    open_(paused_bot(now))
    check("v4. paused bot: amber Paused pill (not the red Stopped), LIVE · real money kept",
          p.locator("#pill.warn").inner_text().upper() == "PAUSED" and "LIVE" in p.inner_text("#mode").upper())
    vd = p.inner_text("#sec-verdict")
    check("v4. verdict banner first in Today, plain words: wins 94% but loses money, here is why",
          p.evaluate("[...document.querySelectorAll('#g-today > .card')].slice(0, 3).map((c) => c.id)") == ["sec-why", "sec-guard", "sec-verdict"] and "You win 94% of bets but lose money: here is why" in vd
          and "−$81.77" in vd and "1,735W 101L" in vd and "paused: nothing is at risk right now." in vd.lower(), vd[:300])
    check("v4. verdict reasons from the numbers: one loss wipes out ~15 wins (6¢ on 94¢), break-even 93.9% vs 94.5%, fee drag, the 90–95¢ leak −$248.30, strategy vs strategy",
          "One loss wipes out about 15 wins" in vd and "6¢" in vd and "93.9%" in vd and "94.5%" in vd and "0.6 points above" in vd and "Fees and slips cost about" in vd
          and "90–95¢" in vd and "−$248.30" in vd and "Hourly BTC" in vd and "(paper)" in vd and p.locator("#sec-verdict .vd-i").count() == 4, vd)
    tg = p.evaluate("[...document.querySelectorAll('#sec-verdict .vd-i')].map((b) => [b.getAttribute('data-v'), !!document.getElementById(b.getAttribute('data-v'))])")
    check("v4. every verdict line links to the card with its numbers (they all exist)", tg and all(ok for _, ok in tg) and [t[0] for t in tg] == ["sec-bk", "sec-cb", "sec-bk", "sec-battle"], tg)
    p.evaluate("window.scrollTo(0, 0)")
    p.click("#sec-verdict .vd-i >> nth=1")
    flashed = p.evaluate("document.getElementById('sec-cb').classList.contains('flash')")
    try:
        p.wait_for_function("window.scrollY > 300", timeout=30000)
    except Exception:
        pass
    check("v4. tapping a verdict line glides to its card and flashes it", p.evaluate("window.scrollY") > 300 and flashed, (flashed, p.evaluate("window.scrollY")))
    p.evaluate("window.scrollTo(0, 0)")
    check("v4. verdict ring shows the win rate", p.locator("#sec-verdict .vd-ring .vr-w").count() == 1 and "94" in p.locator("#sec-verdict .vd-ring").text_content())
    # hero
    check("v4. hero: the balance sparkline is alive (travelling light + ring on the last point), over the daily curve of a paused bot",
          p.locator("#sec-kpi .bal-sp svg .sp-g").count() == 1 and p.locator("#sec-kpi .bal-sp svg .sp-r").count() == 1 and p.locator("#sec-kpi .bal-sp .spark").count() == 1)
    ch = p.locator("#sec-kpi .chips").text_content()
    check("v4. streak chips: loss/win streak now, best run of the list, green days of the 41, days running", p.locator("#sec-kpi .chip").count() >= 3
          and "streak" in ch and "best run of 40" in ch and re.search(r"\d+/42green days", ch) is not None, ch)
    cv = p.locator("#sec-eq").text_content()
    check("v4. a paused bot's flat 24 h curve shows the days instead (Cumulative P&L), with a Live / Daily switch",
          "Cumulative P&L" in cv and p.locator("#sec-eq [data-act=eqv]").count() == 2 and p.get_attribute("#sec-eq [data-v=days]", "aria-pressed") == "true", cv[:200])
    check("v4. equity chart: drawdown shaded under the previous high, with its deepest dip", p.locator("#sec-eq .chart svg .dd").count() == 1 and p.locator("#sec-eq .chart svg .pk").count() == 1
          and "Deepest dip −$" in cv, cv[-160:])
    p.click("#sec-eq [data-v=eq]")
    check("v4. Live shows the flat 24 h equity ($55.81, no shading); Daily brings the curve back",
          p.get_attribute("#sec-eq [data-v=eq]", "aria-pressed") == "true" and "$55.81" in p.inner_text("#eqRead") and p.locator("#sec-eq .chart .dd").count() == 0)
    p.click("#sec-eq [data-v=days]")
    # rest state
    rs = p.locator("#sec-rest").text_content()
    check("v4. no open bets: never blank, 'what happens when it resumes' with 4 steps and the history intact",
          "Paused · what happens when it resumes" in rs and p.locator("#sec-rest .steps li").count() == 4 and "A bet opens" in rs and "stays exactly as it was" in rs
          and "No open bets right now." in p.inner_text("#sec-pos") and p.locator("#sec-ew").count() == 1, rs[:200])
    # heat map
    check("v4. heat map: one cell per day (42), green / red by size, month labels, a reading panel",
          p.locator("#heat .hc:not(.e)").count() == 42 and p.locator("#heat .hc.p4").count() >= 1 and p.locator("#heat .hc.n4").count() >= 1 and "All 42 days" in p.locator("#heatRead").text_content())
    day = paused_bot(now)["days"][22][0]
    p.locator(f"#heat .hc[data-d='{day}']").scroll_into_view_if_needed()
    p.locator(f"#heat .hc[data-d='{day}']").click()
    hr = p.inner_text("#heatRead")
    check("v4. tap a day: its P&L, its rank, the running total; the cell is outlined; the month calendar jumps to the same day",
          "+$81.18" in hr and "the best day" in hr and "running total" in hr
          and p.locator(f"#heat .hc.sel[data-d='{day}']").count() == 1 and p.get_attribute(f"#sec-cal .cd[data-v='{day}']", "aria-pressed") == "true", hr)
    p.locator(f"#heat .hc[data-d='{day}']").click()
    check("v4. tap it again: back to the overview", "All 42 days" in p.locator("#heatRead").text_content() and p.locator("#heat .hc.sel").count() == 0)
    p.focus("#heat")
    p.keyboard.press("ArrowUp")
    check("v4. heat map by keyboard: the arrow keys walk the days", p.locator("#heat .hc.sel").count() == 1 and "running total" in p.inner_text("#heatRead"))
    # calibration
    cb = p.inner_text("#sec-cb")
    check("v4. calibration: the diagonal, a curve, the 95% band and a range bar per group; thin groups only get a faint bar",
          p.locator("#sec-cb .cb-d").count() == 1 and p.locator("#sec-cb .cb-curve").count() == 1 and p.locator("#sec-cb .cb-band").count() == 1
          and p.locator("#sec-cb .cb-eb").count() == 7 and p.locator("#sec-cb .cb-eb.thin").count() == 2 and p.locator("#sec-cb circle").count() == 7 and "95% range" in cb, cb[-300:])
    # race
    rc = p.inner_text("#sec-race")
    check("v4. strategy race: a running-P&L line per strategy from the recent bets, tap-to-hide chips, and the finish line from the totals",
          p.locator("#sec-race .rc-l").count() == 2 and p.locator("#sec-race .rchip").count() == 2 and p.locator("#sec-race .brk li").count() == 4
          and "1st" in rc and "Hourly BTC" in rc and "+$30.32" in rc and "−$88.77" in rc, rc[:300])
    p.click("#sec-race .rchip >> nth=0")
    check("v4. race: a chip hides its line (and says so), tap again to bring it back",
          p.locator("#sec-race .rc-l").count() == 1 and p.get_attribute("#sec-race .rchip >> nth=0", "aria-pressed") == "false")
    p.click("#sec-race .rchip >> nth=0")
    check("v4. race: back to two lines", p.locator("#sec-race .rc-l").count() == 2)
    # battle
    check("v4. strategy battle: 5 measures, win rate first with a bar per strategy",
          p.locator("#sec-battle [data-act=bm]").count() == 5 and p.locator("#sec-battle .brk li").count() == 4 and "95%" in p.inner_text("#sec-battle"))
    p.click("#sec-battle [data-v=aw]")
    aw = p.inner_text("#sec-battle")
    check("v4. battle · win / loss: all bets first (a win about $0.65, a loss $11.77), then the strategies from the list, two bars each",
          "All bets · all time" in aw and "$0.65" in aw and "$11.77" in aw and p.locator("#sec-battle .b1").count() >= 4 and p.get_attribute("#sec-battle [data-v=aw]", "aria-pressed") == "true", aw[:300])
    p.click("#sec-battle [data-v=ev]")
    ev = p.inner_text("#sec-battle")
    check("v4. battle · EV per $: all bets −0.3% ($62.82 lost on $21,601.62 bet)", "−0.3%" in ev and "All bets · all time" in ev, ev[:200])
    p.click("#sec-battle [data-v=fee]")
    fee = p.inner_text("#sec-battle")
    check("v4. battle · fee drag: all bets 0.96% of what was bet, $207.55 in fees and slips", "0.96%" in fee and "$207.5" in fee, fee[:240])
    p.click("#sec-battle [data-v=pb]")
    check("v4. battle · per bet: total P&L over bets (15-min favourites −$0.08 a bet)", "−$0.08" in p.inner_text("#sec-battle"), p.inner_text("#sec-battle")[:200])
    # ruin
    ru = p.inner_text("#sec-ruin")
    m1 = re.search(r"(\d+) in 100", ru)
    r1 = int(m1.group(1)) if m1 else -1
    check("v4. risk of ruin: a gauge, N in 100 runs, the Monte Carlo fan (light 80% + dark middle half + median), chips for ½ / same / 2×",
          0 <= r1 <= 100 and p.locator("#sec-ruin svg.gauge .g-v").count() == 1 and p.locator("#sec-ruin svg.fan .fn-o").count() == 1 and p.locator("#sec-ruin svg.fan .fn-i").count() == 1
          and p.locator("#sec-ruin svg.fan .fn-m").count() == 1 and "ruin at ½" in ru and "ruin at 2×" in ru and "1,836 settled bets" in ru and "400 runs" in ru, ru[:300])
    p.reload()
    ready(p, 20000)
    p.wait_for_selector("#sec-ruin")
    check("v4. the fan is seeded: the same numbers, the same fan after a reload", re.search(r"(\d+) in 100", p.inner_text("#sec-ruin")).group(1) == str(r1))
    p.click("#sec-ruin [data-act=bs][data-v='0.5']")
    r_half = int(re.search(r"(\d+) in 100", p.inner_text("#sec-ruin")).group(1))
    p.click("#sec-ruin [data-act=bs][data-v='2']")
    r_dbl = int(re.search(r"(\d+) in 100", p.inner_text("#sec-ruin")).group(1))
    check("v4. ruin: smaller bets = less ruin, bigger = more (½ <= same <= 2×)", r_half <= r1 <= r_dbl and r_dbl > r_half, (r_half, r1, r_dbl))
    p.click("#sec-ruin [data-act=bs][data-v='1']")
    # timeline
    tl = p.inner_text("#sec-tl")
    check("v4. alerts timeline: Paused (the bot's own alert), every loss, the biggest wins, grouped by day, newest first",
          p.locator("#sec-tl .tl-e").count() >= 6 and p.locator("#sec-tl .tl-e.bad").count() == 3 and p.locator("#sec-tl .tl-e.warn").count() == 1 and p.locator("#sec-tl .tl-d").count() >= 1
          and "Lost $18.33" in tl and "Lost $5.89" in tl and "Won +$0.76" in tl and tl.index("Paused") < tl.index("Lost"), tl[:300])
    # badges
    ai = p.evaluate("[...document.querySelectorAll('#sec-tr .asset')].map((a) => [a.textContent.trim(), a.querySelectorAll('svg.ai path, svg.ai text, svg.ai circle').length])")
    check("v4. asset badges: BTC, DOGE, XRP and ETH each drawn as their own SVG (no image files), name kept as text",
          {a for a, _ in ai} >= {"BTC", "DOGE", "XRP", "ETH"} and all(n >= 3 for _, n in ai) and p.locator("#sec-tr img").count() == 0 and p.locator("#sec-cat .ai").count() >= 3, ai[:6])
    # kelly presets
    p.evaluate("document.getElementById('sec-kelly').scrollIntoView()")
    p.click("#sec-kelly [data-f=p][data-v='94']")
    p.click("#sec-kelly [data-f=c][data-v='94']")
    k94 = p.inner_text("#kcOut")
    check("v4. Kelly calculator presets: 94% at 94¢ = no bet; the boxes follow the chips",
          "No bet" in k94 and p.input_value("#kcP") == "94" and p.input_value("#kcC") == "94" and p.get_attribute("#sec-kelly [data-f=p][data-v='94']", "aria-pressed") == "true", k94)
    p.click("#sec-kelly [data-f=c][data-v='90']")
    check("v4. Kelly presets: 94% at 90¢ = a bet, edge +4.0¢", "of the bankroll" in p.inner_text("#kcOut") and "+4.0¢" in p.inner_text("#kcOut"), p.inner_text("#kcOut"))
    # 3D links
    check("v4. 3D links: Tyche always, Kalshi City only when ../kalshicity/ exists on the site (not here)",
          p.locator("#sec-kpi .lnk3d").count() == 1 and p.get_attribute("#sec-kpi .lnk3d", "href") == "../tyche/#wheel")
    os.makedirs(os.path.join(tmp, "nq-dashboard", "kalshicity"), exist_ok=True)
    with open(os.path.join(tmp, "nq-dashboard", "kalshicity", "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><title>Kalshi City</title>")
    p.reload()
    ready(p, 20000)
    p.wait_for_selector("#sec-kpi .lnk3d.city", timeout=10000)
    check("v4. Kalshi City exists (a HEAD check answers 200 html): its 'See it in 3D' link appears next to Tyche",
          p.get_attribute("#sec-kpi .lnk3d.city", "href") == "../kalshicity/" and p.locator("#sec-kpi .lnk3d").count() == 2 and "Kalshi City" in p.locator("#sec-kpi .l3d").text_content())
    shutil.rmtree(os.path.join(tmp, "nq-dashboard", "kalshicity"), ignore_errors=True)
    shot(p, "10_v4_paused")
    # phone widths: the new views never overflow or clip, every control 44 px
    for wdt, hgt in ((390, 844), (375, 667), (430, 932)):
        p.set_viewport_size({"width": wdt, "height": hgt})
        open_(paused_bot(time.time()), clear=False)
        m = p.evaluate("""() => {
            const W = window.innerWidth, de = document.documentElement;
            const els = [...document.querySelectorAll('#sec-verdict, #sec-verdict *, #sec-heat, #sec-heat > *, #sec-race, #sec-race > *, #sec-battle, #sec-battle > *, #sec-ruin, #sec-ruin > *, #sec-tl, #sec-rest, #sec-rest > *, #sec-cb, #sec-kelly .pres, .chips, .rleg')];
            const out = els.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > W - 15.5 || r.left < 15.5); }).map((e) => (e.id || e.className.baseVal || e.className || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().left) + '-' + Math.round(e.getBoundingClientRect().right));
            const cut = [...document.querySelectorAll('#sec-verdict *, #sec-race *, #sec-battle *, #sec-ruin *, #sec-tl *, #sec-rest *, #sec-heat *, .chip, .rchip')].filter((e) => { const c = getComputedStyle(e);
              return e.getClientRects().length && !(e instanceof SVGElement) && (c.overflowX === 'hidden' || c.textOverflow === 'ellipsis') && e.scrollWidth > e.clientWidth + 1; }).map((e) => e.className + ':' + e.textContent.slice(0, 30));
            return [de.scrollWidth, de.clientWidth, out, cut];
        }""")
        check(f"v4. {wdt}x{hgt}: no sideways scroll, every new card inside the 16 px gutters, no text cut off", m[0] <= m[1] and not m[2] and not m[3], m)
        small = p.evaluate(TARGETS)
        check(f"v4. {wdt}x{hgt}: every control (verdict lines, race chips, measures, bet sizes, presets) at least 44 x 44", not small, small[:6])
        shot(p, f"10_v4_{wdt}")
    # open bets as cards: asset badge, settle ring
    p.set_viewport_size({"width": 390, "height": 844})
    open_(wide(time.time()))
    check("v4. open bets as cards: a settle ring on every bet (6), the asset badge SVG for BTC / ETH / GOLD, the live countdown text kept",
          p.locator("#posList .ring").count() == 6 and p.locator("#posList .asset .ai").count() >= 3 and p.locator("#posList .cdn").count() >= 5
          and p.locator("#posList .ring.soon").count() >= 1, p.locator("#posList .ring").count())
    r0 = p.evaluate("[...document.querySelectorAll('#posList svg.ring')].map((s) => [s.getAttribute('data-c'), s.querySelector('.rg-v').getAttribute('stroke-dasharray')])")
    check("v4. the ring fills with the time left in its window (45 min of an hour = 75%; settled = empty)",
          any(abs(float(d.split()[0]) - 75) < 8 for _, d in r0) and any(d.startswith("0.0") for _, d in r0), r0)
    c0 = p.inner_text("#posList .cdn.soon >> nth=0")
    try:
        p.wait_for_function("(c0) => document.querySelector('#posList .cdn.soon').textContent !== c0", arg=c0, timeout=10000)
    except Exception:
        pass
    c1 = p.inner_text("#posList .cdn.soon >> nth=0")
    check("v4. live countdown: under an hour it counts the seconds (closes in 44m 12s) and moves every second",
          re.fullmatch(r"closes in (4[0-5]|3\d)m \d\ds", c0) and c0 != c1 and re.fullmatch(r"closes in \d+m \d\ds", c1), (c0, c1))
    # skeleton (loading) and reduced motion
    FEED["mode"] = "hold"
    p.evaluate("localStorage.clear()")
    p.goto(page_url)
    p.wait_for_selector("#body .sk")
    sk = p.evaluate("[...document.querySelectorAll('#body .sk')].map((e) => [getComputedStyle(e).backgroundImage.split('linear-gradient').length - 1, getComputedStyle(e, '::after').content, e.getBoundingClientRect().height])")
    check("v4. skeleton while loading: three cards drawn like the page (hero tiles, chart, rows), with a sweep, never blank", len(sk) == 3 and sk[0][0] >= 6 and all(c == '""' for _, c, _ in sk) and sk[0][2] > 250, sk)
    release()
    ready(p, 20000)
    FEED["mode"] = "ok"
    p.emulate_media(reduced_motion="reduce")
    open_(paused_bot(time.time()), clear=False)
    an = p.evaluate("[...document.querySelectorAll('.sp-g, .sp-r, .vr-w, .gauge .g-v')].map((e) => getComputedStyle(e).animationName)")
    check("v4. reduced motion: the sparkline light, ring and gauge do not animate", len(an) >= 3 and all(a_ == "none" for a_ in an), an)
    p.emulate_media(reduced_motion="no-preference")
    # the preview sample also shows the new views
    FEED["mode"] = "404"
    p.goto(page_url)
    p.evaluate("localStorage.clear()")
    p.goto(page_url)
    ready(p, 20000)
    p.click("[data-act=preview]")
    ids = {s_: p.locator(s_).count() for s_ in ("#sec-verdict", "#sec-heat", "#sec-race", "#sec-battle", "#sec-tl", "#sec-ruin")}
    check("v4. the sample preview carries the new views too (verdict, heat map, race, battle, timeline)", all(ids[k_] == 1 for k_ in ("#sec-verdict", "#sec-heat", "#sec-battle", "#sec-tl")), ids)
    check("v4. no page errors in any of it", not errs, errs[:3])
    ctx.close()


def guard_bot(now):
    """The paused bot's feed (buckets, categories, strategies from the research) with four open bets: an XRP 15-minute bet at 93c (the 90-95c leak,
    a losing coin, 28% of the balance), a Late favourite at 96c (clean), a DOGE bet at 96c (14% of the balance) settling with the XRP bet."""
    raw = paused_bot(now)
    t1, t2 = int(now) + 600, int(now) + 4000
    raw["running"], raw["status"] = True, "Trading · 3 live strategies · 3 open bets"
    raw["positions"] = [
        {"ticker": "KXXRP15M-26NOV021000-00", "title": "XRP up or down · 15 min", "side": "no", "contracts": 17, "avg_price": 0.93, "asset": "XRP", "strategy": "15-min favourites",
         "category": "XRP", "closes": iso(t1)},
        {"ticker": "KXBTCD-26NOV0211-T77399.99", "title": "Bitcoin above $77,400 at 11 AM ET", "side": "yes", "contracts": 5, "avg_price": 0.96, "asset": "BTC",
         "strategy": "Late favourite (BTC hourly)", "category": "Bitcoin", "closes": iso(t2)},
        {"ticker": "KXDOGE15M-26NOV021000-00", "title": "DOGE up or down · 15 min", "side": "no", "contracts": 8, "avg_price": 0.96, "asset": "DOGE", "strategy": "15-min favourites",
         "category": "Dogecoin", "closes": iso(t1 + 20)},
    ]
    return raw


def part_guard(br, url, tmp):
    """The guard (2026-11-04): the top card of Today, "Do not take this bet", green / amber / red with the dollar reason, never blank,
    suggestions only (no order is ever placed from it), every tap >= 44 px."""
    page_url = url + "kalshi/"
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    p = ctx.new_page()
    p.set_default_timeout(120000)
    errs, posts = [], []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"Failed to load resource|net::ERR", m.text) else None)
    p.on("request", lambda r: posts.append(r.method + " " + r.url) if r.method not in ("GET", "HEAD") else None)

    def open_(j):
        FEED["mode"], FEED["j"] = "ok", j
        p.goto(page_url)
        p.evaluate("localStorage.clear()")
        p.goto(page_url)
        ready(p, 20000)
        p.wait_for_selector("#sec-guard")

    now = time.time()
    # ---- with open bets
    open_(guard_bot(now))
    g = p.inner_text("#sec-guard")
    rows = p.eval_on_selector_all("#sec-guard > .gd-b", "els => els.map(e => [e.className, e.querySelector('.gd-v').textContent, e.innerText])")
    first = p.evaluate("[...document.querySelectorAll('#g-today > .card')].slice(0, 3).map((c) => c.id)")
    check("g1. the guard follows the 'why am I losing' line at the top of Today (the verdict follows it)", first == ["sec-why", "sec-guard", "sec-verdict"], first)
    check("g1. red headline in plain words with the dollars at risk: 'Do not take 1 of these 3 bets' and the $ in the red one, suggestions only",
          p.get_attribute("#sec-guard", "class").split()[-1] == "red" and "Do not take 1 of these 3 bets" in g and "$15.81 is at risk" in g and "never places, changes or cancels a bet" in g, g[:300])
    check("g1. the XRP bet is red (sorted first) with the three dollar reasons: the 90–95¢ band −$248.30 on 581 bets, needs 93.3% wins vs the band's 92.2%, and 28% of the balance",
          rows[0][1] == "DO NOT TAKE" and "90–95¢" in rows[0][2] and "−$248.30" in rows[0][2] and "581 bets" in rows[0][2] and "Needs 93.5% wins" in rows[0][2] and "92.3%" in rows[0][2]
          and "$15.81" in rows[0][2] and "28%" in rows[0][2] and "XRP" in rows[0][2] and "−$106.63" in rows[0][2], rows[0])
    check("g1. the DOGE bet at 96¢ is amber (13.8% of the balance, settles with the XRP bet), the Late favourite at 96¢ is OK; amber / green lines carry their own reasons",
          rows[1][1] == "CAREFUL" and "DOGE" in rows[1][2] and "settle together" in rows[1][2] and "14%" in rows[1][2]
          and rows[2][1] == "OK" and "Bitcoin above" in rows[2][2] and "+$136.98" in rows[2][2], [r[1] for r in rows])
    check("g1. nothing on the card places an order: no form, no POST, no link to Kalshi's trading", p.locator("#sec-guard form").count() == 0 and not posts
          and p.locator("#sec-guard a").count() == 0, posts[:3])
    # ---- the check-a-bet chips work with bets open, tap size, keyboard
    box = p.evaluate("[...document.querySelectorAll('#sec-guard [data-act=gpx]')].map((b) => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })")
    check("g2. four price chips (91 / 94 / 96 / 98¢), each at least 44 x 44 px", len(box) == 4 and all(w >= 44 and h >= 44 for w, h in box), box)
    p.click("#sec-guard [data-act=gpx][data-v='0.94']")
    r94 = p.inner_text("#sec-guard .gd-chk")
    check("g2. 94¢ is red: the band that lost $248.30, the fee needs 94.4% wins against the band's 92.3%", "DO NOT TAKE" in r94 and "−$248.30" in r94 and "94.4%" in r94 and p.get_attribute("#sec-guard [data-v='0.94']", "aria-pressed") == "true", r94)
    p.click("#sec-guard [data-act=gpx][data-v='0.96']")
    r96 = p.inner_text("#sec-guard .gd-chk")
    check("g2. 96¢ at the bot's usual 9 contracts is CAREFUL only for its size (15% of the balance), the band and the fee pass", "CAREFUL" in r96 and "15%" in r96 and "keep it under 10%" in r96 and "DO NOT TAKE" not in r96, r96)
    p.click("#sec-guard [data-act=gpx][data-v='0.98']")
    r98 = p.inner_text("#sec-guard .gd-chk")
    check("g2. 98¢ is CAREFUL, not OK: the fee line needs 98.1% wins and the band wins 98.6%, 0.5 points of room", "CAREFUL" in r98 and "98.1%" in r98 and "DO NOT TAKE" not in r98, r98)
    p.click("#sec-guard [data-act=gpx][data-v='0.98']")
    check("g2. tapping the chip again clears it", "Tap a price" in p.inner_text("#sec-guard .gd-chk"))
    # ---- paused bot, nothing open: never blank
    open_(paused_bot(now))
    g0 = p.inner_text("#sec-guard")
    check("g3. nothing open (the paused bot): the guard still shows, says nothing is at risk, and offers the check", "No open bets: nothing to stop right now" in g0
          and "Nothing is at risk while it is paused" in g0 and p.locator("#sec-guard [data-act=gpx]").count() == 4 and p.get_attribute("#sec-guard", "class").split()[-1] == "idle", g0[:200])
    p.click("#sec-guard [data-act=gpx][data-v='0.91']")
    check("g3. with nothing open, a 91¢ check is red and names the dollars", "DO NOT TAKE" in p.inner_text("#sec-guard .gd-chk") and "−$248.30" in p.inner_text("#sec-guard .gd-chk"))
    # ---- a feed with no buckets or categories: the research's own leak is used, nothing crashes
    j = paused_bot(now)
    for k_ in ("buckets", "categories", "calibration", "stats"):
        j.pop(k_, None)
    j["positions"] = guard_bot(now)["positions"]
    open_(j)
    rows2 = p.eval_on_selector_all("#sec-guard > .gd-b .gd-v", "els => els.map(e => e.textContent)")
    check("g4. no buckets in the feed: the research's 90–95¢ leak still flags the 93¢ bet (red), the Late favourite is not red (the 15-min bets can be: their own win rate is under the line)", rows2[0] == "DO NOT TAKE" and rows2.count("DO NOT TAKE") >= 1 and rows2[-1] != "DO NOT TAKE"
          and "−$248.30" in p.inner_text("#sec-guard"), rows2)
    # ---- the sample preview and escaping
    FEED["mode"], FEED["j"] = "404", None
    p.goto(page_url)
    p.evaluate("localStorage.clear()")
    p.goto(page_url)
    p.wait_for_selector("[data-act=preview]")
    p.click("[data-act=preview]")
    p.wait_for_selector("#sec-guard")
    check("g5. the sample preview carries the guard too (never blank)", p.locator("#sec-guard .gd-top").count() == 1 and p.locator("#sec-guard .gd-v, #sec-guard [data-act=gpx]").count() >= 1)
    evil = guard_bot(now)
    evil["positions"][0]["title"] = "<img src=x onerror=window.__pwned=1>"
    open_(evil)
    check("g5. a hostile title is text, never markup", p.evaluate("!window.__pwned") and p.locator("#sec-guard img").count() == 0)
    # ---- small phone: no sideways scroll, nothing cut
    ctx2 = br.new_context(viewport={"width": 375, "height": 667}, device_scale_factor=1)
    ctx2.route("https://raw.githubusercontent.com/**", feed)
    ctx2.route("https://api.github.com/**", feed)
    q = ctx2.new_page()
    q.set_default_timeout(120000)
    FEED["mode"], FEED["j"] = "ok", guard_bot(now)
    q.goto(page_url)
    q.evaluate("localStorage.clear()")
    q.goto(page_url)
    ready(q, 20000)
    q.wait_for_selector("#sec-guard")
    sw = q.evaluate("[document.documentElement.scrollWidth, innerWidth, Math.max(...[...document.querySelectorAll('#sec-guard *')].map((e) => e.getBoundingClientRect().right))]")
    check("g6. 375 x 667: the guard fits (no sideways scroll, nothing past the right edge)", sw[0] <= sw[1] and sw[2] <= sw[1] + 0.5, sw)
    ctx2.close()
    check("g7. no page errors and no failed section on the guard", not errs and "could not be shown" not in p.inner_text("#body"), errs[:3])
    ctx.close()


def risk_bot(now, **risk):
    """The guard bot's feed plus the VM risk guard's block (kalshi_guard.py, 2026-11-13)."""
    raw = guard_bot(now)
    r = {"v": 1, "mode": "paper", "why": "not armed (paper is the default)", "kill": False, "connected": True, "stopped": False,
         "unguarded": 0, "limits": {"max_order_usd": 5, "max_market_usd": 10, "max_day_usd": 25, "daily_stop_usd": 10, "max_open_usd": 25,
                                     "no_trade_last_s": 60, "min_edge_cents": 1, "fee_rate": 0.07},
         "today": {"day": "2026-11-14", "spend": 4.2, "pnl": -1.5, "orders": 3, "sent": 2, "blocked": 1}, "open": 4.2,
         "room": {"day": 20.8, "stop": 8.5, "open": 20.8}, "last_block": {"t": int(now) - 120, "text": "price above fair value (41 c > fair 39.0 c + 0)"},
         "intended": [{"t": int(now) - 60, "ticker": "KXBTCD-26NOV1417-T99500", "side": "yes", "action": "buy", "contracts": 5, "price": 0.4,
                       "cost": 2.1, "send": False}],
         "go_live": "GO LIVE 2026-11-14 STOP 10"}
    r.update(risk)
    raw["risk"] = r
    return raw


def part_risk(br, url, tmp):
    """The risk guard card (2026-11-13): shown only when kalshi.json has `risk`, first in Today; the mode, the room, the kill switch,
    orders around the guard; read-only (no form, no POST)."""
    page_url = url + "kalshi/"
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    p = ctx.new_page()
    p.set_default_timeout(120000)
    errs, posts = [], []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("request", lambda r: posts.append(r.method + " " + r.url) if r.method not in ("GET", "HEAD") else None)

    def open_(j, sel="#sec-guard"):
        FEED["mode"], FEED["j"] = "ok", j
        p.goto(page_url)
        p.evaluate("localStorage.clear()")
        p.goto(page_url)
        ready(p, 20000)
        p.wait_for_selector(sel)

    now = time.time()
    open_(guard_bot(now))
    check("r1. no risk block in the feed: no risk card (the page as before)", p.locator("#sec-risk").count() == 0)
    open_(risk_bot(now), "#sec-risk")
    t = p.inner_text("#sec-risk")
    first = p.evaluate("[...document.querySelectorAll('#g-today > .card')].slice(0, 2).map((c) => c.id)")
    check("r1. the risk card is first in Today, then the 'why' line", first == ["sec-risk", "sec-why"], first)
    check("r1. paper: 'Paper: no real orders', the room ($8.50 of $10.00), spend, open, orders, the limits, the last block, the order asked about",
          "Paper: no real orders" in t and "$8.50" in t and "$10.00" in t and "$4.20" in t and "2 let through" in t and "1 blocked" in t
          and "$5.00 per order" in t and "price above fair" in t and "BUY 5 YES @ 40¢" in t and "not sent (paper)" in t, t[:600])
    check("r1. paper shows the phrase the owner types on the server, and says the page is read-only", "GO LIVE 2026-11-14 STOP 10" in t
          and "never arms, changes or places anything" in t)
    check("r1. the mode pill: amber in paper", "warn" in p.get_attribute("#sec-risk .pill", "class"))
    open_(risk_bot(now, mode="live", why="armed by you", go_live=None, intended=[{**risk_bot(now)["risk"]["intended"][0], "send": True}]), "#sec-risk")
    t = p.inner_text("#sec-risk")
    check("r2. live: 'Live: real orders, inside your limits', green pill, the order 'sent', no phrase line", "Live: real orders" in t
          and "ok" in p.get_attribute("#sec-risk .pill", "class") and "sent" in t and "GO LIVE" not in t, t[:400])
    open_(risk_bot(now, mode="paper", kill=True), "#sec-risk")
    t = p.inner_text("#sec-risk")
    check("r3. kill switch: red card, 'Kill switch on: no orders'", "Kill switch on" in t and "bad" in p.get_attribute("#sec-risk", "class"), t[:200])
    open_(risk_bot(now, mode="live", unguarded=2), "#sec-risk")
    check("r3. orders around the guard: red, '2 real orders went around the guard'", "2 real orders went around the guard" in p.inner_text("#sec-risk"))
    open_(risk_bot(now, mode="live", stopped=True, room={"stop": 0, "day": 10, "open": 10}), "#sec-risk")
    check("r3. daily stop: 'Daily stop hit'", "Daily stop hit" in p.inner_text("#sec-risk"))
    open_(risk_bot(now, connected=False), "#sec-risk")
    check("r4. installed but not connected: says so", "has not asked it about an order yet" in p.inner_text("#sec-risk"))
    open_(risk_bot(now, mode="weird", limits="junk", today=[1], room=None, intended="x", last_block=5, go_live="<b>x</b>"), "#sec-risk")
    check("r4. a junk block still renders (paper, dashes), no script error, a junk phrase is not shown", "Paper" in p.inner_text("#sec-risk") and "<b>x</b>" not in p.inner_html("#sec-risk") and "GO LIVE" not in p.inner_text("#sec-risk")
          and not errs, errs[:3])
    wide = p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    check("r4. phone width: no sideways scroll, and nothing was posted", wide and not posts, posts[:3])
    ctx.close()


def part_whatif_py():
    """tools/kalshi_whatif.py (the city feed's copy of the maths): the rule sets, the 100-bet floor, the sentence, the file."""
    sys.path.insert(0, ROOT)
    from tools import kalshi_whatif as KW
    snap = json.load(open(os.path.join(ROOT, "research", "kalshi", "feed_snapshot_2026-11-04.json"), encoding="utf-8"))
    b = KW.build(snap)
    w, y = b["what_if"], b["why"]
    sets = {x["id"]: x for x in w["sets"]}
    bk = {(r["lo"], r["hi"]): r for r in KW.rows_of(snap)}
    check("w0. kalshi_whatif: the rule sets replay the past bets exactly: the bot as it is = the feed's settled-buy P&L, A = that minus the 90-95c band",
          abs(sets["asis"]["net"] - snap["stats"]["pnl"]) < 0.01 and abs(sets["A"]["net"] - (snap["stats"]["pnl"] - bk[(0.9, 0.95)]["pnl"])) < 0.01 and sets["A"]["bets"] == snap["stats"]["trades"] - 581,
          [(k, v["net"], v["bets"]) for k, v in sets.items()])
    check("w0. kalshi_whatif: B and C shrink the past bets to 2% of the balance (cap $1.12), so their net is small and their ruin chance 0%",
          abs(w["cap_dollars"] - round(0.02 * snap["balance"], 2)) < 0.011 and 0 < sets["B"]["net"] < 30 and sets["B"]["ruin"] == 0 and sets["C"]["ruin"] == 0 and sets["asis"]["ruin"] > 0.05, w)
    check("w0. kalshi_whatif: the one-line recommendation names the set the data supports (net up, ruin under 5%), with the paper-first warning",
          w["pick"] == "A" and "The data supports A" in w["recommend"] and "try it on paper first" in w["recommend"] and "−−" not in w["recommend"], w["recommend"])
    check("w0. kalshi_whatif: why = the top two leaks of different kinds in dollars (the 90-95c band, XRP), no double minus",
          [x["kind"] for x in y["leaks"]] == ["band", "coin"] and "$248.30" in y["text"] and "$106.63" in y["text"] and "−−" not in y["text"] and "mostly because" in y["text"], y["text"])
    few = dict(snap)
    few["buckets"] = [{"lo": 0.9, "hi": 0.95, "trades": 60, "wins": 55, "losses": 5, "pnl": -20.0, "staked": 400.0}, {"lo": 0.95, "hi": 0.99, "trades": 39, "wins": 38, "losses": 1, "pnl": 5.0, "staked": 300.0}]
    fb = KW.build(few)
    check("w0. kalshi_whatif: under 100 bets (99): 'not enough bets', no numbers, in both the what-if and the why",
          not fb["what_if"]["enough"] and fb["what_if"]["sets"] == [] and "Not enough bets yet (99 of 100)" in fb["what_if"]["recommend"] and not fb["why"]["enough"], fb["what_if"])
    check("w0. kalshi_whatif: deterministic (the same feed gives the same file)", json.dumps(KW.build(snap), sort_keys=True) == json.dumps(KW.build(snap), sort_keys=True))
    return b


def part_whatif(br, url, tmp):
    """'Why am I losing' (top of Today) and 'If you change the bot' (Edge): the page's numbers equal tools/kalshi_whatif.py's, a backtest
    labelled as such, not enough bets under 100, never blank, taps >= 44 px, escaping, small phones."""
    page_url = url + "kalshi/"
    b = part_whatif_py()
    snap = json.load(open(os.path.join(ROOT, "research", "kalshi", "feed_snapshot_2026-11-04.json"), encoding="utf-8"))
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    p = ctx.new_page()
    p.set_default_timeout(120000)
    errs, posts = [], []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"Failed to load resource|net::ERR", m.text) else None)
    p.on("request", lambda r: posts.append(r.method) if r.method not in ("GET", "HEAD") else None)

    def open_(j):
        FEED["mode"], FEED["j"] = "ok", j
        p.goto(page_url)
        p.evaluate("localStorage.clear()")
        p.goto(page_url)
        ready(p, 20000)
        p.wait_for_selector("#sec-why")

    j = dict(snap)
    j["running"], j["t"], j["pub_t"] = False, int(time.time()) - 20, int(time.time()) - 18
    open_(j)
    order = p.evaluate("[...document.querySelectorAll('#g-today > .card')].slice(0, 3).map((c) => c.id)")
    why = p.inner_text("#sec-why .why-t")
    check("w1. 'Why am I losing' is the first card of the app and says it in one sentence with the two biggest dollar leaks (the page's words = the city feed's words)",
          order[0] == "sec-why" and why == b["why"]["text"] and "$248.30" in why and "$106.63" in why, (order, why))
    check("w1. the sentence's button (What to change) is >= 44 px tall and glides to the what-if card",
          p.evaluate("document.querySelector('#sec-why .why-b').getBoundingClientRect().height") >= 44 and p.get_attribute("#sec-why .why-b", "data-v") == "sec-whatif")
    edge_first = p.evaluate("document.querySelector('#g-edge > .card').id")
    wi = p.inner_text("#sec-whatif")
    check("w2. 'If you change the bot' opens the Edge group, labelled a backtest of past bets, suggestions only, nothing places a bet",
          edge_first == "sec-whatif" and "if you change the bot" in wi.lower() and "a backtest of past bets" in wi.lower() and "suggestions only" in wi.lower() and "places or changes a bet" in wi.lower() and not posts
          and p.locator("#sec-whatif form, #sec-whatif a").count() == 0, (edge_first, wi[:200]))
    check("w2. the one-line recommendation is the city feed's (set A: +$185.48 after fees, 0% ruin against -$62.82 and 13% as the bot is)",
          p.inner_text("#sec-whatif .wi-rec") == b["what_if"]["recommend"] and "+$185.48" in wi and "−$62.82" in wi, p.inner_text("#sec-whatif .wi-rec"))
    got = p.eval_on_selector_all("#sec-whatif .wi-set", """els => els.map(e => [e.querySelector('.wi-n').textContent.replace(/the data favours this/i, '').trim(),
      ...[...e.querySelectorAll('dd')].map(d => d.textContent)])""")
    ok = len(got) == 4
    for g_, x in zip(got, b["what_if"]["sets"]):
        net = KW_usd(x["net"])
        ruin = round(x["ruin"] * 100)
        pr = g_[3].replace("<", "").replace("%", "")
        ok = ok and g_[1] == net and abs(int(pr) - ruin) <= 1 and abs(float(g_[2].replace("$", "").replace(",", "")) - x["dip"]) <= max(0.5, 0.05 * x["dip"])
    check("w2. four sets (as it is, A, B, C) with net $ after fees, typical worst dip $ and ruin % equal to tools/kalshi_whatif.py (net exact, dip within 5%, ruin within 1 point)", ok, got)
    heights = p.evaluate("[...document.querySelectorAll('#sec-whatif .wi-h')].map((b) => Math.round(b.getBoundingClientRect().height))")
    p.click("#sec-whatif .wi-h >> nth=1")
    ex = p.inner_text("#sec-whatif .wi-set >> nth=1")
    check("w3. every set header is a >= 44 px tap that opens its rule in words (A: skips 90–95¢, 1,255 of the past 1,836 bets stay in)",
          len(heights) == 4 and min(heights) >= 44 and "Skips every bet priced 90–95¢" in ex and "1,255 of the past 1,836 bets" in ex, (heights, ex))
    check("w3. the footnote says what net, dip and ruin are, and that a past replay is not a promise", "not a promise" in p.inner_text("#sec-whatif .wi-f") and "400 seeded runs" in p.inner_text("#sec-whatif .wi-f"))
    # ---- the forward test strip at the bottom of the card: RETIRED 2026-11-20 (kalshicity/forward.json came only from the retired kalshi-feed repo)
    strip0 = p.inner_text("#sec-whatif #wi-fwd")
    asked = p.evaluate("performance.getEntriesByType('resource').map((r) => r.name).filter((u) => /forward\\.json|scan\\.json/.test(u))")
    check("w3. forward strip: says plainly it is retired (the old bot's feed was switched off on 2026-11-19, K8 is tested on paper on the home computer), never 'collecting: 0 bets'; "
          "the page never asks for kalshicity/forward.json or scan.json",
          "forward test" in strip0.lower() and "retired" in strip0 and "2026-11-19" in strip0 and "collecting" not in strip0
          and p.locator("#sec-whatif > .wi-fwd:last-child").count() == 1 and not asked, (strip0, asked))
    open_(j)
    # ---- under 100 bets: not enough, never blank
    open_(sample(time.time()))
    check("w4. under 100 bets (the publisher's sample): both cards still show and say 'not enough bets', no sets, no numbers",
          "Not enough settled bets yet" in p.inner_text("#sec-why .why-t") and "Not enough bets yet" in p.inner_text("#sec-whatif .muted") and p.locator("#sec-whatif .wi-set").count() == 0 and "forward test" in p.inner_text("#sec-whatif").lower()
          and p.locator("#sec-why .why-b").count() == 0, p.inner_text("#sec-whatif")[:200])
    # ---- the sample preview and escaping
    FEED["mode"], FEED["j"] = "404", None
    p.goto(page_url)
    p.evaluate("localStorage.clear()")
    p.goto(page_url)
    p.wait_for_selector("[data-act=preview]")
    p.click("[data-act=preview]")
    p.wait_for_selector("#sec-why")
    check("w5. the sample preview carries both cards (never blank)", p.locator("#sec-why .why-t").inner_text() != "" and p.locator("#sec-whatif").count() == 1)
    evil = dict(j)
    evil["categories"] = [dict(c, name="<img src=x onerror=window.__pwned=1>") if c["name"] == "XRP" else c for c in evil["categories"]]
    evil["strategies"] = [dict(x, name="<b onmouseover=window.__pwned=1>x</b>") for x in evil["strategies"]]
    open_(evil)
    check("w5. hostile names are text, never markup", p.evaluate("!window.__pwned") and p.locator("#sec-why img, #sec-why b, #sec-whatif img").count() == 0)
    ctx2 = br.new_context(viewport={"width": 375, "height": 667}, device_scale_factor=1)
    ctx2.route("https://raw.githubusercontent.com/**", feed)
    ctx2.route("https://api.github.com/**", feed)
    q = ctx2.new_page()
    q.set_default_timeout(120000)
    FEED["mode"], FEED["j"] = "ok", j
    q.goto(page_url)
    q.evaluate("localStorage.clear()")
    q.goto(page_url)
    ready(q, 20000)
    q.wait_for_selector("#sec-whatif")
    sw = q.evaluate("[document.documentElement.scrollWidth, innerWidth, Math.max(...[...document.querySelectorAll('#sec-why *, #sec-whatif *')].map((e) => e.getBoundingClientRect().right))]")
    check("w6. 375 x 667: both cards fit (no sideways scroll, nothing past the right edge)", sw[0] <= sw[1] and sw[2] <= sw[1] + 0.5, sw)
    ctx2.close()
    check("w7. no page errors and no failed section", not errs and "could not be shown" not in p.inner_text("#body"), errs[:3])
    ctx.close()


def part_scan(br, url, tmp):
    """'Where the money is' (Edge, under the what-if card): the same maths on the feed's price bands (scan.json is retired 2026-11-20 and never asked for),
    else a dated sample; looking back, not proven; never blank; every tap >= 44 px; text only."""
    page_url = url + "kalshi/"
    sys.path.insert(0, ROOT)
    from tools import kalshi_scan as KS
    snap = json.load(open(os.path.join(ROOT, "research", "kalshi", "feed_snapshot_2026-11-04.json"), encoding="utf-8"))
    scan = KS.scan(snap)
    kdir = os.path.join(tmp, "nq-dashboard", "kalshicity")
    os.makedirs(kdir, exist_ok=True)
    spath = os.path.join(kdir, "scan.json")
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    p = ctx.new_page()
    p.set_default_timeout(120000)
    errs, posts = [], []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"Failed to load resource|net::ERR", m.text) else None)
    p.on("request", lambda r: posts.append(r.method) if r.method not in ("GET", "HEAD") else None)
    j = dict(snap)
    j["running"], j["t"], j["pub_t"] = False, int(time.time()) - 20, int(time.time()) - 18

    def open_(feed_j, wait_text=None):
        FEED["mode"], FEED["j"] = "ok", feed_j
        p.goto(page_url)
        p.evaluate("localStorage.clear()")
        p.goto(page_url)
        ready(p, 20000)
        p.wait_for_selector("#sec-scan")
        if wait_text:
            p.wait_for_function(f"document.querySelector('#sec-scan').textContent.indexOf({json.dumps(wait_text)}) >= 0", timeout=60000)
    try:
        # scan.json is no longer asked for (2026-11-20: it came only from the retired kalshi-feed repo): even a file on the site is ignored
        with open(spath, "w", encoding="utf-8") as fh:
            json.dump(scan, fh)
        open_(j)
        time.sleep(1.5)
        order = p.evaluate("[...document.querySelectorAll('#g-edge > .card')].slice(0, 2).map((c) => c.id)")
        tb = p.inner_text("#sec-scan")
        asked = p.evaluate("performance.getEntriesByType('resource').map((r) => r.name).filter((u) => /scan\\.json/.test(u))")
        check("s1. the card follows the what-if card in Edge, says 'looking back, not proven, suggestions only', two groups; it never asks for scan.json (retired), "
              "so even a file on the site is ignored: the same maths on this feed's price bands",
              order == ["sec-whatif", "sec-scan"] and "looking back" in tb.lower() and "not proven" in tb.lower() and "suggestions only" in tb.lower() and "worth a paper test" in tb.lower()
              and "avoid" in tb.lower() and "price bands only" in tb and not asked, (order, tb[:200], asked))
        rows = p.eval_on_selector_all("#sec-scan .sc-h", "els => els.map(e => [e.querySelector('.sc-n').textContent.trim(), e.querySelector('b').textContent, Math.round(e.getBoundingClientRect().height)])")
        check("s4. from the bands: the 90–95¢ band on the avoid list with −1.1¢, rows to paper-test too, each a >= 44 px tap",
              p.locator("#sec-scan .sc-i.avoid").count() >= 1 and "−1.1¢" in tb and p.locator("#sec-scan .sc-i.test").count() >= 1 and rows and min(h for _, _, h in rows) >= 44, rows)
        p.click("#sec-scan .sc-i.avoid .sc-h >> nth=0")
        check("s4. and its sentence carries the dollars", "−$248" in p.inner_text("#sec-scan .sc-d") or "$248" in p.inner_text("#sec-scan .sc-d"), p.inner_text("#sec-scan .sc-d"))
        p.click("#sec-scan .sc-i.avoid .sc-h >> nth=0")
        check("s2. tapping it again closes it; nothing on the card places an order (no form, no link, no POST)",
              p.locator("#sec-scan .sc-d").count() == 0 and p.locator("#sec-scan form, #sec-scan a").count() == 0 and not posts)
        os.remove(spath)
        open_(j)
        check("s5. no scan.json on the site at all: the card is still there (never blank), from the bands", "price bands only" in p.inner_text("#sec-scan") and p.locator("#sec-scan .sc-h").count() >= 2)
        # a feed with no price bands and no scan.json: the dated sample, labelled
        open_(sample(time.time()))
        ts_ = p.inner_text("#sec-scan")
        check("s5. a feed with no bands and no scan.json: a dated sample from the 2026-11-04 research, labelled 'not your live numbers', 2 + 2 rows",
              "2026-11-04 research" in ts_ and "not your live numbers" in ts_ and p.locator("#sec-scan .sc-h").count() == 4, ts_[:200])
        FEED["mode"], FEED["j"] = "404", None
        p.goto(page_url)
        p.evaluate("localStorage.clear()")
        p.goto(page_url)
        p.wait_for_selector("[data-act=preview]")
        p.click("[data-act=preview]")
        p.wait_for_selector("#sec-scan")
        check("s5. the sample preview carries the card too", p.locator("#sec-scan .sc-h").count() >= 2)
        ctx2 = br.new_context(viewport={"width": 375, "height": 667}, device_scale_factor=1)
        ctx2.route("https://raw.githubusercontent.com/**", feed)
        ctx2.route("https://api.github.com/**", feed)
        q = ctx2.new_page()
        q.set_default_timeout(120000)
        with open(spath, "w", encoding="utf-8") as fh:
            json.dump(scan, fh)
        FEED["mode"], FEED["j"] = "ok", j
        q.goto(page_url)
        q.evaluate("localStorage.clear()")
        q.goto(page_url)
        ready(q, 20000)
        q.wait_for_selector("#sec-scan")
        q.wait_for_function("document.querySelector('#sec-scan').textContent.indexOf('Looking back') >= 0", timeout=60000)
        q.click("#sec-scan .sc-h >> nth=0")
        sw = q.evaluate("[document.documentElement.scrollWidth, innerWidth, Math.max(...[...document.querySelectorAll('#sec-scan *')].map((e) => e.getBoundingClientRect().right))]")
        check("s6. 375 x 667: the card (rows open) fits, no sideways scroll, nothing past the right edge", sw[0] <= sw[1] and sw[2] <= sw[1] + 0.5, sw)
        ctx2.close()
        check("s7. no page errors and no failed section", not errs and "could not be shown" not in p.inner_text("#body"), errs[:3])
    finally:
        if os.path.exists(spath):
            os.remove(spath)
        if os.path.isdir(kdir) and not os.listdir(kdir):
            os.rmdir(kdir)
        ctx.close()


def KW_usd(x):
    v = round(abs(x) + 1e-9, 2)
    return ("−" if x < 0 and v else "+" if v else "") + f"${v:,.2f}"


def part_rewards(br, url, tmp):
    """'Rewards test (paper)' (2026-11-17, kalshi.js rewardsLoad): under the PAUSED note, $ earned / fill $ / net / days of the paper
    rewards test; rewards.json (the site's dated copy + the backtest line) first, the PC's ntfy status post (key kalshi_rewards) when newer;
    hidden when neither is readable; text only (escaped); inside the 16 px gutters at 375 px; GET only."""
    page_url = url + "kalshi/"
    copy = json.load(open(os.path.join(KS, "rewards.json"), encoding="utf-8"))
    ctx = br.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2)
    ctx.route("https://raw.githubusercontent.com/**", feed)
    ctx.route("https://api.github.com/**", feed)
    R = {"own": "file", "ntfy": None, "asked": []}

    def own(route):
        if R["own"] == "file":
            return route.continue_()
        if R["own"] == "404":
            return route.fulfill(status=404, body="no")
        return route.fulfill(status=200, content_type="application/json", body=R["own"])

    def ntfy(route):
        R["asked"].append(route.request.url)
        if R["ntfy"] is None:
            return route.abort()
        return route.fulfill(status=200, content_type="application/x-ndjson", body=R["ntfy"])
    ctx.route("**/kalshi/rewards.json", own)
    ctx.route("https://ntfy.invalid/**", ntfy)
    p = ctx.new_page()
    p.set_default_timeout(60000)
    errs, posts = [], []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"Failed to load resource|net::ERR", m.text) else None)
    p.on("request", lambda r: posts.append(r.method) if r.method not in ("GET", "HEAD") else None)
    FEED["mode"] = "404"

    def open_(wait=True):
        p.goto(page_url)
        if wait:
            p.wait_for_selector("#krw:not([hidden])", timeout=20000)
    try:
        check("rw0. the site has rewards.json: a paper-only copy (kind kalshi_rewards_pub) and a backtest line",
              isinstance(copy.get("paper"), dict) and copy["paper"].get("kind") == "kalshi_rewards_pub" and copy["paper"].get("paper_only") is True
              and isinstance(copy.get("backtest"), dict) and bool(copy["backtest"].get("text")), str(copy)[:200])
        open_()
        t = p.inner_text("#krw")
        order = p.evaluate("[...document.querySelectorAll('main > section, main > div, main > h2')].map((e) => e.id).filter(Boolean).slice(0, 9).join(' ')")
        check("rw1. K8 first (Olympus 2): live day, K8 status, the go-live checklist, then 'History and tests' with the PAUSED note and this card: "
              "'Rewards test (paper)', Earned, Fills, Net, Days, '$0 at risk', 'saved copy', the backtest line",
              order.startswith("k8top k8fx k8d k8s kgo khist kpaused krw") and "Rewards test (paper)" in t
              and all(w in t for w in ("Earned", "Fills", "Net", "Days", "$0 at risk", "saved copy", "Backtest (30 days)")), t[:300])
        check("rw1. the numbers are the copy's ($ earned, fill $)", ("$%.2f" % copy["paper"]["reward"]) in t, t[:200])
        k0 = p.inner_text("#kpaused")
        check("rw1. the Kalshi home's status line: 'Kalshi: PAUSED for real money', the rewards net $ over N days, K1 rules",
              "KALSHI: PAUSED" in k0.upper() and "for real money" in k0 and ("rewards (net +$%.2f over" % copy["paper"]["net"]) in k0 and "K1 rules" in k0, k0[:300])
        check("rw1. the card shows its age; a saved copy over 1 h old says the PC sent nothing newer (amber)",
              "updated " in t and "the PC has not sent newer numbers" in t and p.locator("#krw .krw-age.old").count() == 1, t[-200:])
        hub = p.evaluate("""() => { const h = document.getElementById('khub'), W = window.innerWidth, r = h.getBoundingClientRect();
            const a = (s) => [...h.querySelectorAll(s + ' a')].map((x) => x.getAttribute('href'));
            const rows = [...h.querySelectorAll('.kh-l li, .kh-a li')].filter((x) => x.getBoundingClientRect().height < 43.5).length;
            return [document.getElementById('krw').nextElementSibling.id, a('.kh-l'), a('.kh-a'), h.textContent, r.left >= 15.5 && r.right <= W - 15.5, rows,
                    [...h.querySelectorAll('*')].filter((x) => x.scrollWidth > x.clientWidth + 1).length]; }""")
        check("rw7. the Kalshi home under the rewards card: 9 tested ideas each with its verdict and a link to its write-up (Clio)",
              hub[0] == "kk1" and len(hub[1]) == 9 and all(h.startswith("../clio/?q=") for h in hub[1]) and "What we tested and why it's paused" in hub[3]
              and all(w in hub[3] for w in ("Loses", "No edge", "Too weak", "Paper test")), hub[:2])
        check("rw7. links to Kalshi City, Dionysus and Sibyl, and 'What would turn it back on' (100+ paper bets, 4+ weeks, 95% range above $0)",
              hub[2] == ["../kalshicity/", "../dionysus/", "../sibyl/"] and "What would turn it back on" in hub[3] and "100+ settled bets" in hub[3]
              and "95% range above $0" in hub[3], hub[2])
        kk = p.inner_text("#kk1")
        check("k1a. no PC numbers: the K1 card says plainly it is not running yet / not arriving, and the status line says so",
              "K1 rules test (paper)" in kk and "No numbers yet" in kk and "next update" in kk and "K1 rules (not running yet)" in k0, (kk[:200], k0[:200]))
        check("rw7. 375 px: the home inside the 16 px gutters, every link row at least 44 px tall, nothing cut off", hub[4] and hub[5] == 0 and hub[6] == 0, hub[4:])
        pc = dict(copy["paper"], reward=12.34, fill_pnl=-2.5, net=9.84, days=3.2, updated="2099-01-01T00:00:00+00:00", fills=7)
        msg = {"kind": "le-live", "t": 1, "kalshi_rewards": pc}
        R["ntfy"] = json.dumps({"event": "message", "time": 1, "message": json.dumps(msg)}) + "\n" + '{"event":"keepalive"}\n'
        open_()
        p.wait_for_function("document.querySelector('#krw').textContent.indexOf('from the PC') >= 0", timeout=20000)
        t = p.inner_text("#krw")
        check("rw2. the PC's newer status post wins: $12.34 earned, -$2.50 fills, +$9.84 net, 3.2 days, 7 fills, 'from the PC'",
              all(w in t for w in ("$12.34", "−$2.50", "+$9.84", "3.2", "7 fills", "from the PC")), t[:300])
        k1 = p.inner_text("#kpaused")
        check("rw2. the status line follows the PC: 'rewards (net +$9.84 over 3.2 days)'; a fresh post reads 'updated just now', not amber",
              "rewards (net +$9.84 over 3.2 days)" in k1 and "updated just now" in t and p.locator("#krw .krw-age.old").count() == 0, (k1[:200], t[-120:]))
        check("rw2. the status topic is read from ../status_feed.json (ntfy poll, GET)", any("/olympus-test-status/json?poll=1" in u for u in R["asked"]), R["asked"][:2])
        pc2 = dict(pc, reward=23.45, net=20.95, updated="2099-02-01T00:00:00+00:00")       # 2026-11-18 split: the card rides in the ext post
        ext = {"kind": "le-live-ext", "t": 2, "rt": 2, "part": 0, "of": 1, "x": {"kalshi_rewards": pc2}}
        R["ntfy"] = "\n".join(json.dumps({"event": "message", "time": i + 1, "message": json.dumps(m)}) for i, m in enumerate([msg, ext, {"kind": "le-live", "t": 3}])) + "\n"
        open_()
        p.wait_for_function("document.querySelector('#krw').textContent.indexOf('$23.45') >= 0", timeout=20000)
        check("rw2. the split status (core + le-live-ext post): the ext's newer rewards card wins ($23.45)", "$23.45" in p.inner_text("#krw"))
        k1c = {"kind": "kalshi_k1_pub", "paper_only": True, "updated": "2099-02-01T00:00:00Z", "days": 2.5, "sig": 14, "set": 6, "net": -0.8, "pu": -0.123}
        R["ntfy"] = json.dumps({"event": "message", "time": 1, "message": json.dumps({"kind": "le-live-ext", "t": 2, "part": 0, "of": 1, "x": {"kalshi_k1": k1c}})}) + "\n"
        open_()
        p.wait_for_function("document.querySelector('#kk1').textContent.indexOf('Signals') >= 0", timeout=20000)
        kt = p.inner_text("#kk1")
        check("k1b. the PC's ext post fills the K1 card: Signals 14, Settled 6, Net -$0.80, 2.5 Days, -$0.12 per $1, 'from the PC', age shown",
              all(w in kt for w in ("14", "6", "−$0.80", "2.5", "−$0.12 per $1", "from the PC", "updated")) and "K1 rules (−$0.80 over 2.5 days)" in p.inner_text("#kpaused"), kt[:300])
        # Kalshi LIVE executor (engine/kalshi_live.py, night-klive): OFF = the plain PAUSED line; its PC card (key kalshi_live) = LIVE / STOPPED
        check("kl0. no PC card: the status line says plainly 'PAPER: the PC records every window with no money' (night-kalshi8), "
              "'Live only when you type the phrase' and '$0 at risk'",
              "PAPER: the PC records every window with no money" in k0 and "Live only when you type the phrase" in k0 and "$0 at risk" in k0, k0[:300])
        # phone QA 2026-11-19: the live line names the bot the owner knows (K8, gold and silver) and, with the PC's Kalshi numbers in, the
        # header says the PC runs Kalshi (with their age) instead of the old kalshi-server's "Not connected yet"
        sub = p.inner_text("#sub")
        check("kl0. the line names K8 (the gold and silver clock bot); the header: 'On your PC · real money paused · updated ...'",
              "K8, the gold and silver clock bot" in k0 and sub.startswith("On your PC · real money paused · updated "), (k0[:200], sub))
        klc = {"kind": "kalshi_live_pub", "v": 1, "st": "live", "net": 1.25, "f": 3, "o": 6, "cap": 60, "stop": 8, "u": "2099-02-01T00:00:00+00:00"}
        R["ntfy"] = json.dumps({"event": "message", "time": 1, "message": json.dumps({"kind": "le-live-ext", "t": 2, "part": 0, "of": 1,
                                                                                    "x": {"kalshi_k1": k1c, "kalshi_live": klc}})}) + "\n"
        open_()
        p.wait_for_function("document.querySelector('#kpaused-live').textContent.indexOf('LIVE:') >= 0", timeout=20000)
        kl = p.inner_text("#kpaused")
        check("kl1. the PC's Kalshi LIVE card turns the line into 'Kalshi: LIVE': today +$1.25, 3 fills, 6 orders resting, the limits, "
              "'At most $60.00 at risk' (never '$0 at risk' while live)", "KALSHI: LIVE" in kl.upper()
              and all(w in kl for w in ("+$1.25", "3 fills", "6 orders resting", "$60.00 total", "At most $60.00 at risk"))
              and "$0 at risk" not in kl and "ready to go live" not in kl, kl[:400])
        R["ntfy"] = json.dumps({"event": "message", "time": 1, "message": json.dumps({"kind": "le-live-ext", "t": 2, "part": 0, "of": 1, "x": {
            "kalshi_live": dict(klc, st="stopped", net=-8.4, why="daily loss stop: day -$8.40")}})}) + "\n"
        open_()
        p.wait_for_function("document.querySelector('#kpaused-live').textContent.indexOf('STOPPED') >= 0", timeout=20000)
        kl = p.inner_text("#kpaused")
        check("kl2. after a stop: 'Kalshi: STOPPED (daily loss stop ...)': it is OFF, today -$8.40, type the phrase on the PC to restart",
              "KALSHI: STOPPED" in kl.upper() and all(w in kl for w in ("daily loss stop", "OFF", "−$8.40", "type the phrase", "No new orders")), kl[:400])
        # K8 status card (night-kalshi8): the card's k8 block = mode, bankroll, a bet, today, next window, last 10, week / peak stops
        k8 = {"m": "P", "nx": 4102444800, "b": 55, "s": 2.5, "td": [3, 2, 1.85], "l": "WWLWLLWWWL", "wk": [4.3, 13.75], "dd": [6.2, 16.5],
              "wr": [41, 71], "lp": 1}
        R["ntfy"] = json.dumps({"event": "message", "time": 1, "message": json.dumps({"kind": "le-live-ext", "t": 2, "part": 0, "of": 1, "x": {
            "kalshi_live": {"kind": "kalshi_live_pub", "v": 1, "st": "paper", "u": "2099-02-01T00:00:00+00:00", "k8": k8}}})}) + "\n"
        open_()
        p.wait_for_function("document.querySelectorAll('#k8s .k8s-l span').length === 10", timeout=20000)
        kt = p.inner_text("#k8s")
        geo = p.evaluate("""() => { const W = window.innerWidth, de = document.documentElement, e = document.getElementById('k8s'), r = e.getBoundingClientRect();
            return [de.scrollWidth <= de.clientWidth, r.left >= 15.5 && r.right <= W - 15.5]; }""")
        check("kl3. a PAPER card with the K8 block fills the K8 status card: PAPER, $55.00 bankroll, $2.50 a bet, today 3 bets +$1.85, a next-window "
              "countdown, the last 10 (W/L), this week $4.30 of $13.75 and the peak $6.20 of $16.50; 41 bets 71% won; inside the gutters",
              all(w in kt for w in ("PAPER", "$55.00", "$2.50", "3 bets, +$1.85", "Next window", "−$4.30 of −$13.75", "−$6.20 of −$16.50", "41 bets, 71% won"))
              and p.evaluate("document.querySelectorAll('#k8s .k8s-l span.w').length") == 6 and geo == [True, True]
              and "running on the PC with no money" in p.inner_text("#kpaused"), (kt[:400], geo))
        R["ntfy"] = None
        bad = dict(copy, paper=dict(copy["paper"], reward="<img src=x onerror=window.__pwn=1>"),
                   backtest={"text": "<script>window.__pwn=1</script>bad"})
        R["own"], R["ntfy"] = json.dumps(bad), None
        p.goto(page_url)
        p.wait_for_timeout(1500)
        check("rw3. junk numbers or markup: no script runs, the card hides or shows text only",
              p.evaluate("!window.__pwn && !document.querySelector('#krw img, #krw script')"), "")
        R["own"] = "404"
        p.goto(page_url)
        p.wait_for_timeout(1500)
        check("rw4. no copy and no PC post: the card stays hidden (never an empty box)", p.evaluate("document.querySelector('#krw').hidden"), "")
        check("rw4. ... and the status line says 'rewards (no numbers yet)'", "rewards (no numbers yet)" in p.inner_text("#kpaused"), p.inner_text("#kpaused")[:200])
        R["own"], R["ntfy"] = "file", None
        open_()
        m = p.evaluate("""() => { const W = window.innerWidth, de = document.documentElement, e = document.getElementById('krw'), r = e.getBoundingClientRect();
            const cut = [...e.querySelectorAll('dd, dt, p')].filter((x) => x.scrollWidth > x.clientWidth + 1).length;
            return [de.scrollWidth <= de.clientWidth, r.left >= 15.5 && r.right <= W - 15.5, cut]; }""")
        check("rw5. 375 px: no sideways scroll, the card inside the 16 px gutters, no number cut off", m[0] and m[1] and m[2] == 0, m)
        check("rw6. no page errors, GET only", not errs and not posts, (errs[:3], posts[:3]))
    finally:
        ctx.close()


def main():
    global STEP, PASTE, STEP_PINNED, PASTE_PINNED
    part_a()
    from tests import pw_skip
    if pw_skip.missing("the browser parts (b ...)"):       # night-reds2: a container without it; the PC runs everything
        n = sum(RES)
        print(f"\nkalshi page: {n}/{len(RES)} " + ("PASS (browser parts skipped)" if n == len(RES) else "FAILED"))
        return 0 if n == len(RES) else 1
    tmp = site(tempfile.mkdtemp(prefix="le_kalshi_page_"))
    srv = serve(tmp)
    try:
        _origin = f"http://127.0.0.1:{srv.server_address[1]}"           # what the page's {SITE_URL} becomes
        STEP = STEP_T.replace("{SITE_URL}", _origin)
        PASTE = STEP.split("paste: ", 1)[1]
        STEP_PINNED = STEP + f" (only run kalshi_status_vm.py if its sha256 is {KIT_SHA})"
        PASTE_PINNED = STEP_PINNED.split("paste: ", 1)[1]
        run_browser(f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/", tmp)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
