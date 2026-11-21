---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-30"
time: "13:00"
week: "2026-W27"
side: "LONG"
exit: "TIME"
r: -0.061
pnl: -5.9
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-30 13:00 ET

> [!failure] -$6 · -0.06R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-30|2026-06-30]] · [[Week 2026-W27|2026-W27]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $97 |
| Minutes in | 31 |
| Best (MFE) | +0.73R |
| Worst (MAE) | -0.17R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.766 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.04 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
