---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-two-week-eval.md"
aliases:
  - "LIT two-week eval"
---

# LIT two-week eval

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT two-week eval - how to pass the MFFU 50K in 10 sessions or less

## Summary

The owner's order is that an MFFU eval must pass within 2 weeks (10 sessions), so the eval mode was rebuilt for that one number, using the exact live LIT trades (same signals, same 1m entries, same stops). The new idea is "one winner passes" sizing. Each trade is sized so that, if it reaches its target, it covers what is still missing to +$3,000. The caps are the room to the max-loss floor, the $1,000 soft daily loss and 40 micros. Fixed $ schemes, a clock press, profit protection, more LIT shots a day, an earlier window and start-timing rules were tested next to it. Today's eval mode passes 40% of Jan-Jun starts and 25% of Jul-Oct starts within 10 sessions (cost per 2-week pass $228 / $373). The recommended config (one winner passes, all the room, weekly stop on) passes 58% / 54% (Monte Carlo 51% / 57%), so a 2-week pass costs $158-171 at $91.80. The price is that 18-22% of evals fail within 2 weeks instead of 0-3%. A safer option (60% of the room, no weekly stop) passes 53% / 51% with only 3-8% failing ($174-181). No config gets past about 55-59%. LIT's ceiling is about 70%: that is the share of 10-session windows where at least one target is hit and a perfect hindsight sizing could pass. More LIT shots and an earlier window do not help. Start timing is not proven. Paper only; nothing live was changed.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-experiments|LIT experiments]], [[lit-live-fills|LIT live fills]], [[lit-tight-stops-size|LIT tight stops and bigger size]]
- Runs: `lit_2wk_max_plain, lit_2wk_max, lit_2wk_press, lit_2wk_rec, lit_2wk_safe, lit_2wk_eval_today, lit_2wk_fast_room, lit_2wk_big_fixed, lit_2wk_two_shots, lit_2wk_window0, lit_2wk_timing`
- Source: `research/writeups/lit-two-week-eval.md`
- Back to [[ZEUS Home]]
