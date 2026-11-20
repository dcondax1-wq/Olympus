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
time: "12:00"
week: "2026-W15"
side: "SHORT"
exit: "TIME"
r: -0.289
pnl: -29.9
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-04-08 12:00 ET

> [!failure] -$30 · -0.29R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-08|2026-04-08]] · [[Week 2026-W15|2026-W15]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $103 |
| Minutes in | 31 |
| Best (MFE) | +0.33R |
| Worst (MAE) | -0.74R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.596 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.1 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
