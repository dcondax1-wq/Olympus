---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "info"
source: "research/writeups/lit-report-coverage.md"
aliases:
  - "LIT report coverage"
---

# LIT report coverage

> [!note] Verdict: info
> info

**Full title:** LIT report coverage - is everything in the owner's LIT Complete Report in the bot or tested?

## Summary

The owner's LIT Complete Report was split into 436 items (definitions, rules, numbers, times, checklists, skip reasons, variants, execution and clock requirements, glossary, worked examples, chapter 26 audit facts). 260 are in the bot (50 of them partly), 67 were tested and rejected, 7 were tested as evidence or are neutral, 22 are missing, and 80 are context only. A second pass tested the 38 variants the first pass had not run (strength tiers, range premium/discount, time and news exits, stop buffers, equal-level tolerance, round numbers, mean threshold, DST London box, execution stress). None improves both 2026 halves, so LIT live stays as it is - 2026 +$41,734, PF 3.66, 2.91 trades a week; H2 +$8,962 (about $2,400 a month). The missing items are mostly undefined models in the report and live-data chores, the biggest being the contract roll in the live window.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-report-tests|LIT report tests]]
- Runs: `lit_live, lit_rep2_01_final_sweep_skip_unless_2_levels_swept, lit_rep2_02_final_sweep_half_size_with_1_level, lit_rep2_03_final_sweep_skip_unless_3_levels_swept, lit_rep2_04_tiers_skip_minor_only_sweeps_build_ups_only, lit_rep2_05_tiers_half_size_on_minor_only_sweeps, lit_rep2_06_tiers_half_size_unl`
- Source: `research/writeups/lit-report-coverage.md`
- Back to [[ZEUS Home]]
