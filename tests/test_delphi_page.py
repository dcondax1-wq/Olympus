"""DELPHI, the OLYMPUS oracle's briefing (tools/web_public/delphi/, AGORA look, 2026-11-10): the calm pre-session page: the verdict, a five-line go / no-go checklist, what LIT / ATLAS / BLITZ plan, the VIX-band target, stop and size, news windows.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture
  b. the words and checks in node (delphicore.js): reading home.json safely, the VIX band, every checklist case, the verdict, the plain-language rules
  c. Chromium 390 x 844 (and 375 x 667): the DEMO briefing, the bot cards, the real home.json (fresh, stale, no briefing), LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_delphi_page            (--static: parts a and b only)
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "delphi", "Delphi"
check = AK.check
FIX = os.path.join(AK.WEB, APP, "fixture.json")
AT = "2026-11-10T12:20:00Z"
BUILT = int(dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc).timestamp())


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../ledger/rules.json"))
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page order: the verdict, the checklist, the bots, the target, the size, the news", html.index('id="answer"') < html.index('id="checkCard"') < html.index('id="planCard"') < html.index('id="vixCard"') < html.index('id="sizeCard"') < html.index('id="newsCard"'))
    fx = json.load(open(FIX, encoding="utf-8"))
    b = fx["home"]["live"]["brief"]
    check("a. the fixture is a whole briefing (band, two news events, size, account) so the DEMO is never blank", b["vix"]["low"] < b["vix"]["high"] and len(b["news"]) == 2 and b["eval"]["max_micros"] == 20 and fx["home"]["accounts"][0]["eval"]["room"] == 1420)


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const o = {}, fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), home = fx.home, now = new Date('2026-11-10T12:20:00Z');
  const built = Date.parse('2026-11-10T12:00:00Z') / 1000;
  const real = (mut) => { const x = JSON.parse(JSON.stringify(home)); x.live.brief.built_t = built; if (mut) mut(x); return x; };
  o.words = [C.money(2000), C.moneyS(-838), C.px(23888.3), C.pts(261.68), C.drawdownLine(1420, 2000), C.etDay(new Date('2026-11-10T03:00:00Z')), C.etDay(now), C.px(null)];
  const m = C.readHome(real(), null);
  o.read = [m.has, m.day, m.vix.low, m.vix.high, m.vix.move, m.room, m.mll, m.news.length, m.news[0].time, m.size.micros, m.size.risk, m.size.stop, m.accountName, m.builtT];
  const m2 = C.readHome({ live: { brief: { vix: { vix: 17.2, open18: 24150 } } } }, null);
  o.derive = [m2.vix.move, m2.vix.low, m2.vix.high, m2.vix.has];
  o.junk = [C.readHome(null, null).has, C.readHome('x', 5).has, C.readHome({ live: 'x' }, null).room, C.readHome({ live: { brief: { vix: { vix: 'abc' }, news: ['x', null, { title: 'A', time: '09:00' }], eval: { why: 'x' } } } }, null).news.length,
    C.readHome({ live: { brief: { vix: { vix: 'abc' } } } }, null).vix.has, C.readHome({}, { limits: { builder_50k: { mll: 2500 } } }).mll, C.readHome({}, { limits: { builder_50k: { mll: -1 } } }).mll];
  const L = C.vixLines(m), Ls = C.sizeLines(m), Ln = C.vixLines(C.readHome({ live: { brief: { vix: { vix: 'abc' } } } }, null));
  o.vixLines = [L.length, L[0], L[1], L[2], Ln.length, Ln[0]];
  o.sizeLines = [Ls.length, Ls[2], C.sizeLines(C.readHome({ live: { brief: {} } }, null))[2]];
  const lit = C.litLines(m), litNoPlan = C.litLines(C.readHome({ live: { brief: { day: 'x' } } }, null)), atl = C.atlasLines(), bl = C.blitzLines();
  o.bots = [lit.length, lit[0].startsWith('Today: A sweep of the Asia high'), lit[2].includes('02:00 to 15:30') && lit[2].includes('Flat by 15:55'), lit[3].includes('banked at 8R') && lit[3].includes('after 15 minutes'), litNoPlan[0].startsWith('LIT hunts liquidity'), atl.length, atl[1].includes('PAPER'), bl.length, bl[2].includes('-3R') && bl[2].includes('about -$360'), bl[0].includes('11:00')];
  const lv = (mut, dm, at) => C.checklist(C.readHome(real(mut), null), at || now, !!dm);
  const keys = (l) => l.map((x) => x.key).join(',');
  const lvl = (l) => l.map((x) => x.level).join(',');
  const demoL = lv(null, true), freshL = lv(null, false);
  o.list = [keys(demoL), lvl(demoL), lvl(freshL), freshL[0].text, freshL[3].text.startsWith('2 high-impact events: Core PCE Price Index 08:30, FOMC Minutes 14:00.'), freshL[2].text, freshL[4].text, freshL[1].text];
  o.stale = [lv(null, false, new Date('2026-11-10T16:00:00Z'))[0].level, lv(null, false, new Date('2026-11-10T16:00:00Z'))[0].text.includes('4 hours old'), lv(null, false, new Date('2026-11-10T13:00:00Z'))[0].text.includes('60 minutes') || lv(null, false, new Date('2026-11-10T13:00:00Z'))[0].level];
  o.otherDay = [lv((x) => { x.live.brief.day = '2026-11-09'; }, false)[0].level, lv((x) => { x.live.brief.day = '2026-11-09'; }, false)[0].text.includes('from 2026-11-09, not today (2026-11-10)')];
  const roomL = (r) => lv((x) => { x.accounts[0].eval.room = r; }, false)[2];
  o.room = [roomL(400).level, roomL(800).level, roomL(1000).level, roomL(1400).level, roomL(400).text.startsWith('Drawdown left $400 of $2,000 max loss.'), roomL(400).text.includes('Very close')];
  o.zero = [lv((x) => { x.live.brief.eval.max_micros = 0; }, false)[4].level, lv((x) => { delete x.live.brief.eval; }, false)[4].level];
  o.noBand = [lv((x) => { delete x.live.brief.vix; }, false)[1].level, lv((x) => { delete x.live.brief.vix; }, false)[1].text];
  o.noNews = [lv((x) => { x.live.brief.news = []; }, false)[3].level, lv((x) => { x.live.brief.news = []; }, false)[3].text];
  const none = C.checklist(C.readHome(null, null), now, false);
  o.none = [lvl(none), none[0].text.startsWith('No briefing published yet'), none[2].level];
  const v1 = C.verdict(freshL, false), v2 = C.verdict(demoL, true), v3 = C.verdict(none, false), v4 = C.verdict(lv((x) => { x.live.brief.news = []; }, false), false);
  o.verdict = [[v1.level, v1.word, v1.ok, v1.total, v1.why], [v2.level, v2.word, v2.why.endsWith('(example data)')], [v3.level, v3.word, v3.why.includes('fresh data') && v3.why.includes('target band known')], [v4.level, v4.word, v4.why, v4.doit], v1.doit];
  const card = C.jarvisCard(freshL, v1);
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.lines[0].length < 119, Number.isInteger(card.t), JSON.stringify(card).length < 8192];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, FIX)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: dollars, signed dollars, prices with cents, points to a tenth, the exact drawdown sentence, the New York day (03:00 UTC is still the day before), null -> n/a",
          o["words"] == ["$2,000", "-$838", "23,888.30", "261.7", "Drawdown left $1,420 of $2,000 max loss", "2026-11-09", "2026-11-10", "n/a"], o["words"])
    check("b. reading home.json: the briefing day, the band 23,888.3 / 24,411.7 (move 261.7), the account's $1,420 of $2,000, two news events, 20 micros, $838 risk, a 20-pt stop, the account name, built_t",
          o["read"] == [True, "2026-11-10", 23888.3, 24411.7, 261.7, 1420, 2000, 2, "08:30", 20, 838, 20, "Zlarior 50K", BUILT], o["read"])
    check("b. no band given -> it is derived from VIX 17.2 and the 18:00 open 24,150: 261.7 pts, 23,888.3 / 24,411.7", o["derive"] == [261.7, 23888.3, 24411.7, True], o["derive"])
    check("b. junk never throws: null / string / wrong types give 'no briefing', no room, a bad news list keeps only the good row, a bad VIX gives no band, rules.json overrides a good max loss only",
          o["junk"] == [False, False, None, 1, False, 2500, 2000], o["junk"])
    v = o["vixLines"]
    check("b. the target words: the VIX move formula with its numbers and $523 a micro; shorts / longs aim at the band; banked at 8R with the dollars (+$6,704 when 1R is $838); skipped under 1.5R; no band says 'No band, no trade'",
          v[0] == 3 and "= 17.20 / 100 / 15.87 x 24,150.00 = 261.7 points ($523 per micro)" in v[1] and v[2].startswith("Shorts aim at 23,888.30, longs at 24,411.70") and "8R is +$6,704 when 1R is $838" in v[2]
          and "closer than 1.5R" in v[3] and v[4] == 1 and "No band, no trade" in v[5], v)
    s = o["sizeLines"]
    check("b. the size words: stop beyond the sweep, size follows the stop, '20 micros, $838 at risk (1R = $838); a stop-out is -$838 (-1.0R)'; missing size says so and never invents one",
          s[0] == 3 and s[1] == "Today at a typical 20-point stop: 20 micros, $838 at risk (1R = $838); a stop-out is -$838 (-1.0R)." and "not reported yet" in s[2], s)
    b = o["bots"]
    check("b. the bots in plain words: LIT (today's plan first, entries 02:00 to 15:30, flat by 15:55, banked at 8R, cut after 15 minutes), ATLAS (paper), BLITZ (11:00 checks, -3R about -$360)", b == [4, True, True, True, True, 3, True, 4, True, True], b)
    li = o["list"]
    check("b. the checklist has five lines in order (data, band, room, news, size); the demo shows 'info' for data; a fresh live briefing is all ok but the news (warn); the words are the real numbers",
          li[0] == "data,band,room,news,size" and li[1] == "info,ok,ok,warn,ok" and li[2] == "ok,ok,ok,warn,ok" and li[3] == "Updated 20 minutes ago, for 2026-11-10." and li[4] and li[5].startswith("Drawdown left $1,420 of $2,000 max loss. A safe distance.") and li[6].startswith("20 micros at a typical 20-point stop, $838 at risk (1R)") and li[7].startswith("Shorts 23,888.30, longs 24,411.70"), li)
    check("b. stale data: 4 hours old -> warn with the words; a briefing of another day -> warn that names both days", o["stale"][:2] == ["warn", True] and o["otherDay"] == ["warn", True], (o["stale"], o["otherDay"]))
    check("b. drawdown left levels: $400 of $2,000 bad (very close), $800 warn, $1,000 and $1,400 ok", o["room"] == ["bad", "warn", "ok", "ok", True, True], o["room"])
    check("b. size 0 -> bad (no room to trade); size missing -> warn; no band -> bad 'No VIX band today, so no trade'; no news -> ok 'No high-impact USD news today.'",
          o["zero"] == ["bad", "warn"] and o["noBand"] == ["bad", "No VIX band today, so no trade. The bot waits."] and o["noNews"] == ["ok", "No high-impact USD news today."], (o["zero"], o["noBand"], o["noNews"]))
    check("b. nothing published at all: five lines still, data bad ('No briefing published yet'), drawdown warn, never blank", o["none"] == ["bad,bad,warn,warn,warn", True, "warn"], o["none"])
    vd = o["verdict"]
    check("b. the verdict: one warn -> 'Go, with care' (4 of 5 in order, names the news); demo says '(example data)'; no briefing -> 'Stand down' naming the lines; all ok -> 'Go' and 'Nothing to change.'",
          vd[0][:4] == ["warn", "Go, with care", 4, 5] and vd[0][4] == "news windows need a look." and vd[1] == ["warn", "Go, with care", True] and vd[2] == ["bad", "Stand down", True]
          and vd[3] == ["ok", "Go", "Every line of the checklist is in order.", "Let the bot trade its plan. Nothing to change."] and "read the lines marked Look" in vd[4], vd)
    check("b. the Jarvis card: Delphi, a level, 2 kpis, one short line, an integer t, under 8 KB", o["card"] == ["Delphi", "warn", 2, "4 of 5 ok", True, True, True], o["card"])


def home_json(mut=None, built=BUILT):
    h = copy.deepcopy(json.load(open(FIX, encoding="utf-8"))["home"])
    h["live"]["brief"]["built_t"] = built
    if mut:
        mut(h)
    return json.dumps(h)


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
            AK.open_app(p, origin, APP, "?demo=1&at=" + AT)
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, h: document.querySelector('#ansH').textContent, why: document.querySelector('#ansWhy').textContent, doit: document.querySelector('#ansDo').textContent,
              pill: document.querySelector('#ansPill').textContent, day: document.querySelector('#day').textContent, items: [...document.querySelectorAll('#check li')].map((li) => li.dataset.level + ':' + li.querySelector('b').textContent),
              bots: [...document.querySelectorAll('#bots details')].map((x) => x.dataset.bot + (x.open ? '*' : '')), vix: document.querySelector('#vixTiles').textContent, vixn: document.querySelectorAll('#vixLines li').length,
              size: document.querySelector('#sizeTiles').textContent, news: [...document.querySelectorAll('#news li')].map((li) => li.querySelector('time').textContent), status: document.querySelector('#status').textContent,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor })""")
            check("c. DEMO: the chip, 'Go, with care', '3 of 5 lines in order', five checklist lines (data info, band ok, drawdown ok, news warn, size ok), the briefing day, the status line is spoken",
                  d["demo"] and d["h"] == "Go, with care" and d["pill"] == "3 of 5 lines in order" and d["items"] == ["info:Fresh data", "ok:Target band known", "ok:Drawdown left", "warn:News windows", "ok:Size set"] and d["day"] == "Briefing for 2026-11-10" and "Go, with care" in d["status"]
                  and "example data" in d["why"], d)
            check("c. the bots (LIT open, ATLAS and BLITZ closed), the VIX band (23,888.30 / 24,411.70, 261.7 pts, $523 per micro), the size (20 micros, -$838 with -1.0R, +$6,704 with +8.0R), the two news times",
                  d["bots"] == ["lit*", "atlas", "blitz"] and "23,888.30" in d["vix"] and "24,411.70" in d["vix"] and "261.7 pts" in d["vix"] and "$523 per micro" in d["vix"] and d["vixn"] == 3
                  and "20 pts" in d["size"] and "-$838" in d["size"] and "-1.0R" in d["size"] and "+$6,704" in d["size"] and "+8.0R" in d["size"] and d["news"] == ["08:30", "14:00"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "delphi-demo")
            p.locator("#bots [data-bot=blitz] summary").click()
            p.wait_for_timeout(150)
            b = p.evaluate("() => [document.querySelector('#bots [data-bot=blitz]').open, document.querySelector('#bots [data-bot=blitz]').textContent.includes('-3R')]")
            check("c. tap BLITZ: the card opens and tells the -3R day stop with its dollars", b == [True, True], b)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (the bot cards, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            srv2, origin2 = AK.serve({"/home.json": home_json(lambda h: h["live"]["brief"].update(news=[]))})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=" + AT)
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, h: document.querySelector('#ansH').textContent, pill: document.querySelector('#ansPill').textContent, cls: document.querySelector('#ansH').className,
              items: [...document.querySelectorAll('#check li')].map((li) => li.dataset.level), news: document.querySelector('#news').textContent, data: document.querySelector('#check li').textContent })""")
            check("c. the real home.json, 20 minutes old, no news: no DEMO chip, 'Go', 5 of 5 lines in order, 'Updated 20 minutes ago', 'No high-impact USD news today.'",
                  not r["demo"] and r["h"] == "Go" and r["pill"] == "5 of 5 lines in order" and set(r["items"]) == {"ok"} and "Updated 20 minutes ago" in r["data"] and "No high-impact USD news today." in r["news"] and "pos" in r["cls"], r)
            check("c. the real run reads only the site's files and no console error", any("home.json" in u for u in seen) and any("rules.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/home.json": home_json(lambda h: h["live"]["brief"].pop("vix"))})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?at=" + AT)
            n = p.evaluate("() => [document.querySelector('#ansH').textContent, document.querySelector('#ansWhy').textContent, document.querySelector('#ansPill').className, document.querySelector('#vixTiles').textContent, document.querySelector('#vixLines').textContent]")
            check("c. no VIX band: 'Stand down', the reason names the target band, the target card says 'None today' and 'no band, no trade' (never blank)", n[0] == "Stand down" and "target band known" in n[1] and "bad" in n[2] and "None today" in n[3] and "No band, no trade" in n[4], n)
            ctx.close()
            srv3.shutdown()
            srv4, origin4 = AK.serve({"/home.json": json.dumps({"accounts": []})})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "?at=" + AT)
            e = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#ansH').textContent]")
            check("c. a home.json with no briefing falls back to the DEMO (chip on, never blank)", e == [True, "Go, with care"] and not errs, (e, errs[:2]))
            ctx.close()
            srv4.shutdown()
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
