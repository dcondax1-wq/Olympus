---
title: Plan ranking - every allowed eval plan for Zlarior (LIT) + ATLAS by real money; MFFU Rapid EOD 50K first (MFFU confirms the 5-payout rule is Builder only), FundedNext Rapid Daily 50K second; Decide cards for both with at most 2 re-buys
family: money
date: 2026-11-22
status: ranking + 2 Decide cards (plan-rapid50k-max2-rebuys, plan-fundednext50k-max2-rebuys, recommend yes). Unlimited re-buys meet the pre-set 2021-25 loss bound for no plan; with the lead's re-buy limit (max 2) Rapid EOD 50K (-$311 vs $330) and FundedNext (-$169 vs $300) meet it, LucidPro does not (-$305 vs $252). Nothing bought, nothing live changed.
summary: Pre-registered (research/plans/DESIGN.md, 2 mechanics addenda before the scored run). LIT + ATLAS on ONE account per plan, ATLAS at its measured real fills (10 ticks a side), LIT as stored; eval = the live two_week LIT sizing on each plan's numbers + ATLAS's $250 / $500 lane + the best-day guard where the plan has one; funded = each plan's own payout rules from research/props/firm_rules.json (buffer, min, caps, consistency, win days, max payouts, split) with a stuck line; a failed eval / dead account is re-bought; 1,000 paths a market, every plan on the same paths. Validation: MFFU Rapid EOD 25K reproduces tools/money/rapid25_launch.py exactly (eval 85.5%, funded lost 27.2 / 38.0%, $800 a month Jul-Oct-like). 6-month net $ per account slot, Jul-Oct-like / Jan-Jun-like / 2021-25-like: Rapid EOD 50K $13,691 / $30,010 / -$560 (but $6,749 / $14,544 if MFFU stops at 5 sim payouts), FundedNext Rapid Daily 50K $9,926 / $11,887 / -$650, LucidPro 50K $8,162 / $7,622 / -$927, LucidFlex 50K $7,479 / $8,330 / -$637, Builder 50K $7,371 / $7,253 / -$574, Rapid EOD 25K $4,801 / $11,301 / -$300 ($2,850 capped), Builder 25K $2,904 / $3,288 / -$324. Apex, Take Profit Trader, Alpha, Tradeify, Topstep, Bulenox not ranked (their rules ban the bots or the cross-firm copy, or need a paid API).
runs: research/plans/rank.py -> research/plans/results.json; research/plans/cap5.py (labelled sensitivity)
---

## For the owner

**Settled 2026-11-22 from MFFU's own pages:** the "5 sim payouts, then live" rule is **Builder only** ("Builder Plans: Transition
to a Live Account after: 5 consecutive payouts", help article 13745661). A Rapid / Rapid EOD account has **no payout cap** and moves
live only at **$10,000 net in one session** (automatic) or when MFFU's Risk Management Team picks it (article 13134718). At ANY live
move "all simulated trading accounts and additional purchases are suspended" (the Rapid, the Builders, the evals go dormant), up
to $5,000 of sim profit goes to a Reserve, and several Rapids are combined into one live account. So the uncapped row below is
the right one for the Rapid - but a Builder's 5th payout would pause it too. (research/lit/mffu_rules.json rapid_eod_*.live_rules_2026_11_22.)

**The 2 buys (Decide cards), each with at most 2 re-buys:**

| Card | Price | Jul-Oct-like a month | Jan-Jun-like a month | 2021-25-like, 6 months | Worst case | First payout (median) |
|---|---|---|---|---|---|---|
| plan-rapid50k-max2-rebuys: MFFU Rapid EOD 50K | $165 | **+$2,282** | +$5,001 | -$311 (95% of runs lose) | -$495 (3 evals) | ~9 weeks after the buy |
| plan-fundednext50k-max2-rebuys: FundedNext Rapid Daily 50K | ~$150 | **+$1,546** | +$1,679 | -$169 (89% lose) | -$450 | ~5 weeks |
| (not carded) LucidPro 50K | ~$126 | +$1,350 | +$1,257 | -$305 (over its $252 bound) | -$378 | ~7 weeks |

The full ranking (unlimited re-buys):

