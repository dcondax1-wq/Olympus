"""THE BOT'S EDGE, Mnemosyne's second page (tools/web_public/journal/edge.html, night-botgap 2026-11-18, research/writeups/bot-gap-2026-11-18.md):
what Tradervue / TradesViz / Edgewonk / NinjaTrader / TradingView show and the journal apps did not: R and $ per trade, expectancy by setup / session /
weekday / exit (both 2026 halves), the weekday x hour map, MAE / MFE (how far trades go against you first), the equity curve and its drawdowns, "is this
losing run normal?", and the PC's fill checks. Read only.

  a. static: the files, the kit lines, no markup from data, reads only edge.json / ../trading/trades.json / ../odeon/trades.json / the PC feed, one storage key,
     the pure core, edge.json's shape and dates (tools/journal_edge_build.py --check), the link from Mnemosyne's first page
  b. the maths in node (edgecore.js): words, rows, real-trade merging (one row per signal, real over paper), stats (the Trading page's win %), groups and "both
     halves", the heat map (no claim under 3 / 5 trades), the equity curve and drawdowns, MAE / MFE words, losing runs and the seeded verdict, the real numbers
  d. the fill-check block end to end: engine/feed_fills.compact (the PC builder) -> tools/pc_report.split -> pc_feed.js
     parseLatest -> edgecore.fills
  c. Chromium 390 x 844 with a stubbed PC feed (+ 375 x 667, no feed): every card drawn, the chips, taps >= 44 px, no sideways scroll, no console error,
     nothing off the site; screenshots when AGORA_SHOTS=<dir>
    python -X utf8 -m tests.test_journal_edge            (--static: parts a, b and d only)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

ROOT, WEB = AK.ROOT, AK.WEB
D = os.path.join(WEB, "journal")
check = AK.check
FF_PATH = os.path.join(ROOT, "engine", "feed_fills.py")


def read(p):
    return AK.read(p)


def feed_fills():
    spec = importlib.util.spec_from_file_location("feed_fills_parked", FF_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_static():
    names = ["edge.html", "edge.js", "edgecore.js", "edge.css", "edge.json"]
    check("a. the files: " + ", ".join(names) + " + tools/journal_edge_build.py", all(os.path.isfile(os.path.join(D, n)) for n in names) and os.path.isfile(os.path.join(ROOT, "tools", "journal_edge_build.py")))
    html, js, core, css = (read(os.path.join(D, n)) for n in ("edge.html", "edge.js", "edgecore.js", "edge.css"))
    idx = read(os.path.join(D, "index.html"))
    check("a. the kit as on Mnemosyne's first page (olympus.css, agora.css, themes.js, olympus.js data-app=\"journal\", a11y), journal.css + edge.css, an ES module, one h1, a polite status line",
          all(re.search(re.escape(t.split("?")[0]) + r"\?v=\w+", html) for t in ("../olympus/olympus.css?", "../olympus/agora.css?", "../olympus/themes.js?", "../olympus/olympus.js?"))
          and re.search(r'olympus\.js\?v=\w+" data-app="journal"', html) and all(re.search(re.escape(t), idx) for t in re.findall(r'\.\./olympus/(?:olympus\.css|agora\.css|themes\.js|olympus\.js)\?v=\w+', html))
          and "../olympus/a11y.js" in html and "journal.css?v=" in html and "edge.css?v=" in html and '<script type="module" src="edge.js?v=' in html and html.count("<h1>") == 1 and 'role="status"' in html)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function", r"\bimport\s*\(") if re.search(p, js) or re.search(p, core)]
    check("a. no markup is ever built from data: no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval / dynamic import", not bad, bad)
    fetches = set(re.findall(r"getJSON\('([^']+)'\)", js))
    check("a. it reads only the site's own files (./edge.json, ../trading/trades.json, ../odeon/trades.json) and the PC feed through ../pc_feed.js; it sends nothing (no XHR / WebSocket / beacon / POST / web address)",
          fetches == {"./edge.json", "../trading/trades.json", "../odeon/trades.json"} and "../pc_feed.js?v=" in js and "'../status_feed.json'" in js
          and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|https?://(?!www\.w3\.org)", js + core), fetches)
    check("a. one storage key (journal.edge.v1: the chosen bot / set / grouping), every access in try / catch; no cookies / sessionStorage / indexedDB",
          "const KEY = 'journal.edge.v1'" in js and len(re.findall(r"localStorage\.(?:setItem|getItem)\(", js)) == 2 and not re.search(r"document\.cookie|sessionStorage|indexedDB", js + core)
          and js.count("try { localStorage") == 1 and "try { p = JSON.parse(localStorage" in js)
    check("a. edgecore.js is pure (no document / window / fetch / localStorage), Safari 16 safe (no lookbehind, no .at(), no toSorted / groupBy)",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(|toSorted|groupBy", re.sub(r"//[^\n]*", "", core)))
    check("a. text only through textContent / createElementNS; taps >= 44 px in the CSS (chips), charts are pictures (role=img), no neon look",
          "textContent" in js and "createElementNS" in js and css.count("min-height: 44px") >= 1 and html.count('role="img"') == 4 and not AK.BANNED_LOOK.search(css + js))
    check("a. Mnemosyne's first page links here (a 44 px link card) and keeps its own reads", 'href="edge.html"' in idx and 'id="edgeCard"' in idx and "a.go {" in read(os.path.join(D, "journal.css")))
    e = json.loads(read(os.path.join(D, "edge.json")))
    rows = e.get("rows") or []
    bots = {r[2] for r in rows}
    check("a. edge.json: v 1, the 13 columns, both bots (Zlarior 600+, ATLAS 1,000+ trades), 2021-26, MAE / MFE on every row, dated (built, the anatomy's built, data to Oct 2026)",
          e.get("v") == 1 and e.get("cols") == ["d", "hm", "b", "s", "sd", "q", "k", "r", "u", "f", "a", "x", "m"] and bots == {"L", "A"}
          and sum(1 for r in rows if r[2] == "L") >= 600 and sum(1 for r in rows if r[2] == "A") >= 1000 and min(r[0] for r in rows) < "2022" and max(r[0] for r in rows) >= "2026-10"
          and all(r[9] is not None and r[10] is not None for r in rows) and e.get("built") and all((e.get("anatomy_built") or {}).get(b) for b in "LA") and e["upto"]["lit"] >= "2026-10",
          {k: e.get(k) for k in ("v", "cols", "upto", "anatomy_built")})
    check("a. edge.json says what the money is: the backtest's size per bot, 'not money made', CME NQ futures (never Yahoo / CFD)",
          e["risk"] == {"L": 800, "A": 250} and all("not money made" in e["sources"][b] and "CME NQ futures" in e["sources"][b] for b in "LA") and not re.search(r"yahoo|cfd", json.dumps(e["sources"]), re.I))
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "journal_edge_build.py"), "--check"], capture_output=True, text=True, timeout=120)
    check("a. edge.json is current with research/anatomy (journal_edge_build.py --check)", r.returncode == 0, r.stdout + r.stderr)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import journal_edge_build as JB
    fx = {"L": os.path.join(tempfile.gettempdir(), "nope_lit.json"), "A": os.path.join(tempfile.gettempdir(), "nope_atlas.json")}
    b = JB.build(fx)
    check("a. the build never raises on missing anatomy files (an empty list), and maps every exit (EOD -> FLAT, T15 -> CUT, HEDGE kept)",
          b["rows"] == [] and [JB.EXITS[JB.exit_index(k)] for k in ("EOD", "T15", "HEDGE", "weird", "stop")] == ["FLAT", "CUT", "HEDGE", "FLAT", "STOP"])


HARNESS = r"""
const C = await import(process.argv[2]);
const fs = await import('fs');
const edge = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const o = {};
o.words = [C.money(-1234.6), C.moneyS(565), C.moneyS(0.2), C.rWord(0.8125), C.rWord(-1), C.both(-437, -1.03), C.hourWord(0), C.hourWord(14), C.dayWord('2026-10-28', true), C.sessionWord(C.sessionOf(130)), C.sessionOf(600), C.sessionOf(1100), C.sessionOf(1000)];
const mk = (day, hm, r, usd, extra) => ({ day, hm, min: +hm.slice(0, 2) * 60 + +hm.slice(3), wd: C.dowOf(day), span: C.spanOf(day), bot: 'LIT', setup: 'A', side: 'LONG', qty: 1, risk: 100, r, usd, mfe: Math.max(0, r) + 0.5, mae: r < 0 ? 1 : 0.3, exit: r < 0 ? 'STOP' : 'TARGET', held: 30, src: 'backtest', ...(extra || {}) });
const T = [mk('2026-01-05', '02:10', 2, 200), mk('2026-01-06', '03:10', -1, -100), mk('2026-01-07', '02:40', 0.01, 1), mk('2026-02-02', '02:15', -1, -100), mk('2026-03-02', '02:20', 3, 300, { setup: 'B' }),
  mk('2026-07-06', '02:30', -1, -100), mk('2026-07-07', '02:50', 2, 200), mk('2026-08-03', '09:40', -1, -100, { setup: 'B' }), mk('2026-09-01', '02:05', 1, 100), mk('2026-10-05', '02:25', -1, -100)];
