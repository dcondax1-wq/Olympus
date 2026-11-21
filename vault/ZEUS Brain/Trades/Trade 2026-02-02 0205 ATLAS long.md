---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/win
  - flag/against_htf
  - flag/late
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-02-02"
time: "02:05"
week: "2026-W06"
side: "LONG"
exit: "TARGET"
r: 7.99
pnl: 3150.3
result: "win"
account: "atlas"
member: "MACD"
flags:
  - "against_htf"
  - "late"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-02-02 02:05 ET

> [!success] +$3,150 · +7.99R · TARGET · backtest
> [[ATLAS]] · [[Day 2026-02-02|2026-02-02]] · [[Week 2026-W06|2026-W06]]

## The trade

|  |  |
|---|---|
| Entry | 26045.0 |
| Stop | 25979.25 |
| Target | 26571.0 |
| Exit price | 26571.0 |
| Micros | 3 |
| Risk $ | $394 |
| Minutes in | 466 |
| Best (MFE) | +8.00R |
| Worst (MAE) | -0.14R |

## Checklist flags (it still won)

- [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 1.117 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 1.34 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member MACD (macd_sweep)|MACD]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
