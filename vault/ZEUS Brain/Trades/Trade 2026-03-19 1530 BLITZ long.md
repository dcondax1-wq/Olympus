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
date: "2026-03-19"
time: "15:30"
week: "2026-W12"
side: "LONG"
exit: "EOD"
r: -0.39
pnl: -57.9
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
session: "NY PM 13:30-16"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-19 15:30 ET

> [!failure] -$58 · -0.39R · EOD · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-19|2026-03-19]] · [[Week 2026-W12|2026-W12]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $148 |
| Minutes in | 25 |
| Best (MFE) | +0.23R |
| Worst (MAE) | -0.73R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.738 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
