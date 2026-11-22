---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "promising"
source: "research/writeups/lit-experiments.md"
aliases:
  - "LIT experiments"
---

# LIT experiments

> [!tip] Verdict: promising
> promising

**Full title:** LIT experiments - sizing like a prop trader, a New York session, other targets, other stops, and the masters' ideas

## Summary

About 150 variants of LIT final were tested on 2026 CME NQ1! futures (5m + 1m bars). Each was picked on Jan-Jun and checked on Jul-Oct, with 2021-25 as a reference. None of the strategy changes beat LIT final in both halves. That covers a New York second session, 15 target ideas, 5 stop anchors with 4 buffers, breakeven on structure, partials at liquidity, re-entries, minimum 3R and a two-stage entry. The only real gains come from sizing for the MFFU 50K eval. (1) Fast-eval size: $800 risk up to a 40-pt stop instead of 20. It passes about half of all evals within 2 weeks in both halves (H1 52% vs 33%, H2 47% vs 23%) and halves the expected time to a pass, but about 1 eval in 4 fails within 2 weeks. (2) A max-loss room cap: never risk more than 60% of the distance to the trailing max-loss floor. It cuts 2-week failures from 15% to 4% in H1 and leaves H2 unchanged. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_final, lit_x_fast_eval, lit_x_room_cap60, lit_x_risk600, lit_x_flat800, lit_x_ict_halving, lit_x_cushion, lit_x_ny_plain, lit_x_tgt_vix_gap, lit_x_stop_tap, lit_x_be_struct, lit_x_reentry, lit_x_partial_swing25`
- Source: `research/writeups/lit-experiments.md`
- Back to [[ZEUS Home]]
