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
date: "2026-08-04"
time: "04:00"
week: "2026-W32"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -489.5
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-08-04 04:00 ET

> [!failure] -$490 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-04|2026-08-04]] · [[Week 2026-W32|2026-W32]]

## The trade

|  |  |
|---|---|
| Entry | 29366.5 |
| Stop | 29414.25 |
| Target | 28984.5 |
| Exit price | 29414.5 |
| Micros | 5 |
| Risk $ | $478 |
| Minutes in | 7 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.00R |

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
| Day's range before entry (ATR) | 0.4 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.77 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
