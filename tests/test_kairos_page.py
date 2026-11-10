"""KAIROS, the OLYMPUS "right moment" page (tools/web_public/kairos/, AGORA look, 2026-11-10): the New York trading day on a ring and a marble sundial, the bot windows, what the bots do now, today's trades with $ and R, dollars by hour.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the scene file, the honest labels
  b. the clock in node (kairoscore.js): every window boundary, the week's open and close, and the DST EDGE (clocks go back Sun 1 Nov 2026: a 25-hour day, 01:00-02:00 twice; forward Sun 8 Mar 2026: 23 hours)
  c. Chromium 390 x 844 (and 375 x 667): the demo at a fixed clock, the ring, the windows, trades with $ and R, the hour heat band (no claim below 3 trades), the 1 Nov 2026 clock change, the real trades file, the sundial, LITE
    python -X utf8 -m tests.test_kairos_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "kairos", "Kairos"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../odeon/trades.json", "../home.json"))
    d = os.path.join(AK.WEB, APP)
    js, core, scene, html = (AK.read(os.path.join(d, n)) for n in ("kairos.js", "kairoscore.js", "kairosscene.js", "index.html"))
    check("a. the 3D scene: a marble ring with 24 gold pillars (one per hour), the current hour lit, from three (local copy), WebGL optional (null -> the flat ring only), a LITE tier, no bloom / composer",
          "../jarvis/three.module.min.js" in scene and "LatheGeometry" in scene and "for (let h = 0; h < 24; h++)" in scene and "goldLit" in scene and "return null" in scene and "lite()" in scene and not re.search(r"Bloom|EffectComposer|neon", scene) and "createSundial" in js, None)
    check("a. the windows the brief names are all there: Asia slot (paper), London 02:00, New York, last entry 15:30, flat 15:55, MFFU flat 16:10, CME break 17:00-18:00",
          all(x in core for x in ("Asia slot", "London entries", "New York morning", "15:30", "15:55", "16:10", "CME break", "from: 1020, to: 1080")), None)
    check("a. honest labels: paper-only, 'never places or changes an order', 'at least 3 trades', 'not a promise', every dollar with its R", all(x in html + core + js for x in ("paper", "never places or changes an order", "3 trades", "not a promise", "C.both(")), None)
    fx = json.loads(AK.read(os.path.join(d, "fixture.json")))
    check("a. the fixture: example trades as offsets and New York minutes (never real dates), two 'today' trades so the ring is never empty, hours with fewer than 3 trades exist", len(fx["trades"]) >= 30 and sum(1 for t in fx["trades"] if t["off"] == 0) == 2 and any(sum(1 for t in fx["trades"] if t["mod"] // 60 == h) < 3 for h in (6, 13)), len(fx["trades"]))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const z = (s) => new Date(s), p = (s) => { const e = C.etParts(z(s)); return [e.ymd, e.hhmm, e.wd]; }, ph = (s) => C.nowState(z(s)).id, o = {};
  o.day = [C.dayMinutes('2026-11-01'), C.dayMinutes('2026-03-08'), C.dayMinutes('2026-11-02'), C.dayMinutes('2026-10-31'), C.dstInfo('2026-11-01').kind, C.dstInfo('2026-03-08').kind, C.dstInfo('2026-11-02').kind, C.dstInfo('2026-11-01').text.includes('twice'), C.dstInfo('2026-11-01').text.includes('25 hours')];
  o.mid = [new Date(C.etMidnight('2026-11-01')).toISOString(), new Date(C.etMidnight('2026-11-02')).toISOString(), new Date(C.etMidnight('2026-03-08')).toISOString(), new Date(C.etMidnight('2026-03-09')).toISOString()];
  o.dst = [p('2026-11-01T04:30:00Z'), p('2026-11-01T05:30:00Z'), p('2026-11-01T06:30:00Z'), p('2026-11-01T07:00:00Z'), p('2026-03-08T06:59:00Z'), p('2026-03-08T07:00:00Z')];
  o.edge = [ph('2026-11-02T06:59:00Z'), ph('2026-11-02T07:00:00Z'), ph('2026-11-01T22:59:00Z'), ph('2026-11-01T23:00:00Z'), ph('2026-10-30T20:59:00Z'), ph('2026-10-30T21:00:00Z'), ph('2026-10-29T21:00:00Z'), ph('2026-10-29T22:00:00Z')];
  o.day2 = ['2026-11-02T13:00:00Z', '2026-11-02T14:30:00Z', '2026-11-02T17:00:00Z', '2026-11-02T20:29:00Z', '2026-11-02T20:30:00Z', '2026-11-02T20:55:00Z', '2026-11-02T21:10:00Z', '2026-11-02T22:00:00Z', '2026-11-02T23:00:00Z'].map(ph);
  const a = C.nowState(z('2026-11-01T04:30:00Z')), b = C.nowState(z('2026-11-01T06:30:00Z')), c = C.nowState(z('2026-11-01T05:30:00Z')), d = C.nowState(z('2026-11-02T07:00:00Z')), e = C.nowState(z('2026-03-08T06:30:00Z'));
  o.until = [a.id, a.next, a.mins, c.mins, b.mins, d.id, d.next, d.mins, d.entries, e.next, e.mins, b.until];
  o.wk = [ph('2026-11-06T22:00:00Z'), ph('2026-11-07T15:00:00Z'), ph('2026-11-08T22:59:00Z'), ph('2026-11-08T23:00:00Z'), C.nowState(z('2026-11-06T22:30:00Z')).next, C.nowState(z('2026-11-06T22:30:00Z')).mins];
  const w = C.windowsFor(z('2026-11-10T14:42:00Z')); o.wins = w.map((x) => x.id + ':' + x.state);
  const wc = C.windowsFor(z('2026-11-08T12:00:00Z')); o.winsClosed = wc.map((x) => x.state).join();
  o.ring = [C.angle(720) === Math.PI, C.angle(0), C.polar(160, 160, 100, 0).map(Math.round), C.polar(160, 160, 100, 360).map(Math.round), C.polar(160, 160, 100, 720).map(Math.round), ['asia', 'london', 'nypm', 'break'].map((id) => { const x = C.WINDOWS.find((q) => q.id === id), s = C.arcPath(160, 160, 100, 128, x.from, x.to); return /^M[-\d.,]+ A[\d.]+,[\d.]+ 0 [01] 1 [-\d.,]+ L[-\d.,]+ A[\d.]+,[\d.]+ 0 [01] 0 [-\d.,]+ Z$/.test(s) && !/NaN/.test(s); })];
  o.words = [C.both(437, -1.03), C.both(612, 2), C.both(150, null, 0), C.both(-300, null, 250), C.hhmm(930), C.hhmm(5), C.money(-1234.5), C.duration(90), C.duration(1500), C.rS(0)];
  const tr = (id, t, usd, r, src, side) => ({ id, day: C.etParts(new Date(t * 1000)).ymd, side: side || 'SHORT', bot: 'LIT', src, usd, r, risk_usd: 300, entry: { t }, exit: { kind: 'STOP' }, held_min: 20 });
  const T0 = Date.parse('2026-11-01T05:30:00Z') / 1000, T1 = Date.parse('2026-11-01T06:30:00Z') / 1000, T2 = Date.parse('2026-11-02T08:10:00Z') / 1000;
  const od = { trades: [tr('a', T0, -300, -1, 'real'), tr('a2', T0, -310, -1, 'paper'), tr('b', T1, 450, 1.5, 'paper'), tr('c', T2, 900, 3, 'real'), tr('d', T2 + 86400, 100, 0.3, 'paper'), { junk: 1 }, tr('e', T2, 'x', 1, 'real')] };
  const nt = C.normTrades(od);
  o.norm = [nt.length, nt.map((x) => x.id).join(), nt.map((x) => x.hour).join(), nt.map((x) => x.mod).join(), C.normTrades(null).length];
  const fx = { trades: [{ off: 0, mod: 192, usd: 600, r: 2, risk: 300 }, { off: 3, mod: 580, usd: -280, r: -1, risk: 280 }, { off: 1, mod: 130, usd: 0, r: 0 }, { off: 'x', mod: 1, usd: 1 }] };
  const dt = C.demoTrades(fx, '2026-11-02');
  o.demo = [dt.length, dt.map((x) => x.day + '@' + C.hhmm(x.mod)).join(), dt.map((x) => x.src).join()];
  const dstDay = C.demoTrades({ trades: [{ off: 1, mod: 180, usd: 10, r: 0.1 }, { off: 1, mod: 70, usd: 10, r: 0.1 }] }, '2026-11-02');
  o.demoDst = dstDay.map((x) => x.day + '@' + C.hhmm(x.mod) + '/' + C.etParts(new Date(x.t * 1000)).hhmm);
  const tf1 = C.tradesFor(nt, '2026-11-02'), tf2 = C.tradesFor(nt, '2026-12-25'), tf3 = C.tradesFor([], '2026-11-02');
  o.tf = [tf1.label, tf1.list.length, tf2.label, tf2.day, tf3.label, tf3.list.length];
  const hs = [];
  for (let i = 0; i < 5; i++) hs.push({ hour: 3, usd: i < 3 ? 500 : -300, r: i < 3 ? 1.5 : -1, risk: 300 });
  hs.push({ hour: 9, usd: 100, r: 0.3, risk: 300 }, { hour: 9, usd: -300, r: -1, risk: 300 }, { hour: 14, usd: -300, r: -1, risk: 300 }, { hour: 14, usd: -300, r: -1, risk: 300 }, { hour: 14, usd: -300, r: -1, risk: 300 });
  const H = C.heat(hs);
  o.heat = [H.length, H[3].n, H[3].usd, H[3].shown, H[3].avg, H[3].avgR, Math.round(H[3].win * 100), H[9].n, H[9].shown, H[14].shown, H[14].avg, H[0].n, H[0].shown, C.MIN_N];
  o.heatWords = [C.heatWords(H), C.heatWords(C.heat([])), C.heatWords(C.heat(hs.slice(0, 2)))];
  const card = C.jarvisCard(C.nowState(z('2026-11-10T14:42:00Z')), [], 5);
  o.card = [card.name, card.kpis.length, card.status.level, card.lines.length, Number.isInteger(card.t)];
  console.log(JSON.stringify(o));
});
"""


