---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-17"
status: "rejected - 0 of 51 variants pass; the timing is no better than random cuts of the same size (chance). Paper only, nothing live changed."
source: "research/writeups/drift-switch-2026-11-17.md"
aliases:
  - "\"Edge stopped working\" switch"
---

# "Edge stopped working" switch

> [!failure] Verdict: rejected
> rejected - 0 of 51 variants pass; the timing is no better than random cuts of the same size (chance). Paper only, nothing live changed.

**Full title:** "Edge stopped working" switch - cut size when LIT's / ATLAS's own record drifts below expectation, restore on recovery

## Summary

Owner idea 2026-11-17. Each strategy watches its own record of finished trades (net R, 2021-11 on, paper trades included) and cuts its size to x0.5 / x0.25 / paper while the record drifts (last N trades sum <= 0 or -5R, last-N profit factor < 1 / 1.2, 4 / 6 / 8 losers in a row, cumulative R 5-15R under its 50 / 100-trade high), restoring as soon as the rule clears. 17 rules x 3 levels = 51 variants, scored on the stored lit_live 2026 trades + the 2021-25 REF trades and on the MFFU Builder 50K (LIT alone) and Rapid EOD 50K (LIT + ATLAS $500) with the same Monte Carlo paths as tools/money/stack_one_account.py, costs in. The long-window rules never fire in 2026, so 2026 money is untouched. In 2021-25 they halve the failed Builder evals (55% -> 28% within 60 sessions) and cut fees ($212 -> $166 per 6 months), but the payouts fall by the same amount: the Builder still makes -$7 instead of -$9 a month (noise), and the Rapid EOD falls from +$63 to +$12 a month. Cutting the same number of trades at random places in 2021-25 does as well (the best of the 51 beats 90% of random shifts, the headline rule 80.5%; 95% was needed). No variant passes the pre-registered gate; 2.0% of the random-shift controls pass it by luck.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[lit-risk-money|LIT risk and money]], [[stack-one-account-2026-11-16|More strategies on ONE MFFU account]]
- Runs: `none (research/lab/drift_switch.json)`
- Source: `research/writeups/drift-switch-2026-11-17.md`
- Back to [[ZEUS Home]]
