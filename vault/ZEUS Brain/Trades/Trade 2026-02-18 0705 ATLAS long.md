---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-02-18"
time: "07:05"
week: "2026-W08"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -509.4
result: "loss"
account: "atlas"
member: "EMA"
cause: "turned"
session: "London late 05-08"
vix_band: "VIX 20-25"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-02-18 07:05 ET

> [!failure] -$509 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-02-18|2026-02-18]] · [[Week 2026-W08|2026-W08]]

## The trade

|  |  |
|---|---|
| Entry | 25730.25 |
| Stop | 25689.0 |
| Target | 25899.86 |
| Exit price | 25688.75 |
| Micros | 6 |
| Risk $ | $495 |
| Minutes in | 30 |
| Best (MFE) | +0.76R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 20-25 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.411 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.08 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
