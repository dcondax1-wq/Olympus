---
tags:
  - zeus/research
  - family/filters
  - verdict/rejected
type: "research"
date: "2026-10-17"
status: "rejected"
source: "research/writeups/unexpected-factors.md"
aliases:
  - "Unexpected factors"
---

# Unexpected factors

> [!failure] Verdict: rejected
> rejected

**Full title:** Unexpected factors: 33 things the owner would not think of, none of them real

## Summary

33 unusual conditions knowable at entry (VIX / VXN / GEX / dark-pool buying, overnight and gap size, inside days, days since a 2% day, trades already this week, pre-market sweeps, sweep-to-trigger time, zone and candle sizes, relative volume, pool count, month-to-date P&L and more) were ranked on 2021-25. The best one, "the sweep extreme was made before 09:30" (125 trades, +0.159R vs -0.022R), has a t of 1.3 and a shuffle test says a random relabelling beats it 16% of the time alone and 95% of the time once you allow for 33 tries. The 1.25x size rules that "beat the baseline in both periods" do so only because they add leverage: flat 1.25x on every trade makes more (2021-25 +$18,350 vs +$17,472-17,919). Nothing to adopt.

## Money first

Nothing here should change the locked strategy. The owner was right to ask, and the answer is useful in its own way:
the strategy's edge is in what the trade is made of (the sweep, the trigger, the stop, the target), not in the weather
around it. Any future "unusual factor" claim should be held to the same bar: t above 2 on 2021-25, the same sign in 2026,
and a win against both random groups and flat leverage.

Method and data: `tools/research_wild.py` (features, ranking, size rules, shuffle and random-group controls),
`research/lab/unexpected_factors.json` (every factor and run), runs `wild_*` in `research/runs/`.

## Links

- Family: [[Family filters]]
- Day: [[Day 2026-10-17]]
- Runs: `wild_sweep_premarket_half, wild_sweep_premarket_x125, wild_mtd_r_half, wild_mtd_r_x125, wild_days_since_trade_half, wild_days_since_trade_x125, wild_on_share_half, wild_on_share_x125, wild_kz_minutes_half, wild_kz_minutes_x125, wild_gap_abs_adr_half, wild_gap_abs_adr_x125, wild_vix_vs_20d_half, wild`
- Source: `research/writeups/unexpected-factors.md`
- Back to [[ZEUS Home]]
