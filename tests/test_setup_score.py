"""LIT live setup score (engine/setup_score.py, tools/setupscore_build.py, research/setupscore/DESIGN.md). Offline.
  a. the kNN: same side only, only setups dated before the day, nearest first, missing facts left out, N / won / avg R
  b. the line: '$ at this size', 'history only, not a predictor' unless the pool's verdict is 'separates'; '' on nothing
  c. never raises: junk pool / junk rows / no file -> None or ''
  d. a Brain row (bar CLOSE stamp -> the bar's open minute); NOT in the owner's pushes (lead 2026-11-26: it does not predict)
  e. display only: no order / route / size call in the module; the real pool + eval: verdict = the pre-registered holdout result
    python -X utf8 -m tests.test_setup_score
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import setup_score as SS  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)
    if not ok:
        FAILS.append(name)


def fake_pool(verdict="info only"):
    rows = []
    for i in range(60):
        rows.append(["2025-01-%02d" % (1 + i % 28), 1, 3.0 + 0.01 * i, 1.0, 1.0, 1.0, 15.0, 1.0])     # longs near 03:00: win +1R
        rows.append(["2025-01-%02d" % (1 + i % 28), 1, 12.0 + 0.01 * i, 1.0, 1.0, 1.0, 15.0, -1.0])   # longs near 12:00: lose
        rows.append(["2025-01-%02d" % (1 + i % 28), -1, 3.0, 1.0, 1.0, 1.0, 15.0, -1.0])               # shorts: lose
    rows.append(["2026-02-01", 1, 3.0, 1.0, 1.0, 1.0, 15.0, -50.0])                                     # a later day: never used before it
    return {"cols": ["day", "dir", "h", "depth", "disp", "idm", "vix", "r"], "sd": {"h": 4.0, "depth": 0.5, "disp": 0.5, "idm": 1.0, "vix": 5.0},
            "rows": rows, "verdict": verdict}


def main():
    P = fake_pool()
    s = SS.score(SS.feats(mod=180, depth=1, disp=1, idm=1, vix=15), 1, pool=P, before="2026-01-01")
    check("a. a long at 03:00 finds the 50 winning longs near 03:00 (not the shorts, not 12:00)", s and s["n"] == 50 and s["won"] == 50 and s["avg_r"] == 1.0, s)
    s2 = SS.score(SS.feats(mod=720, depth=1, disp=1, idm=1, vix=15), 1, pool=P, before="2026-01-01")
    check("a. a long at 12:00 finds the losing ones", s2 and s2["avg_r"] == -1.0, s2)
    s3 = SS.score(SS.feats(mod=180, depth=1, disp=1, idm=1, vix=15), 1, pool=P, before="2026-12-31", k=200)
    check("a. 'before' cuts the pool: the 2026-02-01 row only counts for later days", s3 and min(r for r in [s3["avg_r"]]) < 0.5, s3)
    s4 = SS.score(SS.feats(mod=180), 1, pool=P)
    check("a. missing facts are left out of the distance (time only still scores)", s4 and s4["on"] == ["h"], s4)
    check("b. the line: N, won %, avg R, $ at this size, 'history only' while the verdict is 'info only'",
          SS.line(s, 300, "info only") == "Similar setups: 50, won 100%, avg +1.00R (+$300 at this size) · history only, not a predictor", SS.line(s, 300, "info only"))
    check("b. 'separates' drops the warning; no risk -> R only", SS.line(s2, None, "separates") == "Similar setups: 50, won 0%, avg -1.00R")
    check("b. no score -> ''", SS.line(None) == "" and SS.line({"n": 0}) == "")
    check("c. junk never raises", SS.score({"h": "x"}, 1, pool={"rows": "bad"}) is None and SS.score({}, 3, pool=P) is None
          and SS.brain_line({"t": "x"}) == "" and SS.entry_line(None, None) == "" and SS.load("/no/such/file.json") is None)
    tmp = tempfile.mkdtemp()
    pp = os.path.join(tmp, "pool.json")
    json.dump(P, open(pp, "w"))
    keep = SS.POOL_PATH
    SS.POOL_PATH = pp
    try:
        import datetime as dt
        from zoneinfo import ZoneInfo
        t_close = dt.datetime(2026, 11, 24, 3, 5, tzinfo=ZoneInfo("America/New_York")).timestamp()     # the 03:00 bar closes 03:05
        row = {"id": "1:1", "t": t_close, "dir": 1, "checks": [{"key": "depth", "value": 1.0}, {"key": "disp", "value": 1.0}, {"key": "idm", "value": 1}]}
        x = SS.from_brain_row(row)
        check("d. a Brain row: the bar close stamp -> its open minute (03:00 = 3.0 h), its facts", x and abs(x[0]["h"] - 3.0) < 1e-9 and x[0]["depth"] == 1.0 and x[1] == 1, x)
        nsrc = open(os.path.join(ROOT, "engine", "notify.py"), encoding="utf-8").read() + open(os.path.join(ROOT, "engine", "setup_progress.py"), encoding="utf-8").read()
        check("d. NOT in the owner's pushes (it does not predict): notify / setup_progress never import it", "setup_score" not in nsrc)
        check("d. entry_line still works for the page (remembered score reused, $ at the size)", SS.brain_score(row) and "at this size" in SS.entry_line("LONG", t_close + 600, 200))
    finally:
        SS.POOL_PATH = keep
    src = open(os.path.join(ROOT, "engine", "setup_score.py"), encoding="utf-8").read()
    code = re.sub(r'""".*?"""|#[^\n]*', "", src, flags=re.S)
    check("e. display only: no order / route / size / NinjaTrader call, no network", not re.search(r"ninjatrader|place_order|route|requests|urllib|socket|sizing|qty_for", code, re.I))
    ev = json.load(open(os.path.join(ROOT, "research", "setupscore", "eval.json")))
    pool = SS.load()
    check("e. the real pool: >= 2,000 setups with an outcome; its verdict = the holdout result (eval.json)",
          pool and len(pool["rows"]) >= 2000 and pool.get("verdict") == ev["verdict"] and ev["verdict"] in ("separates", "info only"), (len((pool or {}).get("rows") or []), ev.get("verdict")))
    print(f"\nsetup score: {'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
