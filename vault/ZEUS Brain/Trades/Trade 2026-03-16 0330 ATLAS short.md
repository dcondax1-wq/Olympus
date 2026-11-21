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
date: "2026-03-16"
time: "03:30"
week: "2026-W12"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -421.6
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
session: "London 02-05"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-03-16 03:30 ET

> [!failure] -$422 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-16|2026-03-16]] · [[Week 2026-W12|2026-W12]]

## The trade

|  |  |
|---|---|
| Entry | 25331.25 |
| Stop | 25382.75 |
| Target | 24919.25 |
| Exit price | 25383.0 |
| Micros | 4 |
| Risk $ | $412 |
| Minutes in | 162 |
| Best (MFE) | +1.05R |
| Worst (MAE) | -0.74R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 25+ |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.571 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.29 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
