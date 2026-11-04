"""Money roadmap self-check (tools/money_roadmap.py, research/props/roadmap.json): the totals must reconcile.

    python -X utf8 -m tests.test_money_roadmap

Checks, on a small fresh run (150 paths a half) and on the stored roadmap.json:
  - every path: payout events - fee events == the account's own books (payouts, fees, with the already-paid first prices apart);
  - every month: cash in - cash out == net; months add to the 12-month total; the last running total == the total;
  - accounts add to the scenario; the already-paid first prices are 91.80 + 43 + 63 = 197.80;
  - nobody is paid over the payout cap (5 x 80% x the plan's payout max, per purchase);
  - the stored file has the verdict, both halves, and H2 named as the conservative one.
Research only: reads research/second/sn_daily.npz and research/props/roadmap.json, writes nothing.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import money_roadmap as MR  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))


def main():
    res, _split, _n = MR.run_all(150, seed=7, only={"trio", "trio_recycle", "slot_atlas_copy", "solo_L50", "buy_all_now",
                                                    "order_L50_A25_B25"})
    bad = MR.reconcile(res)
    ok("fresh run reconciles (events == books, months == total, accounts == scenario, caps)", not bad, json.dumps(bad[:5]))
    R = res["H2"]["trio"]
    t = MR.table(R)["total"]
    ok("fees + payouts = net (fresh H2 trio)", abs(t["cash_in"] - t["cash_out"] - t["net"]) < 0.02, str(t))
    ok("already-paid first prices = 197.80", abs(t["sunk_already_paid"] - 197.80) < 0.01, str(t["sunk_already_paid"]))
    allnow = MR.table(res["H2"]["buy_all_now"])["total"]
    ok("buying all three now pays the three first prices inside the window", abs(allnow["cash_out"] - t["cash_out"] - 197.80) < 0.01,
       str((allnow["cash_out"], t["cash_out"])))
    rec = MR.table(res["H2"]["trio_recycle"])["total"]
    ok("buying a new eval after the 5th payout costs fees and adds payouts", rec["cash_out"] >= t["cash_out"] and rec["cash_in"] >= t["cash_in"])
    # a 25K never pays more than 5 x 1,000 x 80% per purchase; the 50K never more than 5 x 2,000 x 80%
    c = res["H2"]["solo_L50"]["counters"]
    ok("50K payouts never above 8,000 a purchase", (c[:, 0, 0] <= 8000.0 * (1 + c[:, 0, 3] + c[:, 0, 2]) + 1e-6).all())
    path = MR.OUT_P
    ok("roadmap.json exists", os.path.exists(path))
    if os.path.exists(path):
        d = json.load(open(path))
        bad = MR.check_json(path)
        ok("stored roadmap.json reconciles", not bad, json.dumps(bad[:5]))
        ok("stored file: both halves, H2 conservative, verdict present", set(d["scenarios"]) == {"H1", "H2"} and d["conservative"] == "H2"
           and all(k in d["verdict"] for k in ("do_first", "then", "first_payout", "month12")))
        ok("stored file: 12 months for the base trio", len(d["scenarios"]["H2"]["trio"]["months"]) == 12)
        ok("stored file is small (< 200 KB)", os.path.getsize(path) < 200_000, str(os.path.getsize(path)))
    n, p = len(RESULTS), sum(RESULTS)
    print(f"money roadmap: {p}/{n} {'ALL PASS' if p == n else 'FAILURES'}")
    sys.exit(0 if p == n else 1)


if __name__ == "__main__":
    main()
