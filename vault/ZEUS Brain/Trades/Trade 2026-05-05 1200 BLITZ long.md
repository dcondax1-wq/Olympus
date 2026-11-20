---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/wick
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-05-05"
time: "12:00"
week: "2026-W19"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -149.57
result: "loss"
member: "BLITZ"
cause: "wick"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-05 12:00 ET

> [!failure] -$150 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-05|2026-05-05]] · [[Week 2026-W19|2026-W19]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $150 |
| Minutes in | 29 |
| Best (MFE) | +0.70R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.061 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.46 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
