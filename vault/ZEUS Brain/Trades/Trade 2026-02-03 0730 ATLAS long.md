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
date: "2026-02-03"
time: "07:30"
week: "2026-W06"
side: "LONG"
exit: "STOP"
r: -1.05
pnl: -515.88
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-02-03 07:30 ET

> [!failure] -$516 · -1.05R · STOP · backtest
> [[ATLAS]] · [[Day 2026-02-03|2026-02-03]] · [[Week 2026-W06|2026-W06]]

## The trade

|  |  |
|---|---|
| Entry | 26785.75 |
| Stop | 26763.5 |
| Target | 26950.33 |
| Exit price | 26763.25 |
| Micros | 11 |
| Risk $ | $490 |
| Minutes in | 90 |
| Best (MFE) | +0.76R |
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
| Day's range before entry (ATR) | 0.355 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -14.88 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
