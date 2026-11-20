---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-06-02"
time: "07:35"
week: "2026-W23"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -394.2
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-06-02 07:35 ET

> [!failure] -$394 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-06-02|2026-06-02]] · [[Week 2026-W23|2026-W23]]

## The trade

|  |  |
|---|---|
| Entry | 31150.75 |
| Stop | 31086.25 |
| Target | 31443.48 |
| Exit price | 31086.0 |
| Micros | 3 |
| Risk $ | $387 |
| Minutes in | 95 |
| Best (MFE) | +0.04R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.567 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 1.7 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
