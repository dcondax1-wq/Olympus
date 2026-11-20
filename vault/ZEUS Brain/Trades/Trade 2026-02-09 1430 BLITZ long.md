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
date: "2026-02-09"
time: "14:30"
week: "2026-W07"
side: "LONG"
exit: "TIME"
r: -0.497
pnl: -72.8
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-09 14:30 ET

> [!failure] -$73 · -0.50R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-09|2026-02-09]] · [[Week 2026-W07|2026-W07]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $146 |
| Minutes in | 31 |
| Best (MFE) | +0.28R |
| Worst (MAE) | -0.72R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.818 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.36 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
