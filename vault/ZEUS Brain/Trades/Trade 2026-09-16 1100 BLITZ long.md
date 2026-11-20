---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-09-16"
time: "11:00"
week: "2026-W38"
side: "LONG"
exit: "TIME"
r: -0.088
pnl: -7.9
result: "loss"
member: "BLITZ"
cause: "turned"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-09-16 11:00 ET

> [!failure] -$8 · -0.09R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-16|2026-09-16]] · [[Week 2026-W38|2026-W38]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $90 |
| Minutes in | 31 |
| Best (MFE) | +0.83R |
| Worst (MAE) | -0.33R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.748 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.31 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
