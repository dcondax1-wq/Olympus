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
date: "2026-08-13"
time: "04:55"
week: "2026-W33"
side: "LONG"
exit: "STOP"
r: -1.12
pnl: -547.51
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
session: "London 02-05"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-08-13 04:55 ET

> [!failure] -$548 · -1.12R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-13|2026-08-13]] · [[Week 2026-W33|2026-W33]]

## The trade

|  |  |
|---|---|
| Entry | 30158.5 |
| Stop | 30148.75 |
| Target | 30236.5 |
| Exit price | 30148.5 |
| Micros | 25 |
| Risk $ | $488 |
| Minutes in | 10 |
| Best (MFE) | +0.59R |
| Worst (MAE) | -1.03R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.223 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.28 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
