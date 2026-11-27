"""The STRATEGY ROOMS (day-strats 2026-11-27): nq/strat.html?s=lit|atlas|blitz|poseidon + tools/build_strats.py + the NQ home's 4-room switcher.

  a. builder   strats/<s>.json fresh (--check), the same columns everywhere, src only live / paper / backtest / skip, LIT's periods = the research
               file's (2026 H1 80 trades PF 4.98, Jul-Oct 40 PF 2.91, 2021-25 511 PF 1.01), ATLAS prices joined on every trade, BLITZ / POSEIDON
               marked PAPER, POSEIDON's skipped signals kept with their why, equity per real account
  b. static    the page: 4 tabs, window.NQ_STRAT before the chart, strat.js + nqchartfeed.js modules, text only, OLYMPUS NIGHT (no cyan /
               olive), the Brain loaded lazily (brainview.js, the brains helper's contract); the home: #stratNav with the 4 rooms, no script
  c. Chromium  each room at 390 (Zlarior also at 1440): the right tab current, PAPER only on BLITZ / POSEIDON, the chart's chips = that bot's
               accounts only, the live layer filtered (Zlarior's stage, ATLAS's EMA, POSEIDON's footprint), a tap on a history dot opens its
               trade card (REAL / PAPER / BACKTEST, prices, $, R, why), Older / Newer step, the Real filter, the equity lines, 8 stat tiles,
               the Brain card (a stub module mounts with s + getState; without it a plain sentence), no sideways scroll, taps >= 44, no error
  d. the home  the 4-room switcher on the NQ page at 390: 4 links >= 44 px, no sideways scroll
    python -X utf8 -m tests.test_strats [--static] [--shots]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_chart as T  # noqa: E402
from tests import test_livechart as LC  # noqa: E402

check = AK.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(AK.WEB, "nq")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "strats", "shots")
NOW = LC.NOW


def J(s):
    return json.load(open(os.path.join(D, "strats", s + ".json"), encoding="utf-8"))


def test_builder():
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "build_strats.py"), "--check"], capture_output=True, text=True, timeout=300)
    check("a. strats/<s>.json are fresh: tools/build_strats.py --check (rebuild them with it when the research changes)", r.returncode == 0, (r.stdout + r.stderr)[-300:])
    rooms = {s: J(s) for s in ("lit", "atlas", "blitz", "poseidon")}
    cols = ["src", "day", "t", "xt", "side", "e", "sl", "tg", "x", "k", "usd", "r", "q", "acct", "tag", "why"]
    bad = [(s, i) for s, d in rooms.items() for i, x in enumerate(d["trades"]) if len(x) != 16 or x[0] not in ("live", "paper", "backtest", "skip")]
    check("a. the same 16 columns in every room, src only live / paper / backtest / skip", all(d["cols"] == cols for d in rooms.values()) and not bad, bad[:3])
    sp = {x["k"]: x for x in rooms["lit"]["spans"]}
    check("a. Zlarior's periods = the research file's: 2026 H1 80 trades PF 4.98 max DD -$2,196; Jul-Oct 40 trades PF 2.91; 2021-25 511 trades PF 1.01",
          sp.get("2026 H1", {}).get("n") == 80 and sp["2026 H1"]["pf"] == 4.98 and sp["2026 H1"]["max_dd"] == -2196
          and any(k.startswith("2026 Jul") and v["n"] == 40 and v["pf"] == 2.91 for k, v in sp.items()) and sp.get("2021-25", {}).get("n") == 511 and sp["2021-25"]["pf"] == 1.01, sp)
    at = rooms["atlas"]
    check("a. ATLAS: the combined book (1,288 backtest trades) with entry / stop / target / exit joined on every one + its real trades",
          sum(1 for x in at["trades"] if x[0] == "backtest") == 1288 and all(x[5] is not None and x[6] is not None for x in at["trades"] if x[0] == "backtest")
          and at["data_to"]["prices_joined"] == "1288 of 1288" and any(x[0] == "live" for x in at["trades"]))
    check("a. BLITZ and POSEIDON are PAPER; Zlarior and ATLAS are not", rooms["blitz"]["paper"] and rooms["poseidon"]["paper"] and not rooms["lit"]["paper"] and not rooms["atlas"]["paper"])
    po = rooms["poseidon"]["trades"]
    check("a. POSEIDON keeps its skipped signals with why (taken ones = paper)", any(x[0] == "skip" and x[15].count("skipped:") for x in po) and any(x[0] == "paper" for x in po),
          [x[15] for x in po[:2]])
    check("a. BLITZ: no prices in its source = null prices (never invented), the paper summary carried with its honest note",
          all(x[5] is None for x in rooms["blitz"]["trades"]) and rooms["blitz"]["data_to"]["paper_summary"]["n"] > 0 and "not in the cloud" in rooms["blitz"]["data_to"]["paper_note"])
    check("a. equity: the backtest curve + one curve per real account (Zlarior 50K, ATLAS funded)",
          rooms["lit"]["equity"]["backtest"] and "Zlarior 50K" in rooms["lit"]["equity"]["live"] and rooms["atlas"]["equity"]["live"])
    check("a. the room files stay phone-light (each < 320 KB)", all(os.path.getsize(os.path.join(D, "strats", s + ".json")) < 320_000 for s in rooms))


def test_static():
    html, js, css = (AK.read(os.path.join(D, n)) for n in ("strat.html", "strat.js", "strat.css"))
    home, nav = AK.read(os.path.join(D, "index.html")), AK.read(os.path.join(D, "stratnav.css"))
    check("a. strat.html: the 4 tabs, window.NQ_STRAT set before the chart modules, strat.js + nqchartfeed.js, the chart card ids nqchart.js needs",
          all(f'href="strat.html?s={s}"' in html for s in ("lit", "atlas", "blitz", "poseidon")) and html.index("window.NQ_STRAT") < html.index('src="nqchartfeed.js')
          and 'src="strat.js?v=' in html and all(f'id="{i}"' in html for i in ("chartCard", "chartBox", "chart", "chartChips", "chartTrades", "chartMsg", "brainMount")))
    check("a. text only (no innerHTML / eval), GET only", not re.search(r"\.innerHTML|insertAdjacentHTML|\beval\s*\(|new Function|method:\s*['\"]POST", js))
    check("a. the Brain: brainview.js imported lazily (IntersectionObserver), mount(el, { s, getState }) and a plain sentence when it is missing",
          "import('./brainview.js?v=1')" in js and "IntersectionObserver" in js and "getState" in js and "not on this copy of the site yet" in js)
    cyan = re.findall(r"#(?:67e8f9|22d3ee|06b6d4|0ff|00ffff)\b", js + css + nav, re.I)
    check("a. OLYMPUS NIGHT: black, violet, gold, mint; no cyan, no olive / brown", not cyan and not re.search(r"olive|brown", re.sub(r"--ag-olive|/\*.*?\*/", "", css + nav, flags=re.S), re.I), cyan)
    small = [x for x in re.findall(r"(\d+(?:\.\d+)?)px[/ ]", re.sub(r"/\*.*?\*/", "", css + nav, flags=re.S)) if float(x) < 12 and float(x) > 4]
    check("a. text >= 12 px in the room's styles", not [x for x in re.findall(r"font:\s*\d+\s+(\d+(?:\.\d+)?)px", css + nav) if float(x) < 12], small)
    m = re.search(r'<nav class="snav" id="stratNav"[^>]*>(.*?)</nav>', home, re.S)
    check("a. the NQ home: #stratNav with the 4 rooms as plain links (no script), its own small stylesheet", m and m.group(1).count('href="strat.html?s=') == 4
          and "<script" not in m.group(1) and 'href="stratnav.css?v=' in home)


SNAP = """() => { const S = window.STRAT.S, C = window.NQCHART && window.NQCHART.S, q = (id) => document.getElementById(id);
  return { cur: (document.querySelector('#srTabs a[aria-current="page"]') || {}).dataset ? document.querySelector('#srTabs a[aria-current="page"]').dataset.s : null,
    paper: !q('srPaper').hidden, chips: [...document.querySelectorAll('#chartChips .chip')].map((b) => b.dataset.k),
    stage: !!q('lcStage'), ema: C && C.emaS ? C.emaS.data().length : 0, strip: !!q('lcStrip'), levels: C && C.live ? C.live.levels.map((l) => l.src) : [],
    dots: document.querySelectorAll('#histPlot circle:not(.sr-sel)').length, rows: S.rows.length, eqLines: document.querySelectorAll('#eqPlot path').length,
    tiles: document.querySelectorAll('#statTiles .sr-tile').length, sigs: document.querySelectorAll('#sigList li').length, src: q('srSrc').textContent,
    card: q('tradeCard').hidden ? '' : q('tradeCard').textContent }; }"""


def tap_dot(p, i):
    pt = p.evaluate(f"""() => {{ const P = window.STRAT.S.hp, r = P.svg.getBoundingClientRect(), vb = P.svg.viewBox.baseVal, k = r.width / vb.width, d = P.pts[{i}];
      P.svg.scrollIntoView({{ block: 'center', behavior: 'instant' }}); const r2 = P.svg.getBoundingClientRect(); return {{ x: r2.left + d[0] * k, y: r2.top + d[1] * k }}; }}""")
    p.wait_for_timeout(200)
    p.touchscreen.tap(pt["x"], pt["y"])
    p.wait_for_timeout(300)


def test_page(shots=False):
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_page as NP
    post, info = T.fixture(NOW)
    lite, asia = LC.glance(info)
    real = NP.time.time
    NP.time.time = lambda: float(NOW)
    try:
        home = NP.home_json(180)
    finally:
        NP.time.time = real
    srv, origin = AK.serve({"/status_feed.json": T.FEED, "/home.json": home})
    mock = {f"/{T.TOPIC}-bars/json": T.ndjson(post), f"/{T.TOPIC}/json": LC.core_body(lite, NOW - 30)}
    stub = ("export function mount(el, o) { window.__bv = { s: o.s, st: o.getState ? o.getState() : null }; el.textContent = 'brain ' + o.s; "
            "return { update() { window.__bvu = (window.__bvu || 0) + 1; }, setStrategy() {}, destroy() {} }; }")
    try:
        with AK.browser() as br:
            for s, w, h in (("lit", 390, 844), ("lit", 1440, 900), ("atlas", 390, 844), ("blitz", 390, 844), ("poseidon", 390, 844)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock=mock)
                p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
                if s != "atlas":
                    p.route("**/nq/brainview.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=stub))
                p.goto(f"{origin}/nq/strat.html?s={s}")
                p.wait_for_function("window.STRAT && window.STRAT.ready() && window.NQCHART && window.NQCHART.ready()", timeout=60000)
                p.wait_for_timeout(1200)
                x = p.evaluate(SNAP)
                tag = f"c. {s} {w}px"
                check(f"{tag}: its tab is current; PAPER shown only for BLITZ / POSEIDON", x["cur"] == s and x["paper"] == (s in ("blitz", "poseidon")), (x["cur"], x["paper"]))
                want = {"lit": ["bot:LIT", "z50k", "z25k2"], "atlas": ["bot:ATLAS", "atlas25f"], "blitz": [], "poseidon": []}[s]
                check(f"{tag}: the chart's chips = this strategy's accounts only", x["chips"] == want, x["chips"])
                if s == "lit":
                    check(f"{tag}: the live layer = Zlarior's: its stage strip, its levels, no ATLAS EMA", x["stage"] and x["ema"] == 0 and set(x["levels"]) <= {"lit"} and x["levels"], x)
                if s == "atlas":
                    check(f"{tag}: the live layer = ATLAS's: its EMA 50, no Zlarior stage, no Zlarior levels", x["ema"] > 0 and not x["stage"] and "lit" not in x["levels"], x)
                if s in ("blitz", "poseidon"):
                    check(f"{tag}: no Zlarior / ATLAS marks in a paper room", not x["stage"] and x["ema"] == 0 and "lit" not in x["levels"] and "atlas" not in x["levels"], x)
                check(f"{tag}: every trade drawn (one dot each), equity lines, 8 stat tiles, signals listed", x["dots"] == x["rows"] > 0 and x["eqLines"] >= 1 and x["tiles"] == 8 and x["sigs"] >= 1, x)
                tap_dot(p, x["rows"] - 1)
                c = p.evaluate(SNAP)["card"]
                check(f"{tag}: a tap on the newest dot opens its trade card (tag, entry / stop / target / exit, $, R)",
                      re.search(r"REAL|PAPER|BACKTEST|SKIPPED", c) and all(k in c for k in ("Entry", "Stop", "Target", "Exit")) and "$" in c and "R" in c, c[:200])
                if c:
                    sel = p.evaluate("window.STRAT.S.sel")
                    p.locator("#tradeCard .sr-nb").first.tap()
                    p.wait_for_timeout(200)
                    check(f"{tag}: 'Older' steps to the trade before", sel > 0 and p.evaluate("window.STRAT.S.sel") == sel - 1, sel)
                if s == "lit":
                    p.locator("#histSrc button", has_text="Real").tap()
                    p.wait_for_timeout(300)
                    r = p.evaluate("() => window.STRAT.S.rows.map((r) => r[0])")
                    check(f"{tag}: the Real filter shows the real-account trades only (gold, REAL)", r and set(r) == {"live"}, r)
                p.evaluate("document.getElementById('brainCard').scrollIntoView({ block: 'center', behavior: 'instant' })")
                p.wait_for_timeout(900)
                b = p.evaluate("() => [document.getElementById('brainMount').textContent, window.__bv || null]")
                if s == "atlas":
                    check(f"{tag}: without brainview.js the Brain card says so in plain words", "not on this copy of the site yet" in b[0], b)
                else:
                    check(f"{tag}: the Brain mounts brainview.js lazily with s and getState (the PC's post)", b[1] and b[1]["s"] == s and b[1]["st"] and b[1]["st"]["lite"], b)
                if shots and w == 390 and s in ("lit", "poseidon"):
                    os.makedirs(SHOTS, exist_ok=True)
                    p.evaluate("window.scrollTo(0, 0)")
                    p.screenshot(path=os.path.join(SHOTS, f"strat_{s}_390.png"), full_page=True)
                if shots and w == 1440:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.evaluate("document.getElementById('histCard').scrollIntoView({ block: 'start', behavior: 'instant' })")
                    p.screenshot(path=os.path.join(SHOTS, "strat_lit_1440.png"))
                check(f"{tag}: no sideways scroll, taps >= 44 px, no console error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:3]))
                ctx.close()
            # d. the NQ home's switcher
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock=mock)
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
            T.open_chart(p, origin)
            n = p.evaluate("() => [...document.querySelectorAll('#stratNav a')].map((a) => { const r = a.getBoundingClientRect(); return [a.getAttribute('href'), Math.round(r.height), Math.round(r.width)]; })")
            check("d. the NQ home: 4 room links (Zlarior / ATLAS / BLITZ / POSEIDON), each >= 44 px, no sideways scroll",
                  [x[0] for x in n] == [f"strat.html?s={s}" for s in ("lit", "atlas", "blitz", "poseidon")] and all(x[1] >= 44 and x[2] >= 44 for x in n) and AK.no_sideways(p), n)
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_builder()
    test_static()
    if "--static" not in sys.argv:
        test_page(shots="--shots" in sys.argv)
    AK.finish()
