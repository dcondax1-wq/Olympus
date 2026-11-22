---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/win
  - flag/late
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-01-02"
time: "10:00"
week: "2026-W01"
side: "SHORT"
exit: "TARGET"
r: 1.99
pnl: 840.3
result: "win"
account: "atlas"
member: "S/R"
flags:
  - "late"
session: "NY AM 09:30-11:30"
vix_band: "VIX <15"
span: "Jan-Jun 2026"
---

# ATLAS short · 2026-01-02 10:00 ET

> [!success] +$840 · +1.99R · TARGET · backtest
> [[ATLAS]] · [[Day 2026-01-02|2026-01-02]] · [[Week 2026-W01|2026-W01]]

## The trade

|  |  |
|---|---|
| Entry | 26532.75 |
| Stop | 26603.25 |
| Target | 26391.75 |
| Exit price | 26391.75 |
| Micros | 3 |
| Risk $ | $423 |
| Minutes in | 20 |
| Best (MFE) | +2.00R |
| Worst (MAE) | -0.66R |

## Checklist flags (it still won)

- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | with |
| Day's range before entry (ATR) | 1.047 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 3.49 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
