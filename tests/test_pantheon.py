"""PANTHEON (tools/pantheon/, tools/web_public/pantheon/, docs/PANTHEON.md, 2026-11-03): the free data gods.

  a. the parsers, on the recorded fixtures (tests/fixtures/pantheon/) and on hand-made edge cases
  b. the store: fixtures never touch the network; network -> cache -> local fallback; a failed source is "missing"
  c. the statistics: 5-year percentiles, rolling z-scores use only the past, no look-ahead alignment (publication lag),
     votes clipped, the relation verdicts (signal / inverse / context), event-day moves, run-length intervals
  d. the council: thresholds, the gauge, too few voices = silent, the history needs 3 voices
  e. the build on the fixtures: pantheon.json schema, ARTEMIS display only, the Jarvis card contract, the states.json schema
     (the Data City contract in docs/PANTHEON.md), a broken source leaves the rest standing; the committed outputs
  f. the wiring: the CRONOS task, the site build tuple, sw.js OTHER_APPS, the OLYMPUS kit entry
  g. the page in Playwright Chromium at 390 x 844: no errors, no sideways scroll, the orb corner free, a tap on a pillar
     opens its card, the council panel and its honest table, #god/<key> routes, the demo fixture, ?lite=1, reduced motion

    python -X utf8 -m tests.test_pantheon            (everything; g needs Playwright's Chromium)
    python -X utf8 -m tests.test_pantheon fast       (a-f: no browser)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.pantheon import build as B  # noqa: E402
from tools.pantheon import council as C  # noqa: E402
from tools.pantheon import gods as G  # noqa: E402
from tools.pantheon import sources as SRC  # noqa: E402
from tools.pantheon import stats as S  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "pantheon")
PAGE = os.path.join(ROOT, "tools", "web_public", "pantheon")
NOW = pd.Timestamp("2026-11-03 16:00", tz="UTC").to_pydatetime()
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def rd(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def no_net(url):
    raise AssertionError("the network was used: " + url)


# ------------------------------------------------------------------------------------------------------------ a
def part_a():
    for src in SRC.SOURCES:
        try:
            d = src.parser(rd(src.fixture))
            ok = d is not None and len(d) > 0
        except Exception as e:  # noqa: BLE001
            ok, d = False, e
        check(f"a. {src.id}: its recorded fixture parses", ok, d)
    s = SRC.parse_fred("observation_date,DGS10\n2026-01-02,4.10\n2026-01-05,.\n2026-01-06,4.20\n")
    check("a. FRED: '.' (no value) is dropped, dates parsed, sorted", list(s.round(2)) == [4.1, 4.2] and s.index[-1] == pd.Timestamp("2026-01-06"))
    s = SRC.parse_fred("DATE,X\n2020-01-01,1\n")
    check("a. FRED: the older DATE header also parses", len(s) == 1)
    k = SRC.parse_cboe(rd("cboe_SKEW.csv"))
    check("a. CBOE: a two-column file (SKEW) gives its close", k.iloc[-1] > 90 and k.index.is_monotonic_increasing)
    v = SRC.parse_cboe(rd("cboe_VIX.csv"))
    check("a. CBOE: VIX closes are positive, mm/dd/yyyy dates", (v > 0).all() and v.index[-1] >= pd.Timestamp("2026-10-01"))
    cot = SRC.parse_cftc_tff(rd("cftc_tff_nq.json"))
    check("a. CFTC: one row per Tuesday, net and % of OI derived",
          cot.index.is_unique and {"am_net", "lev_net", "am_net_pct", "lev_net_pct"} <= set(cot.columns)
          and abs(cot["am_net"].iloc[-1] - (cot["am_long"].iloc[-1] - cot["am_short"].iloc[-1])) < 1e-9
          and all(d.weekday() == 1 for d in cot.index[-10:]), cot.tail(2))
    sq = SRC.parse_squeeze(rd("squeeze_dix.csv"))
    check("a. SqueezeMetrics: dix in 0..1, gex in dollars", sq["dix"].between(0.2, 0.7).all() and sq["gex"].abs().max() > 1e8)
    tr = SRC.parse_treasury(rd("treasury_curve.csv"))
    check("a. Treasury: the tenors in order, newest last", list(tr.columns)[:2] == ["1 Mo", "2 Mo"] and tr.index.is_monotonic_increasing)
    ff = SRC.parse_ff_week(rd("ff_week.json"))
    check("a. ForexFactory: only US high-impact rows, times in ET", len(ff) > 0 and ff["when"].dt.tz is None
          and all(isinstance(x, str) and x for x in ff["event"]))
    ev = SRC.parse_events(rd("events.csv"))
    check("a. events.csv: only high-impact rows", len(ev) > 20 and not ev["event"].str.contains("Unemployment Claims").any())
    for bad, fn in (("<html>nope</html>", SRC.parse_cboe), ("{}", SRC.parse_cftc_tff), ("[]", SRC.parse_cftc_tff), ("a\n1\n", SRC.parse_fred)):
        try:
            fn(bad)
            check(f"a. {fn.__name__} refuses junk", False)
        except Exception:  # noqa: BLE001
            check(f"a. {fn.__name__} refuses junk", True)
    check("a. every source is key-less and free (no api_key / token in any URL)",
          all("api_key" not in s.url and "token" not in s.url.lower() for s in SRC.SOURCES))
    check("a. never Yahoo", all("yahoo" not in (s.url + s.name).lower() for s in SRC.SOURCES))


# ------------------------------------------------------------------------------------------------------------ b
def part_b(tmp):
    st = SRC.Store(fixtures=FIX, opener=no_net)
    st.prefetch()
    check("b. fixtures: every source read from its fixture, the network never used",
          all(v["from"] == "fixture" for v in st.log.values()) and len(st.log) == len(SRC.SOURCES), st.log)
    cache = os.path.join(tmp, "cache")
    calls = []

    def fake(url):
        calls.append(url)
        if "DGS10" in url:
            return rd("fred_DGS10.csv").encode()
        raise OSError("offline")
    st = SRC.Store(cache=cache, opener=fake)
    s = st.get("fred:DGS10")
    check("b. network: a good download is used and written to the cache",
          st.log["fred:DGS10"]["from"] == "network" and os.path.exists(os.path.join(cache, "fred_DGS10.csv")) and len(s) > 100)
    st2 = SRC.Store(cache=cache, opener=lambda u: (_ for _ in ()).throw(OSError("down")))
    st2.get("fred:DGS10")
    check("b. network down: the last good download (cache) is used", st2.log["fred:DGS10"]["from"] == "cache")
    st3 = SRC.Store(cache=os.path.join(tmp, "empty"), opener=lambda u: (_ for _ in ()).throw(OSError("down")))
    vix = st3.get("cboe:VIX")
    check("b. no network, no cache: CBOE VIX falls back to the repo's data/VIX_1d.csv", st3.log["cboe:VIX"]["from"] == "local" and len(vix) > 1000)
    check("b. ... and a source with no fallback is 'missing' with the error kept",
          st3.get("fred:WALCL") is None and st3.log["fred:WALCL"]["from"] == "missing" and "down" in st3.log["fred:WALCL"]["error"])
    st4 = SRC.Store(offline=True, cache=os.path.join(tmp, "empty"), opener=no_net)
    st4.get("squeeze:dix")
    check("b. --offline never calls the network (GEX from data/GEX_1d.csv)", st4.log["squeeze:dix"]["from"] == "local")
    check("b. the curated calendar is the repo's own file", SRC.Store(offline=True, opener=no_net).get("local:events") is not None)


# ------------------------------------------------------------------------------------------------------------ c
def part_c():
    idx = pd.bdate_range("2019-01-01", periods=2000)
    s = pd.Series(np.arange(2000, dtype=float), index=idx)
    p, yrs = S.percentile(s)
    check("c. percentile: a new high is the 100th percentile over 5 years", p == 100.0 and 4.9 <= yrs <= 5.0, (p, yrs))
    p2, _ = S.percentile(pd.Series([1.0, 5, 3, 2, 4] * 10, index=pd.bdate_range("2026-01-01", periods=50)))
    check("c. percentile: the last value 4 of a 1..5 mix is the 80th (<= is counted)", p2 == 80.0, p2)
    rnd = pd.Series(np.random.default_rng(1).normal(size=1500), index=pd.bdate_range("2020-01-01", periods=1500))
    z1 = S.rolling_z(rnd)
    rnd2 = rnd.copy()
    rnd2.iloc[1200:] += 50
    z2 = S.rolling_z(rnd2)
    check("c. rolling z: changing the future never changes a past z-score", np.allclose(z1.iloc[:1200].dropna(), z2.iloc[:1200].dropna()))
    check("c. rolling z: no value before ~1 year of history", z1.iloc[:249].isna().all() and z1.iloc[260:].notna().all())
    v = S.vote(pd.Series([-10.0, -1, 0, 1, 10]), -1)
    check("c. vote: direction x z / 2, clipped to -1..+1", list(v) == [1.0, 0.5, -0.0, -0.5, -1.0], list(v))
    obs = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2026-03-02", "2026-03-03", "2026-03-04"]))   # Mon, Tue, Wed
    cot = pd.Series([7.0], index=pd.to_datetime(["2026-03-03"]))                                           # Tuesday positions
    days = pd.bdate_range("2026-03-02", "2026-03-09")
    k0, k1, k3 = S.known_on(obs, days, 0), S.known_on(obs, days, 1), S.known_on(cot, pd.bdate_range("2026-03-02", "2026-03-10"), 3)
    check("c. no look-ahead, lag 0: Monday's value counts from Tuesday's session", np.isnan(k0.iloc[0]) and k0["2026-03-03"] == 1.0 and k0["2026-03-05"] == 3.0)
    check("c. lag 1 (FRED): Monday's value counts from Wednesday's session", np.isnan(k1["2026-03-03"]) and k1["2026-03-04"] == 1.0 and k1["2026-03-06"] == 3.0)
    check("c. lag 3 (CFTC: Tuesday positions out Friday): first used on Monday's session",
          k3[:"2026-03-06"].isna().all() and k3["2026-03-09"] == 7.0, k3.to_dict())
    ret = pd.Series(np.random.default_rng(2).normal(0, 0.01, 1300), index=pd.bdate_range("2021-11-01", periods=1300))
    good = S.relation(np.sign(ret) * 0.8, ret)
    check("c. relation: a vote that knows the sign is a signal in both periods", good["holds"] and all(r["edge"] > 40 for r in good["periods"]))
    inv = S.relation(-np.sign(ret) * 0.8, ret)
    check("c. relation: the opposite vote is 'inverse', never a signal", inv["inverse"] and not inv["holds"])
    noise = S.relation(pd.Series(np.random.default_rng(3).uniform(-1, 1, 1300), index=ret.index), ret)
    check("c. relation: a random vote is 'context, not a signal'", noise["verdict"] == "context, not a signal" and not noise["holds"])
    half = ret.copy()
    half_sig = np.sign(ret) * 0.8
    half_sig[half_sig.index >= "2026-01-01"] *= -1                                    # right in 2021-25, wrong in 2026
    hs = S.relation(half_sig, half)
    check("c. relation: working only in 2021-25 is NOT a signal (both periods required)", not hs["holds"], hs["periods"])
    flag = pd.Series(False, index=ret.index)
    flag.iloc[::10] = True
    big = ret.where(~flag, ret * 3)
    am = S.abs_move(flag, big)
    check("c. event-day moves: 3x bigger moves on flagged days show ~3x", am["holds"] and all(2.0 < r["ratio"] < 4.5 for r in am["periods"]), am)
    iv = S.intervals(pd.Series([False, True, True, False, True], index=pd.bdate_range("2026-01-05", periods=5)))
    check("c. intervals: run-length ranges, inclusive", iv == [["2026-01-06", "2026-01-07"], ["2026-01-09", "2026-01-09"]], iv)
    nq = S.nq_returns()
    check("c. NQ returns: the TradingView NQ1! daily export, 2021-10 -> 2026-10, no huge roll jumps",
          nq.index[0] < pd.Timestamp("2021-11-01") and nq.index[-1] >= pd.Timestamp("2026-10-01") and nq.abs().max() < 0.12, nq.abs().max())


# ------------------------------------------------------------------------------------------------------------ d
def part_d():
    check("d. labels: >= +0.20 risk-on, <= -0.20 risk-off, else mixed",
          (C.label(0.2), C.label(-0.2), C.label(0.19), C.label(None)) == ("RISK-ON", "RISK-OFF", "MIXED", "SILENT"))
    v = C.verdict({"a": ("A", 1.0), "b": ("B", 1.0), "c": ("C", -0.5), "d": ("D", 0.1)})
    check("d. verdict: mean of the votes -> gauge 0-100, who leans where in plain words",
          v["score"] == 0.4 and v["gauge"] == 70 and v["label"] == "RISK-ON" and v["on"] == ["A", "B"] and v["off"] == ["C"]
          and v["neutral"] == ["D"] and "risk-on" in v["text"], v)
    s = C.verdict({"a": ("A", 1.0), "b": ("B", None)})
    check("d. fewer than 3 voices: SILENT, no gauge", s["label"] == "SILENT" and s["gauge"] is None)
    idx = pd.bdate_range("2026-01-01", periods=3)
    h = C.history({"a": pd.Series([1.0, 1, np.nan], index=idx), "b": pd.Series([0.0, np.nan, np.nan], index=idx),
                   "c": pd.Series([-1.0, 1, 1], index=idx)})
    check("d. history: the mean per session only with 3+ voices", h.iloc[0] == 0.0 and h.iloc[1:].isna().all(), h.tolist())


# ------------------------------------------------------------------------------------------------------------ e
STATE_KEYS = {"id", "god", "label", "from", "now", "days_on", "on"}


def states_ok(st):
    bad = []
    if st.get("v") != 1 or st.get("app") != "pantheon":
        bad.append("v/app")
    first, last = st["sessions"]["first"], st["sessions"]["last"]
    ids = [x["id"] for x in st["states"]]
    if len(ids) != len(set(ids)):
        bad.append("duplicate ids")
    for x in st["states"]:
        if set(x) != STATE_KEYS or not x["id"].startswith(x["god"] + ".") or x["god"] not in st["gods"]:
            bad.append(x.get("id"))
            continue
        if x["from"] is not None and not (first <= x["from"] <= last) or x["on"] and x["from"] and x["on"][0][0] < x["from"]:
            bad.append(x["id"] + " from")
        prev = None
        for a, b in x["on"]:
            if not (first <= a <= b <= last) or (prev and a <= prev):
                bad.append(x["id"] + " intervals")
                break
            prev = b
        n = sum(len(pd.bdate_range(a, b)) for a, b in x["on"])
        if n != x["days_on"]:
            bad.append(x["id"] + " days_on")
        if x["now"] != bool(x["on"] and x["on"][-1][1] == last):
            bad.append(x["id"] + " now")
    return bad


def part_e(tmp):
    from tools.cronos import fresh
    store = SRC.Store(fixtures=FIX, opener=no_net)
    doc, st = B.build(store, now=NOW)
    check("e. build on fixtures: 8 gods, every one with data", len(doc["gods"]) == 8 and all(g["ok"] for g in doc["gods"]),
          [(g["key"], g["ok"]) for g in doc["gods"]])
    names = [g["name"] for g in doc["gods"]]
    check("e. the gods' names are new (not Hermes, Fates, Tyche, Prometheus, Daphne, Oracle, Odeon, Mind, Cronos, Atlas)",
          not set(names) & {"HERMES", "FATES", "TYCHE", "PROMETHEUS", "DAPHNE", "ORACLE", "ODEON", "MIND", "CRONOS", "ATLAS"})
    need = {"key", "name", "glyph", "title", "why", "color", "council", "futures", "reading", "change", "pct", "meaning",
            "lean", "spark", "stats", "honesty", "sources", "states_now", "subs"}
    check("e. every god card has its reading, change, percentile, meaning, sparkline and honest check",
          all(need <= set(g) and g["meaning"] and g["honesty"] and (len(g["spark"]) >= 20 or g["key"] == "athena") for g in doc["gods"]),
          [k for g in doc["gods"] for k in need - set(g)])
    art = next(g for g in doc["gods"] if g["key"] == "artemis")
    check("e. ARTEMIS (crypto) is labelled not-futures and never votes", not art["futures"] and not art["council"]
          and art["vote"] is None and "Not futures" in G.BY_KEY["artemis"].why and "NOT futures" in json.dumps(art["subs"]))
    check("e. ATHENA (calendar) never votes", next(g for g in doc["gods"] if g["key"] == "athena")["vote"] is None)
    cv = doc["council"]
    check("e. council: label, gauge 0-100, voices = the council gods, plain text",
          cv["label"] in ("RISK-ON", "RISK-OFF", "MIXED") and 0 <= cv["gauge"] <= 100 and cv["voices"] == 6 and cv["text"]
          and cv["members"] == ["POSEIDON", "ZEUS", "ARES", "DEMETER", "HELIOS", "NYX"], cv)
    check("e. honest: 'context, not a signal' unless a god holds in both periods",
          all(("Weak signal" in g["honesty"]) == bool(g["stats"]["holds"]) for g in doc["gods"]))
    check("e. relation table: the council + every god", [r["god"] for r in doc["relation"]][:1] == ["COUNCIL"] and len(doc["relation"]) == 9)
    check("e. sources listed with where they came from; skipped sources say why",
          len(doc["sources"]) == len(SRC.SOURCES) and all(s["why"] for s in doc["skipped"]))
    check("e. pantheon.json is small (< 80 KB)", len(json.dumps(doc)) < 80_000, len(json.dumps(doc)))
    card = B.jarvis_card(doc)
    check("e. jarvis.json passes the Jarvis contract (docs/JARVIS_APPS.md)", not fresh.valid_card(card), fresh.valid_card(card))
    check("e. jarvis.json: theme, stale_after 259200, opens #council", card["theme"] == B.THEME and card["stale_after"] == 259200
          and card["open"] == "#council" and card["name"] == "Pantheon")
    bad = states_ok(st)
    check("e. states.json: the documented schema (ids god.name, sorted inclusive intervals, days_on, now)", not bad, bad[:5])
    check("e. states.json: every god but none has states; Mon-Fri from 2021-11-01",
          {x["god"] for x in st["states"]} == {g.key for g in G.GODS} and st["sessions"]["first"] == "2021-11-01")
    check("e. states.json: next session = the business day after the build", st["sessions"]["last"] == "2026-11-04")
    check("e. states.json says the no-look-ahead rule", "D-1" in st["rule"])
    # a broken source: the god goes offline, the rest stand
    os.makedirs(os.path.join(tmp, "fx"), exist_ok=True)
    for f in os.listdir(FIX):
        if not f.startswith("fred_DTWEXBGS"):
            shutil.copy(os.path.join(FIX, f), os.path.join(tmp, "fx", f))
    d2, s2 = B.build(SRC.Store(fixtures=os.path.join(tmp, "fx"), opener=no_net), now=NOW)
    dm = next(g for g in d2["gods"] if g["key"] == "helios")
    check("e. a missing source: its god is offline, the other 7 and the council (5 voices) still stand",
          not dm["ok"] and dm["lean"] == "offline" and sum(g["ok"] for g in d2["gods"]) == 7 and d2["council"]["voices"] == 5
          and not states_ok(s2), dm)
    check("e. the card says how many gods are up when some are down", "7/8" in B.jarvis_card(d2)["status"]["label"]
          and B.jarvis_card(d2)["status"]["level"] == "ok", B.jarvis_card(d2)["status"])
    out = os.path.join(tmp, "out")
    sizes = B.write(doc, st, research=None, web=None, out=out)
    check("e. write(): pantheon.json, states.json, jarvis.json into --out", sorted(os.listdir(out)) == ["jarvis.json", "pantheon.json", "states.json"]
          and len(sizes) == 3)
    # the committed outputs
    for rel in ("research/pantheon/pantheon.json", "research/pantheon/states.json", "tools/web_public/pantheon/pantheon.json",
                "tools/web_public/pantheon/jarvis.json", "tools/web_public/pantheon/fixture.json"):
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                obj = json.load(fh)
            ok = isinstance(obj, dict) and obj.get("v") == 1
        except (OSError, ValueError):
            ok, obj = False, None
        check(f"e. committed {rel} is valid", ok)
    with open(os.path.join(ROOT, "research", "pantheon", "states.json"), encoding="utf-8") as fh:
        bad = states_ok(json.load(fh))
    check("e. the committed states.json keeps the schema", not bad, bad[:5])
    with open(os.path.join(PAGE, "fixture.json"), encoding="utf-8") as fh:
        check("e. the demo fixture is marked demo", json.load(fh).get("demo") is True)
    with open(os.path.join(PAGE, "jarvis.json"), encoding="utf-8") as fh:
        check("e. the page's jarvis.json passes the contract", not fresh.valid_card(json.load(fh)))


# ------------------------------------------------------------------------------------------------------------ f
def part_f():
    from tools.cronos import registry, run
    t = registry.get("pantheon")
    check("f. CRONOS: pantheon is a nightly task with a runner and its three files (jarvis.json last)",
          t.cadence == "nightly" and "pantheon" in registry.GROUPS["nightly"] and "pantheon" in run.RUNNERS
          and t.files[-1] == "jarvis.json" and "states.json" in t.files and not t.heavy)
    with open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8") as fh:
        b = fh.read()
    check("f. the site build publishes tools/web_public/pantheon/", bool(re.search(r'for app in \([^)]*"pantheon"[^)]*\):', b)))
    with open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8") as fh:
        check("f. the dashboard's service worker leaves pantheon/ alone (OTHER_APPS)", "'pantheon/'" in fh.read())
    with open(os.path.join(ROOT, "tools", "web_public", "olympus", "olympus.js"), encoding="utf-8") as fh:
        check("f. the OLYMPUS kit knows Pantheon (veil name, glyph, colour)", "pantheon: ['Pantheon'" in fh.read())
    with open(os.path.join(PAGE, "index.html"), encoding="utf-8") as fh:
        h = fh.read()
    check("f. the page uses the shared kit and Jarvis's three.js", "../olympus/olympus.css" in h and 'data-app="pantheon"' in h
          and "viewport-fit=cover" in h)
    with open(os.path.join(PAGE, "pantheon.js"), encoding="utf-8") as fh:
        js = fh.read()
    check("f. pantheon.js: three.js from ../jarvis/, O.track, the hidden-tab guard, auto LITE only when nobody chose",
          "../jarvis/three.module.min.js" in js and "O?.track(this.renderer)" in js and "O.hidden()" in js and "this.chosen" in js)
    with open(os.path.join(ROOT, "docs", "PANTHEON.md"), encoding="utf-8") as fh:
        doc = fh.read()
    check("f. docs/PANTHEON.md documents the gods and the states.json format", "states.json" in doc and all(g.name in doc for g in G.GODS))


# ------------------------------------------------------------------------------------------------------------ g
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _site(tmp, name, with_data):
    base = os.path.join(tmp, name)
    shutil.copytree(PAGE, os.path.join(base, "pantheon"))
    os.makedirs(os.path.join(base, "jarvis"))
    for f in ("three.module.min.js", "orbitron.woff2", "rajdhani-400.woff2", "rajdhani-500.woff2", "rajdhani-600.woff2",
              "rajdhani-700.woff2", "icon-192.png"):
        if os.path.exists(os.path.join(ROOT, "tools", "web_public", "jarvis", f)):
            shutil.copy(os.path.join(ROOT, "tools", "web_public", "jarvis", f), os.path.join(base, "jarvis", f))
    shutil.copytree(os.path.join(ROOT, "tools", "web_public", "olympus"), os.path.join(base, "olympus"))
    from tests.olympus_money_kit import link_assets
    link_assets(base)                                 # the built site's assets/ (the kit's sounds, ui.ogg ...): no 404 on the first tap
    if not with_data:
        for f in ("pantheon.json", "jarvis.json"):
            os.remove(os.path.join(base, "pantheon", f))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=base))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/pantheon/"


def _orb_hits(p):
    return p.evaluate("""() => {
      const W = innerWidth, H = innerHeight, box = {l: W - 80, t: H - 160, r: W, b: H};
      const strip = document.getElementById('strip').getBoundingClientRect();
      return [...document.querySelectorAll('button, input, a:not(.oly-home), .card:not([hidden]), .strip')].filter((e) => {
        let r = e.getBoundingClientRect(); if (!r.width || !r.height || e.closest('[hidden]')) return false;
        if (e.closest('.strip') && e.id !== 'strip') r = {left: Math.max(r.left, strip.left), right: Math.min(r.right, strip.right),
          top: r.top, bottom: r.bottom};                                 // chips scrolled past the strip's edge are clipped there
        if (r.right <= r.left) return false;
        return r.right > box.l && r.left < box.r && r.bottom > box.t && r.top < box.b; }).map((e) => e.id || e.className || e.tagName); }""")


def _open(br, url, errs, reduced=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                         reduced_motion="reduce" if reduced else "no-preference")
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
    p.on("requestfailed", lambda r: errs.append("requestfailed: " + r.url))
    if "q=" not in url:                      # software GPU: pin the render core's cheapest tier ('off': straight draw); part h checks the real tiers
        head, _, frag = url.partition("#")
        url = head + ("&" if "?" in head else "?") + "q=off" + ("#" + frag if frag else "")
    p.goto(url)
    p.wait_for_function("window.__pantheon && window.__pantheon.ready", timeout=90000)
    p.wait_for_timeout(700)
    return ctx, p


def part_g(tmp):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("g. Playwright is installed", False)
        return
    srv1, url = _site(tmp, "site1", True)
    srv2, url_demo = _site(tmp, "site2", False)
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            errs = []
            ctx, p = _open(br, url, errs)
            check("g. loads pantheon.json (not the demo) at 390 x 844", p.evaluate("window.__pantheon.demo") is False and not p.is_visible("#demo"))
            check("g. 3D hall is up (WebGL), the veil lifted", p.evaluate("window.__pantheon.fps") >= 0 and p.evaluate("!!document.querySelector('canvas#hall')")
                  and p.is_hidden("#nogl"))
            check("g. no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check("g. the bottom-right 80 x 160 px stays free for Jarvis's orb", not _orb_hits(p), _orb_hits(p))
            hud = p.inner_text("#c-label")
            check("g. the HUD shows the council verdict", hud in ("RISK-ON", "RISK-OFF", "MIXED"), hud)
            check("g. one chip per god in the strip", p.evaluate("document.querySelectorAll('.god').length") == 8)
            pt = p.evaluate("window.__pantheon.screenOf('zeus')")
            p.mouse.click(pt["x"], pt["y"])
            p.wait_for_timeout(500)
            body = p.inner_text("#card-b") if p.is_visible("#card") else ""
            check("g. a tap on ZEUS's pillar opens ZEUS's card", p.is_visible("#card") and p.inner_text("#card-h") == "ZEUS", p.inner_text("#card-h"))
            check("g. the card: reading, percentile, meaning, the honest NQ table, the curve, the source",
                  all(s in body for s in ("percentile", "NQ", "Against NQ futures", "Treasury curve", "Source", "Corr")), body[:300])
            check("g. the card stays clear of the orb corner", not _orb_hits(p), _orb_hits(p))
            check("g. the hall turns to the chosen god", p.evaluate("window.__pantheon.sel") == "zeus")
            p.click("#cardX")
            p.click(".god[data-key='artemis']")
            p.wait_for_timeout(300)
            check("g. ARTEMIS's card says NOT FUTURES DATA", "not futures data" in p.inner_text("#card-b").lower())
            p.click("#councilBtn")
            p.wait_for_timeout(300)
            cb = p.inner_text("#council-b") if p.is_visible("#council") else ""
            check("g. the council panel: gauge, votes, the honest table, sources, skipped",
                  all(s in cb for s in ("The votes", "Honest check", "Corr", "Edge", "Sources tonight", "Skipped", "context")), cb[:300])
            check("g. the council panel fits (no sideways scroll inside the card)",
                  p.evaluate("(() => { const c = document.getElementById('council'); return c.scrollWidth <= c.clientWidth + 1; })()"))
            o = p.evaluate("window.__pantheon.screenOf('council')")
            p.click("#councilX")
            p.mouse.click(o["x"], o["y"])
            p.wait_for_timeout(300)
            check("g. a tap on the orb opens the council", p.is_visible("#council"))
            ctx.close()
            check("g. no page errors, console errors or failed requests", not errs, errs[:5])

            errs = []
            ctx, p = _open(br, url + "#god/nyx", errs)
            check("g. #god/nyx opens NYX's card", p.is_visible("#card") and p.inner_text("#card-h") == "NYX")
            ctx.close()
            errs = []
            ctx, p = _open(br, url + "#council", errs)
            check("g. #council (the Jarvis card's link) opens the council", p.is_visible("#council"))
            ctx.close()
            errs2 = []
            ctx, p = _open(br, url_demo, errs2)
            check("g. no pantheon.json: the demo fixture loads, marked DEMO DATA", p.evaluate("window.__pantheon.demo") is True and p.is_visible("#demo"))
            ctx.close()
            bad = [e for e in errs2 if "pantheon.json" not in e and "jarvis.json" not in e and "404" not in e]
            check("g. the demo runs without errors (only the missing pantheon.json 404)", not bad, bad[:5])
            errs3 = []
            ctx, p = _open(br, url + "?lite=1", errs3)
            check("g. ?lite=1 forces LITE", p.evaluate("window.__pantheon.lite") is True and not errs3, errs3[:3])
            ctx.close()
            errs4 = []
            ctx, p = _open(br, url, errs4, reduced=True)
            y0 = p.evaluate("window.__pantheon.yaw")
            p.wait_for_timeout(1500)
            check("g. reduced motion: the hall stays still (no idle turn)", abs(p.evaluate("window.__pantheon.yaw") - y0) < 1e-6)
            p.click(".god[data-key='ares']")
            p.wait_for_timeout(200)
            check("g. reduced motion: cards still open, no errors", p.is_visible("#card") and not errs4, errs4[:3])
            ctx.close()
            # 2026-11-03: the OLYMPUS render core (statues, marble, bloom) and the Council's regime verdict history
            errs5 = []
            ctx, p = _open(br, url + "?q=low", errs5)
            check("h. on the render core: LITE draws scene + finish (FXAA), no errors", p.evaluate("window.__pantheon.core") == ["scene", "finish"] and not errs5,
                  (p.evaluate("window.__pantheon.core"), errs5[:3]))
            hist = p.evaluate("window.__pantheon.history")
            check("h. the Council chamber carries the verdict history ring (one block per reading)", hist and len(hist["cells"]) >= 8 and hist["streak"]["n"] >= 1, hist and len(hist["cells"]))
            p.click("#councilBtn")
            p.wait_for_timeout(300)
            check("h. the council card shows the verdict history: a tick per reading, shares, the current streak and flips",
                  p.evaluate("document.querySelectorAll('#council-b .vh i').length") == len(hist["cells"]) and "Verdict history" in p.inner_text("#council-b")
                  and "flip" in p.inner_text("#council-b .vh-sum") and "now " in p.inner_text("#council-b .vh-sum"), p.inner_text("#council-b")[:200])
            vh = p.evaluate("import('./pantheoncore.js').then((m) => m.verdictHistory({ council: { spark: [0.3, 0.1, -0.5, -0.5, 0.25] } }))")
            check("h. verdictHistory: the build's own bands (risk-on >= +0.20, risk-off <= -0.20), counts, streak, flips",
                  vh["counts"] == {"RISK-ON": 2, "MIXED": 1, "RISK-OFF": 2} and vh["streak"] == {"label": "RISK-ON", "n": 1} and vh["flips"] == 3, vh)
            ctx.close()
            errs6 = []
            ctx, p = _open(br, url + "?q=high", errs6)
            check("h. on HD: scene + bloom + finish, no errors", p.evaluate("window.__pantheon.core") == ["scene", "bloom", "finish"] and not errs6, errs6[:3])
            ctx.close()
            br.close()
    finally:
        srv1.shutdown()
        srv2.shutdown()


# ------------------------------------------------------------------------------------------------------------ i (2026-11-04)
PLUS_JS = r"""
import fs from 'node:fs';
const D = '__PAGE__/';
const P = await import(D + 'pantheonplus.js');
const d = JSON.parse(fs.readFileSync(D + 'pantheon.json', 'utf8')), sets = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), out = {};
out.sets = sets.map((s) => { const g = { gods: s.map(([k, v]) => ({ key: k, council: true, vote: v })) }; return P.whatIf(g, {}); });
const real = P.whatIf(d, {}); out.real = [real.score, real.gauge, real.label, real.voices, d.council.score, d.council.gauge, d.council.label, d.council.voices];
out.override = [P.whatIf(d, { zeus: -1 }).label, P.whatIf(d, { zeus: null }).voices, P.whatIf(d, { zeus: null, ares: null, nyx: null, poseidon: null }).label, P.whatIf(d, { zeus: 5 }).score >= P.whatIf(d, { zeus: 1 }).score];
const runs = P.regimes(d); out.runs = { n: runs.length, sum: runs.reduce((a, r) => a + r.n, 0), spark: d.council.spark.length, first: runs[0].label, adjacent: runs.every((r, i) => !i || runs[i - 1].label !== r.label) };
out.flip = [P.flipCheck(d, null).flipped, P.flipCheck(d, { label: d.council.label }).flipped, P.flipCheck(d, { label: 'RISK-ON' }).flipped, P.flipCheck(d, { label: 'RISK-ON' }).from];
const note = P.councilNote(d); out.note = { lines: note.lines.length, max: Math.max(...note.lines.map((l) => l.length)), first: note.lines[0], title: note.title, text: note.text === note.lines.join('\n') };
const mem = {}, st = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); } };
const r1 = P.remember(d, st); const r2 = P.remember({ ...d, council: { ...d.council, label: 'RISK-ON' } }, st); const r3 = P.remember({ ...d, council: { ...d.council, label: 'RISK-ON' } }, st);
out.remember = [r1.flip.flipped, r2.flip.flipped, r2.flip.from, r2.flip.to, r2.flips.length, r3.flip.flipped, r3.flips.length, Object.keys(mem).sort()];
mem['pantheon.last'] = '{junk'; out.junk = P.remember(d, st).flip.flipped;
console.log(JSON.stringify(out));
"""


def part_i(tmp):
    """The Council's what-if sliders, regime runs, the flip memory and the daily note: pure functions in node, checked against the build's own rule (tools/pantheon/council.py)."""
    import random
    import subprocess
    node = shutil.which("node")
    if not node:
        check("i. node is available for pantheonplus.js", False)
        return
    rnd = random.Random(7)
    keys = ["a", "b", "c", "d", "e", "f"]
    sets = []
    for _ in range(60):
        k = rnd.randint(0, 6)
        sets.append([[x, None if i >= k else round(rnd.uniform(-1, 1), 3)] for i, x in enumerate(keys[:rnd.randint(2, 6)])] if rnd.random() < 0.5 else [[x, round(rnd.uniform(-1, 1), 3)] for x in keys[:rnd.randint(3, 6)]])
    sf = os.path.join(tmp, "sets.json")
    json.dump(sets, open(sf, "w"))
    f = os.path.join(tmp, "plus.mjs")
    open(f, "w", encoding="utf-8").write(PLUS_JS.replace("__PAGE__", PAGE.replace(os.sep, "/")))
    r = subprocess.run([node, f, sf], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("i. pantheonplus.js runs in node", False, (r.stdout + r.stderr)[-500:])
        return
    bad = []
    for st, js in zip(sets, o["sets"]):
        py = C.verdict({k: (k, v) for k, v in st})
        if (py["score"], py["gauge"], py["label"]) != (js["score"], js["gauge"], js["label"]):
            bad.append((st, py["score"], js["score"], py["label"], js["label"]))
    check("i. 'what if': the page's rule gives the same score, gauge and verdict as the build's own council.verdict() on 60 random vote sets (including too few voices = SILENT)", not bad, bad[:2])
    check("i. 'what if' on the real votes reproduces pantheon.json's own verdict exactly", o["real"][:4] == o["real"][4:], o["real"])
    check("i. 'what if': an override changes the verdict, a god can sit out (5 voices left), four sitting out = SILENT, votes are clipped to -1..+1",
          o["override"][0] in ("RISK-OFF", "MIXED") and o["override"][1] == 5 and o["override"][2] == "SILENT" and o["override"][3], o["override"])
    rr = o["runs"]
    check("i. the regime timeline: runs of one verdict add up to every reading, neighbours differ, newest first", rr["sum"] == rr["spark"] and rr["adjacent"] and rr["n"] >= 2, rr)
    check("i. the flip check: nothing to compare with = no flip, same verdict = no flip, a different one = a flip with from / to", o["flip"] == [False, False, True, "RISK-ON"], o["flip"])
    nt = o["note"]
    check("i. the daily Council note for Jarvis: a title with the date, 3-4 lines, each at most 120 characters, the text is the lines", nt["title"].startswith("Council note") and 3 <= nt["lines"] <= 4 and nt["max"] <= 120 and nt["first"].startswith("Council 2026-") and nt["text"], nt)
    rm = o["remember"]
    check("i. this phone remembers the last verdict ('pantheon.last') and the flips ('pantheon.flips', newest first, kept to 12), nothing else; a damaged key is just forgotten",
          rm[0] is False and rm[1] is True and rm[2] == "MIXED" and rm[3] == "RISK-ON" and rm[4] == 1 and rm[5] is False and rm[6] == 1 and rm[7] == ["pantheon.flips", "pantheon.last"] and o["junk"] is False, rm)


def part_j(tmp):
    """The Council page's new parts in the browser: a god's history chart, the note, the what-if sliders, the timeline, the flip banner, the effects."""
    from playwright.sync_api import sync_playwright
    srv, url = _site(tmp, "site_j", True)
    d = json.load(open(os.path.join(PAGE, "pantheon.json"), encoding="utf-8"))
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            errs = []
            ctx, p = _open(br, url + "?q=off", errs)
            p.evaluate("window.__pantheon.open('zeus')")
            p.wait_for_selector("#card-b .gchart svg")
            p.locator("#card-b .gchart svg").scroll_into_view_if_needed()
            readout = p.inner_text("#card-b .greadout")
            box = p.evaluate("(() => { const r = document.querySelector('#card-b .gchart svg').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
            p.mouse.move(box[0] + box[2] * 0.25, box[1] + box[3] / 2)
            p.mouse.down()
            p.mouse.move(box[0] + box[2] * 0.3, box[1] + box[3] / 2, steps=3)
            p.mouse.up()
            after = p.inner_text("#card-b .greadout")
            check("j. a god's history chart: low / high marked, a finger-scrub readout ('Reading k of N ... % vs now') and the percentile",
                  "percentile" in readout and "Reading" in after and "vs now" in after and p.evaluate("document.querySelector('#card-b .gchart .gdot').hasAttribute('hidden')") is False, (readout, after))
            check("j. every god with a history gets the chart (7 of 8; ATHENA is a calendar and says so)",
                  all(p.evaluate(f"window.__pantheon.open('{g['key']}') || document.querySelectorAll('#card-b .gchart').length") == (1 if len(g.get('spark') or []) >= 3 else 0) for g in d["gods"] if g["ok"]))
            p.evaluate("window.__pantheon.council()")
            p.wait_for_selector("#cn-if input[type=range]")
            n = p.evaluate("document.querySelectorAll('#cn-if input[type=range]').length")
            note = p.inner_text("#cn-note")
            check(f"j. the Council panel: today's note (copy, show on Jarvis), {n} vote sliders, the verdict timeline", "Council note" in note and p.query_selector("#cn-copy") is not None and n == 6 and p.evaluate("document.querySelectorAll('#cn-tl .tl li').length") >= 2)
            lab0 = p.evaluate("document.getElementById('if-out').dataset.label")
            p.evaluate("(() => { const s = document.querySelector('#cn-if input[data-god=zeus]'); s.value = -90; s.dispatchEvent(new Event('input', { bubbles: true })); })()")
            r1 = p.evaluate("[document.getElementById('if-out').dataset.label, +document.getElementById('if-out').dataset.gauge, window.__pantheon.preview]")
            votes = {g["key"]: g["vote"] for g in d["gods"] if g["council"] and g.get("vote") is not None}
            votes["zeus"] = -0.9
            py = C.verdict({k: (k, v) for k, v in votes.items()})
            check(f"j. moving ZEUS to -0.90 re-rules the Council exactly as the build would ({r1[0]} {r1[1]}/100), the orb takes the pretend colour",
                  lab0 == d["council"]["label"] and r1[0] == py["label"] and r1[1] == py["gauge"] and r1[2] == py["label"], (lab0, r1, py["label"], py["gauge"]))
            p.click("#if-on")
            on = p.evaluate("document.getElementById('if-out').dataset.label")
            p.click("#if-off")
            off = p.evaluate("document.getElementById('if-out').dataset.label")
            p.click("#if-reset")
            back = p.evaluate("[document.getElementById('if-out').dataset.label, +document.getElementById('if-out').dataset.gauge]")
            check("j. All risk-on = RISK-ON, All risk-off = RISK-OFF, Reset = today's verdict again", on == "RISK-ON" and off == "RISK-OFF" and back == [d["council"]["label"], d["council"]["gauge"]], (on, off, back))
            for k in ("zeus", "ares", "nyx", "poseidon"):
                p.click(f"#cn-if [data-sit={k}]")
            check("j. sitting four gods out leaves 2 voices: the Council falls silent ('needs at least 3 voices')", p.evaluate("document.getElementById('if-out').dataset.label") == "SILENT" and "at least 3" in p.inner_text("#if-out"))
            p.click("#if-reset")
            p.click("#councilX")
            check("j. closing the Council gives the orb its real colour back", p.evaluate("window.__pantheon.preview") is None)
            check("j. no console errors on the Council page", not errs, errs[:3])
            keys = p.evaluate("Object.keys(localStorage)")
            check("j. this phone stores only 'pantheon.last' and 'pantheon.flips'", sorted(keys) == ["pantheon.flips", "pantheon.last"], keys)
            ctx.close()
            # the flip banner
            errs2 = []
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            ctx.add_init_script("try { localStorage.setItem('pantheon.last', JSON.stringify({ label: 'RISK-ON', gauge: 70 })); } catch (e) {}")
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errs2.append(str(e)))
            p2.goto(url + "?q=off")
            p2.wait_for_function("window.__pantheon && window.__pantheon.ready", timeout=30000)
            p2.wait_for_timeout(500)
            txt = p2.inner_text("#flip") if p2.is_visible("#flip") else ""
            check("j. the Council changed its mind since the last visit: a banner says 'RISK-ON to " + d["council"]["label"] + "' and can be dismissed",
                  f"RISK-ON to {d['council']['label']}" in txt and p2.evaluate("window.__pantheon.flip.flipped") is True, txt)
            p2.click("#flip-x")
            check("j. the banner goes away and the flip is in the log (shown on the timeline)", p2.is_hidden("#flip"))
            p2.evaluate("window.__pantheon.council()")
            p2.wait_for_selector("#cn-tl")
            check("j. the timeline lists the flips seen on this phone", "RISK-ON to " + d["council"]["label"] in p2.inner_text("#cn-tl"), p2.inner_text("#cn-tl")[-160:])
            ctx.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            p3 = ctx.new_page()
            p3.goto(url + "?q=off")
            p3.wait_for_function("window.__pantheon && window.__pantheon.ready", timeout=30000)
            p3.wait_for_timeout(500)
            check("j. a first visit (nothing remembered) shows no banner", p3.is_hidden("#flip"))
            ctx.close()
            # the effects on a GPU tier
            errs4 = []
            ctx, p4 = _open(br, url + "?q=high", errs4)
            p4.wait_for_function("window.__pantheon.fx && window.__pantheon.fx.length >= 2", timeout=90000)
            fx = p4.evaluate("window.__pantheon.fx")
            check(f"j. the hall has the OLYMPUS effects on HD (light shafts onto the Council orb, dust, fireflies): {fx}", "godRays" in fx and "fireflies" in fx and not errs4, (fx, errs4[:2]))
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def part_k(tmp):
    """MY DESK (2026-11-04): event risk against the 02:00-15:30 window, the gods this phone follows (and who changed their mind), the edge meter, freshness, Copy."""
    from playwright.sync_api import sync_playwright
    srv, url = _site(tmp, "site_k", True)
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            errs = []
            ctx, p = _open(br, url + "?q=off", errs)
            r = p.evaluate("""async () => {
              const D = window.__pantheon.DESK, NOW = Date.UTC(2026, 10, 4, 17, 0);                     // Wed 4 Nov 2026 12:00 New York (EST)
              const d = { t: NOW / 1000 - 3600, council: { label: 'Neutral', gauge: 50, stats: { periods: [{ period: '5y', n: 400, corr: 0.02, hit: 51, chance: 50, calls: 200 }, { period: '2026', n: 200, corr: 0.3, hit: 60, chance: 50, calls: 100 }] } },
                sources: [], gods: [
                { key: 'athena', name: 'Athena', title: 'Calendar', color: '#fff', ok: true, lean: 'neutral', asof: '2026-11-04', extra: { upcoming: [
                  { event: 'ISM services', when: 'Wed Nov 04 14:00' }, { event: 'Fed minutes', when: 'Wed Nov 04 16:30' }, { event: 'Jobs report', when: 'Fri Nov 06 08:30' }, { event: 'Old news', when: 'Wed Nov 04 08:15' }] } },
                { key: 'zeus', name: 'Zeus', title: 'Rates', color: '#0ff', ok: true, lean: 'risk-on', vote: 0.4, asof: '2026-10-20', reading: { text: 'Yields fall' } }] };
              const er = D.eventRisk(d, NOW), w1 = D.watchlist(d, ['zeus'], { zeus: 'risk-off' }), w0 = D.watchlist(d, [], null), em = D.edgeMeter(d), fr = D.freshness(d, NOW), line = D.deskLine(d, NOW, ['zeus']);
              return { ev: er.events.map((e) => [e.event, e.inside, e.today, e.left]), todayIn: er.todayIn.length, level: er.level, line: er.line, flip: w1.flips.map((x) => x.key), flipLine: w1.line, none: w0.line, noWatchFlips: w0.flips.length,
                em: em.rows.map((x) => x.inside), noise: em.noise, fresh: fr.rows.map((x) => [x.key, x.level]), built: fr.builtLabel, dl: line,
                empty: [D.eventRisk({ gods: [] }, NOW).events.length, D.watchlist({ gods: [] }, null, null).rows.length, D.edgeMeter({}).rows.length, D.freshness({}, NOW).rows.length, D.deskLine({}, NOW, []).startsWith('Pantheon:')],
                win: D.WINDOW, leans: D.leansOf(d) }; }""")
            check("k. event risk: the past event is dropped, today's ISM at 14:00 is INSIDE the window (in 2 h), the Fed minutes at 16:30 are outside, a warning for today's inside event",
                  [e[0] for e in r["ev"]] == ["ISM services", "Fed minutes", "Jobs report"] and r["ev"][0][1] is True and r["ev"][1][1] is False and r["ev"][2][1] is True and r["ev"][0][3] == "2 h"
                  and r["todayIn"] == 1 and r["level"] == "warn" and "inside the trading window" in r["line"] and r["win"] == [120, 930], r)
            check("k. my gods: only a followed god can have changed its mind (Zeus risk-off to risk-on), the line says so; following none says how to start",
                  r["flip"] == ["zeus"] and "risk-off to risk-on" in r["flipLine"] and r["noWatchFlips"] == 0 and "Follow" in r["none"], r)
            check("k. edge meter: the 5-year reading is inside the noise band, the 2026 one is outside it; so the Council is not called a coin-toss beater",
                  r["em"] == [True, False] and r["noise"] is False, r["em"])
            check("k. freshness: Athena is current, Zeus (14 days old against a 1-day delay) is flagged; the build is 'under 2 hours ago'",
                  r["fresh"] == [["athena", "ok"], ["zeus", "bad"]] and r["built"] == "under 2 hours ago", r["fresh"])
            check("k. the desk line starts 'Pantheon:' and ends 'context, not a signal'; empty data = every function answers",
                  r["dl"].startswith("Pantheon: Council Neutral 50/100") and r["dl"].endswith("context, not a signal") and r["empty"] == [0, 0, 0, 0, True], (r["dl"], r["empty"]))
            check("k. a first visit is not 'flipped'; the leans are kept for the next one", r["leans"] == {"athena": "neutral", "zeus": "risk-on"})
            # the page
            h = p.evaluate("(() => { const b = document.getElementById('deskBtn').getBoundingClientRect(), c = document.getElementById('councilBtn').getBoundingClientRect(); return [b.width, b.height, c.height]; })()")
            check("k. the Desk button sits beside the Council button, at least 44 px", h[0] >= 43.5 and h[1] >= 43.5, h)
            p.click("#deskBtn")
            p.wait_for_selector("#desk-b section.plus")
            check("k. tapping Desk opens a card with six sections (day cost, events, my gods, edge meter, freshness, copy) and the hash is #desk",
                  p.locator("#desk-b section.plus").count() == 6 and p.is_visible("#desk") and p.evaluate("location.hash") == "#desk" and len(p.inner_text("#desk-b").strip()) > 200)
            fol = p.locator("#desk-b .fol")
            n = fol.count()
            small = [b for b in (fol.nth(i).bounding_box() for i in range(n)) if b["height"] < 43.5 or b["width"] < 43.5]
            check("k. one Follow button per god, each at least 44 x 44", n == len(json.load(open(os.path.join(PAGE, "pantheon.json"), encoding="utf-8"))["gods"]) and not small, (n, small))
            fol.first.click()
            check("k. Follow marks the god (aria-pressed, 'Following') and keeps it on this phone only (localStorage pantheon.watch)",
                  fol.first.get_attribute("aria-pressed") == "true" and fol.first.inner_text() == "Following" and len(json.loads(p.evaluate("localStorage.getItem('pantheon.watch')"))) == 1)
            fol.first.click()
            check("k. tapping again unfollows", fol.first.get_attribute("aria-pressed") == "false" and json.loads(p.evaluate("localStorage.getItem('pantheon.watch')")) == [])
            cb = p.locator("#dk-copy").bounding_box()
            p.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=url.split("/pantheon")[0])
            p.click("#dk-copy")
            p.wait_for_timeout(400)
            check("k. Copy my desk line: at least 44 px, the message holds the same 'Pantheon:' sentence", cb["height"] >= 43.5 and (p.get_attribute("#dk-msg", "data-line") or "").startswith("Pantheon:") and len(p.inner_text("#dk-msg")) > 10, cb)
            check("k. the Desk card: no sideways scroll, the orb's corner free", p.evaluate("document.documentElement.scrollWidth <= innerWidth") and not _orb_hits(p), _orb_hits(p))
            p.click("#deskX")
            check("k. the close button hides the card again", p.is_hidden("#desk"))
            ctx.close()
            ctx, p = _open(br, url + "?q=off#desk", errs)
            check("k. the link #desk opens it straight away", p.is_visible("#desk"))
            ctx.close()
            check("k. no console errors", not errs, errs[:3])
            br.close()
    finally:
        srv.shutdown()


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="pantheon_test_")
    try:
        part_a()
        part_b(tmp)
        part_c()
        part_d()
        part_e(tmp)
        part_f()
        part_i(tmp)
        if not fast:
            part_g(tmp)
            part_j(tmp)
            part_k(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
