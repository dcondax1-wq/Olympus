"""Exit-management + confluence-pruning study (in-sample vs out-of-sample, NQ with ES cross-check).
python study_exits.py
"""
from multiprocessing import Pool

import numpy as np

from engine import backtest

SPLIT = "2026-09-22"


def seg(trs):
    if not trs:
        return {"n": 0, "r": 0.0, "pf": 0.0, "net": 0.0}
    pnl = np.array([t["pnl"] for t in trs]); r = np.array([t["pnl_r"] for t in trs])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    return {"n": len(trs), "r": float(r.mean()), "pf": float(gp / gl) if gl else 9.99, "net": float(pnl.sum())}


def run(job):
    group, name, sym, p = job
    r = backtest.run(sym, "5m", p, light=True)
    tr = r["trades"]
    return group, name, sym, seg([t for t in tr if t["day"] < SPLIT]), seg([t for t in tr if t["day"] >= SPLIT]), seg(tr), r["stats"]["max_dd"]


GROUPS = {
    "PRUNE": [
        ("current", {}),
        ("cut protected", {"w_protected": 0}),
        ("cut SMT", {"w_smt": 0}),
        ("cut quality", {"w_quality": 0}),
        ("cut protected+SMT+quality", {"w_protected": 0, "w_smt": 0, "w_quality": 0}),
        ("lean: htf+lrl+pd only, score>=1", {"w_protected": 0, "w_smt": 0, "w_quality": 0, "min_score": 1}),
        ("lean, score>=0", {"w_protected": 0, "w_smt": 0, "w_quality": 0, "min_score": 0}),
        ("lean, score>=2", {"w_protected": 0, "w_smt": 0, "w_quality": 0, "min_score": 2}),
        ("lean + m15 penalty", {"w_protected": 0, "w_smt": 0, "w_quality": 0, "w_m15": -1}),
        ("current + m15 penalty", {"w_m15": -1}),
    ],
    "TARGET": [
        ("DOL 1.5-5R (current)", {}),
        ("DOL cap 3R", {"max_rr": 3}),
        ("DOL cap 4R", {"max_rr": 4}),
        ("DOL cap 6R", {"max_rr": 6}),
        ("DOL min 1R", {"min_rr": 1.0}),
        ("DOL min 2R", {"min_rr": 2.0}),
        ("next DOL", {"target_mode": "dol_next"}),
        ("fixed 1.5R", {"target_mode": "fixed", "fallback_rr": 1.5}),
        ("fixed 2R", {"target_mode": "fixed", "fallback_rr": 2.0}),
        ("fixed 3R", {"target_mode": "fixed", "fallback_rr": 3.0}),
        ("no AMT targets", {"amt_targets": False}),
    ],
    "STOP": [
        ("swing, buffer x1 (current)", {}),
        ("buffer x0.5", {"stop_buffer_mult": 0.5}),
        ("buffer x2", {"stop_buffer_mult": 2.0}),
        ("buffer x3", {"stop_buffer_mult": 3.0}),
        ("IFVG stop", {"stop_mode": "ifvg"}),
        ("min stop 6", {"spec": {"min_stop": 6}}),
        ("min stop 15", {"spec": {"min_stop": 15}}),
        ("max stop 40", {"spec": {"max_stop": 40}}),
        ("max stop 80", {"spec": {"max_stop": 80}}),
    ],
    "PARTIAL": [
        ("none (current)", {}),
        ("50% @1R + BE", {"partial_pct": 0.5, "partial_r": 1.0, "be_after_partial": True}),
        ("50% @1R no BE", {"partial_pct": 0.5, "partial_r": 1.0, "be_after_partial": False}),
        ("33% @1R no BE", {"partial_pct": 0.34, "partial_r": 1.0, "be_after_partial": False}),
        ("50% @1.5R no BE", {"partial_pct": 0.5, "partial_r": 1.5, "be_after_partial": False}),
        ("50% @2R no BE", {"partial_pct": 0.5, "partial_r": 2.0, "be_after_partial": False}),
        ("50% @2R + BE", {"partial_pct": 0.5, "partial_r": 2.0, "be_after_partial": True}),
        ("50% @first pool no BE", {"partial_pct": 0.5, "partial_at": "pool", "be_after_partial": False}),
        ("50% @first pool + BE", {"partial_pct": 0.5, "partial_at": "pool", "be_after_partial": True}),
        ("33% @first pool no BE", {"partial_pct": 0.34, "partial_at": "pool", "be_after_partial": False}),
    ],
    "MANAGE": [
        ("hold to target (current)", {}),
        ("BE at 1R", {"be_at_r": 1.0}),
        ("BE at 1.5R", {"be_at_r": 1.5}),
        ("BE at 2R", {"be_at_r": 2.0}),
        ("R-trail 1R from 2R", {"trail_mode": "r", "trail_start_r": 2.0, "trail_r": 1.0}),
        ("R-trail 1.5R from 2.5R", {"trail_mode": "r", "trail_start_r": 2.5, "trail_r": 1.5}),
        ("swing trail from 1R", {"trail_mode": "swing", "trail_start_r": 1.0}),
        ("swing trail from 2R", {"trail_mode": "swing", "trail_start_r": 2.0}),
        ("time stop 30m", {"time_stop_min": 30}),
        ("time stop 60m", {"time_stop_min": 60}),
        ("time stop 90m", {"time_stop_min": 90}),
    ],
}


