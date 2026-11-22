---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "fast-entry"
status: "open"
added: "2026-11-20"
usd_month: 100
recommend: "yes"
---

# Decide: Fast entry: send Zlarior's and ATLAS's orders on the minute's first trade instead of waiting 2 seconds?

> [!question] OPEN · +$100 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-20 |
| $ a month | +$100 |
| Claude recommends | yes |
| Changes | On the PC, once: python -X utf8 -m engine.fast_entry --on (off again: --off). No code change; the bot picks it up within 30 s. |
| $ a month by market | jump-low: $0 · linear-high: +$161 · sqrt-central: +$103 |

## Why

Every real entry so far filled worse than the backtest (ATLAS 10-16 ticks, Zlarior 4) because price runs in the 2.7 s before the order arrives; 2.0 s of that is a built-in wait. Fast entry cuts it to ~0.85 s. Same trades, same sizes, only sooner.

## Impact

$0 to ~$160 a month (central ~$100: ATLAS ~5 ticks and Zlarior ~1 tick better per entry); not provable from 1-minute bars, so it is a 2-week test that the fills will settle.

## Risk

No trade decision changes (replay: same ledger ON vs OFF). A minute that spikes and snaps back can make an early fill a few $ worse; expected cost if it does not help: ~$0, a few $ a trade either way.

## Why Claude recommends that

Free to try and undo; the only way to measure it. Check ATLAS's next ~8 fills: if they are not clearly better than 10-16 ticks, switch it off.

## Links

- Write-up: [[nq-speed-fills-2026-11-20|NQ bot speed and fills]]
- Strategy: [[Zlarior (LIT)]]
- Strategy: [[ATLAS]]
- Account: [[Account Zlarior]]
- Account: [[Account ATLAS]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
