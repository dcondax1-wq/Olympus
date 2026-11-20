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
date: "2026-09-21"
time: "07:24"
week: "2026-W39"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -353.6
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "London late 05-08"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# LIT short · 2026-09-21 07:24 ET

> [!failure] -$354 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-09-21|2026-09-21]] · [[Week 2026-W39|2026-W39]]

## The trade

|  |  |
|---|---|
| Entry | 30223.75 |
| Stop | 30267.0 |
| Target | 30026.25 |
| Exit price | 30267.25 |
| Micros | 4 |
| Risk $ | $346 |
| Minutes in | 41 |
| Best (MFE) | +0.18R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.911 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.79 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
