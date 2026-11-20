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
date: "2026-01-13"
time: "02:22"
week: "2026-W03"
side: "SHORT"
exit: "CUT_T15"
r: -0.45
pnl: -284.7
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "CPI (consumer inflation)"
span: "Jan-Jun 2026"
---

# LIT short · 2026-01-13 02:22 ET

> [!failure] -$285 · -0.45R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-01-13|2026-01-13]] · [[Week 2026-W03|2026-W03]]

## The trade

|  |  |
|---|---|
| Entry | 26708.0 |
| Stop | 26732.25 |
| Target | 26579.25 |
| Exit price | 26718.25 |
| Micros | 13 |
| Risk $ | $630 |
| Minutes in | 16 |
| Best (MFE) | +0.01R |
| Worst (MAE) | -0.65R |

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
| Day's range before entry (ATR) | 0.403 |

## News that day

- [[News CPI (consumer inflation)|CPI (consumer inflation)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.92 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
