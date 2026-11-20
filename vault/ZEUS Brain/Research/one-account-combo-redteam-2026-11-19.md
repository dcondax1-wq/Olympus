---
tags:
  - zeus/research
  - family/risk
  - verdict/research
  - bot/zlarior
  - bot/atlas
  - lane/combo50k
type: "research"
date: "2026-11-19"
status: "done - paper only. The study's numbers are computed right (an independent re-build gets the same $ within noise), but the Jul-Oct gain (+$572 a month) rests on 5 ATLAS days; without them it is about ..."
source: "research/writeups/one-account-combo-redteam-2026-11-19.md"
aliases:
  - "Red team"
---

# Red team

> [!abstract] Verdict: research
> done - paper only. The study's numbers are computed right (an independent re-build gets the same $ within noise), but the Jul-Oct gain (+$572 a month) rests on 5 ATLAS days; without them it is about $0. Jan-Jun gain is solid; 2021-25 is ~$0 and 2022 is worse. Verdict - "only if" (see the last line). Nothing live changed.

**Full title:** Red team - Zlarior + ATLAS on ONE Builder 50K (one-account-combo-2026-11-19.md)

## Summary

Owner 2026-11-19 "don't give me bullshit results". Skeptic check of the one-account combo study (design 4e682267, results 2fbb392e). Own simulator written from research/lit/mffu_rules.json + the live engine sizing functions (engine/sizing.lit_qty / funded_qty, engine/account_b.qty / funded_qty), not the study's helpers. Same headline within Monte Carlo noise (Jul-Oct Zlarior alone $736 vs study $714, Zlarior + ATLAS $1,305 vs $1,286, gap +$569 vs +$572). Breaks - remove ATLAS's 5 best Jul-Oct days (25.5 of its 27.9 R) and the gain is -$23 a month; resampling the 16 Jul-Oct weeks themselves, the gain is <= $0 in 14% of histories; week-block bootstrap puts the Jul-Oct 2-week eval fails at 8.8% (study 2.1%); MFFU's move to live after the 5th payout (a funded combo reaches it in 81% of Jul-Oct runs vs 33%) cuts the Jul-Oct gain to +$428; 2022 alone -$108. Holds - trade inputs = the repo's stored trades (Zlarior 631/631 = research/anatomy, ATLAS 100% = the second_mix member cache), no exits after 16:00, no overlaps, first-in, shared EOD floor, 40 micros, costs; +2 ticks each way +$533; Zlarior priority instead of first-in +$484; LIT-armed block no change.

## Money first

Put Zlarior + ATLAS on the Builder 50K: **only if** the lead first builds the account-level lock of section 6 (one
position, cancel Zlarior's resting order when ATLAS fills, one bracket, one fleet-wide direction) and it passes Sim, and you
take the gain as "likely, not sure": Jan-Jun-like +$700 to +$1,100 a month (solid), Jul-Oct-like about +$570 (it rests on
ATLAS's few big trend days; 1 in 7 resampled histories is $0 or worse), 2021-25-like about $0 with 2-3x the eval re-buys
(2022-like -$110). The study's "8 passed, 1 proposed" is counted right, but its "> 2 standard errors" is Monte Carlo noise,
not proof about the next months.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-19]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[50K combo]]
- Refers to: [[atlas|ATLAS]], [[atlas-health-2026-11-18|ATLAS health]]
- Runs: `none (scratch only; numbers below)`
- Source: `research/writeups/one-account-combo-redteam-2026-11-19.md`
- Back to [[ZEUS Home]]
