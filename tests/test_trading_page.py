"""TRADING (tools/web_public/trading/, AGORA look, 2026-11-17, owner: "make a page on Olympus dedicated to trading"): every trade in one place. Today per account
(the $ today, the open trade, drawdown left, $ to pass, the MFFU 16:10 ET flat time), a weekday calendar of daily $ (swipe / arrows, tap a day), the last 30 trades
(filter by bot and source, tap -> Odeon replay), 2026 H1 vs H2 stats per bot, the payout rules check (50% Builder funded / 30% Rapid), time-of-day and weekday bars,
live vs backtest twin, the equity curve and the "Why was my order rejected?" card. Every number says LIVE / PAPER / BACKTEST; BLITZ is hidden.

  a. static: the files and the AGORA kit, read only, the section order, the help card's three reasons, no BLITZ, trades.json is current (tools/trading_export.py --check)
  b. the rules in node (tradingcore.js) on the real trades.json: LIT H1 / H2 = the research file's numbers, the calendar, the MFFU clock, the rules check, twins, junk input
  c. Chromium at 390 x 844 and 320 x 640 (under the browser lock): a 10-day-old home.json, the banner, the calendar arrows and a day sheet, the filters, the Odeon link,
     DEMO mode, taps >= 44 px, no sideways scroll, no console error, nothing off the site; at 390 px also LIVE per account: a fresh ntfy feed (tests/net_stub with
     an ext post) + a data-branch trades.json -> the Account filter, the LIVE table, the replay link / "Replay after tonight's data upload"
  d. LIVE trades first-class (offline fixtures, 2026-11-18): the PC's ext post (engine/feed_trades "at" + board_trades with src, tools/pc_report.split, pc_feed merge),
     the data branch's day folders (tools/live_trades -> tools/trading_export per account, a4 = last 4 only; tools/odeon_export reels on that day's bars),
     graceful without the branch, and the page core (feedRows / merge / liveStats / pick by account) in node
    python -X utf8 -m tests.test_trading_page            (--static: parts a, b and d only)
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "trading", "Trading"
check = AK.check
D = os.path.join(AK.WEB, APP)
READS = ("../home.json", "./trades.json", "../ledger/rules.json", "../business/accounts.json", "../nq/fixture.json")   # nq/fixture.json: the accounts strip's DEMO (nqdash3)


def test_static():
    AK.static_kit(APP, NAME, reads=READS)
    html, js, core = (AK.read(os.path.join(D, n)) for n in ("index.html", "trading.js", "tradingcore.js"))
    ids = ["banner", "todayCard", "filterCard", "calCard", "tradesCard", "statsCard", "rulesCard", "edgeCard", "twinCard", "equityCard", "helpCard"]
    check("a. the sections in the owner's order: today, calendar, recent trades, stats, rules, edges, twin, equity; then the help card",
          all(f'id="{i}"' in html for i in ids) and [html.index(f'id="{i}"') for i in ids] == sorted(html.index(f'id="{i}"') for i in ids))
    check("a. the help card says what 'Limit 0, Scope MNQ' means and the three reasons, and how to tell which (after 18:00 ET, the MFFU dashboard)",
          "Limit 0, Scope MNQ" in html and "16:10" in html and "daily loss limit" in html and "failed (max loss)" in html and "activated" in html
          and "after 18:00 ET" in html and "MFFU dashboard" in html)
    check("a. paper only in plain words; LIVE / PAPER / BACKTEST explained in the footer", "never places an order" in html and "cannot start, stop or change a bot" in html
          and all(w in html for w in ("LIVE =", "PAPER =", "BACKTEST =")))
    check("a. BLITZ is never on the page: no BLITZ word in the page, and the core drops any blitz row", "BLITZ" not in html and "BLITZ" not in js
          and "hidden(x)" in core and "/blitz/i" in core)
    tj = json.loads(AK.read(os.path.join(D, "trades.json")))
    check("a. trades.json: LIT + ATLAS only, each row says its source, the source words are there", tj["n"] == len(tj["trades"]) > 100
          and {t["bot"] for t in tj["trades"]} == {"LIT", "ATLAS"} and {t["src"] for t in tj["trades"]} <= {"backtest", "paper", "live"}
          and "blitz" not in json.dumps(tj).lower() and set(tj["sources"]) == {"backtest", "paper", "live"})
    r = subprocess.run([sys.executable, os.path.join(AK.ROOT, "tools", "trading_export.py"), "--check"], capture_output=True, text=True)
    fresh_ok, why = current_or_branch_built(tj)
    check("a. trades.json is current (tools/trading_export.py --check), or built on a machine that had the PC's data branch: then everything but the "
          "data branch's LIVE rows is the same as a local build", r.returncode == 0 or fresh_ok, r.stdout + r.stderr + why)
    check("a. the calendar is Mon-Fri (5 columns, 44 px cells at 320 px) with arrows and swipe; the day sheet is a labelled dialog",
          html.count("<span>") >= 5 and "repeat(5, minmax(0, 1fr))" in AK.read(os.path.join(D, "trading.css")) and 'id="calPrev"' in html and "touchend" in js
          and 'role="dialog"' in html and 'aria-modal="true"' in html and "'Escape'" in js)
    check("a. a trade opens in Odeon by its reel id (../odeon/#reel=)", "../odeon/#reel=" in core)
    css = AK.read(os.path.join(D, "trading.css"))
    check("a. no layout jump (night-polish 2026-11-20, CLS was 0.08-0.23): the status line, the banner and the ZEUS edge chip keep their height from the first frame, "
          "the cards under them wait unseen until the first draw; trading.js lets them go after the first draw / the chip's data",
          "html:not(.tr-drawn) #banner" in css and "html:not(.tr-drawn) #status" in css and "html:not(.tr-edge) #zeusEdge[hidden]" in css
          and "html:not(.tr-drawn) #todayCard" in css and "settleBoxes()" in js and "'tr-drawn'" in js and "'tr-edge'" in js)


PINNED = os.path.join(AK.ROOT, "tests", "fixtures", "trading", "trades_pinned.json")   # nqdash3 2026-11-20: the pinned-number checks read this copy,
# so the real trades.json can be refreshed (a fresh export with the data branch adds LIVE rows and moves the newest-trade / twin / last-live answers)


def _no_branch(b: dict) -> dict:
    """the bundle without what only the PC's data branch adds (its LIVE rows, accts, data_branch, n)"""
    rows = [t for t in b.get("trades") or [] if not (t.get("src") == "live" and str(t.get("id", "")).startswith("live.") and t.get("ak"))]
    return {k: v for k, v in b.items() if k not in ("trades", "n", "accts", "data_branch", "upto")} | {"trades": [t for t in rows if t.get("src") != "live"]}


