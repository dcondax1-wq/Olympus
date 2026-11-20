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
date: "2026-03-27"
time: "13:00"
week: "2026-W13"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -111.1
result: "loss"
member: "BLITZ"
cause: "wick"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-03-27 13:00 ET

> [!failure] -$111 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-27|2026-03-27]] · [[Week 2026-W13|2026-W13]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $111 |
| Minutes in | 8 |
| Best (MFE) | +0.51R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 25+ |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.983 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 3.4 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
