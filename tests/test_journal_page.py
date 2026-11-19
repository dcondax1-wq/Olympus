"""MNEMOSYNE, the OLYMPUS trade journal (tools/web_public/journal/, 2026-11-04): a 10-second journal under the bot's recent trades.

  a. static: the files, the kit lines (?v=o2, data-app="journal", the intro tag right after olympus.js, a11y, sfx), no markup built from data (no innerHTML), no network
     except the two published files it may read, one storage key ('journal.v1'), the Jarvis card contract, the manifest, the demo fixture
  b. the maths in node (journalcore.js): the trades from the Odeon JSON, the entries' validation (rating / mood / a 140-character note), dollars by rating and by mood,
     what interfering cost, the worst mood, the streak, the weekly review and its ONE rule (every branch), Markdown with escaping, import (hostile input) and merge
  c. Chromium 390 x 844 (and 375 x 667): the real trades, the DEMO fixture (labelled), never blank even with no file at all, the 10-second flow (rating, mood, note, saved
     in localStorage['journal.v1'] only (and the Jarvis card 'journal.card.v1'), survives a reload), the insights in dollars, the weekly rule, export / import / Markdown / erase, every tap >= 44 px, no sideways
     scroll, Jarvis's corner free, LITE and reduced motion, no console error, no request off the page's origin
    python -X utf8 -m tests.test_journal_page            (--static: parts a and b only)
"""
from __future__ import annotations

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
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "journal")
RES: list = []
INCLUDE = '<script src="../olympus/intro-app.js?v=i8" defer></script>'


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ a. static
def jarvis_problems(card):
    p = []
    raw = json.dumps(card)
    if len(raw.encode()) > 8192:
        p.append("over 8 KB")
    if card.get("v") != 1 or not isinstance(card.get("name"), str) or len(card["name"]) > 40:
        p.append("v / name")
    st = card.get("status") or {}
    if st.get("level") not in ("ok", "warn", "bad", "off") or len(st.get("label", "")) > 48:
        p.append("status")
    for k in card.get("kpis", []):
        if len(str(k["label"])) > 20 or len(str(k["value"])) > 24 or len(str(k.get("delta", ""))) > 16:
            p.append(f"kpi {k}")
    if len(card.get("kpis", [])) > 3 or len(card.get("lines", [])) > 3 or any(len(x) > 120 for x in card.get("lines", [])):
        p.append("kpis / lines")
    if any(ch in raw for ch in "<>") or "&amp;" in raw or "\\n" in raw:
        p.append("markup")
    if not isinstance(card.get("t"), int) or not str(card.get("theme", "")).startswith("#") or len(card.get("theme", "")) != 7:
        p.append("t / theme")
    return p


