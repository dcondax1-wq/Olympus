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
date: "2026-04-22"
time: "08:59"
week: "2026-W17"
side: "SHORT"
exit: "STOP"
r: -1.01
pnl: -155.9
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "NY pre 08-09:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-04-22 08:59 ET

> [!failure] -$156 · -1.01R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-04-22|2026-04-22]] · [[Week 2026-W17|2026-W17]]

## The trade

|  |  |
|---|---|
| Entry | 27407.75 |
| Stop | 27484.75 |
| Target | 26977.99 |
| Exit price | 27485.0 |
| Micros | 1 |
| Risk $ | $154 |
| Minutes in | 69 |
| Best (MFE) | +0.16R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY pre 08-09:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.395 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.92 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
