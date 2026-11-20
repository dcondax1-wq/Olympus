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
date: "2026-09-09"
time: "11:20"
week: "2026-W37"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -473.6
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-09-09 11:20 ET

> [!failure] -$474 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-09-09|2026-09-09]] · [[Week 2026-W37|2026-W37]]

## The trade

|  |  |
|---|---|
| Entry | 29738.75 |
| Stop | 29680.75 |
| Target | 29854.75 |
| Exit price | 29680.5 |
| Micros | 4 |
| Risk $ | $464 |
| Minutes in | 5 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.818 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.48 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
