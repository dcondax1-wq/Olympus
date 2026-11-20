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
date: "2026-02-17"
time: "02:15"
week: "2026-W08"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -339.6
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London 02-05"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# LIT short · 2026-02-17 02:15 ET

> [!failure] -$340 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-02-17|2026-02-17]] · [[Week 2026-W08|2026-W08]]

## The trade

|  |  |
|---|---|
| Entry | 25399.0 |
| Stop | 25440.5 |
| Target | 25214.0 |
| Exit price | 25440.75 |
| Micros | 4 |
| Risk $ | $332 |
| Minutes in | 33 |
| Best (MFE) | +0.38R |
| Worst (MAE) | -1.01R |

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
| Day's range before entry (ATR) | 0.49 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.03 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
