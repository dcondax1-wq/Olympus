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
date: "2026-01-02"
time: "02:00"
week: "2026-W01"
side: "SHORT"
exit: "STOP"
r: -1.08
pnl: -525.3
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
session: "London 02-05"
vix_band: "VIX <15"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-02 02:00 ET

> [!failure] -$525 · -1.08R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-02|2026-01-02]] · [[Week 2026-W01|2026-W01]]

## The trade

|  |  |
|---|---|
| Entry | 26435.25 |
| Stop | 26449.5 |
| Target | 26321.25 |
| Exit price | 26449.75 |
| Micros | 17 |
| Risk $ | $484 |
| Minutes in | 61 |
| Best (MFE) | +0.79R |
| Worst (MAE) | -1.02R |

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
| Day's range before entry (ATR) | 0.594 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -4.14 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
