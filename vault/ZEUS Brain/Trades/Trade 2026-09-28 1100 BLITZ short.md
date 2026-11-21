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
date: "2026-09-28"
time: "11:00"
week: "2026-W40"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -150.11
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-09-28 11:00 ET

> [!failure] -$150 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-28|2026-09-28]] · [[Week 2026-W40|2026-W40]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $150 |
| Minutes in | 9 |
| Best (MFE) | +0.07R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.234 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.52 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
