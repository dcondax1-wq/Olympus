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
date: "2026-08-28"
time: "11:00"
week: "2026-W35"
side: "LONG"
exit: "TIME"
r: -0.255
pnl: -36.4
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-08-28 11:00 ET

> [!failure] -$36 · -0.26R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-08-28|2026-08-28]] · [[Week 2026-W35|2026-W35]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $143 |
| Minutes in | 31 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -0.88R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.76 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -3.97 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
