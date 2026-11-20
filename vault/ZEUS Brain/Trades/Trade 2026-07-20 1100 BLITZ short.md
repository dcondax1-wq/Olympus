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
date: "2026-07-20"
time: "11:00"
week: "2026-W30"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -176.14
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-07-20 11:00 ET

> [!failure] -$176 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-07-20|2026-07-20]] · [[Week 2026-W30|2026-W30]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $176 |
| Minutes in | 9 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.754 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.41 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
