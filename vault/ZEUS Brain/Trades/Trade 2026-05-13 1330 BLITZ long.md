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
date: "2026-05-13"
time: "13:30"
week: "2026-W20"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -92.69
result: "loss"
member: "BLITZ"
cause: "wick"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-05-13 13:30 ET

> [!failure] -$93 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-05-13|2026-05-13]] · [[Week 2026-W20|2026-W20]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $93 |
| Minutes in | 31 |
| Best (MFE) | +0.12R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.937 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 1.12 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
