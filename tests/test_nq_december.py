"""THE DECEMBER CARD on nq/ (tools/web_public/nq/decore.js + december.js + december.css, night-nq-main 2026-11-27). Node (+ Chromium when
node's playwright is installed), ~3 s. Fixture = nq/december.json as tools/december_plan.py wrote it (night-of-december f118818a).
  a. static: december.js is code-split (nq.js adds it near its card / idle; no page tag), december.css non-blocking, decore pure + Safari-16 safe,
     text only; the card + the jump link are on the page; no cyan / brown / olive
  b. model: 22 sessions / 1 half day / Dec 25 closed / ~12 LIT / ~9 ATLAS / 5 high news / roll Dec 10; the 4 accounts' odds by Dec 31 on both
     paths (Zlarior 50K pass 49% vs 7%, ATLAS payout 43% vs 7%, earliest Dec 7); the flagged days (Dec 1 7-day deadline, Dec 4 NFP, Dec 9 FOMC,
     Dec 10 CPI + roll, Dec 24 half day, Dec 25 closed, Dec 30 minutes); a Mon-Fri grid (Dec 1 = Tue); the pick = today, else the next flagged day
  c. a day: Dec 1 = the 4 accounts' 7-day clock (keep-alive on); Dec 10 = CPI flat 08:25 + the roll; Dec 25 closed; no file = an honest line;
     January = "December is over"; junk never throws
  d. browser: the card draws from the file at 390 px (no sideways scroll, day buttons >= 44 px), a tap on Dec 10 shows the roll; no file = NOT PUBLISHED
    python -X utf8 -m tests.test_nq_december
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
FIX = os.path.join(ROOT, "tests", "fixtures", "december", "december_2026-12.json")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    core, js, css, html, nqjs = (read(os.path.join(NQ, n)) for n in ("decore.js", "december.js", "december.css", "index.html", "nq.js"))
    check("a. december.js code-split (nq.js adds it near #decCard or idle), december.css non-blocking, the card + jump link on the page",
          'src="december.js' not in html and "./december.js?v=" in nqjs and re.search(r'december\.css\?v=\d+" media="print" onload=', html)
          and 'id="decCard"' in html and 'href="#decCard"' in html)
    check("a. decore.js pure + Safari-16 safe; december.js text only, reads only ./december.json",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core))
          and not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(", js) and re.findall(r"fetch\('([^']+)'", js) == ["./december.json"])
    check("a. december.css: OLYMPUS NIGHT only (no cyan / brown / olive / orange)",
          not re.search(r"cyan|olive|brown|#0ff\b|#22d3ee|#06b6d4|#ff9f43|orange", re.sub(r"/\*[\s\S]*?\*/", "", css), re.I))


JS = r"""
import(process.argv[1]).then((P) => {
  const fs = require('fs'), J = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), o = {};
  const nov27 = Date.parse('2026-11-27T12:00:00Z') / 1000, dec10 = Date.parse('2026-12-10T15:00:00Z') / 1000, jan5 = Date.parse('2027-01-05T15:00:00Z') / 1000;
  const M = P.december(J, nov27);
  o.sum = M.summary; o.accts = M.accts.map((a) => [a.name, a.what, a.good, a.bad, a.day]);
  o.flagged = M.flagged.map((d) => [d, M.days[d].tags]);
  o.weeks = M.weeks.map((w) => w.cells.map((c) => (c ? +c.slice(8) : 0)));
  o.pick = [M.pick, P.december(J, dec10).pick];
  o.d1 = P.dayDetail(M.days['2026-12-01']); o.d10 = P.dayDetail(M.days['2026-12-10']); o.d25 = P.dayDetail(M.days['2026-12-25']); o.d24 = P.dayDetail(M.days['2026-12-24']);
  o.none = P.december(null, nov27); o.over = P.december(J, jan5);
  o.overLine = o.over.line; o.over = o.over.over;
  o.junk = [null, 1, 'x', [], {}, { kind: 'december-plan', days: [null, 3, { day: 'bad' }] }].map((j) => { try { P.december(j, nov27); P.dayDetail(j); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  console.log(JSON.stringify(o));
});
"""


def core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "-e", JS, "file://" + os.path.join(NQ, "decore.js"), FIX], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    s = o["sum"]
    check("b. summary: 22 sessions, 1 half day, 1 closed, ~12.4 LIT, ~9.3 ATLAS, 5 high news, roll Dec 10",
          (s["sessions"], s["half"], s["closed"], s["lit"], s["atlas"], s["news"], s["roll"]) == (22, 1, 1, 12.4, 9.3, 5, "Dec 10"), s)
    check("b. the 4 accounts' odds by Dec 31, both paths: Zlarior 50K pass 49 / 7 (median Dec 17), 25K #2 66 / 19, Rapid 25 / 3, ATLAS payout 43 / 7 (earliest Dec 7)",
          o["accts"] == [["Zlarior 50K eval", "pass by Dec 31", 49, 7, "Dec 17"], ["Zlarior 25K #2 eval", "pass by Dec 31", 66, 19, "Dec 10"],
                         ["Rapid EOD 25K eval", "pass by Dec 31", 25, 3, "Jan 19"], ["ATLAS 25K funded", "payout by Dec 31", 43, 7, "Dec 7"]], o["accts"])
    check("b. flagged: Dec 1 7-day deadline, Dec 4 news, Dec 9 news, Dec 10 news + roll, Dec 24 half day, Dec 25 closed, Dec 30 news",
          o["flagged"] == [["2026-12-01", ["7-day deadline"]], ["2026-12-04", ["High news"]], ["2026-12-09", ["High news"]], ["2026-12-10", ["High news", "Contract roll"]],
                           ["2026-12-24", ["Half day"]], ["2026-12-25", ["CME closed"]], ["2026-12-30", ["High news"]]], o["flagged"])
    check("b. a Mon-Fri grid: Dec 1 is a Tuesday, 5 weeks, Dec 31 a Thursday", o["weeks"][0] == [0, 1, 2, 3, 4] and len(o["weeks"]) == 5 and o["weeks"][-1] == [28, 29, 30, 31, 0], o["weeks"])
    check("b. the pick: Nov 27 -> the next flagged day (Dec 1); on Dec 10 -> today", o["pick"] == ["2026-12-01", "2026-12-10"], o["pick"])
    d1, d10, d25, d24 = o["d1"], o["d10"], o["d25"], o["d24"]
    check("c. Dec 1: the 4 accounts' 7-day clock, MFFU's last day Dec 2, keep-alive on (gold)",
          d1["title"] == "Tue Dec 1 · 7-day deadline" and d1["tone"] == "gold" and "ATLAS 25K funded, Zlarior 25K #2, Zlarior 50K, Rapid EOD 25K must have a trade by today (MFFU's last day Dec 2); the keep-alive is on for all of them." in d1["lines"][0], d1)
    check("c. Dec 10: CPI (LIT flat by 08:25) + the roll to MNQ 03-27, each its own line",
          d10["title"] == "Thu Dec 10 · High news · Contract roll" and any("LIT flat by 08:25" in l for l in d10["lines"]) and any("MNQ 03-27" in l for l in d10["lines"]), d10)
    check("c. Dec 24 half day (halt 13:15); Dec 25 closed (off)", "13:15" in " ".join(d24["lines"]) and d25["tone"] == "off" and "no trades" in " ".join(d25["lines"]), (d24, d25))
    check("c. no file: has false + an honest line; January: 'December is over'; junk never throws",
          o["none"]["has"] is False and "not on the site yet" in o["none"]["line"] and o["over"] is True and o["overLine"].startswith("December is over")
          and all(j == "ok" for j in o["junk"]), (o["none"], o["overLine"], o["junk"]))


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1], FIX = process.argv[2];
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' };
(async () => {
  const b = await chromium.launch(), o = {};
  for (const withFile of [true, false]) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
    await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
      if (u.pathname === '/nq/december.json') return withFile ? r.fulfill({ status: 200, body: fs.readFileSync(FIX), contentType: 'application/json' }) : r.fulfill({ status: 404, body: '' });
      const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
      return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
    const p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('http://site.local/nq/index.html?demo=1', { waitUntil: 'load' });
    await p.waitForFunction(() => !document.getElementById('decCard').hidden, null, { timeout: 15000 }).catch(() => {});
    const k = withFile ? 'file' : 'none';
    o[k] = await p.evaluate(() => { const c = document.getElementById('decCard'), cells = [...c.querySelectorAll('.dc-cell')];
      return { hidden: c.hidden, pill: (c.querySelector('.pill') || {}).textContent, n: cells.length, accts: c.querySelectorAll('.dc-acc').length,
        minH: cells.length ? Math.min(...cells.map((x) => x.getBoundingClientRect().height)) : 0, sw: document.documentElement.scrollWidth - innerWidth,
        none: (c.querySelector('.dc-none') || {}).textContent || '' }; });
    if (withFile) { await p.click('#decCard .dc-cell[data-day="2026-12-10"]'); o.tap = await p.evaluate(() => [document.getElementById('decDay').textContent, document.querySelector('.dc-cell[data-day="2026-12-10"]').getAttribute('aria-pressed')]); }
    o[k].errs = errs; await ctx.close();
  }
  console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("d. browser check skipped: no node playwright", True)
        return
    r = subprocess.run([exe, "-e", BROWSER, WEB, FIX], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("d. the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("d. the browser harness runs", False, o["fail"])
        return
    f = o["file"]
    check("d. with the file: the card draws (23 weekday buttons, 4 accounts, made Nov 27), buttons >= 44 px, no sideways scroll, no errors",
          not f["hidden"] and f["n"] == 23 and f["accts"] == 4 and f["pill"] == "made Nov 27" and f["minH"] >= 44 and f["sw"] <= 0 and not f["errs"], f)
    check("d. a tap on Dec 10 shows the CPI + roll day and marks the button", "Contract roll" in o["tap"][0] and "MNQ 03-27" in o["tap"][0] and o["tap"][1] == "true", o["tap"])
    n = o["none"]
    check("d. no file: NOT PUBLISHED + the honest line", not n["hidden"] and n["pill"] == "NOT PUBLISHED" and "not on the site yet" in n["none"] and not n["errs"], n)


if __name__ == "__main__":
    static()
    core()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
