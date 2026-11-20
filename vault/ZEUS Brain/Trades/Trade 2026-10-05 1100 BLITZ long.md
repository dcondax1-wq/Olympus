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
date: "2026-10-05"
time: "11:00"
week: "2026-W41"
side: "LONG"
exit: "TIME"
r: -0.367
pnl: -37.9
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "no_room"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-10-05 11:00 ET

> [!failure] -$38 · -0.37R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-10-05|2026-10-05]] · [[Week 2026-W41|2026-W41]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $103 |
| Minutes in | 31 |
| Best (MFE) | +0.12R |
| Worst (MAE) | -0.84R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.62 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.17 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
