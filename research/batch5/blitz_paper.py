"""(D) BLITZ paper vs its backtest (research/batch5/DESIGN.md). PAPER RESEARCH ONLY.
The PC's real paper ledger (data/blitz_state.json) is not in the cloud, so this replays the live paper code (engine/blitz.
replay_2026) on the PC's own bars from the PC bot's start (2026-10-19, assumed) = what the paper shadow should have done.
    python -X utf8 research/batch5/blitz_paper.py -> research/batch5/blitz_paper.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT = os.path.join(HERE, "blitz_paper.json")
START = "2026-10-19"


def main():
    from engine import blitz as BZ
    S = BZ.replay_2026(first_run=START)
    L = [r for r in S["ledger"] if r.get("exit_kind") not in (None, "OPEN") and r.get("r") is not None]
    full = BZ.replay_2026(first_run="2026-01-01")
    F = [r for r in full["ledger"] if r.get("exit_kind") not in (None, "OPEN") and r.get("r") is not None and r["day"] < START]
    r = np.array([float(x["r"]) for x in L]); rb = np.array([float(x["r"]) for x in F])
    B = json.load(open(os.path.join(ROOT, "research", "health", "bands.json"), encoding="utf-8"))["bots"]["BLITZ"]["bands"]["2026"]
    rng = np.random.default_rng(5)
    boot = [float(rng.choice(rb, size=len(r)).mean()) for _ in range(5000)] if len(r) and len(rb) else []
    m = float(r.mean()) if len(r) else None
    roll = float(r[-20:].mean()) if len(r) >= 5 else None
    res = {"made": "2026-11-26", "start_assumed": START, "last_day": L[-1]["day"] if L else None,
           "source": "engine/blitz.replay_2026 on data/NQ_1m.csv (the PC's bars after Oct 16); the PC's real paper ledger is NOT in the cloud",
           "paper": {"n": len(r), "win_pct": round(100 * float((r > 0).mean()), 1) if len(r) else None, "mean_r": round(m, 3) if m is not None else None,
                     "sum_r": round(float(r.sum()), 2), "usd_150": round(float(r.sum()) * 150), "last20_mean_r": round(roll, 3) if roll is not None else None},
           "backtest_2026_before_start": {"n": len(rb), "mean_r": round(float(rb.mean()), 3), "win_pct": round(100 * float((rb > 0).mean()), 1)},
           "band_2026_rolling20": {k: B.get(k) for k in ("p5", "p50", "p95")},
           "pct_of_same_size_backtest_samples_at_or_below": round(100 * float(np.mean(np.array(boot) <= m)), 1) if boot else None}
    inside = roll is not None and B["p5"] <= roll <= B["p95"]
    res["verdict"] = ("too few paper trades to judge" if roll is None else
                      "BEHAVING LIKE THE BACKTEST (last-20 mean R inside the 2026 5-95% band)" if inside else
                      "OUTSIDE its 2026 backtest band")
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
