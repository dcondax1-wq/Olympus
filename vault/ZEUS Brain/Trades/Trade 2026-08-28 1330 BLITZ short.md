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
date: "2026-08-28"
time: "13:30"
week: "2026-W35"
side: "SHORT"
exit: "TIME"
r: -0.59
pnl: -79.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
session: "NY PM 13:30-16"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-08-28 13:30 ET

> [!failure] -$79 · -0.59R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-08-28|2026-08-28]] · [[Week 2026-W35|2026-W35]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $135 |
| Minutes in | 31 |
| Best (MFE) | +0.13R |
| Worst (MAE) | -0.90R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.97 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.96 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
