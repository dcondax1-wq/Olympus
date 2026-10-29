"""Deep space + Mission Control (2026-10-29, owner: "make it look cooler ... almost like 3D space"): the 3D background
(tools/web_public/fx/src/space.js in fx.js), the static CSS sky (space.css), Mission Control (missioncore.js, phone mission.js,
PC web_next/js/next/mission.js) and the Live View structure layer (liveviewchart.js), on both dashboards.

  a. static   byte-identical copies (space.css, mission.css, missioncore.js, liveviewchart.js, liveview.css), the bundle has the
              scene, pages load the files, caches bumped (phone le-public-v43+, PC le-shell-next-v25+), FEATURES.md lists it,
              read-only (no POST / no fetch in the renderer)
  b. node     MissionUI from 2 accounts (BLITZ placeholder "paper / not live yet") and 3 accounts (a third board block), the
              bot states for the satellites, closed trades for the shooting stars, never throws on garbage
  c. phone    Playwright 390x844 (+ 844x390 sideways): the scene mounts (WebGL2, SwiftShader), no page errors, frame time sane,
              Home strip + #/mission with 2 and 3 accounts, Live View with the structure layer, fallback when 3D is off and
              when WebGL is unavailable, one still frame with prefers-reduced-motion
  d. PC       Playwright 1440x900 on server.py (board + liveview patched to fixtures): the scene mounts, Mission Control
              renders 3 accounts, Live View draws the structure card, no page errors

  python -X utf8 -m tests.test_space_ui                 # ~2-3 min (browser parts skipped without playwright)
  python -X utf8 -m tests.test_space_ui --shots <dir>   # also saves the screenshots (phone portrait / landscape, PC)
  python -X utf8 -m tests.test_space_ui --no-browser    # a + b only
"""
from __future__ import annotations

import copy
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ fixtures
TKEYS = {"t", "t0", "t1", "entry_t", "exit_t", "expires_t", "armed_t", "ext_t", "taken_t", "open_t", "close_t", "data_t", "at_t", "ts", "set_t"}


