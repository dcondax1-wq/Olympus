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
date: "2026-02-18"
time: "13:00"
week: "2026-W08"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -79.94
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-18 13:00 ET

> [!failure] -$80 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-18|2026-02-18]] · [[Week 2026-W08|2026-W08]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $80 |
| Minutes in | 28 |
| Best (MFE) | +0.75R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.73 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.7 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
