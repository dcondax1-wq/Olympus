---
tags:
  - zeus/research
  - family/filters
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-21"
status: "rejected"
source: "research/writeups/lit-retail-confluence.md"
aliases:
  - "LIT + retail tools as confluence and size"
---

# LIT + retail tools as confluence and size

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT + retail tools as confluence and size - EMAs, MACD, support / resistance, supply / demand

## Summary

The owner asked whether the big retail tools (EMAs, MACD, support / resistance, supply / demand) would make LIT better while keeping about 3 trades a week. This study used them only as a filter or a size change on the 120 trades LIT already takes in 2026 (another study tests them as new entries). 63 retail facts were built, all from bars closed before the entry (look-ahead check 30 of 30 identical). Each was tried 4 ways - skip the trade when the fact is against it, half size when against, x1.25 or x1.5 when with - for 252 tests, scored on the LIT size rule and on the live two_week eval path, picked on Jan-Jun and checked on Jul-Oct 2026. No skip filter keeps 2.9 trades a week (they leave 0.1 to 2.89), and no half-size rule makes more money in both halves. 23 up-size rules pass the letter of the test; all of them are 'bigger size when price is on the trend side of an EMA'. Best: x1.5 when price is on the trade's side of the 1-hour EMA 21, H1 +$42.7k (live +$33.9k), H2 +$11.5k (+$9.5k), eval path 2-week pass H1 63.9% (57.1%), H2 52.2% (unchanged). But they come from more risk, not better picks. Making the same trades bigger at random passes the same test 11-28% of the time and does about as well in Jul-Oct. The 'with' trades beat the 'against' trades in both halves for only 3 of the 63 facts; shuffled facts give 12.3. The eval fails also go up: H1 2-week fails 5.9% to 7.6%, H2 1-month fails 0% to 6.8%. Nothing is adopted, nothing was built, live_model.json is unchanged. Paper only.

## Links

- Family: [[Family filters]]
- Day: [[Day 2026-10-21]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-htf-confluences|LIT higher-time-frame confluences]], [[lit-order-blocks|LIT order blocks]], [[lit-trade-intel|LIT trade intelligence]], [[moving-averages|Moving averages as confluence]]
- Runs: `lit_live, lit_adopt_t15_be_off_eval, lit_retail_c_ema_1h_21_side_x150, lit_retail_c_ema_1h_21_side_x150_eval, lit_retail_c_ema_15m_200_side_x150, lit_retail_c_ema_15m_200_side_x150_eval, lit_retail_c_ema_1h_50_slope_x150, lit_retail_c_ema_1h_50_slope_x150_eval, lit_retail_c_ema_5m_200_slope_x150, li`
- Source: `research/writeups/lit-retail-confluence.md`
- Back to [[ZEUS Home]]
