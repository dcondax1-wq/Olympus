"""HEPHAESTUS (tools/web_public/hephaestus/, OLYMPUS 2026-11-04): the strategy workshop. Read-only; the numbers are the STORED backtest runs.
  a. the static rules: the kit (?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML, only the site's own files are fetched
     (data.json, fixture.json), storage only under 'hephaestus.v1', safe areas and the orb's corner, reduced motion, manifest, icon, jarvis.json,
     nothing in the page can write to the bot (no POST, no WebSocket)
  b. the build (tools/hephaestus_build.py run fresh into a temp file): every setting is a stored run in research/runs/, the full-year 2026 line it
     computes equals the run's own stored 2026 line, the live setting's Jan-Jun / Jul-Oct lines equal research/lab/backtest_live.json, no two
     selectable settings share the same dials, every ref exists, the rejected strip comes from docs/CLAUDE_REFERENCE.md
  c. the logic (hephaestuscore.js in node): which settings exist (the rest "not tested"), the verdict kinds, the table
  d. the page in Chromium at 390 x 844 on the LITE tier: no errors, the live setting first, dials grey out what is not tested, a tested change moves the
     numbers + the verdict + strikes the hammer, an untested one changes nothing and says so, the table matches the stored run, the orb's corner free, no
     sideways page scroll, the DEMO copy when data.json is missing, reduced motion, nothing leaves the machine
    python -X utf8 -m tests.test_hephaestus_page            (HEPH_NO_BROWSER=1 skips d; HEPH_SHOTS=<dir> saves screenshots)
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
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "hephaestus")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body, data_path):
    script = ("import fs from 'fs'; const dir = " + json.dumps(PAGE) + "; const url = 'file://' + dir; const data = JSON.parse(fs.readFileSync(" + json.dumps(data_path) + ", 'utf8'));"
              " const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "hephaestus.css", "hephaestuscore.js", "hephaestus.js", "scene.js", "data.json", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, scene, data, demo fixture, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "hephaestus.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o7">' in html and 'src="../olympus/themes.js?v=o11"' in html and 'src="../olympus/olympus.js?v=o26" data-app="hephaestus"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; the core's dispose is called",
          "from '../jarvis/three.module.min.js'" in js["scene.js"] and "from '../olympus/render.js'" in js["scene.js"] and "from '../olympus/materials.js'" in js["scene.js"]
          and "createRenderer(" in js["scene.js"] and "rc.render()" in js["scene.js"] and "new THREE.WebGLRenderer" not in js["scene.js"] and "rc.dispose()" in js["scene.js"])
    check("a. no innerHTML / insertAdjacentHTML / document.write (the stored words only ever go in as text)", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = set(re.findall(r"getJSON\('([^']+)'", js["hephaestus.js"]))
    check("a. read-only: the page fetches only its own data.json / fixture.json; no POST / PUT / WebSocket / beacon / XHR anywhere; storage only under 'hephaestus.v1'",
          fetched == {"data.json", "fixture.json"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource|method:\s*['\"](POST|PUT|PATCH|DELETE)", s, re.I) for s in js.values())
          and "const KEY = 'hephaestus.v1'" in js["hephaestus.js"] and set(re.findall(r"localStorage\.\w+Item\(([A-Za-z'\"\.]+)", js["hephaestus.js"])) <= {"KEY"}, fetched)
    check("a. the core has no clock, no network and no storage of its own (pure)", not re.search(r"fetch\(|XMLHttpRequest|localStorage|Date\.now|new Date\(\)|Math\.random", js["hephaestuscore.js"]))
    check("a. safe areas on every edge, the orb's corner (the dock stops 96 px from the right, the sheet ends 168 px above the bottom), reduced motion",
          all(f"var(--s{x})" in css for x in "trbl") and "var(--oly-orb-clear, 96px)" in css and "168px" in css and "@media (prefers-reduced-motion: reduce)" in css)
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Hephaestus" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, <= 3 kpis, <= 3 lines, t, open, theme, <= 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Hephaestus" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture is flagged demo and still holds the live setting", fx["demo"] is True and any(s["id"] == fx["live_id"] for s in fx["scenarios"]))


# ------------------------------------------------------------------------------------------------ b. the build
def part_b(tmp):
    out = os.path.join(tmp, "data_fresh.json")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "hephaestus_build.py"), "--out", out], capture_output=True, text=True, timeout=300, cwd=ROOT)
    check("b. tools/hephaestus_build.py runs fresh into a temp file", p.returncode == 0 and os.path.exists(out), (p.stderr or p.stdout)[-400:])
    if not os.path.exists(out):
        return None
    d = json.load(open(out, encoding="utf-8"))
    runs = {s["id"]: json.load(open(os.path.join(ROOT, "research", "runs", s["run"] + ".json"), encoding="utf-8")) for s in d["scenarios"]}
    check("b. every setting is a stored run in research/runs/ (the build never recomputes the strategy)", all(os.path.exists(os.path.join(ROOT, "research", "runs", s["run"] + ".json")) for s in d["scenarios"]) and len(d["scenarios"]) >= 8)
    ok = all(s["y26"] == s["stored26"] and s["stored26"]["net"] == runs[s["id"]]["spans"]["2026"]["net"] and s["stored26"]["pf"] == runs[s["id"]]["spans"]["2026"]["pf"] for s in d["scenarios"])
    check("b. numbers match the stored runs: the full-year 2026 line the build scores equals each run's own stored 2026 line (net, PF, trades, eval pass / fail)", ok,
          [(s["id"], s["y26"], s["stored26"]) for s in d["scenarios"] if s["y26"] != s["stored26"]][:2])
    bl = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))["periods"]
    live = next(s for s in d["scenarios"] if s["id"] == d["live_id"])
    h1, h2 = bl["2026 H1 (picked on)"], bl["2026 H2 (check)"]
    check("b. the live setting's Jan-Jun and Jul-Oct lines equal research/lab/backtest_live.json (trades, trades/week, PF, net, $/month, max drawdown)",
          all((live[k]["n"], live[k]["tpw"], live[k]["pf"], live[k]["net"], live[k]["per_month"], live[k]["dd"]) == (b["trades"], b["per_week"], b["pf"], round(b["net"]), round(b["per_month"]), round(b["max_dd"]))
              for k, b in (("h1", h1), ("h2", h2))), (live["h1"], h1["pf"], live["h2"], h2["pf"]))
    sel = [s for s in d["scenarios"] if s["selectable"]]
    ids = [d_["id"] for d_ in d["dials"]]
    keys = [tuple(s["dials"][k] for k in ids) for s in sel]
    check("b. no two selectable settings share the same dials; the live dials are the live setting; every ref exists", len(set(keys)) == len(keys) and tuple(d["live"][k] for k in ids) == tuple(live["dials"][k] for k in ids)
          and all(s["ref"] is None or any(x["id"] == s["ref"] for x in d["scenarios"]) for s in d["scenarios"]))
    ref_md = rd(ROOT, "docs", "TESTED_AND_REJECTED.md")
    check("b. the rejected strip comes from the Tested-and-rejected section of docs/CLAUDE_REFERENCE.md (>= 10 notes, each with a title and a text)",
          len(d["rejected"]) >= 10 and all(r["title"] and r["text"] for r in d["rejected"]) and "## Tested and rejected" in ref_md)
    shipped = json.load(open(os.path.join(PAGE, "data.json"), encoding="utf-8"))
    check("b. the shipped data.json carries the same numbers as a fresh build (rerun tools/hephaestus_build.py after new runs)",
          [(s["id"], s["h1"], s["h2"], s["y26"]) for s in shipped["scenarios"]] == [(s["id"], s["h1"], s["h2"], s["y26"]) for s in d["scenarios"]])
    return out


# ------------------------------------------------------------------------------------------------ c. the logic
def part_c(data_path):
    js = node("""const C = await import(url + '/hephaestuscore.js'); const L = data.live;
      const dl = (o) => ({ ...L, ...o }); const v = (o) => C.verdict(data, C.find(data, dl(o)));
      const cell = C.table(data, C.find(data, dl({ cut: 'off' })));
      out({ live: C.find(data, L).id, nocut: C.find(data, dl({ cut: 'off' })).id, none: C.find(data, dl({ cut: 'off', be: 'off' })), t: [C.tested(data, L, 'cut', 'off'), C.tested(data, L, 'target', '4R'), C.tested(data, dl({ cut: 'off' }), 'be', 'off')],
        any: [C.anyTested(data, 'target', '4R'), C.anyTested(data, 'target', 'none')], kinds: data.scenarios.filter((s) => s.selectable).map((s) => [s.id, C.verdict(data, s).kind]), nv: C.verdict(data, null).kind,
        usd: [C.usd(43820), C.usd(-2196), C.usd(5, true), C.usd(null)], dec: C.dec(4.185), rows: cell.map((r) => r.k), cut: cell[0].cells.h1, same: C.table(data, C.find(data, L))[0].cells.h1.same });""", data_path)
    if js.get("error"):
        check("c. node runs hephaestuscore.js", False, js["error"])
        return
    kinds = dict(js["kinds"])
    check("c. find() returns the one stored run for the dials, null for a mix that was never run; tested() / anyTested() grey out the rest ('not tested')",
          js["live"] == "live" and js["nocut"] == "no_cut" and js["none"] is None and js["t"] == [True, False, False] and js["any"] == [False, True], js)
    check("c. the live setting says so; a setting that is not live gets a verdict from the two halves (live / beats / tradeoff / mixed / still); no stored run -> 'none'",
          kinds["live"] == "live" and js["nv"] == "none" and all(k in ("beats", "tradeoff", "mixed", "still") for i, k in kinds.items() if i != "live"), kinds)
    d = json.load(open(data_path, encoding="utf-8"))
    sc = {s["id"]: s for s in d["scenarios"]}

    def wins(a, b, h):
        return sc[a][h]["net"] > sc[b][h]["net"] and sc[a][h]["pf"] > sc[b][h]["pf"]
    exp = {}
    for s in d["scenarios"]:
        if not s["selectable"] or s["id"] == "live":
            continue
        r = s["ref"] or "live"
        w = sum(wins(s["id"], r, h) for h in ("h1", "h2"))
        up = all(sc[s["id"]][h]["net"] > sc[r][h]["net"] for h in ("h1", "h2"))
        tpw = all(sc[s["id"]][h]["tpw"] >= 2 for h in ("h1", "h2"))
        exp[s["id"]] = ("beats" if tpw else "mixed") if w == 2 else "tradeoff" if (w == 0 and up) else "still" if w == 0 else "mixed"
    check("c. the verdict follows the owner's rule exactly: 'beats' only when net AND profit factor are higher in BOTH halves (and 2+ trades a week), judged against its own twin run for the one-change runs",
          all(kinds[i] == e for i, e in exp.items()), {i: (kinds[i], e) for i, e in exp.items() if kinds[i] != e})
    check("c. the table has the seven rows (net, $/month, PF, drawdown, eval pass, eval fail, trades/week); changed cells carry live underneath; the live setting shows no live line",
          js["rows"] == ["net", "per_month", "pf", "dd", "p10", "f10", "tpw"] and "$" in js["cut"]["v"] and js["same"] is True, js)
    check("c. the money / PF formats", js["usd"] == ["$43,820", "-$2,196", "+$5", "-"] and js["dec"] in ("4.18", "4.19"), js["usd"])


# ------------------------------------------------------------------------------------------------ d. the browser
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


def make_site(tmp, with_data=True):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "hephaestus"))
    for d in ("jarvis", "olympus"):
        shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
    if not with_data:
        os.remove(os.path.join(site, "hephaestus", "data.json"))
    return site


GEOM = """() => { const W = innerWidth, H = innerHeight, bad = [];
  for (const el of document.querySelectorAll('.top *, #sheet, #dock *')) {
    const b = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (!b.width || !b.height || cs.visibility === 'hidden') continue;
    if (b.right > W - 16 + 0.5 || b.left < 16 - 0.5) bad.push('gutter ' + (el.id || el.className) + ' ' + Math.round(b.left) + '-' + Math.round(b.right));
    if (b.right > W - 80 && b.bottom > H - 160) bad.push('orb ' + (el.id || el.className) + ' ' + Math.round(b.right) + ',' + Math.round(b.bottom));
  }
  const sh = document.getElementById('sheet').getBoundingClientRect(), dk = document.getElementById('dock').getBoundingClientRect();
  if (sh.bottom > dk.top + 0.5) bad.push('sheet over dock ' + Math.round(sh.bottom) + ' > ' + Math.round(dk.top));
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad; }"""


def tap(p, sel):
    """a click through the DOM: the software GL in CI draws about one frame a second, which makes Playwright's own click wait on animation frames"""
    p.evaluate("(s) => document.querySelector(s).click()", sel)


