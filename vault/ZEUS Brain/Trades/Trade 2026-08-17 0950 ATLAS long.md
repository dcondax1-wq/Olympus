---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-08-17"
time: "09:50"
week: "2026-W34"
side: "LONG"
exit: "CUT"
r: -0.34
pnl: -165.6
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
flags:
  - "no_room"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-08-17 09:50 ET

> [!failure] -$166 · -0.34R · CUT · backtest
> [[ATLAS]] · [[Day 2026-08-17|2026-08-17]] · [[Week 2026-W34|2026-W34]]

## The trade

|  |  |
|---|---|
| Entry | 30521.75 |
| Stop | 30460.0 |
| Target | 30738.22 |
| Exit price | 30502.0 |
| Micros | 4 |
| Risk $ | $494 |
| Minutes in | 15 |
| Best (MFE) | +0.44R |
| Worst (MAE) | -0.66R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.299 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.0 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