Money to you in 6 months from ONE account slot (after the firm's split, minus every eval fee and re-buy; before tax):

| # | Plan | Price | Jul-Oct-like market (6 mo / a month) | Jan-Jun-like | 2021-25-like | Eval pass (sessions) | $ back per $1 of fees | Lose a funded account | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **MFFU Rapid EOD 50K** | $165 | **$13,691 / $2,281** | $30,010 | -$560 | 92% (~22) | 58x | 36% | **only $6,749 / $14,544 if MFFU stops sim payouts at 5** (your brief's rule) |
| 2 | **FundedNext Rapid Daily 50K** | $150 | $9,926 / $1,654 | $11,887 | -$650 | 85% (~7) | 19x | 34% | 5 payouts of max $1,200 an account, then a new eval; 15th payout on the profile = live review |
| 3 | **LucidPro 50K (DLL on)** | ~$126 | $8,162 / $1,360 | $7,622 | -$927 | 85% (~7) | 37x | **14%** (safest) | 5 payouts then live move; needs Lucid's written OK for the same bot at two firms |
| 4 | LucidFlex 50K | ~$134 | $7,479 / $1,246 | $8,330 | -$637 | 89% (~17) | 30x | 17% | price set at checkout (unquoted) |
| 5 | MFFU Builder 50K | $91.80 | $7,371 / $1,228 | $7,253 | -$574 | 85% (~7) | 39x | 18% | your current kind; 5 payouts max |
| 6 | MFFU Rapid EOD 25K | $97.20 | $4,801 / $800 | $11,301 | -$300 | 86% (~26) | 34x | 38% | $2,850 if MFFU stops at 5 payouts |
| 7 | MFFU Builder 25K | $63 | $2,904 / $484 | $3,288 | -$324 | 83% (~8) | 25x | 23% | cheapest, smallest |
| - | Apex, Take Profit Trader, Alpha Futures | - | not allowed | | | | | | their rules ban bots |
| - | Tradeify, Bulenox, Topstep | - | not allowed | | | | | | one strategy across firms banned / bots need approval + no cross-firm copy / TopstepX only (paid API) |

What it means:
- **The 50K plans win; the 25Ks are the weakest buys.** A 50K slot makes $7,000-$14,000 in 6 months in a Jul-Oct-like market
  vs $2,900-$4,800 for a 25K, for $30-$100 more in price.
- **Which 50K is first depends on one MFFU fact.** If MFFU keeps paying Rapid accounts past 5 payouts, the Rapid EOD 50K is
  clearly best (daily payouts, 90%). If its 5-sim-payout rule ends the run (your brief: "only 5 sim payouts"), FundedNext
  Rapid Daily 50K and LucidPro 50K come out ahead of it.
- **LucidPro is the safest** (14% chance of losing a funded account in 6 months vs 34-38% for the daily-payout plans).
- **Every plan loses in a 2021-25-like market** (-$300 to -$927 a slot from failed evals and re-buys). That is why no
  plan passes the safety bar set before the test, and why there is no Decide card: set a re-buy limit before buying.

## How it was run (DESIGN.md, committed before the run)
- Trades: LIT + ATLAS per session (stack_one_account.mix_by), ATLAS re-priced to 10 ticks a side (tools/atlas_risk.T_at(10)),
  LIT as stored. MFFU Rapid funded with its Tier-1 news ban.
- Eval: tools/money/rapid_levers.Ev (live two_week LIT sizing on the plan's target / drawdown / max micros, ATLAS lane $250 on a
  25K / $500 on a 50K at 30% of the room, soft day = the firm's daily loss or $500 / $1,000, best-day guard where the eval
  has a consistency rule).
- Funded: research/plans/rank.Funded = tools/account4_sim.Lucid's generic payout logic on each plan's own rules
  (tools/account4_sim.rules from research/props/firm_rules.json) + ATLAS's lane; request the cap where the plan has one, else
  the minimum + the bot's own Rapid cushion ($500 / $1,000 above the buffer, engine/rapid.py); stuck under $100 (25K) /
  $200 (50K) of room = dead.
- One slot per plan, 126 sessions, re-buy the next session after a failed eval / dead account / last payout, 1,000 week-block
  paths a market, all plans on the same paths. Prices: owner's real MFFU prices; Lucid / FundedNext = code prices from the
  corvette plan (unconfirmed).
- Validation: the MFFU Rapid EOD 25K row equals tools/money/rapid25_launch.py's R3 at 10 ticks (eval 85.5%, lost 27.2 / 38.0%,
  $4,801 = $800 a month Jul-Oct-like).

## Caveats
- One slot at a time. Firm-wide caps are not modelled in the main table: MFFU 5 funded at once and (brief) 5 sim payouts
  (sensitivity shown), Lucid 5 funded / live move closes every sim account, FundedNext live review at the 15th payout on the profile.
- Same bots on every firm = the accounts win and lose together (a bad week hits all of them).
- Lucid / FundedNext prices and some of their rules are third-party or unconfirmed (corvette-plan caveats). Lucid's OK for
  the same bot at MFFU is still unread.
