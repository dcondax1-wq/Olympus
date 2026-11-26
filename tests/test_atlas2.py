"""ATLAS v2 study (research/atlas2/atlas2.py, day-atlas2 2026-11-26). Offline, synthetic trades + the committed results.json.
  a. the regime switch only looks at signals CLOSED before the entry, keeps everything while history < n
  b. fixed $250 scoring: net, PF, max DD
  c. results.json: 8 variants, the gate agrees with the stored verdict
    python -X utf8 -m tests.test_atlas2
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research", "atlas2"))
import atlas2 as A  # noqa: E402

FAILS = []


def ok(c, what):
    print(("ok   " if c else "FAIL ") + what)
    if not c:
        FAILS.append(what)


def main():
    T = [{"entry_t": 100 * k, "exit_t": 100 * k + 50, "R_c": r, "day": "2026-01-0%d" % (1 + k % 5)} for k, r in enumerate([-1, -1, 2, -1, -1, 1])]
    T[3]["exit_t"] = 10_000                                  # still open at the later entries: never counted
    K = A.switch(T, 2)
    ok([t["entry_t"] for t in K] == [0, 100, 300, 400, 500], f"a switch keeps {[t['entry_t'] for t in K]}")
    x = A.fixed([{"day": "2026-01-02", "R_c": 1.0}, {"day": "2026-01-05", "R_c": -1.0}, {"day": "2026-01-06", "R_c": -0.5},
                 {"day": "2026-01-07", "R_c": 2.0}], "2026-01-01", "2026-01-31")
    ok(x["net"] == 375 and x["pf"] == 2.0 and x["max_dd"] == 375 and x["n"] == 4, f"b fixed {x}")
    R = json.load(open(A.OUT, encoding="utf-8"))
    ok(sorted(R["fixed"]) == sorted(A.VARIANTS) and sorted(R["engines"]) == sorted(A.VARIANTS), "c results.json has the 8 variants")
    g, v = A.gate(R)
    ok(v == R["verdict"], f"c the gate reproduces the verdict: {v}")
    print("ALL OK" if not FAILS else f"{len(FAILS)} FAILED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
