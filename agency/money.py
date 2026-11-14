"""THE MONEY MATH: from the three packages (agency/config.json) and the funnel guesses (agency/pricing.json) to the
plan for $5,000 a month. Pure functions; the Agency page and docs/AGENCY.md show the same numbers.

    python -m agency.money            prints the table

Monthly income = new clients x average setup fee + all active care plans x average monthly fee (care plans churn).
"""
from __future__ import annotations

import json
import math
import os
import sys

from . import HERE
from . import config as CFG


def load_pricing() -> dict:
    with open(os.path.join(HERE, "pricing.json"), encoding="utf-8") as fh:
        return json.load(fh)


def averages(cfg: dict, mix: dict) -> dict:
    pk = {p["id"]: p for p in cfg.get("packages") or []}
    tot = sum(mix.get(k, 0) for k in pk) or 1
    setup = sum(pk[k]["setup"] * mix.get(k, 0) for k in pk) / tot
    monthly = sum(pk[k]["monthly"] * mix.get(k, 0) for k in pk) / tot
    return {"setup": round(setup, 2), "monthly": round(monthly, 2)}


def care_mrr(new_per_month: float, monthly: float, churn: float, months: int) -> float:
    """Recurring income after `months` months of adding new_per_month clients, each month losing `churn` of them."""
    if churn <= 0:
        return new_per_month * monthly * months
    return new_per_month * monthly * (1 - (1 - churn) ** months) / churn


def month_income(new_per_month: float, avg: dict, churn: float, month: int) -> float:
    return new_per_month * avg["setup"] + care_mrr(new_per_month, avg["monthly"], churn, month)


def months_to(goal: float, new_per_month: float, avg: dict, churn: float, limit=60):
    for m in range(1, limit + 1):
        if month_income(new_per_month, avg, churn, m) >= goal:
            return m
    return None


def plan(cfg: dict, pricing: dict, goal: float | None = None) -> dict:
    a = pricing["assumptions"]
    goal = float(goal or cfg.get("goal_per_month") or 5000)
    avg = averages(cfg, a["package_mix"])
    churn = a["care_churn_per_month"]
    rows = []
    for n in (2, 3, 4, 5, 6, 8):
        m = months_to(goal, n, avg, churn)
        rows.append({"new_per_month": n, "setup_income": round(n * avg["setup"]), "care_after_6": round(care_mrr(n, avg["monthly"], churn, 6)),
                     "care_after_12": round(care_mrr(n, avg["monthly"], churn, 12)), "month_6": round(month_income(n, avg, churn, 6)),
                     "month_12": round(month_income(n, avg, churn, 12)), "months_to_goal": m})
    # the smallest steady pace that reaches the goal within 12 months
    pace = next((r for r in rows if r["months_to_goal"] and r["months_to_goal"] <= 12), rows[-1])
    n = pace["new_per_month"]
    views = n * a["demo_views_per_sale"]
    convos = views * a["conversations_per_demo_view"]
    dials = convos * a["dials_per_conversation"]
    recurring_only = math.ceil(goal / avg["monthly"]) if avg["monthly"] else None
    return {
        "goal": goal, "avg_setup": avg["setup"], "avg_monthly": avg["monthly"], "churn": churn, "rows": rows,
        "pace": {"new_per_month": n, "months_to_goal": pace["months_to_goal"], "demo_views": views, "conversations": convos, "dials": dials,
                 "dials_per_day": round(dials / a["working_days_per_month"], 1), "hours_per_week": round((dials * a.get("minutes_per_call", 5) / 60 + n * a["hours_per_sale"]) / 4.33, 1)},
        "care_clients_for_goal_alone": recurring_only,
        "fees_note": f"Card fees about {a['stripe_fee'] * 100:.1f}% + 30 cents a payment; a domain about ${a['domain_per_year']} a year per client (bill it to them); taxes are yours to set aside.",
    }


def table(p: dict) -> str:
    out = [f"Goal ${p['goal']:,.0f} a month. Average sale ${p['avg_setup']:,.0f} to start + ${p['avg_monthly']:,.0f} a month (care plans lose {p['churn']:.0%} a month).",
           f"{'New clients / month':>20} {'Setup $ / month':>16} {'Care $ after 6 mo':>18} {'Total month 6':>14} {'Total month 12':>15} {'Months to goal':>15}"]
    for r in p["rows"]:
        out.append(f"{r['new_per_month']:>20} {r['setup_income']:>16,} {r['care_after_6']:>18,} {r['month_6']:>14,} {r['month_12']:>15,} {str(r['months_to_goal'] or '-'):>15}")
    pc = p["pace"]
    out.append(f"Pace: {pc['new_per_month']} new clients a month = {pc['demo_views']} demo views = {pc['conversations']} conversations = {pc['dials']} calls "
               f"(about {pc['dials_per_day']} a working day, {pc['hours_per_week']} hours a week). Care plans alone: {p['care_clients_for_goal_alone']} clients.")
    return "\n".join(out)


def main(argv=None):
    print(table(plan(CFG.load(), load_pricing())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
