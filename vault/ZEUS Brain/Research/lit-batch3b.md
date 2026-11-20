---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
  - lane/combo50k
type: "research"
date: "2026-10-20"
status: "no adopt-candidate; one promising target idea (FVG extension, live LIT only); the combo is robust to slippage and commission, sensitive to a late entry, and sits on a plateau (the 15-min check time ..."
source: "research/writeups/lit-batch3b.md"
aliases:
  - "LIT batch 3b"
---

# LIT batch 3b

> [!success] Verdict: adopt-candidate
> no adopt-candidate; one promising target idea (FVG extension, live LIT only); the combo is robust to slippage and commission, sensitive to a late entry, and sits on a plateau (the 15-min check time is the sharp knob)

**Full title:** LIT batch 3b - ES confirmation, NQ/ES strength, structure breakeven, 10:00 day type, Asia / London range, news days, seasonality, FVG targets, stop-scaled target; robustness and stability of the combo

## Summary

Ten new ideas (about 1,850 variants) were tested as size tilts or management tweaks on today's live LIT and on the adopt-candidate combo (t_check + scale_in + be_off). Scoring used the real eval path (two_week for 10 sessions, then safe_eval, no reset, $1.90 a micro, true 1m). Picked on H1 2026, checked on H2. None passed the strict test on both references. The closest is an FVG target extension: when the VIX-band target sits below an untouched opposite 5m FVG from today or yesterday, aim for the FVG. On live LIT it passes the strict test, holds at its neighbours and changes 6 / 5 trades: eval +$887 / +$7,045, LIT rule +$1,591 / +$1,186. On the combo it gains on the LIT rule (+$1.9k / +$1.8k) but loses -$4.1k on the H1 eval path, so it stays promising, not adopted. ES confirmation is not information: ES takes its matching level within 5 minutes on 88 of 120 trades. Structure breakeven costs $2-32k per half. The 10:00 day read and the stop-scaled target change only 1-6 trades. Robustness: on the LIT size rule the combo keeps 95-96% of its $ at +2 ticks on every fill and 99% at commission +50%. A random 20% of missed fills keeps 81-83%. A 1-minute late entry is the weak spot: H2 falls to 53% on the LIT rule (11% on the eval path), almost all from one trade. Stability: every one-step neighbour of the combo beats live in both halves on the LIT size rule (9 of 11 on the eval path; 550 of 1,215 grid points). The check time of 15 min is the one sharp knob. A walk-forward (3-month pick, next month) does not beat the fixed pick: +$35.1k vs +$36.1k on the LIT rule, Apr-Oct.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]], [[50K combo]]
- Refers to: [[lit-adv-audit-smt|LIT advanced report ch.7 audit]], [[lit-live-fills|LIT live fills]], [[lit-market-context|LIT market context]]
- Runs: `lit_b3b_fvg_fvg_target_2day_far_edge_0_0_atr_far, lit_b3b_fvg_fvg_target_2day_near_edge_0_0_atr_far, lit_b3b_fvg_fvg_target_2day_mid_edge_0_0_atr_far, lit_b3b_fvg_all3_fvg_target_day_near_edge_0_25_atr_far, lit_b3b_es_conf_es_took_its_copy_within_60_min_unconf_x1_25, lit_b3b_es_conf_all3_es_took_its`
- Source: `research/writeups/lit-batch3b.md`
- Back to [[ZEUS Home]]
