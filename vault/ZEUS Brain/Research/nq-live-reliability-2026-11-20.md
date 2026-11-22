---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-11-20"
status: "finding - live code fixes + alarms built (tests green); poll-on-the-first-tick built OFF; ATLAS entries fill ~12 ticks worse than its backtest's 1 tick"
source: "research/writeups/nq-live-reliability-2026-11-20.md"
aliases:
  - "NQ live bot reliability"
---

# NQ live bot reliability

> [!info] Verdict: finding
> finding - live code fixes + alarms built (tests green); poll-on-the-first-tick built OFF; ATLAS entries fill ~12 ticks worse than its backtest's 1 tick

**Full title:** NQ live bot reliability - every way a backtest trade can miss the account, the fix or alarm for each, entry timing and real fills

## Summary

Owner - "push the NQ bot to its max ... read data faster, better fills, better timing ... fundeds paying next month". Since the 50K eval started only 2 of 7 backtest trades reached the account. Every cause was traced in the code. Fixed - the audit's "no record = missed" (now "unknown", Oct 28 WAS traded), a hot-added account booking a trade it never took (Zlarior 25K #2, -$129.40 + a CLOSEPOSITION on Nov 17), an update/restart while ATLAS holds a trade. New alarms - bot on but not polling / feed 2 bars behind -> phone push within 2 minutes (was up to 15-30 min); MISSED TRADE with its reason at once (was after 16:05 or never). Every "NOT routed" line now reaches the nightly verdict, the ZEUS review and the PC's day files. Timing - the order leaves 3-5 s after the fill bar opens (2 s is the poll offset); a built-OFF switch polls on NinjaTrader's first tick instead. Fills - Zlarior 3 ticks worse than its open (1 trade), ATLAS 9 / 11 / 15 ticks worse (3 trades) vs 1 tick in the backtests.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-20]]
- Runs: `tests/test_nq_live_reliability.py, tests/test_fast_entry.py, tests/test_account_b_min_room.py; data/pc_days ledger rows 2026-11-06..18 (NinjaTrader fill prices); scratchpad entry-poll timing (engine/poll_timing on the test_lit_live LiveBot harness)`
- Source: `research/writeups/nq-live-reliability-2026-11-20.md`
- Back to [[ZEUS Home]]
