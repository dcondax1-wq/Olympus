"""In-trade exit signals: (1) counterfactual value of each warning sign per period, (2) fixed rules and the walk-forward
exit learner tested in the real engine on every period."""
from multiprocessing import Pool

import numpy as np

from engine import backtest
from engine.model import Engine
from study_be import run

SEGS = [("NQ 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q1 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
WIDE = {"max_trades_day": 9, "stop_after_win": False, "min_score": -99, "daily_max_loss": 1e9, "dd_aware": False}


def _wide(sym):
    return sym, backtest.run(sym, "5m", WIDE, light=True)["trades"]


if __name__ == "__main__":
    with Pool(2) as pool:
        tr = dict(pool.map(_wide, ["NQ", "NQX"]))
    print("=== counterfactual value of leaving at the first firing (R gained vs holding) · wide config, taken trades ===")
    print(f"{'signal':13s} | " + " | ".join(f"{n:>22s}" for n, *_ in SEGS) + " | all")
    stable = []
    for name in Engine.EXIT_SIGNALS:
        cells, allg, signs = [], [], []
        for label, sym, a, z in SEGS:
            T = [t for t in tr[sym] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
            g = [t["xsig"][name]["gain"] for t in T if name in t.get("xsig", {}) and "gain" in t["xsig"][name]]
            allg += g
            if len(g) >= 4:
                m = float(np.mean(g)); signs.append(m)
                cells.append(f"{len(g):3d}/{len(T):3d} {m:+.2f}R {np.mean(np.array(g) > 0.1):3.0%}+")
            else:
                cells.append(f"{len(g):3d}/{len(T):3d}    -")
        a_ = np.array(allg) if allg else np.array([0.0])
        verdict = "STABLE+" if len(signs) >= 3 and all(s > 0.05 for s in signs) else ("STABLE-" if len(signs) >= 3 and all(s < -0.05 for s in signs) else "")
        if verdict == "STABLE+":
            stable.append(name)
        print(f"{name:13s} | " + " | ".join(f"{c:>22s}" for c in cells) + f" | {len(allg):3d} {a_.mean():+.2f}R  {verdict}")

    V = [("current", {})] + [(f"rule: {n}", {"exit_rules": n}) for n in Engine.EXIT_SIGNALS]
    if stable:
        V.append(("rules: all stable+", {"exit_rules": ",".join(stable)}))
    V += [("learner (12 / 0.15R)", {"exit_learn": True}), ("learner (8 / 0.10R)", {"exit_learn": True, "exit_learn_min": 8, "exit_learn_threshold": 0.10}),
          ("learner (20 / 0.20R)", {"exit_learn": True, "exit_learn_min": 20, "exit_learn_threshold": 0.20})]
    with Pool(10) as pool:
        out = pool.map(run, V)
    print(f"\n=== real engine, default config, flat sizing ===\n{'variant':24s} | " + " | ".join(f"{l:44s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:24s} | " + " | ".join(f"{x:44s}" for x in o))
