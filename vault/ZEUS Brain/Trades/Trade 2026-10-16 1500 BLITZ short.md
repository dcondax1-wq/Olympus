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
date: "2026-10-16"
time: "15:00"
week: "2026-W42"
side: "SHORT"
exit: "STOP"
r: -0.285
pnl: -42.47
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-10-16 15:00 ET

> [!failure] -$42 · -0.28R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-10-16|2026-10-16]] · [[Week 2026-W42|2026-W42]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $149 |
| Minutes in | 14 |
| Best (MFE) | +1.23R |
| Worst (MAE) | -0.28R |

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
| Day's range before entry (ATR) | 1.905 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.2 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
