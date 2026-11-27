"""NQ DATA PORTS (tools/nq_ports.py -> nq/ports.json; nq/portscore.js + ports.js + ports.css; day-nqports 2026-11-27). ~10 s.
  a. static: ports.js code-split (nq.js adds it near #ports / idle), ports.css non-blocking, portscore pure + Safari-16 safe, text only,
     reads only ./ports.json + ./news_week.json; the builder uses futures bars only (no Yahoo / CFD / keys), the CFTC's public API with a cache
  b. builder (offline, the real data/ files): all 5 sections; LIT's target = NQ close x VIX / 100 / sqrt(252) (x $2 per MNQ); the curve
     word from VIX9D / VIX / VIX3M; sweep rates are percents of whole sessions; the calendar has the Dec 10 roll + Dec 24 half day + Dec 25
  c. model (fixture): STRESS on a backwardated curve, low gamma said, the $ target; live bars -> range so far vs normal, the PDH / Asia checks
     ("taken today" / "not yet (N pts away)"), an old chart post = no live claims; COT words follow the side (never "bullish" for a short
     without saying net short); countdown: the half day today, news from news_week merged without duplicates; no file = honest lines
  d. browser: 5 cards at 390 px, >= 12 px text, no sideways scroll, no page errors; no ports.json = honest "not in this build" lines (the countdown keeps news_week's releases)
    python -X utf8 -m tests.test_nq_ports
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
NQ = os.path.join(WEB, "nq")
FIX = os.path.join(ROOT, "tests", "fixtures", "ports", "ports_2026-11-27.json")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def read(p):
    return open(p, encoding="utf-8").read()


def static():
    core, js, css, html, nqjs = (read(os.path.join(NQ, n)) for n in ("portscore.js", "ports.js", "ports.css", "index.html", "nq.js"))
    py = read(os.path.join(ROOT, "tools", "nq_ports.py"))
    check("a. ports.js code-split (nq.js adds it near #ports or idle), ports.css non-blocking, the section + jump link on the page",
          'src="ports.js' not in html and "./ports.js?v=" in nqjs and re.search(r'ports\.css\?v=\d+" media="print" onload=', html) and 'id="ports"' in html and 'href="#ports"' in html)
    check("a. portscore.js pure + Safari-16 safe; ports.js text only, reads only ./ports.json + ./news_week.json",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core))
          and not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|\bimport\s*\(", js) and set(re.findall(r"get\('([^']+)'\)", js)) == {"./ports.json", "./news_week.json"})
    check("a. the builder: futures bars only (no Yahoo / CFD), the CFTC's public API (no key) with a cache, no secrets",
          not re.search(r"yahoo|yfinance|\bcfd\b|api[_-]?key|token|password", py, re.I) and "publicreporting.cftc.gov" in py and "COT_CACHE" in py)
    check("a. ports.css: OLYMPUS NIGHT only (no cyan / brown / olive), no font under 12 px",
          not re.search(r"cyan|olive|brown|#0ff\b|#22d3ee|#06b6d4", css, re.I) and not [x for x in re.findall(r"font-size:(\d+(?:\.\d+)?)px", css) if float(x) < 12])


def builder():
    sys.path.insert(0, ROOT)
    from tools import nq_ports as NP
    import datetime as dt
    d = NP.build(offline=True, today=dt.date(2026, 11, 27))
    check("b. offline build: all 5 sections", all(d.get(k) for k in ("vol", "normal", "sweeps", "cot", "cal")), [k for k in ("vol", "normal", "sweeps", "cot", "cal") if not d.get(k)])
    v = d["vol"]
    exp = v["nq_close"] * v["vix"] / 100 / (252 ** 0.5)
    check("b. LIT's target = NQ close x VIX / 100 / sqrt(252), x $2 per MNQ; band from LIT's VIX bands",
          abs(v["move_pts"] - round(exp)) <= 1 and abs(v["move_usd_mnq"] - round(exp * 2)) <= 1 and v["band"] == NP.band(v["vix"]), v)
    s = v["structure"]
    check("b. the curve word follows VIX9D / VIX / VIX3M", s == ("contango" if v["vix9d"] < v["vix"] < v["vix3m"] else "backwardation" if v["vix9d"] > v["vix"] > v["vix3m"] else "mixed"), v)
    w = d["sweeps"]
    check("b. sweep rates are percents of > 1,000 whole sessions (and the last 60); both + neither consistent",
          w["all"]["n"] > 1000 and w["recent"]["n"] in (59, 60) and all(0 <= w["all"][k] <= 100 for k in ("pdh", "pdl", "asia_hi", "asia_lo")), w)
    ev = [(e["day"], e["kind"]) for e in d["cal"]["events"]]
    check("b. the calendar: Dec 10 roll, Dec 24 half day, Dec 25 closed, today's half day", all(x in ev for x in (("2026-12-10", "roll"), ("2026-12-24", "half"), ("2026-12-25", "closed"), ("2026-11-27", "half"))), ev)
    n = d["normal"]
    check("b. normal sizes: Asia < overnight <= day (medians, 20 sessions); the high-window shares sum to ~100%",
          0 < n["asia"] <= n["overnight"] <= n["day"] and 97 <= sum(x["pct"] for x in n["high_at"]) <= 103, n)


JS = r"""
import(process.argv[1]).then((P) => {
  const fs = require('fs'), J = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), o = {};
  const now = Date.parse('2026-11-27T15:00:00Z') / 1000;            // Fri 10:00 ET (the half day)
  o.vol = P.vol(J, now);
  // live bars: Fri's session from Thu 18:00 ET (23:00Z): Asia 26,300-26,500; then up to 26,600 (above PDH 26,435.75), low 26,250
  const bars = [], t0 = Date.parse('2026-11-26T23:00:00Z') / 1000;
  for (let i = 0; i < 180; i++) { const t = t0 + i * 300, asia = i < 96; const hi = asia ? 26500 : (i === 150 ? 26600 : 26450), lo = asia ? 26300 : 26250; bars.push([t, 26400, hi, lo, 26420]); }
  o.norm = P.normal(J, bars, now); o.sw = P.sweeps(J, bars, now);
  o.oldSw = P.sweeps(J, bars, now + 6 * 3600); o.oldN = P.normal(J, bars, now + 6 * 3600);
  o.cot = P.cot(J, now);
  const nw = { events: [{ date: '2026-12-04', time: '08:30', title: 'Non-Farm Payrolls (jobs report)', impact: 'high' }, { date: '2026-11-30', time: '10:00', title: 'Chicago PMI', impact: 'high' }, { date: '2026-11-30', time: '11:00', title: 'Low thing', impact: 'low' }] };
  o.clock = P.clock(J, nw, now);
  o.none = [P.vol(null, now).line, P.normal({}, null, now).line, P.sweeps({}, null, now).line, P.cot({}, now).line, P.clock({}, null, now).line];
  o.junk = [null, 1, 'x', [], {}].map((j) => { try { P.vol(j, now); P.normal(j, j, now); P.sweeps(j, j, now); P.cot(j, now); P.clock(j, j, now); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  console.log(JSON.stringify(o));
});
"""


def core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    r = subprocess.run([exe, "-e", JS, "file://" + os.path.join(NQ, "portscore.js"), FIX], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("the node harness runs", False, r.stderr[-800:])
        return
    o = json.loads(r.stdout)
    v = o["vol"]
    check("c. vol: STRESS on the backwardated curve (29.61 > 28.29 > 26.29), low dealer gamma said, LIT ELEVATED ~463 pts = ~$927 per MNQ, its age",
          v["word"] == "STRESS" and "Dealer gamma is low" in v["gamma"] and "ELEVATED" in v["lit"] and "463 pts" in v["lit"] and "$927 per MNQ" in v["lit"] and v["age"]["text"] == "Wed Nov 25 (2 days old)", v)
    n = o["norm"]
    check("c. today vs normal: live, range so far 350 pts = 35% of a 994-pt day, Asia 200 pts vs normal 437 ('tight, a break is likelier')",
          n["live"] and n["rows"][0]["v"] == "350 pts" and "35% of a normal day (994 pts)" in n["rows"][0]["sub"] and n["rows"][1]["v"] == "200 pts" and "tight" in n["rows"][1]["sub"], n["rows"])
    sw = {r["k"]: r["now"] for r in o["sw"]["rows"]}
    check("c. sweeps live: PDH 26,435.75 taken today, PDL not yet (N pts away), the Asia high taken after 02:00, the Asia low taken",
          o["sw"]["live"] and sw["Prior day's high taken"] == "taken today" and sw["Prior day's low taken"].startswith("not yet (") and sw["Asia high taken after 02:00"] == "taken today"
          and sw["Asia low taken after 02:00"] == "taken today", sw)
    check("c. a 6-hour-old chart post: no live claims (no 'taken today', no range so far)", not o["oldSw"]["live"] and not any(r["now"] for r in o["oldSw"]["rows"][:2]) and not o["oldN"]["live"], (o["oldSw"]["rows"], o["oldN"]["live"]))
    c = o["cot"]
    check("c. COT: hedge funds 'net short 10,928' said first, the relative rank after; never 'most bullish' for a short",
          c["read"].startswith("Hedge funds are net short 10,928 contracts.") and "most bullish" not in c["read"] and c["rows"][0]["line"].startswith("net short 10,928") and c["age"]["text"] == "Tue Nov 17 (10 days old)", c)
    k = o["clock"]["list"]
    check("c. countdown: today's half day first ('today in 3 h 15 min'), news_week's Mon PMI added, NFP not duplicated, a low-impact item never",
          k[0]["kind"] == "half" and k[0]["when"] == "today in 3 h 15 min" and any("Chicago PMI" in e["what"] for e in k) and sum("Non-Farm" in e["what"] for e in k) == 1
          and not any("Low thing" in e["what"] for e in k), [(e["day"], e["kind"], e["when"]) for e in k])
    check("c. no file: an honest line per card; junk never throws", all(isinstance(x, str) and x for x in o["none"]) and all(j == "ok" for j in o["junk"]), (o["none"], o["junk"]))


BROWSER = r"""
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), SITE = process.argv[1];
const T = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
(async () => {
  const b = await chromium.launch(), o = {};
  for (const withFile of [true, false]) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
    await ctx.route('**/*', (r) => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.fulfill({ status: 404, body: '' });
      if (u.pathname === '/nq/ports.json' && !withFile) return r.fulfill({ status: 404, body: '' });
      const f = path.join(SITE, decodeURIComponent(u.pathname)); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
      return r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: T[path.extname(f)] || 'application/octet-stream' }); });
    const p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('http://site.local/nq/index.html?demo=1', { waitUntil: 'load' });
    await p.waitForFunction(() => document.querySelectorAll('#ports .pt-card').length >= 5, null, { timeout: 15000 }).catch(() => {});
    o[withFile ? 'file' : 'none'] = await p.evaluate(() => ({ cards: document.querySelectorAll('#ports .pt-card').length, nones: document.querySelectorAll('#ports .pt-none').length,
      sw: document.documentElement.scrollWidth - innerWidth, titles: [...document.querySelectorAll('#ports .pt-h')].map((h) => h.textContent),
      small: [...document.querySelectorAll('#ports *')].filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 12).length }));
    o[withFile ? 'file' : 'none'].errs = errs; await ctx.close();
  }
  console.log(JSON.stringify(o)); await b.close();
})().catch((e) => { console.log(JSON.stringify({ fail: String(e) })); process.exit(0); });
"""


def browser():
    exe = shutil.which("node")
    if not exe or subprocess.run([exe, "-e", "require('playwright')"], capture_output=True).returncode:
        check("d. browser check skipped: no node playwright", True)
        return
    if not os.path.exists(os.path.join(NQ, "ports.json")):
        check("d. browser check skipped: nq/ports.json not built here (python tools/nq_ports.py)", True)
        return
    r = subprocess.run([exe, "-e", BROWSER, WEB], capture_output=True, text=True, timeout=150)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("d. the browser harness runs", False, (r.stdout + r.stderr)[-800:])
        return
    if "fail" in o:
        check("d. the browser harness runs", False, o["fail"])
        return
    f, n = o["file"], o["none"]
    check("d. 5 cards at 390 px (Coming up, Volatility weather, Today vs a normal day, Sweep odds, CFTC), no text under 12 px, no sideways scroll, no errors",
          f["cards"] == 5 and f["nones"] == 0 and f["titles"][0] == "Coming up" and f["small"] == 0 and f["sw"] <= 0 and not f["errs"], f)
    check("d. no ports.json: 5 cards, the 4 file cards an honest line each (the countdown still has news_week's real releases)", n["cards"] == 5 and n["nones"] >= 4 and not n["errs"], n)


if __name__ == "__main__":
    static()
    builder()
    core()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
