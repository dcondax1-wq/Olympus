---
tags:
  - zeus/research
  - family/risk
  - verdict/promising
  - bot/zlarior
  - bot/atlas
  - bot/blitz
  - lane/rapid
type: "research"
date: "2026-11-16"
status: "promising - paper only. On the Builder 50K, adding ATLAS in the eval does NOT beat LIT alone (more 2-week fails). Adding it only after the account is funded does, in both 2026 halves. On a Rapid EOD ..."
source: "research/writeups/stack-one-account-2026-11-16.md"
aliases:
  - "More strategies on ONE MFFU account"
---

# More strategies on ONE MFFU account

> [!tip] Verdict: promising
> promising - paper only. On the Builder 50K, adding ATLAS in the eval does NOT beat LIT alone (more 2-week fails). Adding it only after the account is funded does, in both 2026 halves. On a Rapid EOD 50K, LIT + ATLAS beats LIT alone in both halves. 2021-25 pays about $0 either way.

**Full title:** More strategies on ONE MFFU account - LIT + ATLAS (+ BLITZ) on the Builder 50K and on a Rapid EOD 50K

## Summary

Owner 2026-11-16 - "it shouldn't take 2 months to get a payout". Stored LIT (live), ATLAS (live EMA + MACD + S/R, never opposite LIT) and BLITZ (account C, never opposite LIT / ATLAS) trades were merged onto one account. LIT keeps its live size. Each added trade risks min($ cap, 30% of the room, the soft daily loss left), so one full stop-out never goes past the $1,000 soft daily loss. Costs are in, and every mix runs on the same Monte Carlo paths as LIT alone. Builder 50K - ATLAS $500 on the FUNDED account only (the eval stays LIT alone) moves the first funded payout from 26 / 23.5 to 17 / 15 sessions (Jan-Jun / Jul-Oct) and the 6-month account from $779 / $753 to $1,202 / $1,205 a month after fees. Adding BLITZ $300 too gives 15 / 13 sessions and $1,313 / $1,347. Putting ATLAS in the eval passes faster (median 5-6 sessions instead of 9) but fails more evals in 2 weeks (3.1% / 1.6% vs 0.8% / 0.2%; 2021-25 20% vs 0.6%). Rapid EOD 50K - LIT + ATLAS $500 halves the slow 30%-rule eval (median 22 / 21 sessions instead of 40 / 38). That is still about a month, not 2 weeks. The account pays $5,022 / $2,301 a month instead of $815 / $799. In 2021-25 every mix makes about $0 a month.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-16]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]], [[Rapid lanes]]
- Refers to: [[second-mix|LIT + the second strategies]]
- Runs: `none (research/lab/stack_one_account.json)`
- Source: `research/writeups/stack-one-account-2026-11-16.md`
- Back to [[ZEUS Home]]
