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
date: "2026-05-05"
time: "02:17"
week: "2026-W19"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -278.7
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

# LIT short · 2026-05-05 02:17 ET

> [!failure] -$279 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-05-05|2026-05-05]] · [[Week 2026-W19|2026-W19]]

## The trade

|  |  |
|---|---|
| Entry | 28412.25 |
| Stop | 28457.75 |
| Target | 28208.0 |
| Exit price | 28458.0 |
| Micros | 3 |
| Risk $ | $273 |
| Minutes in | 35 |
| Best (MFE) | +0.22R |
| Worst (MAE) | -1.00R |

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
| ES 1h | with |
| Day's range before entry (ATR) | 0.36 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.27 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
