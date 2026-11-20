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
date: "2026-09-18"
time: "07:05"
week: "2026-W38"
side: "LONG"
exit: "STOP"
r: -1.03
pnl: -452.41
result: "loss"
account: "atlas"
member: "EMA"
cause: "never"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-09-18 07:05 ET

> [!failure] -$452 · -1.03R · STOP · backtest
> [[ATLAS]] · [[Day 2026-09-18|2026-09-18]] · [[Week 2026-W38|2026-W38]] · reasons from the NQ 1m bars (data/NQ_1m.csv)

## The trade

|  |  |
|---|---|
| Entry | 29897.0 |
| Stop | 29860.5 |
| Target | 30012.85 |
| Exit price | 29860.25 |
| Micros | 6 |
| Risk $ | $438 |
| Minutes in | 5 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.51R |

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
