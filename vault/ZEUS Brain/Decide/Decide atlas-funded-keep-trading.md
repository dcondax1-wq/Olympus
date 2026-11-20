---
tags:
  - zeus/decide
  - decide/yes
type: "decide"
id: "atlas-funded-keep-trading"
status: "yes"
added: "2026-11-19"
usd_month: 6
recommend: "yes"
---

# Decide: ATLAS's funded 25K: keep trading 1 micro when the room drops under $100, instead of stopping for good?

> [!success] YES · +$6 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | yes |
| Added | 2026-11-19 |
| $ a month | +$6 |
| Claude recommends | yes |
| Changes | data/account_b.json "min_room": 0 (built key: the funded stuck line $100 -> none; Claude changes it only after your yes) |
| $ a month by market | jan-jun: +$14 · jul-oct: +$6 · 2021-25: +$1 |

## Why

Today the bot gives the funded account up at $100 of room. Small 1-micro trades that still fit can climb back: about 1 in 5 such accounts recover in a 2026-like market.

## Impact

+$3 a month in a Jul-Oct-like market (+$10 Jan-Jun-like, +$4 2021-25-like); chance of losing the account in 6 months 10.5% -> 9.5% (9.8% -> 7.7% Jan-Jun-like); first payout unchanged. At real fills (10 ticks a side): +$6 a month Jul-Oct-like (+$14 Jan-Jun-like, +$1 2021-25-like); chance of losing the account 23.5% -> 21.7% (20.3% -> 17.6% Jan-Jun-like); first payout unchanged.

## Risk

None found: a 1-micro trade only goes on when its full stop-out fits the room; a stranded account still holds one of the 2 funded 25K places until you close it

## Why Claude recommends that

It only keeps alive an account the bot would abandon: at real fills it never loses an account the old $100 stop would keep (0 of 1,000 test paths) and saves about 2-3 in 100. Small money, no downside.

## Links

- Write-up: [[atlas-more-money-2026-11-19|ATLAS more money]]
- Strategy: [[ATLAS]]
- Account: [[Account ATLAS]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