def shift(obj, d):
    """Every unix time in a liveview / board block moved by d seconds (bars, [t, v] series and the *_t keys)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in TKEYS and isinstance(v, (int, float)) and 1.7e9 < v < 2.1e9:
                out[k] = int(v + d)
            elif k in ("bars", "bars5", "ema21", "ema50") and isinstance(v, list):
                out[k] = [[r[0] + d] + list(r[1:]) if isinstance(r, list) and r and isinstance(r[0], (int, float)) and r[0] > 1.7e9 else shift(r, d) for r in v]
            else:
                out[k] = shift(v, d)
        return out
    if isinstance(obj, list):
        return [shift(x, d) for x in obj]
    return obj


def structure_of(bars5):
    """A plausible market-structure block (the shape engine/liveview_api.view() gets from another change) from 5m bars."""
    rows = [b for b in bars5 if isinstance(b, list) and len(b) >= 5][-120:]
    sw, last = [], {"H": None, "L": None}
    for i in range(2, len(rows) - 2):
        h, lo = rows[i][2], rows[i][3]
        if h >= max(r[2] for r in rows[i - 2:i + 3]):
            k = "HH" if last["H"] is None or h > last["H"] else "LH"; last["H"] = h; sw.append({"t": rows[i][0], "price": h, "kind": k})
        if lo <= min(r[3] for r in rows[i - 2:i + 3]):
            k = "HL" if last["L"] is None or lo > last["L"] else "LL"; last["L"] = lo; sw.append({"t": rows[i][0], "price": lo, "kind": k})
    sw = sw[-14:]
    hi_s = [s for s in sw if s["kind"] in ("HH", "LH")] or [{"t": rows[-1][0], "price": rows[-1][2]}]
    lo_s = [s for s in sw if s["kind"] in ("HL", "LL")] or [{"t": rows[-1][0], "price": rows[-1][3]}]
    top, bot = max(s["price"] for s in hi_s), min(s["price"] for s in lo_s)
    eq = (top + bot) / 2
    px = rows[-1][4]
    ev = {"kind": "BOS", "dir": 1, "t": rows[-3][0], "price": hi_s[-1]["price"]}
    f15 = [s for i, s in enumerate(sw) if i % 2 == 0]
    return {"t": rows[-1][0], "summary": f"5m and 15m trend up (higher highs and higher lows); 1h range. Price {px:,.2f} is in "
                                         f"{'premium' if px > eq else 'discount'}: the last BOS was up at {ev['price']:,.2f}.",
            "frames": {"5m": {"trend": "up", "last_event": ev, "swings": sw, "protected": {"high": top, "low": lo_s[-1]["price"]}},
                       "15m": {"trend": "up", "last_event": {**ev, "kind": "CHoCH", "t": rows[-12][0]}, "swings": f15, "protected": {"high": top, "low": bot}},
                       "1h": {"trend": "range", "last_event": None, "swings": f15[-3:], "protected": {"high": top + 20, "low": bot - 20}}},
            "pools": [{"price": top + 6, "side": "buy", "label": "equal highs", "t0": hi_s[0]["t"], "swept": False},
                      {"price": bot - 5, "side": "sell", "label": "Asia low", "t0": lo_s[0]["t"], "swept": False},
                      {"price": (top + eq) / 2, "side": "buy", "label": "London high", "t0": rows[10][0], "swept": True}],
            "zone": {"lo": bot, "hi": top, "eq": eq, "premium": px > eq},
            "per_strategy": {"lit": {"note": "sweep of the buy side wanted for a short"}}}


def boards(now):
    """(two-account board, three-account board) from the live-board fixture at `now`, with an open Zlarior trade."""
    from tests import test_live_board as TB
    b = TB.board_of(TB.hb_fixture(now), now=now)
    b = json.loads(json.dumps(b, default=str))
    b["lit"]["position"] = {"side": "LONG", "dir": 1, "qty": 5, "entry": 25000.0, "stop": 24955.0, "target": 25360.0, "entry_t": now - 1500,
                            "unrealized_usd": 212.5, "risk_usd": 450.0, "target_usd": 3600.0}
    b["lit"]["today_pnl"] = 212.5
    b["trades"] = [{"acct": "lit", "src": "live", "day": "2026-10-28", "entry_t": now - 9000, "exit_t": now - 7000, "side": "SHORT", "qty": 4, "entry": 25100.0,
                    "stop": 25140.0, "target": 24900.0, "exit_px": 24900.0, "exit": "TARGET", "r": 5.0, "usd": 800.0, "open": False}] + (b.get("trades") or [])
    b3 = copy.deepcopy(b)
    bl = copy.deepcopy(b["atlas"])
    bl.update({"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "method": "scalper", "broker": "MFFU 25K eval (BLITZ)", "balance": 25120.0, "room": 1120.0,
               "to_target": 1380.0, "profit": 120.0, "today_pnl": 120.0, "session": 2, "members": [], "blocks": [], "configured": True, "source": "PC bot (BLITZ)",
               "waiting": "Watching the 09:30 noise band", "position": None})
    b3["blitz"] = bl
    return b, b3


def liveview(now):
    from engine import liveview_api as L, narrator as N
    from tests import test_phone_liveview as PL
    t0 = PL.F.T(4, 50)
    v = L.phone_view(PL.fixture(t0), t0, narr=N.Narrator())
    v = json.loads(json.dumps(v, default=str))
    v["structure"] = structure_of(v.get("bars5") or [])
    return shift(v, now - t0)


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    for a, b in (("tools/web_public/space.css", "web_next/css/space.css"), ("tools/web_public/mission.css", "web_next/css/mission.css"),
                 ("tools/web_public/missioncore.js", "web_next/js/next/missioncore.js"), ("tools/web_public/liveviewchart.js", "web_next/js/next/liveviewchart.js"),
                 ("tools/web_public/liveview.css", "web_next/css/liveview.css"), ("tools/web_public/fx.js", "web_next/js/fx.js")):
        check(f"a. {os.path.basename(a)} byte-identical on both apps", rd(*a.split("/")) == rd(*b.split("/")))
    fx, src = rd("tools", "web_public", "fx.js"), rd("tools", "web_public", "fx", "src", "space.js")
    kb = os.path.getsize(os.path.join(ROOT, "tools", "web_public", "fx.js")) / 1024
    check("a. fx.js bundles the deep-space scene (fx-space, bots / shoot / pnl / stats) and stays under 1.2 MB",
          "fx-space" in fx and "shoot" in fx and kb < 1200, f"{kb:.0f} KB")
    check("a. space.js: WebGL scene with the eclipse, satellites, 30 fps phones, reduced-motion still frame, DPR caps 1.5 / 2",
          "uShC" in src and "BOTS" in src and "1 / 31" in src and "Q.reduced" in src and "dprMax: Q.phone ? 1.5 : 2" in src)
    pidx, psw, sw = rd("tools", "web_public", "index.html"), rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js")
    check("a. phone index: space.css + mission.css, the CSS sky, missioncore.js then mission.js after liveview.js, 3D on by default",
          'href="space.css?v=' in pidx and 'href="mission.css?v=' in pidx and 'class="space-css"' in pidx
          and pidx.index('liveview.js?v=') < pidx.index('missioncore.js?v=') < pidx.index('mission.js?v=') and "navigator.webdriver ? 'off' : 'max'" in pidx)
    widx, app, routes, fx3d = rd("web_next", "index.html"), rd("web_next", "js", "app.js"), rd("web_next", "js", "next", "routes.js"), rd("web_next", "js", "next", "fx3d.js")
    check("a. PC: space.css + mission.css + the CSS sky, Mission Control in Main after Home, page module + 3D sync, 3D on by default",
          "/css/space.css" in widx and "/css/mission.css" in widx and 'class="space-css"' in widx and "MISSION = { id: 'mission'" in routes
          and "PAGES.mission = missionPage" in app and "initMissionSync()" in app and "navigator.webdriver ? 'off' : 'max'" in fx3d)
    check("a. caches: phone le-public-v43+, PC le-shell-next-v25+",
          int(re.search(r"le-public-v(\d+)", psw).group(1)) >= 43 and int(re.search(r"le-shell-next-v(\d+)", sw).group(1)) >= 25)
    mc, pm, phm = rd("tools", "web_public", "missioncore.js"), rd("web_next", "js", "next", "mission.js"), rd("tools", "web_public", "mission.js")
    check("a. read-only: the renderer never fetches, the pages only GET", "fetch(" not in mc and "POST" not in mc + pm + phm and "method:" not in pm + phm)
    feat = rd("web_next", "FEATURES.md")
    check("a. FEATURES.md: the deep-space / Mission Control features registered (51+)", "Mission Control" in feat and "Deep space" in feat
          and len(re.findall(r"^\| *\d+ *\|", feat, re.M)) >= 60)
    lv = rd("web_next", "js", "next", "liveviewchart.js")
    check("a. Live View: the structure layer (zone, pools, swings, BOS / CHoCH, protected) behind a switch; nothing without the block",
          "d.structure" in lv and "CHoCH" in lv and "BSL" in lv and "o.on.structure" in lv and "sw('structure')" in rd("tools", "web_public", "liveview.js")
          and "sw('structure')" in rd("web_next", "js", "next", "liveview.js"))


# ------------------------------------------------------------------------------------------------ b. node render
def part_b(b2, b3, lvd):
    node = shutil.which("node")
    if not node:
        print("[SKIP] b. node not installed")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for n, o in (("b2.json", b2), ("b3.json", b3), ("lv.json", lvd)):
            json.dump(o, open(os.path.join(tmp, n), "w"), default=str)
        js = r"""
