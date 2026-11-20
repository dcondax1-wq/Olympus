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
date: "2026-01-28"
time: "10:40"
week: "2026-W05"
side: "LONG"
exit: "STOP"
r: -1.04
pnl: -482.3
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-01-28 10:40 ET

> [!failure] -$482 · -1.04R · STOP · backtest
> [[ATLAS]] · [[Day 2026-01-28|2026-01-28]] · [[Week 2026-W05|2026-W05]]

## The trade

|  |  |
|---|---|
| Entry | 27022.5 |
| Stop | 26989.25 |
| Target | 27089.0 |
| Exit price | 26989.0 |
| Micros | 7 |
| Risk $ | $466 |
| Minutes in | 5 |
| Best (MFE) | +0.00R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.627 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -2.02 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
