"""Pass-speed round 2: cushion-based sizing and London arming."""
from multiprocessing import Pool

from study_pass import run

LON = {"entry_windows": [[180, 300], [570, 690], [810, 930]], "arm_start": 120}
V = [
    ("current ($350 fixed)", {}),
    ("fixed $450", {"risk_usd": 450}),
    ("cushion 18%", {"risk_mode": "cushion", "cushion_frac": 0.18}),
    ("cushion 20%", {"risk_mode": "cushion", "cushion_frac": 0.20}),
    ("cushion 22%", {"risk_mode": "cushion", "cushion_frac": 0.22}),
    ("cushion 25%", {"risk_mode": "cushion", "cushion_frac": 0.25}),
    ("cushion 20% max 600", {"risk_mode": "cushion", "cushion_frac": 0.20, "risk_max": 600}),
    ("cushion 22% max 900", {"risk_mode": "cushion", "cushion_frac": 0.22, "risk_max": 900}),
    ("London armed (arm 02:00)", LON),
    ("London + cushion 20%", {**LON, "risk_mode": "cushion", "cushion_frac": 0.20}),
    ("arm from 06:00 (pre-NY sweeps)", {"arm_start": 360}),
]

if __name__ == "__main__":
    with Pool(11) as pool:
        out = pool.map(run, V)
    print(f"{'variant':32s} {'trd':>4s} {'t/wk':>5s} {'PF':>5s} {'net':>7s} {'maxDD':>7s} {'worstD':>7s} | {'roll P/F':>8s} {'days':>5s} | {'MC pass':>7s} {'fail':>5s} {'med d':>5s} | {'IS R':>5s} {'OOS R':>5s} {'best%':>5s}")
    for o in out:
        n, t, tw, pf, net, dd, wd, rp, rf, rd, mp, mf, md, ir, orr, bd = o
        print(f"{n:32s} {t:4d} {tw:5.1f} {pf:5.2f} {net:+7.0f} {dd:7.0f} {wd:7.0f} | {rp:3d}/{rf:<4d} {rd or 0:5.1f} | {mp:6.1f}% {mf:4.1f}% {md or 0:5.0f} | {ir:+.2f} {orr:+.2f} {bd or 0:5.1f}")
