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
time: "14:00"
week: "2026-W14"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -145.84
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-04-01 14:00 ET

> [!failure] -$146 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-01|2026-04-01]] · [[Week 2026-W14|2026-W14]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $146 |
| Minutes in | 3 |
| Best (MFE) | +0.18R |
| Worst (MAE) | -1.01R |

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
| Day's range before entry (ATR) | 0.801 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.64 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
