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
date: "2026-07-30"
time: "14:00"
week: "2026-W31"
side: "LONG"
exit: "TIME"
r: 0.293
pnl: 37.1
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "late"
  - "no_room"
session: "NY PM 13:30-16"
vix_band: "VIX 20-25"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-07-30 14:00 ET

> [!success] +$37 · +0.29R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-07-30|2026-07-30]] · [[Week 2026-W31|2026-W31]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $127 |
| Minutes in | 31 |
| Best (MFE) | +0.44R |
| Worst (MAE) | -0.25R |

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
| Day's range before entry (ATR) | 1.583 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.9 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
