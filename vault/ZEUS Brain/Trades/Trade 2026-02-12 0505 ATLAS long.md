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
date: "2026-02-12"
time: "05:05"
week: "2026-W07"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -464.49
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-02-12 05:05 ET

> [!failure] -$464 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-02-12|2026-02-12]] · [[Week 2026-W07|2026-W07]]

## The trade

|  |  |
|---|---|
| Entry | 26169.0 |
| Stop | 26123.75 |
| Target | 26378.31 |
| Exit price | 26123.5 |
| Micros | 5 |
| Risk $ | $452 |
| Minutes in | 28 |
| Best (MFE) | +0.03R |
| Worst (MAE) | -0.79R |

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
| Day's range before entry (ATR) | 0.298 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.85 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
