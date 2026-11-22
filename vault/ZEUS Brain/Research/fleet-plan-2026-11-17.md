---
tags:
  - zeus/research
  - family/risk
  - verdict/research
type: "research"
date: "2026-11-17"
status: "plan (paper research, nothing live changed) - in 2026-like markets the fleet pays from mid-December and keeps $20-35k (4 accounts) or $29-54k (5 accounts) after fees, splits and the 30% tax pot in 6 ..."
source: "research/writeups/fleet-plan-2026-11-17.md"
aliases:
  - "Fleet plan"
---

# Fleet plan

> [!abstract] Verdict: research
> plan (paper research, nothing live changed) - in 2026-like markets the fleet pays from mid-December and keeps $20-35k (4 accounts) or $29-54k (5 accounts) after fees, splits and the 30% tax pot in 6 months; in a 2021-25-like market it makes about $0 and most evals never pass.

**Full title:** Fleet plan - all 5 MFFU accounts on one Monte Carlo, month by month for 6 months

## Summary

One Monte Carlo of the owner's whole fleet on the SAME 5-session-block paths (tools/uprisk.mc_paths seed 23, 1,000 paths x 126 sessions = 2026-11-17 to 2027-05-13 per market), so the accounts are correlated the way they really are (same signals). Accounts - Zlarior Builder 50K eval from its real hole ($49,192.78, $3,807 to go, $1,025 room), funded LIT + ATLAS $500; ATLAS funded Builder 25K from $25,000 this week, ATLAS alone; a NEW Builder 25K eval ($63) LIT, funded LIT + ATLAS $250 (one-account rule); a NEW Rapid EOD 50K ($165) LIT + ATLAS $500, 30% guard, $1,000 cushion; the 5th slot = Rapid EOD 50K #2 bought once payouts in hand after the tax pot reach $165. Re-buy = the research slot logic (a failed eval is bought again at once, a lost funded starts a fresh eval). 6-month cash after fees, splits and 30% tax pot (mean, 5 accounts) $28,568 Jul-Oct-like / $54,349 Jan-Jun-like / $12 2021-25-like; 4 accounts $20,406 / $35,239 / $57. P(no payout by Jan 31) 6.2% / 3.1% / 76.4%. Cash to keep for buys + re-buys (p95) $320 / $320 / $1,363.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Runs: `none (research/lab/fleet_plan.json, tools/money/fleet_plan.py; page tools/web_public/business/plan.html + plan.json)`
- Source: `research/writeups/fleet-plan-2026-11-17.md`
- Back to [[ZEUS Home]]
