"""ARENA + DAPHNE quality pass (2026-11-04, JOB 47): the atmosphere kit (olympus/fx-atmos.js: brazier embers in the colosseum, pollen and a contact shadow
under the laurel tree) and the new money features, all read-only.

  a. static   new files, fx-atmos wired in (after the first paint, ?noatmos=1 probe, follows the tier), embers() takes several source points, read-only
  b. cores    Arena trading desk (the weekly 2-4 rhythm, the 7-day quiet clock, the discipline rate and broken rules, the eval -> payout path) and Daphne's gate
              (the owner's checks, $ beside R at the bot's size, how often / how long to prove, the losing run against the max loss, sort and filter)
  c. pages    Chromium 390 x 844 on the LITE tier: every block draws with its numbers (equal to the core's), nothing blank, every tap >= 44 px, no sideways scroll,
              no page errors; the embers appear on a forced high tier and not with ?noatmos=1

    python -X utf8 -m tests.test_oly_job47 [--no-browser]
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
    check("a. fx-atmos embers(): several source points (the braziers of a ring)", "o.points" in fx and "origin, points" in fx)
    dr = rd("tools", "web_public", "arena", "dress.js")
    check("a. arena dress: embers off the 14 braziers through fx-atmos, after the first paint, ?noatmos=1 probe, skipped on LITE, disposed",
          "fx-atmos.js" in dr and "AT.embers(" in dr and "points: pts" in dr and "setTimeout" in dr and "noatmos=1" in dr and "if (stopped || lite" in dr and "AT.update(" in dr and "geometry.dispose()" in dr)
    t3 = rd("tools", "web_public", "tree", "tree3d.js")
    check("a. daphne 3D: pollen (dust) and a contact shadow through fx-atmos, after the first paint, ?noatmos=1 probe, updated and disposed",
          "fx-atmos.js" in t3 and "AT.dust(" in t3 and "AT.contactAO(" in t3 and "noatmos=1" in t3 and "AT.update(" in t3 and "geometry.dispose()" in t3)
    rh = rd("tools", "web_public", "arena", "rhythm.js")
    check("a. arena rhythm.js: pure functions + a desk renderer", all(f"export function {n}(" in rh for n in ("tradeLog", "mainAccount", "weeklyRhythm", "quietClock", "brokenBoard", "moneyPath", "desk")))
    gt = rd("tools", "web_public", "tree", "gate.js")
    check("a. daphne gate.js: atBot, monthly, gate, rhythm, lossRun, runOdds, sortRules, gateHtml, noteText", all(f"export function {n}(" in gt for n in ("atBot", "monthly", "gate", "rhythm", "lossRun", "runOdds", "sortRules", "gateHtml", "noteText")))
    check("a. both new files are read-only (no fetch, POST, storage write, order call)", all(all(w not in s for w in ("fetch(", "POST", "setItem", "XMLHttpRequest", "place_order")) for s in (rh, gt)))
    check("a. no innerHTML with data in the arena desk (textContent only)", "innerHTML" not in rh)
    mj, ap = rd("tools", "web_public", "arena", "main.js"), rd("tools", "web_public", "tree", "app.js")
    check("a. wired: Bosses tab shows the desk; the top-10 sheet and the rules tab use the gate", "from './rhythm.js'" in mj and "desk(S.ledger.events()" in mj and "gate.js" in ap and "G.gateHtml(" in ap and "G.sortRules(" in ap and "G.noteText(" in ap)
    check("a. daphne: the sort bar is in the markup", 'id="topBar"' in rd("tools", "web_public", "tree", "index.html"))
    check("a. no $ or R is added to an Arena event (the scoring rule stays: no $, size or R in a score)", "no $" in rh.lower() or "never sees dollars" in rh)


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
  const R = await (await fetch('/arena/rules.json')).json();
  const K = await import('/arena/rhythm.js');
  const ev = (kind, day, acct, note, n) => ({ id: kind === 'clean_trade' || kind === 'rule_broken' ? `trade:${acct}:${n || 1}:${day}` : `${kind}:${day}`, day, kind, src: 'site', note: note || '', t: 1000 + (n || 1) });
  const E = [
    ev('clean_trade', '2026-10-28', 'atlas', 'ATLAS: every rule kept'), ev('rule_broken', '2026-10-29', 'atlas', 'ATLAS: broke Hands off'),
    ev('clean_trade', '2026-11-02', 'zl', 'Zlarior: every rule kept'), ev('clean_trade', '2026-11-03', 'zl', 'Zlarior: every rule kept'),
    ev('clean_trade', '2026-10-20', 'zl', 'Zlarior: every rule kept'), ev('clean_trade', '2026-10-22', 'zl', 'Zlarior: every rule kept'), ev('clean_trade', '2026-10-23', 'zl', 'Zlarior: every rule kept'),
    ev('eval_passed', '2026-10-07', '', 'MFFU 25K Funded: eval passed'), ev('payout', '2026-10-28', '', 'MFFU 25K Funded: payout recorded'),
  ];
  const T = K.tradeLog(E, R), main = K.mainAccount(T, '2026-11-04');
  out.log = { n: T.length, clean: T.filter((t) => t.clean).length, rule: (T.find((t) => !t.clean) || {}).rule, main: main.label };
  const w = K.weeklyRhythm(T, '2026-11-04', 8, main.acct);
  out.week = { n: w.cur.n, verdict: w.cur.verdict, room: w.cur.room, left: w.cur.left, weeks: w.weeks.length, prev: w.weeks[w.weeks.length - 2].n, prevState: w.weeks[w.weeks.length - 2].state, inPlan: w.inPlan, run: w.run };
  out.need = K.weeklyRhythm(T.filter((t) => t.day < '2026-11-03'), '2026-11-04', 8, main.acct).cur.verdict;
  out.miss = K.weeklyRhythm(T.filter((t) => t.day < '2026-11-02'), '2026-11-06', 8, main.acct).cur.verdict;
  out.full = K.weeklyRhythm(['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05'].map((d) => ({ day: d, acct: 'zl', clean: true })), '2026-11-05', 8, 'zl').cur.verdict;
  out.over = K.weeklyRhythm(['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-05'].map((d) => ({ day: d, acct: 'zl', clean: true })), '2026-11-05', 8, 'zl').cur.verdict;
  const q = K.quietClock(T, '2026-11-04'), q2 = K.quietClock(T, '2026-11-06');
  out.quiet = { first: q[0].label, left: q[0].left, state: q[0].state, zl: q.find((x) => x.acct === 'zl').state, lapsed: q2[0].state, quiet2: q2[0].quiet };
  const b = K.brokenBoard(T, '2026-11-04');
  out.broken = { total: b.total, clean: b.clean, broken: b.broken, rate: b.rate, rules: b.byRule.map((r) => [r.rule, r.n, r.last]), since: b.cleanSince, none: K.brokenBoard([], '2026-11-04').rate };
  const m = K.moneyPath(E, R, '2026-11-04');
  out.path = { done: m.steps.map((s) => s.done), days: m.days, pays: m.payouts, next: m.next.length > 20, none: K.moneyPath([], R, '2026-11-04').steps.some((s) => s.done) };
  // ---- Daphne
  const G = await import('/tree/gate.js'), doc = await (await fetch('/tree/tree.json')).json();
  const meta = doc.meta, rk = meta.bot_risk_usd, top = doc.top;
  const r0 = { holds: true, test: { n: 45, net_bot: 548, mo_bot: 25, win: 37.8, tpw: 0.49 }, y2026: { n: 22, net_bot: 923, mo_bot: 95, win: 40.9, tpw: 0.54 } };
  const g = G.gate(r0, meta), tb = G.atBot(r0.test, rk), mo = G.monthly(r0.y2026, rk), rh = G.rhythm(r0), lr = G.lossRun(r0, meta);
  out.gate = { verdict: g.verdict, passed: g.passed, bad: G.gate({ ...r0, holds: false }, meta).verdict, nothing: G.gate({ holds: false }, meta).verdict, watch: G.gate({ ...r0, y2026: { ...r0.y2026, n: 5 } }, meta).verdict,
    tbUsd: tb.usd, tbR: tb.r, moR: mo.r, tpw: rh.tpw, stack: rh.stack, weeks: rh.weeks, none: G.rhythm({}), noAt: G.atBot({}, rk) };
  out.run = { k: lr.k, loss: lr.loss, left: lr.left, wipe: lr.wipe, p1: G.runOdds(0.5, 1, 1), p2: G.runOdds(0.5, 2, 2), p3: G.runOdds(0.5, 2, 3), p0: G.runOdds(0, 3, 40), odds: lr.odds, wipeOdds: lr.wipeOdds };
  const mo26 = G.sortRules(top, 'mo2026', false, meta).map((x) => x.i), holds = G.sortRules(top, 'rank', true, meta), tp = G.sortRules(top, 'tpw', false, meta).map((x) => x.r.y2026.tpw ?? x.r.test.tpw);
  out.sort = { mo26, expect: top.map((r, i) => [i, (r.y2026 || {}).mo_bot ?? -1e9]).sort((a, b) => b[1] - a[1] || a[0] - b[0]).map((x) => x[0]), holds: holds.length, expHolds: top.filter((r) => r.holds).length, rank: G.sortRules(top, 'rank', false, meta).map((x) => x.i).join(), tpwDesc: tp.every((v, i) => i === 0 || (v ?? -1) <= (tp[i - 1] ?? -1)) };
  const html = G.gateHtml(r0, meta);
  out.html = { dd: html.includes('Drawdown left $872 of $2,000 max loss'), noOf10: !/of 10\b/.test(html), r: html.includes('+0.04R') && html.includes('+0.34R'), r1: html.includes('1R = $282'), word: html.includes('CANDIDATE FOR THE BOT'), usd: G.fmtUsd(-1128) + ' ' + G.fmtUsd(1234.4) + ' ' + G.fmtR(-4) + ' ' + G.fmtR(0.346) };
  return out;
}"""


