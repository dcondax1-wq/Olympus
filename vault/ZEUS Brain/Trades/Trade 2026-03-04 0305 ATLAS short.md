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
date: "2026-03-04"
time: "03:05"
week: "2026-W10"
side: "SHORT"
exit: "STOP"
r: -1.04
pnl: -491.21
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-03-04 03:05 ET

> [!failure] -$491 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-04|2026-03-04]] · [[Week 2026-W10|2026-W10]]

## The trade

|  |  |
|---|---|
| Entry | 25447.75 |
| Stop | 25477.25 |
| Target | 25211.75 |
| Exit price | 25477.5 |
| Micros | 8 |
| Risk $ | $472 |
| Minutes in | 15 |
| Best (MFE) | +0.43R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.656 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.74 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
