"""OLYMPUS DATA CITY (tools/datacity, tools/web_public/datacity): the data machine and its 3D page.

    python -X utf8 -m tests.test_datacity            # everything (~2-4 min; the page part needs Playwright + Chromium)
    python -X utf8 -m tests.test_datacity --no-page  # the engine only

Checks, on a real slice of data/NQ_5m.csv (2025-03 -> 2025-07):
  a. determinism: two builds of the event table and two scorings of the grid are identical
  b. no look-ahead: garbage after a mid-session cut changes no trigger, stop or state before the cut, and no outcome whose
     window ends before it
  c. incremental == full: a table built to a cut and extended equals one built in one go
  d. the mini-backtest: a hand-made bar path gives the 2R / stop / time exits and the $ after costs
  e. the FDR guard: Benjamini-Hochberg on a textbook case, null t-stats make (almost) no survivors, planted edges are
     found, pure-noise outcomes on the real grid make none; gold needs FDR + both periods + every year
  f. the outputs: keys, building fields, the Jarvis card contract (docs/JARVIS_APPS.md), sizes (city.json < 1 MB, all
     research/datacity JSON < 2 MB), no trading files touched
  g. the page in Chromium at 390 x 844: no errors with the live city.json and with only the demo fixture; panels, search,
     a building card and the LIT card open; nothing drawn in Jarvis's bottom-right 80 x 160 px
"""
from __future__ import annotations

import functools
import glob
import hashlib
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.datacity import bars as B  # noqa: E402
from tools.datacity import features as F  # noqa: E402
from tools.datacity import grid as G  # noqa: E402
from tools.datacity import learn, report, store  # noqa: E402

PAGE = os.path.join(ROOT, "tools", "web_public", "datacity")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f"  -> {detail}"), flush=True)


@functools.cache
def slice_df(a="2025-03-02", z="2025-07-01"):
    df = B.read_csv(B.NQ_5M)
    t = lambda s: int(pd.Timestamp(s, tz="America/New_York").timestamp())  # noqa: E731
    return df[(df["time"] >= t(a + " 18:00")) & (df["time"] < t(z + " 17:00"))].reset_index(drop=True)


@functools.cache
def src():
    return store.sources()


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_json(path):
    return json.loads(read_text(path))


def sha1(path):
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def table_equal(a, b, cols):
    return all(np.array_equal(a[k], b[k], equal_nan=a[k].dtype.kind == "f") for k in cols)


# ------------------------------------------------------------------------------------------------ a. determinism
def test_determinism():
    df = slice_df()
    f1, f2 = F.build(df, **src()), F.build(df, **src())
    check("a. two event-table builds are identical", table_equal(f1["ev"], f2["ev"], f1["ev"].keys()))
    check("a. the slice has every trigger family", {F.TRIGS[k][0].split("_")[0] for k in np.unique(f1["ev"]["trig"])} >=
          {"sweep", "break", "fvg", "ifvg", "cisd", "disp", "vwap", "slot"})
    combos = G.enumerate_combos()
    r1, r2 = G.Grid(f1).score_all(combos), G.Grid(f2).score_all(combos)
    check("a. two grid scorings are identical", json.dumps(r1, sort_keys=True, default=str) == json.dumps(r2, sort_keys=True, default=str))
    ids = [c["id"] for c in combos]
    check("a. combination ids are unique", len(ids) == len(set(ids)), len(ids) - len(set(ids)))


