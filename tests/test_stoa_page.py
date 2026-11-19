"""STOA, the OLYMPUS colonnade "what needs me now" (tools/web_public/stoa/, AGORA look, 2026-11-10): six cards from the site's published JSON, one plain sentence each, Done / Snooze on this phone, a row of marble columns (3D, 2D fallback), a lit column = something needs you.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the 3D module is separate and optional
  b. the rules in node (stoacore.js): each of the six cards (calm and needing you), the order, old feeds, deals ending, Done / Snooze / changed card, the columns, junk input
  c. Chromium 390 x 844 (and 375 x 667 LITE): DEMO, real files, nothing needs you, Done / Snooze / Bring back kept in localStorage, 3D columns (or the 2D fallback), taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_stoa_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "stoa", "Stoa"
check = AK.check


def test_static():
    # the Kalshi feed is the site's own ../kalshi.json (SITE_FEED); the old kalshi-feed repo is retired (polish2 2026-11-19): no web address at all
    AK.static_kit(APP, NAME, reads=("../home.json", "../money/index.json", "../alerts.json"), storage="ls")
    d = os.path.join(AK.WEB, APP)
    js, core, scene, html = (AK.read(os.path.join(d, n)) for n in ("stoa.js", "stoacore.js", "stoascene.js", "index.html"))
    check("a. the only browser storage is Done / Snooze under one key (stoa.state.v1), wrapped in try / catch", js.count("localStorage.") == 2 and "stoa.state.v1" in js and not re.search(r"sessionStorage|indexedDB", js + core + scene) and js.count("try {") >= 2)
    check("a. the 3D scene is its own optional module loaded by the page, never imported by stoa.js", "stoascene.js" in html and "from './stoascene" not in js and "STOA3D" in js)
    check("a. the scene uses the local three.js only, no bloom, no neon, no network", "../jarvis/three.module.min.js" in scene and not re.search(r"https?://|Bloom|UnrealBloom", scene))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture is a DEMO of every input (home, money, kalshi, alerts) with a 'not real' note", fx["demo"] is True and all(k in fx for k in ("home", "money", "kalshi", "alerts")) and "not real" in fx["note"].lower())
    check("a. the page order: right now, the colonnade, the cards, set aside, all calm", html.index('id="hero"') < html.index('id="sceneCard"') < html.index('id="cards"') < html.index('id="quietCard"') < html.index('id="calmCard"'))
    check("a. Done and Snooze buttons carry a spoken label (aria-label) naming the card", "Mark done:" in js and "Snooze for four hours:" in js)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {}, NOW = Date.parse('2026-11-10T15:00:00Z'), H = 3600000;
  const acct = (name, room, mll, o2) => Object.assign({ id: name, name, eval: { room, mll, dll_used: 0, dll: 1000 }, pnl: { today: 0 }, conn: { connected: true } }, o2 || {});
  const calmHome = { accounts: [acct('Zlarior', 1420, 2000, { pnl: { today: 312 } }), acct('Atlas', 900, 1000)] };
  const stream = (id, st, age, items) => ({ id, name: id, status: st, age_min: age, items: items || [] });
  const calmMoney = { streams: ['chrysos', 'mercury', 'sibyl', 'oikos', 'arbiter'].map((id) => stream(id, 'ok', 10)) };
  const by = (cards, slot) => cards.find((c) => c.slot === slot);
  const calm = C.buildCards({ home: calmHome, money: calmMoney, kalshi: { running: true, today_pnl: 12.4 }, alerts: { alerts: [] } }, NOW);
  o.calm = [calm.length, calm.every((c) => !c.needs), calm.map((c) => c.slot).join(), by(calm, 'drawdown').title, by(calm, 'today').title, by(calm, 'today').say.includes('Kalshi today +$12'), C.split(calm, {}, NOW).open.length, C.headline(C.split(calm, {}, NOW)).title];
  const warn = C.buildCards({ home: { accounts: [acct('Atlas', 440, 1000)] }, money: calmMoney }, NOW), bad = C.buildCards({ home: { accounts: [acct('Atlas', 200, 1000)] }, money: calmMoney }, NOW);
  o.dd = [by(warn, 'drawdown').tone, by(bad, 'drawdown').tone, by(bad, 'drawdown').title, by(bad, 'drawdown').say.startsWith('Stay small'), bad[0].slot, by(bad, 'drawdown').needs];
  const off = C.buildCards({ home: { accounts: [acct('Atlas', 900, 1000, { conn: { connected: false } }), acct('Blitz', 500, 1000, { paused: true })] }, money: calmMoney }, NOW);
  o.bots = [by(off, 'bots').tone, by(off, 'bots').title, by(off, 'bots').say];
  const paused = C.buildCards({ home: { accounts: [acct('Blitz', 900, 1000, { paused: true })] }, money: calmMoney }, NOW), kal = C.buildCards({ home: calmHome, money: calmMoney, kalshi: { running: false } }, NOW);
  o.bots2 = [by(paused, 'bots').title, by(kal, 'bots').title, by(kal, 'bots').tone];
  const dll = C.buildCards({ home: { accounts: [acct('Atlas', 900, 1000, { eval: { room: 900, mll: 1000, dll_used: 500, dll: 600 } })] }, money: calmMoney }, NOW);
  o.today = [by(dll, 'today').tone, by(dll, 'today').title, by(dll, 'today').say.startsWith('Stop for the day')];
  const deal = (extra) => ({ streams: [stream('mercury', 'ok', 10, [Object.assign({ title: 'Sale on the 50K', detail: '', usd: 18, score: 70, risk: 'low' }, extra)])] });
  const dsoon = by(C.buildCards({ home: calmHome, money: deal({ expires: new Date(NOW + 20 * H).toISOString() }) }, NOW), 'deals'), dnorm = by(C.buildCards({ home: calmHome, money: deal({}) }, NOW), 'deals'),
    dgone = by(C.buildCards({ home: calmHome, money: deal({ expires: new Date(NOW - H).toISOString() }) }, NOW), 'deals'), dweak = by(C.buildCards({ home: calmHome, money: deal({ score: 30 }) }, NOW), 'deals'),
    dsamp = by(C.buildCards({ home: calmHome, money: { streams: [Object.assign(deal({}).streams[0], { status: 'sample' })] } }, NOW), 'deals');
  const dated = (d, now) => by(C.buildCards({ home: calmHome, money: deal({ expires: d }) }, now), 'deals'), dchr = by(C.buildCards({ home: calmHome, money: { streams: [Object.assign(stream('chrysos', 'ok', 5, [{ title: 'Next buy', usd: 5439, score: 89, risk: 'low' }]), {})] } }, NOW), 'deals');
  const dA = dated('2026-11-13', Date.parse('2026-11-10T15:00:00Z')), dB = dated('2026-11-13', Date.parse('2026-11-12T15:00:00Z')), dC = dated('2026-11-13', Date.parse('2026-11-14T01:00:00Z'));
  o.dates = [dA.tone, dB.tone, dB.title, dC.needs, dchr.needs, C.expiresMs('2026-11-13') === Date.parse('2026-11-13T23:59:59Z'), C.expiresMs('junk'), C.expiresMs(5), C.expiresMs('2026-11-13T10:00:00Z') === Date.parse('2026-11-13T10:00:00Z')];
  o.deals = [dsoon.tone, dsoon.title, dsoon.say.includes('about $18, an estimate'), dnorm.tone, dnorm.title, dgone.needs, dweak.needs, dsamp.needs, dsoon.stream];
  const feeds = C.buildCards({ home: calmHome, money: { streams: [stream('chrysos', 'stale', 700), stream('mercury', 'ok', 10)] }, kalshi: { running: true, t: (NOW - 50 * H) / 1000 } }, NOW);
  const f0 = by(feeds, 'feeds'), nohome = C.buildCards({ money: calmMoney }, NOW), nomoney = C.buildCards({ home: calmHome }, NOW), oldHome = C.buildCards({ home: Object.assign({ t: (NOW - 60 * H) / 1000 }, calmHome), money: calmMoney }, NOW);
  o.feeds = [f0.tone, f0.title, f0.say.includes('RUN_MONEY.bat'), by(nohome, 'feeds').title, by(nohome, 'bots').title, by(nomoney, 'feeds').title, by(oldHome, 'feeds').title];
  const al = C.buildCards({ home: calmHome, money: calmMoney, alerts: { alerts: [{ text: 'Feed stalled', level: 'bad' }, { text: 'x' }, null, { text: '' }] } }, NOW), al2 = C.buildCards({ home: calmHome, money: calmMoney, alerts: [{ text: 'One' }] }, NOW);
  o.alerts = [by(al, 'alerts').tone, by(al, 'alerts').title, by(al2, 'alerts').tone, by(al2, 'alerts').title];
  const mix = C.buildCards({ home: { accounts: [acct('Atlas', 200, 1000)] }, money: { streams: [stream('mercury', 'ok', 10, [{ title: 'Sale', usd: 5, score: 80, risk: 'low' }])] }, alerts: { alerts: [{ text: 'A' }] } }, NOW);
  o.order = [mix.map((c) => c.tone).join(), mix[0].slot];
  const c0 = by(bad, 'drawdown');
  let st = C.markDone({}, c0.key, NOW);
  o.done = [C.isQuiet(st, c0, NOW + 3 * H), C.isQuiet(st, c0, NOW + 30 * H), C.isQuiet(st, Object.assign({}, c0, { key: 'drawdown:warn' }), NOW), C.split(bad, st, NOW).open.length, C.split(bad, st, NOW).quiet.length, C.headline(C.split(bad, st, NOW)).why];
  st = C.snooze({}, c0.key, NOW);
  o.snooze = [C.isQuiet(st, c0, NOW + 3 * H), C.isQuiet(st, c0, NOW + 5 * H), C.isQuiet(C.clearKey(st, c0.key), c0, NOW), Object.keys(C.cleanState({ a: { done: 1 }, b: 'x', c: { until: 'y' }, d: null })).join()];
  const cols = C.columns(bad, C.markDone({}, 'bots:x', NOW), NOW), cols2 = C.columns(bad, C.markDone({}, c0.key, NOW), NOW);
  o.cols = [cols.map((c) => c.id).join(), cols.filter((c) => c.lit).map((c) => c.id).join(), cols2.filter((c) => c.lit).length, cols[1].tone];
  o.junk = [C.buildCards(null, NOW).length, C.buildCards('x', NaN).length, C.buildCards({ home: 5, money: [], kalshi: 'q', alerts: 7 }, NOW).filter((c) => c.needs).map((c) => c.slot).join(), C.accountsOf({ accounts: [null, 5, { error: 'x' }, {}] }).length, C.ageH({ t: 'zz' }, NOW), C.ageH({ t: NOW / 1000 - 7200 }, NOW), C.money(-1420), C.moneyS(312), C.hoursText(0.2), C.hoursText(20), C.hoursText(72)];
  const card = C.jarvisCard(bad, {}, NOW);
  o.card = [card.name, card.status.level, card.status.label, card.kpis.length, card.kpis[0].value, card.lines.length, Number.isInteger(card.t)];
  console.log(JSON.stringify(o));
});
"""


