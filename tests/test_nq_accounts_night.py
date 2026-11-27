"""NQ Accounts premium cards + the business view (night-nq-accounts 2026-11-27). Paper only, no network.

    python -X utf8 -m tests.test_nq_accounts_night [--static]

  a. node: acctcore's new pure parts: daily loss used from the PC's eval block (dll_used, else today's loss), the forecast (pass % /
     1st payout % from business/forecast.json), end-of-day history points + the sparkline path, the room ring's dash, the 7-day dial's
     7 segments, the business view (each row on its own scale with $0 inside, the band split red below / green above $0, the buy
     light ONLY when the PC sends "bg" OK / STOP, its repeated heading stripped); missing data = null, never a made-up number
  b. nq/plan12.json = research/planner/results.json today's plan (K0, no tripwire) for the 4 markets, p10 / p50 / p90 to the dollar
  c. static: OLYMPUS NIGHT only (no cyan / brown / olive hex in accounts.css, payready.css, nqgoals.css), every animation off under
     prefers-reduced-motion, text through textContent, the history button is a real <button> with aria-expanded / aria-controls
  d. browser 390 x 844 and 1440 x 900 (a PC post with dll, eq points and the buy light): a room ring + forecast % on each card, the
     daily-loss bar on Zlarior ($180 of $1,000), History opens a sparkline (aria-expanded true) and closes again, the buy light shows
     with "bg" and is ABSENT without it, the 12-month rows, taps >= 44 px, no sideways scroll, nothing off the site, no console error,
     two card columns at 1440
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_accounts_screen as TA  # noqa: E402

check = AK.check
NQ = os.path.join(ROOT, "tools", "web_public", "nq")


def node(js: str):
    r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, cwd=NQ, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return json.loads(r.stdout)


def part_a():
    o = node("""
import * as A from './acctcore.js';
const lite = { accounts: [{ id: 'x', eval: { dll: 1000, dll_used: 300 } }, { id: 'y', eval: { dll: 500, today: -420 } }, { id: 'z', eval: {} }],
  mf: { a: [{ id: 'x', eq: [0, -100, 50, 200] }, { id: 'z', eq: [5] }] } };
const fc = { made: '2026-11-26 16:13 UTC', accounts: { zlarior: { '2026-like': { pass_pct: 61, pass_med_sessions: 16 }, '2021-25-like': { pass_pct: 13.3 } },
  atlas: { '2026-like': { first_payout_pct: 82.4, lost_pct: 10.2 }, '2021-25-like': { first_payout_pct: 9.8 } } } };
const plan = { made: '2026-11-26', rows: [{ m: 'M25', label: 'Plan', p10: -1484, p50: 1397, p90: 8751, cash: 1512, fees: 94, loss: 34.2 },
  { m: 'G', label: '2026', p10: 19705, p50: 38506, p90: 57045 }, { m: 'B', label: 'bad', p10: -1993, p50: -1449, p90: 1644 }] };
const B0 = A.business(plan, {}), B1 = A.business(plan, { bg: { s: 'STOP', l: 'Buy gate: STOP buying new evals · LIT last 40 trades -2.0R (STOP) (display only)' } });
const B2 = A.business(plan, { bg: { s: 'MAYBE' } });
console.log(JSON.stringify({
  d1: A.dllOf(['x'], lite), d2: A.dllOf(['y'], lite), d3: A.dllOf(['z'], lite), d4: A.dllOf(['q'], lite),
  f1: A.forecastOf('zlarior', fc, false), f2: A.forecastOf('atlas', fc, true), f3: A.forecastOf('rapid2', fc, false), f4: A.forecastOf('zlarior', null, false),
  h1: A.historyOf(['x'], lite), h2: A.historyOf(['z'], lite), sp: A.sparkPath([0, 10, -5, 20], 100, 30, 4),
  r0: A.ringDash(0, 34), r5: A.ringDash(0.5, 34), rn: A.ringDash(null, 34), r9: A.ringDash(1.7, 34),
  s3: A.k7Segments({ left: 3, lvl: 'warn' }), s9: A.k7Segments({ left: 9, lvl: 'ok' }), sneg: A.k7Segments({ left: -2, lvl: 'bad' }), snone: A.k7Segments(null),
  b0: B0, b1: B1.light, b2: B2.light }));
