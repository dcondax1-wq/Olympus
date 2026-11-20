---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-09-16"
time: "12:00"
week: "2026-W38"
side: "LONG"
exit: "TIME"
r: -0.404
pnl: -35.9
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jul-Oct 2026"
---

# BLITZ long · 2026-09-16 12:00 ET

> [!failure] -$36 · -0.40R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-09-16|2026-09-16]] · [[Week 2026-W38|2026-W38]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $89 |
| Minutes in | 31 |
| Best (MFE) | +0.06R |
| Worst (MAE) | -0.75R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.881 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.61 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
