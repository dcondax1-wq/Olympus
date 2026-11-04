"""TYCHE (tools/web_public/tyche/, owner 2026-11-03): the Kalshi bot's bets as a 3D wheel of fortune. Read-only.

It reads the same kalshi.json as the Kalshi page (docs/KALSHI_PUBLISH.md): raw.githubusercontent.com first, the GitHub API
when raw fails; a 404 = the bot is not linked yet -> the demo ("Not linked yet: demo") and a 10-minute backoff, so a load
makes one request. The fixtures go through the real publisher's clean() (engine.kalshi_publish), so the page is tested
against exactly what the bot's server sends.

Runs the real page in Chromium (WebGL through SwiftShader) on a local copy of the site layout (/tyche/, /jarvis/), answers
the two GitHub endpoints itself, and checks:
  a. the files and the static rules: every module used, three.js only from ../jarvis/, no outside URL but the two feed
     endpoints (the same as the Kalshi page's), viewport / theme-color / safe areas / the orb's corner / reduced motion, no
     innerHTML, Safari 16 safe, jarvis.json by the Jarvis contract (with theme), the site build and the root worker know it
  b. the pure parts in the browser: normalize() of v3 / v2 / v1 / junk, Kelly, the formats, the Feed's 404 backoff
  c. not linked (404) at 390 x 844 and 844 x 390: ONE request per load, the "Not linked yet: demo" chip, no console errors,
     the HUD = the demo's numbers, a coin per open bet, no sideways scroll, the orb's corner free, in all three views
  d. a v3 feed: LIVE, every HUD number = the fixture's (balance, today, week, open, win rate, ROI, next settlement), a coin
     per position, the Kelly slider's stakes (capped at the max bet), the pools' and the scales' panels, a tapped coin's sheet
  e. a v2 and a v1 feed (no v3 fields) still render with the numbers they carry; a stale feed says LAST SEEN; raw failing
     falls back to the API; nothing reachable = "Offline: demo"; ?demo=1 makes no request; reduced motion; Jarvis's card
  f. across every case: no request outside the page's origin but the two feed endpoints
    python -X utf8 -m tests.test_tyche_page            (--shots: screenshots to research/handoff/2026-11-03/tyche/)
"""
from __future__ import annotations

import copy
import glob
import http.server
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
TY = os.path.join(WEB, "tyche")
MODULES = ["main.js", "data.js", "demo.js", "fmt.js", "scene.js", "wheel.js", "pools.js", "scales.js", "glow.js", "hud.js", "sparks.js", "bankroll.js", "caustics.js", "fortune.js", "fortunepanel.js", "tychefx.js"]
RAW = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
API = "https://api.github.com/repos/demetrades2000-coder/kalshi-feed/contents/kalshi.json?ref=main"
THEME = "#07060b"
MINUS = "−"
RES: list = []
SHOTS = os.environ.get("TYCHE_SHOTS")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ formats (the page's own, fmt.js)
def usd(v, sign=False):
    if v is None:
        return "—"
    r = float(f"{abs(v):.2f}")
    pre = "" if r == 0 else MINUS if v < 0 else "+" if sign and v > 0 else ""
    return f"{pre}${r:,.2f}"


def pct(x, sign=False, d=1):
    if x is None:
        return "—"
    r = float(f"{abs(x * 100):.{d}f}")
    pre = "" if r == 0 else MINUS if x < 0 else "+" if sign and x > 0 else ""
    return f"{pre}{r:.{d}f}%"


# ------------------------------------------------------------------ fixtures: what the bot's server would publish
def kit():
    from engine import kalshi_publish
    return kalshi_publish


def fixture_v3(now: int, age: int = 20) -> dict:
    """A full v3 feed, through the publisher's clean(). Numbers picked away from rounding ties."""
    iso = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + s))
    pos = [
        # ticker, title, side, contracts, avg, price, prob, closes in, category
        ("KXBTCD-26NOV03-T96000", "Bitcoin above $96,000 at 5 PM ET", "yes", 20, 0.88, 0.91, 0.95, 4 * 3600, "Bitcoin"),
        ("KXHIGHNY-26NOV03-B58.5", "NYC high 58-59°F today", "yes", 30, 0.41, 0.44, 0.52, 280, "Weather"),
        ("KXINXU-26NOV03-B5950", "S&P 500 close 5,950-5,975", "no", 25, 0.52, 0.52, 0.55, 26 * 3600, "S&P 500"),
        ("KXCPI-26NOV-T0.2", "CPI m/m 0.2% or less", "yes", 40, 0.33, 0.35, 0.41, 3 * 86400, "Economics"),
        ("KXGOLDD-26NOV03-T2740", "Gold above $2,740 at 5 PM ET", "yes", 15, 0.7, 0.68, None, 7200, "Gold"),
        ("KXHIGHCHI-26NOV04-R0.1", "Chicago rain over 0.1 in", "no", 22, 0.47, 0.49, 0.58, 30 * 3600, "Weather"),
    ]
    positions = []
    for t, title, side, n, avg, px, prob, s, cat in pos:
        row = {"ticker": t, "title": title, "side": side, "contracts": n, "avg_price": avg, "price": px, "value": round(n * px, 2),
               "pnl": round(n * (px - avg), 2), "closes": iso(s), "category": cat, "strategy": "Model edge"}
        if prob is not None:
            row["prob"] = prob
        positions.append(row)
    trades = []
    for i in range(14):
        win = i % 3 != 2
        price = [0.42, 0.55, 0.91, 0.63, 0.35][i % 5]
        n = 10 + i
        trades.append({"t": now - 1800 - i * 3700, "ticker": f"KXHIGHNY-26NOV0{i % 3 + 1}-B{50 + i}", "title": f"Settled bet {i + 1}", "side": "yes",
                       "action": "settled", "contracts": n, "price": price, "pnl": round(n * (1 - price) * 0.98 if win else -n * price, 2),
                       "category": ["Weather", "Bitcoin", "Economics"][i % 3], "prob": round(min(0.99, price + 0.06), 2)})
    trades.insert(0, {"t": now - 600, "ticker": "KXCPI-26NOV-T0.2", "title": "CPI m/m 0.2% or less", "side": "yes", "action": "buy",
                      "contracts": 40, "price": 0.33})
    eq = [[now - 86400 * 30 + i * 86400, round(1500 + i * 33.1 + (17 if i % 4 == 0 else -9), 2)] for i in range(30)] + [[now - 60, 2481.37]]
    raw = {
        "name": "Kalshi Edge v2", "mode": "live", "running": True, "status": "Trading · 3 live strategies · 6 open bets", "t": now - age,
        "balance": 2481.37, "today_pnl": 46.82, "week_pnl": -12.4, "total_pnl": 981.37,
        "positions": positions, "trades": trades,
        "days": [["2026-10-30", 21.4], ["2026-10-31", -33.1], ["2026-11-01", 18.52]],
        "equity": eq,
        "strategies": [{"name": "15-min favourites", "mode": "live", "running": True, "today_pnl": 30.1, "total_pnl": 600.2, "trades": 150, "wins": 99, "losses": 51}],
        "categories": [{"name": "Weather", "group": "Climate", "trades": 90, "wins": 58, "losses": 32, "pnl": 512.11, "staked": 1904.2},
                       {"name": "Bitcoin", "group": "Crypto", "trades": 80, "wins": 52, "losses": 28, "pnl": 301.4, "staked": 1611.3},
                       {"name": "Economics", "group": "Economics", "trades": 40, "wins": 21, "losses": 19, "pnl": 167.86, "staked": 605.0}],
        "buckets": [{"lo": 0.2, "hi": 0.4, "trades": 30, "wins": 13, "losses": 17, "pnl": 88.2, "staked": 310.4},
                    {"lo": 0.4, "hi": 0.6, "trades": 80, "wins": 47, "losses": 33, "pnl": 402.6, "staked": 1520.1},
                    {"lo": 0.6, "hi": 0.8, "trades": 60, "wins": 41, "losses": 19, "pnl": 311.07, "staked": 1290.0},
                    {"lo": 0.9, "hi": 0.95, "trades": 40, "wins": 30, "losses": 10, "pnl": -41.3, "staked": 1000.0}],
        "calibration": [{"p": 0.33, "n": 30, "hit": 0.4333}, {"p": 0.51, "n": 80, "hit": 0.5875}, {"p": 0.71, "n": 60, "hit": 0.6833},
                        {"p": 0.93, "n": 40, "hit": 0.75}],
        "calib_basis": "model",
        "alerts": [{"t": now - 900, "level": "warn", "text": "3 losses in a row on Economics"}],
        "kelly": {"fraction": 0.25, "bankroll": 2400, "max_bet": 120, "min_edge": 0.03},
        "stats": {"trades": 210, "wins": 131, "losses": 79, "staked": 4120.5, "pnl": 981.37, "avg_price": 0.57},
    }
    return kit().clean(raw, now)


