---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-05-07"
time: "13:30"
week: "2026-W19"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -155.93
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-05-07 13:30 ET

> [!failure] -$156 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-07|2026-05-07]] · [[Week 2026-W19|2026-W19]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $156 |
| Minutes in | 11 |
| Best (MFE) | +0.23R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.933 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.33 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
