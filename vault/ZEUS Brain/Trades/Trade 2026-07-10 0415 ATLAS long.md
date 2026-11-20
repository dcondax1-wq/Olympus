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
date: "2026-07-10"
time: "04:15"
week: "2026-W28"
side: "LONG"
exit: "CUT"
r: -0.56
pnl: -241.6
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-07-10 04:15 ET

> [!failure] -$242 · -0.56R · CUT · backtest
> [[ATLAS]] · [[Day 2026-07-10|2026-07-10]] · [[Week 2026-W28|2026-W28]]

## The trade

|  |  |
|---|---|
| Entry | 30092.0 |
| Stop | 30038.25 |
| Target | 30522.0 |
| Exit price | 30062.75 |
| Micros | 4 |
| Risk $ | $430 |
| Minutes in | 15 |
| Best (MFE) | +0.11R |
| Worst (MAE) | -0.78R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.303 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.85 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
