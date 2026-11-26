"""Batch 5 (day-batch5 2026-11-26): tools/health_bands.py band math + tools/forecast.py output shape. Offline.
    python -X utf8 -m tests.test_batch5
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import health_bands as HB  # noqa: E402

FAILS = []


def ok(c, w):
    print(("ok   " if c else "FAIL ") + w)
    if not c:
        FAILS.append(w)


def main():
    rs = list(np.r_[np.ones(30), -np.ones(30)])
    b = HB.band(rs)
    ok(b and b["p5"] <= b["p50"] <= b["p95"] and b["n_windows"] == len(rs) - HB.W + 1, "band: 5 <= 50 <= 95, rolling windows counted")
    ok(HB.band([1.0] * 10) is None, "band: fewer trades than the window -> None")
    ok(HB.pct_of(np.array([0.0, 1.0, 2.0, 3.0]), 1.5) == 50.0, "percentile of a live mean in the band")
    p = os.path.join(ROOT, "research", "forecast", "forecast.json")
    if os.path.exists(p):
        F = json.load(open(p, encoding="utf-8"))
        a = next(iter(F["accounts"].values()))
        ok({"2026-like", "2021-25-like", "state"} <= set(a) and "words" in F, "forecast.json shape (accounts x markets, words)")
    print("ALL OK" if not FAILS else f"{len(FAILS)} FAILED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
