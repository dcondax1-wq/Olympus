---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
type: "research"
date: "2026-10-17"
status: "adopt-candidate"
source: "research/writeups/trade-construction-summary.md"
aliases:
  - "Trade construction"
---

# Trade construction

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** Trade construction: what to change before Sunday

## Summary

One change is worth making, together with the sizing change: on trending days move the stop to breakeven at +3R instead of +1R. With the sizing change it adds +$4.8k to 2021-25 (PF 1.19 → 1.27) and changes nothing in 2026 evals; on today's sizing alone it causes extra late-May 2026 eval fails, so then keep the current rules. Stops, targets, the other exits, filters and timing are already at their best; 120+ variants tested, no leak found.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-17]]
- Refers to: [[bias-filters|Bias, filters and timing]], [[leakage-check|Leakage check]], [[management|Managing the trade]], [[risk-summary|Risk summary]], [[stops|Stops]], [[targets|Targets]]
- Runs: `baseline, mgt_betrend300_replay, mgt_betrend300, mgt_betrend250, mgt_betrend_off, combo_risk_sizing, combo_betrend3_risksizing, bias_both_07, combo_betrend3_both07, combo_betrend3_bothhalf, flt_vix20_half, stp_max80, stp_atr015_replay, tgt_maxrr8_replay, leak_both_off`
- Source: `research/writeups/trade-construction-summary.md`
- Back to [[ZEUS Home]]
