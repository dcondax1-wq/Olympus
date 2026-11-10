"""PNYX, the OLYMPUS rules and risk calculator (tools/web_public/pnyx/, AGORA look, 2026-11-10): type a stop in points -> micros, $ risk (with R), daily loss left, trailing floor, target distance, prices.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the built-in limits equal MFFU's file (research/lit/mffu_rules.json), the owner's real prices
  b. the maths in node (pnyxcore.js): the size rule to the micro, the trailing floor and its lock, the daily loss, the cap, no-trade cases, the target path, the ladder, limits overrides, live account reading
  c. Chromium 390 x 844 (and 375 x 667): the DEMO case, typing a stop, +/- buttons, the plan chips, the real home.json, ?plan=&stop=&share=, LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_pnyx_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "pnyx", "Pnyx"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../ledger/rules.json"))
    core = AK.read(os.path.join(AK.WEB, APP, "pnyxcore.js"))
    rules = json.load(open(os.path.join(AK.ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))["limits"]
    mine = {}
    for plan in ("builder_50k", "builder_25k"):
        blk = re.search(plan + r": \{([^}]*)\}", core.split("DEFAULT_LIMITS = ")[1]).group(1)
        mine[plan] = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+)", blk)}
    same = all(abs(mine[p][k] - rules[p][k]) < 1e-9 for p in mine for k in mine[p] if k in rules[p]) and all(mine[p]["comm_rt_micro"] == rules[p]["comm_rt_micro"] for p in mine)
    check("a. the built-in limits (used when ledger/rules.json is missing) equal research/lit/mffu_rules.json: target, max loss, daily loss, micro limit, buffer, payouts, commission", same, mine)
    prices = re.findall(r"(b50|b25|atlas): \{[^}]*?price: ([\d.]+)", core)
    check("a. the owner's real prices: Builder 50K $91.80, Builder 25K $63, ATLAS 25K $43 (CLAUDE.md)", dict(prices) == {"b50": "91.8", "b25": "63", "atlas": "43"}, prices)
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page order: account, the stop, the answer, drawdown, target, the ladder, price, rules", html.index('id="plans"') < html.index('id="stop"') < html.index('id="answer"') < html.index('id="floorCard"') < html.index('id="tgtCard"') < html.index('id="ladCard"') < html.index('id="priceCard"') < html.index('id="rules"'))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.words = [C.money(2000), C.moneyS(-60), C.rText(-964, 964), C.rText(7710, 964), C.both(-60, 150, true), C.drawdownLine(1420, 2000), C.price(91.8), C.price(43), C.fmtPts(20.1), C.fmtPts(299.75)];
  const a = C.calc('b50', { stop: 20 }, null);
  o.base = [a.micros, Math.round(a.risk * 100) / 100, a.limiter, a.floor, a.room, a.widest1, a.dllLeft, a.level, Math.round(a.perMicro * 100) / 100, a.roomAfter > 1035 && a.roomAfter < 1037];
  const b = C.calc('b50', { stop: 20, balance: 50420, best: 51000 }, null);
  o.mid = [b.micros, b.limiter, b.floor, b.room, b.toTarget, b.passed, Math.round(b.ptsToTarget), b.wins.map((w) => w.wins), b.level];
  o.trail = [C.trailingFloor(50000, 50000, 2000, 100), C.trailingFloor(50000, 51000, 2000, 100), C.trailingFloor(50000, 52500, 2000, 100), C.trailingFloor(50000, 49000, 2000, 100), C.calc('b50', { balance: 52600, best: 52600 }, null).locked, C.calc('b50', { balance: 50000 }, null).locked];
  const c25 = C.calc('b25', { stop: 30 }, null), atl = C.calc('atlas', { stop: 20 }, null);
  o.p25 = [c25.micros, c25.limiter, c25.dll, c25.mll, c25.target, atl.name, atl.micros];
  const tight = C.calc('b50', { stop: 0.25 }, null);
  o.cap = [tight.micros, tight.limiter, tight.maxMicros];
  const wide = C.calc('b25', { stop: 400 }, null);
  o.none = [wide.micros, wide.level, wide.risk, wide.widest1, wide.lines.length, wide.lines[0].startsWith('No room for even 1 micro'), wide.wins.map((w) => w.wins)];
  const dead = C.calc('b50', { balance: 48000, best: 50000 }, null);
  o.dead = [dead.dead, dead.micros, dead.room, dead.lines.length, dead.roomFrac];
  const hit = C.calc('b50', { stop: 20, lost: 1000 }, null), part = C.calc('b50', { stop: 20, lost: 500 }, null);
  o.daily = [hit.micros, hit.dllLeft, hit.lines.length, part.micros, part.dllLeft, part.limiter];
  o.shares = C.SHARES.map((s) => C.calc('b50', { stop: 20, balance: 50420, best: 51000, share: s }, null).micros);
  o.junk = [C.calc('b50', { stop: 'x', share: 99, balance: -5, lost: 'abc' }, null).stop, C.calc('b50', { share: 99 }, null).share, C.calc('b50', { stop: 9999 }, null).stop, C.calc('nope', {}, null).name, C.calc('b50', null, null).micros];
  const lad = C.ladder('b50', { balance: 50420, best: 51000 }, null);
  o.lad = [lad.map((r) => r.stop), lad.map((r) => r.micros), lad.every((r, i) => i === 0 || r.micros <= lad[i - 1].micros), lad.every((r) => r.risk <= 852.0001)];
  const rules = { limits: { builder_50k: { dll: 'x', mll: 2500, target: -5, comm_rt_micro: 1 } } };
  o.limits = [C.limitsFor('builder_50k', null).mll, C.limitsFor('builder_50k', rules).mll, C.limitsFor('builder_50k', rules).dll, C.limitsFor('builder_50k', rules).target, C.limitsFor('builder_50k', rules).comm_rt_micro, C.limitsFor('builder_25k', 'junk').mll, C.limitsFor('zzz', null).mll];
  o.rulesOverride = C.calc('b50', { stop: 20 }, rules).floor;
  const home = { accounts: [{ id: 'mffu50k_eval', eval: { balance: 50420, floor: 49000, room: 1420, mll: 2000, dll_used: 100 } }, { id: 'acctb', name: 'ATLAS 25K', eval: { balance: 24480, room: 240, mll: 1000, dll_used: 60 } }] };
  const l50 = C.liveFor('b50', home), lat = C.liveFor('atlas', home);
  o.live = [l50 && [l50.balance, l50.best, l50.lost, l50.room], lat && [lat.balance, lat.best, lat.lost, lat.room], C.liveFor('b25', home), C.liveFor('b50', null), C.liveFor('b50', { accounts: [{ id: 'mffu50k_eval' }] }), C.liveFor('b50', { accounts: 'x' })];
  const cl = C.calc('atlas', { stop: 20, balance: 24480, best: 25240, lost: 60 }, null);
  o.liveCalc = [cl.floor, cl.room, cl.dllLeft, cl.micros, Math.round(cl.risk), C.drawdownLine(cl.room, cl.mll)];
  const dflt = C.defaults('b50', null, { home });
  o.dflt = [dflt.live, dflt.demo, dflt.inp.balance, dflt.inp.best, C.defaults('b50', home, null).live, C.defaults('b25', null, { home }).demo, C.defaults('b25', null, null).inp.balance];
  const pl = C.priceLines('b50', null), p2 = C.priceLines('atlas', null), rl = C.ruleLines('b25', null);
  o.price = [pl[0], pl[1].includes('$91.80'), pl[2].includes('$400') && pl[2].includes('4.4 times'), p2[0].startsWith('Your price $43.00'), rl.length, rl[0].includes('$1,000') && rl[0].includes('never moves down'), rl[2].includes('$1,500') && rl[2].includes('20 micro')];
  const card = C.jarvisCard(a);
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.lines[0], Number.isInteger(card.t)];
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
    check("b. words: $2,000, -$60, every dollar has its R (-1.0R, +8.0R, an estimate wears a ~), the exact drawdown sentence, prices with cents, points trimmed to a quarter",
          o["words"] == ["$2,000", "-$60", "-1.0R", "+8.0R", "-$60 (~-0.4R)", "Drawdown left $1,420 of $2,000 max loss", "$91.80", "$43.00", "20", "299.75"], o["words"])
    check("b. Builder 50K, 20-pt stop, fresh account: budget = the smaller of 60% of $2,000 and the $1,000 daily loss -> 23 micros, $963.70 at risk, held by the daily loss; floor $48,000; the widest 1-micro stop is 499 pts",
          o["base"] == [23, 963.7, "daily", 48000, 2000, 499, 1000, "ok", 41.9, True], o["base"])
    check("b. a trailed account (balance $50,420, best day $51,000): floor $49,000, $1,420 left -> 20 micros held by the room, $2,580 to the target, 3 wins of 1.5R, 2 of 3R or 1 of 8R finish it",
          o["mid"] == [20, "room", 49000, 1420, 2580, False, 65, [3, 2, 1], "ok"], o["mid"])
    check("b. the trailing floor: fresh $48,000; best $51,000 -> $49,000; $52,500 -> locked at start + $100 = $50,100; a lower best never lowers it; the lock flag", o["trail"] == [48000, 49000, 50100, 48000, True, False], o["trail"])
    check("b. Builder 25K (20 micros, $600 daily loss, $1,000 max loss, $1,500 target) and ATLAS 25K use the 25K rules", o["p25"] == [9, "room", 600, 1000, 1500, "ATLAS 25K", 14], o["p25"])
    check("b. a very tight stop hits the plan's micro limit (40 on the 50K) and says so", o["cap"] == [40, "cap", 40], o["cap"])
    check("b. a stop too wide for the room: 0 micros, red, $0 risk, the widest stop that fits is named, two sentences, never a made-up size", o["none"] == [0, "bad", 0, 299, 2, True, [None, None, None]], o["none"])
    check("b. a blown floor: dead, 0 micros, $0 left, one sentence", o["dead"] == [True, 0, 0, 1, 0], o["dead"])
    check("b. the daily loss: lost $1,000 -> no size; lost $500 -> $500 left -> 11 micros held by the daily loss", o["daily"][:3] == [0, 0, 2] and o["daily"][3:] == [11, 500, "daily"], o["daily"])
    check("b. share of the drawdown left (40 / 60 / 80%) on $1,420 left: 13 / 20 / 23 micros (the 80% case is held by the $1,000 daily loss)", o["shares"] == [13, 20, 23], o["shares"])
    check("b. junk input is clamped, never a NaN: bad stop -> 20, share > 1 -> 1, stop capped at 500, unknown plan -> Builder 50K, null input works", o["junk"] == [20, 1, 500, "Builder 50K", 23], o["junk"])
    check("b. the ladder: the size follows the stop (never more micros for a wider stop) and no row risks more than the budget", o["lad"][0] == [10, 15, 20, 30, 40, 60] and o["lad"][2] and o["lad"][3] and o["lad"][1][0] >= o["lad"][1][-1], o["lad"])
    check("b. limits: ledger/rules.json overrides good values only (bad daily loss and negative target ignored), junk rules and an unknown plan fall back; the override moves the floor", o["limits"] == [2000, 2500, 1000, 3000, 1, 1000, 1000] and o["rulesOverride"] == 47500, (o["limits"], o["rulesOverride"]))
    check("b. live account from home.json: Zlarior $50,420 / floor $49,000 / best $51,000 / $100 lost; ATLAS from balance and room; the plain 25K has none; missing data -> null", o["live"][0] == [50420, 51000, 100, 1420] and o["live"][1] == [24480, 25240, 60, 240] and o["live"][2:] == [None, None, None, None], o["live"])
    check("b. a live account rebuilds the same floor, room, daily loss: ATLAS $240 of $1,000, $540 daily left, 3 micros, $126 at risk", o["liveCalc"] == [24240, 240, 540, 3, 126, "Drawdown left $240 of $1,000 max loss"], o["liveCalc"])
    check("b. defaults: the fixture gives a DEMO account only when home.json is missing; a fresh plan starts at its start balance", o["dflt"] == [False, True, 50420, 51000, True, False, 25000], o["dflt"])
    check("b. the price words: your price, the fee a failure costs, the payout pays it back 4.4 times; ATLAS $43.00; the 25K rules name $1,000, $1,500 and 20 micros", o["price"][0].startswith("Your price $91.80, one time, $0 activation") and all(o["price"][1:]), o["price"])
    check("b. the Jarvis card: Pnyx, a level, 3 kpis, the drawdown sentence, an integer t", o["card"][0] == "Pnyx" and o["card"][1] == "ok" and o["card"][2] == 3 and o["card"][3] == "23" and o["card"][4].startswith("Drawdown left $2,000 of $2,000 max loss on Builder 50K") and o["card"][5], o["card"])


def home_json():
    return json.dumps({"accounts": [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "kind": "eval", "eval": {"balance": 50420, "floor": 49000, "room": 1420, "mll": 2000, "dll": 1000, "dll_used": 100}},
        {"id": "acctb", "name": "ATLAS 25K", "kind": "eval", "eval": {"balance": 24480, "floor": 24240, "room": 240, "mll": 1000, "dll": 600, "dll_used": 60}}]})


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
            AK.open_app(p, origin, APP, "?demo=1")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, plans: [...document.querySelectorAll('#plans button')].map((b) => b.textContent), on: document.querySelector('#plans [aria-pressed=true]').textContent,
              micros: document.querySelector('#micros').textContent, dd: document.querySelector('#dd').textContent, pill: document.querySelector('#ansPill').textContent, tiles: document.querySelector('#tiles').textContent,
              facts: document.querySelector('#facts').textContent, tgt: document.querySelector('#tgt').textContent, rows: document.querySelectorAll('#ladRows tr').length, price: document.querySelector('#price').textContent,
              rules: document.querySelectorAll('#rules li').length, stop: document.querySelector('#stop').value, shares: [...document.querySelectorAll('#shares button')].map((b) => b.textContent), font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor })""")
            check("c. DEMO (20-pt stop, $50,420 balance, floor $49,000): the chip, three accounts, 20 micros, 'Drawdown left $1,420 of $2,000 max loss', a safe-distance pill, loss -$838 with -1.0R and +$6,704 with +8.0R",
                  d["demo"] and d["plans"] == ["Builder 50K", "Builder 25K", "ATLAS 25K"] and d["on"] == "Builder 50K" and d["micros"] == "20 micros" and d["dd"] == "Drawdown left $1,420 of $2,000 max loss" and d["pill"] == "Safe distance"
                  and "-$838" in d["tiles"] and "-1.0R" in d["tiles"] and "+$6,704" in d["tiles"] and "+8.0R" in d["tiles"], d)
            check("c. floor and daily loss facts, the target ($2,580 to go, in R and points), the ladder (6 rows), your price $91.80, five rules, 20-pt stop, 40 / 60 / 80%",
                  "Trailing floor$49,000" in d["facts"] and "Daily loss left$1,000 of $1,000" in d["facts"] and "Still to make$2,580" in d["tgt"] and "R at this risk" in d["tgt"] and d["rows"] == 6 and "$91.80" in d["price"] and d["rules"] == 5 and d["stop"] == "20" and d["shares"] == ["40%", "60%", "80%"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "pnyx-demo")
            p.fill("#stop", "40")
            p.wait_for_timeout(150)
            s = p.evaluate("() => ({ m: document.querySelector('#micros').textContent, lad: document.querySelectorAll('#ladRows tr.me').length, rows: document.querySelectorAll('#ladRows tr').length, st: document.querySelector('#status').textContent })")
            check("c. type a 40-pt stop: 10 micros, the ladder row is highlighted (40 is already on the ladder, so 6 rows), the status line is spoken", s["m"] == "10 micros" and s["lad"] == 1 and s["rows"] == 6 and "10 micros" in s["st"] and "40-point" in s["st"], s)
            p.fill("#stop", "37")
            p.locator("#stopUp").click()
            p.wait_for_timeout(150)
            s = p.evaluate("() => [document.querySelector('#stop').value, document.querySelector('#micros').textContent, document.querySelectorAll('#ladRows tr').length]")
            check("c. the +5 button: 37 -> 42 pts, 9 micros, the odd stop is added to the ladder (7 rows)", s == ["42", "9 micros", 7], s)
            p.locator("#shares [data-share='0.4']").click()
            p.wait_for_timeout(100)
            s = p.evaluate("() => [document.querySelector('#micros').textContent, document.querySelector('#shares [aria-pressed=true]').textContent]")
            check("c. tap 40%: fewer micros (6) for the same stop", s == ["6 micros", "40%"], s)
            p.fill("#stop", "300")
            p.wait_for_timeout(100)
            n = p.evaluate("() => [document.querySelector('#micros').textContent, document.querySelector('#ansPill').textContent, document.querySelector('#lines').textContent]")
            check("c. a stop too wide: '0 micros', 'No trade', and the page names the widest stop that fits (never blank, never a bigger size)", n[0] == "0 micros" and n[1] == "No trade" and "widest stop" in n[2] and "No room for even 1 micro" in n[2], n)
            p.locator("#plans [data-plan=atlas]").click()
            p.wait_for_timeout(150)
            a = p.evaluate("() => ({ n: document.querySelector('#planNote').textContent, dd: document.querySelector('#dd').textContent, price: document.querySelector('#price').textContent, bal: document.querySelector('#bal').value })")
            check("c. tap ATLAS 25K: your price $43.00, 25K start balance, 'Drawdown left $1,000 of $1,000 max loss'", "$43.00" in a["n"] and a["dd"] == "Drawdown left $1,000 of $1,000 max loss" and "$43.00" in a["price"] and a["bal"] == "25000", a)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, inputs, the +/- buttons, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&plan=b25&stop=15&share=0.8")
            q = p.evaluate("() => [document.querySelector('#plans [aria-pressed=true]').textContent, document.querySelector('#stop').value, document.querySelector('#shares [aria-pressed=true]').textContent, document.querySelector('#micros').textContent]")
            check("c. ?plan=b25&stop=15&share=0.8 opens that case (a link from another app lands on the right numbers): Builder 25K, 15 pts, 80%, 18 micros", q == ["Builder 25K", "15", "80%", "18 micros"], q)
            ctx.close()
            srv2, origin2 = AK.serve({"/home.json": home_json()})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?plan=atlas")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, dd: document.querySelector('#dd').textContent, m: document.querySelector('#micros').textContent, bal: document.querySelector('#bal').value, lost: document.querySelector('#lost').value, src: document.querySelector('#srcNote').textContent })")
            check("c. the real home.json: no DEMO chip, ATLAS balance $24,480 and $60 lost from the file -> 'Drawdown left $240 of $1,000 max loss', 3 micros, the note says it is filled from the live account",
                  not r["demo"] and r["dd"] == "Drawdown left $240 of $1,000 max loss" and r["m"] == "3 micros" and r["bal"] == "24480" and r["lost"] == "60" and "live account" in r["src"], r)
            check("c. the real run reads only the site's files and no console error", any("home.json" in u for u in seen) and any("rules.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
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
