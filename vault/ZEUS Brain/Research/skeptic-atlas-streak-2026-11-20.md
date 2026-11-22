---
tags:
  - zeus/research
  - family/second
  - verdict/research
  - bot/zlarior
  - bot/atlas
  - lane/rapid
type: "research"
date: "2026-11-20"
status: "verdicts - atlas-funded-streak-1micro WEAKER THAN CLAIMED (card text updated, recommend kept yes with a caveat); rapid25-lit-bank NO HOLDS; atlas-on-rapid YES HOLDS. Nothing live changed."
source: "research/writeups/skeptic-atlas-streak-2026-11-20.md"
aliases:
  - "Skeptic check of Decide card atlas-funded-streak-1micro"
---

# Skeptic check of Decide card atlas-funded-streak-1micro

> [!abstract] Verdict: research
> verdicts - atlas-funded-streak-1micro WEAKER THAN CLAIMED (card text updated, recommend kept yes with a caveat); rapid25-lit-bank NO HOLDS; atlas-on-rapid YES HOLDS. Nothing live changed.

**Full title:** Skeptic check of Decide card atlas-funded-streak-1micro (after 2 ATLAS losses in a row, 1 micro until a win) - WEAKER THAN CLAIMED; spot check of rapid25-lit-bank (NO holds) and atlas-on-rapid (YES holds)

## Summary

Lead round 3 (day-newstrat). Re-ran the card's own simulator (tools/atlas_edge.py PGE -> atlas_risk PGF3, today's $887-room funded 25K, 10 and 6 ticks a side, 1,000 paths) and reproduced it exactly (10t lost 17.6 -> 12.2% Jan-Jun-like, 21.7 -> 10.9% Jul-Oct-like, $503 -> $481 / $402 -> $408). Code: no look-ahead (the streak only reads finished sessions), both arms on the same trades / costs / paths, room and floor math untouched. Holds on 2 more seeds (Jul-Oct-like 23.5 -> 12.5%, 23.8 -> 11.7%) and lowers the loss odds in every 2021-25 year (but 89-99% are still lost). Weaker: (1) shuffling single days instead of week blocks halves the gain (Jul-Oct-like 23.5 -> 18.5%) and costs $53 a month (-14%, under the card's own 90% money bar); the effect leans on losses arriving in bunches. (2) In a Jan-Jun-like market a plain flat smaller size beats it on both counts (room 40%: 11.0% lost, $527 vs the rule's 12.2%, $481), so there it is just "trade smaller". (3) It is not a knife edge: 3 losses -> 1 micro (13.9% / $418) and 2 losses -> 2 micros (11.8% / $422) work in Jul-Oct-like too, and cost less in Jan-Jun-like; 1 loss over-shrinks ($304); a per-leg streak is worse (18.1%). (4) On top of room 40% it cuts Jul-Oct-like loss odds 14.0 -> 7.7% at the same $ but costs $49 a month Jan-Jun-like for only 11.0 -> 10.1%. Rapid spot check: both card verdicts follow their pre-registered rules and the stored numbers.

## Links

- Family: [[Family second]]
- Day: [[Day 2026-11-20]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[Rapid lanes]]
- Runs: `none (research/skeptic/streak.py -> research/skeptic/streak_results.json)`
- Source: `research/writeups/skeptic-atlas-streak-2026-11-20.md`
- Back to [[ZEUS Home]]
