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
date: "2026-02-12"
time: "13:00"
week: "2026-W07"
side: "SHORT"
exit: "TIME"
r: -0.073
pnl: -11.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-02-12 13:00 ET

> [!failure] -$11 · -0.07R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-12|2026-02-12]] · [[Week 2026-W07|2026-W07]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $157 |
| Minutes in | 31 |
| Best (MFE) | +0.32R |
| Worst (MAE) | -0.73R |

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
| Day's range before entry (ATR) | 1.087 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.71 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
