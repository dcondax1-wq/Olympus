---
title: Sizing cap invariant - a budget is a ceiling, never "min 1 micro" past it (pre-launch audit)
family: risk
date: 2026-10-24
status: adopted (safety fix, engine/sizing.py; tests/test_sizing_caps.py)
summary: Pre-launch audit. Before, every cap (60% of the eval room, the soft daily loss, the room caps of eval / safe_eval, account B's $150 / $300 safe size, ATLAS's $500, the extra accounts' daily loss) rounded a too-small result back UP to 1 micro, so a wide stop or an almost-used budget could still send 1 micro whose stop-out broke the cap - in the worst case the MFFU max-loss floor (fast_eval had no room cap at all). Now the micros are computed after all caps; if not even 1 micro fits, the entry is skipped. Every cap prices 1 micro at (stop + 1 tick) x $2 + $1.90. A final check (sizing.ceilings) runs last in every eval mode, incl. the 1-micro minimum-days trade - room, soft daily loss and (when switched on) the weekly loss budget. Money on the 2026 eval path: fresh-eval 2-week pass unchanged (LIT 57.1 / 52.2), 2-week fails 5.9 / 0.0 -> 0.0 / 0.0, but the drained evals no longer die - they get "stuck" (room too small for almost any entry). With the old path rule (new eval only after a pass / fail) a stuck eval sits forever: H1 +$34.3k -> +$27.2k, H2 +$9.1k -> -$1.9k. With a stuck rule (room < $200 = buy a new eval) both versions match: H1 +$27.9k -> +$28.5k, H2 +$15.3k -> +$14.8k. So the bot now pushes "EVAL STUCK: buy a new one" when the room is under $200. Account B 25K: 2-week pass H1 68.9 -> 62.2 (the +1 tick + $1.90 in the room cap costs ~6 points), H2 43.5 unchanged, fails 0.
runs: sizing_cap_lit_eval, sizing_cap_lit_eval_stuck200, sizing_cap_acctb_25k_need, sizing_cap_acctb_50k_need, sizing_cap_acctb_25k_safe, sizing_cap_acctb_50k_safe
---

## In one minute

- **The bug.** Each cap did `q = max(1, cap)`: when the cap allowed 0.4 micros, the bot still sent 1. With a $120 room and a
  50-pt stop that is a $102 stop-out against a $72 cap; with $60 room it breaks the max-loss floor (eval failed by the bot's own
  order). Same with the soft daily loss nearly used, ATLAS / account B on a wide stop, the extra accounts' daily loss.
- **The fix.** Micros after all caps; fewer than 1 -> **skip**. Every cap uses (stop + 1 tick) x $2 + $1.90 a micro. The
  "risk $" base may still round to 1 micro, but only when that micro fits every ceiling. The 1-micro minimum-days trade after
  an early target stays, and must fit too. A last check in every eval mode (`sizing.ceilings`): below the room, inside the soft
  daily loss ($1,000 50K / $600 25K), inside the weekly loss budget when `wk_loss_usd` is on.
- **What it costs.** Nothing on fresh evals' pass odds; the 2-week fails become "stuck" evals. The owner must replace a stuck
  eval (push "EVAL STUCK", room under $200), or the bot waits on it for weeks.

## Where "min 1 micro" overrode a cap (before)

| place | cap |
|---|---|
| `engine/sizing.py` two_week_qty caps loop `q = max(1, cap)` | max_usd, protect, 60% room, soft daily loss |
| two_week_qty min-days `return 1` | not checked against any cap |
| lit_qty_core eval / safe_eval `q = max(1, cap)` | 60% room (`safe_cap`) |
| fast_eval | no room cap at all |
| eval_lock min-days `qty=1` | not checked |
| funded_qty best-day / 60% room `max(1, cap)`, hard caps with `skip_breach false` | best day, room, soft daily loss |
| day_guard `breach "one"` | room, daily loss (option, off) |
| second_qty base `max(1, ...)` | ATLAS $500 / account B $150 / $300 |
| `engine/multi_account.py` qty_for `max(1, ...)` | best-day rule, the account's daily loss, max_risk_usd |

Multipliers that floor at 1 (weekly stop, learned cut, inducement cut, old engine cold / late) stay: they only shrink a size
that already fit, and the final ceilings run after them.

## Numbers (2026, eval path, run lit_adopt_t15_be_off_eval units, costs in)

| | H1 path $ | H2 path $ | 2-week pass / fail / stuck H1 | H2 |
|---|---|---|---|---|
| before (published) | +34,253 | +9,059 | 57.1 / 5.9 / - | 52.2 / 0.0 / - |
| after, old path rule | +27,164 | -1,940 | 57.1 / 0.0 / - | 52.2 / 0.0 / - |
| before, stuck at $200 | +27,949 | +15,336 | 57.1 / 0.0 / 14.3 | 52.2 / 0.0 / 11.6 |
| after, stuck at $200 | +28,482 | +14,771 | 57.1 / 0.0 / 13.4 | 52.2 / 0.0 / 11.6 |

Entries skipped by a cap on the path: 4 (H1) + 25 (H2) with the old path rule (the H2 eval from Jul 1 drained to $60 room and
skipped every later signal), 0 with the stuck rule. 1-month pass H2 50.8 -> 49.2. The stored run lit_live (LIT size rule,
mode normal) is unchanged: the invariant acts only in the eval modes.

Account B (tools/second_account_b.py): 25K need H1 2-week 68.9/0.0 -> 62.2/0.0 (stuck 7.6 -> 0.8), H2 43.5/0.0 unchanged; path
H1 +$19.7k -> +$14.8k, H2 +$5.4k -> +$6.7k. 50K need H1 72.3/2.5 -> 73.9/0.0, H2 53.6/0.0 unchanged. Skip-only (old room-cap
denominator) would keep the 25K H1 at 68.1: the 1 tick + $1.90 in the room cap is what costs it. ATLAS EMA routed on LIT's
account (tools/second_route_eval.py, live route): H1 2-week 55.5/10.9 -> 51.3/0.0, H2 69.6/0.0 unchanged.

Path $ hangs on one or two evals (a 40-trade H2): read the fresh-eval odds, not the path, for the change itself.
