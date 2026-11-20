---
tags:
  - zeus/research
  - family/other
  - verdict/finding
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-22"
status: "finding"
source: "research/writeups/second-route.md"
aliases:
  - "Second strategies on LIT's account"
---

# Second strategies on LIT's account

> [!info] Verdict: finding
> finding

**Full title:** Second strategies on LIT's account - the PC route (built, OFF) and what the live rules do to the EMA eval numbers

## Summary

Owner's order (2026-10-22) - "add this to this account, I want the bot to search for both". The PC bot can now trade the second strategies (EMA London pullback, MACD sweep, S/R NY reclaim) on LIT's own NinjaTrader account next to LIT, one switch per strategy, shipped OFF. Account rules - one position at a time, LIT first (no second entry while LIT is in a trade, entering, has a limit armed or waits for its 1m CISD; an open second trade is closed at market when LIT enters), max 2 trades a day with one slot always LIT's, eval-safe size ($500 capped at 60% of the room and the shared $1,000 soft daily loss, pass / fail lock). Under these rules the EMA's eval-path gain shrinks a lot - H2 path +$11.2k instead of the research's +$23.0k (LIT alone +$9.1k), H2 2-week pass/fail 69.6/0.0 (research 69.6/2.9, LIT alone 52.2/0.0) - and H1 gets worse than LIT alone (2-week fail 10.9% vs 5.9%). The main cost is the owner's "no entry while LIT is armed" rule (17 of 71 EMA trades, incl. 4 targets); the LIT-priority close adds the H1 fails. Keep the switch off on the eval; second-mix.md's two-account plan stays the better setup.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[second-ema|Second strategy next to LIT]], [[second-mix|LIT + the second strategies]]
- Runs: `ema2_lon_vix_with_lit, lit_adopt_t15_be_off_eval`
- Source: `research/writeups/second-route.md`
- Back to [[ZEUS Home]]