const s = C.stats(T);
o.stats = [s.n, s.wins, s.losses, s.scratches, s.winPct, s.net, s.exp, s.expR, s.pf, s.avgWin, s.avgLoss, s.payoff, s.sqn, s.risk, s.from, s.to, s.perWeek > 0];
o.empty = C.stats([]).n === 0 && C.stats(null).exp === null;
const G = C.groups(T, 'setup');
o.groups = G.map((g) => [g.key, g.n, g.net, g.enough, g.holds]);
o.gline = [C.groupLine(G, 'setup'), C.groupLine([], 'setup')];
o.sess = C.groups(T, 'session').map((g) => [g.label, g.n]);
const H = C.heat(T);
o.heat = [H.hours, H.n, H.cells.length, H.cells[0].length, H.best && [H.best.d, H.best.h, H.best.n], H.busy, C.cellWord(H.cells[1][1])];
const cv = C.curve(T);
o.curve = [cv.n, cv.net, cv.maxDD, cv.maxDDR, cv.recovery, cv.top.map((d) => [d.from, d.low, d.depth, d.to, d.recovered, d.days]), cv.under];
o.runs = [C.runs(['W', 'L', 'S', 'L', 'W', 'L', 'L', 'L']), C.runs([]), C.runs(['L', 'L', 'W'])];
const r1 = C.rng(7), r2 = C.rng(7);
o.rng = [r1() === r2(), r1() < 1, C.rng(8)() !== C.rng(7)()];
// the real edge.json
const rows = C.rowsFrom(edge);
o.rows = [rows.length, rows.filter((x) => x.bot === 'LIT').length, rows.every((x) => x.span && x.setup && x.exit && x.wd >= 0), C.rowsFrom(null).length, C.rowsFrom({ rows: [[1, 2], ['2026-01-01', '02:00', 'X', 0, 1, 1, 1, 1, 1, 0, 0, 0, 1]] }).length];
const L26 = C.pick(rows, { bot: 'LIT', set: '2026' }), sL = C.stats(L26), sH1 = C.stats(C.pick(rows, { bot: 'LIT', set: 'H1' })), sA = C.stats(C.pick(rows, { bot: 'ATLAS', set: '2026' }));
o.real = [sL.n, Math.round(sL.net), sH1.n, sH1.winPct, sA.n, C.pick(rows, { bot: 'LIT', set: 'real' }).length];
const E = C.excursion(L26);
o.exc = [E.n, E.wins, E.heatMed > 0 && E.heatMed < 1, E.heatP75 >= E.heatMed, E.up1 >= E.up1Won + E.up1Back, E.etd > 0, C.excursionLines(E, 128), C.excursionLines(C.excursion([]), 100)];
const st = C.streak(C.pick(rows, { bot: 'LIT', set: 'all' }), [mk('2026-10-27', '06:12', -1.02, -827, { src: 'paper' }), mk('2026-10-28', '03:43', -1.03, -437, { src: 'live' }), mk('2026-11-16', '06:16', -1.01, -129, { src: 'live' })]);
const st2 = C.streak(C.pick(rows, { bot: 'LIT', set: 'all' }), [mk('2026-11-16', '06:16', -1, -100, { src: 'live' })]);
o.streak = [st.enough, st.current, st.longest, st.longestAll >= st.longest, st.p50 <= st.p90, st.verdict, st.level, st.simShare, C.streak(C.pick(rows, { bot: 'LIT', set: 'all' }), []).verdict, st2.p50 === st.p50,
  C.streak([], []).enough, C.streak(C.pick(rows, { bot: 'LIT', set: 'all' }), Array.from({ length: 40 }, (_, i) => mk('2026-11-17', '02:00', -1, -100, { src: 'live' }))).verdict];
