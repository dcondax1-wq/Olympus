"""Final validation of the adopted strategy and its eval-mode variants."""
from multiprocessing import Pool

from study_pass import run

V = [("FINAL default ($350 + conviction)", {}), ("FINAL eval sprint ($450)", {"risk_usd": 450}),
     ("FINAL eval sprint ($400)", {"risk_usd": 400}), ("FINAL turbo ($450, x1.5 after lock)", {"risk_usd": 450, "lock_boost": 1.5})]

if __name__ == "__main__":
    with Pool(4) as pool:
        out = pool.map(run, V)
    for o in out:
        n, t, tw, pf, net, dd, wd, rp, rf, rd, mp, mf, md, ir, orr, bd = o
        print(f"{n:38s} {t}t {tw} per wk | PF {pf} | net {net:+.0f} | maxDD {dd:.0f} | worst day {wd:.0f} | rolling {rp}/{rf} avg {rd}d | "
              f"MC pass {mp}% fail {mf}% median {md}d | IS {ir:+.2f}R OOS {orr:+.2f}R | best day {bd}%")
