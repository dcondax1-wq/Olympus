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
date: "2026-10-06"
time: "04:32"
week: "2026-W41"
side: "SHORT"
exit: "CUT_T15"
r: -0.49
pnl: -187.0
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-10-06 04:32 ET

> [!failure] -$187 · -0.49R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-10-06|2026-10-06]] · [[Week 2026-W41|2026-W41]]

## The trade

|  |  |
|---|---|
| Entry | 31370.0 |
| Stop | 31408.5 |
| Target | 31082.25 |
| Exit price | 31388.0 |
| Micros | 5 |
| Risk $ | $385 |
| Minutes in | 16 |
| Best (MFE) | +0.23R |
| Worst (MAE) | -0.47R |

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
| Day's range before entry (ATR) | 0.209 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.51 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
