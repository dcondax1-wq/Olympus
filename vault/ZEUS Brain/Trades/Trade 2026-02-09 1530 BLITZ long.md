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
time: "15:30"
week: "2026-W07"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -118.2
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-09 15:30 ET

> [!failure] -$118 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-09|2026-02-09]] · [[Week 2026-W07|2026-W07]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $118 |
| Minutes in | 7 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -1.01R |

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
| Day's range before entry (ATR) | 0.828 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.63 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
