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
date: "2026-06-30"
time: "04:30"
week: "2026-W27"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -469.61
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-06-30 04:30 ET

> [!failure] -$470 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-06-30|2026-06-30]] · [[Week 2026-W27|2026-W27]]

## The trade

|  |  |
|---|---|
| Entry | 30419.0 |
| Stop | 30361.5 |
| Target | 30638.91 |
| Exit price | 30361.25 |
| Micros | 4 |
| Risk $ | $460 |
| Minutes in | 10 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.354 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.06 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
