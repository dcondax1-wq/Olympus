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
date: "2026-04-28"
time: "04:30"
week: "2026-W18"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -447.6
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-28 04:30 ET

> [!failure] -$448 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-28|2026-04-28]] · [[Week 2026-W18|2026-W18]]

## The trade

|  |  |
|---|---|
| Entry | 27941.0 |
| Stop | 27886.25 |
| Target | 28324.92 |
| Exit price | 27886.0 |
| Micros | 4 |
| Risk $ | $438 |
| Minutes in | 64 |
| Best (MFE) | +0.03R |
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
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.485 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.61 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
