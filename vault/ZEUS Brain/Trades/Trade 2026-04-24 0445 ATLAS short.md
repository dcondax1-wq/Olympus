---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-24"
time: "04:45"
week: "2026-W17"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -428.7
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-04-24 04:45 ET

> [!failure] -$429 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-24|2026-04-24]] · [[Week 2026-W17|2026-W17]]

## The trade

|  |  |
|---|---|
| Entry | 27667.75 |
| Stop | 27738.0 |
| Target | 27240.56 |
| Exit price | 27738.25 |
| Micros | 3 |
| Risk $ | $422 |
| Minutes in | 94 |
| Best (MFE) | +0.27R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.362 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.8 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