def current_or_branch_built(tj: dict) -> tuple:
    """(ok, why): the committed file was built WITH the data branch and this machine has none -> compare the rest"""
    from tools import trading_export as TE, live_trades as LT
    if not tj.get("data_branch") or LT.days(LT.PC_DAYS):
        return False, ""
    local = TE.build()
    same = _no_branch(json.loads(TE.dump(local))) == _no_branch(tj)
    return same, "" if same else " (and the non-data-branch part differs from a local build)"


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const o = {}, file = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), rules = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')), biz = JSON.parse(fs.readFileSync(process.argv[5], 'utf8'));
  const rows = C.merge(file, null), bt = C.pick(rows, { src: 'backtest' });
  o.counts = C.counts(rows); o.def = C.defaultSrc(rows); o.n = rows.length;
  const H = C.halves(bt), lit = H.find((x) => x.bot === 'LIT');
  o.lit = [lit.h1, lit.h2].map((s) => [s.n, Math.round(s.net * 100) / 100, s.pf, s.win, s.dd, s.best.usd, s.worst.usd]); o.ref = file.lit_ref;
  o.atlas = H.find((x) => x.bot === 'ATLAS').h1.n;
  o.lines = C.statLines(lit.h1).map((x) => x[0]);
  // the calendar: Oct 2026 starts on Mon 28 Sep, 5 days a week
  const g = C.monthGrid('2026-10', bt); o.grid = [g.label, g.weeks.length, g.weeks.every((w) => w.length === 5), g.weeks[0][0].day, g.weeks[0][0].inMonth, g.days, Math.round(g.total)];
  o.gridLevels = g.weeks.flat().filter((c) => c.n && c.inMonth).every((c) => (Math.abs(c.usd) < 0.5 ? c.level === 0 : Math.abs(c.level) >= 1 && Math.abs(c.level) <= 3 && Math.sign(c.level) === Math.sign(c.usd)));
  o.dec = C.monthGrid('2026-12', []).weeks.flat().filter((c) => c.inMonth).length; o.months = C.months(bt);
  // the MFFU clock (ET); 2026-11-17 is a Tuesday (EST = UTC-5)
  const at = (iso) => C.flatClock(Date.parse(iso) / 1000);
  o.clock = ['2026-11-17T21:09:00Z', '2026-11-17T21:10:00Z', '2026-11-17T22:59:00Z', '2026-11-17T23:00:00Z', '2026-11-20T21:10:00Z', '2026-11-21T15:00:00Z', '2026-11-22T22:59:00Z', '2026-11-22T23:00:00Z', '2026-11-17T14:00:00Z'].map((x) => { const c = at(x); return [c.code, c.open, c.text]; });
  o.session = ['2026-11-07T19:30:00Z', '2026-11-13T23:30:00Z', '2026-11-17T23:59:00Z', '2026-11-17T15:00:00Z'].map((x) => C.sessionDay(C.etParts(Date.parse(x) / 1000)));
  // home.json rows merge in, the same trade is not counted twice, BLITZ is dropped
  const T0 = 1794240000;
  const home = { board: { trades: [
    { acct: 'lit', src: 'live', key: 'lit', side: 'SHORT', usd: -437, r: -1.03, exit: 'STOP', entry_t: 1793173380, exit_t: 1793174520 },
    { acct: 'atlas', src: 'live', key: 'ema_lon_vix', member: 'EMA', side: 'LONG', usd: 120.5, r: 0.8, exit: 'TARGET', entry_t: T0, exit_t: T0 + 600 },
    { acct: 'blitz', src: 'paper', key: 'blitz', side: 'LONG', usd: 99, r: 1, entry_t: T0 + 60 },
    { acct: 'lit', src: 'live', key: 'lit', side: 'LONG', usd: 30, r: 0.1, open: true, entry_t: T0 + 3600 }, null, 4, { usd: 'x' }] } };
  const m = C.merge(file, home);
  o.merge = [m.length - rows.length, m.filter((r) => r.src === 'live').length, m.some((r) => /blitz/i.test(r.id + r.bot)), C.pick(m, { src: 'live' }).length];
  // today cards and the rules check with the PC's numbers
  const A = { lit: { has: true, room: 1145.34, mll: 2000, toTarget: 2600, target: 3000, profit: 400, today: 250, t: Date.parse('2026-11-17T15:00:00Z') / 1000, start: 50000 },
              atlas: { has: true, room: 822, mll: 1000, toTarget: -10, target: 1500, profit: 1510, today: 0, t: Date.parse('2026-11-07T15:00:00Z') / 1000, start: 25000 } };
  const tc = C.todayCards(A, m, home, Date.parse('2026-11-17T16:00:00Z') / 1000);
  o.today = tc.map((c) => [c.name, c.dayWord, c.today, c.open ? c.open.side : null, c.ddLine, c.passLine]);
  const winRows = [{ bot: 'LIT', src: 'live', day: '2026-11-10', usd: 300, t: 1, side: 'LONG' }, { bot: 'LIT', src: 'live', day: '2026-11-11', usd: 100, t: 2, side: 'LONG' }].map((x) => Object.assign({ hm: '03:00', m: '', k: 'TARGET', r: 1 }, x));
  const rc = C.rulesCheck(A, winRows.concat(bt), rules, biz);
  o.rules = rc.accounts.map((a) => [a.name, a.days, a.best && a.best.usd, a.builder.ok, a.builder.text, a.rapid.ok, a.rapid.text, a.payout, a.pass]);
  o.rapidText = rc.rapidText;
  // twins
  o.twins = C.twins(rows).map((t) => [t.day, t.twinSrc, t.level, t.verdict]);
  o.lastLive = [C.lastLive(rows, { pc: { t: Date.parse('2026-11-07T20:00:00Z') / 1000 } }, Date.parse('2026-11-17T20:00:00Z') / 1000).head, C.lastLive(rows, null, 1795000000).head, C.lastLive([], null, 1).head];
  // trades list and the Odeon link
  const rec = C.recent(rows, { src: 'backtest' }, 30); o.recent = [rec.length, rec[0].day >= rec[29].day, rec.filter((v) => v.odeon).length, rec[0].odeon, C.recent(rows, { src: 'live' }, 30)[0].odeon];
  o.edges = [C.hours(C.pick(rows, { src: 'backtest', bot: 'LIT' })).reduce((s, x) => s + x.n, 0), C.weekdays(bt).map((x) => x.label).join(',')];
  const eq = C.equity(bt), ep = C.equityPath(eq, 320, 150, 8); o.eq = [eq.lines.map((l) => l.bot), ep.paths.length, /^M8\.0 /.test(ep.paths[0].d), eq.lines[0].dd <= 0];
  o.money = [C.money(-0.2), C.moneyS(1234.5), C.rFmt(-1.03), C.px(29945), C.dayLabel('2026-10-28'), C.monthLabel('2026-10')];
  const junk = [null, undefined, 7, 'x', [], {}, { trades: 'no' }, { trades: [null, 4, {}, { bot: 'LIT', src: 'live', t: 'x', day: 'nope' }, { bot: 'BLITZ', src: 'paper', t: 5, day: '2026-01-02' }] }];
  o.junk = junk.map((j) => { try { const r = C.merge(j, j); return [r.length, C.monthGrid('', r).weeks.length, C.stats(r).n, C.twins(r).length, C.rulesCheck(j, r, j, j).accounts.length, C.todayCards(j, r, j, 0).length, C.equityPath(C.equity(r), 10, 10).paths.length]; } catch (e) { return 'THROW ' + e.message; } });
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_rules_real():
    """the real (refreshable) trades.json: shape only, no pinned dates"""
    o = AK.node(APP, HARNESS, os.path.join(D, "trades.json"), os.path.join(AK.WEB, "ledger", "rules.json"), os.path.join(AK.WEB, "business", "accounts.json"))
    if o is None or "_error" in o:
        check("b. real file: the node harness runs", o is None, (o or {}).get("_error"))
        return
    c, rc, ref = o["counts"], o["recent"], o["ref"]
    want = [[ref[k]["trades"], ref[k]["net"], ref[k]["pf"], ref[k]["win_pct"], ref[k]["max_dd"], ref[k]["best_day"], ref[k]["worst_day"]] for k in ("h1", "h2")]
    check("b. real file: backtest + paper + live rows, LIVE first; LIT H1 / H2 = the research file; last 30 newest first with Odeon links; junk never throws",
          c["backtest"] > 250 and c["live"] >= 1 and o["def"] == "live" and o["lit"] == want and rc[0] == 30 and rc[1] and rc[2] >= 1
          and o["merge"][2] is False and all(j == [0, 0, 0, 0, 2, 2, 0] for j in o["junk"]), (c, rc, o["merge"]))
    check("b. real file: every twin row has a verdict; 'Last live data' names a day", all(t[2] in ("ok", "warn", "bad") and t[3] for t in o["twins"])
          and o["lastLive"][1].startswith("Last live data: ") and o["lastLive"][2] == "Last live data: none yet.", (o["twins"][:3], o["lastLive"]))


