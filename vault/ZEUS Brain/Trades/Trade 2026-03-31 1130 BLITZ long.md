---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-03-31"
time: "11:30"
week: "2026-W14"
side: "LONG"
exit: "TIME"
r: -0.406
pnl: -65.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "against_htf"
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-31 11:30 ET

> [!failure] -$65 · -0.41R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-31|2026-03-31]] · [[Week 2026-W14|2026-W14]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $161 |
| Minutes in | 31 |
| Best (MFE) | +0.36R |
| Worst (MAE) | -0.71R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

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
| Move 60 min after the exit (R) | 4.2 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
