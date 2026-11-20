---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-11-17"
status: "rejected - nothing adopted, nothing built, nothing live changed"
source: "research/writeups/public-strategies-2026-11-17.md"
aliases:
  - "Famous published strategies on CME NQ"
---

# Famous published strategies on CME NQ

> [!failure] Verdict: rejected
> rejected - nothing adopted, nothing built, nothing live changed

**Full title:** Famous published strategies on CME NQ - none beats LIT, none passes an MFFU eval in a way we can trust

## Summary

Owner 2026-11-17 - "find other people's strategies that are successful and replicate them." Seven famous strategies with published multi-year records, coded the way their authors describe them (no tuning), plus at most 2 variants each - 22 cells, each scored on 2021-25, 2026 H1 and 2026 H2 (66 span cells), costs in. Gao intraday momentum, pre-FOMC drift, turn of the month, overnight drift, Connors RSI(2), time-series momentum (12-month and 20/60-day), Crabel NR7 / NR4. None makes money in all three spans with a t-stat above 1.2 except chance-level cells. The four that look best on paper (pre-FOMC, RSI(2), 12-month trend, overnight drift) all hold positions overnight, which MFFU does not allow (flat by 16:10 ET), and every one of them lost money in 2026 H2 or in 2021-25. The MFFU-legal versions lose or are no better than random days (turn-of-month day trades: placebo p 0.12-0.24). Daily correlation with LIT is about 0 for all of them, but there is no money to diversify with. LIT stays the only strategy.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[quant-anomalies|Quant anomalies on CME NQ]]
- Runs: `(no rl runs) research/quant/pub_strats.json`
- Source: `research/writeups/public-strategies-2026-11-17.md`
- Back to [[ZEUS Home]]
