"""Rebuild tools/web_public/nq/plan12.json from research/planner/results.json (today's plan K0, no tripwire).
    python -X utf8 research/handoff/2026-11-27/night-nq-accounts/make_plan12.py"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
d = json.load(open(os.path.join(ROOT, "research", "planner", "results.json"), encoding="utf-8"))
W = {"M25": "Plan on this: 25% of 2026's edge", "G": "2026-like market", "B": "2021-25-like market", "SW": "Good 3 months, then bad"}
rows = []
for m in ("M25", "G", "B", "SW"):
    s = d["rows"][f"K0 today|W0|{m}"]
    rows.append({"m": m, "label": W[m], "p10": s["net12_p10"], "p50": s["net12_p50"], "p90": s["net12_p90"], "mean": s["net12_mean"], "mo": s["month_1_6"],
                 "mo2": s["month_7_12"], "fees": s["fees_month_mean"], "cash": s["cash_needed_p90"], "loss": s["p_loss12"]})
out = {"v": 1, "made": "2026-11-26", "src": "research/planner/results.json (today's plan K0, no tripwire; 1,000 paths x 12 months, real engine, today's 4 accounts)",
       "note": "Net $ after eval fees and MFFU's split, before tax. A simulation of the next 12 months, not a promise.", "rows": rows}
json.dump(out, open(os.path.join(ROOT, "tools", "web_public", "nq", "plan12.json"), "w", encoding="utf-8"), indent=1)
print("plan12.json:", [(r["m"], r["p50"]) for r in rows])
