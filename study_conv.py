"""Conviction sizing: keep every trade, tilt size toward sign-stable confluences."""
from multiprocessing import Pool

from engine import analytics, backtest
from study_exits import run as run_r
from study_pass import run as run_pass

V = [
    ("current", {}),
    ("conviction 0.25", {"conviction_step": 0.25}),
    ("conviction 0.33", {"conviction_step": 0.33}),
    ("conviction 0.5", {"conviction_step": 0.5}),
    ("conviction 0.25 (no major term)", {"conviction_step": 0.25, "conviction_major": False}),
    ("conviction 0.33 (no major term)", {"conviction_step": 0.33, "conviction_major": False}),
]


def dollars(job):
    name, p = job
    r = backtest.run("NQ", "5m", p, light=True)
    tr = r["trades"]
    split = "2026-09-22"
    a = sum(t["pnl"] for t in tr if t["day"] < split); b = sum(t["pnl"] for t in tr if t["day"] >= split)
    return name, len(tr), a, b, r["stats"]["max_dd"], r["stats"]["profit_factor"]


if __name__ == "__main__":
    with Pool(6) as pool:
        d = pool.map(dollars, V)
        ps = pool.map(run_pass, V)
    print(f"{'variant':34s} {'trd':>4s} {'IS $':>7s} {'OOS $':>7s} {'PF$':>5s} {'maxDD':>7s} | {'roll P/F':>8s} {'days':>5s} | {'MC pass':>7s} {'med d':>5s}")
    for (n, t, a, b, dd, pf), o in zip(d, ps):
        print(f"{n:34s} {t:4d} {a:+7.0f} {b:+7.0f} {pf:5.2f} {dd:7.0f} | {o[7]:3d}/{o[8]:<4d} {o[9] or 0:5.1f} | {o[10]:6.1f}% {o[12] or 0:5.0f}")
