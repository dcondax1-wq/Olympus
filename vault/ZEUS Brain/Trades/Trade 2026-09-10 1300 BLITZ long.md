---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-09-10"
time: "13:00"
week: "2026-W37"
side: "LONG"
exit: "TIME"
r: -0.549
pnl: -61.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "against_htf"
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-09-10 13:00 ET

> [!failure] -$61 · -0.55R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-10|2026-09-10]] · [[Week 2026-W37|2026-W37]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $112 |
| Minutes in | 31 |
| Best (MFE) | +0.63R |
| Worst (MAE) | -0.65R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.313 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.9 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
