---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/win
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-07-21"
time: "10:15"
week: "2026-W30"
side: "LONG"
exit: "TARGET"
r: 1.99
pnl: 783.3
result: "win"
account: "atlas"
member: "S/R"
flags:
  - "no_room"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# ATLAS long · 2026-07-21 10:15 ET

> [!success] +$783 · +1.99R · TARGET · backtest
> [[ATLAS]] · [[Day 2026-07-21|2026-07-21]] · [[Week 2026-W30|2026-W30]]

## The trade

|  |  |
|---|---|
| Entry | 29424.5 |
| Stop | 29358.75 |
| Target | 29556.0 |
| Exit price | 29556.0 |
| Micros | 3 |
| Risk $ | $394 |
| Minutes in | 55 |
| Best (MFE) | +2.00R |
| Worst (MAE) | -0.95R |

## Checklist flags (it still won)

- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.87 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | 0.73 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
