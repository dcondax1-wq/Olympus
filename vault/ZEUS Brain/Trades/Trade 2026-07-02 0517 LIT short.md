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
date: "2026-07-02"
time: "05:17"
week: "2026-W27"
side: "SHORT"
exit: "STOP"
r: -1.01
pnl: -135.4
result: "loss"
account: "zlarior"
member: "LIT"
cause: "turned"
session: "London late 05-08"
vix_band: "VIX 15-20"
news:
  - "Jobs report (NFP)"
span: "Jul-Oct 2026"
---

# LIT short · 2026-07-02 05:17 ET

> [!failure] -$135 · -1.01R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-07-02|2026-07-02]] · [[Week 2026-W27|2026-W27]]

## The trade

|  |  |
|---|---|
| Entry | 30266.5 |
| Stop | 30333.25 |
| Target | 30066.96 |
| Exit price | 30333.5 |
| Micros | 1 |
| Risk $ | $134 |
| Minutes in | 145 |
| Best (MFE) | +0.78R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson worked then turned|turned]]: It worked (+0.5R or more), then turned and lost.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | London late 05-08 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | with |
| ES 1h | against |
| Day's range before entry (ATR) | 0.564 |

## News that day

- [[News Jobs report (NFP)|Jobs report (NFP)]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -3.12 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
