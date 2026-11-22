"""MONEY BOOK (night-moneyideas 2026-11-20): the small money rules in one place, so a buy, a dead eval or a payout is never
decided by memory. PURE and read only: no order, no purchase, no request to MFFU, no network. Write-up:
research/writeups/money-ideas-2026-11-20.md (ideas 2-5).

  slots(accounts)            -> which MFFU funded slots are used / planned / open (caps: 5 sim funded in all; Builder 50K 1,
                                Builder 25K 2, Rapid EOD 25K 3, Rapid EOD 50K 3; 10 evals; research/lit/mffu_rules.json +
                                help article 16727601 for the Rapid EOD 25K)
  best_price(plan, codes)    -> the cheapest checkout among CLUB 40% and any other code (a Black Friday "30% off" is WORSE)
  next_buy(accounts, cash)   -> the one account to buy next from kept payout money (never fill the LAST slot cheap), or why not
  dead_eval(accounts, plan)  -> what to do the night an eval dies (re-buy the same plan at once, never wait or reset)
  tax_true_up(payouts, fees) -> the 30% pot vs a rough tax on profit after the business costs (eval fees lower the tax)

    python -X utf8 tools/money/money_book.py                       # today's fleet (STATE.md 2026-11-20)
    python -X utf8 tools/money/money_book.py --payouts 800 --fees 315.0
"""
from __future__ import annotations

import json
import sys

TAX = 0.30          # owner rule: 30% of every payout to the tax pot the day it lands
BUDGET = 150.0      # owner rule: at most $150 per buy round
EVAL_CAP = 10
FUNDED_CAP = 5
LIST = {"builder50k": 153.0, "builder25k": 105.0, "rapideod25": 162.0, "rapideod50": 275.0}
OWNER_PRICE = {"builder50k": 91.80, "builder25k": 63.0, "rapideod25": 97.20, "rapideod50": 165.0}  # CLUB 40%, owner's real prices
LABEL = {"builder50k": "Builder 50K", "builder25k": "Builder 25K", "rapideod25": "Rapid EOD 25K", "rapideod50": "Rapid EOD 50K"}
PLAN_CAP = {"builder50k": 1, "builder25k": 2, "rapideod25": 3, "rapideod50": 3}
# $ a month to the owner per slot (after the fee and MFFU's cut, before the tax pot), Jul-Oct 2026-like market: Rapid EOD
# 50K $2,295 / 25K $800 at ATLAS's real fills (10 ticks a side; research/writeups/rapid50-ready-2026-11-20.md, LIT + ATLAS;
# was $2,812 / $972 at backtest fills); Builder 50K $818 / 25K $352 (research/writeups/eval-cost.md, one slot for 6 months).
# Used only to RANK slots; in a 2021-25-like market all are ~$0.
USD_MONTH = {"rapideod50": 2295.0, "rapideod25": 800.0, "builder50k": 818.0, "builder25k": 352.0}

# Today's fleet (board.py read 2026-11-19 21:47 ET + STATE.md): stage 'funded' or 'eval'.
TODAY = [
    {"name": "Zlarior", "plan": "builder50k", "stage": "eval"},
    {"name": "ATLAS", "plan": "builder25k", "stage": "funded"},
    {"name": "Zlarior 25K #2", "plan": "builder25k", "stage": "eval"},
    {"name": "Rapid EOD 25K", "plan": "rapideod25", "stage": "eval"},
]


def slots(accounts):
    """Every live account will try to become funded, so an eval holds its funded slot too ('planned')."""
    by = {p: {"funded": 0, "eval": 0} for p in PLAN_CAP}
    for a in accounts:
        by[a["plan"]][a["stage"]] += 1
    used = sum(v["funded"] + v["eval"] for v in by.values())
    out = {"total_cap": FUNDED_CAP, "taken": used, "open": max(0, FUNDED_CAP - used),
           "evals": sum(v["eval"] for v in by.values()), "eval_cap": EVAL_CAP, "plans": {}}
    for p, v in by.items():
        t = v["funded"] + v["eval"]
        out["plans"][p] = {"label": LABEL[p], "funded": v["funded"], "eval": v["eval"], "cap": PLAN_CAP[p],
                           "open": max(0, min(PLAN_CAP[p] - t, out["open"]))}
    return out


def best_price(plan, codes=None):
    """codes: {name: pct off list} seen at checkout. CLUB 40% is always on the list. Cheapest wins; ties keep CLUB."""
    cands = {"CLUB": 40.0}
    cands.update({k: float(v) for k, v in (codes or {}).items()})
    best = min(cands, key=lambda k: (round(LIST[plan] * (1 - cands[k] / 100.0), 2), k != "CLUB"))
    price = round(LIST[plan] * (1 - cands[best] / 100.0), 2)
    if best == "CLUB":
        price = OWNER_PRICE[plan]
    worse = sorted(k for k in cands if cands[k] < cands["CLUB"])
    return {"plan": plan, "code": best, "price": price, "pct": cands[best], "worse_than_club": worse}


