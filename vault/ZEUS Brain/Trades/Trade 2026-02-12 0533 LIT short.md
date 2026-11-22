---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-02-12"
time: "05:33"
week: "2026-W07"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -464.8
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-02-12 05:33 ET

> [!failure] -$465 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-02-12|2026-02-12]] · [[Week 2026-W07|2026-W07]]

## The trade

|  |  |
|---|---|
| Entry | 26141.25 |
| Stop | 26173.5 |
| Target | 25883.25 |
| Exit price | 26173.75 |
| Micros | 7 |
| Risk $ | $452 |
| Minutes in | 119 |
| Best (MFE) | +0.12R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.298 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.82 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
