"""Night study 4 - the 'first week live' plan: how likely is an early hole?

Bootstrap (5,000 resamples, with replacement) of the per-trade R outcomes, converted to dollars at a flat $350 or $250
risk per trade. For 5 / 10 / 20 trades we report the chance of being down more than $600 / $1,000 / $2,000 at ANY point
(running minimum from the start - what matters for an eval account), the chance of being underwater at the end, and the
5th / 50th / 95th percentile of the P&L. Three source distributions, from optimistic to honest:
  1. NQ 2026 only (29 trades, the bot's best period - what the owner is looking at),
  2. all four periods pooled (the bot's full record on this logic, including two losing CFD periods),
  3. the worst period alone (CFD Q4 2023).
Also the drawdown-from-peak view (an MFFU trailing MLL of $2,000 is measured from the balance peak, not the start).
Run: python study_night_4_firstweek.py
"""
import numpy as np

from study_night_common import SEGS, run_both, seg_trades, md_table

N_BOOT = 5000
HORIZONS = (5, 10, 20)
THRESH = (600, 1000, 2000)
RISKS = (350, 250)


def boot(rs, risk, rng):
    rows = []
    rs = np.asarray(rs)
    for n in HORIZONS:
        idx = rng.integers(0, len(rs), size=(N_BOOT, n))
        paths = np.cumsum(rs[idx] * risk, axis=1)
        run_min = np.minimum(paths.min(axis=1), 0)
        peak = np.maximum.accumulate(np.maximum(paths, 0), axis=1)
        dd_peak = (paths - peak).min(axis=1)
        end = paths[:, -1]
        rows.append({"n": n,
                     **{f"p_down_{th}": float((run_min <= -th).mean()) for th in THRESH},
                     "p_dd_2000": float((dd_peak <= -2000).mean()),
                     "p_end_neg": float((end < 0).mean()),
                     "p_end_3000": float((end >= 3000).mean()),
                     "p5": float(np.percentile(end, 5)), "p50": float(np.median(end)), "p95": float(np.percentile(end, 95))})
    return rows


if __name__ == "__main__":
    res = run_both({})
    segs = seg_trades(res)
    R = {lab: [t["pnl_r"] for t in tr] for lab, (tr, dy) in segs.items()}
    pooled = [r for v in R.values() for r in v]
    worst_lab = min(R, key=lambda k: float(np.sum(R[k])))
    sources = [("NQ 2026 only", R["NQ 2026"]), ("all four periods pooled", pooled), (f"worst period alone ({worst_lab})", R[worst_lab])]

    print("# Study 4 - first week live: bootstrap of early drawdown\n")
    print("## Source distributions (flat sizing, per-trade R)\n")
    rows = []
    for lab, rs in [(l, R[l]) for l, *_ in SEGS] + [("pooled", pooled)]:
        a = np.array(rs)
        rows.append([lab, len(a), f"{(a > 0).mean():.0%}", f"{a.mean():+.2f}", f"{np.median(a):+.2f}", f"{a[a > 0].mean():+.2f}" if (a > 0).any() else "-",
                     f"{a[a <= 0].mean():+.2f}" if (a <= 0).any() else "-", f"{a.min():+.2f}", f"{a.max():+.2f}", f"{(a <= -0.9).mean():.0%}"])
    print(md_table(rows, ["distribution", "trades", "win rate", "avg R", "median R", "avg win R", "avg loss R", "worst R", "best R", "full-stop losses (<= -0.9R)"]))
    print()
    rng = np.random.default_rng(20261015)
    for src, rs in sources:
        for risk in RISKS:
            print(f"## {src} - ${risk} risk per trade\n")
            rows = []
            for o in boot(rs, risk, rng):
                rows.append([o["n"], f"{o['p_down_600']:.0%}", f"{o['p_down_1000']:.0%}", f"{o['p_down_2000']:.0%}", f"{o['p_dd_2000']:.0%}",
                             f"{o['p_end_neg']:.0%}", f"{o['p_end_3000']:.0%}", f"${o['p5']:+,.0f}", f"${o['p50']:+,.0f}", f"${o['p95']:+,.0f}"])
            print(md_table(rows, ["trades", "P(down > $600 at any point)", "P(down > $1,000)", "P(down > $2,000)", "P(DD from peak > $2,000)",
                                  "P(underwater at end)", "P(>= +$3,000 at end)", "5th pct", "median", "95th pct"]))
            print()
    # ---- per-trade dollar reality check at default sizing: what did the real (grade-sized, dd-aware) NQ 2026 run look like?
    print("## Reality check: the actual NQ 2026 trade sequence (flat $350, in order)\n")
    tr = segs["NQ 2026"][0]
    eq = 0.0
    rows = []
    for k, t in enumerate(tr, 1):
        eq += t["pnl_r"] * 350
        rows.append([k, t["day"], t["trigger"], t["grade"], f"{t['pnl_r']:+.2f}", f"${t['pnl_r'] * 350:+,.0f}", f"${eq:+,.0f}", t["exit_reason"]])
    print(md_table(rows, ["#", "day", "trigger", "grade", "R", "$ at $350", "running P&L", "exit"]))
