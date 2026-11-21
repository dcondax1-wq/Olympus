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
date: "2026-04-21"
time: "03:15"
week: "2026-W17"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -449.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "turned"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-04-21 03:15 ET

> [!failure] -$449 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-04-21|2026-04-21]] · [[Week 2026-W17|2026-W17]]

## The trade

|  |  |
|---|---|
| Entry | 27405.0 |
| Stop | 27441.5 |
| Target | 27128.75 |
| Exit price | 27441.75 |
| Micros | 6 |
| Risk $ | $438 |
| Minutes in | 175 |
| Best (MFE) | +0.65R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.226 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.12 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
