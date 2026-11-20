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
date: "2026-03-05"
time: "04:00"
week: "2026-W10"
side: "LONG"
exit: "STOP"
r: -1.01
pnl: -485.7
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
session: "London 02-05"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-03-05 04:00 ET

> [!failure] -$486 · -1.01R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-05|2026-03-05]] · [[Week 2026-W10|2026-W10]]

## The trade

|  |  |
|---|---|
| Entry | 25852.0 |
| Stop | 25772.25 |
| Target | 26301.56 |
| Exit price | 25772.0 |
| Micros | 3 |
| Risk $ | $478 |
| Minutes in | 318 |
| Best (MFE) | +1.92R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.594 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.97 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