""")
    check("a. daily loss used: dll_used from the PC ($300 of $1,000 = 30%, ok); else today's loss ($420 of $500 = bad); none sent = null",
          o["d1"]["frac"] == 0.3 and o["d1"]["lvl"] == "ok" and o["d1"]["text"] == "$300 of $1,000" and o["d2"]["used"] == 420 and o["d2"]["lvl"] == "bad"
          and o["d3"] is None and o["d4"] is None, (o["d1"], o["d2"]))
    check("a. forecast: eval pass 61% (13% in 2021-25, ~16 sessions); funded 1st payout 82.4%; an account the forecast lacks = null",
          o["f1"]["pct"] == 61 and o["f1"]["bad"] == 13.3 and o["f1"]["med"] == 16 and o["f2"]["pct"] == 82.4 and o["f2"]["label"].startswith("1st payout")
          and o["f3"] is None and o["f4"] is None, (o["f1"], o["f2"]))
    sp = o["sp"]
    check("a. history: 4 points (first $0, last +$200), 1 point = null; the sparkline has 4 vertices and the $0 line inside the box",
          o["h1"]["n"] == 4 and o["h1"]["last"] == 200 and o["h2"] is None and len(sp["line"].split()) == 4 and 4 <= sp["zero"] <= 26, (o["h1"], sp))
    check("a. ring: 0 = no arc, half = half the circle, missing = 0, over 1 = full (clamped)",
          o["r0"]["dash"].startswith("0.00") and abs(float(o["r5"]["dash"].split()[0]) - o["r5"]["c"] / 2) < 0.02 and o["rn"]["dash"].startswith("0.00")
          and abs(float(o["r9"]["dash"].split()[0]) - o["r9"]["c"]) < 0.02, (o["r0"], o["r5"]))
    check("a. 7-day dial: 3 days left = 3 lit + 4 spent; 9 = all 7; past = none lit; no clock = null",
          o["s3"] == ["warn"] * 3 + ["spent"] * 4 and o["s9"] == ["ok"] * 7 and o["sneg"] == ["spent"] * 7 and o["snone"] is None, o["s3"])
    r = {x["m"]: x for x in o["b0"]["rows"]}
    check("a. business rows each on their own scale: $0 inside every bar, the 2026 row all green (no red part), the bad row red + green",
          all(0 <= x["zero"] <= 1 for x in r.values()) and r["G"]["neg"] is None and r["G"]["posb"] and r["B"]["neg"] and r["B"]["posb"]
          and r["M25"]["plan"] and r["G"]["a"] > 0.3, (r["G"], r["B"]))
    check("a. buy light: none without the PC's 'bg'; STOP shown with its line (heading not repeated); an unknown verdict shows nothing",
          o["b0"]["light"] is None and o["b1"]["stop"] and o["b1"]["word"] == "STOP buying new evals" and not o["b1"]["line"].startswith("Buy gate")
          and "LIT last 40 trades" in o["b1"]["line"] and o["b2"] is None, o["b1"])


def part_a2():
    o = node("""
import * as A from './acctcore.js';
import * as GM from './goals_model.js';
import fs from 'fs';
const pd = JSON.parse(fs.readFileSync('../business/payday.json')), bz = JSON.parse(fs.readFileSync('../business/accounts.json'));
const at = A.payoutEta('atlas', { name: 'ATLAS 25K', plan: 'MFFU Builder 25K', stage: 'Funded' }, bz, pd);
const ca = A.card({ key: 'atlas', name: 'ATLAS 25K', plan: 'MFFU Builder 25K (funded)', stage: 'Funded', has: true, balance: 401, dot: 'live', mll: 1000, roomFrac: 1 },
  { lite: null, biz: bz, payday: pd, k7: [], today: '2026-11-23', minuteET: 600, etDate: '2026-11-23', pcAge: 60 });
