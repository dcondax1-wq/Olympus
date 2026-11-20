---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-09-28"
time: "11:30"
week: "2026-W40"
side: "SHORT"
exit: "TIME"
r: -0.269
pnl: -37.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-09-28 11:30 ET

> [!failure] -$37 · -0.27R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-28|2026-09-28]] · [[Week 2026-W40|2026-W40]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $139 |
| Minutes in | 31 |
| Best (MFE) | +0.56R |
| Worst (MAE) | -0.55R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.234 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.02 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
