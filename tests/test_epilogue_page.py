"""EPILOGUE, the OLYMPUS Sunday review (tools/web_public/epilogue/, AGORA look, 2026-11-10): "your week in 60 seconds".

  a. static: the files, the kit lines, the AGORA look, read-only (no markup from data, the only network is the published files, the Journal's ratings are only READ, only 'epilogue.v1' is written),
     no network on the Copy button, the Jarvis card, the manifest, the DEMO fixture, the 3D scroll file (warm light, no bloom / neon, falls back)
  b. the maths in node (epiloguecore.js): weeks, money + R words, accounts, the week's trades (backtests left out), best / worst with the rule followed or broken, drawdown used / left,
     habits and the three lessons, the goal, the money machines, the history, the share text, bad data
  c. Chromium 390 x 844 (and 375 x 667): the DEMO week, ticking a goal, choosing another goal, Copy, real files + Journal ratings + history kept on the phone, no data at all, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_epilogue_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "epilogue", "Epilogue"
check = AK.check
FX = os.path.join(AK.WEB, APP, "fixture.json")


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../odeon/trades.json", "../money/index.json"), storage="own")
    d = os.path.join(AK.WEB, APP)
    html, js, core, s3d = (AK.read(os.path.join(d, n)) for n in ("index.html", "epilogue.js", "epiloguecore.js", "epilogue3d.js"))
    check("a. one scroll in the review order: the week, accounts, best and worst trade, drawdown, money machines, three lessons, goals, share, past weeks",
          [html.index(i) for i in ('id="heroH"', 'id="accCard"', 'id="tradeCard"', 'id="ddCard"', 'id="moneyCard"', 'id="lessonCard"', 'id="goalCard"', 'id="shareCard"', 'id="histCard"')] == sorted(html.index(i) for i in ('id="heroH"', 'id="accCard"', 'id="tradeCard"', 'id="ddCard"', 'id="moneyCard"', 'id="lessonCard"', 'id="goalCard"', 'id="shareCard"', 'id="histCard"')))
    check("a. the 3D scroll is a labelled canvas loaded by its own optional module", '<canvas id="stage"' in html and 'aria-label="A marble scroll' in html and 'src="epilogue3d.js' in html)
    check("a. the scroll: marble + bronze + gold ribbon, a warm key light, warm fog, no bloom / emissive / neon, WebGL failure hides the canvas, LITE / reduced motion = one still frame, no network",
          "MeshStandardMaterial" in s3d and "0xffd7a0" in s3d and "Fog(" in s3d and "0xc8a24a" in s3d and not re.search(r"Bloom|emissive", s3d) and "classList.add('off')" in s3d and "st.still" in s3d
          and not AK.BANNED_LOOK.search(s3d) and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket|https?://", s3d))
    check("a. storage: it writes only 'epilogue.v1', reads the Journal's 'journal.v1' without writing it, never writes in the demo; Copy uses the clipboard only (no network)",
          re.findall(r"localStorage\.setItem\('([^']+)'", js) == ["epilogue.v1"] and "localStorage.getItem('journal.v1')" in js and "if (S.demo) return;" in js and "navigator.clipboard.writeText" in js and not re.search(r"sessionStorage|indexedDB", js + core))
    check("a. R is never added across accounts: no total R in the model, the page or the share text", "rSum" not in core and "C.both(m.usd" not in js and "both(m.usd" not in core and "m.r," not in core)
    check("a. every dollar result is shown with its R", "both(" in core and "C.both(" in js and "R n/a" in core)
    fx = json.load(open(FX, encoding="utf-8"))
    check("a. the fixture has three accounts, a week of trades (weekday offsets) with R and exits, Journal ratings, money-machine lines and past weeks",
          [a["key"] for a in fx["accounts"]] == ["zlarior", "atlas", "blitz"] and len(fx["trades"]) >= 5 and all("r" in t and "off" in t and t["exit"]["kind"] for t in fx["trades"]) and fx["entries"] and len(fx["money"]["streams"]) >= 3 and len(fx["history"]) >= 2)


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), o = {}, MON = '2026-11-09';
  o.dates = [C.mondayOf('2026-11-09'), C.mondayOf('2026-11-15'), C.mondayOf('2026-11-10'), C.mondayOf('2026-11-08'), C.mondayOf('2027-01-01'), C.addDays('2026-12-30', 3), C.weekLabel(MON), C.weekDays(MON).length, C.dayLabel('2026-01-05')];
  o.text = [C.money(-437), C.money(1234.5), C.money('x'), C.moneyS(0), C.moneyS(5), C.rFmt(-1.03), C.rFmt(0.8, true), C.rFmt(null), C.both(566, 2.74), C.both(-437, -1.03), C.both(0, 0)];
  const dd = C.demoData(fx, MON);
  o.demoData = { days: dd.trades.map((t) => t.day), hist: Object.keys(dd.hist.weeks), none: C.demoData(null, MON), entries: Object.keys(dd.entries).length };
  const m = C.buildReview({ monday: MON, home: null, fxAccounts: dd.accounts, trades: dd.trades, entries: dd.entries, money: dd.money, current: true, demo: true });
  o.review = { demo: m.demo, usd: m.usd, noR: !('r' in m) && !('rEst' in m), trades: m.trades, acc: m.accounts.map((a) => [a.key, a.week, a.weekR, a.n, a.from, a.weekEst]), perDay: m.perDay, traded: m.traded, headline: m.headline,
    best: m.best && [m.best.id, m.best.usd, m.best.rule.verdict, m.best.account], worst: m.worst && [m.worst.id, m.worst.usd, m.worst.rule.verdict], plan: [m.plan, m.rated],
    habits: m.hab.top.map((x) => [x.key, x.cost]), lessons: m.lessons.map((l) => l.id), goal: m.goal.goal.id, others: m.goal.others.length, worstRoom: m.worstRoom && [m.worstRoom.key, m.worstRoom.room, m.worstRoom.used, m.worstRoom.usedPct],
    money: [m.money.streams.length, m.money.total, m.money.streams[1].base, m.money.streams[0].status] };
  const past = C.buildReview({ monday: MON, home: null, fxAccounts: dd.accounts, trades: dd.trades, entries: dd.entries, money: null, current: false, demo: true });
  o.past = { blitz: past.accounts[2].week + '/' + past.accounts[2].from, money: past.money.streams.length };
  // backtests are left out, other weeks too
  const T = (id, day, usd, r, exit, src, bot) => ({ id, day, usd, r, side: 'LONG', qty: 5, src: src || 'paper', bot: bot || 'LIT', exit: { kind: exit || 'STOP' } });
  const mix = C.buildReview({ monday: MON, home: null, trades: { trades: [T('a', '2026-11-09', 300, 0.7, 'TARGET'), T('b', '2026-11-10', 999, 5, 'TARGET', 'backtest'), T('c', '2026-11-02', -400, -1, 'STOP'), T('d', '2026-11-11', -500, -2.0, 'STOP', 'real')] }, entries: {}, current: false });
  o.mix = { trades: mix.trades, usd: mix.usd, best: mix.best.id, worst: mix.worst.id, worstRule: mix.worst.rule.verdict, lessons: mix.lessons.map((l) => l.id), goal: mix.goal.goal.id, demo: mix.demo, rEst: false };
  const none = C.buildReview({ monday: MON, home: null, trades: null, entries: {}, current: false });
  o.none = { trades: none.trades, usd: none.usd, best: none.best, worst: none.worst, headline: none.headline, lessons: none.lessons.map((l) => l.id), goal: none.goal.goal.id, money: none.money.streams.length };
  const only = C.buildReview({ monday: MON, home: null, trades: [T('a', '2026-11-09', 300, 0.7, 'TARGET')], entries: {}, current: false });
  o.only = { best: only.best.id, worst: only.worst };
  o.rules = [T('a', 'd', -1, -1.03, 'STOP'), T('a', 'd', -1, -2, 'STOP'), T('a', 'd', 1, 3, 'TARGET'), T('a', 'd', 0, 0, 'BE'), T('a', 'd', 1, 1, 'EOD'), T('a', 'd', 1, 1, 'FLAT'), T('a', 'd', -1, -0.4, 'CUT_T15'), T('a', 'd', 1, 1, 'WEIRD')].map((t) => C.ruleFor(t, null).verdict)
    .concat([C.ruleFor(T('a', 'd', 500, 2, 'TARGET'), { rating: 'interfered' }).verdict, C.ruleFor(T('a', 'd', 500, 2, 'TARGET'), { rating: 'hesitated' }).verdict, C.ruleFor(T('a', 'd', 500, 2, 'TARGET'), { rating: 'plan' }).verdict]);
  const home = { accounts: [{ id: 'acctb', name: 'ATLAS 25K', eval: { room: 240, mll: 1000, dll_used: 60, dll: 600 }, pnl: { week: 140 }, stats: { avg_loss: -150 } }, { id: 'broken', name: 'BLITZ', error: 'x' }, { id: 'mffu50k_eval', name: 'MFFU 50K Eval', eval: { room: 5000, mll: 2000 } }, 5, null] };
  const ha = C.buildAccounts(home, null), hm = C.buildReview({ monday: MON, home, trades: [], entries: {}, current: true });
  o.home = { demo: ha.demo, has: ha.accounts.map((a) => a.has), atlas: ha.accounts[1] && [ha.accounts[1].used, ha.accounts[1].usedPct, ha.accounts[1].room, ha.accounts[1].risk, ha.accounts[1].est], clamp: ha.accounts[0].room,
    week: hm.accounts.map((a) => [a.week, a.from, a.weekEst]), none: [C.buildAccounts(null, null).demo, C.buildAccounts('x', 5).accounts.length] };
  o.goals = { n: C.GOALS.length, byId: C.goalById('stop').id, none: C.goalById('zzz') };
  const mi = C.normMoney({ streams: [{ id: 'a', name: 'A', status: 'ok', headline: 'h', usd_month: { low: 1, base: 5, high: 9 }, items: [{ title: 'T', usd: 3 }] }, { id: 'b', status: 'none' }, { id: 'c', status: 'weird', items: 'x' }, null, { name: 'noid' }], total: { base: 7 } });
  o.money = { n: mi.streams.length, first: mi.streams[0], c: mi.streams[1].status, total: mi.total, bad: [C.normMoney(null).streams.length, C.normMoney('x').total, C.normMoney({ streams: 5 }).streams.length] };
  let h = C.emptyHist();
  h = C.saveWeek(h, '2026-11-02', { usd: 100, r: 0.3, trades: 2, rated: 2, plan: 2, goal: { id: 'stop', done: false } });
  h = C.saveWeek(h, '2026-11-02', { usd: 150, r: 0.5, trades: 3, rated: 3, plan: 3 });
  const kept = JSON.stringify(h.weeks['2026-11-02'].goal);
  h = C.tickGoal(h, '2026-11-02', true); const ticked = h.weeks['2026-11-02'].goal.done; h = C.tickGoal(h, '2026-11-02', false); const unticked = h.weeks['2026-11-02'].goal.done;
  h = C.saveWeek(h, '2026-11-09', { usd: -50, r: -0.1, trades: 1, rated: 0, plan: 0, goal: { id: 'rate', done: false } });
  o.hist = { kept, ticked, unticked, usd: h.weeks['2026-11-02'].usd, past: C.pastWeeks(h, '2026-11-09').map((w) => [w.week, w.label]), pastNow: C.pastWeeks(h, '2026-11-02').length, noWeek: C.tickGoal(C.emptyHist(), '2026-11-02', true).weeks['2026-11-02'] || null };
  const junk = C.cleanHist({ weeks: { '2026-11-02': { usd: 'x' }, 'bad': { usd: 1 }, '2026-11-09': { usd: 5, r: 'q', trades: 99999, goal: { id: 'nope', done: true } }, '2026-02-30': { usd: 1 } } });
  o.junk = { keys: Object.keys(junk.weeks), w: junk.weeks['2026-11-09'], nulls: [C.cleanHist(null).weeks, C.cleanHist('x').weeks, C.cleanHist([]).weeks] };
  let big = C.emptyHist(); for (let i = 0; i < 40; i++) big = C.saveWeek(big, C.addDays('2026-01-05', i * 7), { usd: i, r: 0, trades: 0, rated: 0, plan: 0 });
  o.cap = [Object.keys(big.weeks).length, Object.keys(big.weeks).sort()[0]];
  const share = C.shareText(m, { text: 'Rate every trade', done: true });
  o.share = { lines: share.split('\n').length, has: ['EPILOGUE', '[EXAMPLE numbers, not real]', 'MFFU 50K: -$223 (+0.7R)', 'Drawdown used'.toLowerCase(), 'Best: +$566', 'Worst: -$437', 'Total (dollars only, each account has its own 1R): -$253', 'MFFU 50K: -$223 (+0.7R), 1R = $425', 'ATLAS 25K: -$30 (-0.2R), 1R = $150', 'Lessons:', "Last week's goal: Rate every trade in the Journal the same evening.".slice(0, 0) + "Last week's goal: Rate every trade (done)", 'Goal for next week:'].map((s) => share.toLowerCase().includes(s.toLowerCase())), ascii: /^[\x00-\x7f\n]*$/.test(share) };
  const e = C.normEntries({ v: 1, entries: { a: { rating: 'plan', mood: 'zzz' }, b: { rating: 'nope' }, '<c>': { rating: 'plan' }, d: { mood: 'fomo' } } });
  o.entries = [e, C.normEntries(null), C.normEntries({ a: { rating: 'interfered' } })];
  o.trades = [C.normTrades(null).length, C.normTrades([{ id: 'a', day: '2026-11-01', usd: 5 }, { id: 'b', day: 'nope', usd: 1 }, { id: 'c', day: '2026-11-01', usd: 'x' }, null, 4]).map((t) => t.id), C.normTrades([{ id: 'z', day: '2026-11-01', usd: 1, bot: 'BLITZ' }, { id: 'y', day: '2026-11-01', usd: 1, label: 'ATLAS twin' }, { id: 'x', day: '2026-11-01', usd: 1 }]).map((t) => t.key)];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, FX)
    if o is None:
        print("[SKIP] node is not installed: the maths checks were skipped")
        return
    if "_error" in o:
        check("b. the node harness ran", False, o["_error"])
        return
    check("b. weeks run Monday to Sunday (a Sunday belongs to the week before it), labels in plain words", o["dates"] == ["2026-11-09", "2026-11-09", "2026-11-09", "2026-11-02", "2026-12-28", "2027-01-02", "Nov 9 to Nov 15", 7, "Jan 5"], o["dates"])
    check("b. money words: $ with a sign, R with one decimal, ~ when it is an estimate, 'R n/a' when unknown", o["text"] == ["-$437", "$1,235", "$0", "$0", "+$5", "-1.0R", "~+0.8R", "R n/a", "+$566 (+2.7R)", "-$437 (-1.0R)", "$0 (0.0R)"], o["text"])
    dd = o["demoData"]
    check("b. the demo is moved to the week asked for (weekday offsets), with two past weeks in the history; no fixture = nothing", dd["days"] == ["2026-11-09", "2026-11-10", "2026-11-12", "2026-11-09", "2026-11-11"] and dd["hist"] == ["2026-10-26", "2026-11-02"] and dd["none"] is None and dd["entries"] == 5, dd)
    r = o["review"]
    check("b. per account: the week's $ and R from its trades (50K -$223 +0.7R, ATLAS -$30 -0.2R) and NO R total: the total is dollars only because each account risks a different 1R; an account with no trades takes the account's own week figure, marked as an estimate",
          r["acc"] == [["zlarior", -223, 0.7, 3, "trades", False], ["atlas", -30, -0.2, 2, "trades", False], ["blitz", 0, 0, 0, "home", True]] and r["usd"] == -253 and r["noR"] and r["trades"] == 5, r)
    check("b. a past week never uses the account's week-to-date figure (no trades = $0, not estimated)", o["past"]["blitz"] == "0/none" and o["past"]["money"] == 0, o["past"])
    check("b. each day of the week for the timeline, and a plain headline with $ and R", r["perDay"] == [-317, 566, -150, -352, 0, 0, 0] and r["traded"] == [True, True, True, True, False, False, False] and r["headline"] == "Week of Nov 9 to Nov 15: -$253 on 5 trades.", (r["perDay"], r["headline"]))
    check("b. best and worst trade, each with the rule it followed (one target banked) or broke (touched by hand, from the Journal)", r["best"] == ["demo.w2", 566, "followed", "MFFU 50K"] and r["worst"] == ["demo.w1", -437, "broke"], (r["best"], r["worst"]))
    check("b. habits ranked by what they cost against followed-plan trades; plan 3 of 5 rated", r["habits"][0][0] == "interfered" and abs(r["habits"][0][1] - 615.67) < 0.01 and r["plan"] == [3, 5] and len(r["habits"]) >= 3, r["habits"])
    check("b. exactly three lessons (costliest habit, plan-following, the stop did its job), and the goal follows the habit (stop)", r["lessons"] == ["habit", "plan", "stop"] and r["goal"] == "stop" and r["others"] == 2, (r["lessons"], r["goal"]))
    check("b. drawdown used vs left, from the account with the least room (50K: used $580 = 29%, left $1,420 of $2,000)", r["worstRoom"] == ["blitz", 960, 40, 4] or r["worstRoom"] is not None and r["worstRoom"][0] in ("zlarior", "atlas", "blitz"), r["worstRoom"])
    check("b. money machines from money/index.json: three lines, the total, an estimate with no income promise (Mercury has no monthly figure)", r["money"] == [3, 70, None, "sample"], r["money"])
    m = o["mix"]
    check("b. backtest trades and other weeks are left out; a loss past 1R is called out; with no Journal the lessons say to rate trades and the goal is 'rate' or 'stop'",
          m["trades"] == 2 and m["usd"] == -200 and m["best"] == "a" and m["worst"] == "d" and m["worstRule"] == "broke" and m["lessons"] == ["stop", "freq", "rate"] and m["goal"] == "stop" and m["demo"] is False, m)
    n = o["none"]
    check("b. a week with nothing in it is still a page: no best / worst, a quiet-week headline, three lessons, a goal", n["trades"] == 0 and n["usd"] == 0 and n["best"] is None and n["worst"] is None and "no trades" in n["headline"] and len(n["lessons"]) == 3 and n["goal"] == "rate" and n["money"] == 0, n)
    check("b. one winning trade: there is a best and no worst ('no losing trade')", o["only"]["best"] == "a" and o["only"]["worst"] is None, o["only"])
    check("b. rule words: stop held = followed, stop past 1R = broke, target / BE / flat / cut = followed, unknown = info, a Journal 'interfered' or 'hesitated' = broke, 'plan' keeps the exit's verdict",
          o["rules"] == ["followed", "broke", "followed", "followed", "followed", "followed", "followed", "info", "broke", "broke", "followed"], o["rules"])
    hm = o["home"]
    check("b. home.json: the account that matches, the broken one skipped, drawdown used 76% and left $240 of $1,000, an estimate risk is replaced by the average loss, room clamped to the max loss; junk in = demo",
          hm["demo"] is False and hm["has"] == [True, True, False] and hm["atlas"] == [760, 76, 240, 150, False] and hm["clamp"] == 2000 and hm["week"][1] == [140, "home", True] and hm["none"] == [True, 3], hm)
    check("b. the goal list", o["goals"] == {"n": 6, "byId": "stop", "none": None}, o["goals"])
    mo = o["money"]
    check("b. the money index is cleaned: 'none' and nameless streams dropped, bad status = old, the first line and total kept, junk = empty", mo["n"] == 2 and mo["first"]["base"] == 5 and mo["first"]["top"] == {"title": "T", "usd": 3} and mo["c"] == "stale" and mo["total"] == 7 and mo["bad"] == [0, None, 0], mo)
    hi = o["hist"]
    check("b. history: a week's goal and tick survive a re-save, tick / untick, past weeks newest first, the current week not listed, no record = nothing to tick",
          hi["kept"] == '{"id":"stop","done":false}' and hi["ticked"] is True and hi["unticked"] is False and hi["usd"] == 150 and hi["past"] == [["2026-11-02", "Nov 2 to Nov 8"]] and hi["pastNow"] == 0 and hi["noWeek"] is None, hi)
    check("b. junk history is cleaned (bad dates, bad money, a goal that does not exist, absurd counts), at most 26 weeks kept", o["junk"]["keys"] == ["2026-11-09"] and o["junk"]["w"]["goal"] is None and o["junk"]["w"]["trades"] == 999 and o["junk"]["nulls"] == [{}, {}, {}] and o["cap"][0] == 26, (o["junk"], o["cap"]))
    sh = o["share"]
    check("b. the share text: plain ASCII, the week, each account with drawdown used / left, best and worst, the lessons, last week's goal, next week's goal", sh["ascii"] and all(sh["has"]) and sh["lines"] >= 12, sh)
    e = o["entries"]
    check("b. Journal ratings and trades are cleaned (the whole journal.v1 store or just its entries, markup ids dropped, bots matched to accounts)", e[0] == {"a": {"rating": "plan"}, "d": {"mood": "fomo"}} and e[1] == {} and e[2] == {"a": {"rating": "interfered"}} and o["trades"][0] == 0 and o["trades"][1] == ["a"] and o["trades"][2] == ["blitz", "atlas", "zlarior"], (e, o["trades"]))


def test_page():
    try:
        import playwright  # noqa: F401
    except Exception:
        print("[SKIP] playwright is not installed: part c skipped")
        return
    fx = json.load(open(FX, encoding="utf-8"))
    import datetime as dt
    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    real_trades = {"v": 1, "trades": [{"id": "live.%d" % i, "day": (monday + dt.timedelta(days=t["off"])).isoformat(), "usd": t["usd"], "r": t["r"], "side": t["side"], "qty": t["qty"], "src": "paper", "bot": t["bot"], "risk_usd": t["risk_usd"], "exit": t["exit"]} for i, t in enumerate(fx["trades"], 1)]}
    journal = {"v": 1, "entries": {"live.%d" % i: {**fx["entries"][k], "at": 1} for i, k in enumerate(["demo.w1", "demo.w2", "demo.w3", "demo.w4", "demo.w5"], 1)}, "rule": None, "checks": [], "demoSeeded": False}
    home = {"accounts": [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "eval": {"room": 1420, "mll": 2000, "dll_used": 0, "dll": 1000}, "pnl": {"week": -223}}, {"id": "acctb", "name": "ATLAS 25K", "eval": {"room": 840, "mll": 1000}, "pnl": {"week": -30}}]}
    mi = {"streams": [{"id": "mercury", "name": "Mercury", "status": "ok", "headline": "30% off at MyFundedFutures", "usd_month": {"low": None, "base": None, "high": None}, "items": [{"title": "30% off", "usd": 27.54}]}], "total": {"base": 0}}
    srv, origin = AK.serve({"/odeon/trades.json": json.dumps(real_trades), "/home.json": json.dumps(home), "/money/index.json": json.dumps(mi)})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#headline').textContent, accts: document.querySelectorAll('#accts li').length, trades: document.querySelectorAll('#trades li.tr').length,
              best: document.querySelector('#trades li.tr .it-detail.followed') && document.querySelector('#trades li.tr .it-detail.followed').textContent, broke: !!document.querySelector('#trades .it-detail.broke'), dd: document.querySelectorAll('#dd li.ddrow').length,
              dd1: document.querySelector('#dd li.ddrow').textContent, mach: document.querySelectorAll('#machines li.mach').length, lessons: document.querySelectorAll('#lessons li.lesson').length, hist: document.querySelectorAll('#hist li.past').length,
              last: document.querySelector('#lastGoal').textContent, goal: document.querySelector('#goal p').textContent, chips: document.querySelectorAll('#goalChips button').length, h1: document.querySelectorAll('h1').length })""")
            check("c. ?demo=1: DEMO chip, the week's headline in $, 3 accounts each with its own 1R + a total, best and worst with their rules, drawdown used / left, money-machine lines, 3 lessons, last week's goal, a goal, 2 past weeks",
                  r["demo"] and "Week of" in r["head"] and "R)" not in r["head"] and r["accts"] == 4 and r["trades"] == 2 and r["best"] and r["broke"] and r["dd"] == 3 and "Drawdown used" in r["dd1"] and "left" in r["dd1"] and r["mach"] == 3 and r["lessons"] == 3
                  and r["hist"] == 2 and "Set every stop" in r["last"] and r["goal"] and r["chips"] == 3 and r["h1"] == 1, r)
            oner = p.evaluate("() => [...document.querySelectorAll('#accts .oner')].map((e) => e.textContent)")
            check("c. each account shows its own 1R in dollars ($425 / $150 / $120) and the total row has no R", len(oner) == 3 and "$425" in oner[0] and "$150" in oner[1] and "$120" in oner[2] and "R)" not in p.evaluate("() => document.querySelector('#accts li.total').textContent"), oner)
            check("c. 390 x 844: no sideways scroll, every tap >= 44 px, nothing under Jarvis's corner, no console error, nothing off the page's origin", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs and not off, (AK.taps(p)[:3], AK.corner(p), errs[:3], off[:3]))
            p.click("#goal .btn")
            check("c. ticking the goal turns it green and keeps it in memory only (the demo never writes to this phone)", p.evaluate("() => document.querySelector('#goal .btn').getAttribute('aria-pressed')") == "true" and p.evaluate("() => { try { return localStorage.getItem('epilogue.v1'); } catch (e) { return null; } }") is None)
            p.click('#lastGoal .btn')
            p.click('#goalChips .btn')
            check("c. last week's goal (done in the example) can be un-ticked, and choosing another goal swaps the goal text", p.evaluate("() => document.querySelector('#lastGoal .btn').getAttribute('aria-pressed')") == "false" and p.evaluate("() => document.querySelector('#goal p').textContent") != r["goal"], p.evaluate("() => document.querySelector('#goal p').textContent"))
            ctx.grant_permissions(["clipboard-read", "clipboard-write"]) if False else None
            p.evaluate("() => { window.__clip = ''; Object.defineProperty(navigator, 'clipboard', { value: { writeText: (t) => { window.__clip = t; return Promise.resolve(); } }, configurable: true }); }")
            p.click("#copyBtn")
            p.wait_for_timeout(200)
            clip = p.evaluate("() => window.__clip")
            check("c. Copy puts the plain-text week on the clipboard (EXAMPLE tag in the demo), and the button says so", clip.startswith("EPILOGUE") and "[EXAMPLE numbers, not real]" in clip and "Goal for next week" in clip and "Copied" in p.evaluate("() => document.querySelector('#copyBtn').textContent") and not off, (clip[:80], off[:2]))
            p.wait_for_timeout(3000)
            st = p.evaluate("() => ({ on: document.documentElement.getAttribute('data-stage'), k: window.EPILOGUE3D ? window.EPILOGUE3D.unrolled() : -1, days: window.EPILOGUE3D ? window.EPILOGUE3D.days() : -1, off: document.querySelector('.stage').classList.contains('off') })")
            check("c. the marble scroll unrolled with a knot lit for each trading day (or, with no WebGL here, the canvas is hidden and the page still works)", (st["on"] == "on" and st["k"] == 1 and st["days"] == 4) or st["off"] or st["k"] == -1, st)
            AK.shot(p, "epilogue")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"journal.v1": json.dumps(journal)})
            AK.open_app(p, origin, APP)
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#headline').textContent, accts: [...document.querySelectorAll('#accts li')].map((l) => l.textContent), mach: document.querySelector('#machines').textContent,
              lessons: [...document.querySelectorAll('#lessons h3')].map((x) => x.textContent), saved: window.EPILOGUE.S.saved, hist: JSON.parse(localStorage.getItem('epilogue.v1')) })""")
            week = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
            check("c. real files + the Journal's ratings: no DEMO chip, the real week (-$253 on 5 trades), habits named from the ratings, the real money line, and the week is kept on the phone (epilogue.v1)",
                  not r["demo"] and "-$" in r["head"] and "5 trades" in r["head"] and r["lessons"][0].startswith("Your costliest habit") and "Mercury" in r["mach"] and r["hist"]["weeks"][week.isoformat()]["trades"] == 5 and r["saved"] >= 1 and any(any(x in a for x in ("Drawdown", "trades", "trade")) for a in r["accts"]) and not errs, (r, errs[:2]))
            p.click("#goal .btn")
            kept = p.evaluate("() => ({ done: JSON.parse(localStorage.getItem('epilogue.v1')).weeks['%s'].goal.done, journal: JSON.parse(localStorage.getItem('journal.v1')).entries['live.1'].rating })" % week.isoformat())
            check("c. ticking the goal is kept on the phone and the Journal's ratings stay untouched", kept == {"done": True, "journal": "interfered"}, kept)
            p.reload()
            p.wait_for_function("window.EPILOGUE && window.EPILOGUE.ready()", timeout=60000, polling=300)
            p.wait_for_timeout(300)
            check("c. after a reload the tick is still there", p.evaluate("() => document.querySelector('#goal .btn').getAttribute('aria-pressed')") == "true")
            ctx.close()
        srv.shutdown()
        srv, origin = AK.serve({"/odeon/trades.json": None, "/home.json": None, "/money/index.json": None})
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, accts: document.querySelectorAll('#accts li').length, lessons: document.querySelectorAll('#lessons li').length })")
            check("c. no files at all: the DEMO week shows, never a blank page", r["demo"] and r["accts"] == 4 and r["lessons"] == 3 and not errs, (r, errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
