"""NQ BRAIN (owner 2026-11-20 19:50 ET: "a brain for each bot ... the steps in order for a trade, and tons more";
research/handoff/2026-11-21/brain3d/SPEC.md): tools/web_public/nq/brain.html + brain.js + braincore.js (+ brain.css), the Brain tab of NQ.
On the PC's real post of 2026-11-20 ~10:20 ET (tests/fixtures/truth/pc_post.json).
  a. static   the page, its own module, text only through textContent, no storage / POST / dynamic import, three.js never on the NQ desk
              page (the Brain loads DESIGN's 3D only on its own page, after the first paint, never on LITE); the Desk links to the Brain
  b. node     Zlarior: the 10 stages of engine/brain.py in order, 'now' = 5m CISD (5/10), 1-4 passed; ATLAS: three lobes (EMA done, MACD
              armed, S/R); the levels with distance in points and $ a micro; memory (one trade per day + $, the streak, the edge GREEN);
              the risk ring (drawdown, DLL, best day 128% of the cycle, the 7-day clock, what the PC does not send says so); ATLAS's
              payout ring (MFFU $401 -> $2,100); health; replay of today's trade; the glass card (now / why / what would change my mind)
  c. Chromium 390 x 844: both bots with the post, the switch, a step's glass card opens and closes (Escape), no sideways scroll, taps >= 44 px,
              no console error; reduced motion; no PC post = the site's copy said plainly
    python -X utf8 -m tests.test_nq_brain [--static]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
NQ = os.path.join(AK.WEB, "nq")
PC = json.load(open(os.path.join(AK.ROOT, "tests", "fixtures", "truth", "pc_post.json"), encoding="utf-8"))
NOW = PC["reporter"]["t"] + 600


def test_static():
    html = open(os.path.join(NQ, "brain.html"), encoding="utf-8").read()
    js = open(os.path.join(NQ, "brain.js"), encoding="utf-8").read() + open(os.path.join(NQ, "braincore.js"), encoding="utf-8").read()
    desk = open(os.path.join(NQ, "index.html"), encoding="utf-8").read()
    check("a. the Brain page: its module, the 2D steps list, the bot switch (Zlarior / ATLAS), every module card, the glass card dialog",
          'src="brain.js?v=' in html and 'id="bSteps"' in html and 'data-bot="lit"' in html and 'data-bot="atlas"' in html
          and all(f'id="{i}"' in html for i in ("thinkCard", "watchCard", "gradeCard", "riskCard", "planCard", "memCard", "payCard", "acctCard", "replayCard", "healthCard"))
          and 'role="dialog"' in html and "brain.css?v=" in html)
    check("a. text only through textContent: no innerHTML / eval / dynamic import / storage / POST / beacon in brain.js + braincore.js",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|\bimport\s*\(|localStorage|sessionStorage|indexedDB|sendBeacon|method:\s*['\"]POST", js))
    check("a. three.js never on the NQ desk page (the 3D brain is the Brain page's alone, after the first paint, never on LITE); the Desk links to the Brain",
          "brain3d" not in desk and 'href="brain.html"' in desk and '<script src="../olympus/brain3d.js?v=' in html and "O.lite" in html
          and html.index("brain3d.js?v=") < html.index("</head>") and "brain3d.js?v=b1\" defer" not in html)
    ids = re.findall(r"\{ id: '([a-z0-9]+)', name: '[^']+' \}", html)
    core = open(os.path.join(NQ, "braincore.js"), encoding="utf-8").read()
    lit = re.findall(r"\['([a-z0-9]+)', '[^']+', '", core)[:10]
    check("a. the brain's regions in brain.html = braincore's (LIT's 10 engine stages, ATLAS's 3 lobes); read only: no Arm / Start / Stop / Flatten control",
          ids[7:17] == lit and ids[:3] == ["ema", "macd", "sr"] and not re.search(r">\s*(Arm|Start|Stop|Flatten)\b", html), (ids, lit))


JS = r"""
const path = require('path'), W = process.argv[2], NOW = +process.argv[3];
global.PC_FEED = require(path.join(W, 'pc_feed.js'));
const COACH = require(path.join(W, 'business', 'payoutcoach.js')), PC = require(path.join(W, '..', '..', 'tests', 'fixtures', 'truth', 'pc_post.json'));
(async () => {
  const BC = await import(path.join(W, 'nq', 'braincore.js'));
  const home = PC_FEED.homeOver({}, PC, NOW, COACH);
  const src = { lite: PC, home, biz: require(path.join(W, 'business', 'accounts.json')), goals: require(path.join(W, 'business', 'goals.json')), brief: require(path.join(W, 'nq', 'brief.json')),
    news: require(path.join(W, 'nq', 'news_week.json')), edge: require(path.join(W, 'edge.json')), file: require(path.join(W, 'trading', 'trades.json')) };
  const z = BC.brain('lit', src, NOW), a = BC.brain('atlas', src, NOW);
  const stopped = JSON.parse(JSON.stringify(PC)); stopped.pc.running = false;
  const zs = BC.brain('lit', { ...src, lite: stopped }, NOW), none = BC.brain('lit', { home: {}, biz: src.biz }, NOW);
  // glance v2 (engine/brain_glance v2 + the ext block glog, day-nqdash3 2026-11-21)
  const P2 = JSON.parse(JSON.stringify(PC)), gb = P2.pc.glance.bots; P2.pc.glance.v = 2; delete P2.price;
  const L2 = gb.find((b) => b.id === 'lit'), A2 = gb.find((b) => b.id === 'atlas');
  Object.assign(L2, { chk: [6, 9], blk: ['Daily loss guard: -$1,000 reached'], px: 26000.25 });
  Object.assign(A2, { lobes: [{ id: 'ema', st: 'off', text: 'No trades on Mondays (rule)' }, { id: 'macd', st: 'trade', text: 'In a paper short from 09:40 ET' }, { id: 'sr', st: 'window', text: 'Waiting for a pullback' }], dll: 600, dll_used: 150, px: 26000.25 });
  P2.glog = { lit: Array.from({ length: 8 }, (_, i) => ['10:' + String(20 - i).padStart(2, '0'), 'line ' + i]), atlas: [['10:01', 'MACD: one']] };
  const z2 = BC.brain('lit', { ...src, lite: P2 }, NOW), a2 = BC.brain('atlas', { ...src, lite: P2 }, NOW);
  const v2 = { grade: z2.grade, think: z2.thoughts, athink: a2.thoughts, regions: a2.regions, steps: a2.steps.filter((s) => s.lobe === 'ema').map((s) => s.state),
    cur: a2.current && a2.current.label, dll: a2.risk.find((r) => r.k === 'dll'), lpx: z2.watch.length && z2.watch[0].dist };
  // audit E3 (2026-11-22): the core's "ar" {bot: [on, armed]} wins over the (up to 44 min old) glance; b25k_2 / Rapid armed on the desk rows
  const P3 = JSON.parse(JSON.stringify(PC)); P3.ar = { lit: [1, 0], b25k_2: [1, 1], rapid: [0, 0] };
  const z3 = BC.brain('lit', { ...src, lite: P3 }, NOW);
  const ar = { armed: z3.armed, on: z3.on, run: z3.health[3].value, acc: z3.accounts.map((x) => [x.key, x.armed === undefined ? null : x.armed]),
    f: BC.accountArmed(P3, 'fresh25'), r: BC.accountArmed(P3, 'rapid1'), none: BC.accountArmed(PC, 'fresh25') };
  console.log(JSON.stringify({ ar, v2, z, a, zs: { stopped: zs.stopped, states: zs.steps.map((s) => s.state) }, none: { has: none.has, steps: none.steps.length, health: none.health },
    n: [BC.stageN('5m CISD (5/10)'), BC.stageN('Sweep'), BC.stageN(''), BC.stageN('In trade (9/10)')] }));
})().catch((e) => console.log(JSON.stringify({ err: String(e && e.stack || e) })));
"""


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("b. node skipped", True)
        return
    tmp = os.path.join(AK.ROOT, "tests", "fixtures", "_nq_brain.cjs")
    try:
        open(tmp, "w", encoding="utf-8").write(JS)
        r = subprocess.run([exe, tmp, AK.WEB, str(NOW)], capture_output=True, text=True, timeout=60)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"err": r.stderr[-800:]}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if "err" in o:
        check("b. the node harness ran", False, o["err"])
        return
    z, a = o["z"], o["a"]
    ar = o["ar"]
    check("b. 'ar' in the core post wins: Zlarior [on 1, armed 0] reads 'on, not armed' though the glance says armed; b25k_2 armed, Rapid off",
          ar["armed"] is False and ar["on"] is True and ar["run"] != "armed, live" and ar["f"] == {"on": True, "armed": True}
          and ar["r"] == {"on": False, "armed": False}, ar)
    check("b. stageN: '5m CISD (5/10)' = 5, a bare label = its place, none = null, 'In trade (9/10)' = 9", o["n"] == [5, 2, None, 9], o["n"])
    check("b. Zlarior: the 10 stages of engine/brain.py in order (Levels ... Done for today), 1-4 passed, 5m CISD NOW, 6-10 waiting; armed, LIVE",
          [s["label"] for s in z["steps"]][:5] == ["Levels", "Sweep", "Inducement", "Displacement", "5m CISD"] and len(z["steps"]) == 10
          and [s["state"] for s in z["steps"]] == ["done"] * 4 + ["now"] + ["wait"] * 5 and z["current"]["key"] == "cisd5" and z["armed"] and z["mode"] == "LIVE", z["steps"])
    c = z["cards"]["cisd5"]
    check("b. the glass card of the NOW step: what I'm doing now (the PC's wait), why (the 09:35 rejected setup), what would change my mind (the next step's rule)",
          c["now"].startswith("5m CISD already closed through 26,117.50") and "09:35 SHORT setup" in c["why"] and c["change"].startswith("What moves it on: A limit order at the CISD level"), c)
    check("b. ATLAS: three lobes in order (EMA done for today, MACD armed, S/R), 5 steps each, the NOW step is 'MACD · Armed'",
          [r["id"] for r in a["regions"]] == ["ema", "macd", "sr"] and a["regions"][0]["state"] == "done" and a["regions"][1]["state"] == "armed"
          and len(a["steps"]) == 15 and a["current"]["label"] == "MACD · Armed", (a["regions"], a["current"]))
    v = o["v2"]
    check("b. glance v2: Zlarior's setup checks (6 of 9 passed) and what blocks a trade come from the PC; no made-up A-D grade",
          v["grade"]["gradeText"] == "Latest setup: 6 of 9 checks passed" and v["grade"]["blocks"] == ["Daily loss guard: -$1,000 reached"] and v["grade"]["grade"] is None, v["grade"])
    check("b. glance v2: the thought stream = the ext 'glog' (8 lines, oldest first) when it is longer than the glance's",
          len(v["think"]) == 8 and v["think"][0]["text"] == "line 7" and v["think"][-1]["text"] == "line 0", v["think"])
    check("b. glance v2: ATLAS's lobes from the PC's states (EMA off, MACD in trade = the NOW step, S/R window); the off lobe's steps read off",
          [r["state"] for r in v["regions"]] == ["off", "trade", "window"] and v["steps"] == ["off"] * 5 and v["cur"] == "MACD · In trade", (v["regions"], v["steps"], v["cur"]))
    check("b. glance v2: ATLAS's daily loss node = $150 of $600 (ok) from the glance (its account row has none)",
          v["dll"]["value"] == "$150 of $600" and v["dll"]["level"] == "ok", v["dll"])
    check("b. glance v2: with no top-level price, the level distances still come (the glance's own lv points or px)", v["lpx"] is not None, v["lpx"])
    w = z["watch"]
    check("b. what I watch: the PC's levels with distance in points and $ a micro (NY 08:30 high 142.5 pts = $285 a micro) and what a sweep would mean",
          w[0]["name"] == "NY 08:30 high" and w[0]["distText"] == "142.5 pts ($285 a micro)" and "I look for a" in w[0]["ifTouch"], w[:1])
    m = a["memory"]
    check("b. memory: one row per trade (the PC's 'at' + the file, no double), newest first (+$514.18 TARGET), the streak, edge GREEN (PF over 40 sessions), last night's scorecard line",
          m["last"][0]["usd"] == 514.18 and len({(x["day"], round(abs(x["usd"] or 0))) for x in m["last"]}) == len(m["last"]) and m["streak"]["text"] == "1 win in a row"
          and m["edge"]["light"] == "GREEN" and "ATLAS" in m["learn"], m)
    R = {r["k"]: r for r in a["risk"]}
    check("b. the risk ring: drawdown left $1,401 above the floor, best day 128% of the cycle (max 50%) = amber, the 7-day clock, the price limit and hedge guard say 'not sent by the PC yet'",
          R["dd"]["value"].startswith("$1,401 above the floor") and R["best"]["value"] == "128% of the cycle (max 50%)" and R["best"]["level"] == "warn"
          and R["idle"]["value"] == "0 days since the last trade" and R["limit"]["value"] == "not sent by the PC yet" and R["hedge"]["level"] == "unknown", a["risk"])
    check("b. ATLAS's payout ring in MFFU's terms: $1,699 to $2,100 (19%); Zlarior has none; accounts: ATLAS funded at MFFU $401",
          a["payout"]["big"] == "$1,699" and a["payout"]["unit"] == "to $2,100" and abs(a["payout"]["frac"] - 0.191) < 0.01 and z["payout"] is None
          and any(x["key"] == "atlas" and abs(x["balance"] - 401.38) < 0.01 for x in a["accounts"]), (a["payout"], a["accounts"]))
    check("b. plan for today: ATLAS's lobe windows from the brief (EMA 03:00-09:30, MACD 02:00-05:00 + 09:30-11:00, S/R 09:30-12:00), open / over at 10:30 ET",
          [(x["who"], x["from"], x["state"]) for x in a["plan"]["windows"]][:2] == [("ATLAS EMA", "03:00", "over"), ("ATLAS MACD", "02:00", "over")]
          and any(x["state"] == "open" for x in a["plan"]["windows"]), a["plan"]["windows"])
    check("b. health: the PC report age, the brain glance, NinjaTrader, the bot armed / on; replay: today's ATLAS trade (in 03:45, out +$514)",
          [h["k"] for h in z["health"]] == ["pc", "brain", "nt", "run"] and z["health"][3]["value"] == "armed, live" and a["replay"]["frames"][0]["text"].startswith("03:45 ET: Short 1")
          and "+$514" in a["replay"]["frames"][1]["text"], (z["health"], a["replay"]))
    check("b. a STOPPED bot (pc.running false): every step not yet passed is 'off', the brain says stopped; no PC post: no glance, still 10 steps, the PC health red",
          o["zs"]["stopped"] and "off" in o["zs"]["states"] and "now" not in o["zs"]["states"] and not o["none"]["has"] and o["none"]["steps"] == 10
          and o["none"]["health"][0]["level"] == "bad", (o["zs"], o["none"]))


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_chart as NC, test_nq_page as NP
    real = NP.time.time
    NP.time.time = lambda: float(NOW)
    try:
        home = NP.home_json(3 * 3600)
    finally:
        NP.time.time = real
    core = json.dumps({"event": "message", "time": PC["reporter"]["t"], "message": json.dumps(PC)}) + "\n"
    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home})
    SNAP = """() => ({ h: document.querySelector('#brainH').textContent, mode: document.querySelector('#bMode').textContent, status: document.querySelector('#bStatus').textContent,
      steps: [...document.querySelectorAll('#bSteps .bstep')].map((li) => li.className.replace('bstep ', '')), now: document.querySelector('#bNow').textContent,
      pressed: [...document.querySelectorAll('.bsw')].map((b) => b.getAttribute('aria-pressed')), pay: !document.querySelector('#payCard').hidden,
      risk: document.querySelectorAll('#bRisk li').length, watch: document.querySelectorAll('#bWatch li').length, three: !!window.BRAIN3D || [...document.scripts].some((s) => /brain3d/.test(s.src)) })"""

    def open_brain(p, q=""):
        p.goto(f"{origin}/nq/brain.html{q}")
        p.wait_for_function("window.NQBRAIN && window.NQBRAIN.ready()", timeout=60000)
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{NC.TOPIC}/json": core})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
            open_brain(p)
            p.wait_for_function("document.querySelector('#bStatus').textContent.startsWith('From your PC')", timeout=30000)
            s = p.evaluate(SNAP)
            check("c. Zlarior's brain at 390 x 844 from the PC's post: ARMED, 1-4 passed, 5m CISD now (pulsing), 6-10 waiting, the risk ring and the levels drawn",
                  s["h"] == "Zlarior's brain" and s["mode"] == "ARMED" and s["steps"] == ["done"] * 4 + ["now"] + ["wait"] * 5 and s["now"].startswith("Now: 5m CISD")
                  and s["risk"] == 7 and s["watch"] == 2 and s["pressed"] == ["true", "false"] and not s["pay"], s)
            p.locator("#bSteps .bstep.now button").click()
            p.wait_for_timeout(200)
            card = p.evaluate("() => ({ open: !document.querySelector('#bCardSheet').hidden, t: document.querySelector('#bCardH').textContent, c: document.querySelector('#bCardChange').textContent })")
            p.keyboard.press("Escape")
            p.wait_for_timeout(150)
            closed = p.evaluate("document.querySelector('#bCardSheet').hidden")
            check("c. tap the NOW step: the glass card (5. 5m CISD: now / why / what would change my mind); Escape closes it",
                  card["open"] and card["t"] == "5. 5m CISD" and card["c"].startswith("What moves it on") and closed, (card, closed))
            p.locator('.bsw[data-bot="atlas"]').click()
            p.wait_for_timeout(300)
            a = p.evaluate(SNAP)
            check("c. switch to ATLAS: its brain (three lobes, 15 steps, MACD armed now), the payout ring card shown",
                  a["h"] == "ATLAS's brain" and len(a["steps"]) == 15 and a["steps"].count("now") == 1 and a["pay"] and a["pressed"] == ["false", "true"], a)
            try:
                p.wait_for_function("window.NQBRAIN_3D && window.NQBRAIN_3D.api && window.NQBRAIN_3D.api.mode === '3d'", timeout=30000)
            except Exception:
                pass
            t3 = p.evaluate("() => { const T = window.NQBRAIN_3D; return T ? { bot: T.bot, mode: T.api.mode, st: T.api.stats(), cur: T.api.state.currentId, s: T.api.state.stageStates, ring: T.api.state.ringValues } : null; }")
            check("c. DESIGN's 3D brain (olympus/brain3d.js) on the Brain page: switched to ATLAS = the lobes layout (3 regions, 4 ring nodes), MACD current, EMA passed, the ring values from the risk ring",
                  t3 and t3["bot"] == "atlas" and t3["cur"] == "macd" and t3["s"]["ema"] == "passed" and t3["s"]["macd"] == "current"
                  and (t3["mode"] != "3d" or (t3["st"]["regions"] == 3 and t3["st"]["ring"] == 4)) and t3["ring"]["dd"].startswith("$1,401"), t3)
            cls = p.evaluate("() => new Promise((ok) => { let v = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) v += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} setTimeout(() => ok(v), 300); })")
            check(f"c. no sideways scroll, taps >= 44 px, no console error, nothing off the origin but the PC feed; layout shift {cls:.3f} < 0.05",
                  AK.no_sideways(p) and not AK.taps(p) and not errs and not off and cls < 0.05, (AK.taps(p)[:4], errs[:3], off[:3], cls))
            AK.shot(p, "nq-brain-atlas")
            ctx.close()
            # reduced motion + no PC post: the site's copy said plainly, the steps still there
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True, mock={f"/{NC.TOPIC}/json": "{}"})
            open_brain(p, "?bot=atlas")
            p.wait_for_timeout(1500)
            n = p.evaluate(SNAP)
            anim = p.evaluate("getComputedStyle(document.querySelector('#bSteps .bstep .bstepb')).animationName")
            check("c. no PC post + reduced motion: 'the site's copy' said, NO REPORT, the 15 ATLAS steps still listed, no pulse, no error",
                  "has not arrived" in n["status"] and n["mode"] == "NO REPORT" and len(n["steps"]) == 15 and anim in ("none", "") and not errs, (n, anim, errs[:2]))
            ctx.close()
            # LITE: no 3D brain at all (the steps list says everything), and the Zlarior brain in 3D: the path layout, 5m CISD current
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True, mock={f"/{NC.TOPIC}/json": core})
            open_brain(p)
            p.wait_for_timeout(2500)
            lt = p.evaluate("() => ({ t: window.NQBRAIN_3D || null, three: performance.getEntriesByType('resource').some((r) => /three\\.module|brain3d-scene/.test(r.name)), steps: document.querySelectorAll('#bSteps .bstep').length })")
            check("c. LITE: no 3D brain mounted and no three.js fetched; the 10 steps still there", lt["t"] is None and not lt["three"] and lt["steps"] == 10 and not errs, (lt, errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
