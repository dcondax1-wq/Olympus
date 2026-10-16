"""Current MFFU Builder 50K evaluation pass rates with today's default settings."""
from engine import analytics, backtest

PLAN = analytics.PLANS["builder_50k"]


def show(label, sym, p, a=None, z=None):
    r = backtest.run(sym, "5m", {**p, "days_from": a, "days_to": z})
    ro, s = r["rolling"], r["stats"]
    mc = analytics.monte_carlo([d["pnl"] for d in r["days"]], PLAN, runs=3000, horizon=60)
    print(f"{label:38s} rolling {ro['pass']}/{ro['completed']} passed ({ro['pass_rate']}%), avg {ro['avg_days_to_pass']}d, "
          f"{ro['fail']} failed, {ro['open']} unfinished | MC pass {mc['pass_prob']}% fail {mc['fail_prob']}% "
          f"median {mc['median_days_to_pass']}d | {s['trades_per_week']}/wk")


if __name__ == "__main__":
    show("NQ futures Aug-Oct 2026, default", "NQ", {})
    show("NQ futures Aug-Oct 2026, Sprint $450", "NQ", {"risk_usd": 450})
    show("Nasdaq CFD Q4 2023, default", "NQX", {}, None, "2023-12-31")
    show("Nasdaq CFD Q4 2025, default", "NQX", {}, "2025-01-01", "2025-12-31")
