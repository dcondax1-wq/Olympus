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
date: "2026-04-28"
time: "11:00"
week: "2026-W18"
side: "LONG"
exit: "STOP"
r: -1.01
pnl: -482.7
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-28 11:00 ET

> [!failure] -$483 · -1.01R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-28|2026-04-28]] · [[Week 2026-W18|2026-W18]]

## The trade

|  |  |
|---|---|
| Entry | 27675.5 |
| Stop | 27596.25 |
| Target | 27834.0 |
| Exit price | 27596.0 |
| Micros | 3 |
| Risk $ | $476 |
| Minutes in | 40 |
| Best (MFE) | +0.36R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | with |
| Day's range before entry (ATR) | 1.157 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.36 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