def next_buy(accounts, cash, codes=None, budget=BUDGET):
    s = slots(accounts)
    if s["open"] == 0:
        return {"buy": None, "why": f"all {FUNDED_CAP} MFFU funded slots are taken or planned: buy only when an eval dies"}
    if s["evals"] >= EVAL_CAP:
        return {"buy": None, "why": f"{EVAL_CAP} evals already running (MFFU cap)"}
    ranked = sorted((p for p in PLAN_CAP if s["plans"][p]["open"] > 0), key=lambda p: -USD_MONTH[p])
    top = ranked[0]
    bp = best_price(top, codes)
    if bp["price"] <= cash + 1e-9:
        return {"buy": top, "label": LABEL[top], "price": bp["price"], "code": bp["code"], "usd_month": USD_MONTH[top],
                "why": f"the best open slot, paid from ${cash:.2f} of kept payout money"}
    if s["open"] > 1:  # more than one slot left: a cheaper plan that fits the money on hand does not block the best one
        for p in ranked[1:]:
            b2 = best_price(p, codes)
            if b2["price"] <= min(cash, budget) + 1e-9:
                return {"buy": p, "label": LABEL[p], "price": b2["price"], "code": b2["code"], "usd_month": USD_MONTH[p],
                        "why": f"fits ${min(cash, budget):.2f} and still leaves a slot for the {LABEL[top]}"}
    return {"buy": None, "wait_for": top, "label": LABEL[top], "price": bp["price"], "code": bp["code"],
            "need": round(bp["price"] - cash, 2),
            "why": (f"the last funded slot is worth most as a {LABEL[top]} (~${USD_MONTH[top]:,.0f} a month vs "
                    f"~${USD_MONTH[ranked[1]] if len(ranked) > 1 else 0:,.0f}); wait for ${bp['price'] - cash:.2f} more kept payout money "
                    f"(it is over the ${budget:.0f} out-of-pocket round, so pay it from payouts), do not fill it with a cheaper plan")}


def dead_eval(accounts, plan, cash, codes=None):
    """Re-buy the same plan the same night: a funded slot earns ~$30-65 per trading day it is funded sooner, a re-buy costs
    $63-165, and MFFU publishes no reset price for one-time plans (a reset would not extend the account anyway)."""
    rest = [a for a in accounts if not (a["plan"] == plan and a["stage"] == "eval")][:]
    # put back the other evals of the same plan: only one died
    n_same = sum(1 for a in accounts if a["plan"] == plan and a["stage"] == "eval")
    rest += [{"name": "eval", "plan": plan, "stage": "eval"}] * max(0, n_same - 1)
    bp = best_price(plan, codes)
    ok = bp["price"] <= min(cash, BUDGET) + 1e-9 and slots(rest)["plans"][plan]["open"] > 0
    return {"plan": plan, "label": LABEL[plan], "rebuy_price": bp["price"], "code": bp["code"], "rebuy_now": ok,
            "per_day_sooner": round(USD_MONTH[plan] / 21.0, 2),
            "steps": [f"Buy a new {LABEL[plan]} tonight with code {bp['code']} (${bp['price']:.2f}), not a reset",
                      "ADD_ACCOUNT.bat -> the plan -> it is added OFF; START BOT + your phrase",
                      "Log the fee as a business cost (it lowers the tax)"] if ok else
                     [f"Not tonight: ${bp['price']:.2f} is more than ${min(cash, BUDGET):.2f} on hand / the ${BUDGET:.0f} round"]}


def tax_true_up(payouts_kept, fees, other_costs=0.0, rate=TAX):
    """payouts_kept = what MFFU sent you (after its 80/90% cut). The pot takes 30% of that; the tax is roughly 30% of the
    PROFIT (payouts - eval fees - other business costs). The gap is money the pot over-holds; keep it until the quarter's
    estimate is paid, then it can fund the next eval. Education only, not tax advice (research/writeups/taxes-2026-11-17.md)."""
    pot = round(rate * payouts_kept, 2)
    profit = max(0.0, payouts_kept - fees - other_costs)
    est = round(rate * profit, 2)
    return {"pot": pot, "profit": round(profit, 2), "tax_estimate": est, "over_held": round(pot - est, 2),
            "next_due": "2027-01-15 (1040-ES, Sep-Dec 2026)", "keep": round(payouts_kept - pot, 2)}


def _arg(argv, k, d):
    return float(argv[argv.index(k) + 1]) if k in argv else d


def main(argv):
    cash = _arg(argv, "--cash", 0.0)
    out = {"slots": slots(TODAY), "next_buy": next_buy(TODAY, cash),
           "dead_eval_50k": dead_eval(TODAY, "builder50k", BUDGET),
           "black_friday_30": best_price("rapideod50", {"BLACK30": 30}),
           "tax": tax_true_up(_arg(argv, "--payouts", 800.0), _arg(argv, "--fees", 315.0))}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
