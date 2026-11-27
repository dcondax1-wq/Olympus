"""NQ desk (nqdash3 2026-11-20, tools/web_public/nq/nqdesk.js): the accounts strip (NQ + Trading pages), each bot's thinking (before / in /
after the trade), the quality checks. Node only (no browser), ~1 s.

  a. static: no innerHTML / fetch / storage in the module; both pages load it and its CSS; tokens only in the CSS; reduced motion stops the motion
  b. accounts: the owner's order from business/accounts.json, planned (Rapid, no PC numbers) last with a dashed 'plan' dot; balance, room, to pass,
     today; a funded account says 'To payout' (the payout coach's number); live / stale from the report age; BLITZ never; an extra PC account
     the plan does not name still shows; the cloud's paper twin never lends numbers
  c. thinking: before (lean from the armed setup side, today's high-impact news, key levels, the window, what it waits for), in (entry, stop, target,
     $ now, R so far = $ now / $ risk, minutes in trade), after (today's closed trade: $ and R, the reel link from trades.json, else 'replay later')
  d. quality: report age, heartbeat age, last alert (the PC's reporter.na when posted, else the newest trade event), twin match / differ / none,
     the news calendar; the worst level wins
  e. junk input never throws
    python -X utf8 -m tests.test_nq_desk
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
MOD = os.path.join(WEB, "nq", "nqdesk.js")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:900]}"))


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def test_static():
    js, css = read(MOD), read(os.path.join(WEB, "nq", "nqdesk.css"))
    check("a. text only: no innerHTML / insertAdjacentHTML / eval, no fetch / storage / cookies (it only draws what the page hands it)",
          not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|fetch\(|localStorage|sessionStorage|document\.cookie|XMLHttpRequest|sendBeacon", js))
    nq, tr = read(os.path.join(WEB, "nq", "index.html")), read(os.path.join(WEB, "trading", "index.html"))
    check("a. the NQ page has the accounts strip, the thinking card and the quality card; Trading has the strip; both load nqdesk.css",
          all(f'id="{i}"' in nq for i in ("acctStrip", "think", "qual")) and 'id="acctStrip"' in tr and "nqdesk.css?v=" in nq and "nqdesk.css?v=" in tr
          and "nqdesk.js?v=" in read(os.path.join(WEB, "nq", "nq.js")) and "nqdesk.js?v=" in read(os.path.join(WEB, "trading", "trading.js")))
    cols = re.findall(r"#[0-9a-fA-F]{3,8}\b", re.sub(r"var\(--[a-z0-9-]+,\s*#[0-9a-fA-F]{3,8}\)", "", css))
    check("a. every colour is a token (a hex only as a var() fallback); motion stops under prefers-reduced-motion", not cols and "prefers-reduced-motion: reduce" in css, cols)
    check("a. no BLITZ word on the cards", "BLITZ" not in js.replace("BLITZ never shows", ""))
    # night-nq-main 2026-11-27: the hero on the NQ page only (its own CSS: Trading's render-blocking size unchanged), the jump bar's anchors exist
    hero_css = read(os.path.join(WEB, "nq", "nqhero.css"))
    ids = re.findall(r'<a href="#([A-Za-z0-9]+)">', nq[nq.find('id="jump"'):nq.find("</nav>", nq.find('id="jump"'))])
    check("a. hero: id=hero with the today / phase / bots / accounts slots + the scene canvas, nqhero.css on nq only, every jump-bar link lands on a card, "
          "the scene pauses (IntersectionObserver / visibilitychange) and stands still under prefers-reduced-motion",
          all(f'data-hx="{k}"' in nq for k in ("today", "age", "phase", "next", "bots", "accts", "honest")) and 'id="heroScene"' in nq
          and "nqhero.css?v=" in nq and "nqhero.css" not in tr and len(ids) >= 6 and all(f'id="{i}"' in nq for i in ids)
          and "IntersectionObserver" in js and "visibilitychange" in js and "prefers-reduced-motion: reduce" in js and "prefers-reduced-motion" in hero_css, ids)


HARNESS = r"""
import(process.argv[2]).then((D) => {
  const now = Date.parse('2026-11-20T15:30:00Z') / 1000;          // Fri 10:30 ET
  const biz = { accounts: [
    { key: 'zlarior', pc: ['mffu50k_eval', 'lit'], name: 'Zlarior', plan: 'MFFU Builder 50K', stage: 'eval', status: 'live' },
    { key: 'atlas', pc: ['atlas', 'acct_b'], name: 'ATLAS', plan: 'MFFU Builder 25K (funded)', stage: 'funded', status: 'live' },
    { key: 'rapid1', pc: ['rapid'], name: 'Rapid EOD 25K', plan: 'MFFU Rapid EOD 25K', stage: 'eval', status: 'buying' },
    { key: 'fresh25', pc: ['b25k_2'], name: 'Zlarior 25K #2', plan: 'MFFU Builder 25K', stage: 'eval', status: 'live' },
    { key: 'blitz', pc: ['blitz'], name: 'BLITZ', stage: 'eval', status: 'paper' }] };
  const home = { built: '2026-11-20T15:00:00Z', pc_feed: { t: now - 240, report_t: now - 240 },
    live: { pc: { t: now - 120, glance: { bots: [
      { id: 'lit', on: true, wait: 'London sweep of the Asia low', arm: [{ side: 'SHORT', text: 'stop 21,060.00 · target 20,980.00 (2.7R)', trig: 'Enters if price comes back to 21,040.00 before 11:00 ET.' }],
        lv: [['Asia high', 21088.5, 42.3], ['Asia low', 20994.25, -52]], why: 'No setup yet today.', log: [['10:20', 'swept the Asia high']] },
      { id: 'atlas', on: true, wait: 'EMA long running', pos: { side: 'LONG', qty: 2, entry: 21031, stop: 21016, target: 21061, risk_usd: 60, tgt_usd: 120, now_usd: 30 } }] } },
      reporter: { t: now - 240, na: now - 1800 } },
    board: { lit: { balance: 49193, room: 1025, mll: 2000, to_target: 3807, today_pnl: -50, window: { open: true, text: '02:00-15:30 ET' }, waiting: 'x' },
             atlas: { status: 'funded', balance: 24887, room: 887, mll: 1000, to_target: 2213, today_pnl: 0, payout_text: 'Ask $1,000 at $27,100.' },
             trades: [
               { acct: 'atlas', src: 'live', side: 'LONG', usd: 30, open: true, entry_t: now - 1500 },
               { acct: 'lit', src: 'live', side: 'LONG', usd: 312, r: 0.8, exit: 'TARGET', open: false, entry_t: Date.parse('2026-11-20T14:00:00Z') / 1000, exit_t: now - 3600 },
               { acct: 'lit', src: 'live', side: 'SHORT', usd: -402, r: -1, exit: 'STOP', open: false, entry_t: now - 90000, exit_t: now - 86000 },
               { acct: 'blitz', src: 'paper', side: 'LONG', usd: 99, open: false, entry_t: now - 100, exit_t: now - 50 }] },
    accounts: [
      { id: 'mffu50k_eval', name: 'Zlarior 50K', source: 'pc', live: true, conn: { t: now - 240 }, eval: { balance: 49193, room: 1025, mll: 2000, to_target: 3807, today: -50, status: 'open' } },
      { id: 'b25k_2', name: 'Zlarior 25K #2', source: 'pc', live: true, conn: { t: now - 3 * 3600 }, eval: { balance: 25000, room: 1000, mll: 1000, to_target: 1500, today: 0, status: 'open' } },
      { id: 'atlas', source: 'pc', live: true, from_board: true, conn: { t: now - 240 }, eval: { balance: 24887, room: 887, mll: 1000, to_target: 2213, today: 0, status: 'funded' } },
      { id: 'xtra9', name: 'Zlarior 50K #3', source: 'pc', live: true, conn: { t: now - 240 }, eval: { balance: 50100, room: 2000, mll: 2000, to_target: 2900, today: 100, status: 'open' } },
      { id: 'blitz', name: 'BLITZ', source: 'pc', live: true, eval: { balance: 1 } },
      { id: 'cloudtwin', source: 'cloud', eval: { balance: 99999 } }] };
  const news = { to: '2026-12-18', events: [{ date: '2026-11-20', time: '08:30', title: 'Jobless claims', impact: 'high' }, { date: '2026-11-20', time: '14:00', title: 'Fed speech', impact: 'high' },
    { date: '2026-11-21', time: '10:00', title: 'Low thing', impact: 'low' }, { date: '2026-12-04', time: '08:30', title: 'Non-Farm Payrolls', impact: 'high' }] };
  const file = { data_branch: { to: '2026-11-19' }, trades: [
    { src: 'live', bot: 'LIT', t: Date.parse('2026-11-20T14:00:00Z') / 1000 + 30, odeon: 'real.z50k.2026-11-20_0900_long', side: 'LONG', k: 'TARGET', day: '2026-11-20', twin: { backtest: { side: 'LONG', k: 'TARGET' } } },
    { src: 'live', bot: 'LIT', t: 1, side: 'SHORT', k: 'STOP', day: '2026-10-28', an: 'Zlarior 50K', twin: { paper: { side: 'SHORT', k: 'TARGET' } } },
    { src: 'live', bot: 'ATLAS', t: 2, side: 'SHORT', k: 'STOP', day: '2026-11-06', twin: null }, { src: 'backtest', bot: 'LIT', t: 3 }] };
  const o = {};
  const A = D.accounts(home, biz, now);
  o.acc = A.map((a) => [a.key, a.name, a.stage, a.balance, a.room, a.goalLabel, a.goalText, a.today, a.dot]);
  o.mffu = A.filter((a) => a.mffu).map((a) => [a.key, a.balance, a.floor]);
  o.accAge = A.map((a) => a.ageText);
  const B = D.thinking(home, news, file, now);
  o.lit = B[0]; o.atlas = B[1];
  const Q = D.quality(home, file, news, now);
  o.q = Q.rows.map((r) => [r.k, r.level, r.value]); o.qlevel = Q.level;
  o.qb = D.quality(home, file, news, now, null, { opens: [], last: 1, t: now - 95 * 60 }).rows.find((r) => r.k === 'bars');
  o.qb2 = D.quality(home, file, news, now, null, { opens: [], last: 1, t: now - 30 * 60 }).rows.find((r) => r.k === 'bars');
  const Qe = D.quality(home, file, news, now, { eh: { d: '2026-11-19', a: ['A', 1.9, 2.8, '2026-10-16'] } }); o.qe = Qe.rows.find((r) => r.k === 'edge');
  const h2 = JSON.parse(JSON.stringify(home)); delete h2.live.reporter.na; h2.pc_feed.report_t = now - 7200; h2.live.pc.t = now - 7200;
  const Q2 = D.quality(h2, { trades: [] }, null, now); o.q2 = Q2.rows.map((r) => [r.k, r.level, r.value]); o.q2level = Q2.level;
  o.stale = D.accounts(h2, biz, now).map((a) => a.dot);
  // the lead's real case (2026-11-20 03:45 ET): ATLAS short 1 MNQ @ 26,380.75, stop moved to 26,379.50, target 26,122.75, last bar 26,283.75
  const chart = { opens: [{ k: 'atlas25f', s: -1, q: 1, t: now - 85 * 60, e: 26380.75, sl: 26379.5, tp: 26122.75, be: 1 }, { k: 'blitz', s: 1, q: 1, t: now, e: 1 }], last: 26283.75, t: now - 180 };
  const B2 = D.thinking(home, news, file, now, chart), A2 = D.accounts(home, biz, now, chart);
  o.real = B2[1].inTrade; o.realLean = B2[1].before.lean; o.realAcct = A2.map((a) => [a.key, a.open ? [a.open.side, a.open.qty, a.open.entry, Math.round(a.open.now), a.open.stopMoved] : null]);
  o.realLit = B2[0].phase;
  // the day-brief helper's brief.json (docs/BRIEF.md v 1): its own examples (tests/fixtures/brief, copied from day-brief), and its absence
  const fs = require('fs'), FX = (n) => JSON.parse(fs.readFileSync(process.argv[3] + '/' + n + '.json', 'utf8'));
  const bToday = FX('brief_today'), bT1 = FX('brief_tier1'), bRecap = FX('brief_tier1_recap');
  const h3 = JSON.parse(JSON.stringify(home)); delete h3.live.pc.glance; delete h3.board.lit.waiting;   // no glance, no card words: the brief fills in (the bot's own live words win when there)
  const atDay = (d, hm) => Date.parse(d + 'T' + hm + ':00-05:00') / 1000;
  const n1 = atDay(bT1.day, '07:00'), Bb = D.thinking(h3, null, file, n1, null, bT1), Bt = D.thinking(h3, null, file, atDay(bToday.day, '07:00'), null, bToday);
  o.brief = { t1: [Bb[0].before.bias, Bb[0].before.news, Bb[0].before.levels.length, Bb[0].before.waiting.slice(0, 20), Bb[0].before.briefHead, Bb[1].before.waiting.slice(0, 40), Bb[1].before.briefHead],
    today: [Bt[0].before.bias && Bt[0].before.bias.side, Bt[0].before.bias && Bt[0].before.bias.context, Bt[0].before.stale] };
  o.briefRecap = D.briefFor(bRecap, 'lit', atDay(bRecap.day, '16:40')).recap;
  o.briefOld = D.thinking(h3, null, file, atDay(bT1.day, '07:00') + 2 * 86400, null, bT1)[0].before.bias;
  o.briefV2 = D.briefFor({ ...bT1, v: 2 }, 'lit', n1);
  o.briefJunk = [D.briefFor('x', 'lit', now), D.briefFor({ v: 1, bots: 5, bias: 7, market: { levels: [null, 1, [2]] } }, 'lit', now)];
  o.briefNone = D.thinking(h3, news, file, now, null, null)[0].before.bias;
  o.briefJunk = [D.briefFor('x', 'lit', now), D.briefFor({ bots: 5, bias: 7, levels: [null, 1, [2]] }, 'lit', now)];
  // N accounts from the feed (the PC adds the Rapid EOD 25K today, id "rapid", and maybe a 3rd Builder): every one gets a tile
  const h4 = JSON.parse(JSON.stringify(home));
  h4.accounts.push({ id: 'rapid', name: 'Rapid EOD 25K', source: 'pc', live: true, conn: { t: now - 240 }, eval: { balance: 25000, room: 1000, mll: 1000, to_target: 1500, today: 0, status: 'open' } });
  o.n4 = D.accounts(h4, biz, now).map((a) => [a.key, a.dot, a.balance]);
  // round 3: Ares gate, Kairos day line, Chronos past days
  const A5 = D.accounts(home, biz, now);
  o.gate = D.gate(A5, home, news, now).map((g) => [g.key, g.level, g.why[0].t]);
  const fri1700 = Date.parse('2026-11-20T22:30:00Z') / 1000, wed0100 = Date.parse('2026-11-18T06:00:00Z') / 1000;
  o.gateClosed = D.gate(A5, home, news, fri1700).map((g) => g.level);
  o.gateAsia = D.gate(A5, home, news, wed0100).map((g) => g.level);
  const newsSoon = { events: [{ date: '2026-11-20', time: '10:45', title: 'Fed speech', impact: 'high' }] };
  o.gateNews = D.gate(A5, home, newsSoon, now).find((g) => g.key === 'zlarior');
  const AD = A5.map((a) => (a.key === 'zlarior' ? { ...a, today: -1000 } : a));
  o.gateDll = D.gate(AD, home, news, now).find((g) => g.key === 'zlarior');
  o.phase = [D.phase(now).id, D.phase(fri1700).id, D.phase(wed0100).id, D.phase(Date.parse('2026-11-20T21:00:00Z') / 1000).id];
  const DLn = D.dayLine(home, now); o.day = [DLn.phase.id, Math.round(DLn.now * 1000) / 1000, DLn.dots.map((d) => [d.bot, d.open]), DLn.segs.length];
  o.past = D.pastDays({ trades: [{ day: '2026-10-28', bot: 'LIT', src: 'real', usd: -437 }, { day: '2026-10-28', bot: 'ATLAS', src: 'paper', usd: 100 }, { day: '2026-10-29', bot: 'BLITZ', usd: 5 },
    { day: '2026-10-27', bot: 'LIT', src: 'lit', usd: 300 }] });
  const junk = [null, undefined, 7, 'x', [], {}, { board: 5, live: [], accounts: 'no' }, { accounts: [null, 4, { id: 'mffu50k_eval' }], live: { pc: { glance: { bots: [null, { id: 'lit', arm: 'x', lv: [null, [1]] }] } } } }];
  o.junk = junk.map((j) => { try { return [D.accounts(j, j, now, j).length, D.thinking(j, j, j, now, j).length, D.quality(j, j, j, now).rows.length]; } catch (e) { return 'THROW ' + e.message; } });
  o.words = [D.money(-0.2), D.money(1234.5, true), D.rText(0.5), D.rText(-1.03), D.ageText(30), D.ageText(4 * 60), D.ageText(2 * 3600 + 600), D.mins(1500)];
  // night-nq-main 2026-11-27: the hero (today's $, each account's ring + room, LIT / ATLAS in one word, the phase + next)
  {
    const A = D.accounts(home, biz, now, chart), Bh = D.thinking(home, news, file, now, chart);
    const goalsL = [{ key: 'zlarior', frac: 0.25, big: '$3,807', unit: 'to pass', kind: 'pass', has: true }, { key: 'atlas', frac: 0.4, big: '$1,213', unit: 'to $2,100', kind: 'payout', has: true }];
    const H = D.hero(A, goalsL, Bh, home, now, false);
    o.hero = { today: H.today, todayText: H.todayText, tone: H.tone, level: H.level, nAcc: H.nAcc, phase: H.phase.id, next: H.nextText,
      accts: H.accts.map((a) => [a.key, a.frac, a.goalBig, a.room]), bots: H.bots.map((b) => [b.id, b.word, b.tone]), honest: H.honest, blitz: JSON.stringify(H).includes('BLITZ') };
    const Hn = D.hero(D.accounts({}, biz, now), [], D.thinking({}, null, null, now), {}, now, false);
    o.heroNone = { today: Hn.today, level: Hn.level, honest: Hn.honest, bots: Hn.bots.map((b) => b.word) };
    o.heroDemo = D.hero(A, goalsL, Bh, home, now, true).ageText;
    o.next = [D.nextUp(Date.parse('2026-11-20T06:30:00Z') / 1000), D.nextUp(Date.parse('2026-11-20T15:30:00Z') / 1000), D.nextUp(Date.parse('2026-11-21T15:00:00Z') / 1000)];
    o.words5 = [D.botState({ has: true, on: true, phase: 'before', before: { lean: { side: 'LONG', why: 'setup armed: x', trig: 'Enters at 1' }, waiting: '' } }).word,
      D.botState({ has: true, on: true, phase: 'before', before: { lean: { side: 'SHORT', why: 'setup forming: swept', trig: '' } } }).word,
      D.botState({ has: true, on: true, phase: 'before', before: { lean: { side: null, why: 'No lean yet' }, waiting: 'w' } }).word,
      D.botState({ has: true, on: false, phase: 'before', before: {} }).word, D.botState(null).word,
      D.botState({ has: true, on: true, phase: 'after', after: { usd: -40, exit: 'STOP', at: '9:00 AM ET' }, before: {} }).tone];
    o.heroJunk = junk.map((j) => { try { D.hero(j, j, j, j, now, false); return 'ok'; } catch (e) { return 'THROW ' + e.message; } });
  }
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_core():
    exe = shutil.which("node")
    if not exe:
        check("node tests skipped: no node", True)
        return
    tmp = tempfile.mkdtemp(prefix="nqdesk-")
    try:
        m = os.path.join(tmp, "nqdesk.mjs")
        shutil.copy(MOD, m)
        h = os.path.join(tmp, "h.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, h, m, os.path.join(ROOT, "tests", "fixtures", "brief")], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("the node harness runs", False, r.stderr[-800:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    acc = o["acc"]
    check("b. the owner's order, planned last, an extra PC account after, BLITZ and the cloud twin never",
          [a[0] for a in acc] == ["zlarior", "atlas", "fresh25", "rapid1", "xtra9"] and not any("BLITZ" in a[1] for a in acc), acc)
    check("b. Zlarior 50K: balance, room left, to pass, today, live dot", acc[0] == ["zlarior", "Zlarior 50K", "Eval", 49193, 1025, "To pass", "$3,807", -50, "live"], acc[0])
    check("b. ATLAS funded: 'To payout' from the board card (the payout coach's number), not 'To pass'", acc[1][2] == "Funded" and acc[1][5] == "To payout" and acc[1][6] == "$2,213", acc[1])
    check("b. ATLAS funded in MFFU's own terms (owner 2026-11-20: a sim-funded account starts at $0): $24,887 -> -$113, floor -$1,000; the evals keep their balance",
          acc[1][3] == -113 and o["mffu"] == [["atlas", -113, -1000]] and acc[0][3] == 49193, (acc[1], o["mffu"]))
    check("b. Zlarior 25K #2 last heard 3 h ago: red 'old' dot (over 1 h, age.js limits) and the site-wide words 'updated 3 h ago'", acc[2][8] == "old" and o["accAge"][2] == "updated 3 h ago", (acc[2], o["accAge"][2]))
    check("b. Rapid EOD 25K with no PC numbers: plan dot, says 'plan only'", acc[3][8] == "plan" and acc[3][3] is None and "plan only" in o["accAge"][3], (acc[3], o["accAge"][3]))
    check("b. a 2-hour-old report turns every PC account stale (the planned one stays plan)", o["stale"][:3] == ["old", "old", "old"] and o["stale"][3] == "plan", o["stale"])
    L = o["lit"]
    bf = L["before"]
    check("c. LIT before: lean SHORT from its armed setup (with the trigger), what it waits for, the open window",
          bf["lean"]["side"] == "SHORT" and "armed" in bf["lean"]["why"] and "21,040.00" in bf["lean"]["trig"] and bf["waiting"] == "London sweep of the Asia low"
          and bf["windowOpen"] is True and bf["window"] == "02:00-15:30 ET", bf)
    check("c. LIT before: today's high-impact news only (the 08:30 one is over), the next one named; key levels with price and distance",
          [(n["time"], n["past"]) for n in bf["news"]] == [("08:30", True), ("14:00", False)] and "Non-Farm Payrolls" in bf["next"] and "Fri" in bf["next"]
          and bf["levels"][0] == {"label": "Asia high", "px": 21088.5, "dist": 42.3}, (bf["news"], bf["next"], bf["levels"]))
    check("c. LIT after: today's closed trade, +$312 +0.8R by target, the reel link from trades.json; yesterday's trade is not 'today'",
          L["phase"] == "after" and L["after"]["usd"] == 312 and L["after"]["r"] == 0.8 and L["after"]["exit"] == "TARGET"
          and L["after"]["reel"] == "../odeon/#reel=real.z50k.2026-11-20_0900_long", L["after"])
    I = o["atlas"]["inTrade"]
    check("c. ATLAS in the trade: entry / stop / target, $ now, R so far = $30 / $60 = 0.5R, 25 min in trade",
          o["atlas"]["phase"] == "in" and I["side"] == "LONG" and I["entry"] == 21031 and I["stop"] == 21016 and I["target"] == 21061 and I["now"] == 30
          and abs(I["r"] - 0.5) < 1e-9 and I["since"] == 1500, I)
    check("c. ATLAS with no armed setup: its lean comes from its own words (LONG), never invented", o["atlas"]["before"]["lean"]["side"] == "LONG", o["atlas"]["before"]["lean"])
    q = {r[0]: r for r in o["q"]}
    check("d. quality on a fresh feed: report 4 min (ok), heartbeat 2 min (ok), last alert 30 min ago from the PC's reporter.na",
          q["report"][1] == "ok" and q["report"][2] == "updated 4 min ago" and q["beat"][1] == "ok" and q["alert"][1] == "ok" and q["alert"][2].startswith("30 min ago"), o["q"])
    check("d. twins: 1 match, 1 differ (live STOP vs twin TARGET), 1 no twin -> red; the worst level wins",
          q["twin"][2] == "1 match · 1 differ · 1 no twin yet" and q["twin"][1] == "bad" and o["qlevel"] == "bad", (q["twin"], o["qlevel"]))
    check("d. the edge check's data: LIT to Nov 19, ATLAS to Oct 16 (35 days) -> red, and it says ATLAS's PF is old; no edge.json -> no row",
          o["qe"]["value"] == "LIT to 2026-11-19 · ATLAS to 2026-10-16" and o["qe"]["level"] == "bad" and "35 days ago" in o["qe"]["note"]
          and "edge" not in q, o["qe"])
    check("d. chart candles in the bots' hours (Fri 10:30 ET): 95 min old -> amber with the age and the time; 30 min -> ok",
          o["qb"]["level"] == "warn" and o["qb"]["value"].startswith("last bar 1 h 35 min ago (8:55 AM ET)") and o["qb2"]["level"] == "ok", (o["qb"], o["qb2"]))
    br = o["brief"]["t1"]
    check("c. brief.json (docs/BRIEF.md v 1, day-brief's Tier-1 example): no bias call -> 'no call: <why_none>' shown as CONTEXT (context_only); "
          "today's CPI 08:30 (Tier 1); its levels; LIT's waiting_for; the headline once (LIT), ATLAS's legs joined",
          br[0]["side"] == "NONE" and br[0]["context"] is True and br[0]["text"].startswith("no call: the overnight move") and br[1][0]["time"] == "08:30"
          and "CPI" in br[1][0]["title"] and "(Tier 1)" in br[1][0]["title"] and br[2] >= 4 and br[3].startswith("A sweep of a level") and br[4] and br[5].startswith("EMA: ")
          and br[6] == "", br)
    check("c. ... today's example: the call is shown as context (works = false), the stale-data lines come through",
          o["brief"]["today"][1] is True and isinstance(o["brief"]["today"][2], list), o["brief"]["today"])
    check("c. ... after the close the recap's 'traded' line; a 2-day-old brief, another contract version or junk read as nothing; no brief = no line",
          o["briefRecap"].startswith("no trade data") and o["briefOld"] is None and o["briefV2"] is None and o["briefNone"] is None
          and o["briefJunk"][0] is None and o["briefJunk"][1]["bias"] is None and o["briefJunk"][1]["levels"] == [], (o["briefRecap"], o["briefOld"], o["briefJunk"]))
    check("b. N accounts: the PC's Rapid EOD 25K (id 'rapid') fills the planned Rapid tile with its numbers, the extra Builder keeps its own tile",
          ["rapid1", "live", 25000] in o["n4"] and ["xtra9", "live", 50100] in o["n4"] and len(o["n4"]) == 5 and o["n4"][-1][0] == "xtra9", o["n4"])
    gt = {g[0]: g for g in o["gate"]}
    check("r3. Ares -> GO / WAIT / HALT per account (Fri 10:30 ET, NY morning): Zlarior 50K GO with its room, the stale 25K #2 WAIT, the planned Rapid not listed",
          gt["zlarior"][1] == "go" and "$1,025 of room" in gt["zlarior"][2] and gt["fresh25"][1] == "wait" and "rapid1" not in gt, o["gate"])
    check("r3. ... Fri 17:30 ET = HALT for all (market closed); Wed 01:00 ET = WAIT (LIT takes no real entry before 02:00); news in 15 min = WAIT; a -$1,000 day on the 50K = HALT (MFFU daily loss limit)",
          set(o["gateClosed"]) == {"halt"} and o["gateAsia"][0] == "wait" and o["gateNews"]["level"] == "wait" and "Fed speech at 10:45" in o["gateNews"]["why"][0]["t"]
          and o["gateDll"]["level"] == "halt" and "Daily loss limit" in o["gateDll"]["why"][0]["t"], (o["gateClosed"], o["gateAsia"], o["gateNews"], o["gateDll"]))
    check("r3. Kairos -> the day line: phases (NY morning / closed / Asia / flat time), the now marker at 10:30 (16.5 of 23 h from 18:00), today's trades as dots (ATLAS open, Zlarior closed), 7 windows; no BLITZ",
          o["phase"] == ["nyam", "closed", "asia", "flat"] and o["day"][0] == "nyam" and o["day"][1] == round(990 / 1380, 3) and o["day"][2] == [["ATLAS", True], ["Zlarior", False]]
          and o["day"][3] == 7, (o["phase"], o["day"]))
    check("r3. Chronos -> past days newest first with their bots, $ and LIVE flag, each a ../chronos/#day link; BLITZ never",
          [(d["day"], d["bots"], d["usd"], d["real"], d["href"]) for d in o["past"]] == [("2026-10-28", "Zlarior + ATLAS", -337, True, "../chronos/#2026-10-28"), ("2026-10-27", "Zlarior", 300, False, "../chronos/#2026-10-27")], o["past"])
    q2 = {r[0]: r for r in o["q2"]}
    check("d. a 2-hour-old report: report red (over 1 h, age.js), a 2-hour-old heartbeat red (the bot beats every 5 min); without reporter.na the last alert is the "
          "newest trade event (ATLAS's entry 25 min ago); no news file -> amber",
          q2["report"][1] == "bad" and q2["beat"][1] == "bad" and q2["alert"][1] == "ok" and q2["alert"][2].startswith("25 min ago") and q2["news"][1] == "warn"
          and q2["twin"][2] == "no LIVE trade in trades.json", o["q2"])
    R = o["real"]
    check("c. the real open trade (ATLAS short 1 MNQ @ 26,380.75, 03:45 ET): from the chart post the stop as it is NOW (26,379.50) says 'moved to break-even' "
          "(+$2.50 locked), target 26,122.75 (+$516), open $ at the last bar 26,283.75 = +$194, 85 min in trade; the lean card says it is in this SHORT",
          R["side"] == "SHORT" and R["qty"] == 1 and R["entry"] == 26380.75 and R["stop"] == 26379.5 and R["stopMoved"] is True and R["locked"] == 2.5
          and R["target"] == 26122.75 and R["target_usd"] == 516 and R["now"] == 194 and R["since"] == 85 * 60 and R["lastAge"] == 180
          and o["realLean"]["side"] == "SHORT", (R, o["realLean"]))
    check("c. ... the accounts strip puts it on the ATLAS tile only (BLITZ's chart row never shows)",
          [a for a in o["realAcct"] if a[1]] == [["atlas", ["SHORT", 1, 26380.75, 194, True]]] and o["realLit"] == "after", o["realAcct"])
    check("e. junk input never throws", all(isinstance(j, list) for j in o["junk"]), o["junk"])
    h = o["hero"]
    check("hero: today = the sum of the accounts with numbers (-$50 + $0 + $0 + $100 = +$50, the 25K #2 stale one counted), its tone, the worst age wins (the 3-h-old 25K -> red); "
          "rings from the goals (Zlarior 25%, ATLAS 40%), none for an account without a goal; no BLITZ anywhere",
          h["today"] == 50 and h["todayText"] == "+$50" and h["tone"] == "up" and h["level"] == "bad" and h["nAcc"] == 4
          and ["zlarior", 0.25, "$3,807", 1025] in h["accts"] and ["atlas", 0.4, "$1,213", 887] in h["accts"] and not h["blitz"] and h["honest"] == "", h)
    check("hero: LIT / ATLAS in one word: the chart's open ATLAS short = IN TRADE (hot); Zlarior traded today = DONE TODAY; Fri 10:30 ET = NY morning, next = last new entries 15:30 in 5 h",
          h["bots"] == [["lit", "DONE TODAY", "up"], ["atlas", "IN TRADE", "hot"]] and h["phase"] == "nyam" and h["next"] == "Last new entries 15:30 in 5 h 0 min", h)
    check("hero: no report = no $, a red age, the honest line, both bots NO REPORT; the DEMO says example numbers",
          o["heroNone"]["today"] is None and o["heroNone"]["level"] == "bad" and "Nothing here is made up" in o["heroNone"]["honest"]
          and o["heroNone"]["bots"] == ["NO REPORT", "NO REPORT"] and o["heroDemo"] == "example numbers (DEMO)", (o["heroNone"], o["heroDemo"]))
    nx = o["next"]
    check("hero next: 01:30 ET -> London 02:00 in 30 min; 10:30 ET -> 15:30 in 5 h; Saturday -> CME reopens Sunday 18:00",
          nx[0]["label"].startswith("London") and nx[0]["inS"] == 1800 and nx[1]["inS"] == 5 * 3600 and nx[2]["inS"] is None and "Sunday" in nx[2]["label"], nx)
    check("hero words: SETUP ARMED / SETUP FORMING / WATCHING / OFF / NO REPORT; a losing closed trade = down",
          o["words5"] == ["SETUP ARMED", "SETUP FORMING", "WATCHING", "OFF", "NO REPORT", "down"], o["words5"])
    check("hero: junk input never throws", all(x == "ok" for x in o["heroJunk"]), o["heroJunk"])
    check("words: $ and R and ages", o["words"] == ["$0", "+$1,235", "+0.5R", "-1.0R", "just now", "4 min ago", "2 h 10 min ago", "25 min"], o["words"])


if __name__ == "__main__":
    test_static()
    test_core()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
