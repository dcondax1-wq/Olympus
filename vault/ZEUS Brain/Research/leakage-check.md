---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/leakage-check.md"
aliases:
  - "Leakage check"
---

# Leakage check

> [!info] Verdict: finding
> finding

**Full title:** Leakage check: does the backtest peek at the future?

## Summary

No leak. Switching off the trade memory (memory_seed) and the exit learner (exit_learn) gives exactly the same 768 trades as the live strategy, so every result in this research is leak-free as it stands.

## Money first

- **No leakage.** All results in the trade-construction research use the live settings unchanged; the leak-free setting
  gives the same trades.
- **One thing to watch later:** once the PC's `memory.db` has 20+ paper trades for one exit signal with a good average,
  the PC bot could start using an extra exit that the cloud monitor (no database) and every backtest never use. If you
  want the PC, the cloud and the backtests to stay identical, set `memory_seed: false` in `live_model.json`. Today it
  changes nothing.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-17]]
- Runs: `baseline, leak_memseed_off, leak_exitlearn_off, leak_both_off`
- Source: `research/writeups/leakage-check.md`
- Back to [[ZEUS Home]]
