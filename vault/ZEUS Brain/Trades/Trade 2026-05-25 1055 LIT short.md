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
date: "2026-05-25"
time: "10:55"
week: "2026-W22"
side: "SHORT"
exit: "TIME"
r: -0.55
pnl: -73.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-05-25 10:55 ET

> [!failure] -$73 · -0.55R · TIME · backtest
> [[Zlarior (LIT)]] · [[Day 2026-05-25|2026-05-25]] · [[Week 2026-W22|2026-W22]]

## The trade

|  |  |
|---|---|
| Entry | 30510.75 |
| Stop | 30578.0 |
| Target | 30085.25 |
| Exit price | 30546.75 |
| Micros | 1 |
| Risk $ | $134 |
| Minutes in | 125 |
| Best (MFE) | +0.20R |
| Worst (MAE) | -0.95R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.612 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
