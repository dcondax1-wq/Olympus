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
date: "2026-07-28"
time: "05:15"
week: "2026-W31"
side: "SHORT"
exit: "STOP"
r: -1.05
pnl: -480.62
result: "loss"
account: "atlas"
member: "EMA"
cause: "wick"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-07-28 05:15 ET

> [!failure] -$481 · -1.05R · STOP · backtest
> [[ATLAS]] · [[Day 2026-07-28|2026-07-28]] · [[Week 2026-W31|2026-W31]] · reasons from the NQ 1m bars (data/NQ_1m.csv)

## The trade

|  |  |
|---|---|
| Entry | 28284.75 |
| Stop | 28310.25 |
| Target | 28170.0 |
| Exit price | 28310.5 |
| Micros | 9 |
| Risk $ | $459 |
| Minutes in | 15 |
| Best (MFE) | +0.19R |
| Worst (MAE) | -1.04R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: clean (a careful human would have taken it too)

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
