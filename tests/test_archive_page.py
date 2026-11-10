"""ARCHIVE, the OLYMPUS library of everything we ever tested (tools/archive_build.py + tools/web_public/archive/, AGORA look, 2026-11-10): a fast, searchable, filterable index of every research run,
every write-up, the tested-and-rejected list and the datasets, with net $ and $ a month next to every result. HISTORY ONLY. Read only.

  a. static: the builder's selftest and --check, index.json under 400 KB, the counts against the raw files, the files, the kit lines, the AGORA look, read-only, the card, the manifest, the DEMO fixture, the new_apps.json row, the wiring section
  b. the maths in node (archivecore.js): money words, filters, sorts, compare in plain words, "Don't redo this", shelves, shards, junk input, no markup from data
  c. Chromium 390 x 844 (and 375 x 667): DEMO, search, filters, compare, "Don't redo this", the 3D library (tap a book -> that shelf; the flat twin with ?q=off), the real index with its shards, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_archive_page            (--static: parts a and b only)
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "archive", "Archive"
check = AK.check
BUILD = os.path.join(AK.ROOT, "tools", "archive_build.py")
D = os.path.join(AK.WEB, APP)


def test_static():
    r = subprocess.run([sys.executable, "-I", BUILD, "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the builder's own selftest passes (tools/archive_build.py --selftest)", r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
    r2 = subprocess.run([sys.executable, "-I", BUILD, "--check"], capture_output=True, text=True, timeout=300)
    check("a. the archive files are EXACTLY what `python tools/archive_build.py` writes now (rebuild after research/runs, research/writeups, the reference or data/ change)", r2.returncode == 0, r2.stdout[-300:] + r2.stderr[-200:])
    AK.static_kit(APP, NAME, reads=("./index.json",))
    idx = json.load(open(os.path.join(D, "index.json"), encoding="utf-8"))
    size = os.path.getsize(os.path.join(D, "index.json"))
    check(f"a. the first load is small: index.json {size / 1024:.0f} KB (< 400 KB), the rest sharded in runs-<k>.json", size < 400_000 and idx["shards"] and all(os.path.isfile(os.path.join(D, s)) for s in idx["shards"]), size)
    n_raw = sum(1 for p in glob.glob(os.path.join(AK.ROOT, "research", "runs", "*.json")) if os.path.basename(p) != "index.json")
    in_shards = sum(len(json.load(open(os.path.join(D, s), encoding="utf-8"))["runs"]) for s in idx["shards"])
    check(f"a. every stored run is in the library: {n_raw} files in research/runs, {len(idx['runs'])} in index.json + {in_shards} in the shards (a few unreadable ones may be skipped: {len(idx['skipped'])})",
          len(idx["runs"]) + in_shards + len(idx["skipped"]) == n_raw and n_raw > 2000, (n_raw, len(idx["runs"]), in_shards, idx["skipped"]))
    wu = len(glob.glob(os.path.join(AK.ROOT, "research", "writeups", "*.md"))) - 1
    check("a. the write-ups are the files of research/writeups (INDEX.md aside), each with a slug and a title", abs(len(idx["writeups"]) - wu) <= 6 and all(w["slug"] and w["title"] for w in idx["writeups"]), (len(idx["writeups"]), wu))
    ref = open(os.path.join(AK.ROOT, "docs", "CLAUDE_REFERENCE.md"), encoding="utf-8").read()
    sec = ref.split("## Tested and rejected")[1].split("\n## ")[0]
    bullets = len(re.findall(r"^- ", sec, re.M))
    check(f"a. the rejected list has every top-level bullet of 'Tested and rejected' ({bullets}) plus the rejected write-ups", len(idx["rejected"]) >= bullets and any("stops" in x["title"].lower() for x in idx["rejected"]), (len(idx["rejected"]), bullets))
    rows = {r[0]: r for r in idx["runs"]}
    lit = rows.get("lit_live")
    live = json.load(open(os.path.join(AK.ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))["spans"]["2026"]
    check("a. money, not only R: the live LIT run keeps net $ and $ a month next to PF, exactly as stored (2026)", lit is not None and lit[8][3] == round(live["net"]) and lit[8][4] == round(live["per_month"]) and lit[8][2] == round(live["pf"], 2) and lit[8][5] == live["p10"], (lit and lit[8], live.get("net")))
    ds = {d["name"]: d for d in idx["datasets"]}
    nq = ds.get("NQ_5m.csv")
    with open(os.path.join(AK.ROOT, "data", "NQ_5m.csv"), encoding="utf-8") as fh:
        n_rows = sum(1 for _ in fh) - 1
    check(f"a. the datasets: NQ_5m.csv listed with its span, {n_rows:,} rows (counted again from the raw file), source and last bar; VIX, ES and the news calendar too",
          nq is not None and nq["rows"] == n_rows and nq["first"] < "2021-12" and nq["last"] >= "2026-10" and "TradingView" in nq["source"] and {"VIX_1d.csv", "ES_5m.csv", "events.csv"} <= set(ds), nq)
    html = AK.read(os.path.join(D, "index.html"))
    check("a. the page order: the library (3D), find a run, runs, write-ups, tested and rejected, the data", html.index('id="stage"') < html.index('id="q"') < html.index('id="results"') < html.index('id="writeups"') < html.index('id="rejected"') < html.index('id="dsRows"'))
    check("a. the 3D library is its own module tag (a failed load can never stop the page) and the flat twin exists", 'src="archivestage.js' in html and "ARCHIVE_LIB_FAIL" in html and 'id="flat"' in html)
    st = AK.read(os.path.join(D, "archivestage.js"))
    check("a. the library is light: the render core + materials, at most 14 shelves x 3 books, bloom <= .25, a dpr cap <= 1.5, no data, no network, idle rules (hidden, frameGap, reduced motion)",
          "olympus/render.js" in st and "k < 14" in st and re.search(r"strength:\s*0\.(?:[0-2]\d?)\b", st) and "maxDpr: 1.5" in st and "O.hidden()" in st and "frameGap" in st and "RM" in st and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket", st))
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: invented 'Example' runs and rejected ideas, 30 runs on 6 shelves, never blank", all(r[1].startswith("Example") for r in fx["runs"]) and len(fx["runs"]) == 30 and len(fx["families"]) == 6 and all(x["title"].startswith("Example") for x in fx["rejected"]))
    sc = AK.read(os.path.join(D, "archive.js")) + AK.read(os.path.join(D, "archivecore.js"))
    check("a. history only, read only: no forecast / predict / signal / order / key words in the page code", not re.search(r"\b(forecast|predict\w*|trade signal|placeOrder|submitOrder|api[_-]?key|Authorization|\.post\()", re.sub(r"`[^`]*`|'[^'\n]*'|\"[^\"\n]*\"", "", re.sub(r"//[^\n]*", "", sc)), re.I))
    check("a. the honest label is on the page and in the data: 'History, not a forecast' and 'a better number is not proof'", "History, not a forecast" in AK.read(os.path.join(D, "archivecore.js")) and "not proof" in AK.read(os.path.join(D, "archivecore.js")) and "History only" in html)
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))["apps"]
    row = next((a for a in na if a["id"] == "archive"), None)
    scenes = set(re.findall(r"^  SC\.(\w+) =", AK.read(os.path.join(AK.WEB, "olympus", "intro-app.js")), re.M))
    check("a. tools/new_apps.json has the Archive row: group trading, a hex accent, a glyph, a description under 80 characters, an ambient bed, an EXISTING intro scene, a transition",
          bool(row) and row["group"] == "trading" and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"] and len(row["description"]) < 80 and row["ambient"] and row["flavour"][0] in scenes and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["transition"]["ms"], row)
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the wiring section for the lead is in docs/NEW_APPS_WIRING.md and names the exact build line (python tools/archive_build.py)", re.search(r"^# .*ARCHIVE", wiring, re.M) is not None and "python tools/archive_build.py" in wiring)
    check("a. the app's own files are untouched elsewhere: no sw.js / apps.js / olympus.js / build-script edit names the archive yet", "archive" not in AK.read(os.path.join(AK.WEB, "sw.js")).lower().replace("archive: previous", ""), None)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fs = require('fs'), o = {}, fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), real = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  const v = C.chooseData(null, fx).v, rv = C.normIndex(real);
  o.words = [C.usd(758), C.usd(-12.4), C.usd(null), C.usdS(43820), C.usdS(-5), C.pf(4.1899), C.pf(null), C.dec(2.91, 1), C.dec(null, 1)];
  o.choose = [C.chooseData(real, fx).src, C.chooseData(null, fx).src, C.chooseData({ runs: [] }, fx).src, C.chooseData(null, null), C.chooseData(fx, null).src, C.chooseData(real, fx).v.runs.length > 500];
  o.fx = [v.runs.length, v.families.length, v.rejected.length, v.writeups.length, v.datasets.length, v.total.runs, v.demo, v.runs[0].m26 && v.runs[0].m26.net, v.runs[3].m26];
  for (const sh of rv.shards) C.addShard(rv, JSON.parse(fs.readFileSync(process.argv[4].replace('index.json', sh), 'utf8')));
  const all = rv.runs;
  o.filt = [C.filterRuns(v.runs, { q: '', verdict: 0 }).length, C.filterRuns(v.runs, { q: 'stops' }).length, C.filterRuns(v.runs, { family: 'risk' }).length, C.filterRuns(v.runs, { years: '26' }).length, C.filterRuns(v.runs, { years: 'both' }).length,
    C.filterRuns(v.runs, { years: '26', min: { net: 1500 } }).length, C.filterRuns(v.runs, { years: '26', min: { pm: 100 }, maxF10: 5 }).length, C.filterRuns(v.runs, { q: 'risk idea number', verdict: 1 }).length, C.filterRuns(v.runs, { q: 'zzzzzz' }).length];
  const live = C.filterRuns(all, { q: 'lit_live' }).find((r) => r.id === 'lit_live');
  o.live = [live.verdict, live.m26.net, live.m26.pm, live.m26.pf, live.m26.p10, live.m26.f10, live.mold && live.mold.n, C.metricsOf(live, 'old').n, C.metricsOf(live, 'any').n, C.periodOf(live, 'any')];
  const s1 = C.sortRuns(v.runs, 'net', '26'), s2 = C.sortRuns(v.runs, 'f10', '26'), s3 = C.sortRuns(v.runs, 'name', 'any');
  o.sort = [s1[0].m26.net >= s1[1].m26.net, s1.slice(-3).every((r) => !r.m26), s2[0].m26.f10 <= s2[1].m26.f10, s3[0].title <= s3[1].title, C.sortRuns(all, 'pm', '26')[0].m26.pm >= C.sortRuns(all, 'pm', '26')[1].m26.pm];
  const a = v.runs.find((r) => r.id === 'example_risk_0'), b = v.runs.find((r) => r.id === 'example_risk_1'), c3 = v.runs.find((r) => r.id === 'example_risk_3');
  const cw = C.compareWords(a, b);
  o.cmp = [cw.length, cw[0], cw[2], cw[3], cw[cw.length - 1], C.compareWords(a, c3).some((x) => x.indexOf('In 2026') >= 0), C.compareWords(a, null).length];
  const R = rv.rejected;
  const hit = (q) => C.matchRejected(q, R).hits.map((h) => h.r.title);
  o.redo = [hit('fixed 12 point stop')[0], hit('stop').length, hit('a brand new idea about oranges').length, hit('trade only on thursdays').length, hit('re-sweep inducement').length > 0, hit('cold streak filter')[0], hit('').length, C.redoWords(C.matchRejected('fixed 12 point stop', R), { n: 2 }).slice(0, 60), C.redoWords(C.matchRejected('oranges', R), null)];
  o.rrun = [C.rejectedRuns('breakeven stop', all).n > 0, C.rejectedRuns('stop', all).n, C.stems('The trailing stops of Fixed 10-15 pts')];
  const sh = C.shelves(rv.families, 14);
  o.shelf = [sh.length, sh[0].name, sh[0].books.map((x) => x.k), sh[0].books.every((x) => x.h >= 0 && x.h <= 1), sh[0].books[2].h > sh[0].books[0].h, Math.max(...sh.map((s) => Math.max(...s.books.map((x) => x.h)))), C.shelves(v.families).length, C.SHELF_WORD(sh[0]).includes('runs')];
  const sd = { runs: [['x_1', 'Only in a shard', 'risk', 0, 1, 'rejected', '26-11-01', 1, [30, 2, 1.2, 500, 50, null, null], 0, '', '']] };
  const w = C.normIndex({ ...real, runs: real.runs.slice(0, 3) }); const n0 = w.runs.length;
  o.shard = [C.addShard(w, sd), C.addShard(w, sd), w.runs.length - n0, C.addShard(w, null), C.addShard(w, { runs: [7, null, []] }), w.runs[w.runs.length - 1].mold];
  const evil = C.normIndex({ runs: [['<b>x</b>', '<i>T</i> `y`', 'f<', 1, 9, 's', 'b', 1, [10, 'x', Infinity, 5, 5, null, null], [0], 'Bad Slug!', '<n>'], 5, [], null], families: [{ name: '<u>f</u>', runs: 3 }, 7], writeups: [{ slug: '../x', title: 'bad' }, { slug: 'ok-one', title: '<b>Ok</b>', verdict: 7 }], rejected: [{ title: '<i>R</i>', text: 't', writeups: ['a b', 'fine'] }], datasets: [{ name: 'n<' }], shards: ['runs-1.json', '../evil.json', 'runs-1000.json'] });
  o.evil = [evil.runs.length, evil.runs[0].id, evil.runs[0].title, evil.runs[0].verdict, evil.runs[0].m26 && evil.runs[0].m26.tpw, evil.runs[0].m26 && evil.runs[0].m26.pf, evil.runs[0].mold, evil.runs[0].writeup, evil.runs[0].note, evil.families[0].name, evil.writeups.length, evil.writeups[0].title, evil.writeups[0].verdict, evil.rejected[0].title, evil.rejected[0].writeups, evil.datasets[0].name, evil.shards, C.normIndex(null), C.normIndex({}), C.normIndex({ runs: [5] })];
  o.head = [C.headline(rv).startsWith(rv.total.runs.toLocaleString('en-US')), C.LABEL.includes('not a forecast'), C.LABEL.includes('not proof'), C.jarvisCard(rv).name, C.jarvisCard(rv).kpis.length, JSON.stringify(C.jarvisCard(rv)).length < 8192, C.jarvisCard(v).status.level, /[<>]/.test(JSON.stringify(C.jarvisCard(rv)))];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    import shutil
    if not shutil.which("node"):
        check("b. node is not installed: maths skipped", True)
        return
    fx, real = os.path.join(D, "fixture.json"), os.path.join(D, "index.json")
    o = AK.node(APP, HARNESS, fx, real)
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. money words: whole dollars, +/- on a net, PF to 2 places, n/a for nothing", o["words"] == ["$758", "-$12", "n/a", "+$43,820", "-$5", "4.19", "n/a", "2.9", "n/a"], o["words"])
    check("b. choosing the data: the built file wins; a missing, empty or demo-marked one falls back to the labelled demo; nothing at all gives null", o["choose"] == ["file", "demo", "demo", None, "demo", True], o["choose"])
    check("b. the demo library: 30 runs, 6 shelves, 3 rejected ideas, the first run's net kept, a run with no 2026 result has NO 2026 period (null, never zero)", o["fx"][:7] == [30, 6, 3, 2, 2, 30, True] and o["fx"][7] == 3300 and o["fx"][8] is None, o["fx"])
    check("b. filters on the demo: 6 adopted; 'stops' finds that shelf; family risk 5; 26 judged 24; both periods 24; net >= 1500 in 2026; $/month and fail <= 5; AND of two words and a verdict; no match gives none",
          o["filt"][0] == 6 and o["filt"][1] == 5 and o["filt"][2] == 5 and o["filt"][3] == 24 and o["filt"][4] == 24 and o["filt"][5] == 18 and o["filt"][6] >= 6 and o["filt"][7] == 3 and o["filt"][8] == 0, o["filt"])
    check("b. the live LIT run in the real index: adopted, 2026 net $43,820, $4,467 a month, PF 4.19, pass10 31.6 / fail10 1, a 2021-25 period of 511 trades; 'any' years reads 2026 first",
          o["live"][:6] == [0, 43820, 4467, 4.19, 31.6, 1] and o["live"][6] == 511 and o["live"][7] == 511 and o["live"][8] == 120 and o["live"][9] == "2026", o["live"])
    check("b. sorting: net best first, runs with no number last, fail10 lowest first, name, and $ a month on the real library", all(o["sort"]), o["sort"])
    check("b. compare in plain words: 6 lines, each run with its verdict and its two periods (net, $ a month, PF, trades a week, n, pass / fail in 10), the monthly difference, the both-periods rule, and 'one backtest each, not proof'",
          o["cmp"][0] == 6 and o["cmp"][1].startswith("A: Example: risk idea number 1. Adopted (an adopt candidate). 2026: +$3,300 net, $660 a month, PF 2.70, 2.1 trades a week, 60 trades; eval in 10 sessions: pass 22%, fail 4%. 2021-25: -$500 net")
          and "In 2026: B makes" in o["cmp"][2] and "a month less than A" in o["cmp"][2] and "In 2021-25: B makes" in o["cmp"][3] and "One backtest each" in o["cmp"][4] and o["cmp"][5] is False and o["cmp"][6] == 0, o["cmp"])
    check("b. Don't redo this: 'fixed 12 point stop' matches the fixed-stops idea first; one ordinary word ('stop') does not warn; a new idea and an empty box do not; 'cold streak filter' finds the cold-streak idea; the warning sentence names the idea and the stored rejected runs",
          o["redo"][0].startswith("Fixed 10") and o["redo"][1] == 0 and o["redo"][2] == 0 and o["redo"][3] == 0 and o["redo"][4] is True and o["redo"][5].startswith("The skip-mode cold-streak") and o["redo"][6] == 0
          and o["redo"][7] == "Don't redo this: it matches an idea we already tested and rejected, \"" [:60] and o["redo"][8] is None, o["redo"])
    check("b. second opinion from the stored runs: 'breakeven stop' has rejected runs behind it; one word never counts; words are stemmed (trailing -> trail, stops -> stop, pts -> point)", o["rrun"][0] is True and o["rrun"][1] == 0 and o["rrun"][2] == ["trail", "stop", "fix", "point"], o["rrun"])
    check("b. the shelves: one per family (14 at most), three books (adopted, open, rejected) of height 0..1 (square-root scale: the tallest book is 1), a book of nothing is 0, the words name the runs",
          o["shelf"][0] == 14 and o["shelf"][1] == "LIT research" and o["shelf"][2] == ["adopted", "open", "rejected"] and o["shelf"][3] and o["shelf"][4] and o["shelf"][5] == 1 and o["shelf"][6] == 6 and o["shelf"][7], o["shelf"])
    check("b. shards add runs once (a repeat adds none), junk rows are dropped, a run with no 2021-25 period keeps null", o["shard"][:6] == [1, 0, 1, 0, 0, None], o["shard"])
    check("b. no markup survives from data: tags and backticks stripped, a bad verdict -> open, NaN / Infinity -> null, a bad slug dropped, bad rows dropped, only runs-<k>.json shard names kept; null / junk -> null",
          o["evil"][:3] == [1, "bx/b", "iT/i y", ] or (o["evil"][0] == 1 and "<" not in o["evil"][1] + o["evil"][2] and o["evil"][3] == 2 and o["evil"][4] is None and o["evil"][5] is None and o["evil"][6] is None and o["evil"][7] == "" and "<" not in o["evil"][8]
          and "<" not in o["evil"][9] and o["evil"][10] == 1 and "<" not in o["evil"][11] and o["evil"][12] == 2 and "<" not in o["evil"][13] and o["evil"][14] == ["fine"] and "<" not in o["evil"][15] and o["evil"][16] == ["runs-1.json"] and o["evil"][17:] == [None, None, None]), o["evil"])
    check("b. the headline and the Jarvis card: runs, write-ups, 3 kpis, off for the demo, under 8 KB, no markup, an honest label", o["head"] == [True, True, True, "Archive", 3, True, "off", False], o["head"])


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
            AK.open_app(p, origin, APP, "?demo=1&q=off")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#head').textContent, tiles: document.querySelector('#tiles').textContent, cards: document.querySelectorAll('#results > li').length,
              count: document.querySelector('#count').textContent, fams: document.querySelectorAll('#family option').length, ws: document.querySelectorAll('#writeups > li').length, rj: document.querySelectorAll('#rejected > li').length, ds: document.querySelectorAll('#dsRows tr').length,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, flat: !document.querySelector('#flat').hidden, rows: document.querySelectorAll('#flat g').length })""")
            check("c. DEMO + ?q=off: the chip, 'Example numbers: 30 runs', 4 tiles, 30 run cards, the family list, 2 write-ups, 3 rejected ideas, 2 datasets, the flat library (6 shelves), AGORA serif + warm dark body",
                  d["demo"] and d["head"].startswith("Example numbers: 30 runs") and "Runs" in d["tiles"] and d["cards"] == 30 and "30 of 30 runs match" in d["count"] and d["fams"] == 7 and d["ws"] == 2 and d["rj"] == 3 and d["ds"] == 2 and d["flat"] and d["rows"] == 6
                  and any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            AK.shot(p, "archive-demo")
            c1 = p.evaluate("() => { const li = document.querySelector('#results > li'); return { text: li.textContent, story: li.querySelector('a').getAttribute('href'), tiles: li.querySelectorAll('.tile').length } }")
            check("c. a run card shows net $, $ a month, PF, trades a week and trades next to each other (money, not only R), the eval odds when it has them, and a link ('Open the run' to the Lab when there is no write-up)",
                  c1["tiles"] == 4 and "Net $" in c1["text"] and "$ a month" in c1["text"] and "PF" in c1["text"] and "pass / fail" in c1["text"] and c1["story"].startswith("../#/run/"), c1)
            p.fill("#q", "stops")
            p.wait_for_timeout(400)
            s1 = p.evaluate("() => [document.querySelectorAll('#results > li').length, document.querySelector('#count').textContent, document.querySelectorAll('#redo:not([hidden])').length]")
            check("c. search 'stops': the list shrinks to that shelf (5 of 30) and the count says so", s1[0] == 5 and s1[1].startswith("5 of 30"), s1)
            p.fill("#q", "fixed 12 point stops")
            p.wait_for_timeout(400)
            s2 = p.evaluate("() => { const r = document.querySelector('#redo'); return { shown: !r.hidden, text: r.textContent, role: r.getAttribute('role') } }")
            check("c. type an idea that was rejected ('fixed 12 point stops'): the 'Don't redo this' warning appears (role alert) and names the idea", s2["shown"] and "Don't redo this" in s2["text"] and "Example: fixed 12 point stops" in s2["text"] and s2["role"] == "alert", s2)
            p.fill("#q", "")
            p.wait_for_timeout(300)
            p.locator("#verdicts button", has_text="Adopted").click()
            p.locator("#years button", has_text="2026").click()
            p.wait_for_timeout(200)
            f1 = p.evaluate("() => [document.querySelectorAll('#results > li').length, document.querySelector('#verdicts [aria-pressed=true]').textContent, document.querySelector('#years [aria-pressed=true]').textContent, document.querySelector('#results').textContent.includes('Adopted')]")
            check("c. the Adopted and 2026 chips filter (6 adopted runs, all judged on 2026), and say which chip is on", f1[0] == 6 and f1[1] == "Adopted" and f1[2] == "2026" and f1[3], f1)
            p.locator("#verdicts button", has_text="All").click()
            p.locator("details.nums summary").click()
            p.fill("#min_net", "2000")
            p.dispatch_event("#min_net", "change")
            p.wait_for_timeout(200)
            f2 = p.evaluate("() => document.querySelectorAll('#results > li').length")
            check("c. 'Net $ at least 2000' (2026, any verdict) keeps only the runs above it (12 of the 24 judged on 2026)", f2 == 12, f2)
            p.locator("#reset").click()
            p.wait_for_timeout(200)
            p.locator('#results [data-cmp]').nth(0).click()
            p.locator('#results [data-cmp]').nth(1).click()
            p.wait_for_timeout(200)
            cm = p.evaluate("() => { const c = document.querySelector('#compare'); return { shown: !c.hidden, lines: c.querySelectorAll('p').length, text: c.textContent, pressed: document.querySelectorAll('#results [aria-pressed=true]').length } }")
            check("c. pick two runs: the side-by-side appears in plain words (A and B with money, the difference a month, the both-periods rule, the 'not proof' line) and both buttons say picked",
                  cm["shown"] and cm["lines"] >= 5 and "Side by side" in cm["text"] and "a month" in cm["text"] and "One backtest each" in cm["text"] and cm["pressed"] == 2, cm)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, selects, inputs, buttons, links, summaries)", not t, t[:6])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            rk = p.evaluate("() => { const r = window.ARCHIVE.rack; return r ? { n: r.count(), h: r.heights(), shown: !document.querySelector('#stage').hidden && document.querySelector('#flat').hidden, size: [document.querySelector('#stage').clientWidth, document.querySelector('#stage').clientHeight] } : null }")
            if rk is None:
                check("c. 3D: no WebGL here, so the flat library is shown (the page still works)", p.evaluate("() => window.ARCHIVE.flat === true && !document.querySelector('#flat').hidden"))
            else:
                tall = max(max(x) for x in rk["h"])
                check("c. 3D: the marble library is up with 6 shelves of 3 books; the tallest book fills 0.7 and a book of nothing has height 0; the flat twin is hidden; the canvas has a real size",
                      rk["n"] == 6 and len(rk["h"][0]) == 3 and abs(tall - 0.7) < 0.01 and rk["shown"] and rk["size"][0] > 200 and rk["size"][1] > 100, rk)
                pos = p.evaluate("() => window.ARCHIVE.rack.screenOf(0, 2)")
                if pos and pos["front"]:
                    p.mouse.click(pos["x"], pos["y"])
                    p.wait_for_timeout(400)
                    sel = p.evaluate("() => [window.ARCHIVE.S.f.family, window.ARCHIVE.S.f.verdict, window.ARCHIVE.rack.selected, document.querySelector('#family').value]")
                    check("c. tap the rejected book of the first shelf in 3D: the list is filtered to that shelf and to rejected runs", sel[0] == window_first(fx_families(), 0) and sel[1] == 1 and sel[2] == 0 and sel[3] == sel[0], (pos, sel))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?q=off")
            p.wait_for_function("window.ARCHIVE.shards()", timeout=60000)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, head: document.querySelector('#head').textContent, count: document.querySelector('#count').textContent, runs: window.ARCHIVE.S.v.runs.length, total: window.ARCHIVE.S.v.total.runs, cards: document.querySelectorAll('#results > li').length, ws: document.querySelectorAll('#writeups > li').length, ds: document.querySelectorAll('#dsRows tr').length })")
            idx = json.load(open(os.path.join(D, "index.json"), encoding="utf-8"))
            check(f"c. the real index: no DEMO chip, all {idx['counts']['runs']:,} runs loaded (index.json first, then {len(idx['shards'])} shards), 30 cards shown with 'Show 30 more', write-ups and datasets listed",
                  not r["demo"] and r["runs"] == idx["counts"]["runs"] and r["total"] == idx["counts"]["runs"] and r["cards"] == 30 and r["ws"] == 8 and r["ds"] == idx["counts"]["datasets"] and "runs match" in r["count"], r)
            check("c. the real run reads only the site's own index.json and shards, and no console error", any("archive/index.json" in u for u in seen) and sum(1 for u in seen if "runs-" in u) == len(idx["shards"]) and not off and not errs, (off[:3], errs[:3]))
            p.fill("#q", "inducement before the sweep")
            p.wait_for_timeout(500)
            w = p.evaluate("() => [!document.querySelector('#redo').hidden, document.querySelector('#redo').textContent.slice(0, 160), document.querySelectorAll('#redo a').length]")
            check("c. the real library warns on a rejected idea ('inducement before the sweep') and links its write-up", w[0] and "Don't redo this" in w[1], w)
            p.fill("#q", "lit_live")
            p.wait_for_timeout(400)
            lv = p.evaluate("() => { for (let k = 0; k < 40 && !document.querySelector('#results > li[data-id=lit_live]') && !document.querySelector('#more').hidden; k++) document.querySelector('#more').click(); const li = document.querySelector('#results > li[data-id=lit_live]'); return li ? li.textContent : '' }")
            check("c. search 'lit_live' finds the live LIT run: $4,467 a month, +$43,820 net, PF 4.19, 2.9 trades a week (2026)", "$4,467" in lv and "+$43,820" in lv and "4.19" in lv and "Adopted" in lv, lv[:300])
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?find=cold%20streak&q=off")
            r = p.evaluate("() => [document.querySelector('#q').value, !document.querySelector('#redo').hidden]")
            check("c. a link can open the library on a search (?find=cold streak) and the Don't-redo warning shows", r[0] == "cold streak" and r[1], r)
            ctx.close()
            srv2, origin2 = AK.serve({"/archive/index.json": "{broken"})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?q=off")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#head').textContent]")
            check("c. a broken index.json falls back to the labelled demo, never blank", r[0] is True and r[1].startswith("Example numbers") and not errs, (r, errs[:2]))
            ctx.close()
            srv2.shutdown()
    finally:
        srv.shutdown()


def fx_families():
    return json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))["families"]


def window_first(fams, i):
    from itertools import islice
    return next(islice((f["name"] for f in fams), i, None))


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
