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
date: "2026-07-21"
time: "02:30"
week: "2026-W30"
side: "SHORT"
exit: "STOP"
r: -1.04
pnl: -511.2
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-07-21 02:30 ET

> [!failure] -$511 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-07-21|2026-07-21]] · [[Week 2026-W30|2026-W30]]

## The trade

|  |  |
|---|---|
| Entry | 29407.75 |
| Stop | 29438.5 |
| Target | 29161.75 |
| Exit price | 29438.75 |
| Micros | 8 |
| Risk $ | $492 |
| Minutes in | 6 |
| Best (MFE) | +0.00R |
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
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.706 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.7 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
