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
date: "2026-08-31"
time: "10:15"
week: "2026-W36"
side: "LONG"
exit: "STOP"
r: -1.05
pnl: -479.0
result: "loss"
account: "atlas"
member: "S/R"
cause: "turned"
flags:
  - "against_htf"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-08-31 10:15 ET

> [!failure] -$479 · -1.05R · STOP · backtest
> [[ATLAS]] · [[Day 2026-08-31|2026-08-31]] · [[Week 2026-W36|2026-W36]]

## The trade

|  |  |
|---|---|
| Entry | 29688.25 |
| Stop | 29665.5 |
| Target | 29733.75 |
| Exit price | 29665.25 |
| Micros | 10 |
| Risk $ | $455 |
| Minutes in | 10 |
| Best (MFE) | +1.67R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX <15 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.691 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 2.92 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
