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
date: "2026-04-03"
time: "04:05"
week: "2026-W14"
side: "LONG"
exit: "STOP"
r: -1.08
pnl: -510.42
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London 02-05"
vix_band: "VIX 20-25"
news:
  - "Jobs report (NFP)"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-03 04:05 ET

> [!failure] -$510 · -1.08R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-03|2026-04-03]] · [[Week 2026-W14|2026-W14]]

## The trade

|  |  |
|---|---|
| Entry | 24747.75 |
| Stop | 24733.0 |
| Target | 24865.75 |
| Exit price | 24732.75 |
| Micros | 16 |
| Risk $ | $472 |
| Minutes in | 20 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.02R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.226 |

## News that day

- [[News Jobs report (NFP)|Jobs report (NFP)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.44 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