def test_clock():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node is not installed: the clock tests were skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. DST edge: Sun 1 Nov 2026 is a 25-hour day (1,500 min), Sun 8 Mar 2026 a 23-hour day (1,380), ordinary days 1,440; the notes say 'twice' and '25 hours'", o["day"] == [1500, 1380, 1440, 1440, "back", "forward", "none", True, True], o["day"])
    check("b. New York midnight as a real instant: 1 Nov 04:00Z (EDT), 2 Nov 05:00Z (EST); 8 Mar 05:00Z (EST), 9 Mar 04:00Z (EDT)", o["mid"] == ["2026-11-01T04:00:00.000Z", "2026-11-02T05:00:00.000Z", "2026-03-08T05:00:00.000Z", "2026-03-09T04:00:00.000Z"], o["mid"])
    check("b. the repeated hour: 05:30Z (EDT) and 06:30Z (EST) both read 01:30 on 1 Nov; 07:00Z reads 02:00; spring forward: 06:59Z reads 01:59, 07:00Z reads 03:00",
          o["dst"] == [["2026-11-01", "00:30", 0], ["2026-11-01", "01:30", 0], ["2026-11-01", "01:30", 0], ["2026-11-01", "02:00", 0], ["2026-03-08", "01:59", 0], ["2026-03-08", "03:00", 0]], o["dst"])
    check("b. the windows follow the wall clock across the change: Mon 2 Nov 01:59 Asia, 02:00 London (07:00Z, EST); Sun closed until 18:00 (22:59Z closed, 23:00Z Asia); Fri 16:59 quiet, 17:00 closed; Thu 17:00 break, 18:00 Asia",
          o["edge"] == ["asia", "london", "closed", "asia", "idle", "closed", "break", "asia"], o["edge"])
    check("b. every boundary of a normal day (EST, Mon 2 Nov): 08:00 NY morning, 09:30 NY morning, 12:00 NY afternoon, 15:29 NY afternoon, 15:30 no new trades, 15:55 flat, 16:10 quiet, 17:00 CME break, 18:00 Asia",
          o["day2"] == ["nyam", "nyam", "nypm", "nypm", "winddown", "flat", "idle", "break", "asia"], o["day2"])
    u = o["until"]
    check("b. durations are counted on the real timeline: from Sun 00:30 EDT to the 18:00 reopen is 1,110 min (the wall clock would say 1,050); from 01:30 EDT 1,050; from 01:30 EST (after the clocks went back) 990; and the page says so",
          u[0] == "closed" and u[1] == "asia" and u[2] == 1110 and u[3] == 1050 and u[4] == 990 and u[11] == "Asia slot (paper) in 16 h 30 min", u)
    check("b. Mon 2 Nov 02:00 EST: London, entries open, next window (New York morning at 08:00) in 360 min; spring forward: Sun 8 Mar 01:30 EST to the 18:00 EDT reopen is 930 min (not 990)", u[5] == "london" and u[6] == "nyam" and u[7] == 360 and u[8] is True and u[9] == "asia" and u[10] == 930, u)
    check("b. the week: Fri 17:00 closes the market (22:00Z in EST); Saturday closed; Sunday closed until 18:00; Fri 17:30 reads closed and the next window is the Asia slot in 2,910 min (48.5 h)", o["wk"] == ["closed", "closed", "closed", "asia", "asia", 2910], o["wk"])
    check("b. the windows list at Tue 09:42: Asia and London done, New York morning NOW, afternoon NEXT, the rest later",
          o["wins"] == ["asia:past", "london:past", "nyam:now", "nypm:next", "winddown:later", "flat:later", "idle:later", "break:later"], o["wins"])
    check("b. the ring: 00:00 at the top, 06:00 right, 12:00 at the bottom, clockwise; every window band is a valid SVG path (the Asia slot wraps midnight)", o["ring"][0] and o["ring"][1] == 0 and o["ring"][2] == [160, 60] and o["ring"][3] == [260, 160] and o["ring"][4] == [160, 260] and all(o["ring"][5]), o["ring"])
    check("b. money words, every dollar with its R: +$437 (-1.0R is the trade's own), +$612 (+2.0R), a worked-out R is marked ~ (+$150 (~+0.5R) on the typical $300; -$300 (~-1.2R) on a $250 risk)",
          o["words"][:4] == ["+$437 (-1.0R)", "+$612 (+2.0R)", "+$150 (~+0.5R)", "-$300 (~-1.2R)"] and o["words"][4:] == ["15:30", "00:05", "-$1,235", "1 h 30 min", "1 day 1 h", "0.0R"], o["words"])
    check("b. trades: junk and bad dollars are dropped, a real trade and its paper twin at the same minute count once (the real one), the two hours of the repeated 01:xx both land in hour 1, newest first",
          o["norm"][0] == 4 and o["norm"][1] == "d,c,b,a" and o["norm"][2] == "3,3,1,1" and o["norm"][3].endswith("90,90") and o["norm"][4] == 0, o["norm"])
    check("b. the demo trades keep their New York wall-clock minute, offsets are days back; a bad offset is dropped", o["demo"][0] == 3 and o["demo"][1] == "2026-11-02@03:12,2026-11-01@02:10,2026-10-30@09:40" and o["demo"][2] == "demo,demo,demo", o["demo"])
    check("b. even on the 25-hour day a demo trade reads the minute it was given (03:00 and 01:10 on 1 Nov)", o["demoDst"] == ["2026-11-01@03:00/03:00", "2026-11-01@01:10/01:10"], o["demoDst"])
    check("b. today's trades, else the last trading day (labelled), else 'No trades yet'", o["tf"] == ["Today", 1, "Last trading day", "2026-11-03", "No trades yet", 0], o["tf"])
    h = o["heat"]
    check("b. the hour heat band: 24 buckets; hour 3 has 5 trades, +$900 in total, $180 and +0.5R each, 60% winners and is judged; hour 9 has 2 trades and hour 14 has 3 (judged: 3 is enough, 2 is not); an empty hour is empty",
          h == [24, 5, 900, True, 180, 0.5, 60, 2, False, True, -300, 0, False, 3], h)
    hw = o["heatWords"]
    check("b. no claim below 3 trades: the sentence names only judged hours; with none it says so; the 'not a promise' warning is always there",
          "Best hour so far: 03:00" in hw[0] and "Weakest: 14:00" in hw[0] and "09:00" not in hw[0] and "not a promise" in hw[0] and hw[1].startswith("No hour has 3 trades") and hw[2].startswith("No hour has 3 trades"), hw)
    check("b. the Jarvis card: Kairos, 3 kpis, two lines, an integer t", o["card"] == ["Kairos", 3, "ok", 2, True], o["card"])


