---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-10"
time: "03:30"
week: "2026-W15"
side: "LONG"
exit: "STOP"
r: -1.05
pnl: -476.09
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
flags:
  - "no_room"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "CPI (consumer inflation)"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-10 03:30 ET

> [!failure] -$476 · -1.05R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-10|2026-04-10]] · [[Week 2026-W15|2026-W15]]

## The trade

|  |  |
|---|---|
| Entry | 25832.0 |
| Stop | 25806.75 |
| Target | 26034.0 |
| Exit price | 25806.5 |
| Micros | 9 |
| Risk $ | $454 |
| Minutes in | 40 |
| Best (MFE) | +0.32R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.193 |

## News that day

- [[News CPI (consumer inflation)|CPI (consumer inflation)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.64 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
