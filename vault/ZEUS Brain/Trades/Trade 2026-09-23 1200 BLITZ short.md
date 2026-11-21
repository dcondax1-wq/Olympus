---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/win
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-09-23"
time: "12:00"
week: "2026-W39"
side: "SHORT"
exit: "TIME"
r: 0.083
pnl: 9.6
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-09-23 12:00 ET

> [!success] +$10 · +0.08R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-23|2026-09-23]] · [[Week 2026-W39|2026-W39]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $115 |
| Minutes in | 31 |
| Best (MFE) | +0.55R |
| Worst (MAE) | -0.17R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.041 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.09 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
