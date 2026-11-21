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
date: "2026-02-10"
time: "03:45"
week: "2026-W07"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -461.4
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-02-10 03:45 ET

> [!failure] -$461 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-02-10|2026-02-10]] · [[Week 2026-W07|2026-W07]]

## The trade

|  |  |
|---|---|
| Entry | 26129.25 |
| Stop | 26166.5 |
| Target | 25876.15 |
| Exit price | 26166.75 |
| Micros | 6 |
| Risk $ | $447 |
| Minutes in | 21 |
| Best (MFE) | +0.09R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.201 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.42 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
