---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
  - flag/late
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-06-08"
time: "10:45"
week: "2026-W24"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -449.6
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-06-08 10:45 ET

> [!failure] -$450 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-06-08|2026-06-08]] · [[Week 2026-W24|2026-W24]]

## The trade

|  |  |
|---|---|
| Entry | 30133.0 |
| Stop | 30188.0 |
| Target | 30023.0 |
| Exit price | 30188.25 |
| Micros | 4 |
| Risk $ | $440 |
| Minutes in | 5 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.479 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.79 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