const cr = A.card({ key: 'rapid1', name: 'Rapid EOD 25K', plan: 'MFFU Rapid EOD 25K', stage: 'Eval', has: true, balance: 24995, goal: 1505, dot: 'live', mll: 1000, roomFrac: 1 },
  { lite: null, biz: bz, payday: pd, k7: [], today: '2026-11-23', minuteET: 600, etDate: '2026-11-23', pcAge: 60 });
const g = GM.goal({ key: 'atlas', name: 'ATLAS 25K', stage: 'Funded', balance: 401 });
const tot = A.totals([ca, cr, { has: false, todayN: 999, roomN: 999 }]), tot0 = A.totals([]);
console.log(JSON.stringify({ at, none: A.payoutEta('nope', { name: 'X', plan: '' }, bz, null), ca: { goal: ca.goal, eta: ca.eta }, cr: cr.goal, g, tot, tot0 }));
""")
    a = o["at"]
    check("a2. QA #4: payoutEta = ONE forecast object (date + funded date + like) both pages can import; no payday file = null",
          a and a["firstPay"] and a["firstPayText"] and a["note"].startswith("estimate") and o["none"] is None, a)
    ca, g = o["ca"], o["g"]
    check("a2. QA #4: the card's to-payout = the ONE goals model (+$1,699 to $2,100, ask $1,000) and the eta's $ = the model's $800, not a 2nd number",
          ca["goal"]["text"] == "+$1,699" and g["left"] == 1699 and "$1,000 at $2,100" in ca["goal"]["sub"] and "($800 to you)" in ca["eta"]
          and "MFFU allows the first $250 ask at $1,350" in ca["goal"]["note"], ca)
    check("a2. the totals strip: only accounts the PC reported count (an account without PC numbers adds nothing); none = '-'",
          o["tot"]["n"] == 2 and o["tot0"]["n"] == 0 and o["tot0"]["todayText"] == "-", (o["tot"], o["tot0"]))
    cr = o["cr"]
    check("a2. the Rapid below its start says so plainly ($5 below the start: $1,505 to make back and reach +$1,500)",
          cr["text"] == "$1,505" and cr["note"] == "$5 below the start: $1,505 to make back and reach +$1,500", cr)


def part_e():
    """day-healthqa 2026-11-27: the 7-day clock counts keep-alive fills; live / today per account; the owner's hands steps."""
    o = node("""
import * as A from './acctcore.js';
import * as K from './clock7.js';
import { createRequire } from 'module';
const F = createRequire(import.meta.url)('../pc_feed.js');
const g = (id, x) => ({ id, on: true, armed: true, ...x });
const lite = { pc: { glance: { bots: [g('lit', { pos: { side: 'long', qty: 4, entry: 26617.5, stop: 26567.25, target: 26880, risk_usd: 412.6, now_usd: 138.4, tgt_usd: 2092 } }),
  g('atlas', { wait: 'EMA: Armed (long): price at the 5m EMA 50' }), g('rapid', { wait: 'Trades the same LIT setups as Zlarior.' }), g('b25k_2', { on: false })] } },
  ck: { nt: [1, 1, 0] }, brd: { ev: [[1795758357, 'self_heal', '', 'Self-heal could not fix: NinjaTrader still runs the old LE_TickRec.cs (before build ids; n']] },
  mf: { a: [{ id: 'atlas', nm: 'ATLAS 25K funded', lt: '2026-11-20' }, { id: 'mffu50k_eval', nm: 'Zlarior 50K', lt: '2026-11-26' }] },
  k7: { a: [{ id: 'atlas', nm: 'ATLAS 25K funded', lf: '2026-11-25', base: 'fill', hard: '2026-12-02', on: true }, { id: 'mffu50k_eval', nm: 'Zlarior 50K', lf: '2026-11-26', base: 'fill', hard: '2026-12-03', on: true }] } };
const now = 1795790702;
const L = { in: A.liveOf(['mffu50k_eval', 'lit'], lite), setup: A.liveOf(['atlas'], lite), wait: A.liveOf(['rapid'], lite), off: A.liveOf(['b25k_2'], lite), none: A.liveOf(['x'], lite) };
const H = { both: A.handsSteps(lite, now).map((x) => x.k), ok: A.handsSteps({ ...lite, ck: { nt: [1, 1, 1] }, brd: { ev: [] } }, now).map((x) => x.k),
  unknown: A.handsSteps({ ck: { nt: [1, 1, null] } }, now).map((x) => x.k),
  old: A.handsSteps({ brd: { ev: [[now - 8 * 86400, 'self_heal', '', 'NinjaTrader still runs the old LE_TickRec.cs']] } }, now).map((x) => x.k),
  fixed: A.handsSteps({ brd: { ev: [[now - 3600, 'self_heal', '', 'NinjaTrader still runs the old LE_TickRec.cs'], [now - 60, 'self_heal', '', 'NinjaTrader runs LE_TickRec.cs 1a2b3c']] } }, now).map((x) => x.k) };
const M = F.merge(JSON.parse(JSON.stringify(lite)), []);
const R = K.rows(M, now), W = Object.fromEntries(R.map((r) => [r.id, { ka: r.ka, w: K.words(r) }]));
const C = A.clockOf(R.find((r) => r.id === 'atlas'), '2026-11-27', 600, null, '2026-11-27');
console.log(JSON.stringify({ L, H, mf: M.mf.a, W, C: { lastText: C.lastText, hardText: C.hardText } }));
""")
    L = o["L"]
    check("e. an open trade from the PC's glance: live $ +$138 (0.34R), risk $413 to the stop, $2,092 at the target, LONG 4",
          L["in"]["state"] == "in" and L["in"]["pos"]["now"] == 138.4 and L["in"]["pos"]["risk"] == 412.6 and L["in"]["pos"]["tgt"] == 2092
          and L["in"]["pos"]["r"] == 0.34 and L["in"]["pos"]["side"] == "LONG" and L["in"]["icon"] == "\U0001F7E2", L["in"])
    check("e. today per account: armed setup = setup forming (eyes), waiting = pause, bot off = off, no glance row = nothing",
          L["setup"]["state"] == "setup" and L["wait"]["state"] == "wait" and L["off"]["state"] == "off" and L["none"]["state"] == "none", L)
    H = o["H"]
    check("e. hands steps: Connect on startup only while ck.nt[2] == 0; F5 only while the newest LE_TickRec event says 'still runs the old' (< 7 days)",
          H["both"] == ["nt_auto", "f5"] and H["ok"] == [] and H["unknown"] == [] and H["old"] == [] and H["fixed"] == [], H)
    mf = {r["id"]: r for r in o["mf"]}
    check("e. pc_feed.merge: an mf row's lt becomes the keep-alive's newer confirmed fill (the strategy's day kept as lt_strat); a newer strategy day stays",
          mf["atlas"]["lt"] == "2026-11-25" and mf["atlas"]["lt_strat"] == "2026-11-20" and mf["atlas"]["lt_ka"] is True
          and mf["mffu50k_eval"]["lt"] == "2026-11-26" and "lt_ka" not in mf["mffu50k_eval"], mf)
    W, C = o["W"], o["C"]
    check("e. 7-day words: 'MFFU last day Wed 12/02 (keep-alive filled Nov 25, ...)' when the keep-alive filled last; a strategy fill says no keep-alive",
          W["atlas"]["ka"] is True and "keep-alive filled Nov 25" in W["atlas"]["w"]["hard"] and "(the keep-alive)" in W["atlas"]["w"]["last"]
          and W["mffu50k_eval"]["ka"] is False and "keep-alive" not in W["mffu50k_eval"]["w"]["hard"], W)
    check("e. the Accounts card's clock: 'Keep-alive filled Wed 11/25' + 'MFFU's last day Wed 12/2 (keep-alive filled Nov 25)'",
          C["lastText"] == "Keep-alive filled Wed 11/25" and C["hardText"] == "MFFU's last day Wed 12/2 (keep-alive filled Nov 25)", C)


