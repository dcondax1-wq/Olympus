---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-10"
time: "04:45"
week: "2026-W15"
side: "LONG"
exit: "CUT"
r: -0.81
pnl: -383.2
result: "loss"
account: "atlas"
member: "MACD"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "CPI (consumer inflation)"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-10 04:45 ET

> [!failure] -$383 · -0.81R · CUT · backtest
> [[ATLAS]] · [[Day 2026-04-10|2026-04-10]] · [[Week 2026-W15|2026-W15]]

## The trade

|  |  |
|---|---|
| Entry | 25816.25 |
| Stop | 25786.5 |
| Target | 26054.25 |
| Exit price | 25793.25 |
| Micros | 8 |
| Risk $ | $476 |
| Minutes in | 15 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -0.98R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.193 |

## News that day

- [[News CPI (consumer inflation)|CPI (consumer inflation)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.67 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
