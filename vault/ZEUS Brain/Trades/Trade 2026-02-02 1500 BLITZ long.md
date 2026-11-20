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
date: "2026-02-02"
time: "15:00"
week: "2026-W06"
side: "LONG"
exit: "TIME"
r: 0.381
pnl: 48.2
result: "win"
member: "BLITZ"
flags:
  - "against_htf"
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-02 15:00 ET

> [!success] +$48 · +0.38R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-02|2026-02-02]] · [[Week 2026-W06|2026-W06]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $127 |
| Minutes in | 31 |
| Best (MFE) | +1.72R |
| Worst (MAE) | -0.85R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | with |
| Day's range before entry (ATR) | 1.846 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.44 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
