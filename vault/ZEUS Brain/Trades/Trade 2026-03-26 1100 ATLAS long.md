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
date: "2026-03-26"
time: "11:00"
week: "2026-W13"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -452.7
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-03-26 11:00 ET

> [!failure] -$453 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-26|2026-03-26]] · [[Week 2026-W13|2026-W13]]

## The trade

|  |  |
|---|---|
| Entry | 24688.25 |
| Stop | 24614.0 |
| Target | 24836.75 |
| Exit price | 24613.75 |
| Micros | 3 |
| Risk $ | $446 |
| Minutes in | 80 |
| Best (MFE) | +0.34R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.728 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.72 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
