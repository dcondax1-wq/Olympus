---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/turned
  - flag/no_room
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-08-19"
time: "05:41"
week: "2026-W34"
side: "SHORT"
exit: "STOP"
r: -1.01
pnl: -149.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "turned"
flags:
  - "no_room"
session: "London late 05-08"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-08-19 05:41 ET

> [!failure] -$149 · -1.01R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-08-19|2026-08-19]] · [[Week 2026-W34|2026-W34]]

## The trade

|  |  |
|---|---|
| Entry | 29862.0 |
| Stop | 29935.75 |
| Target | 29563.29 |
| Exit price | 29936.0 |
| Micros | 1 |
| Risk $ | $148 |
| Minutes in | 177 |
| Best (MFE) | +0.82R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.382 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.17 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