# ------------------------------------------------------------------------------------------------ b. no look-ahead
def test_no_lookahead():
    df = slice_df()
    cut = int(pd.Timestamp("2025-06-11 10:12", tz="America/New_York").timestamp())
    bad = df.copy()
    after = bad["time"] >= cut
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 60, after.sum()).cumsum()
    for k in ("open", "high", "low", "close"):
        bad.loc[after, k] = bad.loc[after, k] + noise + (40 if k == "high" else -40 if k == "low" else 0)
    bad.loc[after, "volume"] = rng.integers(1, 9000, after.sum())
    a, b = F.build(df, **src())["ev"], F.build(bad, **src())["ev"]

    def keyed(ev, upto):
        m = ev["t"] + 300 < upto                         # the decision bar and the entry bar closed before the cut
        return {(int(ev["t"][i]), int(ev["trig"][i])): i for i in np.flatnonzero(m)}

    ka, kb = keyed(a, cut), keyed(b, cut)
    check("b. the same events before the cut (time, trigger)", ka.keys() == kb.keys(), len(ka.keys() ^ kb.keys()))
    ia, ib = np.array([ka[k] for k in sorted(ka)]), np.array([kb[k] for k in sorted(kb)])
    past = ["dir", "win", "slot", "risk"] + [c for c in a if c.startswith("s_")]
    bad_cols = [c for c in past if not np.array_equal(a[c][ia], b[c][ib])]
    check("b. stops, windows and every while-state before the cut are unchanged", not bad_cols, bad_cols)
    done = a["t"][ia] + (F.H + 1) * 300 < cut
    out_cols = ["R", "pnl", "h1", "h2", "h3", "f15", "f30", "f60"]
    bad_out = [c for c in out_cols if not np.array_equal(a[c][ia][done], b[c][ib][done], equal_nan=a[c].dtype.kind == "f")]
    check("b. outcomes whose 2-hour window ended before the cut are unchanged", not bad_out and done.sum() > 1000,
          (bad_out, int(done.sum())))
    changed = ~np.isclose(a["pnl"][ia][~done], b["pnl"][ib][~done], equal_nan=True)
    check("b. control: outcomes running past the cut do change (the garbage is seen)", changed.any())


# ------------------------------------------------------------------------------------------------ c. incremental
def test_incremental():
    df = slice_df()
    tmp = tempfile.mkdtemp(prefix="dc_inc_")
    try:
        cut = int(pd.Timestamp("2025-05-30 17:00", tz="America/New_York").timestamp())
        full, info_f = store.event_table(df, full=True, cache=os.path.join(tmp, "a"), src=src(), log=lambda *_: None)
        store.event_table(df[df["time"] < cut], full=True, cache=os.path.join(tmp, "b"), src=src(), log=lambda *_: None)
        inc, info_i = store.event_table(df, cache=os.path.join(tmp, "b"), src=src(), log=lambda *_: None)
        check("c. the extension is incremental", info_i["mode"] == "incremental" and info_i["new_days"] > 15, info_i)
        check("c. incremental == full (every column, same order)", table_equal(full["ev"], inc["ev"], full["ev"].keys()))
        again, info_c = store.event_table(df, cache=os.path.join(tmp, "b"), src=src(), log=lambda *_: None)
        check("c. same bars again: served from the cache", info_c["mode"] == "cached" and table_equal(again["ev"], inc["ev"], inc["ev"].keys()))
        shifted = df.copy()
        for k in ("open", "high", "low", "close"):
            shifted[k] += 250.0                          # a roll re-basing every price: a shift-invariant fingerprint
        _, info_s = store.event_table(shifted, cache=os.path.join(tmp, "b"), src=src(), log=lambda *_: None)
        check("c. a constant price shift (contract roll) keeps the cache", info_s["mode"] == "cached", info_s)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ d. the mini-backtest
def _bars(path, start="2025-06-10 09:30"):
    t0 = int(pd.Timestamp(start, tz="America/New_York").timestamp())
    rows = [(t0 + 300 * i, o, h, lo, c, 100) for i, (o, h, lo, c) in enumerate(path)]
    return F.Bars(pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]))


