"""NQ, "the NQ bots, right now" (tools/web_public/nq/, AGORA look, 2026-11-11): one page built for trust. Per bot (Zlarior / LIT 50K, ATLAS 25K, BLITZ 25K) the status with the
exact age of the last report, drawdown left, the day's P&L in $ with R, the eval progress; the last 10 trades with the rule that closed each; the plan in one sentence; the backtest
facts with dates; an honest banner when the PC is silent and the three steps that bring reporting back (howto.json = docs/NQ_BOT_BACK.md).

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the 3D module is separate and optional, howto.json matches the doc
  b. the rules in node (nqcore.js): the three statuses and their ages, the 20-minute flame, drawdown / P&L / progress lines, the trades and their closing rules, the plan, the facts, the banner, junk input
  c. Chromium 390 x 844 (and 375 x 667 LITE): DEMO, a real home.json fresh and four days old, the banner and its sheet, the 3D columns (or the 2D fallback), taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_nq_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "nq", "NQ"
check = AK.check
SILENT = "The bots may still be trading; this page just is not hearing from them."


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "./howto.json", "./news_week.json", "../hub/learned.json", "../business/accounts.json", "../trading/trades.json"))   # + the news week and real fills (night-nqdash2); the account list + twins (nqdash3)
    d = os.path.join(AK.WEB, APP)
    js, core, scene, html, css = (AK.read(os.path.join(d, n)) for n in ("nq.js", "nqcore.js", "nqscene.js", "index.html", "nq.css"))
    check("a. it never reads the 8 MB data.json: only home.json, its howto.json and its fixture", "data.json" not in re.sub(r"//[^\n]*", "", js + core) and "../home.json" in js)
    check("a. the 3D scene is its own optional module loaded by the page, never imported by nq.js", "nqscene.js" in html and "from './nqscene" not in js and "NQ3D" in js)
    check("a. the scene uses the local three.js only, no bloom, no neon, no network; three columns", "../jarvis/three.module.min.js" in scene and not re.search(r"https?://|Bloom|UnrealBloom", scene) and "slice(0, 3)" in scene)
    check("a. the flame rule is 20 minutes, in one place (FRESH_S), and the scene only lights what the core says", "FRESH_S = 20 * 60" in core and "lit: b.status.flame" in core and "u.lit" in scene)
    fx = json.loads(AK.read(os.path.join(d, "fixture.json")))
    check("a. the fixture is a DEMO home.json (board, the PC block) with ages instead of dates and a 'not real' note", fx["demo"] is True and "not real" in fx["note"].lower() and "board" in fx["home"] and fx["home"]["live"]["pc"]["t_ago_min"] == 4
          and len(fx["home"]["board"]["trades"]) >= 10)
    dv = json.loads(AK.read(os.path.join(AK.ROOT, "dashboard_view.json")))
    check("a. the DEMO follows the owner's view switch: fixture home.hidden_bots == dashboard_view.json hidden_bots (BLITZ off every page, the example too)",
          fx["home"].get("hidden_bots") == dv.get("hidden_bots"), (fx["home"].get("hidden_bots"), dv.get("hidden_bots")))
    check("a. the page order: the banner, the three columns, the plan, the bots, the trades, the backtest facts, more",
          html.index('id="banner"') < html.index('id="sceneCard"') < html.index('id="planCard"') < html.index('id="bots"') < html.index('id="tradesCard"') < html.index('id="factsCard"') < html.index('id="moreCard"'))
    check("a. the honest words are on the page: the banner sentence, 'Backtest, not a promise', the 5-step button twice (banner + More), the link to the full dashboard",
          SILENT in html and SILENT in core and "Backtest, not a promise" in html and html.count("Bring the bots back (3 steps)") == 2 and 'href="../"' in html)
    check("a. the sheet is a labelled dialog with a Close button; Escape and the veil close it", 'role="dialog"' in html and 'aria-modal="true"' in html and 'id="sheetClose"' in html and "'Escape'" in js and "veil" in js)
    check("a. paper only is said in plain words (never places an order; cannot start, stop or change a bot)", "never places an order" in html and "cannot start, stop or change a bot" in html)
    # phone QA 2026-11-19: a funded account (ATLAS) read "Eval progress: Not yet: need $1,463 more" (its payout line); the status lines above
    # the chart filled in after the page showed and pushed the chart card down
    check("a. a funded account's progress row says 'Payout progress' (no eval there); the status lines above the chart hold their space",
          "b.funded ? 'Payout progress' : 'Eval progress'" in js and "funded: true" in core and "#status { min-height: 3lh; }" in html)
    # howto.json = docs/NQ_BOT_BACK.md
    r = subprocess.run([sys.executable, os.path.join(AK.ROOT, "tools", "nq_howto_build.py"), "--check"], capture_output=True, text=True)
    hw = json.loads(AK.read(os.path.join(d, "howto.json")))
    check("a. howto.json is the doc's steps (tools/nq_howto_build.py --check passes): 3 numbered steps (owner 2026-11-12: BOTS_BACK), step 1 is the zip update, step 2 BOTS_BACK.bat, step 3 the ntfy app, the undo line, no markup",
          r.returncode == 0 and [s["n"] for s in hw["steps"]] == [1, 2, 3] and "UPDATE_FROM_ZIP.bat" in hw["steps"][0]["text"] and "BOTS_BACK.bat" in hw["steps"][1]["title"]
          and "ntfy" in json.dumps(hw["steps"][2]) and "UNDO_UPDATE.bat" in hw["undo"] and "<" not in json.dumps(hw) and "**" not in json.dumps(hw), (r.stdout, hw["steps"][:1]))
    doc = AK.read(os.path.join(AK.ROOT, "docs", "NQ_BOT_BACK.md"))
    steps = re.findall(r"^\d+\. \*\*", doc.split("## Do this")[1].split("\n## ")[0], re.M)
    check("a. docs/NQ_BOT_BACK.md has at most 5 steps and the update step is folded in", 1 <= len(steps) <= 5 and "UPDATE_FROM_ZIP.bat" in doc and "UNDO_UPDATE.bat" in doc, len(steps))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {}, NOW = Date.parse('2026-11-06T21:30:00Z'), T = NOW / 1000, M = 60, H = 3600, D = 86400;
  const home = (age, o2) => Object.assign({ live: { pc: { t: T - age, running: true, second: { t: T - age }, blitz: { t: T - age, eval: { start_balance: 25000, balance: 24607.28, profit: -392.72, today: 0, room: 607.28, target: 26500, to_target: 1892.72 }, state: { text: 'No more checks today.' }, today: [] } } },
    board: { data_t: T - age, running: true,
      lit: { balance: 49313.54, room: 1145.34, mll: 2000, to_target: 3686.46, target_balance: 53000, profit: -686.46, today_pnl: 0, waiting: 'Entry window closed at 15:30 ET with no trade today.' },
      atlas: { balance: 25182.19, room: 822.24, mll: 1000, to_target: 1317.81, target_balance: 26500, profit: 182.19, today_pnl: -168.81, waiting: 'Done for today.' },
      trades: [
        { acct: 'atlas', src: 'live', key: 'ema_lon_vix', member: 'EMA', day: '2026-11-06', entry_t: T - 12 * H, exit_t: T - 12 * H + 300, side: 'SHORT', exit: 'STOP', r: -1.029, usd: -168.81, open: false },
        { acct: 'lit', src: 'paper', key: 'lit', day: '2026-11-03', entry_t: 1793738340, exit_t: 1793739360, side: 'LONG', exit: 'TIME', r: 0.2, usd: 27.1, open: false },
        { acct: 'atlas', src: 'paper', key: 'sr_nyreclaim', member: 'S/R', day: '2026-11-03', entry_t: 1793722200, exit_t: 1793723100, side: 'SHORT', exit: 'TARGET', r: 1.975, usd: 912.6, open: false },
        { acct: 'lit', src: 'paper', key: 'lit', day: '2026-10-28', entry_t: 1793181960, exit_t: 1793191740, side: 'SHORT', exit: 'STOP', r: -1.0, usd: -699, open: false },
        { acct: 'lit', src: 'live', key: 'lit', day: '2026-10-27', entry_t: 1793086200, exit_t: 1793086200 + 1200, side: 'LONG', exit: 'TIME', r: 0.3, usd: 120, open: false },
        { acct: 'lit', src: 'live', key: 'lit', day: '2026-10-26', entry_t: 1793000000, exit_t: 1793003000, side: 'LONG', exit: 'BE', r: 0.01, usd: 4, open: false },
        { acct: 'lit', src: 'live', key: 'lit', day: '2026-10-23', entry_t: 1792700000, exit_t: 1792703000, side: 'LONG', exit: 'TARGET', r: 8, usd: 3200, open: false },
        { acct: 'atlas', src: 'paper', key: 'macd_sweep', member: 'MACD', day: '2026-10-22', entry_t: 1792600000, exit_t: 1792603000, dir: 1, exit_kind: 'LIT', r: 0.9, usd: 140 },
      ] },
    results: { periods: { '2026 H2 (check)': { from: '2026-07-01', to: '2026-10-16', trades: 40, pf: 2.91, net: 9918.78, per_month: 2670 } } } }, o2 || {});
  // ages
  o.ages = [C.ageText(20), C.ageText(60), C.ageText(47 * M), C.ageText(5 * H + 12 * M), C.ageText(2 * H), C.ageText(4 * D + 3 * H + 5 * M), C.ageText(D), C.ageText(4 * D)];
  // statuses at the edges of 20 minutes and 36 hours
  const st = (age, run) => { const s = C.status(T - age, run, T); return [s.code, s.level, s.label, s.flame]; };
  o.status = [st(3 * M, true), st(20 * M, true), st(20 * M + 1, true), st(36 * H, true), st(36 * H + 1, true), st(3 * M, false), C.status(null, true, T).code, C.status(T + 120, true, T).code, st(4 * D, true)];
  // fresh
  const f = C.build(home(3 * M), NOW);
  o.fresh = { headline: f.headline, banner: f.banner, lit: f.columns.map((c) => c.lit), labels: f.bots.map((b) => b.status.label), dd: f.bots.map((b) => b.ddLine), today: f.bots.map((b) => b.todayText), day: f.bots.map((b) => b.dayLabel),
    prog: f.bots.map((b) => b.progLine), line: f.bots[0].status.line, plan: f.plan, tight: f.tight.key, paper: f.bots.map((b) => b.paper), frac: f.bots.map((b) => Math.round(b.roomFrac * 100)) };
  o.trades = f.trades.map((t) => [t.name, t.member, t.dayLabel, t.side, t.text, t.rule, t.src, t.sign]);
  // waiting (5 hours) and stale (4 days)
  const w = C.build(home(5 * H), NOW), s = C.build(home(4 * D + 3 * H), NOW);
  o.wait = { banner: w.banner, labels: w.bots.map((b) => b.status.label), lit: w.columns.map((c) => c.lit), line: w.bots[0].status.line, plan: w.plan.note };
  o.stale = { banner: s.banner, labels: s.bots.map((b) => b.status.label), lit: s.columns.map((c) => c.lit), headline: s.headline, day: s.bots[1].dayLabel, today: s.bots[1].todayText, dd: s.bots[0].ddLine, line: s.bots[0].status.line };
  // one bot newer than the others: only its flame burns
  const mixed = home(2 * D); mixed.live.pc.blitz.t = T - 5 * M;
  const mx = C.build(mixed, NOW); o.mixed = [mx.columns.map((c) => c.lit), mx.bots.map((b) => b.status.code), mx.banner && mx.banner.title, mx.burning];
  // the PC reports but the bot is stopped there
  const stp = home(2 * M); stp.live.pc.running = false; const sp = C.build(stp, NOW); o.stopped = [sp.bots[0].status.label, sp.bots[0].status.flame, sp.banner];
  // a bot without numbers, an estimate R, a passed target
  const part = home(3 * M); delete part.board.atlas; delete part.live.pc.blitz; part.board.lit.today_pnl = -425; part.board.trades = [];
  const pv = C.build(part, NOW); o.part = [pv.bots.map((b) => b.has), pv.bots[1].status.code, pv.bots[1].ddLine, pv.bots[0].todayText, pv.trades.length, pv.bots[2].status.flame];
  const pass = home(3 * M); pass.board.lit.to_target = -20; pass.board.lit.profit = 3020; o.pass = C.build(pass, NOW).bots[0].progLine;
  // fall back to the accounts list (no board)
  const acc = { live: { pc: { t: T - 60, running: true } }, accounts: [{ id: 'cloud_paper', name: 'Paper (cloud)', plan: 'MFFU 50K rules', source: 'cloud', eval: { room: 389 } },
    { id: 'mffu50k_eval', name: 'MFFU 50K Eval', plan: 'Builder 50K', source: 'pc', eval: { start_balance: 50000, balance: 49313.54, room: 1145.34, mll: 2000, to_target: 3686.46, target_balance: 53000 }, pnl: { today: 12 } }] };
  const av = C.build(acc, NOW); o.acc = [av.bots[0].ddLine, av.bots[0].todayText, av.bots[0].status.code, C.hasData(acc)];
  // rules
  o.rules = [C.ruleText('STOP', 'lit', 0), C.ruleText('STOP', 'atlas', 0), C.ruleText('TARGET', 'lit', 0), C.ruleText('BE', 'lit', 0), C.ruleText('TIME', 'lit', 1793739360), C.ruleText('TIME', 'lit', 1793739360 - 3 * H), C.ruleText('TIME', 'blitz', 0), C.ruleText('LIT', 'atlas', 0), C.ruleText('weird', 'lit', 0), C.ruleText('', 'lit', 0)];
  // facts
  const fa = C.facts(home(0)), fb = C.facts({}); o.facts = [fa.map((x) => x.line), fa[0].dates, fa[0].trades, fb[0].line === fa[0].line, fb[2].line];
  // money
  o.money = [C.both(312, 0.8, 425), C.both(-425, null, 425), C.both(0, null, 425), C.both(0.3, null, 425), C.drawdownLine(1145.34, 2000), C.rFmt(-0.04), C.money(-0.2)];
  // junk
  const junk = [null, undefined, 7, 'x', [], {}, { board: 5, live: [], accounts: 'no' }, { board: { lit: { room: 'abc' }, trades: [null, 3, {}, { usd: 'x' }] }, live: { pc: { t: 'never', blitz: 'no' } } }];
  o.junk = junk.map((j) => { try { const v = C.build(j, NOW); return [v.bots.length, v.bots.every((b) => !b.status.flame), v.trades.length, !!v.banner, v.facts.length, C.hasData(j)]; } catch (e) { return 'THROW ' + e.message; } });
  // the CME trading day (polish2 2026-11-19): 18:00 ET starts the next day, so a 23:30 ET stop-out and a 00:40 ET report are one day
  const N2 = Date.parse('2026-11-19T05:40:00Z'), T2 = N2 / 1000, night = home(T - T2 + 5 * M);   // reported 00:35 ET
  night.board.trades = [{ acct: 'atlas', src: 'live', key: 'ema_lon_vix', member: 'EMA', entry_t: Date.parse('2026-11-19T04:25:00Z') / 1000, exit_t: Date.parse('2026-11-19T04:30:00Z') / 1000, side: 'SHORT', exit: 'STOP', r: -1.029, usd: -168.81, open: false }];
  const nv = C.build(night, N2);
  o.cme = [C.tradingDay(Date.parse('2026-11-18T22:59:00Z') / 1000), C.tradingDay(Date.parse('2026-11-18T23:00:00Z') / 1000), C.tradingDay(T2), nv.bots[1].todayText, nv.bots[1].dayLabel, nv.trades[0].day, C.tradingDay(null)];
  // the sheet
  const hw = C.howto({ title: 'How to bring reporting back', intro: 'i', steps: [{ n: 1, title: 'A', text: 'Netlify > avatar > tokens', code: 'python x' }, { title: 'B' }, 4, { title: '<b>C</b>' }, { title: 'D' }, { title: 'E' }, { title: 'F' }], undo: 'u', limits: ['l1', 5, 'l2'] });
  o.howto = [hw.steps.length, hw.steps[0].text, hw.steps[0].code, hw.steps[2].title, hw.limits, C.howto(null), C.howto({ steps: [] })];
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_rules():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node tests skipped: no node", True)
        return
    if "_error" in o:
        check("b. the node harness runs", False, o["_error"])
        return
    check("b. ages in plain words, exact: under a minute, minutes, hours + minutes, days + hours",
          o["ages"] == ["less than a minute ago", "1 minute ago", "47 minutes ago", "5 hours 12 minutes ago", "2 hours ago", "4 days 3 hours ago", "1 day ago", "4 days ago"], o["ages"])
    s = o["status"]
    check("b. status: Running up to 20 minutes (flame), Waiting for the PC up to 36 hours (no flame), then Stale; a stopped bot that still reports keeps its flame; no report = No report yet; a clock a little ahead is not an error",
          s[0] == ["running", "ok", "Running", True] and s[1][0] == "running" and s[2] == ["waiting", "warn", "Waiting for the PC", False] and s[3][0] == "waiting" and s[4] == ["stale", "bad", "Stale", False]
          and s[5] == ["stopped", "warn", "Stopped on the PC", True] and s[6] == "none" and s[7] == "running" and s[8][0] == "stale", s)
    f = o["fresh"]
    check("b. fresh report: no banner, three flames, 'Running' x3, the headline counts them", f["banner"] is None and f["lit"] == [True, True, True] and f["labels"] == ["Running"] * 3 and f["headline"] == "3 of 3 bots reported in the last 20 minutes." and f["line"] == "Reported 3 minutes ago.", f)
    check("b. 'Drawdown left $X of $max loss' for each bot, with the share left", f["dd"] == ["Drawdown left $1,145 of $2,000 max loss", "Drawdown left $822 of $1,000 max loss", "Drawdown left $607 of $1,000 max loss"] and f["frac"] == [57, 82, 61] and f["tight"] == "lit", (f["dd"], f["frac"], f["tight"]))
    check("b. the CME trading day (18:00 ET starts the next): 17:59 ET is still Nov 18, 18:00 ET is Nov 19; a 23:30 stop-out and a 00:40 report are one day, its own R (no ~), 'Today'",
          o["cme"] == ["2026-11-18", "2026-11-19", "2026-11-19", "-$169 (-1.0R)", "Today", "2026-11-19", ""], o["cme"])
    check("b. today's P&L in $ with its R (the R of that day's trades), labelled Today on the report day", f["today"] == ["$0 (0.0R)", "-$169 (-1.0R)", "$0 (0.0R)"] and f["day"] == ["Today"] * 3, (f["today"], f["day"]))
    check("b. eval progress to the target in plain words; BLITZ is marked paper", f["prog"] == ["$3,686 to go to the $3,000 target (0% done)", "$1,318 to go to the $1,500 target (12% done)", "$1,893 to go to the $1,500 target (0% done)"] and f["paper"] == [False, False, True], f["prog"])
    check("b. the plan is one sentence with the LIT rules (02:00-15:30 ET, flat 15:55), plus what the bot said when it is fresh",
          f["plan"]["rule"] == "LIT looks for one trade between 02:00 and 15:30 ET and is flat by 15:55 ET." and f["plan"]["now"].startswith("Entry window closed") and f["plan"]["note"] == "", f["plan"])
    t = o["trades"]
    check("b. the last trades, newest first, each with $ and R, its side, paper or eval account",
          len(t) == 8 and t[0] == ["ATLAS", "EMA", "Fri 6 Nov", "Short", "-$169 (-1.0R)", "Stop hit", "eval account", "neg"] and t[1][:5] == ["Zlarior", "", "Tue 3 Nov", "Long", "+$27 (+0.2R)"] and t[1][6] == "paper" and t[7][3] == "Long", t[:2])
    rules = [x[5] for x in t]
    check("b. the rule that closed each trade in plain words (stop beyond the sweep, target at 8R, breakeven after +1R, flat 15:55, the 15-minute cut, closed because LIT entered)",
          rules == ["Stop hit", "Flat by 15:55 ET rule", "Target reached", "Stop hit: 1 tick beyond the sweep extreme", "Time rule: the 15-minute cut", "Breakeven stop: moved to entry after +1R", "Target reached: the VIX-band objective, banked at 8R", "Closed because LIT entered"], rules)
    r = o["rules"]
    check("b. ruleText covers every kind and never returns nothing", r[0].startswith("Stop hit: 1 tick") and r[1] == "Stop hit" and r[4] == "Flat by 15:55 ET rule" and r[5] == "Time rule: the 15-minute cut" and r[6].startswith("Time exit") and r[8] == "Closed: weird" and r[9] == "Closed", r)
    w, st = o["wait"], o["stale"]
    check("b. 5 hours silent: the banner (warn) with the exact age and the honest sentence, 'Waiting for the PC' x3, no flame, the plan says it only knows the rules",
          w["banner"] == {"level": "warn", "title": "Last report from your PC: 5 hours ago.", "text": SILENT} and w["labels"] == ["Waiting for the PC"] * 3 and w["lit"] == [False] * 3 and "not known while the PC is silent" in w["plan"], w)
    check("b. 4 days silent: the big banner (bad) 'Last report from your PC: 4 days 3 hours ago.', Stale x3, no flame, the old day is named instead of 'Today', the old numbers stay readable",
          st["banner"] == {"level": "bad", "title": "Last report from your PC: 4 days 3 hours ago.", "text": SILENT} and st["labels"] == ["Stale"] * 3 and st["lit"] == [False] * 3 and st["headline"] == "Last report from your PC: 4 days 3 hours ago."
          and st["day"] == "Mon 2 Nov (the last report)" and st["today"].startswith("-$169") and st["dd"].startswith("Drawdown left $1,145") and "old numbers" in st["line"], st)
    check("b. each bot has its own report time: only the one that reported in the last 20 minutes burns", o["mixed"][0] == [False, False, True] and o["mixed"][1] == ["stale", "stale", "running"] and o["mixed"][2] == "Last report from your PC: 2 days ago." and o["mixed"][3] == 1, o["mixed"])
    check("b. the PC reports that the bot is stopped: 'Stopped on the PC', the flame still burns (it reported), no banner", o["stopped"] == ["Stopped on the PC", True, None], o["stopped"])
    p = o["part"]
    check("b. a bot the PC did not report: 'No report yet', no flame, no made-up numbers; a day's $ without a trade gets an estimated R (~)", p[0] == [True, False, False] and p[1] == "none" and p[2] == "Drawdown not reported yet" and p[3] == "-$425 (~-1.0R)" and p[4] == 0 and p[5] is False, p)
    check("b. a passed target reads 'Target of $3,000 reached'", o["pass"] == "Target of $3,000 reached", o["pass"])
    check("b. without the board block it reads the PC's eval account (never the cloud paper twin)", o["acc"] == ["Drawdown left $1,145 of $2,000 max loss", "+$12 (~0.0R)", "running", True], o["acc"])
    fa = o["facts"]
    check("b. the backtest facts with their dates: H2 check 'PF 2.91, +$9,919, about $2,670 a month', 1 Jul 2026 to 16 Oct 2026, 40 trades; the built-in copy is the same; the 5-year reference is shown honestly (about break-even)",
          fa[0][0] == "PF 2.91, +$9,919, about $2,670 a month" and fa[0][1].startswith("PF 4.19, +$43,820") and fa[1] == "1 Jul 2026 to 16 Oct 2026" and fa[2] == 40 and fa[3] is True and fa[4].startswith("PF 1.01, +$1,265"), fa)
    check("b. money words: $ with R, ~ only for an estimate, no '-$0'", o["money"] == ["+$312 (+0.8R)", "-$425 (~-1.0R)", "$0 (0.0R)", "$0 (0.0R)", "Drawdown left $1,145 of $2,000 max loss", "0.0R", "$0"], o["money"])
    check("b. junk input never throws: three bots, no flame, a banner, the facts", all(j == [3, True, 0, True, 3, j[5]] for j in o["junk"]) and not any(o["junk"][i][5] for i in range(6)), o["junk"])
    h = o["howto"]
    check("b. the sheet: at most 5 steps, '>' kept as text, the copy line, markup characters dropped, junk rows skipped, nothing when there are no steps",
          h[0] == 5 and h[1] == "Netlify > avatar > tokens" and h[2] == "python x" and h[3] == "b>C/b>" and h[4] == ["l1", "5", "l2"] and h[5] is None and h[6] is None, h)


def home_json(age_s, trades=True):
    """A real-shaped home.json whose PC report is age_s old (the shape of the 2026-11-06 site)."""
    t = int(time.time()) - age_s
    # every board row carries its CME trading day (engine/live_board.trading_day: 18:00 ET starts the next day); without it the
    # ATLAS trade 11 hours before the report fell on another calendar day between midnight and 11:00 ET, and the day's R became
    # an estimate (polish2 2026-11-19: the check failed every night)
    from engine.live_board import trading_day
    import datetime as _dt
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    d0 = _dt.date.fromisoformat(trading_day(t)) - _dt.timedelta(days=1)
    start = int(_dt.datetime(d0.year, d0.month, d0.day, 18, 0, tzinfo=ny).timestamp())          # 18:00 ET: this report's session began
    x_exit = min(t - 30, max(t - 39700, start + 600))                                             # the ATLAS stop-out: inside that session
    return json.dumps({"built": "x", "home_only": True,
        "live": {"pc": {"present": True, "t": t, "running": True, "second": {"t": t}, "blitz": {"t": t, "eval": {"start_balance": 25000.0, "balance": 24607.28, "profit": -392.72, "today": 0.0, "room": 607.28, "target": 26500.0, "to_target": 1892.72}, "state": {"text": "No more checks today."}, "today": []}}},
        "board": {"data_t": t, "running": True,
                  "lit": {"name": "Zlarior", "balance": 49313.54, "room": 1145.34, "mll": 2000.0, "to_target": 3686.46, "target_balance": 53000.0, "profit": -686.46, "today_pnl": 0.0, "waiting": "Entry window closed at 15:30 ET with no trade today. Next chance tomorrow from 02:00 ET."},
                  "atlas": {"name": "ATLAS", "balance": 25182.19, "room": 822.24, "mll": 1000.0, "to_target": 1317.81, "target_balance": 26500.0, "profit": 182.19, "today_pnl": -168.81, "waiting": "EMA: Done for today (1 trade a day)"},
                  "trades": [{"acct": "atlas", "src": "live", "key": "ema_lon_vix", "member": "EMA", "day": trading_day(x_exit), "entry_t": x_exit - 300, "exit_t": x_exit, "side": "SHORT", "exit": "STOP", "r": -1.029, "usd": -168.81, "open": False},
                             {"acct": "lit", "src": "paper", "key": "lit", "day": "2026-11-03", "entry_t": 1793738340, "exit_t": 1793739360, "side": "LONG", "exit": "TIME", "r": 0.2, "usd": 27.1, "open": False}] if trades else []},
        "results": {"periods": {"2026 H2 (check)": {"from": "2026-07-01", "to": "2026-10-16", "trades": 40, "pf": 2.91, "net": 9918.78, "per_month": 2670.0}}}})


def demo_today():
    """The DEMO's Zlarior day: its +$312 trade closed 90 minutes ago, so its own R (+0.8R) counts when that is the same CME trading day
    as now; in the first 90 minutes of a session (18:00-19:30 ET) the trade is the last session's and the R is the estimate (~)."""
    from engine.live_board import trading_day
    now = int(time.time())
    return "+$312 (+0.8R)" if trading_day(now - 90 * 60) == trading_day(now) else "+$312 (~+0.7R)"


