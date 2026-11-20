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
date: "2026-06-17"
time: "04:55"
week: "2026-W25"
side: "LONG"
exit: "STOP"
r: -1.04
pnl: -519.2
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-06-17 04:55 ET

> [!failure] -$519 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-06-17|2026-06-17]] · [[Week 2026-W25|2026-W25]]

## The trade

|  |  |
|---|---|
| Entry | 30790.25 |
| Stop | 30759.0 |
| Target | 30917.59 |
| Exit price | 30758.75 |
| Micros | 8 |
| Risk $ | $500 |
| Minutes in | 60 |
| Best (MFE) | +0.99R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.353 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.33 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
