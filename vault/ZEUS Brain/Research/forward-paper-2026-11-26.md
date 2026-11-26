---
tags:
  - zeus/research
  - family/other
  - verdict/research
type: "research"
date: "2026-11-26"
source: "research/writeups/forward-paper-2026-11-26.md"
aliases:
  - "Forward-paper harness"
---

# Forward-paper harness

> [!abstract] Verdict: research
> (no status line)

**Full title:** Forward-paper harness (2026-11-26, big-forward)

## Summary

Ideas used to die in backtests or sit as "paper lead / watch" lines nobody re-checked. `tools/forward_paper.py` now scores each watched lead every night on sessions it has never seen, against its OWN backtest band. PAPER ONLY: it never trades, sizes, arms or edits a live file (live_model*.json hashed before / after). Rules + bars written first: `research/forward/DESIGN.md`.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-26]]
- Source: `research/writeups/forward-paper-2026-11-26.md`
- Back to [[ZEUS Home]]
