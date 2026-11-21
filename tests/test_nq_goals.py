"""NQ v4 GOALS + NUMBERS (owner 2026-11-20 15:00 ET: "you should have goals on the NQ dashboard ... more data ... make it look cool").
tools/web_public/nq/nqgoals.js (+ nqgoals.css, nqland.js the 3D price landscape), on the PC's real post of 2026-11-20 ~10:20 ET
(tests/fixtures/truth/pc_post.json: ATLAS funded $25,401.38, Zlarior 50K $49,192.78, 25K #2 $25,000).
  a. node    the goals: ATLAS first in MFFU's own terms (a sim-funded account starts at $0: "$401"; the GOAL = ask $1,000 at $2,100: $1,698.62
             left, 19%, $800 to you; earliest = the $250 minimum at $1,350 = the payout coach's $948.62; floor -$1,000 EOD trailing, stops at +$100;
             2 traded days + best day <= 50%; the cost study's date 'about Dec 18-31 (estimate, 2026-like market)', never a few days' pace), Zlarior 50K +$3,807 to pass, 25K #2 +$1,500, the Rapid
             planned (4+ days, best day <= 30% = $450), the fleet (1 of 5 funded slots, goals.json's $5,200 a month); never "to payout $X" but the coach's
  b. node    the numbers: today's / this week's P&L per account (the PC's today + the week's earlier real fills), win rate + PF over real fills only,
             the last 10; the session clock (London / New York windows, the next one, weekends); the VIX band and the LIT target size
  c. Chromium 390 x 844 (the post + the chart fixture): the goals strip AND the whole chart on the first screen, ATLAS's ring at 19% with "$1,699 left",
             a tap opens its rules; the numbers card; the 3D landscape (or its 2D picture); reduced motion: final numbers at once, no burst;
             LITE: no 3D fetched, the 2D picture; no sideways scroll, taps >= 44 px, no console error, layout shift < 0.05 after the first paint
    python -X utf8 -m tests.test_nq_goals [--static]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
NQ = os.path.join(AK.WEB, "nq")
PC = json.load(open(os.path.join(AK.ROOT, "tests", "fixtures", "truth", "pc_post.json"), encoding="utf-8"))
NOW = PC["reporter"]["t"] + 600          # 10 minutes after the report (its brd.t is 9 min after the core: the feed's 10-minute skew)

JS = r"""
const path = require('path'), W = process.argv[2], NOW = +process.argv[3];
const PC = require(path.join(W, '..', '..', 'tests', 'fixtures', 'truth', 'pc_post.json'));
const F = require(path.join(W, 'pc_feed.js')), COACH = require(path.join(W, 'business', 'payoutcoach.js'));
const biz = require(path.join(W, 'business', 'accounts.json')), plan = require(path.join(W, 'business', 'goals.json'));
const brief = require(path.join(W, 'nq', 'brief.json'));
(async () => {
  const D = await import(path.join(W, 'nq', 'nqdesk.js')), G = await import(path.join(W, 'nq', 'nqgoals.js')), P = await import(path.join(W, 'nq', 'payready.js'));
  const home = F.homeOver({}, PC, NOW, COACH), A = D.accounts(home, biz, NOW, null), day = D.etParts(NOW).day;
  const pay = P.model(PC, home, biz, COACH, day);
  const eq = {}; for (const r of PC.mf.a) { const k = { mffu50k_eval: 'zlarior', b25k_2: 'fresh25', atlas: 'atlas' }[r.id]; if (k) eq[k] = r.eq; }
  const goals = G.goals(A, pay, plan, NOW, eq);
  const noPlan = G.goals(A, [], {}, NOW, {});
  const rows = [{ key: 'atlas', day: '2026-11-17', xt: 1, usd: 1792.5, r: 6.6 }, { key: 'atlas', day: '2026-11-18', xt: 2, usd: -112.8, r: -0.92 },
    { key: 'zlarior', day: '2026-11-16', xt: 3, usd: -129, r: -1.0 }, { key: 'zlarior', day: '2026-11-13', xt: 0, usd: -437, r: -1.0 }];
  const N = G.numbers(A, rows, NOW);
  const real = G.realRows({ trades: [{ src: 'live', ak: 'atlas25f', day: '2026-11-18', xt: 100, usd: -112.8, r: -0.92 }, { src: 'paper', ak: 'z50k', day: '2026-11-18', xt: 200, usd: 50 },
    { src: 'backtest', ak: 'atlas25f', day: '2026-11-18', xt: 300, usd: 70 }] }, { closed: [{ k: 'atlas25f', xt: 100 + 20, usd: -112.8, r: -0.92 }, { k: 'z50k', xt: 9000, usd: 107.5, r: 1.2, s: 1 }] });
  const et = (s) => Math.floor(Date.parse(s) / 1000);
  const clocks = { fri0940: G.clock(et('2026-11-20T09:40:00-05:00')), wed1700: G.clock(et('2026-11-18T17:00:00-05:00')), sat1200: G.clock(et('2026-11-21T12:00:00-05:00')),
    mon0300: G.clock(et('2026-11-23T03:00:00-05:00')), fri1600: G.clock(et('2026-11-20T16:00:00-05:00')) };
  console.log(JSON.stringify({ A: A.map((a) => [a.key, a.stage, a.has, a.balance, a.goal, a.today]), goals, noPlan, N, real, clocks, vix: G.vixLine(brief), none: G.vixLine({}),
    when: [G.when(0, null, '2026-11-20', ''), G.when(1000, { per: 200, days: 4 }, '2026-11-20', ''), G.when(1000, { per: -10, days: 4 }, '2026-11-20', '~Dec 10'), G.when(1000, null, '2026-11-20', '')],
    span: [G.span('2026-12-18', '2026-12-31'), G.span('2026-12-29', '2027-01-06')],
    eras: (() => { const f = { trades: [{ src: 'live', ak: 'atlas25f', day: '2026-11-17', t: 1794950000, xt: 1794951000, usd: 1792.5 }, { src: 'live', ak: 'atlas25f', day: '2026-11-18', t: 1794995400, xt: 1794996480, usd: -112.8 }] };
      const lite = { life: { acc: { atlas: { stage: 'funded', since: 1794965203 } } } };
      return { nq: G.realRows(f, { closed: [{ k: 'atlas25f', xt: 1795165000, usd: 514.18, r: 2 }] }, G.fundedSince(lite)).map((r) => [r.key, r.usd]), noPc: G.realRows(f, null, G.fundedSince(null)).map((r) => r.key) }; })(),
    opens: G.opens([{ key: 'zlarior', name: 'Zlarior 50K', open: { side: 'SHORT', qty: 6, entry: 21555.5, stop: 21574, target_usd: 735, now: 315, stopMoved: false } },
      { key: 'atlas', name: 'ATLAS 25K', open: { side: 'LONG', qty: 2, entry: 100, stop: 101, now: 40, stopMoved: true, locked: 4 } }, { key: 'fresh25', name: 'x' }]) }));
})().catch((e) => { console.log(JSON.stringify({ err: String(e && e.stack || e) })); });
"""


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("a. node skipped", True)
        return
    tmp = os.path.join(AK.ROOT, "tests", "fixtures", "_nq_goals.cjs")
    try:
        open(tmp, "w", encoding="utf-8").write(JS)
        r = subprocess.run([exe, tmp, AK.WEB, str(NOW)], capture_output=True, text=True, timeout=60)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"err": r.stderr[-800:]}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if "err" in o:
        check("a. the node harness ran", False, o["err"])
        return
    G = {g["key"]: g for g in o["goals"]}
    keys = [g["key"] for g in o["goals"]]
    a = G.get("atlas", {})
    check("a. the order: ATLAS's payout first, then the evals, the planned Rapid, the fleet last", keys[0] == "atlas" and keys[-1] == "fleet" and keys.index("rapid1") > keys.index("fresh25"), keys)
    check("a. ATLAS in MFFU's terms: profit $401 shown as its balance; the goal ask $1,000 at $2,100: $1,698.62 left, 19%; '$800 to you at the 80% split'",
          a.get("kind") == "payout" and abs(a.get("left", 0) - 1698.62) < 0.01 and abs(a.get("frac", 0) - 401.38 / 2100) < 1e-6 and a.get("big") == "$1,699"
          and a.get("goal") == "Ask $1,000 at $2,100" and abs(a.get("balance", 0) - 401.38) < 0.01 and a.get("goalAt") == 2100 and a.get("earliest") == 1350
          and "$800 to you at the 80% split" in a["lines"][1] and "its profit: $401 (max-loss floor" in a["lines"][0] and "it stops at +$100" in a["lines"][0], a)
    check("a. ... earliest: the minimum $250 ask at $1,350: '$949 more' (= the payout coach's need_more, the 'to payout' every page shows)",
          "Earliest: the minimum $250 ask at $1,350: $949 more." in a["lines"][2], a.get("lines"))
    check("a. ... the rules as chips: traded days (the PC's tracker) and the best day <= 50%",
          len(a.get("chips", [])) == 2 and a["chips"][0]["label"].startswith("Traded days") and "Best day <= 50%" in a["chips"][1]["label"], a.get("chips"))
    check("a. ... the date: the ATLAS cost study's simulated 'about Dec 18-31 (estimate, 2026-like market)' (a 3-day pace over-promised); evals: the plan's dates",
          a.get("when") == "about Dec 18-31 (estimate, 2026-like market)" and G["zlarior"]["when"] == "plan: about Dec 24 (estimate)"
          and G["fresh25"]["when"] == "plan: about Dec 9 (estimate)", (a.get("when"), G["zlarior"].get("when"), G["fresh25"].get("when")))
    z, f, rp, fl = G.get("zlarior", {}), G.get("fresh25", {}), G.get("rapid1", {}), G.get("fleet", {})
    check("a. Zlarior 50K: +$3,807 to pass at $53,000, 0% (the balance is under the $50,000 start), drawdown left $1,025 in its line",
          z.get("big") == "+$3,807" and z.get("goal") == "Pass at $53,000" and z.get("frac") == 0 and "Drawdown left $1,025" in z["lines"][0], z)
    check("a. Zlarior 25K #2: +$1,500 to pass at $26,500, 0%", f.get("big") == "+$1,500" and f.get("goal") == "Pass at $26,500" and f.get("frac") == 0, f)
    check("a. the Rapid EOD 25K before it exists: planned, dim, '+$1,500 in 4+ days, no day over 30% ($450)', the plan's date",
          rp.get("kind") == "plan" and not rp.get("has") and "+$1,500 in 4+ days, no day over 30% ($450)" in rp["lines"][0] and rp.get("when", "").startswith("plan: about"), rp)
    check("a. the fleet: 1 of 5 funded slots, goals.json's 'about $5,200 a month' by Mar 1 (an estimate), no payout yet",
          fl.get("big") == "1 of 5" and fl.get("goal") == "$5,200 a month" and "$5,200 a month to you by Mar 1" in fl["lines"][0] and "No payout taken yet" in fl["lines"][1], fl)
    import re
    from tools import truth_check as TC
    txt = " ".join(" ".join([g["goal"], g["big"], g["unit"], *g["lines"], g["when"], *[c["label"] for c in g["chips"]]]) for g in o["goals"])
    pays = [m.group(1) for m in TC.PAYOUT_RX.finditer(txt)]
    check("a. the truth scanner finds no second 'to payout' number in the goals (the plan's $1,699 is 'left' for the $1,000 ask)", pays == [], pays)
    bad = [float(m.group(1).replace(",", "")) for m in TC.MONEY_RX.finditer(txt) if 23000 <= float(m.group(1).replace(",", "")) <= 56000
           and not TC.NOT_STATE.search(txt[max(0, m.start() - 40):m.end() + 12])]
    check("a. ... and no balance-looking $ that is not a target / ask / start", bad == [], bad)
    na = {g["key"]: g for g in o["noPlan"]}.get("atlas", {})
    check("a. without the PC's tracker (no payready row) ATLAS still has its goal from the board balance ($25,401 -> MFFU's $401) and the plan constants",
          abs(na.get("left", 0) - 1698.62) < 0.01 and "Earliest: the minimum $250 ask at $1,350: $949 more." in na["lines"][2] and na["chips"][0]["ok"] is None
          and na.get("when") == "about Dec 18-31 (estimate, 2026-like market)", na)
    w = o["when"]
    check("a. when(): reached / a range at a pace (Nov 27 - Dec 3 for $1,000 at $200 a day from Fri Nov 20: 5 to 9 trading days) / the plan's date when the pace is negative / no pace",
          w[0]["text"] == "reached" and w[1]["text"] == "about Nov 27 - Dec 3 at today's pace (estimate)" and w[2]["text"] == "plan: about Dec 10 (estimate)"
          and w[3]["text"] == "not enough days yet for a pace" and o["span"] == ["Dec 18-31", "Dec 29 - Jan 6"], (w, o["span"]))
    # b. the numbers
    N = o["N"]
    per = {p["key"]: p for p in N["per"]}
    check("b. today / this week: ATLAS today +$514.18 (the PC's), the week = Mon-Thu real fills (+$1,792.50 - $112.80) + today = $2,193.88; Zlarior -$129",
          abs(per["atlas"]["today"] - 514.18) < 0.01 and abs(per["atlas"]["week"] - 2193.88) < 0.01 and per["zlarior"]["week"] == -129, per)
    check("b. win rate 25% (1 of 4), PF 1792.5 / (112.8 + 129 + 437) = 2.64, net, the last 10 newest first",
          N["wr"] == 25 and abs(N["pf"] - 2.64) < 0.01 and N["n"] == 4 and N["last"][0]["usd"] == -112.8 and N["last"][-1]["usd"] == -437 and abs(N["net"] - 1113.7) < 0.01, N)
    check("b. realRows: live rows + the PC's chart closed trades, one per account and exit minute; never paper or backtest",
          [(r["key"], r["usd"]) for r in o["real"]] == [("atlas", -112.8), ("zlarior", 107.5)], o["real"])
    C = o["clocks"]
    check("b. the session clock: Fri 09:40 ET = New York morning, the New York window open until 15:30 (5 h 50 min left); London 02:00-08:00, New York 08:00-15:30",
          C["fri0940"]["phase"] == "New York morning" and C["fri0940"]["next"]["text"] == "New York window open until 15:30 ET (5 h 50 min left)" and C["fri0940"]["next"]["open"]
          and [w["text"] for w in C["fri0940"]["windows"]] == ["London 02:00-08:00", "New York 08:00-15:30"] and C["fri0940"]["windows"][1]["on"], C["fri0940"])
    check("b. ... Wed 17:00 ET: next London 02:00 ET in 9 h 0 min; Mon 03:00 London open; Fri 16:00 and Saturday: the window is on Monday, weekend said",
          C["wed1700"]["next"]["text"] == "Next entry window: London 02:00 ET (in 9 h 0 min)" and C["mon0300"]["next"]["open"] and C["mon0300"]["windows"][0]["on"]
          and C["fri1600"]["next"]["text"].endswith("on Monday") and C["sat1200"]["phase"] == "Weekend: no trading" and C["sat1200"]["next"]["text"].endswith("on Monday"), C)
    e = o["eras"]
    check("b. eval vs funded era (finder 2026-11-20): ATLAS's passed-eval +$1,792.50 (closed before it was funded, life.acc.since) is the eval's, not the funded account's; "
          "funded = -$112.80 + $514.18 = $401.38 (MFFU's $401); without the PC the plan's day (2026-11-17) splits the same",
          e["nq"] == [["atlas_eval", 1792.5], ["atlas", -112.8], ["atlas", 514.18]] and e["noPc"] == ["atlas_eval", "atlas"], e)
    op = o["opens"]
    check("b. the open trade, live: SHORT 6 @ 21,555.50 = +$315 = +1.42R (risk 18.5 pts x 6 x $2 = $222), target +$735; a moved stop says what is locked in, no R",
          len(op) == 2 and op[0]["r"] == 1.42 and op[0]["text"] == "SHORT 6 @ 21,555.50" and op[0]["sub"] == "target +$735" and op[1]["r"] is None
          and op[1]["sub"] == "stop moved: +$4 locked in", op)
    v = o["vix"]
    check("b. VIX 28.4 (elevated) of 2026-11-19 and the LIT target size: the 18:00 open +/- 475 pts; no brief = no line",
          v["text"] == "VIX 28.4 (elevated)" and "+/- 475 pts" in v["target"] and "banked at 8R" in v["target"] and v["date"] == "2026-11-19" and o["none"] is None, v)


def test_static():
    html = open(os.path.join(NQ, "index.html"), encoding="utf-8").read()
    js = open(os.path.join(NQ, "nqgoals.js"), encoding="utf-8").read() + open(os.path.join(NQ, "nqland.js"), encoding="utf-8").read()
    gi, ci = html.find('id="goalCard"'), html.find('id="chartCard"')
    check("a. static: the goals card sits right above the live chart (both on the first screen); the numbers and the 3D landscape cards; nqgoals.css",
          0 < gi < ci and 'id="numCard"' in html and 'id="landCard"' in html and "nqgoals.css?v=" in html, (gi, ci))
    check("a. static: the 3D landscape loads through lazy3d when near, skipped on LITE; goals.json fetched early in the head",
          'data-src="nqland.js?v=' in html and 'data-near="#landCard" data-skip="lite" data-event="nqland"' in html and "'../business/goals.json'" in html)
    check("a. static: text only through textContent (no innerHTML), no storage, no fetch in the modules, reduced motion respected",
          "innerHTML" not in js and "localStorage" not in js and "fetch(" not in js and "prefers-reduced-motion" in js)


SNAP = """() => { const r = (s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect() : null; };
  const tiles = [...document.querySelectorAll('#goals .gl-tile')].map((b) => ({ key: b.dataset.key, big: b.querySelector('.gl-big').textContent, pct: b.querySelector('.gl-pct').textContent,
    off: b.querySelector('.gl-arc').style.getPropertyValue('--to'), exp: b.getAttribute('aria-expanded'), h: b.getBoundingClientRect().height }));
  return { tiles, goalBottom: r('#goalCard').bottom + scrollY, chartTop: r('#chartCard').top + scrollY, boxBottom: r('#chartBox').bottom + scrollY, box: r('#chartBox').height,
    detail: document.querySelector('#goalDetail').hidden ? '' : document.querySelector('#goalDetail').textContent, age: document.querySelector('#goalAge').textContent,
    nums: document.querySelectorAll('#nums .nm-acct').length, stats: [...document.querySelectorAll('#nums .nm-stat b')].map((b) => b.textContent),
    clock: (document.querySelector('#nums .nm-next') || {}).textContent || '', open: [...document.querySelectorAll('#nums .nm-open')].map((d) => d.textContent), vix: (document.querySelector('#nums .nm-vix') || {}).textContent || '',
    land: !!window.NQLAND, land3d: !document.querySelector('#land3d').hidden, fb: getComputedStyle(document.querySelector('#landFb')).visibility,
    fbPaths: document.querySelectorAll('#landFb path').length, bursts: document.querySelectorAll('.gl-burst').length, cls: window.__cls || 0 }; }"""
CLS = """(() => { window.__cls = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: 'layout-shift', buffered: true }); } catch (e) {} })();"""


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_chart as NC, test_nq_page as NP
    post, _ = NC.fixture(NOW)
    real = NP.time.time
    NP.time.time = lambda: float(NOW)
    try:
        home = NP.home_json(3 * 3600)                     # the cloud's copy is 3 hours old: the PC's post (10 min) wins
    finally:
        NP.time.time = real
    core = json.dumps({"event": "message", "time": PC["reporter"]["t"], "message": json.dumps(PC)}) + "\n"
    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home})
    mock = {f"/{NC.TOPIC}-bars/json": NC.ndjson(post), f"/{NC.TOPIC}/json": core}

    def page(br, **kw):
        ctx, p, errs, seen, off = AK.page(br, origin, mock=mock, **kw)
        p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
        p.add_init_script(CLS)
        return ctx, p, errs, seen, off
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = page(br)
            NC.open_chart(p, origin)
            p.wait_for_function("document.querySelector('#goalAge').textContent.startsWith('updated')", timeout=30000)
            p.wait_for_timeout(1800)
            s = p.evaluate(SNAP)
            t = {x["key"]: x for x in s["tiles"]}
            check("c. the goals strip: 5 rings, ATLAS first with '$1,699' left at 19%, Zlarior 50K '+$3,807', 25K #2 '+$1,500', the fleet '1 of 5'; the PC's age on it",
                  [x["key"] for x in s["tiles"]][0] == "atlas" and len(s["tiles"]) == 5 and t["atlas"]["big"] == "$1,699" and t["atlas"]["pct"] == "19%"
                  and t["zlarior"]["big"] == "+$3,807" and t["fresh25"]["big"] == "+$1,500" and t["fleet"]["big"] == "1 of 5" and s["age"].startswith("updated 10 min"), s["tiles"])
            check("c. the first screen (390 x 844): the goals card above the chart and the whole chart box still on it (300-441 px tall)",
                  s["goalBottom"] <= s["chartTop"] and s["boxBottom"] <= 844 and 299 <= s["box"] <= 441, (s["goalBottom"], s["chartTop"], s["boxBottom"], s["box"]))
            p.locator('#goals .gl-tile[data-key="atlas"]').click()
            p.wait_for_timeout(300)
            d = p.evaluate(SNAP)
            check("c. tap ATLAS: its rules open below (MFFU's $401, the $1,000 ask at $2,100, $800 to you, the $250 minimum at $1,350, the date estimate), aria-expanded",
                  "Ask $1,000 at $2,100" in d["detail"] and "$800 to you" in d["detail"] and "$1,350: $949 more" in d["detail"] and "Dec 18-31 (estimate" in d["detail"]
                  and "its profit: $401" in d["detail"]
                  and {x["key"]: x for x in d["tiles"]}["atlas"]["exp"] == "true", d["detail"])
            p.locator('#goals .gl-tile[data-key="atlas"]').click()
            p.wait_for_timeout(200)
            check("c. tap it again: closed", p.evaluate(SNAP)["detail"] == "")
            p.evaluate("document.querySelector('#vaultCard').scrollIntoView()")
            p.wait_for_function("window.OLYMPUS_NQFX && document.querySelector('#vault').getAttribute('aria-label')", timeout=30000)
            v = p.evaluate("() => ({ hidden: document.querySelector('#vaultCard').hidden, pill: document.querySelector('#vaultPill').textContent, note: document.querySelector('#vaultNote').textContent, aria: document.querySelector('#vault').getAttribute('aria-label') || '', h: document.querySelector('#vault').getBoundingClientRect().height, kids: document.querySelector('#vault').children.length })")
            check("c. the ATLAS payout vault (DESIGN's NQFX.vault): 19%, MFFU's $401 of $2,100, $800 to you, the study's date; a fixed 4:3 box drawn at once",
                  not v["hidden"] and v["pill"] == "19%" and "MFFU shows $401 of profit" in v["note"] and "$1,699 to go" in v["note"] and "Dec 18-31" in v["note"]
                  and "$401 of $2,100" in v["aria"] and 200 <= v["h"] <= 341 and v["kids"] >= 1, v)
            p.evaluate("document.querySelector('#numCard').scrollIntoView()")
            p.wait_for_timeout(1500)
            n = p.evaluate(SNAP)
            check("c. the numbers card: the open trade with its live $ and R, today / this week per account, win rate + PF + real fills + net, the session clock, the VIX band",
                  n["nums"] >= 3 and len(n["stats"]) == 4 and any("Zlarior 50K: SHORT 6" in x and "R live" in x for x in n["open"]) and n["stats"][0].endswith("%") and "window" in n["clock"] and n["vix"].startswith("VIX 28.4 (elevated)"), n)
            p.evaluate("document.querySelector('#landCard').scrollIntoView()")
            p.wait_for_function("window.NQLAND || document.querySelectorAll('#landFb path').length > 0", timeout=30000)
            p.wait_for_timeout(2500)
            L = p.evaluate(SNAP)
            check("c. the 3D landscape loads when near (or the 2D picture stays when WebGL is missing); one of the two always shows",
                  (L["land"] and L["land3d"] and L["fb"] == "hidden") or (not L["land3d"] and L["fbPaths"] >= 2), L)
            check("c. no sideways scroll, taps >= 44 px, no console error, nothing off the origin but the feed",
                  AK.no_sideways(p) and not AK.taps(p) and not errs and not off, (AK.taps(p)[:4], errs[:3], off[:3]))
            check(f"c. layout shift from load to the end (the PC's post arriving included) < 0.05 (here {L['cls']:.3f})", L["cls"] < 0.05, L["cls"])
            ctx.close()
            # reduced motion + LITE: the numbers at once, no burst, no 3D fetched, the 2D picture
            ctx, p, errs, seen, off = page(br, reduced=True, lite=True)
            NC.open_chart(p, origin)
            p.wait_for_function("document.querySelector('#goalAge').textContent.startsWith('updated')", timeout=30000)
            p.evaluate("document.querySelector('#landCard').scrollIntoView()")
            p.wait_for_timeout(2500)
            r = p.evaluate(SNAP)
            check("c. reduced motion + LITE: '$1,699' at once, no burst canvas, the 3D not fetched, the 2D landscape drawn, no error",
                  {x["key"]: x for x in r["tiles"]}["atlas"]["big"] == "$1,699" and r["bursts"] == 0 and not r["land"] and r["fbPaths"] >= 2
                  and not any("nqland" in u for u in seen) and not errs, (r, errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()
    # the DEMO (no home.json: the perf sweep's page): the thinking cards' long values must still wrap (a global no-wrap on .dk-kv made it 407 px wide)
    srv, origin = AK.serve({"/home.json": None})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "nq")
            p.wait_for_timeout(1500)
            check("c. the DEMO page (no home.json): the goals strip draws, no sideways scroll at 390 px, no console error",
                  p.evaluate("document.querySelectorAll('#goals .gl-tile').length") >= 4 and AK.no_sideways(p)
                  and p.evaluate("document.documentElement.scrollWidth") <= 390 and not errs, (p.evaluate("document.documentElement.scrollWidth"), errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
