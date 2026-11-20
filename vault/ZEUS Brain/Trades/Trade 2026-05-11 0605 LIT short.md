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
date: "2026-05-11"
time: "06:05"
week: "2026-W20"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -212.8
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-05-11 06:05 ET

> [!failure] -$213 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-05-11|2026-05-11]] · [[Week 2026-W20|2026-W20]]

## The trade

|  |  |
|---|---|
| Entry | 29898.0 |
| Stop | 29950.25 |
| Target | 29572.25 |
| Exit price | 29950.5 |
| Micros | 2 |
| Risk $ | $209 |
| Minutes in | 78 |
| Best (MFE) | +0.47R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.382 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.53 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
