"""NIKE, the OLYMPUS trophy hall (tools/web_public/nike/, AGORA look, 2026-11-10): eight trophies from PUBLISHED numbers only, each unlocked / locked with a date and a plain sentence; marble shelves, tap to look closer and turn.

  a. static: the files, the kit lines, the AGORA look, read-only (the journal is read, never written), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (nikecore.js) and the four trophy meshes drawn onto a fake canvas (nikescene.js)
  c. Chromium 390 x 844 (and 375 x 667): DEMO hall, tap a trophy, turn it, the real home.json (honest "not yet" placeholders), the journal ratings, LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_nike_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "nike", "Nike"
check = AK.check
READS = ("../home.json", "../ledger/rules.json", "../odeon/trades.json", "../kalshicity/edges.json")


def test_static():
    AK.static_kit(APP, NAME, reads=READS, storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "nike.js")) + AK.read(os.path.join(d, "nikecore.js")) + AK.read(os.path.join(d, "nikescene.js"))
    check("a. the only browser storage is a READ of the journal ('journal.v1'): no setItem / removeItem / clear", len(re.findall(r"localStorage\.", js)) == 1 and "getItem('journal.v1')" in js and not re.search(r"setItem|removeItem|\.clear\(\)|sessionStorage|indexedDB", js))
    check("a. the scene is pure maths on a 2D context: no WebGL, no document, no fetch, no three.js", not re.search(r"webgl|THREE|\bdocument\.|\bfetch\(|\bwindow\.", re.sub(r"//[^\n]*", "", AK.read(os.path.join(d, "nikescene.js"))), re.I))
    check("a. no markup is ever built from data in the scene either (no innerHTML / eval)", not re.search(r"innerHTML|outerHTML|eval\s*\(|new Function", js))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. page order: wins, the shelves, look closer, where the numbers come from", html.index('id="headline"') < html.index('id="hall"') < html.index('id="big"') < html.index('id="srcs"'))
    check("a. the inspector has turn left / right buttons (not only a drag) and a pause toggle", 'id="turnL"' in html and 'id="turnR"' in html and 'id="spin"' in html and "tabindex=\"0\"" in html)
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture has accounts, payouts, trades, kalshi days (offsets from today), all labelled EXAMPLE", all(k in fx for k in ("accounts", "payouts", "trades", "kalshi")) and "EXAMPLE" in fx["note"])


HARNESS = r"""
Promise.all([import(process.argv[2]), import(process.argv[3])]).then(([C, X]) => {
  const o = {};
  o.words = [C.money(3000), C.moneyS(-60), C.both(640, 1.5), C.both(640, null), C.dateText('2026-11-03'), C.addDays('2026-03-01', -1), C.monday('2026-11-10'), C.monday('2026-11-08'), C.monday('2026-11-09')];
  const L = C.limitsFrom({ plans: { builder_50k: { target: 3500, payout: { min: 600, max_payouts: 4 } } } }), L0 = C.limitsFrom(null), Lj = C.limitsFrom({ plans: { builder_50k: { target: -1, payout: { min: 'x' } } } });
  o.limits = [L.target, L.payoutMin, L.maxPayouts, L0.target, L0.payoutMin, Lj.target, Lj.payoutMin];
  const home = { accounts: [{ name: 'A', kind: 'eval', eval: { to_target: 2580, progress: 0.14 } }, { name: 'B', kind: 'funded', passed_on: '2026-09-01', payouts: [{ usd: 500, date: '2026-10-01' }] }], payouts: [{ amount: 300, date: '2026-09-20' }, { usd: -5 }, { usd: 'x' }, null] };
  const H = C.normHome(home);
  o.home = [H.has, H.accounts.length, H.accounts[0].passed, H.accounts[1].passed, H.accounts[1].passedOn, H.payouts.map((p) => p.usd), C.normHome(null).has, C.normHome({ accounts: [] }).has, C.normHome({ payouts: [] }).has, C.normHome({ accounts: [{ kind: 'eval', eval: { progress: 1 } }] }).accounts[0].passed, C.normHome({ accounts: [{ kind: 'eval', eval: { passed: true } }] }).accounts[0].passed];
  const mk = (day, usd, r, i) => ({ id: 't' + i, day, usd, r, entry: { t: Date.parse(day + 'T14:00:00Z') / 1000 + i } });
  const T = C.normTrades({ trades: [mk('2026-11-02', 300, 0.7, 1), mk('2026-11-03', -1200, -2.8, 2), mk('2026-11-03', 100, 0.2, 3), mk('2026-11-04', 500, 1.2, 4), mk('2026-11-05', 700, 1.6, 5), { id: 'bad', day: 'x', usd: 1 }, null, { id: 'q', day: '2026-11-06' }] });
  o.trades = [T.length, T.map((t) => t.id).join(','), C.normTrades(null).length];
  const days = C.dayTotals(T);
  o.days = [days.map((d) => d.usd), days[1].n];
  const bw = C.bestWeek(days), bw0 = C.bestWeek([]);
  o.week = [bw.start, bw.usd, Math.round(bw.r * 10) / 10, bw0];
  const kept = C.keptStreak(days, 1000), kept2 = C.keptStreak(days, 2000);
  o.kept = [kept.best, kept.end, kept.breaches, kept2.best, kept2.breaches, C.keptStreak([], 1000).best];
  const ps = C.planStreak(T, { t1: 'plan', t2: 'plan', t3: 'plan', t4: 'hesitated', t5: 'plan' });
  o.plan = [ps.best, ps.end, ps.current, ps.rated, C.planStreak(T, {}).best];
  const gs = C.greenStreak([['2026-11-01', 5], ['2026-11-02', 6], ['2026-11-03', -1], ['2026-11-04', 3]]);
  o.green = [gs.best, gs.end, C.crossDate([['2026-11-01', 60], ['2026-11-02', 50]], 110, 100), C.crossDate([['2026-11-01', 60]], 110, 100), C.crossDate([], 0, 100)];
  const none = C.build({ home: C.normHome(null), trades: [], ratings: {}, kalshi: null, rules: null });
  o.none = [none.length, none.every((t) => t.state === 'locked'), none.every((t) => t.sentence.startsWith('Not yet')), none.map((t) => t.id).join(','), none.every((t) => ['cup', 'laurel', 'owl', 'shield'].includes(t.shape)), none[1].sentence.includes('No payout has been published'), none[0].sentence];
  const full = C.build({ home: H, trades: T, ratings: { t1: 'plan', t2: 'plan', t3: 'plan', t4: 'plan', t5: 'plan' }, kalshi: { total: 140, days: [['2026-11-01', 100], ['2026-11-02', 40]] }, rules: null });
  const by = Object.fromEntries(full.map((t) => [t.id, t]));
  o.full = [by.first_eval.state, by.first_eval.date, by.payout_first.state, by.payout_first.value, by.payout_first.date, by.payout_1k.state, by.payout_1k.value, by.payout_1k.date, by.best_week.state, by.best_week.value, by.plan_streak.state, by.plan_streak.value, by.rules_kept.state, by.kalshi_100.state, by.kalshi_100.date, by.kalshi_streak.state];
  o.sent = [by.best_week.sentence, by.payout_first.sentence, by.kalshi_100.sentence];
  const part = C.build({ home: C.normHome({ accounts: [{ name: 'Z', kind: 'eval', eval: { to_target: 1800, progress: 0.4 } }], payouts: [{ usd: 200, date: '2026-10-02' }] }), trades: T, ratings: {}, kalshi: { total: 40, days: [] }, rules: null });
  const bp = Object.fromEntries(part.map((t) => [t.id, t]));
  o.part = [bp.first_eval.state, bp.first_eval.progress, bp.first_eval.sentence, bp.payout_first.state, bp.payout_1k.state, bp.payout_1k.progress, bp.payout_1k.sentence, bp.plan_streak.sentence, bp.kalshi_100.progress, bp.kalshi_100.sentence, bp.rules_kept.sentence];
  const sm = C.summary(full), sn = C.summary(none);
  o.summary = [sm.n, sm.total, sn.n, sn.text.startsWith('No trophy earned yet')];
  const di = C.demoInputs({ accounts: [{ name: 'D', kind: 'funded', passed_off: 5 }], payouts: [{ usd: 100, off: 3 }], trades: [{ off: 2, usd: 10, r: 0.1 }, { off: 1, usd: 20, r: 0.2 }], plan_not: [0], kalshi: { total: 9, days: [[2, 4], [1, 5]] } }, '2026-11-10');
  o.demo = [di.home.accounts[0].passed_on, di.home.payouts[0].date, di.trades.trades.map((t) => t.day), Object.keys(di.store.entries), di.kalshi.book.days, C.demoInputs(null, '2026-11-10').trades.trades.length];
  const card = C.jarvisCard(full, 1793394000, false), cd = C.jarvisCard(none, 5, true);
  o.card = [card.name, card.status.level, card.status.label, card.kpis.length, card.lines.length, Number.isInteger(card.t), cd.status.level, cd.kpis[2].value, JSON.stringify(card).length < 8000];
  // the meshes
  const ctx = { n: 0, fills: 0, clearRect() {}, save() {}, restore() {}, beginPath() { this.n++; }, moveTo() {}, lineTo() {}, closePath() {}, fill() { this.fills++; }, stroke() {}, set fillStyle(v) { this.last = v; }, set strokeStyle(v) {}, set lineWidth(v) {}, set globalAlpha(v) {}, set lineJoin(v) {} };
  o.meshes = X.SEG && ['cup', 'laurel', 'owl', 'shield'].map((s) => { const m = X.makeMesh(s, 'high'), l = X.makeMesh(s, 'low'); ctx.fills = 0; const n = X.draw(ctx, m, 132, 132, 0.5, false, 0.04); const f1 = ctx.fills; X.draw(ctx, m, 132, 132, 2.0, true); return [m.faces.length > 60, l.faces.length < m.faces.length || s === 'shield', n > 20, f1 === n, m.faces.every((f) => f.p.every((p) => p.every(Number.isFinite)))]; });
  const mm = X.makeMesh('cup', 'high'), fr = X.project(mm, 0.3, 0.28, 300, 260, 0.1);
  o.proj = [fr.every((f) => f.pts.every((p) => p[0] >= -5 && p[0] <= 305 && p[1] >= -5 && p[1] <= 265)), fr.every((f, i) => i === 0 || fr[i - 1].z <= f.z), X.makeMesh('nope', 'high').shape];
  console.log(JSON.stringify(o));
});
"""


def node_run():
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="nike-")
    try:
        for n in ("nikecore", "nikescene"):
            shutil.copy(os.path.join(AK.WEB, APP, n + ".js"), os.path.join(tmp, n + ".mjs"))
        h = os.path.join(tmp, "harness.cjs")
        open(h, "w", encoding="utf-8").write(HARNESS)
        r = subprocess.run([exe, h, os.path.join(tmp, "nikecore.mjs"), os.path.join(tmp, "nikescene.mjs")], capture_output=True, text=True, timeout=120)
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
    check("b. words: $3,000, -$60, '+$640 (+1.5R)' (dollars with their R), a lone dollar when R is unknown, dates, week maths (Monday start)",
          o["words"] == ["$3,000", "-$60", "+$640 (+1.5R)", "+$640", "Nov 3, 2026", "2026-02-28", "2026-11-09", "2026-11-02", "2026-11-09"], o["words"])
    check("b. limits come from ledger/rules.json (target, first payout, payout count); bad values and a missing file fall back to $3,000 / $500", o["limits"] == [3500, 600, 4, 3000, 500, 3000, 500], o["limits"])
    check("b. home.json: funded or passed = a passed eval; payouts from the top and from accounts, sorted, only real positive dollars; no accounts and no payouts file = not there",
          o["home"] == [True, 2, False, True, "2026-09-01", [300, 500], False, False, True, True, True], o["home"])
    check("b. trades: bad rows dropped, sorted by time", o["trades"] == [5, "t1,t2,t3,t4,t5", 0], o["trades"])
    check("b. day totals add same-day trades", o["days"] == [[300, -1100, 500, 700], 2], o["days"])
    check("b. best week: the Monday of the week, its dollars and R", o["week"] == ["2026-11-02", 400, 0.9, None], o["week"])
    check("b. rules kept: a $1,000 daily limit is breached once (-$1,100), the best run is 2 days; at $2,000 nothing is breached and all 4 days count; none -> 0", o["kept"] == [2, "2026-11-05", 1, 4, 0, 0], o["kept"])
    check("b. plan streak: 3 'plan' in a row, broken by 'hesitated', then 1; unrated trades count as not followed; no ratings -> 0", o["plan"] == [3, "2026-11-03", 1, 5, 0], o["plan"])
    check("b. Kalshi: longest green run, the day the total crossed $100 (only when the days add up to the total), unknown otherwise", o["green"] == [2, "2026-11-02", "2026-11-02", "", ""], o["green"])
    check("b. nothing published: 8 trophies, every one locked with a 'Not yet' sentence, four shapes used, the first payout says no payout has been published", o["none"][:2] == [8, True] and o["none"][2] and o["none"][4] and o["none"][5] and o["none"][3].startswith("first_eval,payout_first,payout_1k,best_week"), o["none"])
    check("b. everything published and met: the eval and first payout ($300, the earliest of the published payouts) unlock with real dates, $800 of $1,000 is still locked, best week $400, 5 plan trades is the streak, rules kept needs 10 days (still locked at 4), Kalshi $140 unlocked on the crossing day, the green run needs 5",
          o["full"][:2] == ["unlocked", "2026-09-01"] and o["full"][2:5] == ["unlocked", "$300", "2026-09-20"] and o["full"][5] == "locked" and o["full"][8:12] == ["unlocked", "+$400", "unlocked", "5 in a row"] and o["full"][12:] == ["locked", "unlocked", "2026-11-01", "locked"], o["full"])
    check("b. honest numbers in the sentences (dollar with R, the real payout, the Kalshi total)", "+$400 (+0.9R)" in o["sent"][0] and "$300" in o["sent"][1] and "+$140" in o["sent"][2], o["sent"])
    check("b. part-way: a locked eval shows its progress (40%) and the dollars to go; $200 paid is 20% of $1,000; Kalshi $40 is 40%; the journal sentence tells how to start; rules kept shows the real count",
          o["part"][0] == "locked" and o["part"][1] == 0.4 and "$1,800 to go" in o["part"][2] and o["part"][3] == "unlocked" and o["part"][4] == "locked" and o["part"][5] == 0.2 and "$200 of $1,000" in o["part"][6] and "Mnemosyne" in o["part"][7] and o["part"][8] == 0.4 and "+$40" in o["part"][9] and "days in a row" in o["part"][10], o["part"])
    check("b. the summary counts earned trophies in plain words", o["summary"][2:] == [0, True] and o["summary"][1] == 8, o["summary"])
    check("b. demo inputs turn day offsets into dates (UTC maths) and rate every trade 'plan' except the listed ones", o["demo"] == ["2026-11-05", "2026-11-07", ["2026-11-08", "2026-11-09"], ["demo.2"], [["2026-11-08", 4], ["2026-11-09", 5]], 0], o["demo"])
    check("b. the Jarvis card: Nike, a level, label, 3 kpis, 2 lines, integer t, demo -> off, under 8 KB", o["card"][0] == "Nike" and o["card"][3:] == [3, 2, True, "off", o["card"][7], True] and o["card"][1] in ("ok", "warn"), o["card"])
    check("b. the four meshes (cup, laurel, owl, shield) build with finite points, a lighter low-quality version, and draw many filled faces onto a context", all(all(r) for r in o["meshes"]), o["meshes"])
    check("b. projection stays inside the canvas, faces are sorted far to near, an unknown shape falls back to the cup", o["proj"][0] and o["proj"][1] and o["proj"][2] == "nope", o["proj"])


def home_json():
    return json.dumps({"accounts": [{"id": "mffu50k_eval", "name": "Zlarior 50K", "kind": "eval", "eval": {"balance": 50420, "to_target": 2580, "progress": 0.14}}]})


def trades_json():
    return json.dumps({"trades": [{"id": f"x.{i}", "day": f"2026-11-0{i}", "usd": 300 + i, "r": 0.7, "entry": {"t": 1793000000 + i * 86400}} for i in range(1, 6)]})


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
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, count: document.querySelector('#count').textContent, slots: document.querySelectorAll('#hall .slot').length, won: document.querySelectorAll('#hall .slot.won').length,
              canv: [...document.querySelectorAll('#hall canvas')].every((c) => c.width > 100), on: document.querySelector('#hall .slot.on .nm').textContent, name: document.querySelector('#tName').textContent, pill: document.querySelector('#tPill').textContent,
              sent: document.querySelector('#tSentence').textContent, date: document.querySelector('#tDate').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
              note: document.querySelector('#demoNote').textContent, srcs: document.querySelectorAll('#srcs li').length, pix: (() => { const c = document.querySelector('#big'), x = c.getContext('2d'), a = x.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < a.length; i += 4) if (a[i] > 0) n++; return n; })() })""")
            check("c. DEMO: the chip, the EXAMPLE note, 8 trophies on the shelves (5 earned), every shelf canvas drawn, the first earned trophy is open", d["demo"] and "EXAMPLE" in d["note"] and d["slots"] == 8 and d["won"] == 5 and d["count"] == "5 of 8" and d["canv"] and d["pill"] == "Earned" and d["name"] == d["on"], d)
            check("c. the inspector canvas is drawn (many painted pixels); an earned trophy shows its date; five sources are listed; AGORA serif title and warm dark body",
                  d["pix"] > 3000 and "Earned" in d["date"] and d["srcs"] == 5 and any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "nike-demo")
            p.locator("#hall .slot.lost").first.click()
            p.wait_for_timeout(300)
            l = p.evaluate("() => ({ pill: document.querySelector('#tPill').textContent, sent: document.querySelector('#tSentence').textContent, goal: document.querySelector('#tGoal').textContent, st: document.querySelector('#status').textContent, w: document.querySelector('#tBar i').style.width })")
            check("c. tap a locked trophy: 'Not yet', a plain sentence of what it needs, its progress, the spoken status", l["pill"] == "Not yet" and l["sent"].startswith("Not yet") and "published numbers" in l["goal"] and "Not yet" in l["st"], l)
            p.locator("#spin").click()
            y0 = p.evaluate("() => window.NIKE.S.yaw")
            p.locator("#turnR").click()
            y1 = p.evaluate("() => window.NIKE.S.yaw")
            p.locator("#turnL").click()
            y2 = p.evaluate("() => window.NIKE.S.yaw")
            check("c. 'Turn right' / 'Turn left' rotate the trophy (not only a drag); the Turning button pauses the spin", abs((y1 - y0) - 0.5) < 0.3 and abs((y2 - y1) + 0.5) < 0.05 and p.evaluate("() => document.querySelector('#spin').getAttribute('aria-pressed')") == "false", (y0, y1, y2))
            box = p.locator("#big").bounding_box()
            p.mouse.move(box["x"] + 100, box["y"] + 100)
            p.mouse.down()
            p.mouse.move(box["x"] + 170, box["y"] + 100, steps=4)
            p.mouse.up()
            y3 = p.evaluate("() => window.NIKE.S.yaw")
            check("c. dragging sideways on the trophy turns it", y3 - y2 > 0.5, (y2, y3))
            for t in ("cup", "laurel", "owl", "shield"):
                n = p.evaluate("(t) => { const l = window.NIKE.S.list, i = l.findIndex((x) => x.shape === t); window.NIKE.S.pick = i; window.NIKE.select(); const c = document.querySelector('#big'), a = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let k = 0; for (let j = 3; j < a.length; j += 4) if (a[j] > 0) k++; return k; }", t)
                check(f"c. the {t} is drawn in the inspector", n > 2500, n)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (shelf trophies, turn buttons, the canvas)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            srv2, origin2 = AK.serve({"/home.json": home_json(), "/odeon/trades.json": trades_json()})
            ctx, p, errs, seen, off = AK.page(br, origin2, storage={"journal.v1": json.dumps({"v": 1, "entries": {f"x.{i}": {"rating": "plan", "at": 1} for i in range(1, 6)}})})
            AK.open_app(p, origin2, APP, "")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, count: document.querySelector('#count').textContent, list: window.NIKE.S.list.map((t) => t.id + ':' + t.state), srcs: [...document.querySelectorAll('#srcs li')].map((l) => l.textContent), eval: window.NIKE.S.list[0].sentence, pay: window.NIKE.S.list[1].sentence })""")
            check("c. the real home.json (no payouts published): no DEMO chip, the eval is 'not yet' with $2,580 to go, the payouts say none published, the Kalshi trophies say not published; nothing is invented",
                  not r["demo"] and "first_eval:locked" in r["list"] and "payout_first:locked" in r["list"] and "kalshi_100:locked" in r["list"] and "$2,580 to go" in r["eval"] and "No payout has been published" in r["pay"], r)
            check("c. the real trades and the journal's ratings (read from this phone): the plan streak counts 5 trades, rules kept counts the 5 days, the sources list says which files are published",
                  any(s.startswith("Your journal ratings (this phone): published") for s in r["srcs"]) and any("The bot's trades" in s and ": published" in s for s in r["srcs"]) and any(s.startswith("Accounts and payouts") and "not published" not in s for s in r["srcs"]), r["srcs"])
            ps = p.evaluate("() => { const t = window.NIKE.S.list.find((x) => x.id === 'plan_streak'); return [t.state, t.progress, t.sentence]; }")
            check("c. 5 rated 'followed plan' trades in a row is the goal of 5: the owl is earned", ps[0] == "unlocked" and "5 trades in a row" in ps[2], ps)
            check("c. the real run reads only the site's files and no console error", any("home.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/home.json": "{ broken"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "")
            b = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#hall .slot').length]")
            check("c. a broken home.json never blanks the page: the labelled demo hall (8 trophies)", b == [True, 8] and not errs, (b, errs[:2]))
            ctx.close()
            srv3.shutdown()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low&pick=plan_streak")
            lt = p.evaluate("() => [window.NIKE.S.quality, window.NIKE.S.spin, document.querySelector('#spin').textContent, window.NIKE.S.list[window.NIKE.S.pick].id]")
            check("c. 375 x 667, LITE, reduced motion: low-detail meshes, no spinning (still), no sideways scroll, every tap >= 44 px, no error", lt[0] == "low" and lt[1] is False and lt[2] == "Still" and AK.no_sideways(p) and not AK.taps(p) and not errs, (lt, AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
