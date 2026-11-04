"""NEMESIS (tools/web_public/nemesis/, OLYMPUS 2026-11-04): the loss post-mortem. Every losing trade is a fallen figure; tap it for a plain-words autopsy.
  a. the static rules: the kit (olympus.css / themes.js / olympus.js ?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML,
     only the site's own files are fetched, storage only 'nemesis.v1' (write) and 'le.jtags' (read), no network call on Copy, safe areas and the orb's corner,
     reduced motion, the manifest, the icon, jarvis.json, the demo fixture
  b. the maths (nemcore.js, run in node), by hand: the dedupe of a real fill and its twins, the week, the stop beyond the sweep extreme, the entry hours,
     break-even at 1R, one trade a day, trading after two losses, the room replay, heavy size / the bot's ceiling / oversize against the twin, the journal
     tags, the leak ranking and its $ cost, "not recorded" instead of a guess, the Obsidian texts
  c. the page in Chromium at 390 x 844 on the chosen LITE tier: no errors, the summary, the 3D figures, a real tap on a figure opens its autopsy, the week
     stepper, the Leaks / Vow / About sheets, the vow tick kept in localStorage, the Copy buttons (clipboard only), the journal tags, the DEMO copy,
     reduced motion, the orb's corner free, no sideways scroll, nothing leaves the machine
    python -X utf8 -m tests.test_nemesis_page            (NEM_NO_BROWSER=1 skips c)
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
PAGE = os.path.join(WEB, "nemesis")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


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
    need = {"index.html", "nemesis.css", "nemcore.js", "nemesis.js", "scene.js", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, scene, demo fixture, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "nemesis.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o2">' in html and 'src="../olympus/themes.js?v=o2"' in html and 'src="../olympus/olympus.js?v=o2" data-app="nemesis"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; the core's dispose is called",
          "from '../jarvis/three.module.min.js'" in js["scene.js"] and "from '../olympus/render.js'" in js["scene.js"] and "from '../olympus/materials.js'" in js["scene.js"]
          and "createRenderer(" in js["scene.js"] and "rc.render()" in js["scene.js"] and "new THREE.WebGLRenderer" not in js["scene.js"] and "rc.dispose()" in js["scene.js"])
    check("a. no innerHTML / insertAdjacentHTML / document.write (the data only ever goes in as text)", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = set(re.findall(r"getJSON\('([^']+)'", js["nemesis.js"]))
    stores = set(re.findall(r"localStorage\.(\w+)Item\(([A-Za-z'\"\.]+)", js["nemesis.js"]))
    check("a. the page fetches only the site's own files (odeon/trades.json, home.json, its fixture), no WebSocket / beacon / XHR; storage: set only 'nemesis.v1', read 'le.jtags'",
          fetched == {"../odeon/trades.json", "../home.json", "fixture.json"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource", s) for s in js.values())
          and stores == {("get", "KEY"), ("set", "KEY"), ("get", "'le.jtags'")} and "const KEY = 'nemesis.v1'" in js["nemesis.js"], (fetched, stores))
    check("a. it only reads: no POST, no order, nothing that writes to a bot; the only way out is the clipboard", "method:" not in js["nemesis.js"].replace(" ", "").lower()
          and "'POST'" not in js["nemesis.js"] and js["nemesis.js"].count("fetch(") == 1 and "navigator.clipboard.writeText" in js["nemesis.js"])
    check("a. safe areas on every edge, the orb's corner (dock stops 96 px from the right; the sheet stays 176 px above the bottom), 16 px text areas, dvh after vh, reduced motion",
          all(f"var(--s{x})" in css for x in "trbl") and "right: calc(var(--sr) + var(--oly-orb-clear, 96px))" in css and "font-size: 16px" in css and "176px" in css
          and re.search(r"max-height: calc\(100vh[^;]*; max-height: calc\(100dvh", css) is not None and "@media (prefers-reduced-motion: reduce)" in css and "touch-action: none" in css)
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Nemesis" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, 3 kpis, <= 3 lines, t, open, theme, <= 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Nemesis" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture holds the 60 trades the site showed (no charts, no events) and the 50K eval", fx["demo"] is True and len(fx["trades"]) == 60
          and "bars" not in fx["trades"][0] and fx["home"]["accounts"][0]["eval"]["target_balance"] == 53000.0)
    accents = set()
    for sub in os.listdir(WEB):
        ip = os.path.join(WEB, sub, "index.html")
        if sub != "nemesis" and os.path.isfile(ip):
            accents |= {x.lower() for x in re.findall(r"oly-accent', '(#[0-9a-fA-F]{6})'", rd(WEB, sub, "index.html"))}
    mine = re.search(r"oly-accent', '(#[0-9a-fA-F]{6})'", html).group(1).lower()
    check("a. the accent is its own: not the accent of any other app page", mine not in accents, (mine, accents))


# ------------------------------------------------------------------------------------------------ b. the maths
def part_b():
    js = node(r"""const C = await import(url + '/nemcore.js'); const fx = JSON.parse(fs.readFileSync(dir + '/fixture.json', 'utf8'));
      // a hand-made day: 02:00 New York is 06:00 UTC (off -14400); T() builds one trade row
      const base = Date.UTC(2026, 9, 26, 6, 0, 0) / 1000;                                     // Mon 2026-10-26 02:00 ET
      const T = (o) => ({ day: '2026-10-26', side: 'SHORT', strat: 'LIT', src: 'backtest', usd: -300, r: -1, qty: 4, risk_usd: 300, risk_pts: 40, stop: 100.25, sweep: { ext_px: 100 }, entry: { px: 98, t: base + 600 },
        exit: { kind: 'STOP' }, held_min: 12, mfe_r: 0.4, mae_r: 1, off: -14400, ...o });
      const run = (rows, tags) => { const tr = C.parseTrades({ trades: rows }); return { tr, f: C.fallen(tr, tags || {}) }; };
      const ids = (f) => f.a.flags.map((x) => x.id);
      // dedupe: a real fill, its cloud twin and the backtest are one setup; the real one wins and keeps the twin's size
      const dd = C.parseTrades({ trades: [T({ src: 'paper', qty: 8, usd: -480 }), T({ src: 'real', qty: 5, usd: -300 }), T({ src: 'backtest', qty: 8, usd: -480 }), null, { day: 'x', usd: 1 }, { usd: 3 }, { day: '2026-10-26', usd: 'abc' }] });
      // weeks
      const wk = ['2026-10-26', '2026-10-28', '2026-11-01', '2026-11-02'].map(C.weekKey);
      // the stop: SHORT stop must sit above the sweep high by a tick; LONG below the sweep low
      const s1 = run([T({ stop: 100 })]).f[0], s2 = run([T({ stop: 100.25 })]).f[0], s3 = run([T({ side: 'LONG', stop: 99.75, sweep: { ext_px: 100 } })]).f[0], s4 = run([T({ side: 'LONG', stop: 100.25, sweep: { ext_px: 100 } })]).f[0], s5 = run([T({ sweep: null })]).f[0];
      // hours: 01:40 and 16:00 are out; 03:00 is in
      const w1 = run([T({ entry: { px: 98, t: base - 1200 } })]).f[0], w2 = run([T({ entry: { px: 98, t: base + 14 * 3600 } })]).f[0], w3 = run([T({ entry: { px: 98, t: base + 3600 } })]).f[0];
      // break-even at 1R: reached 1.2R then stopped at a full loss
      const b1 = run([T({ mfe_r: 1.2 })]).f[0], b2 = run([T({ mfe_r: 0.9 })]).f[0];
      // one trade a day; after two losses
      const d2 = run([T({ usd: 400, entry: { px: 98, t: base } }), T({ entry: { px: 98, t: base + 7200 } })]);
      const st = run([T({ day: '2026-10-19', entry: { px: 98, t: base - 7 * 86400 } }), T({ day: '2026-10-20', entry: { px: 98, t: base - 6 * 86400 } }), T({ day: '2026-10-21', entry: { px: 98, t: base - 5 * 86400 } }),
        T({ day: '2026-10-22', usd: 500, entry: { px: 98, t: base - 4 * 86400 } }), T({ day: '2026-10-23', entry: { px: 98, t: base - 3 * 86400 } })]);
      // the room replay: +1000 then +1500 on a fresh 50K: room 2000, 2000, 2400
      const rr = C.replayRoom(C.parseTrades({ trades: [T({ day: '2026-10-19', usd: 1000, entry: { px: 98, t: base - 7 * 86400 } }), T({ day: '2026-10-20', usd: 1500, entry: { px: 98, t: base - 6 * 86400 } }), T({ day: '2026-10-21', usd: -100, entry: { px: 98, t: base - 5 * 86400 } })] })).map((t) => t.room);
      // size: 800 at room 2000 is 40% (heavy, soft); 1700 is past the bot's 80% (hard); the twin took 4 and you took 8 (hard)
      const z1 = run([T({ risk_usd: 800, usd: -800 })]).f[0], z2 = run([T({ risk_usd: 1700, usd: -1700 })]).f[0], z3 = run([T({ src: 'real', qty: 8, usd: -300, twin: { qty: 4, usd: -150, src: 'paper' } })]).f[0], z4 = run([T({ src: 'real', qty: 4, usd: -300, twin: { qty: 8, usd: -600, src: 'paper' } })]).f[0];
      // the journal tags (the Zenith key is day_entryEpoch)
      const tg = run([T()], { ['2026-10-26_' + (base + 600)]: ['Late entry', 'Lesson'] }).f[0], tg2 = run([T()], { '2026-10-26_999': ['Would skip'] }).f[0];
      // leaks
      const lk = C.leaks(run([T({ risk_usd: 800, usd: -800, entry: { px: 98, t: base - 3 * 86400 }, day: '2026-10-23' }), T({ stop: 100, usd: -200, entry: { px: 98, t: base - 2 * 86400 }, day: '2026-10-24' }), T({ usd: 500, entry: { px: 98, t: base - 86400 }, day: '2026-10-25' }), T({ usd: -100, risk_usd: 100, entry: { px: 98, t: base }, day: '2026-10-26' })]).f);
      const demo = C.parseTrades(fx), demoF = C.fallen(demo, {});
      const fl = run([T()]).f[0];
      out({ dd: dd.map((t) => [t.src, t.qty, t.twin && t.twin.qty]), ddn: dd.length, wk, lossMin: [C.isLoss({ usd: -26 }), C.isLoss({ usd: -24 }), C.isLoss({ usd: -11.4 })],
        s: [ids(s1), ids(s2), ids(s3), ids(s4), ids(s5)], s5row: s5.a.rows.find((r) => r.id === 'stop'), s2row: s2.a.rows.find((r) => r.id === 'stop').text,
        w: [ids(w1), ids(w2), ids(w3)], b: [ids(b1), ids(b2)], d2: d2.f.map(ids), st: st.f.map(ids), rr,
        z: [z1.a.flags, z2.a.flags, z3.a.flags, z4.a.flags], zv: [z1.a.verdict, z2.a.verdict, z3.a.verdict, z4.a.verdict], z4row: z4.a.rows.find((r) => r.id === 'size').text,
        tg: [ids(tg), tg.a.tags], tg2: [ids(tg2), tg2.a.tags], tagRead: [C.readTags('not json'), C.readTags(null), C.readTags('{"a_b":["x",3],"c":5}')],
        lk: { rank: lk.rank.map((r) => [r.id, r.n, r.cost]), plan: lk.plan, lost: lk.lost }, ob: C.obsidianLesson(fl), obw: C.obsidianWeek('2026-10-26', [fl], C.leaks([fl]), { text: 'I wait.', done: true }),
        obw0: C.obsidianWeek('2026-10-26', [], C.leaks([]), null), verdict: [fl.a.verdict, fl.a.tone, b1.a.verdict, b1.a.tone, z1.a.tone, z2.a.tone], lesson: [fl.a.lesson, b1.a.lesson],
        demoN: demo.length, demoF: demoF.length, demoPlan: demoF.filter((f) => f.tone === 'plan').length, weeks: C.weeks(demo).slice(0, 2), plainWeek: [C.plainWeek([], C.leaks([])), C.plainWeek([fl], C.leaks([fl]))],
        other: C.fallen(C.parseTrades({ trades: [T({ strat: 'EMA', stop: null, sweep: null })] }), {})[0].a.verdict });""")
    if js.get("error"):
        check("b. node runs nemcore.js", False, js["error"])
        return
    check("b. one row per real setup: a real fill, its paper twin and the backtest are one trade; the real one wins and keeps the twin's size; junk rows are dropped",
          js["ddn"] == 1 and js["dd"] == [["real", 5, 8]], js["dd"])
    check("b. a fallen is a loss of more than $25; a -$11 break-even scratch is not one", js["lossMin"] == [True, False, False], js["lossMin"])
    check("b. the week starts on Monday (Wed and Sun stay in it, the next Monday starts a new one)", js["wk"] == ["2026-10-26", "2026-10-26", "2026-10-26", "2026-11-02"], js["wk"])
    check("b. stop beyond the sweep extreme: a SHORT stop at the high is flagged, 1 tick above is not; a LONG stop 1 tick under the low is fine, above it is flagged",
          js["s"] == [["stopinside"], [], [], ["stopinside"], []] and "1 tick beyond" in js["s2row"], (js["s"], js["s2row"]))
    check("b. no sweep on the site = 'Not recorded', never a guess, never a flag", js["s5row"]["st"] == "na" and js["s5row"]["text"].startswith("Not recorded"), js["s5row"])
    check("b. the entry hours (02:00-15:30 New York): 01:40 and 16:00 are flagged, 03:00 is not", js["w"] == [["window"], ["window"], []], js["w"])
    check("b. break-even at 1R: 1.2R then a full stop-out is flagged, 0.9R is not", js["b"] == [["nobe"], []], js["b"])
    check("b. one trade a day: the second trade of a day is flagged (the first is not)", js["d2"] == [[], ["second"]] or js["d2"] == [["second"]], js["d2"])
    check("b. after two losses: the third loss in a row is flagged, a win in between resets it",
          [x for x in js["st"]] == [[], [], ["streak"], [], []] or js["st"] == [[], [], ["streak"], []], js["st"])
    check("b. the room replay by hand: a fresh 50K has $2,000 of room, +$1,000 keeps it at $2,000, +$1,500 more locks the floor at $50,100 and gives $2,400", js["rr"] == [2000, 2000, 2400], js["rr"])
    z = js["z"]
    check("b. size: $800 at $2,000 of room is heavy (a soft flag costing only the part above a third), $1,700 is past the bot's 80% (hard), 8 micros against a twin of 4 is oversize (hard), 4 against 8 is fine",
          z[0][0]["id"] == "oversize" and not z[0][0].get("hard") and abs(z[0][0]["cost"] - 800 * (1 - 0.35 / 0.4)) < 1 and z[1][0]["hard"] is True and z[2][0]["hard"] is True and z[3] == []
          and js["zv"] == ["PLAN, WITH A LEAK", "RULE BREAK", "RULE BREAK", "PLAN LOSS"] and "Smaller than the bot" in js["z4row"], (z, js["zv"], js["z4row"]))
    check("b. the Zenith journal tags (day_entryEpoch): 'Late entry' becomes the late leak and is shown; a tag on another trade changes nothing; 'Would skip' maps to its leak only on a match",
          js["tg"] == [["late"], ["Late entry", "Lesson"]] and js["tg2"] == [[], []] and js["tagRead"][0] == {} and js["tagRead"][1] == {} and js["tagRead"][2] == {"a_b": ["x"]}, (js["tg"], js["tg2"], js["tagRead"]))
    rk = js["lk"]
    check("b. the weekly ranking: leaks sorted by their $ cost, a plain plan loss is counted apart (not a leak), the total is the losses added up",
          rk["rank"][0][0] in ("stopinside", "oversize") and rk["rank"] == sorted(rk["rank"], key=lambda r: -r[2]) and rk["lost"] == 1100
          and [r[0] for r in rk["rank"]] == ["stopinside", "oversize"] and rk["plan"] == {"n": 1, "cost": 100}, rk)
    check("b. verdicts and the one lesson: a clean stop-out is a PLAN LOSS (amber) with a 'five in a row' sizing lesson; a missed break-even is a RULE BREAK (crimson) with the vow as its lesson",
          js["verdict"][:2] == ["PLAN LOSS", "plan"] and js["verdict"][2:4] == ["RULE BREAK", "break"] and js["verdict"][4:] == ["soft", "break"]
          and "five of these in a row" in js["lesson"][0] and js["lesson"][1].startswith("Next time"), (js["verdict"], js["lesson"]))
    check("b. the Obsidian texts: a lesson note and a week note with the vow as a ticked checkbox and tags; an empty week says so",
          js["ob"].startswith("### Nemesis autopsy: 2026-10-26") and "- Lesson:" in js["ob"] and "#nemesis" in js["ob"] and "- [x] Vow: I wait." in js["obw"] and "#weekly-review" in js["obw"]
          and "Biggest leak: none" in js["obw0"], (js["ob"], js["obw"]))
    check("b. another strategy (EMA) is not judged by the LIT rules; the plain week sentences", js["other"] == "Other strategy" and js["plainWeek"][0].startswith("No fallen") and "Every loss followed the plan" in js["plainWeek"][1], (js["other"], js["plainWeek"]))
    check("b. the real trades (demo copy): 60 rows become 58 setups, 26 fallen newest last; the weeks are newest first",
          js["demoN"] == 58 and js["demoF"] == 26 and js["weeks"][0]["wk"] == "2026-10-26" and js["weeks"][0]["wk"] > js["weeks"][1]["wk"], (js["demoN"], js["demoF"], js["weeks"]))


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
    shutil.copytree(PAGE, os.path.join(site, "nemesis"))
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

CLIP_STUB = "window.__copied = []; try { Object.defineProperty(navigator, 'clipboard', { value: { writeText: (t) => { window.__copied.push(String(t)); return Promise.resolve(); } }, configurable: true }); } catch (e) {}"


def run_browser():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="le_nem_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/nemesis/"
    outside, posts = [], []
    shots = os.environ.get("NEM_SHOTS")
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=False, quality="low", vw=(390, 844), init=None):
                ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=1, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
                if quality:
                    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")
                ctx.add_init_script(CLIP_STUB)
                for s in init or []:
                    ctx.add_init_script(s)

                def guard(route):
                    u = route.request.url
                    if route.request.method != "GET":
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

            def ready(p, url=base):
                p.goto(url)
                p.wait_for_function("document.body.dataset.ready === '1' && window.NEM && NEM.state().scene && NEM.state().scene.drawn > 0", timeout=180000)

            st = lambda p: p.evaluate("NEM.state()")  # noqa: E731
            # the software GL here draws about one frame a second, which makes Playwright's "is it stable" wait very slow: UI buttons get a plain click event (the 3D tap below is a real mouse click)
            tap = lambda p, sel: p.locator(sel).dispatch_event("click")  # noqa: E731

            make_site(tmp)
            ctx, p = page()
            ready(p)
            s = st(p)
            fl = p.evaluate("NEM.fallen()")
            check("c. loads on the chosen LITE tier: real mode (no DEMO), 58 setups, 26 fallen, the newest week chosen, 2 passes (scene + finish), one figure per fallen, no errors",
                  not s["demo"] and s["n"] == 58 and s["fallen"] == 26 and s["week"] == "2026-10-26" and s["scene"]["quality"] == "low" and s["scene"]["passes"] == 2
                  and s["scene"]["figures"] == 26 and not p.errs and p.is_visible("#lite") and not p.is_visible("#demo"), (s["scene"], p.errs))
            t = p.inner_text("#verdict")
            check("c. the summary in plain words: the week, 2 fallen, -$1,264 lost, the biggest leak, the live eval line (balance, floor, room)",
                  s["inWeek"] == 2 and p.inner_text("#tFallen") == "2" and p.inner_text("#tLost") == "-$1,264" and "Oct 26 - Nov 1" in t and "Biggest leak: Heavy size" in t
                  and "Your live eval now: balance $52,171, floor $50,100, room $2,071" in t, t)
            check("c. the week bar names the week and counts it; Older is on, Newer is off at the newest week", p.inner_text("#wkLabel") == "Oct 26 - Nov 1" and "2 fallen of" in p.inner_text("#wkSub")
                  and not p.is_disabled("#wkPrev") and p.is_disabled("#wkNext"), (p.inner_text("#wkLabel"), p.inner_text("#wkSub")))
            ov = p.evaluate(GEOM)
            check("c. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not ov, ov)
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "nemesis-home.png"))
            # a real tap on a figure of this week: the raycast picks it and the autopsy opens
            target = next(f for f in fl if f["wk"] == "2026-10-26" and f["day"] == "2026-10-28")
            pos = p.evaluate("(id) => NEM.screenOf(id)", target["id"])
            check("c. the figure of the week sits on screen in the open arena, not under a panel", pos and pos["on"] and 250 < pos["y"] < 640 and 20 < pos["x"] < 370, pos)
            p.mouse.click(pos["x"], pos["y"])
            p.wait_for_function("NEM.state().view === 'autopsy'")
            s = st(p)
            check("c. a real tap on the 3D figure opens ITS autopsy (the raycast picked the right one), the figure is marked, the camera drifts to it", s["sel"] == target["id"] and s["scene"]["selected"] == target["id"], (s["sel"], target["id"]))
            body = p.inner_text("#sheetBody")
            check("c. the autopsy answers in plain words: plan or rule break, the stop, the size against the room, the time of day, the twin, what happened, habits, one lesson",
                  p.locator(".rows li").count() == 7 and all(x in body for x in ("PLAN OR RULE BREAK?", "STOP BEYOND THE SWEEP EXTREME?", "SIZE AGAINST THE ROOM", "TIME OF DAY", "WHAT THE TWIN / BACKTEST SAYS", "WHAT HAPPENED", "HABITS", "ONE LESSON"))
                  and "Not recorded: the site has no sweep extreme for this trade (the stop is 29987.5, 42.5 pts from the entry)" in body and "the bot's twin took 8" in body and "Smaller than the bot" in body and "03:43" in body, body[:600])
            check("c. the verdict badge and who took it: your real trade, plan with a flag (heavy size, 37% of the room), a lesson written", "PLAN, WITH A LEAK" in body and "Your trade on the 50K (real)" in body and "heavy size" in body and p.locator(".lesson p").inner_text().startswith("Next time"), body[:300])
            ov = p.evaluate(GEOM)
            check("c. the autopsy sheet: inside the gutters, out of the orb's corner, no sideways scroll", not ov, ov)
            if shots:
                p.screenshot(path=os.path.join(shots, "nemesis-autopsy.png"))
            tap(p, "#copyLesson")
            p.wait_for_function("window.__copied.length === 1")
            cp = p.evaluate("window.__copied[0]")
            check("c. Copy for Obsidian puts the formatted lesson on the clipboard (heading, verdict, lesson, #nemesis tag); nothing else happens", cp.startswith("### Nemesis autopsy: 2026-10-28 03:43 ET SHORT LIT -$437") and "- Lesson: " in cp and "#nemesis" in cp, cp)
            tap(p, "#olderF")
            p.wait_for_function("NEM.state().sel !== " + json.dumps(target["id"]))
            check("c. Older moves to the previous fallen and re-aims the camera", st(p)["sel"] != target["id"] and st(p)["scene"]["selected"] == st(p)["sel"])
            tap(p, "#toList")
            p.wait_for_function("NEM.state().view === 'fallen' && NEM.state().sel === null")
            check("c. the Fallen list shows this week's two losses, newest first, each with its colour dot and amount", p.locator(".list button").count() == 2 and p.locator(".list .amt").first.inner_text() == "-$437", p.locator(".list").inner_text())
            p.locator(".list button").nth(1).dispatch_event("click")
            p.wait_for_function("NEM.state().view === 'autopsy'")
            check("c. a tap in the list opens the same autopsy (the paper loss, an oversize-for-the-room flag, not a rule break)", "-$827" in p.inner_text("#sheetTitle") and "PLAN, WITH A LEAK" in p.inner_text("#sheetBody"))
            # the week stepper
            tap(p, "#close")
            tap(p, "#wkPrev")
            s = st(p)
            check("c. the week stepper goes to the week before and re-lights the figures (the other weeks dim), the summary follows", s["week"] == "2026-10-19" and p.inner_text("#wkLabel") == "Oct 19 - 25" and s["scene"]["bright"] == s["inWeek"] and s["sel"] is None, (s["week"], s["scene"]["bright"], s["inWeek"]))
            tap(p, "#wkAll")
            s = st(p)
            check("c. All shows every fallen (26) and every figure lit; the arrows are off", s["all"] and s["inWeek"] == 26 and s["scene"]["bright"] == 26 and p.is_disabled("#wkPrev") and p.inner_text("#tFallen") == "26")
            tap(p, "[data-view=leaks]")
            p.wait_for_timeout(300)
            lt = p.inner_text("#sheetBody")
            check("c. the Leaks sheet ranks the leaks with the $ each cost (biggest first), counts plan losses apart and says what the cost means",
                  p.locator(".leaklist li").count() >= 2 and "Plan losses:" in lt and "Trading after 2 losses" in lt and re.search(r"-\$\d", p.locator(".leaklist .cost").first.inner_text())
                  and "price of the edge, not a leak" in lt and "counts under each" in lt, lt[:500])
            costs = [int(x.replace("-$", "").replace(",", "")) for x in p.locator(".leaklist .cost").all_inner_texts()]
            check("c. the ranking is sorted by $ cost", costs == sorted(costs, reverse=True) and len(costs) >= 2, costs)
            if shots:
                p.screenshot(path=os.path.join(shots, "nemesis-leaks.png"))
            ov = p.evaluate(GEOM)
            check("c. the Leaks sheet stays inside the gutters and out of the orb's corner", not ov, ov)
            p.locator(".leaklist .mini").first.dispatch_event("click")
            p.wait_for_function("NEM.state().view === 'vow'")
            vtxt = p.inner_text("#sheetBody")
            check("c. 'Make it my vow' opens the Vow sheet with the vow in plain words, a tick box and the week note button", "I kept this vow" in vtxt and p.locator(".vowbox p").inner_text().strip() != "" and p.is_visible("#copyWeek") and not p.is_checked("#vowTick"), vtxt[:300])
            vow_text = p.locator(".vowbox p").inner_text()
            tap(p, "#vowTick")
            wk = st(p)["week"]
            stored = p.evaluate("JSON.parse(localStorage.getItem('nemesis.v1'))")
            check("c. ticking the vow is kept in the page's localStorage only (nemesis.v1: week, leak, text, done)", stored["vows"][wk]["done"] is True and stored["vows"][wk]["text"] == vow_text and stored["vows"][wk]["leak"], stored)
            tap(p, "#copyWeek")
            p.wait_for_function("window.__copied.length === 2")
            cw = p.evaluate("window.__copied[1]")
            check("c. Copy week note formats the week for Obsidian: fallen, biggest leak, the ticked vow, every lesson, tags", cw.startswith("## Nemesis: week of 2026-10-") and "- [x] Vow: " + vow_text in cw and "### Lessons" in cw and "#weekly-review" in cw, cw[:400])
            if shots:
                p.screenshot(path=os.path.join(shots, "nemesis-vow.png"))
            ov = p.evaluate(GEOM)
            check("c. the Vow sheet stays inside the gutters and out of the orb's corner", not ov, ov)
            tap(p, "[data-view=about]")
            at = p.inner_text("#sheetBody")
            check("c. About is honest: manual trades are not on the site, the room is an estimate, 'heavy' is a rule of thumb, read-only", all(x in at for x in ("trades you place by hand are not on the site", "estimate", "rule of thumb", "Read-only")) and not p.evaluate(GEOM), at[:300])
            p.keyboard.press("Escape")
            check("c. Escape closes the sheet", not p.is_visible("#sheet"))
            p.reload()
            p.wait_for_function("document.body.dataset.ready === '1'", timeout=180000)
            s3 = st(p)
            check("c. after a reload the vow is still ticked (kept on this phone)", s3["vows"].get(wk, {}).get("done") is True, s3["vows"])
            card = p.evaluate("NEM.card()")
            check("c. the card for Jarvis: 3 kpis (fallen, lost, top leak), <= 3 lines of <= 120 characters", len(card["kpis"]) == 3 and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]) and card["name"] == "Nemesis", card)
            ctx.close()

            # the Zenith journal tags: read from this phone, shown, and turned into a leak
            tags_init = "try { localStorage.setItem('le.jtags', JSON.stringify({ '2026-10-28_1793173380': ['Would skip', 'Late entry'], '2026-09-21_1': ['Lesson'] })); } catch (e) {}"
            ctx, p = page(init=[tags_init])
            ready(p)
            fl2 = p.evaluate("NEM.fallen()")
            real = next(f for f in fl2 if f["day"] == "2026-10-28")
            check("c. the journal tags on this phone become leaks of that trade ('Would skip', 'Late entry'); nothing else changes", {"skip", "late"} <= set(real["flags"]), real)
            p.evaluate("(id) => NEM.pick(id)", real["id"])
            p.wait_for_function("NEM.state().view === 'autopsy'")
            body = p.inner_text("#sheetBody")
            check("c. ...and the autopsy shows your own tags and the entry-time note", "Your journal tags: Would skip, Late entry" in body and "late entry in the journal" in body, body[-700:])
            check("c. the journal key is only read: le.jtags is unchanged and no other key is written", p.evaluate("Object.keys(localStorage).filter((k) => !['jfx', 'le.jtags'].includes(k)).length") <= 1, p.evaluate("Object.keys(localStorage)"))
            ctx.close()

            make_site(tmp, with_odeon=False, with_home=False)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. no site files: the recorded copy (DEMO badge, 58 setups, 26 fallen), still no errors", s["demo"] and p.is_visible("#demo") and s["n"] == 58 and s["fallen"] == 26 and not p.errs, (s["demo"], s["n"], p.errs))
            ctx.close()

            make_site(tmp)
            ctx, p = page(reduced=True)
            ready(p)
            before = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1500)
            after = st(p)["scene"]["drawn"]
            check("c. reduced motion: a still scene (no frames while nothing changes), no errors", after - before <= 1 and not p.errs, (before, after, p.errs))
            tap(p, "#wkPrev")
            p.wait_for_timeout(1200)
            check("c. ...and a change redraws it", st(p)["scene"]["drawn"] > after)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. nothing left the machine: no request to any other origin and no POST / PUT of any kind", not outside and not posts, (outside[:3], posts[:3]))


def main():
    part_a()
    part_b()
    if os.environ.get("NEM_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
