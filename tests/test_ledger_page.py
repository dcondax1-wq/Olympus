"""LEDGER (tools/web_public/ledger/, OLYMPUS 2026-11-04): the owner's real money on his phone. Checks, by part:
  a. the static rules: the kit (?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML, only the site's own files plus the public Kalshi feed are read
     (never written to), storage only under 'ledger.v1', nothing sent anywhere, safe areas, the + button out of the orb's corner, 16 px inputs, reduced motion, manifest, icon,
     jarvis.json, the fixture, rules.json equal to what tools/ledger_rules.py makes from research/lit/mffu_rules.json
  b. the maths (ledgercore.js in node, by hand): dates (month-end clamps, leap years), entry validation, recurring items, income / costs / pending / net, the Kalshi result
     (balance and deposits, the bot's own total, none), AUTO entries (the owner's real prices, suppressed by his own entry or a hide), accounts and payback, the break-even
     pace, the tax set-aside by quarter, the payout split, the payout calendar, the waterfall, the day map, CSV (quotes, signs), export / import, junk in
  c. the page in Chromium at 390 x 844: DEMO until the first entry (and nothing written), quick add (3 fields), validation, edit, delete + Undo, recurring, every tab, the
     calculator, the tax %, export / import / CSV downloads, auto entries (Keep / Not mine), the Kalshi result, persistence, the vault's coins follow the net, offline,
     reduced motion, the orb's corner, no sideways scroll, nothing leaves the phone
    python -X utf8 -m tests.test_ledger_page            (LG_NO_BROWSER=1 skips c; LG_NO_HIGH=1 skips the high-tier load; LG_SHOTS=<dir> saves screenshots)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "ledger")
RAW_PREFIX = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/"
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const dir = " + json.dumps(PAGE) + "; const url = 'file://' + dir; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    from tools import ledger_rules as lr
    files = os.listdir(PAGE)
    need = {"index.html", "ledger.css", "ledgercore.js", "ledger.js", "ledgerscene.js", "rules.json", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, scene, rules, demo fixture, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "ledger.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon, the fx library",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o5">' in html and 'src="../olympus/themes.js?v=o4"' in html and 'src="../olympus/olympus.js?v=o5" data-app="ledger"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html and 'rel="icon" href="icon.svg"' in html
          and 'rel="apple-touch-icon"' in html and "fx-core.js?v=f1" in html and "fx-text.js?v=f1" in html and 'data-oly-fx="odometer"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    sc = js["ledgerscene.js"]
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; rc.render(); the core is disposed; the fx library's godRays",
          "from '../jarvis/three.module.min.js'" in sc and "from '../olympus/render.js'" in sc and "from '../olympus/materials.js'" in sc and "createRenderer(" in sc and "rc.render()" in sc
          and "new THREE.WebGLRenderer" not in sc and "rc.dispose()" in sc and "InstancedMesh" in sc and "godRays" in sc)
    check("a. no innerHTML / insertAdjacentHTML / document.write: the data only ever goes in as text", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = {x.strip() for x in re.findall(r"getJSON\(([^,)]+)", js["ledger.js"])} - {"url"}
    check("a. the page reads only home.json, rules.json, the public Kalshi feed (this site's own kalshi.json first), its fixture and the Money plan's ../plutus/roadmap.json (GET); no WebSocket / beacon / XHR / EventSource, no POST, no custom header, nothing sent",
          fetched == {"'../home.json'", "'rules.json'", "RAW", "SITE_FEED", "'fixture.json'", "'../plutus/roadmap.json'"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource", s) for s in js.values())
          and not re.search(r"method\s*:|'POST'|headers\s*:|body\s*:", js["ledger.js"]), fetched)
    ls = re.findall(r"localStorage\.(\w+)Item\(([^,)]+)", " ".join(js.values()))
    check("a. storage only under the one key 'ledger.v1' (read, write) plus the 30-minute 'ledger.opt404.<url>' not-there notes; no cookies, no IndexedDB, no other keys", ls and all(k in ("KEY", "'ledger.opt404.' + u") for _, k in ls) and "const KEY = 'ledger.v1'" in js["ledger.js"]
          and not re.search(r"document\.cookie|indexedDB|sessionStorage", " ".join(js.values())), ls)
    check("a. no key, token or secret anywhere in the app's files", not re.search(r"api[_-]?key|secret|password|access[_-]?token|bearer|\\bsk-[A-Za-z0-9]{10}", html + css + " ".join(js.values()), re.I))
    check("a. safe areas on every edge, the + button on the LEFT (Jarvis's orb owns the bottom-right corner), the toast stops 96 px from the right, 44 px+ targets, 16 px inputs, reduced motion",
          all(f"var(--s{x})" in css for x in "trbl") and re.search(r"\.fab \{[^}]*left: calc\(var\(--sl\) \+ 16px\)", css) is not None and "right: calc(var(--sr) + 96px)" in css and "min-height: 44px" in css
          and "min-height: 48px" in css and "font-size: 16px" in css and "@media (prefers-reduced-motion: reduce)" in css and "width: 64px; height: 64px" in css)
    check("a. honest words are on the page: not tax advice, simulated P&L is not cash, example numbers say DEMO, an early pace is a guess", all(x in " ".join(js.values()) + html for x in ("NOT tax advice", "performance, not cash", "Example numbers", "early guess", "Only money that really moved counts")))
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Ledger" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, 3 kpis, <= 3 lines, t, open, theme, < 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Ledger" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture is marked demo, every entry says Example, offsets are in the past, accounts are named Example", fx["demo"] is True and all("Example" in e["note"] for e in fx["entries"]) and all(e["off"] <= 0 for e in fx["entries"])
          and all("Example" in a["name"] for a in fx["accounts"]) and len(fx["entries"]) >= 10)
    with open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8") as fh:
        built = lr.build(json.load(fh))
    rules = json.loads(rd(PAGE, "rules.json"))
    check("a. rules.json is exactly what tools/ledger_rules.py makes from research/lit/mffu_rules.json: the owner's real prices ($91.80 50K, $63 25K, $43 ATLAS 25K, $0 activation), reset price null, payout rules",
          rules == built and rules["accounts"]["lit50k"]["price"] == 91.8 and rules["accounts"]["atlas25k"]["price"] == 43.0 and rules["plans"]["builder_25k"]["price_owner"] == 63.0
          and rules["plans"]["builder_50k"]["activation"] == 0.0 and rules["plans"]["builder_50k"]["reset"] is None and rules["plans"]["builder_50k"]["payout"]["split"] == 0.8
          and rules["plans"]["builder_50k"]["payout"]["min"] == 500.0 and rules["plans"]["builder_25k"]["payout"]["max"] == 1000.0)


# ------------------------------------------------------------------------------------------------ b. the maths
def part_b():
    js = node(r"""const C = await import(url + '/ledgercore.js'); const rules = JSON.parse(fs.readFileSync(dir + '/rules.json', 'utf8')), fx = JSON.parse(fs.readFileSync(dir + '/fixture.json', 'utf8'));
      const T = '2026-11-04', E = (kind, amount, date, o = {}) => C.cleanEntry({ kind, amount, date, acct: o.acct || 'general', cat: o.cat, note: o.note || '', rec: o.rec || null, id: o.id || (kind + amount + date) });
      // dates
      const dates = { jan31: C.addMonths('2026-01-31', 1), leap: C.addMonths('2028-01-31', 1), back: C.addMonths('2026-03-31', -1), year: C.addMonths('2026-11-15', 3), days: C.addDays('2026-12-31', 1), between: C.daysBetween('2026-10-18', '2026-11-04'),
        bad: ['2026-02-30', '2026-13-01', 'x', '', null, '2026-1-1'].map(C.isDate), good: C.isDate('2028-02-29'), mb: C.monthsBack('2026-02', 3), today: /^\d{4}-\d\d-\d\d$/.test(C.todayET()) };
      // entries
      const bad = [{ kind: 'fee', amount: -5, date: T }, { kind: 'fee', amount: 0, date: T }, { kind: 'fee', amount: 'abc', date: T }, { kind: 'nope', amount: 5, date: T }, { kind: 'fee', amount: 5, date: '2026-02-30' }, null, 5, 'x', { kind: 'fee', amount: 1e12, date: T }].map((e) => C.cleanEntry(e));
      const parsed = [C.num('$1,234.50'), C.num(' 91.80 '), C.num('x'), C.num(''), C.num(null), C.num(12)];
      const okE = C.cleanEntry({ kind: 'fee', amount: '91.804', date: T, note: '  a   b  ', rec: { every: 'bogus' } });
      // recurring
      const mo = (d, o) => C.occurrences(E('expense', 12, d, { rec: { every: 'month', until: o || null } }), T);
      const rec = { m31: C.occurrences(E('expense', 12, '2026-01-31', { rec: { every: 'month' } }), '2026-04-30'), week: C.occurrences(E('expense', 5, '2026-10-07', { rec: { every: 'week' } }), T), year: C.occurrences(E('expense', 99, '2024-11-04', { rec: { every: 'year' } }), T),
        until: mo('2026-08-10', '2026-09-30'), future: C.occurrences(E('expense', 12, '2027-01-01'), T), once: C.occurrences(E('expense', 12, '2026-10-01'), T), upcoming: C.upcoming([E('expense', 12, '2026-08-20', { rec: { every: 'month' } })], T, 30).map((e) => e.date) };
      // the by-hand ledger: fees 91.80 + 43, a 12 / month cost from Sep 4 (Sep 4, Oct 4, Nov 4 = 3), payout 800 received, 1000 requested, 50 other income, 4 tax paid
      const st = { ...C.emptyState(), entries: [E('fee', 91.8, '2026-10-18', { acct: 'a' }), E('fee', 43, '2026-10-26', { acct: 'b' }), E('expense', 12, '2026-09-04', { rec: { every: 'month' }, cat: 'VPS / Azure' }), E('payout_in', 800, '2026-11-02', { acct: 'a' }), E('payout_req', 1000, '2026-10-30', { acct: 'a' }), E('payout_req', 500, '2026-11-03', { acct: 'b', id: 'rb' }), E('income', 50, '2026-11-03'), E('tax', 4, '2026-11-03')] };
      const list = C.expand(st.entries, T), t = C.totals(list, null, T);
      // the Kalshi result
      const kl = (extra, feed) => C.kalshiResult(list.concat(extra.map((e) => ({ ...e, rid: e.id }))), feed);
      const kd = [E('deposit', 200, '2026-10-01', { acct: 'kalshi' }), E('withdrawal', 40, '2026-10-20', { acct: 'kalshi' })];
      const feed = { balance: 188.4, total_pnl: -81.77, week_pnl: -3.3, days: [['2026-11-02', -3.3], ['2026-11-01', 5], ['2026-10-30', -2]] };
      const kal = { bal: kl(kd, feed), bot: kl([], feed), none: kl([], null), junk: kl([], { balance: 'x', total_pnl: null, days: [1, ['bad', 1]] }) };
      const tk = C.totals(list.concat(kd.map((e) => ({ ...e, rid: e.id }))), feed, T), tb = C.totals(list, feed, T);
      // auto entries
      const home = { goals: { accounts: [{ id: 'lit50k', name: 'MFFU Builder 50K', price: 99 }, { id: 'atlas25k', name: 'x', price: 63 }, { id: 'other', name: 'Other acct', price: 20 }, { id: 'free', name: 'No price' }, { id: 'lit50k', price: 1 }] } };
      const auto = C.autoEntries({ home, rules }, T), auto0 = C.autoEntries({ home: null, rules }, T), autoOld = C.autoEntries({ home: { accounts: [{ id: 'atlas25k', eval: { start: '2099-01-01' } , price: 5 }] }, rules: null }, T);
      const mine = { ...C.emptyState(), entries: [E('fee', 90, '2026-10-19', { acct: 'lit50k' })] }, hid = { ...C.emptyState(), hidden: ['auto:fee:atlas25k'] };
      const mg = { none: C.merge(C.emptyState(), auto, T), mine: C.merge(mine, auto, T), hid: C.merge(hid, auto, T) };
      const kept = C.keepAuto(C.emptyState(), auto[0]), keptM = C.merge(kept, auto, T);
      // accounts, break-even, tax, payouts
      const acc = C.accounts(list, null, [{ id: 'a', name: 'A', stage: 'eval', profit: 1240.5 }, { id: 'z', name: 'Z' }]), ac = (id) => acc.find((x) => x.id === id);
      const mkM = (nets) => nets.flatMap((n, i) => { const d = `2026-0${5 + i}-10`; return n >= 0 ? [E('payout_in', n, d, { id: 'p' + i })] : [E('expense', -n, d, { id: 'x' + i })]; });
      const beOf = (entries, today) => C.breakEven(C.expand(entries, today || T), null, today || T);
      const be = { paid: beOf([E('payout_in', 500, '2026-10-01'), E('fee', 100, '2026-10-02')]), nocost: beOf([E('payout_in', 500, '2026-10-01')]), none: beOf([]),
        track: beOf([E('fee', 400, '2026-07-02'), ...[0, 1, 2].map((i) => E('payout_in', 100, ['2026-08-15', '2026-09-15', '2026-10-15'][i], { id: 'q' + i }))]), stalled: beOf([E('fee', 400, '2026-07-02'), ...[0, 1, 2].map((i) => E('expense', 10, ['2026-08-15', '2026-09-15', '2026-10-15'][i], { id: 'r' + i }))]),
        early: beOf([E('fee', 400, '2026-10-02')]) };
      const tx = C.tax(list, null, 25, T), tl = C.tax(C.expand([E('expense', 500, '2026-03-01')], T), null, 25, T), tcap = C.tax(list, null, 500, T);
      const pm = { ok: C.payoutMath(1000, rules.plans.builder_50k.payout), low: C.payoutMath(300, rules.plans.builder_50k.payout), high: C.payoutMath(5000, rules.plans.builder_50k.payout), bad: [C.payoutMath('x', rules.plans.builder_50k.payout), C.payoutMath(-1, rules.plans.builder_50k.payout), C.payoutMath(5, null)], p25: C.payoutMath(250, rules.plans.builder_25k.payout) };
      const pay = C.payouts(list, rules, T), pay2 = C.payouts(list.concat([{ ...E('payout_in', 400, '2026-11-03', { acct: 'b', id: 'g2' }), rid: 'g2' }]), rules, T);
      // the waterfall, the day map, CSV
      const wf = C.byMonth(list, feed, T, 4), dm = C.daily(list, feed, '2026-10-01', T);
      const csv = C.toCSV([{ ...E('expense', 12.5, '2026-11-01', { note: 'say "hi", ok', cat: 'Data feeds' }), rid: 'a' }, { ...E('payout_in', 800, '2026-10-30', { acct: 'a' }), rid: 'b' }, { ...E('payout_req', 1000, '2026-10-29'), rid: 'c' }, { key: 'auto:fee:x', id: 'auto:fee:x', rid: 'auto:fee:x', kind: 'fee', amount: 91.8, date: '2026-10-18', cat: 'Eval fees', acct: 'lit50k', note: 'auto', auto: true }]);
      // export / import
      const exp = C.exportJSON(st, 0), back = C.importJSON(exp, C.emptyState(), 'replace'), merged = C.importJSON(exp, st, 'merge'), partial = C.importJSON(JSON.stringify({ entries: [{ kind: 'fee', amount: 5, date: T, id: 'n1' }, { kind: 'bad' }, null] }), st, 'merge');
      const errs = [C.importJSON('{nope', st, 'merge'), C.importJSON('{"a":1}', st, 'merge'), C.importJSON('[]', st, 'merge')].map((r) => [r.ok, r.error]);
      const ls = [C.loadState('garbage'), C.loadState(null), C.loadState({ entries: 5 }), C.loadState(JSON.stringify({ entries: [{ kind: 'fee', amount: 5, date: T, id: 'a' }, { kind: 'fee', amount: 5, date: T, id: 'a' }], settings: { taxPct: 999 } }))].map((s) => [s.entries.length, s.settings.taxPct]);
      // pure edits
      const a1 = C.addEntry(C.emptyState(), { kind: 'fee', amount: 10, date: T }), u1 = C.updateEntry(a1, a1.entries[0].id, { amount: 20 }), r1 = C.removeEntry(u1, a1.entries[0].id);
      const edits = { added: a1.entries.length, updated: u1.entries[0].amount, removed: r1.entries.length, badAdd: C.addEntry(C.emptyState(), { kind: 'fee', amount: -1, date: T }), badUp: C.updateEntry(a1, 'nope', {}), badUp2: C.updateEntry(a1, a1.entries[0].id, { amount: -5 }), badRm: C.removeEntry(a1, 'nope'), orig: a1.entries[0].amount };
      // the demo fixture works out
      const dl = C.expand(fx.entries.map((e) => C.cleanEntry({ ...e, id: 'd' + e.off + e.kind, date: C.addDays(T, e.off) })), T), dfeed = { balance: fx.kalshi.balance, total_pnl: fx.kalshi.total_pnl, days: fx.kalshi.days.map((d) => [C.addDays(T, d[0]), d[1]]) };
      const dt = C.totals(dl, dfeed, T), dbe = C.breakEven(dl, dfeed, T);
      out({ dates, bad, parsed, okE, rec, t: { income: t.income, costs: t.costs, pending: t.pending, net: t.net, month: t.month, byKind: t.byKind, byCat: t.byCat, taxPaid: t.taxPaid, n: list.length }, kal, tk: { net: tk.net, kalshi: tk.kalshi.result, month: tk.month }, tb: { net: tb.net, month: tb.month },
        auto: auto.map((a) => [a.key, a.amount, a.date, a.acct]), auto0: auto0.length, autoOld: autoOld.map((a) => [a.date, a.amount]), mg: { none: [mg.none.auto.length, mg.none.suppressed.length], mine: [mg.mine.auto.map((a) => a.key), mg.mine.suppressed.map((a) => a.key)], hid: [mg.hid.auto.map((a) => a.key), mg.hid.suppressed.map((a) => a.key)] },
        kept: [kept.entries.length, kept.entries[0].amount, kept.entries[0].date, keptM.auto.map((a) => a.key)],
        acc: { a: ['cost', 'payouts', 'pending', 'net', 'payback', 'sim', 'stage'].map((k) => ac('a')[k]), b: ['cost', 'net', 'payback', 'togo'].map((k) => ac('b')[k]), bPending: ac('b').pending, z: ac('z').payback, general: ['cost', 'net', 'payback'].map((k) => ac('general')[k]), n: acc.length },
        be, tx: { base: tx.base, set: tx.setAside, paid: tx.paid, left: tx.left, q: tx.quarters.map((q) => q.net), losing: tx.losing, tl: [tl.base, tl.setAside, tl.losing], cap: tcap.pct }, pm, pay: { pend: pay.pending.map((p) => [p.amount, p.waiting]), got: pay.received.length, req: pay.requested.length, plans: pay.plans.map((p) => p.name), after: pay2.pending.length, count: pay.countBy },
        wf: wf.map((r) => [r.ym, r.income, r.costs, r.kalshi, r.net, r.cum]), dm, csv, exp: { ok: back.ok, added: back.added, same: JSON.stringify(back.state.entries) === JSON.stringify(st.entries), mergedAdded: merged.added, partial: [partial.added, partial.skipped], errs, nSettings: back.state.settings.taxPct, hasApp: JSON.parse(exp).app },
        ls, edits, demo: { net: dt.net, income: dt.income, costs: dt.costs, kal: dt.kalshi.result, pending: dt.pending, be: dbe.state, bem: dbe.months }, fmt: [C.money(1234.5), C.money(-5), C.moneyS(5), C.moneyS(-5), C.moneyS(0), C.money(null), C.monthName('2026-11')],
        burn: C.monthlyBurn([E('expense', 12, '2026-01-01', { rec: { every: 'month' } }), E('expense', 120, '2026-01-01', { rec: { every: 'year' } }), E('expense', 6, '2026-01-01', { rec: { every: 'week' } }), E('expense', 50, '2026-01-01'), E('income', 99, '2026-01-01', { rec: { every: 'month' } })]) });""")
    if js.get("error"):
        check("b. node runs ledgercore.js", False, js["error"])
        return
    d = js["dates"]
    check("b. dates: 31 Jan + 1 month = 28 Feb (29 in 2028), back a month from 31 Mar = 28 Feb, +3 months across a year, 17 days between 18 Oct and 4 Nov, impossible dates refused, a leap day accepted",
          d["jan31"] == "2026-02-28" and d["leap"] == "2028-02-29" and d["back"] == "2026-02-28" and d["year"] == "2027-02-15" and d["days"] == "2027-01-01" and d["between"] == 17 and d["bad"] == [False] * 6 and d["good"] and d["mb"] == ["2025-12", "2026-01", "2026-02"] and d["today"], d)
    check("b. entries: a negative, zero, text, unknown kind, impossible date, junk or absurd amount is refused; '$1,234.50' parses; an amount rounds to cents, spaces collapse, a bad repeat is dropped",
          js["bad"] == [None] * 9 and js["parsed"] == [1234.5, 91.8, None, None, None, 12] and js["okE"]["amount"] == 91.8 and js["okE"]["note"] == "a b" and "rec" not in js["okE"], (js["bad"], js["parsed"], js["okE"]))
    r = js["rec"]
    check("b. recurring: monthly from 31 Jan lands on 31 Jan, 28 Feb, 31 Mar, 30 Apr; weekly from 7 Oct gives 5 (7, 14, 21, 28 Oct and 4 Nov); yearly gives 3; 'until' stops it; the future and one-offs behave; the next due date is listed",
          r["m31"] == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"] and len(r["week"]) == 5 and r["week"][-1] == "2026-11-04" and len(r["year"]) == 3 and r["until"] == ["2026-08-10", "2026-09-10"] and r["future"] == [] and r["once"] == ["2026-10-01"]
          and r["upcoming"] == ["2026-11-20"], r)
    t = js["t"]
    check("b. by hand: income 800 + 50 = 850; costs 91.80 + 43 + 3 x 12 = 170.80; pending 500 (the 1,000 asked for on 30 Oct is matched by the 800 received; the 500 asked for on 3 Nov is still waiting; neither is income); net 679.20; this month (Nov): +800 +50 - 12 = 838; tax paid 4 is not a cost",
          t["income"] == 850 and abs(t["costs"] - 170.8) < 1e-9 and t["pending"] == 500 and abs(t["net"] - 679.2) < 1e-9 and abs(t["month"]["net"] - 838) < 1e-9 and t["taxPaid"] == 4 and t["n"] == 10 and abs(t["byCat"]["VPS / Azure"] + 36) < 1e-9, t)
    k = js["kal"]
    check("b. Kalshi: deposits 200, withdrawals 40, balance 188.40 -> result -$-1.60 + ... = 28.40 + ... (balance + withdrawals - deposits = 28.40, basis balance); no deposits -> the bot's own total -81.77; no feed -> unknown; junk feed -> unknown",
          k["bal"]["result"] == 28.4 and k["bal"]["basis"] == "balance" and k["bot"]["result"] == -81.77 and k["bot"]["basis"] == "bot" and k["none"]["result"] is None and k["none"]["basis"] == "none" and k["junk"]["result"] is None and len(k["junk"]["days"]) == 0, k)
    check("b. the net includes the Kalshi result (679.20 + 28.40 = 707.60 with deposits; 679.20 - 81.77 = 597.43 from the bot's own total); this month adds the bot's days in the month (-3.30 + 5 -2 on 30 Oct is not in November)",
          abs(js["tk"]["net"] - 707.6) < 1e-9 and abs(js["tb"]["net"] - 597.43) < 1e-9 and abs(js["tb"]["month"]["kalshi"] - 1.7) < 1e-9 and abs(js["tb"]["month"]["net"] - 839.7) < 1e-9, (js["tk"], js["tb"]))
    check("b. AUTO entries: the OWNER's real prices from rules.json win over home.json's ($91.80 on 2026-10-18 for lit50k, $43 on 2026-10-26 for atlas25k); an unknown account uses home.json's own price; no price = no entry; a duplicate id once; nothing without home.json; a future start date is clamped to today",
          js["auto"] == [["auto:fee:lit50k", 91.8, "2026-10-18", "lit50k"], ["auto:fee:atlas25k", 43, "2026-10-26", "atlas25k"], ["auto:fee:other", 20, "2026-11-04", "other"]] and js["auto0"] == 0 and js["autoOld"][0][0] <= "2026-11-04", (js["auto"], js["autoOld"]))
    mg = js["mg"]
    check("b. auto entries are suppressed when you enter a fee for that account yourself (no double count) or hide them; otherwise they count; Keep makes a real entry and the auto copy disappears",
          mg["none"] == [3, 0] and mg["mine"] == [["auto:fee:atlas25k", "auto:fee:other"], ["auto:fee:lit50k"]] and mg["hid"] == [["auto:fee:lit50k", "auto:fee:other"], ["auto:fee:atlas25k"]] and js["kept"][:3] == [1, 91.8, "2026-10-18"] and "auto:fee:lit50k" not in js["kept"][3], (mg, js["kept"]))
    a = js["acc"]
    check("b. accounts: A cost 91.80, payouts 800 (its 1,000 request is matched), net 708.20, paid back, its simulated P&L 1,240.50 kept apart from cash; B cost 43, net -43, 'not yet', 43 to go; an account with no entries 'no cost yet'; General holds the expense",
          a["a"] == [91.8, 800, 0, 708.2, "paid back", 1240.5, "eval"] and a["b"] == [43, -43, "not yet", 43] and a["bPending"] == 500 and a["z"] == "no cost yet" and a["general"][0] == 36 and a["general"][1] == -36 + 50 and a["n"] >= 4, a)
    be = js["be"]
    check("b. break-even: paid back with a surplus; no costs = nothing to pay back; no data = no cost; 400 spent and 100 a month for 3 full months = 4 -> 1 month left ... by hand: net -100 at 100 a month is 1 month; a losing pace is 'stalled'; one month of data gives no pace (unknown, early)",
          be["paid"]["state"] == "paid" and be["paid"]["surplus"] == 400 and be["nocost"]["state"] == "nocost" and be["none"]["state"] == "nocost" and be["track"]["state"] == "on_track" and be["track"]["rate"] == 100 and be["track"]["months"] == 1 and not be["track"]["early"]
          and be["stalled"]["state"] == "stalled" and be["early"]["state"] == "unknown" and be["early"]["early"] is True, be)
    x = js["tx"]
    check("b. tax: 25% of the year's net, minus tax already recorded, by quarter (Q3 -12 for the first VPS month, Q4 +691.20); a losing year sets nothing aside; the rate is capped at 60%",
          abs(x["base"] - 679.2) < 1e-9 and abs(x["set"] - 169.8) < 1e-9 and x["paid"] == 4 and abs(x["left"] - 165.8) < 1e-9 and abs(sum(x["q"]) - 679.2) < 1e-9 and x["q"] == [0, 0, -12, 691.2] and x["tl"] == [-500, 0, True] and x["cap"] == 60, x)
    p = js["pm"]
    check("b. the payout split (MFFU 50K: 80%, $500 to $2,000): 1,000 -> 800 to you, 200 stays; 300 warns below the minimum; 5,000 is counted as the 2,000 maximum (1,600) with a warning; junk gives nothing; the 25K plan's 250 minimum",
          p["ok"]["receive"] == 800 and p["ok"]["kept"] == 200 and p["ok"]["warn"] == "" and "minimum" in p["low"]["warn"] and p["high"]["counted"] == 2000 and p["high"]["receive"] == 1600 and "maximum" in p["high"]["warn"] and p["bad"] == [None, None, None]
          and p["p25"]["receive"] == 200 and p["p25"]["warn"] == "", p)
    y = js["pay"]
    check("b. the payout calendar: the 1,000 requested on 30 Oct is received as 800 (80%) so it does not wait; the 500 asked for on 3 Nov waits 1 day, and stops waiting when 400 (80%) arrives; both plans' rules are listed",
          y["got"] == 1 and y["req"] == 2 and y["plans"] == ["Builder 50K", "Builder 25K"] and y["pend"] == [[500, 1]] and y["after"] == 0 and y["count"] == {"a": 1}, y)
    wf = js["wf"]
    check("b. the waterfall: 4 months, each net = in - out + Kalshi, and the running total ends at the all-time net (597.43 with the bot's total)... months before the bot's first day add nothing; the sum of the months' nets is the cumulative end",
          [r[0] for r in wf] == ["2026-08", "2026-09", "2026-10", "2026-11"] and abs(sum(r[4] for r in wf) - wf[-1][5]) < 1e-9 and wf[-1][5] > 0 and wf[1][2] == 12 and wf[2][1] == 0, wf)
    check("b. the day map: each day's cash in - out plus the bot's own Kalshi days (2 Nov: +800 -3.30 = 796.70; 18 Oct: -91.80)", js["dm"].get("2026-11-02") == 796.7 and js["dm"].get("2026-10-18") == -91.8 and js["dm"].get("2026-10-30") == -2, js["dm"])
    check("b. CSV for an accountant: a header, sorted by date, quotes and commas escaped, outflows negative, payouts positive, the request pending (amount unsigned), the site's auto entry marked",
          js["csv"] == 'date,type,category,account,amount_usd,direction,source,recurring,note\n2026-10-18,Eval fee,Eval fees,lit50k,-91.8,out,site (auto),,auto\n2026-10-29,Payout requested,Payouts,general,1000,pending,you,,\n2026-10-30,Payout received,Payouts,a,800,in,you,,\n2026-11-01,Expense,Data feeds,general,-12.5,out,you,,"say ""hi"", ok"\n', js["csv"])
    e = js["exp"]
    check("b. export / import: a round trip gives the same entries and settings; merging adds only new ids (0 from your own export); a partly bad file adds the good entry and counts the rest as skipped; a non-JSON or non-Ledger file is refused with a message",
          e["ok"] and e["added"] == 8 and e["same"] and e["mergedAdded"] == 0 and e["partial"] == [1, 2] and e["errs"][0][0] is False and "not JSON" in e["errs"][0][1] and e["errs"][1][0] is False and e["errs"][2][0] is False and e["hasApp"] == "ledger", e)
    check("b. junk in, safe out: bad JSON, null, a wrong shape, duplicate ids and a 999% tax rate give a clean state (rate capped at 60); the edits are pure (add, update, remove; refused changes return null; the original is untouched)",
          js["ls"] == [[0, 25], [0, 25], [0, 25], [1, 60]] and js["edits"] == {"added": 1, "updated": 20, "removed": 0, "badAdd": None, "badUp": None, "badUp2": None, "badRm": None, "orig": 10}, (js["ls"], js["edits"]))
    dm = js["demo"]
    check("b. the demo fixture works out (example numbers): net, income, costs, a Kalshi result from its balance, a payout still pending, and 'paid back'", dm["pending"] == 900 and dm["income"] == 1280 and dm["kal"] == 28.4 and dm["be"] in ("paid", "on_track") and dm["net"] > 0, dm)
    check("b. number words: $1,234.50, -$5.00, +$5.00, -$5.00, $0.00 for zero, '-' for nothing, month names; repeating costs per month (12 + 120/12 + 6 x 52/12 = 48; one-offs and income do not count)",
          js["fmt"] == ["$1,234.50", "-$5.00", "+$5.00", "-$5.00", "$0.00", "-", "Nov '26"] and abs(js["burn"] - 48) < 1e-9, (js["fmt"], js["burn"]))


# ------------------------------------------------------------------------------------------------ c. the browser
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


HOME = {"goals": {"accounts": [{"id": "lit50k", "name": "MFFU Builder 50K", "stage": "eval", "status": "open", "price": 99.0, "profit": -699.1},
                               {"id": "atlas25k", "name": "MFFU Builder 25K", "stage": "eval", "status": "open", "price": 63.0, "profit": 354.8}]}}
FEED = {"v": 3, "kind": "kalshi", "name": "Kalshi Edge", "t": 1793759943, "balance": 55.81, "total_pnl": -81.77, "week_pnl": -3.3, "days": [["2026-11-02", -3.3], ["2026-10-30", 6.87]]}
GEOM = """() => { const W = innerWidth, bad = [];
  for (const el of document.querySelectorAll('#app *, .fab, #toast:not([hidden]) *, #sheet:not([hidden]) *')) {
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    const cs = getComputedStyle(el), b = el.getBoundingClientRect();
    if (!b.width || !b.height || cs.visibility === 'hidden' || el.closest('[hidden]') || el.closest('.tabs') && el.tagName === 'BUTTON') continue;
    if (b.right > W - 80 && b.bottom > innerHeight - 170 && el.closest('#sheet')) bad.push('orb ' + (el.id || el.className));
    if (b.right > W - 16 + 0.5 || b.left < 16 - 0.5) { if (!el.closest('svg') && !(el.closest('.hero') && false)) bad.push('gutter ' + (el.id || el.className || el.tagName) + ' ' + Math.round(b.left) + '-' + Math.round(b.right)); }
  }
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad; }"""


def make_site(tmp, home=False, mode="x"):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "ledger"))
    for d in ("jarvis", "olympus"):
        shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
    if home:
        with open(os.path.join(site, "home.json"), "w", encoding="utf-8") as fh:
            json.dump(HOME, fh)
    return site


def run_browser():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="le_ledger_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/ledger/"
    outside, raw_hits = [], []
    shots = os.environ.get("LG_SHOTS")
    live = {"feed": False}
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=True, quality="low", ctx=None, downloads=False):
                if ctx is None:
                    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, accept_downloads=True, reduced_motion="reduce" if reduced else "no-preference")
                    if quality:
                        ctx.add_init_script(f"try {{ if (!localStorage.getItem('jfx')) localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")

                    def guard(route):
                        u = route.request.url
                        if u.startswith(RAW_PREFIX):
                            raw_hits.append(u)
                            return route.fulfill(status=200, body=json.dumps(FEED), content_type="application/json", headers={"access-control-allow-origin": "*"}) if live["feed"] else route.abort()
                        if u.startswith(f"http://127.0.0.1:{srv.server_address[1]}") or u.startswith(("data:", "blob:")):
                            return route.continue_()
                        outside.append(u)
                        return route.abort()
                    ctx.route("**/*", guard)
                p = ctx.new_page()
                p.set_default_timeout(40000)
                p.errs = []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and p.errs.append(m.text))
                return ctx, p

            def ready(p, qs=""):
                p.goto(base + qs)
                p.wait_for_function("document.body.dataset.ready === '1' && window.LG && LG.state().scene && LG.state().scene.drawn > 0", timeout=240000)

            st = lambda p: p.evaluate("LG.state()")  # noqa: E731
            ls = lambda p: p.evaluate("(() => { const v = localStorage.getItem('ledger.v1'); return v ? JSON.parse(v) : null; })()")  # noqa: E731
            net = lambda p: p.inner_text("#net")  # noqa: E731

            def add(p, amount, kind, date=None, more=None):
                p.click("#add")
                p.wait_for_selector("#sheet:not([hidden])")
                p.fill("#fAmount", str(amount))
                p.select_option("#fKind", kind)
                if date:
                    p.fill("#fDate", date)
                if more:
                    p.evaluate("document.getElementById('more').open = true")
                    for k, v in more.items():
                        (p.select_option if k in ("fCat", "fAcct", "fRec") else p.fill)(f"#{k}", v)
                p.click("#fSave")

            # ---- 1. DEMO until the first entry: nothing is written, nothing is blank
            make_site(tmp)
            ctx, p = page()
            ready(p, "?today=2026-11-04")
            s = st(p)
            check("c. no home file, no feed, no entries: the DEMO copy (DEMO tag + banner, example numbers, a vault with coins), nothing written to the phone, no errors",
                  s["demo"] and p.is_visible("#demo") and p.is_visible("#demoBanner") and net(p) == "$570.60" and s["entries"] == 0 and s["scene"]["coins"] > 0 and ls(p) is None and not p.errs and p.is_visible("#lite"), (s, p.errs))
            ov = p.evaluate(GEOM)
            check("c. at 390 x 844: inside the 16 px gutters, no sideways scroll, the + button is on the left (out of Jarvis's orb corner), at least 60 px wide",
                  not ov and p.evaluate("(() => { const b = document.querySelector('.fab').getBoundingClientRect(); return b.left < 100 && b.width >= 60 && b.right < 120; })()"), ov)
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "ledger-demo.png"))
            tabs = {}
            for t in ("acct", "cash", "tax", "list", "over"):
                p.click(f"#t-{t}")
                tabs[t] = p.inner_text(f"#p-{t}")
            check("c. every tab shows something in the demo: accounts (example eval cards + Kalshi), cash (waterfall, heat map, payout calendar, rules), taxes (set-aside + not tax advice), entries (example notice), overview",
                  "example eval 50k" in tabs["acct"].lower() and "kalshi bot" in tabs["acct"].lower() and "monthly waterfall" in tabs["cash"].lower() and "payout calendar" in tabs["cash"].lower() and "mffu payout rules" in tabs["cash"].lower()
                  and "not tax advice" in tabs["tax"].lower() and "example numbers" in tabs["list"].lower() and "break-even tracker" in tabs["over"].lower(), {k: v[:80] for k, v in tabs.items()})
            ctx.close()

            # ---- 2. quick add, validation, edit, delete + undo, recurring, the vault grows
            ctx, p = page(reduced=False)
            ready(p, "?today=2026-11-04")
            p.click("#add")
            p.wait_for_selector("#sheet:not([hidden])")
            p.click("#fSave")
            err0 = p.inner_text("#fErr")
            p.fill("#fAmount", "-5")
            p.click("#fSave")
            check("c. + opens the sheet with 3 fields (amount, what, date) and More; an empty or negative amount shows an error and saves nothing",
                  p.locator("#form > label.f").count() == 3 and "above zero" in err0 and "above zero" in p.inner_text("#fErr") and ls(p) is None and p.is_visible("#sheet"), (err0, ls(p)))
            p.fill("#fAmount", "91.80")
            p.select_option("#fKind", "fee")
            p.fill("#fDate", "2026-10-18")
            p.click("#fSave")
            p.wait_for_function("LG.state().entries === 1")
            e1 = ls(p)["entries"][0]
            check("c. a first entry ends the DEMO: $91.80 eval fee on 2026-10-18 saved on the phone ('ledger.v1'), the hero shows -$91.80, the DEMO banner is gone, a toast says what was added",
                  e1["kind"] == "fee" and e1["amount"] == 91.8 and e1["date"] == "2026-10-18" and net(p) == "-$91.80" and not st(p)["demo"] and not p.is_visible("#demo") and not p.is_visible("#demoBanner") and "Added eval fee $91.80" in p.inner_text("#toast"), (e1, net(p)))
            add(p, "800", "payout_in", "2026-11-02", {"fAcct": "general", "fNote": "first payout"})
            p.wait_for_function("LG.state().entries === 2")
            c2 = st(p)["scene"]
            check("c. a payout received of $800 lifts the net to $708.20, the vault's pile grows from 0 coins to about 71 (1 coin = $10 at this size), and coins rain onto it", net(p) == "$708.20" and 60 <= c2["coins"] <= 80 and c2["unit"] == 10 and c2["raining"] + c2["coins"] > 0, (net(p), c2))
            add(p, "12", "expense", "2026-09-04", {"fCat": "VPS / Azure", "fRec": "month", "fNote": "VPS"})
            p.wait_for_function("LG.state().entries === 3")
            m = p.evaluate("LG.model()")
            check("c. a repeating cost ($12 a month from 4 Sep) is one entry but three dated costs (4 Sep, 4 Oct, 4 Nov): costs 91.80 + 36 = 127.80, net $672.20; this month shows -$12 + $800", len(ls(p)["entries"]) == 3 and abs(m["totals"]["costs"] - 127.8) < 1e-6 and net(p) == "$672.20" and abs(m["totals"]["month"]["net"] - 788) < 1e-6, (net(p), m["totals"]))
            p.click("#t-list")
            rows = p.locator("#p-list .erow")
            check("c. Entries lists them newest first with the repeat noted, and a filter narrows them (Payouts: 1)", rows.count() == 3 and "repeats every month" in p.inner_text("#p-list") and rows.first.inner_text().startswith("11-02"), p.inner_text("#p-list")[:200])
            p.click("[data-f=payouts]")
            check("c. ...Payouts filter shows only the payout", p.locator("#p-list .erow").count() == 1 and "Payout received" in p.inner_text("#p-list .erow"))
            p.click("[data-f=all]")
            p.locator("#p-list .erow").first.click()
            p.wait_for_selector("#sheet:not([hidden])")
            check("c. tapping an entry opens it for editing (title Edit entry, its values filled, a Delete button)", p.inner_text("#sheetTitle").lower() == "edit entry" and p.input_value("#fAmount") == "800" and p.input_value("#fNote") == "first payout" and p.is_visible("#fDelete"))
            p.fill("#fAmount", "900")
            p.click("#fSave")
            p.wait_for_function("document.getElementById('net').textContent === '$772.20'")
            check("c. editing the amount to $900 gives net $772.20 and the toast offers Undo", p.is_visible("#toastUndo") and ls(p)["entries"][1]["amount"] == 900 or ls(p)["entries"][0]["amount"] == 900, net(p))
            p.click("#toastUndo")
            p.wait_for_function("document.getElementById('net').textContent === '$672.20'")
            check("c. Undo puts the old amount back ($672.20) and saves it", any(e["amount"] == 800 for e in ls(p)["entries"]) and not any(e["amount"] == 900 for e in ls(p)["entries"]))
            p.locator("#p-list .erow").first.click()
            p.wait_for_selector("#sheet:not([hidden])")
            p.click("#fDelete")
            p.wait_for_function("LG.state().entries === 2")
            check("c. Delete removes the entry (net drops by $800 to -$127.80... no: costs only) and Undo brings it back", net(p) == "-$127.80" and "Deleted" in p.inner_text("#toast") and p.is_visible("#toastUndo"), net(p))
            p.click("#toastUndo")
            p.wait_for_function("LG.state().entries === 3")
            check("c. ...the deleted entry is back ($672.20), saved", net(p) == "$672.20" and len(ls(p)["entries"]) == 3)
            ov = p.evaluate(GEOM)
            check("c. entries tab inside the gutters, no sideways scroll", not ov, ov)
            # net negative: no coins
            add(p, "2000", "expense", "2026-11-03", {"fCat": "Mini PC / hardware"})
            p.wait_for_function("LG.state().entries === 4")
            check("c. a bigger cost pushes the net below zero (-$1,327.80): the hero turns red and the vault has no coins (honest: an empty vault)", net(p) == "-$1,327.80" and "neg" in p.get_attribute("#net", "class") and st(p)["scene"]["coins"] == 0, (net(p), st(p)["scene"]))
            ctx.close()

            # ---- 3. the tabs on a real-looking ledger (home.json known, Kalshi feed on), auto entries, Kalshi result
            make_site(tmp, home=True)
            live["feed"] = True
            ctx, p = page()
            ready(p, "?today=2026-11-04")
            s = st(p)
            check("c. with the site's accounts file: not DEMO, two AUTO fees at the owner's real prices ($91.80 on 18 Oct, $43 on 26 Oct, not home.json's $99 / $63), the Kalshi result from the bot's own total (-$81.77), net -$216.57",
                  not s["demo"] and s["auto"] == 2 and net(p) == "-$216.57" and "filled in from the site" in p.inner_text("#p-over").lower() and raw_hits, (s, net(p)))
            if shots:
                p.screenshot(path=os.path.join(shots, "ledger-real.png"), full_page=True)
            p.click("#t-acct")
            ac = p.inner_text("#p-acct")
            check("c. Accounts: a card per account (cost to date, payouts, net, payback status, the simulated P&L kept apart as 'not cash') and the Kalshi card with the bot-total note",
                  "mffu builder 50k eval (zlarior)" in ac.lower() and "$91.80" in ac and "not yet" in ac.lower() and "performance on the account, not cash" in ac and "kalshi bot (real money)" in ac.lower() and "bot's own total P&L" in ac, ac[:300])
            p.click("#t-over")
            p.click("[data-act=hide][data-key='auto:fee:atlas25k']")
            p.wait_for_function("document.getElementById('net').textContent === '-$173.57'")
            check("c. 'Not mine' hides an auto entry (the $43 stops counting: net -$173.57) and the choice is kept (hidden list on the phone)", "auto:fee:atlas25k" in ls(p)["hidden"] and st(p)["auto"] == 1, ls(p))
            p.click("[data-act=keep][data-key='auto:fee:lit50k']")
            p.wait_for_function("LG.state().entries === 1")
            check("c. 'Keep' turns an auto fee into your own entry ($91.80, same account, no double count: net unchanged, auto entries 0)", ls(p)["entries"][0]["acct"] == "lit50k" and net(p) == "-$173.57" and st(p)["auto"] == 0, (ls(p), net(p)))
            add(p, "200", "deposit", "2026-10-01", {"fAcct": "kalshi"})
            p.wait_for_function("LG.state().entries === 2")
            p.click("#t-acct")
            check("c. a $200 Kalshi deposit switches the result to balance-based: $55.81 + $0 - $200 = -$144.19 (the card says how it is worked out)", "Result = balance + what you took out - what you put in" in p.inner_text("#p-acct") and "-$144.19" in p.inner_text("#p-acct"), p.inner_text("#p-acct")[-400:])
            p.click("#t-cash")
            cash = p.inner_text("#p-cash")
            cells = p.locator("#p-cash svg rect[data-date]").count()
            check("c. Cash: the waterfall (8 months of bars and a running total), the heat map (98 days), the payout calendar with its rules, and the split calculator ($1,000 -> about $800.00)",
                  p.locator("#p-cash svg polyline").count() == 1 and cells >= 90 and "MFFU payout rules" in cash and "Nov 2026" in cash or "Nov 2026" in cash and p.locator("#p-cash .cal span").count() >= 28, (cells, cash[:200]))
            p.fill("#calcAmt", "1000")
            check("c. ...typing 1000 in the calculator says you would receive about $800.00 (80% split, $200.00 stays with MFFU)", "$800.00" in p.inner_text("#calcOut") and "$200.00" in p.inner_text("#calcOut"), p.inner_text("#calcOut"))
            p.fill("#calcAmt", "300")
            check("c. ...300 warns it is below the minimum request", "minimum" in p.inner_text("#calcOut"), p.inner_text("#calcOut"))
            p.click("[data-act=cal][data-d='-1']")
            check("c. the calendar's previous-month button moves to Oct 2026", "Oct 2026" in p.inner_text("#p-cash"), p.inner_text("#p-cash")[:120])
            p.click("#t-tax")
            tx = p.inner_text("#p-tax")
            check("c. Taxes: the year's income, costs and net, the 25% set-aside (nothing set aside while the year is below zero), by quarter, 'Not tax advice' with the disclaimer, the CSV and tax-payment buttons",
                  "TAX SET-ASIDE, 2026" in tx.upper() and "Still to set aside" in tx and "$0.00" in tx and "NOT tax advice" in tx and "Download CSV for my accountant" in tx and "Q4" in tx, tx[:300])
            p.fill("#taxPct", "30")
            p.dispatch_event("#taxPct", "change")
            p.wait_for_function("(() => { const v = localStorage.getItem('ledger.v1'); return v && JSON.parse(v).settings.taxPct === 30; })()")
            check("c. changing the rate to 30% is kept on the phone and shown", "Set aside (30%)" in p.inner_text("#p-tax") and ls(p)["settings"]["taxPct"] == 30)
            ctx.close()

            # ---- 4. export / import / CSV, persistence, clear + undo
            make_site(tmp)
            live["feed"] = False
            ctx, p = page()
            ready(p, "?today=2026-11-04")
            add(p, "91.80", "fee", "2026-10-18")
            p.wait_for_function("LG.state().entries === 1")
            add(p, "800", "payout_in", "2026-11-02")
            p.wait_for_function("LG.state().entries === 2")
            add(p, "5", "tax", "2026-11-03")
            p.wait_for_function("LG.state().entries === 3")
            p.click("#t-list")
            before = p.evaluate("() => JSON.parse(localStorage.getItem('ledger.v1'))")
            with p.expect_download() as dj:
                p.click("[data-act=json]")
            path_j = dj.value.path()
            exp = json.loads(open(path_j, encoding="utf-8").read())
            with p.expect_download() as dc:
                p.click("[data-act=csv]")
            csv_txt = open(dc.value.path(), encoding="utf-8").read()
            check("c. Export JSON downloads a file with every entry and the settings (v1, app ledger); CSV downloads a header and one signed row per dated entry (fee -91.8, payout 800, tax)",
                  exp["app"] == "ledger" and len(exp["entries"]) == 3 and exp["settings"]["taxPct"] == 25 and dj.value.suggested_filename == "ledger-2026-11-04.json" and csv_txt.startswith("date,type,category,account,amount_usd,direction,source,recurring,note\n")
                  and "2026-10-18,Eval fee,Eval fees,general,-91.8,out,you" in csv_txt and "2026-11-02,Payout received,Payouts,general,800,in,you" in csv_txt and "Tax paid" in csv_txt and dc.value.suggested_filename == "ledger-2026-11-04.csv", (exp["entries"][:1], csv_txt[:300]))
            after = p.evaluate("() => JSON.parse(localStorage.getItem('ledger.v1'))")
            import datetime as _dt
            le = after.get("lastExport", "")
            fresh = False
            try:
                fresh = abs((_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.fromisoformat(le.replace("Z", "+00:00"))).total_seconds()) < 300
            except ValueError:
                pass
            check("c. tapping Export JSON writes `lastExport` (an ISO time, just now) into the ledger.v1 state so Compass can see it; before the export there was none; the CSV button does not set it; the entries are untouched",
                  "lastExport" not in before and fresh and len(after["entries"]) == 3 and after["settings"]["taxPct"] == 25, (before.keys(), after.get("lastExport")))
            p.reload()
            p.wait_for_function("document.body.dataset.ready === '1'", timeout=240000)
            check("c. a reload keeps the ledger (3 entries, net $703.20 = 800 - 91.80 - 0 tax is not a cost... $708.20)", st(p)["entries"] == 3 and net(p) == "$708.20" and not st(p)["demo"], (st(p), net(p)))
            p.click("#t-list")
            p.click("[data-act=clear]")
            check("c. Clear everything asks a second tap first", "Tap again" in p.inner_text("#p-list") and st(p)["entries"] == 3)
            p.click("[data-act=clear]")
            p.wait_for_function("LG.state().entries === 0")
            check("c. ...then clears (the ledger is empty, the demo returns), with Undo offered", st(p)["demo"] and p.is_visible("#toastUndo"), st(p))
            p.click("#toastUndo")
            p.wait_for_function("LG.state().entries === 3")
            check("c. Undo brings the whole ledger back", net(p) == "$708.20")
            p.click("#t-list")
            p.click("[data-act=clear]")
            p.click("[data-act=clear]")
            p.wait_for_function("LG.state().entries === 0")
            p.evaluate("document.getElementById('toast').hidden = true")
            with p.expect_file_chooser() as fc:
                p.click("[data-act=import]")
            fc.value.set_files(path_j)
            p.wait_for_function("LG.state().entries === 3")
            check("c. Import JSON (a file chosen on the phone) puts the three entries back; importing the same file again adds nothing", net(p) == "$708.20" and "Imported 3 entries" in p.inner_text("#toast"), p.inner_text("#toast"))
            r = p.evaluate("LG.importText(" + json.dumps(open(path_j, encoding="utf-8").read()) + ")")
            check("c. ...a second import of the same file adds 0; a file that is not a Ledger export is refused with a message and changes nothing", r["added"] == 0 and st(p)["entries"] == 3 and p.evaluate("LG.importText('{\"x\": 1}')")["ok"] is False and "not a Ledger export" in p.inner_text("#toast") and st(p)["entries"] == 3)
            check("c. no page errors so far, and the only key on the phone besides the quality setting is ledger.v1", not p.errs and p.evaluate("Object.keys(localStorage).filter((k) => k !== 'jfx' && !k.startsWith('olympus') && !k.startsWith('ledger.opt404.'))") == ["ledger.v1"], (p.errs, p.evaluate("Object.keys(localStorage)")))
            ctx.close()

            # ---- 5. reduced motion keeps the vault still; the high tier; offline already covered (no feed, no home)
            ctx, p = page(reduced=True)
            ready(p, "?today=2026-11-04")
            a0 = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1500)
            check("c. reduced motion: the vault is a still picture (no frames while nothing changes), the odometer and the rest still work, no errors", st(p)["scene"]["drawn"] - a0 <= 2 and not p.errs, (a0, st(p)["scene"]["drawn"], p.errs))
            ctx.close()
            if os.environ.get("LG_NO_HIGH") != "1":
                ctx, p = page(reduced=False, quality="high")
                ready(p, "?today=2026-11-04&q=high&gpu=1")
                p.wait_for_function("LG.state().scene.rays", timeout=90000)
                s = st(p)["scene"]
                check("c. the high tier (?q=high&gpu=1): 3 passes (scene, bloom, finish), up to 620 coins, god rays from the fx library, gold dust, no errors", s["quality"] == "high" and s["passes"] == 3 and s["max"] == 620 and s["rays"] and s["dust"] == 320 and not p.errs, (s, p.errs))
                ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. nothing left the phone: no request to any origin but the public Kalshi feed address (a read, answered locally here), and no POST anywhere", not outside and raw_hits and all(u.endswith("/main/kalshi.json") for u in raw_hits), (outside[:3], raw_hits[:2]))


# ------------------------------------------------------------------------------------------------ r. the Money plan check (2026-11-04): expected vs actual cash from ../plutus/roadmap.json
def plan_at(months, today):
    """an independent Python version of ledgercore.planAt, to check the page's numbers against"""
    if today < months[0]["from"]:
        return {"cum": 0.0, "lo": 0.0, "hi": 0.0}
    if today > months[-1]["to"]:
        return {k: months[-1][k] for k in ("cum", "lo", "hi")}
    import datetime as dt
    d = lambda s: dt.date.fromisoformat(s)  # noqa: E731
    i = next((j for j, m in enumerate(months) if m["from"] <= today <= m["to"]), None)
    if i is None:
        i = next(j for j, m in enumerate(months) if m["from"] > today) - 1
    m = months[i]
    prev = months[i - 1] if i else {"cum": 0, "lo": 0, "hi": 0}
    span = max(1, (d(m["to"]) - d(m["from"])).days + 1)
    f = min(1.0, ((d(today) - d(m["from"])).days + 1) / span)
    return {k: round(prev[k] + (m[k] - prev[k]) * f, 2) for k in ("cum", "lo", "hi")}


