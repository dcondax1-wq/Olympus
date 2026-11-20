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
date: "2026-03-27"
time: "11:00"
week: "2026-W13"
side: "SHORT"
exit: "TIME"
r: -0.904
pnl: -132.4
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY AM 09:30-11:30"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-03-27 11:00 ET

> [!failure] -$132 · -0.90R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-03-27|2026-03-27]] · [[Week 2026-W13|2026-W13]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $146 |
| Minutes in | 31 |
| Best (MFE) | +0.73R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 25+ |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.983 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.24 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
