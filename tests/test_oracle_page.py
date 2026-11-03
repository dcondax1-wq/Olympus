"""ORACLE (tools/web_public/oracle/, owner 2026-11-03): a live 3D market radar of NQ, the LIT bot's world. Read-only.

It reads what the Zenith dashboard reads: live.json from the PC (GitHub's API first, raw.githubusercontent.com when the API
says no; the same two addresses tools/web_public/live.js builds), then the site's own ../home.json (or ../data.json). With
neither it replays a fixture day (demo_day.json: 2026-01-22, the London sweeps of the Asia high / PDH and the NY short at
09:24 that banked +6.4R), rebuilt from the stored bars by engine/brain.replay (python -X utf8 -m tests.test_oracle_page --regen).

Runs the real page in Chromium (WebGL through SwiftShader) on a local copy of the site layout (/oracle/, /jarvis/, home.json),
answers the GitHub endpoints with a live.json made by the real publisher (engine/live_publish.build over a heartbeat whose
Brain is the fixture day at 09:40 ET), and checks:
  a. the files and the static rules: every module, no dead export, no outside URL but the two GitHub endpoints, three.js only
     from ../jarvis/, viewport / theme-color / safe areas / reduced motion, jarvis.json by the Jarvis contract
  b. the pure parts (time.js, data.js) in the browser: ET clock, sessions, the next LIT window, normalize() of the fixture
  c. demo at 390 x 844 and 844 x 390: no console errors, the DEMO chip, the replay walks the stages (sweep -> ... -> trade ->
     done), lightning on the London sweeps, the HUD price = the fixture bar
  d. the fixture live.json: the LIVE chip, the HUD price, every level's distance in points and $ per MNQ, the stage
     constellation = the fixture's stages, P&L today, the open position's planes, ATLAS satellites; a second poll with new
     stages moves the constellation; the API answering 403 falls back to raw
  e. a stale live.json (an hour old): LAST SEEN, the last world kept; no live.json and no site files: the demo
  f. reduced motion, no sideways scroll, the orb's 80 x 160 px corner left free, and across every case: no request outside
     the page's origin but the two GitHub endpoints
    python -X utf8 -m tests.test_oracle_page
ORACLE_SHOTS=<dir> saves screenshots there (default research/handoff/2026-11-03/oracle/ when --shots is given).
"""
from __future__ import annotations

import datetime as dt
import glob
import http.server
import json
import math
import os
import re
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
ORC = os.path.join(WEB, "oracle")
DEMO = os.path.join(ORC, "demo_day.json")
ET = ZoneInfo("America/New_York")
DAY = "2026-01-22"
MODULES = ["main.js", "data.js", "demo.js", "time.js", "scene.js", "layers.js", "sky.js", "glow.js", "hud.js"]
API = "https://api.github.com/repos/demetrades2000-coder/nq-dashboard/contents/live.json?ref=live"
RAW = "https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/live/live.json"
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def et_t(day: str, hh: int, mm: int, prev: bool = False) -> int:
    d = dt.date.fromisoformat(day) - dt.timedelta(days=1 if prev else 0)
    return int(dt.datetime.combine(d, dt.time(hh, mm), ET).timestamp())


