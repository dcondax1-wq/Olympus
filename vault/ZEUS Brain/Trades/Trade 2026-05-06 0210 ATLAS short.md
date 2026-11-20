---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-05-06"
time: "02:10"
week: "2026-W19"
side: "SHORT"
exit: "STOP"
r: -1.04
pnl: -511.2
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-05-06 02:10 ET

> [!failure] -$511 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-05-06|2026-05-06]] · [[Week 2026-W19|2026-W19]]

## The trade

|  |  |
|---|---|
| Entry | 28922.5 |
| Stop | 28953.25 |
| Target | 28676.5 |
| Exit price | 28953.5 |
| Micros | 8 |
| Risk $ | $492 |
| Minutes in | 157 |
| Best (MFE) | +1.25R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.449 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -3.71 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
