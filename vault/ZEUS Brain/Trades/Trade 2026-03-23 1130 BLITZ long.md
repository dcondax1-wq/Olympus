---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
  - flag/late
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-03-23"
time: "11:30"
week: "2026-W13"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -173.39
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
  - "late"
  - "no_room"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-23 11:30 ET

> [!failure] -$173 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-23|2026-03-23]] · [[Week 2026-W13|2026-W13]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $173 |
| Minutes in | 12 |
| Best (MFE) | +0.22R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.798 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.63 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
