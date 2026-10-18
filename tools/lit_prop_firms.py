"""LIT on every current futures prop-firm plan (owner, 2026-10-18: "If I start a 25K Builder or a Rapid account on Monday,
what are the stats? On simulated evals I want all account balances and by prop firm.").

Trades: the exact live LIT signals at 1 micro (tools/lit_tightstop.unit(), stop_mode ext = the live sweep-extreme stop; checked
trade for trade against run lit_live: 630/630, 2026 120 trades +$41,734). Each trade carries its points (slippage in), its worst
open loss (w1, points) and its best open profit (mfe, R), so every plan's size can be applied exactly, path by path.

Sizing per plan (two rules):
  scaled  the live eval sizing scaled by the plan's max loss: risk = $800 x (max loss / $2,000) up to a 25-pt stop, then
          risk x 25 / stop; micros rounded down (min 1); weekly stop half size (one rounding, min 1); never more than 60% of
          the room between the balance and the max-loss floor (min 1); capped by the plan's max contracts (micros = 10 x minis)
  lit     the plain LIT rule: $800 up to a 20-pt stop, then 800 x 20 / stop; weekly stop; capped by the plan's max contracts
Costs: $1.40 a micro round trip, 1 tick slippage (in the points).

Eval engine (per plan): EOD trailing = the floor moves with end-of-day balance highs and is checked against the intraday low
(the trade's worst open loss); intraday trailing = the floor also moves with the trade's best open profit (MFE) before the exit
is checked; the floor locks at start + lock; soft daily loss limit = the position is flattened at -DLL (1 tick slippage) and the
day ends; hard DLL = fail; eval consistency = best day <= share x profit to pass (a bigger best day just needs more profit);
minimum trading days = days with a trade; expiry (Apex 4.0: 30 calendar days ~ 21 sessions) = fail.
  exact    a fresh eval on every session of the span (only that span's sessions), up to 60 sessions
  monday   the exact starts that fall on a Monday
  mc       4,000 evals of 60 sessions drawn in blocks of 5 consecutive sessions from the span (like tools/lit_dash_data.py);
           mc_monday = the first block starts on a Monday (2026 only)
Funded engine: 1,000 paths of 252 sessions (block5, 2026 and 2026 H2) under each plan's funded rules (trailing type, lock,
buffer, payout min / max / share of balance, cycle days, winning days, consistency, split, payout count cap): first payout
time, chance of a payout before the account blows, expected trader's share in the first year. Rough: firms' payout rules are
the least documented part.

Cost per funded account = mean fee per eval attempt / pass-within-60-sessions rate + activation fee (an eval still open after
60 sessions counts as an attempt that did not pass). Monthly plans pay price x ceil(sessions / 21). List prices, no coupons,
no reset discounts.

  python tools/lit_prop_firms.py check     # MFFU Builder 50K scaled == the live eval sizing numbers (STRATEGY.md)
  python tools/lit_prop_firms.py all       # every plan -> research/lit/prop_firms.json  (2 processes)
Needs the unit trades: python tools/lit_prop_firms.py unit (about 1 minute, cached in research/runs/_cache/lit_prop_unit.json).
Paper only. Judged on 2026 (pick Jan-Jun, check Jul-Oct); 2021-25 is a reference line (5m only, no 1m data).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lit", "prop_firms.json")
UNIT = os.path.join(ROOT, "research", "runs", "_cache", "lit_prop_unit.json")
PV, COMM, SLIP = 2.0, 1.40, 0.25
SPAN = {"2026": ("2026-01-01", "2026-12-31"), "H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"),
        "2021-25": ("2021-01-01", "2025-12-31")}
H = 60
N_MC, N_FUND, FUND_H = 4000, 1000, 252
SEARCHED = "2026-10-18"

# ================================================================================================ the plans
# Sources: web search results read on 2026-10-18 (pages could not be opened from this sandbox: fetch blocked; every figure is
# from the search engine's reading of the page listed). "unconf" lists the fields that were not confirmed or conflict.
S_MFFU = ["https://help.myfundedfutures.com/en/articles/17036130-builder-plan-25k-a-comprehensive-look",
          "https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide",
          "https://help.myfundedfutures.com/en/articles/17005296-builder-plan-100k-comprehensive-guide",
          "https://help.myfundedfutures.com/en/articles/11802636-traders-evaluation-simplified",
          "https://myfundedfutures.com/plans/builder", "https://myfundedfutures.com/plans/rapid",
          "https://help.myfundedfutures.com/en/articles/16727601-rapid-eod-25k-a-comprehensive-look",
          "https://phidiaspropfirm.com/education/myfundedfutures-builder-plan",
          "https://phidiaspropfirm.com/education/myfundedfutures-rapid-plan",
          "https://propscope.net/en/plans/myfundedfutures-rapid/",
          "https://proptradingvibes.com/blog/myfundedfutures-rapid-eod",
          "https://traderpayout.com/prop-firm-news/myfundedfutures-rapid-eod-launch-explained",
          "https://www.eltraderfinanciado.com/en/news/myfundedfutures/my-funded-futures-launches-builder-25k-july-2026",
          "https://phidiaspropfirm.com/education/myfundedfutures-pro-plan", "https://pipback.com/blog/my-funded-futures-review"]
S_TOP = ["https://help.topstep.com/en/articles/14289835-topstep-pricing-and-payment-questions",
         "https://proptradingvibes.com/blog/topstep-trading-combine-rules", "https://tradecovex.com/guides/topstep-combine-rules-2026",
         "https://www.fundedfuturesfamily.com/topstep-activation-fee/"]
S_APEX = ["https://proptradingvibes.com/blog/apex-evaluation-account-rules", "https://phidiaspropfirm.com/education/apex-trader-funding-4-0-explained",
          "https://pickmytrade.trade/prop-firm-faq/apex-trader-funding-faq/", "https://www.eltraderfinanciado.com/en/review/apex-trader-funding",
          "https://prop-memo.com/en/articles/futures-prop-firms-automation-2026-09"]
S_TFY = ["https://help.tradeify.co/en/articles/10495915-growth-evaluation-accounts", "https://www.quantvps.com/prop-firms/tradeify",
         "https://tradetanto.com/learn/tradeify-rules-explained-what-every-trader-should-know", "https://propdatalab.com/firms/tradeify/",
         "https://phidiaspropfirm.com/education/tradeify-growth-vs-select-vs-lightning"]
S_LUC = ["https://propfirms.net/blogs/lucid-trading-review", "https://tradetanto.com/learn/lucid-trading-rules-explained-every-plan-rule-and-limit",
         "https://phidiaspropfirm.com/education/lucidflex-review", "https://proea.app/en/blog/lucid-trading-rules",
         "https://spicyfutures.com/lucid-trading-rules/"]
S_TPT = ["https://propfirmmap.com/firms/takeprofittrader", "https://pipback.com/blog/take-profit-trader-2026-review-payout-rules-explained",
         "https://tradecovex.com/guides/take-profit-trader-rules-2026", "https://damnpropfirms.com/futures-prop-firms/take-profit-trader/"]
S_ALPHA = ["https://alpha-futures.com/how-it-works", "https://alpha-futures.com/", "https://www.luxalgo.com/prop-firms/alpha-futures/",
           "https://propfirms.net/blogs/alpha-futures-review", "https://tradetanto.com/learn/alpha-futures-rules-every-plan-rule-and-limit",
           "https://blog.traderspost.io/article/alpha-ticks-review"]
S_FN = ["https://fundednext.com/futures/legacy", "https://fundednext.com/blog/futures-rapid-pro-rapid-daily-explained",
        "https://helpfutures.fundednext.com/en/articles/15878201-is-there-any-consistency-rule-in-the-fundednext-futures-rapid-daily-challenge-and-fundednext-account",
        "https://damnpropfirms.com/futures-prop-firms/fundednext/", "https://www.eltraderfinanciado.com/en/news/fundednext/fundednext-futures-account-restructure"]
S_BUL = ["https://funded.now/propfirm/bulenox", "https://tradecovex.com/guides/bulenox-rules-2026", "https://propscope.net/en/plans/bulenox-qualification/",
         "https://www.quantvps.com/blog/bulenox-payout-rules"]


def plan(pid, firm, name, size, price, ptype, target, mll, trail="eod", lock=100.0, dll=None, dll_type="soft", minis=None,
         cons=None, min_days=1, expiry=None, act=0.0, funded=None, bot="", news="", src=(), unconf=(), sold=True, note=""):
    return {"id": pid, "firm": firm, "plan": name, "size": size, "price": price, "price_type": ptype, "target": float(target),
            "mll": float(mll), "trail": trail, "lock": lock, "dll": dll, "dll_type": dll_type if dll else None,
            "max_micros": int(10 * minis) if minis else 40, "max_minis": minis, "cons": cons, "min_days": min_days,
            "expiry": expiry, "activation": act, "funded": funded or {}, "bot": bot, "news": news, "sources": list(src),
            "unconfirmed": list(unconf), "sold": sold, "note": note}


def F(trail="eod", lock=100.0, buffer=None, pay_min=500.0, pay_max=None, pay_pct=None, split=0.9, cons=None, every=1,
      win_days=0, win_min=0.0, cycle_days=0, max_payouts=None, first_wait=1, split_first=None, since_last=0.0, dll=None):
    return {"trail": trail, "lock": lock, "buffer": buffer, "pay_min": pay_min, "pay_max": pay_max, "pay_pct": pay_pct,
            "split": split, "cons": cons, "every": every, "win_days": win_days, "win_min": win_min, "cycle_days": cycle_days,
            "max_payouts": max_payouts, "first_wait": first_wait, "split_first": split_first, "since_last": since_last, "dll": dll}


def plans():
    P = []
    BOT_MFFU = "automation allowed with active oversight (policy unchanged Sep 2026; confirm with MFFU)"
    # ---- MyFundedFutures Builder (one-time since 2026-08-25, $0 activation; EOD trailing, soft DLL; funded 50% consistency)
    for sz, pr, tg, ml, dl, mn, pmin, pmax, unc in (
            (25, 105, 1500, 1000, 600, 2, 250, 1000, ["DLL: $600 soft per the current help center, none on the legacy 25K"]),
            (50, 153, 3000, 2000, 1000, 4, 500, 2000, []),
            (100, None, 6000, 3000, 1750, 6, 500, 3000, ["price not found", "payout min/max assumed (50K x 1.5)",
                                                         "the plan page lists only 25K and 50K for sale"]),
            (150, None, 9000, 4500, 2500, 8, 500, 4000, ["price not found", "max contracts not found (8 minis assumed)",
                                                         "payout min/max assumed", "the plan page lists only 25K and 50K for sale"])):
        P.append(plan(f"mffu_builder_{sz}k", "MyFundedFutures", "Builder", sz, pr, "one", tg, ml, dll=dl, minis=mn, cons=None,
                      min_days=1, funded=F(trail="eod", buffer=ml + 100, pay_min=pmin, pay_max=pmax, split=0.8, cons=0.5,
                                           cycle_days=2, max_payouts=5, first_wait=2),
                      bot=BOT_MFFU, news="allowed", src=S_MFFU, unconf=unc + ["price: list (coupons 40-50% off are common)"],
                      sold=sz <= 50, note="5 sim payouts, then live (80/20, daily, no consistency)"))
    # ---- MyFundedFutures Rapid (EOD in the eval, INTRADAY trailing once funded; 50% eval consistency, 2 days; daily payouts 90/10)
    for sz, pr, tg, ml, mn in ((25, 145, 1500, 1000, 3), (50, 209, 3000, 2000, 5), (100, 356, 6000, 3000, 8), (150, 463, 9000, 4500, 10)):
        P.append(plan(f"mffu_rapid_{sz}k", "MyFundedFutures", "Rapid", sz, pr, "one", tg, ml, dll=None, minis=mn, cons=0.5,
                      min_days=2, funded=F(trail="intra", buffer=ml + 100, pay_min=500, pay_max=None, split=0.9, cons=None),
                      bot=BOT_MFFU, news="allowed in the eval (Tier-1 news rules once funded: check)", src=S_MFFU,
                      unconf=["price: $145/$209/$356/$463 (Phidias) vs $109/$157/$267/$347 list (PropScope); one source says monthly",
                              "eval consistency 50% (one source says none)", "min 2 trading days (older article: none)"],
                      note="funded max loss trails INTRADAY (open profit counts), locks at start + $100"))
    # ---- MyFundedFutures Rapid EOD (Aug/Sep 2026: 25K and 50K only; 30% consistency, 4 days; EOD stays EOD funded)
    for sz, pr, tg, ml, mn, sl in ((25, 145, 1500, 1000, 2, 250), (50, 209, 3000, 2000, 3, 500)):
        P.append(plan(f"mffu_rapid_eod_{sz}k", "MyFundedFutures", "Rapid EOD", sz, pr, "one", tg, ml, minis=mn, cons=0.3, min_days=4,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=500, split=0.9, cons=None, since_last=sl),
                      bot=BOT_MFFU, news="allowed (check)", src=S_MFFU,
                      unconf=(["50K price $157 (launch article) vs $209"] if sz == 50 else []) + ["payout cap: none stated"]))
    # ---- MyFundedFutures Pro (50% eval consistency, EOD, payouts every 14 days, min $1,000, 80/20)
    for sz, pr, tg, ml, mn in ((50, 265, 3000, 2000, 5), (100, None, 6000, 3000, 8), (150, None, 9000, 4500, 10)):
        P.append(plan(f"mffu_pro_{sz}k", "MyFundedFutures", "Pro", sz, pr, "one", tg, ml, minis=mn, cons=0.5, min_days=1,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=1000, split=0.8, every=10, cons=None),
                      bot=BOT_MFFU, news="allowed in the eval, Tier-1 not allowed funded (sources conflict)", src=S_MFFU,
                      unconf=["max contracts not found (Rapid caps assumed)", "price: 'from $265' for 50K, others not found",
                              "min days not found"]))
    # ---- Topstep Combine (monthly + $149 activation; MLL EOD, real-time breach, locks at the start balance; 55% consistency)
    for sz, pr, tg, ml, mn in ((50, 49, 3000, 2000, 5), (100, 99, 6000, 3000, 10), (150, 149, 9000, 4500, 15)):
        P.append(plan(f"topstep_{sz}k", "Topstep", "Combine (Standard path)", sz, pr, "month", tg, ml, lock=0.0, minis=mn,
                      cons=0.55, min_days=2, act=149.0,
                      funded=F(trail="eod", lock=0.0, buffer=0.0, pay_min=125, pay_max=5000, pay_pct=0.5, split=0.9,
                               win_days=5, win_min=150.0),
                      bot="API allowed on Combine and XFA (TopstepX API), not on Live; no VPS/remote servers", news="allowed",
                      src=S_TOP, unconf=["150K price $149 vs $199", "XFA payout cap $5,000 assumed", "no DLL on TopstepX (optional elsewhere)"],
                      note="the No-Activation-Fee path is $95/mo (50K) with $0 activation"))
    # ---- Apex 4.0 EOD (one-time, 30-day expiry, no resets; EOD DLL; automation banned)
    for sz, pr, tg, ml, dl, mn, pmax in ((25, 177, 1500, 1000, 500, 4, 1000), (50, 197, 3000, 2000, 1000, 6, 1500),
                                         (100, 297, 6000, 3000, 1500, 8, 2000), (150, 397, 9000, 4000, 2000, 12, 2500)):
        P.append(plan(f"apex_eod_{sz}k", "Apex Trader Funding", "4.0 EOD", sz, pr, "one", tg, ml, dll=dl, minis=mn, cons=None,
                      min_days=1, expiry=21, act=99.0,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=500, pay_max=pmax, split=1.0, cons=0.5, win_days=5,
                               win_min=0.0, max_payouts=6, split_first=(25000.0, 0.9)),
                      bot="PROHIBITED (Apex bans automated trading on all accounts, Sep 2026)", news="allowed",
                      src=S_APEX, unconf=["prices $177-$397 EOD vs $118-$265 intraday (sources differ)", "DLL soft assumed",
                                          "PA payout caps and 5-day cycle assumed", "activation $79-$159 (sources differ)"]))
    # ---- Tradeify Growth (one-time, soft DLL, no eval consistency) and Select (no DLL, 40% eval consistency, 3 days)
    for sz, pr, tg, ml, dl, mn, pmax in ((25, 99, 1500, 1000, 600, 1, 1000), (50, 145, 3000, 2000, 1250, 4, 1250),
                                         (100, 255, 6000, 3500, 2500, 8, 2000), (150, 369, 9000, 5000, 3750, 12, 2500)):
        P.append(plan(f"tradeify_growth_{sz}k", "Tradeify", "Growth", sz, pr, "one", tg, ml, dll=dl, minis=mn, cons=None, min_days=1,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=250, pay_max=pmax, split=0.9, cons=0.35, win_days=5,
                               dll=dl),
                      bot="own bots allowed (not off-the-shelf); live video of you activating it may be required", news="allowed",
                      src=S_TFY, unconf=["funded payout cap / 5-day cycle assumed", "lock at start + $100 assumed"]))
    for sz, pr, tg, ml, mn, pmax in ((25, 109, 1500, 1000, 1, 1000), (50, 165, 3000, 2000, 4, 2000),
                                     (100, 265, 6000, 3000, 8, 2500), (150, 369, 9000, 4500, 12, 3000)):
        P.append(plan(f"tradeify_select_{sz}k", "Tradeify", "Select", sz, pr, "one", tg, ml, minis=mn, cons=0.4, min_days=3,
                      funded=F(trail="eod", buffer=0.0, pay_min=250, pay_max=pmax, pay_pct=0.5, split=0.9, cons=None,
                               win_days=5, win_min=150.0),
                      bot="own bots allowed (not off-the-shelf)", news="allowed", src=S_TFY,
                      unconf=["funded (Select Flex) payout rules assumed", "lock trigger 25K $26,100 vs $26,600"]))
    # ---- Lucid Trading: LucidPro (no eval consistency, soft DLL above 25K) and LucidFlex (50% eval consistency, no DLL)
    for sz, pr, tg, ml, dl, mn in ((25, 100, 1250, 1000, None, 2), (50, 140, 3000, 2000, 1200, 4), (100, 225, 6000, 3000, 1800, 6),
                                   (150, 420, 9000, 4500, 2700, 10)):
        P.append(plan(f"lucid_pro_{sz}k", "Lucid Trading", "LucidPro", sz, pr, "one", tg, ml, dll=dl, minis=mn, cons=None, min_days=1,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=500, pay_max=2000 * ml / 2000, split=0.9, cons=0.4, win_days=0),
                      bot="automated systems and copiers allowed (no HFT / hedging)", news="allowed", src=S_LUC,
                      unconf=["price $100/$140/$225/$420 vs $89/$129/$220/$420 vs $172 (50K)", "DLL soft/optional (sources differ)",
                              "funded payout cap / buffer assumed"]))
    for sz, pr, tg, ml, mn, pmax in ((25, 79, 1250, 1000, 2, 1000), (50, 136, 3000, 2000, 4, 2000), (100, 258, 6000, 3000, 6, 2500),
                                     (150, 372, 9000, 4500, 10, 3000)):
        P.append(plan(f"lucid_flex_{sz}k", "Lucid Trading", "LucidFlex", sz, pr, "one", tg, ml, minis=mn, cons=0.5, min_days=2,
                      funded=F(trail="eod", buffer=0.0, pay_min=500, pay_max=pmax, pay_pct=0.5, split=0.9, cons=None,
                               win_days=5, win_min=150.0),
                      bot="automated systems and copiers allowed", news="allowed", src=S_LUC,
                      unconf=["price varies $50-$150 at 50K (promos)", "5-winning-day rule possibly removed Feb 2026"]))
    # ---- Take Profit Trader (monthly + $130 activation; EOD test, 50% consistency, 3 days; PRO funded intraday trailing)
    for sz, pr, tg, ml, mn in ((25, 150, 1500, 1500, 3), (50, 170, 3000, 2000, 6), (75, 245, 4500, 2500, 9), (100, 330, 6000, 3000, 12),
                               (150, 360, 9000, 4500, 15)):
        P.append(plan(f"tpt_{sz}k", "Take Profit Trader", "Test", sz, pr, "month", tg, ml, lock=0.0, minis=mn, cons=0.5, min_days=3,
                      act=130.0, funded=F(trail="intra", lock=0.0, buffer=ml, pay_min=0.0, split=0.8, cons=None),
                      bot="not found (check before automating)", news="check (not confirmed)", src=S_TPT,
                      unconf=["drawdown lock at the start balance assumed", "min days 3 (new Tests from 2026-08-17) vs 5",
                              "activation $130 (sometimes waived)"]))
    # ---- Alpha Futures (monthly; EOD trailing that stops at the start balance; Zero: no eval consistency + daily guard)
    for sz, pr, tg, ml in ((50, None, 3000, 2000), (100, 239, 6000, 3000), (150, 349, 9000, 4500)):
        P.append(plan(f"alpha_std_{sz}k", "Alpha Futures", "Standard", sz, pr, "month", tg, ml, lock=0.0, minis=sz // 10, cons=0.5,
                      min_days=1, funded=F(trail="eod", lock=0.0, buffer=0.0, pay_min=200, pay_max=ml, pay_pct=0.5, split=0.9,
                                           cons=0.4, dll=0.02 * sz * 1000),
                      bot="semi-automated only (fully automated prohibited); NinjaTrader/Tradovate not offered for new accounts since 2026-07-12",
                      news="check", src=S_ALPHA,
                      unconf=["50K price not found", "150K price $349 vs $419", "max contracts not found (size/10 minis assumed)",
                              "funded payout rules assumed (cap = max loss per payout)"]))
    P.append(plan("alpha_zero_50k", "Alpha Futures", "Zero", 50, 139, "month", 3000, 2000, lock=0.0, dll=1000, minis=5, cons=None,
                  min_days=1, funded=F(trail="eod", lock=0.0, buffer=0.0, pay_min=200, pay_max=2000, pay_pct=0.5, split=0.9, cons=0.4, dll=1000),
                  bot="semi-automated only; no NinjaTrader for new accounts", news="check", src=S_ALPHA,
                  unconf=["target $3,000 assumed", "max contracts assumed", "daily guard soft assumed"]))
    P.append(plan("alpha_adv_50k", "Alpha Futures", "Advanced", 50, None, "month", 4000, 1750, lock=0.0, minis=5, cons=0.5,
                  min_days=1, funded=F(trail="eod", lock=0.0, buffer=0.0, pay_min=200, pay_max=1750, pay_pct=0.5, split=0.9, cons=None),
                  bot="semi-automated only; no NinjaTrader for new accounts", news="check", src=S_ALPHA,
                  unconf=["price not found", "eval consistency 40% vs 50%", "max contracts assumed"]))
    # ---- FundedNext Futures (one-time; Rapid Pro / Rapid Daily since 2026-07-10; Legacy 40% eval consistency)
    for sz, pr, tg, ml, dl, mn, cap in ((25, 79.99, 1500, 1000, 500, 2, 800), (50, None, 3000, 2000, 1000, 4, 1500),
                                        (100, None, 5000, 2500, 1250, 6, 2500)):
        P.append(plan(f"fn_rapid_pro_{sz}k", "FundedNext Futures", "Rapid Pro", sz, pr, "one", tg, ml, minis=mn, cons=None, min_days=1,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=250, pay_max=cap, split=0.9, cons=0.4, every=3),
                      bot="automation allowed (EAs, bots)", news="check", src=S_FN,
                      unconf=["50K/100K prices not found", "payout caps per size assumed from the $800-$2,500 range"]))
        P.append(plan(f"fn_rapid_daily_{sz}k", "FundedNext Futures", "Rapid Daily", sz, pr, "one", tg, ml, dll=dl, minis=mn, cons=None,
                      min_days=1, funded=F(trail="eod", buffer=ml + 100, pay_min=250, pay_max=cap, split=0.9, cons=None, dll=dl),
                      bot="automation allowed (EAs, bots)", news="check", src=S_FN,
                      unconf=["prices for 50K/100K not found", "DLL soft assumed", "payout caps assumed"]))
    for sz, pr, tg, ml, mn in ((25, 79.99, 1250, 1000, 2), (50, 199.99, 3000, 2000, 4), (100, 239.99, 6000, 3000, 6)):
        P.append(plan(f"fn_legacy_{sz}k", "FundedNext Futures", "Legacy", sz, pr, "one", tg, ml, minis=mn, cons=0.4, min_days=1,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=250, pay_max=None, split=0.8, cons=None),
                      bot="automation allowed (EAs, bots)", news="check", src=S_FN,
                      unconf=["prices conflict between sources", "funded split / payout rules assumed", "max contracts assumed"]))
    # ---- Bulenox Qualification (Option 2 = EOD + DLL; Option 1 = intraday trailing, no DLL; funded 40% consistency)
    for sz, pr, tg, ml, dl, mn, cap in ((25, 145, 1500, 1500, 500, 3, 1000), (50, 175, 3000, 2500, 1100, 7, 1500),
                                        (100, 215, 6000, 3000, 2200, 12, 1750), (150, 325, 9000, 4500, 3300, 15, 2000)):
        P.append(plan(f"bulenox_eod_{sz}k", "Bulenox", "Qualification Option 2 (EOD)", sz, pr, "month", tg, ml, dll=dl, minis=mn,
                      cons=None, min_days=1,
                      funded=F(trail="eod", buffer=ml + 100, pay_min=500, pay_max=cap, split=1.0, cons=0.4, split_first=(10000.0, 0.9),
                               dll=dl),
                      bot="commercial / shared bots banned (Sep 2026); own code: check", news="allowed (check)", src=S_BUL,
                      unconf=["max drawdown figures conflict (50K $2,500 vs others)", "contracts not confirmed",
                              "monthly vs one-time not confirmed", "DLL soft assumed", "funded buffer assumed"]))
    P.append(plan("bulenox_trail_50k", "Bulenox", "Qualification Option 1 (intraday trailing)", 50, 175, "month", 3000, 2500,
                  trail="intra", minis=7, cons=None, min_days=1,
                  funded=F(trail="intra", buffer=2600, pay_min=500, pay_max=1500, split=1.0, cons=0.4, split_first=(10000.0, 0.9)),
                  bot="commercial / shared bots banned; own code: check", news="allowed (check)", src=S_BUL,
                  unconf=["max drawdown 50K conflicts", "contracts not confirmed", "funded rules assumed"]))
    return P


# ================================================================================================ trades
def build_unit():
    from tools import lit_tightstop as T
    U = T.unit()
    keep = ("day", "entry_t", "exit_t", "dir", "risk_pts", "exit", "mfe", "mae", "legs", "w1", "wk_m", "tf")
    with open(UNIT, "w", encoding="utf-8") as fh:
        json.dump({"sess": list(T.SESS), "trades": [{k: t.get(k) for k in keep} for t in U]}, fh, default=float)
    print(f"wrote {UNIT}: {len(U)} unit trades")


_D = {}


def data():
    if not _D:
        if not os.path.exists(UNIT):
            build_unit()
        d = json.load(open(UNIT, encoding="utf-8"))
        sess = d["sess"]
        by = collections.defaultdict(list)
        for t in sorted(d["trades"], key=lambda t: t["entry_t"]):
            # (points, worst open points, best open points, stop points, weekly-stop multiplier)
            by[t["day"]].append((float(t["legs"][0][1]), float(t["w1"]), max(0.0, float(t["mfe"]) * float(t["risk_pts"])),
                                 float(t["risk_pts"]), float(t.get("wk_m") or 1.0)))
        _D.update(sess=sess, by=[by.get(s, []) for s in sess],
                  mon=np.array([dt.date.fromisoformat(s).weekday() == 0 for s in sess]))
    return _D


def span_idx(span):
    a, z = SPAN[span]
    s = data()["sess"]
    ix = [i for i, d in enumerate(s) if a <= d <= z]
    return ix[0], ix[-1] + 1


# ================================================================================================ sizing
def qty(t, P, rule, room):
    pts, w1, mfe, rp, wk = t
    if rule in ("scaled", "skip"):
        risk, ref = 800.0 * P["mll"] / 2000.0, 25.0
    else:
        risk, ref = 800.0, 20.0
    r = risk if rp <= ref else risk * ref / rp
    q = max(1, int(r / (rp * PV)))
    if wk < 1.0:
        q = max(1, int(q * wk + 1e-9))
    if rule in ("scaled", "skip") and room is not None:
        cap = int(0.6 * max(0.0, room) / (rp * PV))
        if cap < q:
            if rule == "skip" and cap < 1:
                return 0                        # research variant: even 1 micro would risk over 60% of the room -> no trade
            q = max(1, cap)
    return min(q, P["max_micros"])


def at_size(t, q):
    pts, w1, mfe, rp, wk = t
    comm = COMM * q
    pnl = pts * PV * q - comm
    low = min(0.0, w1 * PV * q - comm, pnl)
    return pnl, low, mfe * PV * q


# ================================================================================================ the eval
def run_eval(P, rule, seq, by):
    """One eval over the session indices seq. Returns (result, sessions, fee sessions)."""
    mll, tgt, dll, lock = P["mll"], P["target"], P["dll"], P["lock"]
    intra = P["trail"] == "intra"
    lockv = lock if lock is not None else 1e18
    bal = peak = 0.0
    floor = -mll
    best, active = 0.0, 0
    for k, si in enumerate(seq):
        if P["expiry"] and k >= P["expiry"]:
            return "FAIL", k
        cum = 0.0
        traded = False
        for t in by[si]:
            if dll and cum <= -dll:
                break
            q = qty(t, P, rule, bal + cum - floor)
            if q <= 0:
                continue
            pnl, low, up = at_size(t, q)
            traded = True
            if dll and cum + low <= -dll:
                if P["dll_type"] == "hard":
                    return "FAIL", k + 1
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
                up = min(up, 0.0)
            if bal + cum + low <= floor:
                return "FAIL", k + 1
            if intra and up > 0:
                peak = max(peak, bal + cum + up)
                floor = min(max(floor, peak - mll), lockv)
                if bal + cum + pnl <= floor:
                    return "FAIL", k + 1
            cum += pnl
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            active += 1
            best = max(best, cum)
        if bal >= tgt and active >= P["min_days"] and (P["cons"] is None or best <= P["cons"] * bal + 1e-9):
            return "PASS", k + 1
    return "OPEN", len(seq)


def fee(P, n):
    if P["price"] is None:
        return None
    return P["price"] * (math.ceil(max(1, n) / 21) if P["price_type"] == "month" else 1)


def summarize(P, res):
    N = len(res) or 1
    pc = lambda c: round(100.0 * c / N, 1)
    o = {"n": len(res)}
    for lab, h in (("2w", 10), ("1m", 20), ("60", 60)):
        o[f"pass_{lab}"] = pc(sum(1 for r, n in res if r == "PASS" and n <= h))
        o[f"fail_{lab}"] = pc(sum(1 for r, n in res if r == "FAIL" and n <= h))
    o["open_60"] = round(100 - o["pass_60"] - o["fail_60"], 1)
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    p = o["pass_60"] / 100.0
    o["evals_per_pass"] = round(1.0 / p, 2) if p > 0 else None
    fees = [fee(P, n) for r, n in res]
    if P["price"] is not None and p > 0:
        o["fee_per_attempt"] = round(float(np.mean(fees)), 2)
        o["cost_per_funded"] = round(float(np.mean(fees)) / p + P["activation"], 0)
    else:
        o["fee_per_attempt"] = o["cost_per_funded"] = None
    return o


def exact(P, rule, span, monday=False):
    D = data()
    a, z = span_idx(span)
    starts = [i for i in range(a, z) if not monday or D["mon"][i]]
    res = [run_eval(P, rule, list(range(i, min(z, i + H))), D["by"]) for i in starts]
    return summarize(P, res)


_SEQ = {}


def mc_seqs(span, n=N_MC, length=H, monday=False, seed=7):
    key = (span, n, length, monday, seed)
    if key not in _SEQ:
        D = data()
        a, z = span_idx(span)
        rng = np.random.default_rng(seed)
        st = np.arange(a, z - 5 + 1)
        mst = st[D["mon"][st]]
        out = []
        for _ in range(n):
            seq = []
            first = True
            while len(seq) < length:
                j = int(rng.choice(mst if (monday and first) else st))
                seq.extend(range(j, j + 5))
                first = False
            out.append(seq[:length])
        _SEQ[key] = out
    return _SEQ[key]


def mc(P, rule, span, monday=False):
    D = data()
    res = [run_eval(P, rule, s, D["by"]) for s in mc_seqs(span, monday=monday)]
    return summarize(P, res)


# ================================================================================================ the funded account
def run_funded(P, rule, seq, by):
    Fd = P["funded"]
    mll = P["mll"]
    intra = Fd["trail"] == "intra"
    lockv = Fd["lock"] if Fd["lock"] is not None else 1e18
    buf = Fd["buffer"] if Fd["buffer"] is not None else mll + 100
    dll = Fd.get("dll")
    bal = peak = 0.0
    floor = -mll
    paid = 0.0
    gross = 0.0
    n_pay = 0
    first = None
    cyc, last_bal, last_k = [], 0.0, 0
    for k, si in enumerate(seq):
        cum = 0.0
        traded = False
        blown = False
        for t in by[si]:
            if dll and cum <= -dll:
                break
            q = qty(t, P, rule, bal + cum - floor)
            if q <= 0:
                continue
            pnl, low, up = at_size(t, q)
            traded = True
            if dll and cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
                up = min(up, 0.0)
            if bal + cum + low <= floor:
                blown = True
                break
            if intra and up > 0:
                peak = max(peak, bal + cum + up)
                floor = min(max(floor, peak - mll), lockv)
                if bal + cum + pnl <= floor:
                    blown = True
                    break
            cum += pnl
        if blown:
            return {"paid": paid, "n": n_pay, "first": first, "blown": k + 1}
        bal += cum
        if bal <= floor:
            return {"paid": paid, "n": n_pay, "first": first, "blown": k + 1}
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            cyc.append(cum)
        # payout request at the end of the session
        if Fd["max_payouts"] and n_pay >= Fd["max_payouts"]:
            continue
        if k + 1 < Fd["first_wait"] or (k - last_k) < Fd["every"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or prof < Fd["since_last"]:
            continue
        if Fd["win_days"] and sum(1 for x in cyc if x >= max(Fd["win_min"], 0.01)) < Fd["win_days"]:
            continue
        if Fd["cycle_days"] and len(cyc) < Fd["cycle_days"]:
            continue
        if Fd["cons"] is not None and cyc and max(cyc) > Fd["cons"] * prof:
            continue
        amt = bal - buf
        if Fd["pay_pct"] is not None:
            amt = min(amt, Fd["pay_pct"] * bal)
        if Fd["pay_max"] is not None:
            amt = min(amt, Fd["pay_max"])
        if amt < max(Fd["pay_min"], 1.0):
            continue
        sp = Fd["split"]
        if Fd["split_first"]:
            lim, sp2 = Fd["split_first"]
            a1 = max(0.0, min(amt, lim - gross))
            share = a1 * sp + (amt - a1) * sp2
        else:
            share = amt * sp
        paid += share
        gross += amt
        n_pay += 1
        if first is None:
            first = k + 1
        bal -= amt
        last_bal, last_k, cyc = bal, k, []
    return {"paid": paid, "n": n_pay, "first": first, "blown": None}


def funded(P, rule, span):
    D = data()
    R = [run_funded(P, rule, s, D["by"]) for s in mc_seqs(span, n=N_FUND, length=FUND_H, seed=11)]
    fr = [r["first"] for r in R if r["first"]]
    return {"paths": len(R), "p_payout": round(100.0 * len(fr) / len(R), 1),
            "first_med": float(np.median(fr)) if fr else None,
            "blown_before_payout": round(100.0 * sum(1 for r in R if r["blown"] and not r["first"]) / len(R), 1),
            "blown_year": round(100.0 * sum(1 for r in R if r["blown"]) / len(R), 1),
            "paid_year_mean": round(float(np.mean([r["paid"] for r in R])), 0),
            "paid_year_med": round(float(np.median([r["paid"] for r in R])), 0),
            "payouts_mean": round(float(np.mean([r["n"] for r in R])), 2)}


def size_stats(P, rule):
    """Typical size on the plan (fresh account: full room) for the 2026 trades."""
    D = data()
    a, z = span_idx("2026")
    qs, rk = [], []
    for i in range(a, z):
        for t in D["by"][i]:
            q = qty(t, P, rule, P["mll"])
            qs.append(q)
            rk.append(q * t[3] * PV)
    return {"med_micros": float(np.median(qs)), "med_risk": round(float(np.median(rk))), "max_risk": round(max(rk)),
            "capped_pct": round(100.0 * sum(1 for q in qs if q >= P["max_micros"]) / len(qs), 1)}


def score_plan(P):
    out = {"id": P["id"]}
    for rule in ("scaled", "lit"):
        o = {"size": size_stats(P, rule)}
        o["exact"] = {s: exact(P, rule, s) for s in ("2026", "H1", "H2", "2021-25")}
        o["monday"] = {s: exact(P, rule, s, monday=True) for s in ("2026", "H1", "H2")}
        spans = ("2026", "H1", "H2") if rule == "scaled" else ("2026", "H2")
        o["mc"] = {s: mc(P, rule, s) for s in spans}
        o["mc_monday"] = {"2026": mc(P, rule, "2026", monday=True)}
        if rule == "scaled":
            o["funded"] = {s: funded(P, rule, s) for s in ("2026", "H2")}
        out[rule] = o
    if P["firm"] == "MyFundedFutures" and P["plan"] in ("Builder", "Rapid", "Rapid EOD") and P["size"] <= 50:
        out["skip"] = {"exact": {s: exact(P, "skip", s) for s in ("2026", "H1", "H2")},
                       "monday": {s: exact(P, "skip", s, monday=True) for s in ("2026", "H1", "H2")},
                       "mc": {s: mc(P, "skip", s) for s in ("2026", "H1", "H2")},
                       "trades_2026_fresh": trade_count(P)}
    return out


def trade_count(P):
    """Trades a fresh eval takes on the first 60 sessions of every 2026 start, skip vs scaled (how much the skip pauses)."""
    D = data()
    a, z = span_idx("2026")
    out = {}
    for rule in ("scaled", "skip"):
        n_tr, n_s = 0, 0
        for i in range(a, z):
            seq = list(range(i, min(z, i + H)))
            r, n = run_eval(P, rule, seq, D["by"])
            n_s += n
            n_tr += sum(1 for k in seq[:n] for _ in D["by"][k])
        out[rule] = round(n_tr / max(1, n_s) * 5, 2)
    return out


def _work(pids):
    PL = {p["id"]: p for p in plans()}
    return [score_plan(PL[i]) for i in pids]


def check():
    P = next(p for p in plans() if p["id"] == "mffu_builder_50k")
    P = {**P, "dll": None}
    for s in ("H1", "H2", "2026"):
        e = exact(P, "scaled", s)
        print("no DLL", s, {k: e[k] for k in ("pass_2w", "fail_2w", "pass_1m", "fail_1m", "pass_med")})
    P = next(p for p in plans() if p["id"] == "mffu_builder_50k")
    for s in ("H1", "H2", "2026"):
        e = exact(P, "scaled", s)
        print("DLL", s, {k: e[k] for k in ("pass_2w", "fail_2w", "pass_1m", "fail_1m", "pass_med")})
    print("expected (STRATEGY.md, eval mode): 2-week passes H1 37.5 / H2 29.5, fails 3.1 / 0.0, median 10.5 / 17.5")


def run_all(procs=2):
    import concurrent.futures as cf
    PL = plans()
    ids = [p["id"] for p in PL]
    chunks = [ids[i::procs] for i in range(procs)]
    res = {}
    with cf.ProcessPoolExecutor(max_workers=procs) as ex:
        for part in ex.map(_work, chunks):
            for r in part:
                res[r["id"]] = r
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "lit_prop_firms",
           "writeup": "research/writeups/lit-prop-firms.md", "rules_searched": SEARCHED,
           "trades": "exact live LIT signals at 1 micro (tools/lit_tightstop.unit, = run lit_live trade for trade), costs in",
           "sizing": {"scaled": "$800 x (max loss / $2,000) up to a 25-pt stop, then x 25 / stop; weekly stop; <= 60% of the room to "
                                "the max-loss floor; plan max contracts",
                      "lit": "$800 up to a 20-pt stop, then 800 x 20 / stop; weekly stop; plan max contracts"},
           "method": {"exact": "fresh eval on every session of the span, up to 60 sessions, only that span's sessions",
                      "monday": "the exact starts on a Monday", "mc": f"{N_MC} evals x 60 sessions, 5-session blocks from the span",
                      "mc_monday": "the same with the first block starting on a Monday (2026)",
                      "funded": f"{N_FUND} paths x {FUND_H} sessions, 5-session blocks, plan-scaled sizing with the room cap",
                      "cost_per_funded": "mean fee per attempt / pass-within-60 rate + activation; list prices; monthly = price x "
                                         "ceil(sessions/21); an eval open after 60 sessions counts as not passed",
                      "2w": "10 sessions", "1m": "20 sessions", "ever": "60 sessions"},
           "plans": [{**p, "results": res[p["id"]]} for p in PL]}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"), default=float)
    print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB, {len(PL)} plans)")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "unit":
        build_unit()
    elif cmd == "check":
        check()
    else:
        run_all(int(sys.argv[2]) if len(sys.argv) > 2 else 2)
