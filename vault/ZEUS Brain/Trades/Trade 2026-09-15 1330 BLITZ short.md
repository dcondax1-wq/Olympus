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
time: "13:30"
week: "2026-W38"
side: "SHORT"
exit: "TIME"
r: -0.151
pnl: -11.4
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-09-15 13:30 ET

> [!failure] -$11 · -0.15R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-15|2026-09-15]] · [[Week 2026-W38|2026-W38]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $76 |
| Minutes in | 31 |
| Best (MFE) | +0.32R |
| Worst (MAE) | -0.48R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.753 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.03 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