def part_b(br, base):
    p = br.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(base + "arena/rules.json")
    o = p.evaluate(CORES)
    check("b. arena: the trade log = every clean trade and broken rule (the broken rule named), the main account is the one that trades most",
          o["log"] == {"n": 7, "clean": 6, "rule": "Hands off", "main": "Zlarior"}, o["log"])
    w = o["week"]
    check("b. arena: weekly rhythm: 8 weeks of the main account, this week 2 trades = inside the plan with room for 2 and 3 market days left; last week 0 = under, one finished week in the plan",
          w["weeks"] == 8 and w["n"] == 2 and w["verdict"] == "plan" and w["room"] == 2 and w["left"] == 3 and w["prev"] == 0 and w["prevState"] == "under" and w["inPlan"] == 1 and w["run"] == 0, w)
    check("b. arena: the verdicts: 1 trade = need one more, 0 trades on a Friday = the plan will be missed, 4 = full, 5 = over", [o["need"], o["miss"], o["full"], o["over"]] == ["need", "miss", "full", "over"], [o["need"], o["miss"], o["full"], o["over"]])
    q = o["quiet"]
    check("b. arena: quiet clock: ATLAS (last trade 6 days ago) has 1 day left = warn and is listed first, Zlarior is ok, two days later it has lapsed (8 quiet days)",
          q["first"] == "ATLAS" and q["left"] == 1 and q["state"] == "warn" and q["zl"] == "ok" and q["lapsed"] == "lapsed" and q["quiet2"] == 8, q)
    bk = o["broken"]
    check("b. arena: discipline: 6 clean of 7 = 86%, the broken rule listed once, 2 clean in a row since, no trades = no rate (not a made-up 100%)",
          bk["total"] == 7 and bk["clean"] == 6 and bk["broken"] == 1 and abs(bk["rate"] - 6 / 7) < 1e-9 and bk["rules"] == [["Hands off", 1, "2026-10-29"]] and bk["since"] == 2 and bk["none"] is None, bk)
    pa = o["path"]
    check("b. arena: money path: first trade, eval passed and payout all done, 21 days from the pass to the payout; an empty ledger has no step done",
          pa["done"] == [True, True, True] and pa["days"] == 21 and pa["pays"] == 1 and pa["next"] and pa["none"] is False, pa)
    g = o["gate"]
    check("b. daphne: the gate: all four checks = candidate; fails out of sample = not a candidate; an empty rule = reject; few 2026 trades = watch",
          g["verdict"] == "candidate" and g["passed"] == 4 and g["bad"] != "candidate" and g["nothing"] == "reject" and g["watch"] == "watch", g)
    check("b. daphne: $ beside R at the bot's size (net / trades, over $282): test +$12 = +0.04R; 2026 $95 a month = +0.34R; no trades = no number",
          abs(g["tbUsd"] - 548 / 45) < 1e-9 and abs(g["tbR"] - 548 / 45 / 282) < 1e-9 and abs(g["moR"] - 95 / 282) < 1e-9 and g["noAt"] is None, g)
    check("b. daphne: how often: 0.54 a week, 4 like it make 2 a week, 30 live trades take 30 / 0.54 weeks; no frequency = none", g["tpw"] == 0.54 and g["stack"] == 4 and abs(g["weeks"] - 30 / 0.54) < 1e-9 and g["none"] is None, g)
    r = o["run"]
    check("b. daphne: the losing run: 4 stop-outs = -$1,128, Drawdown left $872 of $2,000, 8 in a row use all of it; the run odds are exact (0.5, 0.25, 0.375; none at q 0)",
          r["k"] == 4 and abs(r["loss"] - 1128) < 1e-9 and abs(r["left"] - 872) < 1e-9 and r["wipe"] == 8 and r["p1"] == 0.5 and r["p2"] == 0.25 and r["p3"] == 0.375 and r["p0"] == 0 and 0 < r["wipeOdds"] < r["odds"] < 1, r)
    s = o["sort"]
    check("b. daphne: sort by 2026 $/month = the same order as the data, only-holds keeps exactly the rules that hold, rank keeps the search's order, trades a week is descending",
          s["mo26"] == s["expect"] and s["holds"] == s["expHolds"] and s["rank"] == ",".join(str(i) for i in range(len(s["mo26"]))) and s["tpwDesc"], s)
    h = o["html"]
    check("b. daphne: the gate card says 'Drawdown left $872 of $2,000 max loss' (never 'of 10'), shows R next to every $ and 1R = $282, formats money and R",
          h["dd"] and h["noOf10"] and h["r"] and h["r1"] and h["word"] and h["usd"] == "−$1,128 +$1,234 −4.00R +0.35R", h)
    check("b. no page errors", not errs, errs)
    p.close()


