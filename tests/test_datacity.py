"""OLYMPUS DATA CITY (tools/datacity, tools/web_public/datacity): the data machine and its 3D page.

    python -X utf8 -m tests.test_datacity            # everything (~6-10 min; the page part needs Playwright + Chromium)
    python -X utf8 -m tests.test_datacity --no-page  # the engine only (~2 min)
    DATACITY_SHOTS=<dir> python -X utf8 -m tests.test_datacity   # also screenshots

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
    pre = (ev["slot"] < 39) | (ev["slot"] >= 96)                       # before 09:45 ET (slot 39 = 09:45)
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
           ok: it.every((x) => x.h > 0 && Number.isFinite(x.h) && x.lit >= 0 && x.lit <= 1), tiles: L.tiles.length, blocks: L.blocks.length }; }"""


def _site(tmp, mode, plugin=False):
    site = os.path.join(tmp, mode, "datacity")
    shutil.copytree(PAGE, site)
    # the site layout around it: Jarvis's three.js and fonts (../jarvis/) and the OLYMPUS kit (../olympus/)
    os.makedirs(os.path.join(tmp, mode, "jarvis"))
    for f in ["three.module.min.js"] + glob.glob(os.path.join(os.path.dirname(PAGE), "jarvis", "*.woff2")):
        shutil.copy(os.path.join(os.path.dirname(PAGE), "jarvis", os.path.basename(f)), os.path.join(tmp, mode, "jarvis"))
    shutil.copytree(os.path.join(os.path.dirname(PAGE), "olympus"), os.path.join(tmp, mode, "olympus"))
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
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

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
                        check(f"g. {mode}: layout places everything once, no two buildings overlap, districts apart",
                              lay["n"] == lay["want"] and not lay["clash"] and not lay["over"] and not lay["inTower"] and lay["ok"], lay)
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
    pg.evaluate("window.__app.setQuality('lq')")
    _frames(pg, 2)
    s = pg.evaluate("window.__city.stats()")
    check(f"g. live: LITE drops the reflections and the pixel ratio ({s['calls']} calls)", s["lod"]["mirrors"] == 0 and s["pixelRatio"] <= 1.5, s)
    pg.evaluate("window.__app.setQuality('hq')")


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
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
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
    test_districts_today()
    if "--no-page" not in sys.argv:
        test_page(shots)
        test_synth_budget()
        if PERF:
            print("perf:", json.dumps(PERF))
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed in {time.time() - t0:.0f}s")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
