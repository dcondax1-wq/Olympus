---
tags:
  - zeus/research
  - family/bias
  - verdict/rejected
type: "research"
date: "2026-11-20"
status: "rejected"
source: "research/writeups/premarket-brief-2026-11-20.md"
aliases:
  - "Premarket brief"
---

# Premarket brief

> [!failure] Verdict: rejected
> rejected

**Full title:** Premarket brief - the "thinking before the trade" page data, and a pre-registered day bias that is no better than a coin

## Summary

tools/premarket_brief.py builds nq/brief.json (levels, gap, ATR, VIX/VXN band, Tier-1/2 news with what each bot does, each bot's window + setup + levels, recap). Two day-bias rules were pre-registered before measuring. B1 (overnight drift at 08:00) hit 47.1% of 442 days 2021-25, 59.4% of 69 (2026 H1), 44.6% of 56 (H2); B2 (fade yesterday) 49.7% / 47.7% / 39.8%. Neither beats a coin in all three periods, so the brief shows the call as context only.

## Links

- Family: [[Family bias]]
- Day: [[Day 2026-11-20]]
- Refers to: [[bias-filters|Bias, filters and timing]], [[hq-bias|HQ bias]], [[lit-bias-discretion|LIT with bias and discretion]]
- Runs: `[]`
- Source: `research/writeups/premarket-brief-2026-11-20.md`
- Back to [[ZEUS Home]]
