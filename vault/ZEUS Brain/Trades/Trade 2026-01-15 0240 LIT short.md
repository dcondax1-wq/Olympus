---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-01-15"
time: "02:40"
week: "2026-W03"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -245.6
result: "loss"
account: "zlarior"
member: "LIT"
cause: "turned"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# LIT short · 2026-01-15 02:40 ET

> [!failure] -$246 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-01-15|2026-01-15]] · [[Week 2026-W03|2026-W03]]

## The trade

|  |  |
|---|---|
| Entry | 26492.75 |
| Stop | 26522.5 |
| Target | 26254.75 |
| Exit price | 26522.75 |
| Micros | 4 |
| Risk $ | $238 |
| Minutes in | 31 |
| Best (MFE) | +0.66R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.549 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.68 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
