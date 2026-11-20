---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/win
  - flag/against_htf
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-02-24"
time: "11:30"
week: "2026-W09"
side: "LONG"
exit: "TIME"
r: 0.1
pnl: 12.1
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "no_room"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-24 11:30 ET

> [!success] +$12 · +0.10R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-24|2026-02-24]] · [[Week 2026-W09|2026-W09]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $122 |
| Minutes in | 31 |
| Best (MFE) | +0.42R |
| Worst (MAE) | -0.78R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.704 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.42 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
