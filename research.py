"""Robustness research: grid over model design choices, scored in-sample, verified out-of-sample.

python research.py [split_date]   -> writes reports/research.csv and prints the top robust configs
"""
import csv
import itertools
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

from engine import backtest

SPLIT = sys.argv[1] if len(sys.argv) > 1 else "2026-09-22"
DATASETS = [("NQ", "5m"), ("ES", "5m")]

GRID = {
    "min_score": [0, 1, 2, 3],
    "stop_mode": ["swing", "ifvg"],
    "partial_pct": [0.0, 0.5],
    "min_rr": [1.5, 2.0],
    "entry_windows": [[[570, 690]], [[570, 660]], [[570, 690], [810, 930]]],
    "arm_minor": [False, True],
    "max_rr": [3.0, 5.0],
}


def seg_stats(trades):
    if not trades:
        return {"n": 0, "net": 0.0, "pf": 0.0, "wr": 0.0, "avg_r": 0.0}
    pnl = np.array([t["pnl"] for t in trades])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    return {"n": len(pnl), "net": round(float(pnl.sum()), 1), "pf": round(float(gp / gl), 2) if gl else 9.99,
            "wr": round(float((pnl > 0).mean() * 100), 1), "avg_r": round(float(np.mean([t["pnl_r"] for t in trades])), 3)}


def evaluate(combo):
    params = dict(zip(GRID.keys(), combo))
    row = {"params": json.dumps(params)}
    for sym, tf in DATASETS:
        r = backtest.run(sym, tf, params, light=True)
        tr = r["trades"]
        ins = seg_stats([t for t in tr if t["day"] < SPLIT])
        oos = seg_stats([t for t in tr if t["day"] >= SPLIT])
        for k, v in ins.items():
            row[f"{sym}_is_{k}"] = v
        for k, v in oos.items():
            row[f"{sym}_oos_{k}"] = v
    return row


def main():
    combos = list(itertools.product(*GRID.values()))
    print(f"{len(combos)} configs x {len(DATASETS)} datasets")
    with Pool(max(1, os.cpu_count() - 1)) as pool:
        rows = pool.map(evaluate, combos, chunksize=4)
    os.makedirs("reports", exist_ok=True)
    with open("reports/research.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # robust score: in-sample avg R summed across both instruments, penalise low trade counts
    def is_score(r):
        n = r["NQ_is_n"] + r["ES_is_n"]
        if n < 15:
            return -9
        return (r["NQ_is_avg_r"] * r["NQ_is_n"] + r["ES_is_avg_r"] * r["ES_is_n"]) / np.sqrt(n)

    rows.sort(key=is_score, reverse=True)
    print("\nTOP 25 by in-sample (both instruments) -> out-of-sample check")
    for r in rows[:25]:
        print(f"IS NQ {r['NQ_is_n']:3d}t {r['NQ_is_avg_r']:+.2f}R pf{r['NQ_is_pf']:5.2f} | ES {r['ES_is_n']:3d}t {r['ES_is_avg_r']:+.2f}R pf{r['ES_is_pf']:5.2f}"
              f" || OOS NQ {r['NQ_oos_n']:3d}t {r['NQ_oos_avg_r']:+.2f}R ${r['NQ_oos_net']:+7.0f} | ES {r['ES_oos_n']:3d}t {r['ES_oos_avg_r']:+.2f}R ${r['ES_oos_net']:+7.0f}  {r['params']}")
    # how many configs are profitable OOS overall (is the edge broad or a fluke?)
    pos_nq = sum(1 for r in rows if r["NQ_oos_net"] > 0)
    pos_es = sum(1 for r in rows if r["ES_oos_net"] > 0)
    print(f"\nconfigs profitable OOS: NQ {pos_nq}/{len(rows)}  ES {pos_es}/{len(rows)}")
    top = rows[:25]
    print("top-25 OOS mean avgR: NQ", round(np.mean([r['NQ_oos_avg_r'] for r in top]), 3),
          "ES", round(np.mean([r['ES_oos_avg_r'] for r in top]), 3))


if __name__ == "__main__":
    main()