def anatomy():
    r = backtest.run("NQ", "5m", {}, light=True)
    tr = r["trades"]
    mfe = np.array([t["mfe"] for t in tr]); mae = np.array([t["mae"] for t in tr]); pr = np.array([t["pnl_r"] for t in tr])
    print("TRADE ANATOMY (NQ, current config)")
    for x in (0.5, 1, 1.5, 2, 3, 4):
        print(f"  reached +{x}R: {np.mean(mfe >= x) * 100:5.1f}%   of losers: {np.mean(mfe[pr <= 0] >= x) * 100:5.1f}%")
    w = pr > 0
    print(f"  winners' MAE: median {np.median(mae[w]):.2f}R, 80th pct {np.percentile(mae[w], 80):.2f}R, max {mae[w].max():.2f}R")
    print(f"  losers' MFE: median {np.median(mfe[~w]):.2f}R")
    # fixed-target counterfactual from MFE (stop = -1R when MFE never reached X)
    for X in (1, 1.5, 2, 2.5, 3, 4, 5):
        rr = np.where(mfe >= X, X, np.minimum(pr, 0) if True else pr)
        print(f"  counterfactual fixed {X}R (MFE-based): avg {rr.mean():+.2f}R")
    print()


if __name__ == "__main__":
    anatomy()
    jobs = [(g, n, s, p) for g, V in GROUPS.items() for n, p in V for s in ("NQ", "ES")]
    with Pool(10) as pool:
        out = pool.map(run, jobs)
    res = {}
    for g, n, s, a, b, c, dd in out:
        res.setdefault(g, {}).setdefault(n, {})[s] = (a, b, c, dd)
    f = lambda z: f"{z['n']:3d}t {z['r']:+.2f}R pf{z['pf']:4.2f}"
    for g, V in GROUPS.items():
        print(f"===== {g} =====")
        print(f"{'variant':34s} | {'NQ in-sample':20s} | {'NQ out-of-sample':20s} | {'NQ all':20s} {'net':>7s} {'maxDD':>7s} | {'ES all':20s}")
        for n, _ in V:
            a, b, c, dd = res[g][n]["NQ"]
            ea, eb, ec, edd = res[g][n]["ES"]
            print(f"{n:34s} | {f(a):20s} | {f(b):20s} | {f(c):20s} {c['net']:+7.0f} {dd:7.0f} | {f(ec):20s}")
        print()
