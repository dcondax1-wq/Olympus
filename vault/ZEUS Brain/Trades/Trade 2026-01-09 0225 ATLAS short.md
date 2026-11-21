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
date: "2026-01-09"
time: "02:25"
week: "2026-W02"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -503.4
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "Jobs report (NFP)"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-09 02:25 ET

> [!failure] -$503 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-09|2026-01-09]] · [[Week 2026-W02|2026-W02]]

## The trade

|  |  |
|---|---|
| Entry | 26461.25 |
| Stop | 26502.0 |
| Target | 26266.1 |
| Exit price | 26502.25 |
| Micros | 6 |
| Risk $ | $489 |
| Minutes in | 49 |
| Best (MFE) | +0.24R |
| Worst (MAE) | -0.93R |

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
| Day's range before entry (ATR) | 0.358 |

## News that day

- [[News Jobs report (NFP)|Jobs report (NFP)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.87 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
