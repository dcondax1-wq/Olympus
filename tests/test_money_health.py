"""MONEY VIEW + STRATEGY HEALTH (day-site5 2026-11-26).
  a. static: the files, load order, no innerHTML / storage / POST, OLYMPUS NIGHT (no cyan / brown), the builder's data fresh
  n. node: business/moneyview.js (eval gauge + the payday-plan forecast, the forecaster's shape with a SAMPLE fixture, sim funded gauge +
     the next payout request date in every case, the floor bar red under $300), trading/healthcore.js (normal / cold streak / outside the
     band / hot / too few / no band), the builder's band = an independent percentile count of the backtest's 10-trade stretches
  b. Chromium 390 x 844 (Node Playwright): My MFFU Accounts draws a gauge + a risk bar per account; the Trading page draws the health card
     (2 bots, 'too few trades' today: 2 and 3 real trades). MH_SHOTS=<dir> saves shots. MH_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_money_health
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "tools", "web_public")
RES: list = []

FC_FIXTURE = {"v": 1, "sample": True, "made": "2026-11-26", "market": "Jul-Oct-like", "runs": 2000,
              "accounts": {"Z50": {"name": "Zlarior 50K (eval)", "p_pass": 0.61, "p_fail": 0.27, "days_med": 14, "days_p25": 8, "days_p75": 24, "pass_by": "2026-12-15"}}}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(*p):
    return open(os.path.join(PUB, *p), encoding="utf-8").read()


def static():
    mv, mj, mh = read("business", "moneyview.js"), read("business", "mffu.js"), read("business", "mffu.html")
    hc, hj, th = read("trading", "healthcore.js"), read("trading", "health.js"), read("trading", "index.html")
    code = mv + hc + hj
    check("a. no innerHTML / eval / storage / POST in the new code", not re.search(r"innerHTML|eval\(|new Function|localStorage|method:\s*['\"]POST", code))
    check("a. OLYMPUS NIGHT in the new CSS: violet / gold / mint, no cyan / brown", "#9d59ee" in mh and "#f1c14b" in mh and "#77db89" in mh
          and not re.search(r"cyan|brown|olive|#5fd0c9", mh[mh.index("MONEY VIEW"):] + read("trading", "trading.css")[read("trading", "trading.css").index("STRATEGY HEALTH"):], re.I))
    check("a. mffu.html loads moneyview.js before mffu.js; mffu.js reads forecast.json + payday.json and draws the gauges", mh.index("moneyview.js") < mh.index("mffu.js?v=")
          and "getJSON('forecast.json')" in mj and "moneyView(a, now)" in mj)
    check("a. the Trading page: the health card before the filters, healthcore before health.js, BLITZ never on the page", th.index('id="healthCard"') < th.index('id="filterCard"')
          and th.index("healthcore.js") < th.index("health.js?v=") and "BLITZ" not in th and "BLITZ" not in hj and "'blitz'" not in hc)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_money_health.py"), "--check"], capture_output=True, text=True, timeout=60)
    check("a. tools/build_money_health.py --check: the published data is fresh", r.returncode == 0, r.stdout + r.stderr)


NODE = r"""
const MV = require('%(mv)s'), H = require('%(hc)s'), fs = require('fs');
const pd = JSON.parse(fs.readFileSync('%(pd)s', 'utf8')), fc = %(fc)s, file = JSON.parse(fs.readFileSync('%(tr)s', 'utf8')), bands = JSON.parse(fs.readFileSync('%(bands)s', 'utf8'));
const evalA = { key: 'z50', name: 'Zlarior 50K', target: { v: 3000, left: 1800, progress: 0.4, pnl: 1200, balance: 53000 }, money: { room: 1250, room_now: 1250, mll: 2000, floor: 51750 } };
const coach = (o) => ({ cycle_days: 2, cycle_days_need: 2, need_more: 0, eligible_from: '2026-11-20', plan_line: 2100, first_at_min: true, ...o });
const funded = (p, m) => ({ key: 'a25', name: 'ATLAS 25K', money: { balance: 401, room: 280, mll: 1000, floor: -879, ...m }, payout: { buffer: 1100, pay_min: 250, pay_max: 1000, request_today: 0, to_you: 0, eligible_from: '2026-11-20', ...p } });
const o = {};
o.evalPd = MV.gauge(evalA, { today: '2026-11-26', payday: pd });
o.evalFc = MV.gauge(evalA, { today: '2026-11-26', payday: pd, forecast: fc });
o.evalNone = MV.gauge({ ...evalA, name: 'Unknown 10K' }, { today: '2026-11-26', payday: pd });
o.fund = MV.gauge(funded({ coach: coach({ cycle_days: 1, need_more: 849 }) }), { today: '2026-11-26', payday: pd });
o.ready = MV.gauge(funded({ request_today: 250, to_you: 200, coach: coach({ status: 'ready' }) }, { balance: 1400 }), { today: '2026-11-26', payday: pd });
o.wait48 = MV.nextRequest({ eligible_from: '2026-11-30', coach: coach({ eligible_from: '2026-11-30', cycle_days: 2 }) }, '2026-11-26');
o.days = MV.nextRequest({ coach: coach({ cycle_days: 0 }) }, '2026-11-27');
o.nocoach = MV.nextRequest({ eligible_from: '2026-11-30' }, '2026-11-26');
o.floors = [{ room: 280, mll: 1000 }, { room: 300, mll: 1000 }, { room: 450, mll: 1000 }, { room: 900, mll: 1000 }, { room: 0, mll: 1000 }, {}].map((m) => MV.floor({ money: m })).map((f) => [f.level, f.text]);
o.floorOpen = MV.floor({ money: { room: 900, room_now: 250, mll: 1000 } });
// health: synthetic trades against the real band
const band = { bots: { lit: { window: 10, avg_r: { p5: -0.3, p25: 0.1, p50: 0.6, p75: 1.1, p95: 2.0 }, streak_p75: 2, streak_p95: 6 } } };
const mk = (rs) => ({ trades: rs.map((r, i) => ({ bot: 'LIT', src: 'live', r, usd: r * 100, t: 1e9 + i * 1e5, day: '2026-11-' + String(10 + i).padStart(2, '0') })) });
const w = (rs) => { const b = H.health(band, mk(rs)).bots[0]; return [b.word, b.level, b.n, Math.round((b.avg ?? 0) * 100) / 100, b.streak]; };
o.h = { normal: w([1, -1, 2, 0.5, 1, -1, 1.5, 0.2, 0.8, 1]), cold: w([1, -1, -1, 0.5, 1, -1, 0.3, -1, 0.2, 0]), out: w([-1, -1, -1, -1, 1, -1, -1, 0.2, -1, -1]),
  hot: w([3, 4, 2, 3, 2.5, 1, 3, 2, 4, 3]), few: w([1, -1]), streak: w([2, 3, 2, 1.5, 2, -1, -1, -1, -1, -1, -1, -1]), noband: H.health({}, mk([1, 1, 1, 1, 1])).bots[0].word };
