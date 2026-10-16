"""Regime-conditional exits: on trending days (10-day efficiency > 0.45) move to break-even earlier and/or cap the target
nearer, while rotational days keep the full model. Goal: keep the good-regime profit, shrink the bad-regime loss."""
from multiprocessing import Pool

from study_be import SEGS, run

V = [("current", {}),
     ("trend: BE 0.5R", {"be_at_r_trending": 0.5}), ("trend: BE 0.75R", {"be_at_r_trending": 0.75}),
     ("trend: cap 1.5R", {"max_rr_trending": 1.5}), ("trend: cap 2R", {"max_rr_trending": 2.0}), ("trend: cap 2.5R", {"max_rr_trending": 2.5}),
     ("trend: BE 0.5R + cap 2R", {"be_at_r_trending": 0.5, "max_rr_trending": 2.0}),
     ("trend: BE 0.5R + cap 2.5R", {"be_at_r_trending": 0.5, "max_rr_trending": 2.5}),
     ("trend: BE 0.5R + cap 2R, full size", {"be_at_r_trending": 0.5, "max_rr_trending": 2.0, "regime_mode": "full"}),
     ("trend: BE 0.5R, full size", {"be_at_r_trending": 0.5, "regime_mode": "full"}),
     ("threshold 0.40: BE 0.5R + cap 2R", {"be_at_r_trending": 0.5, "max_rr_trending": 2.0, "regime_er10_max": 0.40}),
     ("threshold 0.50: BE 0.5R + cap 2R", {"be_at_r_trending": 0.5, "max_rr_trending": 2.0, "regime_er10_max": 0.50})]

if __name__ == "__main__":
    with Pool(8) as pool:
        out = pool.map(run, V)
    print(f"{'variant':36s} | " + " | ".join(f"{l:44s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:36s} | " + " | ".join(f"{x:44s}" for x in o))