def test_rules():
    """pinned numbers on tests/fixtures/trading/trades_pinned.json (the 28 Oct live trade, its paper twin, its reel)"""
    o = AK.node(APP, HARNESS, PINNED, os.path.join(AK.WEB, "ledger", "rules.json"), os.path.join(AK.WEB, "business", "accounts.json"))
    if o is None:
        check("b. node tests skipped: no node", True)
        return
    if "_error" in o:
        check("b. the node harness runs", False, o["_error"])
        return
    c = o["counts"]
    check("b. the file's rows: backtest + paper + live, LIVE first when there is any", c["backtest"] > 250 and c["live"] >= 1 and c["paper"] >= 1 and o["def"] == "live", c)
    ref = o["ref"]
    want = [[ref[k]["trades"], ref[k]["net"], ref[k]["pf"], ref[k]["win_pct"], ref[k]["max_dd"], ref[k]["best_day"], ref[k]["worst_day"]] for k in ("h1", "h2")]
    check("b. LIT 2026 H1 and H2 from the page = the research file (trades, net $, PF, win %, max DD, best and worst day)", o["lit"] == want, (o["lit"], want))
    check("b. ATLAS has its own H1 stats (3 members' research trades); the stat lines are the owner's list",
          o["atlas"] > 50 and o["lines"] == ["Trades a week", "Win rate", "Profit factor", "Net", "Average win", "Average loss", "Best day", "Worst day", "Max drawdown", "Longest streak"], o["lines"])
    g = o["grid"]
    check("b. the calendar: October 2026, whole Mon-Fri weeks from Mon 28 Sep (outside the month), green / red levels 1-3 follow the $; December has 23 weekdays",
          g[0] == "October 2026" and g[1] == 5 and g[2] and g[3] == "2026-09-28" and g[4] is False and g[5] > 5 and o["gridLevels"] and o["dec"] == 23 and o["months"][0] == "2026-01", (g, o["dec"]))
    k = o["clock"]
    check("b. the MFFU clock: open to 16:09, closed 16:10-17:59 (no orders), open again 18:00, weekend Fri 16:10 - Sun 17:59, open Sun 18:00",
          [x[0] for x in k] == ["open", "closed", "closed", "evening", "weekend", "weekend", "weekend", "evening", "open"]
          and "Flat by 16:10 ET (in 1 minute)" in k[0][2] and "no orders 16:10-18:00 ET" in k[1][2] and "(in 1 minute)" in k[2][2] and "Sunday 18:00 ET" in k[4][2]
          and "(in 1 minute)" in k[6][2] and k[8][2].startswith("Open. Flat by 16:10 ET (in 7 hours 10 minutes)"), k)
    check("b. the PC's trades land on their futures session day: Saturday -> Monday, Friday 18:30 ET -> Monday, Tuesday 18:59 ET -> Wednesday, Tuesday 10:00 -> Tuesday",
          o["session"] == ["2026-11-09", "2026-11-16", "2026-11-18", "2026-11-17"], o["session"])
    check("b. home.json rows join the file: the PC's copy of a file trade is not counted twice, an open trade is not a closed one, BLITZ is dropped",
          o["merge"] == [2, 3, False, 2], o["merge"])
    t = o["today"]
    check("b. today per account: the $ of the report's day, called 'Today' only when the report is from today (else 'On <day> (the last report)'), the open trade, drawdown left, $ to pass",
          t[0] == ["Zlarior", "Today", 250, "Long", "Drawdown left $1,145 of $2,000", "$2,600 to pass (target +$3,000)"]
          and t[1][1] == "On Sat 7 Nov (the last report)" and t[1][2] == 0 and t[1][5] == "Target reached", t)
    r = o["rules"]
    check("b. rules check: best day $300 of $400 profit is 75%: too big for Builder 50% ($200 more) and Rapid 30% ($600 more); 2 days traded; the payout line from ledger/rules.json",
          r[0][1] == 2 and r[0][2] == 300 and r[0][3] is False and "$200 more" in r[0][4] and r[0][5] is False and "$600 more" in r[0][6]
          and r[0][7].startswith("Once funded: first payout when the profit is at least $2,600 (balance $52,600)") and "80%" in r[0][7] and r[0][8] == "Eval: $2,600 more to pass (+$3,000 target)."
          and r[1][3] is None and "$1,350" in r[1][7] and "30%" in o["rapidText"], r)
    check("b. the twin: the live 28 Oct trade matches its paper twin (same side, same exit)", o["twins"][:1] == [["2026-10-28", "PAPER", "ok", "Match: same side, same exit (STOP), R within 0.00."]], o["twins"])
    ll = o["lastLive"]
    check("b. 'Last live data: <date>' says the day and how old; without a PC report it falls back to the last LIVE trade in the file",
          ll[0] == "Last live data: Sat 7 Nov 2026 (10 days ago)." and ll[1].startswith("Last live data: Wed 28 Oct 2026 (the last LIVE trade") and ll[2] == "Last live data: none yet.", ll)
    rc = o["recent"]
    check("b. the last 30 trades, newest first; the ones Odeon can play link to ../odeon/#reel=<id>; the live trade links to its real reel",
          rc[0] == 30 and rc[1] and rc[2] >= 1 and rc[4] == "../odeon/#reel=real.2026-10-28_0343_short", rc)
    check("b. edges: every LIT backtest trade has an hour; weekdays Mon-Fri; the equity curve has a line per bot from the zero point, drawdown <= 0",
          o["edges"][0] == o["ref"]["h1"]["trades"] + o["ref"]["h2"]["trades"] and o["edges"][1] == "Mon,Tue,Wed,Thu,Fri" and o["eq"] == [["LIT", "ATLAS"], 2, True, True], (o["edges"], o["eq"]))
    check("b. money words", o["money"] == ["$0", "+$1,235", "-1.0R", "29,945.00", "Wed 28 Oct", "October 2026"], o["money"])
    check("b. junk input never throws and never shows a row", all(j == [0, 0, 0, 0, 2, 2, 0] for j in o["junk"]), o["junk"])


