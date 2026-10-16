"""Stack the individually-validated changes and check that they survive together (IS / OOS / ES)."""
from multiprocessing import Pool

from study_exits import run

LEAN = {"w_protected": 0, "w_smt": 0, "w_quality": 0, "w_m15": -1}
C1 = dict(LEAN)
C2 = {**C1, "target_mode": "dol_next"}
C3 = {**C2, "amt_targets": False}
C4 = {**C3, "be_at_r": 1.0}
C5 = {**C4, "time_stop_min": 30}
V = [
    ("C0 current", {}),
    ("C1 lean + m15 penalty", C1),
    ("C2 + next DOL", C2),
    ("C3 + no AMT targets", C3),
    ("C4 + BE at 1R", C4),
    ("C5 + time stop 30m", C5),
    ("C5 BE 1.5R instead", {**C5, "be_at_r": 1.5}),
    ("C6 C5 + max stop 40", {**C5, "spec": {"max_stop": 40}}),
    ("C7 C5 + max stop 50", {**C5, "spec": {"max_stop": 50}}),
    ("C8 C5 + 15m IFVG", {**C5, "ifvg_tf": "highest"}),
    ("C9 C4 (no time stop) + max 50", {**C4, "spec": {"max_stop": 50}}),
]

if __name__ == "__main__":
    jobs = [("COMBO", n, s, p) for n, p in V for s in ("NQ", "ES")]
    with Pool(10) as pool:
        out = pool.map(run, jobs)
    res = {}
    for g, n, s, a, b, c, dd in out:
        res.setdefault(n, {})[s] = (a, b, c, dd)
    f = lambda z: f"{z['n']:3d}t {z['r']:+.2f}R pf{z['pf']:4.2f}"
    print(f"{'variant':32s} | {'NQ in-sample':20s} | {'NQ out-of-sample':20s} | {'NQ all':20s} {'net':>7s} {'maxDD':>7s} | {'ES all':20s}")
    for n, _ in V:
        a, b, c, dd = res[n]["NQ"]
        ec = res[n]["ES"][2]
        print(f"{n:32s} | {f(a):20s} | {f(b):20s} | {f(c):20s} {c['net']:+7.0f} {dd:7.0f} | {f(ec):20s}")