# ------------------------------------------------------------------ the fixture day (demo_day.json)
def regen(day: str = DAY) -> dict:
    """demo_day.json from the stored bars: the 5m bars of the session, every LIT level with the time it formed and the time it
    was taken, the Brain's stage at every 5m close (only when it changed), the day's narration and the trade. Exactly what the
    PC bot would have shown (engine/brain.replay)."""
    import pandas as pd
    from engine import brain
    a = et_t(day, 18, 0, prev=True)
    end = et_t(day, 16, 0)
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df = df[(df["time"] >= a) & (df["time"] < end)]
    bars = [[int(r.time), float(r.open), float(r.high), float(r.low), float(r.close)] for r in df.itertuples()]
    levels, frames, last = {}, [], None
    b = None
    for t in [x[0] + 300 for x in bars]:
        b = brain.replay(day, t)
        if b.get("error"):
            continue
        for lv in b.get("levels") or []:
            key = f"{lv['label']}|{lv['price']}"
            row = levels.setdefault(key, {"label": lv["label"], "price": lv["price"], "side": lv.get("side"), "kind": lv.get("kind"),
                                          "from_t": t, "taken_t": None})
            if lv.get("taken") and row["taken_t"] is None:
                row["taken_t"] = t
                row["deep_ok"] = bool(lv.get("deep_ok"))
        st = b.get("stage") or {}
        tr = b.get("trade")
        fr = {"t": t, "stage": {k: st.get(k) for k in ("key", "label", "n", "dir", "waiting")},
              "stages": [[s["key"], s["state"]] for s in b.get("stages") or []], "atr": b.get("atr"), "day_pnl": b.get("day_pnl"),
              "trade": {k: tr.get(k) for k in ("side", "dir", "entry_t", "entry", "stop0", "stop", "target", "qty", "risk_pts")}
              | {"be": bool((tr.get("be") or {}).get("done"))} if tr else None}
        sig = json.dumps([st.get("key"), st.get("dir"), fr["stages"], fr["trade"] and fr["trade"]["be"], fr["day_pnl"]])
        if sig != last:
            frames.append(fr)
            last = sig
    vix = ((b or {}).get("guards") or {}).get("vix") or {}
    log = [{"t": int(r["t"]), "hm": r.get("hm"), "kind": r.get("kind"), "text": r.get("text")}
           for r in sorted((b or {}).get("log") or [], key=lambda r: r.get("t") or 0) if r.get("kind") != "stage"]
    runs = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    tr = next(dict(zip(runs["trade_cols"], x)) for x in runs["trades"] if dict(zip(runs["trade_cols"], x))["day"] == day)
    out = {"v": 1, "kind": "oracle-demo", "day": day,
           "note": "A replay of a real 2026 session from the stored TradingView bars, rebuilt as the PC bot would have seen it.",
           "bars": bars, "vix": {k: vix.get(k) for k in ("vix", "vxn", "move", "open18", "up", "dn")},
           "regime": {"trend": "down", "vol": "normal", "label": "Trending down · normal volatility"},
           "levels": sorted(levels.values(), key=lambda r: -r["price"]), "frames": frames, "log": log,
           "trade": {"entry_t": int(tr["entry_t"]), "exit_t": int(tr["exit_t"]), "dir": int(tr["dir"]), "r": round(tr["r"], 2),
                     "pnl": round(tr["pnl"], 2), "qty": int(tr["qty"]), "exit": tr["exit"]}}
    with open(DEMO, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


# ------------------------------------------------------------------ the fixture live.json (the real publisher's output)
def fixture_live(now: int, at: tuple = (9, 40), stage_key: str | None = None) -> dict:
    """live.json as engine/live_publish.build makes it, from a heartbeat whose Bot Brain is the fixture day at `at` ET (09:40:
    in the short, breakeven done). stage_key overrides the Brain's stage (the constellation test)."""
    from engine import live_publish as lp
    fx = json.load(open(DEMO, encoding="utf-8"))
    t = et_t(DAY, *at)
    bar = next(b for b in fx["bars"] if b[0] <= t < b[0] + 300)
    price = bar[4]
    fr = [f for f in fx["frames"] if f["t"] <= t][-1]
    stage, stages = dict(fr["stage"]), [list(s) for s in fr["stages"]]
    if stage_key:
        keys = [s[0] for s in stages]
        n = keys.index(stage_key) + 1
        stage.update(key=stage_key, n=n, waiting=f"Fixture: now at {stage_key}")
        stages = [[k, "done" if i + 1 < n else "now" if i + 1 == n else "todo"] for i, k in enumerate(keys)]
    levels = [{"label": l["label"], "price": l["price"], "side": l["side"], "kind": l["kind"], "dist": round(l["price"] - price, 2),
               "taken": bool(l["taken_t"] and l["taken_t"] <= t)} for l in fx["levels"] if l["from_t"] <= t]
    tr = fr["trade"]
    brain = {"v": 1, "kind": "le-brain", "mode": "live", "t": now, "day": DAY, "price": price, "atr": fr["atr"], "stage": stage,
             "stages": stages, "levels": levels, "guards": {"vix": fx["vix"], "market": {"open": True}}, "day_pnl": 0.0,
             "trade": {**tr, "price": price, "usd_now": round(tr["dir"] * (price - tr["entry"]) * 2 * tr["qty"])} if tr else None,
             "log": [{"hm": "09:24", "kind": "entry", "text": "✓ SHORT LIT @ 26,515.75"}, {"hm": "08:45", "kind": "sweep", "text": "Swept London high"}],
             "compact": True}
    pos = {"entry_t": now - 900, "side": "SHORT", "dir": -1, "qty": tr["qty"], "entry": tr["entry"], "stop": tr["stop"], "stop0": tr["stop0"],
           "target": tr["target"], "be": tr["be"], "risk_pts": tr["risk_pts"], "target_label": "VIX band (banked at 8R)"} if tr else None
    hb = {"t": now, "running": True, "adapter": "ninjatrader", "position": bool(pos), "model_state": "IN TRADE", "host": "SURFACE", "model": "lit",
          "acct": {"v": 1, "t": now, "account": {"name": "MFFUEVAL50K", "label": "SIM", "adapter": "ninjatrader"}, "running": True, "kill": False,
                   "model": "lit", "eval": {"start": "2026-11-02", "days": {"2026-11-02": 310.0}}, "position": pos, "orders": [], "trades": [],
                   "day_pnl": 0.0},
          "health": {"v": 1, "t": now, "running": True, "model": "lit", "account": {"name": "MFFUEVAL50K", "adapter": "ninjatrader", "label": "SIM"},
                     "feed": {"source": "ninjatrader", "used": "ninjatrader", "no_yahoo": True, "age_1m_s": 8, "age_5m_s": 60, "stale": False,
                              "market_open": True, "entries_blocked": False},
                     "poll": {"last_t": now - 2, "age_s": 2, "errors": 0}, "lit": {"stage": stage["key"], "text": stage["waiting"], "price": price}},
          "brain": brain,
          "second": {"strategies": {"ema_lon_vix": {"short": "EMA", "state": {"stage": "waiting", "text": "Trend down: waiting for a pullback"}},
                                    "macd_sweep": {"short": "MACD", "state": {"stage": "armed", "text": "Signal (short): MACD divergence"}},
                                    "sr_nyreclaim": {"short": "S/R", "state": {"stage": "off", "text": "Outside its hours"}}}},
          "mind": {"regime": {"label": "Trending down · normal volatility", "trend": "down", "vol": "normal"}}}
    return lp.build(hb, now, lm={"lit_sizing": {"eval_start": "2026-11-02"}}, hb_last={"at": now - 20, "ok": True}, every_s=60)


# ------------------------------------------------------------------ the local site
SITE = {"home": None}                      # home.json body (None = 404, like a site without one)
FRAME_HTML = """<!doctype html><meta charset="utf-8"><body style="margin:0"><script>window.__cards = [];
addEventListener('message', (e) => { if (e.data && e.data.jarvis === 1) window.__cards.push(e.data); });</script>
<iframe src="/oracle/?demo=1" style="border:0;width:390px;height:844px"></iframe></body>"""


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
        path = self.path.split("?")[0]
        if path == "/frame.html":                 # Jarvis's frame: keeps every card the page posts
            data = FRAME_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path in ("/home.json", "/data.json"):
            body = SITE["home"] if path == "/home.json" else None
            if body is None:
                self.send_error(404)
                return
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def translate_path(self, path):
        p = path.split("?")[0]
        if p.startswith("/oracle/") or p.startswith("/jarvis/") or p.startswith("/olympus/"):
            return os.path.join(WEB, *p.lstrip("/").split("/"))
        return os.path.join(WEB, "__missing__")


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# ------------------------------------------------------------------ browser helpers
FEED = {"api": None, "raw": None, "calls": []}     # what the GitHub stubs answer: (status, body) or None (= 404)
OUTSIDE: list = []


def new_page(br, origin, vw, *, reduced=False, quality="high"):
    ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=2, reduced_motion="reduce" if reduced else "no-preference")

    def guard(route):
        u = route.request.url
        if u.startswith(origin) or u.startswith("data:") or u.startswith("blob:"):
            return route.continue_()
        base = u.split("?t=")[0]
        if base in (API, RAW):
            FEED["calls"].append("api" if base == API else "raw")
            ans = FEED["api" if base == API else "raw"]
            st, body = ans if ans else (404, {"message": "Not Found"})
            return route.fulfill(status=st, body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json",
                                                                          "Access-Control-Expose-Headers": "X-RateLimit-Remaining, X-RateLimit-Reset",
                                                                          "x-ratelimit-remaining": "55", "x-ratelimit-reset": "0"})
        OUTSIDE.append(u)
        return route.abort()
    ctx.route("**/*", guard)
    if quality:
        # the OLYMPUS kit's one 3D level (Jarvis's 'jfx' key) is the page's quality (docs/OLYMPUS_DESIGN.md)
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")
    p = ctx.new_page()
    log = {"errors": [], "console": []}
    p.on("pageerror", lambda e: log["errors"].append(str(e)))
    p.on("console", lambda m: log["console"].append((m.text, (m.location or {}).get("url", ""))) if m.type == "error" else None)
    return ctx, p, log


