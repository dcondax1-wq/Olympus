"""HOW TO READ THIS PAGE: the first-visit tour on nq/ (tools/web_public/nq/tour.js, night-nq-main 2026-11-27). Static + Chromium (node's
playwright; skipped without it), ~10 s.
  a. static: tour.js is code-split (nq.js adds it only when localStorage 'nq.tour' is unset, or ?tour=1; an automated browser only with
     ?tour=1); text only; saves 'nq.tour' in try/catch; Skip + Esc; reduced motion = no transitions; the spotlight is an outline (Sunlight-safe)
  b. browser: an automated visit without ?tour=1 gets no tour; ?tour=1: the 5 stops in order (today's $, accounts, bots, battle plan, PC freshness),
     buttons >= 44 px, the callout inside the screen at 390 px, Done saves 'nq.tour' and removes it; Esc skips + saves; reduced motion = static
    python -X utf8 -m tests.test_nq_tour
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
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "night-nq-main", "shots")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    js, nqjs, html = read(os.path.join(NQ, "tour.js")), read(os.path.join(NQ, "nq.js")), read(os.path.join(NQ, "index.html"))
    check("a. tour.js code-split: nq.js adds it only when 'nq.tour' is unset or ?tour=1 (an automated browser: ?tour=1 only); no page tag",
          'src="tour.js' not in html and "./tour.js?v=" in nqjs and "localStorage.getItem('nq.tour')" in nqjs and "navigator.webdriver" in nqjs)
    check("a. text only (no innerHTML / eval / import / fetch); saves 'nq.tour' in try/catch; Skip + Esc; 5 stops",
          not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(|\bfetch\(", js) and "try { localStorage.setItem('nq.tour', 'done'); } catch" in js
          and "'Skip tour'" in js and "'Escape'" in js and js.count("{ sel: ") == 5)
    check("a. reduced motion = static callouts; the spotlight is an outline (SUNLIGHT MODE removes shadows, not outlines); no cyan",
          "@media (prefers-reduced-motion:reduce){.tr-spot,.tr-card{transition:none}}" in js and "outline:9999px solid" in js and not re.search(r"cyan|#0ff\b|#22d3ee", js, re.I))


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1], SHOTS = process.argv[2];
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
(async () => {
  const b = await chromium.launch(), o = {};
  const page = async (q, opts) => {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: (opts && opts.dsf) || 1, reducedMotion: (opts && opts.rm) || 'no-preference' });
    await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
      const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
      return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
    const p = await ctx.newPage(); p.errs = []; p.on('pageerror', (e) => p.errs.push(e.message));
    await p.goto('http://site.local/nq/index.html' + q, { waitUntil: 'load' }); return p;
  };
  let p = await page('?demo=1'); await p.waitForTimeout(6000);
  o.auto = await p.evaluate(() => !!document.getElementById('nqTour')); await p.context().close();
  p = await page('?demo=1&tour=1', { dsf: 2 });
  await p.waitForSelector('#nqTour .tr-card', { timeout: 15000 }); await p.waitForTimeout(700);
  o.stops = [];
  for (let i = 0; i < 8; i++) {
    const s = await p.evaluate(() => { const c = document.querySelector('#nqTour .tr-card'); if (!c) return null; const r = c.getBoundingClientRect(), sp = document.querySelector('#nqTour .tr-spot').getBoundingClientRect();
      return { n: c.querySelector('.tr-n').textContent, t: c.querySelector('.tr-t').textContent, top: r.top, bottom: r.bottom, left: r.left, right: r.right, spotH: sp.height,
        btns: [...c.querySelectorAll('button')].filter((x) => !x.hidden).map((x) => [x.textContent, Math.round(x.getBoundingClientRect().height), Math.round(x.getBoundingClientRect().width)]),
        focus: document.activeElement && document.activeElement.textContent, sw: document.documentElement.scrollWidth - innerWidth }; });
    if (!s) break; o.stops.push(s);
    if (SHOTS && (i === 0 || i === 3)) await p.screenshot({ path: path.join(SHOTS, `tour_stop${i + 1}_phone.png`) });
    await p.click('#nqTour .tr-go'); await p.waitForTimeout(1300);
  }
  o.done = await p.evaluate(() => [!!document.getElementById('nqTour'), localStorage.getItem('nq.tour')]); o.errs = p.errs;
  await p.reload({ waitUntil: 'load' }); await p.waitForTimeout(800);
  await p.evaluate(() => localStorage.removeItem('nq.tour'));
  await p.context().close();
  p = await page('?demo=1&tour=1', { rm: 'reduce' });
  await p.waitForSelector('#nqTour .tr-card', { timeout: 15000 });
  o.rm = await p.evaluate(() => getComputedStyle(document.querySelector('#nqTour .tr-card')).transitionDuration);
  await p.keyboard.press('Escape'); await p.waitForTimeout(200);
  o.esc = await p.evaluate(() => [!!document.getElementById('nqTour'), localStorage.getItem('nq.tour')]);
  await p.context().close();
  console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("b. browser check skipped: no node playwright", True)
        return
    shots = SHOTS if os.environ.get("NQ_TOUR_SHOTS") else ""
    r = subprocess.run([exe, "-e", BROWSER, WEB, shots], capture_output=True, text=True, timeout=180)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("b. the browser harness runs", False, o["fail"])
        return
    check("b. an automated visit without ?tour=1: no tour (the suites are not the owner)", o["auto"] is False, o["auto"])
    st = o["stops"]
    check("b. ?tour=1: the 5 stops in order (today's $, accounts, bots, battle plan, PC freshness), 'n of 5'",
          [s["t"] for s in st] == ["Today's money", "Each account", "The bots in one word", "Today's battle plan", "Is the PC reporting?"]
          and all(s["n"].endswith(f"{i + 1} of 5") for i, s in enumerate(st)), [(s["n"], s["t"]) for s in st])
    check("b. every button >= 44 px, the callout inside the 390 x 844 screen, a spotlight on each stop, focus on Next, no sideways scroll",
          all(h >= 44 and w >= 44 for s in st for _, h, w in s["btns"]) and all(s["top"] >= 0 and s["bottom"] <= 844 and s["left"] >= 0 and s["right"] <= 390 for s in st)
          and all(s["spotH"] > 10 for s in st) and all(s["focus"] in ("Next", "Done") for s in st) and all(s["sw"] <= 0 for s in st), st)
    check("b. stop 1 has no Back, the last says Done; Done saves 'nq.tour' and removes the tour; no page errors",
          [b[0] for b in st[0]["btns"]] == ["Skip tour", "Next"] and [b[0] for b in st[-1]["btns"]] == ["Skip tour", "Back", "Done"]
          and o["done"] == [False, "done"] and not o["errs"], (st[0]["btns"], st[-1]["btns"], o["done"], o["errs"]))
    check("b. reduced motion = static callout (no transition); Esc skips and saves", all(float(x.strip().rstrip("s")) <= 0.01 for x in o["rm"].split(",")) and o["esc"] == [False, "done"], (o["rm"], o["esc"]))


if __name__ == "__main__":
    static()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
