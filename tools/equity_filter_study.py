"""Cold-streak (equity-curve) study for the live pick: engine {grade_sizing False, conviction 0, max_trades_day 1}.
Trades: five-year live replay (2021-10..2025-12) + current-data 2026 test bed. Rules use only past shadow outcomes."""
import json
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = sys.argv[1]
a = json.load(open(os.path.join(ROOT, "research", "five_year", "run_live_nograde_max1.json")))
b = json.load(open(os.path.join(ROOT, "research", "lab", "conf_testbed_orig1day.json")))
old = [t for t in a["trades"] if t["day"] < "2026-01-01"]
new = b["ytd"]["trades"]
T = sorted(old + new, key=lambda t: t["entry_t"])
print("trades", len(T), T[0]["day"], "->", T[-1]["day"], "| old file", a["trades"][0]["day"], a["trades"][-1]["day"])

r = np.array([t["r"] for t in T])
w = (r > 0).astype(int)
n1, n0 = w.sum(), len(w) - w.sum()
runs = 1 + np.sum(w[1:] != w[:-1])
mu = 1 + 2 * n1 * n0 / (n1 + n0)
var = 2 * n1 * n0 * (2 * n1 * n0 - n1 - n0) / ((n1 + n0) ** 2 * (n1 + n0 - 1))
print(f"win rate {w.mean():.3f} | runs {runs} vs expected {mu:.1f} | z {(runs - mu) / var ** 0.5:+.2f} (negative = streaky)")
for k in (1, 2, 3, 4, 5, 6):
    idx = [i for i in range(k, len(w)) if w[i - k:i].sum() == 0]
    print(f"  after {k} straight losses: n={len(idx):3d} next win {w[idx].mean():.3f} avgR {r[idx].mean():+.3f}")
for n in (5, 10, 20):
    idx_pos = [i for i in range(n, len(r)) if r[i - n:i].sum() > 0]
    idx_neg = [i for i in range(n, len(r)) if r[i - n:i].sum() <= 0]
    print(f"  last {n} trades sum R>0: n={len(idx_pos)} avgR {r[idx_pos].mean():+.3f} win {w[idx_pos].mean():.3f} | <=0: n={len(idx_neg)} avgR {r[idx_neg].mean():+.3f} win {w[idx_neg].mean():.3f}")


def apply(rule, k):
    """Return mask of trades actually taken. Shadow = every signal; live only when the rule allows."""
    take = []
    for i in range(len(T)):
        hist = r[:i]
        if rule == "none":
            ok = True
        elif rule == "streak":           # pause after k straight shadow losses, resume after the next shadow win
            j, cnt = i - 1, 0
            while j >= 0 and r[j] <= 0:
                cnt += 1
                j -= 1
            ok = cnt < k
        elif rule == "roll":             # trade only if the last k shadow trades summed > 0 R
            ok = i < k or hist[-k:].sum() > 0
        elif rule == "roll0":            # ... >= -1R
            ok = i < k or hist[-k:].sum() > -1
        take.append(ok)
    return np.array(take)


def summary(mask, lo, hi, label):
    idx = [i for i in range(len(T)) if mask[i] and lo <= T[i]["day"] <= hi]
    allidx = [i for i in range(len(T)) if lo <= T[i]["day"] <= hi]
    rr = r[idx]
    pnl = np.array([T[i]["pnl"] for i in idx])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl) if len(pnl) else np.zeros(1)
    dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() if len(pnl) else 0
    months = defaultdict(float)
    for i in idx:
        months[T[i]["day"][:7]] += T[i]["pnl"]
    weeks = len({T[i]["day"] for i in allidx})
    return (f"{label:<14} kept {len(idx):3d}/{len(allidx):3d} win {(rr > 0).mean() if len(rr) else 0:.2f} avgR {rr.mean() if len(rr) else 0:+.3f} "
            f"PF {gp / gl if gl else 0:4.2f} net {pnl.sum():+8.0f} maxDD {dd:7.0f} losing months {sum(1 for v in months.values() if v < 0)}/{len(months)}"), months


periods = [("train 21-24", "2021-01-01", "2024-12-31"), ("2025", "2025-01-01", "2025-12-31"), ("2026", "2026-01-01", "2026-12-31")]
grid = [("none", 0)] + [("streak", k) for k in (2, 3, 4, 5, 6)] + [("roll", k) for k in (5, 8, 10, 15, 20)] + [("roll0", k) for k in (5, 10, 15)]
best = None
for rule, k in grid:
    m = apply(rule, k)
    print(f"\n== {rule} {k}")
    for lab, lo, hi in periods:
        print("  ", summary(m, lo, hi, lab)[0])
if len(sys.argv) > 3:
    rule, k = sys.argv[2], int(sys.argv[3])
    m = apply(rule, k)
    for lab, lo, hi in periods:
        s, months = summary(m, lo, hi, lab)
        print(s)
        if lab == "2026":
            print("   ", " ".join(f"{mm[5:]}:{v:+.0f}" for mm, v in sorted(months.items())))
