"""Does the A+..D checklist grade predict outcomes in every period? Does sizing by it beat conviction sizing?"""
from multiprocessing import Pool

import numpy as np

from engine import backtest

SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
WIDE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0, "max_trades_day": 9, "stop_after_win": False, "min_score": -99}
MULT = {"A+": 1.5, "A": 1.25, "B": 1.0, "C": 0.75, "D": 0.5}
V = [("conviction sizing (current)", {}), ("grade sizing", {"grade_sizing": True}),
     ("grade sizing, skip D", {"grade_sizing": True, "grade_skip": "D"}), ("flat size", {"conviction_step": 0})]


def run(job):
    name, p = job
    out = []
    for label, sym, a, z in SEGS:
        r = backtest.run(sym, "5m", {**p, "dd_aware": False, "daily_max_loss": 1e9}, light=True)
        tr = [t for t in r["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        if not tr:
            out.append("0t"); continue
        pnl = np.array([t["pnl"] for t in tr]); risk = np.array([t["risk_pts"] * t["qty"] * (20 if 'NQ' in sym else 50) / 10 for t in tr])
        gp, gl = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
        weeks = len({t["day"] for t in r["trades"]}) and (len([d for d in r["days"] if (not a or d["date"] >= a) and (not z or d["date"] <= z)]) / 5)
        out.append(f"{len(tr):3d}t {len(tr) / max(weeks, 1e-9):.1f}/wk ${pnl.sum():+7.0f} PF {gp / gl if gl else 9.99:4.2f}")
    return name, out


if __name__ == "__main__":
    print("Avg R of every candidate by grade")
    for label, sym, a, z in SEGS:
        sh = [s for s in backtest.run(sym, "5m", WIDE)["shadows"] if (not a or s["day"] >= a) and (not z or s["day"] <= z)]
        row = []
        for g in ("A+", "A", "B", "C", "D"):
            rs = [s["r"] for s in sh if s["grade"] == g]
            row.append(f"{g}: {np.mean(rs):+.2f} (n={len(rs)})" if rs else f"{g}: -")
        pts = np.array([s["grade_points"] for s in sh]); rr = np.array([s["r"] for s in sh])
        corr = np.corrcoef(pts, rr)[0, 1] if len(sh) > 2 else float("nan")
        print(f"  {label:12s} " + " | ".join(row) + f" | points-vs-R corr {corr:+.2f}")
    with Pool(4) as pool:
        out = pool.map(run, V)
    print(f"\n{'sizing':30s} | " + " | ".join(f"{l:34s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:30s} | " + " | ".join(f"{x:34s}" for x in o))
