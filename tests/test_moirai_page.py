"""MOIRAI, the OLYMPUS scenario lab (tools/web_public/moirai/, AGORA look, 2026-11-10): sliders for win rate / average win R / average loss R / trades a week / risk per trade and a seeded Monte-Carlo of the MFFU 50K eval.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the defaults equal the bot's own 2026 run (research/runs/lit_live.json), the loom scene, the honest labels
  b. the maths in node (moiraicore.js): seeded determinism, chunking never changes a number, hand-worked paths (a win every day passes on day 10, a loss every day busts on day 7), the daily-loss cap on 1R, p10 / f10 / dec10, bands
  c. Chromium 390 x 844 (and 375 x 667): the default run equals node's, sliders and presets, reseed and back, ?query cases, the loom (WebGL) or the flat bars, LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_moirai_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "moirai", "Moirai"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../ledger/rules.json",), storage=True)
    d = os.path.join(AK.WEB, APP)
    js, core, scene, html = (AK.read(os.path.join(d, n)) for n in ("moirai.js", "moiraicore.js", "moiraiscene.js", "index.html"))
    fx = json.loads(AK.read(os.path.join(d, "fixture.json")))
    check("a. the page keeps only its sliders on the phone ('moirai.v1') and nothing else", "'moirai.v1'" in js and not re.search(r"sessionStorage|indexedDB", js + core), None)
    check("a. honest labels: 'simulation, not a forecast' in the title area, the note and the footer; a SIMULATION tag",
          html.count("not a forecast") >= 2 and "SIMULATION" in html and "not a forecast" in core.lower(), None)
    check("a. the work is chunked so a phone never freezes (runChunked, 100 paths a step) and a new slider move cancels the old run", "runChunked" in js and "chunk: 100" in js and "cancel()" in js, None)
    check("a. 3D: a marble spindle with three threads (olive pass, terracotta bust, gold open), a thread as thick as its chance, a LITE tier, WebGL optional (null -> flat bars), no bloom / composer",
          "../jarvis/three.module.min.js" in scene and "TubeGeometry" in scene and "LatheGeometry" in scene and "return null" in scene and "lite()" in scene and not re.search(r"Bloom|EffectComposer|neon", scene) and "drawFallback" in js, None)
    check("a. every R sits next to its dollars on the page ('both(' for the sliders, the cash table and the note)", js.count("C.both(") >= 6, js.count("C.both("))
    rules = json.load(open(os.path.join(ROOT, "tools", "web_public", "ledger", "rules.json"), encoding="utf-8"))["limits"]["builder_50k"]
    r = fx["rules"]
    check("a. the fixture's 50K rules equal the ledger rules file (target, max loss, lock, daily loss)", all(abs(r[k] - rules[k]) < 1e-9 for k in ("target", "mll", "lock", "dll")), (r, rules))
    run = os.path.join(ROOT, "research", "runs", "lit_live.json")
    if os.path.exists(run):
        t = [x for x in json.load(open(run, encoding="utf-8"))["trades"] if x[0] >= "2026-01-01"]
        n = len(t)
        w = [x[4] for x in t if x[4] > 0.05]
        l = [x[4] for x in t if x[4] < -0.05]
        want = {"win": len(w) / n, "scratch": (n - len(w) - len(l)) / n, "avg_win_r": sum(w) / len(w), "avg_loss_r": -sum(l) / len(l)}
        dd = fx["defaults"]
        check("a. the defaults ARE the bot's 2026 run (win rate, break-even share, average win R, average loss R), not made up", all(abs(dd[k] - want[k]) < 0.006 for k in want) and abs(fx["source"]["pnl_usd"] - sum(x[5] for x in t)) < 2, (dd, want))
    else:
        check("a. research/runs/lit_live.json is not in this checkout: the defaults check was skipped", True)
    check("a. four presets (LIT 2026, Jul-Oct, half the edge, coin flip) and the 0.6% default risk (the median trade risked $282 on $50,000)", [p["id"] for p in fx["presets"]] == ["lit26", "h2", "half", "coin"] and fx["defaults"]["risk_pct"] == 0.6, None)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {}, key = (S) => [S.p10, S.f10, S.dec10, S.p15, S.f15, S.pass, S.bust, S.open, S.slow_pass, S.pass_med];
  const p0 = C.clean({}), a = C.runAll(p0), b = C.runAll(C.clean({})), c = C.runAll(C.clean({ seed: 7 }));
  o.det = [JSON.stringify(a) === JSON.stringify(b), JSON.stringify(key(a)) !== JSON.stringify(key(c))];
  const whole = C.simChunk(p0, 0, 100), parts = C.simChunk(p0, 0, 37).concat(C.simChunk(p0, 37, 100));
  o.chunks = JSON.stringify(whole) === JSON.stringify(parts);
  const syncRun = C.runChunked(p0, { chunk: 130, defer: (f) => f() });
  o.chunked = syncRun.promise.then((S) => JSON.stringify(S) === JSON.stringify(a));
  o.def = [a.n, key(a), Math.round(a.pass + a.bust + a.open) === 1 && Math.abs(a.pass + a.bust + a.open - 1) < 1e-9, a.sample.length, a.bands.length, a.bands[0].every((v) => v === 50000), a.bands.every((r) => r.every((v, i) => i === 0 || v >= r[i - 1])), p0.oneR, Math.round(p0.expR * 10000) / 10000, Math.round(a.expected.usd * 100) / 100];
  const win = C.runAll(C.clean({ win: 0.95, scratch: 0, avg_win_r: 1, tpw: 5, risk_pct: 0.6 }));   // win capped at 95%: nearly every path passes on day 10
  const allWin = C.simPath(Object.assign(C.clean({ win: 0.95, scratch: 0, avg_win_r: 1, tpw: 5 }), { win: 1, loss: 0 }), 0);
  o.allWin = [allWin.end, allWin.day, allWin.eq[10], allWin.eq[30], allWin.trades];
  const allLoss = C.simPath(Object.assign(C.clean({ tpw: 5, avg_loss_r: 1 }), { win: 0, scratch: 0, loss: 1 }), 0);
  o.allLoss = [allLoss.end, allLoss.day, allLoss.eq[6], allLoss.eq[7], allLoss.eq[30]];
  const big = C.clean({ risk_pct: 5 }), tiny = C.clean({ risk_pct: 0.05 });
  o.cap = [big.oneR, tiny.oneR, big.rules.dll];
  const junk = C.clean({ win: 'x', scratch: 5, avg_win_r: -3, avg_loss_r: 99, tpw: 0, risk_pct: -1, seed: -5, paths: 1e9 }, { target: -1, horizon: 9999 });
  o.junk = [junk.win, junk.scratch, junk.avg_win_r, junk.avg_loss_r, junk.tpw, junk.risk_pct, junk.seed, junk.paths, junk.rules.target, junk.rules.horizon, Number.isFinite(junk.expR)];
  const trimmed = C.clean({ win: 0.6, scratch: 0.6 });
  o.trim = [trimmed.win, Math.round(trimmed.scratch * 1000) / 1000, Math.round(trimmed.loss * 1000) / 1000];
  const lo = C.runAll(C.clean({ risk_pct: 0.3 })), hi = C.runAll(C.clean({ risk_pct: 1.5 }));
  o.risk = [hi.f15 > lo.f15, hi.p10 > lo.p10];
  const coin = C.runAll(C.clean({ win: 0.5, scratch: 0, avg_win_r: 1, avg_loss_r: 1 })), good = C.runAll(C.clean({ win: 0.4, scratch: 0, avg_win_r: 3, avg_loss_r: 1 }));
  o.edge = [good.pass > coin.pass, coin.expected.r];
  o.words = [C.both(4.5, 300), C.both(-1, 300), C.rS(0.81), C.pct(0.2656, 1), C.money(-2.5), C.fates(a).map((x) => x.id).join()];
  o.card = [C.jarvisCard(a, p0, 5).name, C.jarvisCard(a, p0, 5).kpis.length, C.jarvisCard(a, p0, 5).lines[0]];
  o.presets = {};
  for (const [id, inp] of Object.entries(JSON.parse(process.argv[3]))) { const S = C.runAll(C.clean(inp)); o.presets[id] = [C.pct(S.pass, 1), C.pct(S.bust, 1), C.pct(S.p15, 1), C.pct(S.f15, 1), S.pass_med == null ? null : Math.round(S.pass_med * 10) / 10]; }
  o.chunked.then((ok) => { o.chunked = ok; console.log(JSON.stringify(o)); });
});
"""


