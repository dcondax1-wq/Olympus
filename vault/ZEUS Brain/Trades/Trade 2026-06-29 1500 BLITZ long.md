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
date: "2026-06-29"
time: "15:00"
week: "2026-W27"
side: "LONG"
exit: "TIME"
r: -0.328
pnl: -30.9
result: "loss"
member: "BLITZ"
cause: "turned"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-06-29 15:00 ET

> [!failure] -$31 · -0.33R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-29|2026-06-29]] · [[Week 2026-W27|2026-W27]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $94 |
| Minutes in | 31 |
| Best (MFE) | +0.56R |
| Worst (MAE) | -0.79R |

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
| Day's range before entry (ATR) | 0.928 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.6 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