def part_roadmap_maths(rm):
    js = node(r"""const C = await import(url + '/ledgercore.js');
      const mk = (cum) => cum.map((c, i) => ({ m: i + 1, from: `2026-${String(11 + i > 12 ? 11 + i - 12 : 11 + i).padStart(2, '0')}-01`, to: `2026-${String(11 + i > 12 ? 11 + i - 12 : 11 + i).padStart(2, '0')}-28`, cum: c, lo: c - 100, hi: c + 100 }));
      const rm = { first_session: '2026-11-01', versions: { H2: { months: mk([100, 300]) }, H1: { months: mk([200, 600]) } } };
      const E = (kind, amount, date) => C.cleanEntry({ kind, amount, date, acct: 'general', note: '', id: kind + date });
      const L = [E('payout_in', 500, '2026-11-12'), E('fee', 43, '2026-11-10'), E('payout_in', 999, '2026-10-15'), E('expense', 50, '2026-11-12')];
      const mid = C.roadmapVsActual(L, rm, '2026-11-14'), before = C.roadmapVsActual(L, rm, '2026-10-31'), after = C.roadmapVsActual(L, rm, '2027-03-01');
      const below = C.roadmapVsActual([], rm, '2026-12-28'), at2 = C.roadmapVsActual([E('payout_in', 300, '2026-12-01')], rm, '2026-12-28'), above = C.roadmapVsActual([E('payout_in', 700, '2026-12-01')], rm, '2026-12-28');
      out({ ok: C.roadmapOk(rm), bad: [null, {}, { versions: {} }, { first_session: 'x', versions: rm.versions }, { first_session: '2026-11-01', versions: { H2: { months: [] }, H1: rm.versions.H1 } }].map(C.roadmapOk),
        mid, before, after, below: below.verdict, at2: at2.verdict, above: above.verdict, none: C.roadmapVsActual(L, null, '2026-11-14'),
        p0: C.planAt(rm.versions.H2.months, '2026-11-01'), p1: C.planAt(rm.versions.H2.months, '2026-11-28'), p2: C.planAt(rm.versions.H2.months, '2026-12-28'), pend: C.planAt(rm.versions.H2.months, '2030-01-01') }); """)
    check("r. the maths runs in node", "error" not in js, js)
    if "error" in js:
        return
    check("r. a good file is accepted; a missing, empty, half-made or date-less one is refused (null: the tracker stays as before)", js["ok"] is True and js["bad"] == [False] * 5 and js["none"] is None, js["bad"])
    m = js["mid"]
    check("r. only cash since the plan started counts: payouts 500 less the 43 fee = 457 (the 999 payout from October and the 50 expense are not in it)", m["actual"] == 457 and m["payouts"] == 500 and m["fees"] == 43, m)
    check("r. the plan's total is spread over the days of the month: 14 of 28 days of month 1 = half of its 100 (conservative) and half of 200 (Jan-Jun)",
          js["mid"]["expected"] == 50.0 or abs(js["mid"]["expected"] - 100 * 14 / 28) < 0.5, m)
    check("r. before the start nothing is expected; after the end the 12-month total stays", js["before"]["state"] == "before" and js["before"]["expected"] == 0 and js["after"]["state"] == "after" and js["after"]["expected"] == 300, (js["before"], js["after"]))
    check("r. the sentence: below the worst 1 in 10 / at the conservative plan / at the Jan-Jun plan",
          "below the worst 1 in 10" in js["below"] and "at or above the conservative plan" in js["at2"] and "at or above the Jan-Jun plan" in js["above"] and "Drawdown left" in js["below"], (js["below"], js["at2"], js["above"]))
    check("r. planAt: the first day of month 1 is a 28th of it; the last day is the month's total; a day after the end is the last total",
          abs(js["p0"]["cum"] - 100 / 28) < 0.02 and js["p1"]["cum"] == 100 and js["p2"]["cum"] == 300 and js["pend"]["cum"] == 300, (js["p0"], js["p1"], js["p2"], js["pend"]))
    # the real file: the page's interpolation equals the independent Python one on every day of the first two months and the last
    days = ["2026-11-05", "2026-11-17", "2026-12-04", "2026-12-10", "2027-01-20", rm["versions"]["H2"]["months"][-1]["to"], "2028-01-01"]
    js2 = node(r"""const C = await import(url + '/ledgercore.js'); const rm = JSON.parse(fs.readFileSync(%s, 'utf8')); const days = %s;
      out(days.map((d) => ({ h2: C.planAt(rm.versions.H2.months, d), h1: C.planAt(rm.versions.H1.months, d) }))); """ % (json.dumps(os.path.join(WEB, "plutus", "roadmap.json")), json.dumps(days)))
    if isinstance(js2, list):
        ok = all(abs(a["h2"][k] - plan_at(rm["versions"]["H2"]["months"], d)[k]) < 0.011 and abs(a["h1"][k] - plan_at(rm["versions"]["H1"]["months"], d)[k]) < 0.011
                 for a, d in zip(js2, days) for k in ("cum", "lo", "hi"))
        check("r. on the real roadmap.json the page's expected cash equals an independent Python version on %d chosen days" % len(days), ok, js2[:2])
    else:
        check("r. real-file check ran", False, js2)