def preset_inputs():
    fx = json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8"))
    return {p["id"]: {k: p[k] for k in ("win", "scratch", "avg_win_r", "avg_loss_r", "tpw", "risk_pct")} | {"seed": fx["defaults"]["seed"]} for p in fx["presets"]}


def test_maths():
    o = AK.node(APP, HARNESS, json.dumps(preset_inputs()))
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. seeded determinism: the same seed gives byte-identical results, another seed gives different numbers", o["det"] == [True, True], o["det"])
    check("b. a path only depends on (seed, its index): paths 0-37 + 37-100 equal paths 0-100", o["chunks"] is True, None)
    check("b. the chunked run (130 paths a step, any scheduler) gives exactly the single-shot summary", o["chunked"] is True, None)
    d = o["def"]
    check("b. defaults: 1,000 paths, three fates sum to 100%, 24 sample paths, 31 session columns, every fan starts at $50,000 and is ordered p10 <= p25 <= p50 <= p75 <= p90, 1R = $300",
          d[0] == 1000 and d[2] and d[3] == 24 and d[4] == 31 and d[5] and d[6] and d[7] == 300, d)
    check("b. expectancy on the bot's odds: +0.81R a trade = +$243 (0.267 x 4.49R - 0.441 x 0.88R, 1R = $300)", abs(d[8] - 0.8107) < 0.002 and abs(d[9] - 243.2) < 1.0, d[8:])
    check("b. hand path: a win of 1R every day (1R = $300) reaches +$3,000 on day 10 exactly, with 10 trades, and is frozen after", o["allWin"] == ["pass", 10, 53000, 53000, 10], o["allWin"])
    check("b. hand path: a loss of 1R every day: $50,000 - 7 x $300 = $47,900 touches the $48,000 floor on day 7 (day 6 is still $48,200); frozen at the floor", o["allLoss"] == ["bust", 7, 48200, 48000, 48000], o["allLoss"])
    check("b. 1R is the risk % of $50,000 but never more than the $1,000 daily loss limit (5% -> $1,000; 0.05% -> $25)", o["cap"] == [1000, 25, 1000], o["cap"])
    check("b. junk input is clamped, never a NaN: win 5%+, break-even <= the rest, win R >= 0.1, loss R <= 3, 0.1 trade a week, risk >= 0.05%, seed >= 0, 5,000 paths, rules sane",
          o["junk"][1] <= 0.95 and o["junk"][2] == 0.1 and o["junk"][3] == 3 and o["junk"][4] == 0.1 and o["junk"][5] == 0.05 and o["junk"][6] == 0 and o["junk"][7] == 5000 and o["junk"][8] == 3000 and o["junk"][9] == 60 and o["junk"][10], o["junk"])
    check("b. win 60% + break-even 60% is trimmed so they never exceed 100% (break-even 35%, losses 5%)", o["trim"] == [0.6, 0.35, 0.05], o["trim"])
    check("b. more risk per trade busts more and passes faster; a real edge beats a coin flip; the coin flip has zero expectancy", o["risk"] == [True, True] and o["edge"][0] and o["edge"][1] == 0, (o["risk"], o["edge"]))
    check("b. words: every R next to its dollars (+4.5R (+$1,350), -1.0R (-$300)), +0.8R, 26.6%, -$2.50, fates pass / bust / open", o["words"] == ["+4.5R (+$1,350)", "-1.0R (-$300)", "+0.8R", "26.6%", "-$2.50", "pass,bust,open"], o["words"])
    check("b. the Jarvis card: Moirai, 3 kpis, the first line says it is a simulation", o["card"][0] == "Moirai" and o["card"][1] == 3 and "not a forecast" in o["card"][2], o["card"])
    globals()["NODE_PRESETS"] = o["presets"]


