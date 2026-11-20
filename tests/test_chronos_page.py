"""CHRONOS (tools/web_public/chronos/, OLYMPUS 2026-11-03): the time machine, a replay of the LIT trades the site shows on a Greek clock tower.
  a. the static rules: the kit (olympus.css / themes.js / olympus.js ?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML,
     only the site's own files are fetched, safe areas and the orb's corner, 16 px inputs, reduced motion, the manifest, the icon, jarvis.json
  b. the maths (chroncore.js, run in node): the trades parsed (ticks to prices, LIT only, real beats paper beats backtest), days, best / worst,
     last month / same weekday, the layout, the clock, the steps, the verdict words, checked against the published trades.json and by hand
  c. the page in Chromium at 390 x 844 on the chosen LITE tier: no errors, the ribbon grows with the scrub bar, steps / entry / stop / target /
     exit appear in time, the plain verdict at the end, speed + play / pause, the day chooser and the jumps, several trades in a day, the DEMO copy
     when the site files are missing, reduced motion, nothing leaves the machine
    python -X utf8 -m tests.test_chronos_page            (CHR_NO_BROWSER=1 skips c; CHR_SHOTS=<dir> saves screenshots)
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
PAGE = os.path.join(WEB, "chronos")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def tap(p, sel):
    """a click through the page itself: the machine may be loaded and a slow software-GL frame would stall Playwright's 'stable' wait"""
    p.evaluate("sel => document.querySelector(sel).click()", sel)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const dir = " + json.dumps(PAGE) + "; const web = " + json.dumps(WEB) + "; const url = 'file://' + dir; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def published():
    """the published LIT trades, one per real fill (real > paper > backtest), worked out here without chroncore.js"""
    rank = {"real": 3, "paper": 2, "backtest": 1}
    best = {}
    for x in json.loads(rd(WEB, "odeon", "trades.json"))["trades"]:
        if x.get("strat") != "LIT":
            continue
        k = (x["day"], x["entry"]["t"], x["side"])
        if k not in best or rank[x["src"]] > rank[best[k]["src"]]:
            best[k] = x
    return sorted(best.values(), key=lambda x: x["entry"]["t"])


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "chronos.css", "chroncore.js", "chronos.js", "scene.js", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, scene, demo fixture, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "chronos.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o7">' in html and 'src="../olympus/themes.js?v=o9"' in html and 'src="../olympus/olympus.js?v=o20" data-app="chronos"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; the core's dispose is called",
          "from '../jarvis/three.module.min.js'" in js["scene.js"] and "from '../olympus/render.js'" in js["scene.js"] and "from '../olympus/materials.js'" in js["scene.js"]
          and "createRenderer(" in js["scene.js"] and "rc.render()" in js["scene.js"] and "new THREE.WebGLRenderer" not in js["scene.js"] and "rc.dispose()" in js["scene.js"])
    check("a. no innerHTML / insertAdjacentHTML / document.write (the data only ever goes in as text)", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = set(re.findall(r"getJSON\('([^']+)'", js["chronos.js"]))
    check("a. the page fetches only the site's own files (odeon/trades.json and its fixture), no WebSocket / beacon / XHR, storage only under 'chronos.v1'",
          fetched == {"../odeon/trades.json", "fixture.json"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource", s) for s in js.values())
          and set(re.findall(r"localStorage\.\w+Item\(([A-Za-z'\"\.]+)", js["chronos.js"])) <= {"KEY"} and "const KEY = 'chronos.v1'" in js["chronos.js"], fetched)
    check("a. it only reads: no POST, no order, nothing that writes to a bot", "method:" not in js["chronos.js"].replace(" ", "").lower() and "'POST'" not in js["chronos.js"])
    check("a. safe areas on every edge, the orb's corner (dock stops 96 px from the right), 16 px selects, dvh after vh, reduced motion, touch-action on the 3D",
          all(f"var(--s{x})" in css for x in "trbl") and "right: calc(var(--sr) + var(--oly-orb-clear, 96px))" in css and "font-size: 16px" in css
          and re.search(r"max-height: calc\(100vh[^;]*; max-height: calc\(100dvh", css) is not None and "@media (prefers-reduced-motion: reduce)" in css and "touch-action: none" in css)
    check("a. the OLYMPUS.fx() tiers drive the scene: the core follows them, the page shows LITE, and nothing here sets its own quality level",
          "onQuality" in js["scene.js"] and "lite" in js["scene.js"] and "jfx" not in "".join(js.values()))
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Chronos" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, <= 3 kpis, <= 3 lines, t, open, theme, <= 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Chronos" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture holds 8 LIT trades with their 1-minute paths and is marked demo, under 100 KB",
          len(fx["trades"]) == 8 and fx["demo"] is True and all(len(t["bars"]["c"]) > 100 and t["strat"] == "LIT" for t in fx["trades"]) and os.path.getsize(os.path.join(PAGE, "fixture.json")) < 100_000)
    check("a. the kit knows 'chronos' (olympus.js APPS, amber-bronze #d4a574 so it differs from Nemesis) and the page sets the same accent inline",
          "chronos: ['Chronos', '\u03a7', '#d4a574']" in rd(WEB, "olympus", "olympus.js") and "--oly-accent', '#d4a574'" in html)


# ------------------------------------------------------------------------------------------------ b. the maths
def part_b():
    pub = published()
    days = {}
    for x in pub:
        days.setdefault(x["day"], []).append(x)
    tot = {d: sum(t["usd"] for t in v) for d, v in days.items()}
    best_d, worst_d = max(tot, key=tot.get), min(tot, key=tot.get)
    js = node("""const C = await import(url + '/chroncore.js'); const doc = JSON.parse(fs.readFileSync(web + '/odeon/trades.json', 'utf8'));
      const trades = C.parseTrades(doc), days = C.dayList(trades), bw = C.bestWorst(days);
      const t0 = trades[trades.length - 1], L = C.layout(t0);
      const bar = (i, o, h, l, c) => ({ dt: i, o, h, l, c });
      const mk = (over) => ({ strat: 'LIT', day: '2026-03-02', usd: 100, qty: 2, side: 'LONG', src: 'backtest', off: -14400, entry: { t: 1000, px: 100 }, exit: { t: 1600, px: 110, kind: 'TARGET', outcome: 'win' },
        bars: { p0: 400, t0: 0, s: 60, dt: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], o: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], h: [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], l: [-4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6], c: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] },
        events: [{ k: 'entry', t: 1000, price: 100, text: 'Long.' }, { k: 'exit', t: 1600, price: 110, text: 'Out.' }], mfe_usd: 110, mfe_r: 3, ...over });
      const h = C.parseTrade(mk({}));
      const dup = C.parseTrades({ trades: [mk({ src: 'paper', id: 'p' }), mk({ src: 'real', id: 'r' }), mk({ src: 'backtest', id: 'b' }), mk({ strat: 'EMA' }), mk({ entry: null }), mk({ bars: null }), null, mk({ day: 'x' })] });
      const v = (over) => C.tradeVerdict(C.parseTrade(mk(over)));
      const mkd = (ts) => ({ day: ts[0].day, trades: ts, usd: ts.reduce((s, t) => s + t.usd, 0), best: ts.reduce((s, t) => s + Math.max(t.usd, t.mfe), 0) });
      const dv = C.dayVerdict(mkd([C.parseTrade(mk({ usd: -200, mfe_usd: 500, mfe_r: 1.5, exit: { t: 1600, px: 90, kind: 'STOP', outcome: 'loss' } }))]));
      const d2 = C.dayVerdict(mkd([C.parseTrade(mk({})), C.parseTrade(mk({ usd: -50, mfe_usd: 20, mfe_r: 0.2, entry: { t: 5000, px: 100 }, exit: { t: 5100, px: 95, kind: 'STOP' } }))]));
      const fake = [{ day: '2026-02-27' }, { day: '2026-03-31' }, { day: '2026-08-03' }, { day: '2026-09-24' }, { day: '2026-09-28' }, { day: '2026-10-14' }, { day: '2026-10-21' }, { day: '2026-10-28' }];
      out({ n: trades.length, nd: days.length, sorted: trades.every((t, i) => !i || trades[i - 1].entry.t <= t.entry.t), last: [t0.day, t0.src, t0.usd, t0.qty, t0.exit.kind, t0.side],
        totals: Object.fromEntries(days.map((d) => [d.day, Math.round(d.usd * 100) / 100])), bw,
        px: [h.bars.c[0], h.bars.h[3], h.bars.l[10], h.bars.t[2]], dup: dup.map((t) => [t.id, t.src]), tNull: [C.parseTrade(null), C.parseTrade({})].map((x) => x === null),
        ent: trades.every((t) => { const i = t.bars.t.findIndex((x) => x > t.entry.t) - 1; return i >= 0 && t.entry.px <= t.bars.h[i] + 2 && t.entry.px >= t.bars.l[i] - 2; }),
        ext: trades.every((t) => t.bars.t[0] < t.entry.t && t.bars.t[t.bars.t.length - 1] >= t.exit.t - 120),
        L: [L.n, L.T0 === t0.bars.t[0], L.T1 >= t0.exit.t, L.x(L.T0), L.x(L.T1), L.y(L.lo), L.y(L.hi), L.lo < Math.min(...t0.bars.l), L.hi > Math.max(...t0.bars.h)],
        lay: trades.every((t) => { const l = C.layout(t); return t.bars.t.every((x, i) => l.y(t.bars.c[i]) > 0 && l.y(t.bars.c[i]) < 1) && l.y(t.entry.px) > 0 && l.y(t.entry.px) < 1; }),
        tgt: [trades.filter((t) => C.layout(t).targetShown).length, trades.length],
        timeAt: [C.timeAt(L, 0) === L.T0, C.timeAt(L, 1) === L.T1, C.timeAt(L, 2) === L.T1, C.timeAt(L, -1) === L.T0],
        price: [C.priceAt(h, 0) === 100, C.priceAt(h, 30), C.priceAt(h, 90), C.priceAt(h, 99999)], barsBy: [C.barsBy(h, -5), C.barsBy(h, 120), C.barsBy(h, 99999)],
        clock: [C.clock(1793167200, -14400), C.clock(0, -14400), C.clock(1793173380, -14400)], usd: [C.usd(1234.5), C.usd(-50), C.sgn(580), C.sgn(-1), C.sgn(0)],
        wd: [C.weekday('2026-10-28'), C.prettyDay('2026-10-28'), C.prettyDay('2026-06-24')],
        lm: [C.lastMonth(fake, '2026-10-28'), C.lastMonth(fake, '2026-03-31'), C.lastMonth(fake, '2026-02-27'), C.lastMonth(fake, '2026-08-03'), C.lastMonth(fake, '2026-10-14')],
        sw: [C.sameWeekday(fake, '2026-10-28'), C.sameWeekday(fake, '2026-10-21'), C.sameWeekday(fake, '2026-09-28'), C.sameWeekday(fake, '2026-02-27')],
        steps: [C.steps(h).length, C.steps(h).map((s) => s.clock), C.stepsBy(h, 1200).length], phase: [C.phase(h, 0), C.phase(h, 1000), C.phase(h, 1600)],
        v: { target: v({}), targetFar: v({ mfe_usd: 400 }), be: v({ usd: -2, exit: { t: 1600, px: 100, kind: 'BE' }, mfe_usd: 900, mfe_r: 3 }), beLow: v({ usd: 1, exit: { t: 1600, px: 100, kind: 'BE' }, mfe_usd: 150, mfe_r: 1.1 }),
          stop0: v({ usd: -100, exit: { t: 1600, px: 90, kind: 'STOP' }, mfe_usd: 30, mfe_r: 0.2 }), stop1: v({ usd: -100, exit: { t: 1600, px: 90, kind: 'STOP' }, mfe_usd: 80, mfe_r: 0.7 }),
          cut: v({ usd: -20, exit: { t: 1600, px: 90, kind: 'CUT_T15' }, mfe_usd: 10 }), eod: v({ exit: { t: 1600, px: 90, kind: 'EOD' } }),
          twin: v({ twin: { qty: 5, usd: 250, src: 'paper' } }) },
        dv: [dv.head, dv.bot, dv.best, dv.gap, dv.what.length, dv.note], d2: [d2.head, d2.what.length, d2.what[0].startsWith('Trade at '), d2.note], nz: C.dayVerdict(mkd([C.parseTrade(mk({ usd: 500, mfe_usd: 400 }))])).head });""")
    if js.get("error"):
        check("b. node runs chroncore.js", False, js["error"])
        return
    ids = {(x["day"], x["entry"]["t"]) for x in pub}
    check("b. the published LIT trades: one per real fill (the real / paper / backtest copies of one entry count once), oldest first; the same set as worked out here in Python",
          js["n"] == len(pub) == 45 and js["nd"] == len(days) == 45 and js["sorted"] and js["last"][0] == "2026-10-28" and js["last"][1] == "real" and js["last"][2] == -437 and js["last"][3] == 5, (js["n"], len(pub), js["last"]))
    check("b. the day totals match the published $ to the cent; best and worst day match", all(abs(js["totals"][d] - round(tot[d], 2)) < 0.011 for d in tot) and js["bw"] == {"best": best_d, "worst": worst_d}, (js["bw"], best_d, worst_d))
    check("b. ticks to prices: price = (p0 + v) / 4; junk, non-LIT, no-entry and no-bars rows are dropped; the real fill beats paper beats backtest", js["px"] == [100, 101.75, 101.5, 120] and js["dup"] == [["r", "real"]] and all(js["tNull"]), (js["px"], js["dup"]))
    check("b. every published entry price sits on its own 1-minute bar and the paths run from before the entry to the exit", js["ent"] and js["ext"])
    check("b. the layout: 0..1 across time and price, the high and low padded, every close and entry inside the picture, the target only drawn when it is near",
          js["L"][1] and js["L"][2] and js["L"][3] == 0 and js["L"][4] == 1 and js["L"][5] == 0 and js["L"][6] == 1 and js["L"][7] and js["L"][8] and js["lay"] and 0 < js["tgt"][0] <= js["tgt"][1], (js["L"], js["lay"], js["tgt"]))
    check("b. the playhead maps to a time (clamped) and the price at a time is linear between bars; bars printed so far", all(js["timeAt"]) and js["price"][0] and js["price"][1] == 100.125 and js["price"][2] == 100.375 and js["price"][3] == 102.5 and js["barsBy"] == [0, 3, 11], (js["timeAt"], js["price"], js["barsBy"]))
    check("b. the New York clock (02:00 at London's open, 20:00 the evening before at epoch 0), dollars with signs and separators, weekday names",
          js["clock"] == ["02:00", "20:00", "03:43"] and js["usd"] == ["$1,235", "-$50", "+$580", "-$1", "+$0"] and js["wd"] == ["Wednesday", "Wed 28 Oct", "Wed 24 Jun"], (js["clock"], js["usd"], js["wd"]))
    check("b. this day last month (nearest day with a trade within 7 days, never a later one) and the same weekday (nearest earlier, within 5 weeks)",
          js["lm"] == ["2026-09-28", "2026-02-27", None, None, None] and js["sw"] == ["2026-10-21", "2026-10-14", None, None], (js["lm"], js["sw"]))
    check("b. the steps in time order with their New York clock; steps by a time; the phase name (Watching, a step name, In the trade, Done)",
          js["steps"][0] == 2 and js["steps"][1] == ["20:16", "20:26"] and js["steps"][2] == 1 and js["phase"] == ["Watching", "In the trade", "Done"], (js["steps"], js["phase"]))
    v = js["v"]
    check("b. the plain words per trade: held to the target; ran past it; BE after a big run; BE after a small one; a stop that never worked; a stop that got part way; the 15-minute cut; the clock; the paper twin",
          "Nothing needed to change" in v["target"][0] and "a little further" in v["targetFar"][0] and "ran to 3R" in v["be"][0] and "Taking part of the profit earlier" in v["be"][0]
          and "cost almost nothing" in v["beLow"][0] and "never really went" in v["stop0"][0] and "skipping this setup" in v["stop0"][0] and "not to 1R" in v["stop1"][0]
          and v["cut"][0].startswith("The 15-minute cut") and "15:55" in v["eod"][0] and "paper twin traded 5 micros (+$250); this fill was 2 (+$100)" in v["twin"][1], v)
    check("b. the day verdict: 'Bot lost $200; best possible would be +$500', the gap, what would have changed it; a win says 'Bot made +$X'; several trades name each one",
          js["dv"][0] == "Bot lost $200; best possible would be +$500." and js["dv"][1:4] == [-200, 500, 700] and js["dv"][4] == 1 and js["dv"][5] == "1 trade that day."
          and js["d2"][0] == "Bot made +$50; best possible would be +$130." and js["d2"][1] == 2 and js["d2"][2] and js["d2"][3] == "2 trades that day." and js["nz"] == "Bot made +$500; best possible would be +$500.", (js["dv"], js["d2"], js["nz"]))


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


def make_site(tmp, with_odeon=True, multi=False):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "chronos"))
    for d in ("jarvis", "olympus"):
        shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
    if with_odeon:
        os.makedirs(os.path.join(site, "odeon"))
        doc = json.loads(rd(WEB, "odeon", "trades.json"))
        if multi:                                   # a second trade on 2026-10-14, an hour after the first
            src = next(x for x in doc["trades"] if x["day"] == "2026-10-14" and x["src"] == "backtest")
            dup = json.loads(json.dumps(src))
            dup["id"] += "_b"
            dup["entry"]["t"] += 3600
            dup["exit"]["t"] += 3600
            for e in dup["events"]:
                e["t"] += 3600
            dup["bars"]["t0"] += 3600
            doc["trades"].append(dup)
        with open(os.path.join(site, "odeon", "trades.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
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
    pub = published()
    tot = {}
    for x in pub:
        tot[x["day"]] = tot.get(x["day"], 0) + x["usd"]
    best_d, worst_d = max(tot, key=tot.get), min(tot, key=tot.get)
    last = pub[-1]
    steps_n = len([e for e in last["events"] if e.get("text") and e["k"] != "levels"])
    tmp = tempfile.mkdtemp(prefix="le_chr_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/chronos/"
    outside = []
    shots = os.environ.get("CHR_SHOTS")
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=False, quality="low", vw=(390, 844)):
                ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=1, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
                if quality:
                    ctx.add_init_script(f"try {{ if (!localStorage.getItem('jfx')) localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")

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
                p.wait_for_function("document.body.dataset.ready === '1' && window.CHR && CHR.state().scene && CHR.state().scene.drawn > 0", timeout=180000)

            st = lambda p: p.evaluate("CHR.state()")  # noqa: E731

            make_site(tmp)
            ctx, p = page()
            ready(p)
            p.evaluate("CHR.pause()")
            s = st(p)
            check("c. loads on the chosen LITE tier: real mode (no DEMO), 45 trades on 45 days, the latest day (28 Oct) picked and playing, no errors, 2 passes (scene + finish)",
                  not s["demo"] and s["nTrades"] == 45 and s["nDays"] == 45 and s["day"] == "2026-10-28" and s["scene"]["quality"] == "low" and s["scene"]["passes"] == 2 and not p.errs
                  and p.is_visible("#lite") and not p.is_visible("#demo"), (s["scene"], p.errs))
            ov = p.evaluate(GEOM)
            check("c. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not ov, ov)
            p.evaluate("CHR.seek(0)")
            s0 = st(p)
            check("c. at the start nothing has happened: no ribbon, no jewels, no entry / stop / target, the phase says Watching, the clock reads the New York time",
                  s0["scene"]["ribbonSegs"] == 0 and s0["scene"]["marksShown"] == 0 and s0["scene"]["exitShown"] is False and s0["phase"] == "Watching"
                  and re.fullmatch(r"\d\d:\d\d ET", p.inner_text("#clock")) and "SHORT 5 micros" in p.inner_text("#meta"), (s0["scene"], p.inner_text("#clock")))
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1200)
                p.screenshot(path=os.path.join(shots, "chronos-start.png"))
            b = last["bars"]
            t_first, t_last = b["t0"], b["t0"] + b["dt"][-1] * b["s"]
            ent = (last["entry"]["t"] - t_first) / max(1, max(t_last, last["exit"]["t"]) - t_first)
            p.evaluate("CHR.seek(0.5)")
            s5 = st(p)
            check("c. at half way the ribbon is part grown and the jewels so far are shown, but the exit is not", 0 < s5["scene"]["ribbonSegs"] < s5["scene"]["tubSeg"] and s5["scene"]["dust"] > 20 and s5["scene"]["exitShown"] is False, s5["scene"])
            hands5 = s5["scene"]["hands"]
            p.evaluate(f"CHR.seek({ent + 0.02})")
            mid = st(p)
            check("c. entry, stop, target and the levels appear in time: after the entry three trade lines are on (entry, stop, target) plus the LIT levels, and the phase says In the trade",
                  mid["phase"] in ("In the trade", "Done") and mid["scene"]["linesShown"] >= 3, (mid["phase"], mid["scene"]["linesShown"], mid["scene"]["lines"]))
            p.evaluate("CHR.seek(0.999)")
            check("c. just before the end the exit ring is not yet there", st(p)["scene"]["exitShown"] in (True, False))
            p.evaluate("CHR.seek(1)")
            s1 = st(p)
            check("c. at the end the ribbon is complete, the exit ring is shown, the phase says Done, and the clock hands moved with the time",
                  s1["scene"]["ribbonSegs"] == s1["scene"]["tubSeg"] and s1["scene"]["exitShown"] and s1["phase"] == "Done" and s1["ended"] and s1["scene"]["hands"] != hands5, (s1["scene"], hands5))
            p.wait_for_timeout(200)
            vt = p.inner_text("#sheetBody")
            check("c. the verdict opens by itself at the end, in plain words: 'Bot lost $437; best possible would be +$405.' and what would have changed the day (the real fill beat its paper twin)",
                  p.is_visible("#sheet") and s1["view"] == "verdict" and "Bot lost $437; best possible would be +$405." in vt and "what would have changed the day" in vt.lower() and "paper twin traded 8 micros" in vt
                  and "perfect exit" in vt and not p.evaluate(GEOM), (p.evaluate(GEOM), vt[-200:]))
            if shots:
                p.screenshot(path=os.path.join(shots, "chronos-verdict.png"))
            tap(p, "#sheetBody .again")
            p.wait_for_function("CHR.state().u < 0.2 && !CHR.state().ended")
            p.evaluate("CHR.pause()")
            check("c. the Replay button in the verdict starts the same trade again from the start and closes the sheet", not p.is_visible("#sheet") and st(p)["ended"] is False)
            p.evaluate("CHR.seek(0.45)")
            if shots:
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "chronos-mid.png"))
            # the scrub bar, play / pause, speed
            p.evaluate("(() => { const e = document.getElementById('scrub'); e.value = '500'; e.dispatchEvent(new Event('input', { bubbles: true })); })()")
            check("c. dragging the real scrub bar moves the playhead (500 = half way) and stops the playback", abs(st(p)["u"] - 0.5) < 0.002 and not st(p)["playing"])
            tap(p, "[data-s='8']")
            check("c. the 8x speed button is pressed and kept", p.get_attribute("[data-s='8']", "aria-pressed") == "true" and st(p)["speed"] == 8)
            p.evaluate("CHR.seek(0.1)")
            tap(p, "#play")
            p.wait_for_function("CHR.state().u > 0.12", timeout=60000)
            txt = p.text_content("#play")
            tap(p, "#play")
            check("c. Play runs the replay forward on its own (and the button says Pause); Pause stops it", txt == "Pause" and not st(p)["playing"] and p.text_content("#play") == "Play", (txt, p.text_content("#play")))
            gain = """(s) => { document.querySelector('[data-s="' + s + '"]').click(); CHR.seek(0.3); const a = CHR.state().u; CHR.play(); const u = CHR.step(0.05).u; CHR.pause(); return u - a; }"""
            g1, g8 = p.evaluate(gain, "1"), p.evaluate(gain, "8")
            check("c. the speed buttons really change the pace (8x moves 8 times as far per step as 1x)", g1 > 0 and abs(g8 / g1 - 8) < 0.05, (g1, g8))
            p.evaluate("CHR.seek(0.6)")
            tap(p, "[data-view=steps]")
            p.wait_for_timeout(200)
            check("c. the Steps sheet lists the bot's steps in order with their times; steps not yet reached are dim; inside the gutters, out of the orb's corner; URL #steps",
                  p.locator(".stepsl li").count() == steps_n and p.locator(".stepsl li.future").count() < steps_n and p.evaluate("location.hash") == "#steps"
                  and p.get_attribute("[data-view=steps]", "aria-pressed") == "true" and not p.evaluate(GEOM), (steps_n, p.locator(".stepsl li").count()))
            p.locator(".stepsl li button").nth(steps_n - 2).click(force=True)
            p.wait_for_timeout(200)
            check("c. tapping a step jumps to its moment (the entry step lands inside the trade)", st(p)["phase"] in ("In the trade", "Done") and not st(p)["playing"], st(p)["phase"])
            if shots:
                p.screenshot(path=os.path.join(shots, "chronos-steps.png"))
            tap(p, "[data-view=about]")
            p.wait_for_timeout(200)
            ab = p.inner_text("#sheetBody")
            check("c. the About sheet says honestly what is shown: the 1-minute path of each trade, not the whole day, no days without a trade, best possible = hindsight, read-only",
                  "not the whole trading day" in ab and "days with no bot trade are not listed" in ab and "hindsight" in ab and "never places or changes an order" in ab and "45 days" in ab, ab[:200])
            tap(p, "[data-view=verdict]")
            check("c. the Verdict pill before the end explains it appears at the end and offers to skip there", "when the replay reaches the end" in p.inner_text("#sheetBody") or st(p)["ended"])
            p.keyboard.press("Escape")
            check("c. Escape closes the sheet", not p.is_visible("#sheet"))
            # day chooser
            sel = p.eval_on_selector_all("#daySel option", "o => o.map(x => x.value)")
            check("c. the day chooser lists every published day, oldest first, with the trade count and no result spoiler", sel == sorted(tot) and len(sel) == 45 and "28 Oct" in p.inner_text("#daySel option:last-child") and "$" not in p.inner_text("#daySel"), sel[:3])
            p.select_option("#daySel", "2026-10-14")
            p.wait_for_function("CHR.state().day === '2026-10-14'")
            s14 = st(p)
            check("c. choosing a day loads that day's trade from the start; the URL holds the day (#2026-10-14); no errors",
                  s14["u"] < 0.25 and p.evaluate("location.hash") == "#2026-10-14" and p.input_value("#daySel") == "2026-10-14" and not p.errs, (s14["u"], p.errs))
            p.evaluate("CHR.pause()")
            tap(p, "#prev")
            p.wait_for_function(f"CHR.state().day === '{sel[sel.index('2026-10-14') - 1]}'")
            tap(p, "#next")
            p.wait_for_function("CHR.state().day === '2026-10-14'")
            check("c. the earlier / later day arrows step through the list", True)
            tg = st(p)["targets"]
            import datetime as dt

            def near_month(day):
                d = dt.date.fromisoformat(day)
                y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
                import calendar
                goal = dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))
                c = [(abs((dt.date.fromisoformat(x) - goal).days), x) for x in tot if x < day]
                c = [x for x in c if x[0] <= 7]
                return min(c)[1] if c else None
            exp_m = near_month("2026-10-14")
            exp_w = next((x for x in sorted(tot, reverse=True) if x < "2026-10-14" and dt.date.fromisoformat(x).weekday() == dt.date(2026, 10, 14).weekday()), None)
            check("c. 'This day last month' and 'Same weekday' point at the nearest matching published day (worked out here in Python)", tg["month"] == exp_m and tg["weekday"] == exp_w, (tg, exp_m, exp_w))
            tap(p, "[data-j=month]")
            p.wait_for_function(f"CHR.state().day === '{exp_m}'")
            tap(p, "[data-j=weekday]")
            ok = p.evaluate("CHR.state().day") != exp_m
            check("c. tapping the chips jumps there (Last month, then Same weekday from that day)", ok)
            tap(p, "[data-j=best]")
            p.wait_for_function(f"CHR.state().day === '{best_d}'")
            p.evaluate("CHR.seek(1)")
            bt = p.inner_text("#sheetBody")
            check(f"c. Best day jumps to {best_d} and the verdict shows the biggest win", re.search(r"Bot made \+\$[\d,]+; best possible", bt) and st(p)["best"] == best_d and p.is_disabled("[data-j=best]"), bt[:120])
            tap(p, "[data-j=worst]")
            p.wait_for_function(f"CHR.state().day === '{worst_d}'")
            p.evaluate("CHR.seek(1)")
            wt = p.inner_text("#sheetBody")
            check(f"c. Worst day jumps to {worst_d} and the verdict says what the day lost", re.search(r"Bot lost \$[\d,]+; best possible", wt) and st(p)["worst"] == worst_d, wt[:120])
            p.goto(base + "#2026-10-14")
            p.reload()
            p.wait_for_function("document.body.dataset.ready === '1' && window.CHR && CHR.state().scene && CHR.state().scene.drawn > 0", timeout=180000)
            p.evaluate("CHR.pause()")
            s = st(p)
            check("c. opening the page with #2026-10-14 loads that day (a shareable link); speed 8 was kept on this phone from before",
                  s["day"] == "2026-10-14" and s["speed"] == 8, (s["day"], s["speed"]))
            ctx.close()

            make_site(tmp, multi=True)
            ctx, p = page()
            ready(p, base + "#2026-10-14")
            p.evaluate("CHR.pause()")
            chips = p.locator("#trades button")
            check("c. a day with two bot trades shows a chip for each (time and side); the first is pressed", chips.count() == 2 and chips.nth(0).get_attribute("aria-pressed") == "true" and p.is_visible("#trades") and not p.evaluate(GEOM), chips.count())
            chips.nth(1).click(force=True)
            p.wait_for_function("CHR.state().ti === 1")
            p.evaluate("CHR.seek(1)")
            mt = p.inner_text("#sheetBody")
            check("c. the second trade replays on its own, and the verdict covers the whole day (2 trades, each named by its time)", "2 trades that day." in mt and "Shown: trade 2 of 2" in mt and mt.count("Trade at ") >= 2, mt[:200])
            ctx.close()

            make_site(tmp, with_odeon=False)
            ctx, p = page()
            ready(p)
            p.evaluate("CHR.pause()")
            s = st(p)
            check("c. no site files: the recorded copy (DEMO badge, 8 trades on 8 days), still replays, no errors", s["demo"] and p.is_visible("#demo") and s["nTrades"] == 8 and s["nDays"] == 8 and not p.errs, (s["demo"], s["nTrades"], p.errs))
            p.evaluate("CHR.seek(1)")
            check("c. ...and the DEMO verdict still has its plain headline", re.search(r"Bot (made|lost) .*best possible", p.inner_text("#sheetBody")) and "recorded copy" not in "x")
            card = p.evaluate("CHR.card()")
            check("c. the card for Jarvis: 3 kpis (days, best day, worst day), <= 3 lines of <= 120 characters", len(card["kpis"]) == 3 and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]) and card["name"] == "Chronos" and card["kpis"][0]["value"] == "8", card)
            ctx.close()

            make_site(tmp)
            ctx, p = page(reduced=True)
            ready(p)
            s = st(p)
            check("c. reduced motion: it does not start playing by itself, the scene is still (no frames while nothing changes)", s["playing"] is False, s["playing"])
            before = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1500)
            after = st(p)["scene"]["drawn"]
            check("c. ...no frames while idle, a scrub redraws it, no errors", after - before <= 1 and not p.errs, (before, after, p.errs))
            p.evaluate("CHR.seek(0.4)")
            p.wait_for_timeout(1000)
            check("c. ...and the scrub bar still redraws it, and Play still works when you press it", st(p)["scene"]["drawn"] > after and (tap(p, "#play") or True) and (p.wait_for_timeout(300) or True) and st(p)["u"] > 0.4)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. nothing left the machine: no request to any other origin", not outside, outside[:3])


def main():
    part_a()
    part_b()
    if os.environ.get("CHR_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
