---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/atlas
type: "research"
date: "2026-11-17"
status: "adopt-candidate (the lead / owner decides; paper only; no live_model file touched). Pick - LIT only, two_week at 40% of the room to session 80, then safe_eval at 60% (= the owner-approved Builder ..."
source: "research/writeups/builder25k-eval-sizing-2026-11-17.md"
aliases:
  - "Eval sizing for a FRESH MFFU Builder 25K"
---

# Eval sizing for a FRESH MFFU Builder 25K

> [!success] Verdict: adopt-candidate
> adopt-candidate (the lead / owner decides; paper only; no live_model file touched). Pick - LIT only, two_week at 40% of the room to session 80, then safe_eval at 60% (= the owner-approved Builder 50K rule). The mffu_builder_25k preset today (50% to session 10, then safe_eval 30%) is worse - change the preset or override it on the new account. Rejected - room 45-60%, every $ cap, first-hit. ATLAS $250 at 20% in the eval is faster in both 2026 halves but raises 2021-25 fails and needs a new ...

**Full title:** Eval sizing for a FRESH MFFU Builder 25K - room share, $ caps, first-hit, ATLAS in the eval

## Summary

Owner buys a fresh Builder 25K tonight ($1,500 target, $1,000 EOD trailing, $600 soft DLL, 20 micros, no consistency, 1 day). 23 eval sizings on the exact bot config (engine/multi_account.sizing_cfg of the mffu_builder_25k preset + override -> engine/sizing.lit_qty), 1,000 Monte Carlo paths per span, the same paths as builder-levers. Pick on H1 = LIT 40% of the room to session 80 (median 12 sessions to pass, 2-week pass/fail 47.6/0.0%, 60-session fail 2.6%; H2 12, 47.2/0.0, 1.7%), first funded payout ~Jan 5 / Jan 6 (33 / 34 sessions), $553 / $456 a month. Bigger room shares (45-60%) pass 1-3 sessions sooner but 60-session fails jump to 7-21%. $ caps $150-$400 are all slower. First-hit does nothing (the first trade is already sized by "one winner covers $1,500"). The 20-micro cap never binds (0 of ~68,000 LIT trades sized); the room share and the "one winner" size bind.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Strategies: [[ATLAS]]
- Refers to: [[builder-levers-2026-11-16|Three MFFU Builder levers for money sooner]], [[lit-builder-25k|MFFU Builder 25K next to the 50K]]
- Runs: `none (research/lab/builder25k_eval.json, tools/money/builder25k_eval.py)`
- Source: `research/writeups/builder25k-eval-sizing-2026-11-17.md`
- Back to [[ZEUS Home]]
