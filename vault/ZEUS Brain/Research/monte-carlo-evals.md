---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/monte-carlo-evals.md"
aliases:
  - "Monte Carlo of the MFFU 50K eval"
---

# Monte Carlo of the MFFU 50K eval

> [!info] Verdict: finding
> finding

**Full title:** Monte Carlo of the MFFU 50K eval: how often, how fast, how many evals

## Summary

One 50K eval on the locked strategy has about a 35% chance of passing within 60 sessions, 30% of failing and 35% of still running (the real history says 41 / 22 / 37); a typical pass takes 28 sessions, and a funded account costs 1.9 evals and about 5.5 months of fees (roughly $840 at list price), median 15 weeks. Starting the eval during a cold streak cuts the 1-month pass odds from 22% to 4%, so time the purchase to the filter. The fast press gets funded in a median 9.8 weeks for 3.7 months of fees but fails half of its evals.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-17]]
- Runs: `mc_locked, mc_pool_2026, mc_pool_2021_25, mc_press`
- Source: `research/writeups/monte-carlo-evals.md`
- Back to [[ZEUS Home]]