o.slines = C.streakLines(st, 'Zlarior', 128, 1024.58);
// real rows: the Trading file, Odeon and a fresh feed (the same signal twice = one row; real wins over paper; a feed row fills the ATLAS member)
const trading = { trades: [{ src: 'paper', bot: 'LIT', day: '2026-10-28', hm: '03:43', t: 1793173380, q: 8, r: -1.03, usd: -699.2, k: 'STOP' }, { src: 'live', bot: 'LIT', day: '2026-10-28', hm: '03:43', t: 1793173380, q: 5, r: -1.03, usd: -437, k: 'STOP', ak: 'z50k' },
  { src: 'backtest', bot: 'LIT', day: '2026-10-14', t: 1791969840, r: 3.8, usd: 579 }] };
const odeon = { trades: [{ src: 'real', bot: 'LIT', day: '2026-10-28', entry: { t: 1793173380 }, side: 'SHORT', qty: 5, r: -1.03, usd: -437, mfe_r: 0.95, mae_r: 1.01, exit: { kind: 'STOP' } }] };
const now = 1795044602;
const lite = { reporter: { t: now - 60 }, t: now - 120, at: { a: [{ id: 'atlas', tr: [[1794995400, 1794996603, -1, 2, 27395.5, 27422.5, 27179.5, 'STOP', -112.8, -1.04]] }, { id: 'acct_c', tr: [[1794995400, 1794996000, 1, 1, 1, 1, 1, 'STOP', -5, -1]] },
  { id: 'mffu50k_eval', tr: [[1794827760, 1794830400, 1, 1, 27799.5, 27735.25, 28174, 'STOP', -129.4, -1.01], [1795040000, null, 1, 1, 1, 1, 1, null, null, null]] }] },
  board: { trades: [{ acct: 'atlas', src: 'live', key: 'macd_sweep', member: 'MACD', day: '2026-11-18', entry_t: 1794995400, exit_t: 1794996603, side: 'SHORT', qty: 2, exit: 'STOP', r: -1.044, usd: -112.8 }] } };
