"""Exit-signal combos around the winner (giveback) + the walk-forward learner."""
from multiprocessing import Pool

from study_be import SEGS, run

G = {"exit_rules": "giveback"}
V = [("current", {}), ("giveback", G),
     ("giveback @0.3R", {**G, "exit_giveback_r": 0.3}), ("giveback @0.75R", {**G, "exit_giveback_r": 0.75}), ("giveback @1.0R", {**G, "exit_giveback_r": 1.0}),
     ("giveback + stall", {"exit_rules": "giveback,stall"}), ("giveback + opp_fvg", {"exit_rules": "giveback,opp_fvg"}),
     ("giveback + stall + opp_fvg", {"exit_rules": "giveback,stall,opp_fvg"}),
     ("giveback + learner 20/0.20", {**G, "exit_learn": True, "exit_learn_min": 20, "exit_learn_threshold": 0.20}),
     ("giveback + learner 12/0.15", {**G, "exit_learn": True}),
     ("giveback + BE 0.75R", {**G, "be_at_r": 0.75}), ("giveback, BE off", {**G, "be_at_r": 0}),
     ("giveback, time stop 45", {**G, "time_stop_min": 45})]

if __name__ == "__main__":
    with Pool(13) as pool:
        out = pool.map(run, V)
    print(f"{'variant':28s} | " + " | ".join(f"{l:44s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:28s} | " + " | ".join(f"{x:44s}" for x in o))
