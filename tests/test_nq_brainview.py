"""THE STRATEGY BRAINS (tools/web_public/nq/brainviewcore.js + brainview.js + brainview.css + brains.js + brains.html; day-brains 2026-11-27).
Node + Chromium (node playwright; skipped without it), ~15 s. Fixture: the real 2026-11-27 post + a "bx" block from engine/brain_xray on the
replayed Nov 20 brain + an "ofp" / "ab" sample (tests/fixtures/brains/post_bx_2026-11-27.json).
  a. static: brainviewcore pure + Safari-16 safe; brainview.js exports mount (+ STRATS), text only, its own CSS from import.meta.url, no
     position:fixed; brains.html loads pc_feed.js + brains.js + nqnav, lifts the Olympus veil; CSS: no cyan, no font under 12 px, taps >= 44 px
  b. LIT: the 9-gate pipeline lit by the PC's stage (Displacement 4/10 = now), the sweep 4.66 ATR vs >= 0.5 ATR (56.9 pts) on the forming long,
     an hours-old rejected setup NOT painted on the pipeline (a note points to Skipped), Skipped today with the plain why + the number,
     the next trade 4 micros / $376 risk / $3,805 at target, room $1,009, health (report age, program, armed, brain numbers age)
  c. a fresh rejected setup (within 30 min) IS painted: inducement 0 / 1 red, the stop 196.5 pts red
  d. ATLAS: per lobe window -> checks (value, need) -> armed -> trade; EMA armed SHORT 26,380.75 (6 micros, $78); S/R's failing check red;
     account B's skip + why; BLITZ (paper): band ready -> break now; POSEIDON (paper): levels / touched 2 of 3 / 1 absorbed / 1 taken / +2.00R
  e. no "bx" = the stages from the glance + an honest note; no post at all = an honest line; an unknown strategy = said so; junk never throws
  f. browser: brains.html at 390 (one brain + 4 chips >= 44 px) and 1440 (4 brains), no text < 12 px, no sideways scroll, no errors;
     mount() into a bare host: draws, setStrategy() switches, destroy() empties it
    python -X utf8 -m tests.test_nq_brainview
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
NQ = os.path.join(WEB, "nq")
FIX = os.path.join(ROOT, "tests", "fixtures", "brains", "post_bx_2026-11-27.json")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:800]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    core, js, css, page, bz = (read(os.path.join(NQ, n)) for n in ("brainviewcore.js", "brainview.js", "brainview.css", "brains.html", "brains.js"))
    check("a. brainviewcore.js pure + Safari-16 safe (no document / window / fetch / storage / lookbehind / .at())",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. brainview.js: exports mount + STRATS, text only (no innerHTML / eval / import()), its own CSS from import.meta.url, no position:fixed",
          "export function mount(host, opts)" in js and "export { STRATS }" in js and not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(", js)
          and "new URL('./brainview.css?v=" in js and "fixed" not in css and "destroy()" in js and "setStrategy(" in js)
    check("a. brains.html: pc_feed.js + brains.js + nqnav.js; brains.js lifts the veil (OLYMPUS.ready) and shares ONE post read (getState)",
          "../pc_feed.js" in page and 'src="brains.js?v=' in page and "nqnav.js" in page and "O.ready()" in bz and "getState: () =>" in bz)
    check("a. CSS: OLYMPUS NIGHT (no cyan / brown / olive), no font under 12 px, taps >= 44 px",
          not re.search(r"cyan|olive|brown|#0ff\b|#22d3ee", css + page, re.I) and not [x for x in re.findall(r"font-size:(\d+(?:\.\d+)?)px", css + page) if float(x) < 12]
          and "min-height:44px" in page)


JS = r"""
import(process.argv[1]).then((B) => {
  const fs = require('fs'), P = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), o = {}, now = P.t + 120;
  const pick = (m) => ({ flow: m.flow.map((f) => [f.key, f.state, f.value, f.rule, f.from || '']), now: m.now, skipped: m.skipped, skippedN: m.skippedN, risk: m.risk, health: m.health, notes: m.notes, mode: m.mode, levels: m.levels, thoughts: m.thoughts.length, name: m.name, summary: m.summary });
  o.lit = pick(B.brain('lit', { lite: P }, now));
  const F = JSON.parse(JSON.stringify(P)); F.bx.t = Date.parse('2026-11-27T21:05:00Z') / 1000;      // 16:05 ET: the 15:50 setup is fresh
  o.fresh = pick(B.brain('lit', { lite: F }, F.bx.t + 60));
  o.atlas = pick(B.brain('atlas', { lite: P }, now)); o.blitz = pick(B.brain('blitz', { lite: P }, now)); o.pos = pick(B.brain('poseidon', { lite: P }, now));
  const N = JSON.parse(JSON.stringify(P)); delete N.bx; o.nobx = pick(B.brain('lit', { lite: N }, now));
  o.none = pick(B.brain('lit', {}, now)); o.zzz = B.brain('zzz', { lite: P }, now).notes;
  o.junk = [null, 1, 'x', [], {}, { lite: 5 }, { lite: { bx: { lit: { s: [[1, 2]], w: [5] } }, pc: { glance: { bots: 3 } } } }].map((j) => { try { for (const s of ['lit', 'atlas', 'blitz', 'poseidon']) B.brain(s, j, now); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  console.log(JSON.stringify(o));
});
"""


def core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "-e", JS, "file://" + os.path.join(NQ, "brainviewcore.js"), FIX], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    L = o["lit"]
    fl = {f[0]: f for f in L["flow"]}
    check("b. LIT: 9 gates, levels / sweep / inducement passed, displacement NOW (the PC's stage 4/10), the rest waiting",
          [f[0] for f in L["flow"]] == ["levels", "sweep", "inducement", "displacement", "cisd5", "limit", "cisd1m", "entry", "trade"]
          and [f[1] for f in L["flow"]] == ["pass", "pass", "pass", "now", "wait", "wait", "wait", "wait", "wait"], L["flow"])
    check("b. the sweep gate: 4.66 ATR on the forming long vs the rule 'depth >= 0.5 ATR (56.9 pts)'",
          fl["sweep"][2] == "4.66 ATR" and fl["sweep"][3] == "depth >= 0.5 ATR (56.9 pts)" and fl["sweep"][4] == "forming long", fl["sweep"])
    check("b. the hours-old 15:50 rejected setup is not painted; a note points to Skipped today",
          not any(f[1] == "fail" for f in L["flow"]) and any("15:50 long" in n and "Skipped today" in n for n in L["notes"]), (L["flow"], L["notes"]))
    check("b. Skipped today: 13:20 LONG 'the sweep was too shallow (0.39 / 0.5 ATR)', 15:50 outside its hours; '9 setups today, 0 blocked'",
          L["skipped"][0]["hm"] == "13:20" and L["skipped"][0]["why"].startswith("the sweep was too shallow (0.39 / 0.5 ATR)") and "outside its entry hours" in L["skipped"][1]["why"]
          and L["skippedN"] == "9 setups today, 0 blocked", L["skipped"])
    rk = {r["k"]: r["v"] for r in L["risk"]}
    check("b. risk: next trade 4 micros, $376 at risk, $3,805 at target, room $1,009", rk.get("Next trade") == "4 micros" and rk.get("$ at risk") == "$376"
          and rk.get("$ at target") == "$3,805" and rk.get("Room left") == "$1,009", L["risk"])
    hk = {h["k"]: (h["v"], h["lv"]) for h in L["health"]}
    check("b. health: report 2 min ago (ok), program running, on + armed, brain numbers 12 min ago",
          hk.get("PC report") == ("2 min ago", "ok") and hk.get("Bot program") == ("running", "ok") and hk.get("On / armed") == ("on · armed", "ok") and hk.get("Brain numbers", ("",))[0] == "12 min ago", L["health"])
    ff = {f[0]: f for f in o["fresh"]["flow"]}
    check("c. a fresh rejected setup IS painted: inducement 0 / 1 red, stop 196.5 pts red (with the target 9.1R / 1.5R), from '15:50 long setup'",
          ff["inducement"][1:3] == ["fail", "0 / 1"] and ff["limit"][1] == "fail" and "9.1R / 1.5R" in ff["limit"][2] and ff["sweep"][4] == "15:50 long setup", o["fresh"]["flow"])
    A = o["atlas"]
    ak = [f[0] for f in A["flow"]]
    check("d. ATLAS: EMA window -> 3 checks -> armed (SHORT 26,380.75) -> trade, then S/R with its failing 'Yesterday's RTH high swept' red",
          ak[:6] == ["EMA:window", "EMA:Entry 02:00-05:00 ET", "EMA:15m EMA 21 vs 50 with the trade", "EMA:Pullback reached the 5m EMA 50", "EMA:armed", "EMA:trade"]
          and A["flow"][4][1] == "now" and A["flow"][4][2] == "SHORT 26,380.75" and any(f[0].startswith("S/R:Yesterday") and f[1] == "fail" and f[2] == "no" for f in A["flow"]), A["flow"])
    check("d. ATLAS now: 'EMA is armed: SHORT at 26,380.75, stop 26,419.50, target 26,122.75'; armed plan 6 micros / $78; account B's skip + why",
          A["now"]["line"].startswith("EMA is armed: SHORT at 26,380.75") and any(r["v"] == "6 micros" and "$78" in r["sub"] for r in A["risk"])
          and A["skipped"][0]["why"].startswith("LIT was in a trade") and A["skippedN"] == "1 skipped today on its account", (A["now"], A["risk"], A["skipped"]))
    check("d. BLITZ (paper): band ready passed, the break NOW, paper trade waiting, money PAPER",
          [f[1] for f in o["blitz"]["flow"]] == ["pass", "now", "wait"] and o["blitz"]["mode"] == "PAPER" and o["blitz"]["risk"][0]["v"] == "PAPER", o["blitz"])
    p = [f[2] for f in o["pos"]["flow"]]
    check("d. POSEIDON (paper): 3 watched, 2 of 3 touched, 1 absorbed, 1 taken 1 skipped, +2.00R today; PDH 'absorbed (a trap: fade it)'",
          p == ["3 watched", "2 of 3", "1 absorbed", "1 taken, 1 skipped", "+2.00R today"] and o["pos"]["levels"][0]["text"] == "absorbed (a trap: fade it)", (p, o["pos"]["levels"]))
    check("e. no bx: the stages still from the glance + the honest note; no post: an honest first line; unknown strategy said so; junk never throws",
          [f[1] for f in o["nobx"]["flow"]][:4] == ["pass", "pass", "pass", "now"] and any('"bx" block' in n for n in o["nobx"]["notes"])
          and o["none"]["notes"][0].startswith("No PC report on this page yet") and o["zzz"] == ['No strategy called "zzz".'] and all(j == "ok" for j in o["junk"]), (o["nobx"]["notes"], o["none"]["notes"], o["junk"]))


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1], P = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
const now = Math.floor(Date.now() / 1000), sh = now - 120 - P.t; P.t += sh; P.bx.t += sh;
const stub = `window.PC_FEED={fetchLatest:async()=>(${JSON.stringify(P)})};`;
(async () => {
  const b = await chromium.launch(), o = {};
  const ctxOf = async (w, h) => { const ctx = await b.newContext({ viewport: { width: w, height: h } });
    await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
      if (u.pathname === '/pc_feed.js') return r.fulfill({ status: 200, body: stub, contentType: 'text/javascript' });
      if (u.pathname === '/nq/bare.html') return r.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><meta charset=utf-8><body style="background:#000"><div id=host style="width:340px"></div><script src="../pc_feed.js"></script></body>' });
      const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
      return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
    return ctx; };
  for (const [w, h, k] of [[390, 844, 'phone'], [1440, 900, 'desk']]) {
    const ctx = await ctxOf(w, h), p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('http://site.local/nq/brains.html?s=atlas', { waitUntil: 'load' });
    await p.waitForFunction(() => document.querySelectorAll('.bv-node').length > 10, null, { timeout: 15000 }).catch(() => {});
    o[k] = await p.evaluate(() => ({ shown: [...document.querySelectorAll('.bz-card')].filter((a) => getComputedStyle(a).display !== 'none').map((a) => a.dataset.s),
      chips: [...document.querySelectorAll('.bz-chip')].filter((c) => getComputedStyle(c).display !== 'none' && c.offsetParent).map((c) => [c.textContent, Math.round(c.getBoundingClientRect().height), c.getAttribute('aria-pressed')]),
      veil: document.documentElement.getAttribute('data-oly-state'), sw: document.documentElement.scrollWidth - innerWidth,
      small: [...document.querySelectorAll('.bv *')].filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).length }));
    o[k].errs = errs; await ctx.close();
  }
  const ctx = await ctxOf(390, 844), p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('http://site.local/nq/bare.html', { waitUntil: 'load' });
  o.mount = await p.evaluate(async () => {
    const M = await import('./brainview.js?v=1'), host = document.getElementById('host');
    const h = M.mount(host, { s: 'lit' }); await new Promise((r) => setTimeout(r, 800));
    const a = [host.querySelector('.bv-name') && host.querySelector('.bv-name').textContent, host.querySelectorAll('.bv-node').length];
    h.setStrategy('poseidon'); const b2 = [host.querySelector('.bv-name').textContent, host.querySelectorAll('.bv-node').length];
    h.destroy(); return [a, b2, host.childNodes.length, !!document.querySelector('link[data-brainview]')];
  });
  o.mount.push(errs); await ctx.close();
  console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("f. browser check skipped: no node playwright", True)
        return
    r = subprocess.run([exe, "-e", BROWSER, WEB, FIX], capture_output=True, text=True, timeout=150)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("f. the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("f. the browser harness runs", False, o["fail"])
        return
    ph, dk = o["phone"], o["desk"]
    check("f. 390: one brain (ATLAS from ?s=atlas), 4 chips >= 44 px with ATLAS pressed, the veil lifted, >= 12 px, no sideways scroll, no errors",
          ph["shown"] == ["atlas"] and len(ph["chips"]) == 4 and all(c[1] >= 44 for c in ph["chips"]) and ["ATLAS", ph["chips"][1][1], "true"] == ph["chips"][1]
          and ph["veil"] == "ready" and ph["small"] == 0 and ph["sw"] <= 0 and not ph["errs"], ph)
    check("f. 1440: all 4 brains, no chips, no sideways scroll, no errors", dk["shown"] == ["lit", "atlas", "blitz", "poseidon"] and not dk["chips"] and dk["sw"] <= 0 and not dk["errs"], dk)
    m = o["mount"]
    check("f. mount() into a bare host (the post via PC_FEED): LIT with 9 gates, setStrategy -> POSEIDON 5 gates, destroy() empties the host; its CSS loaded once",
          m[0] == ["LIT", 9] and m[1] == ["POSEIDON", 5] and m[2] == 0 and m[3] is True and not m[4], m)


if __name__ == "__main__":
    static()
    core()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