# ------------------------------------------------------------------------------------------------ d. LIVE trades per account (fixtures)
ET = ZoneInfo("America/New_York")
DAY1, DAY2 = "2026-11-17", "2026-11-18"
FULL_A, FULL_B = "MFFUEVBLDR000071234", "MFFUEVBLDR000075678"      # fake broker names: only their last 4 may ever show


def ts(day, hh, mm):
    return int(dt.datetime.fromisoformat(f"{day}T{hh:02d}:{mm:02d}:00").replace(tzinfo=ET).timestamp())


def ledger_rows():
    """what engine/datapipe.day_trades writes (already scrubbed: account names -> ...1234): Zlarior 50K + 25K #2 on the same signal, a refused
    entry, ATLAS's account B live, ATLAS paper, BLITZ and a sim row that must never show"""
    e1, e2 = ts(DAY1, 9, 45), ts(DAY2, 11, 0)
    ok = lambda a: {"ok": True, "adapter": "ninjatrader", "account": a}  # noqa: E731
    return [
        {"t": e1 + 5, "side": "buy", "qty": 3, "entry_t": e1, "entry": 21003.0, "stop": 20990.0, "target": 21030.0, "result": ok("...1234"), "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": "live"},
        {"t": e1 + 900, "side": "exit", "qty": 3, "entry_t": e1, "reason": "TARGET", "pnl": 156.3, "exit_t": e1 + 900, "result": {"ok": True}, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": "live"},
        {"t": e1 + 6, "side": "buy", "qty": 1, "entry_t": e1, "entry": 21003.0, "stop": 20990.0, "target": 21030.0, "result": ok("...5678"), "src": "accounts/b25k_2", "bot": "zlarior", "acct": "b25k_2", "mode": "live"},
        {"t": e1 + 901, "side": "exit", "qty": 1, "entry_t": e1, "reason": "TARGET", "pnl": 52.1, "exit_t": e1 + 900, "result": {"ok": True}, "src": "accounts/b25k_2", "bot": "zlarior", "acct": "b25k_2", "mode": "live"},
        {"t": e1 + 1000, "side": "sell", "qty": 2, "entry_t": e1 + 990, "result": {"ok": False, "error": "order refused for account ...1234: Limit 0"}, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": "live"},
        {"t": e2 + 3, "side": "sell", "qty": 2, "entry_t": e2, "entry": 21050.0, "stop": 21060.0, "target": 21020.0, "strategy": "EMA", "result": ok("...9012"), "src": "acctb", "bot": "atlas", "acct": "atlas", "mode": "live"},
        {"t": e2 + 600, "side": "exit", "qty": 2, "entry_t": e2, "reason": "STOP", "pnl": -41.0, "exit_t": e2 + 600, "strategy": "EMA", "result": {"ok": True}, "src": "acctb", "bot": "atlas", "acct": "atlas", "mode": "live"},
        {"t": e2 + 60, "side": "buy", "qty": 1, "entry_t": e2 + 60, "entry": 21040.0, "stop": 21030.0, "result": {"ok": True, "adapter": "paper"}, "src": "atlas_v2", "bot": "atlas_v2", "acct": "atlas_v2", "mode": "paper"},
        {"t": e2 + 700, "side": "exit", "qty": 1, "entry_t": e2 + 60, "reason": "TARGET", "pnl": 80.0, "src": "atlas_v2", "bot": "atlas_v2", "acct": "atlas_v2", "mode": "paper"},
        {"t": e2 + 70, "side": "buy", "qty": 1, "entry_t": e2 + 70, "entry": 21040.0, "stop": 21030.0, "result": ok("...3333"), "src": "acctc", "bot": "blitz", "acct": "blitz", "mode": "live"},
        {"t": e2 + 800, "side": "exit", "qty": 1, "entry_t": e2 + 70, "reason": "TARGET", "pnl": 90.0, "src": "acctc", "bot": "blitz", "acct": "blitz", "mode": "live"},
        {"t": e2 + 80, "side": "buy", "qty": 1, "entry_t": e2 + 80, "entry": 21040.0, "stop": 21030.0, "result": {"ok": True, "adapter": "ninjatrader", "account": "Sim101"}, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": "sim"},
        {"t": e2 + 900, "side": "exit", "qty": 1, "entry_t": e2 + 80, "reason": "TARGET", "pnl": 70.0, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": "sim"}]


def make_pc_days(root):
    """data/pc_days as tools/data_pull.py leaves it: DAY1 with the PC's MNQ 1m bars (so its trades can be replayed), DAY2 without bars yet"""
    rows = ledger_rows()
    for day in (DAY1, DAY2):
        d = os.path.join(root, day)
        os.makedirs(os.path.join(d, "bars"), exist_ok=True)
        lo, hi = ts(day, 0, 0) - 6 * 3600, ts(day, 17, 0)
        mine = [r for r in rows if lo <= int(r["entry_t"]) < hi]
        with open(os.path.join(d, "trades.jsonl.gz"), "wb") as fh:
            fh.write(gzip.compress("".join(json.dumps(r) + "\n" for r in mine).encode(), mtime=0))
        with open(os.path.join(d, "manifest.json"), "w") as fh:
            json.dump({"day": day, "files": {}}, fh)
    e1 = ts(DAY1, 9, 45)
    lines = ["time,open,high,low,close,volume"]
    for i in range(-150, 60):                      # 07:15-10:45 ET: flat near 21000, a climb to 21036 from the entry to the target
        t = e1 + i * 60
        c = 21000.0 if i < 0 else min(21036.0, 21003.0 + i * 2.4)
        lines.append(f"{t},{c - 0.5},{c + 1.0},{c - 1.0},{c},10")
    with open(os.path.join(root, DAY1, "bars", "MNQ_1m.csv.gz"), "wb") as fh:
        fh.write(gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0))


def feed_posts(now):
    """the PC's two ntfy posts of one run (tools/pc_report.split: ext first, then the core) as an ntfy /json?poll=1 answer"""
    from engine import feed_trades as FT
    from tools import pc_report as PR
    e1 = now - 3 * 3600
    L = {"accounts": [
        {"id": "mffu50k_eval", "kind": "eval", "source": "pc", "broker_account": FULL_A, "trades": [
            {"entry_t": e1, "exit_t": e1 + 900, "side": "LONG", "qty": 3, "entry": 21003.0, "stop": 20990.0, "target": 21030.0, "exit": "TARGET", "pnl": 156.3, "r": 1.99}]},
        {"id": "b25k_2", "kind": "eval", "source": "pc", "broker_account": FULL_B, "trades": [
            {"entry_t": e1, "exit_t": e1 + 900, "side": "LONG", "qty": 1, "entry": 21003.0, "stop": 20990.0, "target": 21030.0, "exit": "TARGET", "pnl": 52.1, "r": 2.0}],
         "position": {"entry_t": e1 + 5400, "side": "SHORT", "qty": 1, "entry": 21060.0, "stop": 21070.0, "target": 21020.0}},
        {"id": "acct_c", "kind": "eval", "source": "pc_blitz", "trades": [{"entry_t": e1, "exit_t": e1 + 60, "side": "LONG", "pnl": 5}]},
        {"id": "cloud_paper", "kind": "paper", "source": "cloud", "trades": [{"entry_t": e1, "exit_t": e1 + 60, "side": "LONG", "pnl": 7}]}],
        "board": {"data_t": now - 100, "trades": [
            {"acct": "lit", "src": "live", "key": "lit", "entry_t": e1, "exit_t": e1 + 900, "side": "LONG", "qty": 3, "exit": "TARGET", "usd": 156.3, "r": 1.99},
            {"acct": "atlas", "src": "live", "key": "ema_lon_vix", "member": "EMA", "entry_t": e1 + 3600, "exit_t": e1 + 4000, "side": "SHORT", "qty": 2, "exit": "STOP", "usd": -41.0, "r": -1.02},
            {"acct": "atlas", "src": "paper", "key": "macd_sweep", "member": "MACD", "entry_t": e1 + 7000, "exit_t": e1 + 7300, "side": "LONG", "usd": 310.0, "exit": "TARGET"}]}}
    out = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": now - 120, "reporter": {"t": now - 60, "server": True}, "pc": {"present": True, "t": now - 120},
           "board": {"t": now - 100, "data_t": now - 100, "lit": {"name": "Zlarior", "balance": 49313.54, "room": 1145.34, "mll": 2000, "today_pnl": 156.3},
                     "trades": [{k: t.get(k) for k in PR.TRADE_KEYS if t.get(k) is not None} for t in L["board"]["trades"]]},
           "at": FT.compact(L)}
    core, exts = PR.split(out)
    lines = [json.dumps({"event": "message", "time": now - 61, "message": json.dumps(e)}) for e in exts]
    lines.append(json.dumps({"event": "message", "time": now - 60, "message": json.dumps(core)}))
    return "\n".join(lines) + "\n", core, exts


def live_bundle(tmp):
    """(trades.json bundle, odeon bundle) built from the fixture data branch (the real exporters, pc_days pointed at the fixture)"""
    from tools import odeon_export as OE, trading_export as TE
    pcd = os.path.join(tmp, "pc_days")
    make_pc_days(pcd)
    # the fixture days' only bars are the fixture's own: the repo's TradingView files (data/NQ_1m.csv, NQ_5m.csv) are cut before DAY1,
    # else a data refresh past DAY2 (Nov 19, 2026-11-20) hands DAY2 real bars and the "no bars yet -> replay later" case disappears
    cut, read = ts(DAY1, 0, 0) - 6 * 3600, OE._read_csv

    def read_cut(path, a, z):
        out = read(path, a, z)
        return {k: v for k, v in out.items() if k < cut} if path in (OE.BARS_1M, OE.BARS_5M) else out
    OE._read_csv = read_cut
    try:
        ob = OE.build(1, 1, cloud=False, pc_days=pcd)
    finally:
        OE._read_csv = read
    op = os.path.join(tmp, "odeon.json")
    OE.write(ob, op)
    old = TE.ODEON
    TE.ODEON = op
    try:
        return TE.build(pcd), ob
    finally:
        TE.ODEON = old


LIVE_HARNESS = r"""
const fs = require('fs');
const F = require(process.argv[3]);
import(process.argv[2]).then((C) => {
  const o = {}, file = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')), nd = fs.readFileSync(process.argv[5], 'utf8'), now = +process.argv[6];
  const lite = F.parseLatest(nd);
  o.lite = [!!lite, !!(lite && lite.at), lite && lite.board && Array.isArray(lite.board.trades) ? lite.board.trades.length : -1];
  const fr = C.feedRows(lite, now);
  o.feed = fr.map((r) => [r.src, r.ak || '', r.bot, r.open, r.a4 || '', r.usd]).sort();
  o.stale = C.feedRows(lite, now + 40 * 3600).length;
  const rows = C.merge(file, null, lite, now);
  const live = rows.filter((r) => r.src === 'live');
  o.live = live.map((r) => [r.ak, r.day, r.bot, r.usd, r.a4 || '', !!r.odeon, r.open]).sort();
  o.accts = C.liveAccounts(rows).map((a) => [a.k, a.name, a.n, a.a4]);
  o.stats = C.liveStats(rows, now).map((a) => [a.k, a.s.n, a.s.net]);
  o.pick = [C.pick(rows, { src: 'live', acct: 'z25k2' }).length, C.pick(rows, { src: 'live' }).length, C.pick(rows, { src: 'backtest', acct: 'z25k2' }).length];
  o.views = C.recent(rows, { src: 'live' }, 30).map((v) => [v.who, v.odeon ? 'reel' : v.replayLater]);
  o.paper = rows.filter((r) => r.src === 'paper' && r.feed).map((r) => [r.bot, r.m, r.usd]);
  o.blitz = JSON.stringify(rows).toLowerCase().includes('blitz');
  o.keys = [C.acctKey('mffu50k_eval'), C.acctKey('b25k_2'), C.acctKey('atlas'), C.acctKey('rapid_25k'), C.acctKey('acct_c'), C.acctKey('', 'ATLAS'), C.acctKey('<x>')];
  o.rules = C.rulesCheck({}, rows, {}, {}).accounts.map((a) => a.days);
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_live():
    from tools import live_trades as LT, trading_export as TE
    tmp = tempfile.mkdtemp(prefix="trading-live-")
    try:
        # 1. the PC side: the "at" block + board_trades with src in the ext post, through the privacy pass, merged back by pc_feed
        now = ts(DAY2, 12, 30)
        nd, core, exts = feed_posts(now)
        x = {k: v for e in exts for k, v in (e.get("x") or {}).items()}
        allp = json.dumps([core] + exts)
        check("d. PC ext post: 'at' = every real account's last trades (50K, 25K #2, ATLAS from the board), BLITZ / cloud paper never; board_trades keep src",
              [a["id"] for a in x["at"]["a"]] == ["mffu50k_eval", "b25k_2", "atlas"] and "at" not in core and {t.get("src") for t in x["board_trades"]} == {"live", "paper"}
              and "acct_c" not in allp and "cloud_paper" not in allp, x.get("at"))
        check("d. PC ext post: the broker accounts show their last 4 digits only, every post under 3,900 bytes",
              FULL_A not in allp and FULL_B not in allp and [a.get("l4") for a in x["at"]["a"][:2]] == ["1234", "5678"]
              and all(len(json.dumps(p)) < 3900 for p in [core] + exts), [len(json.dumps(p)) for p in [core] + exts])
        from tools import pc_feed as PF
        m = PF.merge(core, exts)
        check("d. pc_feed.merge lays 'at' top level and board_trades back into board.trades (the JS twin does the same)", isinstance(m.get("at"), dict)
              and len(m["board"]["trades"]) == 3, m.get("board"))
        # 2. the data branch: per-account rows, last 4 only, refused / paper / sim / BLITZ left out
        paired = LT.pair(ledger_rows())
        check("d. data branch: closed LIVE trades per account (Zlarior 50K + 25K #2 on the same signal, ATLAS funded); refused, paper, sim, BLITZ left out",
              sorted((t["ak"], t["bot"], t["usd"], t["a4"]) for t in paired) == [("atlas25f", "ATLAS", -41.0, "9012"), ("z25k2", "LIT", 52.1, "5678"), ("z50k", "LIT", 156.3, "1234")]
              and next(t for t in paired if t["ak"] == "atlas25f")["m"] == "EMA" and next(t for t in paired if t["ak"] == "z50k")["x"] == 21029.05, paired)
        tb, ob = live_bundle(tmp)
        lv = [t for t in tb["trades"] if t["src"] == "live"]
        reels = {t["id"]: t for t in ob["trades"] if t.get("ak")}
        dl = [t for t in lv if t.get("ak") in ("z50k", "z25k2", "atlas25f") and t["day"] >= DAY1]
        check("d. trades.json: the data branch's LIVE rows per account (ak / an / a4), one id each, the old heartbeat row kept; accts + data_branch say what is in",
              sorted((t["ak"], t["an"], t["a4"]) for t in dl) == [("atlas25f", "ATLAS funded 25K", "9012"), ("z25k2", "Zlarior 25K #2", "5678"), ("z50k", "Zlarior 50K", "1234")]
              and len({t["id"] for t in lv}) == len(lv) and any(t["day"] == "2026-10-28" for t in lv)
              and tb["accts"]["z25k2"]["n"] == 1 and tb["data_branch"]["days"] == 2 and tb["data_branch"]["bars"] == [DAY1], (dl, tb.get("accts"), tb.get("data_branch")))
        check("d. Odeon: a live trade whose day has bars gets a reel per account (real.<account>...); the day without bars has none -> the page says replay later",
              sorted(reels) == [f"real.z25k2.{DAY1}_0945_long", f"real.z50k.{DAY1}_0945_long"] and all(len(r["bars"]["c"]) > 60 for r in reels.values())
              and next(t for t in dl if t["ak"] == "z25k2")["odeon"] == f"real.z25k2.{DAY1}_0945_long" and next(t for t in dl if t["ak"] == "atlas25f")["odeon"] is None, (sorted(reels), [(t["ak"], t["odeon"]) for t in dl]))
        bundle_txt = TE.dump(tb)
        check("d. privacy: no full broker account name and no balance key in trades.json or the reels", FULL_A not in bundle_txt and FULL_B not in bundle_txt
              and '"balance"' not in bundle_txt and FULL_A not in json.dumps(ob) and FULL_B not in json.dumps(ob))
        # 3. graceful: no data branch yet (today) = the same trades.json as before
        check("d. no data branch yet: trades.json builds the same as without it (no crash, no live rows invented)",
              _no_branch(TE.build(os.path.join(tmp, "missing"))) == _no_branch(json.loads(AK.read(os.path.join(D, "trades.json"))))
              and TE.build(os.path.join(tmp, "missing"))["data_branch"] is None and not any(str(t["id"]).startswith("live.z") for t in TE.build(os.path.join(tmp, "missing"))["trades"])
              and LT.load(os.path.join(tmp, "missing")) == [])
        # 4. the page core: feed rows (fresh only), merge per account, dedupe against the file and the board copy
        fp, np_ = os.path.join(tmp, "trades.json"), os.path.join(tmp, "feed.ndjson")
        with open(fp, "w") as fh:
            fh.write(bundle_txt)
        with open(np_, "w") as fh:
            fh.write(nd)
        feedjs = os.path.join(tmp, "pc_feed.cjs")
        shutil.copy(os.path.join(AK.WEB, "pc_feed.js"), feedjs)
        o = AK.node(APP, LIVE_HARNESS, feedjs, fp, np_, now)
        if o is None:
            check("d. node tests skipped: no node", True)
            return
        if "_error" in o:
            check("d. the live node harness runs", False, o["_error"])
            return
        check("d. page: the fresh feed gives LIVE rows per account (50K, 25K #2 + its open trade, ATLAS) and the ATLAS paper member stays PAPER; a 40-hour-old feed gives none",
              o["lite"] == [True, True, 3] and ["live", "z25k2", "LIT", True, "5678", 0] in o["feed"] and ["paper", "", "ATLAS", False, "", 310] in o["feed"]
              and sum(1 for f in o["feed"] if f[0] == "live" and f[1] == "z50k") == 2 and o["stale"] == 0, o["feed"])
        check("d. page: merge = one row per trade and account (the feed's copy of a file trade is not counted twice; two accounts on one signal = two rows); BLITZ nowhere",
              sorted(a[0] for a in o["accts"]) == ["atlas25f", "z25k2", "z50k"] and [a[2] for a in o["accts"]] == [3, 2, 2] and not o["blitz"], (o["accts"], o["live"]))
        check("d. page: per-account picks and stats; the Today / rules cards stay on the bot's own account (50K: 3 days traded)",
              o["pick"][0] == 2 and o["pick"][1] == 7 and o["pick"][2] > 0 and o["stats"][0][0] == "z50k" and o["rules"][0] == 3, (o["pick"], o["stats"], o["rules"]))
        check("d. page: a LIVE trade says its account with the last 4 ('Zlarior 25K #2 ...5678 · LIT'); with bars it opens its reel, else 'Replay after tonight's data upload'",
              ["Zlarior 25K #2 ...5678 · LIT", "reel"] in o["views"] and any(v[1] == "Replay after tonight's data upload" and v[0].startswith("ATLAS funded 25K ...9012") for v in o["views"]), o["views"])
        check("d. account keys: PC ids -> z50k / z25k2 / atlas25f / rapid25; BLITZ and junk -> none", o["keys"] == ["z50k", "z25k2", "atlas25f", "rapid25", None, "atlas25f", None], o["keys"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def home_json(age_s):
    now = int(time.time())
    t = now - age_s
    return json.dumps({"live": {"pc": {"present": True, "t": t, "running": True, "second": {"t": t}}},
                       "board": {"running": True, "data_t": t,
                                 "lit": {"name": "Zlarior", "balance": 49313.54, "floor": 48168, "room": 1145.34, "mll": 2000, "to_target": 3686.46, "target_balance": 53000, "profit": -686.46, "today_pnl": -437, "status": "open"},
                                 "atlas": {"name": "ATLAS", "balance": 25182.19, "floor": 24360, "room": 822.24, "mll": 1000, "to_target": 1317.81, "target_balance": 26500, "profit": 182.19, "today_pnl": 0, "status": "open"},
                                 "trades": [{"acct": "atlas", "src": "live", "key": "ema_lon_vix", "member": "EMA", "side": "SHORT", "usd": -168.81, "r": -1.03, "exit": "STOP", "entry_t": t - 7200, "exit_t": t - 6900},
                                            {"acct": "blitz", "src": "paper", "key": "blitz", "side": "LONG", "usd": 50, "r": 0.5, "exit": "TARGET", "entry_t": t - 3600, "exit_t": t - 3000}]}})


def test_browser():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. browser tests skipped: no playwright", True)
        return
    srv, origin = AK.serve({"/home.json": home_json(10 * 86400)})
    try:
        with AK.browser() as br:
            for w, hgt in ((390, 844), (320, 640)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=hgt)
                AK.open_app(p, origin, APP)
                st = p.evaluate("""() => ({ demo: !document.getElementById('demo').hidden, banner: document.getElementById('bannerTitle').textContent, level: document.getElementById('banner').dataset.level,
                    text: document.body.innerText, accts: document.querySelectorAll('#accts .acct').length, days: document.querySelectorAll('#cal .day').length, btn: document.querySelectorAll('#cal button.day').length,
                    trades: document.querySelectorAll('#trades li').length, src: window.TRADING.S.src, month: document.getElementById('calMonth').textContent,
                    stats: document.querySelectorAll('#stats .stat').length, rules: document.querySelectorAll('#rules .rule').length, bars: document.querySelectorAll('#hours .bar').length,
                    twins: document.querySelectorAll('#twins .twin').length, paths: document.querySelectorAll('#eq path').length })""")
                check(f"c. {w}px: real files, not DEMO; the banner says 'Last live data: <date> (10 days ago)' in red; LIVE is the opening source",
                      not st["demo"] and st["banner"].startswith("Last live data: ") and "(10 days ago)" in st["banner"] and st["level"] == "bad" and st["src"] == "live", st["banner"])
                check(f"c. {w}px: every section has its content: 2 accounts, the calendar, trades, 2 stat cards, 2 rule cards, the twin, the curve; BLITZ nowhere",
                      st["accts"] == 2 and st["days"] >= 20 and st["btn"] >= 1 and st["trades"] >= 1 and st["stats"] == 2 and st["rules"] == 2 and st["twins"] >= 1 and st["paths"] >= 1
                      and "BLITZ" not in st["text"].upper().replace("BLITZ", "BLITZ") and "blitz" not in st["text"].lower(), {k: v for k, v in st.items() if k != "text"})
                check(f"c. {w}px: no sideways scroll, taps >= 44 px, clear of the Jarvis corner", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p), (AK.taps(p), AK.corner(p)))
                if w == 390:
                    # night-polish 2026-11-20: '1. Today' no longer moves down 130-300 px when the banner / ZEUS edge chip fill in (CLS was 0.08-0.23)
                    p.wait_for_function("document.documentElement.classList.contains('tr-edge')", timeout=15000)
                    cls = p.evaluate("""() => new Promise((res) => { let v = 0, n = []; const o = new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { v += e.value; n.push(Math.round(e.value * 1000) / 1000); } });
                        o.observe({ type: 'layout-shift', buffered: true }); setTimeout(() => { o.disconnect(); res({ cls: Math.round(v * 1000) / 1000, n }); }, 400); })""")
                    check("c. 390px: no layout jump while the banner and the ZEUS edge chip fill in (CLS < 0.02, the first visit too)", cls["cls"] < 0.02, cls)
                # backtest: the arrows walk the months, a day opens its sheet
                p.click("#fSrc button[data-k=backtest]")
                p.wait_for_timeout(200)
                m1 = p.text_content("#calMonth")
                p.click("#calPrev")
                p.wait_for_timeout(200)
                m2 = p.text_content("#calMonth")
                n30 = p.evaluate("document.querySelectorAll('#trades li').length")
                p.click("#cal button.day")
                p.wait_for_timeout(300)
                sh = p.evaluate("() => ({ open: !document.getElementById('sheet').hidden, h: document.getElementById('sheetH').textContent, n: document.querySelectorAll('#sheetBody li').length })")
                p.keyboard.press("Escape")
                p.wait_for_timeout(200)
                closed = p.evaluate("document.getElementById('sheet').hidden")
                check(f"c. {w}px: BACKTEST: October 2026 first, the arrow goes to September, 30 trades listed, a tapped day opens its trades and Escape closes it",
                      m1 == "October 2026" and m2 == "September 2026" and n30 == 30 and sh["open"] and sh["n"] >= 1 and re.match(r"\w{3} \d+ \w{3} 2026: ", sh["h"]) and closed, (m1, m2, n30, sh, closed))
                p.click("#fBot button[data-k=ATLAS]")
                p.wait_for_timeout(200)
                at = p.evaluate("() => [...document.querySelectorAll('#trades li b')].every((b, i) => i % 2 || b.textContent.startsWith('ATLAS'))")
                link = p.evaluate("() => { const a = document.querySelector('#trades a.tlink'); return a ? a.getAttribute('href') : ''; }")
                check(f"c. {w}px: the ATLAS filter lists only ATLAS; a trade Odeon has opens ../odeon/#reel=<id>", at and link.startswith("../odeon/#reel="), (at, link))
                check(f"c. {w}px: no console error, nothing requested off the site", not errs and not off, (errs[:3], off[:3]))
                AK.shot(p, f"trading-{w}")
                ctx.close()
            # LIVE per account at 390 px: the data-branch trades.json + a fresh PC feed (tests/net_stub answers ntfy with the PC's ext + core posts)
            from tests import net_stub as NS
            tmp = tempfile.mkdtemp(prefix="trading-live-b-")
            try:
                tb, _ob = live_bundle(tmp)
                from tools import trading_export as TE
                srv2, origin2 = AK.serve({"/home.json": home_json(10 * 86400), f"/{APP}/trades.json": TE.dump(tb)})
                try:
                    nd, _c, _e = feed_posts(int(time.time()))
                    ctx, p, errs, seen, off = AK.page(br, origin2, w=390, h=844)
                    NS.stub(ctx, nd)
                    AK.open_app(p, origin2, APP)
                    p.wait_for_function("() => window.TRADING.S.lite && document.querySelectorAll('#liveStats tr[data-acct]').length >= 3", timeout=20000, polling=300)
                    st = p.evaluate("""() => ({ box: !document.getElementById('fAcctBox').hidden, acc: [...document.querySelectorAll('#fAcct button')].map((b) => b.textContent),
                        rows: [...document.querySelectorAll('#liveStats tr[data-acct]')].map((r) => r.dataset.acct), later: [...document.querySelectorAll('#trades .later')].map((x) => x.textContent),
                        links: [...document.querySelectorAll('#trades a.tlink')].map((a) => a.getAttribute('href')), banner: document.getElementById('banner').dataset.level, src: window.TRADING.S.src,
                        text: document.body.innerText })""")
                    check("c. 390px LIVE per account: the Account filter (Zlarior 50K / 25K #2 / ATLAS funded 25K), the LIVE table, a fresh feed turns the banner green",
                          st["box"] and st["src"] == "live" and any(x.startswith("Zlarior 25K #2") for x in st["acc"]) and st["rows"] == ["z50k", "z25k2", "atlas25f"] and st["banner"] == "ok"
                          and "blitz" not in st["text"].lower() and FULL_A not in st["text"] and FULL_B not in st["text"], {k: v for k, v in st.items() if k != "text"})
                    p.click("#fAcct button[data-k=z25k2]")
                    p.wait_for_timeout(250)
                    one = p.evaluate("() => ({ who: [...document.querySelectorAll('#trades .tl b')].map((b) => b.textContent), links: [...document.querySelectorAll('#trades a.tlink')].map((a) => a.getAttribute('href')) })")
                    check("c. 390px: one account shows only its trades; its uploaded day opens the reel, a trade without bars says 'Replay after tonight's data upload'",
                          one["who"] and all(w.startswith("Zlarior 25K #2") for w in one["who"]) and f"../odeon/#reel=real.z25k2.{DAY1}_0945_long" in one["links"]
                          and "Replay after tonight's data upload" in st["later"], (one, st["later"]))
                    check("c. 390px LIVE: taps >= 44 px, no sideways scroll, no console error, nothing off the site (ntfy answered by the stub)",
                          AK.no_sideways(p) and not AK.taps(p) and not errs and not off, (AK.taps(p), errs[:3], off[:3]))
                    AK.shot(p, "trading-live-390")
                    ctx.close()
                finally:
                    srv2.shutdown()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844)
            AK.open_app(p, origin, APP, "?demo=1")
            st = p.evaluate("() => ({ demo: !document.getElementById('demo').hidden, today: document.getElementById('todaySrc').textContent, open: document.querySelector('#accts .acct[data-bot=ATLAS]').innerText })")
            check("c. ?demo=1: the DEMO tag, 'Example numbers ... not real', ATLAS shows its open trade", st["demo"] and "not real" in st["today"] and "Short" in st["open"] and not errs and not off, (st, errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_rules()
    test_rules_real()
    test_live()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
