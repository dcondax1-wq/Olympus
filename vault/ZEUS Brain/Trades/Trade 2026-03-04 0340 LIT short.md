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
date: "2026-03-04"
time: "03:40"
week: "2026-W10"
side: "SHORT"
exit: "CUT_T15"
r: -0.56
pnl: -139.8
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London 02-05"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# LIT short · 2026-03-04 03:40 ET

> [!failure] -$140 · -0.56R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-03-04|2026-03-04]] · [[Week 2026-W10|2026-W10]]

## The trade

|  |  |
|---|---|
| Entry | 25425.25 |
| Stop | 25487.75 |
| Target | 25131.24 |
| Exit price | 25459.5 |
| Micros | 2 |
| Risk $ | $250 |
| Minutes in | 16 |
| Best (MFE) | +0.10R |
| Worst (MAE) | -0.83R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 20-25 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.656 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.49 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
