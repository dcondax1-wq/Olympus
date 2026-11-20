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
date: "2026-05-28"
time: "14:00"
week: "2026-W22"
side: "LONG"
exit: "TIME"
r: -0.413
pnl: -59.8
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-28 14:00 ET

> [!failure] -$60 · -0.41R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-28|2026-05-28]] · [[Week 2026-W22|2026-W22]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $145 |
| Minutes in | 31 |
| Best (MFE) | +0.51R |
| Worst (MAE) | -0.64R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.141 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.07 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