def part_b():
    P = json.load(open(os.path.join(NQ, "plan12.json"), encoding="utf-8"))
    R = json.load(open(os.path.join(ROOT, "research", "planner", "results.json"), encoding="utf-8"))["rows"]
    ok = True
    for r in P["rows"]:
        s = R[f"K0 today|W0|{r['m']}"]
        ok &= (r["p10"], r["p50"], r["p90"], r["cash"]) == (s["net12_p10"], s["net12_p50"], s["net12_p90"], s["cash_needed_p90"])
    check("b. nq/plan12.json = the planner's today's-plan 12-month numbers (4 markets, to the dollar), the planning row first",
          ok and [r["m"] for r in P["rows"]] == ["M25", "G", "B", "SW"] and "not a promise" in P["note"], [r["m"] for r in P["rows"]])


BAD_HEX = re.compile(r"#(?:0ff|00ffff|22d3ee|06b6d4|67e8f9|8fa05a|c0603c|d9a441|c8a24a|e0b060|8b5a2b|a0522d|6b4f2a|808000|556b2f)\b", re.I)


def part_c():
    css = {f: AK.read(os.path.join(NQ, f)) for f in ("accounts.css", "payready.css", "nqgoals.css")}
    code = {f: re.sub(r"/\*.*?\*/", "", s, flags=re.S) for f, s in css.items()}          # the rules, not the comments that name what is banned
    bad = {f: BAD_HEX.findall(s) + re.findall(r"olive|ag-terra|ag-sun|oly-accent-rgb, 200, 162, 74", s) for f, s in code.items()}
    check("c. OLYMPUS NIGHT only: no cyan / brown / olive / old warm-gold colour in accounts.css, payready.css, nqgoals.css",
          not any(bad.values()), bad)
    a = css["accounts.css"]
    rm = a[a.index("prefers-reduced-motion"):]
    check("c. reduced motion: the cards, sheen, bars, history, tilt and rings all stop",
          all(k in rm for k in (".ac-card", ".ac-bar .fl", ".ac-hist", "transform: none", ".rg-arc")), rm[:200])
    js = AK.read(os.path.join(NQ, "accounts.js"))
    check("c. accounts.js: History is a <button> with aria-expanded + aria-controls; text only via textContent; the tilt is off under reduced motion",
          "el('button', 'ac-more'" in js and "aria-expanded" in js and "aria-controls" in js and "innerHTML" not in js and "if (REDUCED) return;" in js)


