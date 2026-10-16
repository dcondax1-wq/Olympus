"""Export a phone snapshot of the dashboard numbers as CSV files (snapshot/)."""
import datetime as dt
import os

import numpy as np
import pandas as pd

from engine import analytics, backtest, robust

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot")
os.makedirs(OUT, exist_ok=True)
FREE = {"dd_aware": False, "daily_max_loss": 1e9, "conviction_step": 0.0}

r = backtest.run("NQ", "5m", {})
s = r["stats"]
pd.DataFrame([{
    "net_pnl": s["net"], "win_rate": s["win_rate"] / 100, "profit_factor": s["profit_factor"], "trades": s["trades"],
    "trades_per_week": s["trades_per_week"], "max_drawdown": s["max_dd"], "avg_r": s["avg_r"],
    "eval_pass_rate": (r["rolling"]["pass_rate"] or 0) / 100, "eval_avg_days": r["rolling"]["avg_days_to_pass"],
    "period_from": r["range"][0], "period_to": r["range"][1],
}]).to_csv(os.path.join(OUT, "summary.csv"), index=False)

pd.DataFrame([{"day": d["date"], "balance": d["balance"], "trailing_mll": d["mll"], "day_pnl": d["pnl"], "trades": d["trades"]}
              for d in r["days"]]).to_csv(os.path.join(OUT, "equity.csv"), index=False)

et = lambda t: dt.datetime.fromtimestamp(t, dt.timezone(dt.timedelta(hours=-4))).strftime("%H:%M")
pd.DataFrame([{"trade_id": f"{t['day']} {et(t['entry_t'])}", "day": t["day"], "side": "Long" if t["dir"] == 1 else "Short",
               "trigger": t["trigger"], "target": t["target_label"], "exit": t["exit_reason"], "r_multiple": t["pnl_r"],
               "pnl": t["pnl"]} for t in r["trades"]]).to_csv(os.path.join(OUT, "trades.csv"), index=False)


def seg(tr):
    rr = np.array([t["pnl_r"] for t in tr]) if tr else np.zeros(0)
    return len(tr), float(np.mean(rr > 0)) if len(rr) else 0.0, float(rr.mean()) if len(rr) else 0.0


# Real CME futures only (no CFD data anywhere): one row per month of NQ history, NQ in total, and ES as a second market.
rows = []
nq_run = backtest.run("NQ", "5m", FREE, light=True)
nq = nq_run["trades"]
months = sorted({d["date"][:7] for d in nq_run["days"]})
for ym in months:
    label = dt.date(int(ym[:4]), int(ym[5:]), 1).strftime("%b %Y")
    rows.append((f"NQ futures · {label}", "CME futures", "Tuned here", *seg([t for t in nq if t["day"].startswith(ym)])))
if months:
    a, z = dt.date(int(months[0][:4]), int(months[0][5:]), 1).strftime("%b"), dt.date(int(months[-1][:4]), int(months[-1][5:]), 1).strftime("%b %Y")
    rows.append((f"NQ futures · {a}–{z} (all)", "CME futures", "Tuned here", *seg(nq)))
if os.path.exists(os.path.join(os.path.dirname(OUT), "data", "ES_5m.csv")):
    es = backtest.run("ES", "5m", FREE, light=True)["trades"]
    rows.append(("ES futures · same weeks", "CME futures", "Not tuned on ES", *seg(es)))
pd.DataFrame(rows, columns=["period", "data", "role", "trades", "win_rate", "avg_r"]).to_csv(os.path.join(OUT, "periods.csv"), index=False)

plan = analytics.PLANS["builder_50k"]
modes = []
for name, p in (("Steady $350", {}), ("Sprint $450", {"risk_usd": 450}), ("Turbo $450 ×1.5 after lock", {"risk_usd": 450, "lock_boost": 1.5})):
    x = backtest.run("NQ", "5m", p)
    mc = analytics.monte_carlo([d["pnl"] for d in x["days"]], plan, runs=3000, horizon=60)
    modes.append({"mode": name, "mc_pass": mc["pass_prob"] / 100, "median_days": mc["median_days_to_pass"],
                  "rolling_passed": x["rolling"]["pass"], "rolling_failed": x["rolling"]["fail"], "net_pnl": x["stats"]["net"]})
pd.DataFrame(modes).to_csv(os.path.join(OUT, "modes.csv"), index=False)

pl = robust.placebo("NQ", "5m", {}, n=500)
pd.DataFrame([{"real_avg_r": pl["real"], "placebo_mean_r": pl["placebo_mean"], "placebo_top1pct_r": pl["placebo_p99"],
               "p_value": pl["p_value"], "flipped_side_r": pl["flipped"], "ci90_low": pl["ci90"][0], "ci90_high": pl["ci90"][1]}]
             ).to_csv(os.path.join(OUT, "placebo.csv"), index=False)
for f in sorted(os.listdir(OUT)):
    print(f, os.path.getsize(os.path.join(OUT, f)), "bytes")
print(open(os.path.join(OUT, "periods.csv")).read())
