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
time: "15:00"
week: "2026-W09"
side: "LONG"
exit: "TIME"
r: -0.692
pnl: -89.8
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-24 15:00 ET

> [!failure] -$90 · -0.69R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-24|2026-02-24]] · [[Week 2026-W09|2026-W09]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $130 |
| Minutes in | 31 |
| Best (MFE) | +0.22R |
| Worst (MAE) | -0.84R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.767 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.68 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
