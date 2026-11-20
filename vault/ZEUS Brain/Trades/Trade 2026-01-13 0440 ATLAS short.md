---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/news
  - flag/against_htf
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-01-13"
time: "04:40"
week: "2026-W03"
side: "SHORT"
exit: "STOP"
r: -1.06
pnl: -488.4
result: "loss"
account: "atlas"
member: "MACD"
cause: "news"
flags:
  - "against_htf"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "CPI (consumer inflation)"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-13 04:40 ET

> [!failure] -$488 · -1.06R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-13|2026-01-13]] · [[Week 2026-W03|2026-W03]]

## The trade

|  |  |
|---|---|
| Entry | 26715.25 |
| Stop | 26736.25 |
| Target | 26547.25 |
| Exit price | 26736.5 |
| Micros | 11 |
| Risk $ | $462 |
| Minutes in | 231 |
| Best (MFE) | +2.17R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson news hit|news]]: A high-impact US release came out while the trade was open.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.403 |

## News that day

- [[News CPI (consumer inflation)|CPI (consumer inflation)]] (came out during the trade)

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.69 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
