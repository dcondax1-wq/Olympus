---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-19"
status: "inducement-count size (option idm_size) is a candidate for the LIT size rule / funded only - on the eval path (two_week) it is rejected; every new entry type rejected"
source: "research/writeups/lit-new-entries.md"
aliases:
  - "LIT new entries and confluences"
---

# LIT new entries and confluences

> [!failure] Verdict: rejected
> inducement-count size (option idm_size) is a candidate for the LIT size rule / funded only - on the eval path (two_week) it is rejected; every new entry type rejected

**Full title:** LIT new entries and confluences - MSNR levels, inducement into order blocks, stacked confluence, confluence as size

## Summary

The owner asked for more LIT entry types and confluences (MSNR, IDM, build-ups, 15m order blocks, smart money trap, stacked setups) and 3+ trades a week. 362 variants on the exact live LIT, picked on Jan-Jun 2026 and checked on Jul-Oct 2026, scored in $ at the LIT size and on the MFFU 50K 2-week eval under the live two_week sizing. No new entry type adds money in both halves next to today's LIT. MSNR 15m support/resistance setups make money on their own (H1 PF 4.19 +$23.7k, H2 PF 2.65 +$8.6k), but most of them are the same days and moves as today's trades: added as a 2nd trade a day they cost $1.6k in Jan-Jun and push the Jul-Oct 2-week fails from 2.9% to 10.1%. SMC inducement into a 15m/1h order block gives 13 trades in 2026 and loses in Jan-Jun. Stacked confluence (2+ of OB, SMT, MSNR, 2+ inducements, build-up, major level, 4h storyline) on setups the live filters reject adds +$3.3k / +$0.6k but doubles the Jul-Oct 2-week fails. One sizing rule holds: trades whose sweep took 2+ inducements (within 2 ATR, 48 bars) earn 1.0-1.2 R against 0.0-0.2 R for the rest in Jan-Jun, Jul-Oct and 2021-25; 1.5x on those and 0.75x on the rest (risk capped at $990) makes H1 +$40.2k (vs +$32.5k) and H2 +$12.7k (vs +$8.9k), 2-week fails 9.2 -> 6.7% and 2.9 -> 0.0%, but drawdown is about 30% bigger. Paper only. On the real eval path (two_week 10 sessions then safe_eval, $1.90, true 1m; engine/sizing.py now applies the multiplier) it does not hold: H1 net -$0.5k, 2-week fails 9.2 -> 10.1%, H2 2-week pass 50.7 -> 49.3%, and on top of t_check + scale_in + be_off it costs $12.9k in H1. For the eval keep it off; the best eval combination stays t_check + scale_in + be_off.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-19]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_ent_base, lit_ent_idm_size, lit_ent_idm_size_up, lit_ent_ctrl_125, lit_ent_msnr15_alone, lit_ent_msnr15_add1, lit_ent_msnr15_add2, lit_ent_msnr1h_add2, lit_ent_msnr1h_all_add2, lit_ent_msnr15_qm_add2, lit_ent_msnrlit_15m, lit_ent_msnrlit_1h, lit_ent_idmob_add1, lit_ent_stack2_add2, lit_ent_stack`
- Source: `research/writeups/lit-new-entries.md`
- Back to [[ZEUS Home]]
