---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/atlas
type: "research"
date: "2026-10-23"
status: "rejected"
source: "research/writeups/hq-continuation.md"
aliases:
  - "HQ continuation"
---

# HQ continuation

> [!failure] Verdict: rejected
> rejected

**Full title:** HQ continuation - first pullback after a directional London / NY leg (FVG / order block / 50%, CISD, stop hunt second leg)

## Summary

Owner (2026-10-23) - "a strategy that trades 2+ times a week, high-quality setups, with high probability and high profit." Tested as a trend-continuation family, the opposite of LIT's reversal. The setup - the London or NY session breaks its opening structure with a leg of k ATR, then the FIRST pullback into the leg's FVG / order block / 50%, a 5m trigger back in the trend, a structural stop and the next liquidity pool (or fixed R, banked R, partials) as the target. The second leg after a stop hunt of the pullback was tested too. 186,624 variants on CME NQ1! (costs $1.90 a micro + 1 tick, no look-ahead) were picked on 2026 H1 and checked on H2, 2025 and 2021-24, with a pre-2025 re-pick, placebos and chance counts. Answer - no. Nothing reaches the goal. The best win rate (+1R or more) at 2+ a week with a positive edge is 35-47% in a single period and never holds across periods. The H1 picks make money in 2026 (best +$17.4k H1 / +$4.6k H2 at 4 a week) and then lose $35k-$44k over 2021-24. The pre-2025 re-pick finds nothing at 2+ a week; at 1.5 a week its picks lose in 2026. A period's result says nothing about another (t-stat correlation H1 vs H2 0.008). Closest lead, chosen after looking - NY 4-ATR leg, FVG pullback, 1h trend, 1.5R with breakeven - is positive in all four periods with a 38-44% win rate, but trades only ~1 a week, earns $180-$530 a month and does not beat random entries in the same direction. Paper only, nothing built.

## Money first

- **Rejected.** As a mechanical rule set, trend continuation after a session leg does not give a high-probability edge on NQ:
  - at 2+ a week it wins +1R or more about 20-35% of the time, the same as LIT;
  - the versions that look good in one period fail in the others;
  - the setup rules do no better than random entries in the leg's direction.
- **The only shape that holds everywhere is the NY strong-leg pullback with a 1.5R target and breakeven** (peeked lead 2).
  - Its win rate is around 40%, at about 1 trade a week and a few hundred dollars a month.
  - It was found by looking at every period, so it would need fresh data (2026 Q4 onward) before anyone trusts it.
  - Its frequency also misses the owner's 2+ a week.
- **No change to LIT or ATLAS.** Nothing was built and nothing is switched on.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-23]]
- Strategies: [[ATLAS]]
- Refers to: [[allday|NQ around the clock]], [[lit-adv-continuation|LIT advanced report ch2-4]], [[second-ema|Second strategy next to LIT]]
- Runs: `hq_cont_h1_1, hq_cont_h1_2, hq_cont_h1_3, hq_cont_pre2025_1, hq_cont_pre2025_2, hq_cont_pre2025_3, hq_cont_peeked_1, hq_cont_peeked_2`
- Source: `research/writeups/hq-continuation.md`
- Back to [[ZEUS Home]]
