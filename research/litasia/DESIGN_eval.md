# EVAL-ONLY Asia slot. Pre-registration (2026-11-26, written BEFORE any run)

PAPER RESEARCH ONLY. Code research/litasia/eval_only.py -> research/litasia/eval_only.json; write-up appended to
research/writeups/litasia-2026-11-26.md.

**The rule tested.** While an account is in its EVAL, LIT also takes the Asia-slot trade (18:00-02:00 ET, own slot, banked at
3R: lit-more-entries `asiaslotn_rr3_x1.0`, the same engine run as research/litasia/asia.py). Once FUNDED: today's LIT only.
Extra Asia slippage: +2 and +4 ticks a side on the Asia trades (entry, and a non-target exit).

**Engine.** research/plans/rank.py unchanged, with ATLAS at 10 ticks a side (AR.T_at(10)).
- **Builder 50K and Builder 25K:** today's routing, LIT only (the eval sizing = live two_week; funded = the MFFU preset).
- **Rapid EOD 25K:** LIT + the ATLAS lane, with its news rule in the funded stage.
- **How the variant is fed in.** The LIT stream is swapped into stack_one_account's LIT list, which is converted from the engine's
  own trades. The converter must reproduce the stored COMPLETE_TRADE_LEDGER LIT stream exactly (631 / 631) before anything is scored.

**Paths.** 1,000 Monte Carlo paths of 5-session blocks: eval seed 7, slot seed 23.
**Markets.** 2026 H1, 2026 Jul-Oct, 2021-25 (REF), plus two business scenarios:
- MIX25: each block from 2021-25 with probability 0.25, else from 2026;
- TURNS BAD: 2026 blocks for the first 30 sessions, then 2021-25.

**Reported per plan x market x cost.**
- 2-week (10 sessions) and 30-day (21 sessions) pass / fail %;
- median sessions to pass (60-session horizon);
- the 6-month slot net to the owner incl. eval and reset fees (rank.slot_run).

**Card only if** the 2021-25 eval pass % (2-week and 30-day) is not worse than today, AND the fail % does not rise in ANY market
at either horizon, on all 3 plans, at +2 ticks. Otherwise: rejected, with the numbers.
