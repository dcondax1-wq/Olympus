---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-01-07"
time: "03:15"
week: "2026-W02"
side: "LONG"
exit: "STOP"
r: -1.07
pnl: -516.0
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
session: "London 02-05"
vix_band: "VIX <15"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-01-07 03:15 ET

> [!failure] -$516 · -1.07R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-07|2026-01-07]] · [[Week 2026-W02|2026-W02]]

## The trade

|  |  |
|---|---|
| Entry | 26574.5 |
| Stop | 26558.5 |
| Target | 26702.5 |
| Exit price | 26558.25 |
| Micros | 15 |
| Risk $ | $480 |
| Minutes in | 44 |
| Best (MFE) | +0.80R |
| Worst (MAE) | -1.02R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.275 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.34 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
