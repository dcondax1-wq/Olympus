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
date: "2026-08-27"
time: "10:35"
week: "2026-W35"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -512.0
result: "loss"
account: "atlas"
member: "S/R"
cause: "turned"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-08-27 10:35 ET

> [!failure] -$512 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-27|2026-08-27]] · [[Week 2026-W35|2026-W35]]

## The trade

|  |  |
|---|---|
| Entry | 29868.5 |
| Stop | 29918.5 |
| Target | 29768.5 |
| Exit price | 29918.75 |
| Micros | 5 |
| Risk $ | $500 |
| Minutes in | 35 |
| Best (MFE) | +0.83R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.66 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.6 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
