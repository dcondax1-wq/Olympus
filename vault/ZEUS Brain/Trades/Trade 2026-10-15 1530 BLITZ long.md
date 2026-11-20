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
time: "15:30"
week: "2026-W42"
side: "LONG"
exit: "STOP"
r: -0.297
pnl: -30.54
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "against_htf"
  - "late"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
news:
  - "Other releases"
  - "PPI (producer inflation)"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-10-15 15:30 ET

> [!failure] -$31 · -0.30R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-10-15|2026-10-15]] · [[Week 2026-W42|2026-W42]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $103 |
| Minutes in | 22 |
| Best (MFE) | +1.22R |
| Worst (MAE) | -0.29R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.216 |

## News that day

- [[News Other releases|Other releases]]
- [[News PPI (producer inflation)|PPI (producer inflation)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.73 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
