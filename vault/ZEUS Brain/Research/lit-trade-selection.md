---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "promising"
source: "research/writeups/lit-trade-selection.md"
aliases:
  - "LIT trade selection"
---

# LIT trade selection

> [!tip] Verdict: promising
> promising

**Full title:** LIT trade selection - can we pick and size LIT setups like an experienced trader?

## Summary

Every LIT setup of 2026 was collected (330 setups on 167 days, 176 that would have filled if taken alone, against the 120 the bot takes) with 50 features known at the decision moment (look-ahead test passed). Person-like rules (an A/B/C grade, wait for a better setup, size by grade) and a small walk-forward model were scored on the real one-trade-a-day path at the eval size ($800 up to 25 pts, 60% room cap). The model has no skill out of sample (test AUC 0.23-0.52), and the data-mined grade only works on the half it was picked on. Two simple size tilts help both halves a little. (1) Fresh trap: 1.25x when the inducement swing is at most 6 bars (30 min) old, else 0.75x. H1 +$6.4k, H2 +$0.9k, max DD lower in both halves, 2-week eval pass H1 43.0% vs 37.5%. (2) The trader's A/B/C grade, A 1.5x / C 0.5x: H1 +$1.4k, H2 +$1.6k, 2-week pass H2 34.6% vs 29.5%. Each passes a shuffle test in one half only, and 2021-25 is worse for both, so neither is proven. Skipping setups ("wait") never pays: a later setup rarely comes. Win rate cannot be raised without dropping below 2 trades a week. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-losses|LIT losses]]
- Runs: `lit_sel_trap6_size, lit_sel_trap8_size, lit_sel_grade_size, lit_sel_grade_skipc, lit_sel_data_grade, lit_sel_model_size, lit_tight_eval_800_25_room60`
- Source: `research/writeups/lit-trade-selection.md`
- Back to [[ZEUS Home]]
