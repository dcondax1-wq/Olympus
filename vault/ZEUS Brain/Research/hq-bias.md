---
tags:
  - zeus/research
  - family/bias
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-23"
status: "rejected - nothing adopted; no lead worth a paper slot"
source: "research/writeups/hq-bias.md"
aliases:
  - "HQ bias"
---

# HQ bias

> [!failure] Verdict: rejected
> rejected - nothing adopted; no lead worth a paper slot

**Full title:** HQ bias - top-down draw on liquidity (the HTF draw picks the direction and the target, LIT's chain enters)

## Summary

Owner (2026-10-23) wants 2+ trades a week with a high win rate and a high payoff. This study tried a top-down draw-on-liquidity strategy. A daily or weekly bias, read from the higher-time-frame draw, sets the trade's DIRECTION and its TARGET (the nearest untested HTF pool - PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG, 4H/daily FVGs - capped at a fixed R). LIT's 5m chain, an FVG pullback or a market entry then takes only the setups that point at that draw. 41,472 variants were run (12 bias methods x pools x target x cap x BE x entry x LIT filters x killzones x trades a day). CME NQ1! data, $1.90 a micro + 1 tick, 2026 on true 1m bars, look-ahead check 46/46 identical. It does not work. Only 8 variants meet the bar on 2026 H1 (>= 2 trades a week, >= 40% true winners at +1R or more, average winner >= 1.5R), and none meets it on 2021-24. The H1 ranking says nothing about H2 (Spearman 0.08) or 2021-24 (-0.01). Best H1 pick (weekly-candle bias, killzones, 3R cap) - H1 43% win, PF 3.95, +$17.2k; H2 28% win, 1.6 trades a week, +$432; 2021-24 -$15.8k. Its H1 edge is no better than a coin-flip bias in H2 (random-bias placebo p 0.41-0.58). Best all-round (nearest PDH/PDL, 3R cap) - H2 38% win, +$380, 2025 +$11.2k, 2021-24 -$11.6k. The pre-2025 re-pick loses in both 2026 halves. Eval path - alone on a 50K, H2 2-week pass 0-22% (LIT 52%); next to LIT it adds nothing (H2 50.7/0.0 vs LIT 52.2/0.0); on a 25K account B 0-22% in H2 (ATLAS 43.5%). Paper only.

## Money first

- **Rejected.** A top-down HTF draw on liquidity, used as both the direction and the target, does not give NQ a
  high-probability edge.
- The owner's wish for 2+ trades a week, 40%+ true winners and 1.5R+ winners was met only in the half where the rules were
  picked.
- LIT stays the strategy. Its edge comes from the far target (the VIX band, winners average 3.7-5.3R). A near HTF target
  raises the win rate but kills the payoff, and on NQ the two do not combine into more money.
- Combined with LIT on the 50K or as a 25K account B, the candidates are worse than what is already built (LIT alone;
  ATLAS on the 25K).
- Don't redo this without a genuinely new direction signal. The same pools with other caps / BE / killzones are now mapped.

## Links

- Family: [[Family bias]]
- Day: [[Day 2026-10-23]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-bias-discretion|LIT with bias and discretion]], [[lit-htf-confluences|LIT higher-time-frame confluences]], [[lit-untested-bias|LIT untested bias and regime ideas]], [[lit-untested-targets|LIT untested target and exit ideas]], [[second-account-b|Account B]]
- Runs: `hq_bias_pick1, hq_bias_pick2, hq_bias_pick3, hq_bias_repick_pre2025`
- Source: `research/writeups/hq-bias.md`
- Back to [[ZEUS Home]]
