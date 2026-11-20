---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/wick
  - flag/late
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-01-20"
time: "10:50"
week: "2026-W04"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -404.7
result: "loss"
account: "atlas"
member: "S/R"
cause: "wick"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-20 10:50 ET

> [!failure] -$405 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-20|2026-01-20]] · [[Week 2026-W04|2026-W04]]

## The trade

|  |  |
|---|---|
| Entry | 26150.25 |
| Stop | 26216.5 |
| Target | 26017.75 |
| Exit price | 26216.75 |
| Micros | 3 |
| Risk $ | $398 |
| Minutes in | 25 |
| Best (MFE) | +0.57R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson shaken out|wick]]: Shaken out: stopped, then price went on to our target.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.012 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.85 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
