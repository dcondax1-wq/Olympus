---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-27"
time: "09:40"
week: "2026-W18"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -488.4
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-27 09:40 ET

> [!failure] -$488 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-27|2026-04-27]] · [[Week 2026-W18|2026-W18]]

## The trade

|  |  |
|---|---|
| Entry | 27976.75 |
| Stop | 27937.25 |
| Target | 28055.75 |
| Exit price | 27937.0 |
| Micros | 6 |
| Risk $ | $474 |
| Minutes in | 10 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.44 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.51 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
