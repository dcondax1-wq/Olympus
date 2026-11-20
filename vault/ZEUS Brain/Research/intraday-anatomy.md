---
tags:
  - zeus/research
  - family/timing
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/intraday-anatomy.md"
aliases:
  - "Intraday anatomy"
---

# Intraday anatomy

> [!info] Verdict: finding
> finding

**Full title:** Intraday anatomy: when, how and where the bot's trades make or lose money

## Summary

The clock does not decide the trade (every hour and weekday flips between 2026 and 2021-25); what the trade is made of does. CISD triggers beat IFVG triggers in both periods (2026 PF 5.7 vs 2.4, 2021-25 PF 1.53 vs 1.11), 30-40 pt stops and equal-highs/lows targets lose money in both. Halving the 30-40 pt stops is the one clean small win (2026 +$413, 2021-25 +$115, max drawdown -$9.3k to -$8.1k, 1-month eval fails 5.2% to 4.0%); adding CISD x1.25 and half size on equal-highs targets makes 2026 +$3.7k and 2021-25 +$1.4k with less drawdown in both, but it is three in-sample slices stacked, so it needs a critic before Sunday.

## Money first

Adopt-candidates: `intra_stop3040_half` (small, clean, defensive) and `intra_combo_all` (the package). Both pass the
owner's rule (better net and PF in 2026 and 2021-25, 2-4 trades a week kept, no more eval fails). But be honest about
what they are: three slices picked from this same data because they looked good in it, then stacked. The CISD edge is
the most believable (5 of 6 years, random groups rarely match it), the 30-40 pt stop next (4 of 6 years), the equal-highs
target the weakest (3 of 6). The 2021-25 money gain of the package is $1.4k over five years, about $23 a month; the
drawdown and eval-fail improvements are the real argument. If only one is taken, take the stop rule; if the critic agrees,
the package. Neither changes a single entry or exit, so Pine and the engine need only a size multiplier.

What failed: every timing rule (the only two that looked good in both periods, 09:30 x1.25 and 10:00 x0.5, are leverage or
flip in 2021-25), halving the under-2R targets, halving IFVG triggers, and every weekday/hour cell.

## Links

- Family: [[Family timing]]
- Day: [[Day 2026-10-17]]
- Refers to: [[calendar-effects|Calendar and seasonality]]
- Runs: `baseline, intra_cisd_125, intra_ifvg_half, intra_stop3040_half, intra_tgt_eq_half, intra_open_125, intra_h10_half, intra_rr2_half, intra_combo_defensive, intra_combo_all`
- Source: `research/writeups/intraday-anatomy.md`
- Back to [[ZEUS Home]]
