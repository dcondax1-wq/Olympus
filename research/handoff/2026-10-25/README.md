# Pre-launch audit handoff, 2026-10-25 (00:15 to ~06:30 ET)

## A. EXECUTIVE_VERDICT: READY_FOR_ISOLATED_SIM, then monitored evaluation by the owner

Code, backtest reproduction, look-ahead, sizing and the fake-folder order lifecycle all pass. What only the owner can
prove on the PC tonight: the real NinjaTrader / Tradovate behaviour (`--sim-roundtrip`, `--sim-roundtrip-add` on Sim101).
Arming the evals stays the owner's own step (MFFU requires him present). Scale-in stays OFF.

Evidence:
- LIT reproduces exactly: run `lit_live` 631/631 trades (A2_lit_baseline.md); live loop `tests.test_lit_live --days --bot`
  120/120 identical, routed entries 2/2 exits 2/2.
- No look-ahead: 220 LIT signals and 175 ATLAS trades unchanged on data cut at the decision bar (A1, A3,
  tests/test_prefix_invariance.py). VIX uses the prior-day close only.
- ATLAS live entry = research entry on 175/175 trades; a full scan of 33,321 live probes gives exactly the 175 (A3).
  "One bar late" was a stress test, not a live bug.
- No eval breach in any 2026 window, fresh or from the owner's real 50K snapshot (A4, EVALUATION_WINDOWS.csv).

Remaining gates (UNTESTED here): real NinjaTrader restart rewriting outgoing files; CLOSEPOSITION cancelling working
orders on the real install; OCO sibling resizing (scale-in); Tradovate login expiry; real fill slippage; MNQ 1m vs NQ 1m
(only a 37-session 5m MNQ sample: about a third of LIT signals differ between the feeds, see A1 section 6).

## Results (costs in)
| | 2026 | Jan-Jun (picked) | Jul-Oct (check) | 2021-25 ref |
|---|---|---|---|---|
| LIT, LIT size rule, $1.90/micro | +$43,502 PF 4.15, 2.91/wk | +$33,9k PF 4.98 | +$9,9k PF 2.91 | ~$0 (5m only) |
| LIT 50K eval, 2-week pass/fail (fresh) | | 57.1 / 0 (5.0 stuck) | 50.7 / 0 | |
| LIT on the owner's real 50K (needs $3,289) | | pass in 10 sessions 40.3% | 31.9% | |
| ATLAS 25K path (today's caps) | | +$6,481 PF 2.30 | +$4,434 PF 3.18 | 2025 -$2,156, 2021-24 +$2,419 |
| ATLAS 25K 2-week pass/fail | | 65.5 / 0 | 43.5 / 0 | |
Per ATLAS setup (EMA / MACD / S/R): PERFORMANCE_BY_SETUP.csv. H2 rests on few trades (15 MACD, 16 S/R); without the top 3
winners each, H2 is EMA +$499, MACD -$2,621, S/R +$140. Treat H2 rates as about +/-10 points.
Honest notes: the 15-minute cut was chosen with H2 visible; the eval "0% fail" counts stuck evals separately (LIT stuck
= room < $200 -> push "EVAL STUCK: buy a new one"); entering 2 minutes late keeps only ~68% of LIT's money.

## J. FIXES (BUG_FIX, each with a failing example and a regression test)
1. Account-scoped kill: account B's kill / remote flatten sent FLATTENEVERYTHING and would have flattened LIT's 50K too.
   Now CLOSEPOSITION + CANCEL by id; global kill only on the owner's own kill (A5, tests/test_nt_exec_audit.py 46/46).
2. Duplicate-process lock per account; 3. OIF files never overwrite; 4. corrupted state file -> alert + entries blocked (A5).
5. Startup DISARMED until positions/orders, feed, clock, contract and eval anchor reconcile; account allowlist (A5).
6. Hedge close: LIT's opposite entry waits for ATLAS's close to be CONFIRMED flat, else skipped at 90 s with a critical
   "HEDGE BLOCKED" alert; an unconfirmed close never marks B flat (A4, tests/test_router_determinism.py 36/36).
7. ATLAS member priority: the next allowed member takes the bar when the first is blocked (A4).
8. ceilings(): unknown stop distance no longer routes uncapped; extra eval account without eval_start no longer trades
   uncapped (A4, tests/test_risk_invariants.py 27/27).
9. recent_bars on a 1m-only chart could return an unfinished 5m bar; July-3 early close added (A1, tests/test_a1_timing.py).
Strategy changes this period (separately approved): safe switches cisd1m 22, room_f 0.55, wk_loss_usd 1200 (owner
2026-10-24). No other strategy change.

## Files (this folder)
A1_data_timing.md · A2_lit_baseline.md, COMPLETE_TRADE_LEDGER.csv, SIGNAL_LEDGER_LIT.csv, A2_robustness.csv ·
A3_atlas.md, PERFORMANCE_BY_SETUP.csv, ATLAS_TRADE_LEDGER.csv, ATLAS_SIGNAL_LEDGER.csv, ROBUSTNESS_BY_SETUP.csv ·
A4_eval_risk.md, EVALUATION_WINDOWS.csv, EVALUATION_SUMMARY.csv, COMMISSION_DRIFT.csv ·
A5_execution.md (EXECUTION_TEST_MATRIX), STARTUP_AND_RECOVERY_RUNBOOK.md (K).
Experiment log (H): research/runs/index.json + research/writeups/INDEX.md (every run and write-up, incl. the rejected
ChatGPT filters / ATLAS templates of 2026-10-24).

## L. FINAL_CHECKPOINT
Done: all five audits merged, full suite green (selftest 70/70, nt_exec_audit 46/46, router 36/36, risk 27/27, sizing
41/41, anchor 43/43, timing 25/25, outgoing 26/26, late entry 10/10, guards 69/69, alerts 92/92, eval lifecycle 41/41,
second_route 24/24, account B 42/42, multi_account 49/49, lit_live 120/120 + routed 2/2/2/2).
Open (owner, PC, after 18:00 ET): `python -m engine.launch_prep --atlas "<25K Name>"` (allowlist both accounts + real
50K anchor + ATLAS on the 25K), the Sim101 roundtrips, then arming. Follow-ups after launch: book LIT P&L at $1.90/micro
(now $1.40, <= $17/trade drift; refresh the anchor from the MFFU dashboard meanwhile); ATLAS "stuck" threshold ($100) vs
idle evals at $100-300 room; MNQ 1m comparison once the PC has archived MNQ 1m bars.
