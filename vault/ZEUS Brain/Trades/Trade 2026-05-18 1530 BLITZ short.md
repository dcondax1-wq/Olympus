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
date: "2026-05-18"
time: "15:30"
week: "2026-W21"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -183.06
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-05-18 15:30 ET

> [!failure] -$183 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-18|2026-05-18]] · [[Week 2026-W21|2026-W21]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $183 |
| Minutes in | 10 |
| Best (MFE) | +0.10R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.24 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.05 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
