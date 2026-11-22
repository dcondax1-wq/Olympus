---
tags:
  - zeus/trade
  - bot/lit
  - src/backtest
  - result/loss
  - cause/news
  - flag/against_htf
  - flag/news_soon
type: "trade"
bot: "LIT"
src: "backtest"
date: "2026-05-08"
time: "08:23"
week: "2026-W19"
side: "SHORT"
exit: "STOP"
r: -1.03
pnl: -482.3
result: "loss"
account: "zlarior"
member: "LIT"
cause: "news"
flags:
  - "against_htf"
  - "news_soon"
session: "NY pre 08-09:30"
vix_band: "VIX 15-20"
news:
  - "Jobs report (NFP)"
span: "Jan-Jun 2026"
---

# LIT short · 2026-05-08 08:23 ET

> [!failure] -$482 · -1.03R · STOP · backtest
> [[Zlarior (LIT)]] · [[Day 2026-05-08|2026-05-08]] · [[Week 2026-W19|2026-W19]]

## The trade

|  |  |
|---|---|
| Entry | 29465.75 |
| Stop | 29499.25 |
| Target | 29276.5 |
| Exit price | 29499.5 |
| Micros | 7 |
| Risk $ | $469 |
| Minutes in | 8 |
| Best (MFE) | +0.14R |
| Worst (MAE) | -1.01R |

## Why it lost (reason codes)

- Main cause: [[Lesson news hit|news]]: A high-impact US release came out while the trade was open.
- Checklist: [[Lesson against both trends|against_htf]]: Taken against the daily AND the 1h trend.
- Checklist: [[Lesson news soon|news_soon]]: A high-impact release within 30 minutes after the entry.

## Context

|  |  |
|---|---|
| Session | NY pre 08-09:30 |
| VIX | VIX 15-20 |
| Daily trend | against |
| 1h trend | against |
| ES 1h | against |
| Day's range before entry (ATR) | 0.897 |

## News that day

- [[News Jobs report (NFP)|Jobs report (NFP)]] (came out during the trade)

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Target reached later that session | no |
| Move 60 min after the exit (R) | 0.75 |

## Links

- Strategy: [[Zlarior (LIT)]]
- Account: [[Account Zlarior]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
