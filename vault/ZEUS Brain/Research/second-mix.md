---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-22"
status: "promising"
source: "research/writeups/second-mix.md"
aliases:
  - "LIT + the second strategies"
---

# LIT + the second strategies

> [!tip] Verdict: promising
> promising

**Full title:** LIT + the second strategies - one eval or two accounts? (EMA, MACD, S/R, Asia slot; sizes, eval odds, funded $)

## Summary

Owner's question (2026-10-22) - what is the best way to combine LIT with the three paper second strategies (London EMA pullback, MACD sweep divergence, S/R NY reclaim) and the LIT Asia slot, for the most money and evals passed within 2 weeks. 375 combinations were scored on the MFFU Builder 50K (fresh eval every session, costs in), picked on 2026 H1 and checked on H2. The LIT eval path was reproduced exactly first (57.1/5.9 H1, 52.2/0.0 H2). Putting second strategies on LIT's own eval does not hold up - the best H1 pick (LIT + MACD at LIT's size, 2-week pass 81.5%) falls below LIT alone in H2 (46.4% vs 52.2%), none of the top 20 H1 picks beats LIT in H2, and they block 12-15 LIT trades a half. Only LIT + EMA + Asia beats LIT in both halves (61.3/2.5 and 66.7/0.0) but needs Asia entries the PC route blocks and fails 24% of 2025 evals (LIT 1%). The better setup is two accounts - LIT alone on its eval, and EMA + MACD + S/R together on a second Builder 50K ($91.80) at LIT's two-week "need" size with a no-hedge guard - 2-week pass/fail 72.3/4.2 in H1 and 53.6/0.0 in H2, both accounts together +$76k / +$17k on the eval paths vs +$34k / +$9k. It is a 2026 bet - in 2025 and 2021-24 that second account fails 15-18% of evals in 2 weeks. Paper first; check MFFU's limit of one funded Builder per person.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[lit-more-entries|LIT more entries]]
- Runs: `mix_lit_alone, mix_acct2_ema_md_sr_need1, mix_acct2_ema_md_sr_300safe, mix_lit_ema_asia_need1, mix_lit_md_need1, mix_lit_ema_500safe`
- Source: `research/writeups/second-mix.md`
- Back to [[ZEUS Home]]
