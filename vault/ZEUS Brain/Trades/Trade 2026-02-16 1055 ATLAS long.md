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
date: "2026-02-16"
time: "10:55"
week: "2026-W08"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -458.4
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-02-16 10:55 ET

> [!failure] -$458 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-02-16|2026-02-16]] · [[Week 2026-W08|2026-W08]]

## The trade

|  |  |
|---|---|
| Entry | 25514.5 |
| Stop | 25477.5 |
| Target | 25810.5 |
| Exit price | 25477.25 |
| Micros | 6 |
| Risk $ | $444 |
| Minutes in | 44 |
| Best (MFE) | +1.03R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.419 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.98 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
