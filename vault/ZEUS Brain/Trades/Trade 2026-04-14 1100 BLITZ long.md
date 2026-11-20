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
date: "2026-04-14"
time: "11:00"
week: "2026-W16"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -76.48
result: "loss"
member: "BLITZ"
cause: "wick"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-04-14 11:00 ET

> [!failure] -$76 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-14|2026-04-14]] · [[Week 2026-W16|2026-W16]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $76 |
| Minutes in | 7 |
| Best (MFE) | +0.03R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.484 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 3.13 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
