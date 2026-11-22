---
tags:
  - zeus/research
  - family/management
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/management.md"
aliases:
  - "Managing the trade"
---

# Managing the trade

> [!info] Verdict: finding
> finding

**Full title:** Managing the trade: breakeven, locks, time stop, giveback

## Summary

Today's management is at its sweet spot on all-days rules, with one exception: on trending days (10-day efficiency above 0.45) waiting until +3R to move to breakeven adds +$4.7k to 2021-25 (PF 1.09 → 1.15) and leaves 2026 net unchanged (+$20.1k). On today's sizing it adds some late-May 2026 eval fails (beyond 1 month); with the sizing research's quarter size in cold streaks it is clean (+$4.8k in 2021-25). Profit locks, other time stops and giveback levels all lose.

## Money first

- Keep breakeven at +1R, the 30-minute time stop and the giveback exit for normal days.
- **Candidate:** on trending days, move to breakeven only at +3R (`be_at_r_trending: 3`). It is the only
  management change that adds money in 2021-25 without taking any from 2026. Adopt it together with the sizing
  change (quarter size in cold streaks); on today's sizing alone it adds late-May 2026 eval fails, so then keep
  breakeven at +1R everywhere. Easy to port: the Pine script already computes the 10-day efficiency for the
  half-size rule.

## Links

- Family: [[Family management]]
- Day: [[Day 2026-10-17]]
- Runs: `baseline, combo_betrend3_risksizing, mgt_be000, mgt_be075, mgt_be125, mgt_be150, mgt_be200, mgt_betrend075, mgt_betrend150, mgt_betrend200, mgt_betrend250, mgt_betrend300, mgt_betrend_off, mgt_betrend300_replay, mgt_lock15_5, mgt_lock20_5, mgt_lock20_10, mgt_lock30_10, mgt_lock30_15, mgt_ts0, mgt_ts`
- Source: `research/writeups/management.md`
- Back to [[ZEUS Home]]