const R = C.realRows(trading, odeon, lite, now), Rold = C.realRows(trading, odeon, lite, now + 4 * 3600);
o.realRows = R.map((x) => [x.bot, x.day, x.hm, x.src, x.usd, x.setup, x.mae]);
o.realOld = Rold.length;
o.riskNow = [C.riskNow(R.filter((x) => x.bot === 'LIT')), C.riskNow(R.filter((x) => x.bot === 'ATLAS')), C.riskNow([])];
o.botOf = [C.botOfAcct('b25k_2'), C.botOfAcct('atlas'), C.botOfAcct('acct_c'), C.botOfAcct('rapid25k'), C.botOfAcct('blitz'), C.botOfAcct('')];
o.fillsNone = C.fills(lite, now);
const evil = C.rowsFrom({ setups: { L: ['<b>x</b>'] }, exits: ['STOP'], rows: [['2026-01-05', '<i>', 'L', 0, 1, 1, 1, 1, 1, 1, 0, 0, 1]] });
o.evil = JSON.stringify(evil).includes('<');
console.log(JSON.stringify(o));
"""


def node_run(harness, *args):
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="edge-")
    try:
        core = os.path.join(tmp, "edgecore.mjs")
        shutil.copy(os.path.join(D, "edgecore.js"), core)
        h = os.path.join(tmp, "h.mjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(harness)
        r = subprocess.run([exe, h, core, *map(str, args)], capture_output=True, text=True, timeout=180)
        if r.returncode:
            return {"_error": r.stderr[-900:]}
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_maths():
    o = node_run(HARNESS, os.path.join(D, "edge.json"))
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: whole dollars with a sign, R with 2 decimals, every $ with its R, 12 AM / 2 PM, the session windows (02:10 London, 10:00 NY morning, 18:20 Asia, 16:40 none)",
          o["words"] == ["-$1,235", "+$565", "$0", "+0.81R", "-1.00R", "-$437 (-1.03R)", "12 AM", "2 PM", "Oct 28, 2026", "London 02:00-05:00", "am", "asia", None], o["words"])
    check("b. stats: 10 trades, 4 wins / 5 losses / 1 breakeven (R), win % = trades that made money (5 of 10 = 50%), net +$301, +$30 (+0.30R) a trade, PF 1.6, payoff 1.6, SQN, 1R $100",
          o["stats"][:12] == [10, 4, 5, 1, 50, 301, 30.1, 0.3, 1.6, 160.2, -100, 1.6] and o["stats"][12] is not None and o["stats"][13:16] == [100, "2026-01-05", "2026-10-05"] and o["stats"][16] and o["empty"], o["stats"])
    check("b. groups: most money first; 'both 2026 halves' needs 5+ trades in each half (none here: null); the line names the best and the weakest with $ and R, or says 'no claim'",
          [g[0] for g in o["groups"]] == ["B", "A"] and o["groups"][1][1:4] == [8, 101, True] and o["groups"][0][1:4] == [2, 200, False] and all(g[4] is None for g in o["groups"])
          and o["gline"][0].startswith("A pays the most per trade: +$13 (+0.13R) over 8 trades.") and "no claim is made" in o["gline"][1], (o["groups"], o["gline"]))
    check("b. sessions: London 02:00-05:00 has 9 trades, NY morning 1", ["London 02:00-05:00", 9] in o["sess"] and ["NY morning 09:30-11:30", 1] in o["sess"], o["sess"])
    check("b. the heat map: hours 2-9, 10 trades, 5 weekday rows x 8 hours, the best cell needs 5+ trades (Monday 2 AM, 5), the busiest hour is 2 AM, a cell under 3 trades says 'no claim'",
          o["heat"][0] == [2, 3, 4, 5, 6, 7, 8, 9] and o["heat"][1:4] == [10, 5, 8] and o["heat"][4] == [0, 2, 5] and o["heat"][5][0] == 2 and "no claim" in o["heat"][6], o["heat"])
    check("b. the equity curve: net +$301, deepest drawdown -$199 (-1.99R) Jan 5 -> Feb 2, back Mar 2 (56 days), recovery factor 1.51, the 3 deepest dated, the open one at the end (34 days)",
          o["curve"][:5] == [10, 301, -199, -1.99, 1.51] and o["curve"][5][0] == ["2026-01-05", "2026-02-02", -199, "2026-03-02", True, 56] and [d[5] for d in o["curve"][5]] == [56, 127, 56]
          and o["curve"][6] == {"from": "2026-09-01", "depth": -100, "days": 34}, o["curve"])
    check("b. losing runs skip breakevens (W L S L W L L L = runs 2 and 3, 3 open), an empty list is 0, the seeded generator repeats itself",
          o["runs"][0] == {"lens": [2, 3], "longest": 3, "current": 3} and o["runs"][1] == {"lens": [], "longest": 0, "current": 0} and o["runs"][2]["current"] == 0 and o["rng"] == [True, True, True], o["runs"])
    check("b. the real edge.json: Zlarior 631 trades, 2026 = 120 trades and +$43,820 (the Trading page's 2026), Jan-Jun 80 trades with 59% making money (the Trading page's 58.8%), ATLAS 2026 163 trades, no real rows in the backtest; junk rows dropped",
          o["rows"][:4] == [1919, 631, True, 0] and o["rows"][4] == 0 and o["real"][0] == 120 and abs(o["real"][1] - 43820) <= 5 and o["real"][2:4] == [80, 59] and o["real"][4] == 163 and o["real"][5] == 0, (o["rows"], o["real"]))
    check("b. MAE / MFE on Zlarior 2026: winners' heat between 0 and 1R, 1 in 4 deeper than the middle, the +1R trades split into winners and breakevens, a positive give-back (ETD); every line has $ and R; under 10 trades: no claim",
          o["exc"][0] == 120 and all(o["exc"][2:6]) and len(o["exc"][6]) == 4 and all("$" in x for x in o["exc"][6] if "R)" in x) and sum("R)" in x for x in o["exc"][6]) == 3 and "no claim is made" in o["exc"][7][0], o["exc"])
    check("b. is this losing run normal: 3 losses in a row (paper + real) on Zlarior = normal (its 2026 longest is 8, 2021-26 longer), the reshuffle is seeded (same p50 every time), no run = 'none', 40 in a row = 'new' (past the history)",
          o["streak"][:3] == [True, 3, 8] and o["streak"][3] and o["streak"][4] and o["streak"][5] == "normal" and o["streak"][6] == "ok" and o["streak"][7] > 50 and o["streak"][8] == "none" and o["streak"][9]
          and o["streak"][10] is False and o["streak"][11] == "new", o["streak"])
    sl = o["slines"]
    check("b. the streak words: 'Normal: Zlarior has lost 3 trades in a row (about $384 at $128 a trade).', the 2026 basis, the reshuffle, and the drawdown left as losses ($1,025 = 8 losses)",
          sl["head"] == "Normal: Zlarior has lost 3 trades in a row (about $384 at $128 a trade)." and any("In 2026, the year its rules were picked and checked" in x for x in sl["lines"]) and any("8 losses at $128 a trade" in x for x in sl["lines"]), sl)
    check("b. real rows: one row per signal (the Oct 28 paper twin and the real fill = 1 real row with Odeon's MAE), the feed's ATLAS fill takes the board's MACD member, BLITZ and the open trade left out, the feed older than 3 h is ignored",
          o["realRows"] == [["LIT", "2026-10-28", "03:43", "live", -437, "Live trade", 1.01], ["LIT", "2026-11-16", "06:16", "live", -129.4, "Live trade", None], ["ATLAS", "2026-11-18", "04:50", "live", -112.8, "MACD", None]]
          and o["realOld"] == 1, o["realRows"])
    check("b. 1R now = the newest real trade's risk ($128 Zlarior, $108 ATLAS); account ids -> bots (25K #2 / Rapid = Zlarior, BLITZ hidden); no fill block in the feed = null; no markup survives from data",
          o["riskNow"] == [128, 108, None] and o["botOf"] == ["LIT", "ATLAS", None, "LIT", None, None] and o["fillsNone"] is None and o["evil"] is False, (o["riskNow"], o["botOf"]))


FQ_HARNESS = r"""
const C = await import(process.argv[2]);
const fs = await import('fs');
const { createRequire } = await import('module');
const req = createRequire(import.meta.url);
const PF = req(process.argv[3]);
const lite = PF.parseLatest(fs.readFileSync(process.argv[4], 'utf8'));
const f = C.fills(lite, +process.argv[5]);
console.log(JSON.stringify({ has: !!(lite && lite.fq), f }));
"""


def fq_sample(now):
    FF = feed_fills()
    ex = {"v": 1, "t": now - 300, "from": "2026-10-19", "to": "2026-11-18", "trades": 3, "missed": 1, "missed_pc_on": 1, "missed_usd": 612.0, "extra": 0, "extra_usd": 0,
          "slip_usd": -14.5, "slip_usd_per_trade": -4.83, "exec_usd": -21.0, "entry_slip_ticks_med": 1.0, "exit_slip_ticks_med": 0.5, "latency_s_med": 2.8, "be_delay_s_med": 4,
          "qty_mismatch": 0, "slipped": 0, "months": [{"month": "2026-10", "trades": 2, "slip_usd": -9.5, "exec_usd": -12.0, "missed": 1, "missed_usd": 612.0},
                                                        {"month": "2026-11", "trades": 1, "slip_usd": -5.0, "exec_usd": -9.0, "missed": 0, "missed_usd": 0}],
          "recent": [{"status": "matched"}], "text": "x"}
    revs = [{"acct": "atlas", "name": "ATLAS", "entry_t": now - 4 * 3600, "side": "SHORT", "dir": -1, "kind": "LIVE", "plan": {"qty": 2}, "real": {"filled": 2},
             "slip": {"entry_ticks": 1.0, "exit_ticks": 1.0}, "costs": {"exec_usd": -1.0}, "flags": [], "ok": True},
            {"acct": "lit", "name": "Zlarior", "entry_t": now - 2 * 3600, "side": "LONG", "dir": 1, "kind": "LIVE", "plan": {"qty": 3}, "real": {"filled": 3},
             "slip": {"entry_ticks": 3.0, "exit_ticks": None}, "costs": {"exec_usd": -4.5}, "flags": [{"code": "slip_entry", "level": "warn", "text": "t"}], "ok": False},
            {"acct": "blitz", "entry_t": now - 3600, "dir": 1, "plan": {"qty": 1}, "real": {"filled": 1}, "slip": {}, "costs": {}, "flags": []}]
    return FF, ex, revs


def test_fill_block():
    now = int(time.time())
    FF, ex, revs = fq_sample(now)
    fq = FF.compact(ex, revs, now)
    check("d. the PC builder (parked for the lead): the 45-day audit + the last fill checks, newest first, BLITZ never sent, no account name, ~600 bytes; nothing -> None; junk never raises",
          fq and fq["t"] == now and fq["ex"]["n"] == 3 and fq["ex"]["mu"] == 612.0 and len(fq["ex"]["m"]) == 2 and [r[0] for r in fq["fc"]] == ["lit", "atlas"] and fq["fc"][0][8] == "slip_entry"
          and len(json.dumps(fq)) < 700 and "ATLAS" not in json.dumps(fq) and FF.compact(None, None, now) is None and FF.compact("x", [1, None, {"acct": "lit"}], "y") is None, fq)
    q2 = json.loads(json.dumps(fq))
    FF.cut(q2, 1)
    q3 = json.loads(json.dumps(fq))
    FF.cut(q3, 0)
    check("d. cut(fq, n) keeps the newest n checks (0 = only the audit totals)", len(q2["fc"]) == 1 and q2["fc"][0][0] == "lit" and "fc" not in q3 and q3["ex"]["n"] == 3, (q2, q3))
    from tools import pc_report as PR
    big = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": now - 120, "reporter": {"t": now - 60, "server": True}, "pc": {"present": True, "t": now - 120, "glance": {"v": 1, "bots": [{"id": "lit", "why": "x" * 1500}]}},
           "board": {"t": now - 100, "data_t": now - 100, "lit": {"name": "Zlarior", "room": 1024.58}, "trades": [{"acct": "atlas", "src": "live", "entry_t": now - 4 * 3600, "r": -1.04, "usd": -112.8}]},
           "brd": {"t": now, "ev": [[now, "daily_review", "", "y" * 90]] * 6}, "mf": {"t": now, "a": [{"id": "mffu50k_eval", "eq": list(range(40))}]}, "fq": fq}
    core, exts = PR.split(big)
    placed = [e for e in exts if "fq" in (e.get("x") or {})]
    check("d. through tools/pc_report.split as the lead would add it: 'fq' rides an ext post under the 3,900-byte limit, not cut, through the privacy pass",
          len(placed) == 1 and not any("fq" in (e.get("cut") or []) for e in exts) and all(len(json.dumps(e)) <= PR.MAX_STATUS_BYTES for e in exts) and placed[0]["x"]["fq"]["ex"]["n"] == 3, [list((e.get("x") or {}).keys()) for e in exts])
    tmp = tempfile.mkdtemp(prefix="edge-fq-")
    try:
        nd = os.path.join(tmp, "feed.ndjson")
        with open(nd, "w", encoding="utf-8") as fh:
            for e in exts:
                fh.write(json.dumps({"event": "message", "time": now - 61, "message": json.dumps(e)}) + "\n")
            fh.write(json.dumps({"event": "message", "time": now - 60, "message": json.dumps(core)}) + "\n")
        o = node_run(FQ_HARNESS, os.path.join(WEB, "pc_feed.js"), nd, now)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if o is None:
        check("d. node is not installed: the feed round trip skipped", True)
        return
    f = (o or {}).get("f") or {}
    a = f.get("audit") or {}
    ch = f.get("checks") or []
    check("d. pc_feed.js lays 'fq' top level and edgecore.fills reads it: 3 Zlarior trades checked, slippage -$15 (-$5 a trade), 1 missed while the PC was on (+$612), the two months, two checks (Zlarior flagged 'entry slipped', ATLAS OK)",
          o.get("has") and a.get("n") == 3 and a["lines"][0].startswith("3 Zlarior trades checked against the backtest on the same bars (Oct 19 - Nov 18): slippage -$15 (-$5 a trade).")
          and any("1 backtest trade not taken (1 while the PC was on): +$612" in x for x in a["lines"]) and [m["month"] for m in a["months"]] == ["2026-10", "2026-11"]
          and [c["name"] for c in ch] == ["Zlarior 50K", "ATLAS"] and ch[0]["flags"] == ["entry slipped"] and ch[0]["ok"] is False and ch[1]["ok"] is True and "Fill check OK." in ch[1]["line"], o)


def stub_feed(now):
    """an ntfy /json?poll=1 answer: the PC's ext + core posts (tools/pc_report.split) with "at", the board trades and "fq" """
    from tools import pc_report as PR
    FF, ex, revs = fq_sample(now)
    out = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": now - 120, "reporter": {"t": now - 60, "server": True}, "pc": {"present": True, "t": now - 120},
           "board": {"t": now - 100, "data_t": now - 100, "lit": {"name": "Zlarior", "room": 1024.58}, "atlas": {"name": "ATLAS", "room": 887.0},
                     "trades": [{"acct": "atlas", "src": "live", "key": "macd_sweep", "member": "MACD", "entry_t": now - 4 * 3600, "exit_t": now - 4 * 3600 + 1200, "side": "SHORT", "qty": 2, "exit": "STOP", "r": -1.04, "usd": -112.8}]},
           "at": {"t": now - 100, "a": [{"id": "mffu50k_eval", "tr": [[now - 50 * 3600, now - 49 * 3600, 1, 1, 27799.5, 27735.25, 28174.0, "STOP", -129.4, -1.01]]},
                                        {"id": "atlas", "tr": [[now - 4 * 3600, now - 4 * 3600 + 1200, -1, 2, 27395.5, 27422.5, 27179.5, "STOP", -112.8, -1.04]]}]},
           "fq": FF.compact(ex, revs, now - 60)}
    core, exts = PR.split(out)
    lines = [json.dumps({"event": "message", "time": now - 61, "message": json.dumps(e)}) for e in exts]
    lines.append(json.dumps({"event": "message", "time": now - 60, "message": json.dumps(core)}))
    return "\n".join(lines) + "\n"


