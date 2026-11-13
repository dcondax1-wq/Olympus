"""Prop plan card self-check (tools/money/prop_plan.py -> tools/web_public/money/prop_plan.json).

    python -X utf8 -m tests.test_prop_plan

Runs the tool's own selftest (bundled numbers: contract keys, paper mode, the owner's real prices, BLITZ on paper not
counted, the ladder steps move with payouts) and checks the stored JSON: paper mode, the three owner accounts, five ladder
steps, H1 / H2 / REF on every step, and no order or secret field anywhere. Reads only, writes nothing.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))

import prop_plan as PP  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))


def main():
    ok("tool selftest", PP.selftest() == 0)
    path = os.path.join(PP.OUT_DIR, "prop_plan.json")
    d = PP.load_json(path)
    ok("stored prop_plan.json is readable", isinstance(d, dict), path)
    if isinstance(d, dict):
        ok("paper mode", d.get("mode") == "paper")
        ids = [a.get("id") for a in d.get("plan", {}).get("accounts", [])]
        ok("the owner's three accounts", ids == ["zlarior50", "atlas25", "blitz25"], str(ids))
        lad = d.get("plan", {}).get("ladder", [])
        ok("five ladder steps with H1 / H2 / REF", len(lad) == 5 and all(set(r["usd_month"]) >= {"h1", "h2", "ref"} for r in lad))
        txt = json.dumps(d).lower()
        ok("no order / secret fields", not any(w in txt for w in ("api_key", "token", "password", "place_order", "\"armed\": true")))
    print("test_prop_plan:", "OK" if all(RESULTS) else f"{RESULTS.count(False)} FAILED")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
