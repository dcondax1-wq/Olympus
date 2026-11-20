---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/turned
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-10-08"
time: "08:45"
week: "2026-W41"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -419.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "turned"
session: "NY pre 08-09:30"
vix_band: "VIX 15-20"
span: "Jul-Oct 2026"
---

# LIT short · 2026-10-08 08:45 ET

> [!failure] -$419 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-10-08|2026-10-08]] · [[Week 2026-W41|2026-W41]]

## The trade

|  |  |
|---|---|
| Entry | 31185.75 |
| Stop | 31219.75 |
| Target | 31104.69 |
| Exit price | 31220.0 |
| Micros | 6 |
| Risk $ | $408 |
| Minutes in | 20 |
| Best (MFE) | +0.52R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY pre 08-09:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.748 |

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.27 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
