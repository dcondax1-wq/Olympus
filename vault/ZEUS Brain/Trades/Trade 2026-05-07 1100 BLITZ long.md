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
date: "2026-05-07"
time: "11:00"
week: "2026-W19"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -100.06
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-07 11:00 ET

> [!failure] -$100 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-07|2026-05-07]] · [[Week 2026-W19|2026-W19]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $100 |
| Minutes in | 6 |
| Best (MFE) | +0.04R |
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
| Day's range before entry (ATR) | 0.731 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -2.63 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
