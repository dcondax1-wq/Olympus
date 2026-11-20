---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/flat
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-03-19"
time: "03:35"
week: "2026-W12"
side: "SHORT"
exit: "BE"
r: 0.0
pnl: 0.4
result: "flat"
account: "atlas"
member: "EMA"
flags:
  - "no_room"
session: "London 02-05"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-03-19 03:35 ET

> [!note] +$0 · +0.00R · BE · backtest
> [[ATLAS]] · [[Day 2026-03-19|2026-03-19]] · [[Week 2026-W12|2026-W12]]

## The trade

|  |  |
|---|---|
| Entry | 25155.25 |
| Stop | 25211.0 |
| Target | 24807.61 |
| Exit price | 25154.25 |
| Micros | 4 |
| Risk $ | $446 |
| Minutes in | 80 |
| Best (MFE) | +1.18R |
| Worst (MAE) | -0.40R |

## Checklist flags (it still won)

- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 25+ |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.31 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.07 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