def fixture_v2(now: int) -> dict:
    d = copy.deepcopy(kit().SAMPLE_V2)
    d["t"] = now - 30
    d["positions"][0]["closes"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + 5400))
    return kit().clean(d, now)


def fixture_v1(now: int) -> dict:
    d = copy.deepcopy(kit().SAMPLE)
    d["t"] = now - 30
    d["positions"][0]["closes"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + 9000))
    d["trades"] += [{"t": now - 4000, "ticker": "KXHIGHNY-26NOV01-B57.5", "title": "NYC high 57-58°F on Nov 1", "side": "yes", "action": "settled",
                     "contracts": 10, "price": 0.42, "pnl": 5.8},
                    {"t": now - 8000, "ticker": "KXHIGHNY-26OCT31-B55.5", "title": "NYC high 55-56°F on Oct 31", "side": "no", "action": "settled",
                     "contracts": 5, "price": 0.6, "pnl": -3.0}]
    return kit().clean(d, now)


def expected(j: dict, now: float) -> dict:
    """The HUD's numbers worked out here, from the fixture, independently of the page."""
    st = j.get("stats")
    if st:
        w, l, roi = st["wins"], st["losses"], st["pnl"] / st["staked"]
    else:
        settled = [t for t in j.get("trades", []) if t.get("pnl") is not None and t.get("action") != "sell"]
        w = sum(1 for t in settled if t["pnl"] > 0.005)
        l = sum(1 for t in settled if t["pnl"] < -0.005)
        if j.get("strategies"):
            w, l = sum(s["wins"] for s in j["strategies"]), sum(s["losses"] for s in j["strategies"])
        staked = sum(abs(t["contracts"]) * t["price"] for t in settled)
        roi = sum(t["pnl"] for t in settled) / staked if staked else None
    pos = sorted(j.get("positions", []), key=lambda p: p["closes"])
    sign = lambda x: "flat" if x is None or abs(x) < 0.005 else "up" if x > 0 else "down"
    return {"h-balance": usd(j["balance"]), "h-today": usd(j["today_pnl"], True), "h-week": usd(j["week_pnl"], True),
            "h-open": str(len(j.get("positions", []))), "h-win": pct(w / (w + l)) if w + l else "—", "h-roi": pct(roi, True),
            "h-next-title": pos[0]["title"] if pos else "No open bet", "_signs": (sign(j["today_pnl"]), sign(j["week_pnl"]), sign(roi))}


# ------------------------------------------------------------------ the local site
FRAME_HTML = """<!doctype html><meta charset="utf-8"><body style="margin:0"><script>window.__cards = [];
addEventListener('message', (e) => { if (e.data && e.data.jarvis === 1) window.__cards.push(e.data); });</script>
<iframe src="/tyche/" style="border:0;width:390px;height:844px"></iframe></body>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/frame.html":
            data = FRAME_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def translate_path(self, path):
        p = path.split("?")[0].split("#")[0]
        if p.startswith("/tyche/") or p.startswith("/jarvis/") or p.startswith("/olympus/"):
            q = p.lstrip("/")
            if q.endswith("/"):
                q += "index.html"
            return os.path.join(WEB, *q.split("/"))
        return os.path.join(WEB, "__missing__")


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


FEED = {"raw": None, "api": None, "calls": []}     # (status, body) | "abort" | None (= 404)
OUTSIDE: list = []


def new_page(br, origin, vw, *, reduced=False, quality="high"):
    ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=2, reduced_motion="reduce" if reduced else "no-preference")

    def guard(route):
        u = route.request.url
        if u.startswith(origin) or u.startswith("data:") or u.startswith("blob:"):
            return route.continue_()
        base = u.split("?t=")[0]
        if base in (RAW, API):
            which = "raw" if base == RAW else "api"
            FEED["calls"].append(which)
            ans = FEED[which]
            if ans == "abort":
                return route.abort()
            st, body = ans if ans else (404, {"message": "Not Found"})
            return route.fulfill(status=st, body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
        OUTSIDE.append(u)
        return route.abort()
    ctx.route("**/*", guard)
    if quality:     # a chosen quality: SwiftShader is slow, and auto-LITE must not change the scene under the checks
        # the OLYMPUS kit's one 3D level (Jarvis's 'jfx' key) is the page's quality (docs/OLYMPUS_DESIGN.md)
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")
    p = ctx.new_page()
    p.set_default_timeout(150000)
    log = {"errors": [], "console": []}
    p.on("pageerror", lambda e: log["errors"].append(str(e)))
    p.on("console", lambda m: log["console"].append((m.text, (m.location or {}).get("url", ""))) if m.type == "error" else None)
    return ctx, p, log


def real_errors(log):
    """Page errors and console errors, except the browser's own line for an expected 404 / failed feed request."""
    return log["errors"] + [t for t, u in log["console"] if "Failed to load resource" not in t]


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], **({"executable_path": exe} if exe else {}))


