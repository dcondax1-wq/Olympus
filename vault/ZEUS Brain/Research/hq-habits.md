---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-24"
status: "rejected"
source: "research/writeups/hq-habits.md"
aliases:
  - "HQ habits"
---

# HQ habits

> [!failure] Verdict: rejected
> rejected

**Full title:** HQ habits - four "what a successful trader does" rules on LIT (news blackout, house-money sizing, cool-off after losses, a weekday / hour self-check)

## Summary

Four habits that successful discretionary traders swear by were backtested on today's live LIT and on the hq-lit candidate set (cisd1m 22 + room_f 0.55 + wk_loss_usd 1200, with and without scale-in), 18 pre-declared variants x 3 bases = 54 tests, money on the LIT size rule ($1.90 a micro) and on the two_week eval path of the MFFU Builder 50K and 25K. None of them makes money that holds up. (1) News blackout (CPI, NFP, FOMC statement + presser, PCE, GDP; 15/30/60 min, skip or half size) touches only 1-3 of the 120 trades in 2026 and none in Jul-Oct, because LIT enters mostly 02:00-08:00. The 15-minute blackout passes the gate on the live rules (+$486 H1, H2 unchanged), but that is one NFP-day stop-out, not evidence; on the scale-in set the same single skip costs $10.5k of H1 eval-path money. Harmless, not a money rule. (2) House-money sizing makes more raw money on the eval path (+$4.4k / +$0.9k on the 50K live) but raises the 2-week fails or lowers the passes in every base; scaling down when the eval is below start costs up to 15 points of 2-week passes; classic house money without two_week halves the passes. Today's two_week sizing is already the better cushion rule. (3) Cool-off (half size after 2 or 3 losses in a row) never improves both halves of the LIT money; the best one (2 losses, reset on any non-loss) cuts the 50K H1 2-week fails 5.9% -> 0.0% but loses $835 in H2 and 2.5 points of H1 passes, and the combo's weekly loss stop already gets the fails to 0. (4) The Sunday self-check halves nothing in 2026 when it learns from 2026 only (no weekday or hour bucket reached 15 trades with a loss), and when it learns from 2021-25 it halves Monday/Thursday and the 02/05/06/10 o'clock hours and costs $3-7k of H1 and $0.9-1.0k of H2. Verdict: adopt none; keep the news blackout only as a possible comfort rule (it changes ~1 trade a year).

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-24]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-learning-loop|LIT learning loop]]
- Runs: `hq_habit_base_combo, hq_habit_base_combo_eval, hq_habit_base_combo_eval25, hq_habit_base_combo_scale, hq_habit_base_combo_scale_eval, hq_habit_base_combo_scale_eval25, hq_habit_base_live, hq_habit_base_live_eval, hq_habit_base_live_eval25, hq_habit_cool2_any, hq_habit_cool2_any_eval, hq_habit_cool2_`
- Source: `research/writeups/hq-habits.md`
- Back to [[ZEUS Home]]
