---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/late
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-09"
time: "15:30"
week: "2026-W24"
side: "SHORT"
exit: "EOD"
r: -0.536
pnl: -162.9
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
  - "no_room"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-06-09 15:30 ET

> [!failure] -$163 · -0.54R · EOD · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-09|2026-06-09]] · [[Week 2026-W24|2026-W24]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $304 |
| Minutes in | 25 |
| Best (MFE) | +0.68R |
| Worst (MAE) | -0.57R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 2.91 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
