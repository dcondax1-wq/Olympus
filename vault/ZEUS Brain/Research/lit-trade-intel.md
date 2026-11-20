---
tags:
  - zeus/research
  - family/other
  - verdict/research
  - bot/zlarior
type: "research"
date: "2026-10-21"
status: "descriptive (no rule change)"
source: "research/writeups/lit-trade-intel.md"
aliases:
  - "LIT trade intelligence"
---

# LIT trade intelligence

> [!abstract] Verdict: research
> descriptive (no rule change)

**Full title:** LIT trade intelligence - every trade with ~60 facts, and what winners and losers have in common

## Summary

Every LIT trade (630 backtest trades of the live settings, run lit_live, plus the cloud paper and PC live trades as they come) now carries ~60 facts - 57 known at entry (time, session, ICT macro, swept level type / age / touches, sweep depth, wick, inducements, displacement, CISD wait, stop, R:R, target, VIX / VXN, gamma, ATR regime, Asia / London range, gap, prior day / week, Monday rule, weekly stop, news, size) and 11 outcomes (exit, R, $, MFE / MAE, minutes, time to +1R, heat before breakeven). Each entry fact is split in terciles set on 2026 H1 and checked on H2. 8 of 50 facts point the same way in both halves by 0.1R or more, but shuffled outcomes give 13.4 on average, so as a group the signs are no stronger than chance. The clearest ones are lower VXN, a closer target, a quiet day so far, ES sweeping its own level too, and more than 2.6R of room to the nearest opposing level. Only the last one also leans the same way in 2021-25. Most of these were already tested as rules and none passed. Nothing changes in live_model.json.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-21]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-batch3a|LIT batch 3a]], [[lit-batch3b|LIT batch 3b]], [[lit-bias-discretion|LIT with bias and discretion]], [[lit-market-context|LIT market context]], [[lit-new-entries|LIT new entries and confluences]], [[lit-trade-selection|LIT trade selection]]
- Runs: `lit_live`
- Source: `research/writeups/lit-trade-intel.md`
- Back to [[ZEUS Home]]
