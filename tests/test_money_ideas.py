"""MONEY IDEAS (night-moneyideas 2026-11-20, research/writeups/money-ideas-2026-11-20.md): offline, no browser, ~10 s.
  a. money_book.slots: today's fleet = 4 of 5 MFFU funded slots taken (evals hold a slot), only Rapid slots open
  b. best_price: CLUB 40% = the owner's real prices; a 30% "Black Friday" code is worse and is flagged; a 50% code wins
  c. next_buy: the LAST slot is never filled with a cheaper plan (waits for the Rapid EOD 50K); with 2 slots open a cheaper
     plan that fits may go first; caps (5 funded, 10 evals) refuse a buy
  d. dead_eval: re-buy the same plan at once (not a reset) when the money and the slot are there; not over the $150 round
  e. tax_true_up: pot = 30% of kept payouts; the estimate counts eval fees as costs; never negative profit
  f. kalshi_bankroll: the phone ladder ($5 / $8 / $10 / $15 at $0 / $53 / $67 / $100) and, on the stored K8 bets, the ladder
     busts far less than flat $15 at the same seed while keeping most of the growth
    python -X utf8 -m tests.test_money_ideas
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))

import kalshi_bankroll as KB  # noqa: E402
import money_book as MB  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-600:]}"), flush=True)


def part_a():
    s = MB.slots(MB.TODAY)
    check("a. 4 of 5 funded slots taken, 1 open", s["taken"] == 4 and s["open"] == 1, s)
    p = s["plans"]
    check("a. Builder 50K and 25K full, Rapid 25K / 50K open", p["builder50k"]["open"] == 0 and p["builder25k"]["open"] == 0
          and p["rapideod25"]["open"] == 1 and p["rapideod50"]["open"] == 1, p)


def part_b():
    check("b. CLUB = owner prices", all(MB.best_price(k)["price"] == v for k, v in MB.OWNER_PRICE.items()))
    b = MB.best_price("rapideod50", {"BLACK30": 30})
    check("b. 30% code is worse than CLUB and flagged", b["code"] == "CLUB" and b["price"] == 165.0 and b["worse_than_club"] == ["BLACK30"], b)
    b = MB.best_price("rapideod50", {"BF50": 50})
    check("b. a 50% code wins ($137.50)", b["code"] == "BF50" and b["price"] == 137.5, b)


def part_c():
    n = MB.next_buy(MB.TODAY, 120.0)
    check("c. last slot: waits for the Rapid 50K, does not buy a Rapid 25K with $120", n["buy"] is None and n["wait_for"] == "rapideod50"
          and n["need"] == 45.0, n)
    n = MB.next_buy(MB.TODAY, 170.0)
    check("c. $170 kept -> buy the Rapid 50K", n["buy"] == "rapideod50" and n["price"] == 165.0, n)
    three = MB.TODAY[:3]
    n = MB.next_buy(three, 120.0)
    check("c. 2 slots open: a Rapid 25K that fits may go first", n["buy"] == "rapideod25", n)
    full = MB.TODAY + [{"name": "R50", "plan": "rapideod50", "stage": "eval"}]
    check("c. 5 of 5 taken -> no buy", MB.next_buy(full, 999.0)["buy"] is None)


def part_d():
    d = MB.dead_eval(MB.TODAY, "builder50k", 150.0)
    check("d. 50K dies -> re-buy now at $91.80, not a reset", d["rebuy_now"] and d["rebuy_price"] == 91.8 and "not a reset" in d["steps"][0], d)
    d = MB.dead_eval(MB.TODAY, "builder50k", 50.0)
    check("d. not enough money -> not tonight", not d["rebuy_now"], d)
    d = MB.dead_eval(MB.TODAY, "builder25k", 150.0)
    check("d. 25K #2 dies -> its slot frees, re-buy $63", d["rebuy_now"] and d["rebuy_price"] == 63.0, d)


def part_e():
    t = MB.tax_true_up(800.0, 315.0)
    check("e. pot 30% = $240, estimate on $485 = $145.50, over-held $94.50", t["pot"] == 240.0 and t["tax_estimate"] == 145.5
          and t["over_held"] == 94.5 and t["keep"] == 560.0, t)
    t = MB.tax_true_up(100.0, 500.0)
    check("e. fees above payouts -> no tax estimate, profit 0", t["profit"] == 0.0 and t["tax_estimate"] == 0.0, t)


def part_f():
    check("f. ladder picks", [KB.ladder_stake(c) for c in (40, 55, 70, 120, -3)] == [5.0, 8.0, 10.0, 15.0, 5.0])
    days = KB.load(period="test")
    st = KB.stats(days)
    check("f. 105 held-out bets on the 3 live legs", st["bets"] == 105 and st["days"] == 35, st)
    flat = KB.simulate(days, "flat15", paths=3000, al=st["avg_loss_per_$1"])
    lad = KB.simulate(days, "ladder", paths=3000, al=st["avg_loss_per_$1"])
    check("f. ladder busts less than flat $15 and keeps >= 80% of the median", lad["bust_pct"] < flat["bust_pct"] / 3
          and lad["median_cash"] >= 0.8 * flat["median_cash"], (flat, lad))


if __name__ == "__main__":
    for f in (part_a, part_b, part_c, part_d, part_e, part_f):
        f()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)
