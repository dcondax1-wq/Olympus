---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-report-tests.md"
aliases:
  - "LIT report tests"
---

# LIT report tests

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT report tests - every codable rule of the owner's LIT Complete Report, tested on 2026

## Summary

The owner's LIT Complete Report (29 chapters) was read end to end and every rule a computer can follow was listed against what LIT live already does. Most of them were already in LIT or had been tested before. The 16 rule ideas that were new became 44 variants, tested on 2026 CME NQ futures (5m + 1m), each picked on Jan-Jun and checked on Jul-Oct. None improves both halves in a way that holds up. The closest, skipping a setup when another level sits within 0.5R of the entry, adds $1,313 in H1 and $10 in H2, but at 0.4R or 0.6R it loses money in H2, so it is noise. The report's own example model (chapter 21) made no trade at all in 2026. LIT live stays as it is (2026 +$41,734, PF 3.66; H2 +$8,962). Chapters 27-28 led to four execution fixes - cancel-pending entries, partial exit fills, CME early closes and a frozen paper ledger - all with tests. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-experiments|LIT experiments]], [[lit-final|LIT final]], [[lit-losses|LIT losses]], [[lit-playbook|LIT playbook]]
- Runs: `lit_live, lit_rep_first_obstacle_skip_when_a_level_sits_within_0_5r, lit_rep_first_obstacle_skip_when_a_level_sits_within_0_75r, lit_rep_reclaim_trigger_closes_back_beyond_the_swept_le, lit_rep_continuation_2nd_trade_same_side_after_a_non_st, lit_rep_failed_reversal_2nd_trade_opposite_side_after_a, `
- Source: `research/writeups/lit-report-tests.md`
- Back to [[ZEUS Home]]
