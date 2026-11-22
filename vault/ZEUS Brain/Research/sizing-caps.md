---
tags:
  - zeus/research
  - family/risk
  - verdict/adopted
type: "research"
date: "2026-10-24"
status: "adopted (safety fix, engine/sizing.py; tests/test_sizing_caps.py)"
source: "research/writeups/sizing-caps.md"
aliases:
  - "Sizing cap invariant"
---

# Sizing cap invariant

> [!success] Verdict: adopted
> adopted (safety fix, engine/sizing.py; tests/test_sizing_caps.py)

**Full title:** Sizing cap invariant - a budget is a ceiling, never "min 1 micro" past it (pre-launch audit)

## Summary

Pre-launch audit. Before, every cap (60% of the eval room, the soft daily loss, the room caps of eval / safe_eval, account B's $150 / $300 safe size, ATLAS's $500, the extra accounts' daily loss) rounded a too-small result back UP to 1 micro, so a wide stop or an almost-used budget could still send 1 micro whose stop-out broke the cap - in the worst case the MFFU max-loss floor (fast_eval had no room cap at all). Now the micros are computed after all caps; if not even 1 micro fits, the entry is skipped. Every cap prices 1 micro at (stop + 1 tick) x $2 + $1.90. A final check (sizing.ceilings) runs last in every eval mode, incl. the 1-micro minimum-days trade - room, soft daily loss and (when switched on) the weekly loss budget. Money on the 2026 eval path: fresh-eval 2-week pass unchanged (LIT 57.1 / 52.2), 2-week fails 5.9 / 0.0 -> 0.0 / 0.0, but the drained evals no longer die - they get "stuck" (room too small for almost any entry). With the old path rule (new eval only after a pass / fail) a stuck eval sits forever: H1 +$34.3k -> +$27.2k, H2 +$9.1k -> -$1.9k. With a stuck rule (room < $200 = buy a new eval) both versions match: H1 +$27.9k -> +$28.5k, H2 +$15.3k -> +$14.8k. So the bot now pushes "EVAL STUCK: buy a new one" when the room is under $200. Account B 25K: 2-week pass H1 68.9 -> 62.2 (the +1 tick + $1.90 in the room cap costs ~6 points), H2 43.5 unchanged, fails 0.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-24]]
- Runs: `sizing_cap_lit_eval, sizing_cap_lit_eval_stuck200, sizing_cap_acctb_25k_need, sizing_cap_acctb_50k_need, sizing_cap_acctb_25k_safe, sizing_cap_acctb_50k_safe`
- Source: `research/writeups/sizing-caps.md`
- Back to [[ZEUS Home]]
