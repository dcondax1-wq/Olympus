---
tags:
  - zeus/research
  - family/money
  - verdict/research
  - bot/zlarior
  - bot/atlas
  - lane/rapid
type: "research"
date: "2026-11-22"
status: "ranking + 2 Decide cards (plan-rapid50k-max2-rebuys, plan-fundednext50k-max2-rebuys, recommend yes). Unlimited re-buys meet the pre-set 2021-25 loss bound for no plan; with the lead's re-buy limit ..."
source: "research/writeups/plan-ranking-2026-11-22.md"
aliases:
  - "Plan ranking"
---

# Plan ranking

> [!abstract] Verdict: research
> ranking + 2 Decide cards (plan-rapid50k-max2-rebuys, plan-fundednext50k-max2-rebuys, recommend yes). Unlimited re-buys meet the pre-set 2021-25 loss bound for no plan; with the lead's re-buy limit (max 2) Rapid EOD 50K (-$311 vs $330) and FundedNext (-$169 vs $300) meet it, LucidPro does not (-$305 vs $252). Nothing bought, nothing live changed.

**Full title:** Plan ranking - every allowed eval plan for Zlarior (LIT) + ATLAS by real money; MFFU Rapid EOD 50K first (MFFU confirms the 5-payout rule is Builder only), FundedNext Rapid Daily 50K second; Decide cards for both with at most 2 re-buys

## Summary

Pre-registered (research/plans/DESIGN.md, 2 mechanics addenda before the scored run). LIT + ATLAS on ONE account per plan, ATLAS at its measured real fills (10 ticks a side), LIT as stored; eval = the live two_week LIT sizing on each plan's numbers + ATLAS's $250 / $500 lane + the best-day guard where the plan has one; funded = each plan's own payout rules from research/props/firm_rules.json (buffer, min, caps, consistency, win days, max payouts, split) with a stuck line; a failed eval / dead account is re-bought; 1,000 paths a market, every plan on the same paths. Validation: MFFU Rapid EOD 25K reproduces tools/money/rapid25_launch.py exactly (eval 85.5%, funded lost 27.2 / 38.0%, $800 a month Jul-Oct-like). 6-month net $ per account slot, Jul-Oct-like / Jan-Jun-like / 2021-25-like: Rapid EOD 50K $13,691 / $30,010 / -$560 (but $6,749 / $14,544 if MFFU stops at 5 sim payouts), FundedNext Rapid Daily 50K $9,926 / $11,887 / -$650, LucidPro 50K $8,162 / $7,622 / -$927, LucidFlex 50K $7,479 / $8,330 / -$637, Builder 50K $7,371 / $7,253 / -$574, Rapid EOD 25K $4,801 / $11,301 / -$300 ($2,850 capped), Builder 25K $2,904 / $3,288 / -$324. Apex, Take Profit Trader, Alpha, Tradeify, Topstep, Bulenox not ranked (their rules ban the bots or the cross-firm copy, or need a paid API).

## Links

- Family: [[Family money]]
- Day: [[Day 2026-11-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[Rapid lanes]]
- Runs: `research/plans/rank.py -> research/plans/results.json; research/plans/cap5.py (labelled sensitivity)`
- Source: `research/writeups/plan-ranking-2026-11-22.md`
- Back to [[ZEUS Home]]
