---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - lane/rapid
type: "research"
date: "2026-11-17"
status: "mostly negative - paper only. 36 variants were scored on MFFU's own payout rules. No second target, high-win-rate scalp or daily profit lock gets the first payout sooner in both 2026 halves. One row ..."
source: "research/writeups/rule-native-2026-11-17.md"
aliases:
  - "Rule-native search"
---

# Rule-native search

> [!success] Verdict: adopt-candidate
> mostly negative - paper only. 36 variants were scored on MFFU's own payout rules. No second target, high-win-rate scalp or daily profit lock gets the first payout sooner in both 2026 halves. One row passes the pre-set rule. That row adds the existing BLITZ (at most 3 a day, $300) to the Rapid EOD 50K, with the first payout about 8 / 5 days sooner and +$822 / +$313 a month. It is only a lead, not an adopt-candidate. Its 3-a-day cap was chosen after the "every signal" row had been seen, the ...

**Full title:** Rule-native search - pick by "days to the first payout" and "P(no payout in 6 months)" instead of PF / net $ (Rapid EOD 50K and Builder 50K)

## Summary

Owner idea 2026-11-17. MFFU pays on winning days (Rapid EOD eval best day <= 30%, funded daily above $2,100; Builder funded best day <= 50%, $2,600 above start). LIT is lumpy, so every variant was scored on the owner's two numbers, using the same trades, costs ($1.90 a micro + 1 tick) and Monte Carlo paths as stack_one_account / rapid_levers. Base rows are today's plan. Rapid EOD 50K is LIT + ATLAS $500 with the 30% guard and a $1,000 cushion kept. Its first payout comes 50 / 62 days after buying (Jan-Jun / Jul-Oct), there is a 2.4% / 8.9% chance of no payout in 6 months, and it makes $6,014 / $2,824 a month. Builder 50K is a LIT eval, then LIT + ATLAS $500 once funded: 49 / 49 days, 4.7% / 7.1%, $1,202 / $1,205 a month. Tested: (A) LIT second smaller target, 50% at 1 / 2 / 3R or 33% at 2R, everywhere or only where the consistency rule bites (8 per account); (B) ATLAS half off at 1R or a fixed 1R; (C) BLITZ as a scalp layer, first signal a day with its live exit, a fixed 1R or a fixed 0.5R (win rate 63-66%), and at most 2 or 3 a day; (D) an add-on profit lock at +$300 / +$600; alone rows. Partials cut money and do not speed the payout: LIT's 8R winners are what pay. The high-win first-signal scalp is too small to move anything. BLITZ alone at $300 never passes the eval. Rapid + BLITZ max 3 a day passes the rule: 42 / 57 days, 2.6% / 9.5%, $6,836 / $3,137 a month, 2021-25 +$68 vs +$63, and BLITZ itself makes 4.5-5.9 trades a week with PF 1.48 / 1.51 / 1.03. Only 2 of the 3 Jan-Jun winners also win Jul-Oct, against 1.5 expected by a coin flip. Builder: nothing passes. ATLAS half at 1R is about 1 day faster and +$45 a month, which is inside the noise.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Rapid lanes]]
- Refers to: [[scalp-na-mffu|BLITZ]]
- Runs: `none (research/lab/rule_native.json)`
- Source: `research/writeups/rule-native-2026-11-17.md`
- Back to [[ZEUS Home]]
