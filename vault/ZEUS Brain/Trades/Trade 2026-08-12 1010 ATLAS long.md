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
date: "2026-08-12"
time: "10:10"
week: "2026-W33"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -442.2
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "CPI (consumer inflation)"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-08-12 10:10 ET

> [!failure] -$442 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-12|2026-08-12]] · [[Week 2026-W33|2026-W33]]

## The trade

|  |  |
|---|---|
| Entry | 30214.75 |
| Stop | 30142.25 |
| Target | 30359.75 |
| Exit price | 30142.0 |
| Micros | 3 |
| Risk $ | $435 |
| Minutes in | 25 |
| Best (MFE) | +0.35R |
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
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.557 |

## News that day

- [[News CPI (consumer inflation)|CPI (consumer inflation)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.21 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
