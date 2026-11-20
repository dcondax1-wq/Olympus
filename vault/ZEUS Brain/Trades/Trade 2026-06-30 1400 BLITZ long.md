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
time: "14:00"
week: "2026-W27"
side: "LONG"
exit: "TIME"
r: -0.044
pnl: -3.4
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-30 14:00 ET

> [!failure] -$3 · -0.04R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-30|2026-06-30]] · [[Week 2026-W27|2026-W27]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $77 |
| Minutes in | 31 |
| Best (MFE) | +0.65R |
| Worst (MAE) | -0.71R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.787 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.25 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
