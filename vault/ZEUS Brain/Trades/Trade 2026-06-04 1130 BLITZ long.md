---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/wick
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-04"
time: "11:30"
week: "2026-W23"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -142.39
result: "loss"
member: "BLITZ"
cause: "wick"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-04 11:30 ET

> [!failure] -$142 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-04|2026-06-04]] · [[Week 2026-W23|2026-W23]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $142 |
| Minutes in | 20 |
| Best (MFE) | +0.09R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.84 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.46 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
