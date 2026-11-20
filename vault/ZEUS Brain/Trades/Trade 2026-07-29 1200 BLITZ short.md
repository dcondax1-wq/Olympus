---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/late
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-07-29"
time: "12:00"
week: "2026-W31"
side: "SHORT"
exit: "STOP"
r: -0.362
pnl: -69.47
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "late"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-07-29 12:00 ET

> [!failure] -$69 · -0.36R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-07-29|2026-07-29]] · [[Week 2026-W31|2026-W31]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $192 |
| Minutes in | 29 |
| Best (MFE) | +1.15R |
| Worst (MAE) | -0.36R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.127 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -1.35 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
