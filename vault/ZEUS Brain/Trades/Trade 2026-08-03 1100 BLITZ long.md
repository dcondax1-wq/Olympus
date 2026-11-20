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
date: "2026-08-03"
time: "11:00"
week: "2026-W32"
side: "LONG"
exit: "TIME"
r: -0.63
pnl: -104.9
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-08-03 11:00 ET

> [!failure] -$105 · -0.63R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-08-03|2026-08-03]] · [[Week 2026-W32|2026-W32]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $167 |
| Minutes in | 31 |
| Best (MFE) | +0.01R |
| Worst (MAE) | -0.96R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.686 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.11 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
