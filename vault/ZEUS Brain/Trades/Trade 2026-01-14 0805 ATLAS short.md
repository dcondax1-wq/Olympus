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
date: "2026-01-14"
time: "08:05"
week: "2026-W03"
side: "SHORT"
exit: "STOP"
r: -1.06
pnl: -514.82
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "NY pre 08-09:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-14 08:05 ET

> [!failure] -$515 · -1.06R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-14|2026-01-14]] · [[Week 2026-W03|2026-W03]]

## The trade

|  |  |
|---|---|
| Entry | 26564.0 |
| Stop | 26584.25 |
| Target | 26431.23 |
| Exit price | 26584.5 |
| Micros | 12 |
| Risk $ | $486 |
| Minutes in | 15 |
| Best (MFE) | +0.33R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY pre 08-09:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.827 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.79 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
