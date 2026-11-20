---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "one small adopt-candidate (breakeven stop at entry + costs); everything else rejected or not testable"
source: "research/writeups/lit-adv-management.md"
aliases:
  - "LIT advanced management"
---

# LIT advanced management

> [!success] Verdict: adopt-candidate
> one small adopt-candidate (breakeven stop at entry + costs); everything else rejected or not testable

**Full title:** LIT advanced management - breakeven versus recoveries, partials at the first obstacle, target choice by location and deadline, and a target that trades before the fill

## Summary

The owner's LIT Advanced Decisions Report (chapters 6, 8, 9, 10 and experiments 2-3 of chapter 13) was tested on the exact live LIT trades of 2026 (true 1m bars, live sizing two_week for 10 sessions then safe_eval, $1.90 commission, no reset), each idea alone and on top of the 15-minute early-loss check (t_check). Breakeven at 1R stays. It removes about 1 recovery for every 7 full losses it saves (H1 3 of 29 breakeven trades would have gone on to the target; H2 0 of 5), which is below the 13% break-even recovery rate, and without it 2-week fails jump (H1 9.2% to 13.4%, H2 2.9% to 7.2%). Moving the breakeven later (1.5R, 2R), to structure (a new 1m/5m swing, price leaving the mitigation area) or holding it while the zone's 50% is untouched does not hold in both halves. Partials at the first obstacle cost a lot, because LIT's sizing needs the whole target to pass the eval with one winner (2-week pass H1 52.9% to 22-50%). Nearer targets from the entry location, the day's range or a time deadline help H1 only. A target that trades before the fill happened once in 2026: not testable. The one change that helps both halves is small and mechanical. Put the breakeven stop at entry + 1.25 pts (5 ticks = $1.90 commission + 1 tick of exit slippage) instead of at the entry. It changed no exit in 2026, and each breakeven exit then nets about $0 instead of about -$2.40 a micro. H1 +$681, H2 +$80 on the eval path, 2-week pass unchanged (52.9 / 50.7), H1 2-week fails 9.2% to 8.4%. With the 15-minute check: H1 +$928, H2 +$20, H1 fails 6.7% to 5.9%. Engine option be_off (default 0 = today). Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_adv_base, lit_adv_base_t15, lit_adv_be_costs, lit_adv_be_costs_t15, lit_adv_be_off_1, lit_adv_be_off_2, lit_adv_be_pend_ob50, lit_adv_be_pend_ob50_t15, lit_adv_be_sw5, lit_adv_be_sw5_t15, lit_adv_be_1p5r, lit_adv_no_be, lit_adv_no_be_t15, lit_adv_part_leg_third, lit_adv_part_struct_half_be_after`
- Source: `research/writeups/lit-adv-management.md`
- Back to [[ZEUS Home]]
