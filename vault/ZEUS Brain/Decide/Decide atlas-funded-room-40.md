---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "atlas-funded-room-40"
status: "open"
added: "2026-11-19"
usd_month: -9
recommend: "yes"
---

# Decide: ATLAS's funded 25K: risk 40% of the room a trade instead of 60% (safer, but the first payout comes later)?

> [!question] OPEN · -$9 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-19 |
| $ a month | -$9 |
| Claude recommends | yes |
| Changes | ATLAS's funded sizing 60% -> 40% of the room (engine/account_b funded preset; Claude changes it only after your yes, Sim check first) |
| $ a month by market | jan-jun: +$24 · jul-oct: -$9 · 2021-25: -$3 |

## Why

The bot stops ATLAS for good once the funded room is under $100. Smaller trades make that rarer, but each win is smaller, so payouts come later.

## Impact

At real fills (10 ticks a side): +$24 a month in a Jan-Jun-like market ($503 -> $527), -$9 Jul-Oct-like ($402 -> $393), -$3 2021-25-like; first payout 3-8 trading days later (Dec 29 instead of Dec 23 Jan-Jun-like; Jan 19 instead of Jan 7 Jul-Oct-like). At backtest fills it was -$26 a month, 5 trading days later.

## Risk

At real fills the funded 25K is lost in 6 months 14.0% of the time instead of 21.7% (Jul-Oct-like), 11.0% instead of 17.6% (Jan-Jun-like); 2021-25-like 98% either way. Backtest fills: 10.2% -> 5.8%.

## Why Claude recommends that

At real fills (ATLAS's entries fill about 10 ticks late) 60% of the room is too big for $887: 40% loses the account about a third less often (1 in 7 instead of 1 in 5) for about the same money. It passed the pre-registered bar at 6 and 10 ticks; the cost is a first payout about 3-8 trading days later.

## Links

- Write-up: [[atlas-health-2026-11-18|ATLAS health]]
- Strategy: [[ATLAS]]
- Account: [[Account ATLAS]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