def test_outcomes():
    flat = [(100, 100.5, 99.5, 100)] * 30
    win = flat[:1] + [(100, 101, 99.5, 100.5), (100.5, 121, 100, 120)] + flat[3:]        # +20 = 2R at a 10-pt stop
    loss = flat[:1] + [(100, 100.5, 89, 90)] + flat[2:]
    both = flat[:1] + [(100, 121, 89, 100)] + flat[2:]                                    # stop and target in one bar
    timed = flat[:1] + [(100, 103, 99.5, 103)] * 29
    sid = np.array([F.TRIG_ID["slot_long"]], np.int16)
    res = {}
    for name, path in (("win", win), ("loss", loss), ("both", both), ("time", timed)):
        res[name] = F.outcomes(_bars(path), np.array([0]), sid, np.array([90.0]))
    check("d. 2R target hit -> +2R, $ = 2 x 10 pts x $2 - $2.90",
          float(res["win"]["R"][0]) == 2.0 and abs(float(res["win"]["pnl"][0]) - (40 - F.COST)) < 1e-4, res["win"]["pnl"])
    check("d. stop hit -> -1R and hit flags off", float(res["loss"]["R"][0]) == -1.0 and not res["loss"]["h1"][0])
    check("d. a bar through both stop and target counts as the stop (conservative)", float(res["both"]["R"][0]) == -1.0)
    check("d. neither within 2 hours -> exit at the last close (+0.3R)", abs(float(res["time"]["R"][0]) - 0.3) < 1e-6, res["time"]["R"])
    tiny = F.outcomes(_bars(flat), np.array([0]), sid, np.array([99.0]))
    check("d. a structure stop under 4 pts is widened to MIN_STOP", float(tiny["risk"][0]) == F.MIN_STOP)
    wrong = F.outcomes(_bars(flat), np.array([0]), sid, np.array([101.0]))
    check("d. a stop on the wrong side of the entry drops the event", len(wrong["R"]) == 0)


# ------------------------------------------------------------------------------------------------ e. the FDR guard
def test_fdr():
    p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    check("e. BH textbook case: 2 rejections at q 0.05", G.bh(p, 0.05).sum() == 2 and G.bh(p, 0.05)[:2].all())
    check("e. BH is step-up: at q 0.10 p(6) = 0.06 <= 0.06 rejects the first 6 although p(3), p(4) miss their own line",
          G.bh(p, 0.10).sum() == 6 and G.bh(p, 0.10)[:6].all())
    rng = np.random.default_rng(1)
    null = rng.normal(size=5000)
    check("e. 5,000 null t-stats: at most 2 FDR survivors", G.bh(G.p_values(null)).sum() <= 2, G.bh(G.p_values(null)).sum())
    planted = np.r_[null, np.full(10, 7.0)]
    rej = G.bh(G.p_values(planted))
    check("e. 10 planted edges (t = 7) among them are all found", rej[-10:].all())
    feat = F.build(slice_df(), **src())
    gr = G.Grid(feat)
    gr.ev = {**gr.ev, "pnl": (np.where(gr.flip > 0, 1, -1) * rng.uniform(5, 60, len(gr.flip))).astype(np.float32)}
    combos = G.enumerate_combos()
    rows = gr.score_all(combos)
    g = G.guard(combos, rows)
    check("e. pure-noise outcomes on the real grid: 0 FDR survivors, tried / tested counted",
          g["fdr_pos"] == 0 and g["tried"] == len(combos) and 0 < g["tested"] < g["tried"], {k: g[k] for k in ("fdr_pos", "tested")})
    years = {2021: (10, 5.0, 0.1), 2022: (40, 6.0, 0.1), 2023: (40, 2.0, 0.05), 2024: (40, 3.0, 0.1), 2025: (40, 4.0, 0.1), 2026: (30, 9.0, 0.2)}
    s = {"n": 200, "mu26": 9.0, "r26": 0.2, "n26": 30, "muold": 4.0, "rold": 0.1, "nold": 170, "years": years}
    check("e. both periods + every year + FDR = gold; without FDR = green", G.classify(s, True) == "gold" and G.classify(s, False) == "green")
    s_bad = {**s, "years": {**years, 2023: (40, -2.0, -0.05)}}
    check("e. one losing year (8+ trades) is not gold", G.classify(s_bad, True) == "green")
    s_smt = {**s, "nold": 35, "years": {2025: (35, 4.0, 0.1), 2026: (30, 9.0, 0.2)}}
    check("e. 2021-25 from 2025 alone (SMT, ES from 2025-04) never holds in both", G.classify(s_smt, True) == "amber")
    s_thin = {"n": 12}
    check("e. under 30 trades = thin", G.classify(s_thin, True) == "thin")


# ------------------------------------------------------------------------------------------------ f. outputs
JARVIS_LEVELS = {"ok", "warn", "bad", "off"}


