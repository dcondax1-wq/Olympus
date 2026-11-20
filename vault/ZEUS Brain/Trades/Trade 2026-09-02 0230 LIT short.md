---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/never
  - flag/no_room
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-09-02"
time: "02:30"
week: "2026-W36"
side: "SHORT"
exit: "CUT_T15"
r: -0.63
pnl: -103.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "no_room"
session: "London 02-05"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-09-02 02:30 ET

> [!failure] -$103 · -0.63R · CUT_T15 · backtest
> [[Zlarior (LIT)]] · [[Day 2026-09-02|2026-09-02]] · [[Week 2026-W36|2026-W36]]

## The trade

|  |  |
|---|---|
| Entry | 29317.5 |
| Stop | 29399.25 |
| Target | 29128.31 |
| Exit price | 29368.5 |
| Micros | 1 |
| Risk $ | $164 |
| Minutes in | 16 |
| Best (MFE) | +0.08R |
| Worst (MAE) | -0.92R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.371 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.04 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
