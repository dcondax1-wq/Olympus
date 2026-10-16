"""Confluence discovery round 2: find sign-stable edges (both halves, NQ alone AND pooled NQ+ES), then test them as weights."""
from multiprocessing import Pool

import numpy as np

from engine import backtest
from study_exits import run, SPLIT

WEIGHT = {"shallow_raid": "w_shallow", "disp_strong": "w_disp", "fast_reclaim": "w_fast", "first_hour": "w_first",
          "multi_sweep": "w_multi", "major_swept": "w_major", "vol_climax": "w_vol", "vwap_disc": "w_vwap",
          "keylevel": "w_keylevel", "midnight": "w_midnight", "dol_align": "w_dol", "smt": "w_smt", "quality": "w_quality",
          "protected": "w_protected", "amt": "w_amt"}


def edges(sh, k):
    out = []
    for S in ([s for s in sh if s["day"] < SPLIT], [s for s in sh if s["day"] >= SPLIT]):
        on = [s["r"] for s in S if s["f"].get(k, 0) > 0]; off = [s["r"] for s in S if s["f"].get(k, 0) <= 0]
        out.append((np.mean(on) - np.mean(off)) if len(on) >= 3 and len(off) >= 3 else None)
    return out


if __name__ == "__main__":
    wide = {"max_trades_day": 9, "stop_after_win": False, "min_score": -99}
    nq = backtest.run("NQ", "5m", wide)["shadows"]
    es = backtest.run("ES", "5m", wide)["shadows"]
    print(f"candidates: NQ {len(nq)}  ES {len(es)}")
    stable = {}
    print(f"\n{'feature':14s} | {'NQ IS':>6s} {'NQ OOS':>6s} | {'pool IS':>7s} {'pool OOS':>8s} | verdict")
    for k in WEIGHT:
        a = edges(nq, k); b = edges(nq + es, k)
        vals = [x for x in a + b if x is not None]
        verdict = ""
        if len(vals) == 4 and (all(x > 0.1 for x in vals) or all(x < -0.1 for x in vals)):
            verdict = "STABLE +" if vals[0] > 0 else "STABLE -"
            stable[k] = 1 if vals[0] > 0 else -1
        fmt = lambda x: "   -  " if x is None else f"{x:+.2f}"
        print(f"{k:14s} | {fmt(a[0]):>6s} {fmt(a[1]):>6s} | {fmt(b[0]):>7s} {fmt(b[1]):>8s} | {verdict}")
    print("\nstable:", stable)
    V = [("current", {})]
    for k, sgn in stable.items():
        V.append((f"{WEIGHT[k]}={sgn:+d}", {WEIGHT[k]: sgn}))
    if len(stable) > 1:
        V.append(("all stable", {WEIGHT[k]: s for k, s in stable.items()}))
        V.append(("all stable, score>=2", {**{WEIGHT[k]: s for k, s in stable.items()}, "min_score": 2}))
    jobs = [("C", n, s, p) for n, p in V for s in ("NQ", "ES")]
    with Pool(10) as pool:
        out = pool.map(run, jobs)
    res = {}
    for g, n, s, a, b, c, dd in out:
        res.setdefault(n, {})[s] = (a, b, c, dd)
    f = lambda z: f"{z['n']:3d}t {z['r']:+.2f}R pf{z['pf']:4.2f}"
    print(f"\n{'variant':24s} | {'NQ in-sample':20s} | {'NQ out-of-sample':20s} | {'NQ all':20s} {'net':>7s} {'maxDD':>7s} | ES all")
    for n, _ in V:
        a, b, c, dd = res[n]["NQ"]
        print(f"{n:24s} | {f(a):20s} | {f(b):20s} | {f(c):20s} {c['net']:+7.0f} {dd:7.0f} | {f(res[n]['ES'][2])}")
