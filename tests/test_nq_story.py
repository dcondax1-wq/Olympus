"""TODAY'S STORY (tools/web_public/nq/storycore.js + story.js + story.css + story.html; day-nqports 2026-11-27). Node + Chromium, ~15 s.
  a. static: story.js code-split on nq/ (nq.js adds it at idle: the hero line), story.css non-blocking, storycore pure + Safari-16 safe,
     text only, reads only published files / the PC's posts; story.html loads pc_feed.js + story.js; the hero slot + the card + a jump link
  b. past day (the replay of Thu Nov 26 + Wed Nov 25 for the prior levels): Asia took the prior day's high 20:25, the Asia range (439 pts vs
     normal 437), 7 stopped LIT setups each with a plain why ("no inducement (no small trap move ...)", "never came back to fill it"),
     the NY open, the 13:00 halt (the bars end early), the day in one line, what LIT worked on last; TWIN tags; the honest past-day note
  c. today from the PC's thought stream (real post 2026-11-27): a counted sweep (✓), a too-shallow sweep (✗ 0.18 ATR, needs 0.5) in plain
     words, stage changes only once, ATLAS's line; the CME halt LATER; "what LIT is waiting for now" without the "Before 02:00" prefix;
     no bars = the honest note; the hero line; real trades: entry + exit with $ and a plain reason, BLITZ / paper never
  d. snap: a mini chart only when the bars reach the moment; junk never throws
  e. browser: the nq/ card (demo: fills tagged DEMO, the hero's "Story so far"), story.html?day=2026-11-26 (12 moments), 390 px, >= 12 px,
     no sideways scroll, no page errors, the day chips >= 44 px
    python -X utf8 -m tests.test_nq_story
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
FIX = os.path.join(ROOT, "tests", "fixtures")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    core, js, css, html, nqjs, page = (read(os.path.join(NQ, n)) for n in ("storycore.js", "story.js", "story.css", "index.html", "nq.js", "story.html"))
    check("a. story.js code-split on nq/ (idle, for the hero line), story.css non-blocking, #storyCard + the hero slot + a jump link",
          'src="story.js' not in html and "./story.js?v=" in nqjs and re.search(r'story\.css\?v=\d+" media="print" onload=', html)
          and 'id="storyCard"' in html and 'data-hx="story"' in html and 'href="#storyCard"' in html)
    check("a. storycore pure + Safari-16 safe; story.js text only, reads ./ports.json, ./replay/index.json, ./replay/<day>.json, ../status_feed.json",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core))
          and not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(", js)
          and set(re.findall(r"get\('(\.{1,2}/[^']+)'\)", js)) == {"./ports.json", "./replay/index.json", "../status_feed.json"} and "`./replay/${day}.json`" in js)
    check("a. story.html: pc_feed.js + story.js + nqnav.js, the #storyPage section", "../pc_feed.js" in page and 'src="story.js?v=' in page and "nqnav.js" in page and 'id="storyPage"' in page)
    check("a. story.css: OLYMPUS NIGHT only, no font under 12 px, taps >= 44 px",
          not re.search(r"cyan|olive|brown|#0ff\b|#22d3ee", css, re.I) and not [x for x in re.findall(r"font-size:(\d+(?:\.\d+)?)px", css) if float(x) < 12] and css.count("min-height:44px") >= 2)


JS = r"""
import(process.argv[1]).then((S) => {
  const fs = require('fs'), F = process.argv[2], o = {};
  const R = JSON.parse(fs.readFileSync(F + '/story/2026-11-26.json', 'utf8')), Rp = JSON.parse(fs.readFileSync(F + '/story/2026-11-25.json', 'utf8'));
  let hi = -1e9, lo = 1e9; for (const b of Rp.bars) { hi = Math.max(hi, b[2]); lo = Math.min(lo, b[3]); }
  const past = S.build({ day: '2026-11-26', bars: R.bars, prior: { pdh: hi, pdl: lo }, normalAsia: 437, twin: R.events, trades: [] });
  o.past = { m: past.moments.map((m) => [m.hm, m.emoji, m.kind, m.tag || '', m.title, m.text]), waiting: past.waiting, note: past.note, line: S.storyLine(past) };
  const P = JSON.parse(fs.readFileSync(F + '/nq_home/real_post_2026-11-27.json', 'utf8'));
  const now = Date.parse('2026-11-27T05:00:00Z') / 1000;
  const live = S.build({ day: '2026-11-27', live: true, nowS: now, bars: [], glog: P.glog, halt: '13:15' });
  o.live = { m: live.moments.map((m) => [m.hm, m.emoji, m.kind, m.title, m.text, !!m.future]), waiting: live.waiting, note: live.note, line: S.storyLine(live) };
  const t0 = Date.parse('2026-11-27T14:30:00Z') / 1000;
  const tr = [{ acct: 'lit', src: 'live', side: 'LONG', qty: 2, entry: 26300.5, entry_t: t0, exit_t: t0 + 1800, exit: 'TARGET', usd: 812.4, open: false },
    { acct: 'atlas', src: 'live', member: 'EMA', side: 'SHORT', entry_t: t0 + 600, exit_t: t0 + 900, exit: 'STOP', usd: -112.8, open: false },
    { acct: 'blitz', src: 'live', side: 'LONG', entry_t: t0 }, { acct: 'lit', src: 'paper', side: 'LONG', entry_t: t0 + 60 }];
  const tt = S.build({ day: '2026-11-27', live: true, nowS: t0 + 3600, bars: [], trades: tr });
  o.trades = tt.moments.map((m) => [m.emoji, m.tag, m.title, m.text]);
  const bars = Array.from({ length: 40 }, (_, i) => [t0 + i * 300, 1, 2, 0, 1]);
  o.snap = [!!S.snap(bars, t0 + 3000, 1.5), S.snap(bars, t0 + 40 * 300 + 7200, null)];
  o.plain = S.plainThought('Displacement push 0.17 ATR; LIT needs 0.8').text;
  o.junk = [null, 1, 'x', [], {}].map((j) => { try { S.build(j); S.storyLine(j); S.snap(j, 1, null); S.plainThought(j); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  console.log(JSON.stringify(o));
});
"""


def core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "-e", JS, "file://" + os.path.join(NQ, "storycore.js"), FIX], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    m = o["past"]["m"]
    check("b. Thu Nov 26: Asia took the prior day's high at 20:25 (🌏), the Asia range 439 pts 'normal size (437 pts)'",
          m[0][:3] == ["20:25", "🌏", "sweep"] and "prior day's high" in m[0][4] and m[1][2] == "asia" and "439 pts, normal size (437 pts)" in m[1][5], m[:2])
    rej = [x for x in m if x[2] == "reject"]
    check("b. 7 stopped LIT setups, TWIN-tagged, each with a plain why (no inducement / never filled / displacement / sweep too shallow) and 'of 8'",
          len(rej) == 7 and all(x[3] == "TWIN" and x[5].startswith("Why: ") and " of 8" in x[4] for x in rej)
          and any("no small trap move" in x[5] for x in rej) and any("never came back to fill it" in x[5] for x in rej), rej)
    kinds = [x[2] for x in m]
    check("b. the NY open, the 13:00 halt (bars end early), the day in one line last; what LIT worked on last; the honest past-day note",
          "open" in kinds and any(x[2] == "halt" and "13:00" in x[4] for x in m) and kinds[-1] == "close" and "up 165 pts" in m[-1][5]
          and o["past"]["waiting"].startswith("its last setup:") and "not stored for past days" in o["past"]["note"], (kinds, o["past"]["waiting"], o["past"]["note"]))
    lv = o["live"]["m"]
    check("c. today's thoughts: the counted sweep of equal highs (👀 1.15 ATR), PDH 7.70 ATR, the too-shallow sweep in plain words (❌ 0.18 vs 0.5)",
          any(x[1] == "👀" and "1.15 ATR deep: deep enough" in x[4] for x in lv) and any("PDH 26,435.75 swept 7.70 ATR deep" in x[4] for x in lv)
          and any(x[1] == "❌" and "swept only 0.18 ATR deep; LIT needs 0.5 ATR" in x[4] for x in lv), lv)
    check("c. each stage once (Sweep, Displacement), ATLAS's line, the 13:15 halt LATER (future), no bars = the honest note",
          [x[3] for x in lv if x[2] == "stage"] == ["LIT stage: Sweep", "LIT stage: Displacement"] and any(x[2] == "atlas" for x in lv)
          and any(x[2] == "halt" and x[5] for x in lv) and o["live"]["note"].startswith("No bars from the PC's chart"), (lv, o["live"]["note"]))
    check("c. waiting = 'Short setup forming: ...' (no 'Before 02:00 ET' prefix); the hero line ends 'LIT now: Short setup forming'",
          o["live"]["waiting"].startswith("Short setup forming: swept equal highs") and o["live"]["line"].startswith("Story so far: ") and o["live"]["line"].endswith("LIT now: Short setup forming"), (o["live"]["waiting"], o["live"]["line"]))
    t = o["trades"]
    check("c. real trades: LIT 🟢 entered LONG 2 MNQ, ✅ hit its target +$812, ATLAS EMA 🛑 stopped -$113; REAL tags; BLITZ + paper never",
          [x[0] for x in t] == ["🟢", "🟢", "🛑", "✅"] and all(x[1] == "REAL" for x in t) and t[0][2] == "LIT entered LONG 2 MNQ" and "hit its target +$812" in t[3][2]
          and "was stopped out -$113" in t[2][2] and not any("BLITZ" in x[2].upper() for x in t) and len(t) == 4, t)
    check("d. snap: a mini chart near the bars, none 2 h past them; plain words for a weak push; junk never throws",
          o["snap"] == [True, None] and "plain: the push was 0.17 ATR, it needs 0.8" in o["plain"] and all(j == "ok" for j in o["junk"]), (o["snap"], o["plain"], o["junk"]))


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1];
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
(async () => {
  const b = await chromium.launch(), o = {};
  for (const [pg, q, k, sel] of [['index.html', '?demo=1', 'card', '#storyCard'], ['story.html', '?day=2026-11-26', 'page', '#storyPage']]) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
    await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
      const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
      return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
    const p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('http://site.local/nq/' + pg + q, { waitUntil: 'load' });
    await p.waitForFunction((s) => { const e = document.querySelector(s); return e && !e.hidden && e.querySelector('.st-head'); }, sel, { timeout: 15000 }).catch(() => {});
    await p.waitForTimeout(600);
    o[k] = await p.evaluate((s) => ({ n: document.querySelectorAll(s + ' .st-m').length, tags: [...document.querySelectorAll(s + ' .st-tag')].map((x) => x.textContent),
      hero: (document.querySelector('[data-hx="story"]') || {}).textContent || '', sw: document.documentElement.scrollWidth - innerWidth,
      chips: [...document.querySelectorAll(s + ' .st-day')].map((x) => [x.textContent, Math.round(x.getBoundingClientRect().height), x.getAttribute('aria-pressed')]),
      small: [...document.querySelectorAll(s + ' *')].filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).length }), sel);
    o[k].errs = errs; await ctx.close();
  }
  console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("e. browser check skipped: no node playwright", True)
        return
    if not os.path.exists(os.path.join(NQ, "replay", "2026-11-26.json")):
        check("e. browser check skipped: the replay files are not in this checkout", True)
        return
    r = subprocess.run([exe, "-e", BROWSER, WEB], capture_output=True, text=True, timeout=150)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("e. the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("e. the browser harness runs", False, o["fail"])
        return
    c, p = o["card"], o["page"]
    check("e. nq/ card (demo): moments drawn, the example fills tagged DEMO (never REAL), the hero's 'Story so far', chips >= 44 px, no errors",
          c["n"] >= 3 and "DEMO" in c["tags"] and "REAL" not in c["tags"] and c["hero"].startswith("Story so far: ") and all(h >= 44 for _, h, _p in c["chips"]) and not c["errs"], c)
    check("e. story.html?day=2026-11-26: 12 moments, that day's chip pressed, TWIN tags, 390 px, >= 12 px, no sideways scroll, no errors",
          p["n"] == 12 and any(x[0] == "Thu Nov 26" and x[2] == "true" for x in p["chips"]) and "TWIN" in p["tags"] and p["small"] == 0 and p["sw"] <= 0 and not p["errs"], p)


if __name__ == "__main__":
    static()
    core()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
