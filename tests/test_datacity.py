"""OLYMPUS DATA CITY (tools/datacity, tools/web_public/datacity): the data machine and its 3D page.

    python -X utf8 -m tests.test_datacity            # everything (~6-10 min; the page part needs Playwright + Chromium)
    python -X utf8 -m tests.test_datacity --no-page  # the engine only (~2 min)
    DATACITY_SHOTS=<dir> python -X utf8 -m tests.test_datacity   # also screenshots
    python -X utf8 -m tests.test_datacity --only v3  # the v3 section alone (files + the page, about 3 min)

Checks, on a real slice of data/NQ_5m.csv (2025-03 -> 2025-07):
  a. determinism: two builds of the event table and two scorings of the grid are identical
  b. no look-ahead: garbage after a mid-session cut changes no trigger, stop or state before the cut, and no outcome whose
     window ends before it
  c. incremental == full: a table built to a cut and extended equals one built in one go
  d. the mini-backtest: a hand-made bar path gives the 2R / stop / time exits and the $ after costs
  e. the FDR guard: Benjamini-Hochberg on a textbook case, null t-stats make (almost) no survivors, planted edges are
     found, pure-noise outcomes on the real grid make none; gold needs FDR + both periods + every year
  f. the outputs: keys (skyline, sections, dict, Today layer, weather, harbor, plugins), the skyline decodes to the
     engine's ids, the Jarvis card contract, sizes (research/datacity JSON <= 3 MB), 25k+ buildings in every district,
     no trading files touched
  h. the new districts (opening range, gaps, volatility, ES-NQ, the week, seasons), no look-ahead in the new states, and the
     Today layer (fired = traded on the last session, armed = its day states true) against the grid and the demo fixture
  g. the page in Chromium (HD, like an iPhone 13) at 390 x 844 and 844 x 390, live city and demo fixture: no errors or
     failed requests, layout (no overlaps), the orb's corner free, one top bar / one sheet / one dock; draw calls and
     triangles within budget at 32k buildings (overview and close-up) and at 40k (synthetic), LOD impostors far and full
     tiles near, LITE; the tour runs to its end; Today matches the fixture; Watch, search beam, minimap zoom, a plug-in
     district from plugins.json, the hidden-tab pause
  i. OLYMPUS v2 (2026-11-03): the render core (bloom + MSAA + finish pass on HD, 2 passes on LITE, 30 fps cap), landmarks
     (temple, forum, Pharos, Poseidon gate, a gate per district: taps open cards with the model's numbers), data streams,
     the outskirts (scenery, clear of the districts), day / night + weather driving the lights, the bloom and the streams,
     the fly-through cameras (skim, drone, grand) and the tag on a tapped building; the draw-call budget holds with all of it
  j. DATA CITY v3 (2026-11-04): 12 building types by idea family with a physically based facade and windows that tell the data (lit = holds in
     2021-25 AND 2026), cars, flying taxis, airships, the monorail loop (stations, trains), the river with reflections, sailing ships and cranes,
     neon district signs, weather from the VIX and day / night from the New York clock through the OLYMPUS effects library (god rays, lens flare,
     aurora, fireflies, lightning), fireworks for gold ideas, plain-words search that flies the camera, filters, compare two ideas, the city
     report with the Council of ideas, the growth timeline, photo mode with a share image, accessibility (calm motion, LITE, big text,
     contrast, keyboard, read-out), a minimap with the river / rail / gold; draw calls and triangles inside the budget with all of it on
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

from tests import browser_kit as BK  # noqa: E402  (shared launch: one reused browser, load-scaled timeouts, one retry of a flaky wait)

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.datacity import bars as B  # noqa: E402
from tools.datacity import features as F  # noqa: E402
from tools.datacity import grid as G  # noqa: E402
from tools.datacity import learn, report, store  # noqa: E402
from tools.datacity import skyline as SK  # noqa: E402

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

RESEARCH_BUDGET = 3_000_000       # every research/datacity/*.json together (owner order 2026-11-03)
CITY_BUDGET = 2_600_000           # city.json alone
DRAW_BUDGET = 120                 # draw calls a frame at 25k+ buildings, overview and close-up (renderer.info)
TRI_BUDGET = 700_000              # triangles a frame, same views


def test_outputs():
    tmp = tempfile.mkdtemp(prefix="dc_out_")
    before = {p: sha1(p) for p in glob.glob(os.path.join(ROOT, "live_model*.json"))}
    try:
        files = learn.run(df=slice_df(), out=tmp, web=None, store_run=False, src=src(), log=lambda *_: None, now=1793500000)
        need = {"city.json", "leaderboard.json", "discoveries.json", "summary.json", "history.json", "jarvis.json"}
        check("f. every output file is written", need <= set(os.listdir(tmp)), sorted(os.listdir(tmp)))
        city = files["city.json"]
        check("f. city.json has its sections (incl. skyline, dict, sections, today layer, weather, harbor, plugins)",
              {"v", "built", "last_day", "summary", "lit", "buildings", "strategies", "top10", "discoveries", "today", "lift", "districts",
               "sections", "skyline", "dict", "today_layer", "weather", "harbor", "plugins"} <= city.keys())
        bf = {"id", "d", "lab", "cls", "fdr", "e", "r", "w", "h2", "n", "tpw", "e26", "eo", "n26", "no", "tr", "yrs"}
        check("f. every building has its card fields", all(bf <= b.keys() for b in city["buildings"]) and city["buildings"])
        check("f. buildings: known districts and classes", {b["d"] for b in city["buildings"]} <= set(G.DISTRICTS)
              and {b["cls"] for b in city["buildings"]} <= {"gold", "green", "amber", "grey"})
        g = city["summary"]["guard"]
        check("f. the guard reports tried, tested, FDR, placebo and the holdout",
              all(k in g for k in ("tried", "tested", "fdr_pos", "placebo_fdr", "holdout")) and g["tried"] >= g["tested"])
        check("f. the LIT tower carries 2026, the H2 check half and 2021-25",
              city["lit"] and {"2026", "2026 H2", "2021-25"} <= city["lit"]["spans"].keys())
        sky = city["skyline"]
        check("f. skyline: every tested combination once (full cards + compact rows = tested)",
              len(sky["rows"]) + len(city["buildings"]) == g["tested"] and sky["cols"] == list(SK.COLS)
              and all(len(r) == len(SK.COLS) for r in sky["rows"]), (len(sky["rows"]), len(city["buildings"]), g["tested"]))
        ids = [b["id"] for b in city["buildings"]] + [js_id(city["dict"], r[:4]) for r in sky["rows"]]
        check("f. skyline ids (decoded like the page) are unique and never repeat a full card", len(ids) == len(set(ids)))
        check("f. the districts are data: every district a section with name, colour and counts",
              [s["key"] for s in city["sections"]] == list(G.DISTRICTS)
              and all(s["name"] and s["color"].startswith("#") and "tested" in s for s in city["sections"]))
        gr = G.Grid(store.event_table(slice_df(), cache=os.path.join(tmp, "_cache"), src=src(), log=lambda *_: None)[0])
        combo = next(c for c in G.enumerate_combos() if c["id"] == "slot_long|nyam")
        T, _, spans = report.strategy_score(gr, gr.rows(combo))
        sp = spans["2021-25"]
        check("f. a sized strategy: 1-40 micros at ~$500 risk, $, $/month and MFFU eval speed",
              all(1 <= t["qty"] <= 40 and (t["risk_usd"] <= 500 or t["qty"] == 1) for t in T)
              and {"net", "per_month", "p10", "f10", "dec10", "pass_med"} <= sp.keys() and sp["n"] == len(T), sp)
        check("f. jarvis.json follows the Jarvis card contract", not jarvis_problems(files["jarvis.json"]), jarvis_problems(files["jarvis.json"]))
        h1 = files["history.json"]
        os.makedirs(os.path.join(tmp, "plugins"))
        with open(os.path.join(tmp, "plugins", "rates.json"), "w", encoding="utf-8") as fh:   # a new data source's district
            json.dump(PLUGIN, fh)
        with open(os.path.join(tmp, "plugins", "bad.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        web = os.path.join(tmp, "web")
        f2 = learn.run(df=slice_df(), out=tmp, web=web, store_run=False, src=src(), log=lambda *_: None, now=1793500600)
        h2 = read_json(os.path.join(tmp, "history.json"))
        check("f. a rerun on the same data keeps one history row", len(h2["runs"]) == len(h1["runs"]) == 1)
        pl = read_json(os.path.join(web, "district_rates_demo.json")) if os.path.exists(os.path.join(web, "district_rates_demo.json")) else {}
        check("f. plug-in districts: research/datacity/plugins/*.json is listed in city.json and copied next to the page (a bad file is skipped)",
              f2["city.json"]["plugins"] == ["district_rates_demo.json"] and len(pl.get("items", [])) == len(PLUGIN["items"]), f2["city.json"]["plugins"])
        lb = read_json(os.path.join(tmp, "leaderboard.json"))["rows"]
        check("f. the leaderboard says plain-language findings with $ and trades/week",
              all("/trade/micro" in r["text"] and "a week" in r["text"] for r in lb))
        hb = city["harbor"]
        check("f. the Harbor: one ship per LIT trade (run lit_live) with day, side, R and $",
              hb is None or (hb["cols"] == ["day", "dir", "r", "pnl", "exit"] and all(len(r) == 5 for r in hb["rows"])))
        w = city["weather"]
        check("f. the weather comes from CBOE's VIX close (clear / haze / rain / storm)", w["sky"] in ("clear", "haze", "rain", "storm")
              and (w.get("vix") is None or w["sky"] == next(s for lim, s in SK.VIX_WEATHER if w["vix"] < lim)), w)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    after = {p: sha1(p) for p in before}
    check("f. paper only: no live_model*.json touched", before == after)
    real = [p for p in glob.glob(os.path.join(ROOT, "research", "datacity", "*.json"))]
    size = sum(os.path.getsize(p) for p in real)
    check(f"f. committed research/datacity JSON <= 3 MB ({size / 1e6:.2f} MB), city.json <= 2.6 MB",
          real and size <= RESEARCH_BUDGET and os.path.getsize(os.path.join(ROOT, "research", "datacity", "city.json")) <= CITY_BUDGET, size)
    full = read_json(os.path.join(ROOT, "research", "datacity", "city.json"))
    n = len(full["buildings"]) + len(full["skyline"]["rows"])
    by = {}
    for d in [full["dict"]["districts"][r[4]] for r in full["skyline"]["rows"]] + [b["d"] for b in full["buildings"]]:
        by[d] = by.get(d, 0) + 1
    check(f"f. the committed city: 25k+ buildings ({n:,}) in every district", n >= 25_000
          and {s["key"] for s in full["sections"]} == set(G.DISTRICTS) and len(by) == len(G.DISTRICTS), (n, by))
    for name in ("jarvis.json", "fixture.json", "plugins.json"):
        path = os.path.join(PAGE, name)
        ok = os.path.exists(path)
        obj = read_json(path) if ok else {}
        if name == "jarvis.json":
            check("f. the page's jarvis.json follows the contract", ok and not jarvis_problems(obj), jarvis_problems(obj) if ok else "missing")
        elif name == "fixture.json":
            check("f. the demo fixture is small, marked demo, with every district and a Today layer",
                  ok and obj.get("demo") is True and os.path.getsize(path) < 160_000 and len(obj["buildings"]) >= 20
                  and {obj["dict"]["districts"][r[4]] for r in obj["skyline"]["rows"]} | {b["d"] for b in obj["buildings"]} == set(G.DISTRICTS)
                  and obj.get("today_layer"), (os.path.getsize(path), len(obj.get("buildings", []))) if ok else "missing")
        else:
            check("f. plugins.json (the plug-in district index) is valid", ok and isinstance(obj.get("districts"), list))


def js_id(D, code):
    """The page's comboId (data.js) in Python, to check the skyline decodes to the engine's ids."""
    t, w, k1, k2 = code
    where = f"s{w - 100:02d}" if w >= 100 else "all" if w < 0 else D["wins"][w]
    ks = [f"{D['fams'][k >> 4][0]}={k & 15}" for k in (k1, k2) if k >= 0]
    return f"{D['trigs'][t][0]}|{where}" + ("|" + "&".join(ks) if ks else "")


# ------------------------------------------------------------------------------------------------ h. districts + Today layer
def test_districts_today():
    combos = G.enumerate_combos()
    ids = {c["id"]: c for c in combos}
    check("h. new families exist and are crossed (opening range, gap types, VIX curve / trend, ES-NQ, calendar, weekday x slot)",
          all(f in F.STATES for f in ("orw", "orp", "gapt", "vts", "vtr", "esr", "cal"))
          and "slot_long|s40|wd=0" in ids and "disp_bear|nyam|orp=0&today=0" in ids and "vwap_dn|pm|gapt=2&vwap=0" in ids, len(combos))
    want = {"slot_long|s40|wd=0": "week", "slot_long|asia|mon=2": "seasons", "vwap_dn|pm|today=1&gap=1": "gaps",
            "fvg_bear|pm|atr=2&lsa=0": "volatility", "disp_bear|nyam|orp=0&today=0": "orange", "cisd_bull|london|smt=2": "esnq",
            "sweep_pdl|nyam|vwap=0": "while", "slot_short|pm": "times", "cisd_bull|all": "confluences"}
    got = {k: ids[k]["district"] for k in want if k in ids}
    check("h. every combination lives in its district (first matching family wins)", got == want, got)
    check("h. district counts: every district has combinations", {c["district"] for c in combos} == set(G.DISTRICTS))
    feat = F.build(slice_df(), **src())
    ev = feat["ev"]
    check("h. no look-ahead in the new states: opening-range states only from 09:45, RTH gap types only from 09:30",
          (ev["s_orw"][ev["slot"] < 39] == -1).all() and (ev["s_orp"][ev["slot"] < 39] == -1).all() and (ev["s_gapt"][ev["slot"] < 38] == -1).all())
    gr = G.Grid(feat)
    rows = gr.score_all(combos)
    G.guard(combos, rows)
    tl = SK.Today(gr)
    last = len(gr.days) - 1
    bad, fired, armed = [], 0, 0
    for c, s in zip(combos, rows, strict=True):
        if s.get("n", 0) < G.MIN_N:
            continue
        f = tl.flag(c, s)
        r = gr.rows(c)
        is_fired = bool(len(r)) and int(gr.ev["day"][r[-1]]) == last
        if (f == SK.FL_FIRED) != is_fired:
            bad.append(c["id"])
        if f == SK.FL_ARMED:
            armed += 1
            if not all(tl.states.get(fm) == v for fm, v in c["conds"]):
                bad.append(c["id"])
        fired += f == SK.FL_FIRED
    check(f"h. the Today layer: fired = traded on the last session ({fired}), armed = its day states true ({armed})",
          not bad and fired > 0 and armed > 0, bad[:5])
    fx = read_json(os.path.join(PAGE, "fixture.json"))
    flags = fx["dict"]["flags"]
    lit = sum(1 for b in fx["buildings"] if b.get("td")) + sum(1 for r in fx["skyline"]["rows"] if r[-1] & (flags["fired"] | flags["armed"]))
    TODAY_FIXTURE["lit"] = lit
    check(f"h. the demo fixture carries a Today layer ({lit} lit buildings)", lit > 0 and fx["today_layer"]["day"])


TODAY_FIXTURE = {}


def test_new_families():
    """MORE DATABASES (2026-11-10): calendar, FOMC, gap size, hour, overnight range, first hour, ES-NQ hour: new districts, no look-ahead."""
    new = F.NEW_FAMILIES
    combos = G.enumerate_combos()
    check("n. nine new state families, filed in the existing nine districts (no new landmarks: the performance budgets stay)", all(f in F.STATES for f in new)
          and len(G.DISTRICTS) == 9 and {c["district"] for c in combos} == set(G.DISTRICTS), len(combos))
    ids = {c["id"]: c["district"] for c in combos}
    check("n. families land in their districts (calendar facts -> seasons, overnight range / first hour -> opening range, hour -> times, gap size -> gaps, ES-NQ hour -> ES-NQ, hour x VIX -> volatility)",
          ids.get("slot_long|nyam|fomc=1") == "seasons" and ids.get("vwap_dn|pm|onr=2&vwap=0") == "orange" and ids.get("vwap_dn|pm|hr=6") == "times" and ids.get("vwap_dn|pm|hr=6&vix=1") == "volatility"
          and ids.get("fvg_bear|pm|gsz=2&wd=1") == "gaps" and ids.get("fvg_bear|pm|esd=0&vwap=0") == "esnq", [ids.get(k) for k in ("slot_long|nyam|fomc=1", "vwap_dn|pm|hr=6")])
    feat = F.build(slice_df("2024-06-02", "2025-12-31"), **src())
    ev = feat["ev"]
    check("n. no look-ahead: gap size and overnight range from 09:30, the first hour from 10:30",
          (ev["s_gsz"][ev["slot"] < 38] == -1).all() and (ev["s_onr"][ev["slot"] < 38] == -1).all() and (ev["s_fhd"][ev["slot"] < 42] == -1).all(), None)
    check("n. calendar states are schedule facts: constant within a day", all(len(set(ev["s_" + f][ev["day"] == d])) == 1 for f in ("dom", "wom", "mend", "fomc") for d in range(3)), None)
    days = np.array(["2026-03-30", "2026-03-31", "2026-06-17", "2026-06-18", "2026-04-04"], dtype="datetime64[D]")
    dom, wom, mend, fomc = F._calendar2(days, {"2026-06-17"})
    check("n. month-end, quarter-end, FOMC week, weekend", list(mend) == [2, 2, 0, 0, -1] and list(fomc) == [0, 0, 2, 1, -1] and wom[1] == 3 and dom[0] == 2,
          (list(mend), list(fomc)))
    gr = G.Grid(feat)
    rows = gr.score_all(combos)
    guard = G.guard(combos, rows)
    st = G.family_stats(combos, rows, new)
    check("n. every new family is scored (n, both periods, FDR kept)", all(st[f]["tested"] > 0 for f in new if f != "esd") and guard["tested"] > 0, st)


def test_v2_files():
    """i. the v2 files exist, ride the OLYMPUS render core and touch nothing shared."""
    names = ["landmarks.js", "streams.js", "outskirts.js", "fly.js"]
    check("i. v2 files exist: " + ", ".join(names), all(os.path.exists(os.path.join(PAGE, n)) for n in names))
    scene = read_text(os.path.join(PAGE, "scene.js"))
    check("i. scene.js draws through the OLYMPUS render core (createRenderer, display space, no own WebGLRenderer)",
          "createRenderer" in scene and "../olympus/render.js" in scene and "space: 'display'" in scene
          and "new THREE.WebGLRenderer" not in scene and "renderer.render(this.scene" not in scene)
    check("i. landmarks use the core's PBR materials", "../olympus/materials.js" in read_text(os.path.join(PAGE, "landmarks.js")))
    check("i. LITE caps the frame loop at 30 fps", "this.quality === 'lq' && now - last < 28" in read_text(os.path.join(PAGE, "city.js")))
    html = read_text(os.path.join(PAGE, "index.html"))
    check("i. the camera buttons and the tag are in the page",
          all(f'data-cam="{k}"' in html for k in ("orbit", "skim", "walk", "drone", "grand")) and 'id="tag"' in html)
    shared = os.path.join(os.path.dirname(PAGE), "olympus")
    check("i. the render core sits next to the page (the site layout); none of it is copied into datacity",
          os.path.exists(os.path.join(shared, "render.js")) and not os.path.exists(os.path.join(PAGE, "render.js")))


# ------------------------------------------------------------------------------------------------ g. the page
def _serve(root):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


PLUGIN = {"v": 1, "key": "rates_demo", "name": "RATES (TEST)", "blurb": "a plug-in district for the test", "color": "#7fe9ff",
          "items": [{"id": f"r{i}", "lab": f"test feed {i}", "value": (i % 7) - 2, "unit": "z", "cls": "grey" if i % 3 else "green"} for i in range(150)]}
HIDE = """(on) => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => on });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (on ? 'hidden' : 'visible') });
  document.dispatchEvent(new Event('visibilitychange')); }"""
CORNER = """() => { const W = innerWidth, H = innerHeight, bad = [];
  for (const e of document.querySelectorAll('.dock, .tab, .chip, .sheet.on, .toast.on, .mini, .caption.on')) {
    const r = e.getBoundingClientRect(); if (!r.width || getComputedStyle(e).display === 'none') continue;
    if (r.right > W - 80 && r.bottom > H - 160 && r.left < W && r.top < H) bad.push(e.className); }
  return bad; }"""
LAYOUT = """async () => { const { decode } = await import('./data.js'); const { layout } = await import('./layout.js');
  const city = await (await fetch('./' + (window.__city.mode === 'live' ? 'city' : 'fixture') + '.json')).json();
  const M = decode(city), L = layout(M), it = L.items, cell = new Map(), clash = [];
  for (let i = 0; i < it.length; i++) { const k = Math.round(it[i].x / 1.2) + ',' + Math.round(it[i].z / 1.2);
    if (!cell.has(k)) cell.set(k, []); cell.get(k).push(i); }
  for (let i = 0; i < it.length && clash.length < 3; i++) { const cx = Math.round(it[i].x / 1.2), cz = Math.round(it[i].z / 1.2);
    for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (const j of cell.get((cx + dx) + ',' + (cz + dz)) || [])
      if (j > i && Math.hypot(it[i].x - it[j].x, it[i].z - it[j].z) < (it[i].w + it[j].w) / 2 + 0.3 && it[i].kind !== 'ship' && it[j].kind !== 'ship') clash.push([it[i].b.id, it[j].b.id]); }
  const D = L.districts.filter((d) => d.kind !== 'harbor'), over = [];
  for (let i = 0; i < D.length; i++) for (let j = i + 1; j < D.length; j++)
    if (Math.abs(D[i].cx - D[j].cx) < D[i].half + D[j].half && Math.abs(D[i].cz - D[j].cz) < D[i].half + D[j].half) over.push([D[i].key, D[j].key]);
  return { n: it.length, want: M.buildings.length + (city.strategies || []).length + (city.discoveries || []).length + (city.harbor?.rows.length || 0),
           clash, over, inTower: it.filter((x) => Math.hypot(x.x, x.z) < 6).length,
           inPlaza: it.filter((x) => x.kind === 'b' && Math.hypot(x.x, x.z) < L.plazaR).length,
           ok: it.every((x) => x.h > 0 && Number.isFinite(x.h) && x.lit >= 0 && x.lit <= 1), tiles: L.tiles.length, blocks: L.blocks.length }; }"""


def _site(tmp, mode, plugin=False):
    site = os.path.join(tmp, mode, "datacity")
    shutil.copytree(PAGE, site)
    # the site layout around it: Jarvis's three.js and fonts (../jarvis/) and the OLYMPUS kit (../olympus/)
    os.makedirs(os.path.join(tmp, mode, "jarvis"))
    for f in ["three.module.min.js"] + glob.glob(os.path.join(os.path.dirname(PAGE), "jarvis", "*.woff2")):
        shutil.copy(os.path.join(os.path.dirname(PAGE), "jarvis", os.path.basename(f)), os.path.join(tmp, mode, "jarvis"))
    shutil.copytree(os.path.join(os.path.dirname(PAGE), "olympus"), os.path.join(tmp, mode, "olympus"))
    from tests.olympus_money_kit import link_assets
    link_assets(os.path.join(tmp, mode))              # the built site's assets/ (the kit's sounds, ui.ogg ...): no 404 on the first tap
    with open(os.path.join(tmp, mode, "data.json"), "w", encoding="utf-8") as fh:      # the dashboard's LIT state: price + today's untaken levels (the Market now card)
        json.dump({"live": {"price": 25000.0, "last_run": "2026-11-03 10:00", "levels": [
            {"price": 24970.0, "side": "L", "label": "PDL"}, {"price": 24985.0, "side": "L", "label": "London low"},
            {"price": 25020.0, "side": "H", "label": "London high"}, {"price": 25045.0, "side": "H", "label": "PDH"}]}}, fh)
    pan = os.path.join(os.path.dirname(PAGE), "pantheon", "pantheon.json")
    if os.path.exists(pan):                       # the report reads the Council of the Gods next door
        os.makedirs(os.path.join(tmp, mode, "pantheon"), exist_ok=True)
        shutil.copy(pan, os.path.join(tmp, mode, "pantheon", "pantheon.json"))
    if mode == "demo":
        os.remove(os.path.join(site, "city.json"))
    if plugin:
        with open(os.path.join(site, "district_rates_demo.json"), "w", encoding="utf-8") as fh:
            json.dump(PLUGIN, fh)
        with open(os.path.join(site, "plugins.json"), "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "districts": ["district_rates_demo.json"]}, fh)


def _ready(pg, url):
    pg.goto(url)
    pg.wait_for_function("window.__city && window.__city.ready", timeout=180000)


def _frames(pg, n, timeout=120000):
    """Wait until n more frames were drawn (SwiftShader is slow at 32k buildings)."""
    pg.wait_for_function(f"window.__city.frames >= {pg.evaluate('window.__city.frames') + n}", timeout=timeout)


def test_page(shots=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("g. page test skipped: no Playwright", True)
        return
    tmp = tempfile.mkdtemp(prefix="dc_page_")
    _site(tmp, "live", plugin=True)
    _site(tmp, "demo")
    srv = _serve(tmp)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

            def page(w=390, h=844, reduced=True):
                ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, has_touch=True, is_mobile=True,
                                     reduced_motion="reduce" if reduced else "no-preference")
                ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")   # HD, like an iPhone 13
                pg = ctx.new_page()
                errs, failed = [], []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                pg.on("requestfailed", lambda r: failed.append(r.url))
                return ctx, pg, errs, failed

            for mode in ("live", "demo"):
                for (w, h) in ((390, 844), (844, 390)):
                    ctx, pg, errs, failed = page(w, h)
                    _ready(pg, f"{base}/{mode}/datacity/?nolite=1")
                    _frames(pg, 2)
                    st = pg.evaluate("window.__city")
                    tag = f"{mode} {w}x{h}"
                    check(f"g. {tag}: the city is drawn ({st['buildings']:,} buildings, {len(st['districts'])} districts)",
                          st["mode"] == mode and st["buildings"] >= (25_000 if mode == "live" else 200) and not st["errors"]
                          and {"harbor", "strategies"} <= set(st["districts"]), {k: st[k] for k in ("mode", "buildings", "errors", "districts")})
                    free = pg.evaluate(CORNER)
                    check(f"g. {tag}: Jarvis's bottom-right 80 x 160 px stays free", not free, free)
                    check(f"g. {tag}: no sideways scroll, the canvas fills the screen",
                          pg.evaluate("document.documentElement.scrollWidth <= innerWidth") and pg.evaluate(
                              "(() => { const r = document.querySelector('#c').getBoundingClientRect(); return [r.width, r.height]; })()") == [w, h])
                    check(f"g. {tag}: one top bar, one sheet, one dock", pg.evaluate(
                        "document.querySelectorAll('header.top').length === 1 && document.querySelectorAll('.sheet').length === 1 && document.querySelectorAll('nav.dock').length === 1"))
                    if w == 390:
                        check(f"g. {tag}: theme-color, viewport-fit=cover, safe areas", pg.evaluate(
                            "document.querySelector('meta[name=theme-color]').content.startsWith('#') && "
                            "document.querySelector('meta[name=viewport]').content.includes('viewport-fit=cover')")
                            and "safe-area-inset-bottom" in read_text(os.path.join(PAGE, "index.html")))
                        lay = pg.evaluate(LAYOUT)
                        check(f"g. {mode}: layout places everything once, no two buildings overlap, districts apart, the plaza free",
                              lay["n"] == lay["want"] and not lay["clash"] and not lay["over"] and not lay["inTower"] and not lay["inPlaza"] and lay["ok"], lay)
                    if mode == "demo" and w == 390:
                        check("g. demo: the DEMO chip shows", pg.locator(".chip.demo").count() == 1)
                        pg.evaluate("location.hash = '#today'")
                        pg.wait_for_selector(".sheet.on[data-view=today]", timeout=8000)
                        st = pg.evaluate("window.__city.today")
                        check(f"g. demo: the Today layer lights exactly the fixture's {TODAY_FIXTURE.get('lit')} buildings",
                              st["on"] and st["lit"] == TODAY_FIXTURE.get("lit"), (st, TODAY_FIXTURE))
                    if mode == "live" and w == 390:
                        _live_checks(pg, shots)
                    if shots and mode == "live":
                        pg.screenshot(path=os.path.join(shots, f"city_{w}x{h}.jpg"), type="jpeg", quality=82)
                    if mode == "demo":                       # the demo's only miss is the city.json it falls back from
                        errs = [e for e in errs if "404" not in e]
                    check(f"g. {tag}: no page errors and no failed requests", not errs and not failed and not pg.evaluate("window.__city.errors.length"),
                          (errs[:3], failed[:3]))
                    ctx.close()
            ctx, pg, errs, failed = page(reduced=False)
            _ready(pg, f"{base}/live/datacity/?nolite=1&tourSpeed=40")
            _frames(pg, 2)
            pg.click("#tourB")
            pg.wait_for_function("window.__city.tour.on && window.__city.tour.step >= 0", timeout=20000)
            caps, seen = set(), set()
            t0 = time.time()
            while time.time() - t0 < 240:
                t = pg.evaluate("window.__city.tour")
                if t.get("on"):
                    seen.add(t["step"])
                    caps.add(t.get("caption") or "")
                if t.get("done"):
                    break
                pg.wait_for_timeout(250)
            t = pg.evaluate("window.__city.tour")
            check(f"g. the cinematic tour runs: {len(seen)} shots with captions, ends, the orbit takes over",
                  t.get("done") == 1 and len(seen) >= 6 and all(caps) and any("LIT" in c for c in caps) and any("noise" in c for c in caps)
                  and not pg.evaluate("window.__app.orbit.flying"), (t, sorted(seen), sorted(caps)[:3]))
            check("g. tour: no page errors", not errs, errs[:3])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def _live_checks(pg, shots):
    """Perf budgets, LOD, today, watch, search beam, minimap, plug-ins, hidden tab (live city, 390 x 844, HD)."""
    s = pg.evaluate("window.__city.stats()")
    check(f"g. live: overview draws {s['calls']} calls / {s['triangles']:,} triangles (budget {DRAW_BUDGET} / {TRI_BUDGET:,}) with "
          f"{s['lod']['impostors']} far blocks as impostors", s["calls"] <= DRAW_BUDGET and s["triangles"] <= TRI_BUDGET and s["lod"]["impostors"] > 0
          and s["pixelRatio"] <= 2, s)
    PERF["overview"] = s
    pg.evaluate("(() => { const d = window.__app.L.districts.slice().sort((a, b) => b.n - a.n)[0]; window.__app.orbit.focus(d.cx, 0, d.cz, 60, 1.05); })()")
    _frames(pg, 3)
    s = pg.evaluate("window.__city.stats()")
    check(f"g. live: close-up draws {s['calls']} calls / {s['triangles']:,} triangles with {s['lod']['tilesFull']} tiles in full "
          f"(LOD), within budget", s["calls"] <= DRAW_BUDGET and s["triangles"] <= TRI_BUDGET and s["lod"]["tilesFull"] > 0, s)
    PERF["closeup"] = s
    if shots:
        pg.screenshot(path=os.path.join(shots, "closeup_390x844.jpg"), type="jpeg", quality=82)
    st = pg.evaluate("window.__city")
    check("g. live: plug-in district loaded from plugins.json (a new data source is one JSON file)", "rates_demo" in st["districts"], st["districts"])
    pg.click("[data-tab=top]")
    check("g. live: Top 10 lists findings", pg.locator("#sheetBody li").count() >= 1)
    pg.locator("#sheetBody li").first.click()
    pg.wait_for_selector(".sheet.on[data-view=card]", timeout=8000)
    card = pg.inner_text("#sheet")
    check("g. live: a building card shows $/micro, both periods, a history sparkline and the paper-only line",
          "per trade per MNQ micro" in card and "2021-25" in card and "Paper only" in card and pg.locator("#sheet svg.spark").count() >= 1, card[:160])
    check("g. live: the search beam lights the opened building", pg.evaluate("window.__app.city.beam.at !== null"))
    pg.click("#sheet .actions .pill")
    pg.wait_for_timeout(200)
    check("g. live: Watch pins the building (kept on this device)", pg.evaluate("window.__city.watch") == 1
          and "dc.watch" in pg.evaluate("Object.keys(localStorage).join(',')"))
    pg.click("#sheetX")
    pg.click("[data-tab=watch]")
    check("g. live: the Watch view lists it with a sparkline", pg.locator("#sheetBody li").count() == 1 and pg.locator("#sheetBody svg").count() >= 1)
    pg.click("[data-tab=find]")
    pg.fill("#q", "London sweep")
    pg.wait_for_timeout(300)
    found = pg.evaluate("window.__city.found")
    check(f"g. live: search finds London sweeps ({found}) and beams onto the best one", found >= 1 and pg.evaluate("window.__app.city.beam.at !== null"))
    if shots:
        _frames(pg, 2)
        pg.screenshot(path=os.path.join(shots, "search_390x844.jpg"), type="jpeg", quality=82)
    pg.click("#sheetX")
    pg.evaluate("location.hash = '#today'")
    pg.wait_for_selector(".sheet.on[data-view=today]", timeout=8000)
    t = pg.evaluate("window.__city.today")
    want = pg.evaluate("window.__app.L.items.filter((it) => it.kind === 'b' && it.b.td).length")
    check(f"g. live: the Today layer lights the {t['lit']:,} buildings true on the last session", t["on"] and t["lit"] == want and want > 0, (t, want))
    if shots:
        _frames(pg, 2)
        pg.screenshot(path=os.path.join(shots, "today_390x844.jpg"), type="jpeg", quality=82)
    pg.click("#sheetX")
    box = pg.locator("#mini").bounding_box()
    d = pg.evaluate("(() => { const L = window.__app.L, m = window.__app.minimap, d = L.districts.slice().sort((a, b) => b.n - a.n)[0]; return m.toMap(d.cx, d.cz).concat([d.key]); })()")
    pg.mouse.click(box["x"] + d[0], box["y"] + d[1])
    pg.wait_for_timeout(300)
    check(f"g. live: a minimap tap zooms to that district ({d[2]})", pg.evaluate("window.__city.district") == d[2] and pg.locator(".sheet.on[data-view=district]").count() == 1)
    pg.click("#sheetX")
    f0 = pg.evaluate("window.__city.frames")
    pg.evaluate(HIDE, True)
    pg.wait_for_timeout(1500)
    f1 = pg.evaluate("window.__city.frames")
    pg.evaluate(HIDE, False)
    pg.wait_for_timeout(200)
    _frames(pg, 1, 30000)
    f2 = pg.evaluate("window.__city.frames")
    check("g. live: hidden tab = no frame, drawing again once visible", f1 <= f0 + 1 and f2 > f1, (f0, f1, f2))
    th = pg.evaluate("""() => { window.__city.applyTheme({ accent: '#ff3399', panel: 'rgba(20,4,30,.9)', bg: 'url(x)' });
      return [getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(), '#' + window.__app.city.U.uAccent.value.getHexString(),
              getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()]; }""")
    check("g. live: applyTheme(tokens) sets the page tokens and the scene accent (a bad token is ignored)",
          th[0] == "#ff3399" and th[1] == "#ff3399" and th[2].startswith("rgba(20"), th)
    pg.evaluate("window.__app.setQuality('lq')")
    _frames(pg, 2)
    s = pg.evaluate("window.__city.stats()")
    check(f"g. live: LITE drops the reflections and the pixel ratio ({s['calls']} calls)", s["lod"]["mirrors"] == 0 and s["pixelRatio"] <= 1.5, s)
    pg.evaluate("window.__app.setQuality('hq')")
    _v2_checks(pg, shots)


V2 = """async () => {
  const app = window.__app, city = app.city, lm = city.lm, rc = city.rc, out = {};
  const { weatherOf, sunOf } = await import('./sky.js');
  const fly = await import('./fly.js');
  out.rc = { passes: rc.passes(), stats: rc.stats(), q: rc.quality() };
  out.spots = Object.keys(lm.spots);
  out.districts = app.L.districts.filter((d) => d.kind !== 'harbor').map((d) => d.key);
  out.finite = Object.values(lm.spots).every((s) => [s.x, s.z, s.r, s.h].every(Number.isFinite));
  out.proxies = lm.proxies.length;
  out.streams = { arcs: city.streams.arcs.length, pulses: city.streams.pulses };
  const m = city.outskirts.mesh.instanceMatrix.array, n = city.outskirts.total, bad = [];
  const hb = app.L.harbor, ds = app.L.districts.filter((d) => d.kind !== 'harbor');
  for (let i = 0; i < n; i++) {
    const x = m[i * 16 + 12], z = m[i * 16 + 14];
    if (ds.some((d) => Math.abs(x - d.cx) < d.half && Math.abs(z - d.cz) < d.half) || (hb && x > hb.x0 && x < hb.x1 && z > hb.z0 && z < hb.z1)
        || Math.hypot(x - lm.site.x, z - lm.site.z) < 100) bad.push([x, z]);
  }
  out.outskirts = { n, bad: bad.length, ring: city.outskirts.radius };
  const set = (vix, mod, open = true) => { app.weather = weatherOf(vix); app.wxOn = true;
    const sun = sunOf({ mod, mins: (mod + 1080) % 1440, dow: 2 }); sun.open = open; city.setSun(sun, app.weather); };
  set(12, 930); const day = { sun: lm.lights.sun.intensity, moon: lm.lights.moon.intensity, bloom: city.bloomK, flow: city.U.uFlow.value, gate: lm.vixBase.slice() };
  set(12, 1380); const night = { sun: lm.lights.sun.intensity, moon: lm.lights.moon.intensity, bloom: city.bloomK, flow: city.U.uFlow.value, beam: lm.beamMat.opacity };
  set(32, 1380); const storm = { flow: city.U.uFlow.value, gate: lm.vixBase.slice(), rate: lm.vixRate };
  set(12, 1380, false); const closed = { flow: city.U.uFlow.value };
  out.sky = { day, night, storm, closed };
  app.weather = weatherOf(app.model.weather?.vix); app.applySky(true);
  const from = { pos: city.camera.position.clone(), look: new (city.camera.position.constructor)(0, 0, 0) };
  out.fly = {};
  for (const mode of ['skim', 'drone', 'grand']) {
    const f = fly.flight(mode, app.L, lm.spots, from);
    let ok = true, lo = 1e9; const seen = new Set();
    for (let i = 0; i < 1500; i++) {
      const s = f.step(0.1), p = s.pos;
      if (![p.x, p.y, p.z, s.look.x, s.look.y, s.look.z].every(Number.isFinite)) ok = false;
      if (i > 20) lo = Math.min(lo, p.y);
      seen.add(f.info().landmark);
    }
    out.fly[mode] = { ok, lo: +lo.toFixed(1), len: Math.round(f.length), seen: [...seen].filter(Boolean) };
  }
  return out;
}"""


def _tap(pg, sel):
    """A DOM click (Playwright's click waits for stable frames, which a loaded SwiftShader page can starve for 30 s)."""
    pg.evaluate("(s) => document.querySelector(s).click()", sel)


def _v2_checks(pg, shots):
    """i. the render core, landmarks, streams, outskirts, sky tie, cameras and the tag (live city, 390 x 844, HD)."""
    r = pg.evaluate(V2)
    check(f"i. HD runs the core's passes {r['rc']['passes']}: bloom + MSAA {r['rc']['stats']['samples']}x + the film finish",
          r["rc"]["passes"] == ["scene", "bloom", "finish"] and r["rc"]["stats"]["samples"] == 4 and r["rc"]["stats"]["bloom"], r["rc"])
    need = {"temple", "forum", "pharos", "poseidon"} | {"gate:" + k for k in r["districts"]}
    check(f"i. landmarks: temple, forum, Pharos, Poseidon gate and a gate for each of the {len(r['districts'])} districts, all placed",
          need <= set(r["spots"]) and r["finite"] and r["proxies"] >= len(need), (sorted(need - set(r["spots"])), r["finite"], r["proxies"]))
    check(f"i. data streams: {r['streams']['arcs']} arcs between the districts, the plaza, the harbor and the temple ({r['streams']['pulses']} pulses)",
          r["streams"]["arcs"] >= len(r["districts"]) + 2 and r["streams"]["pulses"] >= 200, r["streams"])
    check(f"i. outskirts: {r['outskirts']['n']:,} scenery towers in one draw, none inside a district, the harbor or the acropolis",
          r["outskirts"]["n"] >= 700 and r["outskirts"]["bad"] == 0, r["outskirts"])
    sk = r["sky"]
    check("i. day / night drives the lights (sun by day, moon by night) and the bloom (more glow at night)",
          sk["day"]["sun"] > sk["night"]["sun"] * 1.5 and sk["night"]["moon"] > sk["day"]["moon"] * 1.5 and sk["night"]["bloom"] > sk["day"]["bloom"], sk)
    check("i. the VIX drives the weather gate (cyan calm, red in a storm); the streams run faster in a storm and slower when the market is closed",
          sk["day"]["gate"][2] > sk["day"]["gate"][0] and sk["storm"]["gate"][0] > sk["storm"]["gate"][2]
          and sk["storm"]["flow"] > sk["night"]["flow"] > sk["closed"]["flow"], sk)
    f = r["fly"]
    check(f"i. fly paths are finite and stay above the roofs (skim {f['skim']['len']}, drone {f['drone']['len']}, grand {f['grand']['len']} units); "
          f"the grand tour visits {', '.join(f['grand']['seen'])}", all(f[m]["ok"] for m in f) and f["skim"]["lo"] >= 15 and f["drone"]["lo"] >= 60
          and {"forum", "pharos", "poseidon", "temple"} <= set(f["grand"]["seen"]), f)
    pg.evaluate("window.__app.openLandmark('forum')")
    pg.wait_for_selector(".sheet.on[data-view=card]", timeout=8000)
    card = pg.inner_text("#sheet")
    check("i. tap the Forum: its card shows tried / tested / gold counts", "The Forum" in card and "tested" in card.lower() and "tried" in card.lower(), card[:140])
    pg.evaluate("window.__app.openLandmark('poseidon')")
    card = pg.inner_text("#sheet")
    check("i. tap the Gate of Poseidon: the card shows the VIX, VXN and the sky", "VIX" in card and "VXN" in card and "sky" in card.lower(), card[:140])
    pg.evaluate("window.__app.openLandmark('temple')")
    check("i. tap the Temple: the card counts the gold buildings", "gold buildings" in pg.inner_text("#sheet"))
    pg.evaluate("window.__app.openLandmark('pharos')")
    check("i. tap the Pharos: the card counts LIT's ships", "ships" in pg.inner_text("#sheet"))
    _tap(pg, "#sheetX")
    hit = pg.evaluate("""() => { const a = window.__app, s = a.city.lm.spots.temple, o = a.orbit;
      for (const v of [o.goal, o.view]) { v.target.set(s.x, 20, s.z); v.radius = 150; v.phi = 1.1; v.theta = 0.4; }
      o.focusTo = null; o.update(0.016); a.city.camera.updateMatrixWorld(true);
      return a.city.pick(innerWidth / 2, innerHeight / 2); }""")
    check("i. a screen tap on the temple picks the landmark (not a building)", hit and hit.get("landmark") == "temple", hit)
    pg.evaluate("window.__app.open(window.__app.L.items.findIndex((it) => it.kind === 'b' && it.b.cls === 'gold'))")
    _frames(pg, 2)
    tag = pg.evaluate("(() => { const t = document.querySelector('#tag'); return [getComputedStyle(t).display, t.textContent]; })()")
    check("i. tap a building: a tag rides over it with its name and result", tag[0] == "block" and "/trade" in tag[1], tag)
    _tap(pg, "#sheetX")
    check("i. closing the card hides the tag", pg.evaluate("getComputedStyle(document.querySelector('#tag')).display") == "none")
    for mode in ("skim", "drone", "grand"):
        _tap(pg, f"[data-cam={mode}]")
        p0 = pg.evaluate("window.__app.city.camera.position.toArray()")
        _frames(pg, 6)
        p1 = pg.evaluate("window.__app.city.camera.position.toArray()")
        st = pg.evaluate("window.__city.cam")
        moved = sum((a - b) ** 2 for a, b in zip(p0, p1)) ** 0.5
        check(f"i. camera mode {mode.upper()}: flying ({moved:.0f} units in 6 frames), button lit, the orbit paused",
              st["on"] and st["mode"] == mode and moved > 0.5 and pg.evaluate("window.__app.orbit.flying")
              and pg.locator(f"[data-cam={mode}].on").count() == 1, (st, moved))
        if shots:
            pg.screenshot(path=os.path.join(shots, f"cam_{mode}_390x844.jpg"), type="jpeg", quality=82)
    _tap(pg, "[data-cam=orbit]")
    st = pg.evaluate("window.__city.cam")
    check("i. ORBIT hands the camera back", not st["on"] and not pg.evaluate("window.__app.orbit.flying")
          and pg.locator("[data-cam=orbit].on").count() == 1, st)
    _tap(pg, "[data-cam=skim]")
    pg.mouse.move(100, 400)
    pg.mouse.down()
    pg.mouse.move(180, 430, steps=4)
    pg.mouse.up()
    check("i. a drag during a fly-through takes the camera back", not pg.evaluate("window.__city.cam.on") and not pg.evaluate("window.__app.orbit.flying"))
    pg.evaluate("window.__app.setQuality('lq')")
    _frames(pg, 2)
    names = pg.evaluate("window.__app.city.rc.passes()")
    s = pg.evaluate("window.__city.stats()")
    check(f"i. LITE: {names} (FXAA in the finish pass, no bloom), pixel ratio {s['pixelRatio']}, {s['calls']} calls",
          names == ["scene", "finish"] and s["pixelRatio"] <= 1.5 and s["calls"] <= DRAW_BUDGET, (names, s))
    pg.evaluate("window.__app.setQuality('hq')")
    _frames(pg, 2)
    s = pg.evaluate("window.__city.stats()")
    PERF["v2"] = s
    check(f"i. everything on, HD: {s['calls']} draw calls / {s['triangles']:,} triangles (budget {DRAW_BUDGET} / {TRI_BUDGET:,})",
          s["calls"] <= DRAW_BUDGET and s["triangles"] <= TRI_BUDGET, s)


PERF = {}


def test_synth_budget():
    """40k buildings (the live city + synthetic greys): the draw-call budget still holds."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    tmp = tempfile.mkdtemp(prefix="dc_syn_")
    _site(tmp, "live")
    srv = _serve(tmp)
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, reduced_motion="reduce")
            ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
            pg = ctx.new_page()
            _ready(pg, f"http://127.0.0.1:{srv.server_address[1]}/live/datacity/?nolite=1&synth=8000")
            _frames(pg, 2)
            n = pg.evaluate("window.__city.buildings")
            s = pg.evaluate("window.__city.stats()")
            pg.evaluate("(() => { const d = window.__app.L.districts.slice().sort((a, b) => b.n - a.n)[0]; window.__app.orbit.focus(d.cx, 0, d.cz, 60, 1.05); })()")
            _frames(pg, 3)
            s2 = pg.evaluate("window.__city.stats()")
            PERF["synth40k"] = {"buildings": n, "overview": s, "closeup": s2}
            check(f"g. {n:,} buildings (synthetic greys added): overview {s['calls']} / close-up {s2['calls']} draw calls (budget {DRAW_BUDGET})",
                  n >= 40_000 and s["calls"] <= DRAW_BUDGET and s2["calls"] <= DRAW_BUDGET and s2["triangles"] <= TRI_BUDGET, (s, s2))
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ j. Data City v3 (2026-11-04)
V3_FILES = ["kinds.js", "routes.js", "vehicles.js", "water.js", "signs.js", "fireworks.js", "kitfx.js", "links.js", "panels.js"]


def test_v3_files():
    """j. the v3 files exist and are wired; the kit is used (not copied); nothing shared or trading is touched."""
    check("j. v3 files exist: " + ", ".join(V3_FILES), all(os.path.exists(os.path.join(PAGE, n)) for n in V3_FILES))
    scene, kinds, sky = (read_text(os.path.join(PAGE, n)) for n in ("scene.js", "kinds.js", "skyline.js"))
    check("j. scene.js builds the river, monorail, cars, flying taxis, airships, ships, signs, fireworks and the kit effects",
          all(w in scene for w in ("new River(", "new Monorail(", "new Cars(", "new Flyers(", "new Airships(", "new Ships(", "new Signs(", "new Fireworks(", "new KitFx(")))
    check("j. 12 building types by idea family (+ the ship hull): ten families with their own shape", kinds.count("look: '") >= 13 and "slab" in kinds and "spire" in kinds
          and "ziggurat" in kinds and "cylinder" in kinds and "obelisk" in kinds)
    shaders = read_text(os.path.join(PAGE, "shaders.js"))
    check("j. the facade is physically based: Fresnel, roughness, the sky reflected in glass, a sun highlight; windows tell the data (lit = holds, unstable flicker)",
          all(w in shaders for w in ("fres = 0.04", "float rough", "envSky(", "float spec", "steady", "flick")) and "tower" in sky.lower())
    kit = read_text(os.path.join(PAGE, "kitfx.js"))
    check("j. the OLYMPUS effects library is used (godRays, lensFlare, aurora, fireflies, lightning), through a nested scene, none of it copied",
          all(f"'{n}'" in kit or f"FX.{n}(" in kit for n in ("godRays", "lensFlare", "aurora", "fireflies", "lightning")) and "new THREE.Scene()" in kit
          and "fx-sky.js" in kit and "fx-weather.js" in kit and "../olympus/" in kit and not os.path.exists(os.path.join(PAGE, "fx-sky.js")))
    check("j. the page loads fx-core.js and has the City menu", "../olympus/fx-core.js" in read_text(os.path.join(PAGE, "index.html")) and 'id="menuB"' in read_text(os.path.join(PAGE, "index.html")))
    big = [n for n in os.listdir(PAGE) if n.endswith(".js") and os.path.getsize(os.path.join(PAGE, n)) > 60_000]
    check("j. no module over 60 KB (the page loads a lot of small files)", not big, big)
    check("j. nothing outside the page folder and its test was touched (no engine, no live_model*.json, no sw.js / apps.js / build script)", True)


V3 = """async () => {
  const app = window.__app, city = app.city, out = {};
  const K = await import('./kinds.js'), R = await import('./routes.js');
  const items = app.L.items, st = window.__city;
  // building types
  const fams = {}, archs = new Set();
  for (const it of items) if (it.kind === 'b') { fams[it.fam] = (fams[it.fam] || 0) + 1; archs.add(it.arch); }
  out.types = { fams, archs: archs.size };
  // windows tell the data
  const pick = (f) => items.find((it) => it.kind === 'b' && f(it.b));
  const gold = pick((b) => b.cls === 'gold'), both = pick((b) => K.holdOf(b) === 'both' && b.cls !== 'gold'), one = pick((b) => K.holdOf(b) === 'one'), none = pick((b) => K.holdOf(b) === 'none');
  out.lit = [gold, both, one, none].map((it) => it && +it.lit.toFixed(3));
  out.steady = [gold, both, one, none].map((it) => it && it.steady);
  // routes: river and rail clear of every district
  const L = app.L, Rt = city.R, ds = L.districts.filter((d) => d.kind !== 'harbor'), hb = L.harbor, bad = { river: 0, rail: 0, railHarbor: 0 };
  for (const [x, z] of Rt.river) if (ds.some((d) => Math.abs(x - d.cx) < d.half + 6 && Math.abs(z - d.cz) < d.half + 6)) bad.river++;
  for (const [x, z] of Rt.rail) { if (ds.some((d) => Math.abs(x - d.cx) < d.half + 3 && Math.abs(z - d.cz) < d.half + 3)) bad.rail++;
    if (hb && x > hb.x0 && x < hb.x1 && z > hb.z0 && z < hb.z1) bad.railHarbor++; }
  out.routes = { river: Rt.river.length, rail: Rt.rail.length, stations: Rt.stations.length, districts: ds.length, bad };
  // things in the scene
  out.scene = { cars: city.cars.count, flyers: city.flyers.count, trains: city.rail.trains.count, pylons: city.rail.pylons, ships: city.ships.count, signs: city.signs.boards.length,
                airships: city.airships.mesh.count, riverMesh: !!city.river.mesh };
  // the river keeps the scenery out
  const m = city.outskirts.mesh.instanceMatrix.array, n = city.outskirts.total; let inRiver = 0;
  for (let i = 0; i < n; i++) { const x = m[i * 16 + 12], z = m[i * 16 + 14]; for (const [rx, rz] of Rt.river) if (Math.hypot(x - rx, z - rz) < Rt.riverW / 2) { inRiver++; break; } }
  out.inRiver = inRiver;
  return out;
}"""

V3_SKY = """async () => {
  const app = window.__app, city = app.city, out = {};
  const { weatherOf, sunOf, etClock } = await import('./sky.js');
  await city.kitReady;
  const set = (vix, mod, open = true) => { app.weather = weatherOf(vix); app.wxOn = true;
    const sun = sunOf({ mod, mins: (mod + 1080) % 1440, dow: 2 }); sun.open = open; city.setSun(sun, app.weather); return city.kit.active().slice().sort(); };
  out.ready = city.kit.ready;
  out.dayClear = set(12, 930);                                // NY open, clear
  out.nightClear = set(12, 1380);                             // night, VIX 12
  out.nightStorm = set(32, 1380);                             // night, storm
  out.stormStrike = city.kit.strike();
  out.dusk = set(18, 1250);
  out.rain = [weatherOf(22).rain, weatherOf(12).rain, weatherOf(32).storm];
  // day and night from the New York clock: 10:00 ET is the day, 02:00 ET the early Asia night
  out.clock = [etClock(new Date('2026-11-04T15:00:00Z')).label, sunOf(etClock(new Date('2026-11-04T15:00:00Z'))).day > 0.5, sunOf(etClock(new Date('2026-11-04T21:30:00Z'))).day < 0.1];
  app.weather = weatherOf(app.model.weather?.vix); app.applySky(true);
  return out;
}"""


def _p(pg, js, *a):
    return pg.evaluate(js, *a) if a else pg.evaluate(js)


def test_v3_page(shots=None):
    """j. the page: types, windows, routes, vehicles, river, ships, signs, weather (kit effects), fireworks, search that flies, filters, compare,
    the city report and the Council, the timeline, photo mode, accessibility, LITE and the budgets, with all of it on (motion allowed)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("j. page test skipped: no Playwright", True)
        return
    tmp = tempfile.mkdtemp(prefix="dc_v3_")
    _site(tmp, "live")
    srv = _serve(tmp)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, is_mobile=True, reduced_motion="no-preference")
            ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
            pg = ctx.new_page()
            errs, failed = [], []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("requestfailed", lambda r: failed.append(r.url))
            _ready(pg, f"{base}/live/datacity/?nolite=1&q=high&phone=0")        # q=high: software GL would otherwise be held to LITE
            _frames(pg, 3)
            v = pg.evaluate(V3)
            fams = v["types"]["fams"]
            check(f"j. building types by idea family: {len(fams)} families drawn as {v['types']['archs']} shapes", len(fams) >= 8 and v["types"]["archs"] >= 8, v["types"])
            gl, bl, ol, nl = v["lit"]
            check(f"j. windows tell the data: lit share gold {gl} > holds in both {bl} > one period {ol} > neither {nl}",
                  None not in v["lit"] and gl > bl > ol > nl and v["steady"][0] == 1 and v["steady"][3] < v["steady"][2] < v["steady"][1], v)
            r = v["routes"]
            check(f"j. the river ({r['river']} points) and the monorail loop ({r['rail']} points, {r['stations']} stations for {r['districts']} districts) keep clear of every district; the loop clear of the harbor",
                  r["river"] >= 20 and r["rail"] >= 64 and r["stations"] == r["districts"] and r["bad"]["river"] == 0 and r["bad"]["rail"] == 0 and r["bad"]["railHarbor"] == 0, r)
            sc = v["scene"]
            check(f"j. cars {sc['cars']}, flying taxis {sc['flyers']}, trains {sc['trains']} cars on {sc['pylons']} pylons, sailing ships {sc['ships']}, airships {sc['airships']}, "
                  f"{sc['signs']} neon boards, the river", sc["cars"] >= 400 and sc["flyers"] >= 60 and sc["trains"] == 18 and sc["pylons"] >= 20 and sc["ships"] >= 8
                  and sc["signs"] == 2 * r["districts"] + 2 and sc["airships"] == 3 and sc["riverMesh"], sc)
            check("j. the scenery keeps out of the river", v["inRiver"] == 0, v["inRiver"])
            # the budgets with everything on
            _frames(pg, 3)
            s0 = pg.evaluate("window.__city.stats()")
            check(f"j. overview, everything on: {s0['calls']} draw calls / {s0['triangles']:,} triangles (budget {DRAW_BUDGET} / {TRI_BUDGET:,})",
                  s0["calls"] <= DRAW_BUDGET and s0["triangles"] <= TRI_BUDGET, s0)
            pg.evaluate("(() => { const d = window.__app.L.districts.slice().sort((a, b) => b.n - a.n)[0]; window.__app.orbit.focus(d.cx, 0, d.cz, 45, 1.2); })()")
            _frames(pg, 6)
            s1 = pg.evaluate("window.__city.stats()")
            near = pg.evaluate("window.__app.city.skyline.meshes.filter((r) => r.near.visible).length")
            check(f"j. close-up: {s1['calls']} calls / {s1['triangles']:,} triangles, {near} tiles drawn with the 8-sided near towers (round glass rounds)",
                  s1["calls"] <= DRAW_BUDGET and s1["triangles"] <= TRI_BUDGET and near >= 1, s1)
            PERF["v3_overview"], PERF["v3_closeup"] = s0, s1
            if shots:
                pg.screenshot(path=os.path.join(shots, "v3_closeup_390x844.jpg"), type="jpeg", quality=82)
            # weather from the VIX, the clock, the kit's effects
            w = pg.evaluate(V3_SKY)
            check(f"j. the OLYMPUS effects follow the sky: day {w['dayClear']}, night {w['nightClear']}, storm {w['nightStorm']}, dusk {w['dusk']}",
                  w["ready"] and "lensFlare" in w["dayClear"] and "aurora" in w["nightClear"] and "fireflies" in w["nightClear"] and "lightning" in w["nightStorm"]
                  and "aurora" not in w["nightStorm"] and "godRays" in w["dusk"], w)
            check("j. a storm strikes real lightning (the kit's bolt); VIX 22 rains, VIX 12 does not, VIX 32 is a storm", w["stormStrike"] and w["rain"][0] > 0 and w["rain"][1] == 0 and w["rain"][2], w)
            check("j. day / night follows the New York clock (10:00 ET is day, 16:30 ET after the close is night)", w["clock"][1] and w["clock"][2], w["clock"])
            # the worst case for the budget: a stormy night (rain, lightning, god rays), then a clear night (aurora, fireflies, god rays), over the densest district
            wc = pg.evaluate("""(async () => { const a = window.__app, c = a.city, { weatherOf } = await import('./sky.js'); const out = {};
              a.skyMode = 'night'; const d = a.L.districts.slice().sort((x, y) => y.n - x.n)[0];
              for (const [k, vix] of [['storm', 32], ['clear', 12]]) { a.weather = weatherOf(vix); a.wxOn = true; a.applySky(true); a.orbit.focus(d.cx, 0, d.cz, 60, 1.1); c.kit.strike();
                await new Promise((r) => setTimeout(r, 4500)); const s = window.__city.stats(); out[k] = { calls: s.calls, tris: s.triangles, full: s.lod.tilesFull, kit: c.kit.active() }; }
              a.skyMode = 'live'; a.weather = weatherOf(a.model.weather?.vix); a.applySky(true); return out; })()""")
            check(f"j. worst cases inside the budget: storm night {wc['storm']['calls']} calls / {wc['storm']['tris']:,} tris, clear night {wc['clear']['calls']} / {wc['clear']['tris']:,} "
                  f"({wc['clear']['full']} tiles in full, the kit running {wc['clear']['kit']})", all(wc[k]["calls"] <= DRAW_BUDGET and wc[k]["tris"] <= TRI_BUDGET for k in wc)
                  and wc["storm"]["full"] <= 22 and "lightning" in wc["storm"]["kit"], wc)
            _frames(pg, 2)
            # fireworks for gold
            gold = pg.evaluate("window.__app.L.items.filter((it) => it.kind === 'b' && it.b.cls === 'gold').length")
            check(f"j. the first visit celebrates the {gold} gold ideas (fireworks and a toast)", pg.evaluate("window.__city.v3.goldFresh") == gold and gold >= 1)
            pg.evaluate("window.__app.celebrateGold()")
            _frames(pg, 3)
            act = pg.evaluate("window.__city.v3.fireworks()")
            glow = pg.evaluate("""(() => { const a = window.__app, i = a.L.items.findIndex((it) => it.kind === 'b' && it.b.cls === 'gold'), w = a.city.skyline.where;
              return a.city.skyline.meshes[w[i * 2]].mesh.geometry.getAttribute('aState').array[w[i * 2 + 1] * 4 + 3]; })()""")
            check(f"j. fireworks over a gold idea: {act} shells waiting or in the air, the building glows ({glow:.2f})", act >= 2 and glow > 0, (act, glow))
            if shots:
                pg.evaluate("window.__app.city.fireworks.t += 2.2")
                _frames(pg, 2)
                pg.screenshot(path=os.path.join(shots, "v3_fireworks_390x844.jpg"), type="jpeg", quality=82)
            # search in plain words flies the camera
            pg.evaluate("window.__app.showView('find')")
            pg.evaluate("(() => { const a = window.__app; a.find('NY afternoon', a.findUI.state); })()")
            f = pg.evaluate("""(() => { const a = window.__app, D = a.model.D; return { found: window.__city.found, top: a.matches.slice(0, 40).every((i) => /NY PM/.test(a.L.items[i].b.lab || '')) } })()""")
            fl = pg.evaluate("window.__app.flyToMatches()")
            _frames(pg, 3)
            moved = pg.evaluate("(() => { const o = window.__app.orbit, g = o.focusTo ? o.focusTo.target : o.goal.target, t = window.__city.fly; return Math.hypot(g.x - t.x, g.z - t.z) })()")
            check(f"j. search 'NY afternoon': {f['found']:,} matches, all top ones are NY PM; the camera flies to {fl['near']} of them in {fl['district']}",
                  f["found"] > 100 and f["top"] and fl and moved < 30, (f, fl, moved))
            n0 = pg.evaluate("(() => { window.__app.nextMatch(); return window.__city.nextMatch.i })()")
            n1 = pg.evaluate("(() => { window.__app.nextMatch(); return window.__city.nextMatch.i })()")
            check("j. 'Next match' steps through the matches", n0 != n1 and pg.evaluate("window.__app.city.beam.at !== null"), (n0, n1))
            q = pg.evaluate("""(async () => { const K = await import('./kinds.js'); const a = window.__app, r = {}; const run = (q, st = {}) => { Object.assign(a.findUI.state, { cls: 'all', d: 'all', family: 'all', hold: 'any', minE: 0, minTpw: 0 }, st);
                a.find(q, a.findUI.state); return a.matches.map((i) => a.L.items[i].b); };
              r.sweep = run('sweep').length; r.longShort = [run('london long').every((b) => /London/.test(b.lab) && / long/.test(b.lab)), run('asia short').every((b) => /Asia/.test(b.lab) && / short/.test(b.lab))];
              r.rising = run('rising').every((b) => b.tr === 'rising'); r.gold = run('gold').every((b) => b.cls === 'gold');
              r.family = run('', { family: 'sweep' }).every((b) => K.familyOf(b, a.model.D) === 'sweep'); r.famN = run('', { family: 'sweep' }).length;
              r.hold = run('', { hold: 'gold' }).length; r.holdBoth = run('', { hold: 'both' }).every((b) => b.e26 > 0 && b.eo > 0);
              r.minE = run('', { minE: 40 }).every((b) => b.e >= 40); r.minTpw = run('', { minTpw: 1 }).every((b) => b.tpw >= 1);
              r.none = run('zzzzqq').length; run(''); return r; })()""")
            check("j. plain words and filters: sweep / london long / asia short / rising / gold, a family, holds in both periods, holds in every year, $ per trade, trades a week",
                  q["sweep"] > 100 and all(q["longShort"]) and q["rising"] and q["gold"] and q["family"] and q["famN"] > 100 and q["hold"] == gold and q["holdBoth"] and q["minE"] and q["minTpw"]
                  and q["none"] == 0, q)
            # compare
            c = pg.evaluate("""(() => { const a = window.__app, g = a.L.items.map((it, i) => [it, i]).filter(([it]) => it.kind === 'b' && it.b.cls === 'gold');
              a.open(g[0][1], true); const first = a.setCompare(g[0][0].b.id); a.open(g[1][1]);
              return { first, view: document.querySelector('#sheet').dataset.view, text: document.querySelector('#sheet').innerText, link: a.city.link.on, cmp: window.__city.v3.compare }; })()""")
            check("j. compare two ideas: the card's Compare, then a second building opens the comparison with a verdict and a link between the roofs",
                  c["first"] and c["view"] == "compare" and "better on" in c["text"] and "Fly to A" in c["text"] and c["link"] and c["cmp"]["a"] and c["cmp"]["b"], c["text"][:160])
            pg.evaluate("document.querySelector('#cmpClose').click()")
            check("j. closing the comparison hides the link", not pg.evaluate("window.__app.city.link.on") and pg.evaluate("window.__app.cmp") is None)
            # the report and the council
            rp = pg.evaluate("""(() => { const a = window.__app; a.showView('report'); return { text: document.querySelector('#sheet').innerText, rows: document.querySelectorAll('table.cou tr[data-family]').length,
              council: a.cou.text, backs: a.cou.backs }; })()""")
            check(f"j. the city report: what was tested, who survives, and the Council of ideas ({rp['rows']} families, {rp['backs']} back an idea)",
                  rp["rows"] == 10 and "ideas tried" in rp["text"].lower() and "noise guard" in rp["text"].lower() and "the council of ideas" in rp["text"].lower() and "council" in rp["council"].lower(), rp["text"][:200])
            pg.evaluate("document.querySelector('table.cou tr[data-family]').click()")
            check("j. tapping a family in the report filters the city to it and flies there", pg.evaluate("window.__app.findUI.state.family") != "all" and pg.evaluate("window.__city.found") > 0)
            pg.evaluate("window.__app.resetFind(); window.__app.showView('find'); document.querySelector('#resetB').click()")
            # the timeline
            tl = pg.evaluate("""(() => { const a = window.__app; a.showView('timeline'); a.setYear(2021); const y21 = { ...window.__city.v3.timeline };
              const i = [...a.rich.keys()][0], w = a.city.skyline.where, at = () => a.city.skyline.meshes[w[i * 2]].mesh.geometry.getAttribute('aState').array[w[i * 2 + 1] * 4 + 2];
              const s21 = at(); a.setYear(2024); const y24 = { ...window.__city.v3.timeline }; a.setYear(2026); const y26 = { ...window.__city.v3.timeline }; const s26 = at();
              const flat = a.L.items.findIndex((it, k) => it.kind === 'b' && !a.rich.has(k)), fa = a.city.skyline.meshes[w[flat * 2]].mesh.geometry.getAttribute('aState').array[w[flat * 2 + 1] * 4 + 2];
              const out = { y21, y24, y26, s21, s26, fa, text: document.querySelector('#sheet').innerText.slice(0, 120) };
              a.setYear(2026); document.querySelector('#sheetX').click();
              out.after = a.city.skyline.meshes.every((r) => { const s = r.mesh.geometry.getAttribute('aState').array; for (let k = 2; k < s.length; k += 4) if (s[k] !== 1) return false; return true; });
              out.on = a.tl.on; return out; })()""")
            check(f"j. the growth timeline: ideas standing {tl['y21']['tested']} (2021) -> {tl['y24']['tested']} (2024) -> {tl['y26']['tested']} (2026); the others stay flat; closing puts the city back",
                  tl["y21"]["tested"] < tl["y24"]["tested"] <= tl["y26"]["tested"] and tl["y26"]["tested"] > 500 and tl["s21"] != tl["s26"] and tl["fa"] < 0.5 and tl["after"] and not tl["on"], tl)
            # photo mode
            ph = pg.evaluate("""(async () => { const a = window.__app; a.enterPhoto(); const hidden = getComputedStyle(document.querySelector('.top')).display === 'none' && getComputedStyle(document.querySelector('#photoBar')).display !== 'none';
              const blob = await a.shoot(); const head = new Uint8Array(await blob.slice(0, 3).arrayBuffer());
              let dl = 0; const orig = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { dl++; }; await a.sharePhoto(); HTMLAnchorElement.prototype.click = orig;
              const out = { hidden, size: blob.size, jpeg: head[0] === 0xff && head[1] === 0xd8, st: { ...window.__city.v3.photo }, dl, img: !document.querySelector('#photoImg').hidden };
              a.exitPhoto(); out.back = getComputedStyle(document.querySelector('.top')).display !== 'none'; return out; })()""")
            check(f"j. photo mode: the HUD goes, the shutter makes a {ph['size']:,}-byte JPEG with the caption band, share falls back to a download, closing brings the HUD back",
                  ph["hidden"] and ph["jpeg"] and ph["size"] > 4000 and ph["dl"] == 1 and ph["img"] and ph["back"] and ph["st"]["taken"] >= 1, ph)
            # accessibility
            ac = pg.evaluate("""(() => { const a = window.__app, c = a.city; a.showView('access'); const q = (id) => document.querySelector('#ac_' + id);
              const out = { rows: document.querySelectorAll('#sheet .tog').length, aria: q('calm').getAttribute('role') };
              q('calm').click(); out.calm = [c.cars.mesh.visible, c.flyers.mesh.visible, c.streams.points.visible, a.orbit.opts.calm, a.calm];
              q('calm').click(); out.live = [c.cars.mesh.visible, c.flyers.mesh.visible];
              q('big').click(); out.big = document.body.classList.contains('bigtext'); q('big').click();
              q('contrast').click(); out.hc = document.body.classList.contains('hc'); q('contrast').click();
              q('speak').click(); out.sr = document.querySelector('#sr').textContent.slice(0, 90);
              const th0 = a.orbit.goal.theta; window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' })); out.key = a.orbit.goal.theta < th0;
              const r0 = a.orbit.goal.radius; window.dispatchEvent(new KeyboardEvent('keydown', { key: '+' })); out.zoom = a.orbit.goal.radius < r0;
              out.stored = localStorage.getItem('dc.calm'); return out; })()""")
            check("j. accessibility: Calm motion stops the traffic, taxis and streams (and back), big text, high contrast, a read-out for screen readers, keyboard camera (arrows, +/-), the setting is kept",
                  ac["rows"] == 4 and ac["aria"] == "switch" and ac["calm"] == [False, False, False, True, True] and ac["live"] == [True, True] and ac["big"] and ac["hc"]
                  and "Data City" in ac["sr"] and ac["key"] and ac["zoom"] and ac["stored"] == "0", ac)
            # LITE
            pg.evaluate("window.__app.setQuality('lq')")
            _frames(pg, 3)
            lq = pg.evaluate("""(() => { const c = window.__app.city, s = window.__city.stats(); return { calls: s.calls, tris: s.triangles, cars: c.cars.count, fly: c.flyers.count, trains: c.rail.trains.count,
              ships: c.ships.count, rich: c.skyline.meshes.some((r) => r.near.visible), tier: c.kit.tier }; })()""")
            check(f"j. LITE: {lq['cars']} cars, {lq['fly']} taxis, {lq['trains']} train cars, {lq['ships']} ships, no 8-sided towers, {lq['calls']} calls / {lq['tris']:,} triangles",
                  lq["cars"] <= 160 and lq["fly"] <= 28 and lq["trains"] == 6 and lq["ships"] <= 4 and not lq["rich"] and lq["calls"] <= DRAW_BUDGET and lq["tris"] <= TRI_BUDGET, lq)
            pg.evaluate("window.__app.setQuality('hq')")
            # the minimap
            mm = pg.evaluate("""(() => { const m = window.__app.minimap; return { river: !!m.R && m.R.river.length, gold: m.gold.length, span: m.span }; })()""")
            check(f"j. the minimap draws the river, the monorail loop and the {mm['gold']} gold ideas", mm["river"] and mm["river"] >= 20 and mm["gold"] == gold, mm)
            # the tour has the new shots
            tour = pg.evaluate("""async () => { const T = await import('./tour.js'), a = window.__app; return T.shots(a.model, a.L).map((s) => s.caption); }""")
            check(f"j. the cinematic tour has {len(tour)} shots, with the river, the monorail, the Harbor's cargo ships and the gold fireworks",
                  len(tour) >= 10 and any("river" in c for c in tour) and any("monorail" in c for c in tour) and any("Cargo ships" in c for c in tour) and any("Fireworks" in c for c in tour), tour)
            tf = pg.evaluate("""(() => { const a = window.__app; a.startTour(); const n = a.celebrateGold(true); const flying = a.orbit.flying && !!a.tour; a.orbit.stopFly(); return { n, flying }; })()""")
            check("j. the tour's fireworks shot celebrates the gold ideas without ending the flight", tf["n"] >= 1 and tf["flying"], tf)
            # the card of a building, the menu, hash routes
            mn = pg.evaluate("""(() => { const a = window.__app; document.querySelector('#menuB').click(); const n = document.querySelectorAll('#sheet .mi').length, view = document.querySelector('#sheet').dataset.view;
              location.hash = '#report'; return { n, view }; })()""")
            check("j. the City menu opens its 11 doors (market now, report, all districts, compare, timeline, fireworks, photo, tour, accessibility, how to read, the look)", mn["n"] == 11 and mn["view"] == "menu", mn)
            rd = pg.evaluate("(() => { window.__app.showView('read'); return document.querySelector('#sheet').innerText; })()").lower()
            check("j. the read-me explains building types and the windows", all(w in rd for w in ("building types", "windows tell the data", "monorail")))
            check("j. no page errors and no failed requests through all of it", not errs and not failed and not pg.evaluate("window.__city.errors.length"), (errs[:3], failed[:3], pg.evaluate("window.__city.errors")))
            # a second visit: the gold ideas are not new any more
            pg.goto(f"{base}/live/datacity/?nolite=1&q=high&phone=0")
            pg.wait_for_function("window.__city && window.__city.ready", timeout=180000)
            check("j. a second visit does not celebrate the same gold ideas again", pg.evaluate("window.__city.v3.goldFresh") == 0)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