SNAP = """() => ({ demo: !document.querySelector('#demo').hidden, banner: !document.querySelector('#banner').hidden, btitle: document.querySelector('#bannerTitle').textContent, btext: document.querySelector('#bannerText').textContent,
  level: document.querySelector('#banner').dataset.level, pills: [...document.querySelectorAll('#bots .bot .pill')].map((e) => e.textContent), dd: [...document.querySelectorAll('#bots .dd')].map((e) => e.textContent),
  kv: [...document.querySelectorAll('#bots .kv dd')].map((e) => e.textContent), dt: [...document.querySelectorAll('#bots .kv dt')].map((e) => e.textContent), when: [...document.querySelectorAll('#bots .when')].map((e) => e.textContent),
  trades: [...document.querySelectorAll('#trades .trade')].map((e) => e.textContent), rules: [...document.querySelectorAll('#trades .rule')].map((e) => e.textContent), plan: document.querySelector('#planRule').textContent,
  planNote: document.querySelector('#planNote').hidden ? '' : document.querySelector('#planNote').textContent, facts: [...document.querySelectorAll('#facts .fline')].map((e) => e.textContent), factNote: document.querySelector('#facts .note').textContent,
  pill: document.querySelector('#factsPill').textContent, flames: document.querySelectorAll('#fallback .flame').length, legend: [...document.querySelectorAll('#legend .leg')].map((e) => e.dataset.lit), scene: window.NQ.S.scene,
  note: document.querySelector('#sceneNote').textContent, status: document.querySelector('#status').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
  bars: document.querySelectorAll('#bots .meter').length })"""


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve({"/home.json": None})
    try:
        with AK.browser() as br:
            # DEMO
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&flat=1")
            d = p.evaluate(SNAP)
            # night-polish 2026-11-20: the DEMO hides BLITZ too (owner 2026-11-15, dashboard_view.json hidden_bots: BLITZ off every page); was three bots
            check("c. DEMO (the fixture): the chip, no banner, two flames in the 2D picture (BLITZ hidden), 'Running' x2, two 'Drawdown left ... of ... max loss' lines, two bars per bot",
                  d["demo"] and not d["banner"] and d["flames"] == 2 and d["legend"] == ["1", "1"] and d["pills"] == ["Running"] * 2 and d["scene"] == "2d" and d["bars"] == 4
                  and d["dd"] == ["Drawdown left $1,420 of $2,000 max loss", "Drawdown left $840 of $1,000 max loss"], d)
            bz = p.evaluate("() => document.body.innerText.includes('BLITZ')")
            check("c. DEMO: the word BLITZ is nowhere on the page (the hidden bot is never shown, the example too)", not bz, bz)
            check("c. DEMO: today's P&L in $ with R, the eval progress, ten trades each with $ (R) and its closing rule, the plan sentence, the three backtest facts under 'Backtest, not a promise'",
                  d["kv"][0] == demo_today() and d["kv"][1].startswith("$2,580 to go to the $3,000 target") and d["dt"][0] == "Today" and len(d["trades"]) == 10 and all(re.search(r"\$[\d,]+ \(~?[+-]?\d+\.\dR\)", x) for x in d["trades"])
                  and len(d["rules"]) == 10 and all(d["rules"]) and "02:00 and 15:30 ET" in d["plan"] and "flat by 15:55 ET" in d["plan"] and d["facts"][0] == "PF 2.91, +$9,919, about $2,670 a month" and len(d["facts"]) == 3
                  and d["pill"] == "Backtest, not a promise" and "1 Jul 2026 to 16 Oct 2026" in d["factNote"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "nq-demo")
            # the sheet from the More card
            p.locator("#howBtn").scroll_into_view_if_needed()
            p.locator("#howBtn").click()
            p.wait_for_timeout(450)
            s = p.evaluate("""() => ({ open: !document.querySelector('#sheet').hidden, h: document.querySelector('#sheetH').textContent, steps: [...document.querySelectorAll('#sheetBody .steps li b')].map((e) => e.textContent),
              code: [...document.querySelectorAll('#sheetBody .cmd')].map((e) => e.textContent), undo: document.querySelector('#sheetBody').textContent.includes('UNDO_UPDATE.bat'), focus: document.activeElement.id,
              exp: document.querySelector('#howBtn').getAttribute('aria-expanded'), fits: document.querySelector('#sheet').getBoundingClientRect().height <= innerHeight })""")
            check("c. tap 'Bring the bots back (3 steps)': the sheet opens with the doc's three steps (the zip update first, then BOTS_BACK.bat), at most one copy line, the undo line; focus moves to Close",
                  s["open"] and s["h"] == "Bring the bots back (3 steps)" and len(s["steps"]) == 3 and s["steps"][0] == "Update the bot folder from the zip" and s["steps"][1].startswith("Double-click BOTS_BACK.bat") and len(s["code"]) <= 1
                  and s["undo"] and s["focus"] == "sheetClose" and s["exp"] == "true" and s["fits"], s)
            check("c. the open sheet: every tap target >= 44 px, no sideways scroll", not AK.taps(p) and AK.no_sideways(p), AK.taps(p)[:4])
            AK.shot(p, "nq-sheet")
            p.keyboard.press("Escape")
            p.wait_for_timeout(150)
            c = p.evaluate("() => [document.querySelector('#sheet').hidden, document.activeElement.id, document.querySelector('#howBtn').getAttribute('aria-expanded')]")
            check("c. Escape closes the sheet and focus returns to the button", c == [True, "howBtn", "false"], c)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px; no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin; data.json never asked for",
                  not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off and not any("data.json" in u for u in seen), (t[:5], errs[:3], off[:3]))
            ctx.close()
            # DEMO with a silent PC (4 days): the big banner
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&flat=1&silent=4d")
            b = p.evaluate(SNAP)
            check("c. DEMO, PC silent for 4 days: the banner 'Last report from your PC: 4 days ago.' with the honest sentence, Stale x2 (BLITZ hidden), no flame anywhere, the numbers stay on the page",
                  b["banner"] and b["btitle"] == "Last report from your PC: 4 days ago." and b["btext"] == SILENT and b["level"] == "bad" and b["pills"] == ["Stale"] * 2 and b["flames"] == 0 and b["legend"] == ["0", "0"]
                  and len(b["dd"]) == 2 and "No flame burns" in b["note"] and "(the last report)" in b["dt"][0] and "not known while the PC is silent" in b["planNote"], b)
            p.locator("#bannerBtn").click()
            p.wait_for_timeout(300)
            check("c. the banner's button opens the same three steps (howto.json, owner 2026-11-12: BOTS_BACK); the veil closes it", p.evaluate("() => !document.querySelector('#sheet').hidden && document.querySelectorAll('#sheetBody .steps li').length === 3"))
            p.mouse.click(195, 30)
            p.wait_for_timeout(150)
            check("c. a tap on the veil closes the sheet; no console error", p.evaluate("() => document.querySelector('#sheet').hidden") and not errs, errs[:2])
            AK.shot(p, "nq-silent")
            ctx.close()
            # a real home.json, fresh
            srv2, origin2 = AK.serve({"/home.json": home_json(180)})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?flat=1")
            r = p.evaluate(SNAP)
            check("c. a real home.json reported 3 minutes ago: no DEMO chip, no banner, three flames, 'Reported 3 minutes ago.', the real drawdown lines, ATLAS today -$169 (-1.0R), two trades",
                  not r["demo"] and not r["banner"] and r["flames"] == 3 and r["pills"] == ["Running"] * 3 and r["when"][0] == "Reported 3 minutes ago." and r["when"][2] == "Reported 3 minutes ago. Paper only."
                  and r["dd"][0] == "Drawdown left $1,145 of $2,000 max loss" and "-$169 (-1.0R)" in r["kv"] and len(r["trades"]) == 2 and r["rules"] == ["Stop hit", "Flat by 15:55 ET rule"], r)
            check("c. it read the site's home.json, its howto.json and fixture, and nothing else of the site's data; no console error",
                  any(u.endswith("/home.json") for u in seen) and any("howto.json" in u for u in seen) and not any("data.json" in u for u in seen) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            srv2.shutdown()
            # a real home.json, four days old (what the phone has today)
            srv3, origin3 = AK.serve({"/home.json": home_json(4 * 86400 + 3 * 3600 + 120, trades=False)})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?flat=1")
            o = p.evaluate(SNAP)
            check("c. a real home.json that is 4 days 3 hours old: no DEMO chip (these are the owner's last numbers), the big banner with the exact age, Stale x3, no flame, 'No trade in the last report', the status line says the age",
                  not o["demo"] and o["banner"] and o["btitle"] == "Last report from your PC: 4 days 3 hours ago." and o["btext"] == SILENT and o["pills"] == ["Stale"] * 3 and o["flames"] == 0
                  and o["dd"][0] == "Drawdown left $1,145 of $2,000 max loss" and len(o["trades"]) == 0 and o["status"].startswith("Last report from your PC: 4 days 3 hours ago.") and not errs, o)
            check("c. the stale page: taps >= 44 px (the banner button too), no sideways scroll", not AK.taps(p) and AK.no_sideways(p), AK.taps(p)[:4])
            AK.shot(p, "nq-stale-real")
            ctx.close()
            srv3.shutdown()
            # junk home.json: never blank
            srv4, origin4 = AK.serve({"/home.json": "<html>not json</html>", "/nq/howto.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "?flat=1")
            j = p.evaluate(SNAP)
            p.locator("#howBtn").scroll_into_view_if_needed()
            p.locator("#howBtn").click()
            p.wait_for_timeout(250)
            jt = p.evaluate("() => document.querySelector('#sheetBody').textContent")
            check("c. home.json is not JSON and howto.json is missing: the DEMO fills the page (never blank), the sheet says where the steps are, no console error",
                  j["demo"] and len(j["dd"]) == 2 and len(j["trades"]) == 10 and "docs/NQ_BOT_BACK.md" in jt and not errs, (j["demo"], jt, errs[:2]))
            ctx.close()
            srv4.shutdown()
            # the 3D columns
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            p.wait_for_timeout(2500)
            w = p.evaluate("() => ({ scene: window.NQ.S.scene, three: !document.querySelector('#scene3d').hidden, canvas: !!document.querySelector('#scene3d canvas'), frames: window.NQ3D ? window.NQ3D.frames() : -1, lit: window.NQ3D ? window.NQ3D.lit() : [], svg: getComputedStyle(document.querySelector('#fallback')).visibility })")
            if w["scene"] == "webgl":
                check("c. 3D: a canvas draws frames, two columns (BLITZ hidden), both flames burn (all reported 4 minutes ago); the 2D picture steps aside", w["three"] and w["canvas"] and w["frames"] > 1 and w["lit"] == [1, 1], w)
                AK.shot(p, "nq-3d")
            else:
                check("c. 3D not available in this browser: the 2D columns stay (never blank)", w["scene"] == "2d" and not w["three"] and w["svg"] == "visible", w)
            check("c. no console error with the 3D module loaded", not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&silent=2d")
            p.wait_for_timeout(1500)
            w2 = p.evaluate("() => ({ scene: window.NQ.S.scene, lit: window.NQ3D ? window.NQ3D.lit() : [] })")
            check("c. 3D with a silent PC: no flame burns on any column", (w2["scene"] == "webgl" and w2["lit"] == [0, 0]) or w2["scene"] == "2d", w2)
            AK.shot(p, "nq-3d-silent")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low&silent=90m")
            s = p.evaluate("() => [window.NQ.S.scene, !document.querySelector('#lite').hidden, document.querySelector('#bannerTitle').textContent, document.querySelector('#banner').dataset.level]")
            check("c. 375 x 667, LITE, reduced motion, 90 minutes silent (the example report is 4 minutes older): 2D columns only, LITE chip, the banner in its calmer tone with the exact age, no sideways scroll, every tap >= 44 px, no error",
                  s == ["2d", True, "Last report from your PC: 1 hour 34 minutes ago.", "warn"] and AK.no_sideways(p) and not AK.taps(p) and not errs, (s, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "nq-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_rules()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
