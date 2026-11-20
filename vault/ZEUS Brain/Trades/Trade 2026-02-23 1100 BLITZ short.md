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
date: "2026-02-23"
time: "11:00"
week: "2026-W09"
side: "SHORT"
exit: "STOP"
r: -0.393
pnl: -53.69
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "no_room"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-02-23 11:00 ET

> [!failure] -$54 · -0.39R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-23|2026-02-23]] · [[Week 2026-W09|2026-W09]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $137 |
| Minutes in | 29 |
| Best (MFE) | +1.12R |
| Worst (MAE) | -0.39R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.606 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.31 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
