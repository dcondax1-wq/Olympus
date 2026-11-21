"""The NQ page's live chart (owner 2026-11-18, "Live chart + our trades: NQ chart with every entry, stop and target drawn on it").
tools/web_public/nq/nqchart.js (the card, TradingView Lightweight Charts 5.2.1 vendored in nq/vendor/) + nq/nqbars.js (pure: the feed and the
model) reading the PC's "le-bars" post (tools/pc_report.py, tests.test_pc_bars) from the public chart topic <status topic>-bars.

  a. static   the files, the pinned library (sha256 = vendor/NOTICE, its LICENSE, no CDN anywhere), the card on the page (after the banner,
              before the columns), its own module, text only through textContent, no storage, no web address but the attribution link
  b. node     nqbars.model on a fixture post: candles at New York wall time (summer and winter), an entry arrow per trade, an exit dot with its $,
              the open trades' lines (one stop line for the 50K + 25K #2 signal), the list newest first, the chips' counts, the filter,
              the "as of" line, fresh / old / none (never made-up bars), junk
  c. Chromium 390 x 844 (scale 2), the fixture feed from the real packer: the chart draws every bar, the markers and the lines; the four
              chips filter it; a trade row moves the chart to it; Whole day; no bars yet / old bars / no network say so plainly; taps >= 44 px,
              no sideways scroll, nothing off the origin but the feed, no console error. --shots saves the phone screenshots to
              research/handoff/2026-11-18/nqchart/
    python -X utf8 -m tests.test_nq_chart [--static] [--shots]
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tools import pc_report as PR  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "nq")
TOPIC = "olympus-nq-status-00000000c0ffee00"
FEED = json.dumps({"ntfy": "https://ntfy.sh", "topic": TOPIC, "note": "test"})
SHOTS = os.path.join(AK.ROOT, "research", "handoff", "2026-11-18", "nqchart")


# ------------------------------------------------------------------------------------------------ the fixture (the real packer)
def fixture(now, age_s=0, seed=5):
    """(post, info): 180 5-minute bars ending in the bar forming at now - age_s (a random walk on the 0.25 grid that rises into the LONG
    target, rises into ATLAS's stop and falls under the open SHORT) with today's trades of the three accounts at the bars' own prices: the
    50K + 25K #2 LONG to the target, ATLAS SHORT stopped, the 50K + 25K #2 open SHORT. Built by the real packer (tools/pc_report.pack_bars)."""
    t = int(now - age_s)
    end = t // 300 * 300
    e1, x1, e2, x2, e3 = 138, 153, 59, 65, 169                              # bar indices (0 = the oldest of 180): at 13:12 ET = LIT 09:45-11:00, ATLAS 03:10-03:40, the open SHORT 12:20
    drift = lambda i: 1.6 if e1 <= i < x1 else 2.2 if e2 <= i < x2 else -1.3 if i >= e3 else 0.0   # noqa: E731
    rnd, p, bars = random.Random(seed), 21480.0, []
    for i in range(180):
        o = p
        c = round((o + drift(i) + rnd.gauss(0, 6.0)) * 4) / 4
        bars.append((end - (179 - i) * 300, o, max(o, c) + rnd.randint(1, 22) * 0.25, min(o, c) - rnd.randint(1, 22) * 0.25, c))
        p = c
    bt = lambda i: bars[i][0] + 120                                          # noqa: E731  (a time inside bar i)
    c = lambda i: bars[i][4]                                                 # noqa: E731
    acc = {"z50k": ["Zlarior 50K", "LIT", "LIVE"], "z25k2": ["Zlarior 25K #2", "LIT"], "atlas25f": ["ATLAS funded 25K", "ATLAS", "SIM"]}
    gain = lambda q: round((c(x1) - c(e1)) * 2 * q - 1.9 * q, 2)            # noqa: E731
    stop_a = c(e2) + 10.0                                                     # ATLAS's stop 10 points over its short entry; the exit bar reaches it
    bars[x2] = (bars[x2][0], bars[x2][1], max(bars[x2][2], stop_a), bars[x2][3], bars[x2][4])
    closed = [{"k": "z50k", "s": 1, "q": 3, "t": bt(e1), "e": c(e1), "xt": bt(x1), "x": c(x1), "usd": gain(3), "r": 1.99, "why": "TARGET"},
              {"k": "z25k2", "s": 1, "q": 1, "t": bt(e1), "e": c(e1), "xt": bt(x1), "x": c(x1), "usd": gain(1), "r": 2.0, "why": "TARGET"},
              {"k": "atlas25f", "s": -1, "q": 2, "t": bt(e2), "e": c(e2), "xt": bt(x2), "x": stop_a, "usd": round((c(e2) - stop_a) * 2 * 2 - 3.8, 2), "r": -1.02, "why": "STOP"}]
    opens = [{"k": "z50k", "s": -1, "q": 6, "t": bt(e3), "e": c(e3), "sl": c(e3) + 18.5, "tp": c(e3) - 61.25},
             {"k": "z25k2", "s": -1, "q": 2, "t": bt(e3), "e": c(e3), "sl": c(e3) + 18.5, "tp": c(e3) - 61.25}]
    post = PR.pack_bars(bars, opens, closed, acc, now=t, data_t=t - 20, sym="MNQ 12-26", forming=True, day=PR._cme_day(t), trades_t=t - 60)
    return post, {"bars": bars, "opens": opens, "closed": closed, "e": [e1, x1, e2, x2, e3]}


def money_s(v):
    """nqbars.js moneyS in Python: +$156 / -$44 / $0"""
    a = int(abs(v) + 0.5)
    return "$0" if a == 0 else ("+" if v > 0 else "-") + "${:,}".format(a)


def ndjson(*posts):
    return "".join(json.dumps({"event": "message", "time": int(p.get("rt") or 0), "message": json.dumps(p, separators=(",", ":"))}) + "\n" for p in posts)


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    names = ["nqchart.js", "nqbars.js", "vendor/lightweight-charts.standalone.production.js", "vendor/LICENSE", "vendor/NOTICE"]
    check("a. the files: nqchart.js, nqbars.js, vendor/ lightweight-charts + its LICENSE + NOTICE", all(os.path.isfile(os.path.join(D, n)) for n in names),
          [n for n in names if not os.path.isfile(os.path.join(D, n))])
    lib = open(os.path.join(D, "vendor", "lightweight-charts.standalone.production.js"), "rb").read()
    notice, lic = AK.read(os.path.join(D, "vendor", "NOTICE")), AK.read(os.path.join(D, "vendor", "LICENSE"))
    sha = hashlib.sha256(lib).hexdigest()
    check("a. one pinned copy: TradingView Lightweight Charts v5.2.1, its sha256 written in vendor/NOTICE (the attribution notice), the Apache 2.0 LICENSE beside it",
          b"TradingView Lightweight Charts\xe2\x84\xa2 v5.2.1" in lib[:300] and sha in notice and "TradingView Lightweight Charts" in notice and "Apache License" in lic
          and "Version 2.0" in lic, (sha, notice[:120]))
    html, js, core, css = (AK.read(os.path.join(D, n)) for n in ("index.html", "nqchart.js", "nqbars.js", "nq.css"))
    check("a. no CDN anywhere: the page loads the library from vendor/ (pinned ?v=5.2.1), never unpkg / jsdelivr / cdnjs / a tradingview script",
          "vendor/lightweight-charts.standalone.production.js?v=5.2.1" in js and not re.search(r"unpkg|jsdelivr|cdnjs|cdn\.|<script[^>]+tradingview", html + js + core, re.I))
    check("a. the card sits after the banner and before the columns, with its chips, chart box, as-of line, trades list and the attribution link (TradingView + tradingview.com)",
          html.index('id="banner"') < html.index('id="chartCard"') < html.index('id="sceneCard"') and all(f'id="{i}"' in html for i in ("chartChips", "chartBox", "chartAsOf", "chartTrades", "chartPill", "chartWhole"))
          and re.search(r'<a class="attrib"[^>]+href="https://www\.tradingview\.com/"[^>]*>Chart: TradingView Lightweight Charts', html))
    check("a. its own module after nq.js (a chart failure never touches the rest of the page), the stylesheet bumped", html.index('src="nq.js') < html.index('src="nqchart.js?v=') and "nq.css?v=a8" in html
          and "nqchart" not in AK.read(os.path.join(D, "nq.js")))
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function", r"\bimport\s*\(") if re.search(p, js) or re.search(p, core)]
    check("a. text only through textContent (no innerHTML / eval / dynamic import), no storage but the one 2D / 3D choice (nq.chart.view), sends nothing (GET only, no POST / beacon / socket)",
          not bad and "textContent" in js and not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie|sendBeacon|WebSocket|XMLHttpRequest|method:\s*['\"]POST",
                                                            js.replace("window.localStorage.getItem(PREF)", "").replace("window.localStorage.setItem(PREF, v)", "") + core)
          and js.count("localStorage") == 2 and "const PREF = 'nq.chart.view';" in js, bad)
    check("a. nqbars.js is pure (no document / window / fetch / storage), Safari 16 safe (no lookbehind, no .at())",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. the feed is the chart topic of status_feed.json (<topic>-bars or bars_topic), polled like pc_feed.js (/json?poll=1), every 2 minutes",
          "'../status_feed.json'" in js and "-bars" in core and "json?poll=1&since=latest" in core and "POLL_MS = 120000" in js)
    check("a. never fake data: no bundled bars, no demo series; 'has not sent chart bars yet' is the empty state", "has not sent chart bars yet" in core and not re.search(r"demo|fixture", js + core, re.I))
    check("a. phone first: the chart up to 440 px, vertical drags are the page's (vertTouchDrag false, touch-action pan-y), the chips / buttons / rows >= 44 px",
          "clamp(300px, 56vh, 440px)" in css and "vertTouchDrag: false" in js and "touch-action: pan-y" in css and css.count("min-height: 44px") >= 7 and "min-height: 56px" in css)


# ------------------------------------------------------------------------------------------------ b. node
HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((B) => {
  const post = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), now = +process.argv[4], o = {};
  const m = B.model(post, 'all', now);
  o.all = { state: m.state, n: m.candles.length, first: m.candles[0], mk: m.markers.map((x) => [x.kind, x.k, x.shape, x.position, x.color, x.text]), lines: m.lines.map((l) => [l.kind, l.title, l.color, l.style]),
    list: m.list.map((r) => [r.k, r.open, r.money, r.head, r.detail.split(' at ')[0]]), chips: m.chips.map((c) => [c.k, c.name, c.n]), asOf: m.asOf, view: m.view, open: m.open, closed: m.closed, label: m.label, none: m.none,
    extent: m.extent ? [m.extent.min, m.extent.max] : null, colors: m.chips.map((c) => c.color) };
  const z = B.model(post, 'z25k2', now);
  o.z25 = { mk: z.markers.map((x) => [x.kind, x.k, x.text]), lines: z.lines.map((l) => l.title), list: z.list.map((r) => r.k), chips: z.chips.find((c) => c.k === 'z25k2').n, label: z.label };
  const a = B.model(post, 'atlas25f', now);
  o.atlas = { mk: a.markers.map((x) => [x.kind, x.k, x.color, x.text]), lines: a.lines.length, list: a.list.map((r) => [r.k, r.money, r.detail]), view: a.view };
  const p2 = JSON.parse(JSON.stringify(post)), o0 = p2.open[0];
  p2.open.push({ k: 'atlas25f', s: -1, q: 2, t: o0.t, e: o0.e + 5, sl: o0.sl + 5, tp: o0.tp + 5 });
  const m2 = B.model(p2, 'all', now);
  o.tagged = m2.lines.map((l) => l.title); o.extent2 = m2.extent ? [m2.extent.min, m2.extent.max] : null;
  const r = B.model(post, 'rapid25', now);
  o.rapid = [r.markers.length, r.list.length, r.none];
  o.old = (() => { const x = B.model(post, 'all', now + 3 * 3600); return [x.state, x.message, x.asOf]; })();
  o.none = [B.model(null, 'all', now).state, B.model(null, 'all', now).message, B.model(null, 'all', now).candles.length, B.model({ kind: 'le-bars', n: 2, b: [1, 2] }, 'all', now).state];
  o.chipsNone = B.model(null, 'all', now).chips.map((c) => c.name);
  o.tz = [B.et(Date.UTC(2026, 6, 15, 14, 0) / 1000), B.et(Date.UTC(2026, 10, 18, 15, 0) / 1000)].map((p) => [p.hm, p.off, p.day]);
  o.junk = [B.model({ kind: 'le-bars', n: 'x' }, 'all', now).state, ...(() => { const j = B.model(Object.assign({}, post, { open: [null, { k: '<x>', t: 1, e: 1 }, 7], closed: 'x', ac: 5 }), 'all', now); return [j.state, j.list.length, j.candles.length, j.markers.length]; })()];
  o.money = [B.moneyS(156.3), B.moneyS(-43.8), B.moneyS(0), B.px(21060.25), B.ageWords(4000)];
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_node():
    import shutil
    import subprocess
    import tempfile
    exe = shutil.which("node")
    if not exe:
        check("b. node checks skipped: no node", True)
        return
    now = int(time.time())
    post, info = fixture(now)
    tmp = tempfile.mkdtemp(prefix="nqchart_b_")
    try:
        mjs, pj, hj = os.path.join(tmp, "nqbars.mjs"), os.path.join(tmp, "post.json"), os.path.join(tmp, "h.cjs")
        shutil.copy(os.path.join(D, "nqbars.js"), mjs)
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump(post, fh)
        with open(hj, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, hj, mjs, pj, str(now)], capture_output=True, text=True, timeout=120)
        o = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    a = o.get("all") or {}
    b0 = info["bars"][0]
    check("b. every bar is a candle, its time moved to New York wall time (the chart's clock reads ET)", a.get("n") == 180 and a.get("state") == "ok"
          and a["first"]["open"] == b0[1] and a["first"]["time"] - b0[0] in (-4 * 3600, -5 * 3600), (r.stderr[-300:], a.get("first")))
    mk = a.get("mk") or []
    cl = {r["k"]: r for r in info["closed"]}
    check("b. an arrow per entry (long = up under the price, short = down over it) in the account's colour (its chip shows the colour; no text on a phone)",
          sorted(tuple(x[1:]) for x in mk if x[0] == "entry") == sorted([("z50k", "arrowUp", "atPriceTop", "gold", ""), ("z50k", "arrowDown", "atPriceBottom", "gold", ""),
                                                                         ("z25k2", "arrowUp", "atPriceTop", "aegean", ""), ("z25k2", "arrowDown", "atPriceBottom", "aegean", ""),
                                                                         ("atlas25f", "arrowDown", "atPriceBottom", "mauve", "")]), mk)
    check("b. an exit dot on each closed trade's exit bar with its $ (green win / red loss; over the bar for a long, under it for a short, clear of the candles)",
          sorted((x[1], x[2], x[4], x[5]) for x in mk if x[0] == "exit") == sorted([("z50k", "circle", "good", money_s(cl["z50k"]["usd"])), ("z25k2", "circle", "good", money_s(cl["z25k2"]["usd"])),
                                                                                    ("atlas25f", "circle", "bad", money_s(cl["atlas25f"]["usd"]))])
          and cl["z50k"]["usd"] > 0 and cl["atlas25f"]["usd"] < 0
          and sorted((x[1], x[3]) for x in mk if x[0] == "exit") == [("atlas25f", "belowBar"), ("z25k2", "aboveBar"), ("z50k", "aboveBar")], mk)
    check("b. the open trades' lines: one entry (dashed), one stop (red), one target (green) for the 50K + 25K #2 signal, plain words (one signal open)",
          a.get("lines") == [["entry", "Entry", "gold", "dashed"], ["stop", "Stop", "bad", "solid"], ["target", "Target", "good", "solid"]], a.get("lines"))
    op = info["opens"][0]
    check("b. two signals open at once (ATLAS too): each line names its accounts; the price scale takes in every stop and target (extent)",
          o.get("tagged") == ["Z50 + Z25 #2 Entry", "Z50 + Z25 #2 Stop", "Z50 + Z25 #2 Target", "ATLAS Entry", "ATLAS Stop", "ATLAS Target"]
          and a.get("extent") == [op["tp"], op["sl"]] and o.get("extent2") == [op["tp"], op["sl"] + 5], (o.get("tagged"), a.get("extent"), o.get("extent2")))
    check("b. the trades list, newest first: the two open SHORTs ('Open', entry, stop, target), the two LONGs to the target (+$), ATLAS's stop (-$)",
          [x[:2] for x in a.get("list", [])] == [["z50k", True], ["z25k2", True], ["z50k", False], ["z25k2", False], ["atlas25f", False]]
          and a["list"][2][2] == money_s(cl["z50k"]["usd"]) and a["list"][4][2] == money_s(cl["atlas25f"]["usd"]) and a["list"][0][3].startswith("Short 6 micros at ")
          and a["list"][0][4].startswith("Stop ") and a["list"][4][4] == "Stop hit" and a["list"][2][4] == "Target hit", a.get("list"))
    check("b. the chips: All 5, Zlarior 50K 2, Zlarior 25K #2 2, ATLAS funded 1 (the owner's four, in his words), each account with its colour",
          a.get("chips") == [["all", "All", 5], ["z50k", "Zlarior 50K", 2], ["z25k2", "Zlarior 25K #2", 2], ["atlas25f", "ATLAS funded", 1]]
          and a.get("colors") == [None, "gold", "aegean", "mauve"], (a.get("chips"), a.get("colors")))
    check("b. 'As of HH:MM ET, from the PC (just now) · MNQ 12-26.'; the first view = the last 78 bars (6.5 h) reaching back to the open trade",
          re.fullmatch(r"As of \d\d:\d\d ET, from the PC \(just now\) · MNQ 12-26\.", a.get("asOf") or "") and a.get("view") == {"from": 102, "to": 179}
          and a.get("open") == 2 and a.get("closed") == 3 and "180 bars" in (a.get("label") or ""), (a.get("asOf"), a.get("view")))
    z = o.get("z25") or {}
    check("b. filter Zlarior 25K #2: only its entry / exit markers (no tags), its lines without account names, its two rows",
          z.get("mk") == [["entry", "z25k2", ""], ["exit", "z25k2", money_s(cl["z25k2"]["usd"])], ["entry", "z25k2", ""]] and z.get("lines") == ["Entry", "Stop", "Target"]
          and z.get("list") == ["z25k2", "z25k2"] and z.get("chips") == 2 and "on Zlarior 25K #2" in z.get("label", ""), z)
    at = o.get("atlas") or {}
    check("b. filter ATLAS funded: its SHORT arrow (mauve) and its red exit dot with its -$, no lines (no open trade), 'Stop hit at <price>'",
          at.get("mk") == [["entry", "atlas25f", "mauve", ""], ["exit", "atlas25f", "bad", money_s(cl["atlas25f"]["usd"])]] and at.get("lines") == 0
          and at["list"][0][:2] == ["atlas25f", money_s(cl["atlas25f"]["usd"])]
          and at["list"][0][2].startswith("Stop hit at ") and at.get("view") == {"from": 43, "to": 179}, at)
    check("b. an account with no trade today: no markers, no rows, a plain sentence", o.get("rapid") == [0, 0, "No trade on this account today."], o.get("rapid"))
    old = o.get("old") or []
    check("b. three hours later the same post is 'old': the PC's last bars with their time and age (never shown as live)", old and old[0] == "old"
          and old[1].startswith("These are the PC's last bars (") and "3 hours" in old[1] and "about every hour while the bots trade" in old[1] and "ago" in old[2], old)
    check("b. no post: state 'none', the plain sentence, zero candles (never made-up bars); a broken post too",
          o.get("none") == ["none", "The PC has not sent chart bars yet (it needs the new update first). New bars come from its NinjaTrader about every hour while the bots trade (01:50-16:10 ET) and right after each entry or exit.", 0, "none"]
          and o.get("chipsNone") == ["All", "Zlarior 50K", "Zlarior 25K #2", "ATLAS funded"], o.get("none"))
    check("b. New York time in summer (-4 h) and winter (-5 h)", o.get("tz") == [["10:00", -14400, "2026-07-15"], ["10:00", -18000, "2026-11-18"]], o.get("tz"))
    check("b. junk never throws: a bad post is 'none'; junk trades / accounts are skipped, the real bars stay", o.get("junk") == ["none", "ok", 0, 180, 0], o.get("junk"))
    check("b. money words: +$156, -$44, $0, prices with 2 decimals, ages in words", o.get("money") == ["+$156", "-$44", "$0", "21,060.25", "1 hour 6 minutes"]
          and money_s(156.3) == "+$156" and money_s(-43.8) == "-$44", o.get("money"))


# ------------------------------------------------------------------------------------------------ c. the page
SNAP = """() => { const C = window.NQCHART, S = C.S, ts = S.chart ? S.chart.timeScale() : null, lr = ts ? ts.getVisibleLogicalRange() : null, pr = S.chart ? S.chart.priceScale('right').getVisibleRange() : null;
  return { ready: C.ready(), state: S.model && S.model.state, pill: document.querySelector('#chartPill').textContent, pillCls: document.querySelector('#chartPill').className,
    asOf: document.querySelector('#chartAsOf').hidden ? '' : document.querySelector('#chartAsOf').textContent, msg: document.querySelector('#chartMsg').hidden ? '' : document.querySelector('#chartMsg').textContent,
    chips: [...document.querySelectorAll('#chartChips .chip')].map((b) => [b.dataset.k, b.querySelector('.cname').textContent, b.getAttribute('aria-pressed'), (b.querySelector('.cn') || {}).textContent || '']),
    canvas: document.querySelectorAll('#chart canvas').length, data: S.series ? S.series.data().length : 0, marks: S.marks ? S.marks.markers().length : 0,
    lines: S.lines.map((l) => l.options().title), rows: [...document.querySelectorAll('#chartTrades .ctrade')].map((li) => [li.dataset.k, li.dataset.open, li.querySelector('.ctr b').textContent]),
    none: (document.querySelector('#chartTrades .cnone') || {}).textContent || '', lr: lr ? [Math.round(lr.from), Math.round(lr.to)] : null, n: S.model ? S.model.n : 0,
    box: document.querySelector('#chartBox').getBoundingClientRect().height, empty: document.querySelector('#chartBox').classList.contains('empty'),
    whole: document.querySelector('#chartWhole').hidden ? '' : document.querySelector('#chartWhole').textContent, key: !document.querySelector('#chartKey').hidden,
    top: document.querySelector('#chartCard').getBoundingClientRect().top + scrollY, boxBottom: document.querySelector('#chartBox').getBoundingClientRect().bottom + scrollY,
    lib: !!window.LightweightCharts, err: S.err, mode: S.mode, pr: pr ? [pr.from, pr.to] : null, dots: [...document.querySelectorAll('#chartChips .chip .cdot')].length }; }"""


def open_chart(p, origin, q=""):
    AK.open_app(p, origin, "nq", q)
    p.wait_for_function("window.NQCHART && window.NQCHART.ready()", timeout=60000, polling=200)
    p.wait_for_timeout(400)


def shot(p, name, on):
    if on:
        os.makedirs(SHOTS, exist_ok=True)
        p.screenshot(path=os.path.join(SHOTS, name + ".png"))


def test_page(shots=False):
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_page as NP
    import datetime as dt
    from zoneinfo import ZoneInfo
    now = int(dt.datetime(2026, 11, 18, 13, 12, tzinfo=ZoneInfo("America/New_York")).timestamp())   # a normal Wednesday, 13:12 ET (the browser's clock too)
    post, info = fixture(now)
    real_time = NP.time.time
    NP.time.time = lambda: float(now)                     # home.json "3 minutes ago" at that same clock
    try:
        home = NP.home_json(180)
    finally:
        NP.time.time = real_time
    bars_url = f"/{TOPIC}-bars/json"
    core_url = f"/{TOPIC}/json"
    srv, origin = AK.serve({"/status_feed.json": FEED, "/home.json": home})

    def page(br, **kw):
        ctx, p, errs, seen, off = AK.page(br, origin, **kw)
        p.clock.set_fixed_time(dt.datetime.fromtimestamp(now, dt.timezone.utc))   # Date.now() = 13:12 ET: the fixture's "just now"
        return ctx, p, errs, seen, off
    try:
        with AK.browser() as br:
            # the live chart with the fixture feed
            ctx, p, errs, seen, off = page(br, mock={bars_url: ndjson(post), core_url: "{}"})
            t0 = time.time()
            open_chart(p, origin)
            took = time.time() - t0
            s = p.evaluate(SNAP)
            check("c. the chart draws: the vendored library, a canvas, all 180 bars, 5 entry arrows + 3 exit dots, the 'Live' pill, the as-of line from the PC",
                  s["lib"] and s["canvas"] >= 1 and s["data"] == 180 and s["marks"] == 8 and s["pill"] == "Live" and "ok" in s["pillCls"] and not s["msg"]
                  and s["asOf"] == "As of 13:11 ET, from the PC (just now) · MNQ 12-26." and not errs, (s, errs[:3]))
            op = info["opens"][0]
            check("c. the open SHORT's lines: entry, stop, target (one each for the 50K + 25K #2 signal), and the price scale reaches its stop and its target",
                  sorted(s["lines"]) == ["Entry", "Stop", "Target"] and s["pr"] and s["pr"][0] <= op["tp"] and s["pr"][1] >= op["sl"], (s["lines"], s["pr"], op["tp"], op["sl"]))
            check("c. the four chips in the owner's words with their counts and colour dots, All pressed; the trades list newest first with $ (Open, +$, -$)",
                  s["chips"] == [["all", "All", "true", "5"], ["z50k", "Zlarior 50K", "false", "2"], ["z25k2", "Zlarior 25K #2", "false", "2"], ["atlas25f", "ATLAS funded", "false", "1"]]
                  and s["dots"] == 3 and [r[:2] for r in s["rows"]] == [["z50k", "1"], ["z25k2", "1"], ["z50k", "0"], ["z25k2", "0"], ["atlas25f", "0"]]
                  and s["rows"][0][2] == "Open" and s["rows"][2][2].startswith("+$") and s["rows"][4][2].startswith("-$"), (s["chips"], s["rows"]))
            check("c. big on the phone: the chart box 300-440 px tall and wholly on the first 390 x 844 screen (the chips under it), the first view = the last 78 bars to the open trade",
                  300 <= s["box"] <= 441 and s["boxBottom"] <= 844 and s["lr"] and s["lr"][1] >= 179 and 100 <= s["lr"][0] <= 104 and s["key"] and s["whole"] == "Whole day"
                  and s["mode"] == "default", (s["box"], s["top"], s["boxBottom"], s["lr"], s["mode"]))
            check("c. fast: the page and its chart are ready within 15 s here (one feed poll, the library from vendor/)", took < 15, took)
            check("c. it read the site's status_feed.json, the library from vendor/ and the chart topic (mocked), nothing else off the origin; no console error",
                  any(u.endswith("/status_feed.json") for u in seen) and any("vendor/lightweight-charts" in u for u in seen) and any(bars_url in u for u in p.mocked) and not off and not errs, (off[:3], errs[:3]))
            check("c. taps >= 44 px (chips, rows, Whole day, the attribution link), no sideways scroll, Jarvis's corner free", not AK.taps(p) and AK.no_sideways(p) and not AK.corner(p), AK.taps(p)[:5])
            p.evaluate("window.scrollTo(0, 0)")
            p.wait_for_timeout(200)
            shot(p, "nq-chart-all", shots)
            # filter: Zlarior 25K #2
            p.locator('#chartChips .chip[data-k="z25k2"]').click()
            p.wait_for_timeout(300)
            z = p.evaluate(SNAP)
            check("c. tap 'Zlarior 25K #2': pressed, only its 2 entries + 1 exit, its lines, its two rows",
                  [c[2] for c in z["chips"]] == ["false", "false", "true", "false"] and z["marks"] == 3 and sorted(z["lines"]) == ["Entry", "Stop", "Target"]
                  and [r[0] for r in z["rows"]] == ["z25k2", "z25k2"] and z["data"] == 180, z)
            p.locator('#chartChips .chip[data-k="atlas25f"]').click()
            p.wait_for_timeout(300)
            a = p.evaluate(SNAP)
            check("c. tap 'ATLAS funded': its SHORT arrow and red exit dot, no lines (nothing open), one row with its -$, the view reaches back to its 03:10 ET trade",
                  a["marks"] == 2 and a["lines"] == [] and [r[:2] for r in a["rows"]] == [["atlas25f", "0"]] and a["rows"][0][2] == money_s(info["closed"][2]["usd"])
                  and a["lr"] and a["lr"][0] <= info["e"][2] - 4 and a["lr"][1] >= 179, (a["lr"], a["rows"]))
            shot(p, "nq-chart-atlas", shots)
            # a trade row moves the chart to it
            p.locator('#chartChips .chip[data-k="all"]').click()
            p.wait_for_timeout(250)
            p.locator("#chartTrades .ctrade").nth(2).locator("button").click()
            p.wait_for_timeout(500)
            f = p.evaluate(SNAP)
            e1, x1 = info["e"][0], info["e"][1]
            check("c. tap the 50K's closed trade: the chart moves to it (its entry and exit in view, 24 bars around)", f["lr"] and e1 - 30 <= f["lr"][0] <= e1 and f["lr"][1] >= x1
                  and f["mode"] == "focus", (f["lr"], e1, x1, f["mode"]))
            p.locator("#chartWhole").click()
            p.wait_for_timeout(300)
            w = p.evaluate(SNAP)
            check("c. 'Whole day' shows every bar (15 hours), the button then says 'Last 6 hours'", w["lr"] and w["lr"][0] <= 0 and w["lr"][1] >= 179 and w["whole"] == "Last 6 hours", w["lr"])
            # v5 (owner 2026-11-20 15:50 ET "it needs some 3D, it needs some effects"): the glow-up and the 3D toggle
            g = p.evaluate("""() => { const S = window.NQCHART.S, d = document.querySelector('#chartPulse');
              return { area: S.area ? S.area.data().length : 0, tag: S.tag ? S.tag.data().length : 0, tagCol: S.tag ? S.tag.options().color : '', pulse: d && !d.hidden,
                three: !!window.NQCHART3D || [...document.scripts].some((x) => /nqchart3d/.test(x.src)), btn: document.querySelector('#chart3dBtn').textContent,
                pressed: document.querySelector('#chart3dBtn').getAttribute('aria-pressed') }; }""")
            check("c. the glow-up: a violet area under the day's closes, the last price as a GOLD tag + a pulsing dot on the newest close; 3D not fetched until asked; the toggle says 3D",
                  g["area"] == 180 and g["tag"] == 1 and g["tagCol"].lower() == "#f1c14b" and g["pulse"] and not g["three"] and g["btn"] == "3D" and g["pressed"] == "false", g)
            p.locator("#chart3dBtn").click()
            try:
                p.wait_for_function("window.NQCHART.S.mounted3d || (window.NQCHART3D && !window.NQCHART.S.view3d)", timeout=30000)
            except Exception:
                pass
            t = p.evaluate("""() => ({ m: !!window.NQCHART.S.mounted3d, c: document.querySelectorAll('#chart3d canvas').length, pref: localStorage.getItem('nq.chart.view'),
              btn: document.querySelector('#chart3dBtn').textContent, pressed: document.querySelector('#chart3dBtn').getAttribute('aria-pressed') })""")
            check("c. tap 3D: the 3D candles load (nqchart3d.js, only now) into the chart box, the button says 2D (pressed), the choice is kept on this phone",
                  t["m"] and t["c"] == 1 and t["pref"] == "3d" and t["btn"] == "2D" and t["pressed"] == "true", t)
            shot(p, "nq-chart-3d", shots)
            p.locator("#chart3dBtn").click()
            p.wait_for_timeout(300)
            t2 = p.evaluate("() => ({ m: !!window.NQCHART.S.mounted3d, c: document.querySelectorAll('#chart3d canvas').length, pref: localStorage.getItem('nq.chart.view') })")
            check("c. tap 2D: the 3D view is freed (no canvas left), back to the flat chart, the choice kept", not t2["m"] and t2["c"] == 0 and t2["pref"] == "2d", t2)
            # a pinch / drag on the chart must not scroll the page sideways
            check("c. still no sideways scroll and no console error after the taps", AK.no_sideways(p) and not errs, errs[:3])
            ctx.close()
            # ?acct= opens on one account
            ctx, p, errs, seen, off = page(br, mock={bars_url: ndjson(post), core_url: "{}"})
            open_chart(p, origin, "?acct=z50k")
            q = p.evaluate(SNAP)
            check("c. ?acct=z50k opens on Zlarior 50K", [c[2] for c in q["chips"]] == ["false", "true", "false", "false"] and q["marks"] == 3 and not errs, q["chips"])
            ctx.close()
            # no bars yet: the plain sentence, no chart drawn
            ctx, p, errs, seen, off = page(br, mock={bars_url: "{}", core_url: "{}"})
            open_chart(p, origin)
            n = p.evaluate(SNAP)
            check("c. the PC has not sent bars: 'Waiting for the PC', the plain sentence, no candles drawn, the chips without counts, no list; the box keeps "
                  "its height (300-441 px: perf 2026-11-20, a late shrink was a 0.38 layout shift)",
                  n["state"] == "none" and n["pill"] == "Waiting for the PC" and n["msg"].startswith("The PC has not sent chart bars yet") and n["data"] == 0 and n["marks"] == 0
                  and all(c[3] == "" for c in n["chips"]) and not n["rows"] and n["empty"] and 300 <= n["box"] <= 441 and not n["asOf"] and not errs, (errs[:3], n))
            check("c. ... taps >= 44 px, no sideways scroll", not AK.taps(p) and AK.no_sideways(p), AK.taps(p)[:3])
            shot(p, "nq-chart-waiting", shots)
            ctx.close()
            # old bars (3 hours): said plainly, still drawn (they are real)
            oldp, _ = fixture(now, age_s=3 * 3600)
            ctx, p, errs, seen, off = page(br, mock={bars_url: ndjson(oldp), core_url: "{}"})
            open_chart(p, origin)
            o = p.evaluate(SNAP)
            check("c. bars 3 hours old: 'Last bars' (amber), the as-of line says the PC's last bars and their age, the real bars still drawn",
                  o["state"] == "old" and o["pill"] == "Last bars" and "warn" in o["pillCls"] and "These are the PC's last bars" in o["asOf"] and "3 hours" in o["asOf"] and o["data"] == 180 and not errs, o)
            ctx.close()
            # no network to ntfy: said plainly
            ctx, p, errs, seen, off = page(br, mock={core_url: "{}"})
            p.route(f"**/{TOPIC}-bars/**", lambda r: r.abort())
            open_chart(p, origin)
            x = p.evaluate(SNAP)
            check("c. ntfy cannot be reached: 'Could not reach the PC's chart feed', no chart, no console error", x["state"] == "none" and x["msg"].startswith("Could not reach the PC's chart feed")
                  and x["data"] == 0 and not errs, x)
            ctx.close()
            # phone QA 2026-11-20 12:20: an exit on the newest bar ("+$514.18") was cut by the price axis; its whole tag stays inside the plot
            lastp = PR.pack_bars(info["bars"], [], [{**info["closed"][2], "xt": info["bars"][179][0] + 120, "x": info["bars"][179][4], "usd": 514.18, "r": 2.0, "why": "TARGET"}],
                                 {"atlas25f": ["ATLAS funded 25K", "ATLAS", "SIM"]}, now=now, data_t=now - 20, sym="MNQ 12-26", forming=True, day=PR._cme_day(now), trades_t=now - 60)
            ctx, p, errs, seen, off = page(br, mock={bars_url: ndjson(lastp), core_url: "{}"})
            open_chart(p, origin)
            fit = p.evaluate("""() => { const S = window.NQCHART.S, ts = S.chart.timeScale(), cx = document.createElement('canvas').getContext('2d');
              cx.font = '11px ' + getComputedStyle(document.body).fontFamily;
              return S.marks.markers().filter((m) => m.text).map((m) => [m.text, Math.round(ts.timeToCoordinate(m.time) + cx.measureText(m.text).width / 2), Math.round(ts.width())]); }""")
            check("c. an exit on the newest bar: its '+$514' tag ends inside the plot (left of the price axis), the newest bar still in view",
                  fit and all(x[1] <= x[2] - 2 for x in fit) and any(x[0].startswith("+$514") for x in fit) and not errs, (fit, errs[:2]))
            shot(p, "nq-chart-lastexit", shots)
            ctx.close()
            # 375 x 667, LITE, reduced motion: still the chart, no sideways scroll
            ctx, p, errs, seen, off = page(br, w=375, h=667, reduced=True, lite=True, mock={bars_url: ndjson(post), core_url: "{}"})
            open_chart(p, origin)
            l5 = p.evaluate(SNAP)
            check("c. 375 x 667, LITE, reduced motion: the chart draws (300 px), no sideways scroll, taps >= 44 px, no error",
                  l5["data"] == 180 and l5["marks"] == 8 and 299 <= l5["box"] <= 441 and AK.no_sideways(p) and not AK.taps(p) and not errs, (l5["box"], AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page(shots="--shots" in sys.argv)
    AK.finish()
