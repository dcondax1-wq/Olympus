---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/wick
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-24"
time: "04:20"
week: "2026-W17"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -469.61
result: "loss"
account: "atlas"
member: "EMA"
cause: "wick"
flags:
  - "no_room"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-24 04:20 ET

> [!failure] -$470 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-24|2026-04-24]] · [[Week 2026-W17|2026-W17]]

## The trade

|  |  |
|---|---|
| Entry | 27714.5 |
| Stop | 27657.0 |
| Target | 27911.44 |
| Exit price | 27656.75 |
| Micros | 4 |
| Risk $ | $460 |
| Minutes in | 65 |
| Best (MFE) | +0.40R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.322 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.6 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
