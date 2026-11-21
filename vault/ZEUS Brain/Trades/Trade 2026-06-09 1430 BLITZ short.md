---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/late
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-09"
time: "14:30"
week: "2026-W24"
side: "SHORT"
exit: "TIME"
r: -0.433
pnl: -141.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
  - "no_room"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-06-09 14:30 ET

> [!failure] -$141 · -0.43R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-09|2026-06-09]] · [[Week 2026-W24|2026-W24]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $327 |
| Minutes in | 31 |
| Best (MFE) | +0.38R |
| Worst (MAE) | -0.73R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 2.91 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.06 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
