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
date: "2026-09-22"
time: "12:00"
week: "2026-W39"
side: "LONG"
exit: "TIME"
r: -0.291
pnl: -26.4
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY lunch 11:30-13:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-09-22 12:00 ET

> [!failure] -$26 · -0.29R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-22|2026-09-22]] · [[Week 2026-W39|2026-W39]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $91 |
| Minutes in | 31 |
| Best (MFE) | +0.55R |
| Worst (MAE) | -0.50R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.768 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.07 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
