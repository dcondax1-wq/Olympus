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
date: "2026-07-03"
time: "05:58"
week: "2026-W27"
side: "SHORT"
exit: "CUT_T15"
r: -0.42
pnl: -203.2
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-07-03 05:58 ET

> [!failure] -$203 · -0.42R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-07-03|2026-07-03]] · [[Week 2026-W27|2026-W27]]

## The trade

|  |  |
|---|---|
| Entry | 30165.25 |
| Stop | 30195.25 |
| Target | 29963.5 |
| Exit price | 30177.25 |
| Micros | 8 |
| Risk $ | $480 |
| Minutes in | 16 |
| Best (MFE) | +0.48R |
| Worst (MAE) | -0.40R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.494 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.02 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
