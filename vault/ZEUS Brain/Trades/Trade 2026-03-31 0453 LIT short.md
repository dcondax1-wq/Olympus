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
date: "2026-03-31"
time: "04:53"
week: "2026-W14"
side: "SHORT"
exit: "CUT_T15"
r: -0.34
pnl: -54.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London 02-05"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# LIT short · 2026-03-31 04:53 ET

> [!failure] -$54 · -0.34R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-03-31|2026-03-31]] · [[Week 2026-W14|2026-W14]]

## The trade

|  |  |
|---|---|
| Entry | 23893.75 |
| Stop | 23974.5 |
| Target | 23495.25 |
| Exit price | 23920.25 |
| Micros | 1 |
| Risk $ | $162 |
| Minutes in | 16 |
| Best (MFE) | +0.20R |
| Worst (MAE) | -0.52R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 25+ |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.83 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.14 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
