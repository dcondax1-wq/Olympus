---
tags:
  - zeus/research
  - family/other
  - verdict/research
  - bot/zlarior
type: "research"
date: "2026-11-26"
source: "research/writeups/lit-fragility-2026-11-26.md"
aliases:
  - "How fragile is LIT"
---

# How fragile is LIT

> [!abstract] Verdict: research
> (no status line)

**Full title:** How fragile is LIT (Zlarior)? Robustness & fragility audit (2026-11-26)

## Summary

PAPER RESEARCH ONLY: nothing live changed. Plan written before the runs (`research/fragility/DESIGN.md`). Code `research/fragility/{fragility,sizing}.py` -> `results.json`, `sizing.json`. Engine = engine/lit.run_x, live params. Today's LIT: $5,562 / $2,670 / $25 a month (2026 Jan-Jun / Jul-Oct / 2021-25), 50K 2-week pass 44.5 / 39.1%. Fresh weeks Oct 19 - Nov 20: -$858 (1.4 trades a week).

## Money first

**LIT sits on a plateau, not a knife-edge, but its 2026 money is mostly the 2026 market.** Trust about a quarter of the
2026 rate: about $1,000-1,400 a month forward per 50K at the LIT size, not $4,250. Plan evals for a 2021-25-like market
too. In that market today's 40% room size fails about half the evals. **Sizing: keep today's 40% (room_f 0.4).** My simplified sim (below, section 5) suggested 0.3 cuts fails, but big-evalsizer re-checked it in the real eval engine (research/plans/rank.py: every MFFU rule, the soft day stop, the one-winner need cap, the ATLAS lane): 0.3 does NOT cut fails there, and 0.4 earns more in every market mix (branch big-evalsizer, research/evalsizer/mix_check.json).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-26]]
- Strategies: [[Zlarior (LIT)]]
- Source: `research/writeups/lit-fragility-2026-11-26.md`
- Back to [[ZEUS Home]]
