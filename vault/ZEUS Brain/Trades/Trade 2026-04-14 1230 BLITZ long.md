---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-04-14"
time: "12:30"
week: "2026-W16"
side: "LONG"
exit: "TIME"
r: -0.32
pnl: -41.8
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-04-14 12:30 ET

> [!failure] -$42 · -0.32R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-14|2026-04-14]] · [[Week 2026-W16|2026-W16]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $131 |
| Minutes in | 31 |
| Best (MFE) | +0.32R |
| Worst (MAE) | -0.76R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.691 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.38 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
