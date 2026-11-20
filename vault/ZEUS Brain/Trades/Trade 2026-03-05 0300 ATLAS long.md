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
date: "2026-03-05"
time: "03:00"
week: "2026-W10"
side: "LONG"
exit: "STOP"
r: -1.04
pnl: -457.8
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-03-05 03:00 ET

> [!failure] -$458 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-05|2026-03-05]] · [[Week 2026-W10|2026-W10]]

## The trade

|  |  |
|---|---|
| Entry | 25871.5 |
| Stop | 25840.0 |
| Target | 26123.5 |
| Exit price | 25839.75 |
| Micros | 7 |
| Risk $ | $441 |
| Minutes in | 5 |
| Best (MFE) | +0.02R |
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
| Day's range before entry (ATR) | 0.578 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.9 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
