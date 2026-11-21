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
date: "2026-03-20"
time: "11:30"
week: "2026-W12"
side: "SHORT"
exit: "TIME"
r: -0.704
pnl: -109.9
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-03-20 11:30 ET

> [!failure] -$110 · -0.70R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-20|2026-03-20]] · [[Week 2026-W12|2026-W12]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $156 |
| Minutes in | 31 |
| Best (MFE) | +0.14R |
| Worst (MAE) | -0.73R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.786 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.46 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