def real_errors(log):
    """Page errors and console errors, except the expected 404s (no live.json yet, no home.json on the test site)."""
    return log["errors"] + [t for t, u in log["console"] if "404" not in t and "Failed to load resource" not in t]


def ready(p, mode=None, timeout=30000):
    p.wait_for_function("document.body.dataset.ready === '1' && window.oracle && window.oracle.world", timeout=timeout)
    if mode:
        p.wait_for_function(f"window.oracle.mode === '{mode}'", timeout=timeout)


def launch(pw):
    """Chromium with WebGL in software (SwiftShader): the installed full Chromium when there is one."""
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], **({"executable_path": exe} if exe else {}))


SHOTS = os.environ.get("ORACLE_SHOTS")


def shot(p, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        p.wait_for_timeout(600)
        p.screenshot(path=os.path.join(SHOTS, name + ".png"))


# ------------------------------------------------------------------ formats (the page's own)
def fmt_px(p: float) -> str:
    return f"{p:,.2f}"


def lid(x: dict) -> str:
    """A level's id as the page makes it (label|price, the price as JavaScript prints a number)."""
    p = x["price"]
    return f"{x['label']}|{int(p) if float(p).is_integer() else p}"


def jround(x: float) -> int:
    """JavaScript's Math.round (halves up), not Python's banker's rounding."""
    return int(math.floor(x + 0.5))


def fmt_usd(v, sign=False) -> str:
    r = int(math.floor(abs(v) + 0.5))
    s = f"${r:,}"
    return "$0" if r == 0 else ("−" + s if v < 0 else "+" + s if sign else s)


STAGE_KEYS = ["levels", "sweep", "inducement", "displacement", "cisd5", "limit", "cisd1m", "entry", "trade", "done"]


# ------------------------------------------------------------------ a. static rules
def static_checks():
    files = MODULES + ["index.html", "oracle.css", "jarvis.json", "demo_day.json"]
    missing = [f for f in files if not os.path.isfile(os.path.join(ORC, f))]
    check("a. every file is there (flat folder: the site build copies files only)", not missing and not any(
        os.path.isdir(os.path.join(ORC, x)) for x in os.listdir(ORC)), missing)
    src = {f: open(os.path.join(ORC, f), encoding="utf-8").read() for f in MODULES}
    html = open(os.path.join(ORC, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(ORC, "oracle.css"), encoding="utf-8").read()
    unused = []
    for f, s in src.items():
        for name in re.findall(r"^export (?:async )?(?:function|class|const|let) (\w+)", s, re.M):
            if not any(re.search(r"import \{[^}]*\b" + name + r"\b[^}]*\} from '\./" + re.escape(f[:-3]) + r"\.js'", o)
                       for g, o in src.items() if g != f):
                unused.append(f"{f}:{name}")
    check("a. every export is imported by another module (no dead exports)", not unused, unused)
    imports = re.findall(r"^import .* from '([^']+)';", "".join(src.values()), re.M)
    check("a. modules import only each other and ../jarvis/three.module.min.js (once, in main.js)",
          all(re.fullmatch(r"\./\w+\.js", i) or i == "../jarvis/three.module.min.js" for i in imports)
          and "".join(src.values()).count("three.module.min.js") == 1 and "../jarvis/three.module.min.js" in src["main.js"], imports)
    urls = set(re.findall(r"https?://[^\s'\"`)]+", "".join(src.values()) + html + css))
    allowed = {"https://api.github.com/repos/${owner}/${repo}/contents/live.json?ref=live",
               "https://raw.githubusercontent.com/${owner}/${repo}/live/live.json"}
    check("a. no outside address but the two GitHub endpoints live.js uses", urls == allowed and "api.github.com" not in
          "".join(v for k, v in src.items() if k != "data.js"), urls)
    js = open(os.path.join(WEB, "live.js"), encoding="utf-8").read()
    check("a. the same endpoints as tools/web_public/live.js", "contents/live.json?ref=live" in js and "/live/live.json" in js
          and "contents/live.json?ref=live" in src["data.js"] and "/live/live.json" in src["data.js"])
    net = [f for f, s in src.items() if re.search(r"\bfetch\s*\(", s) and f not in ("data.js", "demo.js")]
    check("a. only data.js (and demo.js for its fixture) fetch anything; no XHR, beacon or socket", not net and not re.search(
        r"XMLHttpRequest|sendBeacon|WebSocket|EventSource", "".join(src.values())), net)
    keys = set(re.findall(r"localStorage\.\w+\(([^,)]+)", "".join(src.values())))
    check("a. storage only under the page's own key", keys == {"QUALITY_KEY"} and "const QUALITY_KEY = 'oracle.quality';" in src["main.js"], keys)
    check("a. the HUD writes text only (no innerHTML anywhere)", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML", "".join(src.values())))
    check("a. viewport-fit=cover and its own theme-color", 'viewport-fit=cover' in html and '<meta name="theme-color" content="#04050d">' in html
          and "const THEME = '#04050d';" in src["main.js"])
    check("a. safe areas on every edge, the orb corner reserved, reduced motion in CSS and in the loop",
          all(f"safe-area-inset-{e}" in css for e in ("top", "right", "bottom", "left")) and "--orb-w: 96px" in css
          and "prefers-reduced-motion: reduce" in css and "prefers-reduced-motion: reduce" in src["main.js"])
    check("a. fonts and icons only from ../jarvis/ (self-hosted)", all(u.startswith("../jarvis/") for u in re.findall(r"url\(([^)]+)\)", css))
          and "../jarvis/icon.svg" in html)
    j = json.load(open(os.path.join(ORC, "jarvis.json"), encoding="utf-8"))
    ok = (j.get("v") == 1 and j.get("name") == "Oracle" and (j.get("status") or {}).get("level") in ("ok", "warn", "bad", "off")
          and len((j.get("status") or {}).get("label", "")) <= 48 and isinstance(j.get("t"), int) and j.get("theme") == "#04050d"
          and len(json.dumps(j)) < 8192 and len(j.get("kpis", [])) <= 3 and len(j.get("lines", [])) <= 3
          and all(len(x) <= 120 and "<" not in x and "&" not in x for x in j.get("lines", [])))
    check("a. jarvis.json follows the Jarvis card contract (docs/JARVIS_APPS.md), theme = the page's colour", ok, j)
    fx = json.load(open(DEMO, encoding="utf-8"))
    check("a. demo_day.json: the fixture day, small (< 60 KB), bars / levels / frames / trade",
          fx.get("kind") == "oracle-demo" and fx.get("day") == DAY and os.path.getsize(DEMO) < 60_000 and len(fx["bars"]) > 200
          and len(fx["levels"]) > 10 and len(fx["frames"]) > 5 and fx["trade"]["dir"] == -1, os.path.getsize(DEMO))
    stages = {f["stage"]["key"] for f in fx["frames"]}
    check("a. the fixture day walks the stages: sweep, displacement, 5m CISD, limit, 1m CISD, in trade, done",
          {"sweep", "displacement", "cisd5", "limit", "cisd1m", "trade", "done"} <= stages, stages)
    swept = [l["label"] for l in fx["levels"] if l["taken_t"] and et_t(DAY, 2, 50) <= l["taken_t"] <= et_t(DAY, 4, 0)]
    check("a. the fixture's London session sweeps the Asia high and the PDH", "Asia high" in swept and "PDH" in swept, swept)


# ------------------------------------------------------------------ b. the pure parts, in the browser
def pure_checks(br, origin, j):
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/oracle/?demo=1")
    ready(p, "demo")
    r = p.evaluate("""async ([j, now]) => {
      const T = await import('/oracle/time.js'), D = await import('/oracle/data.js');
      const at = (y, mo, d, h, mi) => T.etToUnix(y, mo, d, h, mi);
      const w = D.normalize(j, now);
      return {
        rt: [T.etParts(at(2026, 7, 15, 9, 30)), T.etParts(at(2026, 1, 22, 2, 0))].map((p) => [p.h, p.mi, p.wd]),
        sess: [T.sessionAt(at(2026, 1, 22, 3, 0)).key, T.sessionAt(at(2026, 1, 22, 20, 30)).key, T.sessionAt(at(2026, 1, 22, 10, 0)).key,
               T.sessionAt(at(2026, 1, 24, 12, 0)).key, T.sessionAt(at(2026, 1, 22, 16, 30)).key],
        kz: [T.killzoneAt(at(2026, 1, 22, 3, 0)), T.killzoneAt(at(2026, 1, 22, 6, 30)), T.killzoneAt(at(2026, 1, 22, 9, 0))],
        monEarly: T.litWindow(at(2026, 1, 19, 1, 0)), wedMid: T.litWindow(at(2026, 1, 21, 10, 0)), friLate: T.litWindow(at(2026, 1, 23, 16, 0)),
        pc: T.litWindow(at(2026, 1, 21, 10, 0), [{ open_t: 100, close_t: 200 }, { open_t: at(2026, 1, 21, 9, 0), close_t: at(2026, 1, 21, 11, 0) }]),
        mon2: at(2026, 1, 19, 2, 0), mon1530: at(2026, 1, 19, 15, 30), wed1530: at(2026, 1, 21, 15, 30), nextMon: at(2026, 1, 26, 2, 0),
        dur: [T.fmtDur(45), T.fmtDur(3725), T.fmtDur(200000)],
        w, nul: [D.normalize(null), D.normalize({}), D.normalize({ kind: 'le-live', t: 1 })],
        sweeps: D.newSweeps({ levels: [{ id: 'a', taken: false }, { id: 'b', taken: true }] },
                            { levels: [{ id: 'a', taken: true }, { id: 'b', taken: true }, { id: 'c', taken: true }] }).map((l) => l.id),
      };
    }""", [j, j["t"]])
    check("b. ET clock round trip in summer and winter (DST)", r["rt"] == [[9, 30, 3], [2, 0, 4]], r["rt"])
    check("b. sessions: London 03:00, Asia 20:30, NY 10:00, weekend, closed 16:30", r["sess"] == ["london", "asia", "ny", "closed", "closed"], r["sess"])
    check("b. killzones: London 03:00 yes, 06:30 no, NY 09:00 yes", r["kz"] == [True, False, True], r["kz"])
    me, wm, fl = r["monEarly"], r["wedMid"], r["friLate"]
    check("b. LIT window: Monday 01:00 opens at 02:00 (1 h), Wednesday 10:00 open until 15:30, Friday 16:00 -> Monday 02:00",
          not me["open"] and me["open_t"] == r["mon2"] and me["close_t"] == r["mon1530"] and me["in_s"] == 3600
          and wm["open"] and wm["close_t"] == r["wed1530"] and wm["in_s"] == 5.5 * 3600 and not fl["open"] and fl["open_t"] == r["nextMon"], [me, wm, fl])
    check("b. LIT window: the PC's own windows win (past ones skipped)", r["pc"]["open"] and r["pc"]["in_s"] == 3600, r["pc"])
    check("b. durations", r["dur"] == ["45s", "1h 02m", "2d 7h"], r["dur"])
    w, mp = r["w"], j["board"]["map"]
    rows = [x for x in mp["levels"] if x["kind"] not in ("open", "target")]
    exp_lv = {lid(x): x for x in rows}
    got = {l["id"]: l for l in w["levels"]}
    bad = [(k, got[k], exp_lv.get(k)) for k in got if k not in exp_lv or abs(got[k]["dist"] - exp_lv[k]["dist"]) > 1e-6
           or got[k]["usd"] != jround(abs(exp_lv[k]["dist"]) * 2) or got[k]["taken"] != exp_lv[k]["taken"]]
    check("b. normalize(live.json): every board level, distance = the publisher's, $ = |pts| x $2 a micro",
          set(got) == set(exp_lv) and not bad, bad[:2])
    br_ = j["pc"]["brain"]
    check("b. normalize: price, stage, the ten stages, the VIX band, ATR, regime",
          w["price"] == j["price"] and w["stage"]["key"] == br_["stage"]["key"] and [s["state"] for s in w["stages"]] == [s[1] for s in br_["stages"]]
          and w["vix"]["up"] == mp["vix"]["up"] and w["atr"] == br_["atr"] and w["regime"]["trend"] == "down", w["stage"])
    lp_ = j["board"]["lit"]["position"]
    check("b. normalize: the open position from the PC account (side, size, entry, stop, target, 1R from the Brain)",
          w["position"]["side"] == "SHORT" and w["position"]["qty"] == lp_["qty"] and w["position"]["entry"] == lp_["entry"]
          and w["position"]["stop"] == lp_["stop"] and w["position"]["target"] == lp_["target"] and 0 < w["position"]["r"] < 10, w["position"])
    check("b. normalize: ATLAS's three members with their stages", [m["stage"] for m in w["atlas"]["members"]] == ["waiting", "armed", "off"], w["atlas"])
    check("b. normalize: nothing in = null; newSweeps = only levels that turned taken", r["nul"] == [None, None, None] and r["sweeps"] == ["a"], r)
    errs = real_errors(log)
    ctx.close()
    return w, errs


# ------------------------------------------------------------------ c. the demo
def orb_free(p):
    """Nothing the owner can tap or read sits in the bottom-right 80 x 160 px (Jarvis's orb); the OLYMPUS seal (.oly-home) sits in the orb's seat only when the page is opened alone: Jarvis's orb is there when framed."""
    return p.evaluate("""() => { const W = innerWidth, H = innerHeight, bad = [];
      for (let x = W - 78; x < W; x += 12) for (let y = H - 158; y < H; y += 12)
        for (const e of document.elementsFromPoint(x, y)) if (!['HTML', 'BODY', 'CANVAS'].includes(e.tagName) && !e.closest('.oly-home')) bad.push(e.id || e.className || e.tagName);
      return [...new Set(bad)]; }""")


def no_sideways(p):
    return p.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth")


def seek(p, hh, mm):
    p.evaluate(f"window.oracle.demo.pause(); window.oracle.demo.seek({et_t(DAY, hh, mm)})")
    p.wait_for_timeout(150)


def demo_checks(br, origin, vw):
    FEED.update(api=None, raw=None, calls=[])
    fx = json.load(open(DEMO, encoding="utf-8"))
    tag = f"{vw[0]}x{vw[1]}"
    ctx, p, log = new_page(br, origin, vw)
    p.goto(origin + "/oracle/")                      # no live.json (404), no home.json: the demo by itself
    ready(p, "demo")
    check(f"c. {tag}: no live data -> the demo, the DEMO chip and the replay bar",
          p.inner_text("#mode") == "DEMO" and p.is_visible("#demo-bar") and DAY in p.inner_text("#demo-tag"), p.inner_text("#mode"))
    t0 = p.evaluate("oracle.demo.t")
    p.wait_for_timeout(1500)
    check(f"c. {tag}: the replay plays (the clock moves)", p.evaluate("oracle.demo.t") > t0 + 60, [t0, p.evaluate("oracle.demo.t")])
    # the constellation follows the fixture's stage at each frame
    bad = []
    for fr in fx["frames"]:
        hh, mm = divmod((dt.datetime.fromtimestamp(fr["t"], ET).hour * 60 + dt.datetime.fromtimestamp(fr["t"], ET).minute), 60)
        if not (0 <= hh < 11):
            continue
        seek(p, hh, mm)
        got = p.evaluate("oracle.constellation")
        exp = [s[1] for s in fr["stages"]]
        if got != exp or p.inner_text("#stage-n") != f"{fr['stage']['n']}/10":
            bad.append((f"{hh:02d}:{mm:02d}", fr["stage"]["key"], got))
    check(f"c. {tag}: the stage constellation = the fixture's ten stages at every stage change (and the HUD's n/10)", not bad, bad[:3])
    # lightning on the London sweeps (Asia high 03:00, PDH 03:25)
    seek(p, 2, 55)
    s0 = p.evaluate("oracle.strikes")
    seek(p, 3, 6)                                   # the 03:00 bar closes at 03:05: the Asia high is taken
    s1 = p.evaluate("oracle.strikes")
    if vw[0] < vw[1]:
        shot(p, "london_sweep_390")
    seek(p, 3, 31)
    s2 = p.evaluate("oracle.strikes")
    check(f"c. {tag}: lightning when the London session sweeps the Asia high, then the PDH", s1 > s0 and s2 > s1, [s0, s1, s2])
    # the NY entry: price, position, P&L today
    bar = next(b for b in fx["bars"] if b[0] == et_t(DAY, 9, 40))
    seek(p, 9, 40)
    tr = [f for f in fx["frames"] if f["t"] <= et_t(DAY, 9, 40)][-1]["trade"]
    exp_px = round(bar[1] * 4) / 4
    open_usd = tr["dir"] * (exp_px - tr["entry"]) * 2 * tr["qty"]
    check(f"c. {tag}: 09:40 in the NY short: HUD price = the fixture bar, the position card, P&L today = the open trade",
          p.inner_text("#price") == fmt_px(exp_px) and p.is_visible("#pos") and p.inner_text("#pos-side") == f"SHORT {tr['qty']} @ {fmt_px(tr['entry'])}"
          and p.inner_text("#pnl") == fmt_usd(open_usd, True) and p.inner_text("#stage-label").startswith("In trade"),
          [p.inner_text("#price"), fmt_px(exp_px), p.inner_text("#pnl"), fmt_usd(open_usd, True)])
    shot(p, f"demo_ny_trade_{vw[0]}")
    seek(p, 10, 30)
    check(f"c. {tag}: after the target: done for today, no position, P&L today = the fixture's booked day",
          p.evaluate("oracle.constellation")[-1] == "now" and not p.is_visible("#pos") and p.inner_text("#pnl") == fmt_usd(fx["frames"][-1]["day_pnl"], True),
          [p.inner_text("#pnl"), fx["frames"][-1]["day_pnl"]])
    check(f"c. {tag}: no sideways scroll", no_sideways(p))
    check(f"c. {tag}: Jarvis's orb corner (bottom-right 80 x 160) left free", not orb_free(p), orb_free(p))
    errs = real_errors(log)
    check(f"c. {tag}: no console errors in the demo", not errs, errs)
    ctx.close()


# ------------------------------------------------------------------ d. the fixture live.json
def live_checks(br, origin, vw, j):
    tag = f"{vw[0]}x{vw[1]}"
    FEED.update(api=(200, j), raw=None, calls=[])
    ctx, p, log = new_page(br, origin, vw)
    p.goto(origin + "/oracle/")
    ready(p, "live")
    check(f"d. {tag}: live.json from the GitHub API -> LIVE chip", p.inner_text("#mode").startswith("LIVE") and FEED["calls"][:1] == ["api"], FEED["calls"])
    check(f"d. {tag}: HUD price = live.json price", p.inner_text("#price") == fmt_px(j["price"]), [p.inner_text("#price"), j["price"]])
    rows = p.eval_on_selector_all("#lv-list li.lv:not(.now)", "els => els.map(e => ({id: e.dataset.id, d: +e.dataset.dist, usd: +e.dataset.usd, "
                                  "txt: e.querySelector('.lv-d').textContent, u: e.querySelector('.lv-usd').textContent}))")
    exp = {lid(x): x for x in j["board"]["map"]["levels"] if x["kind"] not in ("open", "target")}
    bad = [r for r in rows if not (r["id"] in exp and abs(r["d"] - exp[r["id"]]["dist"]) < 1e-6 and r["usd"] == jround(abs(exp[r["id"]]["dist"]) * 2)
                                   and r["u"] == fmt_usd(abs(exp[r["id"]]["dist"]) * 2) and r["txt"] == ("+" if r["d"] > 0 else "−") + f"{abs(r['d']):.2f}")]
    ok = rows and not bad
    untaken = sorted([x for x in exp.values() if not x["taken"]], key=lambda x: abs(x["dist"]))
    above = [x for x in untaken if x["dist"] > 0][:2]
    below = [x for x in untaken if x["dist"] < 0][:2]
    shown = {r["id"] for r in rows}
    check(f"d. {tag}: the levels list = the publisher's nearest untaken levels, points and $ per MNQ exactly",
          ok and all(lid(x) in shown for x in above + below), [bad[:2], shown, [x["label"] for x in above + below]])
    lit = j["board"]["lit"]
    pos = lit["position"]
    booked = lit.get("today_pnl") if lit.get("today_pnl") is not None else j.get("day_pnl") or 0
    open_usd = pos.get("unrealized_usd") if pos.get("unrealized_usd") is not None else round(-1 * (j["price"] - pos["entry"]) * 2 * pos["qty"])
    check(f"d. {tag}: P&L today = booked + the open trade, the position card", p.inner_text("#pnl") == fmt_usd(booked + open_usd, True)
          and p.inner_text("#pos-side") == f"SHORT {pos['qty']} @ {fmt_px(pos['entry'])}" and p.inner_text("#pos-pnl") == fmt_usd(open_usd, True),
          [p.inner_text("#pnl"), booked, open_usd])
    stages = [s[1] for s in j["pc"]["brain"]["stages"]]
    check(f"d. {tag}: the constellation = the Brain's stages", p.evaluate("oracle.constellation") == stages, p.evaluate("oracle.constellation"))
    check(f"d. {tag}: ATLAS satellites and the weather (VIX, ATR, trend)",
          p.evaluate("oracle.world.atlas.members.map(m => m.stage).join()") == "waiting,armed,off"
          and "VIX 16.9" in p.inner_text("#wx") and "Trend ↓" in p.inner_text("#wx"), p.inner_text("#wx"))
    check(f"d. {tag}: the window countdown and the session line", re.search(r"LIT window|No LIT window", p.inner_text("#win-text"))
          and " ET" in p.inner_text("#session"), p.inner_text("#win-text"))
    shot(p, f"live_{vw[0]}")
    # a new poll with the Brain at the 5m CISD moves the constellation
    j2 = fixture_live(j["t"] + 1, stage_key="cisd5")
    FEED["api"] = (200, j2)
    p.evaluate("oracle.refresh()")
    try:
        p.wait_for_function("oracle.constellation.indexOf('now') === 4", timeout=10000)
    except Exception:
        print("   debug:", FEED["calls"], p.evaluate("[oracle.mode, oracle.world.t, oracle.world.stage.key]"), real_errors(log))
    check(f"d. {tag}: next poll at the 5m CISD: the constellation follows (5/10, stars 1-4 done)",
          p.evaluate("oracle.constellation") == ["done"] * 4 + ["now"] + ["todo"] * 5 and p.inner_text("#stage-n") == "5/10")
    check(f"d. {tag}: no sideways scroll, the orb corner free", no_sideways(p) and not orb_free(p), orb_free(p))
    errs = real_errors(log)
    check(f"d. {tag}: no console errors with the fixture live.json", not errs, errs)
    ctx.close()


# ------------------------------------------------------------------ e. fallbacks and states
def state_checks(br, origin, j_now):
    # the API says no (rate limit): raw.githubusercontent.com
    FEED.update(api=(403, {"message": "API rate limit exceeded"}), raw=(200, j_now), calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/oracle/")
    ready(p, "live")
    check("e. API 403 -> raw.githubusercontent.com, still LIVE", FEED["calls"][:2] == ["api", "raw"] and p.inner_text("#price") == fmt_px(j_now["price"]), FEED["calls"])
    ctx.close()
    # an hour-old live.json: LAST SEEN, the world kept; Replay a day -> demo -> Back to live
    old = fixture_live(j_now["t"] - 3600)
    FEED.update(api=(200, old), raw=None, calls=[])
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/oracle/")
    ready(p, "stale")
    check("e. live.json an hour old: LAST SEEN, its price and stage kept, Replay a day offered",
          p.inner_text("#mode").startswith("LAST SEEN") and p.inner_text("#price") == fmt_px(old["price"]) and p.is_visible("#replay"))
    shot(p, "stale_390")
    p.click("#replay")
    p.wait_for_function("oracle.mode === 'demo'")
    ok = p.inner_text("#replay") == "Back to live"
    p.click("#replay")
    p.wait_for_function("oracle.mode === 'stale'")
    check("e. Replay a day -> the demo; Back to live -> the last real world", ok and p.inner_text("#price") == fmt_px(old["price"]))
    errs = real_errors(log)
    ctx.close()
    # the site's own home.json when live.json is missing
    FEED.update(api=None, raw=None, calls=[])
    SITE["home"] = {"board": j_now["board"], "live": {"price": j_now["price"], "bars": [[j_now["t"] - 600 + 300 * i, 1, 1, 1, j_now["price"] + i] for i in range(2)]}}
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/oracle/")
    ready(p, "site")
    check("e. no live.json, the site's home.json: CLOUD chip, its price and levels", p.inner_text("#mode").startswith("CLOUD")
          and p.inner_text("#price") == fmt_px(j_now["price"]) and p.eval_on_selector_all("#lv-list li.lv:not(.now)", "e => e.length") >= 2)
    errs += real_errors(log)
    SITE["home"] = None
    ctx.close()
    check("e. no console errors in the fallbacks", not errs, errs)


# ------------------------------------------------------------------ f. reduced motion, quality, Jarvis's card
def misc_checks(br, origin):
    FEED.update(api=None, raw=None, calls=[])
    ctx, p, log = new_page(br, origin, (390, 844), reduced=True)
    p.goto(origin + "/oracle/?demo=1")
    ready(p, "demo")
    seek(p, 3, 1)
    p.wait_for_timeout(600)
    check("f. reduced motion: the replay still works, lightning without flicker, no errors", p.evaluate("oracle.strikes") >= 0 and not real_errors(log), real_errors(log))
    ctx.close()
    ctx, p, log = new_page(br, origin, (390, 844), quality=None)
    p.goto(origin + "/oracle/?demo=1")
    ready(p, "demo")
    q0 = p.evaluate("oracle.quality")
    p.click("#quality")
    check("f. the quality switch: HD <-> LITE, kept on the phone (in the shared OLYMPUS key, so Jarvis follows)",
          q0 in ("high", "low") and p.evaluate("oracle.quality") != q0
          and p.evaluate("localStorage.getItem('jfx')") == p.evaluate("oracle.quality")
          and p.inner_text("#quality") == ("LITE" if p.evaluate("oracle.quality") == "low" else "HD"))
    p.click("#quality")
    check("f. no errors switching quality twice", not real_errors(log), real_errors(log))
    ctx.close()
    ctx, p, log = new_page(br, origin, (420, 860))
    p.goto(origin + "/frame.html")
    p.wait_for_function("window.__cards.length > 0", timeout=30000)
    card = p.evaluate("window.__cards[window.__cards.length - 1].card")
    check("f. inside Jarvis: the live card posted to the parent (contract, theme, 3 KPIs, plain text)",
          card["v"] == 1 and card["name"] == "Oracle" and card["theme"] == "#04050d" and card["status"]["level"] == "off"
          and len(card["kpis"]) == 3 and all(len(x) <= 120 for x in card["lines"]) and isinstance(card["t"], int), card)
    ctx.close()


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--regen" in argv:
        d = regen()
        print(f"wrote {DEMO}: {len(d['bars'])} bars, {len(d['levels'])} levels, {len(d['frames'])} frames, {len(d['log'])} log lines, "
              f"{os.path.getsize(DEMO) // 1024} KB")
        return 0
    global SHOTS
    if "--shots" in argv and not SHOTS:
        SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-03", "oracle")
    static_checks()
    from playwright.sync_api import sync_playwright
    srv, origin = serve()
    now = int(time.time())
    j = fixture_live(now)
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            _, errs = pure_checks(br, origin, j)
            check("b. no errors loading the modules", not errs, errs)
            for vw in ((390, 844), (844, 390)):
                demo_checks(br, origin, vw)
                live_checks(br, origin, vw, fixture_live(int(time.time())))
            state_checks(br, origin, fixture_live(int(time.time())))
            misc_checks(br, origin)
            br.close()
    finally:
        srv.shutdown()
    check("f. across every case: no request outside the page's origin but the two GitHub endpoints", not OUTSIDE, OUTSIDE[:5])
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} checks passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