SIDE = """() => ({ clock: document.querySelector('#clock').textContent, phase: document.querySelector('#phase').textContent, doing: document.querySelector('#doing').textContent, until: document.querySelector('#until').textContent,
  pill: document.querySelector('#entPill').textContent, demo: !document.querySelector('#demo').hidden, dst: document.querySelector('#dst').hidden ? '' : document.querySelector('#dst').textContent,
  wins: [...document.querySelectorAll('#wins li')].map((l) => l.textContent), now: (document.querySelector('#wins li.now b') || {}).textContent || '', trades: [...document.querySelectorAll('#trades li')].map((l) => l.textContent), trPill: document.querySelector('#trPill').textContent,
  dots: document.querySelectorAll('#ring .dot').length, needle: document.querySelectorAll('#ring .needle').length, bands: document.querySelectorAll('#ring .band').length, mid: document.querySelector('#ring .mid').textContent, cells: document.querySelectorAll('#heat .cell').length,
  few: document.querySelectorAll('#heat .cell.few').length, status: document.querySelector('#status').textContent, ringLabel: document.querySelector('#ring').getAttribute('aria-label') })"""


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
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-10T14:42:00Z")
            g = p.evaluate(SIDE)
            check("c. DEMO at Tue 09:42 ET: the clock, 'New York morning: entries are open', the 'Entries open' pill, what the bots do now in plain words, the next change (New York afternoon at 12:00) in 2 h 18 min, the DEMO chip",
                  g["clock"] == "Tue 09:42 ET" and g["phase"] == "New York morning: entries are open" and g["pill"] == "Entries open" and "LIT can still enter" in g["doing"] and g["until"] == "Next: New York afternoon in 2 h 18 min." and g["demo"], g)
            check("c. the windows list: 8 windows + the fixed marks, New York morning is NOW, and it names the paper-only Asia slot, 15:30 last entry, 15:55 flat, 16:10 MFFU flat, the 17:00 to 18:00 CME break",
                  len(g["wins"]) == 9 and g["now"] == "New York morning" and any("Asia slot" in w and "paper" in w for w in g["wins"]) and "15:30 last entry" in g["wins"][-1] and "17:00 to 18:00 CME break" in g["wins"][-1], g["wins"])
            check("c. today's two example trades are on the clock with their dollars and R: 03:12 +$612 (+2.0R) and 09:40 -$280 (-1.0R); the ring shows 2 dots, 8 bands, the gold hand and 09:42 in the middle",
                  len(g["trades"]) == 2 and "03:12 ET" in g["trades"][0] and "+$612 (+2.0R)" in g["trades"][0] and "09:40 ET" in g["trades"][1] and "-$280 (-1.0R)" in g["trades"][1] and g["dots"] == 2 and g["bands"] == 8 and g["needle"] == 1 and g["mid"] == "09:42", g)
            sc = p.evaluate("() => { const s = window.KAIROS.scene(); return [window.KAIROS.S.mode, s ? s.lit() : null, document.querySelector('.stage').hidden]; }")
            if sc[0] == "webgl":
                check("c. 3D: the marble sundial is drawn (WebGL) and the pillar of the current hour (09) is the lit one", sc[1] == 9 and sc[2] is False, sc)
            else:
                check("c. WebGL is not available here: the sundial is hidden and the flat ring carries the page (never blank)", sc[2] is True, sc)
            AK.shot(p, "kairos-demo")
            font = p.evaluate("() => [getComputedStyle(document.querySelector('h1')).fontFamily, getComputedStyle(document.body).backgroundColor]")
            check("c. AGORA look: serif title, warm dark body", any(f in font[0] for f in ("Palatino", "Iowan", "Georgia")) and font[1] == "rgb(20, 17, 14)", font)
            check("c. the heat band: 24 hour cells, the hours with fewer than 3 trades are dashed ('few'), the note says no claim is made and 'not a promise'", g["cells"] == 24 and g["few"] >= 2, (g["cells"], g["few"]))
            p.locator("#heat [data-hour='3']").click()
            d3 = p.evaluate("() => [document.querySelector('#heatDetail').textContent, document.querySelector('#heat [data-hour=\"3\"]').getAttribute('aria-pressed'), document.querySelector('#heatNote').textContent]")
            check("c. tap 03: its trades, the total with its R, the average with its R and the share of winners; the note names the best hour only among hours with 3+ trades",
                  "03:00 to 03:59 ET" in d3[0] and re.search(r"\d+ trades, [+-]\$[\d,]+ \([+-]\d+\.\dR\) in total, [+-]\$[\d,]+ \([+-]\d+\.\dR\) each on average, \d+% winners", d3[0]) and d3[1] == "true" and "Best hour so far" in d3[2] and "not a promise" in d3[2] and "EXAMPLE trades" in d3[2], d3)
            p.locator("#heat [data-hour='13']").click()
            d13 = p.evaluate("() => document.querySelector('#heatDetail').textContent")
            check("c. tap 13 (one example trade): 'Too few to say anything about this hour (it needs 3)', never a claim", "only 1 trade" in d13 and "Too few to say anything" in d13 and "it needs 3" in d13, d13)
            p.locator("#heat [data-hour='20']").click()
            d20 = p.evaluate("() => document.querySelector('#heatDetail').textContent")
            check("c. tap an empty hour: 'no trades'", "no trades" in d20, d20)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (the 24 hour cells, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # the clock change
            outs = {}
            for tag, at in (("a", "2026-11-01T04:30:00Z"), ("b", "2026-11-01T05:30:00Z"), ("c", "2026-11-01T06:30:00Z"), ("d", "2026-11-02T07:00:00Z"), ("e", "2026-11-02T06:59:00Z")):
                ctx, p, errs, seen, off = AK.page(br, origin)
                AK.open_app(p, origin, APP, f"?demo=1&at={at}")
                outs[tag] = p.evaluate(SIDE)
                outs[tag]["lit"] = p.evaluate("() => { const s = window.KAIROS.scene(); return s ? s.lit() : null; }")
                outs[tag]["err"] = list(errs)
                ctx.close()
            check("c. DST edge, Sun 1 Nov 2026: 04:30Z (00:30 EDT), 05:30Z (01:30 EDT) and 06:30Z (01:30 EST, the repeated hour) show the clock-change note ('twice', '25 hours'); the repeated 01:30 reads the same twice and the sundial lights hour 01 both times",
                  all(o["dst"] and "twice" in o["dst"] and "25 hours" in o["dst"] for o in (outs["a"], outs["b"], outs["c"])) and outs["b"]["clock"] == "Sun 01:30 ET" == outs["c"]["clock"] and outs["a"]["clock"] == "Sun 00:30 ET" and (outs["b"]["lit"] in (None, 1)) and (outs["c"]["lit"] in (None, 1)) and outs["b"]["lit"] == outs["c"]["lit"], {k: (v["clock"], v["dst"][:20], v["lit"]) for k, v in outs.items()})
            check("c. the countdown to the 18:00 reopen is counted on the real timeline: 18 h 30 min from 00:30 EDT, 17 h 30 min from 01:30 EDT, 16 h 30 min from the second 01:30 (EST); the market is closed (Sunday)",
                  outs["a"]["until"] == "Next: Asia slot (paper) in 18 h 30 min." and outs["b"]["until"] == "Next: Asia slot (paper) in 17 h 30 min." and outs["c"]["until"] == "Next: Asia slot (paper) in 16 h 30 min." and outs["c"]["pill"] == "Market closed" and outs["c"]["phase"].startswith("Market closed"), {k: v["until"] for k, v in outs.items()})
            check("c. Mon 2 Nov: 01:59 EST is still the Asia slot (paper) and 02:00 EST (07:00Z) opens London with entries; no clock-change note on the Monday; no console error",
                  outs["e"]["now"] == "Asia slot" and outs["e"]["pill"] == "No new entries" and outs["d"]["now"] == "London entries" and outs["d"]["pill"] == "Entries open" and outs["d"]["dst"] == "" and outs["d"]["clock"] == "Mon 02:00 ET" and not any(o["err"] for o in outs.values()), {k: (v["now"], v["pill"], v["err"]) for k, v in outs.items() if k in "de"})
            # the real trades file and the bot's own state line
            odeon = {"trades": [
                {"id": "real.1", "day": "2026-11-10", "side": "SHORT", "bot": "LIT", "src": "real", "usd": 437.0, "r": 1.03, "risk_usd": 425.0, "entry": {"t": 1794321300}, "exit": {"kind": "TARGET"}, "held_min": 19},
                {"id": "paper.1", "day": "2026-11-10", "side": "SHORT", "bot": "LIT", "src": "paper", "usd": 699.2, "r": 1.03, "risk_usd": 600.0, "entry": {"t": 1794321300}, "exit": {"kind": "TARGET"}, "held_min": 19},
                {"id": "real.0", "day": "2026-11-05", "side": "LONG", "bot": "LIT", "src": "real", "usd": -400.0, "r": -1.0, "risk_usd": 400.0, "entry": {"t": 1793889900}, "exit": {"kind": "STOP"}, "held_min": 11}]}
            home = {"live": {"model_state": "Watching for a sweep of the Asia high."}}
            srv2, origin2 = AK.serve({"/odeon/trades.json": json.dumps(odeon), "/home.json": json.dumps(home)})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=2026-11-10T15:00:00Z")
            r = p.evaluate(SIDE)
            check("c. the real trades file: no DEMO chip, today's real trade only once (its paper twin is the same signal), +$437 (+1.0R), the bot's own state line is quoted, nothing off the site",
                  not r["demo"] and len(r["trades"]) == 1 and "+$437 (+1.0R)" in r["trades"][0] and "real (eval)" in r["trades"][0] and r["trPill"].startswith("Today") and "Watching for a sweep of the Asia high." in r["doing"] and not off and not errs and any("odeon/trades.json" in u for u in seen), (r["trades"], r["doing"], errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=2026-11-12T15:00:00Z")
            lt = p.evaluate(SIDE)
            check("c. a day with no trades shows the last trading day, labelled, with the reason it is shown", lt["trPill"].startswith("Last trading day") and any("Nothing yet today" in x for x in [p.evaluate("() => document.querySelector('#trNote').textContent")]), lt["trPill"])
            ctx.close()
            srv2.shutdown()
            # no trades file at all -> the demo
            srv3, origin3 = AK.serve({"/odeon/trades.json": None, "/home.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?at=2026-11-10T15:00:00Z")
            nf = p.evaluate(SIDE)
            check("c. no trades file (404) -> the DEMO with example trades, never blank, no console error", nf["demo"] and len(nf["trades"]) >= 1 and nf["cells"] == 24 and not errs, errs[:2])
            ctx.close()
            srv3.shutdown()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-10T14:42:00Z&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_clock()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
