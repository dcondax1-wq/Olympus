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
date: "2026-03-17"
time: "07:55"
week: "2026-W12"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -467.01
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-03-17 07:55 ET

> [!failure] -$467 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-17|2026-03-17]] · [[Week 2026-W12|2026-W12]]

## The trade

|  |  |
|---|---|
| Entry | 25399.0 |
| Stop | 25444.5 |
| Target | 25077.03 |
| Exit price | 25444.75 |
| Micros | 5 |
| Risk $ | $455 |
| Minutes in | 15 |
| Best (MFE) | +0.06R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.282 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -2.31 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
