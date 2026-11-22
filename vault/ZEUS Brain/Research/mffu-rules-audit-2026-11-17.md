---
tags:
  - zeus/research
  - family/other
  - verdict/finding
type: "research"
date: "2026-11-17"
status: "finding - nothing the bots do today voids an eval or a payout; two gaps fixed, the 2% price-limit guard still missing"
source: "research/writeups/mffu-rules-audit-2026-11-17.md"
aliases:
  - "MFFU rules audit"
---

# MFFU rules audit

> [!info] Verdict: finding
> finding - nothing the bots do today voids an eval or a payout; two gaps fixed, the 2% price-limit guard still missing

**Full title:** MFFU rules audit (2026-11-17): can anything the bots do void an eval or a payout?

## Summary

78 MFFU help-center articles and the plan pages checked against what the bots do (values in research/lit/mffu_rules.json). Hedging across accounts, max contracts, EOD trailing max loss, daily loss, flat time, holiday half-days, Rapid eval consistency, payouts and account limits are enforced. Fixed: the Rapid funded tier-1 news window had no safety margin and no December / 2027 CPI and jobs dates, and inactivity could cost the ATLAS 25K funded account all its profits with no warning. Missing: no guard for the 2% CME price-limit rule (rare; stand aside on crash days).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-17]]
- Source: `research/writeups/mffu-rules-audit-2026-11-17.md`
- Back to [[ZEUS Home]]
