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
date: "2026-02-25"
time: "06:21"
week: "2026-W09"
side: "SHORT"
exit: "STOP"
r: -1.04
pnl: -754.8
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-02-25 06:21 ET

> [!failure] -$755 · -1.04R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-02-25|2026-02-25]] · [[Week 2026-W09|2026-W09]]

## The trade

|  |  |
|---|---|
| Entry | 25873.0 |
| Stop | 25894.25 |
| Target | 25721.0 |
| Exit price | 25894.5 |
| Micros | 17 |
| Risk $ | $722 |
| Minutes in | 12 |
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
| Day's range before entry (ATR) | 0.257 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.6 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
