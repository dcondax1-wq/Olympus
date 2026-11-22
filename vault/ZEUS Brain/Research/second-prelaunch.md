---
tags:
  - zeus/research
  - family/risk
  - verdict/info
  - bot/atlas
type: "research"
date: "2026-10-22"
status: "info (scorecard built and on the dashboards; no rule change)"
source: "research/writeups/second-prelaunch.md"
aliases:
  - "Account B before launch"
---

# Account B before launch

> [!note] Verdict: info
> info (scorecard built and on the dashboards; no rule change)

**Full title:** Account B before launch - stress test, go / no-go scorecard and a bad-market brake (none adopted)

## Summary

Owner (2026-10-22) - "What else can we do before launching this other strategy?" Three checks for account B (EMA + MACD + S/R on their own MFFU account). 1) Stress test - each strategy re-run by its own research code on worse data. Price noise of +/-1 tick keeps about 87-104% of the 2026 money; 0-3 ticks of extra slippage keeps 97-99%; missing 20% of the trades keeps about 80%. Account B on a Builder 25K keeps its 2026 2-week pass rate at 61-68% (H1) and 41-43% (H2) under all of these, with no hard fails. The one weak spot is a late entry. Entering one 5-minute bar late cuts the 2026 money to about 4-75% (S/R loses money in H2). Account B's 2-week pass rate then drops to 49.6% (H1) and 31.9% (H2). The bot enters about 2 seconds after the bar opens and skips a trade rather than enter it more than 45 s late, so a late fill becomes a missed trade (which the test shows is fine). 2) Go / no-go scorecard - built, and shown on the phone and PC Second strategies pages and in the cloud README. It compares the paper ledger with a bootstrap of the 2026 H2 trades. Go live only after 20+ finished paper trades at or above the expected p10. Under p5 means don't go live. For account B after 20 trades the expected cumulative R is -0.1R to +22.0R (median +9.7R); a 2025-like year has a median of +2.4R. 3) Bad-market brake - 57 simple rules tested, picked on 2025 + 2021-24 and checked on 2026: size cuts after losses, a weekly pause, a VIX/VXN regime size and a softer "stuck" rule. Several halve the dead evals in 2021-25 (35% to 13-20%) and leave 2026 alone, but they also cut 2-week passes by 5-15 points. In real money (passes x funded $ minus evals bought) none is better by more than about $1,600 over 5 years. None is adopted and nothing is built; the scorecard is the brake.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-22]]
- Strategies: [[ATLAS]]
- Refers to: [[second-account-b|Account B]]
- Runs: `sb_robust_base, sb_robust_noise1, sb_robust_noise2, sb_robust_slip03, sb_robust_miss10, sb_robust_miss20, sb_robust_late1, sb_robust_late2, sb_robust_worst, sb_brake_base, sb_brake_vxn20_99, sb_brake_sum8_q, sb_brake_wk4, sb_brake_vix0_35`
- Source: `research/writeups/second-prelaunch.md`
- Back to [[ZEUS Home]]
