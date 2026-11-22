---
tags:
  - zeus/research
  - family/risk
  - verdict/research
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-17"
status: "candidate (owner decides; built OFF in engine/lit25.py) - faster first payout and a little more $ in both 2026 halves, but more 6-month no-payout paths in both halves and slightly worse in 2021-25."
source: "research/writeups/funded25-lit-atlas-2026-11-17.md"
aliases:
  - "ATLAS's funded Builder 25K"
---

# ATLAS's funded Builder 25K

> [!abstract] Verdict: research
> candidate (owner decides; built OFF in engine/lit25.py) - faster first payout and a little more $ in both 2026 halves, but more 6-month no-payout paths in both halves and slightly worse in 2021-25.

**Full title:** ATLAS's funded Builder 25K - ATLAS alone vs LIT + ATLAS $250 on the same account

## Summary

ATLAS's 25K eval passed (balance $26,946.10 on 2026-11-17, target $26,500). Funded 25K (MFFU Builder 25K funded rules = engine/funded_life builder25k - $1,000 EOD trailing, payouts above the $1,100 buffer, $250 min / $1,000 max, 80%, 50% consistency, 2 days a cycle, 5 payouts), a fresh funded start, 600 Monte Carlo paths of 126 sessions per half (builder_levers seeds), costs in, the live one-account rule (ATLAS skipped while LIT holds either side; LIT entering closes ATLAS at market, 1 tick: 38 skips + 84 cuts over 2021-26). First payout ask (median sessions) ATLAS alone 18 / 26 (H1 / H2) vs LIT + ATLAS $250 14 / 18; to the owner $592 / $497 vs $599 / $529 a month; no payout in 6 months 5.0 / 5.5% vs 7.5 / 12.2%; lost 0% everywhere. 2021-25 - $48 vs $35 a month, 78 vs 82% no payout. Reference - both at the 25K funded preset 13 / 14 sessions, $628 / $568, no payout 4.2 / 10.5%.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Runs: `none (research/lab/builder_funded25.json, tools/money/funded25.py)`
- Source: `research/writeups/funded25-lit-atlas-2026-11-17.md`
- Back to [[ZEUS Home]]