def jarvis_problems(card):
    p = []
    raw = json.dumps(card)
    if len(raw.encode()) > 8192:
        p.append("over 8 KB")
    if card.get("v") != 1 or not isinstance(card.get("name"), str) or len(card["name"]) > 40:
        p.append("v / name")
    st = card.get("status") or {}
    if st.get("level") not in JARVIS_LEVELS or len(st.get("label", "")) > 48:
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


def test_outputs():
    tmp = tempfile.mkdtemp(prefix="dc_out_")
    before = {p: sha1(p) for p in glob.glob(os.path.join(ROOT, "live_model*.json"))}
    try:
        files = learn.run(df=slice_df(), out=tmp, web=None, store_run=False, src=src(), log=lambda *_: None, now=1793500000)
        need = {"city.json", "leaderboard.json", "discoveries.json", "summary.json", "history.json", "jarvis.json"}
        check("f. every output file is written", need <= set(os.listdir(tmp)), sorted(os.listdir(tmp)))
        city = files["city.json"]
        check("f. city.json has its sections", {"v", "built", "last_day", "summary", "lit", "buildings", "strategies", "top10",
                                                "discoveries", "today", "lift", "districts"} <= city.keys())
        bf = {"id", "d", "lab", "cls", "fdr", "e", "r", "w", "h2", "n", "tpw", "e26", "eo", "n26", "no", "tr", "yrs"}
        check("f. every building has its card fields", all(bf <= b.keys() for b in city["buildings"]) and city["buildings"])
        check("f. buildings: known districts and classes", {b["d"] for b in city["buildings"]} <= {"times", "confluences", "while"}
              and {b["cls"] for b in city["buildings"]} <= {"gold", "green", "amber", "grey"})
        g = city["summary"]["guard"]
        check("f. the guard reports tried, tested, FDR, placebo and the holdout",
              all(k in g for k in ("tried", "tested", "fdr_pos", "placebo_fdr", "holdout")) and g["tried"] >= g["tested"])
        check("f. the LIT tower carries 2026, the H2 check half and 2021-25",
              city["lit"] and {"2026", "2026 H2", "2021-25"} <= city["lit"]["spans"].keys())
        gr = G.Grid(store.event_table(slice_df(), cache=os.path.join(tmp, "_cache"), src=src(), log=lambda *_: None)[0])
        combo = next(c for c in G.enumerate_combos() if c["id"] == "slot_long|nyam")
        T, _, spans = report.strategy_score(gr, gr.rows(combo))
        sp = spans["2021-25"]
        check("f. a sized strategy: 1-40 micros at ~$500 risk, $, $/month and MFFU eval speed",
              all(1 <= t["qty"] <= 40 and (t["risk_usd"] <= 500 or t["qty"] == 1) for t in T)
              and {"net", "per_month", "p10", "f10", "dec10", "pass_med"} <= sp.keys() and sp["n"] == len(T), sp)
        check("f. jarvis.json follows the Jarvis card contract", not jarvis_problems(files["jarvis.json"]), jarvis_problems(files["jarvis.json"]))
        h1 = files["history.json"]
        learn.run(df=slice_df(), out=tmp, web=None, store_run=False, src=src(), log=lambda *_: None, now=1793500600)
        h2 = read_json(os.path.join(tmp, "history.json"))
        check("f. a rerun on the same data keeps one history row", len(h2["runs"]) == len(h1["runs"]) == 1)
        lb = read_json(os.path.join(tmp, "leaderboard.json"))["rows"]
        check("f. the leaderboard says plain-language findings with $ and trades/week",
              all("/trade/micro" in r["text"] and "a week" in r["text"] for r in lb))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    after = {p: sha1(p) for p in before}
    check("f. paper only: no live_model*.json touched", before == after)
    real = [p for p in glob.glob(os.path.join(ROOT, "research", "datacity", "*.json"))]
    size = sum(os.path.getsize(p) for p in real)
    check("f. committed research/datacity JSON < 2 MB, city.json < 1 MB",
          real and size < 2_000_000 and os.path.getsize(os.path.join(ROOT, "research", "datacity", "city.json")) < 1_000_000, size)
    for name in ("jarvis.json", "fixture.json"):
        path = os.path.join(PAGE, name)
        ok = os.path.exists(path)
        obj = read_json(path) if ok else {}
        if name == "jarvis.json":
            check("f. the page's jarvis.json follows the contract", ok and not jarvis_problems(obj), jarvis_problems(obj) if ok else "missing")
        else:
            check("f. the demo fixture is small and marked demo", ok and obj.get("demo") is True and os.path.getsize(path) < 80_000
                  and len(obj["buildings"]) >= 20)


