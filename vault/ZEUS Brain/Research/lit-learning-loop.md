---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "info"
source: "research/writeups/lit-learning-loop.md"
aliases:
  - "LIT learning loop"
---

# LIT learning loop

> [!note] Verdict: info
> info

**Full title:** LIT learning loop - how the bot learns from its losses, what it may change, and what it would have learned in 2026

## Summary

Every finished LIT trade now goes into a journal (data/lit_journal.jsonl) with its 50 entry facts, the outcome, MFE/MAE and a loss cause code. Every Sunday a review re-estimates a small set of bounded size knobs (0.5x to 1.25x per bucket, a skip only for a bucket that lost money over 15+ trades) with shrinkage toward 1.0x. Each proposed change has to pass six guardrails before it can go live, and every decision is logged and can be reverted. Replayed on 2026 with only the data before each Sunday, the learner made 3 changes, all on the inducement (trap) age, by late April: stale traps 0.5x, fresh traps 1.25x. That is the same thing the trade-selection study found by hand. It made 0 changes on 2021-25. The money was not better in both halves. H1 eval path +$3.6k but funded -$1.1k; H2 -$0.4k, and 2-week passes fell from 29.5% to 23.1%. So the loop ships in OBSERVE mode. It journals, learns and logs what it would do, and leaves the size alone. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-losses|LIT losses]], [[lit-trade-selection|LIT trade selection]]
- Runs: `lit_learn_replay, lit_tight_eval_800_25_room60, lit_sel_trap6_size`
- Source: `research/writeups/lit-learning-loop.md`
- Back to [[ZEUS Home]]
