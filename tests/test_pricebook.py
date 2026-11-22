"""THE ONE PRICE BOOK (agency/pricebook.json, day-caller2 2026-11-21): every place that shows a price or a term says the same thing.
  a. the book itself: Starter $1,500 + $79, nothing upfront $149 x 12, 50% deposit, a 12-month care-plan term, the safe commission
  b. pricebook.check(): offers page, config.example, storefront example, portal page + code, agreement, payments guide, playbook, the caller
     pack / terms / job post / targets, client_deliver's CARE_PLAN, the launch site, the billing guide and the agency docs all agree
  c. the check really catches drift: a changed number in a copy of the book is reported
  d. the sentences pages reuse (words()) are exact
    python -X utf8 -m tests.test_pricebook
"""
from __future__ import annotations

import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency import pricebook as PB  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


def main() -> int:
    b = PB.load()
    s = PB.pkg(b, "starter")
    cm = b["commission"]
    check("a. Starter $1,500 + $79, nothing upfront $149 x 12, 50% deposit ($750), care plan $79 with a 12-month term and 30 days notice",
          (s["setup"], s["monthly"]) == (1500, 79) and (b["no_upfront"]["monthly"], b["no_upfront"]["months"]) == (149, 12) and b["deposit_pct"] == 50
          and b["care_plan"] == {"monthly": 79, "term_months": 12, "notice_days": 30, "edit_minutes": 30})
    check("a. the commission is safe: $300 OR $40, one per business, only after the money clears, 30-day clawback",
          cm["sale"] == 300 and cm["booked_show"] == 40 and cm["one_per_business"] is True and cm["clawback_days"] == 30 and "cleared" in cm["paid_when"])
    bad = PB.check(b)
    check("b. every place that shows a price or a term agrees with the book", not bad, "\n".join(f"{w}: {x}" for w, x in bad))
    drift = copy.deepcopy(b)
    PB.pkg(drift, "starter")["setup"] = 1700
    drift["care_plan"]["term_months"] = 6
    found = PB.check(drift)
    check("c. a changed number is caught everywhere it shows (offers, configs, agreement, care plan ...)",
          len(found) >= 6 and any(w == "offers.json" for w, _ in found) and any("client_deliver" in w for w, _ in found), found[:8])
    w = PB.words(b)
    check("d. the shared sentences are exact", w["starter"] == "$1,500 + $79/month" and w["deposit"] == "$750"
          and w["no_upfront"] == "$149/month for 12 months, nothing upfront"
          and w["price_line"] == "The Starter site is $1,500 once plus $79 a month for hosting and small changes, or $149 a month for 12 months with nothing upfront.")
    bad_n = RES.count(False)
    print(f"\n{len(RES) - bad_n}/{len(RES)} passed")
    return 1 if bad_n else 0


if __name__ == "__main__":
    sys.exit(main())
