---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
type: "research"
date: "2026-10-21"
status: "info (no rule change)"
source: "research/writeups/lit-robust.md"
aliases:
  - "LIT performance checks"
---

# LIT performance checks

> [!note] Verdict: info
> info (no rule change)

**Full title:** LIT performance checks - is live inside the expected range, how robust is the live config, exit efficiency, a monthly walk-forward and a look-ahead audit of every stored run

## Summary

Seven read-only checks from the competitor-features list (#6, 7, 9, 11, 12, 13, 14) now run on the live LIT and show on a new Performance page (PC Data > Performance, phone Money > Performance). Expected range - a bootstrap of the 2026 H2 sessions of run lit_live gives the band for N sessions; after 10 sessions the 90% band is -3.7R to +13.0R (median +3.0R) and -$1.8k to +$5.3k on the eval path, 3-8 trades. Robustness of the live config on 2026 (LIT size rule, base +$43,385 PF 4.07) - prices +/-1 tick on every 5m and 1m bar keep 92% of the $ (50 copies, p10-p90 83-100%, all profitable), +/-2 ticks 85%, random 0-3 ticks of slippage on every fill 98%, 10% / 20% of trades missed at random 90% / 80%, a 1-minute late entry 92% (H1 81%, H2 129%), 2 minutes late 68% (H2 37%): a late entry is the weak spot, as batch 3b found for the combo. All stresses together keep 76%. Exit efficiency - 2026 trades kept 48% of all the open profit they saw; the 66 that reached +1R kept 62% of their best move and gave back 1.3R on average (35 ended at breakeven). Walk-forward - re-picking 6 knobs (729 points) every month on all months before made +$29.3k Feb-Oct vs +$33.3k for the fixed live config; it won 3 of 9 months, so keep the config fixed. Look-ahead audit - 499 LIT runs, 1,472 top trades re-built on data cut at the entry bar: 0 changed, 0 flagged (64 runs need a research executor and were skipped).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-21]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_robust_noise1, lit_robust_noise2, lit_robust_slip03, lit_robust_miss10, lit_robust_miss20, lit_robust_delay1, lit_robust_delay2, lit_robust_worst, lit_live`
- Source: `research/writeups/lit-robust.md`
- Back to [[ZEUS Home]]
