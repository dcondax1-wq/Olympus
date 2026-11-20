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
date: "2026-03-09"
time: "15:30"
week: "2026-W11"
side: "LONG"
exit: "STOP"
r: -0.067
pnl: -10.01
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "against_htf"
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-09 15:30 ET

> [!failure] -$10 · -0.07R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-09|2026-03-09]] · [[Week 2026-W11|2026-W11]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $148 |
| Minutes in | 12 |
| Best (MFE) | +1.45R |
| Worst (MAE) | -0.79R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.957 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.06 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
