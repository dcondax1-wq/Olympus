---
tags:
  - zeus/trade
  - bot/blitz
  - src/backtest
  - result/loss
  - cause/news
  - flag/late
  - flag/news_soon
  - flag/no_room
type: "trade"
bot: "BLITZ"
src: "backtest"
date: "2026-07-29"
time: "13:30"
week: "2026-W31"
side: "SHORT"
exit: "STOP"
r: -1.0
pnl: -172.43
result: "loss"
member: "BLITZ"
cause: "news"
flags:
  - "late"
  - "news_soon"
  - "no_room"
session: "NY PM 13:30-16"
vix_band: "VIX 15-20"
news:
  - "FOMC rate decision"
  - "FOMC press conference"
span: "Jul-Oct 2026"
---

# BLITZ short · 2026-07-29 13:30 ET

> [!failure] -$172 · -1.00R · STOP · backtest
> [[BLITZ (paper)]] · [[Day 2026-07-29|2026-07-29]] · [[Week 2026-W31|2026-W31]] (BLITZ research size $150 a trade)

## The trade

|  |  |
|---|---|
| Risk $ | $172 |
| Minutes in | 31 |
| Best (MFE) | +0.25R |
| Worst (MAE) | -1.00R |

## Why it lost (reason codes)

- Main cause: [[Lesson news hit|news]]: A high-impact US release came out while the trade was open.
- Checklist: [[Lesson late entry|late]]: Late: the day had already moved 1 daily ATR or more before the entry.
- Checklist: [[Lesson news soon|news_soon]]: A high-impact release within 30 minutes after the entry.
- Checklist: [[Lesson no room|no_room]]: The prior-day high / low sat less than 1R ahead on the target side.

## Context

|  |  |
|---|---|
| Session | NY PM 13:30-16 |
| VIX | VIX 15-20 |
| Daily trend | with |
| 1h trend | with |
| ES 1h | with |
| Day's range before entry (ATR) | 1.215 |

## News that day

- [[News FOMC rate decision|FOMC rate decision]] (came out during the trade)
- [[News FOMC press conference|FOMC press conference]]

## After the exit (hindsight, never used by a rule)

|  |  |
|---|---|
| Move 60 min after the exit (R) | -3.54 |

## Links

- Strategy: [[BLITZ (paper)]]
- [[ZEUS Trades]] · [[ZEUS Lessons]] · [[ZEUS Home]]
