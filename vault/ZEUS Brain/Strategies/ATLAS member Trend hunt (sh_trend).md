---
tags:
  - zeus/strategy
  - bot/atlas
  - atlas/member
  - market/nq
type: "strategy-member"
key: "sh_trend"
on: "True"
route: "False"
---

# Trend inducement hunt

> [!success] On
> Key `sh_trend` · routed to an account: no (paper) · candidate (paper only)

## Rules in plain words

Any hour 18:00-15:30 ET: a pullback against the 1h trend takes an inducement swing and runs a 5m swing by 0.25 ATR, then a 5m candle >= 1.2 ATR back with the trend closes through the pool and the last swing; limit at mid-candle for 30 min, stop 1 tick beyond the hunt extreme, 2R, BE + 1.25 at 1R, flat 15:55, 2 a session.

## Links

- Part of [[ATLAS]]
- Write-up: [[stophunt|STOP-HUNT family]]
