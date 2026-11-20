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
date: "2026-06-09"
time: "13:00"
week: "2026-W24"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -406.56
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-06-09 13:00 ET

> [!failure] -$407 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-09|2026-06-09]] · [[Week 2026-W24|2026-W24]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $407 |
| Minutes in | 18 |
| Best (MFE) | +0.09R |
| Worst (MAE) | -1.00R |

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
| Day's range before entry (ATR) | 2.91 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.85 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
