---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-20"
status: "rejected - nothing adopted; one lead (wider target on Power-of-3 days) kept as a default-off option for a forward paper check"
source: "research/writeups/lit-bias-discretion.md"
aliases:
  - "LIT with bias and discretion"
---

# LIT with bias and discretion

> [!failure] Verdict: rejected
> rejected - nothing adopted; one lead (wider target on Power-of-3 days) kept as a default-off option for a forward paper check

**Full title:** LIT with bias and discretion - 12 daily-bias methods, an A+ checklist and meta-labeling as size, target or filter

## Summary

The owner said "trading with bias and discretion - there's stuff you haven't tried". 1,842 variants on today's live LIT and on the adopt-candidate combo (t_check + scale_in + be_off), scored on the real MFFU 50K eval path (two_week for 10 sessions, then safe_eval, no reset, $1.90 a micro, true 1m), picked on Jan-Jun 2026 and checked on Jul-Oct. Twelve daily-bias methods were tested, all read before the entry (look-ahead test 8/8): the HTF draw to PDH/PDL/PWH/PWL, the previous day's close, premium/discount, Power of 3 / AMD, the ICT weekly profile, the midnight / 08:30 / 09:30 / 18:00 / weekly opens, the Asia direction, the previous day's displacement, the daily FVG/IFVG, 1H/4H/daily structure, NQ-ES SMT and a vote of five. Each was used as a size tilt, a target tilt and a filter. Size tilts do not work on the eval path (3 of 279 better in both halves): two_week sizes each trade so one winner passes, so a cut costs passes and a size-up hits the caps. Filters drop Jul-Oct below 2.5 trades a week and lose money (0 of 31). The A+ checklist score is not monotonic in Jul-Oct and is backwards in 2021-25. Meta-labeling has no skill out of sample (AUC 0.46-0.52, label-shuffle p 0.47-0.81). One family helps both halves: a farther target on days the bias agrees. Best: on Power-of-3 days (Asia low taken for a long, Asia high for a short), target x1.25 and no 8R bank. On the eval path it makes +$11.3k in H1 and +$3.1k in H2, and 2-week fails fall 9.2 -> 7.6% and 2.9 -> 0.0%. On the combo it makes +$17.2k / +$0.8k. Random trade sets of the same size do as well only 3% of the time. It is not adopted: the H2 gain rests on 4 trades, it was found in a follow-up after both halves had been seen, and on the combo its neighbours (x1.2, x1.3) lose money in H2. Engine option bias_tgt (default off) is ready for a forward paper check. Paper only.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[data-official|Official data only]]
- Runs: `lit_bias_ref_base, lit_bias_ref_all3, lit_bias_followup_amd_wide_1_25, lit_bias_all3_followup_amd_wide_1_25, lit_bias_followup_or_dpd_amd_wide_1_25, lit_bias_all3_followup_or_dpd_amd_wide_1_25, lit_bias_followup_amd_wide_1_3, lit_bias_followup_or_dpd_amd_wide_1_3, lit_bias_all3_followup_draw_pd_wide`
- Source: `research/writeups/lit-bias-discretion.md`
- Back to [[ZEUS Home]]
