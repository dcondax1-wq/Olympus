"""Draw-on-liquidity study: DOL features on shadow trades + DOL target / filter variants (IS vs OOS, ES cross-check)."""
from multiprocessing import Pool

import numpy as np

from engine import backtest, learn
from study_exits import run, SPLIT

V = [
    ("current (next DOL, any pool)", {}),
    ("nearest DOL", {"target_mode": "dol"}),
    ("nearest MAJOR pool", {"target_mode": "major"}),
    ("next MAJOR pool", {"target_mode": "major_next"}),
    ("w_dol=1 (toward major liq)", {"w_dol": 1}),
    ("w_dol=1, score>=2", {"w_dol": 1, "min_score": 2}),
    ("major target + w_dol=1", {"target_mode": "major", "w_dol": 1}),
    ("min_rr 2 + next DOL", {"min_rr": 2.0}),
]

if __name__ == "__main__":
    pooled = []
    for sym in ("NQ", "ES"):
        r = backtest.run(sym, "5m", {"max_trades_day": 9, "stop_after_win": False, "min_score": -99})
        sh = r["shadows"]
        pooled += sh
        print(f"\n{sym} DOL features ({len(sh)} candidates)")
        for k in ("dol_align", "tgt_major", "dol_room3"):
            for part, S in (("IS ", [s for s in sh if s["day"] < SPLIT]), ("OOS", [s for s in sh if s["day"] >= SPLIT])):
                on = [s["r"] for s in S if s["f"][k] > 0]; off = [s["r"] for s in S if s["f"][k] <= 0]
                print(f"  {k:10s} {part} on n={len(on):3d} R={np.mean(on) if on else 0:+.2f} | off n={len(off):3d} R={np.mean(off) if off else 0:+.2f}")
    jobs = [("DOL", n, s, p) for n, p in V for s in ("NQ", "ES")]
    with Pool(10) as pool:
        out = pool.map(run, jobs)
    res = {}
    for g, n, s, a, b, c, dd in out:
        res.setdefault(n, {})[s] = (a, b, c, dd)
    f = lambda z: f"{z['n']:3d}t {z['r']:+.2f}R pf{z['pf']:4.2f}"
    print(f"\n{'variant':30s} | {'NQ in-sample':20s} | {'NQ out-of-sample':20s} | {'NQ all':20s} {'net':>7s} {'maxDD':>7s} | ES all")
    for n, _ in V:
        a, b, c, dd = res[n]["NQ"]
        print(f"{n:30s} | {f(a):20s} | {f(b):20s} | {f(c):20s} {c['net']:+7.0f} {dd:7.0f} | {f(res[n]['ES'][2])}")
