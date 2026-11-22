"""Fleet v2 (2026-11-22): the v1 fleet (research/fleet/fleet.py) + LucidPro 50K accounts ("LU", LIT only, book B01).
PAPER RESEARCH ONLY. Design (committed before the scored run): research/fleet/DESIGN_V2.md.

    python -X utf8 research/fleet/fleet2.py [--n 1000] [--jobs 4] [--part main|sens|check]   -> research/fleet/results_v2_<part>.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fleet as F  # noqa: E402

B, R, U, SOA = F.B, F.R, F.U, F.SOA
LU_PRICE = 126.0                                           # ASSUMED (UNVERIFIED): rank.py PLANS code price
F.TYPES["LU"] = ("lucid_pro_50k", "B01 LIT only", "lucid", 0)
WIN = 10                                                    # 2 weeks of sessions
BUDGETS = (300, 500, 800)
NS = (0, 1, 2, 3, 5)
ORDERS = ("LU", "BASE")
BASE = ("R50", "FN")


def run_path2(seq, budget, n_lu, order, price=LU_PRICE):
    """v1's run_path (L3 / S0 / P4) with n_lu Lucid slots and a failure log."""
    pol = "P4"
    R.PLANS["lucid_pro_50k"] = price
    accts = F.start_fleet(pol)
    avail, fees, owner, live, fn_pays = 0.0, 0.0, 0.0, None, 0
    hit, turn, pays = None, 0, 0
    fails, buys = [], []                                    # (session, kind 'E'/'F', key)
    lu_owner = 0.0
    c6 = c12 = None
    for k, si in enumerate(seq[:F.LEN]):
        if k % F.MO == 0:
            avail += budget
        while True:
            rot = list(BASE[turn % 2:] + BASE[:turn % 2])
            seqt = (["LU"] + rot) if order == "LU" else (rot + ["LU"])
            bought = False
            for t in seqt:
                plan, _, firm, cap = F.TYPES[t]
                if t == "LU":
                    cap = n_lu
                price_t = R.PLANS[plan]
                if price_t > avail + 1e-9 or (firm == "mffu" and live) or (firm == "fn" and fn_pays >= 15):
                    continue
                same = sum(1 for x in accts if x.key == t)
                mffu = sum(1 for x in accts if x.firm == "mffu")
                if same >= cap or (firm == "mffu" and mffu >= 5):
                    continue
                sp = F.spec(t, None, pol)
                accts.append(F.Acct(t, sp, e=sp["ev"]()))
                avail -= price_t
                fees += price_t
                buys.append((k, t))
                bought = True
                if t != "LU":
                    turn += 1
                break
            if not bought:
                break
        keep = []
        for a in accts:
            if a.firm == "mffu" and live:
                continue
            B.CFG.clear()
            B.CFG.update(a.sp["knobs"])
            if a.e is not None:
                r, _ = a.e.step(a.sp["BYe"][si])
                if r == "pass":
                    a.e, a.wait = None, F.R.GAP
                elif r in ("fail", "stuck"):
                    fails.append((k, "E", a.key))
                    continue
                keep.append(a)
                continue
            if a.f is None:
                a.wait -= 1
                if a.wait <= 0:
                    a.f = a.sp["fund"]()
                keep.append(a)
                continue
            ev, x, cum = a.f.step(a.sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x
                pays += 1
                if a.key == "LU":
                    lu_owner += x
                if a.firm == "fn":
                    fn_pays += 1
            if a.rapid and cum is not None and cum >= 10000.0:
                live = live or ("rapid10k", k)
            if ev == "lost":
                fails.append((k, "F", a.key))
                continue
            if ev == "grad":
                continue
            keep.append(a)
        accts = keep
        if k == 125:
            c6 = (owner, fees, pays, lu_owner)
        if k == 251:
            c12 = (owner, fees)
        if hit is None and owner - fees >= F.CORVETTE:
            hit = k + 1
    B.CFG.clear()
    return {"o6": c6[0], "f6": c6[1], "p6": c6[2], "lu6": c6[3], "o12": c12[0], "f12": c12[1], "hit": hit,
            "net24": owner - fees, "fails": fails, "n_lu_buys6": sum(1 for kk, t in buys if t == "LU" and kk < 126),
            "buys6": [t for kk, t in buys if kk < 126]}


def maxwin(ev, lo, hi):
    """most failures in any WIN-session window among sessions lo <= k < hi."""
    ks = sorted(k for k in ev if lo <= k < hi)
    best = 0
    j = 0
    for i in range(len(ks)):
        while ks[i] - ks[j] >= WIN:
            j += 1
        best = max(best, i - j + 1)
    return best


def summarize2(rows):
    base = F.summarize([{**r, "live6": False, "live12": False, "buy0": [], "buys6": r["buys6"]} for r in rows])
    n6 = np.array([r["o6"] - r["f6"] for r in rows])
    out = {k: base[k] for k in ("net6", "per_month", "p10_6", "owner6", "fees6", "pays6", "net12", "p10_12", "net24", "corvette_med_months",
                                "corvette_6m", "corvette_12m", "corvette_24m")}
    out["per_month12"] = round(base["net12"] / 12)
    out["p10_net6_check"] = round(float(np.percentile(n6, 10)))
    out["p5_6"] = round(float(np.percentile(n6, 5)))
    out["lu_owner6"] = round(float(np.mean([r["lu6"] for r in rows])))
    out["lu_buys6"] = round(float(np.mean([r["n_lu_buys6"] for r in rows])), 2)
    out["loss_paths6"] = round(100.0 * float(np.mean(n6 < 0)), 1)
    for tag, lo, hi in (("6m", 0, 126), ("24m", 0, 504)):
        for name, flt in (("all", lambda f: True), ("fund", lambda f: f[1] == "F"), ("lucid", lambda f: f[2] == "LU")):
            w = [maxwin([f[0] for f in r["fails"] if flt(f)], lo, hi) for r in rows]
            out[f"p3_{name}_{tag}"] = round(100.0 * float(np.mean([x >= 3 for x in w])), 1)
            out[f"win_{name}_{tag}"] = round(float(np.mean(w)), 2)
    day = [max([sum(1 for f in r["fails"] if f[0] == k) for k in {f[0] for f in r["fails"] if f[0] < 126}] or [0]) for r in rows]
    out["max_same_day_fails6"] = round(float(np.mean(day)), 2)
    out["p2_same_day6"] = round(100.0 * float(np.mean([d >= 2 for d in day])), 1)
    out["fails6"] = round(float(np.mean([sum(1 for f in r["fails"] if f[0] < 126) for r in rows])), 2)
    return out


_PATHS = {}


def job(a):
    budget, n_lu, order, price, span, n = a
    if span not in _PATHS:
        _PATHS[span] = U.mc_paths(SOA.data()["S"], span, n, length=F.LEN, seed=23)
    rows = [run_path2(seq, budget, n_lu, order, price) for seq in _PATHS[span]]
    return a, summarize2(rows)


def grid(part, n):
    g = []
    if part in ("main", "check"):
        for b in BUDGETS:
            g.append((b, 0, "LU", LU_PRICE))
            for nl, o in itertools.product(NS[1:], ORDERS):
                g.append((b, nl, o, LU_PRICE))
    else:
        for b, nl, o, p in itertools.product(BUDGETS, NS[1:], ORDERS, (LU_PRICE - 50, LU_PRICE + 50)):
            g.append((b, nl, o, p))
    if part == "check":
        g = [(300, 0, "LU", LU_PRICE)]
    return [(*x, s, n) for x in g for s in R.SPANS]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--part", default="main")
    a = ap.parse_args(argv)
    t0 = time.time()
    out = {}
    with Pool(a.jobs) as pool:
        for key, res in pool.imap_unordered(job, grid(a.part, a.n)):
            b, nl, o, p, sp, _ = key
            out.setdefault(f"${b}/mo | N={nl} | {o}-first | LU ${p:g}", {})[sp] = res
            print(f"${b} N={nl} {o:4s} ${p:g} {sp:3s} net6 ${res['net6']} p10 ${res['p10_6']} fees ${res['fees6']} corv {res['corvette_med_months']} "
                  f"p3all6 {res['p3_all_6m']}% [{time.time() - t0:.0f}s]", flush=True)
    json.dump({"n": a.n, "fleets_counted": len(out), "lu_price_assumed": LU_PRICE, "rows": out},
              open(os.path.join(HERE, f"results_v2_{a.part}.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
