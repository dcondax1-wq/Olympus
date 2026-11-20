---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-05-14"
time: "13:00"
week: "2026-W20"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -104.03
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-14 13:00 ET

> [!failure] -$104 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-14|2026-05-14]] · [[Week 2026-W20|2026-W20]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $104 |
| Minutes in | 11 |
| Best (MFE) | +0.51R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.706 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.34 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
