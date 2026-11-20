---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/win
  - flag/late
  - flag/no_room
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-04-30"
time: "07:05"
week: "2026-W18"
side: "LONG"
exit: "TARGET"
r: 3.28
pnl: 1418.51
result: "win"
account: "atlas"
member: "EMA"
flags:
  - "late"
  - "no_room"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jan-Jun 2026"
---

# ATLAS long · 2026-04-30 07:05 ET

> [!success] +$1,419 · +3.28R · TARGET · backtest
> [[ATLAS]] · [[Day 2026-04-30|2026-04-30]] · [[Week 2026-W18|2026-W18]]

## The trade

|  |  |
|---|---|
| Entry | 27977.5 |
| Stop | 27934.25 |
| Target | 28120.3 |
| Exit price | 28120.3 |
| Micros | 5 |
| Risk $ | $432 |
| Minutes in | 85 |
| Best (MFE) | +3.30R |
| Worst (MAE) | -0.28R |

## Checklist flags (it still won)

- [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 1.085 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -1.02 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member EMA (ema_lon_vix)|EMA]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
