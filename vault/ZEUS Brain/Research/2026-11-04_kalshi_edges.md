---
tags:
  - zeus/research
  - family/kalshi
  - verdict/finding
  - bot/kalshi
type: "research"
date: "2026-11-04"
status: "finding - the Kalshi bot loses to the fee; suggestions only, the bot untouched"
source: "research/writeups/2026-11-04_kalshi_edges.md"
aliases:
  - "Kalshi Edge v2"
---

# Kalshi Edge v2

> [!info] Verdict: finding
> finding - the Kalshi bot loses to the fee; suggestions only, the bot untouched

**Full title:** Kalshi Edge v2: why it loses, and what (if anything) works

## Summary

2026-11-04. Research only. No Kalshi API call, no order, no secret, the bot untouched. Data: the public feed `kalshi.json` (1,836 settled buys with price/asset/strategy totals, 41 days of daily P&L, the last 40 trades). Numbers regenerate with `python tools/kalshi_research.py` (tables in `research/kalshi/edge_tables.json`, schema in the script's docstring). Everything below is **after Kalshi's fees**: the bot's own P&L already has the fee taken out (checked on the last 40 trades: fee = 0.07 x contracts x price x (1 - price), to the cent).

## Links

- Family: [[Family kalshi]]
- Day: [[Day 2026-11-04]]
- Strategies: [[Kalshi K8]]
- Source: `research/writeups/2026-11-04_kalshi_edges.md`
- Back to [[ZEUS Home]]
