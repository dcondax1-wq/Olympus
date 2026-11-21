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
date: "2026-06-03"
time: "03:15"
week: "2026-W23"
side: "LONG"
exit: "BE"
r: 0.0
pnl: 0.38
result: "flat"
account: "atlas"
member: "EMA"
flags:
  - "no_room"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-06-03 03:15 ET

> [!note] +$0 · +0.00R · BE · backtest
> [[ATLAS]] · [[Day 2026-06-03|2026-06-03]] · [[Week 2026-W23|2026-W23]]

## The trade

|  |  |
|---|---|
| Entry | 31314.0 |
| Stop | 31254.0 |
| Target | 31636.95 |
| Exit price | 31315.0 |
| Micros | 4 |
| Risk $ | $480 |
| Minutes in | 313 |
| Best (MFE) | +1.15R |
| Worst (MAE) | -0.72R |

## Checklist flags (it still won)

- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.418 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.19 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
