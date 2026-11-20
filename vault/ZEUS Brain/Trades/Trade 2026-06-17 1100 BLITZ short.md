---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/never
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-06-17"
time: "11:00"
week: "2026-W25"
side: "SHORT"
exit: "TIME"
r: -0.499
pnl: -111.4
result: "loss"
member: "BLITZ"
cause: "never"
flags:
  - "no_room"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jan-Jun 2026"
---

# BLITZ short · 2026-06-17 11:00 ET

> [!failure] -$111 · -0.50R · TIME · backtest
> [[BLITZ (paper)]] · [[Day 2026-06-17|2026-06-17]] · [[Week 2026-W25|2026-W25]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $223 |
| Minutes in | 31 |
| Best (MFE) | +0.10R |
| Worst (MAE) | -0.92R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.381 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -0.52 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
