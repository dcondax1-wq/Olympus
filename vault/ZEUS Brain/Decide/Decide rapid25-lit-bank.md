---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "rapid25-lit-bank"
status: "open"
added: "2026-11-18"
usd_month: 101
recommend: "no"
---

# Decide: Rapid 25K: Zlarior trades 1 micro and takes profit at the day's room (instead of skipping most trades)?

> [!question] OPEN · +$101 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-18 |
| $ a month | +$101 |
| Claude recommends | no |
| Changes | python -X utf8 -m engine.rapid --lit-bank on (built OFF) |
| $ a month by market | jan-jun: +$24 · jul-oct: +$101 · 2021-25: +$1 |

## Why

Today the 30% best-day guard skips 60-65% of Zlarior's trades there. Banking at the room passes and pays sooner, but fails a little more.

## Impact

At real fills (ATLAS 10 ticks a side): +$101 a month in a Jul-Oct-like market (+$24 Jan-Jun-like, +$1 2021-25-like); first payout about 6-9 days sooner. At backtest fills it was +$83.

## Risk

At real fills: Rapid 25K eval fails within 60 trading days 0.5% -> 3.1% (Jan-Jun-like) and 2.0% -> 2.7% (Jul-Oct-like); funded Rapid lost in 6 months 27.2% -> 28.7% / 38.0% -> 39.1%; eval passes in about 21-30 trading days instead of 26-33.

## Why Claude recommends that

Not yet: the money is real (+$101 a month Jul-Oct-like) but at real fills the eval fails 6x as often in a Jan-Jun-like market (0.5% -> 3.1%), over the 1-point limit set before the test. A yes is fine if you prefer a faster pass; it stays built OFF.

## Links

- Write-up: [[rapid-launch-2026-11-20|Rapid EOD 25K launch check]]
- Strategy: [[Zlarior (LIT)]]
- Strategy: [[ATLAS]]
- Strategy: [[Rapid lanes]]
- Account: [[Account Zlarior]]
- Account: [[Account ATLAS]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
