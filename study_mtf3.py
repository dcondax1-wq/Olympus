"""Re-weight test: confluences whose edge was sign-consistent in both halves of pooled NQ+ES candidates."""
from multiprocessing import Pool

from engine import backtest
from study_mtf import seg, SPLIT

V = [
    ("baseline", {}),
    ("AMT off", {"w_amt": 0}),
    ("PD on", {"w_pd": 1}),
    ("AMT off + PD on", {"w_amt": 0, "w_pd": 1}),
    ("AMT off + PD on, score>=2", {"w_amt": 0, "w_pd": 1, "min_score": 2}),
    ("AMT off + PD on + highest", {"w_amt": 0, "w_pd": 1, "ifvg_tf": "highest"}),
]


def run(args):
    name, sym, p = args
    tr = backtest.run(sym, "5m", p, light=True)["trades"]
    return name, sym, seg([t for t in tr if t["day"] < SPLIT]), seg([t for t in tr if t["day"] >= SPLIT]), seg(tr)


if __name__ == "__main__":
    with Pool(8) as pool:
        out = pool.map(run, [(n, s, p) for n, p in V for s in ("NQ", "ES")])
    print(f"{'variant':28s} sym | {'IN-SAMPLE':28s} | {'OUT-OF-SAMPLE':28s} | ALL")
    for name, sym, a, b, c in out:
        print(f"{name:28s} {sym:3s} | {a:28s} | {b:28s} | {c}")
