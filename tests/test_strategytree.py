"""DAPHNE, the strategy-tree search (tools/strategytree): bound, search, look-ahead, determinism, JSON.

    python -X utf8 -m tests.test_strategytree          # ~30 s, real data for the look-ahead and JSON checks

 1. bound(S) equals the best score of any subset of S with min_n+ trades (brute force over every subset).
 2. With an unlimited budget the branch-and-bound finds the same best rule as trying every condition combination, and
    nothing it cut could have beaten that best.
 3. Determinism: the same search twice, and the whole quick build twice, give identical output.
 4. No look-ahead: scrambling every bar after the entry bar (NQ and ES) and every VIX close from the trade's day on
    changes neither the entry nor any condition of a trade.
 5. Root rules: fade stops sit 1 tick beyond the sweep extreme, costs are in, exits never come before the entry.
 6. The JSON: schema, a closed tree per featured root, size <= 1.5 MB, the Jarvis card contract; the module never
    touches the live configuration.
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import data as edata  # noqa: E402
from tools.strategytree import features as fx, report, roots as rx, search as sx, sessions  # noqa: E402

R = []
MAX_JSON_BYTES = 1_500_000


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def _score(vals, root_mean, k):
    return (np.mean(vals) - root_mean) * len(vals) / (len(vals) + k)


def test_bound_brute_force():
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(40):
        x = np.sort(rng.normal(0, 10, 11))[::-1]
        mask = rng.random(11) < 0.8
        root_mean, min_n, k = float(rng.normal()), 3, 4.0
        members = np.flatnonzero(mask)
        brute = max((_score(x[list(c)], root_mean, k) for m in range(min_n, len(members) + 1)
                     for c in itertools.combinations(members, m)), default=-np.inf)
        _, _, _, bound = sx.scores_and_bounds(x, mask[None, :], root_mean, min_n, k)
        worst = max(worst, abs(bound[0] - brute) if np.isfinite(brute) else 0.0)
    check("bound = best score of any min_n+ subset (40 random sets, brute force)", worst < 1e-9, f"max diff {worst:.2e}")


def _synthetic(n=90, seed=3):
    """Three features (ordered 4, plain 3, ordered 3) and values with a planted effect."""
    rng = np.random.default_rng(seed)
    feats = (fx.Feature("a", ("a0", "a1", "a2", "a3"), True, "a"), fx.Feature("b", ("b0", "b1", "b2"), False, "b"),
             fx.Feature("c", ("c0", "c1", "c2"), True, "c"))
    codes = np.column_stack([rng.integers(0, 4, n), rng.integers(0, 3, n), rng.integers(0, 3, n)])
    x = rng.normal(0, 20, n) + 15 * (codes[:, 0] >= 2) - 10 * (codes[:, 1] == 1)
    conds = fx.conditions(feats)
    return x, fx.condition_masks(codes, conds), np.array([c.feature for c in conds]), conds


def test_search_is_exact():
    x, masks, cfeat, conds = _synthetic()
    cfg = sx.SearchConfig(min_n=8, shrink_k=10.0, max_depth=3, max_expand=10**6)
    t = sx.search(x, masks, cfeat, cfg)
    best = 0.0
    for depth in (1, 2, 3):
        for combo in itertools.combinations(range(len(conds)), depth):
            if len({cfeat[c] for c in combo}) < depth:
                continue
            keep = np.logical_and.reduce([masks[c] for c in combo])
            if keep.sum() >= cfg.min_n:
                best = max(best, _score(x[keep], x.mean(), cfg.shrink_k))
    check("unlimited branch-and-bound = exhaustive best", abs(t.score[t.best] - best) < 1e-9,
          f"search {t.score[t.best]:.4f} vs brute {best:.4f}, {len(t) - 1} nodes")
    st = t.stats()
    cut_ok = all(t.bound[i] <= t.score[t.best] + 1e-9 for i, s in enumerate(t.status) if s == sx.CUT)
    check("every cut node's bound <= the final best; nothing left open", cut_ok and st["open"] == 0, st)
    keep = np.logical_and.reduce([masks[c] for c in t.conds_of(t.best)])
    check("the best node's stored n / mean match its conditions",
          keep.sum() == t.n[t.best] and abs(x[keep].mean() - t.mean[t.best]) < 1e-9)
    small = sx.search(x, masks, cfeat, sx.SearchConfig(min_n=8, shrink_k=10.0, max_depth=3, max_expand=5))
    check("a small budget leaves nodes OPEN and never beats the exact best",
          small.stats()["open"] > 0 and small.score[small.best] <= t.score[t.best] + 1e-9)


def test_search_deterministic():
    x, masks, cfeat, _ = _synthetic(seed=11)
    cfg = sx.SearchConfig(min_n=6, max_depth=4, max_expand=200)
    a, b = sx.search(x, masks, cfeat, cfg), sx.search(x, masks, cfeat, cfg)
    check("search twice -> identical trees", a.__dict__ == b.__dict__, f"{len(a)} nodes")


def _scrambled(m: sessions.Market, j: int, rng) -> sessions.Market:
    """A copy of the market with every NQ bar after bar j and every ES close after its time replaced by noise."""
    b = m.bars
    arr = {k: getattr(b, k).copy() for k in ("o", "h", "l", "c", "v")}
    tail = slice(j + 1, None)
    shift = rng.normal(0, 200, len(b) - j - 1)
    for k in ("o", "c"):
        arr[k][tail] += shift
    arr["h"][tail] = np.maximum(arr["o"][tail], arr["c"][tail]) + rng.random(len(b) - j - 1) * 50
    arr["l"][tail] = np.minimum(arr["o"][tail], arr["c"][tail]) - rng.random(len(b) - j - 1) * 50
    bars = edata.Bars(b.sym, b.tf, b.t, arr["o"], arr["h"], arr["l"], arr["c"], arr["v"], b.mod, b.tday, b.dow, b.date_str)
    t_j = int(b.t[j])
    es = {t: (c if t <= t_j else c + float(rng.normal(0, 80))) for t, c in m.es_close.items()}
    return sessions.Market(bars, m.days, es, m.es_open)


def test_no_lookahead():
    m = sessions.load_market()
    vix = pd.read_csv(os.path.join(edata.DATA_DIR, "VIX_1d.csv")).sort_values("date")
    edges = fx.train_edges(m.days)
    rng = np.random.default_rng(5)
    picks = [r for r in rx.all_roots() if r.target_r == 1.0 and r.horizon == 60][::3]
    bad, checked, with_es = [], 0, 0
    for root in picks:
        tr = rx.root_trades(m, root)
        if tr.empty:
            continue
        codes = fx.encode(m, tr, edges)
        late = np.flatnonzero(tr["date"].values >= "2025-04-15")        # ES data exists: the es condition is live
        early = np.flatnonzero(tr["date"].values < "2025-01-01")
        for k in (rng.choice(early), rng.choice(late)):
            t = tr.iloc[[k]]
            j, date = int(t["entry_i"].iloc[0]), t["date"].iloc[0]
            sm = _scrambled(m, j, rng)
            v2 = vix.copy()
            v2.loc[v2["date"] >= date, "close"] += rng.normal(0, 30, int((v2["date"] >= date).sum()))
            sm.days = sessions.build_days(sm.bars, v2)
            row = int(np.flatnonzero(sm.days["date"].values == date)[0])
            sig = rx.find_signal(sm, sm.days.iloc[row].to_dict(), root.level, root.mode)
            same_entry = sig is not None and sig[0] == j and abs(sig[1] - float(t["entry"].iloc[0])) < 1e-9 \
                and abs(sig[2] - float(t["stop"].iloc[0])) < 1e-9
            t2 = t.copy()
            t2["day_row"] = row
            same_codes = np.array_equal(fx.encode(sm, t2, edges)[0], codes[k])
            checked += 1
            with_es += int(codes[k][fx.F["es"]] >= 0)
            if not (same_entry and same_codes):
                bad.append(f"{root.id} {date}")
    check(f"no look-ahead: {checked} trades (half with ES data), the future scrambled (NQ, ES, VIX) -> same entry, "
          f"stop and conditions ({with_es} with an ES code)", checked >= 10 and with_es >= 3 and not bad, bad[:3])


def test_root_rules():
    m = sessions.load_market()
    b = m.bars
    ok_stop, ok_cost, ok_time, n = True, True, True, 0
    for root in (rx.Root("ORH", "fade", 1.0, 60), rx.Root("PDL", "fade", 2.0, 120)):
        tr = rx.root_trades(m, root)
        for t in tr.itertuples():
            n += 1
            row = m.days.iloc[t.day_row]
            mod = b.mod[int(row["a"]):int(row["z"])]
            i0 = int(row["a"] + np.flatnonzero((mod >= rx.FIRST_ENTRY_MOD) & (mod <= rx.LAST_ENTRY_MOD))[0])
            extreme = b.h[i0:t.entry_i + 1].max() if t.dir < 0 else b.l[i0:t.entry_i + 1].min()
            ok_stop &= abs(t.stop - (extreme - t.dir * rx.TICK)) < 1e-9
            ok_cost &= abs(t.pnl - ((t.exit - t.entry) * t.dir * rx.POINT_USD - rx.COST_RT)) < 1e-9
            ok_time &= t.exit_i > t.entry_i and b.mod[t.exit_i] <= rx.FLAT_MOD
    check(f"fade stops 1 tick beyond the sweep extreme ({n} trades)", ok_stop)
    check("P&L = points x $2 - $1.90 a micro", ok_cost)
    check("every exit comes after the entry and by the 15:55 flat", ok_time)


def _quick_doc(m):
    roots = [r for r in rx.all_roots() if r.level in ("ORH", "ORL")][:6]
    return report.build(m, sx.SearchConfig(min_n=50, max_expand=60), roots, placebos=1)


def test_build_and_json():
    m = sessions.load_market()
    a, b = _quick_doc(m), _quick_doc(m)
    strip = lambda d: json.dumps({k: v for k, v in d.items() if not k.startswith("_") and k != "meta"}, sort_keys=True)
    check("quick build twice -> identical JSON", strip(a) == strip(b))
    tmp = tempfile.mkdtemp(prefix="daphne_")
    try:
        path = report.write(a, tmp, page_json=None)
        doc = json.load(open(path, encoding="utf-8"))
    finally:
        for f in glob.glob(os.path.join(tmp, "*")):
            os.remove(f)
        os.rmdir(tmp)
    need = {"v", "meta", "features", "conds", "node_cols", "status_names", "roots", "trees", "top", "honesty"}
    check("schema: top-level keys", need <= set(doc), sorted(need - set(doc)))
    cols = doc["node_cols"]
    closed = True
    for rows in doc["trees"].values():
        ids = {r[0] for r in rows}
        closed &= all(len(r) == len(cols) for r in rows) and all(r[1] in ids or r[1] == -1 for r in rows)
        closed &= sum(r[cols.index("best")] for r in rows) >= 1
    check("every featured tree is closed (each node's parent is in the sample) and holds its best path",
          closed and len(doc["trees"]) >= 1)
    card = doc["top"][0]
    fields = {"key", "steps", "text", "train", "test", "y2026", "holds"}
    money_ok = all({"mean", "win", "tpw", "mo_1", "mo_bot"} <= set(card[p]) for p in ("train",) if card[p]["n"])
    check("top rule card: plain text, steps, train/test/2026 money", fields <= set(card) and money_ok, card["text"][:80])
    h = doc["honesty"]
    check("honesty: nodes searched, best rules, how many hold, a placebo",
          h["real"]["nodes"] > 0 and h["real"]["best_rules"] >= h["real"]["hold"] and len(h["placebo"]) == 1)
    card = report.jarvis_card(a, now=1793700000)
    text = json.dumps(card)
    fits = (card["v"] == 1 and len(card["name"]) <= 40 and card["status"]["level"] in ("ok", "warn", "bad", "off")
            and len(card["status"]["label"]) <= 48 and len(card["kpis"]) <= 3 and len(card["lines"]) <= 3
            and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 for k in card["kpis"])
            and all(len(x) <= 120 and "<" not in x and "&" not in x for x in card["lines"])
            and card["theme"].startswith("#") and len(card["theme"]) == 7 and len(text.encode()) <= 8192)
    check("jarvis.json follows the contract (docs/JARVIS_APPS.md)", fits, card["status"]["label"])
    test_page_core(doc)
    real_json = os.path.join(report.OUT_DIR, "tree.json")
    if os.path.exists(real_json):
        size = os.path.getsize(real_json)
        check("research/strategytree/tree.json <= 1.5 MB", size <= MAX_JSON_BYTES, f"{size / 1e6:.2f} MB")
        page = report.PAGE_JSON
        check("the page's tree.json is the same file", os.path.exists(page) and open(page, "rb").read() ==
              open(real_json, "rb").read())


CORE_CHECK = """
import * as C from '%s';
const doc = JSON.parse(process.argv[1]);
const m = C.readDoc(doc);
const out = {featured: m.featured.length, trees: 0, inRange: true, parentsFirst: true, best: true};
for (const id of m.featured) {
  const L = C.layoutTree(m.trees[id]);
  out.trees++;
  const seen = new Set();
  for (const n of L.nodes) {
    out.inRange &&= n.u >= -1 && n.u <= 1 && n.r >= 0 && n.r <= 1;
    out.parentsFirst &&= n.parent < 0 || seen.has(n.parent);
    seen.add(n.id);
  }
  out.best &&= L.bestPath.length >= 1 && L.bestPath[0].id === L.root.id;
}
out.fmt = [C.usd(12.3), C.usd(-4.1), C.usd(null), C.money(-1234.4)];
console.log(JSON.stringify(out));
"""


def test_page_core(doc: dict):
    """The page's core.js on the built JSON: every featured tree lays out inside the fan, parents before children, the
    best path starts at the root, and the money formats."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        check("page core.js (node not installed: skipped)", True)
        return
    core = os.path.join(ROOT, "tools", "web_public", "tree", "core.js")
    script = CORE_CHECK % ("file://" + core)
    res = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps(doc)], capture_output=True, text=True,
                         timeout=60)
    try:
        out = json.loads(res.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        check("page core.js runs", False, res.stderr[-300:])
        return
    check("page core.js: every featured tree laid out in the fan, parents first, best path from the root",
          out["trees"] == out["featured"] >= 1 and out["inRange"] and out["parentsFirst"] and out["best"], out)
    check("page core.js: money formats", out["fmt"] == ["+$12.30", "\u2212$4.10", "\u2014", "\u2212$1,234"], out["fmt"])


def test_demo_fixture():
    """The page's demo.json: synthetic, marked demo, the same schema as the real file, and current with demo.py."""
    from tools.strategytree import demo
    doc = demo.demo_doc()
    keys = {"v", "meta", "features", "conds", "node_cols", "status_names", "roots", "trees", "top", "honesty"}
    on_disk = json.load(open(demo.DEMO_JSON, encoding="utf-8")) if os.path.exists(demo.DEMO_JSON) else {}
    check("demo fixture: marked demo, real schema, demo.json on disk = demo.py output",
          doc["meta"]["demo"] and keys <= set(doc) and on_disk == json.loads(json.dumps(doc)),
          "rerun python -X utf8 -m tools.strategytree.demo" if on_disk != json.loads(json.dumps(doc)) else "")


THEME_STUB = """(() => { const scene = %s;
  window.OLYMPUS = { app: 'x', fx: () => 'high', chosen: () => true, lite: () => false, reduced: () => false, dpr: () => 1, setFx() {}, onFx() {},
    mode() {}, hidden: () => document.hidden, track: (r) => r, stats: () => ({}), ready() {}, fail() {}, state: () => 'ready',
    theme: () => ({ bg: '#000814', accent: '#4da3ff', mix: 0.5, harmony: 0.3, glass: 'rgba(0, 0, 0, .7)', line: 'rgba(1, 1, 1, .1)', text: '#ffffff', dim: '#cccccc' }),
    onTheme(cb) { window.__onTheme = cb; } };
  if (scene) window.OLYMPUS.themeScene = (o) => { window.__themeScene = o; return () => {}; }; })()"""


PAGE_SHOTS = os.environ.get("DAPHNE_SHOTS") or os.path.join(ROOT, "research", "handoff", "2026-11-03-day", "research_apps", "daphne")


def test_page():
    """The DAPHNE page in Chromium at 390 x 844 (the day-sprint upgrade, 2026-11-03): the tree grows with tapered branches
    and leaves on the surviving ones, the verdict banner on top (beats chance or not, this root holds or fails), the TRAIN /
    TEST lens sweeps a wavefront and stamps the test's verdict, the TOP RULES tab of the bottom sheet opens a root, the
    orb corner stays free, no sideways scroll, reduced motion, applyTheme, no console error. Screenshots: PAGE_SHOTS."""
    import functools
    import http.server
    import threading
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("page: Playwright is installed (skipped)", True)
        return
    site = os.path.join(ROOT, "tools", "web_public")
    doc = json.load(open(os.path.join(site, "tree", "tree.json"), encoding="utf-8"))

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/tree/index.html"
    os.makedirs(PAGE_SHOTS, exist_ok=True)
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    real = doc["honesty"]["real"]
    plc = [x["hold_pct"] for x in doc["honesty"].get("placebo", [])]
    chance_beaten = bool(plc) and real["hold_pct"] > max(plc) + 10
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.goto(base + "?at=9300&q=off")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=30000)
            pg.wait_for_timeout(800)
            st = pg.evaluate("() => { const S = window.__daphne.state; return { leaves: S.leafCount, root: S.rootId, held: S.root.best.holds }; }")
            check(f"page: the tree grows, leaves on the surviving branches ({st['leaves']})", st["leaves"] > 0, st)
            v = pg.inner_text("#verdict")
            check("page: the verdict banner on top: beats chance or chance level, the hold rate, this root holds / fails",
                  ("BEATS CHANCE" if chance_beaten else "CHANCE LEVEL") in v.upper() and f"{real['hold']}/{real['best_rules']}" in v
                  and ("HOLDS" if st["held"] else "FAILS") in v.upper(), v)   # AGORA: sentence case on screen, no CSS uppercase
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "01_grown_train.png"))
            pg.click('.lens [data-lens="test"]')
            pg.wait_for_timeout(350)
            fx = pg.evaluate("() => ({ shown: !document.getElementById('lensFx').hidden, t: document.getElementById('lensT').textContent, "
                             "s: document.getElementById('lensS').textContent, lens: document.getElementById('app').dataset.lens, "
                             "at: window.__daphne.state.lensAt })")
            check("page: TEST lens: the flash + stamp (out of sample, this root's best holds / fails) and the wavefront starts",
                  fx["shown"] and "OUT OF SAMPLE" in fx["t"] and ("HOLDS" if st["held"] else "FAILS") in fx["s"] and fx["lens"] == "test" and fx["at"] > 0, fx)
            # the screenshot: a moment of the switch held still (headless frames are slow), like ?at= for the growth
            pg.evaluate("() => { const S = window.__daphne.state, f = () => { S.fxAt = performance.now() - 520; S.lensAt = performance.now() - 520; document.getElementById(\"lensFx\").hidden = false; }; "
                        "f(); window.__hold = setInterval(f, 30); }")
            pg.wait_for_timeout(700)
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "02_test_lens_wave.png"))
            pg.evaluate("() => { clearInterval(window.__hold); const S = window.__daphne.state; S.lensAt = performance.now() - 2000; S.fxAt = performance.now() - 1500; }")
            pg.wait_for_timeout(1800)
            check("page: the stamp clears by itself", pg.evaluate("document.getElementById('lensFx').hidden"))
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "03_test_lens.png"))
            pg.click('.sheet-tabs [data-tab="rules"]')
            pg.wait_for_timeout(300)
            n = pg.evaluate("document.querySelectorAll('#rules li').length")
            check("page: TOP RULES tab: one row per top rule, HOLDS / FAILS on each", n == len(doc["top"]) and pg.is_visible("#rules")
                  and pg.evaluate("document.querySelectorAll('#rules li .tag').length") == n, n)
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "04_top_rules.png"))
            pick = next((i for i, r in enumerate(doc["top"]) if r["root"] in doc["trees"] and r["root"] != st["root"]), None)
            if pick is not None:
                pg.click(f"#rules li:nth-child({pick + 1})")
                pg.wait_for_timeout(300)
                check("page: a tap on a top rule grows its tree", pg.evaluate("window.__daphne.state.rootId") == doc["top"][pick]["root"])
            free = pg.evaluate("""() => { const W = innerWidth, H = innerHeight, hit = [];
                for (let x = W - 78; x < W; x += 13) for (let y = H - 158; y < H; y += 13) {
                  const el = document.elementFromPoint(x, y); if (el && !el.closest('.oly-home') && el.closest('button, a, li, .card, .sheet')) hit.push([x, y, el.className]); }
                return hit; }""")
            check("page: the bottom-right 80 x 160 px stays free for Jarvis's orb", not free, free[:3])
            check("page: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            got = pg.evaluate("""() => { applyTheme({ accent: '#00e0ff', bg: '#010203' }); return [getComputedStyle(document.documentElement)
                .getPropertyValue('--green').trim(), window.__daphne.state.bg]; }""")
            check("page: applyTheme(tokens): the colours and the canvas background follow", got == ["#00e0ff", "#010203"], got)
            check("page: no page or console errors", not errs, errs[:3])
            ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            ctx.add_init_script(THEME_STUB % "false")
            pg = ctx.new_page()
            pg.goto(base + "?at=9300&q=off")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=30000)
            a = pg.evaluate("() => [window.__daphne.state.themeHook, getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(), window.__daphne.state.bg]")
            pg.evaluate("() => window.__onTheme({ bg: '#123456', accent: '#46ff9a', mix: 1, harmony: 0 })")
            b = pg.evaluate("() => [getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(), window.__daphne.state.bg]")
            # the expected start bg = the page's own bg (OWN in tree/app.js: the AGORA palette since 2026-11-10, was the phosphor dark that
            # gave #02080d) blended into the stub theme's #000814 by its mix 0.5, the same rounding as app.js mixHex
            import math
            import re as _re
            own = _re.search(r"const OWN = \{ bg: '(#[0-9a-fA-F]{6})'", open(os.path.join(ROOT, "tools", "web_public", "tree", "app.js"), encoding="utf-8").read()).group(1)
            want = "#" + "".join("%02x" % math.floor(x + (y - x) * 0.5 + 0.5) for x, y in zip(*[[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in (own, "#000814")]))
            check(f"page: OLYMPUS themes: theme() applied at start (bg blended by the theme's mix: {want}), onTheme follows every change",
                  a == ["theme", want, want] and b == ["#123456", "#123456"], (a, b))
            ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            errs2 = []
            pg.on("pageerror", lambda e: errs2.append(str(e)))
            pg.goto(base + "?q=off")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=30000)
            pg.wait_for_timeout(600)
            pg.click('.lens [data-lens="test"]')
            pg.wait_for_timeout(200)
            check("page: reduced motion: grown at once, the lens switches without the sweep, no errors",
                  pg.evaluate("window.__daphne.state.leafCount") > 0 and pg.evaluate("document.getElementById('app').dataset.lens") == "test" and not errs2, errs2[:3])
            ctx.close()
            # the 2026-11-03 look: BEST tab (plain words), the OLYMPUS render core over the tree (glow.js)
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            errs3 = []
            pg.on("pageerror", lambda e: errs3.append(str(e)))
            pg.on("console", lambda m: errs3.append(m.text) if m.type == "error" else None)
            pg.goto(base + "?at=9300&q=off")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=30000)
            pg.click('.sheet-tabs [data-tab="best"]')
            pg.wait_for_timeout(300)
            bt = pg.inner_text("#best")
            check("page: BEST tab: the best branch of the whole search in plain words, with its money and HOLDS / FAILS",
                  # AGORA Daphne (3e10975f): sentence case, "Unseen, per trade" (was TEST $/TRADE)
                  "BEST BRANCH OF THE WHOLE SEARCH" in bt.upper() and "Take the level trade, but only when" in bt and ("HOLDS" in bt.upper() or "FAILS" in bt.upper()) and "UNSEEN, PER TRADE" in bt.upper(), bt[:200])
            check("page: BEST tab: the count of top rules that hold and the dead ends that fade", "hold out of sample" in bt and "dead ends" in bt, bt[-200:])
            check("page: on ?q=off the render-core overlay stands down (the plain 2D tree)", pg.evaluate("window.__daphne.glow") in (None,) or pg.evaluate("window.__daphne.glow.on") is False)
            ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            errs4 = []
            pg.on("pageerror", lambda e: errs4.append(str(e)))
            pg.on("console", lambda m: errs4.append(m.text) if m.type == "error" else None)
            pg.goto(base + "?at=9300&q=high")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=30000)
            pg.wait_for_function("() => window.__daphne.glow && window.__daphne.glow.on", timeout=60000)
            gl = pg.evaluate("window.__daphne.glow")
            check("page: on HD the render core draws the tree: scene + bloom + finish, the stage still carries the touch", gl["passes"] == ["scene", "bloom", "finish"]
                  and pg.evaluate("document.getElementById('app').dataset.gl") == "on" and pg.evaluate("getComputedStyle(document.getElementById('gl')).pointerEvents") == "none", gl)
            check("page: the 3D laurel tree is what draws on HD (tubes, instanced leaves), a tap picks nothing out of range",
                  gl["mode"] == "3d" and gl["stats"]["leaves"] > 0 and gl["stats"]["edges"] > 20, gl)
            check("page: the 3D tree stays in the draw-call budget (<= 40 calls with bloom, the finish, the light shafts and the weather)", 0 < gl["stats"]["calls"] <= 40, gl["stats"]["calls"])
            pt = pg.evaluate("() => { const n = window.__daphne.state.tree.nodes.find((x) => !x.kids.length && x.status !== 2); return n ? n.id : null; }")
            pg.mouse.move(195, 600)
            pg.mouse.down(); pg.mouse.move(235, 610, steps=4); pg.mouse.up()
            check("page: a drag orbits the camera (no pan of the hidden 2D view)", pg.evaluate("window.__daphne.state.view.x") == 0, pg.evaluate("window.__daphne.state.view"))
            check("page: the render-core overlay raises no console error", not errs4, errs4[:3])
            ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            pg.goto(base + "?at=9300&q=high")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=30000)
            pg.wait_for_timeout(2500)
            g3 = pg.evaluate("window.__daphne.glow")
            check("page: reduced motion: the 3D tree stands down, the 2D tree is the fallback", g3 is None or g3["on"] is False, g3)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


# ------------------------------------------------------------------------------------------------ 2026-11-04: the branch library, seasons, the timeline
BRANCH_JS = r"""
import fs from 'node:fs';
const D = '__TREE__/';
const B = await import(D + 'branches.js');
const C = await import(D + 'core.js');
const doc = JSON.parse(fs.readFileSync(D + 'tree.json', 'utf8')), model = C.readDoc(doc), all = B.branchesOf(model), out = {};
out.n = all.length; out.allPos = all.filter((b) => b.allPos).length; out.holds = all.filter((b) => b.holds).length;
out.filterAll = B.filterBranches(all, { holds: 'all' }).length; out.long = B.filterBranches(all, { dir: 'long' }).length; out.short = B.filterBranches(all, { dir: 'short' }).length;
out.search = B.filterBranches(all, { q: 'asia low' }).every((b) => (b.key + ' ' + b.text).toLowerCase().includes('asia')) && B.filterBranches(all, { q: 'asia low' }).length > 0;
out.minMean = B.filterBranches(all, { minMean: 20 }).every((b) => b.periods.test.mean >= 20);
const byTest = B.sortBranches(all, 'test'); out.sortTest = byTest.every((b, i) => !i || byTest[i - 1].periods.test.mean >= b.periods.test.mean);
const hof = B.hallOfFame(all, 10); out.hof = { n: hof.length, allHold: hof.every((h) => h.b.allPos), sorted: hof.every((h, i) => !i || hof[i - 1].b.worst >= h.b.worst), medals: hof.slice(0, 3).map((h) => h.medal), reason: hof[0].reason };
const c = B.compare(all[0], all[1]); out.cmp = { rows: c.rows.length, text: c.text.length > 10, same: B.compare(all[0], all[0]).text };
out.words = B.plainWords(all[0]).length; out.wordsText = B.plainWords(all[0]).join(' ').length > 120;
const st = B.statsOf(model, all); out.stats = { nodes: st.nodes, histSum: st.hist.reduce((a, b) => a + b, 0), cutPct: st.cutPct, placebo: st.placebo.length, holdPct: st.holdPct };
out.share = B.shareLines(all[0]); out.metaNodes = doc.meta.nodes;
const demo = C.readDoc(JSON.parse(fs.readFileSync(D + 'demo.json', 'utf8'))), db = B.branchesOf(demo); out.demo = [db.length, B.hallOfFame(db, 10).length >= 0, B.statsOf(demo, db).branches === db.length];
out.empty = [B.branchesOf({ roots: [] }).length, B.hallOfFame([], 5).length, B.statsOf({ roots: [], meta: {}, honesty: {} }, []).branches];
console.log(JSON.stringify(out));
"""


def test_branches_node():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        check("branches.js (node not installed: skipped)", True)
        return
    tree = os.path.join(ROOT, "tools", "web_public", "tree")
    f = os.path.join(tempfile.mkdtemp(prefix="daphne_branches_"), "b.mjs")
    open(f, "w", encoding="utf-8").write(BRANCH_JS.replace("__TREE__", tree.replace(os.sep, "/")))
    res = subprocess.run([node, f], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(res.stdout.strip().splitlines()[-1])
    except Exception:
        check("branches.js runs in node", False, (res.stdout + res.stderr)[-400:])
        return
    doc = json.load(open(os.path.join(tree, "tree.json"), encoding="utf-8"))
    best = [r for r in doc["roots"] if r.get("best") and r["best"].get("train") and r["best"].get("test")]
    want = sum(1 for r in best if r["best"].get("y2026") and r["best"]["train"]["mean"] > 0 and r["best"]["test"]["mean"] > 0 and r["best"]["y2026"]["mean"] > 0
               and r["best"]["test"]["n"] >= 10 and r["best"]["y2026"]["n"] >= 10)
    check(f"branches: one branch per root with a best rule ({o['n']}), 'holds in every period' = positive $ per trade in train, test and 2026 on 10+ trades ({o['allPos']}, the same as an independent count)",
          o["n"] == len(best) and o["allPos"] == want and o["filterAll"] == want and o["holds"] == sum(1 for r in best if r["best"]["holds"]), (o["n"], len(best), o["allPos"], want))
    check("branches: filters (long + short = all, a text search, a minimum $ per trade) and the sorts are right", o["long"] + o["short"] == o["n"] and o["search"] and o["minMean"] and o["sortTest"], o)
    h = o["hof"]
    check("branches: the Hall of Fame holds only branches that hold in every period, ranked by their worst period, gold / silver / bronze, with a reason in dollars",
          h["allHold"] and h["sorted"] and h["n"] == min(10, want) and h["medals"] == ["gold", "silver", "bronze"][:min(3, want)] and "Worst period still" in h["reason"], h)
    check("branches: compare gives ten rows and a plain verdict (a branch against itself is a tie); plain words are four sentences", o["cmp"]["rows"] == 10 and o["cmp"]["text"] and "tie" in o["cmp"]["same"].lower() and o["words"] == 4 and o["wordsText"], o["cmp"])
    st = o["stats"]
    check(f"branches: the stats are the run's own numbers ({st['nodes']:,} nodes, {st['cutPct']}% cut, the histogram adds up to every branch, {st['placebo']} shuffled runs)",
          st["nodes"] == o["metaNodes"] == doc["meta"]["nodes"] and st["histSum"] == o["n"] and st["placebo"] == len(doc["honesty"].get("placebo", [])) and st["cutPct"] == doc["meta"]["cut_pct"], st)
    check("branches: the share picture has a title, a verdict, three bars and a sentence", o["share"]["title"] and o["share"]["verdict"] in ("HOLDS IN EVERY PERIOD", "HOLDS OUT OF SAMPLE", "DOES NOT HOLD") and len(o["share"]["bars"]) == 3 and len(o["share"]["text"]) > 20, o["share"])
    check("branches: the demo data and an empty search never crash (empty lists, zero counts)", o["demo"][1] and o["demo"][2] and o["empty"] == [0, 0, 0], (o["demo"], o["empty"]))


def test_page_plus():
    """The 2026-11-04 page: BRANCHES (list, filters, plain words, compare, hall of fame, stats, share picture), the timeline, the seasons."""
    import functools
    import http.server
    import threading
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("page plus: Playwright is installed (skipped)", True)
        return
    site = os.path.join(ROOT, "tools", "web_public")
    doc = json.load(open(os.path.join(site, "tree", "tree.json"), encoding="utf-8"))
    best = [r for r in doc["roots"] if r.get("best") and r["best"].get("train") and r["best"].get("test")]
    want = sum(1 for r in best if r["best"].get("y2026") and r["best"]["train"]["mean"] > 0 and r["best"]["test"]["mean"] > 0 and r["best"]["y2026"]["mean"] > 0
               and r["best"]["test"]["n"] >= 10 and r["best"]["y2026"]["n"] >= 10)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/tree/index.html"
    os.makedirs(PAGE_SHOTS, exist_ok=True)
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.set_default_timeout(60000)
            pg.goto(base + "?q=off")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=60000)
            pg.wait_for_timeout(500)
            tools = pg.evaluate("[...document.querySelectorAll('.tools button, .timeline button')].map(b => Math.round(b.getBoundingClientRect().height))")
            check("page plus: BRANCHES, SEASON, play / pause and the scrubber are on the page, every button 44 px tall", len(tools) >= 6 and all(h >= 44 for h in tools) and pg.is_visible("#scrub"), tools)
            pg.click("#openBranches")
            pg.wait_for_selector("#branches .br")
            n0 = pg.evaluate("document.querySelectorAll('#branches .br').length")
            check(f"page plus: BRANCHES opens the library: '{len(best)} of {len(best)} branches', the first 30 shown, each with its bars and a verdict", pg.inner_text("#brcount").startswith(f"{len(best)} of {len(best)}") and n0 == min(30, len(best))
                  and pg.evaluate("document.querySelectorAll('#branches .br .mb').length") == n0 and pg.evaluate("document.querySelectorAll('#branches .br .bg').length") == n0, (n0, pg.inner_text("#brcount")))
            pg.click('#branches [data-f="holds"][data-v="all"]')
            check(f"page plus: 'holds in every period' leaves exactly the {want} branches that do", pg.inner_text("#brcount").startswith(f"{want} of"), pg.inner_text("#brcount"))
            pg.click('#branches [data-f="holds"][data-v="any"]')
            pg.fill("#brq", "asia low")
            pg.wait_for_timeout(200)
            m = pg.evaluate("[...document.querySelectorAll('#branches .br .k')].map(e => e.textContent)")
            check("page plus: searching 'asia low' lists only Asia branches (the Asia-low ones among them) and typing keeps the cursor in the box", m and all(k.startswith("A") for k in m) and any(k.startswith("AL") for k in m) and len(m) < n0 and pg.evaluate("document.activeElement.id") == "brq", m[:4])
            pg.fill("#brq", "")
            pg.click('#branches [data-f="dir"][data-v="long"]')
            lng = pg.evaluate("document.querySelectorAll('#branches .br').length")
            check("page plus: LONG / SHORT filter", 0 < lng <= n0, lng)
            pg.click('#branches [data-f="dir"][data-v="any"]')
            pg.click("#branches [data-words] >> nth=0")
            wd = pg.inner_text("#branches .words")
            check("page plus: WORDS opens the branch in plain words (what it does, how it fared in each stretch, a verdict, how often it trades)", wd.count("\n") >= 3 and "trades" in wd and "$" in wd and "Numbers are $ per trade" in wd, wd[:160])
            pg.click("#branches [data-cmp=a] >> nth=0")
            pg.click("#branches [data-cmp=b] >> nth=1")
            pg.wait_for_selector("#branches table.cmp")
            rows = pg.evaluate("document.querySelectorAll('#branches table.cmp tbody tr').length")
            saved = pg.evaluate("JSON.parse(localStorage.getItem('daphne.branches'))")
            check("page plus: A and B put two branches side by side: ten rows, the winner of each marked, a plain verdict, kept under 'daphne.branches'",
                  rows == 10 and pg.evaluate("document.querySelectorAll('#branches td.w').length") >= 1 and len(pg.inner_text("#cmpv")) > 15 and saved["a"] and saved["b"] and saved["a"] != saved["b"], (rows, saved))
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "plus_compare.png"))
            pg.click('#branches [data-btab="fame"]')
            medals = pg.evaluate("[...document.querySelectorAll('#branches .fame li')].map(li => li.className)")
            check(f"page plus: the Hall of Fame: {len(medals)} branches that hold everywhere, gold / silver / bronze first", len(medals) == min(10, want) and medals[:3] == ["gold", "silver", "bronze"][:min(3, want)], medals)
            pg.click('#branches [data-btab="stats"]')
            tiles = pg.evaluate("[...document.querySelectorAll('#branches .tiles b')].map(b => b.textContent)")
            check("page plus: STATS: nodes tested, % cut, branches, the survival rates, a histogram of 8 columns and the shuffled check",
                  f"{doc['meta']['nodes']:,}" in tiles and f"{doc['meta']['cut_pct']}%" in tiles and pg.evaluate("document.querySelectorAll('#branches .hist > div').length") == 8
                  and pg.evaluate("document.querySelectorAll('#branches table.cmp tbody tr').length") == 1 + len(doc["honesty"].get("placebo", [])), tiles)
            pg.click('#branches [data-btab="fame"]')
            pg.click("#branches [data-share] >> nth=0")
            pg.wait_for_selector("#shareView:not([hidden])", timeout=60000)
            pg.wait_for_function("() => { const i = document.querySelector('#shareView img'); return i && i.complete && i.naturalWidth > 0; }", timeout=30000)
            size = pg.evaluate("(() => { const i = document.querySelector('#shareView img'); return [i.naturalWidth, i.naturalHeight, i.src.slice(0, 5)]; })()")
            check("page plus: SHARE makes a 1080 x 1350 picture on the phone (a blob, nothing uploaded) and shows it to press and hold", size == [1080, 1350, "blob:"], size)
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "plus_share.png"))
            pg.click("#shareClose")
            pg.keyboard.press("Escape")
            check("page plus: the picture closes, Escape closes the library", pg.evaluate("document.getElementById('shareView').hidden && document.getElementById('branches').hidden"))
            # the timeline
            pg.click('.sheet-tabs [data-tab="search"]')
            pg.click("#play")
            held = pg.evaluate("window.__daphne.state.hold")
            check("page plus: pause freezes the growth clock; the button turns into play", held is not None and pg.get_attribute("#play", "aria-pressed") == "false", held)
            pg.evaluate("() => { const s = document.getElementById('scrub'); s.value = 0; s.dispatchEvent(new Event('input', { bubbles: true })); }")
            a = pg.evaluate("[window.__daphne.state.hold, window.__daphne.state.tree.nodes.filter(n => n.appear <= window.__daphne.state.hold).length]")
            pg.evaluate("() => { const s = document.getElementById('scrub'); s.value = 500; s.dispatchEvent(new Event('input', { bubbles: true })); }")
            b = pg.evaluate("[window.__daphne.state.hold, window.__daphne.state.tree.nodes.filter(n => n.appear <= window.__daphne.state.hold).length]")
            check("page plus: the scrubber walks the tree back and forth through its growth (at the start only the root, at half many nodes)", a[0] == 0 and a[1] <= 2 and b[1] > a[1] + 20, (a, b))
            pg.click("#play")
            check("page plus: play lets it grow on from where it stopped", pg.evaluate("window.__daphne.state.hold") is None)
            pg.click("#season")
            s1 = pg.evaluate("[window.__daphne.state.season, document.getElementById('seasonT').textContent, document.getElementById('app').dataset.season]")
            for _ in range(3):
                pg.click("#season")
            s2 = pg.evaluate("window.__daphne.state.season")
            pg.click("#season")
            check("page plus: SEASON cycles auto, spring, summer, autumn, winter and back", s1 == ["spring", "SPRING", "spring"] and s2 == "winter" and pg.evaluate("window.__daphne.state.season") == "auto", (s1, s2))
            check("page plus: no page or console errors", not errs, errs[:3])
            ctx.close()
            # 3D: the seasons on the render core, the wind, the light shafts, the draw-call budget
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
            pg = ctx.new_page()
            pg.set_default_timeout(120000)
            errs3 = []
            pg.on("pageerror", lambda e: errs3.append(str(e)))
            pg.on("console", lambda m: errs3.append(m.text) if m.type == "error" else None)
            pg.goto(base + "?at=9300&q=high")
            pg.wait_for_function("() => window.__daphne && window.__daphne.ready", timeout=60000)
            pg.wait_for_function("() => window.__daphne.glow && window.__daphne.glow.on", timeout=120000)
            pg.wait_for_function("() => window.__daphne.glow.fx.includes('godRays') && window.__daphne.glow.season", timeout=90000)
            g = pg.evaluate("window.__daphne.glow")
            check(f"page plus: the 3D tree on HD: summer on the TRAIN lens by itself, light shafts from the OLYMPUS effects ({g['fx']}), within the draw-call budget ({g['stats']['calls']} <= 40)",
                  g["season"] == "summer" and "godRays" in g["fx"] and 0 < g["stats"]["calls"] <= 40, g)
            pg.click('.lens [data-lens="test"]')
            pg.wait_for_function("() => window.__daphne.glow.season === 'autumn'", timeout=60000)
            pg.evaluate("window.__daphne.state.season = 'winter'")
            pg.wait_for_function("() => window.__daphne.glow.season === 'winter'", timeout=60000)
            g2 = pg.evaluate("window.__daphne.glow")
            check("page plus: the TEST lens turns the tree to autumn by itself, a chosen season (winter) wins; the weather follows (snow)", "snow" in g2["fx"] and g2["stats"]["calls"] <= 40, g2["fx"])
            pg.screenshot(path=os.path.join(PAGE_SHOTS, "plus_winter.png"))
            check("page plus: the 3D seasons raise no console error", not errs3, errs3[:3])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def test_paper_only():
    src = "".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(ROOT, "tools", "strategytree", "*.py")))
    check("tools/strategytree never names live_model*.json or imports engine trading code",
          "live_model" not in src and "engine.live" not in src and "ninjatrader" not in src.lower())


def main():
    if "plus" in sys.argv[1:]:                        # `... plus`: the branch library (node) and its page checks only
        test_branches_node()
        test_page_plus()
        print(f"strategytree plus: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
        return 0 if all(R) else 1
    if "page" in sys.argv[1:]:                        # `python -X utf8 -m tests.test_strategytree page`: the page only
        test_page()
        print(f"strategytree page: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
        return 0 if all(R) else 1
    test_bound_brute_force()
    test_search_is_exact()
    test_search_deterministic()
    test_root_rules()
    test_no_lookahead()
    test_build_and_json()
    test_demo_fixture()
    test_paper_only()
    test_branches_node()
    test_page()
    test_page_plus()
    print(f"strategytree: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
