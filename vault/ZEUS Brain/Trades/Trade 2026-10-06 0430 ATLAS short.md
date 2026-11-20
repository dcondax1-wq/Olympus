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
date: "2026-10-06"
time: "04:30"
week: "2026-W41"
side: "SHORT"
exit: "CUT"
r: -0.37
pnl: -167.4
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-10-06 04:30 ET

> [!failure] -$167 · -0.37R · CUT · backtest
> [[ATLAS]] · [[Day 2026-10-06|2026-10-06]] · [[Week 2026-W41|2026-W41]]

## The trade

|  |  |
|---|---|
| Entry | 31371.0 |
| Stop | 31408.5 |
| Target | 31071.0 |
| Exit price | 31384.0 |
| Micros | 6 |
| Risk $ | $450 |
| Minutes in | 15 |
| Best (MFE) | +0.27R |
| Worst (MAE) | -0.36R |

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
| Day's range before entry (ATR) | 0.209 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.78 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
