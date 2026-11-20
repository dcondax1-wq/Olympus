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
date: "2026-01-07"
time: "10:40"
week: "2026-W02"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -413.6
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-07 10:40 ET

> [!failure] -$414 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-07|2026-01-07]] · [[Week 2026-W02|2026-W02]]

## The trade

|  |  |
|---|---|
| Entry | 26651.25 |
| Stop | 26701.75 |
| Target | 26550.25 |
| Exit price | 26702.0 |
| Micros | 4 |
| Risk $ | $404 |
| Minutes in | 10 |
| Best (MFE) | +0.29R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.565 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.96 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
