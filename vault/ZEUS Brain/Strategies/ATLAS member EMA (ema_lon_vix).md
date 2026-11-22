---
tags:
  - zeus/strategy
  - bot/atlas
  - atlas/member
  - market/nq
type: "strategy-member"
key: "ema_lon_vix"
on: "True"
route: "False"
---

# London EMA trend pullback

> [!success] On
> Key `ema_lon_vix` · routed to an account: no (paper)

## Rules in plain words

London hours (03:00-09:30 ET, no Mondays): 15m and 1h EMA 21 above the 50, a pullback to the 5m EMA 50 sweeps a swing low, a 5m CISD back up; stop beyond the sweep wick, VIX-band target, breakeven + costs at 1R.

## Links

- Part of [[ATLAS]]
- Write-up: [[second-ema|Second strategy next to LIT]]