def test_rules():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node is not installed: rules skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. everything calm: six cards in slot order, none needs you, 'Drawdown left $1,420 of $2,000 max loss (Zlarior)', today with Kalshi, headline 'Nothing needs you now'",
          o["calm"][:2] == [6, True] and o["calm"][2] == "bots,drawdown,today,deals,feeds,alerts" and o["calm"][3] == "Drawdown left $1,420 of $2,000 max loss (Zlarior)" and o["calm"][4].startswith("Today +$312") and o["calm"][5] and o["calm"][6] == 0 and o["calm"][7] == "Nothing needs you now", o["calm"])
    check("b. drawdown: under half left = warn, under a quarter = bad with a plain 'Stay small' sentence, and it sorts first", o["dd"] == ["warn", "bad", "Drawdown left $200 of $1,000 max loss (Atlas)", True, "drawdown", True], o["dd"])
    check("b. bots: a disconnected bot is bad and names the account ('Open NinjaTrader...'); paused is warn; a stopped Kalshi bot is warn", o["bots"][0] == "bad" and o["bots"][1] == "Bot not connected: Atlas" and "NinjaTrader" in o["bots"][2] and o["bots2"] == ["Bot paused: Blitz", "The Kalshi bot is not running", "warn"], (o["bots"], o["bots2"]))
    check("b. today: the daily loss nearly used (83%) is a warning that says stop for the day", o["today"] == ["warn", "Daily loss nearly used: Atlas", True], o["today"])
    check("b. deals: one ending within 48 h is a warning 'Deal ends in 20 h' with the estimate worded; a good one is info; an ended one, a weak one (score < 40... under 60) and an Example one never need you",
          o["deals"] == ["warn", "Deal ends in 20 h: Sale on the 50K", True, "info", "Deal found: Sale on the 50K", False, False, False, "mercury"], o["deals"])
    check("b. the optional item date `expires`: a date alone means the end of that day (UTC); 81 h away = a plain deal (info), 33 h away = 'Deal ends in 33 h' (warn), after it = gone; a high-score item from another stream (Chrysos) is not a deal; junk dates -> none",
          o["dates"] == ["info", "warn", "Deal ends in 33 h: Sale on the 50K", False, False, True, None, None, True], o["dates"])
    check("b. feeds: old money (Chrysos) and an old Kalshi file are named with the RUN_MONEY.bat step; no home.json -> 'account numbers' missing and a bots card saying so; no money -> 'money data'; a 60 h old home.json is old",
          o["feeds"][0] == "warn" and "money: chrysos" in o["feeds"][1] and "Kalshi (2 days old)" in o["feeds"][1] and o["feeds"][2] and o["feeds"][3] == "Old or missing: account numbers" and o["feeds"][4] == "Account numbers are missing" and o["feeds"][5] == "Old or missing: money data" and "account numbers (3 days old)" in o["feeds"][6], o["feeds"])
    check("b. alerts: junk rows are dropped; a bad one makes the card bad; a plain list also works", o["alerts"] == ["bad", "2 alerts: Feed stalled", "warn", "1 alert: One"], o["alerts"])
    check("b. order: bad first, then warn, then info (the cards that need you come before the calm ones)", o["order"][0].startswith("bad") and o["order"][1] == "drawdown", o["order"])
    check("b. Done hides a card for the rest of today only (not tomorrow), a changed card (new key) comes back at once, the headline says how many are set aside", o["done"][:5] == [True, False, False, 0, 1], o["done"])
    check("b. Snooze lasts 4 hours, Bring back clears it, bad saved state is cleaned to the valid rows only", o["snooze"] == [True, False, False, "a"], o["snooze"])
    check("b. the six columns follow the slots; the lit one is the card that needs you; Done puts it out; a Done on another card changes nothing", o["cols"] == ["bots,drawdown,today,deals,feeds,alerts", "drawdown", 0, "bad"], o["cols"])
    check("b. junk never throws: null / text / NaN inputs give six cards, nothing needing you but the missing-feed cards; bad accounts dropped; ages and money words", o["junk"][:2] == [6, 6] and o["junk"][2] == "bots,feeds" and o["junk"][3] == 1 and o["junk"][4] is None and abs(o["junk"][5] - 2) < 0.01 and o["junk"][6:] == ["-$1,420", "+$312", "under an hour", "20 h", "3 days"], o["junk"])
    check("b. the Jarvis card: Stoa, level bad, '1 need you', 3 kpis, <= 3 lines, integer t", o["card"][:5] == ["Stoa", "bad", "1 need you", 3, "1"] and o["card"][5] == 1 and o["card"][6], o["card"])


