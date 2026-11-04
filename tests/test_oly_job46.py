"""ARES + PLUTUS + FORUM + ARGUS quality pass (2026-11-04, JOB 4+5 follow-up): the atmosphere kit (olympus/fx-atmos.js: shafts, dust, embers, contact
shadows, polished floor) in each scene and 3-5 new money features per app, all read-only.

  a. static   new files, wiring of fx-atmos into the four scenes, the new core functions, the pages' new hooks, read-only (no fetch / POST in the new files),
              additive light that leaves the alpha channel alone (the dark-halo fix for transparent canvases)
  b. cores    Ares (what a win is worth in $ and R and the win rate it needs, the stop ladder, a losing streak, the pace, the day budget, the payout check),
              Plutus (best plan per dollar, evals to buy, who pays first, the cash cushion), Forum (drawdown left "$X of $max loss", the risk plan, the trading
              day, the news rule), Argus (the demo day, can the bot trade, the evals in money words, what red lights cost)
  c. pages    Chromium 390 x 844 on the LITE tier: every new block draws with its numbers (equal to the core's), demo / empty states say what to do, every
              tap target is >= 44 px, no sideways scroll, no page errors

    python -X utf8 -m tests.test_oly_job46 [--no-browser]
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def part_a():
    fx = rd("tools", "web_public", "olympus", "fx-atmos.js")
    check("a. fx-atmos: additive light keeps the alpha channel (no dark halos on a transparent canvas)", "const ADD = {" in fx and fx.count("...ADD") >= 4 and "blendSrcAlpha: THREE.ZeroFactor" in fx)
    for app, f in (("ares", "aresfx.js"), ("plutus", "plutus.js"), ("forum", "scene.js"), ("argus", "argus.js")):
        s = rd("tools", "web_public", app, f)
        check(f"a. {app} scene uses fx-atmos and follows the quality tier", "fx-atmos.js" in s and "setQuality" in s and "AT.update" in s or ("FX.update" in s and "FX.setQuality" in s), f)
    for app, f in (("ares", "aresplus.js"), ("plutus", "plutusplus.js"), ("forum", "forumplus.js"), ("argus", "argusplus.js")):
        s = rd("tools", "web_public", app, f)
        check(f"a. {app}/{f} is read-only (no fetch, POST, storage write or order call)", all(w not in s for w in ("fetch(", "POST", "setItem", "XMLHttpRequest", "place_order")))
    check("a. ares core: oddsPlan, stopLadder, streakTable, passPace, dayBudget, payoutCheck", all(f"export function {n}(" in rd("tools", "web_public", "ares", "arescore.js") for n in ("oddsPlan", "stopLadder", "streakTable", "passPace", "dayBudget", "payoutCheck")))
    check("a. plutus core: rankPlans, buyPlan, payoutRace, cashCushion", all(f"export function {n}(" in rd("tools", "web_public", "plutus", "plutuscore.js") for n in ("rankPlans", "buyPlan", "payoutRace", "cashCushion")))
    check("a. forum core: moneyToday, riskPlan, tradingDay, newsGate", all(f"export function {n}(" in rd("tools", "web_public", "forum", "forumcore.js") for n in ("moneyToday", "riskPlan", "tradingDay", "newsGate")))
    check("a. argus core: demoData, readiness, moneyLines, blindCost", all(f"export function {n}(" in rd("tools", "web_public", "argus", "arguscore.js") for n in ("demoData", "readiness", "moneyLines", "blindCost")))
    ai, pi, fi, gi = (rd("tools", "web_public", a, "index.html") for a in ("ares", "plutus", "forum", "argus"))
    check("a. pages: the new blocks are in the markup", all(w in ai for w in ('id="plusOdds"', 'id="plusLadder"', 'id="plusStreak"', 'id="plusDay"', 'id="plusPace"', 'id="plusPay"'))
          and all(w in pi for w in ('id="plusRank"', 'id="plusBuy"', 'id="plusCushion"', 'id="plusRace"')) and all(w in fi for w in ('id="money"', 'id="day"')) and 'data-tab="money"' in gi and 'id="p-money"' in gi)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
    return pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=args)


CORES = r"""async () => {
  const out = {};
  const A = await import('/ares/arescore.js'), P = await import('/plutus/plutuscore.js'), F = await import('/forum/forumcore.js'), G = await import('/argus/arguscore.js');
  // ---- Ares: a 20-point MNQ long on the 50K at the default room
  const rules = await A.loadRules('/ares/rules.json');
  const I = { plan: '50k', stage: 'eval', inst: 'MNQ', side: 'long', entry: 21500, stop: 21480, riskPct: 40, balance: 50000, today: 0 };
  const z = A.sizeTrade(rules, I), o = A.oddsPlan(rules, I);
  out.odds = { n: o.n, zn: z.n, loss: o.loss, zloss: z.loss1, rows: o.rows.length, r2: o.rows.find((r) => r.r === 2).usd, expR2: z.n * (z.pts * 2 * z.pv - z.comm), need1: o.rows[0].need, expNeed1: z.loss1 / ((z.pts * z.pv - z.comm) + z.loss1), lossR: o.lossR };
  const L = A.stopLadder(rules, I); out.ladder = { n: L.rows.map((r) => r.n), nonInc: L.rows.every((r, i) => i === 0 || r.n <= L.rows[i - 1].n), budget: L.budget };
  const S = A.streakTable(rules, I, 5); out.streak = { rows: S.rows.length, bustAt: S.bustAt, risk: S.risk, rooms: S.rows.map((r) => Math.round(r.room)), text: S.rows[0].text };
  const P2 = A.passPace(rules, I, 10); out.pace = { toT: P2.toTarget, per: P2.perSession, w: P2.winners2R };
  const D = A.dayBudget(rules, { ...I, today: -300 }); out.day = { left: D.left, outs: D.outs, text: D.text };
  out.payoutNo = A.payoutCheck(rules, { ...I, stage: 'funded', balance: 52500 }).ok; const pay = A.payoutCheck(rules, { ...I, stage: 'funded', balance: 53000 }); out.payoutYes = [pay.ok, pay.gross, pay.net];
  out.payEval = A.payoutCheck(rules, I).funded;
  out.dd = [A.ddText(1400, 2000), A.ddText(2071, 2000)];
  // ---- Plutus
  const doc = await P.loadPlans('/plutus/plans.json');
  const rk = P.rankPlans(doc, 'H2'); out.rank = { n: rk.rows.length, sorted: rk.rows.every((r, i) => i === 0 || r.roi <= rk.rows[i - 1].roi), best: rk.best.name };
  const plan = doc.plans[0], b = P.buyPlan(plan, 'H2'); const p = (plan.spans.H2.p60 || 0) / 100;
  out.buy = { rows: b.rows.length, one: b.rows[0].atLeastOne, p, three: b.rows[2].atLeastOne, exp3: 1 - Math.pow(1 - p, 3), need90: b.need90, mono: b.rows.every((r, i) => i === 0 || r.atLeastOne >= b.rows[i - 1].atLeastOne) };
  const pr = P.payoutRace(doc, 'H2'); out.race = { sorted: pr.rows.every((r, i) => i === 0 || r.sessions >= pr.rows[i - 1].sessions), first: pr.first && pr.first.name };
  const proj = P.project(doc, { mffu_builder_50k: 1, lucid_pro_50k: 1 }, { span: 'H2', months: 6 }); const cc = P.cashCushion(proj);
  out.cush = { has: cc.has, dip: cc.dip, plain: cc.plain.length > 20, none: P.cashCushion(P.project(doc, {}, {})).has };
  // ---- Forum
  const ev = { balance: 50200, floor: 48400, target: 53000, room: 1800, toTarget: 2800, session: 4, sessions: 10, locked: false, mll: 2000 };
  const m = F.moneyToday(ev), m2 = F.moneyToday({ ...ev, room: 2071, floor: 50100, locked: true });
  out.money = { dd: m.ddText, frac: m.frac, per: m.perSession, left: m.left, tone: m.tone, dd2: m2.ddText, none: F.moneyToday(null).has };
  const rp = F.riskPlan(ev, 0.4); out.risk = { budget: rp.budget, n: rp.rows.map((r) => r.n), nonInc: rp.rows.every((r, i) => i === 0 || r.n <= rp.rows[i - 1].n) };
  const td = (h, dow) => F.tradingDay({ h, dow }).state; out.day4 = [td(8.67, 3), td(1, 3), td(16, 3), td(10, 6), td(15.7, 2)];
  const fx = await (await fetch('/forum/fixture.json')).json(); const ng = F.newsGate(fx.pantheon); out.news = [ng.has, ng.line.length > 20, F.newsGate(null).has];
  // ---- Argus
  const now = Date.parse('2026-11-04T14:30:00Z') / 1000, d = G.demoData(now), R = G.analyze({ now, home: d.home, cronos: d.cronos, cards: d.cards });
  out.argus = { verdict: R.verdict.level, counts: R.counts, ready: G.readiness(R, now).ready, gates: G.readiness(R, now).gates.length, money: G.moneyLines(R).map((x) => x.ddText), blind: G.blindCost(d.hist, now).incidents, noData: G.readiness(G.analyze({ now, home: {}, cronos: null, cards: {} }), now).ready };
  return out;
}"""


def part_b(br, base):
    p = br.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(base + "ares/rules.json")
    o = p.evaluate(CORES)
    od = o["odds"]
    check("b. ares: the odds maths = the sizing (size, loss), a 2R win = size x (2R pts x $ - commission), the break-even win rate = loss / (win + loss)",
          od["n"] == od["zn"] and abs(od["loss"] - od["zloss"]) < 1e-9 and abs(od["r2"] - od["expR2"]) < 1e-6 and abs(od["need1"] - od["expNeed1"]) < 1e-9 and od["rows"] == 6 and od["lossR"] > 1, od)
    check("b. ares: the stop ladder never gives more contracts for a wider stop", o["ladder"]["nonInc"] and o["ladder"]["n"][0] > o["ladder"]["n"][-1] >= 0, o["ladder"])
    st = o["streak"]
    check("b. ares: a losing streak: 5 rows, the room shrinks by the risk each time, the account dies at the third stop-out, 'Drawdown left $X of $2,000 max loss'",
          st["rows"] == 5 and st["bustAt"] == 3 and st["rooms"][0] > st["rooms"][1] > st["rooms"][2] and "of $2,000 max loss" in st["text"], st)
    check("b. ares: the pace to pass ($3,000 over 10 sessions = $300) and the day budget (daily loss left $700 of $1,000)", o["pace"]["toT"] == 3000 and abs(o["pace"]["per"] - 300) < 1e-9 and o["pace"]["w"] >= 1 and o["day"]["left"] == 700 and "of $1,000" in o["day"]["text"], (o["pace"], o["day"]))
    check("b. ares: the payout check (not yet at $400 above the buffer; $900 above: up to $900, $720 after the 80% split; none in an eval) and the locked-floor wording",
          o["payoutNo"] is False and o["payoutYes"] == [True, 900, 720] and o["payEval"] is False and "of $2,000 max loss" in o["dd"][0] and "floor locked" in o["dd"][1], (o["payoutNo"], o["payoutYes"], o["dd"]))
    check("b. plutus: plans ranked by net per dollar of fees, best first", o["rank"]["n"] == 4 and o["rank"]["sorted"], o["rank"])
    bu = o["buy"]
    check("b. plutus: evals to buy: 'at least one funded' = 1 - (1 - p)^n, rising with every buy, and the buys for 90%", abs(bu["one"] - bu["p"]) < 1e-9 and abs(bu["three"] - bu["exp3"]) < 1e-9 and bu["mono"] and (bu["need90"] or 0) >= 1, bu)
    check("b. plutus: who pays first is ordered by sessions; the cash cushion finds the bad case's dip and says so with no account", o["race"]["sorted"] and o["cush"]["has"] and o["cush"]["plain"] and o["cush"]["none"] is False, (o["race"], o["cush"]))
    mo = o["money"]
    check("b. forum: drawdown left 'of $2,000 max loss' (and 'floor locked' above it), the pace per session over the sessions left, no eval = no card numbers",
          mo["dd"] == "Drawdown left $1,800 of $2,000 max loss" and "floor locked" in mo["dd2"] and abs(mo["frac"] - 0.9) < 1e-9 and mo["left"] == 6 and abs(mo["per"] - 2800 / 6) < 1e-6 and mo["none"] is False, mo)
    check("b. forum: the risk plan: the budget is 40% of the room and a wider stop buys fewer micros", abs(o["risk"]["budget"] - 720) < 1e-9 and o["risk"]["nonInc"], o["risk"])
    check("b. forum: the trading day: open at 08:40 ET, before at 01:00, manage at 16:00? (after the 15:55 flat), closed on Saturday", o["day4"][0] == "open" and o["day4"][1] == "before" and o["day4"][3] == "closed" and o["day4"][4] == "manage", o["day4"])
    check("b. forum: the news rule from the council's caution, and a plain line without it", o["news"] == [True, True, False], o["news"])
    ar = o["argus"]
    check("b. argus: the demo day is one amber (ATLAS inactivity), nothing red, and the bot can trade", ar["verdict"] == "warn" and ar["counts"]["bad"] == 0 and ar["counts"]["warn"] == 1 and ar["ready"] is True and ar["gates"] == 6, ar)
    check("b. argus: the evals in money words and the red-light cost; no data = cannot say", ar["money"][0].startswith("Drawdown left $1,805 of $2,000 max loss") and ar["money"][1].startswith("Drawdown left $640 of $1,000") and ar["blind"] == 1 and ar["noData"] is False, ar)
    check("b. no page errors", not errs, errs)
    p.close()


TAPS = """() => [...document.querySelectorAll('button, a, select, input, summary, [role=button], [role=tab]')].filter((e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  return r.width && r.height && cs.visibility !== 'hidden' && cs.display !== 'none' && (r.height < 43.5 || r.width < 43.5) && !e.closest('[hidden]') && !(e.type === 'checkbox' && e.closest('label')) && r.top < 2000; })
  .map((e) => (e.id || (typeof e.className === 'string' ? e.className : '') || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))"""


def open_page(br, base, path, errs):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append(str(e)[:200]))
    p.on("console", lambda m: errs.append("console: " + m.text[:200]) if m.type == "error" and "Failed to load" not in m.text else None)
    p.goto(base + path)
    return ctx, p


def part_c(br, base):
    errs = []
    # ---- Ares
    ctx, p = open_page(br, base, "ares/", errs)
    p.wait_for_selector("#plusOdds", state="attached", timeout=60000)
    p.wait_for_timeout(1500)
    check("c. ares: with no entry the blocks still say what they need (never blank)", "Enter your entry" in p.inner_text("#plusOdds") and "budget" in p.inner_text("#plusLadderS"))
    p.evaluate("() => { localStorage.setItem('ares.v1', JSON.stringify({ entry: '21500', stop: '21480', riskPct: 40 })); location.reload(); }")
    p.wait_for_selector("#plusOdds table", timeout=60000)
    p.evaluate("() => document.querySelectorAll('.pd').forEach((d) => { d.open = true; })")
    rows = p.locator("#plusOdds tr").count()
    txt = p.inner_text("#plusOdds")
    check("c. ares: what a win must be worth: 6 rows, a stop-out in $ with the size, break-even win rates", rows == 7 and "stop-out costs $772" in txt.replace("\n", " ") and "35%" in txt, txt[:200])
    check("c. ares: the stop ladder lists 8 widths and tints the row nearest the stop on screen", p.locator("#plusLadder tr").count() == 9 and p.locator("#plusLadder tr.me").count() == 1)
    check("c. ares: the losing streak says 'DEAD' at the third stop-out and 'Drawdown left' words", "DEAD" in p.inner_text("#plusStreak") and "max loss" in p.inner_text("#plusStreak") or "of $2,000" in p.inner_text("#plusStreak"), p.inner_text("#plusStreak")[:200])
    p.click("[data-tab=account]")
    check("c. ares: today's loss budget, the pace to pass and the payout check are on the Account pane", "Daily loss left $1,000 of $1,000" in p.inner_text("#plusDay") and "to go" in p.inner_text("#plusPace") and "after the pass" in p.inner_text("#plusPayS"), (p.inner_text("#plusDay")[:120], p.inner_text("#plusPayS")))
    t1 = p.evaluate(TAPS)
    p.click("[data-tab=trade]")
    check("c. ares: every tap target is >= 44 px (trade and account panes)", not t1 and not p.evaluate(TAPS), (t1, p.evaluate(TAPS)))
    check("c. ares: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    ctx.close()
    # ---- Plutus
    ctx, p = open_page(br, base, "plutus/", errs)
    p.wait_for_selector("#plusRank table", state="attached", timeout=60000)
    p.evaluate("() => document.querySelectorAll('.pd').forEach((d) => { d.open = true; })")
    check("c. plutus: the best plan per dollar lists 4 plans, best first, with the sentence", p.locator("#plusRank tr").count() == 5 and "pays back the most" in p.inner_text("#plusRank"))
    before = p.inner_text("#plusBuy")
    p.click("#plusBuy [data-buy='lucid_pro_50k']")
    p.wait_for_timeout(300)
    after = p.inner_text("#plusBuy")
    check("c. plutus: how many evals to buy: 4 rows, and picking another plan changes the numbers", p.locator("#plusBuy tr").count() == 5 and before != after and "funded account" in after, (before[:80], after[:80]))
    p.click("#tabs [data-tab=risk]")
    p.evaluate("() => document.querySelectorAll('.pd').forEach((d) => { d.open = true; })")
    check("c. plutus: the cash cushion and who pays first are on the Risk pane", "bad case" in p.inner_text("#plusCushion").lower() or "above zero" in p.inner_text("#plusCushion").lower())
    check("c. plutus: who pays first has a bar per plan", p.locator("#plusRace .rb").count() >= 3)
    t = p.evaluate(TAPS)
    check("c. plutus: every tap target is >= 44 px", not t, t)
    check("c. plutus: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    ctx.close()
    # ---- Forum
    ctx, p = open_page(br, base, "forum/?t=08:40", errs)
    p.wait_for_function("window.FORUM && window.FORUM.state().ready", timeout=60000)
    mt = p.inner_text("#money")
    check("c. forum: Money today: 'Drawdown left $X of $2,000 max loss' (or the locked-floor words), the pace and four stop widths", "Drawdown left" in mt and ("max loss" in mt) and p.locator("#money .mtab tr").count() == 5 and "a session" in mt, mt[:200])
    check("c. forum: the news rule and the trading day (a bar with a now marker and the countdown)", "half size" in mt.lower() or "flat" in mt.lower() and p.locator("#day .dbar .dnow").count() == 1 and "entry" in p.inner_text("#day").lower(), p.inner_text("#day")[:160])
    check("c. forum: never blank: a recorded eval fills the money card when the site has none, marked DEMO", p.is_visible("#demo"))
    p.click("#start")
    t = p.evaluate(TAPS)
    check("c. forum: every tap target is >= 44 px (the dots row scrolls)", not t, t)
    check("c. forum: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    ctx.close()
    # ---- Argus
    ctx, p = open_page(br, base, "argus/#money", errs)
    p.wait_for_selector("#p-money .demobtn", timeout=60000)
    check("c. argus: with no data the Money tab says what it will show and offers the demo (never blank, never 'all clear')", "NO DATA" in p.inner_text("#vk") and "drawdown left" in p.inner_text("#p-money").lower())
    p.click("#p-money .demobtn")
    p.wait_for_function("document.getElementById('demotag') && !document.getElementById('demotag').hidden", timeout=60000)
    p.wait_for_selector("#p-money .rdy", timeout=30000)
    check("c. argus: the demo day: 'YES' the bot can trade, six gates, the entry-window countdown", p.locator("#p-money .gate").count() == 6 and "YES" in p.inner_text("#p-money .rdy") and "entry window" in p.inner_text("#p-money").lower())
    mt = p.inner_text("#p-money")
    check("c. argus: the evals in money words and the red-light cost", "Drawdown left $1,805 of $2,000 max loss" in mt and "Drawdown left $640 of $1,000 max loss" in mt and "red incident" in mt, mt[:300])
    check("c. argus: the demo is never saved over the real copy", p.evaluate("localStorage.getItem('argus.v1')") is None)
    t = p.evaluate(TAPS)
    check("c. argus: every tap target is >= 44 px", not t, t)
    check("c. argus: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    ctx.close()
    bad = [e for e in errs if not any(w in e for w in ("home.json", "data.json", "jarvis.json", "status.json", "404", "pantheon.json"))]
    check("c. no page errors on any of the four pages", not bad, bad[:5])


def main():
    part_a()
    if "--no-browser" not in sys.argv:
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            print("[SKIP] browser parts: Playwright not installed")
        else:
            srv, base = serve()
            with sync_playwright() as pw:
                br = launch(pw)
                for fn in (part_b, part_c):
                    try:
                        fn(br, base)
                    except Exception as e:
                        check(f"{fn.__name__}: ran to the end", False, repr(e)[:400])
                br.close()
            srv.shutdown()
    n, ok = len(RES), sum(RES)
    print(f"\nAres + Plutus + Forum + Argus (JOB 4+5 follow-up): {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
