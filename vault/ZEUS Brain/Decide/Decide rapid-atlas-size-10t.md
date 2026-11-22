---
tags:
  - zeus/decide
  - decide/yes
type: "decide"
id: "rapid-atlas-size-10t"
status: "yes"
added: "2026-11-20"
usd_month: -31
recommend: "yes"
---

# Decide: Rapid 25K: size ATLAS for its real fills (assume a 10-tick worse stop)?

> [!success] YES · -$31 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | yes |
| Added | 2026-11-20 |
| $ a month | -$31 |
| Claude recommends | yes |
| Changes | engine/rapid.py: ATLAS's Rapid lane sizes on stop + 10 ticks; LIT unchanged (Claude applies the patch only after your yes, Sim check first) |
| $ a month by market | jan-jun: -$141 · jul-oct: -$31 · 2021-25: +$4 |

## Why

ATLAS's real fills are ~10 ticks worse than its backtest, so a full stop costs up to a third more than planned and can push the day past MFFU's $500 pause.

## Impact

-$31 a month in a Jul-Oct-like market (-$141 Jan-Jun-like, +$4 2021-25-like); fewer Rapids lost; same first payout date.

## Risk

Funded Rapid lost in 6 months 27.2% -> 24.0% (Jan-Jun-like), 38.0% -> 34.5% (Jul-Oct-like); days over MFFU's $500 pause 1.1 per 100 -> 0; eval pass unchanged.

## Why Claude recommends that

Safer for a small cost: about 3-4 fewer Rapids lost per 100 for $31-141 a month.

## Links

- Write-up: [[rapid-launch-2026-11-20|Rapid EOD 25K launch check]]
- Strategy: [[Zlarior (LIT)]]
- Strategy: [[ATLAS]]
- Strategy: [[Rapid lanes]]
- Account: [[Account ATLAS]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
