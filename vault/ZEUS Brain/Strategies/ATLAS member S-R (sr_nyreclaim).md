---
tags:
  - zeus/strategy
  - bot/atlas
  - atlas/member
  - market/nq
type: "strategy-member"
key: "sr_nyreclaim"
on: "True"
route: "False"
---

# NY sweep-and-reclaim of the day's levels (S/R)

> [!success] On
> Key `sr_nyreclaim` · routed to an account: no (paper)

## Rules in plain words

NY 09:30-12:00 ET: a level of the day (yesterday's RTH high/low, overnight, Asia / London box, last week, opening range) is swept after an inducement, a strong 5m close reclaims it; market entry, stop beyond the sweep extreme, 2R target, 15-minute check, 1 a day.

## Links

- Part of [[ATLAS]]
- Write-up: [[second-sr|A second strategy next to LIT]]
