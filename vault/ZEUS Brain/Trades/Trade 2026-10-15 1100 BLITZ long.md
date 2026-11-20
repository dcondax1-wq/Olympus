---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-10-15"
time: "11:00"
week: "2026-W42"
side: "LONG"
exit: "TIME"
r: -0.017
pnl: -3.4
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "against_htf"
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "Other releases"
  - "PPI (producer inflation)"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-10-15 11:00 ET

> [!failure] -$3 · -0.02R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-10-15|2026-10-15]] · [[Week 2026-W42|2026-W42]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $199 |
| Minutes in | 31 |
| Best (MFE) | +0.92R |
| Worst (MAE) | -0.46R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.166 |

## News that day

- [[News Other releases|Other releases]]
- [[News PPI (producer inflation)|PPI (producer inflation)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.59 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
