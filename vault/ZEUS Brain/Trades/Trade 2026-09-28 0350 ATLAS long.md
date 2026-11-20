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
date: "2026-09-28"
time: "03:50"
week: "2026-W40"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -411.6
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
session: "London 02-05"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-09-28 03:50 ET

> [!failure] -$412 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-09-28|2026-09-28]] · [[Week 2026-W40|2026-W40]]

## The trade

|  |  |
|---|---|
| Entry | 30614.25 |
| Stop | 30564.0 |
| Target | 31016.25 |
| Exit price | 30563.75 |
| Micros | 4 |
| Risk $ | $402 |
| Minutes in | 75 |
| Best (MFE) | +0.51R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | with |
| Day's range before entry (ATR) | 0.78 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.83 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
