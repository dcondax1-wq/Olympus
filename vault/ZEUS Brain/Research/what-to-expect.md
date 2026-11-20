---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/what-to-expect.md"
aliases:
  - "What to expect"
---

# What to expect

> [!info] Verdict: finding
> finding

**Full title:** What to expect: streaks, drawdowns, flat months and the odds inside a 2-week eval

## Summary

The locked strategy wins 1 trade in 4-5 and loses or scratches the rest, so long runs without a winner are normal: 33 trades in a row without a win happened once (Sep-Nov 2025, -$3,126), and 2026 had 16 (Apr-May, -$1,667). A loss does not make the next trade worse (after a loss +0.02R, after a win -0.01R in 2021-25, p=0.79), so sitting out or halving the trade after a max-size loss loses money in both periods (rejected). Most months lose a little (median month -$184 over 5 years, 40% of months positive; 2026 median +$1,162, 50% positive); 13 trades made the whole 5-year profit. In a 2-week eval expect 4+ non-winners in a row in about half of the starts (2021-25 58%, 2026 27%), a $1,000 dip in 12% (2026 1%), a $2,000 dip in 1%.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-17]]
- Refers to: [[monte-carlo-evals|Monte Carlo of the MFFU 50K eval]], [[risk-summary|Risk summary]]
- Runs: `baseline, seq_after_fullstop_skip, seq_after_fullstop_half, seq_after_big500_skip, seq_after_big500_half, seq_after_big300_half, seq_after_stop_half, seq_after_loss_half, seq_after_loss_150`
- Source: `research/writeups/what-to-expect.md`
- Back to [[ZEUS Home]]
