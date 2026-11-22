---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-22"
status: "adopt-candidate"
source: "research/writeups/scale-plan.md"
aliases:
  - "The scaling plan"
---

# The scaling plan

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** The scaling plan - from 2 accounts (LIT 50K + ATLAS 25K) to 10, when to add each one, what it pays and what a bad year does

## Summary

Owner (2026-10-22) - "LIT is on the 50K, ATLAS (EMA+MACD+S/R, account B) on the 25K, then eventually we just scale. And keep scaling." A ladder of five steps (2 / 4 / 6 / 8 / 10 accounts, two accounts a week apart per step) was modelled with the stored studies' own executors (LIT - tools/lit_funded_combo.py on the live LIT trades, scale-in off; ATLAS - tools/second_account_b.py), on the same Monte Carlo paths so the accounts win and lose together. Next accounts - LucidPro 50K and FundedNext Rapid Daily 50K (bots and copying your own accounts allowed); MFFU holds LIT once (Builder 50K) and ATLAS once (Builder 25K). Each step waits for a payout trigger (first payout; then 3 funded + $2,000 paid; 4 funded + $5,000; 6 funded + $10,000) and for cash (a $300 budget + payouts - fees). On Jul-Oct 2026 trades (the half to quote) the steps pay about $1,160 / $2,850 / $4,600 / $6,100 / $7,900 a month once held, reached in a median 2.1 / 3.6 / 5.1 / 6.5 months for about $440 / $670 / $1,010 / $1,410 of evals. On 2025 trades the same steps pay $90-560 a month and the payout triggers stop the ladder by themselves - only 13% of 2025-like paths reach 10 accounts in 24 months, and the 24-month result is about break-even (median +$100, 1 in 10 -$1,660). Risk at the same moment - typical $300-2,060, worst $1,600-4,700; a $3,000 cross-account cap is proposed. Paper only; nothing live changed.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Source: `research/writeups/scale-plan.md`
- Back to [[ZEUS Home]]
