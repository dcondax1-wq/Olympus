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
date: "2026-01-26"
time: "12:00"
week: "2026-W05"
side: "LONG"
exit: "TIME"
r: -0.024
pnl: -1.9
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-01-26 12:00 ET

> [!failure] -$2 · -0.02R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-01-26|2026-01-26]] · [[Week 2026-W05|2026-W05]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $78 |
| Minutes in | 31 |
| Best (MFE) | +0.79R |
| Worst (MAE) | -0.11R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.566 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.35 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
