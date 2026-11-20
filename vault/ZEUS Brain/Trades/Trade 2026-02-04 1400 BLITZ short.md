---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-02-04"
time: "14:00"
week: "2026-W06"
side: "SHORT"
exit: "TIME"
r: -0.595
pnl: -112.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-02-04 14:00 ET

> [!failure] -$112 · -0.59R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-04|2026-02-04]] · [[Week 2026-W06|2026-W06]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $189 |
| Minutes in | 31 |
| Best (MFE) | +0.64R |
| Worst (MAE) | -0.75R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.535 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.81 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
