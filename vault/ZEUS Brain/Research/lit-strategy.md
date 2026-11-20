---
tags:
  - zeus/research
  - family/other
  - verdict/finding
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "finding"
source: "research/writeups/lit-strategy.md"
aliases:
  - "LIT"
---

# LIT

> [!info] Verdict: finding
> finding

**Full title:** LIT (Liquidity Inducement Theorem) built as its own strategy, head to head with the Liquidity Engine

## Summary

Every LIT component the owner listed was built from CME NQ1! 5m data and backtested as a pure LIT strategy (none of the engine's rules). Taken raw, LIT breaks even (PF 0.97 in 2026, 1.01 in 2021-25). The best rule set (strong displacement + deep sweep + previous day/week/month targets) makes money in both periods (2026 PF 1.26, +$5.3k; 2021-25 PF 1.15, +$31.5k) and holds up in every check, but it is far behind the locked bot in 2026 (+$20.5k, PF 3.94). Its 21% losing-trade drawdown makes the MFFU 50K eval fail more often than it passes. Verdict: LIT does not beat the current bot. Five of the owner's components carry a small edge in both periods; the rest do not.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `baseline, lit_textbook_ny, lit_raw_day, lit_A, lit_B`
- Source: `research/writeups/lit-strategy.md`
- Back to [[ZEUS Home]]
