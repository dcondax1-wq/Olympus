---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-02"
time: "12:00"
week: "2026-W23"
side: "LONG"
exit: "TIME"
r: -0.572
pnl: -52.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "no_room"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-02 12:00 ET

> [!failure] -$52 · -0.57R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-02|2026-06-02]] · [[Week 2026-W23|2026-W23]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $92 |
| Minutes in | 31 |
| Best (MFE) | +0.52R |
| Worst (MAE) | -0.88R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.803 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.48 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
