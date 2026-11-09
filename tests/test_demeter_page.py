"""DEMETER, the OLYMPUS account-health screen (tools/web_public/demeter/, AGORA look, 2026-11-09): a risk dial per account, the payout rules, the what-if size.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, its built-in limits equal MFFU's file (research/lit/mffu_rules.json)
  b. the maths in node (demetercore.js): money + R words, the dial geometry, the limits, the what-if (every multiplier), the payout dates and path, the rule words
  c. Chromium 390 x 844 (and 375 x 667): the DEMO dials, the real home.json, switching account and size, LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_demeter_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "demeter", "Demeter"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../ledger/rules.json", "../plutus/roadmap.json"))
    core = AK.read(os.path.join(AK.WEB, APP, "demetercore.js"))
    rules = json.load(open(os.path.join(AK.ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))["limits"]
    mine = {}
    for plan in ("builder_50k", "builder_25k"):
        blk = re.search(plan + r": \{([^}]*)\}", core.split("DEFAULT_LIMITS")[1]).group(1)
        mine[plan] = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+)", blk)}
    same = all(abs(mine[p][k] - rules[p][k]) < 1e-9 for p in mine for k in mine[p] if k in rules[p])
    check("a. the built-in limits (used when ledger/rules.json is missing) equal research/lit/mffu_rules.json: max loss, daily loss, buffer, payout min / max, split, consistency", same, (mine, {p: rules[p] for p in rules}))
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page order: the three dials, the selected dial, the what-if, the payouts, the rules", html.index('id="pick"') < html.index('id="dialCard"') < html.index('id="wiCard"') < html.index('id="payCard"') < html.index('id="rules"'))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.words = [C.money(2000), C.moneyS(-60), C.rText(-425, 425), C.rText(640, 425), C.rText(150, 150, true), C.both(-60, 150, true), C.drawdownLine(1420, 2000)];
  const rules = { limits: { builder_50k: { mll: 2500, dll: 'x', buffer: -5, pay_min: 600 } } };
  o.limits = [C.limitsFor('builder_50k', null).mll, C.limitsFor('builder_50k', rules).mll, C.limitsFor('builder_50k', rules).dll, C.limitsFor('builder_50k', rules).buffer, C.limitsFor('builder_50k', rules).pay_min, C.limitsFor('builder_25k', 'junk').mll, C.limitsFor('zzz', null).mll];
  const d1 = C.dial(1), d5 = C.dial(0.5), d0 = C.dial(0);
  o.dial = { end1: [d1.end.x, d1.end.y], end5: [d5.end.x, d5.end.y], d0: [d0.arc, d0.pct, d0.level], over: C.dial(7).pct, under: C.dial(-3).pct, nan: C.dial(null).pct, lv: [C.levelOf(0.24), C.levelOf(0.25), C.levelOf(0.49), C.levelOf(0.5)], track: d1.track.startsWith('M20 100 A80 80') };
  const real = { accounts: [{ id: 'mffu50k_eval', name: 'MFFU 50K Eval', kind: 'eval', eval: { room: 1420, mll: 2000, floor: 48580, balance: 50420, start_balance: 50000, locked: false, today: 312, to_target: 2580, progress: 0.14, dll: 1000, dll_used: 100 }, pnl: { today: 312, week: 640 }, stats: { avg_loss: -425, avg_win: 640 } },
    { id: 'acctb', name: 'ATLAS', eval: { room: 240, mll: 1000 }, pnl: {}, stats: {} }, { id: 'acct_c', name: 'BLITZ', kind: 'funded' }] };
  const b = C.buildAccounts(real, null, null), z = b.accounts[0], a = b.accounts[1], bl = b.accounts[2];
  o.acc = { demo: b.demo, z: [z.room, z.mll, z.floor, z.risk, z.win, z.est, z.dllUsed, z.dll, z.toTarget], a: [a.room, a.risk, a.est, a.L.mll, a.plan], bl: [bl.has, bl.stage, bl.room] };
  const dm = C.buildAccounts({ accounts: [] }, null, { accounts: [{ key: 'atlas', room: 840, mll: 1000, risk: 150, win: 210 }] });
  o.demo = [dm.demo, dm.accounts.map((x) => x.has), dm.accounts[1].room, dm.accounts[1].L.max_micros];
  o.health = [C.health(z).level, C.health(a).level, C.health(bl).text, C.health({ has: false }).text, C.health({ ...z, room: 400 }).level];
  const facts = C.dialFacts(z); o.facts = facts.map((f) => f[0] + '=' + f[1]);
  // the what-if: the arithmetic, exactly
  const W = (m, acc) => C.whatIf(acc || z, m);
  const w1 = W(1), w2 = W(2), wh = W(0.5), edge = W(1, { ...z, room: 850 });
  o.wi = { x1: [w1.stops, w1.dayStops, Math.round(w1.share * 100), w1.winsToTarget, w1.level, w1.lossR, w1.winR], x2: [w2.stops, w2.dayStops, w2.level, w2.lossR], xh: [wh.stops, wh.level, wh.dayStops], edge: edge.stops, lines: w1.lines.length, bad: [W('x').mult, W(99).mult, W(0).mult], note: [w1.note.startsWith('This is the size'), w2.note.includes('thought experiment'), wh.note.includes('smaller')],
            noRoom: W(1, { ...a, room: null }).stops, noRoomLines: W(1, { ...a, room: null }).lines.length };
  o.mults = C.MULTS;
  // payouts
  const road = { conservative: 'H2', accounts: [{ id: 'atlas25', H2: { first: ['2026-11-24', '2026-12-21', '2027-02-22'] } }, { id: 'bad', H2: { first: ['x', 'y'] } }] };
  const f1 = C.firstPayout(road, 'atlas25', '2026-11-09'), f2 = C.firstPayout(road, 'atlas25', '2027-03-01');
  o.pay = { f1: [f1.days, f1.daysEarly, f1.daysLate, f1.passed, f1.text.startsWith('Typical first payout in 42 days')], f2: [f2.passed, f2.text.includes('is here')], none: [C.firstPayout(road, 'zzz', '2026-11-09'), C.firstPayout(road, 'bad', '2026-11-09'), C.firstPayout(null, 'atlas25', '2026-11-09')], days: C.daysBetween('2026-11-09', '2026-12-21'), dbad: C.daysBetween('x', 'y') };
  const pz = C.payoutPath(z), pf = C.payoutPath({ ...z, stage: 'funded' });
  o.path = [pz.length, pz[0].includes('$3,000') && pz[0].includes('$2,580'), pz[1].includes('$2,600'), pz[2].includes('$400 to $1,600'), pf.length];
  const rl = C.ruleLines(z.L, 'eval'), rb = C.ruleLines(z.L, 'both');
  o.rules = [rl.length, rb.length, rl[0].includes('Max loss $2,000') && rl[0].includes('never moves down'), rb[4].includes('$500 to $2,000') && rb[4].includes('80%') && rb[4].includes('$2,100'), rb[5].includes('50%') && rb[5].includes('5 payouts')];
  const card = C.jarvisCard(b.accounts);
  o.card = [card.name, card.status.level, card.kpis.length, card.lines[0], card.t];
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
    check("b. words: $2,000, -$60, every dollar has its R (-1.0R, +1.5R, an estimate wears a ~), the exact drawdown sentence",
          o["words"] == ["$2,000", "-$60", "-1.0R", "+1.5R", "~+1.0R", "-$60 (~-0.4R)", "Drawdown left $1,420 of $2,000 max loss"], o["words"])
    check("b. limits: the built-in numbers, then ledger/rules.json overrides good values only (a bad daily loss and a negative buffer are ignored), junk input and an unknown plan fall back",
          o["limits"] == [2000, 2500, 1000, 2100, 600, 1000, 1000], o["limits"])
    d = o["dial"]
    check("b. the dial: full = the right end, half = the top, empty = no arc; out-of-range / null values are clamped; 24% bad, 25% warn, 49% warn, 50% ok",
          d["end1"] == [180, 100] and d["end5"] == [100, 20] and d["d0"] == ["", 0, "bad"] and d["over"] == 100 and d["under"] == 0 and d["nan"] == 0 and d["lv"] == ["bad", "warn", "warn", "ok"] and d["track"], d)
    a = o["acc"]
    check("b. accounts from home.json: Zlarior 1420 of 2000, floor, 1R = its average loss 425 (not an estimate), daily loss 100 of 1000; ATLAS 240 of 1000 with the 25K plan and the plan's risk (~); BLITZ funded has no drawdown",
          not a["demo"] and a["z"] == [1420, 2000, 48580, 425, 640, False, 100, 1000, 2580] and a["a"] == [240, 150, True, 1000, "builder_25k"] and a["bl"] == [True, "funded", None], a)
    check("b. no real account -> DEMO from the fixture; the other cards say 'no numbers yet'; health words per case", o["demo"] == [True, [False, True, False], 840, 20] and o["health"] == ["ok", "bad", "Funded: see the payout rules", "No numbers yet", "bad"], (o["demo"], o["health"]))
    check("b. the dial facts: trailing floor, balance, daily loss left ($900 of $1,000), the target distance, today with its R", o["facts"] == ["Trailing floor=$48,580", "Balance=$50,420", "Daily loss left=$900", "To the target=$2,580", "Today=+$312 (+0.7R)"], o["facts"])
    w = o["wi"]
    check("b. what-if 1x on Zlarior: $1,420 / $425 = 4 stops, 3 losses to the $1,000 daily limit, a 2-loss day = 60% of the room, 5 wins to the target, -1.0R / +1.5R, amber",
          w["x1"] == [4, 3, 60, 5, "warn", "-1.0R", "+1.5R"] and w["lines"] == 4, w["x1"])
    check("b. what-if 2x: 2 stops, 2 daily losses, red, -2.0R; 0.5x: 7 stops, green, 5 daily losses; exactly 2 stops of room stays 2 (no rounding up)", w["x2"] == [2, 2, "bad", "-2.0R"] and w["xh"] == [7, "ok", 5] and w["edge"] == 2, w)
    check("b. what-if limits: sizes are clamped to 0.25x-4x, junk -> 1x; the three notes; no drawdown number -> no stops and fewer lines (never a wrong number)",
          w["bad"] == [1, 4, 1] and w["note"] == [True, True, True] and w["noRoom"] is None and w["noRoomLines"] < 4 and o["mults"] == [0.5, 0.75, 1, 1.5, 2], w)
    p = o["pay"]
    check("b. first payout: 2026-11-09 -> 2026-12-21 is 42 days (early 15, late 105, the words say so); a date in the past says 'is here'; a missing / junk account gives null",
          p["f1"] == [42, 15, 105, False, True] and p["f2"] == [True, True] and p["none"] == [None, None, None] and p["days"] == 42 and p["dbad"] is None, p)
    check("b. the payout path: pass the $3,000 target ($2,580 to go), earn $2,600 (buffer + minimum), a payout of $500 to $2,000 of which you keep $400 to $1,600; a funded account skips step one", o["path"] == [3, True, True, True, 2], o["path"])
    check("b. the rules in words: max loss and 'never moves down', daily loss, size, inactivity; payouts with the 80% split and the buffer; 50% consistency and 5 payouts", o["rules"] == [4, 6, True, True, True], o["rules"])
    check("b. the Jarvis card: Demeter, the worst account sets the level, 3 kpis, one line, an integer t", o["card"][0] == "Demeter" and o["card"][1] == "bad" and o["card"][2] == 3 and o["card"][3].startswith("Drawdown left $240 of $1,000 max loss on ATLAS") and isinstance(o["card"][4], int), o["card"])


def home_json():
    return json.dumps({"accounts": [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "kind": "eval", "eval": {"room": 1420, "mll": 2000, "floor": 48580, "balance": 50420, "start_balance": 50000, "today": 312, "to_target": 2580, "progress": 0.14, "dll": 1000, "dll_used": 100}, "pnl": {"today": 312, "week": 640}, "stats": {"avg_loss": -425, "avg_win": 640}},
        {"id": "acctb", "name": "ATLAS 25K", "kind": "eval", "eval": {"room": 240, "mll": 1000, "floor": 24240, "balance": 25000, "today": -60, "to_target": 1425, "progress": 0.05, "dll": 600, "dll_used": 60}, "pnl": {"today": -60, "week": 140}, "stats": {}}]})


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
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-09T15:00:00Z")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, picks: document.querySelectorAll('#pick .pickbtn').length, sel: document.querySelector('#pick [aria-pressed=true]').dataset.key, dd: document.querySelector('#dd').textContent,
              h: document.querySelector('#dialH').textContent, pill: document.querySelector('#dialPill').textContent, facts: document.querySelector('#facts').textContent, days: document.querySelector('#payDays').textContent,
              chips: [...document.querySelectorAll('#mults button')].map((b) => b.textContent), on: document.querySelector('#mults [aria-pressed=true]').textContent, rules: document.querySelectorAll('#rules li').length,
              arc: document.querySelector('#dialBox svg path:nth-child(2)') ? document.querySelector('#dialBox svg path:nth-child(2)').getAttribute('stroke') : '', font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor }) """)
            check("c. DEMO: the chip, three dials, Zlarior selected with 'Drawdown left $1,420 of $2,000 max loss', a safe-distance pill, the facts, 42 days to the typical first payout, five size chips (1x on), seven rules",
                  d["demo"] and d["picks"] == 3 and d["sel"] == "zlarior" and d["dd"] == "Drawdown left $1,420 of $2,000 max loss" and d["pill"] == "Safe distance" and "Trailing floor" in d["facts"] and "Daily loss left" in d["facts"] and d["chips"] == ["0.5x", "0.75x", "1x", "1.5x", "2x"] and d["on"] == "1x" and d["rules"] == 6, d)
            check("c. AGORA look: serif title, warm dark body, the olive gauge for a safe account", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)" and d["arc"] == "#7f8a52", d)
            AK.shot(p, "demeter-demo")
            p.locator("#pick [data-key=blitz]").click()
            p.locator("#mults [data-m='2']").click()
            p.wait_for_timeout(200)
            s = p.evaluate("""() => ({ h: document.querySelector('#dialH').textContent, dd: document.querySelector('#dd').textContent, wi: document.querySelector('#wiH').textContent, tiles: document.querySelector('#wiTiles').textContent, lines: document.querySelector('#wiLines').textContent,
              status: document.querySelector('#status').textContent, on: document.querySelector('#mults [aria-pressed=true]').textContent, pill: document.querySelector('#dialPill').textContent })""")
            check("c. tap BLITZ and 2x: $560 of $1,000, 'What if BLITZ traded 2x', one loss costs -$240 (-2.0R), 3 stops in a row, the status line is spoken",
                  s["h"] == "BLITZ 25K" and s["dd"] == "Drawdown left $560 of $1,000 max loss" and s["wi"] == "What if BLITZ traded 2x the size?" and "-$240" in s["tiles"] and "-2.0R" in s["tiles"] and "3 stops in a row" in s["lines"] and s["on"] == "2x" and "BLITZ" in s["status"], s)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (dials, chips, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&acct=atlas&size=0.5")
            q = p.evaluate("() => [document.querySelector('#dialH').textContent, document.querySelector('#mults [aria-pressed=true]').textContent, document.querySelector('#payDays').textContent !== '-']")
            check("c. ?acct=atlas&size=0.5 opens ATLAS at 0.5x (a link from another app can land on the right dial)", q == ["ATLAS 25K", "0.5x", True], q)
            ctx.close()
            srv2, origin2 = AK.serve({"/home.json": home_json()})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?at=2026-11-09T15:00:00Z")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, dd: document.querySelector('#dd').textContent, picks: [...document.querySelectorAll('#pick .pickbtn')].map((b) => b.getAttribute('aria-label')), sel: document.querySelector('#pick [aria-pressed=true]').dataset.key })""")
            check("c. the real home.json: no DEMO chip, Zlarior and ATLAS from the file (BLITZ says no numbers yet), the first account that has numbers is selected", not r["demo"] and r["dd"] == "Drawdown left $1,420 of $2,000 max loss" and r["picks"][1].endswith("$240 of $1,000 max loss") and r["picks"][2].endswith("no numbers yet"), r)
            p.locator("#pick [data-key=blitz]").click()
            p.wait_for_timeout(150)
            e = p.evaluate("() => [document.querySelector('#dd').textContent, document.querySelector('#dialPill').textContent, document.querySelector('#wiLines').textContent.length]")
            check("c. an account with no numbers shows 'No numbers yet' and never a made-up dial value; the what-if does not invent stops", e[0].startswith("No numbers yet") and e[1] == "No numbers yet", e)
            check("c. the real run reads only the site's files and no console error", any("home.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
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
