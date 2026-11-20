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
date: "2026-08-18"
time: "09:40"
week: "2026-W34"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -383.7
result: "loss"
account: "atlas"
member: "S/R"
cause: "turned"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-08-18 09:40 ET

> [!failure] -$384 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-18|2026-08-18]] · [[Week 2026-W34|2026-W34]]

## The trade

|  |  |
|---|---|
| Entry | 30030.5 |
| Stop | 29967.75 |
| Target | 30156.0 |
| Exit price | 29967.5 |
| Micros | 3 |
| Risk $ | $376 |
| Minutes in | 10 |
| Best (MFE) | +0.54R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.85 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.08 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
