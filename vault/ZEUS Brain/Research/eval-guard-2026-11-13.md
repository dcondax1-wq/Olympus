---
tags:
  - zeus/research
  - family/risk
  - verdict/research
  - bot/zlarior
type: "research"
date: "2026-11-13"
status: "proposal - nothing live changed (live_model*.json, second_model.json and the engine untouched)"
source: "research/writeups/eval-guard-2026-11-13.md"
aliases:
  - "Eval guard"
---

# Eval guard

> [!abstract] Verdict: research
> proposal - nothing live changed (live_model*.json, second_model.json and the engine untouched)

**Full title:** Eval guard (2026-11-13) - from today's room, risking 80% of it fails Zlarior's eval 4 times in 10; 40% is worth about $1,000 more per eval

## Summary

Risk of ruin of the two evals the owner trades live from tonight, started from their real state (Zlarior 50K $1,145 of room and $3,687 still to make; ATLAS 25K $822 of room and $1,678 to make), with the real sizing code per trade, whole weeks drawn from Jan-Jun 2026 (pick) and Jul-Oct 2026 (check). Today's code is past session 10 on both evals, so it sizes in safe_eval (Zlarior 60% of the room, ATLAS 30%), not in two_week 80% as docs/TONIGHT_EVAL.md says. Two-week 80% from here passes Zlarior in 2 weeks 35/40% of the time but fails it 41/42% of the time and is worth $2,617 / $2,697 per eval. Two-week 40% (kept past session 10) passes 32/27%, fails 3.5/3.5% and is worth $3,908 / $3,776: +$1,291 / +$1,079 per eval, and it beats today's code too (+$379 / +$538, 4 times fewer 2-week fails). The same holds for a fresh eval (+$1,000 / +$835). ATLAS: keep 50% of the room but keep two_week past session 10: 2-week passes 37 -> 57% (H1) and 14.5 -> 34.5% (H2) at about the same $ and under 2% fails. Proposal below; the lead or the owner decides.

## Money first

Picked on H1 by $ per eval among the rules that keep 2-week passes near today's, checked on H2:

- **Zlarior: two-week at 40% of the room, kept past session 10.** H1 $3,908 vs $2,617 at 80% (+$1,291), H2 $3,776 vs $2,697
  (+$1,079); 2-week fails 3.5 / 3.5% vs 41 / 42%; 2-week passes 31.9 / 27.4 vs 35.4 / 39.5 (-3.5 / -12.1 points). Versus
  today's code (safe_eval 60%): +$379 / +$538, fails 14.5 / 16.2 -> 3.5 / 3.5, passes 28.9 / 16.3 -> 31.9 / 27.4: better
  on all three in both halves. 2021-25: fails 51% -> 4.5% (no money either way there).
  Exact change, both `live_model.json` and `live_model_lit.json`, "lit_sizing":
  ```json
  "two_week": { ..., "room_f": 0.4, ... },     // was 0.8
  "two_week_until": 80                          // was 10 (keep two_week sizing for the rest of this eval; after_mode untouched)
  ```
  then `tests/sizing_pins.py` OWNER `"two_week.room_f": 0.4`, the docs (CLAUDE.md headline, CLAUDE_REFERENCE "Live
  strategy", STRATEGY.md, TONIGHT_EVAL.md "$916" -> about $458), `research/lit/uprisk_eval.json` row read by
  `tools/build_web_dashboard._live_eval_odds`, and `python tools/lit_losses.py live` + `tests.test_lit_live` (sizing only;
  the 120 trades do not change). Do not change `eval_start` to restart the count: it also selects the P&L days of the eval book.
- **ATLAS: keep 50% of the room, keep two-week past session 10.** 2-week passes 37.0 / 14.5 -> 57.3 / 34.5, fails 0 -> 1.9 /
  0.1, $ per eval -$67 / -$63 (inside the noise). 40% is +$91 / +$196 but slower: not a clear win, not proposed.
  The ATLAS knob is NOT in live_model.json: the 25K preset overrides it. Exact change (engine code, the lead's call):
  `engine/multi_account.py` PRESETS["mffu_builder_25k"]["sizing"]["two_week_until"] 10 -> 80 (`tests.test_second_account_b`,
  `tests.test_multi_account --quick`).
- **Not proposed:** the "protect when room < $X" rule. It cuts 80%'s fails to 8-10% and keeps the passes, but on H2 it earns
  less than plain 40% ($3,147 vs $3,776) and needs a new engine knob; plain 40% is a config change.
- **Speed, honestly:** from this state no rule meets "pass within 2 weeks, never more than 3": the best 2-week pass rate is
  ~40% and comes with ~42% fails. The eval already lost 43% of its room; that is the price of being behind.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-13]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[2026-11-03-slippage|How much slippage each bot survives]], [[atlas-funded|ATLAS's funded account]], [[lit-live-fills|LIT live fills]], [[uprisk|Uprisk]]
- Runs: `eval_guard_zlarior_as_coded, eval_guard_zlarior_hold_80, eval_guard_zlarior_hold_50, eval_guard_zlarior_hold_40, eval_guard_zlarior_tw_80_prot1000, eval_guard_atlas_as_coded, eval_guard_atlas_hold_80, eval_guard_atlas_hold_50, eval_guard_atlas_hold_40`
- Source: `research/writeups/eval-guard-2026-11-13.md`
- Back to [[ZEUS Home]]
