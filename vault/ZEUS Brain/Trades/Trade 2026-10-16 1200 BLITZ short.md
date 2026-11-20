---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/win
  - flag/late
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-10-16"
time: "12:00"
week: "2026-W42"
side: "SHORT"
exit: "TIME"
r: 0.032
pnl: 5.1
result: "win"
member: "BLITZ"
flags:
  - "late"
  - "no_room"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-10-16 12:00 ET

> [!success] +$5 · +0.03R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-10-16|2026-10-16]] · [[Week 2026-W42|2026-W42]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $160 |
| Minutes in | 31 |
| Best (MFE) | +0.63R |
| Worst (MAE) | -0.63R |

## Checklist flags (it still won)

- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.214 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.92 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
