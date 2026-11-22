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
date: "2026-09-15"
time: "08:34"
week: "2026-W38"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -440.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "NY pre 08-09:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-09-15 08:34 ET

> [!failure] -$440 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-09-15|2026-09-15]] · [[Week 2026-W38|2026-W38]]

## The trade

|  |  |
|---|---|
| Entry | 29405.5 |
| Stop | 29441.25 |
| Target | 29254.5 |
| Exit price | 29441.5 |
| Micros | 6 |
| Risk $ | $429 |
| Minutes in | 15 |
| Best (MFE) | +0.01R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY pre 08-09:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.712 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.2 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
