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
date: "2026-07-31"
time: "13:00"
week: "2026-W31"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -179.79
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-07-31 13:00 ET

> [!failure] -$180 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-07-31|2026-07-31]] · [[Week 2026-W31|2026-W31]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $180 |
| Minutes in | 25 |
| Best (MFE) | +0.08R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.9 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.21 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
