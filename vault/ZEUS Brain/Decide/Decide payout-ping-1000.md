---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "payout-ping-1000"
status: "open"
added: "2026-11-17"
usd_month: -9
recommend: "no"
---

# Decide: Funded 25K: ask for the full $1,000 payout (at balance $27,100) instead of pinging you at $750?

> [!question] OPEN · -$9 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-17 |
| $ a month | -$9 |
| Claude recommends | no |
| Changes | engine/funded_life builder25k ask_above 750 -> 1000 (push line only) |
| $ a month by market | jan-jun: -$11 · jul-oct: -$9 · 2021-25: -$6 |

## Why

The bot pings you when $750 sits above the $1,100 buffer; waiting for the full $1,000 (balance $27,100) means fewer, bigger requests.

## Impact

-$9 a month in a Jul-Oct-like market (-$11 Jan-Jun-like, -$6 2021-25-like); first payout about 2 trading days later. At real fills on ATLAS's 25K (10 ticks a side): about the same money (+$8 a month Jan-Jun-like, -$1 Jul-Oct-like), lost in 6 months 21.7% -> 20.7% (17.6% -> 16.0%), first payout 2-3 trading days later; with room 40% it adds almost nothing (14.0% -> 13.1%).

## Risk

25K #2 no payout in 6 months 16.9% -> 18.5%; in a 2021-25-like market it costs $6 a month

## Why Claude recommends that

Keep the $750 ping: waiting for $1,000 pays the same or a little less and each payout comes 2-5 trading days later. At real fills it is a little safer on ATLAS's 25K, but room 40% does that job much better; on the 25K #2 it still costs about $5 a month.

## Links

- Write-up: [[payout-policy-funded25-2026-11-17|Funded Builder 25K payout policy]]
- Strategy: [[ATLAS]]
- Account: [[Account ATLAS]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