def home_json(room=900, conn=True):
    return json.dumps({"accounts": [{"id": "acctb", "name": "Atlas 25K", "eval": {"room": room, "mll": 1000, "dll_used": 0, "dll": 600}, "pnl": {"today": 40}, "conn": {"connected": conn}}]})


MONEY_OK = json.dumps({"streams": [{"id": i, "name": i.title(), "status": "ok", "age_min": 10, "items": []} for i in ("chrysos", "mercury", "sibyl", "oikos", "arbiter")]})


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
            AK.open_app(p, origin, APP, "?demo=1&flat=1")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, title: document.querySelector('#heroTitle').textContent, pill: document.querySelector('#heroPill').textContent,
              needs: [...document.querySelectorAll('#cards .need h3')].map((h) => h.textContent), btns: [...document.querySelectorAll('#cards .need button')].map((b) => b.textContent),
              calm: document.querySelectorAll('#calm li').length, cols: document.querySelectorAll('#fallback rect').length, scene: window.STOA.S.scene, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
              lit: window.STOA.S.cols.filter((c) => c.lit).map((c) => c.id) })""")
            check("c. DEMO (the fixture): the chip, '3 things need you' (drawdown, the ending deal, the old feed), each with Done and Snooze 4 h, three calm rows, the 2D columns drawn",
                  d["demo"] and d["title"] == "3 things need you" and d["pill"] == "Look once" and len(d["needs"]) == 3 and d["needs"][0].startswith("Drawdown left $440 of $1,000") and any(n.startswith("Deal ends in") for n in d["needs"]) and any(n.startswith("Old or missing") for n in d["needs"])
                  and d["btns"] == ["Done", "Snooze 4 h"] * 3 and d["calm"] == 3 and d["cols"] >= 25 and d["scene"] == "2d" and d["lit"] == ["drawdown", "deals", "feeds"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "stoa-demo")
            p.locator("#cards .need").first.locator("button", has_text="Done").click()
            p.wait_for_timeout(150)
            a = p.evaluate("""() => ({ title: document.querySelector('#heroTitle').textContent, n: document.querySelectorAll('#cards .need').length, quiet: !document.querySelector('#quietCard').hidden, q: document.querySelectorAll('#quiet li').length,
              saved: Object.keys(JSON.parse(localStorage.getItem('stoa.state.v1') || '{}')), lit: window.STOA.S.cols.filter((c) => c.lit).length, st: document.querySelector('#status').textContent })""")
            check("c. tap Done on the first card: 2 things need you, the card moves to 'Set aside', one column goes dark, the choice is saved on the phone, the status line is spoken",
                  a["title"] == "2 things need you" and a["n"] == 2 and a["quiet"] and a["q"] == 1 and len(a["saved"]) == 1 and a["lit"] == 2 and "Done" in a["st"], a)
            p.locator("#cards .need").first.locator("button", has_text="Snooze").click()
            p.wait_for_timeout(150)
            b = p.evaluate("() => [document.querySelector('#heroTitle').textContent, document.querySelectorAll('#quiet li').length, Object.values(JSON.parse(localStorage.getItem('stoa.state.v1'))).some((v) => v.until)]")
            check("c. tap Snooze 4 h on the next one: 'One thing needs you', two set aside, the snooze is saved with its end time", b == ["One thing needs you", 2, True], b)
            p.reload()
            p.wait_for_function("window.STOA && window.STOA.ready()", timeout=60000)
            r = p.evaluate("() => [document.querySelector('#heroTitle').textContent, document.querySelectorAll('#quiet li').length]")
            check("c. after a reload the choices are remembered (still 'One thing needs you', two set aside)", r == ["One thing needs you", 2], r)
            p.locator("#quiet li button").first.click()
            p.wait_for_timeout(150)
            q = p.evaluate("() => [document.querySelector('#heroTitle').textContent, document.querySelectorAll('#quiet li').length]")
            check("c. Bring back returns a card ('2 things need you', one still set aside)", q == ["2 things need you", 1], q)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (Done, Snooze, Bring back)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # real files, all calm
            srv2, origin2 = AK.serve({"/home.json": home_json(), "/money/index.json": MONEY_OK, "/alerts.json": json.dumps({"alerts": []})})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?flat=1")
            c = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, title: document.querySelector('#heroTitle').textContent, pill: document.querySelector('#heroPill').textContent, need: document.querySelectorAll('#cards .need').length, calm: document.querySelectorAll('#calm li').length, note: document.querySelector('#sceneNote').textContent, card: document.querySelector('#cards').textContent })")
            check("c. real files, all fine: no DEMO chip, 'Nothing needs you now', All calm, no Done buttons, six calm rows, 'No column is lit', a plain 'Nothing to do' card (never blank)",
                  not c["demo"] and c["title"] == "Nothing needs you now" and c["pill"] == "All calm" and c["need"] == 0 and c["calm"] == 6 and "No column is lit" in c["note"] and "Nothing to do" in c["card"], c)
            check("c. it read the site's own files and no console error", any("home.json" in u for u in seen) and any("money/index.json" in u for u in seen) and not errs, (errs[:3],))
            ctx.close()
            srv2.shutdown()
            # the REAL scanners' output
            import tempfile
            sys.path.insert(0, os.path.join(AK.ROOT, "tools"))
            import money_engine as ME
            real_out = tempfile.mkdtemp(prefix="stoa-real-")
            ME.run(real_out, True, 120, quiet=True)
            srv5, origin5 = AK.serve({"/home.json": home_json(), "/money/index.json": open(os.path.join(real_out, "index.json"), encoding="utf-8").read()})
            ctx, p, errs, seen, off = AK.page(br, origin5)
            AK.open_app(p, origin5, APP, "?flat=1")
            z = p.evaluate("() => [document.querySelector('#heroTitle').textContent, document.querySelectorAll('#cards .need').length, !document.querySelector('#demo').hidden]")
            check("c. the real scanners' index (all Example): nothing needs you (a sample deal never lights a column), no DEMO chip, no console error", z == ["Nothing needs you now", 0, False] and not errs, (z, errs[:2]))
            ctx.close()
            srv5.shutdown()
            # a disconnected bot
            srv3, origin3 = AK.serve({"/home.json": home_json(room=150, conn=False), "/money/index.json": MONEY_OK})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?flat=1")
            e = p.evaluate("() => [document.querySelector('#heroTitle').textContent, document.querySelector('#heroPill').textContent, [...document.querySelectorAll('#cards .need h3')].map((h) => h.textContent)]")
            check("c. a bot that is not connected and 15% drawdown left: '2 things need you', 'Be careful', both cards named", e[0] == "2 things need you" and e[1] == "Be careful" and any(x.startswith("Bot not connected") for x in e[2]) and any(x.startswith("Drawdown left $150") for x in e[2]), e)
            ctx.close()
            srv3.shutdown()
            # the 3D columns
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            p.wait_for_timeout(2500)
            w = p.evaluate("() => ({ scene: window.STOA.S.scene, three: !document.querySelector('#scene3d').hidden, canvas: !!document.querySelector('#scene3d canvas'), frames: window.STOA3D ? window.STOA3D.frames() : -1, lit: window.STOA3D ? window.STOA3D.lit() : [], svg: getComputedStyle(document.querySelector('#fallback')).visibility })")
            if w["scene"] == "webgl":
                check("c. 3D: a canvas draws frames, six columns, the lit ones are Drawdown, Deals and Feeds; the 2D picture steps aside", w["three"] and w["canvas"] and w["frames"] > 1 and w["lit"] == [0, 1, 0, 1, 1, 0], w)
                AK.shot(p, "stoa-3d")
            else:
                check("c. 3D not available in this browser: the 2D columns stay (never blank)", w["scene"] == "2d" and not w["three"] and w["svg"] == "visible", w)
            check("c. no console error with the 3D module loaded", not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            s = p.evaluate("() => [window.STOA.S.scene, !document.querySelector('#lite').hidden]")
            check("c. 375 x 667, LITE, reduced motion: 2D columns only, LITE chip, no sideways scroll, every tap >= 44 px, no error", s[0] == "2d" and AK.no_sideways(p) and not AK.taps(p) and not errs, (s, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_rules()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
