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
date: "2026-06-29"
time: "14:00"
week: "2026-W27"
side: "LONG"
exit: "TIME"
r: -0.14
pnl: -17.4
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-29 14:00 ET

> [!failure] -$17 · -0.14R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-29|2026-06-29]] · [[Week 2026-W27|2026-W27]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $125 |
| Minutes in | 31 |
| Best (MFE) | +0.34R |
| Worst (MAE) | -0.29R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.892 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.36 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
