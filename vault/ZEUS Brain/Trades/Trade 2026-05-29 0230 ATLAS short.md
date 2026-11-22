---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-05-29"
time: "02:30"
week: "2026-W22"
side: "SHORT"
exit: "CUT"
r: -0.49
pnl: -233.1
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-05-29 02:30 ET

> [!failure] -$233 · -0.49R · CUT · backtest
> [[ATLAS]] · [[Day 2026-05-29|2026-05-29]] · [[Week 2026-W22|2026-W22]]

## The trade

|  |  |
|---|---|
| Entry | 30900.0 |
| Stop | 30926.5 |
| Target | 30688.0 |
| Exit price | 30912.0 |
| Micros | 9 |
| Risk $ | $477 |
| Minutes in | 15 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -0.74R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.296 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.86 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
