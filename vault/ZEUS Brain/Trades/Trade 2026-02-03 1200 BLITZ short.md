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
date: "2026-02-03"
time: "12:00"
week: "2026-W06"
side: "SHORT"
exit: "TIME"
r: 1.158
pnl: 176.6
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-02-03 12:00 ET

> [!success] +$177 · +1.16R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-03|2026-02-03]] · [[Week 2026-W06|2026-W06]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $152 |
| Minutes in | 31 |
| Best (MFE) | +1.20R |
| Worst (MAE) | -0.15R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.233 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.22 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
