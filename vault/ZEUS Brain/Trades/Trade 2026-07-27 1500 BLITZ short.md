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
date: "2026-07-27"
time: "15:00"
week: "2026-W31"
side: "SHORT"
exit: "TIME"
r: -0.781
pnl: -111.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-07-27 15:00 ET

> [!failure] -$111 · -0.78R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-07-27|2026-07-27]] · [[Week 2026-W31|2026-W31]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $143 |
| Minutes in | 31 |
| Best (MFE) | +0.33R |
| Worst (MAE) | -0.87R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.307 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.92 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