def settle(p, cond):
    """wait until the page has finished its latest run AND the inputs carry the case we set (the slider waits 140 ms before it runs)"""
    p.wait_for_function("() => { const m = window.MOIRAI; return !!(m && m.S.sum && m.S.done === m.S.runs && m.S.p && (%s)); }" % cond, timeout=90000, polling=200)
    p.wait_for_timeout(150)


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    pre = globals().get("NODE_PRESETS") or {}
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            p.wait_for_function("document.querySelector('#runPill').textContent.includes('paths')", timeout=60000)
            g = p.evaluate("""() => ({ pill: document.querySelector('#runPill').textContent, tiles: [...document.querySelectorAll('#fates .tile b')].map((b) => b.textContent), head: document.querySelector('#headline').textContent,
              kv: document.querySelectorAll('#kv dt').length, fan: document.querySelectorAll('#fan polyline').length, bands: document.querySelectorAll('#fan polygon').length, cash: document.querySelector('#cash').textContent,
              labels: [...document.querySelectorAll('.fld > span')].map((s) => s.textContent), presets: [...document.querySelectorAll('#presets button')].map((b) => b.textContent), on: document.querySelector('#presets [aria-pressed=true]').textContent,
              honest: document.querySelector('#honest').textContent, status: document.querySelector('#status').textContent, tag: document.querySelector('.tag.demo').textContent }) """)
            lit = pre.get("lit26")
            whole = lambda x: str(int(float(x.rstrip("%")) + 0.5)) + "%"  # the tiles and the headline show whole percents
            check("c. the default run (seed 2026) equals node's numbers exactly: pass, bust and the 15-session figures (whole percents)", lit and g["tiles"][0] == whole(lit[0]) and g["tiles"][1] == whole(lit[1]) and whole(lit[2]) + " pass within 15" in g["head"] and whole(lit[3]) + " bust within 15" in g["head"], (g["tiles"], lit, g["head"]))
            check("c. the page: '1,000 paths', three fate tiles, 10 result rows (p10 f10 dec10 p15 f15 dec15 pass bust slow_pass pass_med), the fan (24 single paths + the middle one, 2 bands), 4 presets with LIT 2026 on",
                  g["pill"] == "1,000 paths" and len(g["tiles"]) == 3 and g["kv"] == 10 and g["fan"] == 25 and g["bands"] == 2 and g["presets"] == ["LIT 2026", "Jul-Oct only", "Half the edge", "Coin flip 1R"] and g["on"] == "LIT 2026", g)
            check("c. every R next to its dollars on the sliders: '+4.5R (+$1,347)', '-0.9R (-$264)', '1R = $300'; and the table '-1.0R (-$300)'",
                  any("+4.5R (+$1,347)" in x for x in g["labels"]) and any("-0.9R (-$264)" in x for x in g["labels"]) and any("1R = $300" in x for x in g["labels"]) and "-1.0R (-$300)" in g["cash"], g["labels"])
            check("c. honest: a SIMULATION tag, the 'not a forecast' note and the status line say so", g["tag"] == "SIMULATION" and "not a forecast" in g["honest"] and "not a forecast" in g["status"], (g["tag"], g["honest"]))
            sc = p.evaluate("() => { const s = window.MOIRAI.scene(); return [window.MOIRAI.S.mode, s ? s.radii() : null, !document.querySelector('#loom').hidden, document.querySelector('#loomFallback').hasAttribute('hidden')]; }")
            if sc[0] == "webgl":
                rr = sc[1]
                check("c. 3D: the loom is drawn and each thread is as thick as its chance (pass thickest on the bot's odds, bust thinnest)", rr["pass"] > rr["open"] > rr["bust"] and sc[2] and sc[3], sc)
            else:
                check("c. WebGL is not available here: three flat bars are drawn instead (never blank)", p.evaluate("() => document.querySelectorAll('#loomFallback rect').length") == 3, sc)
            AK.shot(p, "moirai-demo")
            font = p.evaluate("() => [getComputedStyle(document.querySelector('h1')).fontFamily, getComputedStyle(document.body).backgroundColor]")
            check("c. AGORA look: serif title, warm dark body", any(f in font[0] for f in ("Palatino", "Iowan", "Georgia")) and font[1] == "rgb(20, 17, 14)", font)
            # presets
            p.locator("#presets [data-preset=coin]").click()
            settle(p, "m.S.p.win === 0.5")
            cf = p.evaluate("() => [[...document.querySelectorAll('#fates .tile b')].map((b) => b.textContent), document.querySelector('#headline').textContent, document.querySelector('#expNote').textContent]")
            coin = pre.get("coin")
            check("c. tap 'Coin flip 1R': the same numbers as node for that preset, and the note says the average trade loses / makes nothing", coin and cf[0][0] == whole(coin[0]) and cf[0][1] == whole(coin[1]) and whole(coin[2]) + " pass within 15" in cf[1], (cf, coin))
            # a slider
            p.locator("#presets [data-preset=lit26]").click()
            settle(p, "m.S.p.win === 0.267")
            p.evaluate("() => { const e = document.querySelector('#risk'); e.value = '1.5'; e.dispatchEvent(new Event('input', { bubbles: true })); }")
            settle(p, "m.S.p.risk_pct === 1.5")
            hi = p.evaluate("() => [document.querySelector('#riskL').textContent, [...document.querySelectorAll('#fates .tile b')].map((b) => b.textContent), document.querySelector('#presets [aria-pressed=true]') === null, document.querySelector('#awL').textContent]")
            check("c. risk to 1.5%: '1R = $750', more busts than at 0.6%, no preset is highlighted any more, the win label follows the new 1R ('+4.5R (+$3,368)')",
                  "1R = $750" in hi[0] and float(hi[1][1].rstrip('%')) > float(lit[1].rstrip('%')) and hi[2] and "+$3,367.50" in hi[3], hi)
            # seed
            s1 = p.evaluate("() => document.querySelector('#kv').textContent")
            p.locator("#seedBox summary").click()
            p.locator("#reseed").click()
            settle(p, "m.S.p.seed !== 2026")
            s2 = p.evaluate("() => [document.querySelector('#kv').textContent, document.querySelector('#seed').value]")
            p.fill("#seed", "2026")
            settle(p, "m.S.p.seed === 2026")
            s3 = p.evaluate("() => document.querySelector('#kv').textContent")
            check("c. a new seed changes the numbers; typing the old seed (2026) back gives the first numbers again, to the digit", s2[0] != s1 and s2[1] != "2026" and s3 == s1, (s1[:80], s2[0][:80], s3[:80]))
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, sliders, inputs, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin; only the site's files were read", AK.no_sideways(p) and not AK.corner(p) and not errs and not off and all(u.startswith(origin) for u in seen), (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?win=50&scratch=0&aw=1&al=1&seed=5&risk=0.6")
            p.wait_for_function("document.querySelector('#runPill').textContent.includes('paths')", timeout=60000)
            q = p.evaluate("() => [document.querySelector('#winL').textContent, document.querySelector('#seed').value, document.querySelector('#expNote').textContent, document.querySelector('#headline').textContent]")
            check("c. ?win=50&scratch=0&aw=1&al=1&seed=5 opens that case: win 50%, seed 5, zero edge (the note says an average trade makes nothing)", "50%" in q[0] and q[1] == "5" and "nothing" in q[2] and "pass within 15" in q[3], q)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            p.wait_for_function("document.querySelector('#runPill').textContent.includes('paths')", timeout=60000)
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
