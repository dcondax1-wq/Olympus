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
date: "2026-09-16"
time: "04:05"
week: "2026-W38"
side: "SHORT"
exit: "STOP"
r: -1.02
pnl: -105.9
result: "loss"
account: "zlarior"
member: "LIT"
cause: "never"
session: "London 02-05"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jul-Oct 2026"
---

# LIT short · 2026-09-16 04:05 ET

> [!failure] -$106 · -1.02R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-09-16|2026-09-16]] · [[Week 2026-W38|2026-W38]]

## The trade

|  |  |
|---|---|
| Entry | 29346.25 |
| Stop | 29398.25 |
| Target | 29119.25 |
| Exit price | 29398.5 |
| Micros | 1 |
| Risk $ | $104 |
| Minutes in | 175 |
| Best (MFE) | +0.39R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London 02-05 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.468 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.36 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
