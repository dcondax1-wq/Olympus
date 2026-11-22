---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-11-19"
status: "rejected - 0 of 9 pass; nothing changes in the bot; one live-audit fix proposed (not applied)"
source: "research/writeups/lit-more-money-2026-11-19.md"
aliases:
  - "Zlarior"
---

# Zlarior

> [!failure] Verdict: rejected
> rejected - 0 of 9 pass; nothing changes in the bot; one live-audit fix proposed (not applied)

**Full title:** Zlarior (LIT) more money - 9 pre-registered ideas in 2 batches (ES filler, breakeven, fills, bias, news, through-the-trade, ES vs NQ SMT) + why live missed trades

## Summary

Owner - "improve all of our strategies, there's things we can do to make more". After reading the tested-and-rejected list (about 2,000 LIT variants already), 9 genuinely new single versions were written down and committed before any run, in two batches (batch 2 = the owner's added scope - fills, bias, news, managing through the trade, ES vs NQ). Each was scored on the real live LIT trades, costs in, at the LIT size, on the live Builder 50K eval path (two_week, room 0.4 to session 80) and on the funded 50K, picked on Jan-Jun 2026 and checked on Jul-Oct, 2021-25 not worse, 2-4 trades a week, week-block bootstrap. None passes. The live bot's "missed" days are mostly not missed trades - one real miss (Oct 26, $0), one order refused for a wrong account name (Oct 27, fixed, it saved ~$965), one trade that WAS taken (Oct 28, the audit could not see it), one unknown (Nov 3); two more real misses on Nov 10-11 while the PC was silent. All of them lost money in the backtest.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-19]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `tools/lit_more_money.py run (research/lit/more_money.json, research/lab/lit_more_money.json); designs research/lit/more_money_design_batch1.md, research/lit/more_money_design_batch2.md; tools/live_gap_proposal.py + tests/test_live_gap_proposal.py`
- Source: `research/writeups/lit-more-money-2026-11-19.md`
- Back to [[ZEUS Home]]
