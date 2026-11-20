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
date: "2026-03-09"
time: "11:30"
week: "2026-W11"
side: "LONG"
exit: "TIME"
r: -0.128
pnl: -21.4
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

# BLITZ long · 2026-03-09 11:30 ET

> [!failure] -$21 · -0.13R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-09|2026-03-09]] · [[Week 2026-W11|2026-W11]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $167 |
| Minutes in | 31 |
| Best (MFE) | +0.19R |
| Worst (MAE) | -0.65R |

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
| Day's range before entry (ATR) | 1.325 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.74 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
