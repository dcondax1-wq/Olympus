"""PINAKES, the OLYMPUS catalogue (tools/web_public/pinakes/, AGORA look, 2026-11-11) and its builder tools/pinakes_build.py: every table OLYMPUS keeps, searchable, sortable, filterable, on a phone.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the demo catalogue, the builder (--check, --selftest, stdlib, offline), the catalogue itself
     (no rows copied, every address is a real file of this site, research datasets are span and rows only), the new_apps row
  b. the rules in node (pinakescore.js): the page reads every real table exactly as the builder catalogued it; tricky data (nulls, mixed types, unicode, 10,000 rows) through
     inference, filters, sort, stats, group, histogram, CSV, JSON; the share link and saved views against junk; the Ask questions on the demo and on the real files
  c. Chromium 390 x 844 and 375 x 667: the catalogue, the cabinet (WebGL drawers / flat), open a table, the windowed grid on 10,000 rows, sort, filters in plain words, stats, chart,
     group, the list picker, saved views, export, the share link, honest labels, a table that fails says why, Ask, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_pinakes_page            (--static: parts a and b only)
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_pinakes_page      (the browser part, one browser on the machine)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from tests import agora_kit as AK  # noqa: E402
import pinakes_build as PB  # noqa: E402

APP, NAME, TODAY = "pinakes", "Pinakes", "2026-11-11"
check = AK.check
D = os.path.join(AK.WEB, APP)


def catalog():
    return json.load(open(os.path.join(D, "catalog.json"), encoding="utf-8"))


def test_static():
    AK.static_kit(APP, NAME, reads=("./catalog.json",), storage=True)
    js, core, scene, html, css = (AK.read(os.path.join(D, n)) for n in ("pinakes.js", "pinakescore.js", "pinakesscene.js", "index.html", "pinakes.css"))
    check("a. the page keeps only its own 'pinakes.v1' (saved views) on the phone; no session storage / indexedDB; every table address goes through safeUrl before it is fetched",
          "'pinakes.v1'" in js and len(re.findall(r"localStorage\.setItem\(", js)) == 1 and not re.search(r"sessionStorage|indexedDB", js + core) and "if (!C.safeUrl(url)) return" in js and len(re.findall(r"\bfetch\(", js)) == 2, None)
    check("a. the 3D scene: a marble cabinet from three (local copy), WebGL optional (returns null -> the flat cabinet), draws only while something moves, no bloom or composer",
          "../jarvis/three.module.min.js" in scene and "createCabinet" in js and "return null" in scene and "drawFlat" in js and "if (!moving && !dirty) return" in scene
          and not re.search(r"Bloom|EffectComposer|neon|emissive: '#(?:0ff|f0f)", scene) and not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|eval\(", scene), None)
    ids = ('id="cab"', 'id="districts"', 'id="q"', 'id="list"', 'id="asks"', 'id="pathSel"', 'id="fCol"', 'id="fOp"', 'id="fVal"', 'id="grid"', 'id="statList"', 'id="chart"', 'id="groupTable"',
           'id="csvBtn"', 'id="jsonBtn"', 'id="shareBtn"', 'id="vSave"', 'id="vList"', 'id="vExport"', 'id="vFile"', 'id="tWhy"')
    check("a. the page has every part: cabinet, districts, search, list, Ask, list picker, filter builder, grid, stats, chart, group table, CSV / JSON / share, saved views (save, list, export, import), the 'why' line",
          all(x in html for x in ids), [x for x in ids if x not in html])
    check("a. the grid is windowed: one scroller, a sticky header, pooled rows moved with translateY, repainted once per frame", "position: sticky" in css and "translateY(" in js and "requestAnimationFrame" in js and "idx % P" in js and "contain: strict" in css, None)
    check("a. honest words are on the page: DEMO, SAMPLE, STALE, 'not real', 'Never an order', 'not a promise'", all(x in js + core + html for x in ("DEMO", "SAMPLE", "STALE", "not real", "Never an order", "not a promise")), None)
    # the builder
    src = AK.read(os.path.join(ROOT, "tools", "pinakes_build.py"))
    check("a. the builder is stdlib only, offline and read only (no network module, no engine / bot import, it writes only catalog.json, jarvis.json and fixture.json)",
          not re.search(r"^\s*(?:import|from)\s+(?:urllib|requests|http|socket|ccxt|ninja|engine|numpy|pandas)", src, re.M) and src.count('open(out, "w"') == 2 and src.count('open(jv_path, "w"') == 1 and src.count('open(fx_path, "w"') == 1, None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = PB.selftest()
    check("a. python tools/pinakes_build.py --selftest passes (inference on tricky data, a temp site, --check, the demo catalogue)", rc == 0, buf.getvalue()[-700:])
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "pinakes_build.py"), "--check"], capture_output=True, text=True)
    check("a. python tools/pinakes_build.py --check: the committed catalog.json, jarvis.json and fixture.json are what the builder writes now", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    cat = catalog()
    tabs = cat["tables"]
    site = [c for c in tabs if c["source"] == "site"]
    check("a. the catalogue: 80+ tables in all five districts, unique ids, counts that add up", len(tabs) >= 80 and {c["district"] for c in tabs} == set(PB.DISTRICTS) and len({c["id"] for c in tabs}) == len(tabs)
          and cat["totals"]["tables"] == len(tabs) and cat["totals"]["rows"] == sum(c["rows"] or 0 for c in tabs) and sum(v["tables"] for v in cat["counts"].values()) == len(tabs), cat["totals"])
    check("a. it never copies data: at most 2 short sample rows a table, the whole file is under 160 KB next to the megabytes it describes",
          all(len(c["sample"]) <= 2 and all(len(str(v)) <= 60 for s in c["sample"] for v in s.values()) for c in tabs) and os.path.getsize(os.path.join(D, "catalog.json")) < 160000
          and sum(c["bytes"] or 0 for c in site) > 4000000, os.path.getsize(os.path.join(D, "catalog.json")))
    bad = [c["id"] for c in site if not re.match(r"^\.\./[A-Za-z0-9_\-./~]+\.json$", c["url"]) or ".." in c["url"][3:] or not os.path.isfile(os.path.join(D, c["url"]))]
    check("a. every site table points at a real JSON file of this site (a relative address, no web address, nothing above the site)", not bad and len(site) >= 60, bad[:5])
    res = [c for c in tabs if c["source"] == "research"]
    check("a. the research datasets under data/ are in the catalogue with span and rows only: no address, nothing to download, and the description says so",
          len(res) >= 10 and all(c["url"] is None and c["rows"] > 0 and c["span"]["first"] <= c["span"]["last"] and "not published" in c["desc"] and c["file"].startswith("data/") and not c["sample"] for c in res)
          and any(c["id"] == "research-nq-5m" and c["rows"] > 300000 for c in res), [c["id"] for c in res][:4])
    bld = {c["id"]: c for c in tabs if c["source"] == "build"}
    check("a. the files only the site build writes (home.json, data.json, intel.json, money/*.json ...) are catalogued as 'needs the site build', not measured, never faked",
          {"home", "data", "intel", "money-index", "money-chrysos", "money-mercury"} <= set(bld) and all(c["rows"] is None and c["label"] == "build" and "site build" in c["needs"] for c in bld.values())
          and bld["money-mercury"]["path"] == "items" and {"k": "usd", "t": "usd"} in bld["money-mercury"]["cols"], sorted(bld)[:8])
    by = {c["id"]: c for c in tabs}
    hand = [c for c in tabs if c["source"] != "research" and not c["desc"].startswith(("Demo data", "Sample data")) and "Fields:" not in c["desc"]]
    check("a. 30+ tables carry a hand-written plain description; the rest get one worked out from the file; labels: fixtures are 'demo'",
          len(hand) >= 30 and by["odeon-trades"]["name"] == "Trades (Odeon)" and by["odeon-trades"]["district"] == "Market" and by["oikos-fixture"]["label"] == "demo" and "not real" in by["oikos-fixture"]["desc"], len(hand))
    check("a. types are worked out: Odeon trades have a date 'day', '$' usd, 'R' r; the Archive runs are unpacked into named fields with 'verdict' as a word",
          {"day": "date", "usd": "usd", "r": "R", "side": "text"}.items() <= {c["k"]: c["t"] for c in by["odeon-trades"]["cols"]}.items()
          and {"family": "text", "verdict": "text", "m26.net": "usd", "m26.pf": "number"}.items() <= {c["k"]: c["t"] for c in by["archive-index"]["cols"]}.items()
          and by["datacity-city~skyline-rows"]["rows"] > 30000, [c["k"] for c in by["archive-index"]["cols"]])
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    check("a. the demo catalogue carries its own tables (never blank with no network) and every one is labelled demo", all(c["inline"] in fx["data"] and c["label"] == "demo" for c in fx["catalog"]["tables"]) and len(fx["catalog"]["tables"]) >= 5, None)
    apps = json.load(open(os.path.join(ROOT, "tools", "new_apps.json"), encoding="utf-8"))["apps"]
    row = next((a for a in apps if a["id"] == APP), None)
    check("a. the row in tools/new_apps.json (name, group, accent, glyph, a description under 80 characters, ambient, flavour, transition) and the wiring section",
          row is not None and row["name"] == NAME and len(row["description"]) < 80 and row["group"] in ("trading", "money", "life") and len(row["flavour"]) == 3 and "kind" in row["transition"]
          and "# Wiring PINAKES" in AK.read(os.path.join(ROOT, "docs", "NEW_APPS_WIRING.md")), row)


HARNESS = r"""
const fs = require('fs'), path = require('path');
import(process.argv[2]).then((C) => {
  const web = process.argv[3], today = process.argv[4], out = {};
  // 1. every real table: the page must read it exactly as the builder catalogued it
  const cat = C.normalizeCatalog(JSON.parse(fs.readFileSync(path.join(web, 'pinakes', 'catalog.json'), 'utf8')));
  const diffs = []; let checked = 0; const docs = {};
  for (const c of cat.tables) {
    if (c.source !== 'site') continue;
    const doc = docs[c.url] || (docs[c.url] = JSON.parse(fs.readFileSync(path.join(web, 'pinakes', c.url), 'utf8')));
    const t = C.openTable(doc, c.path, c.kind, c.opts); checked++;
    if (t.rows.length !== c.rows || t.path !== c.path || t.kind !== c.kind || JSON.stringify(t.cols.map((x) => [x.k, x.t])) !== JSON.stringify(c.cols.map((x) => [x.k, x.t]))) diffs.push(c.id);
    const fr = C.findFresh(doc); if (JSON.stringify(fr) !== JSON.stringify(c.fresh)) diffs.push('fresh ' + c.id);
  }
  out.agree = { checked, diffs, tables: cat.tables.length, words: C.totalWords(C.totals(cat.tables)), note: C.totalNote(C.totals(cat.tables)) };
  // 2. tricky data
  const rows = [
    { day: '2026-11-10', pnl: 120.5, r: 1.2, win: true, note: 'Sweep, then "CISD"', qty: 2, t: 1793394000, tags: ['a', 'b'], mix: 1, meta: { a: 1, b: 'x' } },
    { day: '2026-11-07', pnl: null, r: -1, win: false, note: null, qty: '3', t: 1793480400, tags: [], mix: 'two', meta: { a: 2 } },
    { day: null, pnl: -60, r: 0, win: null, note: '日本語 ✓ café', qty: 4, t: null, mix: null, extra: '' },
    { day: '2026-10-01', pnl: 0, r: 2.5, win: true, note: '=SUM(A1:A9)', qty: 1, t: 1793000000, mix: true },
    { day: '2026-11-11T09:30:00Z', pnl: -437, r: -1.03, win: false, note: 'line one\nline two', qty: 5, t: 1793566800, mix: 2.5 },
    { day: '2025-01-02', pnl: 2000, r: 8, win: true, note: 'CAFÉ', qty: 2, t: 1735800000, mix: '-dash' },
  ];
  const flat = rows.map(C.flatten), cols = C.inferColumns(flat, true), ty = {}; cols.forEach((c) => { ty[c.k] = c.t; });
  out.types = ty; out.mixed = cols.filter((c) => c.mixed).map((c) => c.k);
  const F = (fs_, mode) => C.applyFilters(flat, C.cleanFilters(fs_, cols), cols, today, mode).map((r) => flat.indexOf(r));
  out.filters = {
    lt0: F([{ col: 'pnl', op: 'lt', value: '0' }]), gte0: F([{ col: 'pnl', op: 'gte', value: 0 }]), between: F([{ col: 'pnl', op: 'between', value: '-100', value2: '$1,000' }]), empty: F([{ col: 'pnl', op: 'empty' }]),
    last7: F([{ col: 'day', op: 'last', value: '7' }]), last1: F([{ col: 'day', op: 'last', value: 1 }]), before: F([{ col: 'day', op: 'before', value: '2026-01-01' }]), on: F([{ col: 'day', op: 'on', value: '2026-11-11' }]),
    epochLast7: F([{ col: 't', op: 'last', value: 14 }]), has: F([{ col: 'note', op: 'has', value: 'café' }]), hasJp: F([{ col: 'note', op: 'has', value: '日本' }]), nhas: F([{ col: 'note', op: 'nhas', value: 'e' }]),
    starts: F([{ col: 'note', op: 'starts', value: 'sweep' }]), yes: F([{ col: 'win', op: 'yes' }]), no: F([{ col: 'win', op: 'no' }]), numstr: F([{ col: 'qty', op: 'gte', value: 3 }]),
    and: F([{ col: 'pnl', op: 'lt', value: 0 }, { col: 'win', op: 'no' }]), or: F([{ col: 'pnl', op: 'gt', value: 1000 }, { col: 'r', op: 'lt', value: -1 }], 'any'),
    mixHas: F([{ col: 'mix', op: 'has', value: '2' }]), flat: F([{ col: 'meta.a', op: 'eq', value: 2 }]), json: F([{ col: 'tags', op: 'has', value: '"b"' }]),
  };
  out.junkFilters = C.cleanFilters([{ col: 'nope', op: 'lt', value: 1 }, { col: 'pnl', op: 'has', value: 'x' }, { col: 'pnl', op: 'lt', value: 'abc' }, { col: 'day', op: 'last', value: -2 }, { col: 'pnl', op: 'between', value: 1 }, null, 7, { col: 'pnl', op: 'lt' }, { col: 'win', op: 'yes', value: 'ignored' }], cols);
  out.words = [C.filterWords({ col: 'pnl', op: 'lt', value: '0' }, 'usd'), C.filterWords({ col: 'day', op: 'last', value: 7 }, 'date'), C.filterWords({ col: 'note', op: 'has', value: 'sweep' }, 'text'), C.filterWords({ col: 'r', op: 'between', value: -1, value2: 2 }, 'R'), C.filterWords({ col: 'win', op: 'yes' }, 'bool'),
    C.filtersWords([{ col: 'pnl', op: 'lt', value: 0 }, { col: 'day', op: 'last', value: 1 }], cols, 'all'), C.filtersWords([{ col: 'pnl', op: 'lt', value: 0 }, { col: 'win', op: 'no' }], cols, 'any')];
  const S = (k, d) => C.sortRows(flat, k, d, ty[k]).map((r) => flat.indexOf(r));
  out.sorts = { pnlDesc: S('pnl', 'desc'), pnlAsc: S('pnl', 'asc'), dayDesc: S('day', 'desc'), noteAsc: S('note', 'asc'), mixAsc: S('mix', 'asc'), qtyAsc: S('qty', 'asc'), winDesc: S('win', 'desc') };
  out.stats = { pnl: C.stats(flat, 'pnl', 'usd'), qty: C.stats(flat, 'qty', 'number'), day: C.stats(flat, 'day', 'date'), note: C.stats(flat, 'note', 'text'), win: C.stats(flat, 'win', 'bool'), extra: C.stats(flat, 'extra', 'text') };
  out.groups = { win: C.groupBy(flat, 'win', 'bool', 'pnl', 'usd', 'day', 'sum'), month: C.groupBy(flat, 'day', 'date', 'pnl', 'usd', 'month', 'sum'), weekday: C.groupBy(flat, 'day', 'date', 'r', 'R', 'weekday', 'sum'),
    week: C.groupBy(flat, 'day', 'date', null, null, 'week', 'count').map((g) => [g.key, g.count]), mean: C.groupBy(flat, 'win', 'bool', 'r', 'R', 'day', 'mean').map((g) => [g.key, g.mean]) };
  out.hist = [C.histogram(flat, 'pnl', 4).map((b) => b.n), C.histogram([{ v: 5 }, { v: 5 }], 'v', 10).length, C.histogram([], 'v', 10).length];
  out.csv = C.toCSV(flat, cols); out.json = JSON.parse(C.toJSON(flat, cols));
  out.fmt = [C.fmt(120.5, 'usd'), C.fmt(-437, 'usd'), C.fmt(2000, 'usd'), C.fmt('$1,250.50', 'usd'), C.fmt(1.2, 'R'), C.fmt(-1.03, 'R'), C.fmt(1234567.891, 'number'), C.fmt(0.00012, 'number'), C.fmt(true, 'bool'), C.fmt(false, 'bool'), C.fmt(null, 'usd'),
    C.fmt(NaN, 'number'), C.fmt(1793394000, 'date'), C.fmt('2026-11-11T09:30:00Z', 'date'), C.fmt({ a: [1, 2] }, 'json'), C.fmt('x'.repeat(300), 'text').length, C.fmt(-0.001, 'usd'), C.bytesWords(2492634), C.plural(1, 'row'), C.plural(41200, 'row')];
  out.dates = [C.weekdayOf('2026-11-11'), C.weekdayOf('2026-11-08T23:30:00Z'), C.weekOf('2026-11-11'), C.weekOf('2026-11-08'), C.dayOf(1793394000), C.weekdayOf(''), C.toMs('2026-02-30') > 0, isNaN(C.toMs('soon')), C.dayOf('2026-11-11 09:30')];
  // 3. 10,000 rows
  const big = []; for (let i = 0; i < 10000; i++) big.push({ i, day: C.isoDay(Date.UTC(2021, 0, 1) + (i % 2000) * 86400000), usd: ((i * 37) % 1001) - 500, grp: 'g' + (i % 7), txt: i % 13 === 0 ? null : 'row ' + i + (i % 500 === 0 ? ' ünï' : ''), ok: i % 3 === 0 });
  const t0 = Date.now(), bc = C.inferColumns(big, true), kept = C.applyFilters(big, [{ col: 'usd', op: 'lt', value: 0 }, { col: 'txt', op: 'has', value: 'ÜNÏ' }], bc, today), neg = C.applyFilters(big, [{ col: 'usd', op: 'lt', value: 0 }], bc, today);
  const sorted = C.sortRows(big, 'usd', 'desc', 'usd'), st = C.stats(big, 'usd', 'usd'), gr = C.groupBy(big, 'grp', 'text', 'usd', 'usd', 'day', 'sum'), mo = C.groupBy(big, 'day', 'date', 'usd', 'usd', 'month', 'sum'), csv = C.toCSV(big, bc);
  out.big = { ms: Date.now() - t0, types: bc.map((c) => c.t), kept: kept.length, neg: neg.length, top: sorted[0].usd, bottom: sorted[9999].usd, stable: sorted[0].i < sorted[1].i, sum: st.sum, mean: st.mean, min: st.min, max: st.max, median: st.median, distinct: st.distinct,
    groups: gr.length, gsum: gr.reduce((s, g) => s + g.sum, 0), gcount: gr.reduce((s, g) => s + g.count, 0), months: mo.length, firstMonth: mo[0].key, csvLines: csv.split('\r\n').length, txtEmpty: C.stats(big, 'txt', 'text').empty };
  // 4. nested files and the list picker
  const nest = { asof: '2026-11-10T12:00:00Z', a: { rows: [{ x: 1 }, { x: 2 }, { x: 3 }] }, b: [[1, 'p'], [2, 'q']], cols: ['n', 's'], c: { k1: { v: 1, w: 2 }, k2: { v: 2, w: 3 }, k3: { v: 3, w: 4 } }, lone: 5 };
  const p0 = C.openTable(nest, '', 'auto', null), p1 = C.openTable(nest, 'b', null, null), p2 = C.openTable(nest, 'c', null, null), p3 = C.openTable(nest, 'gone/away', 'rows', null), p4 = C.openTable({ a: 1, b: 'x' }, '', 'auto', null), p5 = C.openTable([3, 1, 2], '', null, null), p6 = C.openTable('just text', '', null, null);
  out.paths = { found: p0.paths.map((p) => [p.path, p.kind, p.rows]), auto: [p0.path, p0.rows.length], matrix: p1.rows, map: p2.rows[1], moved: [p3.moved, p3.path], kv: p4.rows, values: [p5.kind, p5.rows.length], scalar: [p6.kind, p6.rows.length], fresh: C.findFresh(nest) };
  // 5. the share link and saved views
  const view = { t: 'odeon-trades', p: 'trades', f: [{ col: 'usd', op: 'lt', value: 0 }, { col: 'day', op: 'last', value: 7 }, { col: 'note', op: 'has', value: 'a&b=c #é "q"' }], m: 'any', s: ['usd', 'desc'], c: { kind: 'line', y: 'usd', by: 'day', agg: 'mean', bucket: 'week' }, tab: 'chart', h: ['bars.c'] };
  const enc = C.encodeView(view);
  out.link = { round: JSON.stringify(C.decodeView('#' + enc)) === JSON.stringify(C.cleanView(view)), ascii: /^[\x21-\x7e]+$/.test(enc), len: enc.length,
    junk: [C.decodeView('#v=%7Bnope'), C.decodeView('#v=' + encodeURIComponent('{"t":"../../etc"}')), C.decodeView(''), C.decodeView('#v=' + encodeURIComponent('[1]')), C.decodeView('#x=1'), C.decodeView('#v=' + 'a'.repeat(9000))],
    trimmed: C.decodeView('#v=' + encodeURIComponent(JSON.stringify({ t: 'a-b', f: new Array(50).fill({ col: 'x', op: 'lt', value: 1 }), tab: 'evil', c: { kind: '<script>', agg: 'drop' }, s: ['x', 'sideways'], zzz: 1 }))) };
  const vs = C.normalizeViews(JSON.stringify({ views: [{ name: '  Losers  ', view, at: '2026-11-11' }, { name: 'Losers', view }, { name: 'bad', view: { t: '../x' } }, { name: '', view }, 5, null, { name: 'B', view: { t: 'x' }, at: 'yesterday' }] }));
  out.views = { names: vs.map((v) => v.name), at: vs.map((v) => v.at), nope: [C.normalizeViews('nope'), C.normalizeViews({ a: 1 }), C.normalizeViews('{"views":5}')], roundtrip: C.normalizeViews(C.exportViews(vs)).length, cap: C.normalizeViews(new Array(100).fill(0).map((_, i) => ({ name: 'v' + i, view: { t: 'x' } }))).length };
  out.urls = ['../odeon/trades.json', './catalog.json', '../money/index.json', '../a/b/c-d_e.json', '//evil.example/x.json', 'http:/' + '/x/y.json', '../../secret.json', '../a/../../b.json', '/abs.json', '../a/b.js', '../a b.json', 'javascript:alert(1)', '..\\x.json', null, '../a//b.json'].map(C.safeUrl);
  // 6. labels and why-words
  const card = cat.tables.filter((c) => c.id === 'odeon-trades')[0], now = C.toMs(today) + 43200000;
  out.labels = [C.labelOf({ label: 'demo', fresh: null }, now), C.labelOf({ label: 'sample', fresh: { field: 'asof', value: '2026-11-10T12:00:00Z' } }, now), C.labelOf({ label: 'live', fresh: { field: 't', value: 1793394000 } }, now),
    C.labelOf({ label: 'live', fresh: { field: 'built', value: '2026-09-01' } }, now), C.labelOf({ label: 'live', fresh: null }, now), C.labelOf({ label: 'research', span: { first: '2021-11-01', last: '2026-10-16' } }, now), C.labelOf({ label: 'build' }, now),
    C.docLabel({ label: 'build' }, { status: 'sample' }), C.docLabel({ label: 'live' }, { demo: true }), C.docLabel({ label: 'build' }, { status: 'ok' }), C.docLabel({ label: 'demo' }, {})];
  out.why = [C.whyWords({ url: '../money/index.json', source: 'build' }, 404), C.whyWords({ url: '../x/y.json', source: 'site' }, 404), C.whyWords({ url: '../x/y.json', source: 'site' }, 'json'), C.whyWords({ url: '../x/y.json', source: 'site' }, 'timeout'),
    C.whyWords({ url: null, file: 'data/NQ_5m.csv', source: 'research' }, 'research'), C.whyWords({ url: '../x/y.json', source: 'site' }, 'empty'), C.whyWords({ url: '../x/y.json', source: 'site' }, 500), C.whyWords({ url: '../x/y.json', source: 'site' }, 'net')];
  out.search = [C.searchCatalog(cat.tables, 'odeon trades', 'All').map((c) => c.id), C.searchCatalog(cat.tables, '', 'Life').length, C.searchCatalog(cat.tables, 'zzzz-nothing', 'All').length, C.searchCatalog(cat.tables, 'NQ 5m', 'Research').map((c) => c.id), C.searchCatalog(cat.tables, 'USD', 'Market').length > 0];
  // 7. Ask: on the demo catalogue and on the real files
  const fx = JSON.parse(fs.readFileSync(path.join(web, 'pinakes', 'fixture.json'), 'utf8')), dcat = C.normalizeCatalog(fx.catalog);
  const rowsOf = (cards, id) => { const c = cards.filter((x) => x.id === id)[0]; if (!c) return null; let doc; if (c.inline) doc = fx.data[c.inline]; else { try { doc = JSON.parse(fs.readFileSync(path.join(web, 'pinakes', c.url), 'utf8')); } catch (_) { return null; } } return C.openTable(doc, c.path, c.kind, c.opts).rows; };
  const ask = (cards, a) => { for (const ids of a.tries) { const sets = ids.map((id) => rowsOf(cards, id)); if (sets.every(Boolean)) return Object.assign(a.run(sets, today), { from: ids }); } return null; };
  out.asks = {}; out.asksReal = {};
  for (const a of C.ASKS) { out.asks[a.id] = ask(dcat.tables, a); out.asksReal[a.id] = ask(cat.tables, a); }
  out.askMeta = C.ASKS.map((a) => [a.id, a.title, a.words.length > 40, a.tries.length]);
  out.demoTotals = C.totalWords(C.totals(dcat.tables));
  console.log(JSON.stringify(out));
});
"""


def test_core():
    o = AK.node(APP, HARNESS, AK.WEB, TODAY)
    if o is None:
        check("b. node is not installed: the page rules were not checked", True)
        return
    check("b. no error in the node harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    cat = catalog()
    ag = o["agree"]
    check(f"b. the page reads all {ag['checked']} real tables exactly as the builder catalogued them (rows, list, kind, every field and its type, the date stamp)", ag["checked"] >= 60 and not ag["diffs"], ag["diffs"][:6])
    check("b. the headline: 'N tables, M rows' with the builder's own totals, and the note says what is open here, what needs the site build and what stays on the PC",
          ag["words"] == f"{cat['totals']['tables']:,} tables, {cat['totals']['rows']:,} rows" and "open right here" in ag["note"] and "site build" in ag["note"] and "kept on the PC" in ag["note"], ag["words"])
    ty = o["types"]
    check("b. types on tricky rows: date, $, R, yes/no, text, a number with a numeric string in it, an epoch as a date, nested, mixed -> text, a flattened field, an all-empty field",
          [ty[k] for k in ("day", "pnl", "r", "win", "note", "qty", "t", "tags", "mix", "meta.a", "meta.b", "extra")] == ["date", "usd", "R", "bool", "text", "number", "date", "json", "text", "number", "text", "text"] and o["mixed"] == ["mix"], ty)
    f = o["filters"]
    check("b. filters on numbers: 'pnl less than 0' (empty cells never match), 'at least 0', 'between -100 and $1,000', 'is empty'", (f["lt0"], f["gte0"], f["between"], f["empty"]) == ([2, 4], [0, 3, 5], [0, 2, 3], [1]), f)
    check("b. filters on dates: 'in last 7 days' = the 7 calendar days up to and including today (11-05 .. 11-11), 'in last 1 day' = today, 'before', 'on' a day with a time, an epoch column works the same",
          (f["last7"], f["last1"], f["before"], f["on"], f["epochLast7"]) == ([0, 1, 4], [4], [5], [4], [0, 1, 4]), f)
    check("b. filters on text: 'contains' ignores case and reads unicode (café finds CAFÉ, 日本 finds 日本語), 'does not contain' skips empty cells, 'starts with'", (f["has"], f["hasJp"], f["nhas"], f["starts"]) == ([2, 5], [2], [2, 3, 5], [0]), f)
    check("b. filters: yes / no, a numeric string counts as its number, AND, OR ('match any'), a mixed field as text, a flattened field, a nested list as its JSON text",
          (f["yes"], f["no"], f["numstr"], f["and"], f["or"], f["mixHas"], f["flat"], f["json"]) == ([0, 3, 5], [1, 4], [1, 2, 4], [4], [4, 5], [4], [1], [0]), f)
    check("b. a filter that makes no sense is dropped, never guessed (unknown field, wrong rule for the type, text where a number goes, a negative day count, half a 'between', junk)", o["junkFilters"] == [{"col": "win", "op": "yes"}], o["junkFilters"])
    check("b. filters in plain words", o["words"] == ["pnl less than $0", "day in last 7 days", 'note contains "sweep"', "r between -1.00R and +2.00R", "win is yes", "pnl less than $0 AND day in last 1 day", "pnl less than $0 OR win is no"], o["words"])
    s = o["sorts"]
    check("b. sort: numbers by value, empty cells always last (both ways), dates newest first, text A to Z without case, a mixed field numbers then text, numeric strings as numbers, ties keep their order",
          s["pnlDesc"] == [5, 0, 3, 2, 4, 1] and s["pnlAsc"] == [4, 2, 3, 0, 5, 1] and s["dayDesc"] == [4, 0, 1, 3, 5, 2] and s["noteAsc"][:2] == [3, 5] and s["noteAsc"][-1] == 1
          and s["mixAsc"] == [0, 4, 5, 3, 1, 2] and s["qtyAsc"] == [3, 0, 5, 1, 2, 4] and s["winDesc"] == [0, 3, 5, 1, 4, 2], s)
    st = o["stats"]
    check("b. stats: count / empty / distinct, sum 1,623.50, mean 324.70, min -437, max 2,000, median 0 for pnl; numeric strings count; a date's first and last; text's commonest values; an all-empty field",
          (st["pnl"]["count"], st["pnl"]["empty"], st["pnl"]["distinct"], st["pnl"]["sum"], st["pnl"]["min"], st["pnl"]["max"], st["pnl"]["median"]) == (5, 1, 5, 1623.5, -437, 2000, 0) and abs(st["pnl"]["mean"] - 324.7) < 1e-9
          and st["qty"]["sum"] == 17 and st["qty"]["distinct"] == 5 and st["day"]["min"] == "2025-01-02" and st["day"]["max"] == "2026-11-11T09:30:00Z" and st["note"]["count"] == 5 and st["win"]["top"][0] == {"value": "true", "n": 3}
          and st["extra"]["count"] == 0 and st["extra"]["empty"] == 6, st["pnl"])
    g = o["groups"]
    check("b. group-by: yes / no / (empty) with sum and count, months in order, weekdays Mon..Sun, weeks start on Monday, a mean",
          {x["key"]: (x["count"], x["sum"]) for x in g["win"]} == {"yes": (3, 2120.5), "no": (2, -437), "(empty)": (1, -60)} and [x["key"] for x in g["month"]] == ["(empty)", "2025-01", "2026-10", "2026-11"]
          and [x["key"] for x in g["weekday"]][:3] == ["Tue", "Wed", "Thu"] and ["2026-11-02", 1] in g["week"] and ["2026-11-09", 2] in g["week"] and dict(g["mean"])["yes"] == 3.9, g["weekday"])
    check("b. histogram: 4 equal ranges holding all 5 numbers, one bar when every value is the same, nothing when there are no numbers", sum(o["hist"][0]) == 5 and len(o["hist"][0]) == 4 and o["hist"][1:] == [1, 0], o["hist"])
    lines = o["csv"].split("\r\n")
    check("b. CSV: a header and 6 rows, quotes doubled, a line break kept inside quotes, unicode intact, yes / no, empty cells empty, a formula-looking cell defused ('=SUM... and '-dash), negative numbers left alone",
          lines[0].startswith("day,pnl,r,win,note,qty,t,tags,mix,meta.a,meta.b,extra") and '"Sweep, then ""CISD"""' in lines[1] and "日本語 ✓ café" in o["csv"] and "'=SUM(A1:A9)" in o["csv"] and '"line one\nline two"' in o["csv"]
          and ",-437,-1.03,no," in o["csv"] and "'-dash" in o["csv"] and lines[2].startswith("2026-11-07,,-1,no,,3,") and '"[""a"",""b""]"' in lines[1] and o["csv"].endswith("\r\n") and o["csv"].count("\r\n") == 7, lines[:3])
    check("b. JSON export: every row with every field (missing -> null), values untouched", len(o["json"]) == 6 and o["json"][1]["pnl"] is None and o["json"][2]["note"] == "日本語 ✓ café" and o["json"][0]["tags"] == ["a", "b"] and o["json"][3]["meta.a"] is None, o["json"][1])
    check("b. words: $120.50, -$437, $2,000, a $ string, +1.20R, -1.03R, 1,234,567.89, 0.0001, yes / no, empty stays empty, an epoch as a UTC time, nested as JSON, long text cut, no '-$0'",
          o["fmt"] == ["$120.50", "-$437", "$2,000", "$1,250.50", "+1.20R", "-1.03R", "1,234,567.89", "0.0001", "yes", "no", "", "", "2026-10-30 21:00 UTC", "2026-11-11 09:30:00Z", '{"a":[1,2]}', 120, "$0", "2.4 MB", "1 row", "41,200 rows"], o["fmt"])
    check("b. dates: 2026-11-11 is a Wed, a Sunday night stays Sunday, weeks start Monday, an epoch's day in UTC, junk is not a date", o["dates"] == ["Wed", "Sun", "2026-11-09", "2026-11-02", "2026-10-30", "", True, True, "2026-11-11"], o["dates"])
    b = o["big"]
    want_neg = sum(1 for i in range(10000) if ((i * 37) % 1001) - 500 < 0)
    want_sum = sum(((i * 37) % 1001) - 500 for i in range(10000))
    check(f"b. 10,000 rows: typed, filtered (two rules, unicode, case), sorted, stats, grouped two ways and written to CSV in {b['ms']} ms (under 1.5 s), all numbers exact",
          b["ms"] < 1500 and b["types"] == ["number", "date", "usd", "text", "text", "bool"] and b["neg"] == want_neg and b["kept"] == sum(1 for i in range(0, 10000, 500) if i % 13 and ((i * 37) % 1001) - 500 < 0)
          and (b["top"], b["bottom"], b["min"], b["max"]) == (500, -500, -500, 500) and b["stable"] and b["sum"] == want_sum == b["gsum"] and abs(b["mean"] - want_sum / 10000) < 1e-9 and b["distinct"] == 1001
          and b["groups"] == 7 and b["gcount"] == 10000 and b["months"] == 66 and b["firstMonth"] == "2021-01" and b["csvLines"] == 10002 and b["txtEmpty"] == sum(1 for i in range(10000) if i % 13 == 0), b)
    p = o["paths"]
    check("b. a nested file: every list is found (records, a grid with its 'cols', named records), the biggest is the default, a list that is gone falls back and says so, a file with no list is a key / value table",
          sorted(map(tuple, p["found"])) == [("a/rows", "rows", 3), ("b", "matrix", 2), ("c", "map", 3)] and p["auto"][1] == 3 and p["matrix"] == [{"n": 1, "s": "p"}, {"n": 2, "s": "q"}] and p["map"] == {"key": "k2", "v": 2, "w": 3}
          and p["moved"][0] is True and p["kv"] == [{"key": "a", "value": 1}, {"key": "b", "value": "x"}] and p["values"] == ["values", 3] and p["scalar"] == ["kv", 1] and p["fresh"] == {"field": "asof", "value": "2026-11-10T12:00:00Z"}, p)
    lk = o["link"]
    check("b. the share link: table + list + filters (with & = # é and quotes) + match-any + sort + chart + tab + hidden fields come back identical; it is plain ASCII",
          lk["round"] and lk["ascii"] and lk["len"] < 900, lk["len"])
    check("b. a hostile or broken link opens nothing: bad JSON, a path as a table id, empty, a list, another key, an over-long link; extra keys, bad enums and 50 filters are trimmed",
          lk["junk"] == [None] * 6 and lk["trimmed"]["t"] == "a-b" and len(lk["trimmed"]["f"]) == 20 and "tab" not in lk["trimmed"] and lk["trimmed"]["c"]["kind"] == "bar" and lk["trimmed"]["c"]["agg"] == "sum" and lk["trimmed"]["s"] == ["x", "asc"]
          and "zzz" not in lk["trimmed"], lk["trimmed"])
    v = o["views"]
    check("b. saved views in and out: names trimmed, doubles / bad table ids / empty names / junk dropped, a bad date blanked, junk files give null, export -> import keeps them, 60 at most",
          v["names"] == ["Losers", "B"] and v["at"] == ["2026-11-11", ""] and v["nope"] == [None, None, None] and v["roundtrip"] == 2 and v["cap"] == 60, v)
    check("b. safeUrl: only a JSON file of this site (4 good); a host, a scheme, climbing above the site, an absolute path, a script, a space, a backslash, null and an empty segment are refused",
          o["urls"] == [True, True, True, True] + [False] * 11, o["urls"])
    lb = o["labels"]
    check("b. honest labels: DEMO, SAMPLE with its age ('24 hours old'), Published with its age in days, STALE past 14 days, no age when the file has no stamp, research = 'On the PC' with its span, 'Site build'",
          (lb[0]["text"], lb[0]["age"]) == ("DEMO", "") and (lb[1]["text"], lb[1]["age"]) == ("SAMPLE", "24 hours old") and (lb[2]["text"], lb[2]["age"]) == ("Published", "11 days old") and (lb[3]["text"], lb[3]["cls"]) == ("STALE", "bad")
          and lb[3]["age"] == "71 days old" and (lb[4]["text"], lb[4]["age"]) == ("Published", "") and (lb[5]["text"], lb[5]["age"]) == ("On the PC", "2021-11-01 to 2026-10-16") and lb[6]["text"] == "Site build", lb[:7])
    check("b. a file that is published but still carries sample or demo data is labelled so once it is read", lb[7:] == ["sample", "demo", "live", "demo"], lb[7:])
    w = o["why"]
    check("b. a table that fails says why in plain words: not built yet, 404, not valid JSON, too slow, research on the PC, no rows, a server answer, no connection",
          "written by the site build" in w[0] and "money/index.json" in w[0] and "not found on this site (404)" in w[1] and "not valid JSON" in w[2] and "too long" in w[3] and "kept on the PC" in w[4] and "data/NQ_5m.csv" in w[4]
          and "no rows" in w[5] and "answered 500" in w[6] and "no connection" in w[7], w)
    sr = o["search"]
    check("b. search: every word must match (name, app, description, field names), by district, nothing found is an empty list", sr[0][0] == "odeon-trades" and sr[1] >= 5 and sr[2] == 0 and "research-nq-5m" in sr[3] and sr[4] is True, sr)
    a, ar = o["asks"], o["asksReal"]
    check("b. Ask: 4 built-in questions, each with its query in plain words and a labelled stand-in when a table is missing", len(o["askMeta"]) == 4 and all(m[2] and m[3] >= 2 for m in o["askMeta"]) and [m[0] for m in o["askMeta"]] == ["weekday", "verdicts", "deals", "kalshi"], o["askMeta"])
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    tr = fx["data"]["trades"]["trades"]
    import datetime as dt
    wd = {}
    for t in tr:
        k = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.date.fromisoformat(t["day"]).weekday()]
        wd.setdefault(k, [0, 0.0])
        wd[k][0] += 1
        wd[k][1] += t["usd"]
    check("b. Ask '$ by weekday' on the demo trades = a plain Python count of the same rows (trades and $ for each weekday, Mon..Fri in order)",
          [(r["weekday"], r["trades"], r["usd"]) for r in a["weekday"]["rows"]] == [(k, wd[k][0], round(wd[k][1], 2)) for k in ("Mon", "Tue", "Wed", "Thu", "Fri") if k in wd] and a["weekday"]["from"] == ["demo-trades"], a["weekday"]["rows"][:2])
    runs = fx["data"]["runs"]["runs"]
    fam = {}
    for r in runs:
        fam.setdefault(r["family"], {"adopted": 0, "rejected": 0, "open": 0})[r["verdict"]] += 1
    check("b. Ask 'runs by verdict per family' on the demo runs = a plain Python count", {r["family"]: (r["adopted"], r["rejected"], r["open"]) for r in a["verdicts"]["rows"]} == {k: (v["adopted"], v["rejected"], v["open"]) for k, v in fam.items()}
          and sum(r["runs"] for r in a["verdicts"]["rows"]) == 60, a["verdicts"]["rows"][:2])
    check("b. Ask 'deals ending this week' (today 2026-11-11): only the dated deals from today to 7 days on, soonest first; ended, later and undated ones are out",
          [(r["ends"], r["days_left"]) for r in a["deals"]["rows"]] == [("2026-11-12", 1), ("2026-11-13", 2), ("2026-11-17", 6), ("2026-11-18", 7)] and "estimate" in a["deals"]["note"], a["deals"]["rows"])
    check("b. Ask 'paper $ by Kalshi strategy' on the demo ledger: every trade counted once, $ adds up", sum(r["trades"] for r in a["kalshi"]["rows"]) == 40 and abs(sum(r["usd"] for r in a["kalshi"]["rows"]) - sum(t["pnl"] for t in fx["data"]["paper"]["trades"])) < 0.02
          and "Never an order" in a["kalshi"]["note"], a["kalshi"]["rows"])
    ix = json.load(open(os.path.join(AK.WEB, "archive", "index.json"), encoding="utf-8"))
    odeon = json.load(open(os.path.join(AK.WEB, "odeon", "trades.json"), encoding="utf-8"))["trades"]
    check("b. Ask on the REAL files: the weekday table counts every Odeon trade and its $; runs by verdict adds up to the Archive's own totals (all runs, adopted, rejected, open) across its 5 files",
          sum(r["trades"] for r in ar["weekday"]["rows"]) == len(odeon) and abs(sum(r["usd"] for r in ar["weekday"]["rows"]) - sum(t["usd"] for t in odeon)) < 0.05 and ar["weekday"]["from"] == ["odeon-trades"]
          and sum(r["runs"] for r in ar["verdicts"]["rows"]) == ix["counts"]["runs"] and sum(r["adopted"] for r in ar["verdicts"]["rows"]) == ix["counts"]["adopted"]
          and sum(r["rejected"] for r in ar["verdicts"]["rows"]) == ix["counts"]["rejected"] and sum(r["open"] for r in ar["verdicts"]["rows"]) == ix["counts"]["open"] and len(ar["verdicts"]["from"]) == 5,
          (sum(r["runs"] for r in ar["verdicts"]["rows"]), ix["counts"]))
    check("b. Ask on the real files: with money/*.json not built here, 'deals' falls back to Mercury's fixture (labelled demo on the page); the Kalshi question reads the real paper ledger",
          ar["deals"]["from"] == ["mercury-fixture"] and all(0 <= r["days_left"] <= 7 for r in ar["deals"]["rows"]) and ar["kalshi"]["from"] == ["kalshicity-ledger"] and sum(r["trades"] for r in ar["kalshi"]["rows"]) == 40, (ar["deals"]["from"], ar["deals"]["rows"][:2]))


