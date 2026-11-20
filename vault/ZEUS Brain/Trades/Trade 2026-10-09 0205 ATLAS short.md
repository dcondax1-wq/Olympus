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
date: "2026-10-09"
time: "02:05"
week: "2026-W41"
side: "SHORT"
exit: "STOP"
r: -1.04
pnl: -495.2
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-10-09 02:05 ET

> [!failure] -$495 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-10-09|2026-10-09]] · [[Week 2026-W41|2026-W41]]

## The trade

|  |  |
|---|---|
| Entry | 31147.5 |
| Stop | 31177.25 |
| Target | 30909.5 |
| Exit price | 31177.5 |
| Micros | 8 |
| Risk $ | $476 |
| Minutes in | 31 |
| Best (MFE) | +0.48R |
| Worst (MAE) | -1.01R |

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
| Day's range before entry (ATR) | 0.46 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.63 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
