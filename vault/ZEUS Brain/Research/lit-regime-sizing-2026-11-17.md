---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-11-17"
status: "rejected - no regime separates LIT's R a trade the same way in Jan-Jun, Jul-Oct and 2021-25; today's flat LIT size stays"
source: "research/writeups/lit-regime-sizing-2026-11-17.md"
aliases:
  - "LIT regime sizing"
---

# LIT regime sizing

> [!failure] Verdict: rejected
> rejected - no regime separates LIT's R a trade the same way in Jan-Jun, Jul-Oct and 2021-25; today's flat LIT size stays

**Full title:** LIT regime sizing (2026-11-17) - bigger / smaller LIT size by the day's regime - dealer gamma, VIX level and change, VXN-VIX spread, VIX term, prior day's range

## Summary

Night helper 2026-11-17 (night-gex). Each live LIT trade (631, 120 in 2026, costs in) tagged with the regime known before the session (prior close) - SqueezeMetrics GEX sign and level, VIX level and 1-day change, VXN minus VIX, VIX/VIX3M, the prior NQ session's range percentile. 124 bucket cells (37 definitions: 2-3 buckets per feature, 2x2 pairs, cut points from Jan-Jun 2026 trades only, plus 8 cells with VIX / spread as a trailing-year percentile). The best Jan-Jun splits flip in Jul-Oct (VIX falling days +1.09R vs +0.61R in Jan-Jun, +0.14R vs +1.24R in Jul-Oct; low VXN-VIX spread +1.02R vs +0.48R in Jan-Jun, but Jul-Oct has 2 such trades and 2021-25 is the other way). 8 size rules (x1.25 good / x0.75 bad, same $ caps, eval two_week room_f 0.4 kept to session 80, funded 50K Monte Carlo, 200-draw placebo): one passes the money gate (VIX/VIX3M high x prior-day range: +$37 / +$119 a month at the LIT size, funded +$10 / +$28 a month) but its Jan-Jun gain is chance (placebo 0.53), its Jul-Oct sizes rest on 5 + 2 trades, VIX3M data ends 2026-09-17, 2021-25 goes the other way and the Jan-Jun 2-week eval pass drops 44.5 -> 42.0%. Rejected. Rapid EOD not run (no candidate). Paper only.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-edge-2026-10-30|Zlarior edge night]], [[lit-market-context|LIT market context]]
- Runs: `none saved (grid in research/lit/regime_size.json, research/lit/regime_size_pct.json)`
- Source: `research/writeups/lit-regime-sizing-2026-11-17.md`
- Back to [[ZEUS Home]]
