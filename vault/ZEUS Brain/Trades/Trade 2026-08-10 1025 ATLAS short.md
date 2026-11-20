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
date: "2026-08-10"
time: "10:25"
week: "2026-W33"
side: "SHORT"
exit: "T15"
r: -0.36
pnl: -179.6
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-08-10 10:25 ET

> [!failure] -$180 · -0.36R · T15 · backtest
> [[ATLAS]] · [[Day 2026-08-10|2026-08-10]] · [[Week 2026-W33|2026-W33]]

## The trade

|  |  |
|---|---|
| Entry | 30133.25 |
| Stop | 30195.0 |
| Target | 30009.75 |
| Exit price | 30154.75 |
| Micros | 4 |
| Risk $ | $494 |
| Minutes in | 15 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -0.87R |

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
| Day's range before entry (ATR) | 0.374 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.59 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
