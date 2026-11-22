---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-adv-continuation.md"
aliases:
  - "LIT advanced report ch2-4"
---

# LIT advanced report ch2-4

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT advanced report ch2-4 - thesis boundary, session carryover, weak reactions, ES same event, owner's session and inducement notes

## Summary

The owner's LIT Advanced Decisions Report (chapters 2-4, experiment 4 of chapter 13) and his LIT group's session / Smart Money Trap / inducement notes became 176 variants on the 2026 LIT path, each picked on Jan-Jun and checked on Jul-Oct, under the live two-week eval sizing. Nothing is adopted. Four variants improve both halves; three are lone points whose neighbours fail, and the best one (skip a sweep made by one huge 5m bar with no pause before it) changes only 2 trades per half. The session rules (Asia direction carries into London, London into NY, no inducement before NY) and the Smart Money Trap (untaken liquidity right beside the zone) all cost money or eval passes in at least one half. Carrying Asia theses into the 02:00 order window helps Jul-Oct and hurts Jan-Jun. LIT live stays as it is. Paper only.

## Money first

- **Nothing passes.** The forceful-sweep skip is the only rule worth keeping an eye on. It is cheap to code and has a clear
  story (a forceful sweep without a pause tends to continue). But it changes 2 trades per half and its neighbours fail.
  - If it is ever wanted, it would be a default-off option on the setup filter: skip when the largest 5m bar between the
    sweep bar and the extreme is ≥ 2.5 ATR and the 6 bars before the sweep span more than 2.5 ATR.
  - It is not implemented in the engine, and `live_model.json` is unchanged.
- The report's own caution fits these results: boundary and trap labels depend on the selector chosen, and a selector
  picked after seeing the outcome would be the "hidden decision" the report warns about.
- **LIT live is unchanged:**
  - 2026 +$41,734, PF 3.66, 2.91 trades a week;
  - under two_week sizing, 2-week pass H1 52.9% / H2 50.7%;
  - **H2 about $2,400-2,800 a month.**

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-losses|LIT losses]]
- Runs: `lit_adv_base, lit_adv_forceful_bar_2_5_atr_without_a_pause_6_bar_range, lit_adv_forceful_bar_2_0_atr_without_a_pause_6_bar_range, lit_adv_own_smt_trap_half_when_an_unbroken_15m_swing_sit, lit_adv_on_the_way_untaken_major_level_2_0_atr_beyond_th, lit_adv_bos15_half_intact, lit_adv_bos1h_half_broken, `
- Source: `research/writeups/lit-adv-continuation.md`
- Back to [[ZEUS Home]]
