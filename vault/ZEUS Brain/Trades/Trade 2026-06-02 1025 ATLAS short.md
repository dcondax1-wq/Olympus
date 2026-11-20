---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/turned
  - flag/against_htf
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-06-02"
time: "10:25"
week: "2026-W23"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -424.2
result: "loss"
account: "atlas"
member: "S/R"
cause: "turned"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-06-02 10:25 ET

> [!failure] -$424 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-06-02|2026-06-02]] · [[Week 2026-W23|2026-W23]]

## The trade

|  |  |
|---|---|
| Entry | 31162.0 |
| Stop | 31231.5 |
| Target | 31023.0 |
| Exit price | 31231.75 |
| Micros | 3 |
| Risk $ | $417 |
| Minutes in | 40 |
| Best (MFE) | +0.58R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.696 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.41 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
