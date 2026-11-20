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
date: "2026-02-09"
time: "12:00"
week: "2026-W07"
side: "LONG"
exit: "TIME"
r: -0.149
pnl: -13.4
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-09 12:00 ET

> [!failure] -$13 · -0.15R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-09|2026-02-09]] · [[Week 2026-W07|2026-W07]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $90 |
| Minutes in | 31 |
| Best (MFE) | +0.58R |
| Worst (MAE) | -0.28R |

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
| Day's range before entry (ATR) | 0.784 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.0 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
