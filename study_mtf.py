"""Multi-timeframe confluence study.

1) feature study on shadow trades (every candidate signal, taken or not), in-sample vs out-of-sample
2) MTF variants (weights / gates / highest-TF IFVG / learner) scored IS vs OOS on real trades
python study_mtf.py [split]
"""
import json
import sys
from multiprocessing import Pool

import numpy as np

from engine import backtest, learn

SPLIT = sys.argv[1] if len(sys.argv) > 1 else "2026-09-22"


def seg(trs):
    if not trs:
        return "  0t        "
    pnl = np.array([t["pnl"] for t in trs]); r = np.array([t["pnl_r"] for t in trs])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    return f"{len(trs):3d}t {r.mean():+.2f}R pf{(gp / gl if gl else 9.99):4.2f} ${pnl.sum():+6.0f}"


def run(name_params):
    name, params = name_params
    r = backtest.run("NQ", "5m", params, light=True)
    tr = r["trades"]
    return name, seg([t for t in tr if t["day"] < SPLIT]), seg([t for t in tr if t["day"] >= SPLIT]), seg(tr), r["stats"]["trades_per_week"]


def main():
    from engine.model import Engine, merge_params
    base = backtest.run("NQ", "5m", {"max_trades_day": 9, "stop_after_win": False, "min_score": -99}, light=False)
    sh = base["shadows"]
    rs = np.array([s["r"] for s in sh])
    print(f"shadow candidates: {len(sh)}  avg R {rs.mean():+.3f}  win {np.mean(rs > 0) * 100:.1f}%")
    fs = learn.feature_study([{**s, "f": s["f"]} for s in sh], SPLIT)
    print(f"\n{'feature':12s} | {'IS on n':>7s} {'R on':>6s} {'R off':>6s} {'edge':>6s} | {'OOS on n':>8s} {'R on':>6s} {'R off':>6s} {'edge':>6s}")
    for row in fs:
        f = lambda k: '  -   ' if row[k] is None else f"{row[k]:+.2f}"
        print(f"{row['feature']:12s} | {row['is_n_on']:7d} {f('is_r_on'):>6s} {f('is_r_off'):>6s} {f('is_edge'):>6s} | "
              f"{row['oos_n_on']:8d} {f('oos_r_on'):>6s} {f('oos_r_off'):>6s} {f('oos_edge'):>6s}")
    # mtf_net buckets
    print("\nMTF net alignment buckets (shadows):")
    for lo, hi in ((-4, -2), (-1, -1), (0, 0), (1, 1), (2, 4)):
        g = [s for s in sh if lo <= s["f"]["mtf_net"] <= hi]
        gi = [s["r"] for s in g if s["day"] < SPLIT]; go = [s["r"] for s in g if s["day"] >= SPLIT]
        print(f"  net {lo:+d}..{hi:+d}: IS n={len(gi):3d} R={np.mean(gi) if gi else 0:+.2f} | OOS n={len(go):3d} R={np.mean(go) if go else 0:+.2f}")

    V = [
        ("baseline", {}),
        ("highest-TF IFVG", {"ifvg_tf": "highest"}),
        ("w_mtf=1", {"w_mtf": 1}),
        ("w_mtf=1 min_score 2", {"w_mtf": 1, "min_score": 2}),
        ("mtf_gate 0", {"mtf_gate": 0}),
        ("mtf_gate 1", {"mtf_gate": 1}),
        ("mtf_gate -1", {"mtf_gate": -1}),
        ("w_m15=1", {"w_m15": 1}),
        ("w_pd=1", {"w_pd": 1}),
        ("w_midnight=1", {"w_midnight": 1}),
        ("w_keylevel=1", {"w_keylevel": 1}),
        ("all MTF w=1, score>=2", {"w_mtf": 1, "w_m15": 1, "w_pd": 1, "w_midnight": 1, "w_keylevel": 1, "min_score": 2}),
        ("all MTF w=1, score>=3", {"w_mtf": 1, "w_m15": 1, "w_pd": 1, "w_midnight": 1, "w_keylevel": 1, "min_score": 3}),
        ("learner thr 0", {"learn": True}),
        ("learner thr 0.2", {"learn": True, "learn_threshold": 0.2}),
        ("learner lam 20", {"learn": True, "learn_lambda": 20}),
        ("learner min 50", {"learn": True, "learn_min": 50}),
    ]
    with Pool(8) as pool:
        out = pool.map(run, V)
    print(f"\n{'variant':26s} | {'IN-SAMPLE':28s} | {'OUT-OF-SAMPLE':28s} | {'ALL':28s} | t/wk")
    for name, a, b, c, tpw in out:
        print(f"{name:26s} | {a:28s} | {b:28s} | {c:28s} | {tpw}")


if __name__ == "__main__":
    main()
