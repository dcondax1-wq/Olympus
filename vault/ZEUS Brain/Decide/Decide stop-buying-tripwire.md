---
tags:
  - zeus/decide
  - decide/open
type: "decide"
id: "stop-buying-tripwire"
status: "open"
added: "2026-11-26"
usd_month: 31
recommend: "yes"
---

# Decide: Stop buying NEW evals when LIT's last 40 trades add up to less than 0R, and start again when a free Sim eval (the same bot on NinjaTrader Sim, Builder 50K rules) passes?

> [!question] OPEN · +$31 a month
> Answer it on the Decide card (Business app): YES / NO / LATER.

|  |  |
|---|---|
| Status | open |
| Added | 2026-11-26 |
| $ a month | +$31 |
| Claude recommends | yes |
| Changes | a buy gate (no live trading change): money_plan / payout autopilot 'buy next eval' line + a Sim101 shadow eval on the PC (lead builds; paper only) |
| $ a month by market | mix25: -$8 · turns-bad: +$31 · 2021-25: +$39 · y2026: -$37 |

## Why

A bad (2021-25-like) market eats eval fees: today's plan loses $667 a year there. This rule stops the buying while the strategy is cold; the accounts you already own keep trading.

## Impact

12 months, today's 4 accounts + re-buys: 2021-25-like -$667 -> -$202 (cash you may need $2,011 -> $1,357); market turns bad after 3 months +$377; 2026-like -$443 of $38,399 (-1%); 25%-of-2026 mix -$94 of $2,651. Today LIT's last 40 trades = +30R: nothing stops now.

## Risk

costs ~1% in a 2026-like market; it reacts slowly (40 trades = ~4 months), so in a sudden bad turn it saves less than the $300-drawdown rule would

## Why Claude recommends that

Pre-registered test: it cut the 2021-25-like loss 70% and helped when the market turns, for ~1% of the good-market money. Two simpler rules passed too (3 eval fails in a row; the business $300 under its peak) and are almost as good.

## Links

- Write-up: [[business-planner-2026-11-26|Business planner]]
- Strategy: [[Zlarior (LIT)]]
- [[ZEUS Decisions]] · [[ZEUS Home]]
