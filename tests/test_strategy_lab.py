"""Strategy Lab data + the Research Hub's Strategy Lab tab (day-mind 2026-11-23).
  d. tools/build_strategy_lab.py: lab-data.json is fresh (--check); the real rows are in (LIT + ATLAS live from edge.json, every
     LEADERBOARD.md strategy with its dev / confirm / ytd spans); with no popular files the SAMPLE fixture fills and says so; when the
     popular files land they replace the fixture (list or {strategies}, span dicts / lists / flat), verdicts normalise, the best add-on
     comes ONLY from a separate (popular) strategy that is positive with PF >= 1.3 in every span, never a SAMPLE row or a LIT variant
  b. Chromium 390 x 844 (Node Playwright): hub.html#lab opens the tab, the table has every row, sorting by $/mo, PF and /wk works both
     ways, verdict chips filter, a row opens its rules + spans, the best add-on card + SAMPLE banner, no sideways scroll, no page error.
     MIND_SHOTS=<dir> saves 9_hub_strategy_lab.png. MB_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_strategy_lab
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
PUB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def data():
    import build_strategy_lab as B
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_strategy_lab.py"), "--check"], capture_output=True, text=True, timeout=60)
    check("d. lab-data.json is fresh (build_strategy_lab --check)", r.returncode == 0, r.stdout + r.stderr)
    d = B.build()
    ids = {x["id"]: x for x in d["rows"]}
    check("d. LIT + ATLAS live rows from edge.json", ids.get("lit", {}).get("verdict") == "live" and ids.get("atlas", {}).get("verdict") == "live" and ids["lit"]["spans"][0]["usd_mo"], ids.get("lit"))
    lb = [x for x in d["rows"] if x["src"] == "LEADERBOARD.md"]
    names = {l.split("|")[1].strip() for l in open(os.path.join(ROOT, "research", "lab", "LEADERBOARD.md"), encoding="utf-8") if l.startswith("| ") and l.count("|") > 12 and l.split("|")[2].strip() in ("dev", "confirm", "ytd")}
    check("d. every LEADERBOARD.md strategy is a row (3 spans max, in order)", len(lb) == len(names) and all(1 <= len(x["spans"]) <= 3 for x in lb) and all([s["k"] for s in x["spans"]] == sorted([s["k"] for s in x["spans"]], key=["dev", "confirm", "ytd"].index) for x in lb), (len(lb), len(names)))
    fx = [x for x in d["rows"] if x["src"] == "fixture"]
    popular_present = any(os.path.exists(p) for p in B.POPULAR)
    check("d. no popular files: the SAMPLE fixture fills and says so", popular_present or (d["fixture"] is True and fx and all(x["name"].startswith("SAMPLE") for x in fx)), d["fixture"])
    check("d. the best add-on is never a SAMPLE row or a LIT variant", not d["best_addon"].get("id") or d["best_addon"].get("src", "").startswith("popular_"), d["best_addon"])
    check("d. every row: id, name, verdict, <= 3 rule lines, <= 3 spans", all(x["id"] and x["name"] and x["verdict"] in B.VERDICTS and len(x["rules"]) <= 3 and len(x["spans"]) <= 3 for x in d["rows"]))
    pop = [x for x in d["rows"] if x["src"].startswith("popular_")]
    if pop:
        check("d. popular files in: no SAMPLE rows, every popular strategy has its rules (spec / tool docstring) and 3 spans",
              not fx and d["fixture"] is False and all(1 <= len(x["rules"]) <= 3 and len(x["spans"]) == 3 for x in pop), [x["id"] for x in pop if not x["rules"]])
        check("d. rule text keeps its arrows / comparisons (no '<' / '>' left, no mangled '- long')", all("<" not in t and ">" not in t and " - long" not in t for x in pop for t in x["rules"]))
        check("d. best add-on is honest: an id only when one passes every span, else 'None passed' with the nearest misses",
              (d["best_addon"].get("id") and d["best_addon"]["src"].startswith("popular_")) or d["best_addon"]["why"].startswith("None passed"), d["best_addon"])
        check("d. the write-ups' nearest misses carry a watch note (verdict stays the file's)", all(ids[k].get("watch") and ids[k]["verdict"] == "rejected" for k in ("popc_crabel", "ict2022") if k in ids))
    check("d. lab-data.json small, no secrets", os.path.getsize(B.OUT) < 200_000 and not any(k in open(B.OUT, encoding="utf-8").read().lower() for k in ("api_key", "token\"", "password")))
    # the popular files landing: a temp folder with both shapes
    with tempfile.TemporaryDirectory() as td:
        ict, cls = os.path.join(td, "popular_ict.json"), os.path.join(td, "popular_classic.json")
        json.dump({"strategies": [
            {"id": "silver_bullet", "name": "Silver Bullet", "verdict": "PROMISING", "rules": "Sweep 10-11 ET. FVG entry. Stop past the sweep.",
             "spans": {"2026 H1": {"tpw": 2.2, "win": 45, "pf": 1.6, "usd_mo": 700, "maxdd": 1500}, "2026 H2": {"tpw": 2.0, "win": 44, "pf": 1.5, "usd_mo": 450, "maxdd": -1400}, "2021-25": {"tpw": 2.1, "win": 43, "pf": 1.4, "usd_mo": 380, "maxdd": 2600}}},
            {"id": "judas", "name": "Judas", "verdict": "rejected", "spans": [{"k": "a", "tpw": 3, "pf": 0.9, "usd_mo": -100}]}]}, open(ict, "w"))
        json.dump([{"id": "orb", "name": "ORB", "verdict": "paper", "spans": {"tpw": 4, "pf": 1.4, "usd_mo": 900, "win": 40, "maxdd": 1000}},
                   {"id": "vwap", "name": "VWAP", "verdict": "promising", "rules": ["a", "b", "c", "d"],
                    "spans": {"x": {"tpw": 2.5, "pf": 1.8, "usd_mo": 1200}, "y": {"tpw": 2.4, "pf": 1.2, "usd_mo": 300}}}], open(cls, "w"))
        old = B.POPULAR
        B.POPULAR = [ict, cls]
        try:
            d2 = B.build()
        finally:
            B.POPULAR = old
        ids2 = {x["id"]: x for x in d2["rows"]}
        check("d. popular files replace the fixture (both shapes)", d2["fixture"] is False and not any(x["src"] == "fixture" for x in d2["rows"]) and {"silver_bullet", "judas", "orb", "vwap"} <= set(ids2), sorted(ids2)[:8])
        check("d. family + verdict + spans normalise", ids2["silver_bullet"]["family"] == "ICT" and ids2["orb"]["family"] == "Classic" and ids2["silver_bullet"]["verdict"] == "promising"
              and len(ids2["silver_bullet"]["spans"]) == 3 and ids2["silver_bullet"]["spans"][1]["maxdd"] == -1400 and ids2["silver_bullet"]["spans"][0]["maxdd"] == -1500
              and len(ids2["orb"]["spans"]) == 1 and len(ids2["vwap"]["rules"]) == 3 and len(ids2["silver_bullet"]["rules"]) == 3, (ids2["silver_bullet"], ids2["orb"]["spans"]))
        check("d. best add-on = the separate strategy positive with PF >= 1.3 in every span (worst span decides)",
              d2["best_addon"].get("id") == "silver_bullet" and d2["best_addon"]["worst_usd_mo"] == 380, d2["best_addon"])


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


JS = r"""
const { chromium } = require('playwright');
const [, BASE, SHOTS] = process.argv.slice(1);
(async () => {
  const out = {}; const b = await chromium.launch();
  try {
    const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, hasTouch: true }), errs = [];
    p.on('pageerror', (e) => errs.push(String(e)));
    await p.goto(BASE + '/cities/hub.html#lab'); await p.waitForSelector('#labTable .lr', { timeout: 20000 });
    const col = (i) => p.evaluate((i) => [...document.querySelectorAll('#labTable .lr')].map((r) => r.children[i].textContent), i);
    const num = (a) => a.map((x) => x === '-' ? null : +x.replace(/[$,]/g, '').replace(/^-\$/, '-'));
    out.tab = await p.evaluate(() => [document.getElementById('lab').hidden, document.getElementById('main').hidden]);
    out.n = (await col(0)).length;
    out.usd = num(await col(1));
    await p.click('button[data-sort="usd_mo"]'); out.usdAsc = num(await col(1));
    await p.click('button[data-sort="pf"]'); out.pf = num(await col(2));
    await p.click('button[data-sort="tpw"]'); out.tpw = num(await col(3));
    await p.click('button[data-sort="usd_mo"]');
    if (SHOTS) await p.screenshot({ path: SHOTS + '/9_hub_strategy_lab.png' });
    await p.click('button[data-lv="rejected"]'); out.rej = await p.evaluate(() => [...document.querySelectorAll('#labTable .lr .vt')].every((x) => x.textContent === 'Rejected') && document.querySelectorAll('#labTable .lr').length);
    await p.click('button[data-lv=""]'); await p.click('#labTable .lr:nth-child(1)');
    out.det = await p.evaluate(() => { const d = document.querySelector('.ldet'); return d ? { rules: d.querySelectorAll('ol li').length, spans: d.querySelectorAll('.lspan tr').length - 1 } : null; });
    out.best = (await p.textContent('#hubBest')) || ''; out.sample = await p.evaluate(() => !!document.getElementById('hubSample'));
    out.sideways = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    await p.click('#tabs button[data-tab="research"]'); out.back = await p.evaluate(() => [document.getElementById('lab').hidden, document.getElementById('main').hidden]);
    out.errors = errs;
  } catch (e) { out.fatal = String(e && e.stack || e); }
  await b.close(); console.log(JSON.stringify(out));
})();
"""


def _npm_root():
    try:
        return subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def browser():
    env = {**os.environ, "NODE_PATH": _npm_root()}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    shots = os.environ.get("MIND_SHOTS", "")
    try:
        r = subprocess.run(["node", "-e", JS, "x", f"http://127.0.0.1:{srv.server_address[1]}", shots], capture_output=True, text=True, timeout=180, env=env)
    finally:
        srv.shutdown()
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or str(e))[:600])
        return
    n = json.load(open(os.path.join(PUB, "cities", "lab-data.json")))["n"]
    desc = lambda a: [x for x in a if x is not None] == sorted([x for x in a if x is not None], reverse=True)  # noqa: E731
    check("b. no fatal / page error", "fatal" not in o and not o.get("errors"), (o.get("fatal"), o.get("errors")))
    check("b. #lab opens the Strategy Lab tab", o.get("tab") == [False, True], o.get("tab"))
    check("b. the table has every strategy", o.get("n") == n, (o.get("n"), n))
    check("b. sort by $/month (down, then up)", desc(o["usd"]) and [x for x in o["usdAsc"] if x is not None] == sorted(x for x in o["usdAsc"] if x is not None), (o["usd"][:5], o["usdAsc"][:5]))
    check("b. sort by PF and by trades a week", desc(o["pf"]) and desc(o["tpw"]), (o["pf"][:5], o["tpw"][:5]))
    check("b. verdict chip filters", isinstance(o.get("rej"), int) and o["rej"] > 0, o.get("rej"))
    check("b. a row opens its rules + spans", (o.get("det") or {}).get("rules", 0) >= 1 and (o.get("det") or {}).get("spans", 0) >= 1, o.get("det"))
    fixture = json.load(open(os.path.join(PUB, "cities", "lab-data.json")))["fixture"]
    check("b. best add-on card; SAMPLE banner only with the fixture", "Best add-on to LIT" in o.get("best", "") and o.get("sample") is fixture, (o.get("best"), o.get("sample")))
    check("b. no sideways scroll at 390", o.get("sideways") is False)
    check("b. back to the Research tab", o.get("back") == [True, False], o.get("back"))


def main():
    data()
    if os.environ.get("MB_NO_BROWSER") != "1":
        browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
