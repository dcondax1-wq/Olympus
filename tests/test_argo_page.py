"""ARGO, the OLYMPUS voyage (tools/web_public/argo/, AGORA look, 2026-11-10): the owner's money goals as islands on a sea map, progress from PUBLISHED numbers only, honest ETA ranges, editable goals.

  a. static: the files, the kit lines, the AGORA look, read-only data (the only thing kept is the goals), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (argocore.js): months, the low / base / high rate, ETA ranges and when none is shown, goal clean / export / import, the map layout and ship, the Jarvis card; the trireme scene drawn onto a fake canvas (argoscene.js)
  c. Chromium 390 x 844 (and 375 x 667): DEMO voyage, tap an island, add / edit / delete / reset goals (kept after a reload), export and import, the real home.json (no payouts = no date), LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_argo_page            (--static: parts a and b only)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "argo", "Argo"
check = AK.check
READS = ("../home.json", "../ledger/rules.json")


def test_static():
    AK.static_kit(APP, NAME, reads=READS, storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "argo.js")) + AK.read(os.path.join(d, "argocore.js")) + AK.read(os.path.join(d, "argoscene.js"))
    check("a. the only thing kept in the browser is the owner's goals (one key, try / catch); no sessionStorage / indexedDB / cookies", len(re.findall(r"localStorage\.", js)) == 2 and "argo.goals.v1" in js and not re.search(r"sessionStorage|indexedDB|document\.cookie", js))
    check("a. the scene is pure maths on a 2D context: no WebGL, no document, no fetch, no window", not re.search(r"webgl|THREE|\bdocument\.|\bfetch\(|\bwindow\.", re.sub(r"//[^\n]*", "", AK.read(os.path.join(d, "argoscene.js"))), re.I))
    check("a. it never trades or asks for a key: no order / key / wallet words in the page code", not re.search(r"api[_-]?key|secret|wallet|place_?order|new_?order", js, re.I))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. page order: next island, the ship, the map, this island, the ladder, your goals", html.index('id="nextName"') < html.index('id="scene"') < html.index('id="map"') < html.index('id="selName"') < html.index('id="ladder"') < html.index('id="goalsEdit"'))
    check("a. 'not a promise' and the honest-ETA rule are on the page; export / import and add / reset controls exist", "not a promise" in html and all(i in html for i in ('id="exportBtn"', 'id="importBtn"', 'id="addBtn"', 'id="resetBtn"', 'id="ioText"')))
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture has accounts and dated payouts (offsets from today), labelled EXAMPLE", "EXAMPLE" in fx["note"] and fx["accounts"] and fx["payouts"] and all("off" in p for p in fx["payouts"]))


HARNESS = r"""
Promise.all([import(process.argv[2]), import(process.argv[3])]).then(([C, X]) => {
  const o = {}, T = '2026-11-10';
  o.words = [C.money(1234.4), C.money(-5), C.pct(0.664), C.pct(2), C.pct(-1), C.addMonths('2026-11', 3), C.addMonths('2026-12', 1), C.addMonths('2026-01', -2), C.monthText('2026-03'), C.etaMonth(T, 2.9), C.etaMonth(T, 3), C.etaMonth(T, 0.2), C.valueText({ type: 'paid' }, 2100), C.goalText({ type: 'month', target: 10000 })];
  const home = { accounts: [{ id: 'a', kind: 'funded' }, { id: 'b', kind: 'eval' }, { id: 'c', kind: 'Funded', payouts: [{ usd: 100, date: '2026-05-01' }] }], payouts: [{ usd: 500, date: '2026-06-10' }, { usd: 700, date: '2026-07-15' }, { amount: 300, date: '2026-07-20' }, { usd: 600, date: '2026-09-05' }, { usd: -5, date: '2026-09-06' }, { usd: 50 }, { usd: 'x', date: '2026-09-07' }, null] };
  const H = C.normHome(home), H0 = C.normHome(null);
  o.home = [H.has, H.accounts, H.funded, H.payouts.length, H.payouts[0].date, H0.has, H0.payouts.length, C.normHome({ payouts: [] }).has, C.normHome({ accounts: 'x' }).has];
  const F = C.facts(home, null, T);
  o.facts = [F.paid, F.payouts, F.funded, F.n, F.months.map((m) => m.ym + ':' + m.usd + ':' + m.count).join(' '), F.low, F.base, F.high, F.firstPayout, F.R.min, F.R.buffer];
  const none = C.facts({ accounts: [{ kind: 'eval' }] }, null, T), cur = C.facts({ accounts: [], payouts: [{ usd: 400, date: '2026-11-02' }] }, null, T), one = C.facts({ accounts: [], payouts: [{ usd: 400, date: '2026-10-02' }] }, null, T);
  o.thin = [none.n, none.paid, none.base, cur.n, cur.base, one.n, one.low, one.base, one.high];
  const many = []; for (let m = 1; m <= 10; m++) many.push({ usd: 100 * m, date: `2026-${String(m).padStart(2, '0')}-05` });
  const Fm = C.facts({ accounts: [], payouts: many }, null, '2026-11-10');
  o.window = [Fm.n, Fm.months[0].ym, Fm.months[5].ym, Fm.high, Fm.low];
  const R = C.rulesFrom({ plans: { builder_50k: { payout: { min: 600, buffer: 2500, max: 1500, split: 0.9, max_payouts: 4 } } } }), R0 = C.rulesFrom(null), Rj = C.rulesFrom({ plans: { builder_50k: { payout: { min: -1, buffer: 'x' } } } });
  o.rules = [R.min, R.buffer, R.max, R.split, R.max_payouts, R0.min, R0.max_payouts, Rj.min, Rj.buffer];
  const gs = C.normGoals(C.DEFAULT_GOALS), g5k = gs[2];
  const e5 = C.eta(g5k, F, T);
  o.eta = [e5.kind, e5.n, e5.fast, e5.base, e5.slow, e5.fastM, e5.baseM, e5.slowM, e5.text.includes('does not arrive'), e5.text.includes('not a promise'), e5.text.includes('last 6 full months')];
  const eNo = C.eta(g5k, none, T), eOne = C.eta(g5k, one, T), eFund = C.eta(gs[3], F, T), eMon = C.eta(gs[4], F, T), eDone = C.eta(gs[1], F, T);
  o.etaNone = [eNo.kind, eNo.text, eOne.kind, eOne.text.includes('needs at least 2'), eFund.kind, eFund.text.includes('No pace is published'), eMon.kind, eMon.text.includes('a pace, not a pile'), eDone.kind];
  const Fz = C.facts({ accounts: [], payouts: [{ usd: 100, date: '2026-05-05' }, { usd: 100, date: '2026-04-05' }] }, null, '2026-11-10');
  const FzA = { ...Fz, low: 0, base: 0, high: 0, n: 3 };
  o.etaZero = [C.eta(g5k, FzA, T).text.includes('paid nothing')];
  const gp = { id: 'p', name: 'Ten payouts', type: 'payouts', target: 10 }, ep = C.eta(gp, F, T);
  o.payoutsEta = [ep.kind, ep.rates.base, ep.text.includes('a month')];
  o.prog = gs.map((g) => { const p = C.progress(g, F); return [Math.round(p.frac * 100), p.done]; });
  o.takes = [C.takes(gs[0], F).includes('$500'), C.takes(gs[1], F).includes('$2,200 so far'), C.takes(gs[3], F).includes('2 funded now'), C.takes(gs[4], F).includes('pace'), C.actions(gs[2], F).length, C.actions(gs[0], none).length, C.actions(gs[1], F).length, C.actions(gs[3], F).length, C.actions(gs[4], F).length, C.actions(gs[0], { ...F, payouts: 5 })[0].startsWith('Keep the rules')];
  const bad = C.normGoals([{ id: 'x', name: ' Good ', type: 'paid', target: '2,500' }, { name: '', type: 'paid', target: 5 }, { name: 'N', type: 'nope', target: 5 }, { name: 'T', type: 'paid', target: -4 }, { name: 'Big', type: 'paid', target: 1e9 }, null, 7, { id: 'x', name: 'Dup', type: 'funded', target: 2.4 }, { name: '<b>Tag</b>', type: 'month', target: 99.6 }, { id: 'bad id!', name: 'Odd', type: 'payouts', target: 0.2 }]);
  o.goals = [bad.length, bad.map((g) => g.id).join(','), bad.map((g) => g.name).join('|'), bad.map((g) => g.target).join(','), C.normGoals('x').length, C.normGoals(Array.from({ length: 30 }, (_, i) => ({ name: 'G' + i, type: 'paid', target: 10 }))).length, C.nextId(gs), C.nextId([{ id: 'g2' }])];
  const ex = C.exportJson(gs), back = C.parseImport(ex), arr = C.parseImport(JSON.stringify([{ name: 'A', type: 'paid', target: 5 }, { name: '', type: 'paid', target: 5 }]));
  o.io = [back.ok, back.goals.length, JSON.parse(ex).kind, JSON.parse(ex).v, arr.ok, arr.goals.length, arr.dropped, C.parseImport('{nope').ok, C.parseImport('{"goals":3}').ok, C.parseImport('{"goals":[{"name":""}]}').ok, C.parseImport('').ok, C.parseImport('{nope').error.includes('valid JSON')];
  const lay = C.layout(5), ship = C.shipAt(gs, F, lay), shipAll = C.shipAt([gs[0]], F, C.layout(1)), shipNone = C.shipAt([], F, C.layout(0));
  o.map = [lay.pts.length, lay.pts.every((p) => p.x > 20 && p.x < 340 && p.y > 20 && p.y < 420), lay.pts[0].y > lay.pts[4].y, ship.next, Math.round(ship.frac * 100), ship.x > Math.min(lay.pts[1].x, lay.pts[2].x) - 1 && ship.x < Math.max(lay.pts[1].x, lay.pts[2].x) + 1, shipAll.next, shipNone.next, C.layout(0).pts.length];
  const sm = C.summary(gs, F), sa = C.summary([gs[0]], F), s0 = C.summary([], F);
  o.summary = [sm.done, sm.total, sm.next, sm.text, sa.next, sa.text.startsWith('All 1 islands reached'), s0.text];
  const card = C.jarvisCard(gs, F, T, 1793394000, false), cd = C.jarvisCard(gs, F, T, 5, true);
  o.card = [card.name, card.status.level, card.status.label, card.kpis.map((k) => k.value), card.lines.length, Number.isInteger(card.t), cd.status.level, JSON.stringify(card).length < 8000, card.lines.every((l) => l.length <= 120)];
  const dh = C.demoHome({ accounts: [{ kind: 'funded' }], payouts: [{ usd: 5, off: 10 }, { usd: 6, off: 0 }] }, T);
  o.demo = [dh.payouts.map((p) => p.date).join(','), dh.accounts.length, C.demoHome(null, T).payouts.length];
  const ctx = { fills: 0, clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, closePath() {}, arc() {}, fill() { this.fills++; }, stroke() {}, createLinearGradient() { return { addColorStop() {} }; }, set fillStyle(v) {}, set strokeStyle(v) {}, set lineWidth(v) {}, set lineJoin(v) {} };
  const nHi = X.draw(ctx, 340, 200, 0.6, 0.5, 'high'), nLo = X.draw(ctx, 340, 200, 0.6, 0.5, 'low'), nT = X.draw(ctx, 340, 200, 3.1, 1, 'high');
  const sc = X.scene(0.6, 0.5, 'high'), small = X.scene(0.6, 0, 'high'), big = X.scene(0.6, 1, 'high'), proj = X.project(sc, -0.62, 0.3, 340, 200);
  const top = (s) => Math.max(...X.island(4.6, -2.6, s).flatMap((q) => q.p.map((p) => p[1])));
  o.scene = [nHi > 250, nLo < nHi, nT > 250, sc.every((q) => q.p.every((p) => p.every(Number.isFinite))), proj.every((f, i) => i === 0 || proj[i - 1].z <= f.z), top(1.2) > top(0.35) && big.length > small.length - 1, X.hullAt(0).w > X.hullAt(1.2).w, X.hullAt(1.25).deck > X.hullAt(0).deck, X.trireme(0, 0).length > 60, ctx.fills > 0];
  console.log(JSON.stringify(o));
});
"""


def node_run():
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="argo-")
    try:
        for n in ("argocore", "argoscene"):
            shutil.copy(os.path.join(AK.WEB, APP, n + ".js"), os.path.join(tmp, n + ".mjs"))
        h = os.path.join(tmp, "harness.cjs")
        open(h, "w", encoding="utf-8").write(HARNESS)
        r = subprocess.run([exe, h, os.path.join(tmp, "argocore.mjs"), os.path.join(tmp, "argoscene.mjs")], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[-1500:])
            return {"_error": r.stderr[-600:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_maths():
    o = node_run()
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: $1,234, -$5, 66%, 100% and 0% clamps, month maths over a year end, 'Mar 2026', ETA months round UP and never say 'this month' (2.9 -> +3, exactly 3 -> +3, 0.2 -> +1)",
          o["words"] == ["$1,234", "-$5", "66%", "100%", "0%", "2027-02", "2027-01", "2025-11", "Mar 2026", "Feb 2027", "Feb 2027", "Dec 2026", "$2,100", "$10,000 a month"], o["words"])
    check("b. home.json: funded accounts counted (any letter case), payouts from the top and from accounts, only dated positive dollars, sorted; nothing published = not there",
          o["home"] == [True, 3, 2, 5, "2026-05-01", False, 0, True, False], o["home"])
    check("b. the real numbers: $2,200 paid in 5 payouts; only COMPLETE calendar months from the first payout's month (May..Oct = 6): slowest $0, base $533, fastest $1,000, first payout date; the built-in payout rules are $500 / $2,100",
          o["facts"][:4] == [2200, 5, 2, 6] and o["facts"][4] == "2026-05:100:1 2026-06:500:1 2026-07:1000:2 2026-08:0:0 2026-09:600:1 2026-10:0:0" and o["facts"][5:] == [0, 366.6666666666667, 1000, "2026-05-01", 500, 2100], o["facts"])
    check("b. thin data: no payouts = n 0 and no rate; a payout only in the current month = n 0 (a partial month is never counted); one full month = n 1 with equal low / base / high",
          o["thin"] == [0, 0, None, 0, None, 1, 400, 400, 400], o["thin"])
    check("b. the window is the last 6 full months, however long the history", o["window"] == [6, "2026-05", "2026-10", 1000, 500], o["window"])
    check("b. rules come from ledger/rules.json (min, buffer, max, split, payout count); bad values and a missing file fall back", o["rules"] == [600, 2500, 1500, 0.9, 4, 500, 5, 500, 2100], o["rules"])
    check("b. ETA for $5,000 paid: a RANGE (fastest / base / slowest) from n = 6 months, with the months to go (2.8 / 7.6); the slowest month paid $0, so it says plainly that it does not arrive; 'not a promise' always",
          o["eta"] == ["range", 6, "Feb 2027", "Jul 2027", None, 2.8, 7.6, None, True, True, True], o["eta"])
    check("b. no date without data: no payouts -> none; one full month -> none ('needs at least 2'); funded accounts have no pace; a monthly-pace goal is 'a pace, not a pile'; a reached goal says Reached",
          o["etaNone"][0] == "none" and "No payout has been published" in o["etaNone"][1] and o["etaNone"][2:] == ["none", True, "none", True, "none", True, "done"], o["etaNone"])
    check("b. an all-zero history shows no date ('paid nothing') instead of a guess; payout-count goals use payouts a month", o["etaZero"] == [True] and o["payoutsEta"][0] == "range" and o["payoutsEta"][2], (o["etaZero"], o["payoutsEta"]))
    check("b. progress: first payout and $1,000 reached, $5,000 is 44%, 2 of 3 funded accounts is 67%, the monthly pace $367 of $10,000 is 4%",
          o["prog"] == [[100, True], [100, True], [44, False], [67, False], [4, False]], o["prog"])
    check("b. plain words: what it takes uses the real rules and numbers; three actions for each kind; a reached goal says to keep the rules", o["takes"][:4] == [True, True, True, True] and o["takes"][4:9] == [3, 3, 3, 3, 3] and o["takes"][9], o["takes"])
    check("b. goals clean: bad names / kinds / targets dropped, '2,500' read as 2500, tags stripped, 2.4 accounts -> 2, a target below 1 -> 1, ids made unique and safe, at most 12, junk input -> none",
          o["goals"] == [4, "x,x_1,g9,g10", "Good|Dup|bTag/b|Odd", "2500,2,100,1", 0, 12, "g6", "g3"], o["goals"])
    check("b. export / import: the export re-imports to the same 5 goals; a mixed list keeps the good one and counts what it dropped; broken JSON, no goals, nothing readable and an empty string all fail with a plain error",
          o["io"] == [True, 5, "argo-goals", 1, True, 1, 1, False, False, False, False, True], o["io"])
    check("b. the map: one island per goal inside the sea, the first goal lowest (nearest the harbour), the ship between island 2 and 3 on its way to the next; no goals = no islands, no error",
          o["map"][0] == 5 and o["map"][1] and o["map"][2] and o["map"][3] == 2 and o["map"][4] == 44 and o["map"][5] and o["map"][6] == -1 and o["map"][7] == -1 and o["map"][8] == 0, o["map"])
    check("b. summary sentences: '2 of 5 islands reached. Next: ...', all reached, no goals", o["summary"][:3] == [2, 5, 2] and o["summary"][3].startswith("2 of 5 islands reached. Next: $5,000 paid out.") and o["summary"][4] == -1 and o["summary"][5] and o["summary"][6].startswith("No goals yet"), o["summary"])
    check("b. the Jarvis card: Argo, level, 3 kpis (2 of 5, $5,000 paid out, 44%), 2 lines of at most 120, integer t, demo -> off, under 8 KB", o["card"][0] == "Argo" and o["card"][3] == ["2 of 5", "$5,000 paid out", "44%"] and o["card"][4:] == [2, True, "off", True, True], o["card"])
    check("b. demo payouts become dates by day offsets (UTC maths); no fixture = none", o["demo"] == ["2026-10-31,2026-11-10", 1, 0], o["demo"])
    check("b. the trireme scene: many faces drawn, fewer in low quality, finite points, sorted far to near, the island grows as the goal nears, the hull rises at bow and stern",
          all(o["scene"]), o["scene"])


def iso(days_back):
    return (dt.date.today() - dt.timedelta(days=days_back)).isoformat()


def home_json(payouts=None, funded=1):
    d = {"accounts": [{"id": "mffu50k_eval", "name": "Zlarior 50K", "kind": "funded" if funded else "eval"}]}
    if payouts is not None:
        d["payouts"] = payouts
    return json.dumps(d)


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
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, note: document.querySelector('#demoNote').textContent, count: document.querySelector('#count').textContent, name: document.querySelector('#nextName').textContent, pct: document.querySelector('#nextPct').textContent,
              eta: document.querySelector('#nextEta').textContent, isles: document.querySelectorAll('#map .isle').length, ship: !!document.querySelector('#shipMark'), ladder: document.querySelectorAll('#ladder .step').length, sel: document.querySelector('#selName').textContent,
              range: document.querySelector('#selRange').textContent, acts: document.querySelectorAll('#selActs li').length, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
              pix: (() => { const c = document.querySelector('#scene'), a = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < a.length; i += 4) if (a[i] > 0) n++; return n; })(), cap: document.querySelector('#sceneCap').textContent })""")
            check("c. DEMO: the chip and the EXAMPLE note, '2 of 5', the next island is $5,000 paid out at 66%, the ETA is a base month with 'Not a promise', five islands, one ship, five ladder steps, that island is open with 3 actions",
                  d["demo"] and "EXAMPLE" in d["note"] and d["count"] == "2 of 5" and d["name"] == "$5,000 paid out" and d["pct"] == "66%" and "Not a promise" in d["eta"] and d["isles"] == 5 and d["ship"] and d["ladder"] == 5 and d["sel"] == d["name"] and d["acts"] == 3, d)
            check("c. the trireme canvas is painted (thousands of pixels), the caption names the island and the percent; the range line shows n; AGORA serif title and warm dark body",
                  d["pix"] > 20000 and "Sailing toward $5,000 paid out: 66%" in d["cap"] and re.search(r"n = [4-6] full months", d["range"]) and any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "argo-demo")
            p.locator("#map .isle").nth(3).click()
            p.wait_for_timeout(200)
            i3 = p.evaluate("() => ({ n: document.querySelector('#selName').textContent, takes: document.querySelector('#selTakes').textContent, eta: document.querySelector('#selEta').textContent, pressed: document.querySelectorAll('#ladder .step[aria-pressed=true]').length, st: document.querySelector('#status').textContent })")
            check("c. tap the 4th island on the map: Fund 3 accounts, what it takes in plain words, 'No pace is published' (no made-up date), the ladder follows, the spoken status", i3["n"] == "Fund 3 accounts" and "funded now" in i3["takes"] and "No pace is published" in i3["eta"] and i3["pressed"] == 1 and "Fund 3 accounts" in i3["st"], i3)
            p.locator("#ladder .step").nth(1).click()
            p.wait_for_timeout(200)
            r1 = p.evaluate("() => [document.querySelector('#selName').textContent, document.querySelector('#selPill').textContent, document.querySelector('#selEta').textContent]")
            check("c. tap a reached step on the ladder: '$1,000 paid out', Reached", r1 == ["$1,000 paid out", "Reached", "Reached."], r1)
            p.fill("#addName", "Pay off the car")
            p.select_option("#addType", "paid")
            p.fill("#addTarget", "8000")
            p.locator("#addBtn").click()
            p.wait_for_timeout(200)
            a = p.evaluate("() => ({ n: document.querySelectorAll('#ladder .step').length, isles: document.querySelectorAll('#map .isle').length, sel: document.querySelector('#selName').textContent, store: localStorage.getItem('argo.goals.v1'), msg: document.querySelector('#editMsg').textContent })")
            check("c. add a goal 'Pay off the car' ($8,000 paid): 6 ladder steps and 6 islands, it opens, it is saved in this browser", a["n"] == 6 and a["isles"] == 6 and a["sel"] == "Pay off the car" and "Pay off the car" in a["store"] and "Added" in a["msg"], a)
            p.fill("#addName", "")
            p.locator("#addBtn").click()
            check("c. an empty name is refused with a plain sentence and nothing is added", p.evaluate("() => [document.querySelector('#editMsg').textContent, document.querySelectorAll('#ladder .step').length]") == ["A goal needs a name and a target above zero.", 6])
            p.reload()
            p.wait_for_function("window.ARGO && window.ARGO.ready()", timeout=60000)
            p.wait_for_timeout(300)
            check("c. the goals survive a reload (this browser only)", p.evaluate("() => document.querySelectorAll('#ladder .step').length") == 6)
            row = p.locator("#goalsEdit .edrow").nth(5)
            row.locator("input[type=number]").fill("9000")
            row.locator("input[type=number]").dispatch_event("change")
            p.wait_for_timeout(200)
            p.wait_for_timeout(100)
            e = p.evaluate("() => window.ARGO.S.goals[5].target")
            check("c. editing a target in your goals changes the goal (9000) and the page", e == 9000, e)
            p.locator("#goalsEdit .edrow .btn.del").nth(5).click()
            p.wait_for_timeout(200)
            check("c. delete removes it (5 left)", p.evaluate("() => document.querySelectorAll('#ladder .step').length") == 5)
            p.locator("#io summary").click()
            p.locator("#exportBtn").click()
            ex = p.evaluate("() => [document.querySelector('#ioText').value, document.querySelector('#ioMsg').textContent]")
            check("c. Export puts the goals as JSON in the box ('argo-goals', 5 goals) and says so", '"argo-goals"' in ex[0] and ex[0].count('"target"') == 5 and "Exported 5 goals" in ex[1], ex)
            p.fill("#ioText", json.dumps({"v": 1, "goals": [{"name": "Two islands", "type": "paid", "target": 300}, {"name": "Funded two", "type": "funded", "target": 2}, {"name": "", "type": "paid", "target": 1}]}))
            p.locator("#importBtn").click()
            p.wait_for_timeout(200)
            im = p.evaluate("() => [document.querySelectorAll('#ladder .step').length, document.querySelector('#ioMsg').textContent, document.querySelector('#count').textContent]")
            check("c. Import replaces the goals (2 read, 1 skipped and said so) and the page redraws", im[0] == 2 and "Imported 2 goals" in im[1] and "1 could not be read" in im[1] and im[2] == "1 of 2", im)
            p.fill("#ioText", "{ not json")
            p.locator("#importBtn").click()
            bad = p.evaluate("() => [document.querySelectorAll('#ladder .step').length, document.querySelector('#ioMsg').textContent]")
            check("c. broken JSON changes nothing and says why", bad[0] == 2 and "not valid JSON" in bad[1], bad)
            p.locator("#resetBtn").click()
            p.wait_for_timeout(200)
            check("c. 'Back to the starter goals' restores the five", p.evaluate("() => document.querySelectorAll('#ladder .step').length") == 5)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (islands, ladder steps, fields, buttons)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            srv2, origin2 = AK.serve({"/home.json": home_json(None)})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, count: document.querySelector('#count').textContent, name: document.querySelector('#nextName').textContent, eta: document.querySelector('#nextEta').textContent, range: document.querySelector('#selRange').textContent })")
            check("c. the real home.json with NO payouts published: no DEMO chip, '0 of 5', the next island is the first payout at 0%, no date ('No payout has been published'), n = 0; nothing is invented",
                  not r["demo"] and r["count"] == "0 of 5" and r["name"] == "First payout" and "No payout has been published" in r["eta"] and "n = 0" in r["range"], r)
            ctx.close()
            srv2.shutdown()
            pays = [{"usd": 500, "date": iso(35)}, {"usd": 650, "date": iso(65)}, {"usd": 400, "date": iso(95)}, {"usd": 700, "date": iso(125)}]
            srv3, origin3 = AK.serve({"/home.json": home_json(pays)})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, count: document.querySelector('#count').textContent, name: document.querySelector('#nextName').textContent, eta: document.querySelector('#selEta').textContent, range: document.querySelector('#selRange').textContent })")
            check("c. real dated payouts ($2,250 over 4 months): no DEMO chip, '2 of 5', the $5,000 island shows a fastest / base / slowest range with n and 'not a promise'",
                  not r["demo"] and r["count"] == "2 of 5" and r["name"] == "$5,000 paid out" and "Fastest about" in r["eta"] and "base about" in r["eta"] and "not a promise" in r["eta"] and re.search(r"n = [2-5] full months", r["range"]), r)
            check("c. the real run reads only the site's files and no console error", any("home.json" in u for u in seen) and any("rules.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv3.shutdown()
            srv4 = AK.serve({"/home.json": "{ broken"})
            ctx, p, errs, seen, off = AK.page(br, srv4[1])
            AK.open_app(p, srv4[1], APP, "")
            b = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#map .isle').length]")
            check("c. a broken home.json never blanks the page: the labelled demo voyage (5 islands)", b == [True, 5] and not errs, (b, errs[:2]))
            ctx.close()
            srv4[0].shutdown()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low&pick=2")
            lt = p.evaluate("() => [window.ARGO.S.quality, document.querySelector('#selName').textContent, (() => { const c = document.querySelector('#scene'), a = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < a.length; i += 4) if (a[i] > 0) n++; return n; })()]")
            check("c. 375 x 667, LITE, reduced motion: low-detail still frame (the ship is drawn once, not animated), ?pick=2 opens the $1,000 island, no sideways scroll, every tap >= 44 px, no error",
                  lt[0] == "low" and lt[1] == "$1,000 paid out" and lt[2] > 15000 and AK.no_sideways(p) and not AK.taps(p) and not errs, (lt, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
