---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-10-22"
status: "finding"
source: "research/writeups/retail-standalone.md"
aliases:
  - "Retail strategies on their own"
---

# Retail strategies on their own

> [!info] Verdict: finding
> finding

**Full title:** Retail strategies on their own (EMA, MACD, support/resistance incl. ORB, supply/demand) - which versions make money on NQ

## Summary

The owner asked whether EMA, MACD, support/resistance and supply/demand strategies make money on their own, separate from LIT. 13,320 versions (8,636 with different trades) were tested as standalone NQ strategies on real CME NQ1! 5m data, with costs ($1.40 a micro + 1 tick slippage), structural stops, picked on 2021-11..2024-12 and checked untouched on 2025 and 2026. Three families have versions that made money in all three periods. The best robust ones: S/R bounce at the prior-day / overnight high and low (+$40.3k / +$36.1k / +$6.1k at $500 risk a trade, PF 1.20 / 1.79 / 1.16), the 8/21 EMA opening-hour momentum (+$37.9k / +$23.8k / +$5.4k, PF 1.11 / 1.25 / 1.07) and the 15m EMA ribbon (+$41.6k / +$12.6k / +$2.5k). PD/ON break-and-retest with a limit at the level is the strongest in 2026 (PF 3.13, +$21.2k) but was flat in 2025. MACD versions picked in-sample are flat to negative in 2026. Supply/demand loses in almost every version. All edges are thin next to LIT (2026 PF 1.1-1.2 vs 4.07), 2026 H2 is negative for most, and the eval odds are far worse than LIT's. Correlation with LIT is low (-0.1 to +0.26). Worth paper-trading the PD/ON bounce and the opening-hour EMA as a second-account idea; not worth real money yet.

## Money first

- **Do they make money? Some versions, yes, measured honestly:** the PD/ON bounce, the 8/21 opening-hour EMA and the 15m
  ribbon made money in 2021-24, 2025 and 2026 with costs in, structural stops and parameters chosen before 2025. The best
  robust one made about $1,000 a month in 2021-24, $2,950 a month in 2025 and $630 a month in 2026 at $500 risk.
- **How much next to LIT:** much less. LIT 2026 is PF 4.07 and +$43.4k; the best retail version is PF 1.16 and +$6.1k, with
  a losing Jul-Oct 2026. MACD and supply/demand did not hold up out of sample in any version picked fairly.
- **As a second strategy:** low correlation with LIT (-0.1 to +0.13 for the robust ones) is the good part. **Paper-trade the
  PD/ON bounce and the opening-hour EMA** (both rules are short enough for the cloud monitor) and judge them on live paper
  months before any account. Nothing here changes LIT; `engine/lit.py`, `live_model*.json` and the live loop are untouched.
- Open idea: the bounce and LIT both live on prior-day levels; a bounce only on levels LIT did not sweep that day would be the
  natural next test.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-22]]
- Refers to: [[second-ema|Second strategy next to LIT]], [[second-md|Second strategy next to LIT]], [[second-sr|A second strategy next to LIT]]
- Runs: `retail_sa_sr_sr_bounce_plateau, retail_sa_ema_ema_openhour_plateau, retail_sa_ema_ema_ribbon_best, retail_sa_sr_sr_limit_best, retail_sa_sr_orb_plateau, retail_sa_sr_orb_best, retail_sa_macd_macd_zero_best, retail_sa_macd_macd_cross_best, retail_sa_macd_macd_cross_plateau, retail_sa_macd_macd_hist_b`
- Source: `research/writeups/retail-standalone.md`
- Back to [[ZEUS Home]]
