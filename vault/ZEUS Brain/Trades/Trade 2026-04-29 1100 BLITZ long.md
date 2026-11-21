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
date: "2026-04-29"
time: "11:00"
week: "2026-W18"
side: "LONG"
exit: "STOP"
r: -1.0
pnl: -95.9
result: "loss"
member: "BLITZ"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jan-Jun 2026"
---

# BLITZ long · 2026-04-29 11:00 ET

> [!failure] -$96 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-04-29|2026-04-29]] · [[Week 2026-W18|2026-W18]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $96 |
| Minutes in | 10 |
| Best (MFE) | +0.13R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.479 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | 0.01 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
