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
date: "2026-02-26"
time: "03:55"
week: "2026-W09"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -361.6
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

# LIT short · 2026-02-26 03:55 ET

> [!failure] -$362 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-02-26|2026-02-26]] · [[Week 2026-W09|2026-W09]]

## The trade

|  |  |
|---|---|
| Entry | 26147.5 |
| Stop | 26191.75 |
| Target | 25891.72 |
| Exit price | 26192.0 |
| Micros | 4 |
| Risk $ | $354 |
| Minutes in | 44 |
| Best (MFE) | +0.05R |
| Worst (MAE) | -1.01R |

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
| Day's range before entry (ATR) | 0.335 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.73 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
