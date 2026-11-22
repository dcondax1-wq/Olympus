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
date: "2026-05-05"
time: "14:30"
week: "2026-W19"
side: "LONG"
exit: "TIME"
r: -0.271
pnl: -27.8
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-05 14:30 ET

> [!failure] -$28 · -0.27R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-05|2026-05-05]] · [[Week 2026-W19|2026-W19]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $102 |
| Minutes in | 31 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -0.94R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.154 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -2.14 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
