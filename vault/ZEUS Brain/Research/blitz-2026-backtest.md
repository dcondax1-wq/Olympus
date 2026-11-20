---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/blitz
type: "research"
date: "2026-10-30"
status: "info - a report of today's rule, nothing changed or switched (BLITZ stays paper until the owner arms its own 25K)"
source: "research/writeups/blitz-2026-backtest.md"
aliases:
  - "BLITZ"
---

# BLITZ

> [!note] Verdict: info
> info - a report of today's rule, nothing changed or switched (BLITZ stays paper until the owner arms its own 25K)

**Full title:** BLITZ - the whole 2026 backtest on its own 25K (live rule, account C, live eval and funded sizes) - +$8,351 at $150 a trade (PF 1.67, $851 a month); the calendar run from Jan 2 passed 2 of 2 evals and paid $2,078 (net $1,952 after fees); Jul-Oct alone and 2021-25 are much weaker

## Summary

Owner 2026-10-30 - "backtest BLITZ on all of 2026, give me data, eval passed, profit". The live rule (engine/blitz.py v2) as account C (never opposite LIT / ATLAS), costs in, on CME NQ 1m bars Jan 2 - Oct 16, 2026 (2021-25 on 5m as the reference). At $150 a trade - 323 trades, 7.8 a week, 86% of weeks with 2+, win 56.7%, PF 1.67, net +$8,351 ($851 a month), max DD -$1,152 (H1 PF 1.70 / $963 a month, H2 1.62 / $667; 2021-25 PF 1.05 / $73). The 25K eval at the live size (40% of the room, the full room from session 5) on every 2026 start - 2-week pass / fail 34.5 / 34.0%, decided 68.5%, median 6 sessions to pass. The calendar run from 2026-01-02 (eval -> 2 sessions paperwork -> funded at 10% of the room <= $150, +$400 day stop -> payouts 80%) - 2 evals bought ($126), 2 passed (22 and 5 sessions), funded #1 stuck without a payout, funded #2 paid 3 payouts = $2,078 to the owner and still holds +$1,923, net +$1,952 after fees (~$199 a month). Started Jul 1 instead - 3 evals, 1 pass, 0 payouts by Oct 16 (-$189). 6-month Monte Carlo slot - $270 / $37 / -$40 a month (H1 / H2 / 2021-25).

## Money first

**BLITZ made money in every month of 2026 but April (flat), but most of the eval / funded money came from one good funded
account.** On its own 25K, the real calendar from Jan 2 would have cost $126 in evals and paid about $2,078 by Oct 16. Started
on Jul 1 instead, it would have paid nothing yet. Over 5 years (2021-25) the same rule about breaks even.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-30]]
- Strategies: [[BLITZ (paper)]]
- Refers to: [[blitz-25k|BLITZ on its own MFFU Builder 25K]]
- Runs: `blitz_2026_backtest`
- Source: `research/writeups/blitz-2026-backtest.md`
- Back to [[ZEUS Home]]
