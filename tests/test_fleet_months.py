"""FLEET MONTHS (day-fleet 2026-11-20, research/writeups/fleet-plan-2026-11-20.md): offline, no browser, ~30 s.
  a. tools/web_public/business/fleet_plan.json is EXACTLY fleet_months.phone(research/lab/fleet_months.json): no number on the
     phone is typed by hand
  b. the stored check block is re-made to the dollar by the same code on the repo's trade lists (n = 12, Jul-Oct-like, real fills)
  c. a trade-list change moves the money: LIT at 10 ticks a side (stress) gives less than real fills (stored, every market)
  d. the 5th-slot buy (Rapid EOD 50K) is paid from payouts only: on the small run it is never bought before a payout landed,
     and the stored plan keeps MFFU's caps (5 funded, 10 evals, Builder 50K 1, Builder 25K 2)
  e. the phone file: Dec 2026 - Jun 2027 months, the tax placeholder 35% said, 3 top cards that are open Decide cards
    python -X utf8 -m tests.test_fleet_months
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))

import fleet_months as FM  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-600:]}"), flush=True)


RESULT = json.load(open(FM.OUT, encoding="utf-8"))
PHONE = json.load(open(FM.PHONE, encoding="utf-8"))


def part_a():
    check("a. fleet_plan.json = phone(fleet_months.json)", PHONE == json.loads(json.dumps(FM.phone(RESULT))))


def part_b():
    c = RESULT["check"]
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    r = FM.market((c["span"], c["fills"], c["n"], False))["summary"]
    got = {"total_median": r["total_median"], "total_mean": r["total_mean"],
           "months_median": [m["median"] for m in r["months"]], "r2_date_med": r["next_buy"]["date_med"]}
    want = {k: c[k] for k in got}
    check("b. the check block re-made from the trade lists", got == want, (got, want))


def part_c():
    for sp in FM.SPANS:
        a = RESULT["rows"]["real"][sp]["summary"]["total_mean"]
        b = RESULT["rows"]["stress"][sp]["summary"]["total_mean"]
        check(f"c. {sp}: stress (LIT 10 ticks) < real fills", b < a, (a, b))
    h2 = RESULT["rows"]["real"]["H2"]["summary"]["total_mean"]
    ref = RESULT["rows"]["real"]["REF"]["summary"]["total_mean"]
    check("c. 2021-25-like makes far less than Jul-Oct-like", ref < 0.25 * h2, (h2, ref))


def part_d():
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    FM.set_fills("real")
    cal = FM.calendar()
    P = FM.paths("H2", 10, len(cal))
    R = FM.run(P, cal, FM.BASE)
    ok, bought = True, 0
    for p in range(len(P)):
        k = int(R["r2k"][p])
        if k < 0:
            continue
        bought += 1
        paid = sum(R["own"][nm][p, :max(0, k - FM.BANK_LAG)].sum() for nm in ("Z50", "N25", "A25", "R25"))
        fees = sum(R["fee"][nm][p, :k].sum() for nm in ("Z50", "N25", "A25", "R25")) - R["fee"]["R25"][p, 0]
        ok &= paid * (1 - FM.TAX) - fees >= FM.MB.OWNER_PRICE["rapideod50"] - 1e-6
    check("d. the Rapid EOD 50K is bought only from kept payout money", ok and bought > 0, bought)
    caps = RESULT["caps"]
    check("d. MFFU caps kept in the plan", caps["funded"] == 5 and caps["evals"] == 10 and caps["per_plan"]["builder50k"] == 1
          and caps["per_plan"]["builder25k"] == 2, caps)
    s = FM.MB.slots([{"name": k, "plan": FM.PLAN[k], "stage": "eval"} for k in ("Z50", "N25", "A25", "R25", "R2")])
    check("d. with the 5th slot filled no slot is open", s["open"] == 0 and s["taken"] == 5, s)


def part_e():
    ms = [m["m"] for m in PHONE["months"]]
    check("e. Dec 2026 - Jun 2027 in the phone file", all(f"{y}" in ms for y in ("2026-12", "2027-01", "2027-03", "2027-06")), ms)
    check("e. tax placeholder 35% and said so", PHONE["tax"] == 0.35 and "placeholder" in PHONE["tax_note"])
    dec = json.load(open(os.path.join(ROOT, "tools", "web_public", "business", "decisions.json"), encoding="utf-8"))
    ids = {c["id"] for c in dec["items"]}
    top = [c["id"] for c in PHONE["top_cards"]]
    check("e. 3 top cards, all Decide cards", len(top) == 3 and all(t in ids for t in top), top)
    check("e. next buy = Rapid EOD 50K at the owner's price", PHONE["next_buy"]["what"] == "Rapid EOD 50K"
          and PHONE["next_buy"]["price"] == 165.0)
    check("e. phone file is small (< 6 KB)", os.path.getsize(FM.PHONE) < 6000, os.path.getsize(FM.PHONE))


if __name__ == "__main__":
    for f in (part_a, part_b, part_c, part_d, part_e):
        f()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)
