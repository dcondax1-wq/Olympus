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
date: "2026-02-03"
time: "14:30"
week: "2026-W06"
side: "SHORT"
exit: "TIME"
r: -0.343
pnl: -46.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-02-03 14:30 ET

> [!failure] -$46 · -0.34R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-03|2026-02-03]] · [[Week 2026-W06|2026-W06]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $135 |
| Minutes in | 31 |
| Best (MFE) | +0.90R |
| Worst (MAE) | -0.53R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 1.78 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.63 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
