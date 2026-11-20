---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-27"
status: "rejected"
source: "research/writeups/b-holds-vs-lit-priority.md"
aliases:
  - "B-holds vs LIT priority"
---

# B-holds vs LIT priority

> [!failure] Verdict: rejected
> rejected

**Full title:** B-holds vs LIT priority - when ATLAS is in a trade and LIT signals the other way, who gives way?

## Summary

Owner (2026-10-27) - "If ATLAS is in a trade and its target is clear it should hold, and not let Zlarior trade?" Today ATLAS went long at 03:30 (MACD, hit its 8R target at 06:48, +$1,662 at 3 micros) and LIT shorted at 06:12. The live rule (LIT priority) closed ATLAS at market (+$525) and LIT was stopped (-$965). B-holds would have made +$1,662 that day instead of -$440. Over the backtest this kind of clash is rare - 9 times in 2026 (about once a month) and 35 times in 2021-25. Both accounts together, B-holds makes +$1,221 more in 2026 (+$1,031 H1, +$190 H2) but -$1,823 less in 2021-25, and it lowers ATLAS's 2-week pass rate in 2026 H1 from 65.5% to 60.5%. It is not better in both periods, so it is not adopted. LIT priority stays. Trades a week stay at 2-4 with either rule.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-27]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Runs: `bholds_lit_priority_lit, bholds_lit_priority_b, bholds_b_holds_lit, bholds_b_holds_b`
- Source: `research/writeups/b-holds-vs-lit-priority.md`
- Back to [[ZEUS Home]]