READ = """() => ({ head: document.querySelector('#runHead').textContent, lvl: document.querySelector('#runHead').dataset.level, runLines: document.querySelectorAll('#runLines li').length,
  bars: document.querySelectorAll('#runBars rect').length, tiles: [...document.querySelectorAll('#tiles .tile b')].map((b) => b.textContent), sum: document.querySelector('#sumLine').textContent,
  fill: document.querySelector('#fillHead').textContent, fillLines: [...document.querySelectorAll('#fillLines li')].map((l) => l.textContent), checks: [...document.querySelectorAll('#fillChecks li')].map((l) => l.textContent),
  grp: [...document.querySelectorAll('#grpRows li .nm')].map((l) => l.textContent), grpLine: document.querySelector('#grpLine').textContent, heat: document.querySelectorAll('#heat rect').length,
  heatLines: [...document.querySelectorAll('#heatLines li')].map((l) => l.textContent), mae: [...document.querySelectorAll('#maeLines li')].map((l) => l.textContent), dots: document.querySelectorAll('#maeDots circle').length,
  list: document.querySelectorAll('#maeList li').length, eq: document.querySelectorAll('#eqSvg polyline').length, eqLine: document.querySelector('#eqLine').textContent, dd: document.querySelectorAll('#ddRows li').length,
  src: document.querySelector('#srcNote').textContent, live: !document.querySelector('#live').hidden, nodata: !document.querySelector('#demo').hidden,
  pressed: [...document.querySelectorAll('[aria-checked=true]')].map((b) => b.textContent) })"""


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import net_stub as NS
    now = int(time.time())
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            NS.stub(ctx, stub_feed(now))
            AK.open_app(p, origin, "journal", "edge.html", hook="EDGE")
            p.wait_for_function("() => window.EDGE.feedDone()", timeout=30000, polling=300)
            p.wait_for_timeout(300)
            d = p.evaluate(READ)
            check("c. 390 px, Zlarior 2026: the tiles (120 trades, $ a trade, % that made money, net), the summary in $ and R, the source dated ('not money made')",
                  d["tiles"][0] == "120" and d["tiles"][1].startswith("+$") and d["tiles"][3].startswith("+$43,8") and "a trade at" in d["sum"] and "not money made" in d["src"] and "Data to Oct 14, 2026" in d["src"]
                  and d["pressed"][:2] == ["Zlarior", "2026"] and d["live"] and not d["nodata"], d)
            check("c. the losing run: 'Normal: Zlarior has lost N trades in a row (about $... at $128 a trade)' from the feed's real trades, the 2026 basis, the bars, the drawdown left ($1,025)",
                  d["head"].startswith("Normal") and "at $128 a trade" in d["head"] and d["lvl"] == "ok" and d["runLines"] >= 4 and d["bars"] >= 6, (d["head"], d["runLines"], d["bars"]))
            check("c. fills vs plan from the feed's 'fq': the audit lines (3 trades, slippage, 1 missed), the months and the two checks (Zlarior 'Check', ATLAS 'OK')",
                  d["fill"].startswith("From the PC's fill check") and d["fillLines"][0].startswith("3 Zlarior trades checked") and len(d["checks"]) == 4
                  and any("Zlarior 50K" in c and "Check" in c for c in d["checks"]) and any(c.startswith("ATLAS") and "OK" in c for c in d["checks"]), (d["fill"], d["checks"]))
            check("c. where the money comes from: one row per setup (build-up, London box, Asia box ...), the best / weakest line in $ and R; the heat map has 5 rows of cells and its lines name the busy hours",
                  any("build-up" in g for g in d["grp"]) and any("London box" in g for g in d["grp"]) and "pays the most per trade" in d["grpLine"] and d["heat"] >= 5 * 8
                  and any("Most trades start at" in x for x in d["heatLines"]), (d["grp"], d["grpLine"], d["heatLines"]))
            check("c. MAE / MFE: the meaning line, 4 lines in $ at the real size, 120 dots, the last 10 trades; equity: the curve, the deepest drawdown and 3 dated drawdowns",
                  d["mae"][0].startswith("MAE = how far") and "$128 a trade" in d["mae"][0] and len(d["mae"]) == 5 and d["dots"] == 120 and d["list"] == 10 and d["eq"] == 1 and "Deepest drawdown" in d["eqLine"] and d["dd"] == 3, (d["mae"], d["dots"], d["eqLine"]))
            AK.shot(p, "edge-390-zlarior")
            t = AK.taps(p)
            check("c. every tap target >= 44 x 44 px, no sideways scroll, Jarvis's corner free, no console error, nothing off the site (ntfy answered by the stub)",
                  not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:4], errs[:3], off[:3]))
            p.click("#bots button[data-k=ATLAS]")
            p.click("#sets button[data-k=H2]")
            p.click("#groupBy button[data-k=session]")
            p.wait_for_timeout(250)
            a = p.evaluate(READ)
            check("c. ATLAS, Jul-Oct 2026, by session: the chips move, the rows are sessions, the source says $250 a trade, the run card is ATLAS's ($108 a trade)",
                  a["pressed"] == ["ATLAS", "Jul-Oct", "Session"] and any("NY" in g or "London" in g for g in a["grp"]) and "$250 a trade" in a["src"] and "ATLAS" in a["head"] and "$108 a trade" in a["head"], (a["pressed"], a["grp"], a["head"]))
            AK.shot(p, "edge-390-atlas-h2")
            p.click("#sets button[data-k=real]")
            p.wait_for_timeout(250)
            r = p.evaluate(READ)
            check("c. Real: one row per signal from the feed, the summary splits real money from the paper twin and says it is too few to judge",
                  r["pressed"][1] == "Real" and "Real money:" in r["sum"] and "Too few trades to judge" in r["sum"] and "PC's live feed" in r["src"], (r["sum"], r["src"]))
            prefs = p.evaluate("() => localStorage.getItem('journal.edge.v1')")
            check("c. the view is remembered on this phone only (journal.edge.v1 = bot / set / grouping)", json.loads(prefs) == {"bot": "ATLAS", "set": "real", "by": "session"}, prefs)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, "journal", "edge.html", hook="EDGE")
            p.wait_for_function("() => window.EDGE.feedDone()", timeout=30000, polling=300)
            n = p.evaluate(READ)
            check("c. 375 px, no PC feed (the default stub answers '{}'): the fill card says the PC does not send its checks yet and what it checks; the page still has every card; taps, no sideways scroll, no error",
                  n["fill"].startswith("The PC checks every real fill") and len(n["fillLines"]) == 3 and n["tiles"][0] == "120" and n["dots"] == 120 and not n["live"]
                  and not AK.taps(p) and AK.no_sideways(p) and not errs and not off, (n["fill"], errs[:3], off[:3]))
            AK.shot(p, "edge-375-nofeed")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "journal", "", hook="JOURNAL")
            lk = p.evaluate("() => { const a = document.querySelector('#edgeLink'); const r = a.getBoundingClientRect(); return [a.getAttribute('href'), Math.round(r.height), a.textContent]; }")
            check("c. Mnemosyne's first page shows the link card (44 px) to the bot's edge", lk[0] == "edge.html" and lk[1] >= 44 and "bot's edge" in lk[2] and not errs, (lk, errs[:2]))
            ctx.close()
        srv.shutdown()
        srv2, origin2 = AK.serve({"/journal/edge.json": "{broken"})
        try:
            with AK.browser() as br:
                ctx, p, errs, seen, off = AK.page(br, origin2)
                AK.open_app(p, origin2, "journal", "edge.html", hook="EDGE")
                b = p.evaluate(READ)
                check("c. a broken edge.json: the page still opens (NO DATA chip only when nothing at all loaded), says so in plain words, no console error",
                      "did not load" in b["src"] and b["tiles"][0] == "0" and not errs, (b["src"], errs[:3]))
                ctx.close()
        finally:
            srv2.shutdown()
    except Exception:
        try:
            srv.shutdown()
        except Exception:  # noqa: BLE001
            pass
        raise


if __name__ == "__main__":
    test_static()
    test_maths()
    test_fill_block()
    if "--static" not in sys.argv:
        test_page()
    sys.exit(AK.finish())
