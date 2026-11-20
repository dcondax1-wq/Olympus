---
tags:
  - zeus/research
  - family/management
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-28"
status: "rejected"
source: "research/writeups/lit-reversal-exit.md"
aliases:
  - "LIT reversal exits"
---

# LIT reversal exits

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT reversal exits - get out on a violent reversal, trail after 0.5-1R, breakeven near 1R, stop at the first highs (after the first live trade)

## Summary

The first real live LIT trade (2026-10-28, short 5 MNQ at 29,945) went 0.95R in our favour, then four big green 1m candles took it to the full stop (-$437). The owner asked for discretion, so 103 variants were tested on the exact live LIT trades (true 1m bars in 2026, 5m in 2021-25). None makes more money in both halves of 2026, so nothing changes in the bot. Every rule that would have saved today's trade also cuts real winners, because LIT winners also snap back hard after +0.5-1R before they run to the target. Exit on a big reversal candle after +0.9R: today +$168 instead of -$437, but 2026 H1 -$9,082 and H2 -$2,317 (6 + 6 winners cut, 0 losers saved). A 1m swing trail after +0.9R: H1 -$19,171, H2 -$8,713. Breakeven at 0.9R: today $0, H1 -$931, H2 -$579. A stop at the first 1m highs (27 pts today, 7 micros): today breakeven, H1 +$29,330 but H2 -$13,147, PF 0.75, and 47% of evals fail within 2 weeks. In all of 2026 no trade before today went 0.9-1R and then hit the full stop, and only 4 went 0.75-0.9R and then stopped (-$917 in total). Today's trade is rare; the rules that fix it cost every month. Paper only.

## Links

- Family: [[Family management]]
- Day: [[Day 2026-10-28]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-1m-management|LIT on the 1-minute chart]], [[lit-adv-management|LIT advanced management]], [[lit-tight-stops-size|LIT tight stops and bigger size]], [[lit-untested-stops|LIT untested stop ideas]]
- Runs: `lit_rev_base, lit_rev_bar_k09_m2_exit, lit_rev_bar_k05_m3_exit, lit_rev_run2_k075_m2_be, lit_rev_run2_k09_m2_be, lit_rev_retr_k09_g05_exit, lit_rev_retr_k075_g075_be, lit_rev_trail1m_k09, lit_rev_trail5m_k09, lit_rev_be09, lit_rev_be075, lit_rev_tight1m_same, lit_rev_tight5m_cap8`
- Source: `research/writeups/lit-reversal-exit.md`
- Back to [[ZEUS Home]]
