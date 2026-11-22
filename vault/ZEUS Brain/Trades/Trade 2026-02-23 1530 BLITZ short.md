---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-02-23"
time: "15:30"
week: "2026-W09"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -146.41
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "no_room"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-02-23 15:30 ET

> [!failure] -$146 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-23|2026-02-23]] · [[Week 2026-W09|2026-W09]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $146 |
| Minutes in | 4 |
| Best (MFE) | +0.06R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.74 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.71 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
