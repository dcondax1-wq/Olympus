---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - lane/rapid
type: "research"
date: "2026-11-20"
status: "rejected (no change, no Decide card). live_model*.json, second_model.json, accounts untouched."
source: "research/writeups/newstrat-ict-smt-2026-11-20.md"
aliases:
  - "New strategy for the extra accounts"
---

# New strategy for the extra accounts

> [!failure] Verdict: rejected
> rejected (no change, no Decide card). live_model*.json, second_model.json, accounts untouched.

**Full title:** New strategy for the extra accounts (Rapid EOD 25K) - ICT ATM range + ES/NQ SMT as the trigger, MES as the traded market, and a Judas-swing control; none passes, nothing changed

## Summary

Owner 2026-11-20 - pull in "the ATM model ICT", ES/NQ SMT and "trades for ES if it looks cleaner" for the new MFFU Rapid EOD 25K. Five rule sets were written down before any run (research/newstrat/RULES.md, commit before the code) - SMT-ATM on NQ and on MES, session SMT (prior-day / overnight high-low) on NQ and on MES, and a no-ES Judas swing - each 1 trade a day max, stop 1 tick beyond the sweep extreme, one target, $250 risk, costs in. 0 of 5 pass. Every SMT set loses money in all three periods (PF 0.57-0.99, gross PF before costs 0.59-1.05): SMT used as the trigger has no edge, on NQ or on ES. MES is not cleaner (S2/S4 lose like S1/S3, and the 10-tick stress is far worse on ES because stops are 5-7 pts). The Judas control makes +$1,672 in 2026 Jan-Jun and then loses Jul-Oct (-$2,244) and 2021-25 (-$11,472 on 633 trades). Rapid EOD 25K 60-day eval pass 0-5% for every SMT set (blow 43-86%). Correlation with LIT / ATLAS is near zero (-0.16..+0.15), so a real edge could stack - but there is none to stack.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-20]]
- Strategies: [[Rapid lanes]]
- Refers to: [[lit-untested-entries|LIT untested entry ideas]]
- Runs: `none (research/newstrat/results.json; research/newstrat/smt.py)`
- Source: `research/writeups/newstrat-ict-smt-2026-11-20.md`
- Back to [[ZEUS Home]]
