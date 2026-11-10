"""AEGIS, the OLYMPUS risk guard (tools/web_public/aegis/, AGORA look, 2026-11-10): per account (Zlarior 50K, ATLAS 25K, BLITZ 25K) the MFFU rules in plain words, 'Drawdown left $X of $max loss',
a what-if 'if the next trade is a full stop: you will have $Y left', a when-to-stop list, and a bronze shield whose gold rim shrinks as the drawdown is used (3D, flat fallback).

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the built-in limits equal MFFU's file (research/lit/mffu_rules.json)
  b. the maths in node (aegiscore.js): matching, limits override, health, what-if, lock-outs, rules text, shield rim, junk safety
  c. Chromium 390 x 844: DEMO, the account chips, the what-if (typing, +/-, quick sizes), the real home.json, a broken one falls back, 3D or flat shield, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_aegis_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "aegis", "Aegis"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../ledger/rules.json"))
    d = os.path.join(AK.WEB, APP)
    check("a. the 3D files: shield.js (render core) and shieldload.js (its own module tag)", all(os.path.isfile(os.path.join(d, n)) for n in ("shield.js", "shieldload.js")))
    sh = AK.read(os.path.join(d, "shield.js"))
    check("a. shield.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network, no markup from data",
          "../olympus/render.js" in sh and "../jarvis/three.module.min.js" in sh and not AK.BANNED_LOOK.search(sh) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", sh)
          and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", sh)))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. shieldload.js before aegis.js; the page has a canvas AND a flat svg shield (the fallback); page order: account, shield, what-if, lock-outs, all three, rules",
          html.index("shieldload.js") < html.index('src="aegis.js') and 'id="stage"' in html and 'id="flat"' in html
          and html.index('id="accts"') < html.index('id="stage"') < html.index('id="ifLine"') < html.index('id="locks"') < html.index('id="all"') < html.index('id="rules"'))
    core = AK.read(os.path.join(d, "aegiscore.js"))
    rules = json.load(open(os.path.join(AK.ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))["limits"]
    mine = {}
    for plan in ("builder_50k", "builder_25k"):
        blk = re.search(plan + r": \{([^}]*)\}", core.split("DEFAULT_LIMITS = ")[1]).group(1)
        mine[plan] = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+)", blk)}
    same = all(abs(mine[p][k] - rules[p][k]) < 1e-9 for p in mine for k in mine[p] if k in rules[p])
    check("a. the built-in limits (used when ledger/rules.json is missing) equal research/lit/mffu_rules.json: target, max loss, lock, daily loss, micros, flat time, buffer, payouts, consistency", same, mine)
    check("a. no promise or blocking words: Aegis only warns", not re.search(r"guarantee|risk-free|will block|blocks your|auto-?close", html + core, re.I))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const home = { accounts: [
    { id: 'mffu50k_eval', name: 'MFFU 50K Eval', kind: 'eval', eval: { balance: 50420, floor: 49000, room: 1420, mll: 2000, dll: 1000, dll_used: 100 }, pnl: { today: -100, week: 640 } },
    { id: 'acctb', name: 'ATLAS 25K', kind: 'eval', eval: { balance: 24480, floor: 24240, room: 240, mll: 1000, dll: 600, dll_used: 60 }, stats: { avg_loss: -150 } }] };
  const fx = { accounts: [{ key: 'zlarior', room: 1420, mll: 2000, floor: 49000, balance: 50420, risk: 425, dll: 1000, dllUsed: 0, today: 312, week: 640, toTarget: 2580 }, { key: 'blitz', room: 560, mll: 1000, risk: 120 }] };
  o.words = [C.money(2000), C.moneyS(-60), C.rText(-425, 425, false), C.rText(-150, 150, true), C.both(-425, 425, false), C.drawdownLine(1420, 2000), C.clock(970), C.clock(null)];
  o.match = [C.matchKey({ id: 'acct_c' }), C.matchKey({ name: 'ATLAS' }), C.matchKey({ id: 'mffu50k_eval' }), C.matchKey({ id: 'zzz' }), C.matchKey(null)];
  const b = C.buildAccounts(home, fx, null);
  o.build = [b.demo, b.accounts.map((a) => [a.key, a.has, a.room, a.mll, a.dll, a.dllUsed, a.risk, a.est])];
  const d = C.buildAccounts(null, fx, null);
  o.demo = [d.demo, d.accounts.map((a) => [a.key, a.has, a.demo, a.room])];
  const e = C.buildAccounts({ accounts: 'x' }, null, null);
  o.empty = [e.demo, e.accounts.every((a) => !a.has), e.accounts.map((a) => a.mll)];
  o.limits = [C.limitsFor('builder_50k', null).mll, C.limitsFor('builder_50k', { limits: { builder_50k: { mll: 2500, dll: 'x', target: -5 } } }).mll, C.limitsFor('builder_50k', { limits: { builder_50k: { mll: 2500, dll: 'x', target: -5 } } }).dll, C.limitsFor('builder_50k', { limits: { builder_50k: { target: -5 } } }).target, C.limitsFor('zzz', 'junk').mll];
  const z = d.accounts[0], at = b.accounts[1];
  o.health = [C.health(z).level, C.health({ ...z, room: 900 }).level, C.health({ ...z, room: 400 }).level, C.health({ ...z, room: 0 }).level, C.health({ ...z, dllUsed: 850 }).level, C.health({ ...z, dllUsed: 550 }).level, C.health(b.accounts[2]).level, C.health(null).level, C.health(at).level];
  o.rim = [C.rimFraction(z), C.rimFraction(b.accounts[2]), C.rimFraction(at), C.shieldOf(z).rim, C.shieldOf(b.accounts[2]).rim];
  const w = C.whatIf(z, 425), w2 = C.whatIf(z, 1500), w3 = C.whatIf(z, 1420), w4 = C.whatIf(b.accounts[2], 100), wd = C.whatIf(z, null);
  o.what = [w.left, w.level, w.text, w2.left, w2.level, w3.level, w4.ok, w4.lines.length, wd.risk, wd.text.includes('(-$425 (-1.0R)') || wd.text.includes('-$425'), C.whatIf(z, 'abc').risk, C.whatIf(z, -300).risk];
  const wa = C.whatIf({ ...z, dllUsed: 700 }, 425);
  o.dayend = [wa.level, wa.lines.some((l) => l.includes('daily loss'))];
  o.lock = C.lockouts({ ...z, dllUsed: 700, today: -900, room: 450 }).map((l) => [l.id, l.level]);
  o.lock0 = C.lockouts(z).map((l) => l.level);
  o.lockNo = [C.lockouts(b.accounts[2]).length, C.lockouts(null).length];
  o.lockTarget = C.lockouts({ ...z, toTarget: 0 }).find((l) => l.id === 'target').level;
  o.lockFunded = C.lockouts({ ...z, kind: 'funded', today: 800, week: 1000 }).find((l) => l.id === 'cons').level;
  const rl = C.ruleLines(z), rl25 = C.ruleLines(at);
  o.rules = [rl.length, rl[0].includes('$2,000') && rl[0].includes('$100 above the start'), rl[1].includes('$1,000') && rl[1].includes('soft'), rl[2].includes('16:10 ET'), rl[3].includes('40 micros'), rl[4].includes('$3,000'), rl[5].includes('$500 to $2,000') && rl[5].includes('50%'), rl25[0].includes('$1,000'), rl25[1].includes('$600'), rl25[3].includes('20 micros')];
  o.say = [C.sayLine(z), C.sayLine(b.accounts[2])];
  const card = C.jarvisCard(z, null);
  o.card = [card.name, card.level, card.room, card.mll, card.line.startsWith('If the next trade is a full stop')];
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
    check("b. words: $2,000, -$60, every dollar with its R (-1.0R, ~-1.0R when the stop is an estimate), the exact drawdown sentence, 16:10",
          o["words"] == ["$2,000", "-$60", "-1.0R", "~-1.0R", "-$425 (-1.0R)", "Drawdown left $1,420 of $2,000 max loss", "16:10", "16:10"], o["words"])
    check("b. account matching: acct_c -> BLITZ, ATLAS, mffu50k -> Zlarior, unknown and null -> none", o["match"] == ["blitz", "atlas", "zlarior", None, None], o["match"])
    check("b. real home.json: not demo; Zlarior $1,420 of $2,000, $100 daily used, the plan's 425 stand-in (estimate); ATLAS $240 of $1,000, its own average loss $150 (real); BLITZ has no row (no numbers, never invented)",
          o["build"][0] is False and o["build"][1] == [["zlarior", True, 1420, 2000, 1000, 100, 425, True], ["atlas", True, 240, 1000, 600, 60, 150, False], ["blitz", False, None, 1000, 600, 0, 120, True]], o["build"])
    check("b. no home.json: the fixture rows show as DEMO (Zlarior and BLITZ; ATLAS has no row)", o["demo"] == [True, [["zlarior", True, True, 1420], ["atlas", False, False, None], ["blitz", True, True, 560]]], o["demo"])
    check("b. nothing at all: three empty shields with the plan's max loss, never a crash", o["empty"] == [True, True, [2000, 1000, 1000]], o["empty"])
    check("b. limits: ledger/rules.json overrides good numbers only; junk and an unknown plan fall back", o["limits"] == [2000, 2500, 1000, 3000, 2000], o["limits"])
    check("b. health: safe / getting close (<50%) / very close (<25%) / used up / daily loss at 80% / at 50% / no numbers / none / ATLAS with $240 of $1,000 (bad)",
          o["health"] == ["ok", "warn", "bad", "bad", "bad", "warn", "off", "off", "bad"], o["health"])
    check("b. the gold rim is the share of the max loss still there: 71% for Zlarior, none without numbers, 24% for ATLAS", abs(o["rim"][0] - 0.71) < 1e-9 and o["rim"][1] is None and abs(o["rim"][2] - 0.24) < 1e-9 and abs(o["rim"][3] - 0.71) < 1e-9 and o["rim"][4] == 0, o["rim"])
    check("b. what-if: a full -$425 stop leaves $995 of $2,000 (warn, under half), the sentence has the R; a stop bigger than the room is 'bad'; a stop equal to the room is 'bad'; no numbers -> not ok; the default risk is the account's; junk risk -> default; negative is its size",
          o["what"][0] == 995 and o["what"][1] == "warn" and o["what"][2] == "If the next trade is a full stop (-$425 (-1.0R)): you will have $995 left of $2,000 max loss, and $575 of the $1,000 daily loss." and o["what"][3] == 0 and o["what"][4] == "bad" and o["what"][5] == "bad"
          and o["what"][6] is False and o["what"][7] == 0 and o["what"][8] == 425 and o["what"][10] == 425 and o["what"][11] == 300, o["what"])
    check("b. a full stop that would use the daily loss says the day would be over", o["dayend"] == ["warn", True] or o["dayend"][1] is True, o["dayend"])
    check("b. lock-outs on a bad day (daily loss 70%, -$900 today, $450 left): daily-loss stop hit, two-stops hit (warn; three would be over), floor stop is 'bad' (under a quarter), 15:30 / flat rule is a note, target and consistency not hit",
          o["lock"] == [["dll", "warn"], ["two", "warn"], ["floor", "bad"], ["late", "ok"], ["target", "ok"], ["cons", "ok"]], o["lock"])
    check("b. lock-outs on a calm day: nothing is hit", set(o["lock0"]) == {"ok"}, o["lock0"])
    check("b. lock-outs: no numbers -> none; the target reached -> stop; a funded account with a day over 50% of the week -> stop", o["lockNo"] == [0, 0] and o["lockTarget"] == "warn" and o["lockFunded"] == "warn", (o["lockNo"], o["lockTarget"], o["lockFunded"]))
    check("b. the rules in plain words: six lines with the real numbers (50K: $2,000 trailing, lock $100, $1,000 soft daily loss, flat 16:10 ET, 40 micros, $3,000 target, $500-$2,000 payouts, 50% consistency; 25K: $1,000, $600, 20 micros)", all(o["rules"][1:]) and o["rules"][0] == 6, o["rules"])
    check("b. the status sentences", o["say"][0] == "Zlarior 50K: Drawdown left $1,420 of $2,000 max loss. Safe distance." or o["say"][0].startswith("Zlarior 50K: Drawdown left $1,420 of $2,000 max loss."), o["say"])
    check("b. the Jarvis helper card", o["card"][0] == "Aegis" and o["card"][2] == "$1,420" and o["card"][3] == "$2,000" and o["card"][4], o["card"])


def home_json():
    return json.dumps({"accounts": [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "kind": "eval", "eval": {"balance": 50420, "floor": 49000, "room": 1420, "mll": 2000, "dll": 1000, "dll_used": 100}, "pnl": {"today": -100}},
        {"id": "acctb", "name": "ATLAS 25K", "kind": "eval", "eval": {"balance": 24480, "floor": 24240, "room": 240, "mll": 1000, "dll": 600, "dll_used": 60}, "stats": {"avg_loss": -150}}]})


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
            AK.open_app(p, origin, APP, "?demo=1", hook="AEGIS")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, chips: [...document.querySelectorAll('#accts button')].map((b) => b.textContent), on: document.querySelector('#accts [aria-pressed=true]').textContent,
              dd: document.querySelector('#dd').textContent, pill: document.querySelector('#pill').textContent, tiles: document.querySelector('#tiles').textContent, ifl: document.querySelector('#ifLine').textContent,
              locks: document.querySelectorAll('#locks .lock').length, all: document.querySelectorAll('#all .acard').length, rules: document.querySelectorAll('#rules li').length,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, mode: window.AEGIS.mode, risk: document.querySelector('#risk').value })""")
            check("c. DEMO (Zlarior): the chip, three accounts, 'Drawdown left $1,420 of $2,000 max loss', a safe-distance pill (71% left), the what-if '$995 left', 6 lock-out rules, 3 shields, 6 rules, risk 425",
                  d["demo"] and d["chips"] == ["Zlarior 50K", "ATLAS 25K", "BLITZ 25K"] and d["on"] == "Zlarior 50K" and d["dd"] == "Drawdown left $1,420 of $2,000 max loss" and d["pill"] == "Safe distance"
                  and "If the next trade is a full stop (-$425 (-1.0R)): you will have $995 left of $2,000 max loss" in d["ifl"] and d["locks"] == 6 and d["all"] == 3 and d["rules"] == 6 and d["risk"] == "425" and "Daily loss left$1,000" in d["tiles"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the shield is 3D or the flat drawing, never nothing: the canvas XOR the svg is visible", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#flat').hasAttribute('hidden')"), d["mode"])
            rim = p.evaluate("() => document.querySelector('#flat path.rim').getAttribute('stroke-dasharray')")
            check("c. the flat shield's gold rim is 71% of the shield for $1,420 of $2,000", rim.startswith("71 "), rim)
            AK.shot(p, "aegis-demo")
            p.locator("#accts [data-acct=atlas]").click()
            p.wait_for_timeout(200)
            a = p.evaluate("() => [document.querySelector('#dd').textContent, document.querySelector('#pill').textContent, document.querySelector('#risk').value, document.querySelector('#flat path.rim').getAttribute('stroke-dasharray'), [...document.querySelectorAll('#locks .lock')].map((l) => l.className)]")
            check("c. tap ATLAS: 'Drawdown left $840 of $1,000 max loss', its own stop $150, a rim of 84%, the daily-loss stop is hit (60% used)", a[0] == "Drawdown left $840 of $1,000 max loss" and a[2] == "150" and a[3].startswith("84") and "warn" in a[4][0], a)
            p.fill("#risk", "900")
            p.wait_for_timeout(150)
            w = p.evaluate("() => [document.querySelector('#ifLine').textContent, document.querySelector('#status').textContent]")
            check("c. type a $900 stop on ATLAS ($840 left): 'you will have $0 left', the page warns it is over the floor, the status line is spoken", "you will have $0 left" in w[0] and "-$900 (-6.0R)" in w[0] and "Do not take it" in p.evaluate("() => document.querySelector('#ifLines').textContent") and "you will have $0 left" in w[1], w)
            p.locator("#riskUp").click()
            p.wait_for_timeout(100)
            v = p.evaluate("() => document.querySelector('#risk').value")
            check("c. the +25 button: 900 -> 925", v == "925", v)
            p.locator("#quick [data-risk='75']").click()
            p.wait_for_timeout(100)
            v = p.evaluate("() => [document.querySelector('#risk').value, document.querySelector('#ifLine').textContent]")
            check("c. the 'Half stop' chip: $75, you will have $765 left", v[0] == "75" and "you will have $765 left" in v[1], v)
            p.locator("#all [data-acct=blitz]").click()
            p.wait_for_timeout(200)
            bz = p.evaluate("() => document.querySelector('#dd').textContent")
            check("c. tap BLITZ in the list of three: 'Drawdown left $560 of $1,000 max loss'", bz == "Drawdown left $560 of $1,000 max loss", bz)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=high&acct=blitz&risk=300", hook="AEGIS")
            hq = p.evaluate("() => [window.AEGIS.mode, getComputedStyle(document.querySelector('#flat')).display, document.querySelector('#risk').value, document.querySelector('#accts [aria-pressed=true]').textContent]")
            check("c. ?q=high&acct=blitz&risk=300 opens BLITZ with a $300 stop; the 3D shield builds and the flat drawing is hidden (or, with no WebGL, the flat shield stays), no console error",
                  hq[2] == "300" and hq[3] == "BLITZ 25K" and ((hq[0] == "3d" and hq[1] == "none") or (hq[0] == "flat" and hq[1] != "none")) and not errs, (hq, errs[:2]))
            ctx.close()

            srv2, origin2 = AK.serve({"/home.json": home_json()})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?acct=atlas", hook="AEGIS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#dd').textContent, document.querySelector('#risk').value, document.querySelector('#ifLine').textContent]")
            check("c. the real home.json: no DEMO chip, ATLAS 'Drawdown left $240 of $1,000 max loss', its real average loss $150, the what-if 'you will have $90 left'", not r[0] and r[1] == "Drawdown left $240 of $1,000 max loss" and r[2] == "150" and "you will have $90 left" in r[3], r)
            check("c. the real run reads home.json and rules.json only, no console error", any("home.json" in u for u in seen) and any("rules.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()

            srv3, origin3 = AK.serve({"/home.json": '{"accounts": "junk"}', "/ledger/rules.json": "not json"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "", hook="AEGIS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#dd').textContent]")
            check("c. a broken home.json and rules.json never blank the page: the fixture shows with the DEMO chip and the built-in limits", r == [True, "Drawdown left $1,420 of $2,000 max loss"] and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low", hook="AEGIS")
            mode = p.evaluate("() => window.AEGIS.mode")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the flat shield, no sideways scroll, every tap >= 44 px, no error", mode == "flat" and AK.no_sideways(p) and not AK.taps(p) and not errs, (mode, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "aegis-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
