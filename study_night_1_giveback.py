"""Night study 1 - walk-forward honesty check of the 'giveback' exit signal.

Question: the giveback exit (trade reached +0.5R, then a bar closes back below entry -> leave) was adopted because it
improved all four periods. Was that luck of a few trades, or does it help in BOTH halves of every period, and is the
0.5R threshold knife-edge?

Method: real engine, flat sizing. Each period is cut in two halves by trading day (same number of days each side).
Variants: no giveback (exit_rules "") vs giveback at 0.3 / 0.4 / 0.5 (default) / 0.6 / 0.75 R.
Run: python study_night_1_giveback.py
"""
from multiprocessing import Pool

import numpy as np

from study_night_common import SEGS, run_both, seg_trades, metrics, fmt, md_table

V = [("no giveback", {"exit_rules": ""}),
     ("no giveback, learner off", {"exit_rules": "", "exit_learn": False}),
     ("giveback 0.3R", {"exit_rules": "giveback", "exit_giveback_r": 0.3}),
     ("giveback 0.4R", {"exit_rules": "giveback", "exit_giveback_r": 0.4}),
     ("giveback 0.5R (default)", {}),
     ("giveback 0.6R", {"exit_rules": "giveback", "exit_giveback_r": 0.6}),
     ("giveback 0.75R", {"exit_rules": "giveback", "exit_giveback_r": 0.75})]


def _job(job):
    name, p = job
    res = run_both(p)
    segs = seg_trades(res)
    out = {}
    for lab, (tr, dy) in segs.items():
        dates = [d["date"] for d in dy]
        mid = dates[len(dates) // 2]
        h1 = [t for t in tr if t["day"] < mid]; d1 = [d for d in dy if d["date"] < mid]
        h2 = [t for t in tr if t["day"] >= mid]; d2 = [d for d in dy if d["date"] >= mid]
        gb = [t for t in tr if t["exit_reason"] == "SIGNAL giveback"]
        out[lab] = {"full": metrics(tr, dy), "h1": metrics(h1, d1), "h2": metrics(h2, d2), "mid": mid,
                    "gb_n": len(gb), "gb_r": float(np.mean([t["pnl_r"] for t in gb])) if gb else 0.0,
                    "trades": [(t["day"], t["entry_t"], t["pnl"], t["pnl_r"], t["exit_reason"]) for t in tr]}
    return name, out


if __name__ == "__main__":
    with Pool(min(6, len(V))) as pool:
        out = dict(pool.map(_job, V))

    print("# Study 1 - giveback walk-forward\n")
    print("Cells: trades / trades-per-week / avg R / net $ / profit factor / max drawdown. Halves split by trading day.\n")
    for lab, *_ in SEGS:
        mid = out["giveback 0.5R (default)"][lab]["mid"]
        print(f"## {lab}  (half 1 = before {mid}, half 2 = from {mid})\n")
        rows = []
        for name, _ in V:
            o = out[name][lab]
            rows.append([name, fmt(o["full"]), fmt(o["h1"]), fmt(o["h2"]), f"{o['gb_n']} ({o['gb_r']:+.2f}R)"])
        print(md_table(rows, ["variant", "full period", "half 1", "half 2", "giveback exits (avg R)"]))
        print()

    # ---- does giveback beat no-giveback in each half? (8 half-periods)
    print("## Half-by-half scorecard: giveback net $ minus no-giveback net $\n")
    base = out["no giveback"]
    rows = []
    for name, _ in V[2:]:
        cells, wins, tot = [], 0, 0.0
        for lab, *_ in SEGS:
            for h in ("h1", "h2"):
                diff = out[name][lab][h]["net"] - base[lab][h]["net"]
                tot += diff
                wins += diff > 0
                cells.append(f"{diff:+.0f}")
        rows.append([name] + cells + [f"{wins}/8", f"{tot:+.0f}"])
    hdr = ["variant"] + [f"{lab} {h}" for lab, *_ in SEGS for h in ("H1", "H2")] + ["halves improved", "total"]
    print(md_table(rows, hdr))
    print()
    # ---- four-period totals and NQ 2026 check
    print("## Four-period totals\n")
    rows = []
    for name, _ in V:
        tot = sum(out[name][lab]["full"]["net"] for lab, *_ in SEGS)
        nq = out[name]["NQ 2026"]["full"]["net"]
        mn = min(out[name][lab]["full"]["tpw"] for lab, *_ in SEGS)
        rows.append([name, f"${tot:+,.0f}", f"${nq:+,.0f}", f"{mn:.1f}"])
    print(md_table(rows, ["variant", "four-period total", "NQ 2026 net", "min trades/wk"]))
