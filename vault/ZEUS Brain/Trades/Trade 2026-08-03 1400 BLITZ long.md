---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-08-03"
time: "14:00"
week: "2026-W32"
side: "LONG"
exit: "STOP"
r: -0.153
pnl: -21.41
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-08-03 14:00 ET

> [!failure] -$21 · -0.15R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-08-03|2026-08-03]] · [[Week 2026-W32|2026-W32]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $140 |
| Minutes in | 27 |
| Best (MFE) | +1.38R |
| Worst (MAE) | -0.13R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.851 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.03 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
