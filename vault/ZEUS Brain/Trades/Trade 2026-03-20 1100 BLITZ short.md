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
date: "2026-03-20"
time: "11:00"
week: "2026-W12"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -147.23
result: "loss"
member: "BLITZ"
cause: "wick"
session: "NY AM 09:30-11:30"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-03-20 11:00 ET

> [!failure] -$147 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-20|2026-03-20]] · [[Week 2026-W12|2026-W12]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $147 |
| Minutes in | 24 |
| Best (MFE) | +0.45R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.786 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.05 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
