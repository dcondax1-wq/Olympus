---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/win
  - flag/against_htf
  - flag/late
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-11"
time: "14:30"
week: "2026-W24"
side: "LONG"
exit: "TIME"
r: 0.711
pnl: 213.6
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "late"
  - "no_room"
session: "NY PM 13:30-16"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-11 14:30 ET

> [!success] +$214 · +0.71R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-11|2026-06-11]] · [[Week 2026-W24|2026-W24]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $300 |
| Minutes in | 31 |
| Best (MFE) | +0.84R |
| Worst (MAE) | -0.10R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.575 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.22 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