def big_doc(n=10000):
    return {"asof": "2026-11-11T08:00:00Z", "rows": [{"i": i, "day": f"20{21 + (i // 12) % 6}-{1 + i % 12:02d}-{1 + i % 28:02d}", "usd": ((i * 37) % 1001) - 500, "r": round((((i * 37) % 1001) - 500) / 250, 2), "grp": f"g{i % 7}",
                                                      "txt": None if i % 13 == 0 else f"row {i}" + (" ünï ✓" if i % 500 == 0 else ""), "ok": i % 3 == 0} for i in range(n)]}


def extra_catalog():
    """The real catalogue plus three test tables: 10,000 rows, a file that is not JSON, a file that is missing."""
    cat = catalog()
    cols = [{"k": "i", "t": "number"}, {"k": "day", "t": "date"}, {"k": "usd", "t": "usd"}, {"k": "r", "t": "R"}, {"k": "grp", "t": "text"}, {"k": "txt", "t": "text"}, {"k": "ok", "t": "bool"}]
    base = {"app": "pinakes", "district": "Command", "path": "rows", "kind": "rows", "bytes": 900000, "cols": cols, "sample": [], "label": "live", "source": "site"}
    cat["tables"] = [dict(base, id="zz-big", name="Big test table", url="../pinakes/big.json", desc="Ten thousand rows for the scroll test.", rows=10000),
                     dict(base, id="zz-broken", name="Broken test table", url="../pinakes/broken.json", desc="A file that is not JSON.", rows=5),
                     dict(base, id="zz-missing", name="Missing test table", url="../pinakes/missing.json", desc="A file that is not there.", rows=5)] + cat["tables"]
    return cat