# ------------------------------------------------------------------------------------------------ g. the page
def _serve(root):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_page(shots=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("g. page test skipped: no Playwright", True)
        return
    tmp = tempfile.mkdtemp(prefix="dc_page_")
    for mode in ("live", "demo"):
        site = os.path.join(tmp, mode, "datacity")
        shutil.copytree(PAGE, site)
        if mode == "demo":
            os.remove(os.path.join(site, "city.json"))
    srv = _serve(tmp)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            for mode in ("live", "demo"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
                pg = ctx.new_page()
                errs, failed = [], []
                pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                pg.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" and "404" not in m.text else None)
                pg.on("requestfailed", lambda r, failed=failed: failed.append(r.url))
                pg.goto(f"{base}/{mode}/datacity/")
                pg.wait_for_function("window.__city && window.__city.ready", timeout=90000)
                st = pg.evaluate("window.__city")
                check(f"g. {mode}: the city is drawn ({st['buildings']} buildings) in {st['mode']} mode",
                      st["mode"] == mode and st["buildings"] >= 20 and not st["errors"], st)
                check(f"g. {mode}: theme-color, viewport-fit=cover, safe areas", pg.evaluate(
                    "document.querySelector('meta[name=theme-color]').content.startsWith('#') && "
                    "document.querySelector('meta[name=viewport]').content.includes('viewport-fit=cover')")
                    and "safe-area-inset-bottom" in read_text(os.path.join(PAGE, "index.html")))
                if mode == "demo":
                    check("g. demo: the DEMO chip shows", pg.locator(".chip.demo").count() == 1)
                pg.wait_for_timeout(1500)
                if shots:
                    pg.screenshot(path=os.path.join(shots, f"{mode}_city.jpg"), type="jpeg", quality=80)
                free = pg.evaluate("""() => { const W = innerWidth, H = innerHeight, bad = [];
                    for (const e of document.querySelectorAll('.bar, .btn, .chip, .panel.on, .toast')) {
                      const r = e.getBoundingClientRect(); if (!r.width || getComputedStyle(e).display === 'none') continue;
                      if (r.right > W - 80 && r.bottom > H - 160) bad.push(e.className); }
                    return bad; }""")
                check(f"g. {mode}: Jarvis's bottom-right 80 x 160 px stays free", not free, free)
                check(f"g. {mode}: no sideways scroll", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                lay = pg.evaluate("""async () => { const { layout } = await import('./layout.js');
                    const city = await (await fetch('./' + (window.__city.mode === 'live' ? 'city' : 'fixture') + '.json')).json();
                    const L = layout(city), it = L.items, box = {}, clash = [];
                    for (let i = 0; i < it.length; i++) for (let j = i + 1; j < it.length; j++)
                      if (Math.hypot(it[i].x - it[j].x, it[i].z - it[j].z) < (it[i].w + it[j].w) / 2 + 0.3) clash.push([it[i].b.id, it[j].b.id]);
                    for (const x of it.filter((x) => x.kind === 'b')) { const b = box[x.b.d] ||= [1e9, 1e9, -1e9, -1e9];
                      b[0] = Math.min(b[0], x.x); b[1] = Math.min(b[1], x.z); b[2] = Math.max(b[2], x.x); b[3] = Math.max(b[3], x.z); }
                    const inTower = it.filter((x) => Math.hypot(x.x, x.z) < 6).length;
                    return { n: it.length, want: city.buildings.length + (city.strategies || []).length + (city.discoveries || []).length,
                             clash: clash.slice(0, 3), boxes: box, inTower,
                             heightsOk: it.every((x) => x.h > 0 && Number.isFinite(x.h)), litOk: it.every((x) => x.lit >= 0 && x.lit <= 1) }; }""")
                over = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]  # noqa: E731
                bx = list(lay["boxes"].values())
                check(f"g. {mode}: layout places every building, tower and monument once, no two overlap, districts apart",
                      lay["n"] == lay["want"] and not lay["clash"] and not lay["inTower"] and lay["heightsOk"] and lay["litOk"]
                      and not any(over(a, b) for i, a in enumerate(bx) for b in bx[i + 1:]), lay)
                pg.click("[data-open=topP]")
                check(f"g. {mode}: Top 10 panel lists findings", pg.locator("#topBody li").count() >= 1)
                pg.locator("#topBody li").first.click()
                pg.wait_for_selector("#card.on", timeout=5000)
                card = pg.inner_text("#card")
                check(f"g. {mode}: a building card shows $/micro, both periods and the paper-only line",
                      "per trade per MNQ micro" in card and "2021-25" in card and "Paper only" in card, card[:200])
                if shots and mode == "live":
                    pg.wait_for_timeout(2500)
                    pg.screenshot(path=os.path.join(shots, "live_card.jpg"), type="jpeg", quality=80)
                pg.click("[data-close=card]")
                pg.wait_for_timeout(3500)                    # the camera glides to the building it just opened
                pg.mouse.click(195, 422)                     # the screen centre = the middle of the focused building
                pg.wait_for_timeout(400)
                tapped = pg.locator("#card.on").count() == 1
                check(f"g. {mode}: tapping the focused building in the 3D view opens its card",
                      tapped and "per trade per MNQ micro" in pg.inner_text("#card"))
                if tapped:
                    pg.click("[data-close=card]")
                pg.click("[data-open=findP]")
                pg.fill("#q", "London")
                pg.wait_for_timeout(300)
                found = pg.evaluate("window.__city.found")
                check(f"g. {mode}: search finds London buildings ({found})", found and found >= 1)
                pg.click("[data-close=findP]")
                pg.evaluate("location.hash = '#today'")
                pg.wait_for_selector("#todayP.on", timeout=5000)
                check(f"g. {mode}: #today opens today's discoveries", pg.locator("#todayBody li").count() >= 1)
                if shots and mode == "live":
                    pg.wait_for_timeout(800)
                    pg.screenshot(path=os.path.join(shots, "live_today.jpg"), type="jpeg", quality=80)
                pg.click("[data-open=aboutP]")
                check(f"g. {mode}: the Read panel explains the honesty numbers", "FDR" in pg.inner_text("#aboutP"))
                if shots and mode == "live":
                    pg.wait_for_timeout(800)
                    pg.screenshot(path=os.path.join(shots, "live_read.jpg"), type="jpeg", quality=80)
                pg.click("[data-close=aboutP]")
                pg.evaluate("location.hash = ''")
                lit_opened = pg.evaluate("""() => { const c = document.querySelector('#c');
                    const r = c.getBoundingClientRect(); return [r.width, r.height]; }""")
                check(f"g. {mode}: the canvas fills the screen", lit_opened == [390, 844], lit_opened)
                pg.click("#flyB")
                pg.wait_for_timeout(4000 if shots else 1500)
                if shots and mode == "live":
                    pg.screenshot(path=os.path.join(shots, "live_fly.jpg"), type="jpeg", quality=80)
                pg.click("#flyB")
                pg.click("#skyB")
                pg.wait_for_timeout(1500 if shots else 300)
                if shots and mode == "live":
                    pg.screenshot(path=os.path.join(shots, "live_day.jpg"), type="jpeg", quality=80)
                check(f"g. {mode}: no page errors and no failed requests", not errs and not failed and not pg.evaluate("window.__city.errors.length"),
                      (errs, failed))
                ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    t0 = time.time()
    shots = os.environ.get("DATACITY_SHOTS")
    if shots:
        os.makedirs(shots, exist_ok=True)
    test_outcomes()
    test_fdr()
    test_determinism()
    test_no_lookahead()
    test_incremental()
    test_outputs()
    if "--no-page" not in sys.argv:
        test_page(shots)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed in {time.time() - t0:.0f}s")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
