---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-20"
status: "rejected (no adopt-candidate)"
source: "research/writeups/lit-batch3a.md"
aliases:
  - "LIT batch 3a"
---

# LIT batch 3a

> [!failure] Verdict: rejected
> rejected (no adopt-candidate)

**Full title:** LIT batch 3a - ICT macros, volume, delta, sweep rejection, speed, level age / touches, equal highs-lows, round numbers, level type, consecutive-day sweeps

## Summary

13 setup-quality ideas were tested on today's live LIT trades and on the adopt-candidate combo (t_check + scale_in + be_off), as size tilts, fitted size weights, filters (only if 2026 keeps >= 2.5 trades/week) and, for equal highs/lows, as extra LIT levels. About 1,800 variants, judged on the real MFFU 50K eval path (two_week for 10 sessions, then safe_eval, no reset, $1.90 a micro, true 1m), pick on H1 (Jan-Jun 2026), check on H2 (Jul-Oct 16). None passed the strict test (net $ up in both halves, no rise in 2-week fails, neighbours hold, enough trades, beats flat leverage), on either reference. The best money idea, a 1.5x size when the fill lands within 10 minutes of an ICT macro window, adds +$7.1k / +$2.3k on live LIT but loses -$8.8k in H1 on top of the combo, loses in 2021-25 and nudges the Monte Carlo fail rate up. Round numbers (a swept level within ~8 pts of a 00/50 handle, 1.5x) add money in H1, H2 AND 2021-25 under the LIT size rule and beat flat leverage there, but lose on the eval path; it is noted for a future funded sizing only. Equal highs/lows are already LIT levels (build-ups): removing them costs -$14k in H1, looser or tighter detectors lose; today's detector stays. Filters all cost money and most drop below 2.5 trades/week. Nothing changes in live_model.json.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-funded-sizing|LIT funded sizing]], [[lit-htf-confluences|LIT higher-time-frame confluences]]
- Runs: `lit_b3a_01_mac_fill_w10_x1_5, lit_b3a_02_rv_ext3_q0_67_1_349_lo_x1_5, lit_b3a_03_rv_disp_q0_67_1_381_lo_x1_5, lit_b3a_04_dl_ext3_q0_2_0_1743_hi_x1_25_lo_x0_75, lit_b3a_05_rj_back_x0_5, lit_b3a_06_sp_ext_q0_67_5_93_hi_x1_5, lit_b3a_07_age_h_q0_2_2_083_lo_x1_5, lit_b3a_08_tc2_q0_5_3_5_lo_x1_5, lit_b3a`
- Source: `research/writeups/lit-batch3a.md`
- Back to [[ZEUS Home]]