global.window = {}; global.document = { querySelectorAll: () => [], querySelector: () => null, hidden: false };
require(process.argv[2]);
const M = window.MissionUI, fs = require('fs'), dir = process.argv[3];
const b2 = JSON.parse(fs.readFileSync(dir + '/b2.json')), b3 = JSON.parse(fs.readFileSync(dir + '/b3.json')), lv = JSON.parse(fs.readFileSync(dir + '/lv.json'));
const out = {};
const m2 = { board: b2, now: b2.t, lv, news: [{ t: b2.t + 3600, title: 'CPI', impact: 'high' }], where: 'phone' };
const m3 = { board: b3, now: b3.t, lv, news: [], where: 'pc' };
const a2 = M.accounts(m2), a3 = M.accounts(m3);
out.a2 = a2.map((a) => [a.key, a.name, a.state, a.placeholder]); out.a3 = a3.map((a) => [a.key, a.name, a.state, a.placeholder]);
out.p2 = M.page(m2); out.p3 = M.page(m3); out.s2 = M.strip(m2, { go: (id) => `data-go="${id}"` });
out.bots2 = M.botStates(m2); out.bots3 = M.botStates(m3); out.closed = M.closed(m2).slice(0, 2);
out.why = M.whyNot(a2[1], m2).map((r) => r.text);
let bad = 0; for (const g of [null, {}, { board: null }, { board: { lit: 5, atlas: 'x', trades: 'no', health: { items: 3 } } }, { board: { lit: { id: 'lit', name: 'Z', balance: 'x', days: 4, position: 7 } } }]) {
  try { M.page(g || {}); M.strip(g || {}); M.botStates(g || {}); M.closed(g || {}); } catch (e) { bad++; out.err = String(e.stack).slice(0, 300); } }