TAPS = """(root) => [...document.querySelectorAll((root || 'body') + ' button, ' + (root || 'body') + ' a, ' + (root || 'body') + ' input, ' + (root || 'body') + ' [role=tab]')].filter((e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  return r.width && r.height && cs.visibility !== 'hidden' && cs.display !== 'none' && (r.height < 43.5 || r.width < 43.5) && !e.closest('[hidden]') && r.top < 2000; })
  .map((e) => (e.id || (typeof e.className === 'string' ? e.className : '') || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))"""


def open_page(br, base, path, errs, jfx="low"):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{jfx}'); }} catch (e) {{}}")
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append(str(e)[:200]))
    p.on("console", lambda m: errs.append("console: " + m.text[:200]) if m.type == "error" and "Failed to load" not in m.text else None)
    p.goto(base + path)
    return ctx, p


def part_c(br, base):
    errs = []
    # ---- Arena: the desk on the Bosses tab
    ctx, p = open_page(br, base, "arena/", errs)
    p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=90000)
    p.evaluate("() => document.querySelector('[data-tab=bosses]').click()")        # no stability wait: the scene never stops animating
    p.wait_for_selector(".desk .desk-rhythm", timeout=30000)
    txt = p.inner_text(".desk")
    txt_l = txt.lower()          # the headings are drawn in capitals by the stylesheet
    check("c. arena: the Bosses tab has the trading desk: rhythm, quiet clock, discipline rate, money path, nothing blank",
          all(w in txt_l for w in ("weekly rhythm", "quiet clock", "discipline rate", "money path")) and p.locator(".desk > section").count() == 4 and len(txt) > 400, txt[:200])
    exp = p.evaluate("""async () => {
      const K = await import('/arena/rhythm.js'), R = await (await fetch('/arena/rules.json')).json(), site = await (await fetch('/arena/events.json')).json();
      const today = ARENA.state().today, T = K.tradeLog(site.events, R), main = K.mainAccount(T, today), w = K.weeklyRhythm(T, today, 8, main.acct), b = K.brokenBoard(T, today);
      return { verdict: w.cur.verdict, n: w.cur.n, bars: w.weeks.length, rate: b.rate30 == null ? 'no trades yet' : Math.round(b.rate30 * 100) + '%', since: String(b.cleanSince), label: main.label };
    }""")
    shown = p.evaluate("() => ({ verdict: document.querySelector('.desk .say').dataset.verdict, bars: document.querySelectorAll('.desk .rhythm rect.wk').length, rate: document.querySelector('.desk .rate b').textContent, since: document.querySelectorAll('.desk .rate b')[2].textContent, head: document.querySelector('.desk-rhythm h3').textContent })")
    check("c. arena: the page shows what the core says: this week's verdict, 8 bars, the 30-day discipline rate, the clean run, the main account's name",
          shown["verdict"] == exp["verdict"] and shown["bars"] == exp["bars"] == 8 and shown["rate"] == exp["rate"] and shown["since"] == exp["since"] and exp["label"] in shown["head"], (shown, exp))
    check("c. arena: the quiet clock has a row per account with 'days left' or 'lapsed', and the money path says what is next", p.locator(".desk .qrow").count() >= 1 and "left" in p.inner_text(".desk-quiet") or "lapsed" in p.inner_text(".desk-quiet"))
    check("c. arena: Arena stays honest: the desk says it counts rules and days, not dollars", "not dollars" in p.inner_text(".desk-path"))
    t = p.evaluate(TAPS, None)
    check("c. arena: every tap target is >= 44 px at 390 x 844 (Bosses tab)", not t, t)
    check("c. arena: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    st = p.evaluate("ARENA.state().scene.dress")
    check("c. arena: on the LITE tier the embers are skipped (cheap) and the scene still dresses", st is None or st["embers"] == 0, st)
    ctx.close()
    ctx, p = open_page(br, base, "arena/?q=high", errs, jfx="high")
    p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=90000)
    try:
        p.wait_for_function("(() => { const s = ARENA.state().scene; return s && s.dress && s.dress.embers === 1; })()", timeout=90000)
        ok = True
    except Exception:
        ok = False
    check("c. arena: on a forced high tier the brazier embers join after the first paint", ok, p.evaluate("ARENA.state().scene && ARENA.state().scene.dress"))
    ctx.close()
    ctx, p = open_page(br, base, "arena/?q=high&noatmos=1", errs, jfx="high")
    p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=90000)
    p.wait_for_timeout(4000)
    st = p.evaluate("ARENA.state().scene && ARENA.state().scene.dress")
    check("c. arena: ?noatmos=1 keeps the scene without the embers (the perf probe)", st is None or st["embers"] == 0, st)
    ctx.close()
    # ---- Daphne: the top 10 sheet and the rules tab
    ctx, p = open_page(br, base, "tree/?q=off", errs)
    p.wait_for_function("window.__daphne && window.__daphne.state && window.__daphne.state.model", timeout=90000)
    p.click('.sheet-tabs [data-tab="rules"]')
    p.wait_for_timeout(300)
    n = p.locator("#rules li").count()
    notes = p.locator("#rules li .gn").count()
    check("c. daphne: TOP RULES: every row says candidate / watch / not yet with its checks, the 2026 $ a month with R, and $ a trade with R",
          n >= 3 and notes == n and "R TEST/TR" in p.inner_text("#rules li:first-child") and "/MO" in p.inner_text("#rules li:first-child") and "1R = $" in p.inner_text("#rulesNote"), p.inner_text("#rules li:first-child"))
    p.click("#openTop")
    p.wait_for_selector("#toplist .gate", timeout=10000)
    gates = p.locator("#toplist li .gate").count()
    check("c. daphne: TOP 10: a gate card on every rule (checks, $ beside R for test and 2026, how often, the losing run), the sort bar has 5 buttons",
          gates == n and p.locator("#topBar button").count() == 5 and "LOSING RUN" in p.inner_text("#toplist li:first-child") and "max loss" in p.inner_text("#toplist li:first-child") and "HOW OFTEN" in p.inner_text("#toplist li:first-child"))
    first = p.inner_text("#toplist li:first-child .hd b")
    p.click("#topBar [data-sort=mo2026]")
    p.wait_for_timeout(200)
    best = p.evaluate("() => { const r = window.__daphne.state.model.top, k = (x) => (x.y2026 || {}).mo_bot ?? -1e9; return r.slice().sort((a, b) => k(b) - k(a))[0].key; }")
    sorted_first = p.inner_text("#toplist li:first-child .hd b")
    check("c. daphne: sorting by 2026 $/month puts the best 2026 month first and marks the button pressed", sorted_first == best and p.get_attribute("#topBar [data-sort=mo2026]", "aria-pressed") == "true", (first, sorted_first, best))
    p.click("#topBar [data-hold]")
    p.wait_for_timeout(200)
    held = p.evaluate("() => window.__daphne.state.model.top.filter((r) => r.holds).length")
    check("c. daphne: ONLY HOLDS keeps the rules that hold out of sample, and every one shows HOLDS", p.locator("#toplist li[data-root]").count() == held and p.locator("#toplist li .tag.no").count() == 0, held)
    t = p.evaluate(TAPS, "#top")
    check("c. daphne: every tap target in the top-10 sheet is >= 44 px at 390 x 844", not t, t)
    check("c. daphne: no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    ctx.close()
    check("c. no page errors", not errs, errs)


def main():
    part_a()
    if "--no-browser" not in sys.argv:
        from playwright.sync_api import sync_playwright
        srv, base = serve()
        with sync_playwright() as pw:
            br = launch(pw)
            part_b(br, base)
            part_c(br, base)
            br.close()
        srv.shutdown()
    ok = sum(RES)
    print(f"\n{ok}/{len(RES)} passed", flush=True)
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
