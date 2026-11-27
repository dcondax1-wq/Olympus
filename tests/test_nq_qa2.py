"""QA second sweep fixes on nq/ (night-nq-main 2026-11-27, research/handoff/2026-11-27/qa/FINDINGS.md "Second sweep"). Static + Chromium.
  N2/N3/#9: the dock + PC pill + the kit's Ask ring + Olympus Home in ONE row (phone / tablet: just above the dock; >= 1100: inside the
            full-width bottom bar), never stacked, never over the dock's tabs, the dock flush with the bottom edge
  N4: the hero says "London open now" in the London window; the next moment is "New York opens 09:30" (not 08:00)
  #8: one plan sentence from the day's real close (the brief's early_close: entries -15, flat -5), never "flat by 15:55" next to a halt
  #6: the Replay list in the folded Checks block loads when the fold opens (no "Loading when you get here..." forever)
  #11: the ORDER FLOW chip says "Ready" once the tick days reach the need (313/60 read as broken)
  (N1 = tests/test_nq_plan.py: the battle plan's price; nqdesk briefLevels: the thinking card's)
    python -X utf8 -m tests.test_nq_qa2
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
    nav, nqjs, desk, html = (read(os.path.join(NQ, n)) for n in ("nqnav.css", "nq.js", "nqdesk.js", "index.html"))
    pc = read(os.path.join(WEB, "pillars", "pillarscore.js"))
    check("N2/N3: nqnav.css puts Home / Ask / the pill on one row above the dock, the wide dock flush at the bottom, in-bar at >= 1100",
          "html.nqnav-on .oly-home, html.nqnav-on .oly-ask-btn { bottom: calc(var(--nqnav-h) + 20px) !important; }" in nav
          and re.search(r"@media \(min-width: 760px\) \{\s*html\.nqnav-on \{ --nqnav-h: calc\(56px", nav) and "@media (min-width: 1240px)" in nav)
    check("N4: hero 'London open now'; next = 'New York opens 09:30' (570)", "'London open now'" in desk and "{ at: 570, label: 'New York opens 09:30' }" in desk
          and "New York morning 08:00" not in desk)
    check("#8: one sentence from the brief's early_close (entries -15, flat -5); no 'Other days ... 15:55' tail",
          "export function haltClose(" in nqjs and "entry: hm(m - 15), flat: hm(m - 5)" in nqjs and "Other days: one trade between 02:00 and 15:30 ET, flat by 15:55 ET." not in nqjs)
    check("#6: the Replay list loads when its fold opens; placeholder says so", "fold.addEventListener('toggle'" in nqjs and "Loading when you get here" not in html
          and "Loads when you open this section." in html)
    check("#11: ORDER FLOW chip 'Ready' at d >= of", "m.tick.d >= m.tick.of ? 'Ready'" in pc)


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1];
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
(async () => {
  const b = await chromium.launch(), o = {};
  for (const [w, h] of [[390, 844], [900, 1000], [1440, 900]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
      const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
      return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
    const p = await ctx.newPage(); await p.goto('http://site.local/nq/index.html?demo=1', { waitUntil: 'load' }); await p.waitForTimeout(3500);
    await p.evaluate(() => { const h = document.querySelector('.oly-home'); if (h) h.classList.remove('oly-away'); }); await p.waitForTimeout(700);
    o[w] = await p.evaluate(() => {
      const hm = document.querySelector('.oly-home'); if (hm) { hm.style.transition = 'none'; hm.classList.remove('oly-away'); hm.style.transform = 'none'; }
      const R = (s) => { const e = document.querySelector(s); if (!e || getComputedStyle(e).display === 'none') return null; const r = e.getBoundingClientRect(); return r.width ? [r.left, r.top, r.right, r.bottom] : null; };
      const tabs = [...document.querySelectorAll('.nqn-tab')].map((t) => { const r = t.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; });
      return { dock: R('.nqn-dock'), pill: R('.nqn-float'), home: R('.oly-home'), ask: R('.oly-ask-btn'), tabs, vh: innerHeight, vw: innerWidth };
    });
    await ctx.close();
  }
  console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def hit(a, b):
    return bool(a and b and a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("browser check skipped: no node playwright", True)
        return
    r = subprocess.run([exe, "-e", BROWSER, WEB], capture_output=True, text=True, timeout=150)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("the browser harness runs", False, o["fail"])
        return
    for w, v in o.items():
        fl = [x for x in (v["pill"], v["home"], v["ask"]) if x]
        tops = sorted({round(x[1]) for x in fl})
        check(f"{w} px: dock flush with the bottom, the floaters in one row (same top), none over a tab or each other",
              v["dock"] and abs(v["dock"][3] - v["vh"]) <= 1 and len(tops) == 1 and not any(hit(f, t) for f in fl for t in v["tabs"])
              and not any(hit(a, b) for i, a in enumerate(fl) for b in fl[i + 1:]), v)


if __name__ == "__main__":
    static()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
