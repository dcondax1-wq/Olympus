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
date: "2026-05-07"
time: "05:35"
week: "2026-W19"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -506.42
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-05-07 05:35 ET

> [!failure] -$506 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-05-07|2026-05-07]] · [[Week 2026-W19|2026-W19]]

## The trade

|  |  |
|---|---|
| Entry | 29335.75 |
| Stop | 29294.75 |
| Target | 29567.14 |
| Exit price | 29294.5 |
| Micros | 6 |
| Risk $ | $492 |
| Minutes in | 35 |
| Best (MFE) | +0.26R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.422 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.74 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
