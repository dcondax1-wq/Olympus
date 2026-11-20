---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-07-06"
time: "04:46"
week: "2026-W28"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -353.6
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-07-06 04:46 ET

> [!failure] -$354 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-07-06|2026-07-06]] · [[Week 2026-W28|2026-W28]]

## The trade

|  |  |
|---|---|
| Entry | 30135.75 |
| Stop | 30179.0 |
| Target | 29917.5 |
| Exit price | 30179.25 |
| Micros | 4 |
| Risk $ | $346 |
| Minutes in | 69 |
| Best (MFE) | +0.31R |
| Worst (MAE) | -1.01R |

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
| ES 1h | against |
| Day's range before entry (ATR) | 0.45 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.45 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
