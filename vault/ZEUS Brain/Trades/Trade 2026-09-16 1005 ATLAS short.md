---
tags:
  - zeus/trade
  - bot/atlas
  - src/backtest
  - result/loss
  - cause/never
type: "trade"
bot: "ATLAS"
src: "backtest"
date: "2026-09-16"
time: "10:05"
week: "2026-W38"
side: "SHORT"
exit: "T15"
r: -0.72
pnl: -357.0
result: "loss"
account: "atlas"
member: "S/R"
cause: "never"
session: "NY AM 09:30-11:30"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jul-Oct 2026"
---

# ATLAS short · 2026-09-16 10:05 ET

> [!failure] -$357 · -0.72R · T15 · backtest
> [[ATLAS]] · [[Day 2026-09-16|2026-09-16]] · [[Week 2026-W38|2026-W38]]

## The trade

|  |  |
|---|---|
| Entry | 29435.0 |
| Stop | 29484.5 |
| Target | 29336.0 |
| Exit price | 29469.75 |
| Micros | 5 |
| Risk $ | $495 |
| Minutes in | 15 |
| Best (MFE) | +0.34R |
| Worst (MAE) | -0.85R |

## Why it lost (reason codes)

- Main cause: [[Lesson never worked|never]]: It never worked: less than +0.5R in our favour before the stop.
- Checklist: clean (a careful human would have taken it too)

## Context

|  |  |
|---|---|
| Session | NY AM 09:30-11:30 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 0.703 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]]
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | yes |
| Move 60 min after the exit (R) | -0.77 |

## Links

- Strategy: [[ATLAS]]
- Member: [[ATLAS member S-R (sr_nyreclaim)|S/R]]
- Account: [[Account ATLAS]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
