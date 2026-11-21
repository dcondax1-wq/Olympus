---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-08"
time: "11:00"
week: "2026-W24"
side: "LONG"
exit: "TIME"
r: -0.814
pnl: -182.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "against_htf"
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-08 11:00 ET

> [!failure] -$182 · -0.81R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-08|2026-06-08]] · [[Week 2026-W24|2026-W24]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $224 |
| Minutes in | 31 |
| Best (MFE) | +0.60R |
| Worst (MAE) | -0.87R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.624 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.17 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
