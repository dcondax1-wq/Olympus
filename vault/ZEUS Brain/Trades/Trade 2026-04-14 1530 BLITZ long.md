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
date: "2026-04-14"
time: "15:30"
week: "2026-W16"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -114.55
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-04-14 15:30 ET

> [!failure] -$115 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-14|2026-04-14]] · [[Week 2026-W16|2026-W16]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $115 |
| Minutes in | 6 |
| Best (MFE) | +0.26R |
| Worst (MAE) | -1.01R |

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
| Day's range before entry (ATR) | 0.799 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.11 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
