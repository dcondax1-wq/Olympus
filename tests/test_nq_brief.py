"""BRIEF ME + SUNLIGHT MODE (tools/web_public/nq/briefcore.js, briefme.js, sun.css; night-nq-main 2026-11-27). Node only (+ a Chromium
check when node's playwright is installed), ~3 s.
  a. static: briefme.js is code-split (nq.js adds it at idle / on the first tap, never a page tag); briefcore is pure + Safari-16 safe;
     sun.css is not render-blocking when off (media query link), the head script reads localStorage in try/catch + prefers-contrast: more;
     sun.css has no glow / blur left, never cyan; both hero buttons are real <button>s with aria-pressed
  b. words: the hero model -> "as of 12 minutes ago" (counted to the tap), today's $, each account's $ to pass / payout + room, LIT / ATLAS,
     next session, a warning on low room / an old report; no report = an honest line, no numbers; demo says example numbers; ~20 s (<= 80 words)
  c. voice: the best English voice (neural / natural > known good > en-US), novelty voices never, no English = null
  d. browser (Chromium, a stub speechSynthesis): nothing speaks on load; a tap speaks each sentence, the button says Stop; a 2nd tap stops;
     Sunlight on -> html.sun, saved '1', still on after a reload, glow gone; off -> '0'
    python -X utf8 -m tests.test_nq_brief
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
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    core, js, css, html, nqjs = (read(os.path.join(NQ, n)) for n in ("briefcore.js", "briefme.js", "sun.css", "index.html", "nq.js"))
    check("a. briefme.js is code-split (nq.js adds it at idle or on the first tap; no page tag)",
          'src="briefme.js' not in html and "./briefme.js?v=" in nqjs and "NQ_BRIEF_ASK" in nqjs and "NQ_BRIEF_ASK" in js)
    check("a. briefcore.js is pure and Safari-16 safe (no document / window / fetch / storage / speech / lookbehind / .at())",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage|speechSynthesis|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. briefme.js: text only (no innerHTML / eval / dynamic import); speaks only inside toggle() (no speak at module load)",
          not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(", js) and js.count("SS.speak(") == 1
          and re.search(r"async function start\(\)[\s\S]*SS\.speak\(", js))
    check("a. sun.css: a media-query link (not render-blocking when off) + the head script (localStorage in try/catch, prefers-contrast: more)",
          re.search(r'<link rel="stylesheet" href="sun\.css\?v=\d+" id="sunCss" media="\(prefers-contrast: more\)">', html)
          and re.search(r"try \{ v = localStorage\.getItem\('nq\.sun'\); \} catch", html) and "matchMedia('(prefers-contrast: more)')" in html)
    body = re.sub(r"/\*[\s\S]*?\*/", "", css)
    check("a. sun.css: scoped to html.sun, kills glow + blur (the kit's token names --nq-cyan* are violet in nqtheme.css), never cyan / brown / olive",
          all(r.strip().startswith("html.sun") for r in re.findall(r"(?:^|})\s*([^{}@]+)\{", body)) and "text-shadow:none!important" in body
          and "backdrop-filter:none!important" in body and "box-shadow:none!important" in body
          and not re.search(r"#(0ff|00ffff|22d3ee|06b6d4|67e8f9)\b|cyan|olive|brown", re.sub(r"--nq-cyan(-hi)?", "", body), re.I))
    check("a. the hero has both buttons (aria-pressed, >= 44 px) and the caption",
          re.search(r'<button type="button" class="btn hx-tool" id="hxBrief" aria-pressed="false"', html)
          and re.search(r'<button type="button" class="btn hx-tool" id="hxSun" aria-pressed="false"', html) and 'id="hxBriefText"' in html
          and "min-height:44px;min-width:44px" in read(os.path.join(NQ, "nqhero.css")))


JS = r"""
import(process.argv[1]).then((P) => {
  const o = {}, now = 1764225000;
  const H = { today: 240.4, nowS: now - 120, ageS: 600, level: 'ok', demo: false, next: { label: 'London open', inS: 1620 },
    accts: [{ name: 'Zlarior', has: true, goalBig: '$1,850', goalUnit: 'to pass', room: 1600, roomFrac: 0.8 },
            { name: 'ATLAS', has: true, goalBig: '$1,200', goalUnit: 'to $2,100', room: 250, roomFrac: 0.25 },
            { name: 'Fresh 25K', has: false }],
    bots: [{ name: 'LIT', word: 'SETUP ARMED', side: 'long', line: 'Buy above 21,050.25 · stop 21,020. More text here.', ageS: 600 },
           { name: 'ATLAS', word: 'WATCHING', line: 'Waiting for its setup.', ageS: 3000 }] };
  o.full = P.briefText(H, now);
  o.none = P.briefText({ today: null, ageS: null, level: 'bad', accts: [{ name: 'Zlarior', has: false }], bots: [], next: { label: 'CME reopens Sunday 18:00 ET', inS: null } }, now);
  o.demo = P.briefText({ ...H, demo: true }, now);
  o.old = P.briefText({ ...H, ageS: 3 * 3600, level: 'bad' }, now);
  o.ago = [30, 120, 600, 5400, 7200, 3 * 86400, null].map(P.agoWords);
  o.junk = [null, 1, 'x', [], {}].map((j) => { try { P.briefText(j, now); P.pickVoice(j); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  const V = [{ name: 'Fred', lang: 'en-US' }, { name: 'Bad News', lang: 'en-US' }, { name: 'Google UK English Male', lang: 'en-GB' },
             { name: 'Microsoft Aria Online (Natural) - English (United States)', lang: 'en-US' }, { name: 'Thomas', lang: 'fr-FR' }];
  o.voice = [P.pickVoice(V).name, P.pickVoice(V.slice(0, 3)).name, P.pickVoice([V[0], V[1]]).name, P.pickVoice([V[4]])];
  console.log(JSON.stringify(o));
});
"""


def core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "-e", JS, "file://" + os.path.join(NQ, "briefcore.js")], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    t = o["full"]["text"]
    check("b. the age is counted to the tap (600 s + 120 s = 'as of 12 minutes ago'), today 'up $240 across 2 accounts'",
          t.startswith("Olympus brief, as of 12 minutes ago.") and "Today: up $240 across 2 accounts." in t, t)
    check("b. each account with numbers: its $ to pass / payout + room; one with none is not read",
          "Zlarior: $1,850 to pass, $1,600 of room." in t and "ATLAS: $1,200 to $2,100, $250 of room." in t and "Fresh 25K" not in t, t)
    check("b. LIT armed long + its trigger's first sentence (spoken words: no '·'); ATLAS watching, its report 52 minutes old; next London in 25 minutes",
          "LIT: setup armed long, Buy above 21,050.25, stop 21,020." in t and "ATLAS: watching, its report is 52 minutes old." in t
          and "Next: London open in 25 minutes." in t, t)
    check("b. warning: ATLAS's low room; ~20 s (<= 80 words)", "Warning: ATLAS has only $250 of room left." in t and o["full"]["words"] <= 80, (t, o["full"]["words"]))
    check("b. no report: an honest line, no $ at all", "has not reported yet" in o["none"]["text"] and "$" not in o["none"]["text"]
          and "Next: CME reopens Sunday 18:00 Eastern." in o["none"]["text"], o["none"])
    check("b. demo: 'example numbers, not your accounts', no stale warning", "example numbers, not your accounts" in o["demo"]["text"]
          and "out of date" not in o["demo"]["text"], o["demo"])
    check("b. a 3-hour-old report: 'as of 3 hours ago' + a warning that the numbers may be out of date",
          "as of 3 hours ago" in o["old"]["text"] and "the PC report is 3 hours old, so these numbers may be out of date" in o["old"]["text"], o["old"])
    check("b. ages in words", o["ago"] == ["just now", "2 minutes ago", "10 minutes ago", "2 hours ago", "2 hours ago", "3 days ago", ""], o["ago"])
    check("b/c. junk never throws", all(j == "ok" for j in o["junk"]), o["junk"])
    check("c. voice: natural/neural first, then a known good one, novelty never, no English -> null",
          o["voice"][0].startswith("Microsoft Aria Online") and o["voice"][1] == "Google UK English Male" and o["voice"][2] == "Fred" and o["voice"][3] is None, o["voice"])


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1];
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' };
(async () => {
  const b = await chromium.launch(), ctx = await b.newContext({ viewport: { width: 390, height: 844 } }), o = {};
  await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
    const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
    return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
  await ctx.addInitScript(() => { window.__said = []; const SS = { speaking: false, getVoices: () => [{ name: 'Google US English', lang: 'en-US' }],
      speak(u) { if (!u.text) return; window.__said.push(u.text); setTimeout(() => { u.onstart && u.onstart(); }, 5); }, cancel() { window.__said.push('#cancel'); },
      addEventListener() {} };
    Object.defineProperty(window, 'speechSynthesis', { value: SS }); window.SpeechSynthesisUtterance = function (t) { this.text = t; }; });
  const p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('http://site.local/nq/index.html?demo=1', { waitUntil: 'load' }); await p.waitForTimeout(3000);
  o.load = await p.evaluate(() => window.__said.slice());
  await p.click('#hxBrief'); await p.waitForTimeout(1200);
  o.on = await p.evaluate(() => ({ said: window.__said.filter((s) => s !== '#cancel'), btn: document.querySelector('#hxBrief .hx-tl').textContent,
    pressed: document.getElementById('hxBrief').getAttribute('aria-pressed'), cap: !document.getElementById('hxBriefText').hidden }));
  await p.click('#hxBrief'); await p.waitForTimeout(200);
  o.off = await p.evaluate(() => ({ btn: document.querySelector('#hxBrief .hx-tl').textContent, cancels: window.__said.filter((s) => s === '#cancel').length }));
  const box = await p.evaluate(() => ['hxBrief', 'hxSun'].map((i) => { const r = document.getElementById(i).getBoundingClientRect(); return [r.width, r.height]; }));
  o.box = box;
  await p.click('#hxSun'); await p.waitForTimeout(200);
  o.sun = await p.evaluate(() => ({ cls: document.documentElement.classList.contains('sun'), saved: localStorage.getItem('nq.sun'), media: document.getElementById('sunCss').media,
    glow: getComputedStyle(document.querySelector('.hx-acc') || document.body).boxShadow, sw: document.documentElement.scrollWidth - innerWidth }));
  await p.reload({ waitUntil: 'load' }); await p.waitForTimeout(800);
  o.reload = await p.evaluate(() => [document.documentElement.classList.contains('sun'), document.getElementById('hxSun').getAttribute('aria-pressed')]);
  await p.click('#hxSun'); await p.waitForTimeout(200);
  o.off2 = await p.evaluate(() => [document.documentElement.classList.contains('sun'), localStorage.getItem('nq.sun')]);
  o.errs = errs; console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("d. browser check skipped: no node playwright", True)
        return
    r = subprocess.run([exe, "-e", BROWSER, WEB], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("d. the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("d. the browser harness runs", False, o["fail"])
        return
    check("d. nothing speaks on load (never autoplays)", o["load"] == [], o["load"])
    check("d. a tap: every sentence spoken (starts 'Olympus brief'), the button says Stop + aria-pressed, the caption shows",
          len(o["on"]["said"]) >= 3 and o["on"]["said"][0].startswith("Olympus brief") and o["on"]["btn"] == "Stop" and o["on"]["pressed"] == "true" and o["on"]["cap"], o["on"])
    check("d. a 2nd tap stops (cancel) and the button says Brief me", o["off"]["btn"] == "Brief me" and o["off"]["cancels"] >= 2, o["off"])
    check("d. both buttons >= 44 px", all(w >= 44 and h >= 44 for w, h in o["box"]), o["box"])
    check("d. Sunlight: html.sun, saved '1', sun.css on, glow gone, no sideways scroll",
          o["sun"]["cls"] and o["sun"]["saved"] == "1" and o["sun"]["media"] == "all" and o["sun"]["glow"] in ("none", "") and o["sun"]["sw"] <= 0, o["sun"])
    check("d. still on after a reload (applied before paint), off -> saved '0'", o["reload"] == [True, "true"] and o["off2"] == [False, "0"], (o["reload"], o["off2"]))
    check("d. no page errors", not o["errs"], o["errs"])


if __name__ == "__main__":
    static()
    core()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
