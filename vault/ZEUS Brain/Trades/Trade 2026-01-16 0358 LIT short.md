---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-01-16"
time: "03:58"
week: "2026-W03"
side: "SHORT"
exit: "CUT_T15"
r: -0.6
pnl: -167.0
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-01-16 03:58 ET

> [!failure] -$167 · -0.60R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-01-16|2026-01-16]] · [[Week 2026-W03|2026-W03]]

## The trade

|  |  |
|---|---|
| Entry | 26616.75 |
| Stop | 26644.75 |
| Target | 26446.75 |
| Exit price | 26632.75 |
| Micros | 5 |
| Risk $ | $280 |
| Minutes in | 16 |
| Best (MFE) | +0.21R |
| Worst (MAE) | -0.80R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.452 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.18 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
