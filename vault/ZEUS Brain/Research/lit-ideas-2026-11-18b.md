---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-11-18"
status: "rejected - nothing passes, Zlarior stays as it is. ATLAS's zombie-eval rule on Zlarior's evals makes +$57 / +$51 a month for the pair only by killing evals faster (2-week fails 50K 4.9 -> 10.4% / ..."
source: "research/writeups/lit-ideas-2026-11-18b.md"
aliases:
  - "Zlarior ideas night 2"
---

# Zlarior ideas night 2

> [!failure] Verdict: rejected
> rejected - nothing passes, Zlarior stays as it is. ATLAS's zombie-eval rule on Zlarior's evals makes +$57 / +$51 a month for the pair only by killing evals faster (2-week fails 50K 4.9 -> 10.4% / 3.1 -> 6.9%, 25K 0 -> 8.1% / 0 -> 8.3%); staggered full / half size across the two evals costs -$80 / -$49 a month and slows both passes. Every other angle on the list was already tested.

**Full title:** Zlarior ideas night 2 (2026-11-18b) - the two live evals together - zombie-eval rule, staggered size, and an audit of the other angles

## Summary

Zlarior trades two MFFU evals on the same signals - the Builder 50K from its hole ($1,025 room, $3,807 to go) and the fresh Builder 25K #2. New tool tools/money/lit_two_evals.py runs both on ONE Monte Carlo (same 5-session-block paths, 1,000 per span, live sizing = engine/sizing.lit_qty, costs in; base = builder25k_eval / builder_levers exactly). Two pre-declared ideas, one version each - (1) ATLAS's approved zombie-eval rule ported to Zlarior (1-micro last bullet at 80% of the room + give up under $200) - seats +$57 / +$51 a month for the pair, but both evals die together within 20 sessions 16.3% / 14.5% of the time (today 0.4% / 0.3%), 25K 60-session fails 2.6 -> 22.4% / 1.7 -> 23.1%; Lab eval path H1 -$114, 2 trades changed - rejected. (2) Stagger - the evals alternate full / half size on each signal - pair -$80 / -$49 a month, 25K 2-week pass 47.6 -> 31.2% / 47.2 -> 31.8%, first payout 4 sessions later; Lab LIT size -$1,391 / -$1,400 a month - rejected. Today the two evals almost never die together (0.3-0.4% within a month); the joint risk is waiting, not failing. Reference (a purchase, not a rule) - a fresh 50K next to the hole, re-measured from today - +$50 / +$54 a month for the 50K after its $91.80. ES confirmation, overnight range, gap size, prior-day structure, weekday x session, news, early closes and entry timing were all tested before (sources listed); no Lab cells spent on them.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[2026-11-04_lit_ideas_night|LIT ideas night]], [[2026-11-15-atlas-deep|ATLAS deep edge]], [[2026-11-15-s2-edge|S2 edge]], [[builder-levers-2026-11-16|Three MFFU Builder levers for money sooner]], [[builder25k-eval-sizing-2026-11-17|Eval sizing for a FRESH MFFU Builder 25K]], [[calendar-effects|Calendar and seasonality]], [[cross-market-context|Cross-market and regime context]], [[edge-health-2026-11-17|Edge health, 2026-11-17]], [[eval-game|The eval game]], [[lit-ablation|LIT ablation]], [[lit-adv-audit-smt|LIT advanced report ch.7 audit]], [[lit-bias-discretion|LIT with bias and discretion]], [[lit-edge-2026-10-30|Zlarior edge night]], [[lit-entry-precision|LIT entry precision]], [[lit-losses|LIT losses]], [[lit-risk-money|LIT risk and money]], [[lit-smart-entries-2026-11-17|LIT smart entries]], [[lit-trade-intel|LIT trade intelligence]], [[unexpected-factors|Unexpected factors]], [[zeus-lab-lit-ideas-2026-11-18|ZEUS Lab]]
- Runs: `none (research/lab/lit_two_evals.json; ZEUS Lab lit_idea lit_eval_zombie, lit_two_eval_stagger in research/lab/zeus_lab/registry.json)`
- Source: `research/writeups/lit-ideas-2026-11-18b.md`
- Back to [[ZEUS Home]]