out.bad = bad; out.features = M.FEATURES.length;
console.log(JSON.stringify(out));
"""
        jp = os.path.join(tmp, "r.js")
        open(jp, "w").write(js)
        r = subprocess.run([node, jp, os.path.join(ROOT, "tools", "web_public", "missioncore.js"), tmp], capture_output=True, text=True, timeout=60)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            check("b. node render ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-500:])
            return
    check("b. 2 accounts on the board -> Zlarior, ATLAS + the BLITZ placeholder (paper / not live yet)",
          [x[0] for x in o["a2"]] == ["lit", "atlas", "blitz"] and o["a2"][2][3] is True and "paper / not live yet" in o["p2"], o["a2"])
    check("b. 3 accounts (a third board block) -> BLITZ drawn from its own account, no placeholder",
          [x[0] for x in o["a3"]] == ["lit", "atlas", "blitz"] and o["a3"][2][3] is False and o["p3"].count('class="mc-orbit ') == 3, o["a3"])
    check("b. the page: three orbits, today's mission, the 9 feature cards; the strip: 3 chips + the mission list",
          o["p2"].count('class="mc-orbit ') == 3 and o["p2"].count("data-mc-f=") == 10 and o["s2"].count('class="mc-chip ') == 3 and "mc-mission" in o["s2"])
    check("b. open position shows $ at stop / target and 'If it stops out now' the room after", "-$450" in o["p2"] and "+$3,600" in o["p2"] and "room left" in o["p2"])
    check("b. satellites: Zlarior in a trade, BLITZ off until its account; with 3 accounts BLITZ idle",
          o["bots2"]["lit"] == "trade" and o["bots2"]["scalp"] in ("off", "idle", "trade") and o["bots3"]["scalp"] == "idle", (o["bots2"], o["bots3"]))
    check("b. closed trades for the shooting stars (newest first, stable ids)", o["closed"] and o["closed"][0]["usd"] == 800.0 and "|" in o["closed"][0]["id"], o["closed"])
    check("b. why no trade yet lists plain reasons; never throws on garbage; 13 features registered", len(o["why"]) >= 1 and o["bad"] == 0 and o["features"] >= 12,
          (o["why"], o.get("err")))


# ------------------------------------------------------------------------------------------------ browsers
GPU_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def launch(p, args):
    try:
        return p.chromium.launch(args=args)
    except Exception:
        import glob
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        for exe in sorted(glob.glob(os.path.join(root, "chromium-*", "chrome-linux", "chrome")), reverse=True):
            return p.chromium.launch(executable_path=exe, args=args)
        raise


def serve(d):
    class Q(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=d, **k)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def site_with(tmp, board, lvd, now):
    site = os.path.join(tmp, "site")
    if os.path.isdir(site):
        shutil.rmtree(site)
    shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules", "icon_options"))
    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 600)),
            "live": {"last_run": now - 600, "runs": 1, "pc": {"present": True, "t": now - 60, "age_s": 60, "running": True, "every_s": 60, "host": "SURFACE"}},
            "accounts": [], "results": {"periods": {}}, "trades": [], "strategy": {}, "board": board,
            "news": {"events": [{"t": now + 5400, "title": "Initial Jobless Claims", "impact": "high"}, {"t": now + 9000, "title": "GDP (Q3 advance)", "impact": "high"}]}}
    for n in ("data.json", "home.json"):
        json.dump(data, open(os.path.join(site, n), "w"), default=str)
    lvp = os.path.join(tmp, "liveview.json")
    json.dump(lvd, open(lvp, "w"), default=str)
    return site, lvp


def phone_page(br, base, lvp, w, h, url, errs, reduced=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=True, has_touch=True,
                         reduced_motion="reduce" if reduced else "no-preference")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"{w}x{h} pageerror: {str(e)[:240]}"))
    pg.route("**/api.github.com/**", lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url else r.fulfill(status=404, body="{}"))
    pg.route("**/raw.githubusercontent.com/**", lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url else r.fulfill(status=404, body="{}"))
    pg.goto(base + url, wait_until="domcontentloaded")
    return ctx, pg


def wait_space(pg, t=45000):
    try:
        pg.wait_for_function("() => { const s = window.__LEFX && window.__LEFX.space; return !!(s && s.stats.frames > 0 && document.querySelector('.fx-space.on')); }", timeout=t)
        pg.wait_for_timeout(1600)          # the canvas fade-in (1.4 s)
        return True
    except Exception:
        return False


def frame_stats(pg, ms=3000):
    a = pg.evaluate("() => ({ f: window.__LEFX.space.stats.frames, t: performance.now() })")
    pg.wait_for_timeout(ms)
    b = pg.evaluate("() => { const s = window.__LEFX.space.stats; return { f: s.frames, t: performance.now(), ms: s.ms, bake: s.bakeMs, dpr: window.__LEFX.space.renderer.getPixelRatio(), soft: window.__LEFX.space.soft }; }")
    n = b["f"] - a["f"]
    return {"frames": n, "fps": n / ((b["t"] - a["t"]) / 1000), "cpu_ms": b["ms"], "bake_ms": b["bake"], "dpr": b["dpr"], "soft": b["soft"]}


def part_c(b2, b3, lvd, now, shots, perf):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    tmp = tempfile.mkdtemp(prefix="le_space_")
    try:
        site, lvp = site_with(tmp, b2, lvd, now)
        srv = serve(site)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        with sync_playwright() as p:
            br = launch(p, GPU_ARGS)
            errs = []
            # 0. the scene alone at phone size (fx/space.html: no page, no 3D panels): the frame-time numbers
            shutil.copytree(os.path.join(ROOT, "tools", "web_public", "fx"), os.path.join(site, "fx"), ignore=shutil.ignore_patterns("node_modules", "src"))
            ctx, pg = phone_page(br, base, lvp, 390, 844, "/fx/space.html?cards=0&lit=trade&atlas=armed", errs)
            ok = wait_space(pg)
            if ok:
                pg.wait_for_timeout(1500)
                fs = frame_stats(pg, 4000)
                perf["phone_390_scene"] = fs
                check("c. phone 390x844 scene alone: frame time sane (>= 8 frames in 4 s and < 250 ms CPU a frame in a software GPU, DPR <= 1.5)",
                      fs["frames"] >= 8 and fs["cpu_ms"] < 250 and fs["dpr"] <= 1.5, fs)
            else:
                check("c. phone 390x844 scene alone mounts", False, errs[-3:])
            ctx.close()
            # 1. Home with the 3D scene (software GPU: small bakes, adaptive resolution)
            ctx, pg = phone_page(br, base, lvp, 390, 844, "/index.html?fx=max#/today", errs)
            ok = wait_space(pg)
            check("c. phone 390x844: the deep-space scene mounts (WebGL2) and fades in", ok, errs[-3:])
            if ok:
                fs = frame_stats(pg)
                perf["phone_390_in_app"] = fs
                check("c. phone in the app: the scene keeps drawing (software GPU, every 3D panel of Home on) at DPR <= 1.5", fs["frames"] >= 1 and fs["dpr"] <= 1.5, fs)
            pg.wait_for_selector(".mc-strip", timeout=20000)
            check("c. phone Home: Mission Control strip on top with 3 orbit chips and today's mission",
                  pg.eval_on_selector_all(".mc-strip .mc-chip", "e => e.length") == 3 and pg.is_visible(".mc-mission")
                  and pg.evaluate("() => { const s = document.querySelector('.mc-strip').getBoundingClientRect(), c = [...document.querySelectorAll('#page .card')].filter((x) => !x.closest('.mc-strip'))[0]; return !c || s.top <= c.getBoundingClientRect().top; }"))
            st = pg.evaluate("() => { const s = window.__LEFX && window.__LEFX.space; return s ? s.sats.map((x) => [x.key, x.state]) : null; }")
            check("c. phone: the satellites follow the bots (Zlarior in a trade)", st and dict(st).get("lit") == "trade", st)
            pg.evaluate("() => FX.shoot('win')")
            pg.wait_for_timeout(700)
            check("c. phone: a closed trade fires a shooting star", pg.evaluate("() => (window.__LEFX.space.shots || 0) >= 1 || !!window.__LEFX.space.meteor"))
            if shots:
                pg.evaluate("() => { window.__LEFX.space.hold = 0.05; }")
                pg.wait_for_timeout(1500)
                pg.screenshot(path=os.path.join(shots, "phone_home_390.png"))
            pg.evaluate("() => { location.hash = '#/mission'; }")
            pg.wait_for_selector(".mc-page .mc-orbit", timeout=20000)
            pg.wait_for_timeout(900)
            n = pg.eval_on_selector_all(".mc-page .mc-orbit", "e => e.length")
            txt = pg.inner_text(".mc-page")
            check("c. phone #/mission: 3 orbits (2 accounts + BLITZ paper / not live yet), the features, no horizontal scroll",
                  n == 3 and "paper / not live yet" in txt and "If it stops out now" in txt and "Why no trade yet?" in txt and "Session timeline" in txt
                  and pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"), (n, txt[:200]))
            if shots:
                pg.wait_for_timeout(1200)        # the page's warp-in
                pg.screenshot(path=os.path.join(shots, "phone_mission_390.png"))
                pg.screenshot(path=os.path.join(shots, "phone_mission_390_full.png"), full_page=True)
            # Live View with the structure layer
            pg.evaluate("() => { location.hash = '#/liveview'; }")
            try:
                pg.wait_for_selector(".lv-struct", timeout=30000)
                pg.wait_for_timeout(1200)
                lv_ok = True
            except Exception:
                lv_ok = False
            check("c. phone Live View: the structure card + the Structure switch (data has the block)",
                  lv_ok and pg.is_visible('[data-lv-on="structure"]') and "Market structure" in pg.inner_text(".lv-struct"))
            if shots and lv_ok:
                pg.screenshot(path=os.path.join(shots, "phone_liveview_390.png"))
            ctx.close()
            # 2. three accounts (a third board block)
            site_with(tmp, b3, lvd, now)
            ctx, pg = phone_page(br, base, lvp, 390, 844, "/index.html?fx=off#/mission", errs)
            pg.wait_for_selector(".mc-page .mc-orbit", timeout=20000)
            t3 = pg.inner_text(".mc-page")
            check("c. phone #/mission with 3 accounts: BLITZ from its account (no placeholder)", pg.eval_on_selector_all(".mc-page .mc-orbit", "e => e.length") == 3
                  and pg.eval_on_selector_all(".mc-page .mc-orbit.ph", "e => e.length") == 0 and "BLITZ" in t3, t3[:200])
            # 3. 3D off -> the CSS sky, no canvas
            pg.evaluate("() => { location.hash = '#/today'; }")
            pg.wait_for_timeout(800)
            off = pg.evaluate("() => ({ fx: document.documentElement.dataset.fx, canvas: !!document.querySelector('.fx-space'), sky: getComputedStyle(document.querySelector('.space-css')).visibility })")
            check("c. phone 3D Off: the static CSS sky shows, no WebGL canvas", off["fx"] in (None, "off") and not off["canvas"] and off["sky"] == "visible", off)
            ctx.close()
            # 4. sideways
            site_with(tmp, b2, lvd, now)
            ctx, pg = phone_page(br, base, lvp, 844, 390, "/index.html?fx=max#/today", errs)
            ok = wait_space(pg)
            check("c. phone sideways 844x390: the scene mounts", ok)
            if shots and ok:
                pg.evaluate("() => { window.__LEFX.space.hold = 0.05; }")
                pg.wait_for_timeout(1200)
                pg.screenshot(path=os.path.join(shots, "phone_home_landscape_844.png"))
                pg.evaluate("() => { location.hash = '#/liveview'; }")
                try:
                    pg.wait_for_selector(".lv-struct", timeout=20000)
                    pg.wait_for_timeout(1000)
                    pg.screenshot(path=os.path.join(shots, "phone_liveview_landscape_844.png"))
                except Exception:
                    pass
            ctx.close()
            # 5. reduced motion -> one still frame
            ctx, pg = phone_page(br, base, lvp, 390, 844, "/index.html?fx=max#/today", errs, reduced=True)
            ok = wait_space(pg)
            f0 = pg.evaluate("() => window.__LEFX.space.stats.frames") if ok else None
            pg.wait_for_timeout(2500)
            f1 = pg.evaluate("() => window.__LEFX.space.stats.frames") if ok else None
            check("c. prefers-reduced-motion: a still frame (no animation loop)", ok and f1 is not None and f1 - f0 <= 2, (f0, f1))
            ctx.close()
            check("c. phone: no page errors", not errs, errs[:6])
            br.close()
            # 6. no WebGL at all -> the CSS sky
            br = launch(p, ["--disable-webgl", "--disable-3d-apis", "--disable-gpu"])
            errs2 = []
            ctx, pg = phone_page(br, base, lvp, 390, 844, "/index.html?fx=max#/today", errs2)
            pg.wait_for_selector(".mc-strip", timeout=20000)
            pg.wait_for_timeout(2500)
            nw = pg.evaluate("() => ({ fx: document.documentElement.dataset.fx, canvas: !!document.querySelector('.fx-space'), sky: getComputedStyle(document.querySelector('.space-css')).visibility })")
            check("c. no WebGL: fallback to the CSS sky (data-fx off, no canvas), no page errors", nw["fx"] == "off" and not nw["canvas"] and nw["sky"] == "visible" and not errs2, (nw, errs2[:3]))
            if shots:
                pg.screenshot(path=os.path.join(shots, "phone_home_390_css_fallback.png"))
            ctx.close()
            br.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pc_go(pg, page, tries=8):
    """LE.go(page) until it sticks (the PC app opens Start by itself once its first health ping says the bot is stopped)."""
    for _ in range(tries):
        pg.evaluate(f"() => window.LE.go('{page}')")
        pg.wait_for_timeout(1200)
        if pg.evaluate(f"() => !!document.querySelector('#page-{page}.active')"):
            return True
    return False


def part_d(b3, lvd, now, shots, perf):
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn  # noqa: F401
    except Exception:
        print("[SKIP] d. PC Playwright: playwright / uvicorn not installed")
        return
    from tests.shots_board import free_port, snapshot_files, restore_files
    snap = snapshot_files()
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
    try:
        import uvicorn
        import server
        from engine import board_api, liveview_api
        board_api.board_view = lambda bot, now=None: copy.deepcopy(b3)
        lv_pc = {**copy.deepcopy(lvd), "tf": "5m", "bars": lvd.get("bars5") or lvd.get("bars")}
        liveview_api.view = lambda bot, tf="1m", now=None, narr=None, n_feed=100: copy.deepcopy(lv_pc if tf == "5m" else {**lvd, "tf": "1m"})
        port = free_port()
        srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=srv.run, daemon=True).start()
        for _ in range(300):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        base = f"http://127.0.0.1:{port}"
        with sync_playwright() as p:
            br = launch(p, GPU_ARGS)
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(f"pc pageerror: {str(e)[:240]}"))
            pg.add_init_script("localStorage.setItem('page', 'cc');")
            pg.goto(base + "/?fx=max", wait_until="domcontentloaded")
            ok = wait_space(pg, 60000)
            check("d. PC 1440x900: the deep-space scene mounts behind the dashboard", ok, errs[-3:])
            if ok:
                fs = frame_stats(pg)
                perf["pc_1440_in_app"] = fs
                check("d. PC in the app: the scene keeps drawing (software GPU) at DPR <= 2", fs["frames"] >= 1 and fs["dpr"] <= 2, fs)
            pg.wait_for_function("() => window.LE && window.LE.go", timeout=30000)
            pg.wait_for_timeout(2500)
            if shots and ok:
                pc_go(pg, 'cc')
                pg.evaluate("() => { window.__LEFX.space.hold = 0.05; }")
                pg.wait_for_timeout(2500)
                pg.screenshot(path=os.path.join(shots, "pc_home_1440.png"))
            pc_go(pg, 'mission')
            pg.wait_for_selector("#page-mission .mc-orbit", timeout=30000)
            pg.wait_for_timeout(1200)
            n = pg.eval_on_selector_all("#page-mission .mc-orbit", "e => e.length")
            txt = pg.inner_text("#page-mission")
            check("d. PC Mission Control: 3 accounts (BLITZ from its own block), the features", n == 3 and "BLITZ" in txt and "Health constellation" in txt
                  and "Alerts center" in txt, (n, txt[:300]))
            st = pg.evaluate("() => { const s = window.__LEFX && window.__LEFX.space; return s ? s.sats.map((x) => [x.key, x.state]) : null; }")
            check("d. PC: the satellites follow the bots (Zlarior in a trade)", st and dict(st).get("lit") == "trade", st)
            if shots:
                pg.screenshot(path=os.path.join(shots, "pc_mission_1440.png"))
                pg.screenshot(path=os.path.join(shots, "pc_mission_1440_full.png"), full_page=True)
            pc_go(pg, 'liveview')
            try:
                pg.wait_for_selector("#page-liveview .lv-struct", timeout=30000)
                pg.wait_for_timeout(1500)
                lv_ok = True
            except Exception:
                lv_ok = False
            check("d. PC Live View: structure card + switch", lv_ok and "Market structure" in pg.inner_text("#page-liveview"))
            if shots and lv_ok:
                pg.screenshot(path=os.path.join(shots, "pc_liveview_1440.png"))
            check("d. PC: no page errors", not errs, errs[:6])
            br.close()
        srv.should_exit = True
    finally:
        restore_files(snap)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    shots = None
    if "--shots" in argv:
        shots = argv[argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    now = int(time.time()) // 60 * 60
    b2, b3 = boards(now)
    lvd = liveview(now)
    part_a()
    part_b(b2, b3, lvd)
    perf = {}
    if "--no-browser" not in argv:
        part_c(b2, b3, lvd, now, shots, perf)
        part_d(b3, lvd, now, shots, perf)
    kb = os.path.getsize(os.path.join(ROOT, "tools", "web_public", "fx.js")) / 1024
    print(f"perf: fx.js {kb:.0f} KB; " + json.dumps(perf))
    print(f"\nspace ui: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
