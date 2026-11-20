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
date: "2026-03-04"
time: "15:00"
week: "2026-W10"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -129.03
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-04 15:00 ET

> [!failure] -$129 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-04|2026-03-04]] · [[Week 2026-W10|2026-W10]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $129 |
| Minutes in | 11 |
| Best (MFE) | +0.20R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.549 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.5 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
