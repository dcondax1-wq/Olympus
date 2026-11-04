"""LABYRINTH (tools/web_public/labyrinth/, OLYMPUS 2026-11-03): the risk maze of a prop-firm eval, a size what-if on the LIT trades the site shows.
  a. the static rules: the kit (olympus.css / themes.js / olympus.js ?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML,
     only the site's own files are fetched, safe areas and the orb's corner, 16 px inputs, reduced motion, the manifest, the icon, jarvis.json
  b. the maths (labcore.js, run in node): the trades parsed, the live eval's own rules, the trailing floor that locks at start + $100, pass and bust
     by hand, the risk cap as a ceiling, determinism, bust odds rising with size, a cap lowering them, the sweet spot, the plain verdicts
  c. the page in Chromium at 390 x 844 on the chosen LITE tier: no errors, the verdict and the odds, the slider moves the odds and the 3D run,
     the Sizes / March / Rules sheets, the cap and the look-ahead, the live eval line, the orb's corner free, no sideways scroll,
     the kept settings, the DEMO copy when the site files are missing, reduced motion, nothing leaves the machine
    python -X utf8 -m tests.test_labyrinth_page            (LAB_NO_BROWSER=1 skips c)
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "labyrinth")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const dir = " + json.dumps(PAGE) + "; const url = 'file://' + dir; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "labyrinth.css", "labcore.js", "labyrinth.js", "scene.js", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, scene, demo fixture, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "labyrinth.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o3">' in html and 'src="../olympus/themes.js?v=o3"' in html and 'src="../olympus/olympus.js?v=o3" data-app="labyrinth"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; the core's dispose is called",
          "from '../jarvis/three.module.min.js'" in js["scene.js"] and "from '../olympus/render.js'" in js["scene.js"] and "from '../olympus/materials.js'" in js["scene.js"]
          and "createRenderer(" in js["scene.js"] and "rc.render()" in js["scene.js"] and "new THREE.WebGLRenderer" not in js["scene.js"] and "rc.dispose()" in js["scene.js"])
    check("a. no innerHTML / insertAdjacentHTML / document.write (the data only ever goes in as text)", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = set(re.findall(r"getJSON\('([^']+)'", js["labyrinth.js"]))
    check("a. the page fetches only the site's own files (odeon/trades.json, home.json, its fixture), no WebSocket / beacon / XHR, storage only under 'labyrinth.v1'",
          fetched == {"../odeon/trades.json", "../home.json", "fixture.json"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource", s) for s in js.values())
          and set(re.findall(r"localStorage\.\w+Item\(([A-Za-z'\"\.]+)", js["labyrinth.js"])) <= {"KEY"} and "const KEY = 'labyrinth.v1'" in js["labyrinth.js"], fetched)
    check("a. it only reads: no POST, no order, nothing that writes to a bot", "method:" not in js["labyrinth.js"].replace(" ", "").lower() and "'POST'" not in js["labyrinth.js"])
    check("a. safe areas on every edge, the orb's corner (dock and cards stop 96 px from the right), 16 px selects, dvh after vh, reduced motion",
          all(f"var(--s{x})" in css for x in "trbl") and "right: calc(var(--sr) + var(--oly-orb-clear, 96px))" in css and "font-size: 16px" in css
          and re.search(r"max-height: calc\(100vh[^;]*; max-height: calc\(100dvh", css) is not None and "@media (prefers-reduced-motion: reduce)" in css and "touch-action: none" in css)
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Labyrinth" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, <= 3 kpis, <= 3 lines, t, open, theme, <= 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Labyrinth" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture holds 46 LIT trades and the 50K eval", len(fx["trades"]) == 46 and fx["demo"] is True and fx["home"]["accounts"][0]["eval"]["target_balance"] == 53000.0)


# ------------------------------------------------------------------------------------------------ b. the maths
def part_b():
    js = node("""const L = await import(url + '/labcore.js'); const fx = JSON.parse(fs.readFileSync(dir + '/fixture.json', 'utf8'));
      const R = { ...L.DEFAULT_RULES }, T = (day, usd, risk = 500) => ({ day, usd, r: 0, risk, src: 'x' });
      const pool = L.parseTrades(fx), hm = L.rulesFrom(fx.home);
      // by hand: +1,000 +1,200 +900: peak 53,100 -> target 53,000 passed on the third trade; floor = min(50,100, peak - 2,000)
      const w1 = L.walk([T('2026-01-01', 1000), T('2026-01-02', 1200), T('2026-01-03', 900)], 1, 0, R);
      const w2 = L.walk([T('2026-01-01', 1500), T('2026-01-02', -1900), T('2026-01-03', -300)], 1, 0, R);      // peak 51,500 -> floor 49,500; 49,600 then 49,300
      const w3 = L.walk([T('2026-01-01', 2100), T('2026-01-02', -2500)], 1, 0, R);                                // peak 52,100 -> floor locks at 50,100; 49,600 busts
      const wc = L.walk([T('2026-01-01', -800, 800)], 1, 400, R), wm = L.walk([T('2026-01-01', -800, 800)], 2, 0, R);
      const base = L.sim(pool, 1, 0, hm, { len: 15, n: 500, seed: 7 }), again = L.sim(pool, 1, 0, hm, { len: 15, n: 500, seed: 7 });
      const small = L.sim(pool, 0.5, 0, hm, { len: 15, n: 500, seed: 7 }), big = L.sim(pool, 2, 0, hm, { len: 15, n: 500, seed: 7 });
      const capd = L.sim(pool, 2, 300, hm, { len: 15, n: 500, seed: 7 }), nocap = L.sim(pool, 2, 0, hm, { len: 15, n: 500, seed: 7 });
      const rows = L.sweep(pool, 0, hm, [0.25, 0.5, 1, 1.5, 2], { len: 15, n: 300 }), sweet = L.sweetSpot(rows, 0.3);
      const g = L.ghosts(pool, 1, 0, hm, 24, 15, 11);
      out({ n: pool.length, sorted: pool.every((t, i) => !i || pool[i - 1].day <= t.day), lit: L.parseTrades({ trades: [{ day: '2026-01-01', usd: 5, strat: 'EMA' }, { day: '2026-01-02', usd: 6, strat: 'LIT', risk_usd: 100 }, { day: 'x', usd: 1 }, { usd: 3 }, null, { day: '2026-01-03', usd: 'abc' }] }),
        hm, def: L.rulesFrom(null), b50: L.rulesFrom({ accounts: [{ plan: 'Builder 25K', kind: 'eval', eval: { start_balance: 25000, target_balance: 26500, mll: 1000 } }] }),
        w1: [w1.outcome, w1.at, w1.steps.map((s) => s.floor)], w2: [w2.outcome, w2.at, w2.steps.map((s) => s.floor)], w3: [w3.outcome, w3.at, w3.steps.map((s) => s.floor)],
        wc: [wc.steps[1].usd, wc.outcome], wm: [wm.steps[1].usd, wm.outcome], fac: [L.factor(T('d', 1, 800), 2, 400), L.factor(T('d', 1, 100), 2, 400), L.factor(T('d', 1, 800), 1, 0)],
        same: JSON.stringify(base) === JSON.stringify(again), base, small, big, capd, nocap, rows: rows.map((r) => [r.m, r.pass, r.bust]), sweet,
        gn: g.length, gl: g.map((x) => x.bal.length).sort((a, b) => a - b)[0], plain: [0.6, 0.4, 0.1].map((b) => L.plain({ pass: 0.3, bust: b }, R, 15)).concat([L.plain({ pass: 0.1, bust: 0.05 }, R, 8)]),
        usd: [L.usd(1234.5), L.usd(-50)], march: L.march(pool, { ...hm, since: '2099-01-01' }, 5).length, empty: L.sim([], 1, 0, R, {}) });""")
    if js.get("error"):
        check("b. node runs labcore.js", False, js["error"])
        return
    check("b. the trades: 46 LIT trades oldest first; junk rows, other strategies and bad days dropped; a missing risk falls back to the loss size",
          js["n"] == 46 and js["sorted"] and js["lit"] == [{"day": "2026-01-02", "usd": 6, "r": 0, "risk": 100, "src": "trade"}], js["lit"])
    check("b. the live eval's own rules win (start, target, trailing max loss, the live balance and floor); without them the Builder 50K defaults; a 25K account is not the 50K",
          js["hm"]["start"] == 50000 and js["hm"]["target"] == 3000 and js["hm"]["balance"] == 52170.5 and js["hm"]["floor"] == 50100 and js["def"]["mll"] == 2000 and js["def"]["start"] == 50000
          and js["b50"]["start"] == 50000, (js["hm"], js["b50"]))
    check("b. by hand: +1,000 +1,200 +900 passes on trade 3; the floor trails the peak and is capped at start + $100",
          js["w1"][0:2] == ["pass", 3] and js["w1"][2] == [48000, 49000, 50100, 50100], js["w1"])
    check("b. by hand: peak 51,500 -> floor 49,500, 49,600 is alive, 49,300 busts on trade 3; peak 52,100 locks the floor at 50,100 and 49,600 busts on trade 2",
          js["w2"][0:2] == ["bust", 3] and js["w2"][2] == [48000, 49500, 49500, 49500] and js["w3"][0:2] == ["bust", 2] and js["w3"][2][1] == 50100, (js["w2"], js["w3"]))
    check("b. the risk cap is a ceiling on $ at risk: a $800 stop-out at cap $400 loses $400; double size loses $1,600; factor = min(size, cap / risk)",
          js["wc"][0] == -400 and js["wm"][0] == -1600 and js["fac"] == [0.5, 2, 1], (js["wc"], js["wm"], js["fac"]))
    check("b. the same seed gives the same odds (deterministic); the three outcomes add up to 100%",
          js["same"] and abs(js["base"]["pass"] + js["base"]["bust"] + js["base"]["open"] - 1) < 1e-9 and js["base"]["n"] == 500, js["base"])
    check("b. bigger size, more floor hits and more passes early (2x busts more than 0.5x); a $300 cap at 2x busts less than no cap",
          js["big"]["bust"] > js["small"]["bust"] and js["big"]["pass"] > js["small"]["pass"] and js["capd"]["bust"] < js["nocap"]["bust"], (js["small"], js["big"], js["capd"], js["nocap"]))
    check("b. the sweet spot is the size with the most passes that busts at most 30%; a sweep returns one row per size",
          len(js["rows"]) == 5 and js["sweet"]["m"] in [r[0] for r in js["rows"]] and js["sweet"]["bust"] <= 0.3 and js["sweet"]["safe"]
          and js["sweet"]["pass"] == max(r[1] for r in js["rows"] if r[2] <= 0.3), (js["rows"], js["sweet"]))
    check("b. 24 ghost paths of up to 16 points; an empty pool gives an empty, honest result (no crash)",
          js["gn"] == 24 and js["gl"] >= 2 and js["empty"]["n"] == 0 and js["empty"]["open"] == 1, (js["gn"], js["gl"], js["empty"]))
    check("b. plain verdicts: too big / risky / safe but slow / a good size; dollars with thousands separators",
          js["plain"][0].startswith("Too big") and js["plain"][1].startswith("Risky") and js["plain"][2].startswith("A good size") and js["plain"][3].startswith("Safe but slow")
          and "about 2 weeks" in js["plain"][3] and js["usd"] == ["$1,235", "-$50"], (js["plain"], js["usd"]))


# ------------------------------------------------------------------------------------------------ c. the browser
class Quiet(http.server.SimpleHTTPRequestHandler):
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


def make_site(tmp, with_odeon=True, with_home=True):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "labyrinth"))
    for d in ("jarvis", "olympus"):
        shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
    if with_odeon:
        os.makedirs(os.path.join(site, "odeon"))
        shutil.copy(os.path.join(WEB, "odeon", "trades.json"), os.path.join(site, "odeon", "trades.json"))
    if with_home:
        with open(os.path.join(site, "home.json"), "w", encoding="utf-8") as fh:
            json.dump(json.loads(rd(PAGE, "fixture.json"))["home"], fh)
    return site


GEOM = """() => { const W = innerWidth, H = innerHeight, bad = [];
  for (const el of document.querySelectorAll('#ui *, #dock *, #sheet:not([hidden]) *')) {
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    const b = el.getBoundingClientRect(), cs = getComputedStyle(el), clip = el.closest('.sheet .body');
    if (!b.width || !b.height || cs.visibility === 'hidden') continue;
    const c = clip ? clip.getBoundingClientRect() : null, r = { left: b.left, right: b.right, top: c ? Math.max(b.top, c.top) : b.top, bottom: c ? Math.min(b.bottom, c.bottom) : b.bottom };
    if (r.bottom <= r.top) continue;
    if (r.right > W - 16 + 0.5 || r.left < 16 - 0.5) bad.push('gutter ' + (el.id || el.className) + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
    if (r.right > W - 80 && r.bottom > H - 160) bad.push('orb ' + (el.id || el.className) + ' ' + Math.round(r.right) + ',' + Math.round(r.bottom));
  }
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad; }"""


def run_browser():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="le_lab_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/labyrinth/"
    outside = []
    shots = os.environ.get("LAB_SHOTS")
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=False, quality="low", vw=(390, 844)):
                ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=1, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
                if quality:
                    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")

                def guard(route):
                    u = route.request.url
                    if u.startswith(f"http://127.0.0.1:{srv.server_address[1]}") or u.startswith(("data:", "blob:")):
                        return route.continue_()
                    outside.append(u)
                    return route.abort()
                ctx.route("**/*", guard)
                p = ctx.new_page()
                p.set_default_timeout(120000)
                p.errs = []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and "vibrate" not in m.text and p.errs.append(m.text))
                return ctx, p

            def ready(p, url=base):
                p.goto(url)
                p.wait_for_function("document.body.dataset.ready === '1' && window.LAB && LAB.state().scene && LAB.state().scene.drawn > 0", timeout=180000)

            st = lambda p: p.evaluate("LAB.state()")  # noqa: E731

            make_site(tmp)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. loads on the chosen LITE tier: real mode (no DEMO), 46 LIT trades (42 backtest, 3 paper, 1 real), the live eval's rules, no errors, 2 passes (scene + finish)",
                  not s["demo"] and s["n"] == 46 and s["counts"] == {"backtest": 42, "paper": 3, "real": 1} and s["rules"]["balance"] == 52170.5 and s["scene"]["quality"] == "low"
                  and s["scene"]["passes"] == 2 and not p.errs and p.is_visible("#lite") and not p.is_visible("#demo"), (s["scene"], p.errs))
            t = p.inner_text("#verdict")
            check("c. the verdict in plain words with the odds, and the live eval line (balance, floor, room, to the target)",
                  re.search(r"\d+%", p.inner_text("#oPass")) and re.search(r"\d+%", p.inner_text("#oBust")) and p.inner_text("#vText").split(":")[0] in ("Too big", "Risky", "Safe but slow", "A good size")
                  and "Your live eval now: balance $52,171" in t and "floor $50,100" in t and "$830 to the target" in t, t)
            check("c. the 3D maze is built from the run: floor blocks (look-ahead + 1), 24 ghost paths, walls of the labyrinth", s["scene"]["blocks"] == 16 and s["scene"]["ghosts"] > 100 and s["scene"]["walls"] > 80, s["scene"])
            ov = p.evaluate(GEOM)
            check("c. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not ov, ov)
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "labyrinth-home.png"))
            a = st(p)
            b = p.evaluate("LAB.set('mult', 2)")
            c = p.evaluate("LAB.set('mult', 0.5)")
            check("c. the size slider moves the odds and the run: 2x busts more than 0.5x, the label and the slider follow, the 3D run is rebuilt",
                  b["bust"] > c["bust"] and p.inner_text("#multV") == "0.50x" and p.input_value("#mult") == "0.5" and c["scene"]["steps"] >= 2, (a["bust"], b["bust"], c["bust"]))
            p.evaluate("(() => { const e = document.getElementById('mult'); e.value = '1.5'; e.dispatchEvent(new Event('input', { bubbles: true })); })()")
            p.wait_for_function("LAB.state().mult === 1.5")
            p.wait_for_function("document.getElementById('multV').textContent === '1.50x'")
            check("c. dragging the real range input works (1.50x) and the 1.5x preset is pressed", p.inner_text("#multV") == "1.50x" and p.get_attribute("[data-m='1.5']", "aria-pressed") == "true")
            p.click("#sweetBtn")
            p.wait_for_function("LAB.state().mult === LAB.state().sweet.m")
            check("c. the Sweet spot button jumps to the best size under 30% floor hits", p.evaluate("LAB.state().mult === LAB.state().sweet.m") and p.get_attribute("#sweetBtn", "aria-pressed") == "true")
            p.select_option("#cap", "300")
            p.select_option("#hor", "30")
            p.wait_for_function("LAB.state().cap === 300 && LAB.state().hor === 30")
            s2 = st(p)
            check("c. the risk cap and the look-ahead change the maze (31 floor blocks at 30 trades) and are kept", s2["scene"]["blocks"] == 31 and s2["cap"] == 300 and s2["hor"] == 30, s2["scene"])
            p.click("[data-view=sizes]")
            p.wait_for_timeout(300)
            ov = p.evaluate(GEOM)
            check("c. the Sizes sheet: the chart (two lines), 8 sizes in the table with the current one marked, the sweet spot in words; URL #sizes; inside the gutters, out of the orb's corner",
                  p.locator(".chart polyline").count() == 2 and p.locator(".tbl tr").count() == 9 and p.locator(".tbl tr.me").count() == 1 and "Sweet spot" in p.inner_text("#sheet")
                  and p.evaluate("location.hash") == "#sizes" and p.get_attribute("[data-view=sizes]", "aria-pressed") == "true" and not ov, ov)
            if shots:
                p.screenshot(path=os.path.join(shots, "labyrinth-sizes.png"))
            p.click("[data-view=march]")
            p.wait_for_timeout(300)
            check("c. the March sheet: the recent trades in order, each with its balance and room, an ending line (PASS or BUST) when the run ends, the sample counts",
                  p.locator(".march li").count() >= 3 and "room $" in p.inner_text(".march") and "42 backtest" in p.inner_text("#sheet") and not p.evaluate(GEOM))
            p.click("[data-view=rules]")
            p.wait_for_timeout(300)
            check("c. the Rules sheet explains the floor, the target, the size and the cap, and says it is a what-if, never an order",
                  all(x in p.inner_text("#sheet") for x in ("FLOOR wall", "TARGET gate", "risk cap", "what-if, not a forecast", "never places or changes an order")))
            p.keyboard.press("Escape")
            check("c. Escape closes the sheet", not p.is_visible("#sheet"))
            p.reload()
            p.wait_for_function("document.body.dataset.ready === '1'", timeout=180000)
            s3 = st(p)
            check("c. the settings are kept on this phone (size, cap, look-ahead) after a reload", s3["mult"] == s2["mult"] and s3["cap"] == 300 and s3["hor"] == 30, (s3["mult"], s3["cap"], s3["hor"]))
            card = p.evaluate("LAB.card()")
            check("c. the card for Jarvis: 3 kpis (pass, bust, sweet spot), <= 3 lines of <= 120 characters", len(card["kpis"]) == 3 and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]) and card["name"] == "Labyrinth", card)
            ctx.close()

            make_site(tmp, with_odeon=False, with_home=False)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. no site files: the recorded copy (DEMO badge, 46 trades, the fixture's eval), still no errors", s["demo"] and p.is_visible("#demo") and s["n"] == 46 and s["rules"]["balance"] == 52170.5 and not p.errs, (s["demo"], s["n"], p.errs))
            ctx.close()

            make_site(tmp)
            ctx, p = page(reduced=True)
            ready(p)
            before = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1500)
            after = st(p)["scene"]["drawn"]
            check("c. reduced motion: a still scene (no frames while nothing changes), a change redraws it, no errors", after - before <= 1 and not p.errs, (before, after, p.errs))
            p.evaluate("LAB.set('mult', 1.25)")
            p.wait_for_timeout(1500)
            check("c. ...and the slider still redraws it", st(p)["scene"]["drawn"] > after)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. nothing left the machine: no request to any other origin", not outside, outside[:3])


def main():
    part_a()
    part_b()
    if os.environ.get("LAB_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
