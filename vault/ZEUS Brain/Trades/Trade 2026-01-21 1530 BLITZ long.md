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
date: "2026-01-21"
time: "15:30"
week: "2026-W04"
side: "LONG"
exit: "EOD"
r: -0.203
pnl: -33.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-01-21 15:30 ET

> [!failure] -$33 · -0.20R · EOD · backtest
> [[BLITZ (paper)]] · [[Day 2026-01-21|2026-01-21]] · [[Week 2026-W04|2026-W04]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $165 |
| Minutes in | 25 |
| Best (MFE) | +0.36R |
| Worst (MAE) | -0.50R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.765 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
