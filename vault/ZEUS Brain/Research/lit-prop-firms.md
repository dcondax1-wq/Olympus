---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
  - lane/rapid
type: "research"
date: "2026-10-18"
status: "info"
source: "research/writeups/lit-prop-firms.md"
aliases:
  - "LIT on every prop firm"
---

# LIT on every prop firm

> [!note] Verdict: info
> info

**Full title:** LIT on every prop firm - which account, which size, and what a Monday start on the MFFU 25K Builder or Rapid looks like

## Summary

The current rules of 60 futures prop-firm plans (MyFundedFutures Builder, Rapid, Rapid EOD and Pro; Topstep, Apex, Tradeify, Lucid, Take Profit Trader, Alpha Futures, FundedNext, Bulenox; every size) were run on the exact live LIT trades of 2026 with the eval sizing scaled to each plan's max loss. One rule decides almost everything for LIT: a best-day consistency rule in the eval. Plans without one (MFFU Builder, Lucid Pro, Tradeify Growth, FundedNext Rapid, Bulenox, Apex, Alpha Zero) pass 24-48% of evals within 2 weeks; plans with one (MFFU Rapid 50%, Rapid EOD 30%, Topstep 55%, Take Profit Trader, LucidFlex, Tradeify Select, FundedNext Legacy, Alpha Standard) pass 0-7%. A Monday start on the MFFU 25K Builder passed 34% of 2026 Monday starts within 2 weeks (H2 27%) but failed 17% within a month and 37% in the end, because 1 micro on a 60-88 point stop is too big for a $1,000 max loss; the 50K Builder passes at the same speed and fails 5% within a month (H2 0%). The MFFU Rapid passes 5% within 2 weeks at any size. Top picks for LIT: MFFU Builder 50K (keep), Lucid Pro 50K, FundedNext Rapid Daily. Paper only; rules read through search results on 2026-10-18 and partly unconfirmed.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]], [[Rapid lanes]]
- Refers to: [[eval-game|The eval game]]
- Runs: `lit_live`
- Source: `research/writeups/lit-prop-firms.md`
- Back to [[ZEUS Home]]