FC_Z = json.load(open(os.path.join(ROOT, "tools", "web_public", "business", "forecast.json"), encoding="utf-8"))["accounts"]["zlarior"]["2026-like"]["pass_pct"]


def post_rich(bg=True):
    core, exts = TA.post()
    for a in core["accounts"]:
        a["eval"].update(dll=1000.0 if a["eval"]["start_balance"] == 50000 else 500.0, dll_used=0.0)
    core["accounts"][0]["eval"]["dll_used"] = 180.0
    eq = {"mffu50k_eval": [0, -310, -520, -410, -690, -822, -786], "atlas": [0, 120, 260, 190, 401]}
    for r in exts[0]["x"]["mf"]["a"]:
        if r["id"] in eq:
            r["eq"] = eq[r["id"]]
    if bg:                                        # day-healthqa: an open trade on Zlarior, the hands steps open, a keep-alive fill newer than ATLAS's last trade
        core["pc"]["glance"] = {"bots": [{"id": "lit", "on": True, "armed": True, "pos": {"side": "long", "qty": 4, "entry": 26617.5, "stop": 26567.25, "target": 26880,
                                                                                      "risk_usd": 412.6, "now_usd": 138.4, "tgt_usd": 2092}},
                                         {"id": "atlas", "on": True, "armed": True, "wait": "EMA: Armed (long): price at the 5m EMA 50"}]}
        exts[0]["x"]["ck"] = {"nt": [1, 1, 0]}
        exts[0]["x"]["brd"] = {"ev": [[TA.NOW - 3600, "self_heal", "", "Self-heal could not fix: NinjaTrader still runs the old LE_TickRec.cs (before build ids"]]}
        for r in exts[0]["x"]["k7"]["a"]:
            if r["id"] == "atlas":
                r.update(lf="2026-11-22", base="fill", hard="2026-11-29")
        exts[0]["x"]["bg"] = {"s": "OK", "l": "Buy gate: OK to buy new evals · LIT last 40 trades +30.4R · payouts-minus-fees rule OK (display only)", "sh": "", "t": TA.NOW}
    return core, exts


