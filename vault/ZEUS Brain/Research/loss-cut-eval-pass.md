---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/loss-cut-eval-pass.md"
aliases:
  - "Cutting losses to pass more MFFU evals"
---

# Cutting losses to pass more MFFU evals

> [!info] Verdict: finding
> finding

**Full title:** Cutting losses to pass more MFFU evals: what works, and how high the pass rate can go

## Summary

No loss-cut rule makes a big, proven difference. The best new idea, half size for the rest of the eval week after two losing trades in that week, lifts the pass rate of decided evals from 40% to 42% (2021-25) and 53% to 56% (5 years), makes a little more money in both periods (2026 +$289, 2021-25 +$828) and cuts 2021-25 1-month fails from 5.2% to 3.1%. Its neighbours agree, but the trades it shrinks are not worse than average, so it is a small safety rule, not an edge. The intraday package does not survive the critic: CISD x1.25 lowers the pass rate, and the 30-40 pt and equal-highs slices flip by year or by odd/even month. The math: with a 21% win rate, a +$542 average win and a -$114 average loss, 2021-25 passes about 40% of decided evals at today's size. 70-80% is only reachable in a 2026-like market (91% today), or by trading so small that one eval takes 6-12 months.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-17]]
- Refers to: [[eval-game|The eval game]], [[eval-sizing|Eval sizing]]
- Runs: `baseline, losscut_wk2loss_half, losscut_wkneg2_half, losscut_wk2loss_q25, losscut_wk2loss_q75, losscut_wk2loss_skip, losscut_wk1loss_half, losscut_wk3loss_half, losscut_loss2_half, losscut_wk200_half, losscut_wk300_half, losscut_wk400_half, losscut_wk500_half, losscut_wk800_half, losscut_wk500_skip,`
- Source: `research/writeups/loss-cut-eval-pass.md`
- Back to [[ZEUS Home]]
