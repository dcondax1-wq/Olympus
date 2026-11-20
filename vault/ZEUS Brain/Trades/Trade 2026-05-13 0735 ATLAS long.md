---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-05-13"
time: "07:35"
week: "2026-W20"
side: "LONG"
exit: "STOP"
r: -1.04
pnl: -491.21
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-05-13 07:35 ET

> [!failure] -$491 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-05-13|2026-05-13]] · [[Week 2026-W20|2026-W20]]

## The trade

|  |  |
|---|---|
| Entry | 29961.25 |
| Stop | 29931.75 |
| Target | 30064.64 |
| Exit price | 29931.5 |
| Micros | 8 |
| Risk $ | $472 |
| Minutes in | 45 |
| Best (MFE) | +0.93R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.833 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -2.08 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