o.real = H.health(bands, file).bots.map((b) => [b.id, b.word, b.n]);
o.liveOnly = H.liveTrades({ trades: [{ bot: 'LIT', src: 'backtest', r: 1, t: 1 }, { bot: 'LIT', src: 'paper', r: 1, t: 2 }, { bot: 'LIT', src: 'live', r: -1, t: 3 }, { bot: 'ATLAS', src: 'live', r: 1, t: 4 }] }, 'lit').length;
// the real published files (research/health/bands.json, research/forecast/forecast.json via the builder) or the provisional band
const FCR = (() => { try { return JSON.parse(fs.readFileSync('%(fcpub)s', 'utf8')); } catch (e) { return null; } })();
const acc = [{ key: 'x', name: 'Zlarior 50K', plan: 'MFFU Builder 50K evaluation', funded: false }, { key: 'y', name: 'Zlarior 25K #2', plan: 'MFFU Builder 25K evaluation', funded: false },
  { key: 'r', name: 'Rapid EOD 25K', plan: 'MFFU Rapid EOD 25K evaluation', funded: false }, { key: 'a', name: 'ATLAS 25K', plan: 'MFFU Builder 25K sim funded', funded: true }];
o.fcReal = FCR ? acc.map((a) => { const F = MV.forecastFor(a, FCR, pd); return F && [F.src, F.p_pass, F.days_med, F.p_payout, F.payout_sessions, F.ref_pass]; }) : null;
o.fcLine = FCR ? MV.gauge({ ...evalA, plan: 'MFFU Builder 50K evaluation', funded: false }, { today: '2026-11-26', payday: pd, forecast: FCR }).forecast : null;
o.fcFund = FCR ? MV.gauge({ ...funded({ coach: coach({}) }), plan: 'MFFU Builder 25K sim funded', funded: true }, { today: '2026-11-26', payday: pd, forecast: FCR }).forecast : null;
o.fcRaw = FCR ? Object.fromEntries(Object.entries(FCR.accounts).map(([k, v]) => [k, v['2026-like'] || null])) : null;
o.bandsProv = !!bands.provisional; o.bandsWin = bands.window;
o.bandsPub = ['lit', 'atlas'].map((b) => [bands.bots[b].n_backtest, bands.bots[b].avg_r.p5, bands.bots[b].avg_r.p50, bands.bots[b].avg_r.p95, (bands.bots[b].live || []).length]);
o.realH = H.health(bands, file).bots.map((b) => [b.id, b.word, b.n, b.ref ? b.ref.span : null]);
o.indep = bands.provisional ? ['lit', 'atlas'].map((bot) => {
  const rs = file.trades.filter((t) => String(t.bot).toLowerCase() === bot && t.src === 'backtest' && typeof t.r === 'number').sort((a, b) => a.t - b.t).map((t) => t.r);
  const av = []; for (let i = 0; i + 10 <= rs.length; i++) av.push(rs.slice(i, i + 10).reduce((s, x) => s + x, 0) / 10);
  av.sort((a, b) => a - b); const q = (p) => { const k = (av.length - 1) * p; const lo = Math.floor(k), hi = Math.min(lo + 1, av.length - 1); return av[lo] + (av[hi] - av[lo]) * (k - lo); };
  return [rs.length, Math.round(q(0.05) * 1000) / 1000, Math.round(q(0.5) * 1000) / 1000, Math.round(q(0.95) * 1000) / 1000];
}) : null;
// a p5 / p50 / p95 band (the health study's shape): cold = under halfway from p5 to the median
const b3 = { bots: { lit: { window: 20, avg_r: { p5: 0.14, p50: 0.61, p95: 1.54 } } } };
const w3 = (rs) => { const b = H.health(b3, mk(rs)).bots[0]; return b.word; };
o.h3 = [w3([1, 0.5, 0.8, 0.6, 0.7]), w3([0.3, 0.2, 0.4, 0.3, 0.2]), w3([-1, -1, 0.5, -0.5, 0.2]), w3([3, 2, 2.5, 2, 3]), w3([2, 2, 1, -1, -1, -1, -1])];
o.bandLive = H.health({ bots: { lit: { window: 20, avg_r: { p5: 0.14, p50: 0.61, p95: 1.54 }, live: [{ day: '2026-11-01', r: 1 }, { day: '2026-11-02', r: 1 }, { day: '2026-11-03', r: 1 }] } } }, mk([1])).bots[0].n;
console.log(JSON.stringify(o));
"""


def node():
    js = NODE % {"mv": os.path.join(PUB, "business", "moneyview.js"), "hc": os.path.join(PUB, "trading", "healthcore.js"), "pd": os.path.join(PUB, "business", "payday.json"),
                 "fc": json.dumps(FC_FIXTURE), "tr": os.path.join(PUB, "trading", "trades.json"), "bands": os.path.join(PUB, "trading", "bands.json"), "fcpub": os.path.join(PUB, "business", "forecast.json")}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("n. node run", False, (r.stderr or str(e))[:800]); return
    e = o["evalPd"]
    check("n. eval gauge: $1,800 to pass, 40%, the payday plan's forecast (pass by Dec 31 58%, most likely Mon 12/28, lost first 32%) named as such",
          e["kind"] == "pass" and e["text"] == "$1,800 to pass" and e["frac"] == 0.4 and "58%" in e["forecast"]["line"] and "12/28" in e["forecast"]["line"] and "32%" in e["forecast"]["line"]
          and "Payday plan" in e["forecast"]["src"] and "not landed" in e["forecast"]["src"] and e["forecast"]["sample"] is False, e)
    f = o["evalFc"]["forecast"]
    check("n. eval gauge with the forecaster's file: pass 61%, fail 27%, about 14 trading days, most likely Tue 12/15; its SAMPLE flag kept",
          f["line"] == "Pass 61% · fail 27% · about 14 trading days · most likely Tue 12/15" and f["sample"] is True and "2,000 runs" in f["src"], f)
    check("n. an account no forecast knows: the gauge, no forecast (nothing made up)", o["evalNone"]["forecast"] is None and o["evalNone"]["text"] == "$1,800 to pass", o["evalNone"])
    g = o["fund"]
    check("n. sim funded gauge: $1,699 to the $250 first payout (goal balance $2,100 = buffer + the owner's ask), the payday plan's first payout",
          g["kind"] == "payout" and g["text"] == "$1,699 to the $250 payout" and g["goal"] == 2100 and abs(g["frac"] - 401 / 2100) < 1e-9 and "First payout most likely" in g["forecast"]["line"], g)
    check("n. next request: needs 1 more traded day + $849 more profit -> 'Earliest request' with both reasons", g["next"]["text"].startswith("Earliest request: Fri 11/27")
          and "1 more traded day" in g["next"]["text"] and "$849 more profit" in g["next"]["text"], g["next"])
    check("n. next request: payout ready today -> 'Can request $250 today ($200 to you)', the gauge says ready", o["ready"]["next"]["today"] and o["ready"]["next"]["text"] == "Can request $250 today ($200 to you)"
          and o["ready"]["eligible"] and o["ready"]["text"] == "Payout ready: $250", o["ready"])
    check("n. next request: the 48 h wait -> Mon 11/30; days missing over a weekend -> Mon 11/30 + Tue 12/1; no tracker -> the earliest date and what is missing",
          o["wait48"]["date"] == "2026-11-30" and o["wait48"]["sure"] and o["days"]["date"] == "2026-12-01" and "2 more traded days" in o["days"]["text"]
          and o["nocoach"]["date"] == "2026-11-30" and "tracker" in o["nocoach"]["text"], (o["wait48"], o["days"], o["nocoach"]))
    check("n. floor bar: $280 red (UNDER $300), $300 gold (under half the max loss), $450 gold, $900 ok, $0 gone, no numbers -> says so",
          [x[0] for x in o["floors"]] == ["red", "gold", "gold", "ok", "gone", "none"] and o["floors"][0][1] == "$280 from the floor · UNDER $300" and "PC" in o["floors"][5][1], o["floors"])
    check("n. floor bar counts the open trade (room now $250 -> red)", o["floorOpen"]["level"] == "red" and o["floorOpen"]["room"] == 250 and "open trade counted" in o["floorOpen"]["sub"], o["floorOpen"])
    h = o["h"]
    check("n. health words: normal / cold streak / outside the band (bad) / outside the band (hot) / too few / 7-loss streak / no band",
          h["normal"][0] == "normal" and h["cold"][0:2] == ["cold streak", "warn"] and h["out"][0:2] == ["outside the band", "bad"] and h["hot"][0:2] == ["outside the band", "hot"]
          and h["few"][0] == "too few trades" and h["streak"][0] == "outside the band" and h["streak"][4] == 7 and o["h"]["noband"] == "no band yet", h)
    check("n. health counts only the real (live) trades of that bot", o["liveOnly"] == 1, o["liveOnly"])
    research = os.path.join(ROOT, "research", "health", "bands.json")
    if os.path.exists(research):
        R = json.load(open(research, encoding="utf-8"))
        want = [[R["bots"][k]["bands"]["2026"]["trades"], R["bots"][k]["bands"]["2026"]["p5"], R["bots"][k]["bands"]["2026"]["p50"], R["bots"][k]["bands"]["2026"]["p95"], len(R["bots"][k]["live"]["trades"])] for k in ("LIT", "ATLAS")]
        check("n. the published band = research/health/bands.json (2026: trades, p5 / p50 / p95, its live trades), not provisional", not o["bandsProv"] and o["bandsPub"] == want and o["bandsWin"] == R["window"], (o["bandsPub"], want))
        zones = [R["bots"][k]["live"]["zone"] for k in ("LIT", "ATLAS")]
        check("n. today's real health agrees with the study: < 5 live trades = 'too few trades' (LIT 2, ATLAS 4), the 2021-25 band rides along",
              [x[1] for x in o["realH"]] == ["too few trades" if "too few" in z else x[1] for z, x in zip(zones, o["realH"])] and [x[2] for x in o["realH"]] == [r[4] for r in want]
              and all(x[3] == "2021-25" for x in o["realH"]), (o["realH"], zones))
    else:
        check("n. the published band = an independent count of every 10-trade backtest stretch (n, p5, p50, p95)", o["bandsProv"] and o["indep"] is not None
              and all(a[0] == b[0] and all(abs(x - y) <= 0.002 for x, y in zip(a[1:4], b[1:4])) for a, b in zip(o["indep"], o["bandsPub"])), (o["indep"], o["bandsPub"]))
    check("n. a p5 / p50 / p95 band: normal, cold (under halfway to the median), outside (bad), outside (hot), cold (4 losses in a row); the band's own live list wins when longer",
          o["h3"] == ["normal", "cold streak", "outside the band", "outside the band", "cold streak"] and o["bandLive"] == 3, (o["h3"], o["bandLive"]))
    fr = os.path.join(ROOT, "research", "forecast", "forecast.json")
    if os.path.exists(fr):
        raw = o["fcRaw"]
        check("n. the real forecast (research/forecast/forecast.json): each card finds ITS row (50K -> zlarior, 25K #2 -> fresh25, Rapid -> rapid1, ATLAS funded -> atlas)",
              o["fcReal"] and [x[1] for x in o["fcReal"][:3]] == [round(raw[k]["pass_pct"] / 100, 6) if raw[k] else None for k in ("zlarior", "fresh25", "rapid1")]
              and all(x[0] == "forecast" for x in o["fcReal"]) and abs(o["fcReal"][3][3] - raw["atlas"]["first_payout_pct"] / 100) < 1e-9 and o["fcReal"][3][4] == raw["atlas"]["first_payout_med_sessions"], (o["fcReal"], raw))
        check("n. the real forecast lines: 'Pass 61% · fail 31% · about 16 trading days (2021-25-like market: pass 13%)'; ATLAS 'First payout 82% · about 22 trading days · lost first 10%'",
              o["fcLine"]["line"].startswith("Pass ") and "trading days" in o["fcLine"]["line"] and "2021-25-like market: pass" in o["fcLine"]["line"] and "Pass forecaster" in o["fcLine"]["src"]
              and o["fcFund"]["line"].startswith("First payout ") and "lost first" in o["fcFund"]["line"], (o["fcLine"], o["fcFund"]))



class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


BROWSER = r"""
const { chromium } = require('playwright');
const [, , BASE, SHOTS] = process.argv; const out = {};
(async () => {
  const b = await chromium.launch(); const errs = [];
  const page = async (u) => { const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1 }); const p = await ctx.newPage();
    p.on('pageerror', (e) => errs.push(String(e))); await p.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' })); await p.goto(BASE + u, { waitUntil: 'load' }); return { p, ctx }; };
  try {
    let { p, ctx } = await page('/business/mffu.html');
    await p.waitForFunction(() => window.MFFU_PAGE && window.MFFU_PAGE.ready, null, { timeout: 30000 });
    out.mffu = await p.evaluate(() => ({ cards: document.querySelectorAll('#list .mf').length, mv: [...document.querySelectorAll('#list .mv')].map((m) => ({ g: (m.querySelector('.mv-g') || {}).dataset ? m.querySelector('.mv-g') && m.querySelector('.mv-g').dataset.kind : null,
      t: (m.querySelector('.mv-g .mv-t') || {}).textContent || '', fc: (m.querySelector('.mv-fc') || {}).textContent || '', next: (m.querySelector('.mv-next') || {}).textContent || '',
      f: (m.querySelector('.mv-f') || {}).dataset ? m.querySelector('.mv-f').dataset.level : null, ft: (m.querySelector('.mv-f .mv-t') || {}).textContent || '' })),
      wide: document.documentElement.scrollWidth > innerWidth + 1 }));
    if (SHOTS) { await p.evaluate(() => { const e = document.querySelector('#list .mf'); if (e) window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 10); }); await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/11_money_view.png' }); }
    await ctx.close();
    ({ p, ctx } = await page('/trading/'));
    await p.waitForFunction(() => document.getElementById('healthCard') && document.getElementById('healthCard').dataset.ready === '1', null, { timeout: 30000 });
    out.health = await p.evaluate(() => ({ rows: [...document.querySelectorAll('#healthList .hb')].map((r) => r.dataset.bot + ':' + r.dataset.word), src: document.getElementById('healthSrc').textContent,
      bars: document.querySelectorAll('#healthList .hb-bar i.mid, #healthList .hb-bar i.med').length, live: document.querySelectorAll('#healthList .hb-bar i.live').length, wide: document.documentElement.scrollWidth > innerWidth + 1 }));
    if (SHOTS) { await p.evaluate(() => { const e = document.getElementById('healthCard'); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 10); }); await p.waitForTimeout(500); await p.screenshot({ path: SHOTS + '/12_strategy_health.png' }); }
    await ctx.close();
  } catch (e) { out.fatal = String(e && e.stack || e).slice(0, 500); }
  out.errors = errs; await b.close(); console.log(JSON.stringify(out));
})();
"""


def browser():
    npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    env = {**os.environ, "NODE_PATH": npm}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True); return
    shots = os.environ.get("MH_SHOTS", "")
    if shots:
        os.makedirs(shots, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False) as fh:
        fh.write(BROWSER); js = fh.name
    try:
        r = subprocess.run(["node", js, f"http://127.0.0.1:{srv.server_address[1]}", shots], capture_output=True, text=True, timeout=300, env=env)
    finally:
        srv.shutdown(); os.unlink(js)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or r.stdout or str(e))[:800]); return
    check("b. no fatal, no page error", "fatal" not in o and not o.get("errors"), (o.get("fatal"), o.get("errors")))
    M = o.get("mffu") or {}
    check("b. My MFFU Accounts: every account card has a gauge (to pass / to payout) and a risk-distance bar", M.get("cards", 0) >= 1 and len(M.get("mv", [])) == M.get("cards")
          and all(m["g"] in ("pass", "payout") and m["t"] and m["f"] for m in M["mv"]), M)
    check("b. My MFFU Accounts: forecasts named (payday plan / forecaster) and a funded account's next request line; no sideways scroll",
          any("Payday plan" in m["fc"] or "forecaster" in m["fc"] for m in M.get("mv", [])) and (not any(m["g"] == "payout" for m in M.get("mv", [])) or any(m["next"] for m in M["mv"] if m["g"] == "payout"))
          and M.get("wide") is False, M)
    T = o.get("health") or {}
    check("b. Trading: the Strategy health card, LIT + ATLAS 'too few trades' today, the band drawn with the live marker, its source said",
          T.get("rows") == ["lit:too few trades", "atlas:too few trades"] and T.get("bars") == 2 and T.get("live") == 2 and ("PROVISIONAL" in T.get("src", "") or "health study" in T.get("src", "")) and T.get("wide") is False, T)


def main():
    static()
    node()
    if os.environ.get("MH_NO_BROWSER") != "1":
        browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
