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
date: "2026-04-01"
time: "04:25"
week: "2026-W14"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -431.58
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-01 04:25 ET

> [!failure] -$432 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-01|2026-04-01]] · [[Week 2026-W14|2026-W14]]

## The trade

|  |  |
|---|---|
| Entry | 24670.0 |
| Stop | 24617.25 |
| Target | 24862.27 |
| Exit price | 24617.0 |
| Micros | 4 |
| Risk $ | $422 |
| Minutes in | 30 |
| Best (MFE) | +0.39R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.515 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.76 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