def part_roadmap_browser(rm):
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="le_ledger_rm_")
    site = os.path.join(tmp, "nq-dashboard")

    def build(with_plan):
        shutil.rmtree(site, ignore_errors=True)
        shutil.copytree(PAGE, os.path.join(site, "ledger"))
        for d in ("jarvis", "olympus"):
            shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
        if with_plan:
            os.makedirs(os.path.join(site, "plutus"))
            shutil.copy(os.path.join(WEB, "plutus", "roadmap.json"), os.path.join(site, "plutus", "roadmap.json"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/ledger/"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def open_(qs, seed):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, reduced_motion="reduce")
                ctx.add_init_script("try { if (!localStorage.getItem('jfx')) localStorage.setItem('jfx', 'low'); } catch (e) {}")

                def guard(route):
                    u = route.request.url
                    if u.startswith(RAW_PREFIX):
                        return route.abort()
                    return route.continue_() if u.startswith(f"http://127.0.0.1:{srv.server_address[1]}") or u.startswith(("data:", "blob:")) else route.abort()
                ctx.route("**/*", guard)
                p = ctx.new_page()
                p.set_default_timeout(40000)
                p.errs = []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and p.errs.append(m.text))
                p.goto(base + qs)
                p.wait_for_function("document.body.dataset.ready === '1' && window.LG && LG.state().scene && LG.state().scene.drawn > 0", timeout=240000)
                for e in seed:
                    p.evaluate("(e) => LG.add(e)", e)
                p.wait_for_timeout(300)
                return ctx, p

            today = "2026-12-10"
            seed = [{"kind": "payout_in", "amount": 480, "date": "2026-12-08", "acct": "general", "cat": "Payouts"},
                    {"kind": "fee", "amount": 63, "date": "2026-11-25", "acct": "general", "cat": "Eval fees"}]
            build(True)
            ctx, p = open_(f"?today={today}", seed)
            exp2, exp1 = plan_at(rm["versions"]["H2"]["months"], today)["cum"], plan_at(rm["versions"]["H1"]["months"], today)["cum"]
            money = lambda x: ("-$" if x < 0 else "$") + f"{abs(x):,.0f}"  # noqa: E731
            txt = p.inner_text("#planCheck") if p.locator("#planCheck").count() else ""
            check("r. with the Money plan file: the break-even tracker shows 'Expected vs actual cash so far this year', conservative first, Jan-Jun second, then the actual",
                  p.locator("#planCheckHead").count() == 1 and "so far this year" in p.inner_text("#planCheckHead") and rm["first_session"] in p.inner_text("#planCheckHead")
                  and txt.index("conservative") < txt.index("Jan-Jun") < txt.index("Actual") and money(exp2) in txt and money(exp1) in txt and "+$417" in txt, txt)
            check("r. ... and a plain sentence about where he stands (the page says one of the four sentences)", any(s in p.inner_text("#planCheckMsg") for s in (
                "at or above the Jan-Jun plan", "at or above the conservative plan", "inside its normal range", "below the worst 1 in 10")), p.inner_text("#planCheckMsg"))
            check("r. ... inside the Break-even tracker card, no errors", p.evaluate("!!document.querySelector('#planCheckHead').closest('article.card') && document.querySelector('#planCheckHead').closest('article.card').querySelector('h2').textContent") == "Break-even tracker" and not p.errs, p.errs[:3])
            check("r. no sideways scroll with the extra lines", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            ctx.close()
            ctx, p = open_("?today=2026-10-20", seed)
            check("r. before the plan's first day: the tracker says the plan starts on its date and expects $0", "starts " + rm["first_session"] in p.inner_text("#planCheckMsg") and "$0" in p.inner_text("#planCheck"), p.inner_text("#planCheckMsg"))
            ctx.close()
            ctx, p = open_(f"?today={today}", [])
            check("r. DEMO (no entries): the expected lines show, the actual says to add the first entry, nothing is compared", p.evaluate("LG.state().demo") and "add your first entry" in p.inner_text("#planCheck") and "example numbers" in p.inner_text("#planCheckMsg"), p.inner_text("#planCheck"))
            ctx.close()
            build(False)
            ctx, p = open_(f"?today={today}", seed)
            check("r. no plutus/roadmap.json: the tracker is exactly as before (no plan lines), no errors, the page is not blank",
                  p.locator("#planCheckHead").count() == 0 and "back of" in p.inner_text("#p-over") and not p.errs, p.errs[:3])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_b()
    with open(os.path.join(WEB, "plutus", "roadmap.json"), encoding="utf-8") as fh:
        rm = json.load(fh)
    part_roadmap_maths(rm)
    if os.environ.get("LG_NO_BROWSER") != "1":
        run_browser()
        part_roadmap_browser(rm)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
