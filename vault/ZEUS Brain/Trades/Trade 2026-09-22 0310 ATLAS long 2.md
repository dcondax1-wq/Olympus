---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-09-22"
time: "03:10"
week: "2026-W39"
side: "LONG"
exit: "STOP"
r: -1.07
pnl: -523.5
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
session: "London 02-05"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-09-22 03:10 ET

> [!failure] -$524 · -1.07R · STOP · backtest
> [[ATLAS]] · [[Day 2026-09-22|2026-09-22]] · [[Week 2026-W39|2026-W39]]

## The trade

|  |  |
|---|---|
| Entry | 30781.5 |
| Stop | 30765.25 |
| Target | 30911.5 |
| Exit price | 30765.0 |
| Micros | 15 |
| Risk $ | $488 |
| Minutes in | 21 |
| Best (MFE) | +0.77R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.354 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -5.57 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
