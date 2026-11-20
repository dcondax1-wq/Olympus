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
date: "2026-04-15"
time: "09:45"
week: "2026-W16"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -428.7
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-04-15 09:45 ET

> [!failure] -$429 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-15|2026-04-15]] · [[Week 2026-W16|2026-W16]]

## The trade

|  |  |
|---|---|
| Entry | 26573.75 |
| Stop | 26644.0 |
| Target | 26433.25 |
| Exit price | 26644.25 |
| Micros | 3 |
| Risk $ | $422 |
| Minutes in | 10 |
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
| Day's range before entry (ATR) | 0.228 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.46 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
