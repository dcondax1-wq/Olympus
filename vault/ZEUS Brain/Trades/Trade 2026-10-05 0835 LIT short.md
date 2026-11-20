---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/never
  - flag/against_htf
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-10-05"
time: "08:35"
week: "2026-W41"
side: "SHORT"
exit: "STOP"
r: -1.01
pnl: -164.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
flags:
  - "against_htf"
session: "NY pre 08-09:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-10-05 08:35 ET

> [!failure] -$164 · -1.01R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-10-05|2026-10-05]] · [[Week 2026-W41|2026-W41]]

## The trade

|  |  |
|---|---|
| Entry | 30989.25 |
| Stop | 31070.5 |
| Target | 30759.45 |
| Exit price | 31070.75 |
| Micros | 1 |
| Risk $ | $162 |
| Minutes in | 57 |
| Best (MFE) | +0.30R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.

## Context

|  |  |
|---|---|
| Session | NY pre 08-09:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.55 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -1.73 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
