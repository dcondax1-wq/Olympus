---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-05-21"
time: "05:10"
week: "2026-W21"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -484.5
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
flags:
  - "no_room"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-05-21 05:10 ET

> [!failure] -$484 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-05-21|2026-05-21]] · [[Week 2026-W21|2026-W21]]

## The trade

|  |  |
|---|---|
| Entry | 29980.25 |
| Stop | 29933.0 |
| Target | 30164.79 |
| Exit price | 29932.75 |
| Micros | 5 |
| Risk $ | $472 |
| Minutes in | 80 |
| Best (MFE) | +0.71R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.677 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.54 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
