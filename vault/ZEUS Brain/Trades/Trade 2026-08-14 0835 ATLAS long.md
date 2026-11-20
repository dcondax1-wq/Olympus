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
date: "2026-08-14"
time: "08:35"
week: "2026-W33"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -391.22
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-08-14 08:35 ET

> [!failure] -$391 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-14|2026-08-14]] · [[Week 2026-W33|2026-W33]] · reasons from the NQ 1m bars (data/NQ_1m.csv)

## The trade

|  |  |
|---|---|
| Entry | 30567.0 |
| Stop | 30503.0 |
| Target | 30786.64 |
| Exit price | 30502.75 |
| Micros | 3 |
| Risk $ | $384 |
| Minutes in | 60 |
| Best (MFE) | +0.17R |
| Worst (MAE) | -1.04R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
