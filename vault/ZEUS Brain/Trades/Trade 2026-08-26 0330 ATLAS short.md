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
date: "2026-08-26"
time: "03:30"
week: "2026-W35"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -466.21
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-08-26 03:30 ET

> [!failure] -$466 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-26|2026-08-26]] · [[Week 2026-W35|2026-W35]]

## The trade

|  |  |
|---|---|
| Entry | 29495.75 |
| Stop | 29572.25 |
| Target | 29294.83 |
| Exit price | 29572.5 |
| Micros | 3 |
| Risk $ | $459 |
| Minutes in | 230 |
| Best (MFE) | +0.21R |
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
| Day's range before entry (ATR) | 0.532 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.97 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
