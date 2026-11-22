---
tags:
  - zeus/research
  - family/bias
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/bias-filters.md"
aliases:
  - "Bias, filters and timing"
---

# Bias, filters and timing

> [!info] Verdict: finding
> finding

**Full title:** Bias, filters and timing: which trades to take, and how big

## Summary

Two simple biases separate trades in both periods: fading yesterday's candle and trading on the side of last week's midpoint. As filters or score points they cut trades below 2 a week and the replacement trades lose; as a size-down (70% size when both disagree) they raise PF in both periods (2026 3.48 → 3.62, 2021-25 1.09 → 1.12) and cut 2021-25 drawdown, for −$0.75k in 2026. No filter or timing change beats today's rules.

## Money first

- No bias, filter or timing change is recommended for Sunday.
- The two new biases (yesterday's candle, prior-week side) are real enough to keep researching as a **size**
  rule: "70% size when both disagree" is the best balance found (PF up in both periods, 2026 −$0.75k).
- Never use them as filters or score points: frequency falls under 2 a week and the replacement trades lose.

## Links

- Family: [[Family bias]]
- Day: [[Day 2026-10-17]]
- Runs: `baseline, screen_baseline, flt_vix20_half, flt_vix20_07, bias_pdc_half, bias_pwmid_half, bias_any_half, bias_both_half, bias_both_07, bias_both_033, bias_pdc_07, bias_pwmid_07, bias_pdc_skip, bias_pwmid_skip, bias_wkopen_skip, bias_draw_skip, bias_draw_half, bias_smt_only, bias_pdc1, bias_pwmid1, bi`
- Source: `research/writeups/bias-filters.md`
- Back to [[ZEUS Home]]
