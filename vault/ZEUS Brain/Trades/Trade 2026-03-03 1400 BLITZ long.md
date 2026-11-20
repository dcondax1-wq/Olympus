---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-03-03"
time: "14:00"
week: "2026-W10"
side: "LONG"
exit: "TIME"
r: -0.521
pnl: -74.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-03 14:00 ET

> [!failure] -$74 · -0.52R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-03|2026-03-03]] · [[Week 2026-W10|2026-W10]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $143 |
| Minutes in | 31 |
| Best (MFE) | +0.20R |
| Worst (MAE) | -0.99R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.477 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.27 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
