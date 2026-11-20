---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/parameter-robustness.md"
aliases:
  - "Parameter robustness"
---

# Parameter robustness

> [!info] Verdict: finding
> finding

**Full title:** Parameter robustness: does the lock sit on a plateau or on a peak?

## Summary

Mostly a plateau, with one ridge. Cold size, late size, the trending-day breakeven (anything from +3R to never gives the same money), the $ risk and the wide-stop rule all move smoothly. The exception is the cold-streak lookback of 15 signals: 15 and 16 give +$16.4k / +$16.9k in 2021-25, but 14 gives +$13.3k, 13 gives +$7.8k and 17 gives +$10.7k, so about half of the 5-year gain over the morning rules (+$6.5k) depends on that one number. Every one of 105 neighbouring combinations stays profitable in both periods (2021-25 worst +$6.8k, 2026 worst +$19.6k). The lock has 17 of 55 rolling 6-month windows negative (morning rules 22) and a longest flat stretch of 68 weeks (85).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-17]]
- Runs: `sens_lb12, sens_lb13, sens_lb17, sens_lb18, sens_cold015, sens_cold020, sens_cold030, sens_cold035, sens_late035, sens_late065, sens_betrend250, sens_betrend350, sens_betrend350_replay, sens_regime040, sens_regime050, sens_regime050_replay, sens_ref15, sens_ref25, sens_usd700, sens_usd900, baseline,`
- Source: `research/writeups/parameter-robustness.md`
- Back to [[ZEUS Home]]
