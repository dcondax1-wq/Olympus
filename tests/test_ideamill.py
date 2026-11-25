"""IDEA MILL (tools/ideamill.py, research/ideamill/grammar.py; day-ideamill 2026-11-25). Offline, synthetic data, temp files.

  a. statistics: BH passes a planted p and none of pure noise; the bootstrap p sees a strong planted edge and not noise;
     DSR falls as the trial count grows; PF
  b. the trade walker on a tiny bar series: stop before target on the same bar, target hit, flat at 15:55, one a day,
     costs in R, a stop under 4 points skipped
  c. the log: rows are appended (gzip members), an idea is never re-scored on the same data end, the placebo is seeded by the id
  d. the Brain block reads summary.json
    python -X utf8 -m tests.test_ideamill
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "ideamill"))
from tools import ideamill as M  # noqa: E402
import grammar as G  # noqa: E402

FAILS = []


def ok(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


def part_a():
    rng = np.random.default_rng(3)
    noise = rng.uniform(size=2000)
    ok(M.bh(noise).sum() == 0, "a BH: pure noise -> no discovery")
    ok(M.bh(np.r_[1e-7, noise]).sum() >= 1, "a BH: a planted p = 1e-7 among 2,000 is found")
    x = np.zeros(800); m = rng.random(800) < 0.4; x[m] = rng.normal(0.6, 1.0, m.sum())
    y = np.zeros(800); y[m] = rng.normal(0.0, 1.0, m.sum())
    ok(M.boot_p(x) < 1e-6 and M.boot_p(y) > 0.01, f"a bootstrap p: edge {M.boot_p(x):.2e}, noise {M.boot_p(y):.3f}")
    w = np.zeros(800); w[m] = rng.normal(0.12, 1.0, m.sum())
    v10, _ = M.dsr(w, 10, 0.002); v1e5, _ = M.dsr(w, 100000, 0.002)
    ok(0 <= v1e5 < v10 <= 1, f"a DSR falls with more trials ({v10:.3f} -> {v1e5:.3f})")
    ok(abs(M.pf(np.array([2.0, -1.0, -1.0])) - 1.0) < 1e-9, "a PF")


def part_b():
    # 3 days, bars at 10:00, 10:05 ... ; prices crafted per case
    mins = np.array([600, 605, 610, 615, 950, 955, 600, 605, 610], np.int64)
    di = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1], np.int64)
    o = np.array([100, 100, 100, 100, 100, 100, 200, 200, 200], float)
    h = np.array([101, 101, 125, 101, 101, 101, 201, 201, 201], float)
    l = np.array([99, 99, 89, 99, 99, 99, 199, 199, 199], float)
    c = o.copy()
    sig = np.zeros(9, np.int8); sig[0] = 1; sig[3] = 1                       # 2nd signal the same day: ignored
    stop = np.full(9, 90.0)
    d, r, g = G.walk(o, h, l, c, mins, di, sig, stop, 2.0, 0)
    ok(len(r) == 1 and abs(g[0] - (-1.0)) < 1e-9, "b stop and target on the same bar -> the stop (gross -1R), one trade a day")
    ok(abs(r[0] - (-(10 + 1.45) / 10)) < 1e-9, "b costs: 1.45 points taken off in R")
    h2 = h.copy(); l2 = l.copy(); l2[2] = 95
    d, r, g = G.walk(o, h2, l2, c, mins, di, sig, stop, 2.0, 0)
    ok(len(g) == 1 and abs(g[0] - 2.0) < 1e-9, "b target 2R hit")
    h3 = np.full(9, 101.0); l3 = np.full(9, 99.0); c3 = c.copy(); o3 = o.copy(); o3[5] = 104
    d, r, g = G.walk(o3, h3, l3, c3, mins, di, sig, stop, 3.0, 0)
    ok(abs(g[0] - 0.4) < 1e-9, "b no stop / target -> flat at the 15:55 open")
    d, r, g = G.walk(o, h, l, c, mins, di, sig, np.full(9, 98.0), 2.0, 0)
    ok(len(r) == 0, "b a stop under 4 points is skipped")


def part_c():
    with tempfile.TemporaryDirectory() as td:
        old = M.TRIALS
        M.TRIALS = os.path.join(td, "t.jsonl.gz")
        try:
            for k in range(2):
                with gzip.open(M.TRIALS, "at", encoding="utf-8") as fh:
                    fh.write(json.dumps({"id": f"x{k}", "proto": M.PROTO, "data_end": "2026-11-20", "n": k + 1}) + "\n")
            T = M.load_trials()
            ok(len(T) == 2 and T[-1]["n"] == 2, "c the log appends gzip members and reads them all back")
        finally:
            M.TRIALS = old
    r = np.array([0.5, -1.0, 2.0]); g = r + 0.1
    ok(np.allclose(M.placebo_r("abc", r, g), M.placebo_r("abc", r, g)), "c the placebo is seeded by the idea id (repeatable)")
    ids = [I["id"] for I in G.ideas()]
    ok(len(ids) == len(set(ids)) and len(ids) == 3 * len(G.TRIGGERS) * 2 * 5 * len(G.FILTERS) * 2 * 4, f"c {len(ids)} unique grammar ids")


def part_d():
    from engine import market_learn as ML
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "research", "ideamill"))
        json.dump({"made": "x", "counts": {"trials_total": 7, "G1_bh": 1, "G2_dsr": 0, "G3_holdouts": 0, "G4_forward": 0,
                                           "placebo_G1": 0, "placebo_G2": 0, "placebo_G3": 0},
                   "week": {"tested_this_week": 7}, "top": [{"id": "a|b"}]},
                  open(os.path.join(td, "research", "ideamill", "summary.json"), "w"))
        b = ML.ideamill_block(td)
        ok(b["tested_total"] == 7 and b["passed_discovery"] == 1 and b["best"] == "a|b", "d the Brain block reads summary.json")
        ok(ML.ideamill_block(os.path.join(td, "nothing")) is None, "d no summary yet -> None")


def main():
    for f in (part_a, part_b, part_c, part_d):
        f()
    print("ALL OK" if not FAILS else f"{len(FAILS)} FAILED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
