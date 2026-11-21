---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-05-28"
time: "13:00"
week: "2026-W22"
side: "LONG"
exit: "TIME"
r: -0.516
pnl: -44.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-28 13:00 ET

> [!failure] -$44 · -0.52R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-28|2026-05-28]] · [[Week 2026-W22|2026-W22]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $86 |
| Minutes in | 31 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -0.76R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.112 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.01 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
