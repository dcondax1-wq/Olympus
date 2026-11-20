---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-06-16"
time: "05:27"
week: "2026-W25"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -293.7
result: "loss"
account: "zlarior"
member: "LIT"
cause: "turned"
flags:
  - "against_htf"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-06-16 05:27 ET

> [!failure] -$294 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-06-16|2026-06-16]] · [[Week 2026-W25|2026-W25]]

## The trade

|  |  |
|---|---|
| Entry | 31191.5 |
| Stop | 31239.5 |
| Target | 30815.04 |
| Exit price | 31239.75 |
| Micros | 3 |
| Risk $ | $288 |
| Minutes in | 94 |
| Best (MFE) | +0.70R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.245 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.21 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
