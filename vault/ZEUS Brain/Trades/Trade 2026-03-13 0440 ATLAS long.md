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
date: "2026-03-13"
time: "04:40"
week: "2026-W11"
side: "LONG"
exit: "STOP"
r: -1.02
pnl: -461.7
result: "loss"
account: "atlas"
member: "MACD"
cause: "turned"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 25+"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-03-13 04:40 ET

> [!failure] -$462 · -1.02R · STOP · backtest
> [[ATLAS]] · [[Day 2026-03-13|2026-03-13]] · [[Week 2026-W11|2026-W11]]

## The trade

|  |  |
|---|---|
| Entry | 25271.75 |
| Stop | 25196.0 |
| Target | 25802.32 |
| Exit price | 25195.75 |
| Micros | 3 |
| Risk $ | $454 |
| Minutes in | 427 |
| Best (MFE) | +4.39R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 25+ |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.501 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.14 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
