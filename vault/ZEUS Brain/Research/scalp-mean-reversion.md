---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/blitz
type: "research"
date: "2026-10-28"
status: "rejected - nothing adopted; no mean-reversion scalp holds in 2026 H1, H2 and 2021-25 after costs"
source: "research/writeups/scalp-mean-reversion.md"
aliases:
  - "Mean-reversion scalps for a third account"
---

# Mean-reversion scalps for a third account

> [!failure] Verdict: rejected
> rejected - nothing adopted; no mean-reversion scalp holds in 2026 H1, H2 and 2021-25 after costs

**Full title:** Mean-reversion scalps for a third account - none makes money in both 2026 and 2021-25 after costs

## Summary

Owner 2026-10-28 - a third strategy, a scalper that trades several times a day on its own MFFU account and makes money. Mean-reversion fades (VWAP / band / range-edge fades, limit and market entries) were tested on CME NQ1! (1m for 2026, 5m for 2021-25), costs in. The best makes about +$270 to +$360 a month in each 2026 half at $100 risk a trade, but the same idea on 5m bars loses about $320 a month over 2021-25 and its eval pass rate is no better than a coin flip. Nothing built.

## Money first

Money is shown at a fixed **$100 risk a trade** on a Builder 25K (size = $100 / (stop $ + costs), max 20 micros, $600
soft daily loss). Eval columns use the fastest size that does not simply blow up: **$300 risk on the 25K, $600 on the
50K**, capped at half the room to the floor, with a fresh eval started on every session. 2026 is tested on 1m bars and
2021-25 on 5m bars.

| Candidate | Span | Trades/wk | Win % | PF | Net $ | $/month | Max DD $ | Costs $ (gross $) | 25K pass/fail in 2 wks | 50K pass/fail in 2 wks |
|---|---|---|---|---|---|---|---|---|---|---|
| **1. RTH-VWAP 2.5-sd fade** (`vwap25`) | H1 2026 | 16.8 | 45.8 | 1.14 | +2,212 | +363 | -1,500 | 2,674 (4,886) | 35.2 / 31.2 | 36.7 / 33.6 |
| | H2 2026 | 14.8 | 45.5 | 1.13 | +1,018 | +274 | -1,390 | 1,456 (2,474) | 32.1 / 20.5 | 34.6 / 28.2 |
| | 2021-25 (5m) | 10.4 | 39.7 | 0.84 | -16,204 | -316 | -16,464 | 12,398 (-3,934) | 9.1 / 29.2 | 8.4 / 33.1 |
| **2. Same, range days only** (`vwap25_flat`) | H1 2026 | 7.6 | 47.4 | 1.22 | +1,389 | +228 | -742 | 1,163 (2,552) | 28.1 / 11.7 | 28.9 / 7.0 |
| | H2 2026 | 6.9 | 47.2 | 1.20 | +707 | +190 | -1,060 | 710 (1,417) | 12.8 / 6.4 | 15.4 / 0.0 |
| | 2021-25 (5m) | 3.5 | 38.9 | 0.80 | -6,492 | -127 | -7,526 | 4,144 (-2,348) | 1.7 / 11.8 | 1.4 / 11.6 |
| **3. Level sweep-and-reclaim, target VWAP** (`levels_am`) | H1 2026 | 11.4 | 19.2 | 1.56 | +10,081 | +1,654 | -2,461 | 2,706 (12,787) | 32.0 / 53.1 | 25.8 / 60.9 |
| | H2 2026 | 11.0 | 14.0 | 0.62 | -4,815 | -1,296 | -5,195 | 1,525 (-3,290) | 10.3 / 56.4 | 10.3 / 61.5 |
| | 2021-25 (5m) | 8.3 | 28.3 | 0.82 | -18,270 | -356 | -22,687 | 14,955 (-3,314) | 13.8 / 70.8 | 14.3 / 72.8 |

Other eval figures (in `research/scalp/mr_final.json`): for candidate 1 on the 25K the median pass takes 5-6 sessions
when it passes. About 54-68% of evals are decided within 2 weeks. For comparison, LIT's 50K 2-week pass/fail is about 58 / 21.

**What the costs do.** The costs column is commission ($1.90 a micro round trip) plus 1 tick of slippage on each market or
stop fill. For candidate 1 in 2026 they take about **55-60% of the profit before costs**. In 2021-25 the trades lose
money even before costs.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-28]]
- Strategies: [[BLITZ (paper)]]
- Runs: `-`
- Source: `research/writeups/scalp-mean-reversion.md`
- Back to [[ZEUS Home]]
