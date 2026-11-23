---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
  - lane/rapid
type: "research"
date: "2026-11-21"
status: "finding - recommend YES on new card rapid-funded-refit (25K cap $2,000 + keep $1,000; a 50K cap $4,000 + keep $2,000) and on keep-1000-rapid (reopened). Owner's yes before any preset change; nothing ..."
source: "research/writeups/rapid-funded-refit-2026-11-21.md"
aliases:
  - "Rapid EOD funded refit"
---

# Rapid EOD funded refit

> [!info] Verdict: finding
> finding - recommend YES on new card rapid-funded-refit (25K cap $2,000 + keep $1,000; a 50K cap $4,000 + keep $2,000) and on keep-1000-rapid (reopened). Owner's yes before any preset change; nothing live changed.

**Full title:** Rapid EOD funded refit - the Builder's winner cap does not belong on a Rapid; a bigger cap + keep more in the account

## Summary

The Rapid funded presets copied the Builder's per-trade winner cap ($1,000 25K / $2,000 50K), which only exists for the Builder's 50% consistency and $2,000 payout cap; MFFU's Rapid EOD funded has neither. Pre-registered grid (cap x amount kept in x room share, 1,000 paths, ATLAS at real fills and sized on a 10-tick stop): on the 25K, cap $2,000 + keep $1,000 makes $2,283 / $1,083 a month vs $1,742 / $769 (Jan-Jun / Jul-Oct-like) and loses fewer funded accounts (24.0 -> 18.3%, 34.5 -> 31.8%); 2021-25 -$47 vs -$46. On a 50K the rule's pick was cap $7,500 + keep $2,000 ($7,551 / $2,888), but its biggest simulated day reaches $9,621 (MFFU moves a Rapid to LIVE at $10,000 in a day and pauses every sim account), so Claude recommends cap $4,000 + keep $2,000 ($6,404 / $2,921, lost 19.4 -> 15.3%, 22.7 -> 21.6%, biggest day $7,229). The cap alone loses more accounts; keeping more in alone is ~$0 for 10 fewer lost Rapids in 100.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-21]]
- Strategies: [[Rapid lanes]]
- Runs: `tools/money/rapid_funded_refit.py run -> research/lab/rapid_funded_refit.json; design research/second/rapid_funded_refit_design.md (0023b1a3, committed first)`
- Source: `research/writeups/rapid-funded-refit-2026-11-21.md`
- Back to [[ZEUS Home]]
