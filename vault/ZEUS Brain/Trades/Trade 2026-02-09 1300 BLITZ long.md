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
date: "2026-02-09"
time: "13:00"
week: "2026-W07"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -138.34
result: "loss"
member: "BLITZ"
cause: "wick"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-02-09 13:00 ET

> [!failure] -$138 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-02-09|2026-02-09]] · [[Week 2026-W07|2026-W07]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $138 |
| Minutes in | 22 |
| Best (MFE) | +0.79R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.806 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 2.21 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
