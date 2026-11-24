---
tags:
  - zeus/research
  - family/money
  - verdict/research
  - bot/zlarior
  - bot/atlas
  - bot/blitz
  - lane/rapid
type: "research"
date: "2026-11-23 (night, run 2026-11-24 early ET)"
status: "research only, paper. Nothing armed, no live_model*.json touched. One owner yes/no proposed (BLITZ Rapid lane $300 -> $150)."
source: "research/writeups/four-pillars-2026-11-23.md"
aliases:
  - "The four pillars"
---

# The four pillars

> [!abstract] Verdict: research
> research only, paper. Nothing armed, no live_model*.json touched. One owner yes/no proposed (BLITZ Rapid lane $300 -> $150).

**Full title:** The four pillars (LIT, ATLAS, BLITZ, ORDER FLOW) - each case at its honest strongest; BLITZ on the Rapid 25K eval is good enough to switch on only at $150, not the built $300

## Summary

LIT GREEN (last 40 sessions PF 4.62 vs backtest 3.91) but no edge in 2021-25 (PF 1.01). ATLAS GREEN (PF 2.27 vs 2.75) at real fills, 2021-25 PF 0.82. BLITZ pre-registered test on the Rapid 25K eval - the built $300 lane fails the eval 0.5% -> 3.1% (Jan-Jun); at $150 1.2%, passes every pre-set check, +$45 / +$91 a month. ORDER FLOW - recorder built, never compiled, 0 tick days; first test about Nov 26-30 with the backfill, else Feb 22 2027; priors low.

## Links

- Family: [[Family money]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]], [[Rapid lanes]]
- Refers to: [[atlas-edge-2026-11-20|ATLAS edge at real fills]], [[atlas-fills-2026-11-20|ATLAS real fills]], [[lit-edge-2026-11-20|Zlarior]], [[orderflow-2026-11-23|Order flow]], [[orderflow-program-2026-11-23|Order-flow program]]
- Runs: `research/pillars/blitz_rapid.py -> research/pillars/blitz_rapid.json (design research/pillars/DESIGN.md, commit 24d5d94e2); tools/edge_health.py; pillars file research/lab/pillars.json`
- Source: `research/writeups/four-pillars-2026-11-23.md`
- Back to [[ZEUS Home]]
