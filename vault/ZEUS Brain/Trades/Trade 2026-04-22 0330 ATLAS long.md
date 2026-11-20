---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/wick
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-22"
time: "03:30"
week: "2026-W17"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -496.98
result: "loss"
account: "atlas"
member: "EMA"
cause: "wick"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-22 03:30 ET

> [!failure] -$497 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-04-22|2026-04-22]] · [[Week 2026-W17|2026-W17]]

## The trade

|  |  |
|---|---|
| Entry | 27434.25 |
| Stop | 27385.75 |
| Target | 27649.01 |
| Exit price | 27385.5 |
| Micros | 5 |
| Risk $ | $485 |
| Minutes in | 65 |
| Best (MFE) | +0.29R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.295 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.03 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
