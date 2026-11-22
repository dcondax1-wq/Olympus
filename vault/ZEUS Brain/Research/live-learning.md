---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-25"
status: "info"
source: "research/writeups/live-learning.md"
aliases:
  - "Live learning"
---

# Live learning

> [!note] Verdict: info
> info

**Full title:** Live learning - Zlarior and ATLAS learn from real trading like a disciplined trader (costs, trade reviews, suggestions)

## Summary

Owner order 2026-10-25, "the bots should learn, like a human trader without emotion". Built in three parts. (1) Execution learning from the real NinjaTrader fills - entry and stop slippage, latency, the commission really booked - with ONE automatic effect behind a switch (lit_sizing learn_costs, default OFF) that can only make sizing more conservative - every cap is re-priced at the slippage the bot really gets (p75 of the last 30 fills, 1 to 4 ticks; commission $1.90 to $4.00). Off = today's exact sizing (proved on 2,100 cases). On the MFFU 50K eval Monte Carlo it is neutral (2-week pass H1 51.5% = 51.5%, H2 52.2% = 52.2% at 2 ticks; fails 0% either way), so it is insurance, not a profit change. The stronger version that also shrinks every size in proportion ("scale") cost about 11% of the money on the 2026 journal (2026 +$48,705 -> +$43,536) for a smaller drawdown, so it is not recommended. (2) A trade review journal - every finished Zlarior, ATLAS and ATLAS v2 trade against its backtest twin on the same bars, with the loss cause, MFE / MAE and (PC) the rule checks - and a weekly live-vs-backtest summary pushed Sunday evening. (3) The learning loop's size knobs shown as "The bot suggests" cards with what they would have changed in $ and the one command that approves them. Nothing changes an entry, a stop or a target. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-25]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[hq-habits|HQ habits]], [[lit-learning-loop|LIT learning loop]]
- Runs: `lit_live, lit_learn_replay`
- Source: `research/writeups/live-learning.md`
- Back to [[ZEUS Home]]
