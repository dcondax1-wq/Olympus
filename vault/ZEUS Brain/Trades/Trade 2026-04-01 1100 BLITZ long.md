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
date: "2026-04-01"
time: "11:00"
week: "2026-W14"
side: "LONG"
exit: "TIME"
r: -0.31
pnl: -50.9
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-04-01 11:00 ET

> [!failure] -$51 · -0.31R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-01|2026-04-01]] · [[Week 2026-W14|2026-W14]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $164 |
| Minutes in | 31 |
| Best (MFE) | +0.33R |
| Worst (MAE) | -0.38R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.667 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.87 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
