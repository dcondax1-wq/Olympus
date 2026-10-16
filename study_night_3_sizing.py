"""Night study 3 - position sizing on the NQ 2026 period with the trade list held fixed.

Sizing changes the dollars per trade, not the entries, so the question is purely: which sizing gives the best MFFU
Builder 50K evaluation outcome without a single day worse than -$1,000 (the MFFU soft daily loss limit)?
Real engine with the LIVE risk settings (dd_aware on, daily_max_loss 600), so this is what the bot would actually do.
For every variant we report whether the trade list is identical to the default (entry timestamps compared).
Eval metrics come from engine.analytics: simulate_eval from day 1, rolling_evals (an eval started on every day),
and monte_carlo (2,000 bootstrapped 60-day sequences of NQ 2026 trading days).
Run: python study_night_3_sizing.py
"""
from multiprocessing import Pool

import numpy as np

from engine import analytics, backtest
from study_night_common import md_table

V = [
    ("default: grade sizing, $350 fixed", {}),
    ("conviction sizing (grade off)", {"grade_sizing": False}),
    ("flat $350 (grade + conviction off)", {"grade_sizing": False, "conviction_step": 0}),
    ("grade, $300", {"risk_usd": 300}),
    ("grade, $400", {"risk_usd": 400}),
    ("grade, $350, lock_boost 1.25", {"lock_boost": 1.25}),
    ("grade, $350, lock_boost 1.5", {"lock_boost": 1.5}),
    ("grade, $400, lock_boost 1.5", {"risk_usd": 400, "lock_boost": 1.5}),
    ("grade, risk_mode cushion (25% of cushion)", {"risk_mode": "cushion"}),
    ("grade, cushion + lock_boost 1.5", {"risk_mode": "cushion", "lock_boost": 1.5}),
    ("flat $300", {"grade_sizing": False, "conviction_step": 0, "risk_usd": 300}),
    ("flat $400", {"grade_sizing": False, "conviction_step": 0, "risk_usd": 400}),
    ("flat $250", {"grade_sizing": False, "conviction_step": 0, "risk_usd": 250}),
    ("grade, $350, dd_aware off", {"dd_aware": False}),
]
PLAN = analytics.PLANS["builder_50k"]


def _job(job):
    name, p = job
    r = backtest.run("NQ", "5m", p, light=False)
    tr, days = r["trades"], r["days"]
    pnl = np.array([t["pnl"] for t in tr])
    eq = np.cumsum(pnl)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(tr) else 0.0
    dp = [d["pnl"] for d in days]
    mc = analytics.monte_carlo(dp, PLAN, runs=2000, horizon=60)
    return name, {
        "keys": sorted(t["entry_t"] for t in tr), "n": len(tr), "net": float(pnl.sum()), "dd": dd,
        "worst_day": min(dp), "worst_intra": min(d["low_intraday"] for d in days), "best_day": max(dp),
        "max_risk": max(t["risk_usd_plan"] for t in tr), "avg_risk": float(np.mean([t["risk_usd_plan"] for t in tr])),
        "max_qty": max(t["qty"] for t in tr),
        "eval": r["eval"]["result"], "eval_days": r["eval"]["days"], "eval_bal": r["eval"]["balance"],
        "roll_pass": r["rolling"]["pass_rate"], "roll_done": r["rolling"]["completed"], "roll_days": r["rolling"]["avg_days_to_pass"],
        "mc_pass": mc["pass_prob"], "mc_fail": mc["fail_prob"], "mc_med_days": mc["median_days_to_pass"],
        "payout": mc["funded"]["avg_paid_to_trader"], "blow": mc["funded"]["blow_rate"],
    }


if __name__ == "__main__":
    with Pool(6) as pool:
        out = pool.map(_job, V)
    base = out[0][1]
    print("# Study 3 - sizing on NQ 2026 (Aug-Oct 2026, live risk settings)\n")
    print(f"Plan: {PLAN['name']} - target +${PLAN['target']:,}, trailing MLL ${PLAN['mll']:,} (locks at +${PLAN['lock_above']}), soft daily loss ${PLAN['dll']:,}.\n")
    rows = []
    for name, o in out:
        same = "yes" if o["keys"] == base["keys"] else f"NO ({o['n']} vs {base['n']})"
        ok = "ok" if o["worst_day"] > -1000 and o["worst_intra"] > -1000 else "BREACH"
        rows.append([name, same, f"${o['net']:+,.0f}", f"${o['dd']:,.0f}", f"${o['worst_day']:,.0f}", f"${o['worst_intra']:,.0f}", ok,
                     f"${o['best_day']:,.0f}", f"${o['avg_risk']:.0f} / ${o['max_risk']:.0f}", o["max_qty"],
                     f"{o['eval']} d{o['eval_days']}", f"{o['roll_pass']}% ({o['roll_done']} runs, {o['roll_days']} d)",
                     f"{o['mc_pass']}% / {o['mc_fail']}% / {o['mc_med_days']}", f"${o['payout']:,.0f} / {o['blow']}%"])
    print(md_table(rows, ["sizing", "same trades?", "net", "max DD", "worst day", "worst intraday", "<$1k day", "best day",
                          "avg / max risk per trade", "max micros", "eval from day 1", "rolling evals pass (n, avg days)",
                          "MC pass / fail / median days", "funded: avg payout / blow-up"]))
    print("\nNotes: 'rolling evals' starts a fresh evaluation on each historical day and runs it forward; OPEN runs (not finished by data end) are excluded.")
    print("'MC' bootstraps NQ 2026 trading days into 2,000 random 60-day evaluations. 'funded' = simulated funded-stage payouts over 120 days.")
