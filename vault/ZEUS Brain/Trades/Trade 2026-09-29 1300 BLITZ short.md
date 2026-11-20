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
date: "2026-09-29"
time: "13:00"
week: "2026-W40"
side: "SHORT"
exit: "TIME"
r: -0.333
pnl: -38.9
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-09-29 13:00 ET

> [!failure] -$39 · -0.33R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-29|2026-09-29]] · [[Week 2026-W40|2026-W40]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $117 |
| Minutes in | 31 |
| Best (MFE) | +0.42R |
| Worst (MAE) | -0.77R |

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
| Day's range before entry (ATR) | 0.746 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.72 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
