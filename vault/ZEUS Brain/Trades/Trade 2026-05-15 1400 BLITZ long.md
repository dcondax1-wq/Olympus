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
date: "2026-05-15"
time: "14:00"
week: "2026-W20"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -117.16
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-15 14:00 ET

> [!failure] -$117 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-15|2026-05-15]] · [[Week 2026-W20|2026-W20]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $117 |
| Minutes in | 20 |
| Best (MFE) | +0.65R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.402 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.57 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
