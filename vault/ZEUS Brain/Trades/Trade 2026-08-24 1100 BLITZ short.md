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
date: "2026-08-24"
time: "11:00"
week: "2026-W35"
side: "SHORT"
exit: "TIME"
r: -0.72
pnl: -96.9
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-08-24 11:00 ET

> [!failure] -$97 · -0.72R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-08-24|2026-08-24]] · [[Week 2026-W35|2026-W35]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $135 |
| Minutes in | 31 |
| Best (MFE) | +0.67R |
| Worst (MAE) | -0.82R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.176 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.09 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
