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
  // the day-brief helper's brief.json (contract not out yet: two likely shapes), and its absence
  const brief1 = { day: '2026-11-20', bias: { side: 'long', why: 'Above the overnight VWAP; Asia low swept' }, levels: [{ label: 'ONH', price: 26468.5 }],
    bots: [{ id: 'lit', waiting: 'a London sweep' }, { id: 'atlas', bias: { call: 'SHORT', text: 'under the 20 EMA' } }], recap: { lit: 'Took the 09:00 long, +0.8R.' } };
  const h3 = JSON.parse(JSON.stringify(home)); delete h3.live.pc.glance; delete h3.board.lit.waiting;   // no glance, no card words: the brief fills in (the bot's own live words win when there)
  const Bb = D.thinking(h3, news, file, now, null, brief1);
  o.brief = [Bb[0].before.bias, Bb[0].before.levels, Bb[0].before.waiting, Bb[0].before.recap, Bb[1].before.bias && Bb[1].before.bias.side];
  o.briefOld = D.thinking(h3, news, file, now, null, { ...brief1, day: '2026-11-19' })[0].before.bias;
  o.briefNone = D.thinking(h3, news, file, now, null, null)[0].before.bias;
  o.briefJunk = [D.briefFor('x', 'lit', now), D.briefFor({ bots: 5, bias: 7, levels: [null, 1, [2]] }, 'lit', now)];
  // N accounts from the feed (the PC adds the Rapid EOD 25K today, id "rapid", and maybe a 3rd Builder): every one gets a tile
  const h4 = JSON.parse(JSON.stringify(home));
  h4.accounts.push({ id: 'rapid', name: 'Rapid EOD 25K', source: 'pc', live: true, conn: { t: now - 240 }, eval: { balance: 25000, room: 1000, mll: 1000, to_target: 1500, today: 0, status: 'open' } });
  o.n4 = D.accounts(h4, biz, now).map((a) => [a.key, a.dot, a.balance]);
  const junk = [null, undefined, 7, 'x', [], {}, { board: 5, live: [], accounts: 'no' }, { accounts: [null, 4, { id: 'mffu50k_eval' }], live: { pc: { glance: { bots: [null, { id: 'lit', arm: 'x', lv: [null, [1]] }] } } } }];
  o.junk = junk.map((j) => { try { return [D.accounts(j, j, now, j).length, D.thinking(j, j, j, now, j).length, D.quality(j, j, j, now).rows.length]; } catch (e) { return 'THROW ' + e.message; } });
  o.words = [D.money(-0.2), D.money(1234.5, true), D.rText(0.5), D.rText(-1.03), D.ageText(30), D.ageText(4 * 60), D.ageText(2 * 3600 + 600), D.mins(1500)];
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
        r = subprocess.run([exe, h, m], capture_output=True, text=True, timeout=60)
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
    check("b. Zlarior 25K #2 last heard 3 h ago: stale dot (its own conn time)", acc[2][8] == "stale" and o["accAge"][2] == "3 h ago", (acc[2], o["accAge"][2]))
    check("b. Rapid EOD 25K with no PC numbers: plan dot, says 'plan only'", acc[3][8] == "plan" and acc[3][3] is None and "plan only" in o["accAge"][3], (acc[3], o["accAge"][3]))
    check("b. a 2-hour-old report turns every PC account stale (the planned one stays plan)", o["stale"][:3] == ["stale", "stale", "stale"] and o["stale"][3] == "plan", o["stale"])
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
          q["report"][1] == "ok" and q["report"][2] == "4 min ago" and q["beat"][1] == "ok" and q["alert"][1] == "ok" and q["alert"][2].startswith("30 min ago"), o["q"])
    check("d. twins: 1 match, 1 differ (live STOP vs twin TARGET), 1 no twin -> red; the worst level wins",
          q["twin"][2] == "1 match · 1 differ · 1 no twin yet" and q["twin"][1] == "bad" and o["qlevel"] == "bad", (q["twin"], o["qlevel"]))
    check("d. the edge check's data: LIT to Nov 19, ATLAS to Oct 16 (35 days) -> red, and it says ATLAS's PF is old; no edge.json -> no row",
          o["qe"]["value"] == "LIT to 2026-11-19 · ATLAS to 2026-10-16" and o["qe"]["level"] == "bad" and "35 days ago" in o["qe"]["note"]
          and "edge" not in q, o["qe"])
    check("d. chart candles in the bots' hours (Fri 10:30 ET): 95 min old -> amber with the age and the time; 30 min -> ok",
          o["qb"]["level"] == "warn" and o["qb"]["value"].startswith("last bar 1 h 35 min ago (8:55 AM ET)") and o["qb2"]["level"] == "ok", (o["qb"], o["qb2"]))
    br = o["brief"]
    check("c. brief.json (day-brief) when there: the morning bias (LONG + why), its levels, what LIT waits for and the recap when the glance has none; "
          "ATLAS's own bias call (SHORT)", br[0] == {"side": "LONG", "text": "Above the overnight VWAP; Asia low swept", "conf": None}
          and br[1] == [{"label": "ONH", "px": 26468.5, "dist": None}] and br[2] == "a London sweep" and br[3] == "Took the 09:00 long, +0.8R." and br[4] == "SHORT", br)
    check("c. ... yesterday's brief or none: no bias line, nothing breaks; junk briefs read as nothing", o["briefOld"] is None and o["briefNone"] is None
          and o["briefJunk"][0] is None and o["briefJunk"][1]["bias"] is None and o["briefJunk"][1]["levels"] == [], (o["briefOld"], o["briefJunk"]))
    check("b. N accounts: the PC's Rapid EOD 25K (id 'rapid') fills the planned Rapid tile with its numbers, the extra Builder keeps its own tile",
          ["rapid1", "live", 25000] in o["n4"] and ["xtra9", "live", 50100] in o["n4"] and len(o["n4"]) == 5 and o["n4"][-1][0] == "xtra9", o["n4"])
    q2 = {r[0]: r for r in o["q2"]}
    check("d. a 2-hour-old report: report amber, a 2-hour-old heartbeat red (the bot beats every 5 min); without reporter.na the last alert is the "
          "newest trade event (ATLAS's entry 25 min ago); no news file -> amber",
          q2["report"][1] == "warn" and q2["beat"][1] == "bad" and q2["alert"][1] == "ok" and q2["alert"][2].startswith("25 min ago") and q2["news"][1] == "warn"
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
    check("words: $ and R and ages", o["words"] == ["$0", "+$1,235", "+0.5R", "-1.0R", "just now", "4 min ago", "2 h 10 min ago", "25 min"], o["words"])


if __name__ == "__main__":
    test_static()
    test_core()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
