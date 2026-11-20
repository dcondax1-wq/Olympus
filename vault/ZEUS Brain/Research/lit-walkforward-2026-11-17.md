---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-11-17"
status: "rejected - re-tuning makes more in 2022-25, but the gain is inside the noise, mostly 2025 alone, and random re-picks do almost as well; it loses in both 2026 halves in all 8 versions. 2023 loses at ..."
source: "research/writeups/lit-walkforward-2026-11-17.md"
aliases:
  - "LIT walk-forward re-tuning"
---

# LIT walk-forward re-tuning

> [!failure] Verdict: rejected
> rejected - re-tuning makes more in 2022-25, but the gain is inside the noise, mostly 2025 alone, and random re-picks do almost as well; it loses in both 2026 halves in all 8 versions. 2023 loses at every one of the 27 settings, so the weak years are not a tuning problem. Paper only, nothing live changed.

**Full title:** LIT walk-forward re-tuning (2026-11-17) - re-fit LIT's knobs every month / quarter on the trailing 6 / 12 months, trade the next period out of sample, 2022-05 to 2026-10

## Summary

LIT was tuned on 2026 Jan-Jun and makes about $0 in 2021-25. Test - does a LIT that re-tunes itself (walk-forward) make money in the old years too? Grid of 27 points (displacement 0.7 / 0.8 / 0.9 ATR, breakeven at 1R / 1.5R / off, target banked at 5R / 8R / 12R; the knobs that moved $ most in a one-at-a-time scan). Each point is a full engine/lit.py backtest with costs. Eight versions (refit monthly or quarterly, trailing 6 or 12 months, score = net minus max drawdown, or PF with at least 1.5 trades a week). Monthly / 12 months / net-minus-DD was named the main one before looking. Every trade is out of sample (2022-05 to 2026-10), re-sized after splicing (LIT size rule, live Builder eval path two_week room_f 0.4 to session 80, Rapid EOD LIT lane). Main version - 2022-25 +$23,095 (PF 1.19, $511 a month) vs static +$710. The +$22.4k gain is 1.3 standard errors and +$26.3k of it is 2025 (2023 and 2024 are worse than static). A random setting at each refit makes +$4.7k (median); the main version beats 93.5% of random draws (95% needed), and the other 7 versions beat only 44-83%. 2026 - Jan-Jun +$22,867 vs +$33,901 (-$11.0k), Jul-Oct +$6,909 vs +$9,919 (-$3.0k); every version loses in both halves (-$9.5k to -$15.6k / -$1.7k to -$7.8k). Stability - the main version changes setting at 13 of 53 refits and picks today's setting at only 1 of 54. 2023 loses money at all 27 settings (best -$6.6k), so no re-tuning of these knobs fixes the bad years. They look like a regime LIT does not trade well, not a fit to 2026. Nothing adopted.

## Money first

1. **Beat static in 2022-25 out of sample:** yes on the raw number in all 8, but **no version is clear of the noise.** The main
   version's gain is 1.3 s.e., beats 93.5% of random re-picks (not 95%), and 2025 alone is +$26.3k of the +$22.4k. In 2023
   and 2024 it does worse than static. The other 7 versions beat random re-picks only 44-83% of the time.
2. **Not worse in 2026 H1 / H2 by more than noise:** the main version is -$11.0k (1.2 s.e.) and -$3.0k (1.3 s.e.). Every
   version is worse in **both** halves, and four of them by about 2 s.e. in a half. That pattern is not noise.
3. **Stability:** the main version changes setting at 13 of 53 refits (mostly the target bank 5R / 8R / 12R: 9 changes; BE 4;
   displacement 3). It picks today's setting at only 1 of 54 months. Its favourites are "BE off / bank 12R" (18 months),
   "BE 1.5R / bank 8R" (10) and "BE off / bank 5R" (10). Quarterly / 6 months flips at 16 of 17 refits (noise chasing).

**Rejected.** Re-tuning these knobs does not insure against a regime change. The bad years stay bad (2023 loses at all 27
settings: worst -$30.1k, median -$17.2k, best -$6.6k; 2024 is positive at only 9 of 27). The good years (2022, 2025, 2026)
are good at almost every setting (2022: 27/27 positive, 2025: 26/27). So the years differ by **market regime, not by
knobs**. A re-tuner can only lag behind: it learns "BE off" from 2024-25 and pays for it in 2026, when BE at 1R was right.
One useful fact for later: today's knobs are among the weakest in 2022-25 (rank 18 of 27). The cheaper insurance question
is *when not to trade* (a regime filter), not *how to re-tune*. The drift switch and the 6 bias / regime studies already
tried that without success (see "Tested and rejected").

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[rapid-levers-2026-11-16|Rapid EOD 50K levers]]
- Runs: `none saved (research/lit/wf_retune.json, tools/lit_wf_retune.py)`
- Source: `research/writeups/lit-walkforward-2026-11-17.md`
- Back to [[ZEUS Home]]
