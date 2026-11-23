"""Prop economics (2026-11-23), stage 1: EV per eval dollar of ONE account slot under a phase policy.
PAPER RESEARCH ONLY. Engine: research/onebook/book.py -> research/plans/rank.py (real fills, ATLAS 10 ticks, costs in).
A policy = (eval lanes, eval LIT size x, eval add-on size x, funded lanes, funded LIT size x, funded add-on size x, payout ask).
"""
from __future__ import annotations
import itertools, json, os, sys, time
from multiprocessing import Pool
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "onebook"))
import book as B  # noqa
R, SOA, U = B.R, B.SOA, B.U
R.PLANS.update({"lucid_pro_50k": 126.0})
LA = ("LIT", "ATLAS")
MIX = {"L": ("LIT",), "LA": LA, "LAB": LA + ("BLITZ",), "A": ("ATLAS",)}


def book_name(em, le, ae, fm, lf, af):
    name = f"P|{em}|{le}|{ae}|{fm}|{lf}|{af}"
    if name not in B.EXTRA:
        lanes = {"BLITZ": 300} if ("B" in em or "B" in fm) else {}
        knobs = {"lit_e": le, "add_e": ae, "lit_f": lf, "add_f": af}
        me, mf = MIX[em], MIX[fm]
        B.EXTRA[name] = (me, mf, knobs, None, lanes)
    return name


def build(plan, em, le, ae, fm, lf, af, ask="plan", pmax=None):
    sp = B.build(plan, book_name(em, le, ae, fm, lf, af))
    F = dict(sp["F"])
    if pmax:
        F["max_payouts"] = min(F["max_payouts"], pmax)
    big = "50k" in plan
    a = ("cap" if F["cap1"] < 1e8 else F["pay_min"]) if ask == "plan" else (F["pay_min"] if ask == "min" else ask)
    sp["fund"] = lambda F=F, z=sp["z"], big=big, a=a: R.Funded(U.UP50 if big else U.UP25, F, z, a)
    sp["F"] = F
    return sp


def slot(sp, paths, L=126):
    B.CFG.clear(); B.CFG.update(sp["knobs"])
    R.LEN = L
    r = R.slot_run(sp, paths)
    B.CFG.clear()
    return r


_P = {}


def paths(span, n, L=126, seed=23):
    k = (span, n, L, seed)
    if k not in _P:
        _P[k] = U.mc_paths(SOA.data()["S"], span, n, length=L, seed=seed)
    return _P[k]


def job(a):
    plan, pol, span, n = a
    sp = build(plan, *pol)
    t0 = time.time()
    r = slot(sp, paths(span, n))
    r["secs"] = round(time.time() - t0, 1)
    return a[:3], r


PLANS = ["mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k", "mffu_rapid_eod_50k", "fn_rapid_daily_50k", "lucid_pro_50k"]
if __name__ == "__main__":
    n = int(sys.argv[1]); out = sys.argv[2]; spans = sys.argv[3].split(",")
    grid = []
    for em, le, ae in [("L", 1.0, 1.0), ("LA", 1.0, 1.0), ("LA", 0.5, 1.0), ("LA", 1.5, 1.0), ("LA", 2.0, 1.0), ("LA", 1.0, 2.0),
                       ("LA", 2.0, 2.0), ("LAB", 1.0, 1.0), ("LAB", 2.0, 2.0), ("L", 2.0, 1.0)]:
        for fm, lf, af in [("LA", 1.0, 1.0), ("LA", 0.5, 0.5), ("LA", 0.75, 1.0), ("L", 1.0, 1.0), ("L", 0.5, 1.0)]:
            for ask in ("plan", "min"):
                grid.append((em, le, ae, fm, lf, af, ask))
    jobs = [(p, g, s, n) for p in PLANS for g in grid for s in spans]
    res = {}
    t0 = time.time()
    with Pool(int(os.environ.get("JOBS", "4"))) as pool:
        for i, (k, r) in enumerate(pool.imap_unordered(job, jobs, chunksize=4)):
            res["|".join(map(str, [k[0], *k[1], k[2]]))] = r
            if i % 50 == 0:
                print(i, len(jobs), round(time.time() - t0), k, r["net_6m"], flush=True)
    json.dump(res, open(out, "w"))