def ready(p, timeout=150000):
    p.wait_for_function("document.body.dataset.ready === '1' && window.tyche && window.tyche.model && window.tyche.coins > 0", timeout=timeout)


def shot(p, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        p.wait_for_timeout(2500)
        p.screenshot(path=os.path.join(SHOTS, name + ".png"))


def orb_free(p):
    """Nothing the owner can tap or read sits in the bottom-right 80 x 160 px (Jarvis's orb): no control under any point of it,
    and no shown 3D label or HUD box over it (labels let taps through, so they are checked by their boxes); the OLYMPUS seal (.oly-home) sits in the orb's seat only when the page is opened alone: Jarvis's orb is there when framed."""
    return p.evaluate("""() => { const W = innerWidth, H = innerHeight, bad = [];
      for (let x = W - 78; x < W; x += 6) for (let y = H - 158; y < H; y += 6)
        for (const e of document.elementsFromPoint(x, y)) if (!['HTML', 'BODY', 'CANVAS'].includes(e.tagName) && e.id !== 'labels' && !e.closest('.oly-home')) bad.push(e.id || e.className || e.tagName);
      for (const e of document.querySelectorAll('#labels .lb, #dock, .panel, .sheet, .tabs')) {
        if (e.hidden || e.closest('[hidden]')) continue;
        const r = e.getBoundingClientRect();
        if (r.width && r.right > W - 80 && r.bottom > H - 160 && r.left < W && r.top < H) bad.push('box:' + (e.id || e.className));
      }
      return [...new Set(bad)]; }""")


def no_sideways(p):
    return p.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth")


def hud(p):
    return p.evaluate("""() => { const o = {}; for (const id of ['h-balance', 'h-today', 'h-week', 'h-open', 'h-win', 'h-roi', 'h-next-title', 'h-next-cd'])
      o[id] = document.getElementById(id).textContent; o._signs = ['h-today', 'h-week', 'h-roi'].map((i) => document.getElementById(i).dataset.sign);
      o._chip = document.getElementById('mode').textContent.trim(); o._mode = document.getElementById('mode').dataset.mode; return o; }""")


def cd_seconds(s: str):
    m = re.fullmatch(r"(?:(\d+)d (\d+)h|(\d+)h (\d\d)m|(\d+)m (\d\d)s)", s)
    if not m:
        return None
    d, h, h2, m2, mm, ss = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + h2 * 3600 + m2 * 60 + mm * 60 + ss


# ------------------------------------------------------------------ a. static
def static_checks():
    files = {n: read(os.path.join(TY, n)) for n in MODULES}
    idx, css, jj = read(os.path.join(TY, "index.html")), read(os.path.join(TY, "tyche.css")), read(os.path.join(TY, "jarvis.json"))
    every = "\n".join([idx, css] + list(files.values()))
    check("a. every file is there", all(os.path.isfile(os.path.join(TY, n)) for n in MODULES + ["index.html", "tyche.css", "jarvis.json"]))
    imported = set(re.findall(r"from '\./([a-z]+\.js)'", "\n".join(files.values())))
    check("a. every module is used (main.js loads the rest)", imported | {"main.js"} == set(MODULES) and 'src="main.js' in idx, sorted(set(MODULES) - imported))
    three = re.findall(r"from '([^']*three[^']*)'", "\n".join(files.values()))
    check("a. three.js only from ../jarvis/three.module.min.js, imported once (main.js)", three == ["../jarvis/three.module.min.js"]
          and "three.module.min.js" in files["main.js"], three)
    urls = set(re.findall(r"https?://[^\s'\"`)<>]+", every))
    check("a. the 3D runs on the OLYMPUS render core (createRenderer), no second WebGLRenderer; glass coins and gold from materials.js",
          "createRenderer" in files["scene.js"] and "WebGLRenderer" not in "\n".join(files.values()) and "../olympus/materials.js" in files["wheel.js"]
          and "glass(" in files["wheel.js"] and "metal(" in files["wheel.js"])
    check("a. no outside URL but the two feed endpoints", urls <= {RAW, API}, urls - {RAW, API})
    kal = read(os.path.join(WEB, "kalshi", "kalshi.js"))
    check("a. the same feed as the Kalshi page (raw, then the API)", f"'{RAW}'" in kal and f"'{API}'" in kal
          and f"RAW = '{RAW}'" in files["data.js"] and f"API = '{API}'" in files["data.js"])
    check("a. viewport-fit=cover, its own theme-color, dark color-scheme", 'viewport-fit=cover' in idx and f'name="theme-color" content="{THEME}"' in idx
          and 'name="color-scheme" content="dark"' in idx)
    check("a. safe areas on every edge, the orb's corner reserved, reduced motion in CSS and in the loop",
          all(f"safe-area-inset-{e}" in css for e in ("top", "right", "bottom", "left")) and "--orb-w: 96px" in css
          and "var(--orb-w)" in css and "prefers-reduced-motion: reduce" in css and "prefers-reduced-motion: reduce" in files["main.js"])
    check("a. no sideways scroll by construction (overflow hidden, max-width 100vw)", "overflow: hidden" in css and "max-width: 100vw" in css)
    check("a. read-only: no POST / PUT, no form, no Kalshi host", not re.search(r"method:\s*'(POST|PUT|DELETE)'", every) and "<form" not in idx
          and "kalshi.com" not in every.replace("kalshi-feed", ""))
    check("a. feed text never goes through innerHTML (textContent only)", "innerHTML" not in "\n".join(files.values()))
    check("a. Safari 16 safe: no regex lookbehind, no .at(), no Array copy methods, no Object.groupBy",
          not re.search(r"\(\?<[=!]|\.at\(|\.toSorted\(|\.toReversed\(|\.findLast\(|Object\.groupBy|AbortSignal\.timeout", "\n".join(files.values())))
    try:
        j = json.loads(jj)
    except ValueError as e:
        j = {"error": str(e)}
    texts = [j.get("name", ""), (j.get("status") or {}).get("label", "")] + list(j.get("lines") or [])
    check("a. jarvis.json by the Jarvis contract, with its theme", j.get("v") == 1 and 0 < len(j.get("name", "")) <= 40
          and (j.get("status") or {}).get("level") in ("ok", "warn", "bad", "off") and len(j["status"].get("label", "")) <= 48
          and len(j.get("kpis", [])) <= 3 and len(j.get("lines", [])) <= 3 and all(len(x) <= 120 for x in j.get("lines", []))
          and isinstance(j.get("t"), int) and j.get("theme") == THEME and re.fullmatch(r"#[0-9a-f]{6}", j["theme"])
          and len(jj.encode()) <= 8192 and not any(re.search(r"<[a-z/]|&[a-z]+;|\n", x) for x in texts), j)
    b = read(os.path.join(ROOT, "tools", "build_web_dashboard.py"))
    check("a. the site build publishes tyche/", bool(re.search(r'for app in \([^)]*"tyche"[^)]*\):', b)))
    sw = read(os.path.join(WEB, "sw.js"))
    m = re.search(r"const OTHER_APPS = \[([^\]]*)\]", sw)
    check("a. the root worker leaves tyche/ alone (OTHER_APPS)", bool(m) and "'tyche/'" in m.group(1), m and m.group(1))


# ------------------------------------------------------------------ b. the pure parts
def pure_checks(br, origin, now):
    ctx, p, log = new_page(br, origin, (390, 844))
    FEED["raw"] = FEED["api"] = None
    p.goto(origin + "/tyche/?demo=1")
    ready(p)
    v3, v2, v1 = fixture_v3(now), fixture_v2(now), fixture_v1(now)
    r = p.evaluate("""async ([v3, v2, v1, now]) => {
      const d = await import('./data.js'), f = await import('./fmt.js'), demo = await import('./demo.js');
      const m3 = d.normalize(v3, now), m2 = d.normalize(v2, now), m1 = d.normalize(v1, now);
      const junk = [d.normalize(null, now), d.normalize([], now), d.normalize('x', now)];
      let odd = null; try { odd = d.normalize({ t: 'x', positions: 'no', trades: [null, 5, {}], equity: [[1, 2], 'z'], kelly: 7, stats: [] }, now); } catch (e) { odd = 'threw ' + e; }
      const fake = (seq) => { let i = 0; return async () => { const s = seq[Math.min(i++, seq.length - 1)]; if (s === 'net') throw new TypeError('offline');
        return { ok: s === 200, status: s, json: async () => ({ t: now, balance: 1 }) }; }; };
      const f404 = new d.Feed(fake([404])), a = await f404.poll(), d1 = f404.delay(), b = await f404.poll(), d2 = f404.delay();
      const fApi = new d.Feed(fake([500, 200])), c = await fApi.poll();
      const fNet = new d.Feed(fake(['net', 'net'])), e = await fNet.poll();
      const dm = d.normalize(demo.demoFeed(now), now);
      return {
        m3: { bal: m3.balance, open: m3.open.length, win: m3.stats.winRate, roi: m3.stats.roi, src: m3.stats.src, next: m3.next.title, kelly: m3.kelly,
              said: m3.calibration.said, won: m3.calibration.won, basis: m3.calibration.basis, own: [m3.categories.own, m3.buckets.own, m3.calibration.own],
              noProb: m3.open.filter((o) => o.prob == null).map((o) => o.edge), edges: m3.open.map((o) => o.edge), eq: m3.equity.src, settled: m3.settled.length,
              alerts: m3.alerts.length, order: m3.order },
        m2: { win: m2.stats.winRate, src: m2.stats.src, eq: m2.equity.src, prob: m2.hasProb, cats: m2.categories.own, kb: m2.kelly.bankroll },
        m1: { win: m1.stats.winRate, roi: m1.stats.roi, src: m1.stats.src, eq: m1.equity.src, cats: m1.categories.rows.map((c) => c.name), bk: m1.buckets.rows.length,
              cal: [m1.calibration.basis, m1.calibration.n], kb: m1.kelly.bankroll, own: m1.kelly.own },
        junk, odd: typeof odd === 'string' ? odd : odd && { open: odd.open.length, settled: odd.settled.length, eq: odd.equity.pts.length, win: odd.stats.winRate },
        kelly: [d.kellyStake(0.6, 0.5, 0.25, { bankroll: 1000, maxBet: 25 }), d.kellyStake(0.55, 0.52, 0.25, { bankroll: 2400, maxBet: 120 }),
                d.kellyStake(0.4, 0.5, 1, { bankroll: 1000, maxBet: 25 }), d.kellyStake(null, 0.5, 1, { bankroll: 1000 })],
        feed: [a.state, d1, b.state, d2, f404.requests, c.state, fApi.requests, e.state, fNet.requests, fNet.delay()],
        fmt: [f.usd(-3.1, true), f.usd(1234.5), f.usd(0, true), f.pct(0.6421), f.pct(0.083, true), f.cents(0.42), f.cents(0.968), f.edgeC(0.05),
              f.countdown(252), f.countdown(7500), f.countdown(3 * 86400 + 4 * 3600 + 5), f.countdown(-1)],
        demo: { open: dm.open.length, w: dm.stats.wins, l: dm.stats.losses, n: dm.stats.trades, cats: dm.categories.rows.length, bk: dm.buckets.rows.length,
                cal: dm.calibration.n, settled: dm.settled.length, prob: dm.hasProb, closes: dm.open.every((o) => o.left > 0), eq: dm.equity.src },
      };
    }""", [v3, v2, v1, now])
    st = v3["stats"]
    cal = v3["calibration"]
    said = sum(c["p"] * c["n"] for c in cal) / sum(c["n"] for c in cal)
    won = sum(c["hit"] * c["n"] for c in cal) / sum(c["n"] for c in cal)
    m3 = r["m3"]
    check("b. normalize v3: balance, open bets, win rate and ROI from the bot's stats, the soonest settlement, Kelly settings",
          m3["bal"] == 2481.37 and m3["open"] == 6 and abs(m3["win"] - st["wins"] / (st["wins"] + st["losses"])) < 1e-9
          and abs(m3["roi"] - st["pnl"] / st["staked"]) < 1e-9 and m3["src"] == "bot" and m3["next"] == "NYC high 58-59°F today"
          and m3["kelly"] == {"fraction": 0.25, "own": True, "bankroll": 2400, "maxBet": 120, "minEdge": 0.03}, m3)
    check("b. normalize v3: calibration weighed by n (said / won), the bot's own lists used, edge = prob - price, none without prob",
          abs(m3["said"] - said) < 1e-9 and abs(m3["won"] - won) < 1e-9 and m3["basis"] == "model" and m3["own"] == [True, True, True]
          and m3["noProb"] == [None] and abs(m3["edges"][0] - (0.95 - 0.91)) < 1e-9 and m3["eq"] == "equity" and m3["settled"] == 14
          and m3["alerts"] == 1 and m3["order"][:2] == ["Weather", "Bitcoin"], m3)
    check("b. normalize v2: win rate from the strategies' W/L, equity from the feed, no prob, Kelly on the balance",
          abs(r["m2"]["win"] - 34 / 53) < 1e-9 and r["m2"]["src"] == "strategies" and r["m2"]["eq"] == "equity" and r["m2"]["prob"] is False
          and r["m2"]["cats"] is False and r["m2"]["kb"] == 512.34, r["m2"])
    check("b. normalize v1: win rate / ROI / categories / buckets / calibration worked out from the trades, equity from the days",
          r["m1"]["win"] == 0.5 and abs(r["m1"]["roi"] - 2.8 / 7.2) < 1e-9 and r["m1"]["src"] == "trades" and r["m1"]["eq"] == "days"
          and r["m1"]["cats"] == ["Other"] and r["m1"]["bk"] == 2 and r["m1"]["cal"] == ["price", 2] and r["m1"]["kb"] == 512.34 and r["m1"]["own"] is False, r["m1"])
    check("b. junk in: null for a non-object, never a throw on odd fields", r["junk"] == [None, None, None] and isinstance(r["odd"], dict)
          and r["odd"]["open"] == 0 and r["odd"]["settled"] == 0, r["odd"])
    k = r["kelly"]
    check("b. Kelly: (p - c) / (1 - c) x fraction x bankroll, capped at the max bet; no edge = no bet; no chance = no number",
          abs(k[0]["f"] - 0.2) < 1e-9 and k[0]["stake"] == 25 and k[0]["capped"] is True and abs(k[0]["raw"] - 50) < 1e-9
          and abs(k[1]["stake"] - 0.0625 * 0.25 * 2400) < 1e-9 and k[1]["capped"] is False
          and k[2]["stake"] == 0 and k[2]["f"] < 0 and k[3]["stake"] is None, k)
    check("b. the Feed: a 404 = unlinked, one request, 10 then 20 min backoff; raw failing -> the API; offline -> error, 2 min",
          r["feed"] == ["unlinked", 600000, "unlinked", 1200000, 2, "ok", 2, "error", 2, 120000], r["feed"])
    check("b. formats: money to the cent with a real minus, percents, cents, edge, countdowns",
          r["fmt"] == [f"{MINUS}$3.10", "$1,234.50", "$0.00", "64.2%", "+8.3%", "42¢", "96.8¢", "+5.0¢", "4m 12s", "2h 05m", "3d 4h", "settling"], r["fmt"])
    dm = r["demo"]
    check("b. the demo feed: a full v3 account (open bets settling later, every total over the same bets)",
          dm["open"] == 13 and dm["w"] + dm["l"] == dm["n"] and dm["n"] > 300 and dm["cats"] >= 6 and dm["bk"] >= 6 and dm["cal"] == dm["n"]
          and dm["settled"] == 40 and dm["prob"] and dm["closes"] and dm["eq"] == "equity", dm)
    errs = real_errors(log)
    ctx.close()
    return errs


# ------------------------------------------------------------------ c. not linked yet (404)
def unlinked_checks(br, origin, vw):
    tag = f"{vw[0]}x{vw[1]}"
    FEED.update(raw=None, api=None, calls=[])
    ctx, p, log = new_page(br, origin, vw)
    p.goto(origin + "/tyche/")
    ready(p)
    p.wait_for_timeout(4000)
    h, m = hud(p), p.evaluate("""() => { const m = window.tyche.model; return { open: m.open.length, bal: m.balance, today: m.today, week: m.week,
      win: m.stats.winRate, roi: m.stats.roi, next: m.next && m.next.title, coins: window.tyche.coins, req: window.tyche.requests }; }""")
    check(f"c. {tag}: a 404 = ONE request per load (raw only, no API retry, no poll), backed off", FEED["calls"] == ["raw"] and m["req"] == 1, FEED["calls"])
    check(f"c. {tag}: the chip says 'Not linked yet: demo'", h["_mode"] == "unlinked" and h["_chip"] == "Not linked yet: demo", h["_chip"])
    want = {"h-balance": usd(m["bal"]), "h-today": usd(m["today"], True), "h-week": usd(m["week"], True), "h-open": str(m["open"]),
            "h-win": pct(m["win"]), "h-roi": pct(m["roi"], True), "h-next-title": m["next"]}
    check(f"c. {tag}: the HUD shows the demo's numbers, a coin per open bet", all(h[k] == v for k, v in want.items()) and m["coins"] == m["open"] == 13,
          {k: (h[k], v) for k, v in want.items() if h[k] != v})
    for v in ("wheel", "pools", "scales"):
        p.evaluate(f"window.tyche.setView('{v}')")
        p.wait_for_timeout(1200)
        bad = orb_free(p)
        check(f"c. {tag} {v}: no sideways scroll, the orb's corner free", no_sideways(p) and not bad, bad)
        shot(p, f"demo-unlinked-{v}-{tag}")
    errs = real_errors(log)
    check(f"c. {tag}: no console errors in the demo", not errs, errs)
    ctx.close()


# ------------------------------------------------------------------ d. a v3 feed
def _lit_share(png: bytes, box) -> float:
    """The share of pixels in box (x0, y0, x1, y1) that are not near-black: the 3D scene is really drawn (a NaN in the bloom, or a lost
    context, turns the whole canvas black)."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("L").crop(box)
    px = list(im.getdata())
    return sum(1 for v in px if v > 22) / max(1, len(px))


def _bank_checks(p, tag, j):
    """The Bank view (2026-11-03): the bankroll curve + the risk of ruin, from the bot's own settled bets."""
    p.locator(".tabs button[data-view=bank]").click()
    p.wait_for_timeout(700)
    b = p.evaluate("""() => { const t = window.tyche, g = (i) => document.getElementById(i).textContent;
      return { view: t.view, hash: location.hash, sim: t.bank && { ok: t.bank.ok, ruin: t.bank.ruin, half: t.bank.half, fan: t.bank.fan.length, sizes: t.bank.sizes.map((s) => s.ruin),
        n: t.bank.n }, ruin: g('bk-ruin'), half: g('bk-half'), med: g('bk-med'), text: g('bk-text'), size: g('bk-size'),
        paths: document.querySelectorAll('#bk-svg path').length, vis: !document.getElementById('p-bank').hidden }; }""")
    sim = b["sim"] or {}
    check(f"g. {tag}: the Bank tab shows the bankroll curve and the odds ({b['ruin']} ruin, {b['half']} lose half, median {b['med']})",
          b["view"] == "bank" and b["hash"] == "#bank" and b["vis"] and sim.get("ok") and b["paths"] >= 3 and "replayed" in b["text"]
          and "Risk of ruin if every stake were" in b["size"] and b["ruin"] not in ("–", "") and b["med"].startswith("$"), b)
    check(f"g. {tag}: the odds are numbers between 0 and 1, ruin <= lose-half, doubling every stake never lowers the risk (x2 >= x1/2)",
          0 <= sim["ruin"] <= sim["half"] <= 1 and len(sim["sizes"]) == 3 and sim["sizes"][2] >= sim["sizes"][0] and sim["fan"] >= 10, sim)
    check(f"g. {tag}: the Bank panel stays clear of the orb corner, no sideways scroll", not orb_free(p) and no_sideways(p), orb_free(p))
    again = p.evaluate("""async () => { const m = await import('./bankroll.js'); const model = window.tyche.model; const a = m.simulate(model), b = m.simulate(model);
      const few = m.simulate({ settled: model.settled.slice(0, 3), balance: 1000 });
      const mk = (r) => ({ balance: 1000, settled: Array.from({ length: 20 }, (_, i) => ({ pnl: r * 100, staked: 100, t: i })) });
      const up = m.simulate(mk(0.5)), down = m.simulate(mk(-0.9));
      return { same: JSON.stringify(a) === JSON.stringify(b), few: few.ok, up: [up.ruin, up.half, up.p50 > 1000], down: [down.ruin, down.half] }; }""")
    check(f"g. {tag}: the simulation is seeded (the same feed, the same odds), refuses under 8 bets, a winning book has no ruin, a losing one has it",
          again["same"] and again["few"] is False and again["up"] == [0, 0, True] and again["down"][0] > 0.9, again)
    passes = p.evaluate("window.tyche.passes")
    check(f"g. {tag}: the 3D runs on the render core: passes {passes} (scene + bloom + finish on HD, scene + finish on LITE)",
          passes in (["scene", "bloom", "finish"], ["scene", "finish"]), passes)
    if tag == "390x844":
        p.locator(".tabs button[data-view=wheel]").click()
        p.wait_for_timeout(2500)
        wp = p.evaluate("window.tyche.wheelAt()")
        p.mouse.click(wp["x"], wp["y"])
        p.wait_for_timeout(300)
        w1 = p.evaluate("window.tyche.spin")
        p.wait_for_timeout(2500)
        w2 = p.evaluate("window.tyche.spin")
        check(f"g. {tag}: a tap on the wheel spins it and it eases out (visual only): {w1:.1f} -> {w2:.1f} rad/s, no coin selected",
              w1 > 3 and 0 <= w2 < w1 and p.evaluate("document.getElementById('sheet').hidden"), (w1, w2))
        lit = _lit_share(p.screenshot(), (0, 400, 780, 1180))
        check(f"g. {tag}: the wheel is really drawn: {lit * 100:.0f}% of the middle of the screen is lit (not black)", lit > 0.08, lit)
        p.locator(".tabs button[data-view=scales]").click()


def v3_checks(br, origin, vw):
    tag = f"{vw[0]}x{vw[1]}"
    now = int(time.time())
    j = fixture_v3(now)
    FEED.update(raw=(200, j), api=None, calls=[])
    ctx, p, log = new_page(br, origin, vw)
    p.goto(origin + "/tyche/#wheel")
    ready(p)
    p.wait_for_timeout(800)
    h, want = hud(p), expected(j, now)
    check(f"d. {tag}: v3 feed -> LIVE", h["_mode"] == "live" and h["_chip"] == "LIVE" and FEED["calls"] == ["raw"], (h["_chip"], FEED["calls"]))
    diff = {k: (h[k], v) for k, v in want.items() if not k.startswith("_") and h[k] != v}
    check(f"d. {tag}: every HUD number = the fixture's (balance, today, week, open, win rate, ROI, next)", not diff and h["_signs"] == list(want["_signs"]), (diff, h["_signs"]))
    left = cd_seconds(h["h-next-cd"])
    check(f"d. {tag}: the next settlement counts down (about 4m 40s)", left is not None and 200 < left <= 280, h["h-next-cd"])
    coins = p.evaluate("window.tyche.coins")
    check(f"d. {tag}: one coin per open bet", coins == len(j["positions"]) == 6, coins)
    # the Kelly slider: S&P 500 'no' at 52¢, the bot's chance 55% -> full Kelly 6.25% of the 2,400 bankroll, capped at 120
    key = "KXINXU-26NOV03-B5950#2"
    stakes = []
    for i, name in enumerate(["¼", "½", "Full"]):
        p.locator("#kelly").fill(str(i))
        p.wait_for_timeout(150)
        stakes.append((p.evaluate(f"window.tyche.kellyStake('{key}')"), p.locator("#k-frac").text_content(), p.locator("#k-sum").text_content()))
    ok = (abs(stakes[0][0] - 37.5) < 1e-6 and abs(stakes[1][0] - 75) < 1e-6 and stakes[2][0] == 120 and [s[1] for s in stakes] == ["¼", "½", "Full"]
          and "on 5 bets" in stakes[0][2] and "at the $120.00 max" in stakes[2][2])
    check(f"d. {tag}: the Kelly slider sizes each coin's halo (¼ $37.50, ½ $75, full capped at the $120 max bet)", ok, stakes)
    # the slider's focus ring (tyche.css #kelly:focus { none } / :focus-visible { gold }): the keyboard shows the 2 px gold ring
    # (iOS Safari never matches :focus-visible on a tap; desktop Chromium does for a range input, so a tap is not asserted);
    # the slider is a 44 px tap target (OLYMPUS)
    p.evaluate("document.activeElement && document.activeElement.blur()")
    p.keyboard.press("Tab")
    for _ in range(12):
        if p.evaluate("document.activeElement && document.activeElement.id") == "kelly":
            break
        p.keyboard.press("Tab")
    ring = p.evaluate("""(() => { const s = getComputedStyle(document.getElementById('kelly'));
      return [document.activeElement.id, s.outlineStyle, s.outlineWidth, s.outlineColor, document.getElementById('kelly').getBoundingClientRect().height]; })()""")
    check(f"d. {tag}: the Kelly slider: the gold focus ring from the keyboard, a 44 px tap target",
          ring[0] == "kelly" and ring[1] == "solid" and ring[2] == "2px" and "255, 207, 90" in ring[3] and ring[4] >= 44, ring)
    p.locator("#kelly").fill("2")                         # back to full Kelly, as the loop above left it
    p.evaluate("document.activeElement && document.activeElement.blur()")
    shot(p, f"v3-wheel-{tag}")
    p.locator(".tabs button[data-view=pools]").click()
    p.wait_for_timeout(600)
    st = j["stats"]
    pools = p.evaluate("['pl-w', 'pl-l', 'pl-tot'].map((i) => document.getElementById(i).textContent)")
    check(f"d. {tag}: Pools: wins, losses and the all-time P&L", pools == [str(st["wins"]), str(st["losses"]), usd(j["total_pnl"], True)]
          and p.evaluate("window.tyche.view") == "pools" and p.evaluate("location.hash") == "#pools", pools)
    shot(p, f"v3-pools-{tag}")
    p.locator(".tabs button[data-view=scales]").click()
    p.wait_for_timeout(600)
    cal = j["calibration"]
    n = sum(c["n"] for c in cal)
    said, won = sum(c["p"] * c["n"] for c in cal) / n, sum(c["hit"] * c["n"] for c in cal) / n
    sc = p.evaluate("['sc-said', 'sc-won', 'sc-gap', 'sc-best'].map((i) => document.getElementById(i).textContent)")
    gap = (won - said) * 100
    check(f"d. {tag}: Scales: said / won / the gap, the best and worst price bucket",
          sc[0] == pct(said) and sc[1] == pct(won) and sc[2] == f"{'+' if gap >= 0 else MINUS}{abs(gap):.1f} pts"
          and "Best 20–40¢ +28.4%" in sc[3] and "worst 90–95¢ " + MINUS + "4.1%" in sc[3], sc)
    bad = orb_free(p)
    check(f"d. {tag}: no sideways scroll, the orb's corner free (v3)", no_sideways(p) and not bad, bad)
    lk = p.evaluate("""() => { const a = document.getElementById('to-kalshi'), r = a.getBoundingClientRect(), s = getComputedStyle(document.documentElement);
        window.applyTheme({ accent: '#ff00aa', text: 'x;y' }); const g = s.getPropertyValue('--gold').trim(), t = s.getPropertyValue('--text').trim();
        window.applyTheme(null); return [a.getAttribute('href'), Math.round(r.height), g, t, s.getPropertyValue('--gold').trim(), window.tyche.intro]; }""")
    check(f"d. {tag}: the link to the Kalshi page (44 px), applyTheme (hex only, null = Tyche's gold), the intro camera move done",
          lk[0] == "../kalshi/" and lk[1] >= 44 and lk[2] == "#ff00aa" and lk[3] == "#fff8e8" and lk[4] == "#ffcf5a" and lk[5] == 1, lk)
    shot(p, f"v3-scales-{tag}")
    _bank_checks(p, tag, j)
    errs = real_errors(log)
    check(f"d. {tag}: no console errors with the v3 feed", not errs, errs)
    ctx.close()


def tap_checks(br, origin):
    """Reduced motion (the coins hold still): a tap on a coin opens its sheet; the countdown keeps running."""
    now = int(time.time())
    j = fixture_v3(now)
    FEED.update(raw=(200, j), api=None, calls=[])
    ctx, p, log = new_page(br, origin, (390, 844), reduced=True)
    p.goto(origin + "/tyche/#wheel")
    ready(p)
    p.wait_for_timeout(1200)
    key = "KXCPI-26NOV-T0.2#3"
    at = p.evaluate(f"window.tyche.coinAt('{key}')")
    p.mouse.click(at["x"], at["y"])
    p.wait_for_timeout(400)
    sheet = p.evaluate("""() => ({ open: !document.getElementById('sheet').hidden, title: document.getElementById('s-title').textContent,
      rows: [...document.querySelectorAll('#s-rows dd')].map((e) => e.textContent), cd: document.getElementById('s-cd').textContent,
      panel: document.getElementById('p-wheel').hidden })""")
    # CPI: 40 @ 33¢ = $13.20; 35¢ now; chance 41%; edge +6.0¢; ¼ Kelly of 2,400: (0.41-0.35)/0.65 x 0.25 x 2400 = $55.38
    check("e. reduced motion: tapping a coin opens its numbers (stake, price, chance, edge, ¼ Kelly, open P&L, countdown)",
          sheet["open"] and sheet["title"] == "CPI m/m 0.2% or less" and sheet["panel"]
          and sheet["rows"] == ["$13.20 · 40 @ 33¢", "35¢", "41.0%", "+6.0¢", "$55.38", "+$0.80"] and sheet["cd"] in ("3d 0h", "2d 23h"), sheet)
    shot(p, "v3-coin-sheet-390x844")
    p.locator("#s-close").click()
    p.wait_for_timeout(200)
    check("e. reduced motion: the sheet closes, the Kelly panel is back; no errors", p.evaluate("document.getElementById('sheet').hidden && !document.getElementById('p-wheel').hidden")
          and not real_errors(log), real_errors(log))
    ctx.close()


# ------------------------------------------------------------------ e. older feeds and the other states
def state_checks(br, origin):
    now = int(time.time())
    for name, j in (("v2", fixture_v2(now)), ("v1", fixture_v1(now))):
        FEED.update(raw=(200, j), api=None, calls=[])
        ctx, p, log = new_page(br, origin, (390, 844))
        p.goto(origin + "/tyche/")
        ready(p)
        p.wait_for_timeout(600)
        h, want = hud(p), expected(j, now)
        diff = {k: (h[k], v) for k, v in want.items() if not k.startswith("_") and h[k] != v}
        ks = p.locator("#k-sum").text_content()
        for v in ("pools", "scales"):
            p.evaluate(f"window.tyche.setView('{v}')")
            p.wait_for_timeout(500)
        check(f"e. a {name} feed (no v3 fields) still renders: LIVE (paper), the HUD = its numbers, a coin, Kelly asks for prob, no errors",
              h["_mode"] == "live" and not diff and p.evaluate("window.tyche.coins") == 1 and "needs the bot's own chance" in ks and not real_errors(log),
              (h["_chip"], diff, ks, real_errors(log)))
        shot(p, f"{name}-scales-390x844")
        ctx.close()
    # stale: an hour old
    FEED.update(raw=(200, fixture_v3(now, age=3600)), api=None, calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/tyche/")
    ready(p)
    h = hud(p)
    check("e. a feed an hour old: LAST SEEN 1 H AGO, the bot's numbers kept", h["_mode"] == "stale" and h["_chip"] == "LAST SEEN 1 H AGO" and h["h-balance"] == "$2,481.37", h)
    ctx.close()
    # raw failing -> the API
    FEED.update(raw=(500, {"message": "boom"}), api=(200, fixture_v3(now)), calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/tyche/")
    ready(p)
    check("e. raw failing (500) -> the GitHub API, LIVE", FEED["calls"] == ["raw", "api"] and hud(p)["_mode"] == "live", FEED["calls"])
    ctx.close()
    # nothing reachable -> the demo, said so
    FEED.update(raw="abort", api="abort", calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/tyche/")
    ready(p)
    h = hud(p)
    check("e. nothing reachable: 'Offline: demo', no page errors", h["_mode"] == "offline" and h["_chip"] == "Offline: demo" and not log["errors"], (h["_chip"], log["errors"]))
    ctx.close()
    # ?demo=1: no request at all
    FEED.update(raw=None, api=None, calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/tyche/?demo=1")
    ready(p)
    p.wait_for_timeout(1500)
    h = hud(p)
    check("e. ?demo=1: the DEMO chip and no request to the feed", h["_chip"] == "DEMO" and FEED["calls"] == [] and not real_errors(log), (h["_chip"], FEED["calls"]))
    ctx.close()
    # inside Jarvis: the live card
    FEED.update(raw=(200, fixture_v3(now)), api=None, calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/frame.html")
    p.wait_for_function("window.__cards.length > 0", timeout=30000)
    card = p.evaluate("window.__cards[window.__cards.length - 1].card")
    check("e. inside Jarvis: the card posted to the parent (contract, theme, 3 KPIs = balance / today / win rate)",
          card["v"] == 1 and card["name"] == "Tyche" and card["theme"] == THEME and card["status"]["level"] == "ok"
          and [k["value"] for k in card["kpis"]] == ["$2,481.37", "+$46.82", "62.4%"] and card["lines"] == ["Next: NYC high 58-59°F today"]
          and isinstance(card["t"], int), card)
    ctx.close()


def fortune_checks(br, origin):
    """The Fortune view (2026-11-04): leaderboard, streak coins, today's fortune, two bankrolls, the session replay, and the effects library on the scene."""
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/tyche/?demo=1#fortune")
    ready(p)
    p.wait_for_timeout(600)
    check("g. fortune: the fifth tab, a panel with five sections, the wheel still turning behind it",
          p.locator(".tabs button[data-view=fortune]").count() == 1 and p.is_visible("#p-fortune") and p.locator("#f-seg button").count() == 5
          and p.evaluate("window.tyche.view") == "fortune" and p.evaluate("window.tyche.coins") > 0)
    r = p.evaluate("""async () => { const F = await import('./fortune.js'); const m = tyche.model; const b = F.leaderboard(m), s = F.streakCoins(m), f = F.fortune(m), c = F.compareBankrolls(m, 0.5), fr = F.replayFrames(m);
       const tot = m.settled.reduce((a, x) => a + x.pnl, 0);
       return { rows: b.rows.length, sum: b.rows.reduce((a, r) => a + r.pnl, 0), total: b.total, n: m.settled.length, tot, sorted: b.rows.every((r, i) => !i || b.rows[i - 1].pnl >= r.pnl),
         coins: s.coins.length, head: f.headline, lines: f.lines.length, note: f.note, endA: c.endA, bal: m.balance, fr: fr.length, half: c.b[c.b.length - 1].bal - c.b[0].bal, full: c.a[c.a.length - 1].bal - c.a[0].bal,
         empty: [F.leaderboard(null).rows.length, F.streakCoins({}).coins.length, F.fortune({ settled: [] }).headline, F.replayFrames(null).length, F.compareBankrolls({ settled: [] }).n] }; }""")
    check("g. fortune.js on the demo: the board adds up to the settled bets' money (or shows the top 6), best first; at most 12 coins; a fortune with a headline, lines and the honest note",
          r["total"] == r["n"] and (abs(r["sum"] - r["tot"]) < 0.01 or r["rows"] == 6) and r["sorted"] and r["coins"] == min(12, r["n"]) and r["head"] and r["lines"] >= 2 and "not a forecast" in r["note"], r)
    check("g. two bankrolls: the real one ends on the balance; the same bets at half the stake move half as much; the replay has a frame per bet plus the start",
          abs(r["endA"] - r["bal"]) < 0.02 and abs(r["half"] - r["full"] / 2) < 0.01 * max(1, r["n"]) and r["fr"] == r["n"] + 1, r)
    check("g. no data: every function answers (empty board, no coins, 'no settled bets yet', one start frame)", r["empty"][:2] == [0, 0] and "no settled bets" in r["empty"][2].lower() and r["empty"][3] == 1 and r["empty"][4] == 0, r["empty"])
    rows = p.locator("#f-body .lrow").count()
    check("g. Board: one row per strategy / market, with its money and its win count", rows == r["rows"] and rows >= 1 and "W" in p.locator("#f-body .lrow").first.inner_text(), rows)
    p.locator("#f-seg button[data-f=streak]").click()
    check("g. Streak: a coin per recent settled bet (gold = won, dark = lost)", p.locator("#f-body .coin").count() == r["coins"] and p.locator("#f-body .coin.win").count() + p.locator("#f-body .coin.loss").count() == r["coins"])
    p.locator("#f-seg button[data-f=fortune]").click()
    check("g. Fortune: the daily card shows the headline and says it is not a forecast", r["head"] in p.inner_text("#f-body") and "not a forecast" in p.inner_text("#f-body"), p.inner_text("#f-body")[:200])
    p.locator("#f-seg button[data-f=compare]").click()
    check("g. Compare: both bankrolls drawn (two lines), 'As it was' and 'Half stake' with their end and deepest drop",
          p.is_visible("#f-cmp") and p.locator("#f-cmp polyline").count() == 2 and "As it was" in p.inner_text("#f-body") and "Half stake" in p.inner_text("#f-body") and "deepest drop" in p.inner_text("#f-body"))
    p.locator("#f-seg button[data-f=replay]").click()
    check("g. Replay: the balance, the bet line and a slider with one stop per bet (and the comparison's svg goes back out of sight)", p.is_visible("#f-body .rbal") and not p.is_visible("#f-cmp")
          and p.evaluate("+document.querySelector('#f-body input[type=range]').max") == r["n"])
    p.locator("#f-body input[type=range]").fill("3")
    check("g. Replay: moving the slider shows that bet and the balance after it", "Bet 3 of" in p.inner_text("#f-body .rinfo"), p.inner_text("#f-body .rinfo"))
    p.locator("#f-body .rplay").click()
    try:
        p.wait_for_function("+document.querySelector('#f-body input[type=range]').value > 3", timeout=30000)
        ok = True
    except Exception:
        ok = False
    p.locator("#f-body .rplay").click()
    check("g. Replay: Play steps through the bets by itself, Pause stops it", ok and "Play" in p.locator("#f-body .rplay").inner_text())
    bad = orb_free(p)
    check("g. fortune view: no sideways scroll, the orb's corner free", no_sideways(p) and not bad, bad)
    try:
        p.wait_for_function("window.OLYMPUS_FX && OLYMPUS_FX.stats().byName.caustics >= 1", timeout=60000)
        fx_ok = True
    except Exception:
        fx_ok = False
    check("g. the effects library is on the scene: water-light caustics on the floor (and gold motes unless LITE), ceremonial ring on a wheel tap",
          fx_ok and p.evaluate("typeof OLYMPUS_FX.shockwave") == "function")
    p.evaluate("window.tyche.setView('pools')")
    check("g. another view hides the panel again", not p.is_visible("#p-fortune"))
    errs = real_errors(log)
    check("g. no console errors in the Fortune view", not errs, errs)
    ctx.close()


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    global SHOTS
    if "--shots" in argv and not SHOTS:
        SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-03", "tyche")
    static_checks()
    from playwright.sync_api import sync_playwright
    srv, origin = serve()
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            errs = pure_checks(br, origin, int(time.time()))
            check("b. no errors loading the modules", not errs, errs)
            for vw in ((390, 844), (844, 390)):
                unlinked_checks(br, origin, vw)
                v3_checks(br, origin, vw)
            tap_checks(br, origin)
            state_checks(br, origin)
            fortune_checks(br, origin)
            br.close()
    finally:
        srv.shutdown()
    check("f. across every case: no request outside the page's origin but the two feed endpoints", not OUTSIDE, OUTSIDE[:5])
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} checks passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
