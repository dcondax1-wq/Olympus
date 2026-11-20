---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-04-08"
time: "15:00"
week: "2026-W15"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -89.88
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-04-08 15:00 ET

> [!failure] -$90 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-08|2026-04-08]] · [[Week 2026-W15|2026-W15]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $90 |
| Minutes in | 12 |
| Best (MFE) | +0.22R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.596 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.97 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
