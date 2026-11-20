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
date: "2026-03-20"
time: "10:35"
week: "2026-W12"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -458.7
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-03-20 10:35 ET

> [!failure] -$459 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-20|2026-03-20]] · [[Week 2026-W12|2026-W12]]

## The trade

|  |  |
|---|---|
| Entry | 24899.5 |
| Stop | 24824.25 |
| Target | 25501.5 |
| Exit price | 24824.0 |
| Micros | 3 |
| Risk $ | $452 |
| Minutes in | 20 |
| Best (MFE) | +0.16R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.769 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.94 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
