"""HESTIA, the OLYMPUS "today at home" screen (tools/web_public/hestia/, AGORA look, 2026-11-09): what should I do right now, for the three accounts.

  a. static: the files, the kit lines (?v=o3, data-app="hestia", the intro tag, a11y, sfx, agora.css), the AGORA look, read-only (no markup from data, no network except the published files), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (hestiacore.js): money + R words, "Drawdown left $X of $max loss", the New York clock and its windows (DST, weekend), the advice ladder (every branch), account matching, the trades
  c. Chromium 390 x 844 (and 375 x 667): the DEMO screen, the real home.json, no file at all, details, LITE and reduced motion, every tap >= 44 px, no sideways scroll, no console error, nothing off the page's origin
    python -X utf8 -m tests.test_hestia_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "hestia", "Hestia"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../odeon/trades.json"))
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page answers first (an 'answer' card before the accounts), then the three accounts, today, the clock and the bot's next action",
          html.index('id="answer"') < html.index('id="accts"') < html.index('id="todayCard"') < html.index('id="clockCard"') < html.index('id="botCard"'))
    fx = json.loads(AK.read(os.path.join(AK.WEB, APP, "fixture.json")))
    check("a. the fixture has Zlarior 50K, ATLAS 25K and BLITZ 25K with drawdown left, and a few trades with their R",
          [a["key"] for a in fx["accounts"]] == ["zlarior", "atlas", "blitz"] and all(a["room"] <= a["mll"] for a in fx["accounts"]) and all("r" in t for t in fx["trades"]))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.money = [C.money(1234.5), C.money(-437), C.money(-0.2), C.money(0), C.moneyS(312), C.moneyS(-60), C.moneyS(0), C.money('x')];
  o.r = [C.rText(312, 425), C.rText(-437, 425), C.rText(0, 425), C.rText(100, 0), C.rText(300, 150, true), C.both(312, 425, false), C.both(-60, 150, true)];
  o.dd = C.drawdownLine(1420, 2000);
  const at = (s) => { const x = C.sessionState(new Date(s)); return [x.id, x.et.hhmm, x.entries, x.next, x.mins]; };
  o.clock = { london: at('2026-11-09T07:00:00Z'), ny: at('2026-11-09T14:41:00Z'), wind: at('2026-11-09T20:40:00Z'), flat: at('2026-11-09T20:58:00Z'), brk: at('2026-11-09T22:30:00Z'), night: at('2026-11-10T03:00:00Z'), early: at('2026-11-09T06:59:00Z'),
              satd: at('2026-11-14T15:00:00Z'), fri: at('2026-11-13T21:30:00Z'), sun: at('2026-11-15T22:59:00Z'), sun2: at('2026-11-15T23:00:00Z'), dst: at('2026-03-09T06:00:00Z'), edt: at('2026-10-27T13:41:00Z') };
  o.dur = [C.duration(5), C.duration(60), C.duration(349), C.duration(1920), C.duration(null)];
  // accounts
  const real = { accounts: [
    { id: 'mffu50k_eval', name: 'MFFU 50K Eval', plan: 'Builder 50K', kind: 'eval', conn: { connected: true }, eval: { room: 1420, mll: 2000, floor: 48580, balance: 50420, today: 312, progress: 0.14, to_target: 2580, target_balance: 53000, start_balance: 50000, dll: 1000, dll_used: 0, clock_text: 'on pace' }, pnl: { today: 312, week: 640 }, stats: { avg_loss: -425 } },
    { id: 'acctb', name: 'ATLAS 25K', kind: 'eval', conn: { connected: true }, eval: { room: 240, mll: 1000, today: -60, progress: 0.05, to_target: 1425, dll: 600, dll_used: 60 }, pnl: { today: -60, week: 140 }, stats: {} },
    { id: 'acct_c', name: 'BLITZ', strategy: 'BLITZ', kind: 'funded', eval: null, pnl: { today: 0, week: 0 } },
    { id: 'paper_cloud', name: 'Paper (cloud)', kind: 'paper' }, { id: 'broken', name: 'ATLAS twin', error: 'boom' }] };
  const b = C.buildAccounts(real, null);
  o.keys = real.accounts.map(C.matchKey);
  o.real = { demo: b.demo, n: b.accounts.length, z: [b.accounts[0].room, b.accounts[0].mll, b.accounts[0].risk, b.accounts[0].toTarget, b.accounts[0].target, b.accounts[0].today], a: [b.accounts[1].room, b.accounts[1].mll, b.accounts[1].dllUsed], bl: [b.accounts[2].has, b.accounts[2].kind, b.accounts[2].room] };
  const fx = { accounts: [{ key: 'zlarior', room: 1420, mll: 2000, today: 10, risk: 425 }] };
  const d = C.buildAccounts({ accounts: [] }, fx);
  o.demo = { demo: d.demo, has: d.accounts.map((a) => a.has), room: d.accounts[0].room, dem: d.accounts[0].demo };
  o.nulls = [C.buildAccounts(null, null).demo, C.buildAccounts('x', {}).accounts.length, C.matchKey(null), C.matchKey({ id: 'zzz' })];
  const A = (room, mll, extra) => ({ ...C.accountView('zlarior', null), has: true, room, mll, name: 'Zlarior', ...extra });
  o.health = [C.health(A(1900, 2000)).level, C.health(A(900, 2000)).level, C.health(A(400, 2000)).level, C.health(A(1900, 2000, { dllUsed: 850, dll: 1000 })).level, C.health(A(1500, 2000, { progress: 1 })).level, C.health(A(null, 2000)).level, C.health({ has: false }).level];
  // the advice ladder
  const sess = (s) => C.sessionState(new Date(s));
  const ny = sess('2026-11-09T14:41:00Z'), good = [A(1700, 2000), { ...A(800, 1000), name: 'ATLAS' }];
  const adv = (m) => C.advice({ sess: ny, accounts: good, position: null, connected: true, ageMin: 3, ...m });
  o.adv = {
    calm: adv({}).level + '|' + adv({}).title, stale: adv({ connected: false }).title, age: adv({ ageMin: 45 }).level, crit: adv({ accounts: [A(300, 2000), ...good] }).title,
    done: adv({ accounts: [A(1700, 2000, { progress: 1 })] }).title, dll: adv({ accounts: [A(1700, 2000, { dllUsed: 900, dll: 1000 })] }).title, pos: adv({ position: { side: 'long' } }).title,
    closed: adv({ sess: sess('2026-11-14T15:00:00Z') }).title, night: adv({ sess: sess('2026-11-10T03:00:00Z') }).why.slice(0, 40), wind: adv({ sess: sess('2026-11-09T20:40:00Z') }).title,
    staleBeatsCrit: adv({ connected: false, accounts: [A(300, 2000)] }).title, none: adv({ accounts: [] }).level,
    critWhy: adv({ accounts: [A(300, 2000)] }).why.startsWith('Drawdown left $300 of $2,000 max loss') };
  // bot words
  o.bot = [C.botNext(ny, { side: 'long' }, null).slice(0, 16), C.botNext(sess('2026-11-09T07:00:00Z'), null, { model_state: 'watching London high' }).includes('Right now: watching London high'), C.botNext(sess('2026-11-14T15:00:00Z'), null, { model_state: 'x' }).includes('Right now')];
  // trades
  const raw = { trades: [null, { day: 'bad', usd: 1 }, { day: '2026-11-09', usd: 'x' }, { id: 'a', day: '2026-11-06', usd: -437, r: -1.03, side: 'short', qty: 5, entry: { t: 100 }, exit: { kind: 'STOP' } }, { id: 'b', day: '2026-11-09', usd: 312, r: 0.73, side: 'long', qty: 6, entry: { t: 200 } }, { id: 'c', day: '2026-11-09', usd: 100, entry: { t: 150 }, risk_usd: 50 }] };
  const T = C.normTrades(raw);
  o.trades = { n: T.length, first: T[0].id, today: C.tradesFor(T, '2026-11-09').list.length, label: C.tradesFor(T, '2026-11-09').label, last: C.tradesFor(T, '2026-11-10').label, lastDay: C.tradesFor(T, '2026-11-10').day, none: C.tradesFor([], '2026-11-09').label, r: [C.rOfTrade(T[0]), C.rOfTrade(T[1]), C.rOfTrade(T[2])] };
  o.add = [C.addDays('2026-11-09', -1), C.addDays('2026-03-01', -1), C.addDays('2026-12-31', 1)];
  const dt = C.demoTrades({ trades: [{ off: 0, usd: 10, r: 1, side: 'LONG' }, { off: 2, usd: -5, r: -1 }] }, '2026-11-09');
  o.demoT = [dt.length, dt.map((t) => t.day).sort(), C.demoTrades(null, '2026-11-09').length];
  // the Jarvis card
  const acc = b.accounts, card = C.jarvisCard(acc, C.advice({ sess: ny, accounts: acc, connected: true, ageMin: 1 }), ny, 1793394000.5);
  o.card = { v: card.v, name: card.name, lvl: card.status.level, kpis: card.kpis.length, lines: card.lines.length, t: Number.isInteger(card.t), len: Math.max(...card.kpis.map((k) => k.value.length)), ll: Math.max(...card.lines.map((x) => x.length)) };
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. money words: $1,235 (rounded), -$437, -$0.2 -> $0 (no minus zero), +$312, -$60, $0", o["money"] == ["$1,235", "-$437", "$0", "$0", "+$312", "-$60", "$0", "$0"], o["money"])
    check("b. every dollar has its R: +0.7R / -1.0R / 0.0R, no risk -> 0.0R, an estimate wears a ~, both() joins them", o["r"] == ["+0.7R", "-1.0R", "0.0R", "0.0R", "~+2.0R", "+$312 (+0.7R)", "-$60 (~-0.4R)"], o["r"])
    check("b. the drawdown sentence is exactly 'Drawdown left $X of $max loss'", o["dd"] == "Drawdown left $1,420 of $2,000 max loss", o["dd"])
    c = o["clock"]
    check("b. London 02:00 ET: entries on, next window in 360 min; 06:59Z (01:59) is overnight, 1 min to go", c["london"] == ["london", "02:00", True, "ny", 360] and c["early"] == ["overnight", "01:59", False, "london", 1], (c["london"], c["early"]))
    check("b. New York 09:41: next 'last call passed' in 349 min; 15:40 wind-down, 15:58 flat, 17:30 daily break (30 min)",
          c["ny"] == ["ny", "09:41", True, "winddown", 349] and c["wind"][:2] == ["winddown", "15:40"] and c["flat"][:2] == ["flat", "15:58"] and c["brk"] == ["break", "17:30", False, "overnight", 30], c)
    check("b. the weekend: Friday 16:30 and Saturday are closed, Sunday 17:59 closed, Sunday 18:00 the market opens (overnight); Saturday 10:00 -> Sunday 18:00 is 1920 min",
          c["fri"][0] == "closed" and c["satd"] == ["closed", "10:00", False, "overnight", 1920] and c["sun"][0] == "closed" and c["sun"][4] == 1 and c["sun2"][0] == "overnight", (c["fri"], c["satd"], c["sun"], c["sun2"]))
    check("b. New York time through the clock change: 06:00Z on 2026-03-09 is 02:00 EDT (London), 13:41Z on 2026-10-27 is 09:41 EDT", c["dst"][:2] == ["london", "02:00"] and c["edt"][:2] == ["ny", "09:41"], (c["dst"], c["edt"]))
    check("b. durations: 5 min, 1 h 0 min, 5 h 49 min, 1 day 8 h, empty", o["dur"] == ["5 min", "1 h 0 min", "5 h 49 min", "1 day 8 h", ""], o["dur"])
    r = o["real"]
    check("b. accounts: ids map to Zlarior / ATLAS / BLITZ; the paper twin and a broken row are ignored; Zlarior's numbers (drawdown 1420 of 2000, 1R = its average loss 425, target 3000)",
          o["keys"] == ["zlarior", "atlas", "blitz", None, "atlas"] and r["demo"] is False and r["n"] == 3 and r["z"] == [1420, 2000, 425, 2580, 3000, 312], (o["keys"], r))
    check("b. ATLAS: 240 of 1000 left and 60 of the daily loss used; BLITZ (funded, no eval) is present but has no drawdown number", r["a"] == [240, 1000, 60] and r["bl"] == [True, "funded", None], r)
    check("b. no real account -> DEMO with the fixture's numbers (the others stay 'no numbers yet'); null / junk input never throws",
          o["demo"] == {"demo": True, "has": [True, False, False], "room": 1420, "dem": True} and o["nulls"] == [True, 3, None, None], (o["demo"], o["nulls"]))
    check("b. health: safe / half used / close to the limit / daily loss 85% / target reached / not reported / no account", o["health"] == ["ok", "warn", "bad", "warn", "ok", "off", "off"], o["health"])
    a = o["adv"]
    check("b. advice, every branch: calm, PC silent (flag or 45 min), a close account, target reached, daily loss, open trade, closed market, overnight, wind-down",
          a["calm"] == "ok|Leave the bot alone" and a["stale"] == "Check the PC" and a["age"] == "warn" and a["crit"] == "Hands off Zlarior" and a["done"] == "Zlarior hit its target" and a["dll"].endswith("daily loss nearly used")
          and a["pos"] == "A trade is open" and a["closed"] == "Nothing to do" and a["night"].startswith("The bot starts watching in") and a["wind"] == "Check that you are flat", a)
    check("b. advice order: a silent PC beats a close account; with no accounts it is still calm; the close-account text carries the drawdown sentence", a["staleBeatsCrit"] == "Check the PC" and a["none"] == "ok" and a["critWhy"] is True, a)
    check("b. the bot's next action: an open trade, the live note only while entries are on", o["bot"][0] == "A trade is open." and o["bot"][1] is True and o["bot"][2] is False, o["bot"])
    t = o["trades"]
    check("b. trades: junk rows dropped (3 kept), newest first, today's list, else the last trading day (labelled), R from the file or a ~ estimate",
          t["n"] == 3 and t["first"] == "b" and t["today"] == 2 and t["label"] == "Today" and t["last"] == "Last trading day" and t["lastDay"] == "2026-11-09" and t["none"] == "No trades yet" and t["r"] == ["+0.7R", "~+2.0R", "-1.0R"], t)
    check("b. day maths without time zones: 2026-11-08, 2026-02-28, 2027-01-01; demo trades get real dates, junk fixture -> none", o["add"] == ["2026-11-08", "2026-02-28", "2027-01-01"] and o["demoT"] == [2, ["2026-11-07", "2026-11-09"], 0], (o["add"], o["demoT"]))
    cd = o["card"]
    check("b. the Jarvis card from the model: v1, name, a level Jarvis knows, 3 kpis, 1 line <= 120, integer t", cd["v"] == 1 and cd["name"] == "Hestia" and cd["lvl"] in ("ok", "warn", "bad", "off") and cd["kpis"] == 3 and cd["lines"] == 1 and cd["t"] and cd["ll"] <= 120 and cd["len"] <= 24, cd)


# ------------------------------------------------------------------------------------------------ c. Chromium
def home_json():
    return json.dumps({"built": "x", "accounts": [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "conn": {"connected": True},
         "eval": {"room": 1420, "mll": 2000, "floor": 48580, "balance": 50420, "today": 312, "progress": 0.14, "to_target": 2580, "target_balance": 53000, "start_balance": 50000, "dll": 1000, "dll_used": 0, "clock_text": "Session 4 of 10"},
         "pnl": {"today": 312, "week": 640}, "stats": {"avg_loss": -425}},
        {"id": "acctb", "name": "ATLAS 25K", "kind": "eval", "conn": {"connected": True}, "eval": {"room": 240, "mll": 1000, "today": -60, "progress": 0.05, "to_target": 1425, "dll": 600, "dll_used": 60}, "pnl": {"today": -60, "week": 140}, "stats": {}}],
        "live": {"position": None, "model_state": "watching the London high"}})


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-09T14:41:00Z")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, cards: document.querySelectorAll('#accts .acct').length, ans: document.querySelector('#ansH').textContent, dd: [...document.querySelectorAll('.dd')].map((e) => e.textContent),
              clock: document.querySelector('#clkTime').textContent, phase: document.querySelector('#clkPhase').textContent, tl: document.querySelectorAll('#tlist .trow').length, tl0: document.querySelector('#tlist .trow b').textContent,
              h1: document.querySelectorAll('h1').length, status: document.querySelector('#status').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme,
              reads: performance.getEntriesByType('resource').map((r) => r.name).filter((u) => /home\\.json|trades\\.json/.test(u)).length }) """)
            check("c. DEMO (?demo=1): the DEMO chip, three account cards, an answer, 09:41 New York day, example trades with their R",
                  d["demo"] and d["cards"] == 3 and d["ans"] == "Leave the bot alone" and d["clock"] == "09:41" and d["phase"] == "New York day" and d["tl"] == 1 and "(+0.7R)" in d["tl0"], d)
            check("c. 'Drawdown left $X of $max loss' on every eval card (Zlarior $1,420 of $2,000, ATLAS $840 of $1,000, BLITZ $560 of $1,000)",
                  d["dd"] == ["Drawdown left $1,420 of $2,000 max loss", "Drawdown left $840 of $1,000 max loss", "Drawdown left $560 of $1,000 max loss"], d["dd"])
            check("c. the AGORA look: a serif title, a warm dark body (not black), data-theme agora, one h1, a spoken status line", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] != "rgb(0, 0, 0)" and d["theme"] == "agora" and d["h1"] == 1 and "Leave the bot alone" in d["status"], d)
            check("c. ?demo=1 never reads the real files", d["reads"] == 0 and not any("home.json" in u for u in seen), seen[-6:])
            AK.shot(p, "hestia-demo")
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's bottom-right corner is free", AK.no_sideways(p) and not AK.corner(p))
            check("c. no console error, no page error, nothing requested off the page's origin", not errs and not off, (errs[:3], off[:3]))
            btn = p.locator("#accts .acct button").first
            btn.click()
            p.wait_for_timeout(150)
            o = p.evaluate("() => ({ exp: document.querySelector('#accts .acct button').getAttribute('aria-expanded'), vis: !document.querySelector('#more-zlarior').hidden, txt: document.querySelector('#more-zlarior').textContent })")
            check("c. Details opens the account's extra lines (week, balance, floor, daily loss used) and says so (aria-expanded)", o["exp"] == "true" and o["vis"] and "This week" in o["txt"] and "Trailing floor" in o["txt"] and "Daily loss used" in o["txt"], o)
            ctx.close()
            # ---- the weekend and the night
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-14T15:00:00Z")
            w = p.evaluate("() => [document.querySelector('#ansH').textContent, document.querySelector('#clkPhase').textContent, document.querySelector('#clkNext').textContent, document.querySelector('#clkEntries').textContent]")
            check("c. Saturday: 'Nothing to do', market closed, the next window and how long (1 day 8 h), no new trade", w[0] == "Nothing to do" and w[1] == "Market closed" and "1 day 8 h" in w[2] and "will not open" in w[3], w)
            ctx.close()
            # ---- the real home.json
            srv2, origin2 = AK.serve({"/home.json": home_json()})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=2026-11-09T14:41:00Z")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, dd: [...document.querySelectorAll('.dd')].map((e) => e.textContent), blitz: document.querySelector('[data-key=blitz]').textContent, today: document.querySelector('#todayTiles').textContent, ans: document.querySelector('#ansH').textContent,
              pills: [...document.querySelectorAll('.acct-top .pill')].map((e) => e.textContent), z: document.querySelector('[data-key=zlarior] .kv').textContent })""")
            check("c. the real home.json: no DEMO chip, Zlarior and ATLAS from the file, BLITZ 'no numbers yet' (never invented), the day's sum next to its week", not r["demo"] and r["dd"][:2] == ["Drawdown left $1,420 of $2,000 max loss", "Drawdown left $240 of $1,000 max loss"] and "No numbers yet" in r["blitz"] and "+$252" in r["today"], r)
            check("c. ATLAS at 24% of its max loss left is 'Close to the limit' and the answer is 'Hands off ATLAS'; Zlarior's day shows +$312 (+0.7R)", r["pills"][1] == "Close to the limit" and r["ans"] == "Hands off ATLAS" and "+$312 (+0.7R)" in r["z"] and "~" not in r["z"], r)
            check("c. the real run reads the site's files only (home.json, odeon/trades.json) and nothing off the origin", any("home.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            # ---- no file at all (the plain site folder has no home.json): DEMO, never blank
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "")
            n = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, cards: document.querySelectorAll('#accts .acct').length, ans: document.querySelector('#ansH').textContent.length })")
            check("c. no home.json on the site: the DEMO screen appears by itself, never blank", n["demo"] and n["cards"] == 3 and n["ans"] > 5, n)
            ctx.close()
            # ---- small phone, LITE, reduced motion
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-09T14:41:00Z&q=low")
            check("c. 375 x 667 with LITE and reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
