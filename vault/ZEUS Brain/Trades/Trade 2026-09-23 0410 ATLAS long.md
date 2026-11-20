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
date: "2026-09-23"
time: "04:10"
week: "2026-W39"
side: "LONG"
exit: "STOP"
r: -1.05
pnl: -515.88
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-09-23 04:10 ET

> [!failure] -$516 · -1.05R · STOP · backtest
> [[ATLAS]] · [[Day 2026-09-23|2026-09-23]] · [[Week 2026-W39|2026-W39]] · reasons from the NQ 1m bars (data/NQ_1m.csv)

## The trade

|  |  |
|---|---|
| Entry | 31037.25 |
| Stop | 31015.0 |
| Target | 31215.25 |
| Exit price | 31014.75 |
| Micros | 11 |
| Risk $ | $490 |
| Minutes in | 30 |
| Best (MFE) | +0.63R |
| Worst (MAE) | -1.40R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
