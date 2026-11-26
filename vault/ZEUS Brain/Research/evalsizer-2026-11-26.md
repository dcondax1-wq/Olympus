---
tags:
  - zeus/research
  - family/other
  - verdict/research
type: "research"
date: "2026-11-26"
source: "research/writeups/evalsizer-2026-11-26.md"
aliases:
  - "Optimal eval sizing policy"
---

# Optimal eval sizing policy

> [!abstract] Verdict: research
> (no status line)

**Full title:** Optimal eval sizing policy: today's rule is already the best (2026-11-26)

## Summary

PAPER RESEARCH ONLY (nothing changed live). Design first: `research/evalsizer/DESIGN.md` (committed before the scored run). Code `research/evalsizer/sizer.py` -> `results.json`, DP tables `dp_tables.npz` / `dp_table.txt`. Engine = research/plans/rank.py (as research/badcase): only the LIT eval sizing call is swapped; ATLAS lane, funded sizing and every MFFU rule unchanged; 1,000 paths, 60-session eval, 6-month slot with re-buys, owner prices. Check: T0 reproduces badcase (50K H1 83.8/16.2% vs 84/16%).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-26]]
- Source: `research/writeups/evalsizer-2026-11-26.md`
- Back to [[ZEUS Home]]
