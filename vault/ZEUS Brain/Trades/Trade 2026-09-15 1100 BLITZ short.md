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
date: "2026-09-15"
time: "11:00"
week: "2026-W38"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -99.69
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-09-15 11:00 ET

> [!failure] -$100 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-15|2026-09-15]] · [[Week 2026-W38|2026-W38]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $100 |
| Minutes in | 6 |
| Best (MFE) | +0.01R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.753 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.22 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
