"""Pass-speed round 3: boost risk only after the MLL locks."""
from multiprocessing import Pool

from study_pass import run

V = [
    ("current ($350)", {}),
    ("fixed $450", {"risk_usd": 450}),
    ("$350, x1.5 after lock", {"lock_boost": 1.5}),
    ("$350, x2 after lock", {"lock_boost": 2.0}),
    ("$400, x1.5 after lock", {"risk_usd": 400, "lock_boost": 1.5}),
    ("$400, x2 after lock", {"risk_usd": 400, "lock_boost": 2.0}),
    ("$450, x1.5 after lock", {"risk_usd": 450, "lock_boost": 1.5}),
    ("$400 fixed", {"risk_usd": 400}),
]

if __name__ == "__main__":
    with Pool(8) as pool:
        out = pool.map(run, V)
    print(f"{'variant':26s} {'trd':>4s} {'PF':>5s} {'net':>7s} {'maxDD':>7s} {'worstD':>7s} | {'roll P/F':>8s} {'days':>5s} | {'MC pass':>7s} {'fail':>5s} {'med d':>5s} | E[days incl. resets]")
    for o in out:
        n, t, tw, pf, net, dd, wd, rp, rf, rd, mp, mf, md, ir, orr, bd = o
        exp_days = (md or 0) / max(0.01, mp / 100)
        print(f"{n:26s} {t:4d} {pf:5.2f} {net:+7.0f} {dd:7.0f} {wd:7.0f} | {rp:3d}/{rf:<4d} {rd or 0:5.1f} | {mp:6.1f}% {mf:4.1f}% {md or 0:5.0f} | {exp_days:5.1f}")