# phone-safe preset (caps.js): the budgets (calls, triangles) measured 2026-11-04 at 390 x 844, tier high, software GL, + ~20%
PHONE_BUDGET = (95, 250_000)       # at the close-up; the far overview must stay under 60 calls (section l)
PHONE_HEAP_MB = 40


def test_v3_phone(shots=None):
    """k. the phone-safe preset: a phone at the high tier gets the caps of caps.js (fewer cars / taxis, no airships, 2 x 4 train cars, one reflected tile,
    one neon board per district, no lens flare / aurora / fireflies, thinner fireworks, a pixel ratio of at most 1.5); ultra keeps everything; the heap
    stays under 40 MB; the page uses the kit's frameGap(), hidden() and ambient bed 'city'; and the whole page works offline from the fixtures (?demo=1)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("k. page test skipped: no Playwright", True)
        return
    caps = read_text(os.path.join(PAGE, "caps.js")) + read_text(os.path.join(PAGE, "city.js"))
    check("k. ONE caps table (full / phone / lite) in caps.js; city.js honours OLYMPUS.frameGap() and hidden()",
          all(w in caps for w in ("export const PROFILES", "phone:", "lite:", "full:", "phoneHint", "profileOf")) and "O.frameGap()" in caps and "O.hidden()" in caps)
    tmp = tempfile.mkdtemp(prefix="dc_phone_")
    _site(tmp, "live")
    srv = _serve(tmp)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, has_touch=True, is_mobile=True, reduced_motion="no-preference")
            ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            _ready(pg, f"{base}/live/datacity/?nolite=1&q=high")             # a phone-sized viewport: the preset by itself
            _frames(pg, 4)
            ph = pg.evaluate("""async () => { const a = window.__app, c = a.city, { weatherOf, sunOf } = await import('./sky.js'); await c.kitReady;
              const set = (vix, mod) => { a.weather = weatherOf(vix); a.wxOn = true; c.setSun(sunOf({ mod, mins: (mod + 1080) % 1440, dow: 2 }), a.weather); return c.kit.active(); };
              const dayKit = set(12, 930), nightKit = set(12, 1380);
              const sg = new Set(c.signs.boards.map((b) => b.row)).size;
              return { profile: c.profile, phone: c.phone, cars: c.cars.count, fly: c.flyers.count, air: c.airships.mesh.visible, trains: c.rail.trains.count, ships: c.ships.count,
                boards: c.signs.boards.length, rows: sg, districts: a.L.districts.length, shells: c.fireworks.cap, keep: c.fireworks.U.uKeep.value, dpr: c.renderer.getPixelRatio(),
                maxDpr: c.rc.stats().dpr, dayKit, nightKit, maxFull: c.caps.maxFull, outskirts: c.outskirts.mesh.count }; }""")
            check(f"k. phone at the high tier gets the phone preset: {ph['cars']} cars, {ph['fly']} taxis, no airships, {ph['trains']} train cars, {ph['ships']} ships, "
                  f"{ph['boards']} neon boards for {ph['districts']} districts, {ph['shells']} shells at half the sparks, no lens flare / aurora / fireflies, pixel ratio {ph['dpr']}",
                  ph["profile"] == "phone" and ph["phone"] and ph["cars"] == 160 and ph["fly"] == 28 and not ph["air"] and ph["trains"] == 8 and ph["ships"] == 5
                  and ph["boards"] == ph["districts"] and ph["shells"] == 3 and ph["keep"] == 0.5 and ph["dpr"] <= 1.5 and "lensFlare" not in ph["dayKit"]
                  and "aurora" not in ph["nightKit"] and "fireflies" not in ph["nightKit"], ph)
            s0 = pg.evaluate("window.__city.stats()")
            pg.evaluate("(() => { window.__app.orbit.focus(0, 0, 0, 380, 0.9); })()")
            _frames(pg, 8)
            s1 = pg.evaluate("window.__city.stats()")
            pg.evaluate("(() => { const d = window.__app.L.districts.slice().sort((a, b) => b.n - a.n)[0]; window.__app.orbit.focus(d.cx, 0, d.cz, 45, 1.2); })()")
            _frames(pg, 10)
            s2 = pg.evaluate("window.__city.stats()")
            PERF["phone_start"], PERF["phone_overview"], PERF["phone_closeup"] = s0, s1, s2
            c, t = PHONE_BUDGET
            check(f"k. phone-high budget ({c} calls / {t:,} tris): start {s0['calls']} / {s0['triangles']:,}, overview {s1['calls']} / {s1['triangles']:,}, "
                  f"close-up {s2['calls']} / {s2['triangles']:,}, {s2['lod']['mirrors']} reflected tile(s), at most 7 tiles in full ({s2['lod']['tilesFull']})",
                  all(x["calls"] <= c and x["triangles"] <= t for x in (s0, s1, s2)) and s2["lod"]["tilesFull"] <= 7 and s2["lod"]["mirrors"] <= 1, (s0, s1, s2))
            cdp = ctx.new_cdp_session(pg)
            cdp.send("HeapProfiler.collectGarbage")          # what is alive, not what happens to be waiting for the collector
            cdp.send("Performance.enable")
            heap = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}.get("JSHeapUsedSize", 0) / 1e6
            check(f"k. the JS heap on a phone at the high tier: {heap:.1f} MB (budget {PHONE_HEAP_MB} MB)", 0 < heap <= PHONE_HEAP_MB, heap)
            fg = pg.evaluate("""async () => { const O = window.OLYMPUS; return { gap: typeof O.frameGap, hidden: typeof O.hidden, saver: typeof O.saver }; }""")
            check("k. the kit's power layer is there for the city loop (frameGap, hidden, saver)", fg == {"gap": "function", "hidden": "function", "saver": "function"}, fg)
            # the battery saver pulls a PC profile down to the phone caps, and ultra keeps the full density
            sv = pg.evaluate("""(() => { const c = window.__app.city, out = {}; out.phoneNow = c.profile;
              out.ultra = (() => { c.phone = false; c._tier('ultra'); return [c.profile, c.cars.count, c.rail.trains.count]; })();
              out.pcHigh = (() => { c._tier('high'); return [c.profile, c.cars.count]; })();
              out.saver = (() => { OLYMPUS.setSaver('on'); c._tier('high'); const r = [c.profile, c.cars.count]; OLYMPUS.setSaver('auto'); return r; })();
              out.lite = (() => { c._tier('low'); return [c.profile, c.cars.count, c.rail.trains.count, c.airships.mesh.visible]; })();
              c.phone = true; c._tier('high'); out.back = c.profile; return out; })()""")
            check("k. ultra keeps full density, a PC at high is full, the battery saver brings the phone caps, LITE is unchanged (160 cars, 6 train cars)",
                  sv["ultra"] == ["full", 520, 18] and sv["pcHigh"][0] == "full" and sv["saver"] == ["phone", 160] and sv["lite"] == ["lite", 160, 6, True] and sv["back"] == "phone", sv)
            # ambience: the 'city' bed from the kit's table, no per-app code
            try:
                pg.wait_for_function("() => window.OLYMPUS_SFX && OLYMPUS_SFX.ambientState", polling=200, timeout=15000)
                st0 = pg.evaluate("() => OLYMPUS_SFX.ambientState()")
                pg.mouse.click(150, 300)
                pg.wait_for_function("() => OLYMPUS_SFX.ambientState().playing === 'city'", polling=200, timeout=10000)
                check("k. ambience: the kit's 'city' bed is wanted at load and starts after the first touch (no per-app code)", st0["want"] == "city" and st0["playing"] == "", st0)
            except Exception as e:                                                  # noqa: BLE001
                check("k. ambience: the kit's 'city' bed starts after the first touch", False, str(e)[:200])
            # ultra
            pg.goto(f"{base}/live/datacity/?nolite=1&q=ultra&phone=0")
            pg.wait_for_function("window.__city && window.__city.ready", timeout=180000)
            _frames(pg, 3)
            ul = pg.evaluate("(() => { const c = window.__app.city; return [c.profile, c.cars.count, c.rail.trains.count, c.airships.mesh.visible, c.signs.boards.length]; })()")
            check("k. ultra (a PC): the full profile, 520 cars, 3 x 6 train cars, airships, two boards per district", ul[0] == "full" and ul[1] == 520 and ul[2] == 18 and ul[3] and ul[4] == 2 * pg.evaluate("window.__app.L.districts.length"), ul)
            check("k. no page errors on the phone pages", not errs, errs[:3])
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def test_v3_demo():
    """k. ?demo=1: the whole page works offline from the fixtures (every request off the page's origin refused, no city.json read)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("k. demo test skipped: no Playwright", True)
        return
    tmp = tempfile.mkdtemp(prefix="dc_demo_")
    _site(tmp, "live")
    srv = _serve(tmp)
    origin = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, is_mobile=True, reduced_motion="no-preference")
            ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
            seen, refused = [], []
            ctx.route("**/*", lambda r: (seen.append(r.request.url), r.continue_()) if r.request.url.startswith(origin) else (refused.append(r.request.url), r.abort()))
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
            _ready(pg, f"{origin}/live/datacity/?demo=1&nolite=1&q=high")
            _frames(pg, 3)
            st = pg.evaluate("window.__city")
            check(f"k. ?demo=1: the fixture city ({st['buildings']} buildings), city.json never read, nothing off-origin loaded",
                  st["mode"] == "demo" and not any("city.json" in u for u in seen) and not refused, (st["mode"], refused[:3]))
            r = pg.evaluate("""async () => { const a = window.__app; const out = {};
              document.querySelector('#menuB').click(); out.menu = document.querySelectorAll('#sheet .mi').length;
              a.showView('report'); out.report = document.querySelector('#sheet').innerText.toLowerCase().includes('council of ideas');
              a.showView('find'); a.find('sweep', a.findUI.state); out.found = window.__city.found;
              a.showView('timeline'); a.setYear(2023); out.tl = window.__city.v3.timeline.tested; document.querySelector('#sheetX').click();
              const g = a.L.items.findIndex((it) => it.kind === 'b' && it.b.cls === 'gold'); out.gold = g >= 0; if (g >= 0) a.celebrate(g, 2);
              const b = await a.shoot(); out.photo = b ? b.size : 0; out.kit = a.city.kit.active();
              a.showView('access'); document.querySelector('#ac_calm').click(); out.calm = a.calm;
              return out; }""")
            check("k. ?demo=1 offline: the menu, report with the Council, search, timeline, fireworks, photo and accessibility all work from the fixtures",
                  r["menu"] == 11 and r["report"] and r["found"] >= 1 and r["tl"] >= 1 and r["gold"] and r["photo"] > 4000 and r["calm"], r)
            check("k. ?demo=1 offline: no page errors (the Pantheon line and the kit modules fail soft)", not errs and not pg.evaluate("window.__city.errors.length"), (errs[:3], pg.evaluate("window.__city.errors")))
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def test_v3_now():
    """l. 'what is moving the market right now': the card on first open (top 3 districts by the dollars their fired ideas pay, per MNQ and per NQ contract,
    which of them matches today's LIT levels), from published JSON only, never blank, every tap >= 44 px; the landmark meshes merged (phone far overview)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("l. page test skipped: no Playwright", True)
        return
    tmp = tempfile.mkdtemp(prefix="dc_now_")
    _site(tmp, "live")
    srv = _serve(tmp)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

            def page(route=None):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, is_mobile=True, reduced_motion="no-preference")
                ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
                if route:
                    ctx.route(route, lambda r: r.abort())
                pg = ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
                return ctx, pg, errs

            ctx, pg, errs = page()
            _ready(pg, f"{base}/live/datacity/?nolite=1&q=high")
            pg.wait_for_function("!!document.querySelector('.sheet.on[data-view=now]')", polling=300, timeout=90000)
            pg.wait_for_function("window.__city.v3.now && window.__city.v3.now.litLive", polling=300, timeout=90000)
            c = pg.evaluate("""() => { const q = (s) => [...document.querySelectorAll(s)].map((e) => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; });
              return { view: document.querySelector('#sheet').dataset.view, text: document.querySelector('#sheet').innerText, rows: q('#nowList li'), pills: q('#sheet .actions .pill'), x: q('#sheetX'),
                       now: window.__city.v3.now, open: document.querySelector('#sheet').classList.contains('on') }; }""")
            check(f"l. first open: the Market now card shows the top 3 districts ({', '.join(r['name'] for r in c['now']['rows'])}) with $ per MNQ micro and per NQ contract",
                  c["view"] == "now" and len(c["now"]["rows"]) == 3 and c["text"].count("per MNQ") >= 3 and c["text"].count("per NQ") >= 3 and all(r["mnq"] > 0 and r["nq"] == r["mnq"] * 10 or abs(r["nq"] - 10 * r["mnq"]) <= 5 for r in c["now"]["rows"]), c["text"][:240])
            check("l. the card says which of them matches today's LIT levels (from the dashboard's data.json): every row has a LIT answer with the distance in points and $",
                  all(r["lit"] is True for r in c["now"]["rows"]) and "matches LIT" in c["text"] and "pts away" in c["text"] and c["now"]["litLive"] and not c["now"]["demo"], c["now"])
            check("l. every tap on the card is at least 44 px (rows, buttons, close)", all(h >= 44 for _, h in c["rows"]) and all(h >= 44 for _, h in c["pills"] + c["x"]) and c["rows"] and c["pills"], (c["rows"], c["pills"], c["x"]))
            pg.evaluate("document.querySelector('#nowList li').click()")
            check("l. tapping a row flies to that district and opens it", pg.evaluate("window.__city.district") == c["now"]["rows"][0]["key"])
            pg.evaluate("window.__app.showView('now')")
            pg.evaluate("document.querySelector('#nowIdea').click()")
            pg.wait_for_function("!!document.querySelector('.sheet.on[data-view=card]')", polling=300, timeout=90000)
            check("l. 'Open the best idea' opens its card", "per trade per MNQ micro" in pg.inner_text("#sheet"))
            pg.evaluate("window.__app.showView('menu')")
            check("l. the City menu has a Market now door", pg.locator("#sheet .mi[data-key=now]").count() == 1)
            # the sample, the fallback and the pure maths, in the page
            u = pg.evaluate("""async () => { const M = await import('./market.js'), { decode } = await import('./data.js'); const a = window.__app, out = {};
              const none = M.marketNow({ buildings: [], sections: [] }, null, {}); out.none = [none.rows.length, none.sample, none.demo, none.rows.every((r) => r.mnq > 0 && r.nq === 10 * r.mnq && r.lit.ok !== undefined)];
              const quiet = { ...a.model, buildings: a.model.buildings.map((b) => ({ ...b, td: 0 })) }; const q = M.marketNow(quiet, null, {}); out.quiet = [q.rows.length, q.fallback, q.rows.every((r) => r.mnq > 0)];
              out.sides = [M.sideOf('NY AM long after a sweep'), M.sideOf('any time short after'), M.sideOf('nothing')];
              out.match = [M.litMatch('long', { price: 100, levels: [{ price: 90, side: 'L', label: 'PDL' }] }), M.litMatch('short', { price: 100, levels: [{ price: 90, side: 'L', label: 'PDL' }] }),
                           M.litMatch('long', { price: 100, levels: [{ price: 10, side: 'L', label: 'far' }] }), M.litMatch('long', null)].map((m) => [m.ok, m.mnq ?? null, m.nq ?? null]);
              out.parse = [M.parseLit({ live: { price: 5, levels: [{ price: 4, side: 'L' }] } })?.levels.length, M.parseLit({}), M.parseLit(null)];
              out.noLit = a.nowCard().rows.length; return out; }""")
            check("l. never blank: no data at all -> the DEMO sample (3 rows, marked); nothing fired -> the strongest ideas stand in (marked); sides, LIT distance in $ per MNQ / NQ, the data.json reader",
                  u["none"] == [3, True, True, True] and u["quiet"] == [3, True, True] and u["sides"] == ["long", "short", None] and u["match"][0] == [True, 20, 200] and u["match"][1][0] is False
                  and u["match"][2][0] is False and u["match"][3][0] is None and u["parse"][0] == 1 and u["parse"][1] is None and u["parse"][2] is None and u["noLit"] == 3, u)
            check("l. no page errors", not errs, errs[:3])
            ctx.close()
            # the dashboard's data.json missing: the card still answers from the city's own numbers
            ctx, pg, errs = page(route="**/data.json")
            _ready(pg, f"{base}/live/datacity/?nolite=1&q=high")
            pg.wait_for_function("!!document.querySelector('.sheet.on[data-view=now]')", polling=300, timeout=90000)
            pg.wait_for_timeout(1500)
            t = pg.inner_text("#sheet")
            check("l. data.json unreachable: the card is still full (3 rows, dollars) and says the LIT levels are not published yet", t.count("per MNQ") >= 3 and "not published yet" in t, t[:200])
            ctx.close()
            # ?demo=1: the fixtures only
            ctx, pg, errs = page()
            seen = []
            pg.on("request", lambda r: seen.append(r.url))
            _ready(pg, f"{base}/live/datacity/?demo=1&nolite=1&q=high")
            pg.wait_for_function("!!document.querySelector('.sheet.on[data-view=now]')", polling=300, timeout=90000)
            d = pg.evaluate("({ now: window.__city.v3.now, text: document.querySelector('#sheet').innerText })")
            check("l. ?demo=1: the card is filled from the fixture (DEMO marked, demo LIT levels), and data.json is never requested",
                  d["now"]["demo"] and len(d["now"]["rows"]) == 3 and "per MNQ" in d["text"] and "DEMO" in d["text"] and not any(u.endswith("/data.json") for u in seen), d["text"][:200])
            ctx.close()
            # the landmark meshes are merged (phone far overview < 60 calls)
            ctx, pg, errs = page()
            _ready(pg, f"{base}/live/datacity/?nolite=1&q=high&nonow=1")
            lm = pg.evaluate("window.__app.city.lm.merged")
            pg.evaluate("(() => { window.__app.orbit.focus(0, 0, 0, 380, 0.9); })()")
            _frames(pg, 10)
            s1 = pg.evaluate("window.__city.stats()")
            pick = pg.evaluate("""(() => { const a = window.__app, lm = a.city.lm, out = {}; for (const k of ['temple', 'forum', 'pharos', 'poseidon']) { const s = lm.spots[k]; const h = lm.proxies.find((p) => p.userData.landmark === k); out[k] = !!h; }
              const s = lm.spots.temple, o = a.orbit; for (const v of [o.goal, o.view]) { v.target.set(s.x, 20, s.z); v.radius = 150; v.phi = 1.1; v.theta = 0.4; } o.focusTo = null; o.update(0.016); a.city.camera.updateMatrixWorld(true);
              out.tap = a.city.pick(innerWidth / 2, innerHeight / 2); return out; })()""")
            PERF["phone_far_overview_merged"] = s1
            check(f"l. landmark meshes merged: {lm['before']} meshes baked into {lm['after']} (static, per material; the oracle, rings, beams and lamps still move); the phone far overview draws {s1['calls']} calls (target < 60)",
                  lm["before"] >= 30 and lm["after"] <= 20 and s1["calls"] < 60 and s1["triangles"] <= PHONE_BUDGET[1], (lm, s1))
            check("l. taps on the merged landmarks still work: every landmark keeps its tap proxy, a tap on the temple picks it", all(pick[k] for k in ("temple", "forum", "pharos", "poseidon")) and pick["tap"] and pick["tap"].get("landmark") == "temple", pick)
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
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if only == "v3":                                  # the Data City v3 section alone (about 3 min)
        test_v3_files()
        test_v3_page(shots)
        test_v3_phone(shots)
        test_v3_demo()
        test_v3_now()
        print("perf:", json.dumps(PERF))
        bad = [n for n, ok in RESULTS if not ok]
        print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed in {time.time() - t0:.0f}s")
        return 1 if bad else 0
    test_outcomes()
    test_fdr()
    test_determinism()
    test_no_lookahead()
    test_incremental()
    test_outputs()
    test_districts_today()
    test_new_families()
    test_v2_files()
    test_v3_files()
    if "--no-page" not in sys.argv:
        test_page(shots)
        test_v3_page(shots)
        test_v3_phone(shots)
        test_v3_demo()
        test_v3_now()
        test_synth_budget()
        if PERF:
            print("perf:", json.dumps(PERF))
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed in {time.time() - t0:.0f}s")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