GRID = "() => { const g = window.PINAKES.G, o = window.PINAKES.S.open; return { dom: document.querySelectorAll('#gbody .grow').length, n: o.view ? o.view.length : -1, cols: g.cols.map((c) => c.k), first: [...document.querySelectorAll('#gbody .grow')].map((r) => +r.dataset.i).sort((a, b) => a - b)[0], h: document.querySelector('#gbody').style.height, count: document.querySelector('#count').textContent, words: document.querySelector('#fWords').textContent }; }"
CELL = "(i) => { const r = [...document.querySelectorAll('#gbody .grow')].filter((x) => +x.dataset.i === i)[0]; return r ? [...r.querySelectorAll('.gc')].map((c) => c.textContent) : null; }"


def add_filter(p, col, op, val=None, val2=None):
    p.evaluate("() => { document.querySelector('#fBox').open = true; }")
    p.select_option("#fCol", col)
    p.select_option("#fOp", op)
    if val is not None:
        p.fill("#fVal", str(val))
    if val2 is not None:
        p.fill("#fVal2", str(val2))
    p.locator("#fAdd").click()
    p.wait_for_timeout(200)


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    big = big_doc()
    over = {"/pinakes/catalog.json": json.dumps(extra_catalog()), "/pinakes/big.json": json.dumps(big), "/pinakes/broken.json": "{ this is not json", "/pinakes/missing.json": None}
    srv, origin = AK.serve(over)
    cat = catalog()
    try:
        with AK.browser() as br:
            # ---------------------------------------------------------------- 1. the DEMO catalogue
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?demo=1&today={TODAY}")
            d = p.evaluate("() => [document.querySelector('#demo').hidden, document.querySelector('#headline').textContent, document.querySelector('#totalNote').textContent, document.querySelectorAll('#list .trow').length, [...document.querySelectorAll('#districts button')].map((b) => b.textContent), document.querySelector('#status').textContent, [...document.querySelectorAll('#list .trow .pill')].map((x) => x.textContent.slice(0, 4))]")
            check("c. DEMO (?demo=1): the chip, '7 tables, N rows', 'EXAMPLE tables', 7 cards each with a DEMO badge, six drawer buttons with counts, never blank",
                  d[0] is False and d[1].startswith("7 tables, ") and "EXAMPLE tables (demo)" in d[2] and d[3] == 7 and d[4][0] == "All7" and len(d[4]) == 6 and "DEMO" in d[5] and set(d[6]) == {"DEMO"}, d)
            mode = p.evaluate("() => window.PINAKES.S.sceneMode")
            if mode == "webgl":
                p.locator("#districts [data-d=Money]").click()
                p.wait_for_timeout(900)
                sc = p.evaluate("() => { const s = window.PINAKES.scene(); return [s.selected(), s.open(), s.frames(), !document.querySelector('#cab').hidden, document.querySelector('#cabFlat').hidden]; }")
                check("c. 3D: the marble cabinet is drawn (WebGL); tapping Money slides that drawer out (and only that one)", sc[0] == 2 and sc[1][2] == 1 and sum(sc[1]) == 1 and sc[2] > 3 and sc[3] and sc[4], sc)
                f0 = p.evaluate("() => window.PINAKES.scene().frames()")
                p.wait_for_timeout(700)
                f1 = p.evaluate("() => window.PINAKES.scene().frames()")
                check("c. 3D: a still cabinet draws nothing (no idle frames: nothing to pay while you read)", f1 == f0, (f0, f1))
                box = p.evaluate("() => { const r = document.querySelector('#cab').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
                p.evaluate("() => window.scrollTo(0, 0)")
                box = p.evaluate("() => { const r = document.querySelector('#cab').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
                p.mouse.click(box[0] + box[2] * 0.5, box[1] + box[3] * 0.62)
                p.wait_for_timeout(700)
                tapd = p.evaluate("() => [window.PINAKES.S.district, window.PINAKES.scene().selected()]")
                check("c. 3D: tapping a drawer on the cabinet itself picks its district (the middle drawer = Money toggles back to All, or picks the one under the finger)", tapd[0] in ("All", "Research", "Money", "Command") and (tapd[1] == -1) == (tapd[0] == "All"), tapd)
                p.locator("#districts [data-d=Money]").click() if tapd[0] != "Money" else None
                p.wait_for_timeout(300)
            else:
                p.locator("#districts [data-d=Money]").click()
                p.wait_for_timeout(300)
                fb = p.evaluate("() => [document.querySelectorAll('#cabFlat .drawer').length, document.querySelectorAll('#cabFlat .drawer.on').length, !document.querySelector('#cabFlat').hidden]")
                check("c. WebGL is not available here: the flat cabinet is drawn instead, with the Money drawer pulled out (never blank)", fb == [5, 1, True], fb)
            lst = p.evaluate("() => [window.PINAKES.S.district, [...document.querySelectorAll('#list .trow')].map((b) => b.dataset.id), document.querySelector('#foundPill').textContent, document.querySelector('#districts [data-d=Money]').getAttribute('aria-pressed')]")
            check("c. opening the Money drawer flips the list to its tables (2 of 7)", lst[0] == "Money" and sorted(lst[1]) == ["demo-deals", "demo-paper"] and lst[2] == "2 of 7" and lst[3] == "true", lst)
            AK.shot(p, "pinakes-demo")
            view_shot(p, "pinakes-cabinet", top=True)
            p.locator("#districts [data-d=All]").click()
            p.fill("#q", "HABIT log")
            p.wait_for_timeout(200)
            sr = p.evaluate("() => [[...document.querySelectorAll('#list .trow')].map((b) => b.dataset.id), document.querySelector('#foundPill').textContent]")
            p.fill("#q", "zzzz")
            p.wait_for_timeout(150)
            none = p.evaluate("() => document.querySelector('#list').textContent")
            check("c. search: 'HABIT log' finds the habits table (every word, any case, 1 of 7); a word that matches nothing says so", sr == [["demo-habits"], "1 of 7"] and 'No table matches "zzzz"' in none, (sr, none))
            p.fill("#q", "")
            font = p.evaluate("() => [getComputedStyle(document.querySelector('h1')).fontFamily, getComputedStyle(document.body).backgroundColor]")
            check("c. AGORA look: serif title, warm dark body", any(f in font[0] for f in ("Palatino", "Iowan", "Georgia")) and font[1] == "rgb(20, 17, 14)", font)
            t = AK.taps(p)
            check("c. catalogue view: every tap target is at least 44 x 44 px, no sideways scroll, Jarvis's corner is free, no console error, nothing off the origin", not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:5], errs[:3], off[:3]))
            # open a demo table
            p.evaluate("() => window.scrollTo(0, 0)")
            p.locator("#list .trow[data-id=demo-trades]").click()
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view", timeout=20000)
            p.wait_for_timeout(300)
            g = p.evaluate(GRID)
            hd = p.evaluate("() => [document.querySelector('#tName').textContent, [...document.querySelectorAll('#tPills .pill')].map((x) => x.textContent), document.querySelector('#tSrc').textContent, document.querySelector('#catView').hidden, location.hash.slice(0, 3), document.querySelector('#pathFld').hidden]")
            check("c. open 'Demo trades': the table view with its name, a DEMO badge with the file's age, 160 rows, where it comes from and its own date stamp; the address bar carries the share link",
                  hd[0] == "Demo trades" and hd[1][0].startswith("DEMO") and "old" in hd[1][0] and "160 rows" in hd[1] and "fixture.json" in hd[2] and '"asof"' in hd[2] and hd[3] is True and hd[4] == "#v=" and hd[5] is True, hd)
            check("c. the grid shows 160 rows through a window (far fewer row elements than rows), typed fields first", g["n"] == 160 and 10 <= g["dom"] <= 40 and g["cols"][:5] == ["day", "side", "strat", "qty", "r"] and g["h"] == "6400px", g)
            row0 = p.evaluate(CELL, 0)
            tr0 = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))["data"]["trades"]["trades"][0]
            check("c. cells are formatted by type: a date, R as '+1.25R', $ with its sign, yes / no, an empty cell as a dash", row0[0] == tr0["day"] and row0[4] == PB_r(tr0["r"]) and row0[5] == money(tr0["usd"]) and row0[8] in ("yes", "no"), (row0, tr0))
            # sort
            p.locator("#ghead .gh[data-k=usd]").click()
            p.wait_for_timeout(200)
            top = p.evaluate(CELL, 0)
            srt = p.evaluate("() => [document.querySelector('#ghead .gh[data-k=usd]').getAttribute('aria-sort'), window.PINAKES.S.open.view[0].usd, window.PINAKES.S.open.view[159].usd]")
            fxt = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))["data"]["trades"]["trades"]
            check("c. tap the 'usd' field name: biggest first (the best trade on top, the worst at the bottom), the header says 'descending'", srt[0] == "descending" and srt[1] == max(t_["usd"] for t_ in fxt) and srt[2] == min(t_["usd"] for t_ in fxt) and top[5] == money(srt[1]), (srt, top))
            p.locator("#ghead .gh[data-k=usd]").click()
            p.wait_for_timeout(150)
            asc = p.evaluate("() => [document.querySelector('#ghead .gh[data-k=usd]').getAttribute('aria-sort'), window.PINAKES.S.open.view[0].usd]")
            check("c. tap again: smallest first", asc == ["ascending", min(t_["usd"] for t_ in fxt)], asc)
            # filters in plain words
            add_filter(p, "usd", "lt", "0")
            g1 = p.evaluate(GRID)
            n_neg = sum(1 for t_ in fxt if t_["usd"] < 0)
            check("c. filter builder: 'usd less than $0' -> only the losing trades, the count line and the sentence say so, a chip to remove it",
                  g1["n"] == n_neg and g1["count"] == f"{n_neg} of 160 rows match." and g1["words"] == "Showing rows where usd less than $0." and p.evaluate("() => document.querySelectorAll('#fChips .chip').length") == 1, g1)
            add_filter(p, "day", "last", "7")
            g2 = p.evaluate(GRID)
            import datetime as dt
            n_recent = sum(1 for t_ in fxt if t_["usd"] < 0 and 0 <= (dt.date(2026, 11, 11) - dt.date.fromisoformat(t_["day"])).days < 7)
            check("c. a second filter 'day in last 7 days' (today fixed to 2026-11-11) narrows it; both in one plain sentence joined by AND", g2["n"] == n_recent and "usd less than $0 AND day in last 7 days" in g2["words"], (g2["n"], n_recent, g2["words"]))
            p.locator("#fMode").click()
            p.wait_for_timeout(150)
            g3 = p.evaluate(GRID)
            n_any = sum(1 for t_ in fxt if t_["usd"] < 0 or 0 <= (dt.date(2026, 11, 11) - dt.date.fromisoformat(t_["day"])).days < 7)
            check("c. 'Match any' turns AND into OR", g3["n"] == n_any and " OR " in g3["words"], (g3["n"], n_any))
            p.locator("#fChips .chip").nth(1).click()
            p.locator("#fClear").click() if p.evaluate("() => window.PINAKES.S.open.filters.length") != 1 else None
            p.wait_for_timeout(150)
            add_filter(p, "note", "has", "CAFÉ")
            g4 = p.evaluate(GRID)
            n_cafe = sum(1 for t_ in fxt if t_["usd"] < 0 and t_["note"] and "café" in t_["note"].lower())
            check("c. a text filter 'note contains \"CAFÉ\"' finds 'Café session' rows (case and accents handled)", g4["n"] == n_cafe and 'note contains "CAFÉ"' in g4["words"], (g4["n"], n_cafe))
            p.evaluate("() => { document.querySelector('#fBox').open = true; }")
            p.select_option("#fCol", "usd")
            p.select_option("#fOp", "gt")
            p.fill("#fVal", "lots")
            p.locator("#fAdd").click()
            p.wait_for_timeout(120)
            msg = p.evaluate("() => [document.querySelector('#fMsg').textContent, window.PINAKES.S.open.filters.length]")
            check("c. a filter with a word where a number goes is refused in plain words and changes nothing", msg == ["Type a number first.", 2], msg)
            p.locator("#fClear").click()
            p.wait_for_timeout(150)
            add_filter(p, "usd", "lt", "0")
            p.evaluate("() => { document.querySelector('#fBox').open = true; }")
            tt = AK.taps(p)
            check("c. table view (Rows tab, a filter on, the builder open): every tap target is at least 44 x 44 px, no sideways scroll, Jarvis's corner is free", not tt and AK.no_sideways(p) and not AK.corner(p), tt[:6])
            p.evaluate("() => window.scrollTo(0, 0)")
            # a row in full
            p.locator("#gbody .grow").first.click()
            p.wait_for_timeout(150)
            rc = p.evaluate("() => [document.querySelector('#rowCard').hidden, document.querySelector('#rowTitle').textContent, document.querySelectorAll('#rowKv dt').length, document.querySelectorAll('#gbody .grow.sel').length]")
            check("c. tap a row: its full record opens below (every field, hidden ones too)", rc[0] is False and rc[1].startswith("Row ") and rc[2] == p.evaluate("() => window.PINAKES.S.open.cols.length") and rc[3] == 1, rc)
            # stats
            p.locator("#tabStats").click()
            p.wait_for_timeout(200)
            sx = p.evaluate("() => { const li = document.querySelector('#statList li[data-k=usd]'); return [document.querySelectorAll('#statList li').length, li.textContent, document.querySelector('#statNote').textContent]; }")
            neg = [t_["usd"] for t_ in fxt if t_["usd"] < 0]
            check("c. Stats tab: one card per field; 'usd' shows count, distinct, sum, mean, min, max of the FILTERED rows in $", sx[0] == p.evaluate("() => window.PINAKES.S.open.cols.length") and f"Count{len(neg)}" in sx[1] and "Sum" + money(round(sum(neg), 2)) in sx[1]
                  and "Min" + money(min(neg)) in sx[1] and "Max" + money(max(neg)) in sx[1] and "after the filters" in sx[2], sx[1])
            # chart + group
            p.locator("#fClear").click() if False else None
            p.locator("#tabChart").click()
            p.wait_for_timeout(200)
            p.select_option("#cBy", "strat")
            p.select_option("#cY", "usd")
            p.wait_for_timeout(200)
            cx = p.evaluate("() => [document.querySelectorAll('#chart rect.bar').length, document.querySelector('#chartWords').textContent, [...document.querySelectorAll('#groupTable tbody tr')].map((r) => [...r.children].map((c) => c.textContent)), [...document.querySelectorAll('#groupTable thead th')].map((c) => c.textContent), document.querySelectorAll('#chart rect.bar.down').length]")
            want = {}
            for t_ in fxt:
                if t_["usd"] < 0:
                    want.setdefault(t_["strat"], [0, 0.0])
                    want[t_["strat"]][0] += 1
                    want[t_["strat"]][1] += t_["usd"]
            check("c. Chart tab: bars of the sum of 'usd' for each 'strat' (losses drawn in terracotta), the query in plain words, and the same numbers as a group table (rows, sum, mean)",
                  cx[0] == len(want) == cx[4] and cx[1] == 'The sum of "usd" for each "strat".' and cx[3] == ["strat", "rows", "sum", "mean"] and {r[0]: (r[1], r[2]) for r in cx[2]} == {k: (str(v[0]), money(round(v[1], 2))) for k, v in want.items()}, cx)
            p.select_option("#cBy", "day")
            p.select_option("#cBucket", "weekday")
            p.select_option("#cKind", "line")
            p.select_option("#cAgg", "count")
            p.wait_for_timeout(200)
            cl = p.evaluate("() => [document.querySelectorAll('#chart polyline.ln').length, [...document.querySelectorAll('#groupTable tbody tr')].map((r) => r.children[0].textContent), document.querySelector('#chartWords').textContent, document.querySelector('#cBucketFld').hidden]")
            check("c. a line of rows counted by weekday: Mon..Fri in order, 'Dates by' appears for a date field", cl[0] == 1 and cl[1] == [k for k in ("Mon", "Tue", "Wed", "Thu", "Fri") if any(dt.date.fromisoformat(t_["day"]).weekday() == i and t_["usd"] < 0 for t_ in fxt for i in [("Mon", "Tue", "Wed", "Thu", "Fri").index(k)])]
                  and "counted" in cl[2] and cl[3] is False, cl)
            p.select_option("#cKind", "hist")
            p.wait_for_timeout(200)
            ch = p.evaluate("() => [document.querySelectorAll('#chart rect.bar').length, [...document.querySelectorAll('#groupTable tbody tr')].reduce((s, r) => s + +r.children[2].textContent, 0), document.querySelector('#cByFld').hidden, document.querySelector('#chartWords').textContent]")
            check("c. a histogram of 'usd': 12 ranges that hold every filtered row", ch[0] == 12 and ch[1] == len(neg) and ch[2] is True and "spread" in ch[3], ch)
            AK.shot(p, "pinakes-chart")
            view_shot(p, "pinakes-chart-view")
            tc = AK.taps(p)
            check("c. Chart tab: every tap target is at least 44 x 44 px, no sideways scroll", not tc and AK.no_sideways(p), tc[:5])
            # saved views
            p.select_option("#cKind", "bar")
            p.fill("#vName", "Losers by weekday")
            p.locator("#vSave").click()
            p.wait_for_timeout(200)
            sv = p.evaluate("() => [document.querySelector('#viewsPill').textContent, [...document.querySelectorAll('#vList .trow')].map((b) => b.dataset.view), JSON.parse(window.PINAKES.raw()).views[0].view, document.querySelector('#status').textContent]")
            check("c. Save view: it is listed and kept on this phone (pinakes.v1) with the table, the filter, the sort and the chart", sv[0] == "1" and sv[1] == ["Losers by weekday"] and sv[2]["t"] == "demo-trades" and sv[2]["f"] == [{"col": "usd", "op": "lt", "value": "0"}]
                  and sv[2]["s"] == ["usd", "asc"] and sv[2]["c"]["by"] == "day" and sv[2]["tab"] == "chart" and "on this phone" in sv[3], sv)
            link = p.evaluate("() => location.href")
            p.locator("#tabRows").click()
            p.wait_for_timeout(200)
            # export
            with p.expect_download(timeout=20000) as dl:
                p.locator("#csvBtn").click()
            csv = open(dl.value.path(), encoding="utf-8-sig", newline="").read()
            check("c. Export CSV: the filtered rows only (a header + the losing trades), every field, unicode intact, named after the table", csv.count("\r\n") == len(neg) + 1 and csv.startswith("day,side,strat,qty,r,usd,risk_usd,held_min,win,entry.px,entry.hour,note")
                  and dl.value.suggested_filename == "demo-trades-filtered.csv" and ("Café" in csv or not any(t_["usd"] < 0 and t_["note"] and "Café" in t_["note"] for t_ in fxt)), csv[:160])
            with p.expect_download(timeout=20000) as dl:
                p.locator("#jsonBtn").click()
            ex = json.load(open(dl.value.path(), encoding="utf-8"))
            check("c. Export JSON: the same filtered rows, in the order shown (smallest $ first)", len(ex) == len(neg) and ex[0]["usd"] == min(neg) and all(r["usd"] < 0 for r in ex) and "entry.px" in ex[0], ex[:1])
            p.locator("#shareBtn").click()
            p.wait_for_timeout(300)
            sh = p.evaluate("() => [document.querySelector('#shareFld').hidden, document.querySelector('#shareOut').value, document.querySelector('#status').textContent]")
            check("c. Share link: the link is shown (and copied when the browser allows) and it is this page's own address with #v=", sh[0] is False and sh[1].startswith(origin + "/pinakes/") and "#v=" in sh[1] and ("copied" in sh[2] or "box below" in sh[2]), sh)
            # back, then the saved view, then the link in a fresh page
            p.locator("#back").click()
            p.wait_for_timeout(200)
            bk = p.evaluate("() => [document.querySelector('#catView').hidden, document.querySelector('#tabView').hidden, location.hash, document.querySelector('#saveBar').hidden]")
            check("c. Back to the catalogue: the list is back, the address is clean, the save bar is hidden", bk == [False, True, "", True], bk)
            p.locator("#vList .trow").first.click()
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view", timeout=20000)
            p.wait_for_timeout(300)
            rv = p.evaluate("() => { const o = window.PINAKES.S.open; return [o.card.id, o.view.length, o.sort, o.tab, document.querySelector('#panelChart').hidden, document.querySelector('#cBy').value, document.querySelector('#fWords').textContent]; }")
            check("c. tapping the saved view restores the table, its filter, sort, tab and chart", rv[0] == "demo-trades" and rv[1] == len(neg) and rv[2] == ["usd", "asc"] and rv[3] == "chart" and rv[4] is False and rv[5] == "day" and "usd less than $0" in rv[6], rv)
            with p.expect_download(timeout=20000) as dl:
                p.locator("#vExport").click()
            vfile = open(dl.value.path(), encoding="utf-8").read()
            check("c. Export views: a Pinakes views file with the saved view", json.loads(vfile)["app"] == "pinakes" and json.loads(vfile)["views"][0]["name"] == "Losers by weekday", vfile[:120])
            p.locator("#vList .del").first.click()
            p.wait_for_timeout(150)
            p.set_input_files("#vFile", {"name": "junk.json", "mimeType": "application/json", "buffer": b"not a views file"})
            p.wait_for_timeout(300)
            junk = p.evaluate("() => [document.querySelector('#status').textContent, document.querySelector('#viewsPill').textContent]")
            p.set_input_files("#vFile", {"name": "views.json", "mimeType": "application/json", "buffer": vfile.encode()})
            p.wait_for_timeout(300)
            im = p.evaluate("() => [document.querySelector('#viewsPill').textContent, [...document.querySelectorAll('#vList .trow')].map((b) => b.dataset.view), document.querySelector('#status').textContent]")
            check("c. delete, then import: a junk file is refused in plain words and changes nothing; the exported file brings the view back", "not a Pinakes views file" in junk[0] and junk[1] == "0" and im[0] == "1" and im[1] == ["Losers by weekday"] and "Imported 1 view" in im[2], (junk, im))
            check("c. the whole demo run sent nothing off the site and raised no console error", not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(link.replace("?demo=1", "?demo=1"))
            p.wait_for_function("window.PINAKES && window.PINAKES.ready()", timeout=120000, polling=300)
            p.wait_for_timeout(500)
            rl = p.evaluate("() => { const o = window.PINAKES.S.open; return o && o.view ? [o.card.id, o.view.length, o.sort, o.tab, o.filters, document.querySelector('#tabView').hidden, document.querySelector('#tName').textContent] : null; }")
            check("c. the share link in a fresh page restores the table, the filter, the sort and the tab", rl is not None and rl[0] == "demo-trades" and rl[1] == len(neg) and rl[2] == ["usd", "asc"] and rl[3] == "chart" and rl[4] == [{"col": "usd", "op": "lt", "value": "0"}] and rl[5] is False, rl)
            # the list picker on a nested demo file
            p.locator("#back").click()
            p.evaluate("() => window.PINAKES.open('demo-queue', null)")
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view && window.PINAKES.S.open.card.id === 'demo-queue'", timeout=20000)
            p.wait_for_timeout(200)
            pk = p.evaluate("() => [document.querySelector('#pathFld').hidden, [...document.querySelectorAll('#pathSel option')].map((o) => o.value), window.PINAKES.S.open.path, window.PINAKES.S.open.view.length]")
            p.select_option("#pathSel", "learnings")
            p.wait_for_timeout(250)
            pk2 = p.evaluate("() => [window.PINAKES.S.open.path, window.PINAKES.S.open.view.length, window.PINAKES.G.cols.map((c) => c.k), decodeURIComponent(location.hash)]")
            check("c. a file with two lists: the picker offers both ('queue/tasks' 12 rows, 'learnings' 8 rows); choosing the other one re-reads the table and the link remembers it",
                  pk[0] is False and pk[1] == ["queue/tasks", "learnings"] and pk[2] == "queue/tasks" and pk[3] == 12 and pk2[0] == "learnings" and pk2[1] == 8 and pk2[2] == ["d", "who", "text", "kind"] and '"p":"learnings"' in pk2[3], (pk, pk2))
            check("c. no console error in the fresh page", not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            # ---------------------------------------------------------------- 2. the REAL catalogue (plus the three test tables)
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?today={TODAY}")
            n_all = len(cat["tables"]) + 3
            r = p.evaluate("() => [document.querySelector('#demo').hidden, document.querySelector('#headline').textContent, document.querySelector('#totalNote').textContent, document.querySelectorAll('#list .trow').length, document.querySelector('#more').hidden, document.querySelector('#foundPill').textContent, [...document.querySelectorAll('#districts button')].map((b) => b.textContent)]")
            check(f"c. the real catalogue: no DEMO chip, '{n_all} tables, N rows', what is open here / needs the build / stays on the PC, 30 cards and 'Show more', a count on every drawer",
                  r[0] is True and r[1].startswith(f"{n_all} tables, ") and "open right here" in r[2] and "kept on the PC" in r[2] and r[3] == 30 and r[4] is False and r[5] == f"All {n_all}"
                  and r[6][1:] == [f"{d}{cat['counts'][d]['tables'] + (3 if d == 'Command' else 0)}" for d in PB.DISTRICTS], r)
            p.locator("#more").click()
            p.wait_for_timeout(150)
            check("c. 'Show more' adds the next 30", p.evaluate("() => document.querySelectorAll('#list .trow').length") == 60, None)
            for _ in range(10):
                if p.evaluate("() => document.querySelector('#more').hidden"):
                    break
                p.locator("#more").click()
                p.wait_for_timeout(80)
            badges = p.evaluate("() => { const m = {}; for (const b of document.querySelectorAll('#list .trow')) { const t = b.querySelector('.pill').textContent.split(' · ')[0]; m[t] = (m[t] || 0) + 1; } return m; }")
            n_demo = sum(1 for c in cat["tables"] if c["label"] == "demo")
            check("c. every card has an honest badge: DEMO for the fixtures, 'Site build' for files not built here, 'On the PC' for research data, Published / STALE (by its own date stamp) for the rest",
                  badges.get("DEMO") == n_demo and badges.get("Site build") == cat["totals"]["build_tables"] and badges.get("On the PC") == cat["totals"]["research_tables"] and badges.get("Published", 0) + badges.get("STALE", 0) + badges.get("SAMPLE", 0) == n_all - n_demo - cat["totals"]["build_tables"] - cat["totals"]["research_tables"], badges)
            # the real Odeon trades from their own URL
            p.fill("#q", "odeon trades")
            p.wait_for_timeout(150)
            p.locator("#list .trow[data-id=odeon-trades]").click()
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view", timeout=30000)
            p.wait_for_timeout(300)
            od = json.load(open(os.path.join(AK.WEB, "odeon", "trades.json"), encoding="utf-8"))["trades"]
            ro = p.evaluate("() => { const o = window.PINAKES.S.open; return [o.view.length, o.cols.length, window.PINAKES.G.cols.length, document.querySelector('#colSum').textContent, document.querySelector('#tSrc').textContent, [...document.querySelectorAll('#tPills .pill')].map((x) => x.textContent)]; }")
            shown = p.evaluate("() => window.PINAKES.G.cols.map((c) => c.k)")
            check("c. 'Trades (Odeon)' loads from its real file odeon/trades.json (never a copy): every trade, 14 fields shown of the many it has, dates / $ / R first (day, usd, r are in; the bar arrays are one tap away)",
                  ro[0] == len(od) and ro[1] > 30 and ro[2] == 14 and {"day", "usd", "r", "risk_usd"} <= set(shown) and "bars.c" not in shown and ro[3] == f"Fields shown: 14 of {ro[1]}" and "odeon/trades.json" in ro[4] and any("odeon/trades.json" in u for u in seen) and f"{len(od)} rows" in ro[5], ro)
            if os.environ.get("AGORA_SHOTS"):
                p.evaluate("() => document.querySelector('#count').scrollIntoView()")
                view_shot(p, "pinakes-grid-view")
                p.evaluate("() => window.scrollTo(0, 0)")
            p.evaluate("() => { document.querySelector('#colBox').open = true; }")
            p.locator("#colChips .btn[data-k=usd]").click()
            p.wait_for_timeout(150)
            hc = p.evaluate("() => [window.PINAKES.G.cols.map((c) => c.k).includes('usd'), document.querySelector('#colChips .btn[data-k=usd]').getAttribute('aria-pressed')]")
            p.locator("#colChips .btn[data-k=usd]").click()
            check("c. 'Fields shown': tapping the 'usd' field hides its column (tap again and it is back)", hc == [False, "false"] and p.evaluate("() => window.PINAKES.G.cols.map((c) => c.k).includes('usd')"), hc)
            # ---------------------------------------------------------------- 3. ten thousand rows
            p.evaluate("() => window.PINAKES.open('zz-big', null)")
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view && window.PINAKES.S.open.card.id === 'zz-big'", timeout=60000)
            p.wait_for_timeout(300)
            g = p.evaluate(GRID)
            check("c. 10,000 rows: all of them are in the table but only a window of row elements exists (under 40), the scroll area is 400,000 px tall", g["n"] == 10000 and g["dom"] <= 40 and g["h"] == "400000px" and g["cols"] == ["i", "day", "usd", "r", "grp", "txt", "ok"], g)
            p.evaluate("() => { document.querySelector('#grid').scrollTop = 7777 * 40; }")
            p.wait_for_timeout(250)
            mid = p.evaluate(CELL, 7780)
            rw = big["rows"][7780]
            check("c. jump to row 7,780: it is drawn with the right values (the window follows the scroll)", mid is not None and mid[0] == "7,780" and mid[1] == rw["day"] and mid[2] == money(rw["usd"]) and mid[4] == rw["grp"] and mid[6] == ("yes" if rw["ok"] else "no")
                  and p.evaluate("() => document.querySelectorAll('#gbody .grow').length") <= 40, (mid, rw))
            p.evaluate("() => { document.querySelector('#grid').scrollTop = 10000 * 40; }")
            p.wait_for_timeout(250)
            last = p.evaluate(CELL, 9999)
            check("c. the very last row (9,999) is reachable and drawn", last is not None and last[0] == "9,999", last)
            bench = p.evaluate("() => window.PINAKES.bench(120)")
            check(f"c. scrolling 10,000 rows: a repaint (with layout) takes {bench['median']:.1f} ms median, {bench['p95']:.1f} ms at the 95th percentile, in software-rendered Chromium: inside the 16.7 ms a 60 fps frame allows; {bench['dom']} row elements, {bench['cells']} cells",
                  bench["median"] < 16.7 and bench["p95"] < 33 and bench["dom"] <= 40 and bench["rows"] == 10000, bench)
            t0 = p.evaluate("() => performance.now()")
            p.locator("#ghead .gh[data-k=usd]").click()
            p.wait_for_timeout(50)
            add_filter(p, "txt", "has", "ÜNÏ")
            t1 = p.evaluate("() => performance.now()")
            gb = p.evaluate(GRID)
            want_big = [r_ for r_ in big["rows"] if r_["txt"] and "ünï" in r_["txt"].lower()]
            top = p.evaluate(CELL, 0)
            check("c. sort 10,000 rows by $ and filter them by text with accents: the right rows, biggest $ first", gb["n"] == len(want_big) and top[2] == money(max(r_["usd"] for r_ in want_big)) and gb["dom"] <= 40, (gb["n"], len(want_big), top))
            p.locator("#fClear").click()
            p.locator("#tabStats").click()
            p.wait_for_timeout(400)
            sb = p.evaluate("() => document.querySelector('#statList li[data-k=usd]').textContent")
            tot = sum(r_["usd"] for r_ in big["rows"])
            check("c. stats over all 10,000 rows: the exact sum in $, count, distinct", "Count10,000" in sb and "Sum" + money(tot) in sb and "Distinct1,001" in sb and "Min-$500" in sb and "Max$500" in sb, sb)
            p.locator("#tabChart").click()
            p.select_option("#cBy", "day")
            p.select_option("#cBucket", "month")
            p.select_option("#cKind", "line")
            p.wait_for_timeout(400)
            cm = p.evaluate("() => [document.querySelectorAll('#chart polyline.ln').length, document.querySelector('#chartNote').textContent, document.querySelectorAll('#groupTable tbody tr').length]")
            check("c. 10,000 rows grouped by month as a line: 72 months, the list capped at 50 and it says so", cm[0] == 1 and "72 groups from 10,000 rows" in cm[1] and "first 50" in cm[1] and cm[2] == 50, cm)
            p.locator("#tabRows").click()
            with p.expect_download(timeout=30000) as dl:
                p.locator("#csvBtn").click()
            big_csv = open(dl.value.path(), encoding="utf-8-sig", newline="").read()
            check("c. export all 10,000 rows as CSV: 10,001 lines, unicode intact", big_csv.count("\r\n") == 10001 and "ünï ✓" in big_csv, big_csv[:80])
            check("c. no console error through the big-table run", not errs and not off, (errs[:3], off[:3]))
            # the biggest real table: 37,000 rows from datacity/city.json
            p.evaluate("() => window.PINAKES.open('datacity-city~skyline-rows', null)")
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view && window.PINAKES.S.open.card.id === 'datacity-city~skyline-rows'", timeout=90000)
            p.wait_for_timeout(300)
            sk = p.evaluate(GRID)
            bs = p.evaluate("() => window.PINAKES.bench(60)")
            check(f"c. the biggest real table (Data City skyline, {sk['n']:,} rows from the 2.4 MB city.json): still under 40 row elements, repaint {bs['median']:.1f} ms median",
                  sk["n"] == next(c["rows"] for c in cat["tables"] if c["id"] == "datacity-city~skyline-rows") and sk["dom"] <= 40 and bs["median"] < 16.7 and p.evaluate("() => document.querySelector('#pathFld').hidden") is False, (sk["n"], bs))
            # the Archive runs: a packed grid unpacked into named fields
            p.evaluate("() => window.PINAKES.open('archive-index', null)")
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view && window.PINAKES.S.open.card.id === 'archive-index'", timeout=60000)
            p.wait_for_timeout(200)
            add_filter(p, "verdict", "is", "adopted")
            ix = json.load(open(os.path.join(AK.WEB, "archive", "index.json"), encoding="utf-8"))
            av = p.evaluate("() => [window.PINAKES.S.open.view.length, window.PINAKES.S.open.cols.map((c) => c.k + ':' + c.t).filter((x) => /m26\\.(net|pf)|verdict/.test(x))]")
            check("c. the Archive runs (packed as lists in the file) open as named fields; 'verdict is exactly \"adopted\"' finds the adopted runs kept in the index",
                  av[0] == sum(1 for r_ in ix["runs"] if r_[4] == 0) and av[1] == ["verdict:text", "m26.pf:number", "m26.net:usd"], av)
            # ---------------------------------------------------------------- 4. tables that cannot be opened say why
            for tid, frag, extra in (("zz-broken", "not valid JSON", ""), ("zz-missing", "was not found on this site (404)", ""), ("home", "written by the site build", "home.json"), ("research-nq-5m", "kept on the PC", "data/NQ_5m.csv")):
                p.evaluate("(id) => window.PINAKES.open(id, null)", tid)
                p.wait_for_timeout(900)
                wy = p.evaluate("() => [document.querySelector('#tWhy').hidden, document.querySelector('#tWhy').textContent, document.querySelector('#work').hidden, document.querySelector('#saveBar').hidden, document.querySelector('#tName').textContent, document.querySelector('#tCols').textContent]")
                check(f"c. a table that cannot be opened says why ({tid}: '{frag}'), shows no grid and offers nothing to save; never a blank screen", wy[0] is False and frag in wy[1] and extra in wy[1] and wy[2] is True and wy[3] is True and len(wy[4]) > 2, wy)
            rs = p.evaluate("() => [document.querySelector('#tCols').hidden, document.querySelector('#tCols').textContent, [...document.querySelectorAll('#tPills .pill')].map((x) => x.textContent)]")
            check("c. a research dataset shows its span, its row count and its fields, and no export", rs[0] is False and "time (date)" in rs[1] and "354,333 rows" in rs[1] and rs[2][0].startswith("On the PC") and "2021-" in rs[2][0] and "to 2026-" in rs[2][0], rs)
            AK.shot(p, "pinakes-research")
            view_shot(p, "pinakes-research-view")
            check("c. the failures raised no console error (a 404 is an answer, not a crash)", not errs and not off, (errs[:3], off[:3]))
            # ---------------------------------------------------------------- 5. Ask on the real files
            p.locator("#back").click()
            p.wait_for_timeout(150)
            p.locator("#asks [data-ask=weekday]").click()
            p.wait_for_function("() => window.PINAKES.S.ask && window.PINAKES.S.ask.id === 'weekday'", timeout=30000)
            p.wait_for_timeout(200)
            aw = p.evaluate("() => [document.querySelector('#askWords').textContent, document.querySelector('#askSrc').textContent, [...document.querySelectorAll('#askTable tbody tr')].map((r) => [...r.children].map((c) => c.textContent)), document.querySelector('#askChart').hidden, document.querySelectorAll('#askChart rect.bar').length, [...document.querySelectorAll('#askTable thead th')].map((c) => c.textContent)]")
            wd = {}
            for t_ in od:
                k = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.date.fromisoformat(t_["day"]).weekday()]
                wd.setdefault(k, [0, 0.0])
                wd[k][0] += 1
                wd[k][1] += t_["usd"]
            check("c. Ask '$ by weekday from trades' on the real Odeon file: the query in plain words, where it read from, a bar chart, and a table equal to a plain Python count ($ next to R)",
                  "Group the trades by the weekday" in aw[0] and "Trades (Odeon)" in aw[1] and f"{len(od)} rows" in aw[1] and "DEMO" not in aw[1] and aw[3] is False and aw[4] == len(wd) and aw[5] == ["weekday", "trades", "usd", "avg_usd", "r"]
                  and [(r_[0], r_[1], r_[2]) for r_ in aw[2]] == [(k, str(wd[k][0]), money(round(wd[k][1], 2))) for k in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun") if k in wd], aw[2])
            p.locator("#asks [data-ask=verdicts]").click()
            p.wait_for_function("() => window.PINAKES.S.ask && window.PINAKES.S.ask.id === 'verdicts'", timeout=60000)
            p.wait_for_timeout(200)
            avd = p.evaluate("() => [window.PINAKES.S.ask.rows.reduce((s, r) => s + r.runs, 0), window.PINAKES.S.ask.from.length, document.querySelector('#askNote').textContent]")
            check(f"c. Ask 'runs by verdict per family' joins the Archive's 5 files: {avd[0]:,} runs = the Archive's own total", avd[0] == ix["counts"]["runs"] and avd[1] == 5 and "families" in avd[2], avd)
            p.locator("#asks [data-ask=deals]").click()
            p.wait_for_function("() => window.PINAKES.S.ask && window.PINAKES.S.ask.id === 'deals'", timeout=30000)
            p.wait_for_timeout(200)
            adl = p.evaluate("() => [document.querySelector('#askSrc').textContent, window.PINAKES.S.ask.demo, window.PINAKES.S.ask.from, window.PINAKES.S.ask.rows.map((r) => r.days_left)]")
            check("c. Ask 'deals ending this week': money/mercury.json is not built here, so it says so and uses a stand-in clearly labelled DEMO (never passed off as real)",
                  adl[0].startswith("DEMO data (not real).") and "written by the site build" in adl[0] and "labelled stand-in" in adl[0] and adl[1] is True and adl[2] == ["mercury-fixture"] and all(0 <= x <= 7 for x in adl[3]) and adl[3] == sorted(adl[3]), adl)
            AK.shot(p, "pinakes-ask")
            view_shot(p, "pinakes-ask-view")
            ta = AK.taps(p)
            check("c. catalogue view with an answer open: every tap target is at least 44 x 44 px, no sideways scroll, no console error, nothing off the origin", not ta and AK.no_sideways(p) and not errs and not off, (ta[:5], errs[:3], off[:3]))
            ctx.close()
            # the built site: money/mercury.json exists -> the real (sample) feed is used and labelled SAMPLE
            feed = {"v": 1, "id": "mercury", "asof": "2026-11-11T06:00:00Z", "mode": "paper", "status": "sample", "headline": {"text": "x", "usd_month": 10}, "notes": [],
                    "items": [{"title": "Ends tomorrow", "detail": "d", "usd": 12.5, "score": 70, "risk": "low", "expires": "2026-11-12"}, {"title": "Next month", "detail": "d", "usd": 5, "score": 20, "risk": "low", "expires": "2026-12-20"}]}
            ch_feed = dict(feed, id="chrysos", items=[{"title": "Chrysos deal", "detail": "d", "usd": 40, "score": 60, "risk": "med", "expires": "2026-11-15"}, {"title": "No date", "detail": "d", "usd": 1, "score": 1, "risk": "low"}])
            srv2, origin2 = AK.serve(dict(over, **{"/money/mercury.json": json.dumps(feed), "/money/chrysos.json": json.dumps(ch_feed)}))
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, f"?today={TODAY}")
            p.locator("#asks [data-ask=deals]").click()
            p.wait_for_function("() => window.PINAKES.S.ask && window.PINAKES.S.ask.id === 'deals'", timeout=30000)
            p.wait_for_timeout(200)
            ab = p.evaluate("() => [document.querySelector('#askSrc').textContent, window.PINAKES.S.ask.from, window.PINAKES.S.ask.rows.map((r) => [r.title, r.days_left, r.usd])]")
            check("c. on a built site the same question joins money/mercury.json and money/chrysos.json, says SAMPLE (their own status) and keeps only this week's dated deals",
                  ab[0].startswith("SAMPLE data.") and ab[1] == ["money-mercury", "money-chrysos"] and ab[2] == [["Ends tomorrow", 1, 12.5], ["Chrysos deal", 4, 40]], ab)
            p.evaluate("() => window.PINAKES.open('money-mercury', null)")
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view", timeout=30000)
            p.wait_for_timeout(200)
            bm = p.evaluate("() => [window.PINAKES.S.open.view.length, window.PINAKES.S.open.cols.map((c) => c.k + ':' + c.t), [...document.querySelectorAll('#tPills .pill')].map((x) => x.textContent)[0], document.querySelector('#status').textContent]")
            check("c. a 'Site build' table, once it exists, is measured when opened: rows, typed fields ($, date), and it is labelled SAMPLE with its age because the file says so",
                  bm[0] == 2 and "usd:usd" in bm[1] and "expires:date" in bm[1] and bm[2].startswith("SAMPLE") and "hours old" in bm[2] and "SAMPLE data" in bm[3] and not errs, bm)
            ctx.close()
            srv2.shutdown()
            # no catalogue at all -> the DEMO, never blank
            srv3, origin3 = AK.serve({"/pinakes/catalog.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, f"?today={TODAY}")
            nb = p.evaluate("() => [document.querySelector('#demo').hidden, document.querySelectorAll('#list .trow').length, document.querySelector('#status').textContent]")
            check("c. catalog.json missing (404) -> the DEMO catalogue with a plain reason, never blank, no console error", nb[0] is False and nb[1] == 7 and "could not be read" in nb[2] and "DEMO" in nb[2] and not errs, (nb, errs[:2]))
            p.locator("#asks [data-ask=kalshi]").click()
            p.wait_for_function("() => window.PINAKES.S.ask && window.PINAKES.S.ask.id === 'kalshi'", timeout=30000)
            check("c. Ask works on the demo catalogue too and says DEMO", p.evaluate("() => document.querySelector('#askSrc').textContent").startswith("DEMO data (not real)."), None)
            ctx.close()
            srv3.shutdown()
            # ---------------------------------------------------------------- 6. 375 x 667, LITE, reduced motion
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, f"?demo=1&today={TODAY}&q=low")
            lt = p.evaluate("() => [window.PINAKES.S.sceneMode, document.querySelector('#lite').hidden, document.querySelector('#cab').hidden, document.querySelectorAll('#cabFlat .drawer').length]")
            check("c. 375 x 667, LITE, reduced motion: the flat cabinet (no WebGL at all), the LITE chip", lt == ["flat", False, True, 5], lt)
            p.locator("#districts [data-d=Life]").click()
            p.wait_for_timeout(200)
            fl = p.evaluate("() => [document.querySelectorAll('#cabFlat .drawer.on').length, [...document.querySelectorAll('#list .trow')].map((b) => b.dataset.id)]")
            check("c. LITE: tapping a district pulls its flat drawer out and lists its tables", fl == [1, ["demo-habits"]], fl)
            check("c. 375 x 667 catalogue: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            p.locator("#list .trow[data-id=demo-habits]").click()
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view", timeout=20000)
            p.wait_for_timeout(250)
            add_filter(p, "done", "no")
            add_filter(p, "minutes", "empty")
            hb = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))["data"]["habits"]["days"]
            sm = p.evaluate(GRID)
            check("c. 375 x 667 table: yes / no and 'is empty' filters work ('done is no AND minutes is empty'), the grid fits, no sideways scroll, every tap >= 44 px, no error",
                  sm["n"] == sum(1 for x in hb if x["done"] is False and x["minutes"] is None) and "done is no AND minutes is empty" in sm["words"] and AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs, (sm, AK.taps(p)[:3], errs[:2]))
            p.evaluate("() => window.scrollTo(0, 0)")
            p.locator("#tabStats").click()
            p.wait_for_timeout(150)
            p.locator("#tabChart").click()
            p.wait_for_timeout(200)
            check("c. 375 x 667 Stats and Chart tabs: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "pinakes-375")
            view_shot(p, "pinakes-375-view")
            ctx.close()
            # ?flat=1 at full quality, and storage blocked
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });")
            AK.open_app(p, origin, APP, f"?demo=1&flat=1&today={TODAY}")
            p.locator("#list .trow[data-id=demo-runs]").click()
            p.wait_for_function("() => window.PINAKES.S.open && window.PINAKES.S.open.view", timeout=20000)
            p.locator("#vSave").click()
            p.wait_for_timeout(200)
            blk = p.evaluate("() => [window.PINAKES.S.sceneMode, document.querySelector('#status').textContent, document.querySelector('#viewsPill').textContent]")
            check("c. ?flat=1 draws the flat cabinet; with browser storage blocked the page still works and says the view is kept for this visit only", blk[0] == "flat" and "this visit only" in blk[1] and blk[2] == "1" and not [e for e in errs if "blocked" not in e], (blk, errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


def view_shot(p, name, top=False):
    """What the phone shows right now (only when AGORA_SHOTS=<dir> is set); any full-screen overlay of the kit is hidden for the picture only."""
    d = os.environ.get("AGORA_SHOTS")
    if not d:
        return
    os.makedirs(d, exist_ok=True)
    if top:
        p.evaluate("() => window.scrollTo(0, 0)")
    p.evaluate("() => { for (const e of document.querySelectorAll('body *')) { const cs = getComputedStyle(e); if (cs.position === 'fixed' && e.getBoundingClientRect().height >= innerHeight * 0.9 && !e.closest('#app')) e.style.visibility = 'hidden'; } }")
    p.wait_for_timeout(600)
    p.screenshot(path=os.path.join(d, name + ".png"))


def money(v):
    a = abs(v)
    whole = abs(a - round(a)) < 0.005
    s = f"{round(a):,}" if whole else f"{a:,.2f}"
    return ("-" if v < 0 and float(s.replace(",", "")) != 0 else "") + "$" + s


def PB_r(v):
    return ("+" if v > 0 else "") + f"{v:.2f}R"


if __name__ == "__main__":
    test_static()
    test_core()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
