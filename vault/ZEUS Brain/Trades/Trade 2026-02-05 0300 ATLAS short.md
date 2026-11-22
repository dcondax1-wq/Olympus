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
date: "2026-02-05"
time: "03:00"
week: "2026-W06"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -477.0
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-02-05 03:00 ET

> [!failure] -$477 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-02-05|2026-02-05]] · [[Week 2026-W06|2026-W06]]

## The trade

|  |  |
|---|---|
| Entry | 25842.75 |
| Stop | 25889.25 |
| Target | 25557.34 |
| Exit price | 25889.5 |
| Micros | 5 |
| Risk $ | $465 |
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
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.506 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.95 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
