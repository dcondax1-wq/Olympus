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
date: "2026-09-02"
time: "11:30"
week: "2026-W36"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -106.95
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-09-02 11:30 ET

> [!failure] -$107 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-02|2026-09-02]] · [[Week 2026-W36|2026-W36]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $107 |
| Minutes in | 19 |
| Best (MFE) | +0.06R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.71 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.22 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
