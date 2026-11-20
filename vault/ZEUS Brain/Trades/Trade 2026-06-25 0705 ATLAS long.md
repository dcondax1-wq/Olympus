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
date: "2026-06-25"
time: "07:05"
week: "2026-W26"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -474.48
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-06-25 07:05 ET

> [!failure] -$474 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-06-25|2026-06-25]] · [[Week 2026-W26|2026-W26]]

## The trade

|  |  |
|---|---|
| Entry | 30480.75 |
| Stop | 30434.5 |
| Target | 30741.09 |
| Exit price | 30434.25 |
| Micros | 5 |
| Risk $ | $462 |
| Minutes in | 20 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.00R |

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
| ES 1h | against |
| Day's range before entry (ATR) | 0.321 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.05 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
