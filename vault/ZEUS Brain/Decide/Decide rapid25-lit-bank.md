---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "rapid25-lit-bank"
status: "open"
added: "2026-11-18"
usd_month: 164
recommend: "yes"
---

# Decide: Rapid 25K: Zlarior trades 1 micro and takes profit at the day's room (instead of skipping most trades)?

> [!question] OPEN · +$164 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-18 |
| $ a month | +$164 |
| Claude recommends | yes |
| Changes | python -X utf8 -m engine.rapid --lit-bank on (built OFF) |
| $ a month by market | jan-jun: +$363 · jul-oct: +$164 · 2021-25: +$4 |

## Why

MFFU closes a Rapid that goes 7 days without a trade, and the 30% best-day guard makes the Rapid 25K skip most trades: the red team's replay of Nov 6-19 traded it on 1 day in 10. With this lane on, the same days traded on 4. In the simulation 56% / 44% of evals (Jan-Jun / Jul-Oct-like) hit 5 trading days without a trade as built; 22% / 9% with it.

## Impact

With MFFU's 7-day inactivity close counted: +$164 a month in a Jul-Oct-like market (+$363 Jan-Jun-like, +$4 2021-25-like); the eval passes in 71% / 90% of runs instead of 41% / 54%; first payout about 3 weeks sooner (Feb 5-9 vs Feb 24-26).

## Risk

Trades more: without the inactivity close it fails the eval a bit more often (0.5% -> 3.1% Jan-Jun-like, 2.0% -> 2.7% Jul-Oct-like) and loses a funded Rapid a bit more often (27% -> 29%, 38% -> 39%). In Nov 6-19 its 3 extra trades (1 micro each) lost $288 in a cold week.

## Why Claude recommends that

Turn it on: as built the Rapid 25K hardly trades and risks MFFU's 7-day inactivity close; this lane passes much more often and sooner for slightly more eval risk. The pre-set test (which did not model the inactivity close) said no; with the close counted it wins in both 2026 halves.

## Links

- Write-up: [[rapid25-pass-2026-11-21|Rapid EOD 25K]]
- Strategy: [[Zlarior (LIT)]]
- Strategy: [[Rapid lanes]]
- Account: [[Account Zlarior]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
