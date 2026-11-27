---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "oflane-sim"
status: "open"
added: "2026-11-27"
usd_month: 0
recommend: "yes"
---

# Decide: Order flow on the practice account (Sim, no real money): yes = text /oflane on in Telegram

> [!question] OPEN · $0 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-27 |
| $ a month | $0 |
| Claude recommends | yes |
| Changes | YES = text /oflane on (or on the PC: python -X utf8 -m engine.of_lane --sim on). It starts by itself at 09:20 ET on weekdays on Sim102, or on Sim101 when Sim102 does not exist and nothing else uses Sim101 (the reply says which). /oflane off stops new trades. Real / MFFU accounts are refused in three places and never touched. |

## Why

The order-flow bot fades a sweep of yesterday's / overnight / opening-range high or low only when the sweep bar was absorbed. On 43 real trading days (Sep 28 - Nov 25, Monday prior-day fix in), the first trade of each day: 39 trades, 4.5 a week, 51% won, +0.51R a trade, PF 2.40, +$2,931 at 1 micro (about $1,450 a month), worst drawdown $542. Honest catch: the older half was much better than the newer half (+0.91R vs +0.10R a trade), later trades in the same day lose (-$561 to -$834 at 1 micro), it is one 2-month market, and 0 forward days have been scored. 8 more order-flow idea families were tested overnight: no new edge.

## Impact

$0: practice money only. It shows whether the real order path (limit at the level, stop, 2R target, 15:55 close) gets the fills the paper bot assumes. Those Sim fills are what the next step (one small eval test) waits for.

## Risk

No real money (simulation account). It can never trade an eval or funded account: that needs the forward gate plus your separate yes and the live phrase.

## Why Claude recommends that

It costs nothing, the stop rules and kill switch apply, and the forward ladder needs real-order-path fills before any eval is even asked.

## Links

- [[ZEUS Decisions]] · [[ZEUS Home]]
