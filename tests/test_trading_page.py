"""TRADING (tools/web_public/trading/, AGORA look, 2026-11-17, owner: "make a page on Olympus dedicated to trading"): every trade in one place. Today per account
(the $ today, the open trade, drawdown left, $ to pass, the MFFU 16:10 ET flat time), a weekday calendar of daily $ (swipe / arrows, tap a day), the last 30 trades
(filter by bot and source, tap -> Odeon replay), 2026 H1 vs H2 stats per bot, the payout rules check (50% Builder funded / 30% Rapid), time-of-day and weekday bars,
live vs backtest twin, the equity curve and the "Why was my order rejected?" card. Every number says LIVE / PAPER / BACKTEST; BLITZ is hidden.

  a. static: the files and the AGORA kit, read only, the section order, the help card's three reasons, no BLITZ, trades.json is current (tools/trading_export.py --check)
  b. the rules in node (tradingcore.js) on the real trades.json: LIT H1 / H2 = the research file's numbers, the calendar, the MFFU clock, the rules check, twins, junk input
  c. Chromium at 390 x 844 and 320 x 640 (under the browser lock): a 10-day-old home.json, the banner, the calendar arrows and a day sheet, the filters, the Odeon link,
     DEMO mode, taps >= 44 px, no sideways scroll, no console error, nothing off the site
    python -X utf8 -m tests.test_trading_page            (--static: parts a and b only)
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

APP, NAME = "trading", "Trading"
check = AK.check
D = os.path.join(AK.WEB, APP)
READS = ("../home.json", "./trades.json", "../ledger/rules.json", "../business/accounts.json")


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
    check("a. trades.json is current (tools/trading_export.py --check)", r.returncode == 0, r.stdout + r.stderr)
    check("a. the calendar is Mon-Fri (5 columns, 44 px cells at 320 px) with arrows and swipe; the day sheet is a labelled dialog",
          html.count("<span>") >= 5 and "repeat(5, minmax(0, 1fr))" in AK.read(os.path.join(D, "trading.css")) and 'id="calPrev"' in html and "touchend" in js
          and 'role="dialog"' in html and 'aria-modal="true"' in html and "'Escape'" in js)
    check("a. a trade opens in Odeon by its reel id (../odeon/#reel=)", "../odeon/#reel=" in core)


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


def test_rules():
    o = AK.node(APP, HARNESS, os.path.join(D, "trades.json"), os.path.join(AK.WEB, "ledger", "rules.json"), os.path.join(AK.WEB, "business", "accounts.json"))
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
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
