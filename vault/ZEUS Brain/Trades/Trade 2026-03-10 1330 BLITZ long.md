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
date: "2026-03-10"
time: "13:30"
week: "2026-W11"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -100.59
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-03-10 13:30 ET

> [!failure] -$101 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-10|2026-03-10]] · [[Week 2026-W11|2026-W11]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $101 |
| Minutes in | 5 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.725 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.63 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
