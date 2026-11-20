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
date: "2026-10-08"
time: "15:30"
week: "2026-W41"
side: "SHORT"
exit: "EOD"
r: -0.112
pnl: -14.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-10-08 15:30 ET

> [!failure] -$14 · -0.11R · EOD · backtest
> [[BLITZ (paper)]] · [[Day 2026-10-08|2026-10-08]] · [[Week 2026-W41|2026-W41]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $129 |
| Minutes in | 25 |
| Best (MFE) | +0.46R |
| Worst (MAE) | -0.42R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.455 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