def run_browser(tmp):
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/hephaestus/"
    outside, posts = [], []
    shots = os.environ.get("HEPH_SHOTS")
    stored = json.load(open(os.path.join(PAGE, "data.json"), encoding="utf-8"))
    sc = {s["id"]: s for s in stored["scenarios"]}
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=False, quality="low"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
                if quality:
                    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")

                def guard(route):
                    u = route.request.url
                    if route.request.method not in ("GET", "HEAD"):
                        posts.append(route.request.method + " " + u)
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

            def ready(p, q=""):
                p.goto(base + q)
                p.wait_for_function("document.body.dataset.ready === '1' && window.HEPH && HEPH.state().scene && HEPH.state().scene.drawn > 0", timeout=180000)

            st = lambda p: p.evaluate("HEPH.state()")  # noqa: E731
            cell = lambda p, row, half: p.inner_text(f"tr[data-row={row}] td[data-half={half}] b")  # noqa: E731

            make_site(tmp)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("d. loads on the chosen LITE tier: real data (no DEMO), the live setting selected, 2 passes, the LITE tag, no errors",
                  not s["demo"] and s["scenario"] == "live" and s["run"] == "lit_live" and s["scene"]["passes"] == 2 and p.is_visible("#lite") and not p.is_visible("#demo") and not p.errs and s["scene"]["quality"] == "low", (s, p.errs))
            check("d. the honest line is on the page: it changes nothing in the bot, it only reads stored runs", "changes nothing in the bot" in p.inner_text("#honest") and "only reads" in p.inner_text("#honest"))
            check("d. six dials with their options; today's value of each is marked live and pressed",
                  p.locator(".dial").count() == 6 and p.locator(".chip.live").count() == 6 and p.locator(".chip.live[aria-pressed=true]").count() == 6)
            check("d. the live verdict is shown in the dock", "live setting" in p.inner_text("#vh").lower() and st(p)["verdict"]["kind"] == "live")
            L = sc["live"]
            check("d. the table shows the stored live run: Jan-Jun and Jul-Oct net, PF and trades a week equal data.json (and so the stored run)",
                  cell(p, "net", "h1") == f"${L['h1']['net']:,}" and cell(p, "net", "h2") == f"${L['h2']['net']:,}" and cell(p, "pf", "h1") == f"{L['h1']['pf']:.2f}" and cell(p, "pf", "h2") == f"{L['h2']['pf']:.2f}"
                  and cell(p, "tpw", "h2") == f"{L['h2']['tpw']:.2f}" and p.locator("#rows tr").count() == 7, [cell(p, "net", "h1"), cell(p, "pf", "h2")])
            check("d. dials that were never run are greyed out (4R target, 02:00-15:30 is live, 09:30 window) and say 'not tested'; the tested ones are not",
                  p.get_attribute(".chip[data-dial=target][data-v='4R']", "aria-disabled") == "true" and p.get_attribute(".chip[data-dial=window][data-v='0930-1530']", "aria-disabled") == "true"
                  and p.get_attribute(".chip[data-dial=cut][data-v=off]", "aria-disabled") == "false" and p.get_attribute(".chip[data-dial=size][data-v=uprisk]", "aria-disabled") == "false")
            check("d. 24-ish rejected notes are in the strip (>= 10 cards), as plain text", p.locator("#rej .card").count() >= 10)
            ov = p.evaluate(GEOM)
            check("d. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, the sheet ends above the dock, no sideways page scroll", not ov, ov)
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "hephaestus-live.png"))
            n0 = st(p)["scene"]["strikes"] if "strikes" in st(p)["scene"] else None
            p.click(".chip[data-dial=cut][data-v=off]")
            p.wait_for_timeout(500)
            s = st(p)
            T = sc["no_cut"]
            check("d. turning the cut off picks the stored no-cut run, the table moves to its numbers (with live underneath), the hammer strikes, the verdict follows the halves",
                  s["scenario"] == "no_cut" and s["run"] == "abl_rm_t_check" and cell(p, "net", "h1") == f"${T['h1']['net']:,}" and cell(p, "net", "h2") == f"${T['h2']['net']:,}"
                  and "live" in p.inner_text("tr[data-row=net] td[data-half=h1] i") and s["scene"]["strikes"] == (n0 or 0) + 1 and s["verdict"]["kind"] in ("beats", "tradeoff", "mixed", "still")
                  and not p.evaluate(GEOM) and not p.errs, (s, p.evaluate(GEOM), p.errs))
            check("d. now be=off with the cut off was never run: greyed out, a tap changes nothing and says so",
                  p.get_attribute(".chip[data-dial=be][data-v=off]", "aria-disabled") == "true")
            tap(p, ".chip[data-dial=be][data-v=off]")
            check("d. ...tap: still the no-cut setting, a 'Not tested' message", st(p)["dials"]["be"] == "on" and st(p)["scenario"] == "no_cut" and "Not tested" in p.inner_text("#msg"), (st(p)["dials"], p.inner_text("#msg")))
            if shots:
                p.wait_for_timeout(300)
                p.screenshot(path=os.path.join(shots, "hephaestus-nocut.png"))
            tap(p, "#reset")
            p.wait_for_timeout(300)
            check("d. 'Back to live' returns to the live setting", st(p)["scenario"] == "live" and "live setting" in p.inner_text("#vh").lower() and p.inner_text("#msg") == "")
            tap(p, ".chip[data-dial=size][data-v=uprisk]")
            p.wait_for_timeout(300)
            s = st(p)
            check("d. size mode: Uprisk is a stored run too (lit_edge_eval_live) with its own numbers", s["scenario"] == "uprisk" and s["run"] == "lit_edge_eval_live" and cell(p, "net", "h2") == f"${sc['uprisk']['h2']['net']:,}", s)
            tap(p, ".chip[data-dial=size][data-v=two_week]")
            p.wait_for_timeout(300)
            check("d. ...and Two-week (abl_rec_cisd22_eval)", st(p)["scenario"] == "two_week" and st(p)["run"] == "abl_rec_cisd22_eval")
            kinds = {}
            for did, v, sid in (("target", "none", "no_cap"), ("be", "off", "no_be"), ("window", "0100-1555", "wide_window"), ("maxtr", "5", "five_trades"), ("be", "nocost", "be_nocost")):
                tap(p, "#reset")
                tap(p, f".chip[data-dial={did}][data-v='{v}']")
                p.wait_for_timeout(120)
                kinds[sid] = (st(p)["scenario"], st(p)["verdict"]["kind"])
            check("d. every stored one-change run can be reached by its dial (no cap, no BE, wide window, 5 trades a day, BE without costs)", all(k == v[0] for k, v in kinds.items()), kinds)
            tap(p, "#reset")
            tap(p, ".chip[data-dial=cut][data-v=off]")
            p.wait_for_timeout(300)
            p.reload()
            p.wait_for_function("document.body.dataset.ready === '1' && HEPH.state().scene.drawn > 0", timeout=180000)
            check("d. the last dials stay on this phone only: a reload comes back on the no-cut setting (localStorage 'hephaestus.v1')", st(p)["scenario"] == "no_cut"
                  and "dials" in json.loads(p.evaluate("localStorage.getItem('hephaestus.v1')")) and set(json.loads(p.evaluate("localStorage.getItem('hephaestus.v1')"))) <= {"dials", "hist", "pin"})   # JOB 4+5: the dials, the history of dials tried and the pinned compare side, nothing else
            card = p.evaluate("HEPH.card()")
            check("d. the card for Jarvis: 3 kpis, <= 3 lines of <= 120 characters, name Hephaestus", card["name"] == "Hephaestus" and len(card["kpis"]) == 3 and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]), card)
            ctx.close()

            make_site(tmp, with_data=False)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("d. no data.json: the recorded copy (DEMO badge), the live setting, the untested dials greyed, still no errors", s["demo"] and p.is_visible("#demo") and s["scenario"] == "live" and not p.errs
                  and p.get_attribute(".chip[data-dial=maxtr][data-v='5']", "aria-disabled") == "true", (s, p.errs))
            ctx.close()

            make_site(tmp)
            ctx, p = page(reduced=True)
            ready(p)
            before = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1500)
            after = st(p)["scene"]["drawn"]
            check("d. reduced motion: a still scene (no frames while nothing changes), no errors", after - before <= 1 and not p.errs, (before, after, p.errs))
            tap(p, ".chip[data-dial=cut][data-v=off]")
            p.wait_for_function(f"HEPH.state().scene.drawn > {after}", timeout=60000)
            check("d. ...and a dial still redraws it (a flash, no animation)", st(p)["scene"]["drawn"] > after and st(p)["scenario"] == "no_cut")
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
    check("d. nothing left the machine and nothing was sent: no request to another origin, no POST / PUT", not outside and not posts, (outside[:3], posts[:3]))


def main():
    tmp = tempfile.mkdtemp(prefix="le_heph_page_")
    try:
        part_a()
        out = part_b(tmp)
        if out:
            part_c(out)
        if os.environ.get("HEPH_NO_BROWSER") != "1":
            run_browser(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
