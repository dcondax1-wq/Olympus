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
date: "2026-01-30"
time: "07:55"
week: "2026-W05"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -470.41
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-30 07:55 ET

> [!failure] -$470 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-30|2026-01-30]] · [[Week 2026-W05|2026-W05]]

## The trade

|  |  |
|---|---|
| Entry | 26632.25 |
| Stop | 26670.25 |
| Target | 26512.8 |
| Exit price | 26670.5 |
| Micros | 6 |
| Risk $ | $456 |
| Minutes in | 15 |
| Best (MFE) | +0.04R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.898 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.15 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