def part_d():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    at = dt.datetime.fromtimestamp(TA.NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    srv, origin = AK.serve({"/home.json": None})
    try:
        with AK.browser() as br:
            core, exts = post_rich(True)
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": TA.ndjson(core, exts)})
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
            p.wait_for_timeout(600)
            p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
            o = p.evaluate("""() => ({ rings: document.querySelectorAll('.ac-card .ac-ring svg').length, cards: document.querySelectorAll('.ac-card').length,
                fc: [...document.querySelectorAll('#acct-zlarior .fc-big b')].map((e) => e.textContent),
                dll: (document.querySelector('#acct-zlarior .ac-bar.dll .lab b') || {}).textContent,
                light: !!document.getElementById('buyLight'), lightTxt: (document.getElementById('buyLight') || {}).textContent || '',
                biz: document.querySelectorAll('#biz .bz-row').length, k7segs: document.querySelectorAll('#acct-zlarior .k7-seg').length,
                tot: document.getElementById('tot').hidden ? null : [...document.querySelectorAll('#tot .tt-cell b')].map((e) => e.textContent),
                bal: document.querySelector('#acct-zlarior .ac-num.big b').textContent })""")
            check("d. 390: a room ring on every card, Zlarior's pass forecast (= business/forecast.json) and its daily loss $180 of $1,000, the 7-segment dial",
                  o["rings"] == o["cards"] == 5 and o["fc"] == [f"{round(FC_Z)}%"] and o["dll"] == "$180 of $1,000" and o["k7segs"] == 7, o)
            check("d. the totals strip: today over all accounts (+$22 - $35 = -$13), the room in all, 5 of 5 live; the balance counted up to the exact $49,214",
                  o["tot"] and o["tot"][0] == "-$13" and o["tot"][2] == "5 of 5" and o["bal"] == "$49,214", (o["tot"], o["bal"]))
            check("d. the buy light shows with the PC's 'bg' (OK, green), the 4 twelve-month rows under it",
                  o["light"] and "OK to buy new evals" in o["lightTxt"] and o["biz"] == 4, o)
            wide = p.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            check("d. QA #12: the page is exactly the phone's width (the 3D tilt / raised ring no longer widen it to ~411 px)", wide[0] <= wide[1], wide)
            small = p.evaluate("""() => { const out = []; const w = document.createTreeWalker(document.getElementById('app'), NodeFilter.SHOW_TEXT);
                for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.textContent.trim(); if (!t) continue; const e = n.parentElement;
                  if (!e || !e.offsetParent && getComputedStyle(e).position !== 'fixed') continue;
                  const fs = parseFloat(getComputedStyle(e).fontSize); if (fs < 12) out.push(t.slice(0, 30) + ' ' + fs); } return out; }""")
            check("d. QA #15: no visible text on the accounts page under 12 px (was 38 runs of 10-11.5 px)", not small, small[:8])
            btn = "#acct-atlas .ac-more"
            p.click(btn)
            a1 = p.evaluate("() => ({ x: document.querySelector('#acct-atlas .ac-more').getAttribute('aria-expanded'), h: document.getElementById('hist-atlas').hidden, pl: !!document.querySelector('#hist-atlas polyline') })")
            p.click(btn)
            a2 = p.evaluate("() => ({ x: document.querySelector('#acct-atlas .ac-more').getAttribute('aria-expanded'), h: document.getElementById('hist-atlas').hidden })")
            o2 = p.evaluate("""() => ({ hands: document.getElementById('hands').hidden, open: !!document.querySelector('#acct-zlarior .ac-open'),
                live: (document.querySelector('#acct-zlarior .op-cell.live b') || {}).textContent, now: (document.querySelector('#acct-zlarior .ac-now') || {}).textContent,
                steps: [...document.querySelectorAll('#hands li b')].map((e) => e.textContent), k7: (document.querySelector('#acct-atlas .ac-k7') || {}).textContent })""")
            check("d. day-healthqa: Zlarior's open trade shows its live $ (pulsing), the 'in a trade' line; the hands chip lists Connect on startup + F5",
                  o2["open"] and o2["live"] and o2["live"].startswith("+$138") and "In a trade" in (o2["now"] or "") and not o2["hands"]
                  and o2["steps"] == ["NinjaTrader: tick 'Connect on startup'", "NinjaTrader: press F5 once"], o2)
            check("d. day-healthqa: the 7-day clock names the keep-alive's fill", "keep-alive filled" in (o2["k7"] or ""), o2["k7"])
            check("d. History opens ATLAS's sparkline (aria-expanded true) and closes it again",
                  a1 == {"x": "true", "h": False, "pl": True} and a2 == {"x": "false", "h": True}, (a1, a2))
            p.click("#acct-rapid1 .ac-more")
            t = p.evaluate("() => document.getElementById('hist-rapid1').textContent")
            check("d. an account with no history points says so (no made-up line)", "has not sent" in t, t)
            check("d. 390: taps >= 44 px, no sideways scroll, nothing fetched off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs and p.mocked, (AK.taps(p)[:4], off[:3], errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": ""})      # loading / no PC post: plan rows only
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            ws = []
            for _ in range(6):
                p.wait_for_timeout(250)
                ws.append(p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
            check("d. QA #12 while it loads (no PC post yet, cards still tilting in): never wider than the phone", max(ws) <= 0, ws)
            ctx.close()
            core, exts = post_rich(False)
            ctx, p, errs, seen, off = AK.page(br, origin, w=1440, h=900, mock={"json?poll=1": TA.ndjson(core, exts)})
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
            p.wait_for_timeout(400)
            o = p.evaluate("""() => { const c = [...document.querySelectorAll('.ac-card')].map((e) => e.offsetLeft);
                return { cols: new Set(c).size, light: !!document.getElementById('buyLight') }; }""")
            check("d. 1440: two card columns; no 'bg' in the post (the show switch off) = no buy light at all",
                  o["cols"] == 2 and not o["light"] and AK.no_sideways(p) and not errs, o)
            check("d. day-healthqa: no open hands step in the post = the chip stays hidden; no open trade = no trade box",
                  p.evaluate("() => document.getElementById('hands').hidden && !document.querySelector('.ac-open')"))
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_a2()
    part_e()
    part_b()
    part_c()
    if "--static" not in sys.argv:
        part_d()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
