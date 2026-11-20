---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-05-08"
time: "11:00"
week: "2026-W19"
side: "LONG"
exit: "TIME"
r: -0.02
pnl: -2.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "Jobs report (NFP)"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-08 11:00 ET

> [!failure] -$2 · -0.02R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-08|2026-05-08]] · [[Week 2026-W19|2026-W19]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $117 |
| Minutes in | 31 |
| Best (MFE) | +0.44R |
| Worst (MAE) | -0.66R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.521 |

## News that day

- [[News Jobs report (NFP)|Jobs report (NFP)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.24 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