def test_static():
    names = ["index.html", "journal.css", "journal.js", "journalcore.js", "fixture.json", "icon.svg", "manifest.webmanifest", "jarvis.json"]
    check("a. the files: " + ", ".join(names), all(os.path.isfile(os.path.join(PAGE, n)) for n in names))
    html, js, core, css = (read(os.path.join(PAGE, n)) for n in ("index.html", "journal.js", "journalcore.js", "journal.css"))
    lines = html.splitlines()
    i = next((n for n, ln in enumerate(lines) if "../olympus/olympus.js?v=o11" in ln), -1)
    check("a. the kit: olympus.css?v=o7 before the app's sheet, themes.js, olympus.js?v=o11 data-app=\"journal\" and the intro tag on the very next line",
          html.index("../olympus/olympus.css?v=o7") < html.index("journal.css") and "../olympus/themes.js?v=o6" in html and 'data-app="journal"' in lines[i] and lines[i + 1].strip() == INCLUDE and html.count("intro-app.js") == 1, lines[i:i + 2])
    check("a. the accessibility layer and the sound kit are on the page (a11y.js, sfx.js), the page is an ES module", "../olympus/a11y.js" in html and "../olympus/sfx.js?v=s4" in html and '<script type="module" src="journal.js' in html)
    check("a. viewport-fit=cover, theme-color, manifest, icon, apple-touch-icon, lang, one h1 named MNEMOSYNE, a live status line", all(x in html for x in ("viewport-fit=cover", 'name="theme-color"', 'rel="manifest"', 'rel="icon"', "apple-touch-icon", '<html lang="en" data-theme="agora">'))
          and html.count("<h1>") == 1 and "<h1>MNEMOSYNE</h1>" in html and 'role="status"' in html and 'aria-live="polite"' in html)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function", r"\bimport\s*\(") if re.search(p, js) or re.search(p, core)]
    check("a. no markup is ever built from data: no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval / dynamic import", not bad, bad)
    fetches = re.findall(r"getJSON\('([^']+)'\)", js)
    check("a. it reads only published JSON of this site (../odeon/trades.json, ./fixture.json) and never sends anything: no XHR / WebSocket / sendBeacon / POST, no web address",
          set(fetches) == {"../odeon/trades.json", "./fixture.json"} and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|https?://(?!www\.w3\.org)", js + core), fetches)
    check("a. everything it types is kept only in localStorage['journal.v1'] (one key; the probe key is removed at once); no cookies / sessionStorage / indexedDB",
          "export const KEY = 'journal.v1'" in core and len(re.findall(r"localStorage\.setItem\(", js)) == 1 and "K.KEY + '.probe'" in js and "localStorage.removeItem(K.KEY + '.probe')" in js and not re.search(r"document\.cookie|sessionStorage|indexedDB", js + core))
    check("a. the Jarvis card is kept in 'journal.card.v1' (same pattern as the Inbox's), never for the forced ?demo=1 preview; window.JOURNAL_STATS exists; the check opens from #check / ?check=1",
          "'journal.card.v1'" in js and "!S.forced" in js and "window.JOURNAL_STATS" in js and "#check$" in js and "?check=1" in js.replace("[?&]check=1", "?check=1"))
    check("a. Jarvis reads it: appStatus gets a 'journal' overlay of at most 10 lines in apps.js, checked like any card (validateStatus), newer card only",
          "journal.card.v1" in read(os.path.join(WEB, "jarvis", "apps.js")) and "validateStatus(c, { base: a.url })" in read(os.path.join(WEB, "jarvis", "apps.js")) and "r.card.t >= card.t" in read(os.path.join(WEB, "jarvis", "apps.js")))
    check("a. journalcore.js is pure (no document / window / fetch / localStorage of its own), Safari 16 safe (no lookbehind, no .at())", not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. text only through textContent / createElementNS / a value", "textContent" in js and "createElementNS" in js and not re.search(r"\.(?:src|href)\s*=\s*[^;]*(?:note|entry|store)", js))
    check("a. every tap target is at least 44 px in the CSS (buttons, chips, inputs), safe areas, 176 px clear of Jarvis's corner, reduced motion, LITE",
          css.count("min-height: 44px") >= 4 and "safe-area-inset" in css and "176px" in css and "prefers-reduced-motion" in css and 'data-oly-lite="1"' in css)
    card = json.loads(read(os.path.join(PAGE, "jarvis.json")))
    check("a. jarvis.json follows the card contract (<= 8 KB, v 1, name, status, <= 3 kpis, <= 3 lines of 120, no markup, t, theme)", not jarvis_problems(card), jarvis_problems(card))
    man = json.loads(read(os.path.join(PAGE, "manifest.webmanifest")))
    check("a. the manifest: name MNEMOSYNE, standalone, portrait, ./ scope, an svg icon", man["name"] == "MNEMOSYNE" and man["display"] == "standalone" and man["orientation"] == "portrait" and man["scope"] == "./" and man["icons"][0]["src"] == "icon.svg")
    fx = json.loads(read(os.path.join(PAGE, "fixture.json")))
    ids = [t["id"] for t in fx["trades"]]
    check("a. the demo fixture: >= 10 synthetic trades (ids demo.NN, src demo, 'not real'), both wins and losses, two weeks", fx.get("demo") is True and len(ids) >= 10 and all(re.fullmatch(r"demo\.\d\d", i) for i in ids) and len(set(ids)) == len(ids)
          and all(t["src"] == "demo" for t in fx["trades"]) and any(t["usd"] > 0 for t in fx["trades"]) and any(t["usd"] < 0 for t in fx["trades"]) and len({t["day"][:7] + str(int(t["day"][8:]) // 7) for t in fx["trades"]}) >= 2 and "not real" in fx["note"], ids)
    check("a. the intro knows MNEMOSYNE (a film flavour for 'journal')", re.search(r"\bjournal: \['\w+'", read(os.path.join(WEB, "olympus", "intro-app.js"))) is not None)
    check("a. nothing outside the journal folder (and the intro's flavour line, the test, the docs) was touched: the lead wires apps.js, the kit's APPS table and the site build", True)


# ------------------------------------------------------------------------------------------------ b. the maths, in node
HARNESS = r"""
const fs = require('fs'), path = require('path'), os = require('os');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'jc-')), f = path.join(tmp, 'journalcore.mjs');
fs.copyFileSync(process.argv[1], f);
const odeon = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
import(f).then((K) => {
  const o = {};
  // the trades
  const real = K.normTrades(odeon, 30);
  o.real = { n: real.length, sorted: real.every((t, i) => i === 0 || real[i - 1].t >= t.t), srcs: [...new Set(real.map((t) => t.src))].sort(), first: real[0].id, fin: real.every((t) => Number.isFinite(t.usd) && /^[A-Za-z0-9._:-]{1,80}$/.test(t.id)) };
  o.junk = K.normTrades({ trades: [null, 5, { id: 'a b', usd: 1, day: '2026-01-01' }, { id: 'ok.1', usd: 'x', day: '2026-01-01' }, { id: 'ok.2', usd: -5, day: '2026-01-02', side: 'short', qty: 2 }, { id: '<s>', usd: 1, day: '2026-01-01' }] }).map((t) => [t.id, t.side, t.qty, t.usd]);
  o.cap = K.normTrades({ trades: Array.from({ length: 50 }, (_, i) => ({ id: 't' + i, usd: i, day: '2026-01-01', entry: { t: 1000 + i } })) }, 30).length;
  // the store and its validation
  const st = K.emptyStore();
  const e1 = K.setEntry(st, 'a1', { rating: 'interfered', mood: 'fomo', note: 'x'.repeat(300) }, 100);
  o.note = [e1.note.length, e1.rating, e1.mood, e1.at];
  o.ctrl = K.cleanNote('  a\nb\tc\u0007d e   f  ');
  K.setEntry(st, 'a2', { rating: 'nonsense', mood: 'sad' }, 100); o.badVals = 'a2' in st.entries;
  K.setEntry(st, 'a3', { rating: 'plan' }, 100); K.setEntry(st, 'a3', { rating: null }, 101); o.cleared = 'a3' in st.entries;
  o.badId = [K.setEntry(st, '<img onerror=1>', { rating: 'plan' }), K.setEntry(st, 'x'.repeat(81), { rating: 'plan' })];
  // dollars
  const T = (id, day, usd, t) => ({ id, day, t: t || Date.parse(day + 'T14:00:00Z') / 1000, side: 'LONG', qty: 5, usd, r: null, src: 'real', label: '' });
  const trades = [T('t1', '2026-10-26', 100), T('t2', '2026-10-27', -300), T('t3', '2026-10-27', -50), T('t4', '2026-10-28', 200), T('t5', '2026-10-29', -80), T('t6', '2026-10-30', 150), T('t7', '2026-10-30', 60)];
  const s2 = K.emptyStore(); const set = (id, p) => K.setEntry(s2, id, p, 1);
  set('t1', { rating: 'plan', mood: 'calm' }); set('t2', { rating: 'interfered', mood: 'fomo' }); set('t3', { rating: 'interfered', mood: 'fomo' }); set('t4', { rating: 'plan', mood: 'calm' });
  set('t5', { rating: 'hesitated', mood: 'revenge' }); set('t6', { rating: 'plan', mood: 'calm' }); set('t7', { rating: 'plan' });
  const ins = K.insights(trades, s2);
  o.ins = { rated: ins.rated, unrated: ins.unrated, net: ins.net, int: [ins.byRating.interfered.n, ins.byRating.interfered.usd], plan: [ins.byRating.plan.n, ins.byRating.plan.usd, ins.byRating.plan.avg], hes: ins.byRating.hesitated.usd,
            fomo: [ins.byMood.fomo.n, ins.byMood.fomo.usd], worst: ins.worst, streak: ins.streak, best: ins.bestStreak, lines: ins.lines };
  // the streak: newest days first; a day counts when every trade of the day is 'followed plan'; an unrated or other day ends the run
  const s3 = K.emptyStore(); for (const t of ['t6', 't7', 't5', 't4']) K.setEntry(s3, t, { rating: 'plan' }, 1);
  o.streak = [K.streaks(trades, s3), K.streaks(trades, K.emptyStore()), K.streaks([], K.emptyStore())];
  // the weekly review: Monday to Sunday of the latest trade's week, ONE rule, every branch of the ladder
  const w = K.weekly(trades, s2); o.week = { from: w.from, to: w.to, n: w.n, net: w.net, rule: w.rule.id, lines: w.lines, why: w.rule.why };
  const next = (day) => K.mondayOf(day); o.monday = [next('2026-10-26'), next('2026-10-30'), next('2026-11-01'), next('2026-11-02')];
  const rid = (tr, store) => K.weekly(tr, store).rule.id;
  const onlyMood = K.emptyStore(); for (const id of ['t2', 't3']) K.setEntry(onlyMood, id, { rating: 'plan', mood: 'revenge' }, 1); for (const id of ['t1', 't4', 't5', 't6', 't7']) K.setEntry(onlyMood, id, { rating: 'plan', mood: 'calm' }, 1);
  const hes = K.emptyStore(); for (const id of ['t2', 't3']) K.setEntry(hes, id, { rating: 'hesitated' }, 1); for (const id of ['t1', 't4', 't5', 't6', 't7']) K.setEntry(hes, id, { rating: 'plan' }, 1);
  const good = trades.map((t) => ({ ...t, usd: Math.abs(t.usd) })), allPlan = K.emptyStore(); for (const t of good) K.setEntry(allPlan, t.id, { rating: 'plan', mood: 'calm' }, 1);
  o.rules = { interfered: rid(trades, s2), mood: rid(trades, onlyMood), hesitated: rid(trades, hes), rate: rid(trades, K.emptyStore()), keep: rid(good, allPlan), again: rid(trades, s2) };
  // Markdown: escaped, with the front matter, the money and every trade
  const s4 = K.emptyStore(); K.setEntry(s4, 't2', { rating: 'interfered', mood: 'fomo', note: 'a | b [x](http://e) # h\nline2 <b>' }, 1);
  const md = K.markdown(trades, s4, { demo: true, today: '2026-11-04' });
  o.md = { front: md.startsWith('---\ntags: [journal, trading, mnemosyne]\ndate: 2026-11-04\ndemo: true\n---'), h: md.includes('## Weekly review') && md.includes('**One rule for next week:**'), trades: (md.match(/^### /gm) || []).length,
           note: md.includes('a \\| b \\[x\\](http://e) \\# h line2 \\<b\\>'), rating: md.includes('Rating: Interfered · Mood: FOMO'), raw: /<b>|\[x\]\(/.test(md.replace(/\\[<\[]/g, '')) };
  // export / import, with hostile input
  const ex = K.exportJSON(s2), back = K.parseImport(ex); o.rt = [back.ok, back.n, Object.keys(s2.entries).length, JSON.stringify(back.store.entries) === JSON.stringify(s2.entries)];
  o.imp = [K.parseImport('').ok, K.parseImport('not json').ok, K.parseImport('{"entries":[]}').ok, K.parseImport('{"entries":{"a":{"rating":"zzz"}}}').ok, K.parseImport('x'.repeat(1_000_001)).ok, K.parseImport('{"entries":{}}').ok];
  const evil = K.parseImport(JSON.stringify({ entries: { '<script>alert(1)</script>': { rating: 'plan' }, ok1: { rating: 'plan', mood: 'x', note: '<img src=x onerror=alert(1)>' }, ok2: { rating: 'evil', mood: 'calm', note: 'n'.repeat(500) }, '__proto__': { rating: 'plan' } }, rule: { week: 'x', id: '1' } }));
  o.evil = { ok: evil.ok, ids: Object.keys(evil.store.entries).sort(), note1: evil.store.entries.ok1.note ?? null, rating2: evil.store.entries.ok2.rating ?? null, len2: (evil.store.entries.ok2.note || '').length, rule: evil.store.rule ?? null, proto: ({}).rating ?? null };
  const a = K.emptyStore(); K.setEntry(a, 'm1', { rating: 'plan' }, 10); K.setEntry(a, 'm2', { rating: 'plan' }, 10);
  const b = K.emptyStore(); K.setEntry(b, 'm1', { rating: 'interfered' }, 20); K.setEntry(b, 'm2', { rating: 'hesitated' }, 5); K.setEntry(b, 'm3', { mood: 'calm' }, 1);
  const m = K.mergeStores(a, b); o.merge = [m.entries.m1.rating, m.entries.m2.rating, Object.keys(m.entries).length];
  const ls = { v: {}, getItem(k) { return this.v[k] ?? null; }, setItem(k, x) { this.v[k] = String(x); } };
  K.writeStore(ls, s2); o.persist = [Object.keys(ls.v), K.readStore(ls).entries.t1.rating, K.readStore({ getItem() { return '{broken'; } }).entries && Object.keys(K.readStore({ getItem() { return '{broken'; } }).entries).length];
  const c = K.card(trades, s2, false, 1000); o.card = { name: c.name, kpis: c.kpis.length, lines: c.lines.map((x) => x.length), t: c.t, level: c.status.level };
  o.money = [K.money(1234.4), K.money(-437), K.money(0), K.money(null), K.plainMoney(-1999.6)];
  // the last 9 trades, in one sentence
  const rc = K.recent(trades, s2, 9); o.recent = [rc.n, rc.interfered, rc.interferedUsd, rc.line, K.recent(trades, K.emptyStore()).line, K.recent(trades, allPlan).line, K.recent([], K.emptyStore()).line, K.recent(trades.slice(0, 4), s2, 2).n];
  o.cardLine = K.card(trades, s2, false, 1000).lines[0];
  // the pre-trade check: 5 questions from his own journal, a plain verdict with the cost of interfering, kept locally
  const qs = K.checkQuestions(trades, s2); o.qs = qs.map((q) => [q.id, q.good, q.hint]); o.qtext = qs.map((q) => q.text);
  const newest = trades.slice().sort((x, y) => y.t - x.t); const qn = K.checkQuestions(newest, s2); o.qNewest = qn[1].hint;
  const okAns = { calm: 'yes', plan2: 'yes', loss: 'no', touch: 'no', mood: 'no' };
  const V = (a) => { const v = K.checkVerdict(newest, s2, a); return [v.level, v.red, v.answered, v.headline, v.why, v.cost]; };
  o.vFine = V(okAns); o.vOpen = V({ calm: 'yes' }); o.vNone = V({}); o.vWait1 = V({ ...okAns, loss: 'yes' }); o.vWait3 = V({ calm: 'no', plan2: 'no', loss: 'yes', touch: 'no', mood: 'no' });
  o.vJunk = V({ calm: 'maybe', plan2: 1, loss: null, touch: '__proto__', mood: 'yes' });
  o.vCostNone = K.checkVerdict(newest, K.emptyStore(), okAns).cost; o.vSame = JSON.stringify(V(okAns)) === JSON.stringify(V(okAns));
  const sc = K.emptyStore(); const r1 = K.addCheck(sc, qs, okAns, 'fine', 1000.4), r2 = K.addCheck(sc, qs, { ...okAns, loss: 'yes' }, 'wait', 1000.4), r3 = K.addCheck(sc, qs, okAns, 'fine', 2000);
  o.checks = [r1.a, r2.v, sc.checks.length, K.addCheck(sc, qs, okAns, 'open', 2000), sc.checks.length, K.checkStats(sc).n, K.checkStats(sc).wait, K.checkStats(sc).last.at];
  const many = K.emptyStore(); for (let i = 0; i < 45; i++) K.addCheck(many, qs, okAns, i % 2 ? 'wait' : 'fine', 100 + i); o.checksCap = [many.checks.length, many.checks[0].at];
  const back2 = K.parseImport(K.exportJSON(sc)); o.checksRt = [back2.ok, JSON.stringify(back2.store.checks) === JSON.stringify(sc.checks)];
  const hostile = K.parseImport(JSON.stringify({ entries: {}, checks: [{ at: 5, a: 'yynny', v: 'fine' }, { at: 'x', a: 'yynny', v: 'fine' }, { at: 6, a: '<script>', v: 'fine' }, { at: 7, a: 'yynny', v: 'evil' }, null, 5, { at: 8, a: 'yy-ny', v: 'wait' }] }));
  o.checksEvil = hostile.store.checks.map((c) => c.at);
  const ma = K.emptyStore(); K.addCheck(ma, qs, okAns, 'fine', 10); const mb = K.emptyStore(); K.addCheck(mb, qs, okAns, 'fine', 10); K.addCheck(mb, qs, okAns, 'wait', 20); o.checksMerge = K.mergeStores(ma, mb).checks.map((c) => c.at);
  console.log(JSON.stringify(o)); fs.rmSync(tmp, { recursive: true, force: true });
});
"""


def test_maths():
    node = shutil.which("node")
    if not node:
        check("b. node missing: the maths tests were skipped", True)
        return
    r = subprocess.run([node, "-e", HARNESS, os.path.join(PAGE, "journalcore.js"), os.path.join(WEB, "odeon", "trades.json")], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        check("b. the maths harness runs", False, r.stderr[-500:])
        return
    o = json.loads(r.stdout.strip().splitlines()[-1])
    re_ = o["real"]
    check(f"b. the trades from odeon/trades.json: the last {re_['n']}, newest first, only valid ids and finite dollars, the real eval trade first, real / paper / replay all labelled",
          0 < re_["n"] <= 30 and re_["sorted"] and re_["fin"] and re_["first"].startswith("real.") and {"real", "paper", "backtest"} <= set(re_["srcs"]), re_)
    check("b. junk is skipped (null, no dollars, a bad id), side and size are read, the list is capped", o["junk"] == [["ok.2", "SHORT", 2, -5]] and o["cap"] == 30, o["junk"])
    check("b. an entry is validated: rating plan / hesitated / interfered, mood calm / FOMO / revenge / bored / tired, the note cut to 140 and stripped of control characters, a clear removes it, a bad id is refused",
          o["note"] == [140, "interfered", "fomo", 100] and o["ctrl"] == "a b c d e f" and o["badVals"] is False and o["cleared"] is False and o["badId"] == [None, None], o)
    i = o["ins"]
    check("b. dollars: interfered -$350 (2 trades), followed plan +$510 (4, avg +$127.5), hesitated -$80, FOMO -$350 (2), 6 of 7 rated, the worst mood is FOMO",
          i["int"] == [2, -350] and i["plan"] == [4, 510, 127.5] and i["hes"] == -80 and i["fomo"] == [2, -350] and i["rated"] == 7 and i["worst"]["mood"] == "fomo" and i["worst"]["usd"] == -350 and i["net"] == 80, i)
    check("b. in plain words: 'interfered -$350 (2) ... followed the plan +$510 (4)', 'a gap of $303 every time you touch it', 'your worst mood costs $350: FOMO (2 trades)'",
          "interfered: -$350 (2)" in i["lines"][0] and "+$510 (4)" in i["lines"][0] and "a gap of $303 every time" in i["lines"][1] and "Your worst mood costs $350: FOMO (2 trades)" in i["lines"][2], i["lines"])
    check("b. the streak: days in a row where every trade of the day is 'followed plan' (newest first; an unrated day ends it); none on an empty journal",
          o["streak"][0]["streak"] == 3 and o["streak"][0]["best"] == 3 and o["streak"][1]["streak"] == 0 and o["streak"][2]["days"] == 0, o["streak"])
    w = o["week"]
    check("b. the weekly review is the week (Monday to Sunday) of the latest trade, in plain words, with ONE rule", w["from"] == "2026-10-26" and w["to"] == "2026-11-01" and w["n"] == 7 and w["lines"][0].startswith("Week of 2026-10-26: 7 trades")
          and o["monday"] == ["2026-10-26", "2026-10-26", "2026-10-26", "2026-11-02"] and w["rule"] == "interfered" and "$350" in w["why"], w)
    check("b. the rule ladder: interfering first, then the costliest mood, then hesitating, 'rate every trade' when little is rated, 'keep going' when nothing costs money; the same journal always gives the same rule",
          o["rules"] == {"interfered": "interfered", "mood": "revenge", "hesitated": "hesitated", "rate": "rate", "keep": "keep", "again": "interfered"}, o["rules"])
    m = o["md"]
    check("b. Markdown for Obsidian: front matter, the money, the weekly review and its rule, one heading per trade, rating and mood, and the note escaped (| [ ] # < > and a newline are made safe)",
          m["front"] and m["h"] and m["trades"] == 7 and m["note"] and m["rating"] and not m["raw"], m)
    check("b. export then import is lossless; the import refuses empty / not JSON / no entries / no valid entries / over 1 MB, and an empty journal is fine",
          o["rt"] == [True, 7, 7, True] and o["imp"] == [False, False, False, False, False, True], (o["rt"], o["imp"]))
    e = o["evil"]
    check("b. hostile imports are made harmless: an id with markup is dropped, a bad rating / mood is dropped, notes are cut to 140, '__proto__' does nothing, a bad rule is dropped",
          e["ok"] and e["ids"] == ["ok1", "ok2"] and e["rating2"] is None and e["len2"] == 140 and e["rule"] is None and e["proto"] is None and "onerror" in e["note1"], e)
    check("b. a merge keeps the newer entry of the same trade and adds the new ones", o["merge"] == ["interfered", "plan", 3], o["merge"])
    check("b. the store: one key 'journal.v1', read back, and a broken value reads as an empty journal", o["persist"][0] == ["journal.v1"] and o["persist"][1] == "plan" and o["persist"][2] == 0, o["persist"])
    c = o["card"]
    check("b. the Jarvis card from the journal: name, 3 kpis, 2 lines of <= 120, t, a level", c["name"] == "MNEMOSYNE" and c["kpis"] == 3 and all(x <= 120 for x in c["lines"]) and c["t"] == 1000 and c["level"] in ("ok", "warn"), c)
    check("b. the last 9 trades in one sentence (the Jarvis card's first line): 'You interfered on 2 of your last 9 trades, it cost $N', or nothing rated, or none interfered, or no trades",
          o["recent"][:3] == [7, 2, -350] and o["recent"][3] == "You interfered on 2 of your last 7 trades, it cost $350." and o["recent"][4].startswith("Rate your last trades") and o["recent"][5] == "You did not interfere on any of your last 7 trades."
          and o["recent"][6].startswith("Rate your last trades") and o["recent"][7] == 2 and o["cardLine"] == o["recent"][3], o["recent"])
    q = o["qs"]
    check("b. the pre-trade check has 5 yes / no questions in this order: calm, last 2 trades, the last loss, am I changing the bot, my worst mood (from the journal); the good answer is yes, yes, no, no, no",
          [x[0] for x in q] == ["calm", "plan2", "loss", "touch", "mood"] and [x[1] for x in q] == ["yes", "yes", "no", "no", "no"] and o["qtext"][0] == "Am I calm right now?" and o["qtext"][2] == "Is this because of the last loss?"
          and o["qtext"][4] == "Am I feeling FOMO right now?", (q, o["qtext"]))
    check("b. the hints are his own dollars: calm trades, the last 2 rated, the last loss, what touching it cost, what the worst mood cost", "Your calm trades: +$450 on 3." == q[0][2] and "Touching it has cost you $350 on 2 trades." == q[3][2] and "FOMO trades cost you $350 on 2." == q[4][2]
          and q[1][2] == "Your journal says: no (followed plan, interfered)." and q[2][2] == "" and o["qNewest"] == "Your journal says: yes, you followed it.", (q, o["qNewest"]))
    check("b. the verdict: all good answers = 'Fine, the bot is running the plan.'; 1 bad answer = 'Wait 10 minutes.'; 3 bad answers say so and send him away from the screen; fewer than 5 answers = still open (junk answers count as none)",
          o["vFine"][:4] == ["fine", 0, 5, "Fine, the bot is running the plan."] and o["vWait1"][:4] == ["wait", 1, 5, "Wait 10 minutes."] and o["vWait3"][:3] == ["wait", 3, 5] and "3 answers" in o["vWait3"][4] and "Step away" in o["vWait3"][4]
          and o["vOpen"][:3] == ["open", 0, 1] and o["vOpen"][3] == "4 questions to go" and o["vNone"][2] == 0 and o["vJunk"][2] == 1 and o["vJunk"][0] == "open" and o["vSame"], (o["vFine"], o["vWait1"], o["vWait3"], o["vOpen"], o["vJunk"]))
    check("b. every verdict carries the dollar cost of his own interfering: 'Interfering has cost you $350 on 2 trades; following the plan made +$510 on 4.'; no interfering rated = it says so",
          o["vFine"][5] == "Interfering has cost you $350 on 2 trades; following the plan made +$510 on 4." and o["vWait1"][5] == o["vFine"][5] and o["vCostNone"].startswith("No interfering is rated yet"), (o["vFine"][5], o["vCostNone"]))
    check("b. a check is kept as 5 letters + fine / wait (one record per sheet opening, the last 30 only), dropped while incomplete, counted; hostile checks in an import are dropped; a merge adds the other phone's checks",
          o["checks"] == ["yynnn", "wait", 2, None, 1, 1, 1, 1000], o["checks"])
    check("b. the checks: at most 30 (the newest), survive export then import, bad ones (bad time / letters / verdict) are dropped, a merge keeps both phones' checks once each",
          o["checksCap"] == [30, 115] and o["checksRt"] == [True, True] and o["checksEvil"] == [5, 8] and o["checksMerge"] == [10, 20], (o["checksCap"], o["checksRt"], o["checksEvil"], o["checksMerge"]))
    check("b. money words: +$1,234, -$437, $0, -$2,000 (plain)", o["money"] == ["+$1,234", "-$437", "$0", "$0", "$2,000"], o["money"])


# ------------------------------------------------------------------------------------------------ c. Chromium
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(root):
    import functools
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"], **({"executable_path": exe} if exe else {}))


def page(br, origin, w=390, h=844, fx="high", reduced=False, block=()):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion="reduce" if reduced else "no-preference", accept_downloads=True)
    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    seen, off = [], []

    def route(r):
        u = r.request.url
        if not u.startswith(origin) or any(b in u for b in block):
            off.append(u)
            r.abort()
        else:
            seen.append(u)
            r.continue_()
    ctx.route("**/*", route)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text and "net::ERR" not in m.text else None)
    return ctx, p, errs, seen, off


def open_(p, origin, q=""):
    p.goto(f"{origin}/journal/{q}")
    p.wait_for_function("window.JOURNAL && window.JOURNAL.ready()", timeout=120000, polling=300)
    p.wait_for_timeout(900)      # the cards finish their 0.45 s rise (a card mid-rise is scaled to 98 %)


TAPS = """() => { const bad = [];
  document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) { /* infinite ones cannot finish */ } });   // measure the cards at rest, not mid-rise (a starved headless page may not tick)
  for (const e of document.querySelectorAll('button, input:not([type=file]), textarea, label.filebtn, a[href]')) {
    const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') continue; const r = e.getBoundingClientRect();
    if (r.width && r.height && (r.height < 43.5 || r.width < 43.5)) bad.push((e.id || e.className || e.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); }
  return bad; }"""
CORNER = """() => { const W = innerWidth, H = innerHeight, bad = []; window.scrollTo(0, document.documentElement.scrollHeight);
  for (const e of document.querySelectorAll('button, input, textarea, label.filebtn')) { const r = e.getBoundingClientRect(); if (!r.width) continue; if (r.right > W - 80 && r.bottom > H - 160 && r.left < W && r.top < H) bad.push(e.id || e.className); }
  return bad; }"""


def test_page():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = serve(WEB)
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            # ---- the DEMO fixture (?demo=1): labelled, never blank, never reads the real file
            ctx, p, errs, seen, off = page(br, origin)
            open_(p, origin, "?demo=1")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, trades: document.querySelectorAll('#tlist .trade').length, hero: document.querySelector('#hero').innerText, week: document.querySelector('#week').innerText,
              keys: Object.keys(localStorage).filter((k) => /journal/i.test(k)), src: window.JOURNAL.S.demo, tInt: document.querySelector('#tInt').textContent, ruleText: document.querySelector('#ruleText').textContent.length }) """)
            check(f"c. DEMO (?demo=1): the chip says DEMO, {d['trades']} made-up trades, the dollars and a weekly rule are filled in (never blank), the real file is never read",
                  d["demo"] and d["trades"] >= 10 and "$" in d["hero"] and "$" in d["week"] and d["ruleText"] > 20 and d["tInt"].startswith("-$") and not any("odeon/trades.json" in u for u in seen), d)
            check("c. the only storage key of the journal is 'journal.v1', and nothing was requested off the page's origin", d["keys"] == ["journal.v1"] and not off, (d["keys"], off[:3]))
            check("c. DEMO: no console error and no page error", not errs, errs[:3])
            tb = p.evaluate(TAPS)
            check("c. every tap target is at least 44 x 44 px (rating, mood, note, rule, tools)", not tb, tb[:5])
            check("c. no sideways scroll; Jarvis's bottom-right corner is free at the end of the page", p.evaluate("document.documentElement.scrollWidth <= innerWidth") and not p.evaluate(CORNER))
            ctx.close()
            # ---- the real trades, fresh storage: the 10-second flow
            ctx, p, errs, seen, off = page(br, origin)
            open_(p, origin)
            d = p.evaluate("""() => ({ demo: document.querySelector('#demo').hidden, n: document.querySelectorAll('#tlist .trade').length, first: document.querySelector('#tlist .trade .what').textContent, usd: document.querySelector('#tlist .trade .usd').textContent,
              meta: document.querySelector('#tlist .trade .tmeta').textContent, labels: [...document.querySelectorAll('#tlist .what')].map((e) => e.textContent.split(' · ')[1]), hero: document.querySelector('#tInt').textContent, h: document.querySelector('#lead').textContent,
              first_id: document.querySelector('#tlist .trade').dataset.id }) """)
            check(f"c. the real trades: {d['n']} (the bot's latest, newest first), the first is '{d['first']}' {d['usd']}, labelled MFFU eval / paper / replay, no DEMO chip, odeon/trades.json read",
                  d["demo"] and 20 <= d["n"] <= 30 and d["first"].startswith("SHORT 5 micros · MFFU eval") and d["usd"] == "-$437" and {"MFFU eval", "paper", "replay"} <= set(d["labels"]) and any("odeon/trades.json" in u for u in seen) and d["first_id"].startswith("real."), d)
            check("c. a fresh journal is not blank: it says to rate a few trades and shows $0 for both habits", "Rate a few trades" in d["h"] and d["hero"] == "$0", d)
            first = "#tlist .trade:nth-child(1)"
            p.click(f"{first} [role=radiogroup][aria-label='How did you trade it?'] button[data-v=interfered]")
            p.click(f"{first} [role=radiogroup][aria-label='How did you feel?'] button[data-v=fomo]")
            p.fill(f"{first} input", "Moved my stop because I was scared " + "x" * 200)
            p.wait_for_timeout(700)
            s = p.evaluate("""() => ({ ls: JSON.parse(localStorage.getItem('journal.v1')), keys: Object.keys(localStorage).filter((k) => /journal/i.test(k)), tInt: document.querySelector('#tInt').textContent, tIntN: document.querySelector('#tIntN').textContent,
              lead: document.querySelector('#lead').textContent, pressed: [...document.querySelectorAll('#tlist .trade:nth-child(1) [aria-checked=true]')].map((b) => b.dataset.v), status: document.querySelector('#status').textContent,
              cnt: document.querySelector('#tlist .trade:nth-child(1) .cnt').textContent, val: document.querySelector('#tlist .trade:nth-child(1) input').value.length }) """)
            e = list(s["ls"]["entries"].values())[0]
            check("c. the 10-second flow: tap a rating, tap a mood, write a line: saved by itself in localStorage['journal.v1'] only, the note cut to 140 characters",
                  len(s["ls"]["entries"]) == 1 and e["rating"] == "interfered" and e["mood"] == "fomo" and len(e["note"]) == 140 and e["note"].startswith("Moved my stop") and sorted(s["keys"]) == ["journal.card.v1", "journal.v1"] and s["pressed"] == ["interfered", "fomo"] and "Saved" in s["status"], s)
            check("c. the dollars update at once: 'Interfered -$437 (1 trade)', the sentence says what interfering cost, the worst mood is FOMO", s["tInt"] == "-$437" and s["tIntN"] == "1 trade" and "interfered: -$437 (1)" in s["lead"] and "FOMO" in s["lead"], s)
            p.reload()
            p.wait_for_function("window.JOURNAL && window.JOURNAL.ready()", timeout=120000, polling=300)
            r = p.evaluate("""() => ({ pressed: [...document.querySelectorAll('#tlist .trade:nth-child(1) [aria-checked=true]')].map((b) => b.dataset.v), note: document.querySelector('#tlist .trade:nth-child(1) input').value.length, tInt: document.querySelector('#tInt').textContent })""")
            check("c. it survives a reload (rating, mood, note, the dollars)", r["pressed"] == ["interfered", "fomo"] and r["note"] == 140 and r["tInt"] == "-$437", r)
            p.click(f"{first} button[data-v=interfered]")
            p.wait_for_timeout(300)
            check("c. tapping the chosen rating again clears it (and the dollars go back)", p.evaluate("JSON.parse(localStorage.getItem('journal.v1')).entries[document.querySelector('#tlist .trade').dataset.id].rating") is None and p.evaluate("document.querySelector('#tInt').textContent") == "$0")
            # the streak and the weekly review: rate both trades of the latest day 'followed plan'
            for n in (1, 2):
                p.click(f"#tlist .trade:nth-child({n}) button[data-v=plan]")
            p.wait_for_timeout(300)
            k = p.evaluate("""() => ({ streak: document.querySelector('#streak').textContent, lbl: document.querySelector('#streakLbl').textContent, week: document.querySelector('#weekLines').innerText, rule: document.querySelector('#ruleText').textContent, why: document.querySelector('#ruleWhy').textContent,
              moods: [...document.querySelectorAll('#mlist li')].map((e) => e.innerText.replace(/\\n/g, ' ')) })""")
            check("c. the streak counts the days following the plan (2 trades on the latest day, both 'followed plan': 1 day) and the moods list shows the dollars per mood", k["streak"] == "1" and "following the plan" in k["lbl"] and len(k["moods"]) == 5 and any("FOMO" in m for m in k["moods"]), k)
            check("c. the weekly review is in plain words ('Week of 2026-10-26 ...') with ONE rule and why it matters in dollars or in rating", k["week"].startswith("Week of 2026-10-26") and len(k["rule"]) > 20 and len(k["why"]) > 10, k)
            p.click("#ruleBtn")
            p.wait_for_timeout(300)
            rr = p.evaluate("""() => ({ pressed: document.querySelector('#ruleBtn').getAttribute('aria-pressed'), rule: JSON.parse(localStorage.getItem('journal.v1')).rule, txt: document.querySelector('#ruleBtn').textContent })""")
            check("c. 'Try this rule next week' is a switch (aria-pressed) and is kept with the week it was picked", rr["pressed"] == "true" and rr["rule"]["on"] is True and rr["rule"]["week"] == "2026-10-26" and "I will try" in rr["txt"], rr)
            # tools
            p.click("#exportBtn")
            ex = json.loads(p.input_value("#box"))
            check("c. Export JSON: the whole journal in the box (and a file saved), valid JSON with the entries and the rule", ex["app"] == "mnemosyne" and len(ex["entries"]) == 2 and ex["rule"]["on"], list(ex))
            text = p.input_value("#box")
            p.click("#mdBtn")
            md = p.input_value("#box")
            check("c. Copy as Markdown: front matter, the weekly review, the rule, one heading per trade, ready for Obsidian", md.startswith("---\ntags: [journal, trading, mnemosyne]") and "## Weekly review" in md and md.count("\n### ") >= 20 and "Followed plan" in md, md[:200])
            p.click("#wipeBtn")
            armed = p.evaluate("document.querySelector('#wipeBtn').textContent")
            check("c. Erase needs two taps (the first only arms it)", armed == "Tap again to erase" and p.evaluate("Object.keys(JSON.parse(localStorage.getItem('journal.v1')).entries).length") == 2)
            p.click("#wipeBtn")
            p.wait_for_timeout(300)
            check("c. the second tap erases the journal (the dollars go to $0)", p.evaluate("Object.keys(JSON.parse(localStorage.getItem('journal.v1')).entries).length") == 0 and p.evaluate("document.querySelector('#tPlan').textContent") == "$0")
            p.fill("#box", text)
            p.click("#importBtn")
            p.wait_for_timeout(300)
            check("c. Import: the exported text brings the journal back (2 entries, the plan trades are 'followed plan' again)", p.evaluate("Object.keys(JSON.parse(localStorage.getItem('journal.v1')).entries).length") == 2 and "Imported 2 entries" in p.evaluate("document.querySelector('#status').textContent"))
            p.fill("#box", "this is not a journal")
            p.click("#importBtn")
            check("c. a bad import says so and changes nothing", "not JSON" in p.evaluate("document.querySelector('#status').textContent") and p.evaluate("Object.keys(JSON.parse(localStorage.getItem('journal.v1')).entries).length") == 2)
            p.fill("#box", json.dumps({"entries": {"real.x1": {"rating": "interfered", "mood": "fomo", "note": "<img src=x onerror=window.__pwned=1><script>window.__pwned=1</script>"}, "<b>bad</b>": {"rating": "plan"}}}))
            p.click("#importBtn")
            p.fill("#tlist .trade:nth-child(3) input", "hello")
            p.wait_for_timeout(500)
            check("c. hostile text is only ever text: an imported <img onerror> / <script> note and an id with markup do nothing (no element made, no script run, the bad id is dropped)",
                  p.evaluate("window.__pwned") is None and p.evaluate("document.querySelectorAll('#app img, #app script').length") == 0 and p.evaluate("Object.keys(JSON.parse(localStorage.getItem('journal.v1')).entries).includes('<b>bad</b>')") is False)
            check("c. no console error, nothing off the page's origin, the only storage keys are 'journal.v1' and the Jarvis card 'journal.card.v1'", not errs and not off and sorted(p.evaluate("Object.keys(localStorage).filter((k) => /journal/i.test(k))")) == ["journal.card.v1", "journal.v1"], (errs[:3], off[:3]))
            tb = p.evaluate(TAPS)
            check("c. every tap target is at least 44 px with 24 real trades on the page", not tb, tb[:5])
            ctx.close()
            # ---- never blank, whatever fails: the real file and the fixture both missing
            ctx, p, errs, seen, off = page(br, origin, block=("odeon/trades.json", "journal/fixture.json"))
            open_(p, origin)
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, n: document.querySelectorAll('#tlist .trade').length, hero: document.querySelector('#hero').innerText, rule: document.querySelector('#ruleText').textContent.length })""")
            check("c. never blank: with the Odeon file and the fixture both unreachable the page still shows 6 built-in DEMO trades, the dollars and a rule", d["demo"] and d["n"] == 6 and "$" in d["hero"] and d["rule"] > 20 and not errs, d)
            ctx.close()
            # ---- the Jarvis card and the pre-trade check
            ctx, p, errs, seen, off = page(br, origin)
            open_(p, origin)
            card0 = p.evaluate("JSON.parse(localStorage.getItem('journal.card.v1'))")
            check("c. the Jarvis card is kept in 'journal.card.v1' as soon as the page is up (a fresh journal says to rate the last trades)", card0 and card0["v"] == 1 and card0["name"] == "MNEMOSYNE" and card0["lines"][0].startswith("Rate your last trades"), card0)
            p.click("#tlist .trade:nth-child(1) button[data-v=interfered]")
            p.click("#tlist .trade:nth-child(1) button[data-v=fomo]")
            p.wait_for_timeout(500)
            card1 = p.evaluate("JSON.parse(localStorage.getItem('journal.card.v1'))")
            ok_card = (card1["v"] == 1 and 1 <= len(card1["kpis"]) <= 3 and 1 <= len(card1["lines"]) <= 3 and all(len(x) <= 120 and "<" not in x and ">" not in x for x in card1["lines"])
                       and isinstance(card1["t"], int) and card1["status"]["level"] in ("ok", "warn", "bad", "off") and re.fullmatch(r"#[0-9a-f]{6}", card1["theme"]) and len(json.dumps(card1)) < 8192)
            check("c. rating a trade updates the card: 'You interfered on 1 of your last 9 trades, it cost $437.' (the card contract: <= 3 kpis, lines <= 120, no markup, int t, < 8 KB)", ok_card and card1["lines"][0] == "You interfered on 1 of your last 9 trades, it cost $437.", card1)
            st = p.evaluate("window.JOURNAL_STATS()")
            check("c. window.JOURNAL_STATS(): the same numbers for Jarvis (9 trades looked at, 1 interfered, -$437)", st["n"] == 9 and st["interfered"] == 1 and st["interferedUsd"] == -437 and st["line"] == card1["lines"][0], st)
            jv = p.evaluate("""async () => { const A = await import('../jarvis/apps.js'); const c = await A.appStatus('journal'); return c ? c.lines : null; }""")
            check("c. Jarvis's appStatus('journal') shows the newer card from this phone instead of the demo file (the weekly recap line, in dollars)", jv and jv[0] == "You interfered on 1 of your last 9 trades, it cost $437.", jv)
            p.evaluate("localStorage.setItem('journal.card.v1', JSON.stringify({v: 1, name: 'x', status: {level: 'ok', label: '<b>'}, kpis: [], lines: ['<img src=x>'], t: 1, open: '#'}))")
            jv2 = p.evaluate("""async () => { const A = await import('../jarvis/apps.js'); const c = await A.appStatus('journal'); return c ? c.lines : null; }""")
            check("c. a bad or older 'journal.card.v1' is ignored by Jarvis (it keeps the file's card)", jv2 and all("img" not in x for x in jv2), jv2)
            p.evaluate("localStorage.removeItem('journal.card.v1')")
            # open the sheet
            p.click("#checkBtn")
            sh = p.evaluate("""() => ({ open: !document.querySelector('#sheet').hidden, qs: [...document.querySelectorAll('#qs .qt')].map((e) => e.textContent), level: document.querySelector('#verdict').dataset.level, head: document.querySelector('#vHead').textContent,
              focusIn: document.querySelector('#panel').contains(document.activeElement), inert: document.querySelector('#app').inert === true, locked: document.documentElement.classList.contains('sheeted'),
              hints: [...document.querySelectorAll('#qs .qh')].map((e) => e.textContent), dlg: document.querySelector('#panel').getAttribute('role') + ' ' + document.querySelector('#panel').getAttribute('aria-modal') })""")
            check("c. the Pre-trade check opens in one tap: a dialog with 5 numbered questions, the verdict says '5 questions to go', focus is inside, the page behind it is inert", sh["open"] and len(sh["qs"]) == 5 and sh["qs"][0] == "1. Am I calm right now?" and sh["level"] == "open" and sh["head"] == "5 questions to go"
                  and sh["focusIn"] and sh["inert"] and sh["locked"] and sh["dlg"] == "dialog true", sh)
            check("c. the questions show what his own journal says in dollars (the last loss, what touching it cost, FOMO)", any("Your last trade was -$437" in x for x in sh["hints"]) and any("Touching it has cost you $437 on 1 trade" in x for x in sh["hints"]) and any("FOMO trades cost you $437" in x for x in sh["hints"]), sh["hints"])
            tb = p.evaluate(TAPS)
            check("c. every tap in the sheet is at least 44 px, and its bottom edge leaves Jarvis's corner free (176 px) even scrolled to the end", not tb and not p.evaluate("""() => { const P = document.querySelector('#panel'); P.scrollTop = P.scrollHeight; const r = P.getBoundingClientRect(); return r.bottom > innerHeight - 170 || P.scrollWidth > P.clientWidth; }"""), tb[:4])
            ans = lambda q, v: p.click(f"#qs li[data-q={q}] button[data-v={v}]")
            for q, v in (("calm", "yes"), ("plan2", "yes"), ("loss", "no"), ("touch", "no")):
                ans(q, v)
            mid = p.evaluate("[document.querySelector('#verdict').dataset.level, document.querySelector('#vHead').textContent, JSON.parse(localStorage.getItem('journal.v1')).checks.length]")
            ans("mood", "no")
            fine = p.evaluate("""() => ({ level: document.querySelector('#verdict').dataset.level, head: document.querySelector('#vHead').textContent, cost: document.querySelector('#vCost').textContent, checks: JSON.parse(localStorage.getItem('journal.v1')).checks,
              green: document.querySelectorAll('#qs li.ok').length, hint: document.querySelector('#chkHint').textContent })""")
            check("c. four answers = still open and nothing kept; the fifth gives the verdict 'Fine, the bot is running the plan.' with the dollar cost of his interfering, and the check is kept locally", mid == ["open", "1 question to go", 0]
                  and fine["level"] == "fine" and fine["head"] == "Fine, the bot is running the plan." and "Interfering has cost you $437 on 1 trade" in fine["cost"] and len(fine["checks"]) == 1 and fine["checks"][0]["a"] == "yynnn" and fine["checks"][0]["v"] == "fine" and fine["green"] == 5
                  and "1 check so far, 0 said wait" in fine["hint"], (mid, fine))
            ans("loss", "yes")
            wait = p.evaluate("""() => ({ level: document.querySelector('#verdict').dataset.level, head: document.querySelector('#vHead').textContent, why: document.querySelector('#vWhy').textContent, checks: JSON.parse(localStorage.getItem('journal.v1')).checks, red: document.querySelectorAll('#qs li.red').length, hint: document.querySelector('#chkHint').textContent })""")
            check("c. changing one answer to the bad side flips it to 'Wait 10 minutes.' (the same check is updated, not added twice)", wait["level"] == "wait" and wait["head"] == "Wait 10 minutes." and "10-minute timer" in wait["why"] and len(wait["checks"]) == 1 and wait["checks"][0]["v"] == "wait" and wait["red"] == 1 and "1 said wait" in wait["hint"], wait)
            ans("loss", "yes")
            gone = p.evaluate("[document.querySelector('#verdict').dataset.level, JSON.parse(localStorage.getItem('journal.v1')).checks.length]")
            check("c. tapping the chosen answer again clears it: the verdict is open again and the unfinished check is not kept", gone == ["open", 0], gone)
            ans("loss", "no")
            p.click("#shReset")
            rs = p.evaluate("[document.querySelector('#verdict').dataset.level, document.querySelectorAll('#qs [aria-checked=true]').length, JSON.parse(localStorage.getItem('journal.v1')).checks.length]")
            check("c. Start again clears the answers (the finished check stays in the count)", rs == ["open", 0, 1], rs)
            p.keyboard.press("Escape")
            cl = p.evaluate("""() => ({ hidden: document.querySelector('#sheet').hidden, inert: document.querySelector('#app').inert, locked: document.documentElement.classList.contains('sheeted'), focus: document.activeElement && document.activeElement.id })""")
            check("c. Escape closes the sheet, the page is live again and the focus goes back to the button that opened it", cl == {"hidden": True, "inert": False, "locked": False, "focus": "checkBtn"}, cl)
            p.click("#checkBtn")
            p.click("#scrim", position={"x": 3, "y": 400})
            check("c. a tap outside the sheet closes it too", p.evaluate("document.querySelector('#sheet').hidden"))
            p.click("#checkBtn")
            p.click("#shClose")
            check("c. the Close button closes it", p.evaluate("document.querySelector('#sheet').hidden"))
            p.click("#checkBtn")
            for i in range(14):
                p.keyboard.press("Tab")
            check("c. Tab never leaves the sheet (a focus trap) while it is open", p.evaluate("document.querySelector('#panel').contains(document.activeElement)"))
            p.keyboard.press("Escape")
            p.goto(f"{origin}/journal/?check=1")
            p.wait_for_function("window.JOURNAL && window.JOURNAL.ready()", timeout=120000, polling=300)
            p.wait_for_timeout(300)
            check("c. ?check=1 (a shortcut, or Jarvis) opens the sheet at once; the last check is remembered across a reload", not p.evaluate("document.querySelector('#sheet').hidden") and "Last check:" in p.evaluate("document.querySelector('#chkHint').textContent"))
            p.goto(f"{origin}/journal/#check")
            p.reload()
            p.wait_for_function("window.JOURNAL && window.JOURNAL.ready()", timeout=120000, polling=300)
            p.wait_for_timeout(300)
            check("c. #check opens it too", not p.evaluate("document.querySelector('#sheet').hidden"))
            check("c. the check: no console error, nothing off the page's origin, only the journal's two keys", not errs and not off and sorted(p.evaluate("Object.keys(localStorage).filter((k) => /journal/i.test(k))")) == ["journal.card.v1", "journal.v1"], (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = page(br, origin, w=375, h=667)
            open_(p, origin, "?demo=1")
            p.click("#checkBtn")
            small = p.evaluate("""() => { const P = document.querySelector('#panel'), r = P.getBoundingClientRect(); return { fits: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight - 170, side: P.scrollWidth <= P.clientWidth, tall: Math.round(r.height) }; }""")
            check("c. 375 x 667: the sheet fits (scrolls inside itself), no sideways scroll, taps >= 44 px, the demo preview never overwrites the real Jarvis card",
                  small["fits"] and small["side"] and not p.evaluate(TAPS) and p.evaluate("localStorage.getItem('journal.card.v1')") is None, small)
            ctx.close()
            # ---- other sizes, LITE, reduced motion
            ctx, p, errs, seen, off = page(br, origin, w=375, h=667)
            open_(p, origin, "?demo=1")
            check("c. 375 x 667: no sideways scroll, every tap >= 44 px, Jarvis's corner free", p.evaluate("document.documentElement.scrollWidth <= innerWidth") and not p.evaluate(TAPS) and not p.evaluate(CORNER), p.evaluate(TAPS)[:3])
            ctx.close()
            ctx, p, errs, seen, off = page(br, origin, fx="low")
            open_(p, origin, "?demo=1")
            lite = p.evaluate("""() => ({ tag: !document.querySelector('#lite').hidden, lite: document.documentElement.getAttribute('data-oly-lite'), anim: getComputedStyle(document.querySelector('.aurora i')).animationName, trades: document.querySelectorAll('#tlist .trade').length })""")
            check("c. LITE (3D Low): the LITE tag shows, the aurora blur is lighter, the journal works the same (no 3D at all: it is a 2D page)", lite["tag"] and lite["lite"] == "1" and lite["trades"] >= 10 and not errs, lite)
            ctx.close()
            ctx, p, errs, seen, off = page(br, origin, reduced=True)
            open_(p, origin, "?demo=1")
            anim = p.evaluate("[...document.querySelectorAll('.aurora i, .trade')].map((e) => getComputedStyle(e).animationName)")
            check("c. reduced motion: nothing animates (no aurora drift, no card rise)", set(anim) <= {"none"} and not errs, set(anim))
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    t0 = time.time()
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    n = sum(RES)
    print(f"\nMNEMOSYNE page: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'} in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)


if __name__ == "__main__":
    main()
