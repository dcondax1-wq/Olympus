---
tags:
  - zeus/research
  - family/winrate
  - verdict/rejected
type: "research"
date: "2026-10-23"
status: "rejected"
source: "research/writeups/hq-reversion.md"
aliases:
  - "High-probability mean reversion at exhaustion"
---

# High-probability mean reversion at exhaustion

> [!failure] Verdict: rejected
> rejected

**Full title:** High-probability mean reversion at exhaustion - fade a stretched move back to VWAP / the middle / 1R

## Summary

Owner (2026-10-23) - "a strategy that trades 2+ times a week, high-quality setups, with high probability and high profit." Four mean-reversion families that should have high win rates by construction (a close target after a stretched move) were tested with the EXHAUSTION condition as the new angle - (1) the day's range already >= 0.8-1.5x the 14-day mean range + a sweep of the day's high/low + a 5m rejection, back to VWAP / the day's middle; (2) the overnight / London / Asia range swept on BOTH sides, then a rejection, to the range middle; (3) a move >= 1.5-4 ATR from VWAP into an untaken PDH/PDL, PWH/PWL or PMH/PML, then a rejection; (4) failed opening-range breakouts 10:00-11:30. 26,112 variants on CME NQ1! (costs $1.90 a micro + 1 tick, structural stops, $500 risk, no look-ahead, 40/40 re-derived on cut data). Answer - no. Fading a stretched day loses money in 3 of 4 periods (-0.14 to -0.26 R a trade); the exhaustion filter makes the other families worse, not better; the stop at the exhaustion extreme is wide (median 20-33 pts), so VWAP or the middle is 2-4R away and is reached only 11-32% of the time. A 1R target lifts the true win rate to 45-60%, which is about break-even after costs. Only 64 variants pass the H1 gate (20+ trades, 55%+ true winners, avg winner >= 1R, PF >= 1.3); 4 of them are positive in H2 and none in all of H2, 2025 and 2021-24. Best lead - the failed 30-minute ORB fade at 1R (picked on H1 AND by the pre-2025 re-pick) - 60% true winners in H1 and H2 and 56% in 2021-24 (+$3.0k / +$1.8k / +$10.2k), but it loses in 2025 (46%, -$4.1k), trades 1.3 a week, its H2 is negative without its 5 best trades, and on a 25K alone it passes 0% of evals in 2 weeks. Nothing to switch on; paper-watch only.

## Links

- Family: [[Family winrate]]
- Day: [[Day 2026-10-23]]
- Refers to: [[allday|NQ around the clock]], [[retail-standalone|Retail strategies on their own]], [[stophunt|STOP-HUNT family]]
- Runs: `hq_rev_h1_of, hq_rev_h1_of_runner, hq_rev_peeked_bx, hq_rev_h1_vx, hq_rev_h1_bx, hq_rev_long_bx, hq_rev_book_h1, hq_rev_book_long`
- Source: `research/writeups/hq-reversion.md`
- Back to [[ZEUS Home]]
