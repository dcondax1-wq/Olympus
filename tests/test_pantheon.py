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
    p.goto(url)
    p.wait_for_function("window.__pantheon && window.__pantheon.ready", timeout=30000)
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
            check("g. ARTEMIS's card says NOT FUTURES DATA", "NOT FUTURES DATA" in p.inner_text("#card-b"))
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
            br.close()
    finally:
        srv1.shutdown()
        srv2.shutdown()


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
        if not fast:
            part_g(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
