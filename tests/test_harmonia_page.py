"""HARMONIA, the OLYMPUS balance (tools/web_public/harmonia/, AGORA look, 2026-11-10): where the owner's risk and income sit across the three NQ accounts and the five money machines (a donut and a stacked bar in plain SVG),
a concentration warning when everything depends on the same NQ signals (copies fail together), an 'if the NQ bots stop' scenario in $ a month with honest ranges, and a marble balance beam with gold weights (3D, flat fallback).

  a. static: the files, the kit lines, the AGORA look, read-only (it keeps nothing), the Jarvis card, the manifest, the DEMO fixture, the row in tools/new_apps.json
  b. the maths in node (harmoniacore.js): matching, the risk shares, the income bars, the concentration levels and words, the scenario ranges (a loss is a loss), the geometry, junk safety
  c. Chromium 390 x 844: DEMO, the stop button, the real files (and the REAL money engine run with the Chrysos Stress range), broken and missing files fall back, 3D or flat balance, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_harmonia_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "harmonia", "Harmonia"
check = AK.check
FIX = os.path.join(AK.WEB, APP, "fixture.json")
SCENES = {"stars", "smoke", "coins", "embers", "neurons", "skyline", "torches", "threads", "streaks", "bars", "leaves", "columns", "shards", "rings", "maze"}


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../money/index.json"))
    d = os.path.join(AK.WEB, APP)
    check("a. the 3D files: beam.js (render core) and beamload.js (its own module tag)", all(os.path.isfile(os.path.join(d, n)) for n in ("beam.js", "beamload.js")))
    bj = AK.read(os.path.join(d, "beam.js"))
    check("a. beam.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network, no markup from data",
          "../olympus/render.js" in bj and "../jarvis/three.module.min.js" in bj and not AK.BANNED_LOOK.search(bj) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", bj) and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", bj)))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. beamload.js before harmonia.js; a canvas AND a flat svg balance (the fallback); the donut and the stacked bar are plain SVG; page order: balance, concentration, scenario, risk, income, how",
          html.index("beamload.js") < html.index('src="harmonia.js') and 'id="stage"' in html and 'id="flat"' in html and 'id="donut"' in html and 'id="bars"' in html
          and html.index('id="headline"') < html.index('id="concTitle"') < html.index('id="tiles"') < html.index('id="donut"') < html.index('id="bars"') < html.index('id="how"'))
    check("a. Harmonia only shows: no POST, no window.open, no browser storage written", not re.search(r"method:\s*['\"]POST|window\.open|localStorage\.setItem|sessionStorage", AK.read(os.path.join(d, "harmonia.js")) + AK.read(os.path.join(d, "harmoniacore.js"))))
    fx = json.load(open(FIX, encoding="utf-8"))
    check("a. the fixture: three accounts and five money streams with their own low / base / high (Chrysos's Stress low end is a loss)",
          [a["key"] for a in fx["accounts"]] == ["zlarior", "atlas", "blitz"] and [s["id"] for s in fx["money"]["streams"]] == ["chrysos", "mercury", "sibyl", "oikos", "arbiter"] and fx["money"]["streams"][0]["usd_month"]["low"] < 0)
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))
    row = next((a for a in na["apps"] if a["id"] == APP), None)
    check("a. the row in tools/new_apps.json: group money, a description under 80 characters, an existing intro scene, a transition, an ambient bed, an accent and a glyph (and --apply is for the lead)",
          row is not None and row["group"] == "money" and len(row["description"]) < 80 and row["flavour"][0] in SCENES and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["ambient"] and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"], row)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
  const o = {};
  o.words = [C.money(2000), C.money(-42), C.money(null), C.pct(0.8956), C.pct(null), C.drawdownLine(1420, 2000), C.rangeText(-42, 2235), C.rangeText(0, 312), C.rangeText(null, 5)];
  o.match = [C.matchKey({ id: 'acct_c' }), C.matchKey({ name: 'ATLAS' }), C.matchKey({ id: 'mffu50k_eval' }), C.matchKey({ id: 'zzz' }), C.matchKey(null), C.ORDER];
  const home = { accounts: [{ id: 'mffu50k_eval', kind: 'eval', eval: { room: 1420, mll: 2000 } }, { id: 'acctb', eval: { room: 240, mll: 1000 }, stats: { avg_loss: -150 } }] };
  const b = C.buildAccounts(home, fx), d = C.buildAccounts(null, fx), e = C.buildAccounts({ accounts: 'x' }, null);
  o.build = [b.demo, b.accounts.map((a) => [a.key, a.has, a.room, a.mll, a.risk, a.est]), d.demo, d.accounts.map((a) => [a.has, a.room]), e.demo, e.accounts.map((a) => [a.has, a.mll])];
  const sl = C.riskSlices(b.accounts);
  o.slices = [sl.map((s) => [s.key, Math.round(s.share * 100), s.usd]), sl.reduce((a, s) => a + s.share, 0), sl[0].line, sl[2].line, sl[1].trade, sl[1].est];
  const st = C.streamsOf(fx.money);
  o.streams = st.map((s) => [s.id, s.has, s.base, s.low, s.high, s.nq, s.depends, s.status]);
  o.streamsEmpty = [C.streamsOf(null).length, C.streamsOf(null).every((s) => !s.has && s.base === 0), C.streamsOf({ streams: [null, 5, { id: 'chrysos', usd_month: { base: 'x' } }, { id: 'oikos', status: 'ok', usd_month: { base: 40 } }] }).map((s) => [s.id, s.has, s.base, s.low, s.high])];
  const bars = C.incomeBars(st);
  o.bars = [bars.total, Math.round(bars.parts.reduce((a, p) => a + p.share, 0) * 1000) / 1000, bars.parts.map((p) => Math.round(p.share * 100)), C.incomeBars(C.streamsOf(null)).total];
  const c = C.concentration(st, b.accounts), c0 = C.concentration(C.streamsOf(null), b.accounts);
  const mk = (nq, other) => C.streamsOf({ streams: [{ id: 'chrysos', usd_month: { low: 0, base: nq, high: nq } }, { id: 'oikos', usd_month: { low: 0, base: other, high: other } }] });
  o.conc = [c.level, Math.round(c.share * 100), c.nqUsd, c.otherUsd, c.total, c.title, c.text.includes('win and lose TOGETHER'), c.text.includes('3 accounts are not 3 independent chances'), c0.level, c0.title, C.concentration(mk(50, 50), b.accounts).level, C.concentration(mk(45, 55), b.accounts).level, C.concentration(mk(20, 80), b.accounts).level, C.concentration(mk(70, 30), b.accounts).level, C.concentration(mk(69, 31), b.accounts).level];
  const sc = C.scenario(st), sc0 = C.scenario(C.streamsOf(null));
  o.sc = [sc.now, sc.left, sc.lost, sc.text, sc.worst, Math.round(sc.keepShare * 1000) / 1000, sc0.text, sc0.now.base, sc0.keepShare];
  const neg = C.scenario(C.streamsOf({ streams: [{ id: 'chrysos', usd_month: { low: -42, base: 100, high: 150 } }, { id: 'oikos', usd_month: { low: 10, base: 20, high: 30 } }] }));
  o.neg = [neg.now.low, neg.left.low, neg.worst, neg.lost.low, neg.text.includes('$-')];
  const be = C.beam(st, false), bs = C.beam(st, true), bz = C.beam(C.streamsOf(null), false), bw = C.beam(mk(50, 50), false), bl = C.beam(mk(10, 90), false);
  o.beam = [be.L, be.R, be.tilt, be.level, bs.L, bs.tilt, bs.level, bz.tilt, bz.level, bw.tilt, bw.level, bl.tilt, bl.level, be.left.map((x) => x.id), be.right.map((x) => x.id)];
  const ang = C.sliceAngles([{ share: 0.5 }, { share: 0.25 }, { share: 0.25 }], 0.04), one = C.sliceAngles([{ share: 1 }], 0.04), zero = C.sliceAngles([{ share: 0 }, { share: 1 }], 0.04);
  o.geo = [ang.length, Math.round(ang[0].a0 * 1000) / 1000, Math.round(ang[2].a1 * 1000) / 1000, ang.every((a) => a.a1 > a.a0), one[0].a0 === 0 && Math.abs(one[0].a1 - Math.PI * 2) < 1e-9, zero[0].a1 === zero[0].a0,
    C.arcPath(100, 100, 58, 92, 0, 1).startsWith('M'), C.arcPath(100, 100, 58, 92, 0, Math.PI * 2).split('M').length - 1, C.arcPath(100, 100, 58, 92, 0, 3.5).includes(' 1 1 '), C.arcPath(100, 100, 58, 92, 0, 1).includes('NaN')];
  o.head = [C.headline(c, sc), C.headline(c0, sc0)];
  o.card = [C.jarvisCard(c, sc), C.jarvisCard(c0, sc0).level];
  const junk = [null, undefined, 'x', 5, [], {}, { streams: 'x' }, { streams: [{ id: 'chrysos', usd_month: { base: Infinity } }] }];
  o.junk = junk.map((j) => { try { const s = C.streamsOf(j), cc = C.concentration(s, []), ss = C.scenario(s), bb = C.beam(s, true); return [s.length, Number.isFinite(cc.share), Number.isFinite(ss.left.base), Number.isFinite(bb.tilt)]; } catch (x) { return String(x); } });
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
    check("b. words: $2,000, -$42, $0, 90%, 0%, the exact drawdown sentence, a range with a loss ('a loss of $42 a month to $2,235 a month'), a plain range, no range",
          o["words"] == ["$2,000", "-$42", "$0", "90%", "0%", "Drawdown left $1,420 of $2,000 max loss", "a loss of $42 a month to $2,235 a month", "$0 to $312 a month", "no range yet"], o["words"])
    check("b. account matching: acct_c -> BLITZ, ATLAS, mffu50k -> Zlarior, unknown and null -> none; the order", o["match"] == ["blitz", "atlas", "zlarior", None, None, ["zlarior", "atlas", "blitz"]], o["match"])
    check("b. accounts: the real home.json gives Zlarior $1,420 of $2,000 (plan stand-in 425, an estimate) and ATLAS $240 of $1,000 with its real $150 loss; BLITZ has no row; no home.json -> the fixture's rows as DEMO; nothing at all -> three empty accounts at their plan's max loss",
          o["build"][0] is False and o["build"][1] == [["zlarior", True, 1420, 2000, 425, True], ["atlas", True, 240, 1000, 150, False], ["blitz", False, None, 1000, 120, True]] and o["build"][2] is True and o["build"][3] == [[True, 1420], [True, 840], [True, 560]]
          and o["build"][4] is True and o["build"][5] == [[False, 2000], [False, 1000], [False, 1000]], o["build"])
    check("b. the risk donut: max loss shares 50% / 25% / 25% of $4,000 (they add to 100%), 'Drawdown left $1,420 of $2,000 max loss', no numbers -> 'Max loss $1,000 (no live numbers yet)', the stop costs $150 (real)",
          o["slices"][0] == [["zlarior", 50, 2000], ["atlas", 25, 1000], ["blitz", 25, 1000]] and abs(o["slices"][1] - 1) < 1e-9 and o["slices"][2] == "Drawdown left $1,420 of $2,000 max loss" and o["slices"][3] == "Max loss $1,000 (no live numbers yet)" and o["slices"][4] == 150 and o["slices"][5] is False, o["slices"])
    check("b. the five money streams in a fixed order with what they depend on (only Chrysos on NQ); a stream without a number is kept at $0 and flagged; junk rows are ignored; a low end below zero is kept",
          [s[0] for s in o["streams"]] == ["chrysos", "mercury", "sibyl", "oikos", "arbiter"] and [s[5] for s in o["streams"]] == [True, False, False, False, False] and o["streams"][0][3] < 0 and o["streams"][1][1] is False and o["streams"][1][2] == 0
          and o["streamsEmpty"][0] == 5 and o["streamsEmpty"][1] and o["streamsEmpty"][2][0] == ["chrysos", False, 0, 0, 0] and o["streamsEmpty"][2][3] == ["oikos", True, 40, 0, 40], (o["streams"], o["streamsEmpty"]))
    check("b. the income bar: the total is the sum of the bases ($1,495), the shares add to 1, Chrysos is 90%; no streams -> $0", o["bars"][0] == 1495.01 and o["bars"][1] == 1 and o["bars"][2][0] == 90 and o["bars"][3] == 0, o["bars"])
    c = o["conc"]
    check("b. the concentration: the demo is 'bad' (90% on NQ, $1,339 of $1,495), it says copies win and lose TOGETHER and '3 accounts are not 3 independent chances'; no estimate -> 'off'; 50% -> warn; 45% -> warn; 20% -> ok; 70% -> bad; 69% -> warn",
          c[0] == "bad" and c[1] == 90 and c[2] == 1339.01 and c[3] == 156 and c[4] == 1495.01 and c[5] == "90% of the estimate depends on the same NQ signals" and c[6] and c[7] and c[8] == "off" and c[9] == "No estimate to weigh yet" and c[10:] == ["warn", "warn", "ok", "bad", "warn"], c)
    s = o["sc"]
    check("b. 'if the NQ bots stop': now -$42 / $1,495 / $2,547, left $0 / $156 / $312, lost the Chrysos base $1,339; the sentence says 'about $156 a month is left' and that fees do not come back; the worst case says nothing is left; 10% kept; no estimate says so",
          s[0] == {"low": -42.01, "base": 1495.01, "high": 2546.78} and s[1] == {"low": 0, "base": 156, "high": 312} and s[2]["base"] == 1339.01 and "about $156 a month is left ($0 to $312 a month)" in s[3] and "fees already paid do not come back" in s[3]
          and s[4] == "In the worst case nothing is left." and s[5] == 0.104 and s[6].startswith("No estimate yet") and s[7] == 0 and s[8] == 0, s)
    check("b. honest ranges: a loss on the NQ side stays a loss in 'now' (-$42) and never leaks into what is left; what is left keeps its own low end ($10 -> 'In the worst case $10 a month is left.'); nothing reads '$-'", o["neg"] == [-32, 10, "In the worst case $10 a month is left.", -42, False], o["neg"])
    b = o["beam"]
    check("b. the balance beam: NQ weight $1,339 left, $156 right, tilts toward NQ (0.317, 'bad'); 'stopped' empties the left pan and it tilts the other way; no estimate level; a 50/50 beam is level; a light NQ side tilts right; the NQ stream is on the left only",
          b[0] == 1339.01 and b[1] == 156 and b[2] == 0.317 and b[3] == "bad" and b[4] == 0 and b[5] < 0 and b[6] in ("bad", "warn") and b[7] == 0 and b[8] == "off" and b[9] == 0 and b[10] == "ok" and b[11] < 0 and b[13] == ["chrysos"] and "chrysos" not in b[14], b)
    g = o["geo"]
    check("b. the donut geometry: 3 slices from the top round to a full turn, each with a gap, a lone slice is a full circle (two halves), a zero slice is empty, the path is valid and never NaN", g[0] == 3 and g[1] == 0.02 and g[3] and g[4] and g[5] and g[6] and g[7] == 2 and g[8] and not g[9], g)
    check("b. the headline and the Jarvis card: '90% of the estimated $1,495 a month depends on the NQ bots; if they stop, about $156 a month is left.'; no estimate says so; the card has the level, 90% and $156",
          o["head"][0] == "90% of the estimated $1,495 a month depends on the NQ bots; if they stop, about $156 a month is left." and o["head"][1].startswith("No estimate to weigh yet") and o["card"][0]["name"] == "Harmonia" and o["card"][0]["nq"] == "90%" and o["card"][0]["left"] == "$156" and o["card"][1] == "off", o["head"] + [o["card"]])
    check("b. junk in, never a throw or a NaN: null, text, numbers, arrays, empty, a broken streams list and Infinity all give five streams and finite numbers", all(x == [5, True, True, True] for x in o["junk"]), o["junk"])


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
            AK.open_app(p, origin, APP, "?demo=1", hook="HARMONIA")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#pill').textContent, head: document.querySelector('#headline').textContent, cpill: document.querySelector('#concPill').textContent,
              ctitle: document.querySelector('#concTitle').textContent, ctext: document.querySelector('#concText').textContent, tiles: document.querySelector('#tiles').textContent, slices: document.querySelectorAll('#donut path.slice').length,
              parts: document.querySelectorAll('#bars rect.part').length, risk: [...document.querySelectorAll('#riskLegend .lg')].map((l) => l.textContent), inc: document.querySelectorAll('#incLegend .lg').length, how: document.querySelectorAll('#how li').length,
              weights: document.querySelectorAll('#flat rect.weight').length, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, mode: window.HARMONIA.mode, donut: document.querySelector('#donut').textContent })""")
            check("c. DEMO: the chip, 'Leaning hard', the headline '90% ... if they stop, about $156 a month is left', a strong warning with 'win and lose TOGETHER', the scenario tiles ($1,495 / $156 / $1,339), 3 ring slices, 4 income parts (Mercury has no number), 3 + 5 legend rows",
                  d["demo"] and d["pill"] == "Leaning hard" and d["head"].startswith("90% of the estimated $1,495 a month depends on the NQ bots") and d["cpill"] == "Strong warning" and "win and lose TOGETHER" in d["ctext"] and "$1,495" in d["tiles"] and "$156" in d["tiles"] and "$1,339" in d["tiles"]
                  and d["slices"] == 3 and d["parts"] == 4 and len(d["risk"]) == 3 and d["inc"] == 5 and d["how"] == 5 and d["weights"] >= 4 and "$4,000" in d["donut"], d)
            check("c. every risk row says 'Drawdown left $X of $Y max loss' and one full stop's cost: Zlarior 50% of the risk, ATLAS 25%, BLITZ 25%", "50% of the risk" in d["risk"][0] and "Drawdown left $1,420 of $2,000 max loss" in d["risk"][0] and "25% of the risk" in d["risk"][1] and "Drawdown left $560 of $1,000 max loss" in d["risk"][2], d["risk"])
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the balance is 3D or the flat drawing, never nothing", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#flat').hasAttribute('hidden')"), d["mode"])
            AK.shot(p, "harmonia-demo")
            p.locator("#stop").click()
            p.wait_for_timeout(250)
            a = p.evaluate("() => ({ pill: document.querySelector('#pill').textContent, head: document.querySelector('#headline').textContent, btn: document.querySelector('#stop').textContent, on: document.querySelector('#stop').getAttribute('aria-pressed'), st: document.querySelector('#status').textContent, w: document.querySelectorAll('#flat rect.weight').length })")
            check("c. tap 'If the NQ bots stop': the pill says what-if, 'about $156 a month is left of $1,495', the button flips to 'Put the NQ bots back', the gold weights leave the left pan, the status line is spoken",
                  a["pill"] == "NQ bots stopped (what-if)" and "$156 a month is left of $1,495" in a["head"] and a["btn"] == "Put the NQ bots back" and a["on"] == "true" and "$156" in a["st"] and a["w"] < d["weights"], a)
            p.locator("#stop").click()
            p.wait_for_timeout(250)
            b = p.evaluate("() => [document.querySelector('#pill').textContent, document.querySelector('#stop').getAttribute('aria-pressed')]")
            check("c. tap again: back to the balance", b == ["Leaning hard", "false"], b)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=high&stop=1", hook="HARMONIA")
            hq = p.evaluate("() => [window.HARMONIA.mode, getComputedStyle(document.querySelector('#flat')).display, document.querySelector('#stop').getAttribute('aria-pressed')]")
            check("c. ?q=high&stop=1: the 3D beam builds and the flat drawing is hidden (or, with no WebGL, the flat balance stays), the what-if is on, no console error", ((hq[0] == "3d" and hq[1] == "none") or (hq[0] == "flat" and hq[1] != "none")) and hq[2] == "true" and not errs, (hq, errs[:2]))
            ctx.close()

            # the REAL money engine run (the real Chrysos scanner with its Stress range), served as money/index.json, and a real-looking home.json
            import money_engine as ME
            real_out = tempfile.mkdtemp(prefix="harmonia-real-")
            ME.run(real_out, True, 120, quiet=True)
            home = {"accounts": [{"id": "mffu50k_eval", "kind": "eval", "eval": {"room": 1420, "mll": 2000}}, {"id": "acctb", "eval": {"room": 240, "mll": 1000}, "stats": {"avg_loss": -150}}]}
            srv2, origin2 = AK.serve({"/money/index.json": open(os.path.join(real_out, "index.json"), encoding="utf-8").read(), "/home.json": json.dumps(home)})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "", hook="HARMONIA")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, tiles: document.querySelector('#tiles').textContent, risk: [...document.querySelectorAll('#riskLegend .lg')].map((l) => l.textContent), all: document.body.innerText.includes('$-'), c: document.querySelector('#concText').textContent })")
            check("c. the REAL engine run and a real home.json: no DEMO chip; today is a range that starts below zero (Chrysos's Stress case is a loss), what is left after the NQ bots stop is the other machines only; ATLAS 'Drawdown left $240 of $1,000 max loss'; BLITZ 'no live numbers yet'; nothing reads '$-'",
                  not r["demo"] and "a loss of $42 a month" in r["tiles"] and "Drawdown left $240 of $1,000 max loss" in r["risk"][1] and "no live numbers yet" in r["risk"][2] and not r["all"] and "TOGETHER" in r["c"], r)
            check("c. the real run reads home.json and money/index.json only and no console error", any("home.json" in u for u in seen) and any("money/index.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()

            srv3, origin3 = AK.serve({"/home.json": '{"accounts": "junk"}', "/money/index.json": "not json"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "", hook="HARMONIA")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#headline').textContent]")
            check("c. broken files never blank the page: the fixture shows with the DEMO chip, no console error", r[0] and r[1].startswith("90%") and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()

            srv4, origin4 = AK.serve({"/home.json": None, "/money/index.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "", hook="HARMONIA")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#donut path.slice').length]")
            check("c. both files missing (404): the fixture shows with the DEMO chip and the ring", r == [True, 3], r)
            ctx.close()
            srv4.shutdown()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low", hook="HARMONIA")
            mode = p.evaluate("() => window.HARMONIA.mode")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the flat balance, no sideways scroll, every tap >= 44 px, no error", mode == "flat" and AK.no_sideways(p) and not AK.taps(p) and not errs, (mode, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "harmonia-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
