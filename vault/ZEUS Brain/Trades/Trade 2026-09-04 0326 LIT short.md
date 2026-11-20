---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-09-04"
time: "03:26"
week: "2026-W36"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -468.3
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London 02-05"
vix_band: "VIX <15"
news:
  - "Jobs report (NFP)"
span: "Jul-Oct 2026"
---

# LIT short · 2026-09-04 03:26 ET

> [!failure] -$468 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-09-04|2026-09-04]] · [[Week 2026-W36|2026-W36]]

## The trade

|  |  |
|---|---|
| Entry | 29906.25 |
| Stop | 29938.75 |
| Target | 29646.25 |
| Exit price | 29939.0 |
| Micros | 7 |
| Risk $ | $455 |
| Minutes in | 8 |
| Best (MFE) | +0.07R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX <15 |
| Daily trend | with |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.398 |

## News that day

- [[News Jobs report (NFP)|Jobs report (NFP)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | -0.45 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
