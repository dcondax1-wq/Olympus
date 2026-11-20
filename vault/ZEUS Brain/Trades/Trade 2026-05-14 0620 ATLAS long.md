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
date: "2026-05-14"
time: "06:20"
week: "2026-W20"
side: "LONG"
exit: "STOP"
r: -1.05
pnl: -509.01
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-05-14 06:20 ET

> [!failure] -$509 · -1.05R · STOP · backtest
> [[ATLAS]] · [[Day 2026-05-14|2026-05-14]] · [[Week 2026-W20|2026-W20]]

## The trade

|  |  |
|---|---|
| Entry | 30157.0 |
| Stop | 30132.75 |
| Target | 30351.0 |
| Exit price | 30132.5 |
| Micros | 10 |
| Risk $ | $485 |
| Minutes in | 5 |
| Best (MFE) | +0.00R |
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
| Day's range before entry (ATR) | 0.45 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.77 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
