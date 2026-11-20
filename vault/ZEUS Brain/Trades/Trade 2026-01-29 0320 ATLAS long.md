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
date: "2026-01-29"
time: "03:20"
week: "2026-W05"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -421.6
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-01-29 03:20 ET

> [!failure] -$422 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-29|2026-01-29]] · [[Week 2026-W05|2026-W05]]

## The trade

|  |  |
|---|---|
| Entry | 27077.0 |
| Stop | 27025.5 |
| Target | 27360.68 |
| Exit price | 27025.25 |
| Micros | 4 |
| Risk $ | $412 |
| Minutes in | 95 |
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
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.548 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.33 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
