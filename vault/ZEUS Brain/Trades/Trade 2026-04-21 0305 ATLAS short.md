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
date: "2026-04-21"
time: "03:05"
week: "2026-W17"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -446.4
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

# ATLAS short · 2026-04-21 03:05 ET

> [!failure] -$446 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-21|2026-04-21]] · [[Week 2026-W17|2026-W17]]

## The trade

|  |  |
|---|---|
| Entry | 27405.5 |
| Stop | 27441.5 |
| Target | 27117.5 |
| Exit price | 27441.75 |
| Micros | 6 |
| Risk $ | $432 |
| Minutes in | 185 |
| Best (MFE) | +0.67R |
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
| Day's range before entry (ATR) | 0.226 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.12 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
