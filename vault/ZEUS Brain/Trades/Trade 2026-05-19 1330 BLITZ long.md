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
date: "2026-05-19"
time: "13:30"
week: "2026-W21"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -146.03
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-19 13:30 ET

> [!failure] -$146 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-19|2026-05-19]] · [[Week 2026-W21|2026-W21]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $146 |
| Minutes in | 25 |
| Best (MFE) | +0.51R |
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
| Day's range before entry (ATR) | 1.061 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.49 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
