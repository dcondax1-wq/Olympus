#!/usr/bin/env python3
"""Deep dive on the one candidate that looked alive in study.py: 'buy where a lognormal vol model disagrees with the quote by
>= margin, ~8 minutes before a 15-minute BTC up/down market closes'.  Tests whether it survives: execution delay, a spread cap,
neighbouring horizons, the other asset (ETH), the walk-forward split (rule frozen on TRAIN only) and multiple-testing.

    python research/kalshi_edge_B/study2.py [KXBTC15M|KXETH15M ...]  -> results_candidate.json
"""
import json, math, os, sys, datetime as dt
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from study import prep, quote, model_prob, basis_sigma, summarise, split_arrays, buy, day

HERE = os.path.dirname(os.path.abspath(__file__))
VOLS = []
NPERM = int(os.environ.get("NPERM", "200"))


def run(rows, spot, sig_b, tau, mg, kv=1.0, delay=0, spread_cap=1.0, only=None):
    prof, cost, wins, grp, tm, sides = [], [], [], [], [], []
    for r in rows:
        q0 = quote(r, tau)
        qx = quote(r, tau - delay) if delay else q0
        ts = r["close"] - tau * 60
        S, sg = spot.at(ts), spot.vol(ts)
        if not q0 or not qx or not S or not sg or r["k"] is None:
            continue
        if qx[1] - qx[0] > spread_cap:
            continue
        p = model_prob(S, r["k"], sg, tau, sig_b, kv)
        b, a = q0
        ey, en = p - a - fee(a), (1 - p) - (1 - b) - fee(1 - b)  # signal from the quote at signal time
        if ey >= en and ey > mg:
            side = "yes"
        elif en > mg:
            side = "no"
        else:
            continue
        if only and side != only:
            continue
        px = qx[1] if side == "yes" else 1 - qx[0]  # price actually paid after the delay
        pr, w = buy(r, side, px)
        prof.append(pr); cost.append(px); wins.append(w); grp.append(day(r)); tm.append(r["close"]); sides.append(side)
        for c in r["c"]:
            if int(c[0]) == int(r["close"] - tau * 60):
                VOLS.append(c[4] or 0)
    return prof, cost, wins, grp, tm, sides


def cell(rows, spot, sig_b, **kw):
    prof, cost, wins, grp, tm, sides = run(rows, spot, sig_b, **kw)
    out = {"all": summarise(prof, cost, wins, grp), **split_arrays(prof, cost, wins, grp, tm, rows)}
    out["yes_share"] = round(sides.count("yes") / max(len(sides), 1), 3)
    return out


def main():
    names = sys.argv[1:] or ["KXBTC15M"]
    res = {}
    for nm in names:
        spot = Spot("BTC" if "BTC" in nm else "ETH")
        rows = prep(nm + ".json.gz")
        sig_b, _ = basis_sigma(rows, spot)
        R = {"n_markets": len(rows), "sig_b": sig_b, "grid": [], "n_cells": 0}
        taus = [6, 7, 8, 9, 10, 12]
        mgs = [0.06, 0.08, 0.10, 0.12, 0.15]
        for tau in taus:
            for mg in mgs:
                c = cell(rows, spot, sig_b, tau=tau, mg=mg)
                c.update({"tau": tau, "margin": mg})
                R["grid"].append(c)
                R["n_cells"] += 1
        # rule frozen on TRAIN only: best train edge with n>=40
        cand = [c for c in R["grid"] if c["train"].get("n", 0) >= 40]
        best = max(cand, key=lambda c: c["train"]["edge"])
        R["frozen"] = {"tau": best["tau"], "margin": best["margin"], "train": best["train"], "val": best["val"], "test": best["test"]}
        # robustness of the frozen rule
        t, m = best["tau"], best["margin"]
        del VOLS[:]
        run(rows, spot, sig_b, tau=t, mg=m)
        R["signal_minute_volume_contracts"] = {"median": float(np.median(VOLS)), "p25": float(np.percentile(VOLS, 25)), "p75": float(np.percentile(VOLS, 75)), "n": len(VOLS)}
        R["delay"] = {str(d): cell(rows, spot, sig_b, tau=t, mg=m, delay=d) for d in (0, 1, 2)}
        R["spread_cap_3c"] = cell(rows, spot, sig_b, tau=t, mg=m, spread_cap=0.03)
        R["yes_only"] = cell(rows, spot, sig_b, tau=t, mg=m, only="yes")
        R["no_only"] = cell(rows, spot, sig_b, tau=t, mg=m, only="no")
        R["kv_0.9"] = cell(rows, spot, sig_b, tau=t, mg=m, kv=0.9)
        R["kv_1.2"] = cell(rows, spot, sig_b, tau=t, mg=m, kv=1.2)
        # permutation / multiple testing: shuffle outcomes within each day, re-take the best-of-grid train->test edge
        rng = np.random.default_rng(7)
        null_best = []
        by_day = {}
        for i, r in enumerate(rows):
            by_day.setdefault(day(r), []).append(i)
        orig = [r["win"] for r in rows]
        for it in range(NPERM):
            u = rng.random(len(rows))
            best_edge = -9
            for tau in taus:
                for i, r in enumerate(rows):  # efficient-market null: outcome ~ Bernoulli(quoted mid at this horizon)
                    qq = quote(r, tau)
                    r["win"] = (1 if u[i] < (qq[0] + qq[1]) / 2 else 0) if qq else orig[i]
                for mg in mgs:
                    prof, cost, wins, grp, tm, _ = run(rows, spot, sig_b, tau=tau, mg=mg)
                    if len(prof) < 40:
                        continue
                    best_edge = max(best_edge, float(np.mean(prof)))
            null_best.append(best_edge)
        for i, r in enumerate(rows):
            r["win"] = orig[i]
        obs_best = max(c["all"]["edge"] for c in R["grid"] if c["all"].get("n", 0) >= 40)
        R["permutation"] = {"iterations": len(null_best), "null_best_mean": round(float(np.mean(null_best)), 4),
                            "null_best_p95": round(float(np.percentile(null_best, 95)), 4), "null_best_max": round(float(max(null_best)), 4),
                            "observed_best_all": round(obs_best, 4),
                            "note": "efficient-market null: outcomes redrawn as Bernoulli(quoted mid) per horizon, same grid, best mean edge (n>=40) each time"}
        res[nm] = R
    json.dump(res, open(os.path.join(HERE, "results_candidate.json"), "w"), indent=1)
    for nm, R in res.items():
        print(nm, R["frozen"]["tau"], R["frozen"]["margin"], "train", R["frozen"]["train"].get("n"), R["frozen"]["train"].get("edge"),
              "val", R["frozen"]["val"].get("n"), R["frozen"]["val"].get("edge"), "test", R["frozen"]["test"].get("n"), R["frozen"]["test"].get("edge"))
        for k in ("delay", ):
            for d, c in R[k].items():
                print(" delay", d, c["all"].get("n"), c["all"].get("edge"), c["all"].get("ci"), "test", c["test"].get("n"), c["test"].get("edge"))
        for k in ("spread_cap_3c", "yes_only", "no_only", "kv_0.9", "kv_1.2"):
            print(" ", k, R[k]["all"].get("n"), R[k]["all"].get("edge"), R[k]["all"].get("ci"), "test", R[k]["test"].get("n"), R[k]["test"].get("edge"))
        print(" perm", R["permutation"])


if __name__ == "__main__":
    main()
