---
tags:
  - zeus/research
  - family/filters
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/vwap-volume-profile.md"
aliases:
  - "VWAP and volume profile as confluence"
---

# VWAP and volume profile as confluence

> [!info] Verdict: finding
> finding

**Full title:** VWAP and volume profile as confluence

## Summary

None of 24 VWAP and volume-profile ideas made the live strategy better in both 2026 and 2021-25 when used to size trades up or down (every trade still taken, 2.2 and 3.2 trades a week). The only raw pass, 1.25x size on days that open inside yesterday's value area (2026 PF 3.50 vs 3.48, 2021-25 PF 1.10 vs 1.09), fails the robustness checks, so the live strategy stays as it is.

## Links

- Family: [[Family filters]]
- Day: [[Day 2026-10-17]]
- Runs: `baseline, vp_balance_cold, vp_balance_half, vp_balance_skip, vp_balance_up, vp_balance_up110, vp_balance_up150, vp_balance_va60_up, vp_balance_va70_up, vp_balance_va80_up, vp_dev_poc_side_cold, vp_dev_poc_side_half, vp_dev_poc_side_skip, vp_dev_poc_side_up, vp_naked_between_cold, vp_naked_between_ha`
- Source: `research/writeups/vwap-volume-profile.md`
- Back to [[ZEUS Home]]
