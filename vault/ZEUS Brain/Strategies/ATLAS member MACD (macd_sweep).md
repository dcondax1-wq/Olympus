---
tags:
  - zeus/strategy
  - bot/atlas
  - atlas/member
  - market/nq
type: "strategy-member"
key: "macd_sweep"
on: "True"
route: "False"
---

# MACD divergence at a liquidity sweep

> [!success] On
> Key `macd_sweep` · routed to an account: no (paper)

## Rules in plain words

London (02:00-05:00 ET) and NY open (09:30-11:00): a LIT level is swept by 0.5 ATR, a 5m CISD closes back with MACD-line divergence; market entry, stop beyond the sweep extreme, VIX-band target, 15-minute check.

## Links

- Part of [[ATLAS]]
- Write-up: [[second-md|Second strategy next to LIT]]
