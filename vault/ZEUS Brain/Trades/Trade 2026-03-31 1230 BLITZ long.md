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
date: "2026-03-31"
time: "12:30"
week: "2026-W14"
side: "LONG"
exit: "STOP"
r: 2.839
pnl: 402.2
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "late"
  - "no_room"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-31 12:30 ET

> [!success] +$402 · +2.84R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-31|2026-03-31]] · [[Week 2026-W14|2026-W14]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $142 |
| Minutes in | 17 |
| Best (MFE) | +4.41R |
| Worst (MAE) | -0.28R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.172 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.5 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
