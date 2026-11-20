---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-07-10"
time: "11:40"
week: "2026-W28"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -461.7
result: "loss"
account: "atlas"
member: "S/R"
cause: "turned"
session: "NY lunch 11:30-13:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-07-10 11:40 ET

> [!failure] -$462 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-07-10|2026-07-10]] · [[Week 2026-W28|2026-W28]]

## The trade

|  |  |
|---|---|
| Entry | 30210.75 |
| Stop | 30286.5 |
| Target | 30059.25 |
| Exit price | 30286.75 |
| Micros | 3 |
| Risk $ | $454 |
| Minutes in | 40 |
| Best (MFE) | +1.08R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY lunch 11:30-13:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.434 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.29 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
