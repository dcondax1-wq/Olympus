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
date: "2026-02-24"
time: "12:30"
week: "2026-W09"
side: "LONG"
exit: "TIME"
r: -0.301
pnl: -28.4
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-24 12:30 ET

> [!failure] -$28 · -0.30R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-24|2026-02-24]] · [[Week 2026-W09|2026-W09]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $94 |
| Minutes in | 31 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -0.62R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.762 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.3 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
