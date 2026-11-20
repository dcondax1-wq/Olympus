---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/wick
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-17"
time: "02:15"
week: "2026-W16"
side: "LONG"
exit: "CUT"
r: -0.49
pnl: -226.8
result: "loss"
account: "atlas"
member: "MACD"
cause: "wick"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-17 02:15 ET

> [!failure] -$227 · -0.49R · CUT · backtest
> [[ATLAS]] · [[Day 2026-04-17|2026-04-17]] · [[Week 2026-W16|2026-W16]]

## The trade

|  |  |
|---|---|
| Entry | 27057.0 |
| Stop | 27023.75 |
| Target | 27323.0 |
| Exit price | 27041.75 |
| Micros | 7 |
| Risk $ | $466 |
| Minutes in | 15 |
| Best (MFE) | +0.17R |
| Worst (MAE) | -0.44R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.115 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.38 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
