---
tags:
  - zeus/research
  - family/management
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-loss-learning.md"
aliases:
  - "LIT loss learning"
---

# LIT loss learning

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT loss learning - the 15-minute check, and what the losses can't tell us

## Summary

Every 2026 LIT trade was re-played on its true 1-minute path and scored on the number that matters most, the MFFU 50K 2-week pass rate under the live two-week sizing (config C). One rule holds in both halves. The 15-minute check: 15 minutes after the fill, if the trade has never been +0.5R in profit and the 1m close is more than 0.3R below the entry, get out at the next 1m open. It cut 13 trades in 2026, all of them would-be full stop-outs, at about -0.45R instead of -1R, and touched no winner. 2-week pass H1 52.9% -> 57.1% and H2 50.7% -> 52.2%; 2-week fails 8.4% -> 5.9% and 2.9% -> 0%; the Monte Carlo agrees in both halves; eval-path money +$4.4k (H1) and +$5.0k (H2). Its neighbours (0.25-0.4R, +0.3-0.7R, minute 15-20) agree. Checking earlier (5-12 min) or later (25-30 min), or keeping the check on after minute 15, kills slow winners in Jul-Oct. Everything else failed: wider stops (stop-outs are not stop hunts), tightening the stop with time, scratching after a small profit, sequence memory (after a loss in the same direction, the same level type or the day before), and a walk-forward context model (no skill out of sample). Small sample (13 trades), so it is an adopt-candidate for after the launch, not before.

## Links

- Family: [[Family management]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-live-fills|LIT live fills]], [[lit-trade-selection|LIT trade selection]]
- Runs: `lit_ll_t15, lit_ll_t15_win, lit_ll_cont15, lit_ll_cont10, lit_ll_t25, lit_ll_t5, lit_ll_tighten60, lit_ll_scratch07, lit_ll_wide2, lit_ll_seq_samedir, lit_ll_model, lit_2wk_rec`
- Source: `research/writeups/lit-loss-learning.md`
- Back to [[ZEUS Home]]
