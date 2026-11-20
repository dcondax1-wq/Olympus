---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-09-09"
time: "02:30"
week: "2026-W37"
side: "SHORT"
exit: "CUT"
r: -0.51
pnl: -251.4
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-09-09 02:30 ET

> [!failure] -$251 · -0.51R · CUT · backtest
> [[ATLAS]] · [[Day 2026-09-09|2026-09-09]] · [[Week 2026-W37|2026-W37]]

## The trade

|  |  |
|---|---|
| Entry | 29887.25 |
| Stop | 29928.75 |
| Target | 29555.25 |
| Exit price | 29907.25 |
| Micros | 6 |
| Risk $ | $498 |
| Minutes in | 15 |
| Best (MFE) | +0.11R |
| Worst (MAE) | -0.52R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | with |
| Day's range before entry (ATR) | 0.392 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.44 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
