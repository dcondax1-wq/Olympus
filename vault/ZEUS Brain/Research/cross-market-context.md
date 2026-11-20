---
tags:
  - zeus/research
  - family/filters
  - verdict/adopt-candidate
type: "research"
date: "2026-10-17"
status: "adopt-candidate"
source: "research/writeups/cross-market-context.md"
aliases:
  - "Cross-market and regime context"
---

# Cross-market and regime context

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** Cross-market and regime context: does the market around the setup matter?

## Summary

Mostly no. VIX level and change, the VXN/VIX ratio, dealer gamma (GEX), NQ-vs-ES relative strength, SMT divergence and the shape of the entry day do not split trades in a way that holds in both 2026 and 2021-25; 25 of 32 size rules were rejected. One small thing does hold: when BOTH the 10-day and the 20-day trend reading say "trending" (12 trades in 2026, 75 in 2021-25), the reversal loses money in every period; half size there adds +$378 in 2026 (PF 3.94 to 4.16, drawdown -$2,249 to -$1,871) and +$677 in 2021-25 (PF 1.27 to 1.29). The bigger lead is that the 20-day trend test picks the bad days better than the live 10-day test (swap: 2026 +$2.1k, 2021-25 +$5.6k, but more 1-month eval fails); it needs an engine option and a longer live data window before it can be tested exactly.

## Links

- Family: [[Family filters]]
- Day: [[Day 2026-10-17]]
- Runs: `xm_both_trend_half, xm_both_trend_quarter, xm_er20_swap_45, xm_er20_only, xm_er20_45_half, xm_er20_trend_half, xm_vix20_half, xm_vixup5_half, xm_vixup5_x125, xm_vxnvix_hi_half, xm_vxnvix_lo_half, xm_vxn_mid_half, xm_gexneg_half, xm_gexneg_x125, xm_gexlow_half, xm_rangedone_half, xm_rangedone_x125, x`
- Source: `research/writeups/cross-market-context.md`
- Back to [[ZEUS Home]]
