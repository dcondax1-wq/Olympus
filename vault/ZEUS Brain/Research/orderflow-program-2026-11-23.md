---
tags:
  - zeus/research
  - family/research
  - verdict/rejected
type: "research"
date: "2026-11-23"
status: "6 bar tests rejected; 3 tick designs pre-registered; tick import fixed (UTC) and made simple"
source: "research/writeups/orderflow-program-2026-11-23.md"
aliases:
  - "Order-flow program"
---

# Order-flow program

> [!failure] Verdict: rejected
> 6 bar tests rejected; 3 tick designs pre-registered; tick import fixed (UTC) and made simple

**Full title:** Order-flow program - what pros use, what our bars can test, and 3 tick designs ready to run

## Summary

Ten order-flow topics pro NQ traders use are written up below as testable rules, each with the data it needs. Six new bar-data tests ran with pre-set rules and costs in. All six fail. The best near miss is a stand-alone LVN rejection (PF 1.26 / 1.10 / 4.56, placebo p 0.004, uncorrelated with LIT, but only 0.5-0.7 trades a week). Three tick designs are pre-registered and run by themselves at 60+ tick days. The tick importer had a real bug (NinjaTrader exports in UTC, the importer assumed New York time) that is now fixed and tested, along with a 9x faster streaming import and no loss of same-timestamp trades. LIT is unchanged and nothing was armed.

## Links

- Family: [[Family research]]
- Day: [[Day 2026-11-23]]
- Runs: `research/orderflow/of_program.py -> research/orderflow/program_results.json; of_study.py prereg() (tick mode)`
- Source: `research/writeups/orderflow-program-2026-11-23.md`
- Back to [[ZEUS Home]]
