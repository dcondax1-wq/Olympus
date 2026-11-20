---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-15"
time: "12:30"
week: "2026-W25"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -98.24
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-15 12:30 ET

> [!failure] -$98 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-15|2026-06-15]] · [[Week 2026-W25|2026-W25]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $98 |
| Minutes in | 18 |
| Best (MFE) | +0.29R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.987 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.37 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
