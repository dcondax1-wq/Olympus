"""tools/data_check.py on the real files (clean) and on a synthetic broken copy (every defect found) + the HEALTH_CHECK line.

  python -X utf8 -m tests.test_data_check
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import ops_checks  # noqa: E402
from tools import data_check as DC  # noqa: E402

R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def main():
    rep = DC.run()
    check("real data: nothing to fix", rep["n_fix"] == 0, DC.summary(rep))
    tmp = tempfile.mkdtemp(prefix="le_dc_")
    try:
        for f in ("VIX_1d.csv", "NQ_rolls.json"):
            shutil.copy(os.path.join(DC.DATA, f), tmp)
        d = pd.read_csv(os.path.join(DC.DATA, "NQ_5m.csv")).tail(20000).reset_index(drop=True)
        d.loc[100, "high"] = d.loc[100, "low"] - 5                 # high below low
        d.loc[200, "close"] = d.loc[200, "close"] * 1.2            # a lone 20% print
        d = pd.concat([d, d.iloc[[300]]]).sort_values("time", kind="stable")   # a duplicate
        d.to_csv(os.path.join(tmp, "NQ_5m.csv"), index=False)
        b = DC.run(tmp)
        f = next(x for x in b["files"] if x["file"] == "NQ_5m.csv")
        lv = {i["what"]: i["level"] for i in f["items"]}
        check("duplicate -> fix", lv.get("order") == DC.BAD, lv.get("order"))
        check("high below low -> look", lv.get("ohlc") in (DC.WARN, DC.BAD), lv.get("ohlc"))
        check("lone spike -> look", lv.get("spikes") == DC.WARN, lv.get("spikes"))
        check("missing NQ_1m -> fix", any(x["file"] == "NQ_1m.csv" and x["items"][0]["level"] == DC.BAD for x in b["files"]))
        lvl, txt = DC.summary(b)
        check("summary level fix", lvl == DC.BAD, txt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    c = ops_checks.check_data(lambda: ("fix", "NQ_5m.csv order"))
    check("HEALTH_CHECK line: fix level + the fix text", c["level"] == ops_checks.BAD and "data_check" in c["fix"], c)
    check("HEALTH_CHECK line on the real data", ops_checks.check_data()["level"] in (ops_checks.OK, ops_checks.WARN, ops_checks.INFO))
    # 2026-11-18: files that are only old (no defect) -> a quiet note pointing at the data pipe, not a daily yellow line
    fresh_only = {"n_fix": 0, "n_warn": 1, "cross": [],
                  "files": [{"file": "NQ_5m.csv", "first": "2021-01-04", "last": "2026-10-16",
                             "items": [{"level": DC.WARN, "what": "freshness", "text": "last bar 2026-10-16 (33 days ago)"}]},
                            {"file": "NQ_1m.csv", "last": "2026-10-16", "items": []}]}
    lv, txt = DC.summary(fresh_only)
    c = ops_checks.check_data(lambda: (lv, txt))
    check("only old data files -> INFO (not WARN), no fix step, says the data pipe is coming",
          lv == "info" and c["level"] == ops_checks.INFO and not c["fix"] and "data pipe" in c["text"] and "2026-10-16" in c["text"], c)
    gap = {**fresh_only, "files": [{**fresh_only["files"][0], "items": fresh_only["files"][0]["items"]
                                    + [{"level": DC.WARN, "what": "gaps", "text": "x"}]}, fresh_only["files"][1]]}
    check("old + a real defect -> still WARN", DC.summary(gap)[0] == DC.WARN)
    print(f"data_check: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
